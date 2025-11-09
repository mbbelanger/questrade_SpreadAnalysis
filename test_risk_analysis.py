"""
Unit tests for risk_analysis.py
Tests all strategy risk calculations for accuracy
"""
import unittest
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
from datetime import datetime, timedelta


class TestRiskAnalysis(unittest.TestCase):
    """Test risk calculation functions"""

    def test_bull_call_spread_basic(self):
        """Test bull call spread risk calculation with known values"""
        # Buy 450C @5.20, Sell 455C @3.10
        # Net debit: 5.20 - 3.10 = 2.10
        # Max profit: (455 - 450) - 2.10 = 2.90
        # Breakeven: 450 + 2.10 = 452.10

        risk = calculate_bull_call_spread_risk(
            long_strike=450,
            short_strike=455,
            long_price=5.20,
            short_price=3.10
        )

        self.assertAlmostEqual(risk['max_loss'], 2.10, places=2)
        self.assertAlmostEqual(risk['max_profit'], 2.90, places=2)
        self.assertAlmostEqual(risk['breakeven'], 452.10, places=2)
        self.assertAlmostEqual(risk['risk_reward_ratio'], 1.38, places=2)
        self.assertIn('prob_profit', risk)

    def test_bull_call_spread_zero_width(self):
        """Test bull call spread with same strikes (invalid)"""
        risk = calculate_bull_call_spread_risk(
            long_strike=450,
            short_strike=450,  # Same strike
            long_price=5.20,
            short_price=3.10
        )

        # Should return dict even with invalid inputs
        self.assertIsInstance(risk, dict)
        self.assertIn('max_loss', risk)

    def test_bear_put_spread_basic(self):
        """Test bear put spread risk calculation"""
        # Buy 450P @5.20, Sell 445P @3.10
        # Net debit: 5.20 - 3.10 = 2.10
        # Max profit: (450 - 445) - 2.10 = 2.90
        # Breakeven: 450 - 2.10 = 447.90

        risk = calculate_bear_put_spread_risk(
            long_strike=450,
            short_strike=445,
            long_price=5.20,
            short_price=3.10
        )

        self.assertAlmostEqual(risk['max_loss'], 2.10, places=2)
        self.assertAlmostEqual(risk['max_profit'], 2.90, places=2)
        self.assertAlmostEqual(risk['breakeven'], 447.90, places=2)

    def test_iron_condor_basic(self):
        """Test iron condor risk calculation"""
        # Buy 445P @1.50, Sell 450P @2.50, Sell 460C @2.50, Buy 465C @1.50
        # Net credit: (2.50 + 2.50) - (1.50 + 1.50) = 2.00
        # Max loss: 5 - 2.00 = 3.00 (using put wing width)

        risk = calculate_iron_condor_risk(
            long_put_strike=445,
            short_put_strike=450,
            short_call_strike=460,
            long_call_strike=465,
            long_put_price=1.50,
            short_put_price=2.50,
            short_call_price=2.50,
            long_call_price=1.50
        )

        self.assertIn('net_credit', risk)
        if 'net_credit' in risk: self.assertAlmostEqual(risk['net_credit'], 2.00, places=2)
        self.assertAlmostEqual(risk['max_profit'], 2.00, places=2)
        self.assertAlmostEqual(risk['max_loss'], 3.00, places=2)
        self.assertAlmostEqual(risk['breakeven_lower'], 448.00, places=2)  # 450 - 2.00
        self.assertAlmostEqual(risk['breakeven_upper'], 462.00, places=2)  # 460 + 2.00

    def test_straddle_basic(self):
        """Test straddle risk calculation"""
        # Buy 450C @5.20 + Buy 450P @5.10
        # Total cost: 10.30
        # Breakeven lower: 450 - 10.30 = 439.70
        # Breakeven upper: 450 + 10.30 = 460.30

        risk = calculate_straddle_risk(
            strike=450,
            call_price=5.20,
            put_price=5.10,
            underlying_price=450,
            dte=30
        )

        self.assertAlmostEqual(risk['max_loss'], 10.30, places=2)
        self.assertEqual(risk['max_profit'], 'unlimited')
        self.assertAlmostEqual(risk['breakeven_lower'], 439.70, places=2)
        self.assertAlmostEqual(risk['breakeven_upper'], 460.30, places=2)

        # Implied move % = (total premium / underlying) * 100
        expected_move = (10.30 / 450) * 100
        self.assertAlmostEqual(risk['implied_move_pct'], expected_move, places=2)

    def test_long_call_basic(self):
        """Test long call risk calculation"""
        risk = calculate_long_call_risk(
            strike=450,
            call_price=5.20,
            underlying_price=450,
            delta=0.5
        )

        self.assertAlmostEqual(risk['max_loss'], 5.20, places=2)
        self.assertEqual(risk['max_profit'], 'unlimited')
        self.assertAlmostEqual(risk['breakeven'], 455.20, places=2)
        self.assertAlmostEqual(risk['delta'], 0.5, places=2)
        # Prob of profit ≈ delta for ATM calls
        self.assertAlmostEqual(risk['prob_profit'], 50.0, places=0)

    def test_long_put_basic(self):
        """Test long put risk calculation"""
        risk = calculate_long_put_risk(
            strike=450,
            call_price=5.10,
            underlying_price=450,
            delta=-0.5
        )

        self.assertAlmostEqual(risk['max_loss'], 5.10, places=2)
        self.assertAlmostEqual(risk['max_profit'], 444.90, places=2)  # 450 - 5.10
        self.assertAlmostEqual(risk['breakeven'], 444.90, places=2)
        self.assertAlmostEqual(risk['delta'], -0.5, places=2)

    def test_call_ratio_backspread_credit(self):
        """Test call ratio backspread (1x2) - credit scenario"""
        # Sell 1x 450C @5.20, Buy 2x 455C @3.10
        # Net credit: 5.20 - (2 * 3.10) = -0.80 (debit)

        risk = calculate_call_ratio_backspread_risk(
            short_strike=450,
            long_strike=455,
            short_price=5.20,
            long_price=3.10,
            short_qty=1,
            long_qty=2
        )

        self.assertIsInstance(risk, dict)
        self.assertIn('net_credit_debit', risk)
        self.assertIn('max_loss', risk)
        self.assertIn('breakeven_lower', risk)
        self.assertIn('breakeven_upper', risk)

    def test_put_ratio_backspread_debit(self):
        """Test put ratio backspread (1x2)"""
        risk = calculate_put_ratio_backspread_risk(
            short_strike=450,
            long_strike=445,
            short_price=5.20,
            long_price=3.10,
            short_qty=1,
            long_qty=2
        )

        self.assertIsInstance(risk, dict)
        self.assertIn('net_credit_debit', risk)
        self.assertIn('max_loss', risk)
        self.assertIn('max_profit', risk)

    def test_calendar_spread_basic(self):
        """Test calendar spread risk calculation"""
        risk = calculate_calendar_spread_risk(
            front_price=3.10,
            back_price=5.20,
            strike=450,
            front_dte=30,
            back_dte=60
        )

        net_debit = 5.20 - 3.10
        self.assertAlmostEqual(risk['net_debit'], net_debit, places=2)
        self.assertAlmostEqual(risk['max_loss'], net_debit, places=2)
        self.assertEqual(risk['front_dte'], 30)
        self.assertEqual(risk['back_dte'], 60)
        self.assertIn('optimal_scenario', risk)

    def test_calculate_days_to_expiry(self):
        """Test DTE calculation"""
        # Test with today's date
        today = datetime.now().date()
        expiry_str = today.strftime("%Y-%m-%d")
        dte = calculate_days_to_expiry(expiry_str)
        self.assertIn(dte, [-1, 0, 1])  # Allow for timezone differences

        # Test with future date
        future = today + timedelta(days=30)
        expiry_str = future.strftime("%Y-%m-%d")
        dte = calculate_days_to_expiry(expiry_str)
        self.assertEqual(dte, 30)

        # Test with past date
        past = today - timedelta(days=10)
        expiry_str = past.strftime("%Y-%m-%d")
        dte = calculate_days_to_expiry(expiry_str)
        self.assertEqual(dte, -10)

    def test_format_risk_analysis(self):
        """Test risk analysis formatting"""
        risk = {
            'max_loss': 2.10,
            'max_profit': 2.90,
            'breakeven': 452.10,
            'risk_reward_ratio': 1.38,
            'prob_profit': 50.0
        }

        formatted = format_risk_analysis(risk)

        self.assertIsInstance(formatted, str)
        self.assertIn('RISK ANALYSIS', formatted)
        self.assertIn('Max Loss', formatted)
        self.assertIn('Max Loss', formatted)  # Just check presence
        self.assertIn('Max Profit', formatted)
        self.assertIn('2.90', formatted)

    def test_negative_prices(self):
        """Test handling of negative prices (should not occur in real data)"""
        risk = calculate_bull_call_spread_risk(
            long_strike=450,
            short_strike=455,
            long_price=-1.0,  # Invalid
            short_price=3.10
        )

        # Should still return dict without crashing
        self.assertIsInstance(risk, dict)

    def test_zero_prices(self):
        """Test handling of zero prices"""
        risk = calculate_long_call_risk(
            strike=450,
            call_price=0,  # Free option (unrealistic)
            underlying_price=450,
            delta=0.5
        )

        self.assertEqual(risk['max_loss'], 0)
        self.assertEqual(risk['breakeven'], 450)


