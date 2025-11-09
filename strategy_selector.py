import requests
import csv
from datetime import datetime
from trend_analysis import detect_market_trend
from questrade_utils import (
    log, refresh_access_token, get_headers, search_symbol
)
import questrade_utils
import config

def calculate_iv_rank(symbol_id, symbol_str):
    """
    Calculate IV rank by sampling multiple strikes and expiries.

    IV Rank = (Current IV - Min IV) / (Max IV - Min IV)

    This improved version:
    - Samples multiple expiries (not just nearest)
    - Collects IV from multiple strikes across the chain
    - Uses the range of sampled IVs as proxy for historical range

    NOTE: True IV rank requires historical IV data (52-week percentile).
    This implementation uses cross-sectional IV data (multiple strikes/expiries)
    as a proxy. For production use, consider storing daily IV readings.

    Returns: float 0-1 representing IV rank (0=lowest, 1=highest)
    Falls back to 0.55 if insufficient data
    """
    try:
        # 1. Fetch the full option chain
        log(f"{symbol_str}: Fetching option chain...")
        chain_url = f"{questrade_utils.API_SERVER}v1/symbols/{symbol_id}/options"
        chain_resp = requests.get(chain_url, headers=get_headers(), timeout=10).json()

        # 2. Fetch underlying price
        log(f"{symbol_str}: Fetching underlying price...")
        underlying_q = requests.get(
            f"{questrade_utils.API_SERVER}v1/markets/quotes/{symbol_id}", headers=get_headers(), timeout=10
        ).json()["quotes"][0]
        underlying_px = underlying_q.get("lastTradePrice") or underlying_q.get("price")

        if not underlying_px:
            raise Exception("No underlying price available")

        # 3. Collect all option IDs across multiple expiries
        all_option_ids = []
        option_chain = chain_resp.get("optionChain", [])

        for chain_entry in option_chain:
            expiry = chain_entry.get("expiryDate", "").split("T")[0]
            if not expiry:
                continue

            chain_roots = chain_entry.get("chainPerRoot", [])
            for root in chain_roots:
                strikes = root.get("chainPerStrikePrice", [])

                # Sort by distance from ATM
                strikes_sorted = sorted(strikes, key=lambda s: abs(s.get("strikePrice", 0) - underlying_px))

                # Take closest 10 strikes to ATM for this expiry
                for strike in strikes_sorted[:10]:
                    call_id = strike.get("callSymbolId") or strike.get("call", {}).get("symbolId")
                    put_id = strike.get("putSymbolId") or strike.get("put", {}).get("symbolId")

                    if call_id:
                        all_option_ids.append(str(call_id))
                    if put_id:
                        all_option_ids.append(str(put_id))

        if not all_option_ids:
            raise Exception("No option IDs found in chain")

        # Limit to first 100 options to avoid overwhelming the API
        all_option_ids = list(dict.fromkeys(all_option_ids))[:100]
        log(f"{symbol_str}: Collected {len(all_option_ids)} option IDs, fetching Greeks...")

        # 4. Fetch Greeks in chunks
        all_ivs = []
        chunk_size = 50  # Conservative chunk size for Greeks endpoint

        for i in range(0, len(all_option_ids), chunk_size):
            chunk_ids = all_option_ids[i:i+chunk_size]
            greeks_url = f"{questrade_utils.API_SERVER}v1/markets/quotes/options"

            try:
                # Correct endpoint uses POST with optionIds in body
                log(f"{symbol_str}: Fetching Greeks chunk {i//chunk_size + 1}/{(len(all_option_ids)-1)//chunk_size + 1}...")
                payload = {"optionIds": [int(id) for id in chunk_ids]}
                greeks_resp = requests.post(greeks_url, json=payload, headers=get_headers(), timeout=15).json()
                greeks = greeks_resp.get("optionQuotes", [])

                # Collect IV values
                for g in greeks:
                    iv = g.get("volatility")
                    if iv and iv > 0:  # Ensure positive IV
                        all_ivs.append(iv)
            except Exception as chunk_error:
                log(f"[WARNING] Error fetching Greeks chunk: {chunk_error}")
                continue

        if len(all_ivs) < 5:
            raise Exception(f"Insufficient IV data (only {len(all_ivs)} values)")

        # 5. Calculate IV rank using collected data
        current_iv = sum(all_ivs[:10]) / min(10, len(all_ivs))  # Use average of first 10 (nearest ATM)
        min_iv = min(all_ivs)
        max_iv = max(all_ivs)

        # Calculate IV rank
        if max_iv > min_iv:
            iv_rank = (current_iv - min_iv) / (max_iv - min_iv)
        else:
            iv_rank = 0.5  # If no range, assume mid-rank

        # Log the calculation for transparency
        log(f"{symbol_str}: Current IV={current_iv:.3f}, Range=[{min_iv:.3f}, {max_iv:.3f}], Rank={iv_rank:.2f} (from {len(all_ivs)} samples)")

        return round(max(0, min(1, iv_rank)), 2)

    except Exception as e:
        log(f"[WARNING] IV rank calculation failed for {symbol_str}: {e}")
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
    from cleanup_utils import cleanup_temp_files

    # Validate watchlist file exists
    if not os.path.exists(config.WATCHLIST_FILE):
        log(f"❌ ERROR: Watchlist file '{config.WATCHLIST_FILE}' not found!")
        log(f"   Please create {config.WATCHLIST_FILE} with one ticker per line.")
        return

    # Clean up old temp files before starting
    if config.CLEANUP_TEMP_FILES:
        cleanup_temp_files(max_age_hours=24)

    refresh_access_token()
    log(f"API_SERVER = {questrade_utils.API_SERVER}")

    with open(config.WATCHLIST_FILE) as f:
        # Filter out empty lines and comments (lines starting with #)
        tickers = [
            line.strip().upper()
            for line in f
            if line.strip() and not line.strip().startswith('#')
        ]

    if not tickers:
        log(f"[WARNING] No tickers found in {config.WATCHLIST_FILE}")
        return

    log(f"Processing {len(tickers)} ticker(s): {', '.join(tickers)}")

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
