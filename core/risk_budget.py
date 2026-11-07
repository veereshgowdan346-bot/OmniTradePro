#!/usr/bin/env python3
"""
OmniTradePro - Mathematical Risk Budget & Profit Hurdle Evaluator
Platform: Windows 10/11 64-bit | Python 3.10+
Calculates precise position sizing from a 10% risk floor and strictly enforces
the mandatory ₹70.0 gross profit hurdle (₹60.0 round-trip statutory friction buffer)
with uncapped continuous intraday session execution.
"""

import math
from typing import Dict, Any


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

    @classmethod
    def calculate_position_size(
        cls,
        capital_inr: float,
        entry_price: float,
        stop_loss: float,
        target_price: float,
        margin_leverage: float = 5.0
    ) -> Dict[str, Any]:
        """
        Calculates exact share sizing and evaluates statutory fee hurdle clearance.
        Formula:
            Max Risk = Capital * 0.10
            Per Share Risk = |Entry Price - Stop Loss|
            Quantity = max(1, floor(Max Risk / Per Share Risk))
        """
        if capital_inr <= 0.0:
            raise ValueError(f"Capital must be > 0, got {capital_inr}")
        if entry_price <= 0.0:
            raise ValueError(f"Entry price must be > 0, got {entry_price}")

        # 1. Compute Max Risk (10% of Capital)
        max_risk = capital_inr * cls.MAX_CAPITAL_RISK_RATIO

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

