"""
Unit tests for trade_analyzer.py

Run with: python -m pytest test_trade_analyzer.py -v
Or: python test_trade_analyzer.py
"""

import unittest
import os
import csv
import tempfile
import shutil
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock, mock_open
import trade_analyzer


class TestParseTradeDescription(unittest.TestCase):
    """Test trade description parsing"""

    def test_parse_bull_call_spread(self):
        """Test parsing bull call spread description"""
        description = "Buy 195.0C @4.25 / Sell 200.0C @2.09"
        strategy = "bull_call_spread"

        legs = trade_analyzer.parse_trade_description(description, strategy)

        self.assertEqual(len(legs), 2)
        self.assertEqual(legs[0]['action'], 'Buy')
        self.assertEqual(legs[0]['strike'], 195.0)
        self.assertEqual(legs[0]['option_type'], 'C')
        self.assertEqual(legs[0]['price'], 4.25)

        self.assertEqual(legs[1]['action'], 'Sell')
        self.assertEqual(legs[1]['strike'], 200.0)
        self.assertEqual(legs[1]['option_type'], 'C')
        self.assertEqual(legs[1]['price'], 2.09)

    def test_parse_bear_put_spread(self):
        """Test parsing bear put spread description"""
        description = "Buy 92.0P @1.0 / Sell 88.0P @0.04"
        strategy = "bear_put_spread"

        legs = trade_analyzer.parse_trade_description(description, strategy)

        self.assertEqual(len(legs), 2)
        self.assertEqual(legs[0]['action'], 'Buy')
        self.assertEqual(legs[0]['strike'], 92.0)
        self.assertEqual(legs[0]['option_type'], 'P')
        self.assertEqual(legs[0]['price'], 1.0)

        self.assertEqual(legs[1]['action'], 'Sell')
        self.assertEqual(legs[1]['strike'], 88.0)
        self.assertEqual(legs[1]['option_type'], 'P')
        self.assertEqual(legs[1]['price'], 0.04)

    def test_parse_long_call(self):
        """Test parsing long call description"""
        description = "Buy 447.5C @10.95"
        strategy = "long_call"

        legs = trade_analyzer.parse_trade_description(description, strategy)

        self.assertEqual(len(legs), 1)
        self.assertEqual(legs[0]['action'], 'Buy')
        self.assertEqual(legs[0]['strike'], 447.5)
        self.assertEqual(legs[0]['option_type'], 'C')
        self.assertEqual(legs[0]['price'], 10.95)

    def test_parse_long_put(self):
        """Test parsing long put description"""
        description = "Buy 150.0P @5.50"
        strategy = "long_put"

        legs = trade_analyzer.parse_trade_description(description, strategy)

        self.assertEqual(len(legs), 1)
        self.assertEqual(legs[0]['action'], 'Buy')
        self.assertEqual(legs[0]['strike'], 150.0)
        self.assertEqual(legs[0]['option_type'], 'P')
        self.assertEqual(legs[0]['price'], 5.50)

    def test_parse_straddle(self):
        """Test parsing straddle description"""
        description = "Buy 500.0C @5.7 + 500.0P @4.65"
        strategy = "straddle"

        legs = trade_analyzer.parse_trade_description(description, strategy)

        self.assertEqual(len(legs), 2)
        self.assertEqual(legs[0]['action'], 'Buy')
        self.assertEqual(legs[0]['strike'], 500.0)
        self.assertEqual(legs[0]['option_type'], 'C')
        self.assertEqual(legs[0]['price'], 5.7)

        self.assertEqual(legs[1]['action'], 'Buy')
        self.assertEqual(legs[1]['strike'], 500.0)
        self.assertEqual(legs[1]['option_type'], 'P')
        self.assertEqual(legs[1]['price'], 4.65)

    def test_parse_invalid_description(self):
        """Test parsing invalid description"""
        description = "Invalid trade description"
        strategy = "unknown"

        legs = trade_analyzer.parse_trade_description(description, strategy)

        self.assertEqual(len(legs), 0)


