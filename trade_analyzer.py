"""
Trade Performance Analyzer

Analyzes past trade recommendations and calculates their current P&L
based on today's market prices.
"""

import csv
import os
import requests
from datetime import datetime, timedelta
from questrade_utils import log, refresh_access_token, get_headers
import questrade_utils


def list_archived_recommendations():
    """
    List all archived trade recommendation files

    Returns:
        List of tuples: (filename, date_string)
    """
    files = []
    for filename in os.listdir('.'):
        if filename.startswith('trade_recommendations_') and filename.endswith('.csv'):
            # Extract date from filename
            date_part = filename.replace('trade_recommendations_', '').replace('.csv', '')
            files.append((filename, date_part))

    # Sort by date (newest first)
    files.sort(key=lambda x: x[1], reverse=True)
    return files


def parse_trade_description(description, strategy):
    """
    Parse trade description to extract legs

    Args:
        description: Trade description string
        strategy: Strategy type

    Returns:
        List of leg dictionaries with action, strike, option_type, price
    """
    import re

    legs = []

    # Pattern: Buy/Sell STRIKE C/P @PRICE
    # Examples:
    # "Buy 195.0C @4.25 / Sell 200.0C @2.09"
    # "Buy 500.0C @5.7 + 500.0P @4.65"

    # Split by / or + to separate legs (but preserve the + in pattern matching)
    leg_strings = re.split(r'\s*/\s*|\s+\+\s+', description)

    # Track the last action for legs missing explicit action (straddles)
    last_action = 'Buy'

    for leg_str in leg_strings:
        leg_str = leg_str.strip()

        # Try matching with action: "Buy 500.0C @5.7"
        match = re.match(r'(Buy|Sell)\s+(\d+(?:\.\d+)?)(C|P)\s+@([\d.]+)', leg_str)
        if match:
            action, strike, option_type, price = match.groups()
            last_action = action  # Remember for next leg
            legs.append({
                'action': action,
                'strike': float(strike),
                'option_type': option_type,
                'price': float(price),
                'quantity': 1
            })
            continue

        # Try matching without action: "500.0P @4.65" (use last action)
        match = re.match(r'(\d+(?:\.\d+)?)(C|P)\s+@([\d.]+)', leg_str)
        if match:
            strike, option_type, price = match.groups()
            legs.append({
                'action': last_action,  # Use last action
                'strike': float(strike),
                'option_type': option_type,
                'price': float(price),
                'quantity': 1
            })

    return legs


def get_symbol_id(symbol, retries=3):
    """
    Get Questrade symbol ID for a ticker symbol

    Args:
        symbol: Ticker symbol string
        retries: Number of retry attempts

    Returns:
        Symbol ID or None if failed
    """
    for attempt in range(retries):
        try:
            timeout = 30 + (attempt * 30)
            url = f"{questrade_utils.API_SERVER}v1/symbols/search?prefix={symbol}"
            response = requests.get(url, headers=get_headers(), timeout=timeout)

            if response.status_code == 429:
                wait_time = 5 * (attempt + 1)
                log(f"[WARNING] Rate limited searching for {symbol}, waiting {wait_time}s")
                from time import sleep
                sleep(wait_time)
                continue

            data = response.json()
            symbols = data.get('symbols', [])

            # Find exact match for the symbol
            for sym in symbols:
                if sym.get('symbol') == symbol:
                    return sym.get('symbolId')

            return None

        except Exception as e:
            log(f"[WARNING] Error searching for symbol {symbol}: {e}")
            if attempt < retries - 1:
                from time import sleep
                sleep(2)

    return None


def get_option_chain_for_expiry(symbol_id, expiry, retries=3):
    """
    Get option chain for specific expiry date

    Args:
        symbol_id: Questrade symbol ID
        expiry: Expiry date string (YYYY-MM-DD)
        retries: Number of retry attempts

    Returns:
        Option chain data or None
    """
    for attempt in range(retries):
        try:
            timeout = 30 + (attempt * 30)
            url = f"{questrade_utils.API_SERVER}v1/symbols/{symbol_id}/options"
            response = requests.get(url, headers=get_headers(), timeout=timeout)

            if response.status_code == 429:
                wait_time = 5 * (attempt + 1)
                log(f"[WARNING] Rate limited fetching chain, waiting {wait_time}s")
                from time import sleep
                sleep(wait_time)
                continue

            data = response.json()
            option_chain = data.get('optionChain', [])

            # Find the specific expiry
            for chain_entry in option_chain:
                chain_expiry = chain_entry.get('expiryDate', '').split('T')[0]
                if chain_expiry == expiry:
                    return chain_entry

            return None

        except Exception as e:
            log(f"[WARNING] Error fetching option chain: {e}")
            if attempt < retries - 1:
                from time import sleep
                sleep(2)

    return None


