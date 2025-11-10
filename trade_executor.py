"""
Interactive trade execution with approval workflow
Integrates trade_generator recommendations with order_manager
"""
import csv
import re
import requests
from datetime import datetime
from questrade_utils import log, refresh_access_token, get_headers
import questrade_utils
import config
from order_manager import OrderManager, get_primary_account
from position_tracker import PositionTracker


class TradeExecutor:
    """Execute trades from CSV recommendations with user approval"""

    def __init__(self, account_id=None):
        self.account_id = account_id or get_primary_account()
        self.order_manager = OrderManager()
        self.position_tracker = PositionTracker(self.account_id) if self.account_id else None
        self.executed_orders = []
        self.symbol_cache = {}  # Cache for symbol lookups

    def _parse_trade_description(self, description, strategy):
        """
        Parse trade description to extract legs

        Args:
            description: Trade description string (e.g., "Buy 195.0C @3.7 / Sell 200.0C @1.77")
            strategy: Strategy name

        Returns:
            List of leg dictionaries with {action, strike, option_type, price}
        """
        legs = []

        # Split by " / " for multi-leg strategies
        parts = description.split(" / ")

        for part in parts:
            part = part.strip()

            # Pattern: "Buy/Sell [quantity]x strike[C/P] @price"
            # Examples: "Buy 195.0C @3.7", "Sell 2x 250.0C @5.6", "Buy 244.0C @0.69 + 244.0P @0.76"

            # Handle straddles with + separator
            if " + " in part:
                sub_parts = part.split(" + ")
                for sub_part in sub_parts:
                    leg = self._parse_single_leg(sub_part.strip())
                    if leg:
                        legs.append(leg)
            else:
                leg = self._parse_single_leg(part)
                if leg:
                    legs.append(leg)

        return legs

    def _parse_single_leg(self, text):
        """
        Parse a single leg description

        Args:
            text: Single leg text (e.g., "Buy 195.0C @3.7" or "Sell 2x 250.0C @5.6")

        Returns:
            Dictionary with {action, strike, option_type, price, quantity}
        """
        # Pattern: Action [quantity]x strike[C/P] @price
        match = re.match(r'(Buy|Sell)\s+(?:(\d+)x\s+)?(\d+(?:\.\d+)?)(C|P)\s+@([\d.]+)', text)

        if not match:
            log(f"⚠️  Could not parse leg: {text}")
            return None

        action, quantity, strike, option_type, price = match.groups()

        return {
            "action": action,
            "quantity": int(quantity) if quantity else 1,
            "strike": float(strike),
            "option_type": option_type,
            "price": float(price)
        }

    def _lookup_option_symbol_id(self, symbol, expiry, strike, option_type):
        """
        Look up option symbol ID from the option chain

        Args:
            symbol: Underlying symbol (e.g., "NVDA")
            expiry: Expiry date (e.g., "2025-11-14")
            strike: Strike price (e.g., 195.0)
            option_type: "C" for call, "P" for put

        Returns:
            Symbol ID (int) or None if not found
        """
        cache_key = f"{symbol}_{expiry}_{strike}_{option_type}"

        # Check cache first
        if cache_key in self.symbol_cache:
            return self.symbol_cache[cache_key]

        try:
            # Get symbol ID for underlying
            symbol_id = self._get_underlying_symbol_id(symbol)
            if not symbol_id:
                log(f"❌ Could not find symbol ID for {symbol}")
                return None

            # Fetch option chain
            url = f"{questrade_utils.API_SERVER}v1/symbols/{symbol_id}/options"
            response = requests.get(url, headers=get_headers(), timeout=30)

            if response.status_code != 200:
                log(f"❌ Error fetching option chain for {symbol}: {response.status_code}")
                return None

            data = response.json()
            option_chain = data.get("optionChain", [])

            # Find the expiry in the chain
            chain_entry = None
            for entry in option_chain:
                if expiry in entry.get("expiryDate", ""):
                    chain_entry = entry
                    break

            if not chain_entry:
                log(f"❌ Expiry {expiry} not found in option chain for {symbol}")
                return None

            # Find the strike in the chain
            for root in chain_entry.get("chainPerRoot", []):
                for strike_entry in root.get("chainPerStrikePrice", []):
                    if abs(strike_entry.get("strikePrice", 0) - strike) < 0.01:
                        # Found the strike
                        if option_type == "C":
                            symbol_id_result = strike_entry.get("callSymbolId")
                        else:
                            symbol_id_result = strike_entry.get("putSymbolId")

                        if symbol_id_result:
                            self.symbol_cache[cache_key] = symbol_id_result
                            return symbol_id_result

            log(f"❌ Could not find option: {symbol} {expiry} {strike}{option_type}")
            return None

        except Exception as e:
            log(f"❌ Error looking up option symbol ID: {e}")
            return None

    def _get_underlying_symbol_id(self, symbol):
        """
        Get the symbol ID for an underlying ticker

        Args:
            symbol: Ticker symbol (e.g., "NVDA")

        Returns:
            Symbol ID (int) or None if not found
        """
        cache_key = f"underlying_{symbol}"

        if cache_key in self.symbol_cache:
            return self.symbol_cache[cache_key]

        try:
            url = f"{questrade_utils.API_SERVER}v1/symbols/search?prefix={symbol}"
            response = requests.get(url, headers=get_headers(), timeout=30)

            if response.status_code != 200:
                return None

            data = response.json()
            symbols = data.get("symbols", [])

            # Find exact match
            for s in symbols:
                if s.get("symbol") == symbol:
                    symbol_id = s.get("symbolId")
                    self.symbol_cache[cache_key] = symbol_id
                    return symbol_id

            return None

        except Exception as e:
            log(f"❌ Error looking up symbol ID: {e}")
            return None

    def _construct_order(self, trade, legs, quantity):
        """
        Construct an order from parsed legs

        Args:
            trade: Trade dictionary from CSV
            legs: List of leg dictionaries from _parse_trade_description
            quantity: Number of contracts

        Returns:
            Order dictionary ready for submission, or None if construction fails
        """
        strategy = trade.get('strategy')
        symbol = trade.get('symbol')
        expiry = trade.get('expiry')

        if not legs:
            log("❌ No legs to construct order")
            return None

        # Look up symbol IDs for all legs
        order_legs = []
        for leg in legs:
            symbol_id = self._lookup_option_symbol_id(
                symbol,
                expiry,
                leg['strike'],
                leg['option_type']
            )

            if not symbol_id:
                log(f"❌ Failed to lookup symbol ID for {symbol} {leg['strike']}{leg['option_type']}")
                return None

            order_legs.append({
                "symbol_id": symbol_id,
                "action": leg['action'],
                "quantity": leg['quantity'] * quantity,
                "price": leg['price']
            })

        # Construct order based on strategy type
        if len(order_legs) == 1:
            # Single leg order (long call, long put)
            leg = order_legs[0]
            return self.order_manager.create_option_order(
                account_id=self.account_id,
                symbol_id=leg['symbol_id'],
                quantity=leg['quantity'],
                price=leg['price'],
                action=leg['action'],
                order_type="Limit",
                time_in_force="Day"
            )
        else:
            # Multi-leg order (spreads, straddles, etc.)
            multi_leg_legs = []
            net_price = 0

            for leg in order_legs:
                multi_leg_legs.append({
                    "symbol_id": leg['symbol_id'],
                    "quantity": leg['quantity'],
                    "action": leg['action']
                })

                # Calculate net price (debit is positive, credit is negative)
                if leg['action'] == 'Buy':
                    net_price += leg['price'] * leg['quantity']
                else:
                    net_price -= leg['price'] * leg['quantity']

            return self.order_manager.create_multi_leg_order(
                account_id=self.account_id,
                strategy_type=strategy,
                legs=multi_leg_legs,
                net_price=abs(net_price) / quantity,  # Per-contract net price
                order_type="Limit"
            )

    def load_trade_recommendations(self, filename=None):
        """
        Load trade recommendations from CSV

        Args:
            filename: CSV file path (default: config.TRADE_OUTPUT_FILE)

        Returns:
            List of trade dictionaries
        """
        filename = filename or config.TRADE_OUTPUT_FILE

        try:
            with open(filename, 'r', encoding='utf-8') as csvfile:
                reader = csv.DictReader(csvfile)
                trades = list(reader)

            log(f"📋 Loaded {len(trades)} trade recommendation(s) from {filename}")
            return trades

        except FileNotFoundError:
            log(f"❌ File not found: {filename}")
            log("   Please run trade_generator.py first to generate recommendations")
            return []
        except Exception as e:
            log(f"❌ Error loading trade recommendations: {e}")
            return []

    def display_trade_list(self, trades):
        """
        Display formatted list of available trades

        Args:
            trades: List of trade dictionaries
        """
        log("\n" + "="*80)
        log("📊 AVAILABLE TRADE RECOMMENDATIONS")
        log("="*80)

        for i, trade in enumerate(trades, 1):
            symbol = trade.get('symbol', '')
            strategy = trade.get('strategy', '')
            expiry = trade.get('expiry', '')
            max_loss = trade.get('max_loss', '')
            max_profit = trade.get('max_profit', '')
            prob_profit = trade.get('prob_profit', '')

            log(f"\n{i}. {symbol} - {strategy.upper()}")
            log(f"   Expiry: {expiry}")
            log(f"   Trade: {trade.get('trade_description', '')}")
            log(f"   Max Loss: ${max_loss}  |  Max Profit: ${max_profit}  |  Prob: {prob_profit}")

        log("\n" + "="*80 + "\n")

    def execute_trade_interactive(self, trade, dry_run=False):
        """
        Execute a single trade with interactive approval

        Args:
            trade: Trade dictionary from CSV
            dry_run: If True, only simulate (don't actually submit)

        Returns:
            Order ID if executed, None if rejected/failed
        """
        if not self.account_id:
            log("❌ No account ID available. Cannot execute trades.")
            return None

        log(f"\n🔄 Preparing order for {trade.get('symbol')} {trade.get('strategy')}")

        # Note: This is a simplified example. Real implementation would need:
        # 1. Symbol lookup to get actual option symbol IDs
        # 2. Current market quotes to set limit prices
        # 3. Strategy-specific leg construction

        log("⚠️  IMPORTANT: Full order execution requires:")
        log("   1. Symbol ID lookup for each option leg")
        log("   2. Current market quotes for limit price setting")
        log("   3. Strategy-specific order construction")
        log("\n   This is a framework - add symbol lookup logic for production use.\n")

        # Example order display (would be real order in production)
        order_info = {
            "symbol": trade.get('symbol'),
            "strategy": trade.get('strategy'),
            "description": trade.get('trade_description'),
            "max_loss": trade.get('max_loss'),
            "max_profit": trade.get('max_profit'),
            "expiry": trade.get('expiry')
        }

        log("📋 Order Preview:")
        log(f"   Symbol: {order_info['symbol']}")
        log(f"   Strategy: {order_info['strategy']}")
        log(f"   Description: {order_info['description']}")
        log(f"   Max Loss: ${order_info['max_loss']} (per contract)")
        log(f"   Max Profit: ${order_info['max_profit']} (per contract)")
        log(f"   Expiry: {order_info['expiry']}")

        # Get number of contracts
        quantity = self._get_contract_quantity(trade)
        if quantity is None:
            log("❌ Trade cancelled")
            return None

        # Calculate total risk
        max_loss_per_contract = float(str(order_info['max_loss']).replace('$', '').replace(',', ''))
        total_risk = max_loss_per_contract * quantity

        log(f"\n💰 Position Size:")
        log(f"   Contracts: {quantity}")
        log(f"   Total Max Loss: ${total_risk:,.2f}")
        log(f"   Total Max Profit: ${float(str(order_info['max_profit']).replace('$', '').replace(',', '')) * quantity:,.2f}")

        # Check if position is too large
        self._warn_if_position_too_large(total_risk)

        # Get user approval
        while True:
            response = input(f"\n{'🔍 Simulate' if dry_run else '⚠️  Execute'} this trade? (yes/no/skip): ").strip().lower()

            if response in ['yes', 'y']:
                if dry_run:
                    log(f"✅ Trade approved: {quantity} contract(s) (DRY RUN - not actually submitted)")
                    self.executed_orders.append({
                        "trade": trade,
                        "quantity": quantity,
                        "total_risk": total_risk,
                        "order_id": "DRY_RUN_" + datetime.now().strftime("%Y%m%d%H%M%S"),
                        "status": "SIMULATED",
                        "timestamp": datetime.now()
                    })
                    return "DRY_RUN_ORDER"
                else:
                    log(f"✅ Trade approved: {quantity} contract(s) - submitting order...")

                    # Parse trade description and construct order
                    description = trade.get('trade_description', '')
                    strategy = trade.get('strategy', '')

                    log(f"🔍 Parsing trade: {description}")
                    legs = self._parse_trade_description(description, strategy)

                    if not legs:
                        log("❌ Failed to parse trade description")
                        return None

                    log(f"✓ Parsed {len(legs)} leg(s)")

                    # Construct the order
                    log("🔍 Looking up option symbol IDs...")
                    order = self._construct_order(trade, legs, quantity)

                    if not order:
                        log("❌ Failed to construct order")
                        return None

                    log("✓ Order constructed successfully")

                    # Display order for final review
                    self.order_manager.display_order_summary(order, f"{trade.get('symbol')} {strategy}")

                    # Submit the order
                    log("\n📤 Submitting order to Questrade...")
                    order_id = self.order_manager.submit_order(
                        account_id=self.account_id,
                        order=order,
                        dry_run=False  # LIVE MODE
                    )

                    if order_id:
                        log(f"✅ Order submitted successfully! Order ID: {order_id}")
                        self.executed_orders.append({
                            "trade": trade,
                            "quantity": quantity,
                            "total_risk": total_risk,
                            "order_id": order_id,
                            "status": "SUBMITTED",
                            "timestamp": datetime.now()
                        })
                        return order_id
                    else:
                        log("❌ Order submission failed")
                        return None

            elif response in ['no', 'n', 'skip', 's']:
                log("❌ Trade skipped")
                return None
            else:
                log("Invalid input. Please enter 'yes', 'no', or 'skip'")

    def _get_contract_quantity(self, trade):
        """
        Prompt user for number of contracts to trade

        Args:
            trade: Trade dictionary

        Returns:
            Number of contracts (int) or None if cancelled
        """
        while True:
            qty_input = input("\nHow many contracts? (default: 1, 'c' to cancel): ").strip().lower()

            if qty_input in ['c', 'cancel']:
                return None

            if qty_input == '':
                return 1

            try:
                quantity = int(qty_input)
                if quantity <= 0:
                    log("❌ Quantity must be positive")
                    continue
                return quantity
            except ValueError:
                log("❌ Invalid input. Please enter a number or 'c' to cancel")

    def _warn_if_position_too_large(self, total_risk):
        """
        Warn user if position size is too large relative to account balance

        Args:
            total_risk: Total maximum loss for the position
        """
        if not self.account_id:
            return

        try:
            balances = self.order_manager.get_account_balances(self.account_id)
            buying_power = balances.get('buying_power', 0)
            total_equity = balances.get('total_equity', 0)

            if total_equity > 0:
                risk_pct = (total_risk / total_equity) * 100

                if risk_pct > 10:
                    log(f"\n⚠️  WARNING: This position is {risk_pct:.1f}% of your total equity!")
                    log("   Recommended max: 5-10% per position")
                    log("   Consider reducing position size for better risk management")
                elif risk_pct > 5:
                    log(f"\n⚠️  Notice: This position is {risk_pct:.1f}% of your total equity")
                    log("   Within acceptable range but monitor total portfolio risk")

            if buying_power > 0 and total_risk > buying_power:
                log(f"\n⚠️  WARNING: Insufficient buying power!")
                log(f"   Required: ${total_risk:,.2f}")
                log(f"   Available: ${buying_power:,.2f}")
                log("   This trade may be rejected by the broker")

        except Exception as e:
            log(f"⚠️  Could not verify account balance: {e}")

    def execute_batch_interactive(self, trades=None, dry_run=False):
        """
        Execute multiple trades with interactive approval for each

        Args:
            trades: List of trade dictionaries (default: load from CSV)
            dry_run: If True, only simulate (default: False for live trading)

        Returns:
            List of executed order IDs
        """
        if trades is None:
            trades = self.load_trade_recommendations()

        if not trades:
            return []

        self.display_trade_list(trades)

        log(f"\n{'🔍 DRY RUN MODE' if dry_run else '⚠️  LIVE EXECUTION MODE'}")
        if not dry_run:
            log("⚠️  You are in LIVE mode - orders will be submitted to Questrade!")
        log("You will be prompted to approve each trade individually.\n")

        # Confirm live mode
        if not dry_run:
            confirm = input("Continue with LIVE trading? (yes/no): ").strip().lower()
            if confirm not in ['yes', 'y']:
                log("❌ Execution cancelled")
                return []

        executed_order_ids = []

        for i, trade in enumerate(trades, 1):
            log(f"\n--- Trade {i}/{len(trades)} ---")

            order_id = self.execute_trade_interactive(trade, dry_run=dry_run)
            if order_id:
                executed_order_ids.append(order_id)

        log(f"\n✅ Execution complete: {len(executed_order_ids)}/{len(trades)} trades executed")
        return executed_order_ids

    def check_portfolio_before_trade(self, max_loss):
        """
        Check if account has sufficient buying power for trade

        Args:
            max_loss: Maximum loss for the trade

        Returns:
            True if sufficient funds, False otherwise
        """
        if not self.account_id:
            return False

        balances = self.order_manager.get_account_balances(self.account_id)
        buying_power = balances.get('buying_power', 0)

        required = float(max_loss.replace('$', '').replace(',', '')) if isinstance(max_loss, str) else max_loss

        if buying_power >= required:
            log(f"✅ Sufficient buying power: ${buying_power:,.2f} available, ${required:,.2f} required")
            return True
        else:
            log(f"❌ Insufficient buying power: ${buying_power:,.2f} available, ${required:,.2f} required")
            return False

    def save_execution_log(self, filename=None):
        """
        Save executed orders to log file

        Args:
            filename: Output filename (default: executions_YYYYMMDD.csv)

        Returns:
            Filename where data was saved
        """
        if not self.executed_orders:
            log("No executed orders to save")
            return None

        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d")
            filename = f"executions_{timestamp}.csv"

        with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
            fieldnames = ['timestamp', 'symbol', 'strategy', 'quantity', 'total_risk', 'order_id', 'status', 'description']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()

            for exec_order in self.executed_orders:
                trade = exec_order['trade']
                writer.writerow({
                    'timestamp': exec_order['timestamp'].strftime('%Y-%m-%d %H:%M:%S'),
                    'symbol': trade.get('symbol'),
                    'strategy': trade.get('strategy'),
                    'quantity': exec_order.get('quantity', 1),
                    'total_risk': f"${exec_order.get('total_risk', 0):,.2f}",
                    'order_id': exec_order['order_id'],
                    'status': exec_order['status'],
                    'description': trade.get('trade_description')
                })

        log(f"✅ Execution log saved to {filename}")
        return filename


