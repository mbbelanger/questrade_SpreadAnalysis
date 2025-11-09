# Questrade Options Spread Analyzer

A comprehensive Python-based system for analyzing options spreads using the Questrade API. This tool identifies prospect tickers, analyzes market conditions, recommends appropriate strategies, and generates detailed trade recommendations with full risk analysis.

## Features

- **Automated Strategy Selection**: Analyzes market trend and IV rank to recommend optimal strategies
- **9 Strategy Support**: Implements all major options strategies:
  - Bull Call Spread
  - Bear Put Spread
  - Iron Condor
  - Long Call
  - Long Put
  - Straddle
  - Calendar Spread
  - Call Ratio Backspread
  - Put Ratio Backspread
- **Comprehensive Risk Analysis**: Calculates max loss, max profit, breakeven, risk/reward ratio, and probability of profit for each trade
- **Questrade API Integration**: Full OAuth2 authentication with automatic token refresh
- **Configurable Parameters**: All magic numbers (deltas, IV thresholds, strike widths) in config file

## Project Structure

```
tradep1/
├── strategy_selector.py      # Stage 1: Analyzes tickers and selects strategies
├── trade_generator.py         # Stage 2: Generates specific trade recommendations
├── trend_analysis.py          # Helper: Detects market trend using SMA
├── questrade_utils.py         # Shared: API authentication and utilities
├── risk_analysis.py           # Risk calculations for all strategies
├── config.py                  # Configuration parameters
├── watchlist.txt              # Input: List of tickers to analyze
├── strategy_output_latest.csv # Intermediate: Strategy recommendations
├── .env                       # Credentials: Questrade refresh token
└── README.md                  # This file
```

## Setup Instructions

### 1. Prerequisites

- Python 3.7 or higher
- Questrade account with API access
- Questrade refresh token (obtain from Questrade API portal)

### 2. Installation

```bash
# Clone or download the repository
cd tradep1

# Create virtual environment (recommended)
python -m venv .venv

# Activate virtual environment
# On Windows:
.venv\Scripts\activate
# On macOS/Linux:
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Configuration

1. **Set up Questrade API credentials**:
   - Log into Questrade
   - Navigate to API portal and generate a refresh token
   - Create `.env` file in project root:
   ```
   QUESTRADE_REFRESH_TOKEN=your_refresh_token_here
   ```

2. **Create watchlist**:
   - Create `watchlist.txt` in project root
   - Add one ticker per line:
   ```
   QQQ
   SPY
   AAPL
   ```

3. **Adjust configuration** (optional):
   - Edit [config.py](config.py) to customize:
     - IV thresholds
     - Delta targets
     - Spread strike widths
     - Risk management parameters

## Usage

### Basic Workflow

The system operates in two stages:

#### Stage 1: Strategy Selection

```bash
python strategy_selector.py
```

This script:
1. Reads tickers from `watchlist.txt`
2. Fetches market data for each ticker
3. Detects trend (bullish/bearish/neutral) using SMA analysis
4. Calculates IV rank
5. Selects appropriate strategy based on trend + IV matrix
6. Outputs recommendations to `strategy_output_latest.csv`

**Strategy Selection Matrix**:

| Trend     | IV < 0.3           | IV 0.3-0.6    | IV > 0.6              |
|-----------|--------------------| --------------|-----------------------|
| Bullish   | bull_call_spread   | long_call     | call_ratio_backspread |
| Bearish   | bear_put_spread    | long_put      | put_ratio_backspread  |
| Neutral   | calendar_spread    | straddle      | iron_condor           |

#### Stage 2: Trade Generation

```bash
python trade_generator.py
```

This script:
1. Reads strategies from `strategy_output_latest.csv`
2. Fetches option chains and quotes
3. Identifies specific strikes and prices for each strategy
4. Calculates comprehensive risk metrics
5. Outputs detailed trade recommendations to console

### Example Output

```
[2025-01-09 10:30:15] QQQ 2025-01-17: BULL CALL SPREAD - Buy 450C @5.20 / Sell 455C @3.10

  📊 RISK ANALYSIS (BULL_CALL_SPREAD)
  ├─ Max Loss: $2.10
  ├─ Max Profit: $2.90
  ├─ Breakeven: $452.10
  ├─ Risk/Reward: 1.38
  └─ Prob of Profit: ~50%
