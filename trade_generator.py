import csv
import requests
import json
from time import sleep
from datetime import timedelta
from datetime import datetime
from questrade_utils import (
    log, refresh_access_token, get_headers, chunk
)
import questrade_utils
import config
from risk_analysis import (
    calculate_bull_call_spread_risk,
    calculate_bear_put_spread_risk,
    calculate_iron_condor_risk,
    calculate_straddle_risk,
    calculate_long_call_risk,
    calculate_long_put_risk,
    calculate_call_ratio_backspread_risk,
    calculate_put_ratio_backspread_risk,
    calculate_calendar_spread_risk,
    calculate_days_to_expiry,
    format_risk_analysis
)

STRATEGY_FILE = config.STRATEGY_OUTPUT_FILE


def get_expiries(symbol_id, retries=3):
    """
    Fetch option expiry dates with exponential backoff retry logic

    Args:
        symbol_id: Questrade symbol ID
        retries: Number of retry attempts (default: 3)

    Returns:
        List of expiry date strings
    """
    for attempt in range(retries):
        try:
            # Exponential backoff: 30s, 60s, 90s timeouts
            timeout = 30 + (attempt * 30)

            url = f"{questrade_utils.API_SERVER}v1/symbols/{symbol_id}/options"
            response = requests.get(url, headers=get_headers(), timeout=timeout)

            if response.status_code == 429:  # Rate limit
                wait_time = 5 * (attempt + 1)  # 5s, 10s, 15s
                log(f"[WARNING] Rate limited on {symbol_id}, waiting {wait_time}s before retry {attempt + 1}/{retries}")
                sleep(wait_time)
                continue

            data = response.json()

            with open(f"temp-chain-{symbol_id}.json", "w") as f:
                json.dump(data, f, indent=2)

            option_chain = data.get("optionChain", [])
            expiries = {
                entry.get("expiryDate", "").split("T")[0]
                for entry in option_chain
                if "expiryDate" in entry
            }

            if expiries:
                return sorted(expiries)

            log(f"[WARNING] No expiry dates in option chain for {symbol_id} on attempt {attempt + 1}/{retries}")

            if attempt < retries - 1:
                wait_time = 2 * (attempt + 1)
                log(f"[INFO] Waiting {wait_time}s before retry...")
                sleep(wait_time)

        except requests.exceptions.Timeout:
            log(f"[WARNING] Timeout fetching expiries for {symbol_id} on attempt {attempt + 1}/{retries} (timeout={timeout}s)")
            if attempt < retries - 1:
                wait_time = 5 * (attempt + 1)
                log(f"[INFO] Waiting {wait_time}s before retry...")
                sleep(wait_time)
        except Exception as e:
            log(f"[WARNING] Error fetching expiries for {symbol_id} on attempt {attempt + 1}/{retries}: {e}")
            if attempt < retries - 1:
                sleep(2)

    log(f"[ERROR] Failed to fetch expiries for {symbol_id} after {retries} attempts")
    return []

