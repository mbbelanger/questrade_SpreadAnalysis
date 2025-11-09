"""
Risk analysis calculations for option strategies
"""
import math
from typing import Dict, List, Optional
from datetime import datetime

def calculate_days_to_expiry(expiry_date: str) -> int:
    """Calculate days to expiration from ISO date string"""
    expiry = datetime.fromisoformat(expiry_date.split('T')[0])
    today = datetime.now()
    return (expiry - today).days

def calculate_bull_call_spread_risk(long_strike: float, short_strike: float,
                                    long_price: float, short_price: float) -> Dict:
    """
    Calculate risk metrics for bull call spread

    Returns dict with:
    - max_loss: Maximum possible loss
    - max_profit: Maximum possible profit
    - breakeven: Breakeven price at expiration
    - risk_reward_ratio: Ratio of max profit to max loss
    - prob_profit: Estimated probability of profit (simplified)
    """
    net_debit = long_price - short_price
    width = short_strike - long_strike

    max_loss = net_debit
    max_profit = width - net_debit
    breakeven = long_strike + net_debit
    risk_reward_ratio = max_profit / max_loss if max_loss > 0 else 0

    # Simplified prob of profit: assume ~50% if ATM, adjust based on position
    # This is a placeholder - real calculation would use delta or BSM
    prob_profit = 0.50

    return {
        "max_loss": round(max_loss, 2),
        "max_profit": round(max_profit, 2),
        "breakeven": round(breakeven, 2),
        "risk_reward_ratio": round(risk_reward_ratio, 2),
        "prob_profit": round(prob_profit, 2),
        "strategy_type": "bull_call_spread"
    }

def calculate_bear_put_spread_risk(long_strike: float, short_strike: float,
                                   long_price: float, short_price: float) -> Dict:
    """Calculate risk metrics for bear put spread"""
    net_debit = long_price - short_price
    width = long_strike - short_strike

    max_loss = net_debit
    max_profit = width - net_debit
    breakeven = long_strike - net_debit
    risk_reward_ratio = max_profit / max_loss if max_loss > 0 else 0

    prob_profit = 0.50

    return {
        "max_loss": round(max_loss, 2),
        "max_profit": round(max_profit, 2),
        "breakeven": round(breakeven, 2),
        "risk_reward_ratio": round(risk_reward_ratio, 2),
        "prob_profit": round(prob_profit, 2),
        "strategy_type": "bear_put_spread"
    }

def calculate_iron_condor_risk(long_put_strike: float, short_put_strike: float,
                               short_call_strike: float, long_call_strike: float,
                               long_put_price: float, short_put_price: float,
                               short_call_price: float, long_call_price: float) -> Dict:
    """Calculate risk metrics for iron condor"""
    net_credit = (short_put_price + short_call_price) - (long_put_price + long_call_price)
    put_width = short_put_strike - long_put_strike
    call_width = long_call_strike - short_call_strike
    max_wing_width = max(put_width, call_width)

    max_profit = net_credit
    max_loss = max_wing_width - net_credit
    breakeven_lower = short_put_strike - net_credit
    breakeven_upper = short_call_strike + net_credit
    risk_reward_ratio = max_profit / max_loss if max_loss > 0 else 0

    # Probability of profit based on wing widths and credit
    # Simplified: assume symmetric distribution
    profit_range = short_call_strike - short_put_strike
    total_range = long_call_strike - long_put_strike
    prob_profit = profit_range / total_range if total_range > 0 else 0.5

    return {
        "max_loss": round(max_loss, 2),
        "max_profit": round(max_profit, 2),
        "breakeven_lower": round(breakeven_lower, 2),
        "breakeven_upper": round(breakeven_upper, 2),
        "risk_reward_ratio": round(risk_reward_ratio, 2),
        "prob_profit": round(prob_profit, 2),
        "strategy_type": "iron_condor"
    }

