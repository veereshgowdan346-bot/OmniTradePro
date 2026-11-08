#!/usr/bin/env python3
"""
OmniTradePro - Predictive Probability Gate & Target Reachability Engine
Platform: Windows 10/11 64-bit | Python 3.10+
Implements rigorous drift-diffusion and first-passage probability modeling:
1. Calculates instantaneous drift (mu) and diffusion volatility (sigma) from log returns.
2. Models the forward probability of price reaching the target before stop-loss.
3. Enforces institutional risk hurdles:
   - Forward Probability of Hitting Target >= 65.0%
   - Expected Gross Gain >= ₹70 Hurdle Gate
Zero placeholders, pure mathematical execution.
"""

import math
from typing import Dict, Any, Optional
import numpy as np
import pandas as pd


class PredictiveGate:
    """
    Stochastic drift-diffusion forward probability calculator.
    Rejects setups where statistical drift and volatility dynamics
    indicate a sub-65% target probability.
    """

    MIN_PROBABILITY_THRESHOLD_PCT = 65.0  # Statutory 65% forward target confidence
    MIN_GROSS_GAIN_HURDLE_INR = 70.0      # Pre-trade ₹70 friction hurdle
    DEFAULT_HORIZON_BARS = 15             # 15-period maximum forward holding horizon

    @classmethod
    def norm_cdf(cls, x: float) -> float:
        """Standard normal cumulative distribution function (CDF) via error function."""
        return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))

    @classmethod
    def evaluate(
        cls,
        df: pd.DataFrame,
        signal: str,
        entry_price: float,
        target_price: float,
        stop_loss: float,
        quantity: int = 1,
        horizon_bars: int = 15,
        lookback_bars: int = 25
    ) -> Dict[str, Any]:
        """
        Calculates the forward probability of hitting the target price before stop-loss.
        Returns:
            {
                "approved": bool,
                "probability_pct": float,
                "expected_gross_gain": float,
                "hurdle_passed": bool,
                "drift_annualized": float,
                "volatility_annualized": float,
                "horizon_bars": int,
                "rationale": str
            }
        """
        if df.empty or len(df) < 15 or entry_price <= 0.0 or target_price <= 0.0 or stop_loss <= 0.0:
            return {
                "approved": False,
                "probability_pct": 0.0,
                "expected_gross_gain": 0.0,
                "hurdle_passed": False,
                "drift_annualized": 0.0,
                "volatility_annualized": 0.0,
                "horizon_bars": horizon_bars,
                "rationale": "Insufficient historical data or invalid pricing parameters."
            }

        normalized_signal = signal.strip().upper()
        if normalized_signal not in ("BUY", "SELL"):
            return {
                "approved": False,
                "probability_pct": 0.0,
                "expected_gross_gain": 0.0,
                "hurdle_passed": False,
                "drift_annualized": 0.0,
                "volatility_annualized": 0.0,
                "horizon_bars": horizon_bars,
                "rationale": f"Signal '{signal}' is not directional."
            }

        # 1. Compute Pre-Trade Gross Expected Gain
        if normalized_signal == "BUY":
            expected_gross_gain = round((target_price - entry_price) * quantity, 2)
        else:
            expected_gross_gain = round((entry_price - target_price) * quantity, 2)

        hurdle_passed = expected_gross_gain >= cls.MIN_GROSS_GAIN_HURDLE_INR

        # 2. Extract price log returns over lookback
        closes = df["Close"].iloc[-lookback_bars:].values
        valid_closes = closes[closes > 0]
        if len(valid_closes) < 10:
            return {
                "approved": False,
                "probability_pct": 0.0,
                "expected_gross_gain": expected_gross_gain,
                "hurdle_passed": hurdle_passed,
                "drift_annualized": 0.0,
                "volatility_annualized": 0.0,
                "horizon_bars": horizon_bars,
                "rationale": "Insufficient positive prices for log returns."
            }

        log_returns = np.diff(np.log(valid_closes))
        mu_bar = float(np.mean(log_returns))
        sigma_bar = float(np.std(log_returns)) + 1e-9

        # Annualized proxies (assuming 252 days * 6.25 hours = ~1575 hourly bars)
        drift_annualized = round(mu_bar * 1575.0, 4)
        volatility_annualized = round(sigma_bar * math.sqrt(1575.0), 4)

        # 3. Geometric Brownian Motion & First-Passage Formulation
        # Required log price move to target
        target_log_move = math.log(target_price / entry_price)
        stop_log_move = math.log(stop_loss / entry_price)

        # Directional alignment: for BUY, positive target_log_move; for SELL, negative target_log_move
        direction = 1.0 if normalized_signal == "BUY" else -1.0
        directional_drift = direction * mu_bar

        # Risk-adjusted distance
        abs_target_dist = abs(target_log_move)
        abs_stop_dist = abs(stop_log_move)

        # Variance over the forward horizon
        horizon_sigma = sigma_bar * math.sqrt(horizon_bars)
        horizon_drift = directional_drift * horizon_bars

        # First-passage probability to target before stop-loss:
        # Standard analytical two-barrier probability approximation with drift:
        # P = (1 - exp(-2 * mu * stop_dist / sigma^2)) / (1 - exp(-2 * mu * (target_dist + stop_dist) / sigma^2))
        alpha_factor = (2.0 * directional_drift) / (sigma_bar ** 2 + 1e-9)

        if abs(alpha_factor) < 1e-4:  # Near-zero drift (pure martingale)
            p_target = abs_stop_dist / (abs_target_dist + abs_stop_dist + 1e-9)
        else:
            try:
                # Scaled to prevent float overflow
                s_term = np.clip(alpha_factor * abs_stop_dist, -50.0, 50.0)
                tot_term = np.clip(alpha_factor * (abs_target_dist + abs_stop_dist), -50.0, 50.0)
                numerator = 1.0 - math.exp(-s_term)
                denominator = 1.0 - math.exp(-tot_term)
                p_target = numerator / (denominator + 1e-9)
            except (OverflowError, ZeroDivisionError):
                p_target = 0.50

        # Also incorporate directional forward CDF over the horizon
        z_forward = (horizon_drift - abs_target_dist) / (horizon_sigma + 1e-9)
        p_terminal = cls.norm_cdf(z_forward)

        # Composite institutional confidence: 60% first-passage, 40% forward terminal probability
        composite_p = (0.60 * p_target) + (0.40 * p_terminal)
        composite_p_pct = round(max(5.0, min(95.0, composite_p * 100.0)), 2)

        # 4. Strict Dual-Gate Approval
        probability_qualified = composite_p_pct >= cls.MIN_PROBABILITY_THRESHOLD_PCT
        approved = bool(probability_qualified and hurdle_passed)

        rationale = (
            f"Predictive Gate: Target Prob {composite_p_pct}% "
            f"({'PASS' if probability_qualified else 'FAIL'} vs {cls.MIN_PROBABILITY_THRESHOLD_PCT}%) | "
            f"Expected Gross ₹{expected_gross_gain:.2f} "
            f"({'PASS' if hurdle_passed else 'FAIL'} vs ₹{cls.MIN_GROSS_GAIN_HURDLE_INR:.2f}) | "
            f"Drift: {mu_bar:+.5f}, Sigma: {sigma_bar:.5f} | Approved: {approved}"
        )

        return {
            "approved": approved,
            "probability_pct": composite_p_pct,
            "expected_gross_gain": expected_gross_gain,
            "hurdle_passed": hurdle_passed,
            "drift_annualized": drift_annualized,
            "volatility_annualized": volatility_annualized,
            "horizon_bars": horizon_bars,
            "rationale": rationale
        }

