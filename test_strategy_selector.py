"""
Unit tests for strategy_selector.py
Tests strategy selection logic and IV rank calculations
"""
import unittest
from unittest.mock import patch, MagicMock
from strategy_selector import select_strategy


class TestStrategySelection(unittest.TestCase):
    """Test strategy selection matrix"""

    def test_bullish_low_iv(self):
        """Test bullish trend with low IV → bull call spread"""
        strategy = select_strategy(trend="bullish", iv_rank=0.2)
        self.assertEqual(strategy, "bull_call_spread")

    def test_bullish_mid_iv(self):
        """Test bullish trend with mid IV → long call"""
        strategy = select_strategy(trend="bullish", iv_rank=0.45)
        self.assertEqual(strategy, "long_call")

    def test_bullish_high_iv(self):
        """Test bullish trend with high IV → call ratio backspread"""
        strategy = select_strategy(trend="bullish", iv_rank=0.75)
        self.assertEqual(strategy, "call_ratio_backspread")

    def test_bearish_low_iv(self):
        """Test bearish trend with low IV → bear put spread"""
        strategy = select_strategy(trend="bearish", iv_rank=0.2)
        self.assertEqual(strategy, "bear_put_spread")

    def test_bearish_mid_iv(self):
        """Test bearish trend with mid IV → long put"""
        strategy = select_strategy(trend="bearish", iv_rank=0.45)
        self.assertEqual(strategy, "long_put")

    def test_bearish_high_iv(self):
        """Test bearish trend with high IV → put ratio backspread"""
        strategy = select_strategy(trend="bearish", iv_rank=0.75)
        self.assertEqual(strategy, "put_ratio_backspread")

    def test_neutral_low_iv(self):
        """Test neutral trend with low IV → calendar spread"""
        strategy = select_strategy(trend="neutral", iv_rank=0.2)
        self.assertEqual(strategy, "calendar_spread")

    def test_neutral_mid_iv(self):
        """Test neutral trend with mid IV → straddle"""
        strategy = select_strategy(trend="neutral", iv_rank=0.45)
        self.assertEqual(strategy, "straddle")

    def test_neutral_high_iv(self):
        """Test neutral trend with high IV → iron condor"""
        strategy = select_strategy(trend="neutral", iv_rank=0.75)
        self.assertEqual(strategy, "iron_condor")

    def test_boundary_conditions(self):
        """Test IV rank boundary values"""
        # Exactly at low threshold (0.3)
        strategy = select_strategy(trend="bullish", iv_rank=0.3)
        self.assertEqual(strategy, "long_call")  # >= threshold

        # Exactly at high threshold (0.6)
        strategy = select_strategy(trend="bullish", iv_rank=0.6)
        self.assertEqual(strategy, "call_ratio_backspread")  # >= threshold

        # Just below low threshold
        strategy = select_strategy(trend="bullish", iv_rank=0.29)
        self.assertEqual(strategy, "bull_call_spread")

    def test_extreme_iv_values(self):
        """Test with IV rank at extremes"""
        # Minimum IV (0)
        strategy = select_strategy(trend="neutral", iv_rank=0.0)
        self.assertEqual(strategy, "calendar_spread")

        # Maximum IV (1)
        strategy = select_strategy(trend="neutral", iv_rank=1.0)
        self.assertEqual(strategy, "iron_condor")

    def test_invalid_trend(self):
        """Test with invalid trend value"""
        strategy = select_strategy(trend="sideways", iv_rank=0.5)
        self.assertEqual(strategy, "hold_cash")

        strategy = select_strategy(trend="", iv_rank=0.5)
        self.assertEqual(strategy, "hold_cash")

    def test_negative_iv_rank(self):
        """Test with negative IV rank (should not occur normally)"""
        # Should still return valid strategy without crashing
        strategy = select_strategy(trend="bullish", iv_rank=-0.1)
        self.assertIn(strategy, ["bull_call_spread", "long_call", "call_ratio_backspread"])

    def test_iv_rank_above_one(self):
        """Test with IV rank > 1 (should not occur normally)"""
        strategy = select_strategy(trend="bullish", iv_rank=1.5)
        self.assertIn(strategy, ["bull_call_spread", "long_call", "call_ratio_backspread"])

    def test_all_trend_types(self):
        """Test all valid trend types"""
        valid_trends = ["bullish", "bearish", "neutral"]
        iv_rank = 0.5

        for trend in valid_trends:
            strategy = select_strategy(trend=trend, iv_rank=iv_rank)
            self.assertIsInstance(strategy, str)
            self.assertGreater(len(strategy), 0)

    def test_strategy_matrix_completeness(self):
        """Test that all 9 strategies are reachable"""
        strategies_found = set()

        test_cases = [
            ("bullish", 0.2, "bull_call_spread"),
            ("bullish", 0.45, "long_call"),
            ("bullish", 0.75, "call_ratio_backspread"),
            ("bearish", 0.2, "bear_put_spread"),
            ("bearish", 0.45, "long_put"),
            ("bearish", 0.75, "put_ratio_backspread"),
            ("neutral", 0.2, "calendar_spread"),
            ("neutral", 0.45, "straddle"),
            ("neutral", 0.75, "iron_condor"),
        ]

        for trend, iv, expected in test_cases:
            result = select_strategy(trend, iv)
            self.assertEqual(result, expected)
            strategies_found.add(result)

        # Verify all 9 strategies are covered
        expected_strategies = {
            "bull_call_spread", "long_call", "call_ratio_backspread",
            "bear_put_spread", "long_put", "put_ratio_backspread",
            "calendar_spread", "straddle", "iron_condor"
        }
        self.assertEqual(strategies_found, expected_strategies)


class TestStrategySelectionWithConfig(unittest.TestCase):
    """Test strategy selection with config thresholds"""

    @patch('config.IV_LOW_THRESHOLD', 0.25)
    @patch('config.IV_HIGH_THRESHOLD', 0.65)
    def test_custom_thresholds(self):
        """Test that custom config thresholds are respected"""
        # With custom thresholds (0.25, 0.65)
        # IV = 0.2 should be LOW
        # IV = 0.5 should be MID
        # IV = 0.7 should be HIGH

        # Note: This test assumes the module respects config changes
        # In practice, you'd need to reload the module or use dependency injection


class TestIVRankEdgeCases(unittest.TestCase):
    """Test IV rank calculation edge cases"""

    def test_iv_rank_returns_float(self):
        """Test that IV rank is always a float between 0 and 1"""
        # This would require mocking the API calls
        # Placeholder for integration test
        pass

    def test_iv_rank_fallback(self):
        """Test that IV rank returns fallback value (0.55) on error"""
        # This would require mocking API failures
        # Placeholder for integration test
        pass


if __name__ == '__main__':
    unittest.main(verbosity=2)
