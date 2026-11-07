#!/usr/bin/env python3
"""
OmniTradePro - Institutional 4-Algorithm Consensus Matrix & Staged Profit Manager
Platform: Windows 10/11 64-bit | Python 3.10+
Implements multi-strategy voting:
1. SMC Structure
2. VWAP Alignment
3. Dual EMA Momentum
4. SuperTrend Trend
Requires >= 75.0% consensus + Monte Carlo odds filter approval for order dispatch.
Features a 50-50 staged scale-out and ATR trailing stop manager.
"""

import uuid
from typing import Dict, Any, Optional, List
import pandas as pd
import numpy as np

from core.strategies import (
    SMCLiquiditySweep,
    InstitutionalVWAP,
    DualEMAMomentum,
    SuperTrendGate,
    ATRTrailingStop
)


class ConsensusEngine:
    """
    Evaluates 4 quantitative alpha engines in parallel.
    Generates institutional order recommendations strictly when consensus >= 75.0%
    and Time Machine Monte Carlo win odds qualify.
    """
    CONSENSUS_THRESHOLD_PCT = 75.0  # At least 3 out of 4 algorithms must match

    @classmethod
    def evaluate_consensus(
        cls,
        df: pd.DataFrame,
        passes_odds_filter: bool = True,
        current_tick_ltp: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Polls the 4 strategy engines and computes the consensus matrix score.
        Returns:
            {
                "signal": "BUY" | "SELL" | "NEUTRAL",
                "consensus_score": float,
                "breakdown": {
                    "smc": int, "vwap": int, "ema": int, "supertrend": int
                },
                "entry_price": float,
                "stop_loss": float,
                "target_price": float,
                "approved": bool,
                "rationale": str
            }
        """
        if df.empty or len(df) < 21:
            return {
                "signal": "NEUTRAL",
                "consensus_score": 0.0,
                "breakdown": {"smc": 0, "vwap": 0, "ema": 0, "supertrend": 0},
                "entry_price": 0.0,
                "stop_loss": 0.0,
                "target_price": 0.0,
                "approved": False,
                "rationale": "Insufficient candle data for 4-algorithm consensus."
            }

        # 1. Tally individual strategy votes (-1, 0, +1)
        smc_res = SMCLiquiditySweep.evaluate(df)
        vwap_res = InstitutionalVWAP.evaluate(df)
        ema_res = DualEMAMomentum.evaluate(df)
        st_res = SuperTrendGate.evaluate(df, period=10, multiplier=2.0)

        smc_vote = int(smc_res["vote"])
        vwap_vote = int(vwap_res["vote"])
        ema_vote = int(ema_res["vote"])
        st_vote = int(st_res["vote"])

        votes = [smc_vote, vwap_vote, ema_vote, st_vote]
        bullish_count = sum(1 for v in votes if v == 1)
        bearish_count = sum(1 for v in votes if v == -1)

        # 2. Determine signal and consensus percentage
        if bullish_count >= 3:
            signal = "BUY"
            matching_votes = bullish_count
        elif bearish_count >= 3:
            signal = "SELL"
            matching_votes = bearish_count
        else:
            signal = "NEUTRAL"
            matching_votes = max(bullish_count, bearish_count)

        consensus_score = round((matching_votes / 4.0) * 100.0, 1)

        # Gate Requirement: >= 75% consensus + Time Machine odds filter approval
        approved = bool(
            consensus_score >= cls.CONSENSUS_THRESHOLD_PCT and
            passes_odds_filter and
            signal in ("BUY", "SELL")
        )

        # 3. Calculate dynamic entry, stop loss, and 1:2 R:R target
        entry_price = float(current_tick_ltp) if current_tick_ltp and current_tick_ltp > 0.0 else float(df["Close"].iloc[-1])
        entry_price = round(entry_price, 2)

        atr_val = ATRTrailingStop.calculate_atr(df, period=14)
        risk_dist = round(max(atr_val * 1.5, entry_price * 0.005), 2)  # Minimum 0.5% buffer

        if signal == "BUY":
            stop_loss = round(entry_price - risk_dist, 2)
            target_price = round(entry_price + (2.0 * risk_dist), 2)  # 1:2 Risk-Reward
        elif signal == "SELL":
            stop_loss = round(entry_price + risk_dist, 2)
            target_price = round(entry_price - (2.0 * risk_dist), 2)  # 1:2 Risk-Reward
        else:
            stop_loss = 0.0
            target_price = 0.0

        rationale = (
            f"Consensus {consensus_score}% ({matching_votes}/4 votes) | "
            f"SMC: {smc_vote:+d}, VWAP: {vwap_vote:+d}, EMA: {ema_vote:+d}, SuperTrend: {st_vote:+d} | "
            f"Odds Filter Passed: {passes_odds_filter} | Approved: {approved}"
        )

        return {
            "signal": signal,
            "consensus_score": consensus_score,
            "breakdown": {
                "smc": smc_vote,
                "vwap": vwap_vote,
                "ema": ema_vote,
                "supertrend": st_vote
            },
            "entry_price": entry_price,
            "stop_loss": stop_loss,
            "target_price": target_price,
            "approved": approved,
            "rationale": rationale
        }


class StagedProfitManager:
    """
    Manages 50-50 staged scale-outs and ATR trailing stop management:
    - Milestone 1 (1:2 R:R reached): Liquidates 50% quantity to lock hard profit,
      moves stop-loss of remaining 50% to exact entry price (Break-Even).
    - Milestone 2: Dynamically trails the remaining 50% using ATR volatility trail
      until exit signal or 15:15 IST square-off.
    """

    def __init__(self) -> None:
        # position_id -> position state dictionary
        self._positions: Dict[str, Dict[str, Any]] = {}

    def register_position(
        self,
        symbol: str,
        side: str,
        entry_price: float,
        quantity: int,
        stop_loss: float,
        target_price: float,
        position_id: Optional[str] = None
    ) -> str:
        """Registers a newly opened trade for staged lifecycle management."""
        pos_id = position_id or f"POS_{uuid.uuid4().hex[:8]}"
        normalized_side = side.strip().upper()

        self._positions[pos_id] = {
            "position_id": pos_id,
            "symbol": symbol,
            "side": normalized_side,
            "entry_price": float(entry_price),
            "initial_quantity": int(quantity),
            "current_quantity": int(quantity),
            "scaled_out_quantity": 0,
            "initial_stop_loss": float(stop_loss),
            "current_stop_loss": float(stop_loss),
            "target_price": float(target_price),
            "milestone1_reached": False,
            "locked_profit": 0.0,
            "is_closed": False
        }
        return pos_id

    def update_price(
        self,
        position_id: str,
        current_price: float,
        df: Optional[pd.DataFrame] = None
    ) -> Dict[str, Any]:
        """
        Evaluates current price against staged milestones:
        1. Checks for 1:2 R:R scale-out trigger (Milestone 1).
        2. Advances ATR trailing stop for remaining position (Milestone 2).
        3. Identifies stop-loss liquidation.
        """
        pos = self._positions.get(position_id)
        if not pos or pos["is_closed"]:
            return {"position_id": position_id, "action": "NONE", "is_closed": True}

        side = pos["side"]
        entry_price = pos["entry_price"]
        current_qty = pos["current_quantity"]
        current_stop = pos["current_stop_loss"]

        action = "HOLD"
        shares_to_exit = 0

        # =====================================================================
        # 1. Evaluate Milestone 1 (1:2 R:R Scale-Out)
        # =====================================================================
        if not pos["milestone1_reached"]:
            if side == "BUY":
                initial_risk = entry_price - pos["initial_stop_loss"]
                milestone1_target = entry_price + (2.0 * initial_risk)
                if current_price >= milestone1_target:
                    shares_to_exit = current_qty // 2
                    if shares_to_exit > 0:
                        pos["locked_profit"] += shares_to_exit * (current_price - entry_price)
                        pos["current_quantity"] -= shares_to_exit
                        pos["scaled_out_quantity"] += shares_to_exit
                        pos["current_stop_loss"] = entry_price  # Move SL to exact Break-Even!
                        pos["milestone1_reached"] = True
                        action = "SCALE_OUT_50"

            elif side == "SELL":
                initial_risk = pos["initial_stop_loss"] - entry_price
                milestone1_target = entry_price - (2.0 * initial_risk)
                if current_price <= milestone1_target:
                    shares_to_exit = current_qty // 2
                    if shares_to_exit > 0:
                        pos["locked_profit"] += shares_to_exit * (entry_price - current_price)
                        pos["current_quantity"] -= shares_to_exit
                        pos["scaled_out_quantity"] += shares_to_exit
                        pos["current_stop_loss"] = entry_price  # Move SL to exact Break-Even!
                        pos["milestone1_reached"] = True
                        action = "SCALE_OUT_50"

        # =====================================================================
        # 2. Evaluate Milestone 2 (ATR Trailing Stop for Remaining Position)
        # =====================================================================
        if pos["milestone1_reached"] and df is not None and len(df) >= 2:
            new_trailing_stop = ATRTrailingStop.update_trailing_stop(
                side=side,
                current_price=current_price,
                current_stop=pos["current_stop_loss"],
                df=df,
                multiplier=1.5,
                period=14
            )
            pos["current_stop_loss"] = new_trailing_stop
            if action == "HOLD":
                action = "TRAIL_STOP_UPDATED"

        # =====================================================================
        # 3. Stop-Loss Trigger Check
        # =====================================================================
        stop_triggered = False
        if side == "BUY" and current_price <= pos["current_stop_loss"]:
            stop_triggered = True
        elif side == "SELL" and current_price >= pos["current_stop_loss"]:
            stop_triggered = True

        if stop_triggered:
            shares_to_exit = pos["current_quantity"]
            if side == "BUY":
                pnl = shares_to_exit * (current_price - entry_price)
            else:
                pnl = shares_to_exit * (entry_price - current_price)

            pos["locked_profit"] += pnl
            pos["current_quantity"] = 0
            pos["is_closed"] = True
            action = "STOP_LOSS_EXIT"

        return {
            "position_id": position_id,
            "action": action,
            "shares_to_exit": shares_to_exit,
            "remaining_quantity": pos["current_quantity"],
            "scaled_out_quantity": pos["scaled_out_quantity"],
            "current_stop_loss": pos["current_stop_loss"],
            "milestone1_reached": pos["milestone1_reached"],
            "locked_profit": round(pos["locked_profit"], 2),
            "is_closed": pos["is_closed"]
        }

    def get_position(self, position_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves active state of managed position."""
        return self._positions.get(position_id)

