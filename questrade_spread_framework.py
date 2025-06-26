
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
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}")

def refresh_access_token():
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
        log("✅ Saved new refresh token to .env")
    else:
        log("⚠️ No new refresh token returned by Questrade")

    log("Access token refreshed successfully.")

def get_headers():
    return {"Authorization": f"Bearer {ACCESS_TOKEN}"}

def search_symbol(symbol):
    url = f"{API_SERVER}v1/symbols/search?prefix={symbol}"
    response = requests.get(url, headers=get_headers())
    data = response.json()
    if not data["symbols"]:
        raise Exception("Symbol not found.")
    return data["symbols"][0]

def get_expiries(symbol_id):
    url = f"{API_SERVER}v1/symbols/{symbol_id}/options"
    response = requests.get(url, headers=get_headers())
    data = response.json()

    print("🟡 Full chain response:", data)

    # Directly return the top-level option expiry dates
    if "optionExpiryDates" in data:
        expiries = sorted(data["optionExpiryDates"])
        return expiries
    else:
        raise Exception("No optionExpiryDates found in response.")


def get_option_quotes(symbol_id, expiry):
    url = f"{API_SERVER}v1/options/quotes?underlyingId={symbol_id}&expiryDate={expiry}"
    response = requests.get(url, headers=get_headers())
    return response.json().get("optionQuotes", [])

def simulate_bull_call_spread(quotes):
    calls = [q for q in quotes if q["optionRight"] == "Call" and q["askPrice"] and q["bidPrice"]]
    if not calls:
        log("No valid call options found.")
        return

    calls = sorted(calls, key=lambda x: x["strikePrice"])
    mid_index = len(calls) // 2
    buy_leg = calls[mid_index]
    sell_leg = next((c for c in calls[mid_index+1:] if c["strikePrice"] >= buy_leg["strikePrice"] + 2), None)

    if not sell_leg:
        log("No suitable higher strike found.")
        return

    net_debit = buy_leg["askPrice"] - sell_leg["bidPrice"]
    max_profit = sell_leg["strikePrice"] - buy_leg["strikePrice"] - net_debit

    log(f"Bull Call Spread:")
    log(f"  BUY {buy_leg['strikePrice']} Call @ {buy_leg['askPrice']}")
    log(f"  SELL {sell_leg['strikePrice']} Call @ {sell_leg['bidPrice']}")
    log(f"  Net Debit: ${net_debit:.2f}, Max Profit: ${max_profit:.2f}")

def main():
    refresh_access_token()
    symbol_data = search_symbol("QQQ")
    symbol_id = symbol_data["symbolId"]
    log(f"Symbol: {symbol_data['symbol']} (ID: {symbol_id})")

    expiries = get_expiries(symbol_id)
    if not expiries:
        raise Exception("No expiries found.")
    nearest_expiry = expiries[0].split("T")[0]
    log(f"Using nearest expiry: {nearest_expiry}")

    option_quotes = get_option_quotes(symbol_id, nearest_expiry)
    simulate_bull_call_spread(option_quotes)

if __name__ == "__main__":
    main()
