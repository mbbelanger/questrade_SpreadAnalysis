"""
Position tracking and P&L monitoring for open trades
"""
import requests
import csv
from datetime import datetime
from questrade_utils import log, get_headers
import questrade_utils
import config


class PositionTracker:
    """Track and monitor open positions with P&L calculations"""

    def __init__(self, account_id):
        self.account_id = account_id
        self.api_server = questrade_utils.API_SERVER
        self.positions = []
        self.executions = []

    def fetch_positions(self):
        """
        Fetch all current positions for the account

        Returns:
            List of position dictionaries
        """
        try:
            url = f"{self.api_server}v1/accounts/{self.account_id}/positions"
            response = requests.get(url, headers=get_headers(), timeout=10)
            data = response.json()

            if response.status_code != 200:
                log(f"❌ Error fetching positions: {data}")
                return []

            self.positions = data.get("positions", [])
            log(f"📊 Loaded {len(self.positions)} position(s)")
            return self.positions

        except Exception as e:
            log(f"❌ Error fetching positions: {e}")
            return []

    def fetch_executions(self, start_date=None, end_date=None):
        """
        Fetch execution history (filled orders)

        Args:
            start_date: Start date (YYYY-MM-DD format)
            end_date: End date (YYYY-MM-DD format)

        Returns:
            List of execution dictionaries
        """
        try:
            url = f"{self.api_server}v1/accounts/{self.account_id}/executions"

            params = {}
            if start_date:
                params["startTime"] = f"{start_date}T00:00:00-05:00"
            if end_date:
                params["endTime"] = f"{end_date}T23:59:59-05:00"

            response = requests.get(url, headers=get_headers(), params=params, timeout=10)
            data = response.json()

            if response.status_code != 200:
                log(f"❌ Error fetching executions: {data}")
                return []

            self.executions = data.get("executions", [])
            log(f"📜 Loaded {len(self.executions)} execution(s)")
            return self.executions

        except Exception as e:
            log(f"❌ Error fetching executions: {e}")
            return []

    def calculate_position_pnl(self, position):
        """
        Calculate P&L for a single position

        Args:
            position: Position dictionary from API

        Returns:
            Dictionary with P&L metrics
        """
        open_quantity = position.get("openQuantity", 0)
        current_market_value = position.get("currentMarketValue", 0)
        current_price = position.get("currentPrice", 0)
        average_entry_price = position.get("averageEntryPrice", 0)
        total_cost = position.get("totalCost", 0)

        # Calculate unrealized P&L
        unrealized_pnl = current_market_value - total_cost

        # Calculate percentage gain/loss
        if total_cost != 0:
            pnl_percent = (unrealized_pnl / abs(total_cost)) * 100
        else:
            pnl_percent = 0

        return {
            "symbol": position.get("symbol", ""),
            "open_quantity": open_quantity,
            "average_entry_price": average_entry_price,
            "current_price": current_price,
            "total_cost": total_cost,
            "current_market_value": current_market_value,
            "unrealized_pnl": unrealized_pnl,
            "pnl_percent": pnl_percent,
            "is_option": position.get("isRealTime", False) and "." in position.get("symbol", "")
        }

    def get_portfolio_summary(self):
        """
        Generate portfolio-wide P&L summary

        Returns:
            Dictionary with portfolio metrics
        """
        if not self.positions:
            self.fetch_positions()

        total_market_value = 0
        total_cost = 0
        total_unrealized_pnl = 0

        option_positions = []
        stock_positions = []

        for pos in self.positions:
            pnl = self.calculate_position_pnl(pos)

            total_market_value += pnl["current_market_value"]
            total_cost += pnl["total_cost"]
            total_unrealized_pnl += pnl["unrealized_pnl"]

            if pnl["is_option"]:
                option_positions.append(pnl)
            else:
                stock_positions.append(pnl)

        if total_cost != 0:
            total_pnl_percent = (total_unrealized_pnl / abs(total_cost)) * 100
        else:
            total_pnl_percent = 0

        return {
            "total_positions": len(self.positions),
            "option_positions": len(option_positions),
            "stock_positions": len(stock_positions),
            "total_market_value": total_market_value,
            "total_cost": total_cost,
            "total_unrealized_pnl": total_unrealized_pnl,
            "total_pnl_percent": total_pnl_percent,
            "option_details": option_positions,
            "stock_details": stock_positions
        }

    def display_portfolio_summary(self):
        """Display formatted portfolio summary"""
        summary = self.get_portfolio_summary()

        log("\n" + "="*70)
        log("📊 PORTFOLIO SUMMARY")
        log("="*70)
        log(f"Total Positions: {summary['total_positions']} "
            f"(Options: {summary['option_positions']}, Stocks: {summary['stock_positions']})")
        log(f"Total Market Value: ${summary['total_market_value']:,.2f}")
        log(f"Total Cost Basis: ${summary['total_cost']:,.2f}")

        pnl_color = "🟢" if summary['total_unrealized_pnl'] >= 0 else "🔴"
        log(f"Unrealized P&L: {pnl_color} ${summary['total_unrealized_pnl']:,.2f} "
            f"({summary['total_pnl_percent']:+.2f}%)")
        log("="*70)

        # Display option positions
        if summary['option_details']:
            log("\n📈 OPTION POSITIONS:")
            log("-"*70)
            for pos in summary['option_details']:
                pnl_indicator = "🟢" if pos['unrealized_pnl'] >= 0 else "🔴"
                log(f"{pos['symbol']:20s} | Qty: {pos['open_quantity']:>4} | "
                    f"Entry: ${pos['average_entry_price']:>7.2f} | "
                    f"Current: ${pos['current_price']:>7.2f} | "
                    f"P&L: {pnl_indicator} ${pos['unrealized_pnl']:>8.2f} "
                    f"({pos['pnl_percent']:+.2f}%)")

        # Display stock positions
        if summary['stock_details']:
            log("\n📊 STOCK POSITIONS:")
            log("-"*70)
            for pos in summary['stock_details']:
                pnl_indicator = "🟢" if pos['unrealized_pnl'] >= 0 else "🔴"
                log(f"{pos['symbol']:20s} | Qty: {pos['open_quantity']:>4} | "
                    f"Entry: ${pos['average_entry_price']:>7.2f} | "
                    f"Current: ${pos['current_price']:>7.2f} | "
                    f"P&L: {pnl_indicator} ${pos['unrealized_pnl']:>8.2f} "
                    f"({pos['pnl_percent']:+.2f}%)")

        log("\n")

    def save_portfolio_snapshot(self, filename=None):
        """
        Save current portfolio state to CSV

        Args:
            filename: Output filename (default: portfolio_YYYYMMDD_HHMMSS.csv)

        Returns:
            Filename where data was saved
        """
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"portfolio_{timestamp}.csv"

        summary = self.get_portfolio_summary()
        all_positions = summary['option_details'] + summary['stock_details']

        with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
            fieldnames = [
                'timestamp', 'symbol', 'type', 'open_quantity',
                'average_entry_price', 'current_price', 'total_cost',
                'current_market_value', 'unrealized_pnl', 'pnl_percent'
            ]
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()

            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            for pos in all_positions:
                writer.writerow({
                    'timestamp': timestamp,
                    'symbol': pos['symbol'],
                    'type': 'OPTION' if pos['is_option'] else 'STOCK',
                    'open_quantity': pos['open_quantity'],
                    'average_entry_price': pos['average_entry_price'],
                    'current_price': pos['current_price'],
                    'total_cost': pos['total_cost'],
                    'current_market_value': pos['current_market_value'],
                    'unrealized_pnl': pos['unrealized_pnl'],
                    'pnl_percent': pos['pnl_percent']
                })

        log(f"✅ Portfolio snapshot saved to {filename}")
        return filename

    def get_position_by_symbol(self, symbol):
        """
        Get position details for a specific symbol

        Args:
            symbol: Ticker symbol to search for

        Returns:
            Position dictionary with P&L, or None if not found
        """
        if not self.positions:
            self.fetch_positions()

        for pos in self.positions:
            if pos.get("symbol", "").upper() == symbol.upper():
                return self.calculate_position_pnl(pos)

        return None

    def monitor_positions(self, alert_threshold_percent=10):
        """
        Monitor positions and alert on significant P&L changes

        Args:
            alert_threshold_percent: Alert if P&L exceeds this percentage

        Returns:
            List of positions exceeding threshold
        """
        summary = self.get_portfolio_summary()
        alerts = []

        for pos in summary['option_details'] + summary['stock_details']:
            if abs(pos['pnl_percent']) >= alert_threshold_percent:
                alert_type = "🚨 PROFIT" if pos['pnl_percent'] > 0 else "⚠️ LOSS"
                alerts.append({
                    "type": alert_type,
                    "symbol": pos['symbol'],
                    "pnl_percent": pos['pnl_percent'],
                    "unrealized_pnl": pos['unrealized_pnl']
                })

                log(f"{alert_type}: {pos['symbol']} is {pos['pnl_percent']:+.2f}% "
                    f"(${pos['unrealized_pnl']:,.2f})")

        return alerts


if __name__ == "__main__":
    # Example usage
    from questrade_utils import refresh_access_token
    from order_manager import get_primary_account

    refresh_access_token()

    account_id = get_primary_account()
    if account_id:
        tracker = PositionTracker(account_id)

        # Fetch and display portfolio
        tracker.fetch_positions()
        tracker.display_portfolio_summary()

        # Save snapshot
        tracker.save_portfolio_snapshot()

        # Monitor for large moves
        tracker.monitor_positions(alert_threshold_percent=10)
