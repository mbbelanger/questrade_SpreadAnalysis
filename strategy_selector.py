import os
import requests
import csv
import random
from datetime import datetime
from dotenv import load_dotenv
from trend_analysis import detect_market_trend

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

def calculate_iv_rank(symbol_id, symbol_str):
    """
    Return a float 0-1 representing IV rank.
    Falls back to 0.55 if no IV could be found (e.g. after-hours).
    """
    try:
        # 1) Pull the full option chain
        chain_url = f"{API_SERVER}v1/symbols/{symbol_id}/options"
        chain = requests.get(chain_url, headers=get_headers()).json()
        root = chain["optionChain"][0]["chainPerRoot"][0]

        # 2) Pick the nearest expiry
        strikes = root["chainPerStrikePrice"]
        if not strikes:
            raise Exception("empty strike list")

        # Find ATM strike: strike closest to underlying price
        # Fetch underlying last price
        underlying_q = requests.get(
            f"{API_SERVER}v1/markets/quotes/{symbol_id}", headers=get_headers()
        ).json()["quotes"][0]
        underlying_px = underlying_q["lastTradePrice"] or underlying_q["price"]

        atm = min(strikes, key=lambda s: abs(s["strikePrice"] - underlying_px))

        call_id = atm.get("callSymbolId") or atm.get("call", {}).get("symbolId")
        put_id  = atm.get("putSymbolId")  or atm.get("put",  {}).get("symbolId")
        ids = [str(i) for i in (call_id, put_id) if i]

        if not ids:
            raise Exception("no option IDs")

        # 3) Get their quotes → grab IV
        qurl = f"{API_SERVER}v1/markets/quotes?ids={','.join(ids)}"
        quotes = requests.get(qurl, headers=get_headers()).json()["quotes"]
        ivs = [q["volatility"] for q in quotes if q.get("volatility")]

        if not ivs:
            raise Exception("IV missing in quotes")

        current_iv = sum(ivs) / len(ivs)

        # 4) Simulate rank (until you store real history)
        iv_low, iv_high = current_iv * 0.5, current_iv * 1.5
        iv_rank = (current_iv - iv_low) / (iv_high - iv_low)
        return round(max(0, min(1, iv_rank)), 2)

    except Exception as e:
        log(f"⚠️ IV fetch failed for {symbol_str}: {e}")
        return 0.55   # sensible fallback

def select_strategy(trend: str, iv_rank: float) -> str:
    if trend == "bullish":
        if iv_rank < 0.3:
            return "bull_call_spread"
        elif iv_rank < 0.6:
            return "long_call"
        else:
            return "call_ratio_backspread"
    elif trend == "bearish":
        if iv_rank < 0.3:
            return "bear_put_spread"
        elif iv_rank < 0.6:
            return "long_put"
        else:
            return "put_ratio_backspread"
    elif trend == "neutral":
        if iv_rank < 0.3:
            return "calendar_spread"
        elif iv_rank < 0.6:
            return "straddle"
        else:
            return "iron_condor"
    return "hold_cash"

def main():
    refresh_access_token()
    log(f"🔍 API_SERVER = {API_SERVER}")

    with open("watchlist.txt") as f:
        tickers = [line.strip().upper() for line in f if line.strip()]

    output_file = "strategy_output_latest.csv"
    with open(output_file, "w", newline="") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(["symbol", "symbol_id", "trend", "iv_rank", "strategy", "timestamp"])

        for ticker in tickers:
            try:
                symbol_data = search_symbol(ticker)
                symbol_id = symbol_data["symbolId"]
                trend = detect_market_trend(symbol_id, API_SERVER, ACCESS_TOKEN)
                iv_rank = calculate_iv_rank(symbol_id, ticker)

                strategy = select_strategy(trend, iv_rank)
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                log(f"{ticker}: Trend={trend}, IV Rank={iv_rank:.2f} => Strategy: {strategy}")
                writer.writerow([ticker, symbol_id, trend, iv_rank, strategy, timestamp])

            except Exception as e:
                log(f"{ticker}: Error - {e}")

if __name__ == "__main__":
    main()
