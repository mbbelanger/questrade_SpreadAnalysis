"""
Questrade Options Trading System - Main Launcher
Entry point for the Windows executable
"""
import sys
import os

def print_banner():
    """Print application banner"""
    print("=" * 70)
    print("QUESTRADE OPTIONS TRADING SYSTEM")
    print("=" * 70)
    print()

def print_menu():
    """Display main menu"""
    print("\nMAIN MENU:")
    print("-" * 70)
    print("1. Strategy Selector - Analyze watchlist and find trading opportunities")
    print("2. Trade Generator - Generate detailed trade recommendations")
    print("3. Trade Analyzer - Analyze past trade performance with current prices")
    print("4. Position Tracker - View current positions and P&L")
    print("5. Trade Executor - Execute trades from recommendations")
    print("6. Cleanup Utilities - Clean temp files and old data")
    print("7. Run Tests - Execute unit test suite")
    print()
    print("0. Exit")
    print("-" * 70)

def run_strategy_selector():
    """Run the strategy selector"""
    print("\n[Running Strategy Selector...]")
    print("This will analyze your watchlist and find trading opportunities.\n")
    import strategy_selector
    strategy_selector.main()

def run_trade_generator():
    """Run the trade generator"""
    print("\n[Running Trade Generator...]")
    print("This will generate detailed trade recommendations.\n")
    import trade_generator
    trade_generator.main()

def run_trade_analyzer():
    """Run the trade analyzer"""
    print("\n[Running Trade Analyzer...]")
    print("This will analyze past trade recommendations with current market prices.\n")
    import trade_analyzer
    trade_analyzer.main()

def run_position_tracker():
    """Run the position tracker"""
    print("\n[Running Position Tracker...]")
    print("This will display your current positions and P&L.\n")

    from questrade_utils import refresh_access_token
    from order_manager import get_primary_account
    from position_tracker import PositionTracker

    refresh_access_token()
    account_id = get_primary_account()

    if account_id:
        tracker = PositionTracker(account_id)
        tracker.fetch_positions()
        tracker.fetch_account_balances()
        tracker.display_portfolio_summary()
        tracker.save_portfolio_snapshot()
        tracker.monitor_positions(alert_threshold_percent=10)
    else:
        print("[ERROR] Could not get account ID")

def run_trade_executor():
    """Run the trade executor"""
    print("\n[Running Trade Executor...]")
    print("This will execute trades from your recommendations file.\n")
    import trade_executor
    trade_executor.main()

def run_cleanup():
    """Run cleanup utilities"""
    print("\n[Running Cleanup Utilities...]")
    print("This will clean temporary files and old data.\n")

    from cleanup_utils import list_temp_files, cleanup_temp_files, cleanup_all_temp_files

    # Show current temp files
    print("\nCurrent temporary files:")
    print("-" * 70)
    list_temp_files()

    # Ask user what to do
    print("\nCleanup options:")
    print("1. Clean files older than 24 hours")
    print("2. Clean files older than 7 days")
    print("3. Clean ALL temp files")
    print("4. Cancel (don't delete anything)")

    choice = input("\nEnter your choice (1-4): ").strip()

    if choice == '1':
        print("\nCleaning files older than 24 hours...")
        count = cleanup_temp_files(max_age_hours=24)
        print(f"\n[OK] Deleted {count} file(s)")
    elif choice == '2':
        print("\nCleaning files older than 7 days...")
        count = cleanup_temp_files(max_age_hours=168)
        print(f"\n[OK] Deleted {count} file(s)")
    elif choice == '3':
        confirm = input("\nAre you sure you want to delete ALL temp files? (yes/no): ").strip().lower()
        if confirm == 'yes':
            print("\nCleaning all temp files...")
            count = cleanup_all_temp_files()
            print(f"\n[OK] Deleted {count} file(s)")
        else:
            print("\n[Cancelled]")
    else:
        print("\n[Cancelled] No files deleted")

def run_tests():
    """Run the test suite"""
    print("\n[Running Unit Tests...]")
    print("This will execute the full test suite.\n")
    import run_tests
    success = run_tests.discover_and_run_tests(verbosity=2)
    if success:
        print("\n[OK] All tests passed!")
    else:
        print("\n[FAIL] Some tests failed. Check output above.")

def main():
    """Main application entry point"""
    print_banner()

    # Check for .env file
    if not os.path.exists('.env'):
        print("[WARNING] .env file not found!")
        print("You need a .env file with your Questrade refresh token.")
        print("\nCreate a .env file with:")
        print("QUESTRADE_REFRESH_TOKEN=your_token_here")
        print("\nPress Enter to continue anyway or Ctrl+C to exit...")
        input()

    # Check for watchlist.txt
    if not os.path.exists('watchlist.txt'):
        print("[WARNING] watchlist.txt not found!")
        print("Creating a sample watchlist.txt file...")
        with open('watchlist.txt', 'w') as f:
            f.write("# Sample Watchlist\nQQQ\nSPY\nAAPL\n")
        print("[OK] Created watchlist.txt with sample tickers")

    while True:
        print_menu()

        try:
            choice = input("\nEnter your choice (0-7): ").strip()

            if choice == '0':
                print("\nExiting... Goodbye!")
                sys.exit(0)
            elif choice == '1':
                run_strategy_selector()
            elif choice == '2':
                run_trade_generator()
            elif choice == '3':
                run_trade_analyzer()
            elif choice == '4':
                run_position_tracker()
            elif choice == '5':
                run_trade_executor()
            elif choice == '6':
                run_cleanup()
            elif choice == '7':
                run_tests()
            else:
                print("\n[ERROR] Invalid choice. Please enter 0-7.")

            print("\n" + "=" * 70)
            input("\nPress Enter to return to main menu...")
            print()

        except KeyboardInterrupt:
            print("\n\nExiting... Goodbye!")
            sys.exit(0)
        except Exception as e:
            print(f"\n[ERROR] An error occurred: {e}")
            import traceback
            traceback.print_exc()
            print("\n" + "=" * 70)
            input("\nPress Enter to return to main menu...")

if __name__ == "__main__":
    main()