class TestCalculateTradePnL(unittest.TestCase):
    """Test P&L calculation logic"""

    def test_bull_call_spread_profit(self):
        """Test profitable bull call spread"""
        legs = [
            {'action': 'Buy', 'strike': 195.0, 'option_type': 'C', 'price': 4.25},
            {'action': 'Sell', 'strike': 200.0, 'option_type': 'C', 'price': 2.09}
        ]

        current_prices = [
            {'bid': 5.75, 'ask': 5.85, 'last': 5.80},
            {'bid': 3.15, 'ask': 3.25, 'last': 3.20}
        ]

        result = trade_analyzer.calculate_trade_pnl(legs, current_prices, quantity=1)

        # Entry: -4.25 + 2.09 = -2.16 per share = -$216
        # Exit: 5.80 - 3.20 = 2.60 per share = $260
        # P&L: 260 - 216 = $44

        self.assertIsNotNone(result)
        self.assertAlmostEqual(result['entry_cost'], -216.0, places=2)
        self.assertAlmostEqual(result['exit_value'], 260.0, places=2)
        self.assertAlmostEqual(result['pnl'], 44.0, places=2)
        self.assertGreater(result['pnl_pct'], 0)

    def test_bull_call_spread_loss(self):
        """Test losing bull call spread"""
        legs = [
            {'action': 'Buy', 'strike': 195.0, 'option_type': 'C', 'price': 4.25},
            {'action': 'Sell', 'strike': 200.0, 'option_type': 'C', 'price': 2.09}
        ]

        current_prices = [
            {'bid': 2.00, 'ask': 2.10, 'last': 2.05},
            {'bid': 0.50, 'ask': 0.60, 'last': 0.55}
        ]

        result = trade_analyzer.calculate_trade_pnl(legs, current_prices, quantity=1)

        # Entry: -4.25 + 2.09 = -2.16 per share = -$216
        # Exit: 2.05 - 0.55 = 1.50 per share = $150
        # P&L: 150 - 216 = -$66

        self.assertIsNotNone(result)
        self.assertAlmostEqual(result['entry_cost'], -216.0, places=2)
        self.assertAlmostEqual(result['exit_value'], 150.0, places=2)
        self.assertAlmostEqual(result['pnl'], -66.0, places=2)
        self.assertLess(result['pnl_pct'], 0)

    def test_long_call_profit(self):
        """Test profitable long call"""
        legs = [
            {'action': 'Buy', 'strike': 447.5, 'option_type': 'C', 'price': 10.95}
        ]

        current_prices = [
            {'bid': 15.00, 'ask': 15.20, 'last': 15.10}
        ]

        result = trade_analyzer.calculate_trade_pnl(legs, current_prices, quantity=1)

        # Entry: -10.95 per share = -$1095
        # Exit: 15.10 per share = $1510
        # P&L: 1510 - 1095 = $415

        self.assertIsNotNone(result)
        self.assertAlmostEqual(result['entry_cost'], -1095.0, places=2)
        self.assertAlmostEqual(result['exit_value'], 1510.0, places=2)
        self.assertAlmostEqual(result['pnl'], 415.0, places=2)

    def test_long_call_loss(self):
        """Test losing long call"""
        legs = [
            {'action': 'Buy', 'strike': 447.5, 'option_type': 'C', 'price': 10.95}
        ]

        current_prices = [
            {'bid': 5.00, 'ask': 5.20, 'last': 5.10}
        ]

        result = trade_analyzer.calculate_trade_pnl(legs, current_prices, quantity=1)

        # Entry: -10.95 per share = -$1095
        # Exit: 5.10 per share = $510
        # P&L: 510 - 1095 = -$585

        self.assertIsNotNone(result)
        self.assertAlmostEqual(result['entry_cost'], -1095.0, places=2)
        self.assertAlmostEqual(result['exit_value'], 510.0, places=2)
        self.assertAlmostEqual(result['pnl'], -585.0, places=2)

    def test_straddle_profit(self):
        """Test profitable straddle"""
        legs = [
            {'action': 'Buy', 'strike': 500.0, 'option_type': 'C', 'price': 5.7},
            {'action': 'Buy', 'strike': 500.0, 'option_type': 'P', 'price': 4.65}
        ]

        current_prices = [
            {'bid': 8.00, 'ask': 8.20, 'last': 8.10},
            {'bid': 6.00, 'ask': 6.20, 'last': 6.10}
        ]

        result = trade_analyzer.calculate_trade_pnl(legs, current_prices, quantity=1)

        # Entry: -5.7 - 4.65 = -10.35 per share = -$1035
        # Exit: 8.10 + 6.10 = 14.20 per share = $1420
        # P&L: 1420 - 1035 = $385

        self.assertIsNotNone(result)
        self.assertAlmostEqual(result['entry_cost'], -1035.0, places=2)
        self.assertAlmostEqual(result['exit_value'], 1420.0, places=2)
        self.assertAlmostEqual(result['pnl'], 385.0, places=2)

    def test_multiple_contracts(self):
        """Test P&L calculation with multiple contracts"""
        legs = [
            {'action': 'Buy', 'strike': 195.0, 'option_type': 'C', 'price': 4.25}
        ]

        current_prices = [
            {'bid': 6.00, 'ask': 6.20, 'last': 6.10}
        ]

        result = trade_analyzer.calculate_trade_pnl(legs, current_prices, quantity=5)

        # Entry: -4.25 per share × 100 × 5 = -$2125
        # Exit: 6.10 per share × 100 × 5 = $3050
        # P&L: 3050 - 2125 = $925

        self.assertIsNotNone(result)
        self.assertAlmostEqual(result['entry_cost'], -2125.0, places=2)
        self.assertAlmostEqual(result['exit_value'], 3050.0, places=2)
        self.assertAlmostEqual(result['pnl'], 925.0, places=2)

    def test_none_current_price(self):
        """Test P&L calculation with None current price"""
        legs = [
            {'action': 'Buy', 'strike': 195.0, 'option_type': 'C', 'price': 4.25}
        ]

        current_prices = [None]

        result = trade_analyzer.calculate_trade_pnl(legs, current_prices, quantity=1)

        self.assertIsNone(result)