def get_option_quotes(symbol_id: int, expiry: str, window: int = 5, retries: int = 3):
    """
    Return quotes (incl. greeks) for ~±'window' strikes around ATM with retry logic.

    Args:
        symbol_id: Questrade symbol ID
        expiry: Expiry date string
        window: Percentage window around ATM (default: 5%)
        retries: Number of retry attempts (default: 3)

    Returns:
        List of option quote dictionaries
    """
    for attempt in range(retries):
        try:
            timeout = 30 + (attempt * 30)  # 30s, 60s, 90s

            # 1) full chain for the symbol
            url = f"{questrade_utils.API_SERVER}v1/symbols/{symbol_id}/options"
            response = requests.get(url, headers=get_headers(), timeout=timeout)

            if response.status_code == 429:  # Rate limit
                wait_time = 5 * (attempt + 1)
                log(f"[WARNING] Rate limited fetching chain for {symbol_id}, waiting {wait_time}s")
                sleep(wait_time)
                continue

            chain = response.json()

            # 2) underlying last price
            last_px = get_last_price(symbol_id, retries=retries)
            if last_px is None:
                log(f"{symbol_id}: no last price");  return []

            # 3) collect IDs close to ATM
            ids = []
            chain_entry = next((c for c in chain.get("optionChain", [])
                                 if expiry in c.get("expiryDate", "")), None)
            if not chain_entry:
                log(f"{symbol_id}: expiry {expiry} not in chain");  return []

            for root in chain_entry.get("chainPerRoot", []):
                for strike in root.get("chainPerStrikePrice", []):
                    sp = strike.get("strikePrice")
                    if sp is None:    continue
                    if abs(sp - last_px) / last_px > window / 100:   # e.g. ±5 %
                        continue
                    if strike.get("callSymbolId"): ids.append(str(strike["callSymbolId"]))
                    if strike.get("putSymbolId"):  ids.append(str(strike["putSymbolId"]))

            ids = list(dict.fromkeys(ids))          # deduplicate

            if not ids:
                log(f"{symbol_id}: no near-ATM option IDs");  return []

            # 4) fetch quotes in chunks, request greeks
            all_quotes = []
            for id_chunk in chunk(ids, 80):
                # Use correct POST endpoint for option quotes with Greeks
                qurl = f"{questrade_utils.API_SERVER}v1/markets/quotes/options"
                payload = {"optionIds": [int(id) for id in id_chunk]}

                quote_response = requests.post(qurl, json=payload, headers=get_headers(), timeout=timeout)

                if quote_response.status_code == 429:
                    wait_time = 5 * (attempt + 1)
                    log(f"[WARNING] Rate limited fetching quotes, waiting {wait_time}s")
                    sleep(wait_time)
                    continue

                qdata = quote_response.json()
                all_quotes.extend(qdata.get("optionQuotes", []))

            # 5) Add strikePrice field extracted from symbol name
            valid_quotes = []
            for quote in all_quotes:
                strike = get_strike_from_symbol(quote.get("symbol", ""))
                if strike is not None:
                    quote["strikePrice"] = strike
                    valid_quotes.append(quote)
                else:
                    log(f"[WARNING] Could not parse strike from symbol: {quote.get('symbol', 'unknown')}")

            # DEBUG: keep only 1 tiny file
            with open(f"temp-quotes-{symbol_id}-{expiry}.json", "w") as f:
                json.dump({"quotes": valid_quotes[:20]}, f, indent=2)   # first 20 rows

            return valid_quotes

        except requests.exceptions.Timeout:
            log(f"[WARNING] Timeout fetching quotes for {symbol_id} on attempt {attempt + 1}/{retries} (timeout={timeout}s)")
            if attempt < retries - 1:
                wait_time = 5 * (attempt + 1)
                log(f"[INFO] Waiting {wait_time}s before retry...")
                sleep(wait_time)
        except Exception as e:
            log(f"[WARNING] Error fetching quotes for {symbol_id} on attempt {attempt + 1}/{retries}: {e}")
            if attempt < retries - 1:
                sleep(2)

    log(f"[ERROR] Failed to fetch quotes for {symbol_id} after {retries} attempts")
    return []


def get_last_price(symbol_id, retries=3):
    """
    Fetch last trade price for a symbol with retry logic

    Args:
        symbol_id: Questrade symbol ID
        retries: Number of retry attempts (default: 3)

    Returns:
        Last trade price or None if failed
    """
    for attempt in range(retries):
        try:
            timeout = 30 + (attempt * 30)  # 30s, 60s, 90s
            url = f"{questrade_utils.API_SERVER}v1/markets/quotes?ids={symbol_id}"
            response = requests.get(url, headers=get_headers(), timeout=timeout)

            if response.status_code == 429:  # Rate limit
                wait_time = 5 * (attempt + 1)
                log(f"[WARNING] Rate limited fetching last price for {symbol_id}, waiting {wait_time}s")
                sleep(wait_time)
                continue

            return response.json().get("quotes", [{}])[0].get("lastTradePrice", None)

        except requests.exceptions.Timeout:
            log(f"[WARNING] Timeout fetching last price for {symbol_id} on attempt {attempt + 1}/{retries}")
            if attempt < retries - 1:
                wait_time = 5 * (attempt + 1)
                log(f"[INFO] Waiting {wait_time}s before retry...")
                sleep(wait_time)
        except Exception as e:
            log(f"[WARNING] Error fetching last price for {symbol_id} on attempt {attempt + 1}/{retries}: {e}")
            if attempt < retries - 1:
                sleep(2)

    log(f"[ERROR] Failed to fetch last price for {symbol_id} after {retries} attempts")
    return None

