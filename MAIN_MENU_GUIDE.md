# Main Menu Guide

## Updated Menu Structure

The main menu has been enhanced with the new Trade Analyzer feature:

```
======================================================================
QUESTRADE OPTIONS TRADING SYSTEM
======================================================================

MAIN MENU:
----------------------------------------------------------------------
1. Strategy Selector - Analyze watchlist and find trading opportunities
2. Trade Generator - Generate detailed trade recommendations
3. Trade Analyzer - Analyze past trade performance with current prices
4. Position Tracker - View current positions and P&L
5. Trade Executor - Execute trades from recommendations
6. Cleanup Utilities - Clean temp files and old data
7. Run Tests - Execute unit test suite

0. Exit
----------------------------------------------------------------------
```

## Complete Workflow

### Standard Trading Workflow

```
1. Strategy Selector
   ↓
   Analyzes watchlist tickers
   Determines optimal strategies based on IV, trend, etc.
   Outputs: strategy_output_latest.csv

2. Trade Generator
   ↓
   Reads strategy recommendations
   Generates detailed trade recommendations with risk analysis
   Outputs: trade_recommendations.csv (and archives old ones)

3. Trade Executor [OPTIONAL]
   ↓
   Reads trade recommendations
   Allows interactive selection and execution
   Submits orders to Questrade

4. Position Tracker [OPTIONAL]
   ↓
   Views current positions
   Monitors P&L
   Sets alerts for position changes
```

### Backtesting Workflow (New!)

```
1. Trade Analyzer (NEW!)
   ↓
   Lists archived trade_recommendations_*.csv files
   You select which date to analyze
   Fetches current market prices
   Calculates P&L for each trade
   Shows performance summary and statistics
   Outputs: trade_analysis_YYYY-MM-DD_HHMMSS.csv
```

## Menu Options Explained

### 1. Strategy Selector
**Purpose**: Find trading opportunities based on market conditions

**What it does**:
- Reads tickers from watchlist.txt
- Fetches IV data, price trends, candles
- Analyzes which strategy is optimal for each ticker
- Writes recommendations to strategy_output_latest.csv

**When to use**: At the start of trading day or when looking for new opportunities

**Input required**: watchlist.txt with ticker symbols

**Output**: strategy_output_latest.csv

---

### 2. Trade Generator
**Purpose**: Create detailed trade recommendations with risk analysis

**What it does**:
- Reads strategy_output_latest.csv
- Fetches option chains and quotes
- Selects optimal strikes and expiries
- **NEW**: For spreads, generates near/mid/long term options
- Calculates max loss, max profit, breakeven, risk/reward
- Archives old trade_recommendations.csv files
- Writes new trade_recommendations.csv

**When to use**: After running Strategy Selector

**Input required**: strategy_output_latest.csv

**Output**:
- trade_recommendations.csv (current)
- trade_recommendations_YYYY-MM-DD.csv (archived)

---

### 3. Trade Analyzer (NEW!)
**Purpose**: Backtest past recommendations against current market prices

**What it does**:
- Lists all archived trade recommendation files
- You select which date to analyze
- Fetches current option prices from Questrade API
- Calculates entry cost vs current exit value
- Detects expired options (marks as 100% loss)
- Shows P&L for each trade
- Generates comprehensive statistics:
  - Win rate
  - Total P&L
  - Best/worst trades
  - Performance by strategy
- Saves results to timestamped CSV

**When to use**:
- Daily: Check today's recommendations performance
- Weekly: Review strategy effectiveness
- Post-expiry: Learn from expired trades

**Input required**:
- Archived trade_recommendations_*.csv files
- Active Questrade API connection

**Output**: trade_analysis_YYYY-MM-DD_HHMMSS.csv

**Interactive**: Yes - prompts you to select which file to analyze

---

### 4. Position Tracker
**Purpose**: Monitor current open positions and account balance

**What it does**:
- Fetches positions from Questrade account
- Shows current P&L for each position
- Displays account balances (cash, equity, buying power)
- Saves portfolio snapshot
- Can set alerts for position changes

**When to use**: Check positions throughout trading day

**Input required**: Valid Questrade API token

**Output**: portfolio_YYYY-MM-DD_HHMMSS.csv

---

### 5. Trade Executor
**Purpose**: Execute trades from recommendations file

