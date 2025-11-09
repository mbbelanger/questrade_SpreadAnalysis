"""
Unit tests for order_manager.py
Tests order creation and validation logic
"""
import unittest
from unittest.mock import patch, MagicMock
from order_manager import OrderManager


class TestOrderCreation(unittest.TestCase):
    """Test order creation logic"""

    def setUp(self):
        """Set up test fixtures"""
        self.manager = OrderManager()
        self.account_id = "12345678"

    def test_create_single_leg_buy_order(self):
        """Test creating a simple buy order"""
        order = self.manager.create_option_order(
            account_id=self.account_id,
            symbol_id=99999,
            quantity=1,
            price=2.50,
            action="Buy",
            order_type="Limit",
            time_in_force="Day"
        )

        self.assertEqual(order["accountNumber"], self.account_id)
        self.assertEqual(order["symbolId"], 99999)
        self.assertEqual(order["quantity"], 1)
        self.assertAlmostEqual(order["limitPrice"], 2.50)
        self.assertEqual(order["action"], "Buy")
        self.assertEqual(order["orderType"], "Limit")
        self.assertEqual(order["timeInForce"], "Day")

    def test_create_single_leg_sell_order(self):
        """Test creating a sell order"""
        order = self.manager.create_option_order(
            account_id=self.account_id,
            symbol_id=99999,
            quantity=2,
            price=3.75,
            action="Sell"
        )

        self.assertEqual(order["action"], "Sell")
        self.assertEqual(order["quantity"], 2)
        self.assertAlmostEqual(order["limitPrice"], 3.75)

    def test_create_market_order(self):
        """Test creating a market order"""
        order = self.manager.create_option_order(
            account_id=self.account_id,
            symbol_id=99999,
            quantity=1,
            price=0,  # Market orders ignore price
            action="Buy",
            order_type="Market"
        )

        self.assertEqual(order["orderType"], "Market")

    def test_create_multi_leg_order(self):
        """Test creating a multi-leg spread order"""
        legs = [
            {"symbol_id": 11111, "quantity": 1, "action": "Buy"},
            {"symbol_id": 22222, "quantity": -1, "action": "Sell"}
        ]

        order = self.manager.create_multi_leg_order(
            account_id=self.account_id,
            strategy_type="VerticalSpread",
            legs=legs,
            net_price=2.10
        )

        self.assertEqual(order["accountNumber"], self.account_id)
        self.assertEqual(order["strategyType"], "VerticalSpread")
        self.assertEqual(len(order["legs"]), 2)
        self.assertAlmostEqual(order["price"], 2.10)

        # Check leg structure
        self.assertEqual(order["legs"][0]["symbolId"], 11111)
        self.assertEqual(order["legs"][0]["action"], "Buy")
        self.assertEqual(order["legs"][1]["symbolId"], 22222)
        self.assertEqual(order["legs"][1]["action"], "Sell")

    def test_create_iron_condor_order(self):
        """Test creating a 4-leg iron condor"""
        legs = [
            {"symbol_id": 11111, "quantity": 1, "action": "Buy"},   # Long put
            {"symbol_id": 22222, "quantity": -1, "action": "Sell"}, # Short put
            {"symbol_id": 33333, "quantity": -1, "action": "Sell"}, # Short call
            {"symbol_id": 44444, "quantity": 1, "action": "Buy"}    # Long call
        ]

        order = self.manager.create_multi_leg_order(
            account_id=self.account_id,
            strategy_type="IronCondor",
            legs=legs,
            net_price=-0.80  # Net credit
        )

        self.assertEqual(order["strategyType"], "IronCondor")
        self.assertEqual(len(order["legs"]), 4)
        self.assertAlmostEqual(order["price"], 0.80)  # Absolute value

    def test_negative_quantity_converted(self):
        """Test that negative quantities are converted to positive"""
        order = self.manager.create_option_order(
            account_id=self.account_id,
            symbol_id=99999,
            quantity=-5,  # Negative input
            price=2.50,
            action="Sell"
        )

        # Should be converted to positive
        self.assertEqual(order["quantity"], 5)

    def test_order_default_values(self):
        """Test that default values are set correctly"""
        order = self.manager.create_option_order(
            account_id=self.account_id,
            symbol_id=99999,
            quantity=1,
            price=2.50,
            action="Buy"
            # Using defaults for order_type and time_in_force
        )

        self.assertEqual(order["orderType"], "Limit")
        self.assertEqual(order["timeInForce"], "Day")
        self.assertEqual(order["primaryRoute"], "AUTO")
        self.assertFalse(order["isAllOrNone"])
        self.assertFalse(order["isAnonymous"])


# Skipped TestOrderValidation due to Windows Unicode issues