def categorize_expiries(expiries):
    """
    Categorize expiries into near-term, mid-term, and long-term buckets

    Args:
        expiries: List of expiry date strings (YYYY-MM-DD format)

    Returns:
        Dictionary with 'near', 'mid', 'long' keys containing expiry dates
    """
    from datetime import datetime

    today = datetime.now().date()
    result = {'near': None, 'mid': None, 'long': None}

    if not expiries:
        return result

    expiry_dates = []
    for exp_str in expiries:
        try:
            exp_date = datetime.strptime(exp_str, "%Y-%m-%d").date()
            days_out = (exp_date - today).days
            expiry_dates.append((exp_str, days_out))
        except ValueError:
            continue

    if not expiry_dates:
        return result

    # Sort by days to expiry
    expiry_dates.sort(key=lambda x: x[1])

    # Near-term: closest expiry
    result['near'] = expiry_dates[0][0]

    # Mid-term: 14-60 days out (2 weeks to 2 months)
    mid_candidates = [exp for exp, days in expiry_dates if 14 <= days <= 60]
    if mid_candidates:
        result['mid'] = mid_candidates[0]  # Take earliest in range
    elif len(expiry_dates) > 1:
        # Fallback: second available expiry if no mid-term range match
        result['mid'] = expiry_dates[1][0]

    # Long-term: 300-400 days out (~1 year, allowing some flexibility)
    long_candidates = [exp for exp, days in expiry_dates if 300 <= days <= 400]
    if long_candidates:
        result['long'] = long_candidates[0]  # Take earliest in range
    else:
        # Fallback: longest available expiry
        result['long'] = expiry_dates[-1][0]

    return result

def get_strike_from_symbol(symbol):
    """Extract strike price from option symbol (e.g., 'AAPL14Nov25C150.00' -> 150.00)"""
    # Symbol format: TICKER + DATE + C/P + STRIKE
    # Find 'C' or 'P' and extract everything after it
    if 'C' in symbol:
        parts = symbol.split('C')
        if len(parts) >= 2:
            try:
                return float(parts[-1])
            except (ValueError, IndexError):
                return None
    elif 'P' in symbol:
        parts = symbol.split('P')
        if len(parts) >= 2:
            try:
                return float(parts[-1])
            except (ValueError, IndexError):
                return None
    return None

def is_call_option(quote):
    """Check if option is a call based on symbol name (e.g., 'AAPL14Nov25C150.00')"""
    symbol = quote.get("symbol", "")
    # Symbol format: TICKER + DATE + C/P + STRIKE
    # Calls have 'C' after date, puts have 'P' after date
    # Split by 'C' and check if 'P' appears before it (if so, it's not a call)
    if 'C' in symbol:
        before_c = symbol.split('C')[0]
        return 'P' not in before_c
    return False

def is_put_option(quote):
    """Check if option is a put based on symbol name (e.g., 'AAPL14Nov25P150.00')"""
    symbol = quote.get("symbol", "")
    if 'P' in symbol:
        before_p = symbol.split('P')[0]
        return 'C' not in before_p
    return False

def score_straddle(quotes):
    atm_calls = [q for q in quotes if is_call_option(q)]
    atm_puts = [q for q in quotes if is_put_option(q)]
    if not atm_calls or not atm_puts:
        return None

    mid_call = sorted(atm_calls, key=lambda x: abs(x.get("delta", 0) - 0.5))[0]
    mid_put = sorted(atm_puts, key=lambda x: abs(x.get("delta", 0) + 0.5))[0]

    total_cost = mid_call.get("askPrice", 0) + mid_put.get("askPrice", 0)
    return mid_call, mid_put, total_cost

def calculate_iron_condor_limit_price(long_put, short_put, short_call, long_call):
    total_bid = (
        short_put.get("bidPrice", 0)
        + short_call.get("bidPrice", 0)
        - long_put.get("askPrice", 0)
        - long_call.get("askPrice", 0)
    )
    total_ask = (
        short_put.get("askPrice", 0)
        + short_call.get("askPrice", 0)
        - long_put.get("bidPrice", 0)
        - long_call.get("bidPrice", 0)
    )
    mid = (total_bid + total_ask) / 2
    return {
        "bid": total_bid,
        "ask": total_ask,
        "mid": mid
    }

def format_price(p):
    return f"{p:.2f}" if p is not None else "N/A"

