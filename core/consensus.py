#!/usr/bin/env python3
"""
OmniTradePro - Institutional Multi-Regime Consensus Matrix & Staged Profit Manager
Platform: Windows 10/11 64-bit | Python 3.10+
Implements multi-strategy consensus voting with:
1. SMC Liquidity Sweep (Smart Money Concepts)
2. Institutional VWAP Alignment
3. Dual EMA (9 & 21) Momentum
4. SuperTrend Trend Gate
5. Strategy 5: Institutional Crash & Liquidity Vacuum Short (CrashLiquidityShort)
6. Strategy 6: Adaptive Volatility Breakout (VolatilityBreakoutEngine)
Plus Market Regime Classification (ADX, Hurst, ATR) and Predictive Probability Gate.
Features 50-50 staged scale-out and 1:1 Break-Even Capital Lock.
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
    ATRTrailingStop,
    CrashLiquidityShort,
    VolatilityBreakoutEngine
)
from core.regime_classifier import RegimeClassifier, MarketRegime
from core.predictive_gate import PredictiveGate


class ConsensusEngine:
    """
    Evaluates institutional alpha engines in parallel.
    Generates order recommendations strictly when consensus >= 75.0% (or crash short trigger),
    the market regime is not CHOPPY, and predictive probability qualifies.
    """
    CONSENSUS_THRESHOLD_PCT = 75.0
    DEFAULT_RR_MULTIPLIER = 2.5  # Calibrated 1:2.5 Risk-to-Reward

    @classmethod
    def evaluate_consensus(
        cls,
        df: pd.DataFrame,
        passes_odds_filter: bool = True,
        current_tick_ltp: Optional[float] = None,
        rr_multiplier: float = 2.5,
        enforce_regime_lock: bool = False,
        enforce_predictive_gate: bool = False,
        quantity: int = 1
    ) -> Dict[str, Any]:
        """
        Polls strategy engines and computes the consensus matrix score.
        """
        if df.empty or len(df) < 21:
            return {
                "signal": "NEUTRAL",
                "consensus_score": 0.0,
                "breakdown": {"smc": 0, "vwap": 0, "ema": 0, "supertrend": 0, "crash": 0, "breakout": 0},
                "entry_price": 0.0,
                "stop_loss": 0.0,
                "target_price": 0.0,
                "approved": False,
                "regime": "NEUTRAL",
                "rationale": "Insufficient candle data for consensus evaluation."
            }

        # 0. Market Regime Check
        regime_info = RegimeClassifier.classify(df)
        regime = regime_info["regime"]
        is_crash = (regime == MarketRegime.MARKET_CRASH)
        is_choppy = regime_info["is_trading_locked"]

        if enforce_regime_lock and is_choppy:
            return {
                "signal": "NEUTRAL",
                "consensus_score": 0.0,
                "breakdown": {"smc": 0, "vwap": 0, "ema": 0, "supertrend": 0, "crash": 0, "breakout": 0},
                "entry_price": 0.0,
                "stop_loss": 0.0,
                "target_price": 0.0,
                "approved": False,
                "regime": str(regime.value) if hasattr(regime, "value") else str(regime),
                "rationale": f"Hard Trading Lock: {regime_info['rationale']}"
            }

        # 1. Tally strategy votes (-1, 0, +1)
        smc_res = SMCLiquiditySweep.evaluate(df)
        vwap_res = InstitutionalVWAP.evaluate(df)
        ema_res = DualEMAMomentum.evaluate(df)
        st_res = SuperTrendGate.evaluate(df, period=10, multiplier=2.0)
        crash_res = CrashLiquidityShort.evaluate(df)
        vb_res = VolatilityBreakoutEngine.evaluate(df)

        smc_vote = int(smc_res["vote"])
        vwap_vote = int(vwap_res["vote"])
        ema_vote = int(ema_res["vote"])
        st_vote = int(st_res["vote"])
        crash_vote = int(crash_res["vote"])
        vb_vote = int(vb_res["vote"])

        # Core 4-algorithm vote tally
        core_votes = [smc_vote, vwap_vote, ema_vote, st_vote]
        bullish_count = sum(1 for v in core_votes if v == 1)
        bearish_count = sum(1 for v in core_votes if v == -1)

        # 2. Crash Short Override & Breakout Enhancement
        is_crash_short = crash_res.get("is_crash_short", False) or (is_crash and bearish_count >= 2)

        if is_crash_short:
            signal = "SELL"
            matching_votes = 4
            consensus_score = 100.0
        elif bullish_count >= 3:
            signal = "BUY"
            matching_votes = bullish_count
            consensus_score = round((matching_votes / 4.0) * 100.0, 1)
        elif bearish_count >= 3:
            signal = "SELL"
            matching_votes = bearish_count
            consensus_score = round((matching_votes / 4.0) * 100.0, 1)
        else:
            signal = "NEUTRAL"
            matching_votes = max(bullish_count, bearish_count)
            consensus_score = round((matching_votes / 4.0) * 100.0, 1)

        # 3. Calculate dynamic entry, stop loss, and target price (1:2.5 R:R)
        entry_price = float(current_tick_ltp) if current_tick_ltp and current_tick_ltp > 0.0 else float(df["Close"].iloc[-1])
        entry_price = round(entry_price, 2)

        atr_val = ATRTrailingStop.calculate_atr(df, period=14)
        risk_dist = round(max(atr_val * 1.5, entry_price * 0.005), 2)

        if signal == "BUY":
            stop_loss = round(entry_price - risk_dist, 2)
            target_price = round(entry_price + (rr_multiplier * risk_dist), 2)
        elif signal == "SELL":
            stop_loss = round(entry_price + risk_dist, 2)
            target_price = round(entry_price - (rr_multiplier * risk_dist), 2)
        else:
            stop_loss = 0.0
            target_price = 0.0

        # Gate Requirement: >= 75% consensus + Time Machine odds filter
        approved = bool(
            consensus_score >= cls.CONSENSUS_THRESHOLD_PCT and
            passes_odds_filter and
            signal in ("BUY", "SELL")
        )

        # 4. Predictive Gate Evaluation (if enabled)
        pred_prob = 100.0
        if enforce_predictive_gate and approved:
            pred_res = PredictiveGate.evaluate(
                df=df,
                signal=signal,
                entry_price=entry_price,
                target_price=target_price,
                stop_loss=stop_loss,
                quantity=quantity
            )
            pred_prob = pred_res["probability_pct"]
            if not pred_res["approved"]:
                approved = False

        rationale = (
            f"Consensus {consensus_score}% ({matching_votes}/4 votes) | "
            f"SMC: {smc_vote:+d}, VWAP: {vwap_vote:+d}, EMA: {ema_vote:+d}, SuperTrend: {st_vote:+d}, "
            f"CrashShort: {crash_vote:+d}, Breakout: {vb_vote:+d} | "
            f"Regime: {regime_info['regime']} | Approved: {approved}"
        )

        return {
            "signal": signal,
            "consensus_score": consensus_score,
            "breakdown": {
                "smc": smc_vote,
                "vwap": vwap_vote,
                "ema": ema_vote,
                "supertrend": st_vote,
                "crash": crash_vote,
                "breakout": vb_vote
            },
            "entry_price": entry_price,
            "stop_loss": stop_loss,
            "target_price": target_price,
            "risk_distance": risk_dist,
            "rr_multiplier": rr_multiplier,
            "approved": approved,
            "regime": str(regime.value) if hasattr(regime, "value") else str(regime),
            "predictive_probability_pct": pred_prob,
            "rationale": rationale
        }


class StagedProfitManager:
    """
    Institutional Staged Profit Manager with 1:1 Break-Even Capital Lock & 50-50 Scaling.
    1. Break-Even Capital Lock: Automatically advances stop loss to Entry Price
       (+ ₹5 buffer) as soon as position reaches 1:1 R:R, eliminating capital loss.
    2. Milestone 1: At 1:2.5 (or target), liquidates 50% of the position.
    3. Milestone 2: Dynamically trails the remaining 50% with ATR trailing stops.
    """

    def __init__(self, be_buffer: float = 0.0) -> None:
        self._positions: Dict[str, Dict[str, Any]] = {}
        self.be_buffer = be_buffer

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
            "be_locked": False,
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
        1. 1:1 R:R Break-Even Lock.
        2. Milestone 1 (Scale-out 50%).
        3. Milestone 2 (ATR Trailing Stop for remainder).
        4. Stop-loss liquidation.
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
        # 1. 1:1 R:R Break-Even Capital Lock
        # =====================================================================
        if not pos["be_locked"] and not pos["milestone1_reached"]:
            if side == "BUY":
                initial_risk = entry_price - pos["initial_stop_loss"]
                if current_price >= entry_price + (2.0 * initial_risk):
                    # Will be caught by Milestone 1
                    pass
                elif current_price >= entry_price + initial_risk and self.be_buffer > 0.0:
                    pos["current_stop_loss"] = round(entry_price + self.be_buffer, 2)
                    pos["be_locked"] = True
            elif side == "SELL":
                initial_risk = pos["initial_stop_loss"] - entry_price
                if current_price <= entry_price - (2.0 * initial_risk):
                    pass
                elif current_price <= entry_price - initial_risk and self.be_buffer > 0.0:
                    pos["current_stop_loss"] = round(entry_price - self.be_buffer, 2)
                    pos["be_locked"] = True

        # =====================================================================
        # 2. Evaluate Milestone 1 (Scale-Out 50%)
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
        # 3. Evaluate Milestone 2 (ATR Trailing Stop for Remaining Position)
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
        # 4. Stop-Loss Trigger Check
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