def find_option_symbol_id(chain_entry, strike, option_type):
    """
    Find option symbol ID in chain for specific strike and type

    Args:
        chain_entry: Option chain entry for specific expiry
        strike: Strike price
        option_type: 'C' for call, 'P' for put

    Returns:
        Option symbol ID or None
    """
    for root in chain_entry.get('chainPerRoot', []):
        for strike_entry in root.get('chainPerStrikePrice', []):
            strike_price = strike_entry.get('strikePrice', 0)

            # Match strike (with small tolerance for floating point)
            if abs(strike_price - strike) < 0.01:
                if option_type == 'C':
                    return strike_entry.get('callSymbolId')
                else:
                    return strike_entry.get('putSymbolId')

    return None


def get_current_option_price(symbol_id, retries=3):
    """
    Get current market price for an option

    Args:
        symbol_id: Option symbol ID
        retries: Number of retry attempts

    Returns:
        Dictionary with bid, ask, last prices, or None
    """
    for attempt in range(retries):
        try:
            timeout = 30 + (attempt * 30)
            url = f"{questrade_utils.API_SERVER}v1/markets/quotes?ids={symbol_id}"
            response = requests.get(url, headers=get_headers(), timeout=timeout)

            if response.status_code == 429:
                wait_time = 5 * (attempt + 1)
                log(f"[WARNING] Rate limited fetching quote, waiting {wait_time}s")
                from time import sleep
                sleep(wait_time)
                continue

            data = response.json()
            quotes = data.get('quotes', [])

            if quotes:
                quote = quotes[0]
                return {
                    'bid': quote.get('bidPrice', 0),
                    'ask': quote.get('askPrice', 0),
                    'last': quote.get('lastTradePrice', 0),
                    'symbol': quote.get('symbol', '')
                }

            return None

        except Exception as e:
            log(f"[WARNING] Error fetching option price: {e}")
            if attempt < retries - 1:
                from time import sleep
                sleep(2)

    return None


def calculate_trade_pnl(legs, current_prices, quantity=1):
    """
    Calculate P&L for a multi-leg trade

    Args:
        legs: List of leg dictionaries with action, strike, option_type, price (entry)
        current_prices: List of current price dictionaries (same order as legs)
        quantity: Number of contracts

    Returns:
        Dictionary with P&L analysis
    """
    entry_cost = 0
    exit_value = 0

    for leg, current in zip(legs, current_prices):
        if current is None:
            return None

        entry_price = leg['price']
        # Use mid price for exit
        exit_price = (current['bid'] + current['ask']) / 2 if (current['bid'] > 0 and current['ask'] > 0) else current['last']

        if leg['action'] == 'Buy':
            # Bought at entry, sell at exit
            entry_cost -= entry_price * 100 * quantity  # Negative = money out
            exit_value += exit_price * 100 * quantity   # Positive = money in
        else:  # Sell
            # Sold at entry, buy back at exit
            entry_cost += entry_price * 100 * quantity  # Positive = money in
            exit_value -= exit_price * 100 * quantity   # Negative = money out

    pnl = exit_value + entry_cost  # Net result
    pnl_pct = (pnl / abs(entry_cost) * 100) if entry_cost != 0 else 0

    return {
        'entry_cost': entry_cost,
        'exit_value': exit_value,
        'pnl': pnl,
        'pnl_pct': pnl_pct
    }


