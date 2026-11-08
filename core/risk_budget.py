#!/usr/bin/env python3
"""
OmniTradePro - Mathematical Risk Budget & Profit Hurdle Evaluator
Platform: Windows 10/11 64-bit | Python 3.10+
Calculates precise position sizing from a 10% risk floor and strictly enforces
the mandatory ₹70.0 gross profit hurdle (₹60.0 round-trip statutory friction buffer)
with uncapped continuous intraday session execution.
"""

import math
from typing import Dict, Any, Optional, Tuple


class RiskBudget:
    """
    Evaluates position sizing against strict mathematical risk constraints:
    - 10% maximum capital allocation risk
    - Mandatory ₹60 statutory friction deduction (brokerage + STT + turnover + GST)
    - Minimum ₹70.0 gross profit trigger (guaranteeing >= ₹10.0 net profit)
    - Zero arbitrary daily trade count caps
    """
    FRICTION_BUFFER_INR = 60.0
    MIN_GROSS_PROFIT_TRIGGER_INR = 70.0
    MIN_NET_PROFIT_HURDLE_INR = 10.0
    MAX_CAPITAL_RISK_RATIO = 0.10  # 10% floor
    MAX_SLIPPAGE_PCT = 0.0008      # 0.08% / 8 bps dynamic slippage guardrail

    # Front-page execution and risk controller state
    _current_mode: str = "PAPER"
    _user_trade_capital: float = 1000.0
    _user_risk_percentage: float = 5.0
    _user_max_sl: float = 80.0
    _user_daily_drawdown_pct: float = 10.0

    @classmethod
    def update_risk_parameters(
        cls,
        mode: str,
        trade_capital: float,
        max_sl: float,
        risk_percentage: Optional[float] = None,
        daily_drawdown_pct: Optional[float] = None
    ) -> None:
        """Global update hook called when front-page or RMS risk controller applies new rules."""
        clean_mode = str(mode).strip().upper()
        if clean_mode in ("PAPER", "LIVE"):
            cls._current_mode = clean_mode
        if trade_capital > 0:
            cls._user_trade_capital = float(trade_capital)
        if max_sl > 0:
            cls._user_max_sl = float(max_sl)
        if risk_percentage is not None and float(risk_percentage) > 0:
            cls._user_risk_percentage = float(risk_percentage)
            cls.MAX_CAPITAL_RISK_RATIO = float(risk_percentage) / 100.0
        elif trade_capital > 0 and max_sl > 0:
            cls._user_risk_percentage = round((float(max_sl) / float(trade_capital)) * 100.0, 1)
            cls.MAX_CAPITAL_RISK_RATIO = cls._user_risk_percentage / 100.0
        if daily_drawdown_pct is not None and float(daily_drawdown_pct) > 0:
            cls._user_daily_drawdown_pct = float(daily_drawdown_pct)

    @classmethod
    def get_risk_parameters(cls) -> Dict[str, Any]:
        """Returns the currently active user risk control parameters."""
        return {
            "mode": cls._current_mode,
            "trade_capital": cls._user_trade_capital,
            "risk_percentage": cls._user_risk_percentage,
            "max_sl": cls._user_max_sl,
            "daily_drawdown_pct": cls._user_daily_drawdown_pct
        }

    @classmethod
    def calculate_effective_capital(
        cls,
        mode: str,
        user_allocated_capital: float,
        account_balance: Optional[float] = None
    ) -> float:
        """
        Determines effective capital ceiling:
        - LIVE: min(account_balance, user_allocated_capital) if account_balance > 0, else user_allocated_capital
        - PAPER: user_allocated_capital
        """
        normalized_mode = str(mode).strip().upper()
        user_cap = float(user_allocated_capital) if user_allocated_capital > 0 else cls._user_trade_capital
        if normalized_mode == "LIVE":
            if account_balance is not None and account_balance > 0:
                return round(min(float(account_balance), user_cap), 2)
            return user_cap
        else:
            return user_cap

    @classmethod
    def calculate_uniform_lot_size(
        cls,
        entry_price: float,
        effective_capital: float,
        leverage: float = 5.0
    ) -> int:
        """
        Uniform lot quantity calculation:
        qty = floor((effective_capital * leverage) / entry_price)
        Returns 0 if margin is insufficient to buy even 1 lot/share.
        """
        if entry_price <= 0.0 or effective_capital <= 0.0:
            return 0
        raw_qty = math.floor((effective_capital * leverage) / entry_price)
        return int(max(0, raw_qty))

    @classmethod
    def derive_bracket_stop_loss(
        cls,
        entry_price: float,
        side: str,
        quantity: int,
        user_max_sl: float
    ) -> float:
        """
        Dynamically calculates bracket stop-loss price such that:
        abs(entry_price - sl_trigger_price) * qty <= user_max_sl
        """
        if entry_price <= 0.0 or quantity <= 0 or user_max_sl <= 0.0:
            return 0.0
        max_dist_per_share = user_max_sl / quantity
        normalized_side = str(side).strip().upper()
        if normalized_side == "BUY":
            sl_price = max(0.05, entry_price - max_dist_per_share)
        else:  # SELL / SHORT
            sl_price = entry_price + max_dist_per_share
        return round(sl_price, 2)

    @classmethod
    def is_circuit_breaker_tripped(
        cls,
        cumulative_realized_loss: float,
        user_max_sl: float,
        daily_floor: Optional[float] = None
    ) -> tuple[bool, str]:
        """
        Checks if cumulative intraday realized loss >= (user_max_sl * 2.5) or dynamic daily floor.
        Returns: (is_tripped: bool, reason: str)
        """
        loss = abs(float(cumulative_realized_loss))
        sl_threshold = round(user_max_sl * 2.5, 2)
        if loss >= sl_threshold:
            return True, f"Cumulative intraday realized loss ₹{loss:.2f} >= 2.5x max SL limit (₹{sl_threshold:.2f})."
        
        effective_floor = daily_floor if (daily_floor is not None and daily_floor > 0) else round(cls._user_trade_capital * (cls._user_daily_drawdown_pct / 100.0), 2)
        if effective_floor > 0 and loss >= effective_floor:
            return True, f"Cumulative intraday realized loss ₹{loss:.2f} >= statutory daily floor (₹{effective_floor:.2f})."
        return False, "OK"

    @classmethod
    def calculate_marketable_limit_price(
        cls,
        price: float,
        side: str,
        max_slippage_pct: float = 0.0008
    ) -> float:
        """
        Calculates marketable limit price to guard against execution slippage and flash crashes.
        BUY: price * (1 + max_slippage_pct)
        SELL: price * (1 - max_slippage_pct)
        """
        if price <= 0.0:
            return 0.0
        normalized_side = str(side).strip().upper()
        if normalized_side == "BUY":
            return round(price * (1.0 + max_slippage_pct), 2)
        else:
            return round(price * (1.0 - max_slippage_pct), 2)

    @classmethod
    def is_slippage_acceptable(
        cls,
        requested_price: float,
        current_price: float,
        side: str,
        max_slippage_pct: float = 0.0008
    ) -> tuple[bool, float]:
        """
        Verifies if price drift between signal generation and routing is within the 0.08% boundary.
        Returns: (is_acceptable: bool, drift_pct: float)
        """
        if requested_price <= 0.0 or current_price <= 0.0:
            return False, 1.0

        normalized_side = str(side).strip().upper()
        if normalized_side == "BUY":
            drift = (current_price - requested_price) / requested_price
        else:  # SELL / SHORT
            drift = (requested_price - current_price) / requested_price

        # Adverse drift check (favorable drift is always acceptable)
        if drift > max_slippage_pct:
            return False, round(drift, 6)
        return True, round(drift, 6)


    @classmethod
    def calculate_position_size(
        cls,
        capital_inr: float,
        entry_price: float,
        stop_loss: float,
        target_price: float,
        margin_leverage: float = 5.0,
        risk_ratio: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Calculates exact share sizing and evaluates statutory fee hurdle clearance.
        Formula:
            Max Risk = Capital * Risk Ratio (default user_risk_percentage / 100.0)
            Per Share Risk = |Entry Price - Stop Loss|
            Quantity = max(1, floor(Max Risk / Per Share Risk))
        """
        if capital_inr <= 0.0:
            raise ValueError(f"Capital must be > 0, got {capital_inr}")
        if entry_price <= 0.0:
            raise ValueError(f"Entry price must be > 0, got {entry_price}")

        # 1. Compute Max Risk (Dynamic user risk percentage or custom ratio)
        effective_ratio = float(risk_ratio) if (risk_ratio is not None and risk_ratio > 0) else (cls._user_risk_percentage / 100.0)
        max_risk = capital_inr * effective_ratio

        # 2. Compute Per-Share Risk
        per_share_risk = abs(entry_price - stop_loss)
        if per_share_risk <= 0.0:
            per_share_risk = entry_price * 0.005  # Default 0.5% minimal distance

        # 3. Base Quantity by Risk Allocation
        raw_quantity = math.floor(max_risk / per_share_risk)
        quantity = max(1, int(raw_quantity))

        # 4. Enforce Committed Capital Constraint (with margin leverage support)
        # For standard Indian Intraday MIS, leverage is typically 5x (20% margin requirement)
        margin_per_share = entry_price / margin_leverage if margin_leverage > 0 else entry_price
        max_allowed_shares = max(1, int(capital_inr / margin_per_share))
        
        # Quantity cannot exceed capital leverage capacity
        quantity = min(quantity, max_allowed_shares)

        # 5. Expected Profit & Friction Calculation
        reward_per_share = abs(target_price - entry_price)
        gross_profit_expected = round(quantity * reward_per_share, 2)
        friction_buffer = cls.FRICTION_BUFFER_INR
        net_profit_expected = round(gross_profit_expected - friction_buffer, 2)

        # 6. Strict ₹70 Gross Profit Hurdle (No-Skip Rule)
        if gross_profit_expected >= cls.MIN_GROSS_PROFIT_TRIGGER_INR and net_profit_expected >= cls.MIN_NET_PROFIT_HURDLE_INR:
            can_execute = True
            reason = (
                f"Execution approved: Gross Profit ₹{gross_profit_expected:.2f} >= ₹{cls.MIN_GROSS_PROFIT_TRIGGER_INR:.2f} "
                f"(Net Profit ₹{net_profit_expected:.2f} >= ₹{cls.MIN_NET_PROFIT_HURDLE_INR:.2f} after ₹{friction_buffer:.2f} friction)."
            )
        else:
            can_execute = False
            reason = (
                f"Execution blocked by fee hurdle: Gross Profit ₹{gross_profit_expected:.2f} < ₹{cls.MIN_GROSS_PROFIT_TRIGGER_INR:.2f} "
                f"(Net Profit ₹{net_profit_expected:.2f} < ₹{cls.MIN_NET_PROFIT_HURDLE_INR:.2f} after ₹{friction_buffer:.2f} statutory friction buffer)."
            )

        return {
            "quantity": int(quantity),
            "max_risk_inr": round(max_risk, 2),
            "gross_profit_expected": round(gross_profit_expected, 2),
            "friction_buffer": round(friction_buffer, 2),
            "net_profit_expected": round(net_profit_expected, 2),
            "can_execute": can_execute,
            "reason": reason
        }