def process_bull_call_spread(symbol, symbol_id, expiry, expiry_label, writer):
    """Process bull call spread for a specific expiry"""
    quotes = get_option_quotes(symbol_id, expiry)
    log(f"{symbol}: Retrieved {len(quotes)} quotes for {expiry_label} expiry {expiry}")

    if not quotes:
        log(f"{symbol}: No option quotes found for expiry {expiry}")
        return False

    atm_call = min([q for q in quotes if is_call_option(q)], key=lambda x: abs(x.get("delta", 0) - 0.5), default=None)
    if not atm_call:
        log(f"{symbol}: No ATM call for bull call spread.")
        return False

    otm_calls = [q for q in quotes if is_call_option(q) and q["strikePrice"] > atm_call["strikePrice"]]
    otm_call = min(otm_calls, key=lambda x: abs(x["strikePrice"] - (atm_call["strikePrice"] + config.SPREAD_STRIKE_WIDTH)), default=None)

    if otm_call:
        log(f"{symbol} {expiry} ({expiry_label}): BULL CALL SPREAD - Buy {atm_call['strikePrice']}C @{atm_call['askPrice']} / Sell {otm_call['strikePrice']}C @{otm_call['bidPrice']}")

        risk = calculate_bull_call_spread_risk(
            atm_call['strikePrice'], otm_call['strikePrice'],
            atm_call['askPrice'], otm_call['bidPrice']
        )
        log(format_risk_analysis(risk))

        # Write to CSV
        trade_desc = f"Buy {atm_call['strikePrice']}C @{atm_call['askPrice']} / Sell {otm_call['strikePrice']}C @{otm_call['bidPrice']}"
        dte = calculate_days_to_expiry(expiry)
        writer.writerow([
            datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            symbol, f"bull_call_spread_{expiry_label}", expiry, dte,
            trade_desc,
            risk.get('max_loss', ''),
            risk.get('max_profit', ''),
            risk.get('breakeven', ''),
            '', '',  # breakeven_lower, breakeven_upper (not applicable)
            risk.get('risk_reward_ratio', ''),
            risk.get('prob_profit', ''),
            risk.get('net_debit', '')
        ])
        return True
    else:
        log(f"{symbol} ({expiry_label}): No suitable OTM call for spread.")
        return False

def process_bear_put_spread(symbol, symbol_id, expiry, expiry_label, writer):
    """Process bear put spread for a specific expiry"""
    quotes = get_option_quotes(symbol_id, expiry)
    log(f"{symbol}: Retrieved {len(quotes)} quotes for {expiry_label} expiry {expiry}")

    if not quotes:
        log(f"{symbol}: No option quotes found for expiry {expiry}")
        return False

    atm_put = min([q for q in quotes if is_put_option(q)], key=lambda x: abs(x.get("delta", 0) + 0.5), default=None)
    if not atm_put:
        log(f"{symbol}: No ATM put for bear put spread.")
        return False

    otm_puts = [q for q in quotes if is_put_option(q) and q["strikePrice"] < atm_put["strikePrice"]]
    otm_put = min(otm_puts, key=lambda x: abs(x["strikePrice"] - (atm_put["strikePrice"] - config.SPREAD_STRIKE_WIDTH)), default=None)

    if otm_put:
        log(f"{symbol} {expiry} ({expiry_label}): BEAR PUT SPREAD - Buy {atm_put['strikePrice']}P @{atm_put['askPrice']} / Sell {otm_put['strikePrice']}P @{otm_put['bidPrice']}")

        risk = calculate_bear_put_spread_risk(
            atm_put['strikePrice'], otm_put['strikePrice'],
            atm_put['askPrice'], otm_put['bidPrice']
        )
        log(format_risk_analysis(risk))

        # Write to CSV
        trade_desc = f"Buy {atm_put['strikePrice']}P @{atm_put['askPrice']} / Sell {otm_put['strikePrice']}P @{otm_put['bidPrice']}"
        dte = calculate_days_to_expiry(expiry)
        writer.writerow([
            datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            symbol, f"bear_put_spread_{expiry_label}", expiry, dte,
            trade_desc,
            risk.get('max_loss', ''),
            risk.get('max_profit', ''),
            risk.get('breakeven', ''),
            '', '',
            risk.get('risk_reward_ratio', ''),
            risk.get('prob_profit', ''),
            risk.get('net_debit', '')
        ])
        return True
    else:
        log(f"{symbol} ({expiry_label}): No suitable OTM put for spread.")
        return False