def calculate_straddle_risk(strike: float, call_price: float, put_price: float,
                           underlying_price: float, dte: int) -> Dict:
    """Calculate risk metrics for long straddle"""
    total_cost = call_price + put_price

    max_loss = total_cost
    max_profit = float('inf')  # Theoretically unlimited
    breakeven_lower = strike - total_cost
    breakeven_upper = strike + total_cost

    # Prob of profit depends on implied move vs actual move
    # Simplified: use cost relative to underlying
    implied_move_pct = total_cost / underlying_price if underlying_price > 0 else 0

    # Estimate prob profit based on typical ATM straddle success rate
    prob_profit = 0.35  # Straddles typically have lower prob of profit

    return {
        "max_loss": round(max_loss, 2),
        "max_profit": "unlimited",
        "breakeven_lower": round(breakeven_lower, 2),
        "breakeven_upper": round(breakeven_upper, 2),
        "implied_move_pct": round(implied_move_pct * 100, 2),
        "prob_profit": round(prob_profit, 2),
        "strategy_type": "straddle"
    }

def calculate_long_call_risk(strike: float, call_price: float,
                             underlying_price: float, delta: Optional[float] = None) -> Dict:
    """Calculate risk metrics for long call"""
    max_loss = call_price
    max_profit = float('inf')  # Theoretically unlimited
    breakeven = strike + call_price

    # Use delta as proxy for prob of profit if available
    prob_profit = abs(delta) if delta else 0.50

    return {
        "max_loss": round(max_loss, 2),
        "max_profit": "unlimited",
        "breakeven": round(breakeven, 2),
        "prob_profit": round(prob_profit, 2),
        "delta": round(delta, 3) if delta else None,
        "strategy_type": "long_call"
    }

def calculate_long_put_risk(strike: float, put_price: float,
                            underlying_price: float, delta: Optional[float] = None) -> Dict:
    """Calculate risk metrics for long put"""
    max_loss = put_price
    max_profit = strike - put_price  # Max profit when stock goes to 0
    breakeven = strike - put_price

    # Use delta as proxy for prob of profit if available
    prob_profit = abs(delta) if delta else 0.50

    return {
        "max_loss": round(max_loss, 2),
        "max_profit": round(max_profit, 2),
        "breakeven": round(breakeven, 2),
        "prob_profit": round(prob_profit, 2),
        "delta": round(delta, 3) if delta else None,
        "strategy_type": "long_put"
    }

def calculate_call_ratio_backspread_risk(short_strike: float, long_strike: float,
                                        short_price: float, long_price: float,
                                        short_qty: int = 1, long_qty: int = 2) -> Dict:
    """Calculate risk metrics for call ratio backspread (typically 1x2)"""
    net_credit_debit = (short_price * short_qty) - (long_price * long_qty)
    is_credit = net_credit_debit > 0

    # Max loss occurs at long strike
    max_loss = (long_strike - short_strike) * short_qty - net_credit_debit

    # Max profit is unlimited above upper breakeven
    max_profit = float('inf')

    # Breakeven calculations
    if is_credit:
        # Lower BE: short strike - net credit
        breakeven_lower = short_strike - abs(net_credit_debit)
        # Upper BE: long strike + max loss
        breakeven_upper = long_strike + (max_loss / (long_qty - short_qty))
    else:
        # Only upper breakeven if net debit
        breakeven_lower = None
        breakeven_upper = long_strike + (abs(net_credit_debit) / (long_qty - short_qty))

    prob_profit = 0.45  # Moderate probability

    return {
        "max_loss": round(max_loss, 2),
        "max_profit": "unlimited",
        "net_credit_debit": round(net_credit_debit, 2),
        "is_credit": is_credit,
        "breakeven_lower": round(breakeven_lower, 2) if breakeven_lower else None,
        "breakeven_upper": round(breakeven_upper, 2),
        "prob_profit": round(prob_profit, 2),
        "strategy_type": "call_ratio_backspread"
    }