```

## Configuration Reference

Key parameters in [config.py](config.py):

### Strategy Selection
- `IV_LOW_THRESHOLD = 0.3` - Below this is low IV
- `IV_HIGH_THRESHOLD = 0.6` - Above this is high IV

### Delta Targets
- `DELTA_ATM = 0.5` - At-the-money delta
- `DELTA_SHORT_LEG = 0.3` - Short legs in iron condor
- `DELTA_LONG_OPTION = 0.5` - Long calls/puts

### Spread Parameters
- `SPREAD_STRIKE_WIDTH = 5` - Strikes between legs
- `MIN_VOLUME = 10` - Minimum option volume
- `MAX_SPREAD_PCT = 0.30` - Max bid-ask spread

### Trend Analysis
- `TREND_SMA_SHORT = 10` - Short-term SMA period
- `TREND_SMA_LONG = 30` - Long-term SMA period

## Risk Analysis

Each strategy includes comprehensive risk metrics:

### Vertical Spreads (Bull Call, Bear Put)
- Max Loss: Net debit paid
- Max Profit: Strike width - net debit
- Breakeven: Long strike ± net debit
- Risk/Reward Ratio
- Probability of Profit (based on delta)

### Iron Condor
- Max Loss: Wing width - net credit
- Max Profit: Net credit received
- Breakeven Upper & Lower
- Probability of Profit (based on strike range)

### Long Options (Call/Put)
- Max Loss: Premium paid
- Max Profit: Unlimited (call) or strike - premium (put)
- Breakeven: Strike ± premium
- Delta-based probability

### Ratio Backspreads
- Max Loss: At long strike
- Max Profit: Unlimited (calls) or substantial (puts)
- Net Credit/Debit status
- Upper & Lower Breakevens

### Calendar Spreads
- Max Loss: Net debit
- Max Profit: Estimated time decay capture
- DTE for both months
- Optimal scenario description

## Troubleshooting

### Common Issues

**"Refresh token not found in .env file"**
- Ensure `.env` file exists in project root
- Check that `QUESTRADE_REFRESH_TOKEN` is set correctly

**"No option quotes found"**
- Ticker may not have options available
- Try a different expiration date
- Check if market is open

**"Empty strike list" or "No greeks returned"**
- Questrade API may be experiencing issues
- Greeks endpoint can be unreliable - system falls back to bid-ask spread proxy
- Try again after a few minutes

**"Strategy not yet implemented"**
- All 9 strategies are now implemented as of latest version
- Check that you're running the updated `trade_generator.py`

### Debug Mode

Temporary JSON files are saved for debugging:
- `temp-chain-{symbol_id}.json` - Option chain data
- `temp-quotes-{symbol_id}-{expiry}.json` - Quote data
- `temp-{SYMBOL}-{strike}-quotes.json` - IV calculation quotes
- `temp-{SYMBOL}-{strike}-greeks.json` - Greeks data

These files can help diagnose API issues.

## Architecture

### Data Flow

```
watchlist.txt
    ↓
strategy_selector.py
    ├─ trend_analysis.py (SMA-based trend detection)
    ├─ questrade_utils.py (API calls)
    └─ config.py (parameters)
    ↓
strategy_output_latest.csv
    ↓
trade_generator.py
    ├─ questrade_utils.py (API calls)
    ├─ risk_analysis.py (risk calculations)
    └─ config.py (parameters)
    ↓
Console Output (trade recommendations with risk metrics)
```

### Authentication Flow

1. Load `QUESTRADE_REFRESH_TOKEN` from `.env`
2. Exchange refresh token for access token via OAuth2
3. Receive new API server URL + access token + new refresh token
4. Auto-save new refresh token back to `.env`
5. Use Bearer token for all subsequent API calls
6. Access tokens expire after 30 minutes (future: implement auto-refresh)

## Limitations & Future Enhancements

### Current Limitations

1. **No Trade Execution**: System only generates recommendations - no actual order placement
2. **IV Rank Placeholder**: Uses 50%-150% range instead of true historical IV percentiles
3. **No Position Tracking**: Cannot track open positions or P&L
4. **No Rate Limiting**: May hit API limits with large watchlists
5. **Manual Workflow**: Two-step process requires running scripts separately

### Planned Enhancements

- [ ] Implement Questrade order placement API
- [ ] Add interactive trade approval workflow
- [ ] Fix IV rank to use 52-week historical percentiles
- [ ] Add position tracking and P&L monitoring
- [ ] Implement API rate limiting
- [ ] Add account buying power validation
- [ ] Save trade recommendations to CSV file
- [ ] Add cleanup for temporary JSON files
- [ ] Implement token refresh middleware for long-running jobs
- [ ] Add backtesting capability
- [ ] Create web dashboard for visualization

## Contributing

This is a personal trading tool. Use at your own risk.

## Disclaimer

**This software is for educational purposes only. Trading options involves substantial risk of loss. Past performance does not guarantee future results. Always paper trade first and never risk money you cannot afford to lose. The authors are not responsible for any financial losses incurred using this software.**

## License

MIT License - See LICENSE file for details

## Support

For issues or questions:
1. Check the Troubleshooting section above
2. Review temporary JSON debug files
3. Verify Questrade API status
4. Check that all dependencies are installed

## Version History

### v1.0.0 (Current)
- ✅ All 9 strategies implemented
- ✅ Comprehensive risk analysis
- ✅ Configurable parameters
- ✅ Shared utilities module
- ✅ Auto-token refresh
- ⚠️ IV rank uses placeholder calculation
- ⚠️ No trade execution capability

---

**Happy Trading! Remember to always validate trades before execution and never trade with money you can't afford to lose.**
