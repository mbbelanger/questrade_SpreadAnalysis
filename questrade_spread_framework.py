
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

    # Reload the .env file to get the latest token before each run
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
    return {
        "Authorization": f"Bearer {ACCESS_TOKEN}"
    }

def search_symbol(symbol):
    url = f"{API_SERVER}v1/symbols/search?prefix={symbol}"
    response = requests.get(url, headers=get_headers())
    data = response.json()
    if not data["symbols"]:
        raise Exception("Symbol not found.")
    return data["symbols"][0]

def get_option_chain(symbol_id):
    url = f"{API_SERVER}v1/options/chain?underlyingId={symbol_id}"
    response = requests.get(url, headers=get_headers())
    return response.json()

def simulate_bull_call_spread(option_chain):
    option_pairs = option_chain.get("optionPairs", [])
    call_options = [o for o in option_pairs if o["optionRight"] == "Call"]

    if not call_options:
        log("No call options found.")
        return

    call_options = sorted(call_options, key=lambda x: x["strikePrice"])
    mid_index = len(call_options) // 2
    buy_leg = call_options[mid_index]
    sell_leg = next((c for c in call_options[mid_index+1:] if c["strikePrice"] >= buy_leg["strikePrice"] + 2), None)

    if not sell_leg:
        log("No suitable higher strike found for spread.")
        return

    # Fallback prices if bid/ask are missing
    buy_price = buy_leg.get("askPrice") or buy_leg.get("lastTradePrice") or 0.00
    sell_price = sell_leg.get("bidPrice") or sell_leg.get("lastTradePrice") or 0.00

    net_debit = buy_price - sell_price
    max_profit = sell_leg["strikePrice"] - buy_leg["strikePrice"] - net_debit

    log(f"Bull Call Spread:")
    log(f"  BUY {buy_leg['strikePrice']} Call @ {buy_price}")
    log(f"  SELL {sell_leg['strikePrice']} Call @ {sell_price}")
    log(f"  Net Debit: ${net_debit:.2f}, Max Profit: ${max_profit:.2f}")

def main():
    refresh_access_token()
    symbol_data = search_symbol("QQQ")
    log(f"Symbol: {symbol_data['symbol']} (ID: {symbol_data['symbolId']})")
    option_chain = get_option_chain(symbol_data["symbolId"])
    simulate_bull_call_spread(option_chain)

if __name__ == "__main__":
    main()
