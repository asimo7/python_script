import requests
from flask import Flask, jsonify
from flask_socketio import SocketIO
import time
import random
from flask_cors import CORS
from collections import defaultdict
from datetime import datetime, timezone
import json
import pandas as pd
import os

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})  # Enable CORS for all domains
# Create the SocketIO instance and allow the same origin
socketio = SocketIO(app, cors_allowed_origins="*")

# Load API Token and other environment variables
API_TOKEN = os.getenv("API_TOKEN")  # Your API token from your stock data provider (if any)
BACKEND_HOST = os.getenv("HOST", "0.0.0.0")  # Default host for Flask
BACKEND_PORT = int(os.getenv("PORT", 5000))  # Default port

# Alpha Vantage API configuration (if you need to use this as an API for fetching stocks)
def get_stocks():
    # Reading stock data from an Excel file (or any other source)
    stocks_elements = pd.read_excel('myr_data.xlsx')  # Make sure this file exists on your server
    stocks_elements['Code'] = stocks_elements['Code'].astype(str) + ".KLSE"  # Add suffix to stock codes
    symbol_list = stocks_elements['Code'].tolist()  # List of stock symbols
    name_list = stocks_elements['Name'].tolist()  # List of stock names
    return symbol_list[:1], name_list[:1]  # Limiting to first 2 stocks for testing

def get_warrant_data(symbols, name):
    access_key = "67413dc0158284.44313462"  # Replace with your access key from the external stock API
    BASE_URL = "https://eodhistoricaldata.com/api/real-time/"
    
    latest_data = defaultdict(lambda: None)
    last_close = defaultdict(lambda: None)  # To store the last close value for each symbol
    
    # Join the list of symbols into a comma-separated string
    symbols_str = ",".join(symbols[1:])
    url = f'{BASE_URL}{symbols[0]}?s={symbols_str}&api_token={access_key}&fmt=json'
    
    # Fetch data from the external API
    response = requests.get(url)
    api_data = response.json()
    
    # Processing the data
    counter = 0
    for entry in api_data:
        symbol = entry['code']
        nama = name[counter]
        counter += 1
        
        close_price = entry.get('close', None)
        if close_price is None:
            close_price = last_close[symbol]  # Use the last valid close if no new close price
        
        if close_price is not None:
            timestamp = int(entry['timestamp'])
            date = datetime.fromtimestamp(timestamp, timezone.utc)
            formatted_date = date.strftime('%Y-%m-%d %H:%M:%S')
            open_price = float(entry['open'])
            high_price = float(entry['high'])
            low_price = float(entry['low'])
            vol = int(entry['volume'])
            change = round(entry['change'], 2)
            percent_change = round(entry['change_p'], 2)
            vwap = round(((open_price + high_price + low_price + close_price) / 4) / vol, 5)
            turnover = round(vwap * vol, 5)

            # Store the last valid close price
            last_close[symbol] = close_price

            current_entry = {
                "date": formatted_date,
                "symbol": symbol,
                "name": nama,
                "price": close_price,
                "change": change,
                "percent_change": percent_change,
                "volume": vol,
                "VWAP": vwap,
                'TO': turnover
            }

            # Store the most recent data for the symbol
            latest_data[symbol] = current_entry

    return list(latest_data.values())

@socketio.on('connect')
def handle_connection():
    print("Client connected!")

@socketio.on('disconnect')
def handle_disconnection():
    print("Client disconnected!")

# Function to periodically fetch stock data and emit to frontend
def fetch_data():
    tickers, names = get_stocks()
    symbols = [ticker for ticker in tickers]  # List of stock symbols
    desc = [name for name in names]  # List of stock names
    while True:
        data = get_warrant_data(symbols, desc)  # Fetch real-time data
        print("Fetched data:", data)
        socketio.emit('warrant_update', data)  # Emit data to the frontend
        print("Emitted data to frontend")
        time.sleep(60)  # Delay between updates, set to 60 seconds for real-time updates

if __name__ == '__main__':
    socketio.start_background_task(fetch_data)  # Run fetch_data in the background as a task
    socketio.run(app, host='0.0.0.0', port=5000)