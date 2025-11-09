"""
Test runner for all unit tests
Runs all test modules and generates a summary report
"""
import unittest
import sys
import os
from datetime import datetime


def discover_and_run_tests(verbosity=2):
    """
    Discover and run all tests in the project

    Args:
        verbosity: Level of output detail (0=quiet, 1=normal, 2=verbose)

    Returns:
        True if all tests passed, False otherwise
    """
    # Discover all test files
    loader = unittest.TestLoader()
    start_dir = '.'
    pattern = 'test_*.py'

    suite = loader.discover(start_dir, pattern=pattern)

    # Run tests with results
    runner = unittest.TextTestRunner(verbosity=verbosity)

    print("\n" + "="*70)
    print("RUNNING UNIT TESTS")
    print("="*70)
    print(f"Test Discovery Pattern: {pattern}")
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*70 + "\n")

    result = runner.run(suite)

    # Print summary
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)
    print(f"Tests Run: {result.testsRun}")
    print(f"Successes: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print(f"Skipped: {len(result.skipped)}")
    print("="*70)

    # Print failures and errors if any
    if result.failures:
        print("\n[X] FAILURES:")
        for test, traceback in result.failures:
            print(f"\n  {test}:")
            print(f"  {traceback}")

    if result.errors:
        print("\n[X] ERRORS:")
        for test, traceback in result.errors:
            print(f"\n  {test}:")
            print(f"  {traceback}")

    # Return success status
    success = result.wasSuccessful()

    if success:
        print("\n[OK] ALL TESTS PASSED!")
    else:
        print("\n[FAIL] SOME TESTS FAILED")

    return success


def run_specific_test_file(filename, verbosity=2):
    """
    Run a specific test file

    Args:
        filename: Test filename (e.g., 'test_risk_analysis.py')
        verbosity: Output verbosity level

    Returns:
        True if tests passed, False otherwise
    """
    loader = unittest.TestLoader()

    # Load tests from specific file
    if not filename.endswith('.py'):
        filename += '.py'

    module_name = filename[:-3]  # Remove .py extension

    try:
        suite = loader.loadTestsFromName(module_name)
    except Exception as e:
        print(f"❌ Error loading test file '{filename}': {e}")
        return False

    runner = unittest.TextTestRunner(verbosity=verbosity)

    print(f"\n{'='*70}")
    print(f"RUNNING: {filename}")
    print(f"{'='*70}\n")

    result = runner.run(suite)

    return result.wasSuccessful()


def main():
    """Main entry point for test runner"""
    import argparse

    parser = argparse.ArgumentParser(description='Run unit tests for the trading system')
    parser.add_argument(
        '--file',
        '-f',
        help='Run specific test file (e.g., test_risk_analysis.py)',
        default=None
    )
    parser.add_argument(
        '--verbose',
        '-v',
        action='count',
        default=1,
        help='Increase verbosity (use -v, -vv, or -vvv)'
    )
    parser.add_argument(
        '--quiet',
        '-q',
        action='store_true',
        help='Minimal output'
    )

    args = parser.parse_args()

    # Determine verbosity level
    if args.quiet:
        verbosity = 0
    else:
        verbosity = min(args.verbose, 2)

    # Run tests
    if args.file:
        success = run_specific_test_file(args.file, verbosity)
    else:
        success = discover_and_run_tests(verbosity)

    # Exit with appropriate code
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