class TestListArchivedRecommendations(unittest.TestCase):
    """Test listing archived recommendation files"""

    def setUp(self):
        """Create temporary directory with test files"""
        self.test_dir = tempfile.mkdtemp()
        self.original_dir = os.getcwd()
        os.chdir(self.test_dir)

    def tearDown(self):
        """Clean up temporary directory"""
        os.chdir(self.original_dir)
        shutil.rmtree(self.test_dir)

    def test_list_archived_files(self):
        """Test listing archived recommendation files"""
        # Create test files
        test_files = [
            'trade_recommendations_2025-11-10.csv',
            'trade_recommendations_2025-11-09.csv',
            'trade_recommendations_2025-11-08.csv',
            'other_file.csv'  # Should be ignored
        ]

        for filename in test_files:
            with open(filename, 'w') as f:
                f.write('test')

        files = trade_analyzer.list_archived_recommendations()

        # Should return 3 files (not 'other_file.csv')
        self.assertEqual(len(files), 3)

        # Should be sorted newest first
        self.assertEqual(files[0][1], '2025-11-10')
        self.assertEqual(files[1][1], '2025-11-09')
        self.assertEqual(files[2][1], '2025-11-08')

    def test_list_no_archived_files(self):
        """Test listing when no archived files exist"""
        files = trade_analyzer.list_archived_recommendations()

        self.assertEqual(len(files), 0)

    def test_list_with_timestamp_files(self):
        """Test listing files with timestamps"""
        test_files = [
            'trade_recommendations_2025-11-10_143022.csv',
            'trade_recommendations_2025-11-10.csv'
        ]

        for filename in test_files:
            with open(filename, 'w') as f:
                f.write('test')

        files = trade_analyzer.list_archived_recommendations()

        self.assertEqual(len(files), 2)


