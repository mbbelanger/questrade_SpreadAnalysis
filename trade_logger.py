"""
Trade recommendation logger - saves trades to CSV
"""
import csv
from datetime import datetime
import config

class TradeLogger:
    def __init__(self, filename=None):
        self.filename = filename or config.TRADE_OUTPUT_FILE
        self.trades = []

    def log_trade(self, symbol, strategy, expiry, trade_desc, risk_metrics):
        """
        Log a trade recommendation

        Args:
            symbol: Ticker symbol
            strategy: Strategy name
            expiry: Expiration date
            trade_desc: Human-readable trade description
            risk_metrics: Dict with risk analysis results
        """
        trade_record = {
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'symbol': symbol,
            'strategy': strategy,
            'expiry': expiry,
            'dte': risk_metrics.get('front_dte') or risk_metrics.get('dte', ''),
            'trade_description': trade_desc,
            'max_loss': risk_metrics.get('max_loss', ''),
            'max_profit': risk_metrics.get('max_profit', ''),
            'breakeven': risk_metrics.get('breakeven', ''),
            'breakeven_lower': risk_metrics.get('breakeven_lower', ''),
            'breakeven_upper': risk_metrics.get('breakeven_upper', ''),
            'risk_reward_ratio': risk_metrics.get('risk_reward_ratio', ''),
            'prob_profit': risk_metrics.get('prob_profit', ''),
            'net_cost_credit': risk_metrics.get('net_debit') or risk_metrics.get('net_credit_debit', '')
        }
        self.trades.append(trade_record)

    def save(self):
        """Save all logged trades to CSV"""
        if not self.trades:
            return

        with open(self.filename, 'w', newline='', encoding='utf-8') as csvfile:
            fieldnames = [
                'timestamp', 'symbol', 'strategy', 'expiry', 'dte',
                'trade_description', 'max_loss', 'max_profit',
                'breakeven', 'breakeven_lower', 'breakeven_upper',
                'risk_reward_ratio', 'prob_profit', 'net_cost_credit'
            ]
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(self.trades)

        return len(self.trades)
