"""
Configuration parameters for Questrade spread analyzer
"""

# Strategy selection thresholds
IV_LOW_THRESHOLD = 0.3      # Below this is considered low IV
IV_HIGH_THRESHOLD = 0.6     # Above this is considered high IV

# Delta targets for option selection
DELTA_ATM = 0.5             # At-the-money delta target
DELTA_SHORT_LEG = 0.3       # Delta for short legs in iron condor/credit spreads
DELTA_LONG_OPTION = 0.5     # Delta for long calls/puts

# Spread construction parameters
SPREAD_STRIKE_WIDTH = 5     # Number of strikes between long and short legs
SPREAD_MIN_WIDTH = 1        # Minimum strike difference for spreads

# Quote validation parameters
MIN_VOLUME = 10             # Minimum option volume for valid quote
MAX_SPREAD_PCT = 0.30       # Maximum bid-ask spread as % of bid price

# Option quote fetching
ATM_WINDOW_PCT = 5          # Percentage window around ATM for quote fetching
CHUNK_SIZE = 80             # Number of IDs per API request chunk

# Trend analysis parameters
TREND_SMA_SHORT = 10        # Short-term SMA period (days)
TREND_SMA_LONG = 30         # Long-term SMA period (days)
TREND_BULLISH_THRESHOLD = 1.01  # SMA ratio for bullish signal
TREND_BEARISH_THRESHOLD = 0.99  # SMA ratio for bearish signal
TREND_LOOKBACK_DAYS = 50    # Historical candles to fetch

# IV rank calculation
IV_LOOKBACK_DAYS = 252      # Trading days for IV percentile (1 year)
IV_PERCENTILE_WINDOW = 30   # Days to use for current IV calculation

# Ratio backspread parameters
RATIO_LONG_COUNT = 2        # Number of long options in ratio spread
RATIO_SHORT_COUNT = 1       # Number of short options in ratio spread

# Calendar spread parameters
CALENDAR_FRONT_DTE = 30     # Days to expiration for front month
CALENDAR_BACK_DTE = 60      # Days to expiration for back month
CALENDAR_DTE_TOLERANCE = 7  # Days tolerance for expiry selection

# Risk management
MAX_POSITION_RISK_PCT = 0.02    # Max 2% account risk per position
MAX_PORTFOLIO_RISK_PCT = 0.10   # Max 10% total portfolio risk
MIN_PROB_PROFIT = 0.40          # Minimum 40% probability of profit
MAX_BUYING_POWER_PCT = 0.20     # Max 20% buying power per trade

# File paths
STRATEGY_OUTPUT_FILE = "strategy_output_latest.csv"
TRADE_OUTPUT_FILE = "trade_recommendations.csv"
TRADE_OUTPUT_DETAILED_FILE = "trade_recommendations_detailed.csv"
WATCHLIST_FILE = "watchlist.txt"

# API rate limiting
API_REQUESTS_PER_SECOND = 2     # Max API calls per second
API_REQUEST_DELAY = 0.5         # Delay between requests (seconds)

# Retry parameters
MAX_RETRIES = 2                 # Maximum API retry attempts
RETRY_DELAY = 1                 # Delay between retries (seconds)

# Debug settings
SAVE_DEBUG_JSON = True          # Save API responses for debugging
CLEANUP_TEMP_FILES = True       # Clean up temp files after run
