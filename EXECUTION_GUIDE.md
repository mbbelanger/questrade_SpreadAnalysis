# Trade Execution and Position Tracking Guide

This guide covers the new trade execution and position management features added to the Questrade spread analyzer.

## Overview

Three new modules have been added:

1. **order_manager.py** - Order placement API integration
2. **position_tracker.py** - Position tracking and P&L monitoring
3. **trade_executor.py** - Interactive trade approval workflow

## Features

### ✅ Order Management (`order_manager.py`)

**Capabilities:**
- Submit single-leg option orders
- Submit multi-leg spread orders (vertical spreads, iron condors, etc.)
- Get account balances and buying power
- Check order status
- Cancel pending orders
- Interactive approval workflow with order preview

**Key Functions:**
```python
from order_manager import OrderManager, get_primary_account

manager = OrderManager()
account_id = get_primary_account()

# Get account info
balances = manager.get_account_balances(account_id)
positions = manager.get_account_positions(account_id)

# Create an order
order = manager.create_option_order(
    account_id=account_id,
    symbol_id=12345,  # Option symbol ID
    quantity=1,
    price=2.50,
    action="Buy"
)

# Submit with user approval
approved = manager.get_user_approval(order, "Long Call")
if approved:
    order_id = manager.submit_order(account_id, order, dry_run=False)
```

### ✅ Position Tracking (`position_tracker.py`)

**Capabilities:**
- Fetch all open positions
- Calculate unrealized P&L for each position
- Generate portfolio-wide P&L summary
- Monitor positions for significant moves
- Save portfolio snapshots to CSV
- Track execution history

**Key Functions:**
```python
from position_tracker import PositionTracker

tracker = PositionTracker(account_id)

# Fetch positions
tracker.fetch_positions()

# Display summary
tracker.display_portfolio_summary()

# Save snapshot
tracker.save_portfolio_snapshot()

# Monitor for alerts (±10% moves)
alerts = tracker.monitor_positions(alert_threshold_percent=10)
```

**Example Output:**
```
======================================================================
📊 PORTFOLIO SUMMARY
======================================================================
Total Positions: 5 (Options: 3, Stocks: 2)
Total Market Value: $15,420.50
Total Cost Basis: $14,800.00
Unrealized P&L: 🟢 $620.50 (+4.19%)
======================================================================

📈 OPTION POSITIONS:
----------------------------------------------------------------------
QQQ251219C00450000   | Qty:    1 | Entry: $  5.20 | Current: $  6.10 | P&L: 🟢 $   90.00 (+17.31%)
SPY251115P00560000   | Qty:   -2 | Entry: $  3.40 | Current: $  2.80 | P&L: 🟢 $  120.00 (+17.65%)
```

### ✅ Interactive Execution (`trade_executor.py`)

**Capabilities:**
- Load trade recommendations from CSV
- Display formatted trade list with risk metrics
- Execute trades with interactive approval
- Batch execution with per-trade approval
- Buying power validation
- Execution logging

**Usage:**
```bash
# Run interactive execution (dry run mode)
python trade_executor.py
```

**Workflow:**
1. Shows current portfolio summary
2. Loads trades from `trade_recommendations.csv`
3. Displays all available trades with risk metrics
4. Prompts for approval on each trade
5. Validates buying power
6. Submits orders (or simulates in dry run mode)
7. Saves execution log

**Example Session:**
```
📊 AVAILABLE TRADE RECOMMENDATIONS
================================================================================

1. QQQ - BULL_CALL_SPREAD
   Expiry: 2025-01-17
   Trade: Buy 450C @5.20 / Sell 455C @3.10
   Max Loss: $2.10  |  Max Profit: $2.90  |  Prob: ~50%

2. SPY - IRON_CONDOR
   Expiry: 2025-01-17
   Trade: IC: Buy 555P / Sell 560P / Sell 575C / Buy 580C
   Max Loss: $4.20  |  Max Profit: $0.80  |  Prob: ~65%

================================================================================

--- Trade 1/2 ---

🔄 Preparing order for QQQ BULL_CALL_SPREAD

📋 Order Preview:
   Symbol: QQQ
   Strategy: bull_call_spread
   Description: Buy 450C @5.20 / Sell 455C @3.10
   Max Loss: $2.10
   Max Profit: $2.90
   Expiry: 2025-01-17

🔍 Simulate this trade? (yes/no/skip): yes
✅ Trade approved (DRY RUN - not actually submitted)
```

## Important Setup Notes

### 🔴 Production Requirements

Before using these modules for **live trading**, you MUST:

1. **Add Symbol Lookup Logic**
   - Convert ticker symbols to option symbol IDs
   - The Questrade API requires specific symbol IDs for each option
   - Example: QQQ 450C Jan 17 2025 → symbol ID 12345678

2. **Implement Current Quote Fetching**
   - Get real-time bid/ask prices for limit order pricing
   - Use midpoint or custom logic for limit price calculation

3. **Build Strategy-Specific Order Construction**
   - Map each strategy to proper leg structure
   - Handle quantity ratios correctly (e.g., 1x2 ratio backspreads)

4. **Test in Paper Trading Account**
   - Questrade offers practice accounts
   - Test ALL workflows before going live

### 🔧 Current Limitations

**These modules provide the FRAMEWORK but require completion:**

- ✅ API integration structure
- ✅ Order submission workflow
- ✅ Interactive approval system
- ✅ Position tracking and P&L
- ⚠️ Symbol ID lookup (needs implementation)
- ⚠️ Real-time quote integration (needs implementation)
- ⚠️ Strategy-to-order mapping (partial)

## Configuration

Add to `config.py` if needed:

```python
# Order execution settings
ENABLE_LIVE_TRADING = False  # Set to True only after testing
DEFAULT_ORDER_TYPE = "Limit"  # or "Market"
DEFAULT_TIME_IN_FORCE = "Day"  # or "GTC", "IOC", "FOK"

# Position monitoring
PNL_ALERT_THRESHOLD = 10  # Alert on ±10% moves
PORTFOLIO_SNAPSHOT_FREQUENCY = "daily"  # or "hourly"
```

## Safety Features

### Built-in Safeguards:

1. **Dry Run Mode** - All modules default to simulation
2. **Interactive Approval** - User must confirm each trade
3. **Order Preview** - Full order details shown before submission
4. **Buying Power Check** - Validates sufficient funds
5. **Execution Logging** - All actions recorded to CSV

### Recommended Practices:

- ✅ Always test in dry run mode first
- ✅ Review order details carefully
- ✅ Start with small position sizes
- ✅ Monitor positions regularly
- ✅ Set stop losses manually
- ✅ Keep execution logs for review

## Workflow Examples

### Daily Trading Routine

```bash
# 1. Check current positions
python position_tracker.py

# 2. Generate new trade recommendations
python strategy_selector.py
python trade_generator.py

# 3. Review and execute trades
python trade_executor.py

# 4. Save portfolio snapshot
# (Automatically done by trade_executor.py)
```

### Position Monitoring

```bash
# Check portfolio at market close
python position_tracker.py

# Or integrate into a monitoring script:
```

```python
from position_tracker import PositionTracker
from order_manager import get_primary_account

account_id = get_primary_account()
tracker = PositionTracker(account_id)

tracker.fetch_positions()
tracker.display_portfolio_summary()

# Alert on big moves
alerts = tracker.monitor_positions(alert_threshold_percent=10)
if alerts:
    # Send email, SMS, etc.
    pass
```

## API Reference

### OrderManager

| Method | Description |
|--------|-------------|
| `get_account_balances(account_id)` | Fetch buying power and equity |
| `get_account_positions(account_id)` | Get all open positions |
| `create_option_order(...)` | Build single-leg order |
| `create_multi_leg_order(...)` | Build spread order |
| `submit_order(account_id, order, dry_run)` | Submit to Questrade |
| `get_order_status(account_id, order_id)` | Check order status |
| `cancel_order(account_id, order_id)` | Cancel pending order |
| `get_user_approval(order, strategy, risk)` | Interactive approval prompt |

### PositionTracker

| Method | Description |
|--------|-------------|
| `fetch_positions()` | Load all positions from API |
| `fetch_executions(start_date, end_date)` | Get execution history |
| `calculate_position_pnl(position)` | Compute P&L for one position |
| `get_portfolio_summary()` | Aggregate portfolio metrics |
| `display_portfolio_summary()` | Print formatted summary |
| `save_portfolio_snapshot(filename)` | Export to CSV |
| `get_position_by_symbol(symbol)` | Find specific position |
| `monitor_positions(threshold)` | Alert on large moves |

### TradeExecutor

| Method | Description |
|--------|-------------|
| `load_trade_recommendations(filename)` | Load from CSV |
| `display_trade_list(trades)` | Show formatted list |
| `execute_trade_interactive(trade, dry_run)` | Execute one trade |
| `execute_batch_interactive(trades, dry_run)` | Execute multiple |
| `check_portfolio_before_trade(max_loss)` | Validate buying power |
| `save_execution_log(filename)` | Export execution history |

## Troubleshooting

### "No account ID available"
- Ensure you've run `refresh_access_token()` first
- Check that your `.env` file has a valid `REFRESH_TOKEN`
- Verify Questrade API access is active

### "Symbol ID not found"
- You need to implement symbol lookup logic
- Use Questrade's symbol search API endpoint
- Map option specifications to symbol IDs

### "Insufficient buying power"
- Check account balances with `get_account_balances()`
- Reduce position size
- Ensure you're not exceeding `config.MAX_BUYING_POWER_PCT`

### Orders not executing
- Verify you've set `dry_run=False` (if intentional)
- Check order price is within current bid/ask spread
- Ensure market is open (9:30 AM - 4:00 PM ET)

## Next Steps

To enable **full live trading**:

1. **Implement Symbol Lookup**
   ```python
   def get_option_symbol_id(ticker, strike, expiry, right):
       """Convert option specs to Questrade symbol ID"""
       # Use Questrade symbol search API
       # Return symbol ID
       pass
   ```

2. **Add Quote Fetching**
   ```python
   def get_current_quote(symbol_id):
       """Get real-time bid/ask for limit pricing"""
       # Fetch from Questrade quotes API
       # Return bid, ask, mid
       pass
   ```

3. **Complete Strategy Mapping**
   - Build order legs for each strategy type
   - Handle quantity ratios
   - Set appropriate limit prices

4. **Add Error Handling**
   - API rate limiting
   - Order rejection handling
   - Position reconciliation

5. **Testing Checklist**
   - [ ] Test all strategies in paper account
   - [ ] Verify P&L calculations
   - [ ] Test order cancellation
   - [ ] Test with market/limit orders
   - [ ] Verify buying power checks
   - [ ] Test error scenarios

## Disclaimer

**This code is provided as a framework and educational tool.**

- ⚠️ Trading options involves substantial risk of loss
- ⚠️ Test thoroughly in paper trading before going live
- ⚠️ You are responsible for all trades executed
- ⚠️ No warranty or guarantee of functionality
- ⚠️ Not financial advice

Always review orders carefully and understand the risks before trading.

---

**Version**: 1.0.0 (January 2025)
**Status**: Framework ready - requires symbol lookup implementation for production use