**What it does**:
- Reads trade_recommendations.csv
- Shows each trade with risk details
- Prompts for DRY RUN or LIVE mode
- For each trade:
  - Shows details
  - Prompts for quantity
  - Asks for confirmation
  - Submits order to Questrade (if LIVE mode)
- Logs all executions

**When to use**: After reviewing trade recommendations

**Input required**:
- trade_recommendations.csv
- Valid Questrade API token with trading permissions

**Output**: execution_log_YYYY-MM-DD_HHMMSS.csv

**⚠️ Warning**: LIVE mode submits real orders! Be careful!

---

### 6. Cleanup Utilities
**Purpose**: Remove old temporary files

**What it does**:
- Lists temp-*.json files
- Offers cleanup options:
  - Files older than 24 hours
  - Files older than 7 days
  - All temp files

**When to use**: Periodically to free up disk space

**Input required**: User confirmation for cleanup

---

### 7. Run Tests
**Purpose**: Execute unit test suite

**What it does**:
- Runs all unit tests
- Tests:
  - Trade analyzer functionality
  - Risk calculations
  - File operations
  - API mocking

**When to use**:
- After code changes
- Before important trading sessions
- To verify system integrity

**Output**: Test results summary

---

### 0. Exit
Exits the application

---

## Example Session

### Session 1: Find and Generate Trades
```
1. Run Strategy Selector (option 1)
   - Analyzes NVDA, TSLA, QQQ, etc.
   - Determines best strategies

2. Run Trade Generator (option 2)
   - Generates detailed recommendations
   - Creates near/mid/long term options for spreads
   - Archives old recommendations

3. [Optional] Run Trade Analyzer (option 3)
   - Analyze yesterday's recommendations
   - See how they performed
   - Decide whether to adjust strategy
```

### Session 2: Execute and Monitor
```
1. Run Trade Executor (option 5)
   - Select which trades to execute
   - Submit orders to Questrade

2. Run Position Tracker (option 4)
   - Monitor open positions
   - Track P&L throughout day
```

### Session 3: Daily Review (End of Day)
```
1. Run Trade Analyzer (option 3)
   - Select today's archived recommendations
   - See current P&L vs entry
   - Identify winning/losing strategies

2. Review results CSV
   - Import into Excel
   - Analyze patterns
   - Adjust strategy for tomorrow
```

## Tips

1. **Start with Strategy Selector**: Always run this first to get fresh opportunities

2. **Archive Auto-Saves**: Trade Generator automatically archives old files, so you never lose data

3. **Use Trade Analyzer Daily**: Track performance to improve strategy selection

4. **DRY RUN First**: Always test with DRY RUN before LIVE execution

5. **Monitor Positions**: Run Position Tracker throughout the day to stay informed

6. **Clean Up Weekly**: Use Cleanup Utilities to keep project directory tidy

7. **Run Tests After Updates**: Verify system integrity after any code changes

## Keyboard Shortcuts

- `Ctrl+C`: Exit current operation (returns to menu or exits)
- `Enter`: After each operation, press Enter to return to menu
- `0`: Quick exit from main menu

## File Organization

After running the system, your directory will contain:

```
project/
├── watchlist.txt                           # Your input tickers
├── strategy_output_latest.csv              # Strategy recommendations
├── trade_recommendations.csv               # Current recommendations
├── trade_recommendations_2025-11-10.csv    # Archived recommendations
├── trade_recommendations_2025-11-11.csv    # Archived recommendations
├── trade_analysis_2025-11-11_143022.csv    # Analysis results
├── portfolio_2025-11-11_150000.csv         # Portfolio snapshots
├── execution_log_2025-11-11_093000.csv     # Execution logs
└── temp-chain-*.json                       # Temporary API data
```

## Troubleshooting

### "No archived files found"
- Run Trade Generator first to create recommendations
- Recommendations are automatically archived each time you run the generator

### "Could not refresh API token"
- Check .env file has valid QUESTRADE_REFRESH_TOKEN
- Token may have expired - get new one from Questrade

### "Trade Analyzer shows all losses"
- Make sure you're analyzing trades from a reasonable timeframe
- Very old trades may have expired (marked as 100% loss)

### "Permission denied" errors
- Close any Excel files viewing the CSV outputs
- Run as administrator if needed

## Next Steps

After running the system:

1. Review `trade_recommendations.csv` before executing
2. Use `trade_analyzer.py` to backtest effectiveness
3. Adjust watchlist based on performance
4. Refine strategy selection criteria in config.py