def analyze_trade(trade_row):
    """
    Analyze a single trade recommendation against current prices

    Args:
        trade_row: Dictionary from CSV row

    Returns:
        Dictionary with analysis results
    """
    symbol = trade_row['symbol']
    strategy = trade_row['strategy']
    expiry = trade_row['expiry']
    description = trade_row['trade_description']
    entry_timestamp = trade_row['timestamp']

    log(f"\n{'='*60}")
    log(f"Analyzing: {symbol} - {strategy}")
    log(f"Entry Date: {entry_timestamp}")
    log(f"Expiry: {expiry}")
    log(f"Trade: {description}")

    # Check if trade has expired
    try:
        expiry_date = datetime.strptime(expiry, '%Y-%m-%d').date()
        today = datetime.now().date()

        if today > expiry_date:
            days_expired = (today - expiry_date).days
            log(f"[!] EXPIRED {days_expired} days ago - Options are worthless")

            # Parse to get entry cost
            legs = parse_trade_description(description, strategy)
            entry_cost = 0
            for leg in legs:
                if leg['action'] == 'Buy':
                    entry_cost -= leg['price'] * 100
                else:
                    entry_cost += leg['price'] * 100

            return {
                'symbol': symbol,
                'strategy': strategy,
                'expiry': expiry,
                'status': 'EXPIRED',
                'pnl': entry_cost,  # Total loss = entry cost
                'pnl_pct': -100.0,
                'entry_cost': entry_cost,
                'exit_value': 0
            }
    except ValueError:
        pass

    # Parse trade legs
    legs = parse_trade_description(description, strategy)
    if not legs:
        log(f"[ERROR] Could not parse trade description")
        return None

    log(f"Parsed {len(legs)} leg(s)")

    # Get symbol ID
    symbol_id = get_symbol_id(symbol)
    if not symbol_id:
        log(f"[ERROR] Could not find symbol ID for {symbol}")
        return None

    # Get option chain for the expiry
    chain_entry = get_option_chain_for_expiry(symbol_id, expiry)
    if not chain_entry:
        log(f"[ERROR] Could not find option chain for expiry {expiry}")
        return None

    # Find current prices for each leg
    current_prices = []
    for i, leg in enumerate(legs):
        # Find option symbol ID
        option_id = find_option_symbol_id(chain_entry, leg['strike'], leg['option_type'])
        if not option_id:
            log(f"[ERROR] Could not find option ID for {leg['strike']}{leg['option_type']}")
            return None

        # Get current price
        current = get_current_option_price(option_id)
        if not current:
            log(f"[ERROR] Could not fetch current price for {leg['strike']}{leg['option_type']}")
            return None

        current_prices.append(current)
        log(f"  Leg {i+1}: {leg['action']} {leg['strike']}{leg['option_type']} - Entry: ${leg['price']:.2f}, Current: ${current['last']:.2f} (Bid: ${current['bid']:.2f}, Ask: ${current['ask']:.2f})")

    # Calculate P&L
    pnl_data = calculate_trade_pnl(legs, current_prices)
    if not pnl_data:
        log(f"[ERROR] Could not calculate P&L")
        return None

    log(f"\n[P&L Analysis]:")
    log(f"   Entry Cost: ${pnl_data['entry_cost']:.2f}")
    log(f"   Exit Value: ${pnl_data['exit_value']:.2f}")
    log(f"   Net P&L: ${pnl_data['pnl']:.2f} ({pnl_data['pnl_pct']:+.2f}%)")

    return {
        'symbol': symbol,
        'strategy': strategy,
        'expiry': expiry,
        'entry_date': entry_timestamp,
        'status': 'ACTIVE',
        'pnl': pnl_data['pnl'],
        'pnl_pct': pnl_data['pnl_pct'],
        'entry_cost': pnl_data['entry_cost'],
        'exit_value': pnl_data['exit_value']
    }