def calculate_put_ratio_backspread_risk(short_strike: float, long_strike: float,
                                       short_price: float, long_price: float,
                                       short_qty: int = 1, long_qty: int = 2) -> Dict:
    """Calculate risk metrics for put ratio backspread (typically 1x2)"""
    net_credit_debit = (short_price * short_qty) - (long_price * long_qty)
    is_credit = net_credit_debit > 0

    # Max loss occurs at long strike
    max_loss = (short_strike - long_strike) * short_qty - net_credit_debit

    # Max profit when underlying goes to 0
    max_profit = long_strike * (long_qty - short_qty) + net_credit_debit

    # Breakeven calculations
    if is_credit:
        # Upper BE: short strike + net credit
        breakeven_upper = short_strike + abs(net_credit_debit)
        # Lower BE: based on max profit potential
        breakeven_lower = long_strike - (max_loss / (long_qty - short_qty))
    else:
        breakeven_upper = None
        breakeven_lower = long_strike - (abs(net_credit_debit) / (long_qty - short_qty))

    prob_profit = 0.45

    return {
        "max_loss": round(max_loss, 2),
        "max_profit": round(max_profit, 2),
        "net_credit_debit": round(net_credit_debit, 2),
        "is_credit": is_credit,
        "breakeven_lower": round(breakeven_lower, 2) if breakeven_lower else None,
        "breakeven_upper": round(breakeven_upper, 2) if breakeven_upper else None,
        "prob_profit": round(prob_profit, 2),
        "strategy_type": "put_ratio_backspread"
    }

def calculate_calendar_spread_risk(front_price: float, back_price: float,
                                   strike: float, front_dte: int, back_dte: int) -> Dict:
    """Calculate risk metrics for calendar spread"""
    net_debit = back_price - front_price

    # Max loss is the net debit paid
    max_loss = net_debit

    # Max profit occurs when front expires worthless and back retains value
    # Simplified: assume back month retains ~70% of original value
    max_profit = front_price * 0.5  # Conservative estimate

    risk_reward_ratio = max_profit / max_loss if max_loss > 0 else 0

    # Calendar spreads benefit from time decay and low volatility
    prob_profit = 0.55

    return {
        "max_loss": round(max_loss, 2),
        "max_profit": round(max_profit, 2),
        "net_debit": round(net_debit, 2),
        "risk_reward_ratio": round(risk_reward_ratio, 2),
        "optimal_scenario": f"Price stays near {strike} with declining IV",
        "front_dte": front_dte,
        "back_dte": back_dte,
        "prob_profit": round(prob_profit, 2),
        "strategy_type": "calendar_spread"
    }

def format_risk_analysis(risk: Dict) -> str:
    """Format risk analysis as readable string"""
    lines = [f"\n  📊 RISK ANALYSIS ({risk.get('strategy_type', 'unknown').upper()})"]
    lines.append(f"  ├─ Max Loss: ${risk.get('max_loss', 'N/A')}")
    lines.append(f"  ├─ Max Profit: ${risk.get('max_profit', 'N/A')}")

    if 'breakeven' in risk:
        lines.append(f"  ├─ Breakeven: ${risk['breakeven']}")
    if 'breakeven_lower' in risk and risk['breakeven_lower']:
        lines.append(f"  ├─ Breakeven Lower: ${risk['breakeven_lower']}")
    if 'breakeven_upper' in risk and risk['breakeven_upper']:
        lines.append(f"  ├─ Breakeven Upper: ${risk['breakeven_upper']}")

    if 'risk_reward_ratio' in risk:
        lines.append(f"  ├─ Risk/Reward: {risk['risk_reward_ratio']}")

    if 'prob_profit' in risk:
        prob_pct = risk['prob_profit'] * 100 if risk['prob_profit'] <= 1 else risk['prob_profit']
        lines.append(f"  └─ Prob of Profit: ~{prob_pct:.0f}%")

    return '\n'.join(lines)