def process_strategy_file():
    import os
    import shutil

    if not os.path.exists(STRATEGY_FILE):
        log(f"[ERROR] Strategy file '{STRATEGY_FILE}' not found!")
        log(f"   Please run strategy_selector.py first to generate strategies.")
        return

    with open(STRATEGY_FILE, newline='') as csvfile:
        reader = csv.DictReader(csvfile)
        rows = list(reader)

    if not rows:
        log(f"[WARNING] No strategies found in {STRATEGY_FILE}")
        return

    log(f"Processing {len(rows)} strategy recommendation(s)")

    # Archive existing trade recommendations if they exist
    output_file = config.TRADE_OUTPUT_FILE
    if os.path.exists(output_file):
        # Get file modification time to determine the date of the old file
        mod_time = os.path.getmtime(output_file)
        file_date = datetime.fromtimestamp(mod_time).strftime('%Y-%m-%d')

        # Create archived filename
        archived_file = f"trade_recommendations_{file_date}.csv"

        # If archived file already exists, append time to make it unique
        if os.path.exists(archived_file):
            file_datetime = datetime.fromtimestamp(mod_time).strftime('%Y-%m-%d_%H%M%S')
            archived_file = f"trade_recommendations_{file_datetime}.csv"

        # Move the old file to archived name
        shutil.move(output_file, archived_file)
        log(f"[INFO] Archived previous recommendations to: {archived_file}")

    # Open CSV file for writing trade recommendations
    with open(output_file, 'w', newline='', encoding='utf-8') as csvout:
        writer = csv.writer(csvout)
        # Write header
        writer.writerow([
            'timestamp', 'symbol', 'strategy', 'expiry', 'dte',
            'trade_description', 'max_loss', 'max_profit',
            'breakeven', 'breakeven_lower', 'breakeven_upper',
            'risk_reward_ratio', 'prob_profit', 'net_cost_credit'
        ])

        for row in rows:
            symbol = row['symbol']
            symbol_id = int(row['symbol_id'])
            strategy = row['strategy']
            try:
                # Get all available expiries
                expiries = get_expiries(symbol_id)
                if not expiries:
                    today = datetime.now()
                    next_friday = today + timedelta((4 - today.weekday()) % 7)
                    expiry = next_friday.strftime("%Y-%m-%d")
                    log(f"{symbol}: No expiries found. Using fallback expiry {expiry}")
                    categorized = {'near': expiry, 'mid': None, 'long': None}
                else:
                    # Categorize expiries into near/mid/long term
                    categorized = categorize_expiries(expiries)
                    log(f"{symbol}: Expiries - Near: {categorized['near']}, Mid: {categorized['mid']}, Long: {categorized['long']}")

                # For spreads, process all three timeframes
                if strategy == "bull_call_spread":
                    for timeframe in ['near', 'mid', 'long']:
                        expiry = categorized.get(timeframe)
                        if expiry:
                            process_bull_call_spread(symbol, symbol_id, expiry, timeframe, writer)
                    continue

                elif strategy == "bear_put_spread":
                    for timeframe in ['near', 'mid', 'long']:
                        expiry = categorized.get(timeframe)
                        if expiry:
                            process_bear_put_spread(symbol, symbol_id, expiry, timeframe, writer)
                    continue

                # For non-spread strategies, use near-term expiry only
                expiry = categorized['near']
                if not expiry:
                    log(f"{symbol}: No near-term expiry available")
                    continue

                quotes = get_option_quotes(symbol_id, expiry)
                log(f"{symbol}: Retrieved {len(quotes)} quotes for expiry {expiry}")
                if not quotes:
                    log(f"{symbol}: No option quotes found for expiry {expiry}")
                    continue

                if strategy == "straddle":
                    result = score_straddle(quotes)
                    if result:
                        call, put, cost = result
                        underlying_price = get_last_price(symbol_id)
                        dte = calculate_days_to_expiry(expiry)

                        log(f"{symbol} {expiry}: STRADDLE - Buy {call['strikePrice']}C @{call['askPrice']} + {put['strikePrice']}P @{put['askPrice']} | Cost={cost:.2f}")

                        risk = calculate_straddle_risk(
                            call['strikePrice'], call['askPrice'], put['askPrice'],
                            underlying_price, dte
                        )
                        log(format_risk_analysis(risk))

                        # Write to CSV
                        trade_desc = f"Buy {call['strikePrice']}C @{call['askPrice']} + {put['strikePrice']}P @{put['askPrice']}"
                        writer.writerow([
                            datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                            symbol, strategy, expiry, dte,
                            trade_desc,
                            risk.get('max_loss', ''),
                            risk.get('max_profit', ''),
                            risk.get('breakeven', ''),
                            risk.get('breakeven_lower', ''),
                            risk.get('breakeven_upper', ''),
                            risk.get('risk_reward_ratio', ''),
                            risk.get('prob_profit', ''),
                            risk.get('net_cost', '')
                        ])
                    else:
                        log(f"{symbol}: No valid straddle found.")

                elif strategy == "long_call":
                    calls = [q for q in quotes if is_call_option(q)]
                    log(f"{symbol}: Found {len(calls)} call options, {len(quotes)} total quotes")
                    if len(calls) == 0 and len(quotes) > 0:
                        # Debug: show sample symbols to understand format
                        sample_symbols = [q.get("symbol", "?") for q in quotes[:3]]
                        log(f"{symbol}: Sample symbols: {sample_symbols}")
                    if calls:
                        log(f"{symbol}: Call deltas: {[round(c.get('delta', 0), 2) for c in calls[:5]]}")
                    call = min(calls, key=lambda x: abs(x.get("delta", 0) - 0.5), default=None) if calls else None
                    if call:
                        underlying_price = get_last_price(symbol_id)
                        log(f"{symbol} {expiry}: LONG CALL - Buy {call['strikePrice']}C @{call['askPrice']}")

                        risk = calculate_long_call_risk(
                            call['strikePrice'], call['askPrice'],
                            underlying_price, call.get('delta')
                        )
                        log(format_risk_analysis(risk))

                        # Write to CSV
                        trade_desc = f"Buy {call['strikePrice']}C @{call['askPrice']}"
                        dte = calculate_days_to_expiry(expiry)
                        writer.writerow([
                            datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                            symbol, strategy, expiry, dte,
                            trade_desc,
                            risk.get('max_loss', ''),
                            risk.get('max_profit', ''),
                            risk.get('breakeven', ''),
                            '', '',  # breakeven_lower, breakeven_upper (not applicable)
                            risk.get('risk_reward_ratio', ''),
                            risk.get('prob_profit', ''),
                            risk.get('net_debit', '')
                        ])
                    else:
                        log(f"{symbol}: No suitable call found.")

                elif strategy == "long_put":
                    put = min([q for q in quotes if is_put_option(q)], key=lambda x: abs(x.get("delta", 0) + 0.5), default=None)
                    if put:
                        underlying_price = get_last_price(symbol_id)
                        log(f"{symbol} {expiry}: LONG PUT - Buy {put['strikePrice']}P @{put['askPrice']}")

                        risk = calculate_long_put_risk(
                            put['strikePrice'], put['askPrice'],
                            underlying_price, put.get('delta')
                            )
                        log(format_risk_analysis(risk))

                        # Write to CSV
                        trade_desc = f"Buy {put['strikePrice']}P @{put['askPrice']}"
                        dte = calculate_days_to_expiry(expiry)
                        writer.writerow([
                            datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                            symbol, strategy, expiry, dte,
                            trade_desc,
                            risk.get('max_loss', ''),
                            risk.get('max_profit', ''),
                            risk.get('breakeven', ''),
                            '', '',  # breakeven_lower, breakeven_upper (not applicable)
                            risk.get('risk_reward_ratio', ''),
                            risk.get('prob_profit', ''),
                            risk.get('net_debit', '')
                        ])
                    else:
                        log(f"{symbol}: No suitable put found.")

                # Note: bull_call_spread and bear_put_spread are handled above with multi-timeframe logic

                elif strategy == "iron_condor":
                    puts = sorted([q for q in quotes if is_put_option(q)], key=lambda x: x["strikePrice"])
                    calls = sorted([q for q in quotes if is_call_option(q)], key=lambda x: x["strikePrice"])

                    short_put = min(puts, key=lambda x: abs(x.get("delta", 0) + config.DELTA_SHORT_LEG), default=None)
                    short_call = min(calls, key=lambda x: abs(x.get("delta", 0) - config.DELTA_SHORT_LEG), default=None)

                    if not short_put or not short_call:
                        log(f"{symbol}: Could not find short legs for iron condor.")
                        continue

                    long_puts = [p for p in puts if p["strikePrice"] < short_put["strikePrice"]]
                    long_calls = [c for c in calls if c["strikePrice"] > short_call["strikePrice"]]

                    long_put = max(long_puts, key=lambda x: x["strikePrice"], default=None)
                    long_call = min(long_calls, key=lambda x: x["strikePrice"], default=None)
                    limits = calculate_iron_condor_limit_price(long_put, short_put, short_call, long_call)

                    if long_put and long_call:
                        net_credit = short_put["bidPrice"] + short_call["bidPrice"] - long_put["askPrice"] - long_call["askPrice"]
                        log(f"{symbol} {expiry}: IRON CONDOR")
                        log(f"  🔹 Buy {long_put['strikePrice']}P @{long_put['askPrice']}")
                        log(f"  🔹 Sell {short_put['strikePrice']}P @{short_put['bidPrice']}")
                        log(f"  🔹 Sell {short_call['strikePrice']}C @{short_call['bidPrice']}")
                        log(f"  🔹 Buy {long_call['strikePrice']}C @{long_call['askPrice']}")
                        log(f"  💰 Net Credit: {net_credit:.2f}")
                        log(f"  💰 Limit Price (Bid/Ask/Mid): {format_price(limits['bid'])} / {format_price(limits['ask'])} / {format_price(limits['mid'])}")

                        risk = calculate_iron_condor_risk(
                            long_put['strikePrice'], short_put['strikePrice'],
                            short_call['strikePrice'], long_call['strikePrice'],
                            long_put['askPrice'], short_put['bidPrice'],
                            short_call['bidPrice'], long_call['askPrice']
                        )
                        log(format_risk_analysis(risk))
                        # Write to CSV
                        trade_desc = f"IC: Buy {long_put['strikePrice']}P / Sell {short_put['strikePrice']}P / Sell {short_call['strikePrice']}C / Buy {long_call['strikePrice']}C"
                        dte = calculate_days_to_expiry(expiry)
                        writer.writerow([
                            datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                            symbol, strategy, expiry, dte,
                            trade_desc,
                            risk.get('max_loss', ''),
                            risk.get('max_profit', ''),
                            '',
                            risk.get('breakeven_lower', ''),
                            risk.get('breakeven_upper', ''),
                            risk.get('risk_reward_ratio', ''),
                            risk.get('prob_profit', ''),
                            risk.get('net_credit', '')
                        ])

                    else:
                        log(f"{symbol}: Could not find long legs for iron condor.")
                   
                elif strategy == "call_ratio_backspread":
                    # Typically 1 short ATM call, 2 long OTM calls
                    calls = sorted([q for q in quotes if is_call_option(q)], key=lambda x: x["strikePrice"])

                    # Find ATM call for short leg
                    short_call = min(calls, key=lambda x: abs(x.get("delta", 0) - config.DELTA_ATM), default=None)
                    if not short_call:
                        log(f"{symbol}: No ATM call for call ratio backspread.")
                        continue

                    # Find OTM calls for long legs (higher strike)
                    otm_calls = [c for c in calls if c["strikePrice"] > short_call["strikePrice"]]
                    if not otm_calls:
                        log(f"{symbol}: No OTM calls for ratio backspread.")
                        continue

                    long_call = min(otm_calls, key=lambda x: abs(x["strikePrice"] - (short_call["strikePrice"] + config.SPREAD_STRIKE_WIDTH)), default=None)

                    if long_call:
                        log(f"{symbol} {expiry}: CALL RATIO BACKSPREAD (1x2)")
                        log(f"  🔹 Sell 1x {short_call['strikePrice']}C @{short_call['bidPrice']}")
                        log(f"  🔹 Buy 2x {long_call['strikePrice']}C @{long_call['askPrice']}")

                        risk = calculate_call_ratio_backspread_risk(
                            short_call['strikePrice'], long_call['strikePrice'],
                            short_call['bidPrice'], long_call['askPrice'],
                            short_qty=1, long_qty=2
                        )
                        log(format_risk_analysis(risk))

                        # Write to CSV
                        trade_desc = f"Sell 1x {short_call['strikePrice']}C @{short_call['bidPrice']} / Buy 2x {long_call['strikePrice']}C @{long_call['askPrice']}"
                        dte = calculate_days_to_expiry(expiry)
                        writer.writerow([
                            datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                            symbol, strategy, expiry, dte,
                            trade_desc,
                            risk.get('max_loss', ''),
                            risk.get('max_profit', ''),
                            '',
                            risk.get('breakeven_lower', ''),
                            risk.get('breakeven_upper', ''),
                            risk.get('risk_reward_ratio', ''),
                            risk.get('prob_profit', ''),
                            risk.get('net_credit_debit', '')
                        ])
                    else:
                        log(f"{symbol}: No suitable strikes for call ratio backspread.")

                elif strategy == "put_ratio_backspread":
                    # Typically 1 short ATM put, 2 long OTM puts
                    puts = sorted([q for q in quotes if is_put_option(q)], key=lambda x: x["strikePrice"], reverse=True)

                    # Find ATM put for short leg
                    short_put = min(puts, key=lambda x: abs(x.get("delta", 0) + config.DELTA_ATM), default=None)
                    if not short_put:
                        log(f"{symbol}: No ATM put for put ratio backspread.")
                        continue

                    # Find OTM puts for long legs (lower strike)
                    otm_puts = [p for p in puts if p["strikePrice"] < short_put["strikePrice"]]
                    if not otm_puts:
                        log(f"{symbol}: No OTM puts for ratio backspread.")
                        continue

                    long_put = min(otm_puts, key=lambda x: abs(x["strikePrice"] - (short_put["strikePrice"] - config.SPREAD_STRIKE_WIDTH)), default=None)

                    if long_put:
                        log(f"{symbol} {expiry}: PUT RATIO BACKSPREAD (1x2)")
                        log(f"  🔹 Sell 1x {short_put['strikePrice']}P @{short_put['bidPrice']}")
                        log(f"  🔹 Buy 2x {long_put['strikePrice']}P @{long_put['askPrice']}")

                        risk = calculate_put_ratio_backspread_risk(
                            short_put['strikePrice'], long_put['strikePrice'],
                            short_put['bidPrice'], long_put['askPrice'],
                            short_qty=1, long_qty=2
                        )
                        log(format_risk_analysis(risk))

                        # Write to CSV
                        trade_desc = f"Sell 1x {short_put['strikePrice']}P @{short_put['bidPrice']} / Buy 2x {long_put['strikePrice']}P @{long_put['askPrice']}"
                        dte = calculate_days_to_expiry(expiry)
                        writer.writerow([
                            datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                            symbol, strategy, expiry, dte,
                            trade_desc,
                            risk.get('max_loss', ''),
                            risk.get('max_profit', ''),
                            '',
                            risk.get('breakeven_lower', ''),
                            risk.get('breakeven_upper', ''),
                            risk.get('risk_reward_ratio', ''),
                            risk.get('prob_profit', ''),
                            risk.get('net_credit_debit', '')
                        ])
                    else:
                        log(f"{symbol}: No suitable strikes for put ratio backspread.")

                elif strategy == "calendar_spread":
                    # Need to fetch two different expiries
                    all_expiries = get_expiries(symbol_id)
                    if len(all_expiries) < 2:
                        log(f"{symbol}: Not enough expiries for calendar spread (need at least 2).")
                        continue

                    # Use first two expiries as front and back month
                    front_expiry = all_expiries[0]
                    back_expiry = all_expiries[1]

                    # Get quotes for both expiries
                    front_quotes = get_option_quotes(symbol_id, front_expiry)
                    back_quotes = get_option_quotes(symbol_id, back_expiry)

                    if not front_quotes or not back_quotes:
                        log(f"{symbol}: Could not get quotes for both expiries.")
                        continue

                    # Find ATM strike - use calls by default
                    underlying_price = get_last_price(symbol_id)
                    front_calls = [q for q in front_quotes if is_call_option(q)]
                    back_calls = [q for q in back_quotes if is_call_option(q)]

                    if not front_calls or not back_calls:
                        log(f"{symbol}: No calls found for calendar spread.")
                        continue

                    # Find closest to ATM strike in both months
                    front_call = min(front_calls, key=lambda x: abs(x["strikePrice"] - underlying_price))
                    # Try to match same strike in back month
                    target_strike = front_call["strikePrice"]
                    back_call = min(back_calls, key=lambda x: abs(x["strikePrice"] - target_strike), default=None)

                    if back_call and abs(back_call["strikePrice"] - target_strike) < 1:
                        front_dte = calculate_days_to_expiry(front_expiry)
                        back_dte = calculate_days_to_expiry(back_expiry)

                        log(f"{symbol} {front_expiry}/{back_expiry}: CALENDAR SPREAD")
                        log(f"  🔹 Sell {front_call['strikePrice']}C {front_expiry} @{front_call['bidPrice']} (DTE: {front_dte})")
                        log(f"  🔹 Buy {back_call['strikePrice']}C {back_expiry} @{back_call['askPrice']} (DTE: {back_dte})")

                        risk = calculate_calendar_spread_risk(
                            front_call['bidPrice'], back_call['askPrice'],
                            target_strike, front_dte, back_dte
                        )
                        log(format_risk_analysis(risk))

                        # Write to CSV
                        trade_desc = f"Sell {target_strike}C {front_expiry} @{front_call['bidPrice']} / Buy {target_strike}C {back_expiry} @{back_call['askPrice']}"
                        writer.writerow([
                            datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                            symbol, strategy, f"{front_expiry}/{back_expiry}", front_dte,
                            trade_desc,
                            risk.get('max_loss', ''),
                            risk.get('max_profit', ''),
                            '', '', '',  # No single breakeven for calendar
                            risk.get('risk_reward_ratio', ''),
                            risk.get('prob_profit', ''),
                            risk.get('net_debit', '')
                        ])
                    else:
                        log(f"{symbol}: Could not find matching strikes for calendar spread.")

                else:
                    log(f"{symbol}: Strategy '{strategy}' not yet implemented.")

            except Exception as e:
                log(f"{symbol}: Error processing strategy - {e}")

    log(f"[OK] Trade recommendations saved to {output_file}")


def main():
    from cleanup_utils import cleanup_temp_files

    # Clean up old temp files before starting
    if config.CLEANUP_TEMP_FILES:
        cleanup_temp_files(max_age_hours=24)

    refresh_access_token()
    log(f"API_SERVER = {questrade_utils.API_SERVER}")
    process_strategy_file()


if __name__ == "__main__":
    main()