def analyze_recommendations_file(filename):
    """
    Analyze all trades in a recommendations file

    Args:
        filename: Path to CSV file with trade recommendations

    Returns:
        List of analysis results
    """
    if not os.path.exists(filename):
        log(f"[ERROR] File not found: {filename}")
        return []

    log(f"\n{'='*60}")
    log(f"Loading recommendations from: {filename}")
    log(f"{'='*60}")

    with open(filename, 'r', newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        trades = list(reader)

    log(f"Found {len(trades)} trade(s) to analyze\n")

    results = []
    for i, trade in enumerate(trades, 1):
        log(f"\n[{i}/{len(trades)}] Processing...")
        result = analyze_trade(trade)
        if result:
            results.append(result)

    return results


def print_summary(results):
    """
    Print summary statistics for analyzed trades

    Args:
        results: List of analysis result dictionaries
    """
    if not results:
        log("\n[WARNING] No results to summarize")
        return

    log(f"\n{'='*60}")
    log(f"SUMMARY REPORT")
    log(f"{'='*60}")

    total_trades = len(results)
    winning_trades = [r for r in results if r['pnl'] > 0]
    losing_trades = [r for r in results if r['pnl'] < 0]
    breakeven_trades = [r for r in results if r['pnl'] == 0]

    total_pnl = sum(r['pnl'] for r in results)
    avg_pnl = total_pnl / total_trades if total_trades > 0 else 0

    win_rate = (len(winning_trades) / total_trades * 100) if total_trades > 0 else 0

    log(f"\nTotal Trades: {total_trades}")
    log(f"Winners: {len(winning_trades)} ({len(winning_trades)/total_trades*100:.1f}%)")
    log(f"Losers: {len(losing_trades)} ({len(losing_trades)/total_trades*100:.1f}%)")
    log(f"Breakeven: {len(breakeven_trades)}")
    log(f"\nWin Rate: {win_rate:.2f}%")
    log(f"Total P&L: ${total_pnl:.2f}")
    log(f"Average P&L per trade: ${avg_pnl:.2f}")

    if winning_trades:
        avg_win = sum(r['pnl'] for r in winning_trades) / len(winning_trades)
        log(f"Average Win: ${avg_win:.2f}")

    if losing_trades:
        avg_loss = sum(r['pnl'] for r in losing_trades) / len(losing_trades)
        log(f"Average Loss: ${avg_loss:.2f}")

    # Best and worst trades
    best_trade = max(results, key=lambda x: x['pnl'])
    worst_trade = min(results, key=lambda x: x['pnl'])

    log(f"\n[BEST] Best Trade: {best_trade['symbol']} {best_trade['strategy']} - ${best_trade['pnl']:.2f} ({best_trade['pnl_pct']:+.2f}%)")
    log(f"[WORST] Worst Trade: {worst_trade['symbol']} {worst_trade['strategy']} - ${worst_trade['pnl']:.2f} ({worst_trade['pnl_pct']:+.2f}%)")

    # Strategy breakdown
    log(f"\n[By Strategy]:")
    strategies = {}
    for result in results:
        strat = result['strategy']
        if strat not in strategies:
            strategies[strat] = {'count': 0, 'pnl': 0, 'wins': 0}
        strategies[strat]['count'] += 1
        strategies[strat]['pnl'] += result['pnl']
        if result['pnl'] > 0:
            strategies[strat]['wins'] += 1

    for strat, data in sorted(strategies.items(), key=lambda x: x[1]['pnl'], reverse=True):
        win_rate = (data['wins'] / data['count'] * 100) if data['count'] > 0 else 0
        log(f"  {strat}: {data['count']} trades, ${data['pnl']:.2f} P&L, {win_rate:.1f}% win rate")


def save_results_to_csv(results, output_file):
    """
    Save analysis results to CSV file

    Args:
        results: List of analysis result dictionaries
        output_file: Output CSV filename
    """
    if not results:
        return

    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow([
            'symbol', 'strategy', 'expiry', 'entry_date', 'status',
            'entry_cost', 'exit_value', 'pnl', 'pnl_pct'
        ])

        for r in results:
            writer.writerow([
                r['symbol'],
                r['strategy'],
                r['expiry'],
                r.get('entry_date', ''),
                r['status'],
                f"{r['entry_cost']:.2f}",
                f"{r['exit_value']:.2f}",
                f"{r['pnl']:.2f}",
                f"{r['pnl_pct']:.2f}"
            ])

    log(f"\n[SUCCESS] Results saved to: {output_file}")


def main():
    """Main entry point for trade analyzer"""
    log("=" * 60)
    log("TRADE PERFORMANCE ANALYZER")
    log("=" * 60)

    # Refresh API token
    try:
        refresh_access_token()
    except Exception as e:
        log(f"[ERROR] Failed to refresh API token: {e}")
        return

    # List available archived files
    archived_files = list_archived_recommendations()

    if not archived_files:
        log("\n[WARNING] No archived trade recommendation files found.")
        log("Run trade_generator.py first to create recommendations.")
        return

    log(f"\nFound {len(archived_files)} archived recommendation file(s):\n")
    for i, (filename, date_str) in enumerate(archived_files, 1):
        log(f"  {i}. {filename} (Date: {date_str})")

    # Prompt user to select file
    log("\nEnter the number of the file to analyze (or 'q' to quit): ")
    choice = input().strip()

    if choice.lower() == 'q':
        log("Exiting...")
        return

    try:
        file_index = int(choice) - 1
        if file_index < 0 or file_index >= len(archived_files):
            log("[ERROR] Invalid selection")
            return

        selected_file = archived_files[file_index][0]
    except ValueError:
        log("[ERROR] Invalid input")
        return

    # Analyze the selected file
    results = analyze_recommendations_file(selected_file)

    # Print summary
    print_summary(results)

    # Save results
    timestamp = datetime.now().strftime('%Y-%m-%d_%H%M%S')
    output_file = f"trade_analysis_{timestamp}.csv"
    save_results_to_csv(results, output_file)

    log("\n" + "=" * 60)
    log("Analysis complete!")
    log("=" * 60)


if __name__ == "__main__":
    main()
