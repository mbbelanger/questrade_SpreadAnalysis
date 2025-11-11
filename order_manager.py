"""
Order management and execution for Questrade API
Handles order placement, modification, and cancellation with user approval workflow
"""
import requests
import json
from datetime import datetime
from questrade_utils import log, get_headers
import questrade_utils
import config


class OrderManager:
    """Manages order placement and execution through Questrade API"""

    def __init__(self):
        self.api_server = questrade_utils.API_SERVER
        self.pending_orders = []

    def get_account_positions(self, account_id):
        """
        Fetch current positions for an account

        Args:
            account_id: Questrade account number

        Returns:
            List of position dictionaries
        """
        try:
            url = f"{self.api_server}v1/accounts/{account_id}/positions"
            response = requests.get(url, headers=get_headers(), timeout=30)
            data = response.json()

            if response.status_code != 200:
                log(f"❌ Error fetching positions: {data}")
                return []

            positions = data.get("positions", [])
            log(f"📊 Found {len(positions)} open position(s)")
            return positions

        except Exception as e:
            log(f"❌ Error fetching positions: {e}")
            return []

    def get_account_balances(self, account_id):
        """
        Fetch account balances and buying power

        Args:
            account_id: Questrade account number

        Returns:
            Dictionary with balance information
        """
        try:
            url = f"{self.api_server}v1/accounts/{account_id}/balances"
            response = requests.get(url, headers=get_headers(), timeout=30)
            data = response.json()

            if response.status_code != 200:
                log(f"❌ Error fetching balances: {data}")
                return {}

            balances = data.get("perCurrencyBalances", [])
            combined_balances = data.get("combinedBalances", [])

            # Extract key metrics
            result = {
                "total_equity": 0,
                "buying_power": 0,
                "cash": 0,
                "market_value": 0
            }

            for balance in combined_balances:
                if balance.get("currency") == "CAD":
                    result["total_equity"] = balance.get("totalEquity", 0)
                    result["buying_power"] = balance.get("buyingPower", 0)
                    result["cash"] = balance.get("cash", 0)
                    result["market_value"] = balance.get("marketValue", 0)

            log(f"💰 Account Balance: Total Equity=${result['total_equity']:,.2f}, "
                f"Buying Power=${result['buying_power']:,.2f}")

            return result

        except Exception as e:
            log(f"❌ Error fetching balances: {e}")
            return {}

    def create_option_order(self, account_id, symbol_id, quantity, price,
                           action, order_type="Limit", time_in_force="Day"):
        """
        Create an option order (does not submit)

        Args:
            account_id: Questrade account number
            symbol_id: Option symbol ID
            quantity: Number of contracts (positive for buy, negative for sell)
            price: Limit price per contract
            action: "Buy" or "Sell"
            order_type: "Limit" or "Market"
            time_in_force: "Day", "GTC", "IOC", "FOK"

        Returns:
            Order dictionary ready for submission
        """
        order = {
            "accountNumber": str(account_id),
            "symbolId": symbol_id,
            "quantity": abs(quantity),
            "icebergQuantity": abs(quantity),
            "limitPrice": price,
            "isAllOrNone": False,
            "isAnonymous": False,
            "orderType": order_type,
            "timeInForce": time_in_force,
            "action": action,
            "primaryRoute": "AUTO",
            "secondaryRoute": "AUTO"
        }

        return order

    def create_multi_leg_order(self, account_id, strategy_type, legs,
                               net_price, order_type="Limit"):
        """
        Create a multi-leg option order (spread, iron condor, etc.)

        Args:
            account_id: Questrade account number
            strategy_type: Strategy name for tracking
            legs: List of leg dictionaries with:
                  - symbol_id: Option symbol ID
                  - quantity: Number of contracts (positive=buy, negative=sell)
                  - action: "Buy" or "Sell"
            net_price: Net debit (positive) or credit (negative) for the spread
            order_type: "Limit" or "Market"

        Returns:
            Multi-leg order dictionary ready for submission
        """
        order_legs = []
        for leg in legs:
            order_legs.append({
                "symbolId": leg["symbol_id"],
                "ratio": abs(leg["quantity"]),
                "action": leg["action"]
            })

        order = {
            "accountNumber": str(account_id),
            "orderType": order_type,
            "timeInForce": "Day",
            "price": abs(net_price),
            "isAllOrNone": False,
            "isAnonymous": False,
            "primaryRoute": "AUTO",
            "secondaryRoute": "AUTO",
            "strategyType": strategy_type,
            "legs": order_legs
        }

        return order

    def submit_order(self, account_id, order, dry_run=True):
        """
        Submit an order to Questrade

        Args:
            account_id: Questrade account number
            order: Order dictionary from create_option_order() or create_multi_leg_order()
            dry_run: If True, only validate order without submitting

        Returns:
            Order ID if successful, None if failed
        """
        try:
            url = f"{self.api_server}v1/accounts/{account_id}/orders"

            if dry_run:
                log("🔍 DRY RUN MODE - Order validation only (not submitted)")
                log(f"Order details: {json.dumps(order, indent=2)}")
                return "DRY_RUN_ORDER_ID"

            response = requests.post(url, headers=get_headers(), json=order, timeout=30)
            data = response.json()

            if response.status_code == 200 or response.status_code == 201:
                order_id = data.get("orderId")
                log(f"✅ Order submitted successfully! Order ID: {order_id}")
                return order_id
            else:
                log(f"❌ Order submission failed: {data}")
                return None

        except Exception as e:
            log(f"❌ Error submitting order: {e}")
            return None

    def get_order_status(self, account_id, order_id):
        """
        Get status of a submitted order

        Args:
            account_id: Questrade account number
            order_id: Order ID returned from submit_order()

        Returns:
            Order status dictionary
        """
        try:
            url = f"{self.api_server}v1/accounts/{account_id}/orders/{order_id}"
            response = requests.get(url, headers=get_headers(), timeout=30)
            data = response.json()

            if response.status_code != 200:
                log(f"❌ Error fetching order status: {data}")
                return {}

            return data.get("orders", [{}])[0]

        except Exception as e:
            log(f"❌ Error fetching order status: {e}")
            return {}

    def cancel_order(self, account_id, order_id):
        """
        Cancel a submitted order

        Args:
            account_id: Questrade account number
            order_id: Order ID to cancel

        Returns:
            True if successful, False otherwise
        """
        try:
            url = f"{self.api_server}v1/accounts/{account_id}/orders/{order_id}"
            response = requests.delete(url, headers=get_headers(), timeout=10)

            if response.status_code == 200 or response.status_code == 204:
                log(f"✅ Order {order_id} cancelled successfully")
                return True
            else:
                log(f"❌ Failed to cancel order {order_id}: {response.json()}")
                return False

        except Exception as e:
            log(f"❌ Error cancelling order: {e}")
            return False

    def display_order_summary(self, order, strategy_name=""):
        """
        Display a formatted summary of an order for user review

        Args:
            order: Order dictionary
            strategy_name: Optional strategy description
        """
        log("\n" + "="*60)
        log(f"📋 ORDER SUMMARY: {strategy_name}")
        log("="*60)

        if "legs" in order:
            # Multi-leg order
            log(f"Strategy Type: {order.get('strategyType', 'Unknown')}")
            log(f"Order Type: {order.get('orderType')}")
            log(f"Net Price: ${order.get('price', 0):.2f}")
            log(f"Time in Force: {order.get('timeInForce')}")
            log("\nLegs:")
            for i, leg in enumerate(order.get("legs", []), 1):
                log(f"  {i}. {leg['action']} {leg['ratio']} contracts of symbol ID {leg['symbolId']}")
        else:
            # Single-leg order
            log(f"Action: {order.get('action')}")
            log(f"Symbol ID: {order.get('symbolId')}")
            log(f"Quantity: {order.get('quantity')} contracts")
            log(f"Order Type: {order.get('orderType')}")
            log(f"Limit Price: ${order.get('limitPrice', 0):.2f}")
            log(f"Time in Force: {order.get('timeInForce')}")

        log("="*60 + "\n")

    def get_user_approval(self, order, strategy_name="", risk_metrics=None):
        """
        Interactive prompt for user to approve/reject order

        Args:
            order: Order dictionary to review
            strategy_name: Strategy description
            risk_metrics: Optional risk analysis dictionary

        Returns:
            True if approved, False if rejected
        """
        self.display_order_summary(order, strategy_name)

        if risk_metrics:
            log("📊 RISK ANALYSIS:")
            log(f"  Max Loss: ${risk_metrics.get('max_loss', 'N/A')}")
            log(f"  Max Profit: ${risk_metrics.get('max_profit', 'N/A')}")
            log(f"  Risk/Reward: {risk_metrics.get('risk_reward_ratio', 'N/A')}")
            log(f"  Probability of Profit: {risk_metrics.get('prob_profit', 'N/A')}")
            log("")

        while True:
            response = input("⚠️  Submit this order? (yes/no/details): ").strip().lower()

            if response in ['yes', 'y']:
                log("✅ Order approved by user")
                return True
            elif response in ['no', 'n']:
                log("❌ Order rejected by user")
                return False
            elif response in ['details', 'd']:
                log("\nFull order JSON:")
                log(json.dumps(order, indent=2))
                continue
            else:
                log("Invalid input. Please enter 'yes', 'no', or 'details'")


