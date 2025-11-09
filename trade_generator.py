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


def get_expiries(symbol_id, retries=2):
    for attempt in range(retries):
        url = f"{questrade_utils.API_SERVER}v1/symbols/{symbol_id}/options"
        response = requests.get(url, headers=get_headers())
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

        log(f"⚠️ No expiry dates in option chain for {symbol_id} on attempt {attempt + 1}")
        sleep(1)

    return []

def get_option_quotes(symbol_id: int, expiry: str, window: int = 5):
    """
    Return quotes (incl. greeks) for ~±'window' strikes around ATM.
    """
    # 1) full chain for the symbol
    url = f"{questrade_utils.API_SERVER}v1/symbols/{symbol_id}/options"
    chain = requests.get(url, headers=get_headers(), timeout=10).json()

    # 2) underlying last price
    last_px = get_last_price(symbol_id)
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
    for id_chunk in chunk(ids, 80):         # 80 keeps URL well below 2 KB
        qurl = (f"{questrade_utils.API_SERVER}v1/markets/quotes?"
                f"ids={','.join(id_chunk)}&fields=all,greeks")
        qdata = requests.get(qurl, headers=get_headers(), timeout=10).json()
        all_quotes.extend(qdata.get("quotes", []))

    # DEBUG: keep only 1 tiny file
    with open(f"temp-quotes-{symbol_id}-{expiry}.json", "w") as f:
        json.dump({"quotes": all_quotes[:20]}, f, indent=2)   # first 20 rows

    return all_quotes


def get_last_price(symbol_id):
    url = f"{questrade_utils.API_SERVER}v1/markets/quotes?ids={symbol_id}"
    response = requests.get(url, headers=get_headers())
    return response.json().get("quotes", [{}])[0].get("lastTradePrice", None)

def score_straddle(quotes):
    atm_calls = [q for q in quotes if q.get("optionRight") == "Call"]
    atm_puts = [q for q in quotes if q.get("optionRight") == "Put"]
    if not atm_calls or not atm_puts:
        return None

    mid_call = sorted(atm_calls, key=lambda x: abs(x["delta"] - 0.5))[0]
    mid_put = sorted(atm_puts, key=lambda x: abs(x["delta"] + 0.5))[0]

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

def process_strategy_file():
    import os

    if not os.path.exists(STRATEGY_FILE):
        log(f"❌ ERROR: Strategy file '{STRATEGY_FILE}' not found!")
        log(f"   Please run strategy_selector.py first to generate strategies.")
        return

    with open(STRATEGY_FILE, newline='') as csvfile:
        reader = csv.DictReader(csvfile)
        rows = list(reader)

    if not rows:
        log(f"⚠️ WARNING: No strategies found in {STRATEGY_FILE}")
        return

    log(f"📊 Processing {len(rows)} strategy recommendation(s)")

    # Open CSV file for writing trade recommendations
    output_file = config.TRADE_OUTPUT_FILE
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
                expiries = get_expiries(symbol_id)
                if not expiries:
                    today = datetime.now()
                    next_friday = today + timedelta((4 - today.weekday()) % 7)
                    expiry = next_friday.strftime("%Y-%m-%d")
                    log(f"{symbol}: No expiries found. Using fallback expiry {expiry}")
                else:
                    expiry = expiries[0]

                quotes = get_option_quotes(symbol_id, expiry)
                if not quotes:
                    log(f"{symbol}: No option quotes found.")
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
                    call = min([q for q in quotes if q.get("optionRight") == "Call"], key=lambda x: abs(x["delta"] - 0.5), default=None)
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
                    put = min([q for q in quotes if q.get("optionRight") == "Put"], key=lambda x: abs(x["delta"] + 0.5), default=None)
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

                elif strategy == "bull_call_spread":
                    atm_call = min([q for q in quotes if q.get("optionRight") == "Call"], key=lambda x: abs(x["delta"] - 0.5), default=None)
                    if not atm_call:
                        log(f"{symbol}: No ATM call for bull call spread.")
                        continue

                    otm_calls = [q for q in quotes if q.get("optionRight") == "Call" and q["strikePrice"] > atm_call["strikePrice"]]
                    otm_call = min(otm_calls, key=lambda x: abs(x["strikePrice"] - (atm_call["strikePrice"] + config.SPREAD_STRIKE_WIDTH)), default=None)

                    if otm_call:
                        log(f"{symbol} {expiry}: BULL CALL SPREAD - Buy {atm_call['strikePrice']}C @{atm_call['askPrice']} / Sell {otm_call['strikePrice']}C @{otm_call['bidPrice']}")

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
                        log(f"{symbol}: No suitable OTM call for spread.")

                elif strategy == "bear_put_spread":
                    atm_put = min([q for q in quotes if q.get("optionRight") == "Put"], key=lambda x: abs(x["delta"] + 0.5), default=None)
                    if not atm_put:
                        log(f"{symbol}: No ATM put for bear put spread.")
                        continue

                    otm_puts = [q for q in quotes if q.get("optionRight") == "Put" and q["strikePrice"] < atm_put["strikePrice"]]
                    otm_put = min(otm_puts, key=lambda x: abs(x["strikePrice"] - (atm_put["strikePrice"] - config.SPREAD_STRIKE_WIDTH)), default=None)

                    if otm_put:
                        log(f"{symbol} {expiry}: BEAR PUT SPREAD - Buy {atm_put['strikePrice']}P @{atm_put['askPrice']} / Sell {otm_put['strikePrice']}P @{otm_put['bidPrice']}")

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
                            symbol, strategy, expiry, dte,
                            trade_desc,
                            risk.get('max_loss', ''),
                            risk.get('max_profit', ''),
                            risk.get('breakeven', ''),
                            '', '',
                            risk.get('risk_reward_ratio', ''),
                            risk.get('prob_profit', ''),
                            risk.get('net_debit', '')
                        ])
                    else:
                        log(f"{symbol}: No suitable OTM put for spread.")
                
                elif strategy == "iron_condor":
                    puts = sorted([q for q in quotes if q.get("optionRight") == "Put"], key=lambda x: x["strikePrice"])
                    calls = sorted([q for q in quotes if q.get("optionRight") == "Call"], key=lambda x: x["strikePrice"])

                    short_put = min(puts, key=lambda x: abs(x["delta"] + config.DELTA_SHORT_LEG), default=None)
                    short_call = min(calls, key=lambda x: abs(x["delta"] - config.DELTA_SHORT_LEG), default=None)

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
                    calls = sorted([q for q in quotes if q.get("optionRight") == "Call"], key=lambda x: x["strikePrice"])

                    # Find ATM call for short leg
                    short_call = min(calls, key=lambda x: abs(x["delta"] - config.DELTA_ATM), default=None)
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
                    puts = sorted([q for q in quotes if q.get("optionRight") == "Put"], key=lambda x: x["strikePrice"], reverse=True)

                    # Find ATM put for short leg
                    short_put = min(puts, key=lambda x: abs(x["delta"] + config.DELTA_ATM), default=None)
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
                    front_calls = [q for q in front_quotes if q.get("optionRight") == "Call"]
                    back_calls = [q for q in back_quotes if q.get("optionRight") == "Call"]

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

    log(f"✅ Trade recommendations saved to {output_file}")


def main():
    from cleanup_utils import cleanup_temp_files

    # Clean up old temp files before starting
    if config.CLEANUP_TEMP_FILES:
        cleanup_temp_files(max_age_hours=24)

    refresh_access_token()
    log(f"🔍 API_SERVER = {questrade_utils.API_SERVER}")
    process_strategy_file()


if __name__ == "__main__":
    main()
