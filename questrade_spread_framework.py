
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

    try:
        expiries = set()
        chain_roots = data.get("optionChain", [])[0].get("chainPerRoot", [])

        for root in chain_roots:
            strike_chains = root.get("chainPerStrikePrice", [])
            for strike_entry in strike_chains:
                expiry = strike_entry.get("expiryDate")
                if expiry:
                    expiries.add(expiry)

        if not expiries:
            raise Exception("No expiryDates found in chainPerStrikePrice.")

        return sorted(expiries)

    except Exception as e:
        raise Exception(f"Failed to extract expiries: {e}")

def get_option_quotes(symbol_id, expiry):
    url = f"{API_SERVER}v1/options/quotes?underlyingId={symbol_id}&expiryDate={expiry}"
    response = requests.get(url, headers=get_headers())
    return response.json().get("optionQuotes", [])

def score_spread(buy, sell):
    net_debit = buy["askPrice"] - sell["bidPrice"]
    width = sell["strikePrice"] - buy["strikePrice"]
    if net_debit <= 0 or width <= 0:
        return float("-inf")
    return (width - net_debit) / net_debit

def best_bull_call(quotes):
    calls = [q for q in quotes if q["optionRight"] == "Call" and q["askPrice"] and q["bidPrice"]]
    calls = sorted(calls, key=lambda x: x["strikePrice"])
    best = (None, None, float("-inf"))

    for i in range(len(calls)):
        for j in range(i+1, len(calls)):
            if calls[j]["strikePrice"] - calls[i]["strikePrice"] < 1:
                continue
            score = score_spread(calls[i], calls[j])
            if score > best[2]:
                best = (calls[i], calls[j], score)

    return best if best[0] and best[1] else None

def main():
    refresh_access_token()

    with open("watchlist.txt") as f:
        tickers = [line.strip() for line in f if line.strip()]

    for ticker in tickers:
        try:
            symbol_data = search_symbol(ticker)
            symbol_id = symbol_data["symbolId"]
            expiries = get_expiries(symbol_id)
            nearest_expiry = expiries[0].split("T")[0]
            quotes = get_option_quotes(symbol_id, nearest_expiry)
            result = best_bull_call(quotes)

            if result:
                buy, sell, score = result
                net_debit = buy["askPrice"] - sell["bidPrice"]
                width = sell["strikePrice"] - buy["strikePrice"]
                log(f"{ticker} {nearest_expiry}: BUY {buy['strikePrice']}C @{buy['askPrice']} / SELL {sell['strikePrice']}C @{sell['bidPrice']} | Width={width}, Debit={net_debit:.2f}, RR={score:.2f}")
            else:
                log(f"{ticker}: No valid bull call spread found.")

        except Exception as e:
            log(f"{ticker}: Error - {str(e)}")

if __name__ == "__main__":
    main()
