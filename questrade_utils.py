"""
Shared utilities for Questrade API interaction
"""
import os
import requests
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

REFRESH_TOKEN = os.getenv("QUESTRADE_REFRESH_TOKEN")
BASE_URL = "https://login.questrade.com"
ACCESS_TOKEN = None
API_SERVER = None

def log(msg):
    """Log a timestamped message to console"""
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}")

def refresh_access_token():
    """
    Refresh the Questrade API access token using the refresh token from .env
    Automatically saves new refresh token back to .env file
    Returns: tuple of (access_token, api_server)
    """
    global ACCESS_TOKEN, API_SERVER, REFRESH_TOKEN
    load_dotenv(override=True)
    REFRESH_TOKEN = os.getenv("QUESTRADE_REFRESH_TOKEN")

    if not REFRESH_TOKEN:
        raise Exception("Refresh token not found in .env file")

    url = f"{BASE_URL}/oauth2/token"
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    data = {
        "grant_type": "refresh_token",
        "refresh_token": REFRESH_TOKEN
    }

    response = requests.post(url, headers=headers, data=data)
    if response.status_code != 200:
        raise Exception(f"Token refresh failed: {response.text}")

    data = response.json()
    ACCESS_TOKEN = data["access_token"]
    API_SERVER = data["api_server"]
    new_refresh_token = data.get("refresh_token")

    if new_refresh_token:
        with open(".env", "w") as f:
            f.write(f"QUESTRADE_REFRESH_TOKEN={new_refresh_token}\n")
        log("[OK] Saved new refresh token to .env")
    else:
        log("[WARNING] No new refresh token returned by Questrade")

    log("Access token refreshed successfully.")
    return ACCESS_TOKEN, API_SERVER

def get_headers():
    """Get authorization headers for API requests"""
    return {"Authorization": f"Bearer {ACCESS_TOKEN}"}

def search_symbol(symbol):
    """Search for a symbol and return symbol data"""
    url = f"{API_SERVER}v1/symbols/search?prefix={symbol}"
    response = requests.get(url, headers=get_headers())
    data = response.json()
    if not data["symbols"]:
        raise Exception("Symbol not found.")
    return data["symbols"][0]

def chunk(lst, size):
    """Split a list into chunks of specified size"""
    for i in range(0, len(lst), size):
        yield lst[i:i + size]

def is_valid_quote(q):
    """Check if a quote has sufficient volume and reasonable bid-ask spread"""
    return (
        q.get("volume", 0) > 10 and
        q.get("bidPrice") and q.get("askPrice") and
        abs(q["askPrice"] - q["bidPrice"]) < q["bidPrice"] * 0.3  # spread < 30%
    )