class TestFindOptionSymbolId(unittest.TestCase):
    """Test finding option symbol ID in chain"""

    def test_find_call_symbol_id(self):
        """Test finding call option symbol ID"""
        chain_entry = {
            'chainPerRoot': [{
                'chainPerStrikePrice': [
                    {
                        'strikePrice': 195.0,
                        'callSymbolId': 12345,
                        'putSymbolId': 12346
                    },
                    {
                        'strikePrice': 200.0,
                        'callSymbolId': 12347,
                        'putSymbolId': 12348
                    }
                ]
            }]
        }

        symbol_id = trade_analyzer.find_option_symbol_id(chain_entry, 195.0, 'C')

        self.assertEqual(symbol_id, 12345)

    def test_find_put_symbol_id(self):
        """Test finding put option symbol ID"""
        chain_entry = {
            'chainPerRoot': [{
                'chainPerStrikePrice': [
                    {
                        'strikePrice': 195.0,
                        'callSymbolId': 12345,
                        'putSymbolId': 12346
                    }
                ]
            }]
        }

        symbol_id = trade_analyzer.find_option_symbol_id(chain_entry, 195.0, 'P')

        self.assertEqual(symbol_id, 12346)

    def test_find_nonexistent_strike(self):
        """Test finding strike that doesn't exist"""
        chain_entry = {
            'chainPerRoot': [{
                'chainPerStrikePrice': [
                    {
                        'strikePrice': 195.0,
                        'callSymbolId': 12345,
                        'putSymbolId': 12346
                    }
                ]
            }]
        }

        symbol_id = trade_analyzer.find_option_symbol_id(chain_entry, 999.0, 'C')

        self.assertIsNone(symbol_id)

    def test_find_with_floating_point_tolerance(self):
        """Test finding strike with floating point tolerance"""
        chain_entry = {
            'chainPerRoot': [{
                'chainPerStrikePrice': [
                    {
                        'strikePrice': 195.001,  # Close to 195.0
                        'callSymbolId': 12345,
                        'putSymbolId': 12346
                    }
                ]
            }]
        }

        symbol_id = trade_analyzer.find_option_symbol_id(chain_entry, 195.0, 'C')

        self.assertEqual(symbol_id, 12345)


