"""
Interactive trade execution with approval workflow
Integrates trade_generator recommendations with order_manager
"""
import csv
from datetime import datetime
from questrade_utils import log, refresh_access_token
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

    def execute_trade_interactive(self, trade, dry_run=True):
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
        log(f"   Max Loss: ${order_info['max_loss']}")
        log(f"   Max Profit: ${order_info['max_profit']}")
        log(f"   Expiry: {order_info['expiry']}")

        # Get user approval
        while True:
            response = input(f"\n{'🔍 Simulate' if dry_run else '⚠️  Execute'} this trade? (yes/no/skip): ").strip().lower()

            if response in ['yes', 'y']:
                if dry_run:
                    log("✅ Trade approved (DRY RUN - not actually submitted)")
                    self.executed_orders.append({
                        "trade": trade,
                        "order_id": "DRY_RUN_" + datetime.now().strftime("%Y%m%d%H%M%S"),
                        "status": "SIMULATED",
                        "timestamp": datetime.now()
                    })
                    return "DRY_RUN_ORDER"
                else:
                    log("✅ Trade approved - submitting order...")
                    # Here you would call order_manager.submit_order() with real order
                    log("⚠️  Add symbol lookup and order construction for real execution")
                    return None

            elif response in ['no', 'n', 'skip', 's']:
                log("❌ Trade skipped")
                return None
            else:
                log("Invalid input. Please enter 'yes', 'no', or 'skip'")

    def execute_batch_interactive(self, trades=None, dry_run=True):
        """
        Execute multiple trades with interactive approval for each

        Args:
            trades: List of trade dictionaries (default: load from CSV)
            dry_run: If True, only simulate

        Returns:
            List of executed order IDs
        """
        if trades is None:
            trades = self.load_trade_recommendations()

        if not trades:
            return []

        self.display_trade_list(trades)

        log(f"{'🔍 DRY RUN MODE' if dry_run else '⚠️  LIVE EXECUTION MODE'}")
        log(f"You will be prompted to approve each trade individually.\n")

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
            fieldnames = ['timestamp', 'symbol', 'strategy', 'order_id', 'status', 'description']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()

            for exec_order in self.executed_orders:
                trade = exec_order['trade']
                writer.writerow({
                    'timestamp': exec_order['timestamp'].strftime('%Y-%m-%d %H:%M:%S'),
                    'symbol': trade.get('symbol'),
                    'strategy': trade.get('strategy'),
                    'order_id': exec_order['order_id'],
                    'status': exec_order['status'],
                    'description': trade.get('trade_description')
                })

        log(f"✅ Execution log saved to {filename}")
        return filename


def main():
    """Main interactive execution workflow"""
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

    # Execute in dry run mode
    log("\n" + "="*80)
    log("🔍 INTERACTIVE TRADE EXECUTION (DRY RUN MODE)")
    log("="*80)
    log("This will simulate trade execution without actually submitting orders.")
    log("For live trading, modify dry_run=False in the code.\n")

    input("Press Enter to continue...")

    executor.execute_batch_interactive(trades, dry_run=True)

    # Save execution log
    executor.save_execution_log()


if __name__ == "__main__":
    main()
