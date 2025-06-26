import os
import csv
import requests
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()
REFRESH_TOKEN = os.getenv("QUESTRADE_REFRESH_TOKEN")
BASE_URL = "https://login.questrade.com"
ACCESS_TOKEN = None
API_SERVER = None

STRATEGY_FILE = "strategy_output_latest.csv"  # Adjust if needed


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


def get_expiries(symbol_id):
    url = f"{API_SERVER}v1/symbols/{symbol_id}/options"
    response = requests.get(url, headers=get_headers())
    data = response.json()
    expiries = set()
    for chain in data.get("optionChain", []):
        for root in chain.get("chainPerRoot", []):
            for strike_entry in root.get("chainPerStrikePrice", []):
                expiry = strike_entry.get("expiryDate")
                if expiry:
                    expiries.add(expiry.split("T")[0])
    return sorted(expiries)


def get_option_quotes(symbol_id, expiry):
    url = f"{API_SERVER}v1/options/quotes?underlyingId={symbol_id}&expiryDate={expiry}"
    response = requests.get(url, headers=get_headers())
    return response.json().get("optionQuotes", [])


def score_straddle(quotes):
    atm_calls = [q for q in quotes if q["optionRight"] == "Call"]
    atm_puts = [q for q in quotes if q["optionRight"] == "Put"]
    if not atm_calls or not atm_puts:
        return None

    mid_call = sorted(atm_calls, key=lambda x: abs(x["delta"] - 0.5))[0]
    mid_put = sorted(atm_puts, key=lambda x: abs(x["delta"] + 0.5))[0]

    total_cost = mid_call.get("askPrice", 0) + mid_put.get("askPrice", 0)
    return mid_call, mid_put, total_cost


def process_strategy_file():
    with open(STRATEGY_FILE, newline='') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            symbol = row['symbol']
            symbol_id = int(row['symbol_id'])
            strategy = row['strategy']
            try:
                expiries = get_expiries(symbol_id)
                if not expiries:
                    log(f"{symbol}: No expiries found.")
                    continue
                expiry = expiries[0]  # Choose the nearest expiry
                quotes = get_option_quotes(symbol_id, expiry)

                if strategy == "straddle":
                    result = score_straddle(quotes)
                    if result:
                        call, put, cost = result
                        log(f"{symbol} {expiry}: STRADDLE - Buy {call['strikePrice']}C @{call['askPrice']} + {put['strikePrice']}P @{put['askPrice']} | Cost={cost:.2f}")
                    else:
                        log(f"{symbol}: No valid straddle found.")
                else:
                    log(f"{symbol}: Strategy '{strategy}' not yet implemented.")

            except Exception as e:
                log(f"{symbol}: Error processing strategy - {e}")


def main():
    refresh_access_token()
    log(f"🔍 API_SERVER = {API_SERVER}")
    process_strategy_file()


if __name__ == "__main__":
    main()