class TestSaveResultsToCSV(unittest.TestCase):
    """Test saving results to CSV"""

    def setUp(self):
        """Create temporary directory"""
        self.test_dir = tempfile.mkdtemp()
        self.output_file = os.path.join(self.test_dir, 'test_results.csv')

    def tearDown(self):
        """Clean up temporary directory"""
        shutil.rmtree(self.test_dir)

    def test_save_results(self):
        """Test saving analysis results to CSV"""
        results = [
            {
                'symbol': 'NVDA',
                'strategy': 'bull_call_spread_near',
                'expiry': '2025-11-14',
                'entry_date': '2025-11-10 12:02:03',
                'status': 'ACTIVE',
                'entry_cost': -216.0,
                'exit_value': 260.0,
                'pnl': 44.0,
                'pnl_pct': 20.37
            },
            {
                'symbol': 'TSLA',
                'strategy': 'long_call',
                'expiry': '2025-11-14',
                'entry_date': '2025-11-10 12:02:05',
                'status': 'ACTIVE',
                'entry_cost': -1095.0,
                'exit_value': 906.0,
                'pnl': -189.0,
                'pnl_pct': -17.26
            }
        ]

        trade_analyzer.save_results_to_csv(results, self.output_file)

        # Verify file exists
        self.assertTrue(os.path.exists(self.output_file))

        # Verify content
        with open(self.output_file, 'r', newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            rows = list(reader)

            self.assertEqual(len(rows), 2)
            self.assertEqual(rows[0]['symbol'], 'NVDA')
            self.assertEqual(rows[0]['pnl'], '44.00')
            self.assertEqual(rows[1]['symbol'], 'TSLA')
            self.assertEqual(rows[1]['pnl'], '-189.00')

    def test_save_empty_results(self):
        """Test saving empty results"""
        results = []

        trade_analyzer.save_results_to_csv(results, self.output_file)

        # File should not be created
        self.assertFalse(os.path.exists(self.output_file))


class TestPrintSummary(unittest.TestCase):
    """Test summary statistics printing"""

    def test_print_summary_with_results(self):
        """Test printing summary with valid results"""
        results = [
            {
                'symbol': 'NVDA',
                'strategy': 'bull_call_spread_near',
                'expiry': '2025-11-14',
                'pnl': 44.0,
                'pnl_pct': 20.37
            },
            {
                'symbol': 'TSLA',
                'strategy': 'long_call',
                'expiry': '2025-11-14',
                'pnl': -189.0,
                'pnl_pct': -17.26
            },
            {
                'symbol': 'MSFT',
                'strategy': 'straddle',
                'expiry': '2025-11-14',
                'pnl': 245.0,
                'pnl_pct': 23.67
            }
        ]

        # This should not raise an exception
        try:
            trade_analyzer.print_summary(results)
        except Exception as e:
            self.fail(f"print_summary raised an exception: {e}")

    def test_print_summary_empty_results(self):
        """Test printing summary with empty results"""
        results = []

        # This should not raise an exception
        try:
            trade_analyzer.print_summary(results)
        except Exception as e:
            self.fail(f"print_summary raised an exception: {e}")


class TestIntegration(unittest.TestCase):
    """Integration tests"""

    def setUp(self):
        """Create temporary directory with test CSV"""
        self.test_dir = tempfile.mkdtemp()
        self.original_dir = os.getcwd()
        os.chdir(self.test_dir)

        # Create a test recommendations file
        self.test_file = 'trade_recommendations_2025-11-10.csv'
        with open(self.test_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([
                'timestamp', 'symbol', 'strategy', 'expiry', 'dte',
                'trade_description', 'max_loss', 'max_profit',
                'breakeven', 'breakeven_lower', 'breakeven_upper',
                'risk_reward_ratio', 'prob_profit', 'net_cost_credit'
            ])
            writer.writerow([
                '2025-11-10 12:02:03', 'NVDA', 'bull_call_spread_near', '2025-11-14', '3',
                'Buy 195.0C @4.25 / Sell 200.0C @2.09', '2.16', '2.84',
                '197.16', '', '', '1.31', '0.5', ''
            ])
            writer.writerow([
                '2025-11-10 12:02:05', 'TSLA', 'long_call', '2025-11-14', '3',
                'Buy 447.5C @10.95', '10.95', 'unlimited',
                '458.45', '', '', '', '0.51', ''
            ])

    def tearDown(self):
        """Clean up temporary directory"""
        os.chdir(self.original_dir)
        shutil.rmtree(self.test_dir)

    def test_parse_recommendations_file(self):
        """Test parsing recommendations CSV file"""
        with open(self.test_file, 'r', newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            trades = list(reader)

        self.assertEqual(len(trades), 2)
        self.assertEqual(trades[0]['symbol'], 'NVDA')
        self.assertEqual(trades[1]['symbol'], 'TSLA')

        # Test parsing trade descriptions
        legs_1 = trade_analyzer.parse_trade_description(
            trades[0]['trade_description'],
            trades[0]['strategy']
        )
        self.assertEqual(len(legs_1), 2)

        legs_2 = trade_analyzer.parse_trade_description(
            trades[1]['trade_description'],
            trades[1]['strategy']
        )
        self.assertEqual(len(legs_2), 1)


def run_tests():
    """Run all tests"""
    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # Add all test classes
    suite.addTests(loader.loadTestsFromTestCase(TestParseTradeDescription))
    suite.addTests(loader.loadTestsFromTestCase(TestCalculateTradePnL))
    suite.addTests(loader.loadTestsFromTestCase(TestListArchivedRecommendations))
    suite.addTests(loader.loadTestsFromTestCase(TestFindOptionSymbolId))
    suite.addTests(loader.loadTestsFromTestCase(TestSaveResultsToCSV))
    suite.addTests(loader.loadTestsFromTestCase(TestPrintSummary))
    suite.addTests(loader.loadTestsFromTestCase(TestIntegration))

    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    # Print summary
    print("\n" + "="*70)
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print(f"Success rate: {(result.testsRun - len(result.failures) - len(result.errors)) / result.testsRun * 100:.2f}%")
    print("="*70)

    return result.wasSuccessful()


if __name__ == '__main__':
    success = run_tests()
    exit(0 if success else 1)
