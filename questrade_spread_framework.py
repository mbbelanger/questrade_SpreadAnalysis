
import requests
from questrade_utils import (
    log, refresh_access_token, get_headers, search_symbol
)
import questrade_utils

def get_expiries(symbol_id):
    url = f"{questrade_utils.API_SERVER}v1/symbols/{symbol_id}/options"
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
    url = f"{questrade_utils.API_SERVER}v1/options/quotes?underlyingId={symbol_id}&expiryDate={expiry}"
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
