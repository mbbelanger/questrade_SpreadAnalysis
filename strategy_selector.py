import requests
import csv
import json
from datetime import datetime
from trend_analysis import detect_market_trend
from questrade_utils import (
    log, refresh_access_token, get_headers, search_symbol,
    is_valid_quote, ACCESS_TOKEN, API_SERVER
)
import questrade_utils
import config
    
def calculate_iv_rank(symbol_id, symbol_str):
    """
    Return a float 0–1 representing IV rank using ATM options.
    Falls back to 0.55 if no valid options with IV are found.
    Only considers the 6 strikes closest to ATM.
    """
    try:
        # 1. Fetch the full option chain
        chain_url = f"{questrade_utils.API_SERVER}v1/symbols/{symbol_id}/options"
        chain = requests.get(chain_url, headers=get_headers()).json()
        root = chain["optionChain"][0]["chainPerRoot"][0]
        strikes = root["chainPerStrikePrice"]
        if not strikes:
            raise Exception("Empty strike list")

        # 2. Fetch underlying price (for ATM proximity)
        underlying_q = requests.get(
            f"{questrade_utils.API_SERVER}v1/markets/quotes/{symbol_id}", headers=get_headers()
        ).json()["quotes"][0]
        underlying_px = underlying_q.get("lastTradePrice") or underlying_q.get("price")

        # 3. Sort strikes by closeness to ATM
        strikes_sorted = sorted(strikes, key=lambda s: abs(s["strikePrice"] - underlying_px))

        # 4. Try the 6 closest strikes to find valid quotes with IV
        for s in strikes_sorted[:6]:
            call_id = s.get("callSymbolId") or s.get("call", {}).get("symbolId")
            put_id  = s.get("putSymbolId")  or s.get("put",  {}).get("symbolId")
            ids = [str(i) for i in (call_id, put_id) if i]
            if not ids:
                continue

            # 5. Fetch Quotes
            quote_url = f"{questrade_utils.API_SERVER}v1/markets/quotes?ids={','.join(ids)}"
            quotes_resp = requests.get(quote_url, headers=get_headers()).json()
            quotes = quotes_resp.get("quotes", [])
            if not quotes:
                log(f"❌ 'quotes' key missing in response from: {quote_url}")
                continue

            with open(f"temp-{symbol_str.upper()}-{s['strikePrice']}-quotes.json", "w") as f:
                json.dump(quotes, f, indent=2)

            # 6. Fetch Greeks
            greeks_url = f"{questrade_utils.API_SERVER}v1/markets/options/greeks?optionIds={','.join(ids)}"
            greeks_resp = requests.get(greeks_url, headers=get_headers()).json()
            greeks = greeks_resp.get("optionGreeks", [])
            # Instead of raising an exception, fallback to volume-based IV estimate
            if not greeks:
                log(f"❌ No greeks returned from: {greeks_url}")
                # TEMP fallback: estimate IV rank using quote volume and price only
                ivs = []
                for q in quotes:
                    if is_valid_quote(q) and q.get("volume"):
                        # Estimate IV proxy using normalized bid/ask (just a crude proxy)
                        spread = q.get("askPrice", 0) - q.get("bidPrice", 0)
                        mid = (q.get("askPrice", 0) + q.get("bidPrice", 0)) / 2
                        if mid > 0 and spread / mid < 0.5:  # Tight spread
                            ivs.append(spread / mid)

                if ivs:
                    iv_proxy = sum(ivs) / len(ivs)
                    iv_rank = (iv_proxy - 0.1) / (0.3 - 0.1)
                    return round(max(0, min(1, iv_rank)), 2)

                continue


            with open(f"temp-{symbol_str.upper()}-{s['strikePrice']}-greeks.json", "w") as f:
                json.dump(greeks, f, indent=2)

            greeks_by_id = {g["optionId"]: g for g in greeks}

            # 7. Match valid quotes to Greeks and extract volatility
            ivs = []
            for q in quotes:
                if not is_valid_quote(q):
                    continue
                g = greeks_by_id.get(q["symbolId"])
                if g and g.get("volatility"):
                    ivs.append(g["volatility"])

            if ivs:
                current_iv = sum(ivs) / len(ivs)
                iv_low, iv_high = current_iv * 0.5, current_iv * 1.5
                iv_rank = (current_iv - iv_low) / (iv_high - iv_low)
                return round(max(0, min(1, iv_rank)), 2)

        raise Exception("No valid options with IV found in nearest strikes")

    except Exception as e:
        log(f"⚠️ IV fetch failed for {symbol_str}: {e}")
        return 0.55  # fallback IV rank


def select_strategy(trend: str, iv_rank: float) -> str:
    if trend == "bullish":
        if iv_rank < config.IV_LOW_THRESHOLD:
            return "bull_call_spread"
        elif iv_rank < config.IV_HIGH_THRESHOLD:
            return "long_call"
        else:
            return "call_ratio_backspread"
    elif trend == "bearish":
        if iv_rank < config.IV_LOW_THRESHOLD:
            return "bear_put_spread"
        elif iv_rank < config.IV_HIGH_THRESHOLD:
            return "long_put"
        else:
            return "put_ratio_backspread"
    elif trend == "neutral":
        if iv_rank < config.IV_LOW_THRESHOLD:
            return "calendar_spread"
        elif iv_rank < config.IV_HIGH_THRESHOLD:
            return "straddle"
        else:
            return "iron_condor"
    return "hold_cash"

def main():
    import os

    # Validate watchlist file exists
    if not os.path.exists(config.WATCHLIST_FILE):
        log(f"❌ ERROR: Watchlist file '{config.WATCHLIST_FILE}' not found!")
        log(f"   Please create {config.WATCHLIST_FILE} with one ticker per line.")
        return

    refresh_access_token()
    log(f"🔍 API_SERVER = {questrade_utils.API_SERVER}")

    with open(config.WATCHLIST_FILE) as f:
        tickers = [line.strip().upper() for line in f if line.strip()]

    if not tickers:
        log(f"⚠️ WARNING: No tickers found in {config.WATCHLIST_FILE}")
        return

    log(f"📋 Processing {len(tickers)} ticker(s): {', '.join(tickers)}")

    output_file = config.STRATEGY_OUTPUT_FILE
    with open(output_file, "w", newline="") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(["symbol", "symbol_id", "trend", "iv_rank", "strategy", "timestamp"])

        for ticker in tickers:
            try:
                symbol_data = search_symbol(ticker)
                symbol_id = symbol_data["symbolId"]
                trend = detect_market_trend(symbol_id, questrade_utils.API_SERVER, questrade_utils.ACCESS_TOKEN)
                iv_rank = calculate_iv_rank(symbol_id, ticker)

                strategy = select_strategy(trend, iv_rank)
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                log(f"{ticker}: Trend={trend}, IV Rank={iv_rank:.2f} => Strategy: {strategy}")
                writer.writerow([ticker, symbol_id, trend, iv_rank, strategy, timestamp])

            except Exception as e:
                log(f"{ticker}: Error - {e}")

if __name__ == "__main__":
    main()