def main(dry_run=None):
    """
    Main interactive execution workflow

    Args:
        dry_run: If True, simulate only. If False, execute live. If None, ask user.
    """
    refresh_access_token()

    executor = TradeExecutor()

    if not executor.account_id:
        log("❌ Could not get account ID. Exiting.")
        return

    # Show current portfolio
    if executor.position_tracker:
        executor.position_tracker.fetch_positions()
        executor.position_tracker.display_portfolio_summary()

    # Load and display trades
    trades = executor.load_trade_recommendations()
    if not trades:
        return

    # Ask user for execution mode if not specified
    if dry_run is None:
        log("\n" + "="*80)
        log("🎯 INTERACTIVE TRADE EXECUTION")
        log("="*80)

        while True:
            mode = input("\nExecution mode:\n  1. DRY RUN (simulate only)\n  2. LIVE TRADING (real orders)\n\nSelect mode (1/2): ").strip()

            if mode == '1':
                dry_run = True
                break
            elif mode == '2':
                dry_run = False
                break
            else:
                log("Invalid input. Please enter 1 or 2")

    if dry_run:
        log("\n🔍 DRY RUN MODE - Simulating execution")
    else:
        log("\n⚠️  LIVE TRADING MODE - Real orders will be submitted!")

    input("\nPress Enter to continue...")

    executor.execute_batch_interactive(trades, dry_run=dry_run)

    # Save execution log
    executor.save_execution_log()


if __name__ == "__main__":
    main()