class TestRiskAnalysisEdgeCases(unittest.TestCase):
    """Test edge cases and error handling"""

    def test_inverted_spread(self):
        """Test spread with inverted strikes"""
        # Short strike lower than long strike (inverted)
        risk = calculate_bull_call_spread_risk(
            long_strike=455,
            short_strike=450,  # Inverted
            long_price=3.10,
            short_price=5.20
        )

        # Should handle gracefully
        self.assertIsInstance(risk, dict)

    def test_extreme_delta_values(self):
        """Test with delta values outside normal range"""
        risk = calculate_long_call_risk(
            strike=450,
            call_price=5.20,
            underlying_price=450,
            delta=1.5  # Invalid (should be 0-1)
        )

        self.assertIsInstance(risk, dict)

    def test_very_long_dte(self):
        """Test with very long time to expiration"""
        future = datetime.now().date() + timedelta(days=365 * 2)
        expiry_str = future.strftime("%Y-%m-%d")
        dte = calculate_days_to_expiry(expiry_str)

        self.assertGreater(dte, 700)
        self.assertLess(dte, 750)

    def test_format_with_missing_fields(self):
        """Test formatting with incomplete risk dict"""
        risk = {
            'max_loss': 2.10,
            # Missing other fields
        }

        formatted = format_risk_analysis(risk)
        self.assertIsInstance(formatted, str)
        self.assertIn('Max Loss', formatted)


if __name__ == '__main__':
    # Run tests with verbose output
    unittest.main(verbosity=2)