def get_primary_account():
    """
    Fetch the primary trading account ID

    Returns:
        Account ID string, or None if failed
    """
    try:
        url = f"{questrade_utils.API_SERVER}v1/accounts"
        response = requests.get(url, headers=get_headers(), timeout=30)
        data = response.json()

        if response.status_code != 200:
            log(f"❌ Error fetching accounts: {data}")
            return None

        accounts = data.get("accounts", [])
        if not accounts:
            log("❌ No accounts found")
            return None

        # Use first account or filter by type
        primary = accounts[0]
        account_id = primary.get("number")
        account_type = primary.get("type")

        log(f"🏦 Using account: {account_id} ({account_type})")
        return account_id

    except Exception as e:
        log(f"❌ Error fetching accounts: {e}")
        return None


if __name__ == "__main__":
    # Example usage
    from questrade_utils import refresh_access_token

    refresh_access_token()
    manager = OrderManager()

    # Get account info
    account_id = get_primary_account()
    if account_id:
        balances = manager.get_account_balances(account_id)
        positions = manager.get_account_positions(account_id)

        # Example: Create a test order (dry run)
        test_order = manager.create_option_order(
            account_id=account_id,
            symbol_id=12345,  # Replace with real symbol ID
            quantity=1,
            price=2.50,
            action="Buy",
            order_type="Limit"
        )

        manager.display_order_summary(test_order, "Test Long Call")

        # Note: Actual submission requires user approval
        # approved = manager.get_user_approval(test_order, "Test Long Call")
        # if approved:
        #     order_id = manager.submit_order(account_id, test_order, dry_run=True)
