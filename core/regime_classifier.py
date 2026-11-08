#!/usr/bin/env python3
"""
OmniTradePro - Institutional Multi-Regime Market Classifier
Platform: Windows 10/11 64-bit | Python 3.10+
Implements multi-regime classification prior to quantitative signal dispatch:
1. Trend Persistence: Hurst Exponent (H > 0.55 = Trending, H < 0.45 = Mean-Reverting)
2. Volatility & Trend Matrix:
   - State A (BULL_TREND): ADX > 22, Price > 200 EMA & Price > VWAP
   - State B (BEAR_TREND): ADX > 22, Price < 200 EMA & Price < VWAP
   - State C (MARKET_CRASH): Real-time ATR expanding > 2.5x rolling 20-period average ATR
     with heavy volume breakdown (Volume > 2x average and Close < Open)
   - State D (CHOPPY): ADX < 20. Initiates HARD TRADING LOCK to prevent statutory tax drag.
"""

from enum import Enum
from typing import Dict, Any, Optional, Tuple
import numpy as np
import pandas as pd

from core.strategies import ATRTrailingStop, InstitutionalVWAP


class MarketRegime(str, Enum):
    BULL_TREND = "BULL_TREND"
    BEAR_TREND = "BEAR_TREND"
    MARKET_CRASH = "MARKET_CRASH"
    CHOPPY = "CHOPPY"
    NEUTRAL = "NEUTRAL"


class RegimeClassifier:
    """
    Institutional market state classifier.
    Determines whether market conditions are conducive to trend following,
    short crash exploitation, or require hard risk lockouts during sideways chop.
    """

    ADX_TREND_THRESHOLD = 22.0
    ADX_CHOP_THRESHOLD = 20.0
    CRASH_ATR_EXPANSION_RATIO = 2.5
    CRASH_VOLUME_SURGE_RATIO = 2.0
    HURST_TREND_THRESHOLD = 0.55
    HURST_MEAN_REV_THRESHOLD = 0.45

    @classmethod
    def calculate_hurst_exponent(
        cls,
        series: np.ndarray,
        min_window: int = 10,
        max_window: Optional[int] = None
    ) -> float:
        """
        Calculates the Hurst Exponent (H) using Rescaled Range (R/S) analysis.
        Interpretation:
            H > 0.55: Persistent / Directional Trending series
            H < 0.45: Anti-persistent / Mean-reverting / Choppy series
            0.45 <= H <= 0.55: Brownian motion / Random walk
        """
        if len(series) < 30:
            return 0.50

        vals = np.array(series, dtype=float)
        positive_vals = vals[vals > 0]
        if len(positive_vals) < 30:
            return 0.50

        returns = np.diff(np.log(positive_vals))
        N = len(returns)
        if N < 20:
            return 0.50

        if max_window is None:
            max_window = N // 2
        if max_window <= min_window:
            return 0.50

        window_sizes = np.unique(np.linspace(min_window, max_window, 8, dtype=int))
        rs_values = []
        valid_windows = []

        for w in window_sizes:
            num_chunks = N // w
            if num_chunks == 0:
                continue
            chunk_rs = []
            for c in range(num_chunks):
                chunk = returns[c * w : (c + 1) * w]
                m = np.mean(chunk)
                dev = chunk - m
                cum_dev = np.cumsum(dev)
                r = np.max(cum_dev) - np.min(cum_dev)
                s = np.std(chunk)
                if s > 1e-9:
                    chunk_rs.append(r / s)
            if chunk_rs:
                rs_values.append(np.mean(chunk_rs))
                valid_windows.append(w)

        if len(rs_values) < 3:
            return 0.50

        try:
            poly = np.polyfit(np.log(valid_windows), np.log(rs_values), 1)
            h_val = float(poly[0])
            return round(max(0.0, min(1.0, h_val)), 3)
        except Exception:
            return 0.50

    @classmethod
    def calculate_adx(cls, df: pd.DataFrame, period: int = 14) -> float:
        """
        Calculates Wilder's Average Directional Index (ADX).
        Measures pure trend strength regardless of direction.
        """
        if len(df) < period + 2:
            return 0.0

        high = df["High"].values
        low = df["Low"].values
        close = df["Close"].values

        tr_list = []
        dm_plus_list = []
        dm_minus_list = []

        for k in range(1, len(df)):
            h_diff = high[k] - high[k - 1]
            l_diff = low[k - 1] - low[k]

            dm_p = h_diff if (h_diff > l_diff and h_diff > 0) else 0.0
            dm_m = l_diff if (l_diff > h_diff and l_diff > 0) else 0.0

            c_tr = max(
                high[k] - low[k],
                abs(high[k] - close[k - 1]),
                abs(low[k] - close[k - 1])
            )
            tr_list.append(c_tr)
            dm_plus_list.append(dm_p)
            dm_minus_list.append(dm_m)

        if len(tr_list) < period:
            return 0.0

        tr_s = pd.Series(tr_list).ewm(alpha=1.0 / period, adjust=False).mean()
        pdm_s = pd.Series(dm_plus_list).ewm(alpha=1.0 / period, adjust=False).mean()
        mdm_s = pd.Series(dm_minus_list).ewm(alpha=1.0 / period, adjust=False).mean()

        pdi = 100.0 * (pdm_s / (tr_s + 1e-9))
        mdi = 100.0 * (mdm_s / (tr_s + 1e-9))

        dx = 100.0 * (abs(pdi - mdi) / (pdi + mdi + 1e-9))
        adx_s = dx.ewm(alpha=1.0 / period, adjust=False).mean()

        return round(float(adx_s.iloc[-1]), 2)

    @classmethod
    def calculate_atr_series(cls, df: pd.DataFrame, period: int = 14) -> pd.Series:
        """Calculates 14-period True Range series."""
        high = df["High"]
        low = df["Low"]
        close = df["Close"]
        tr1 = high - low
        tr2 = (high - close.shift(1)).abs()
        tr3 = (low - close.shift(1)).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        return tr.rolling(window=period, min_periods=1).mean()

    @classmethod
    def classify(cls, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Evaluates full multi-regime state from candle series:
        Returns:
            {
                "regime": MarketRegime (BULL_TREND | BEAR_TREND | MARKET_CRASH | CHOPPY | NEUTRAL),
                "is_trading_locked": bool,
                "adx": float,
                "hurst": float,
                "atr": float,
                "atr_ratio": float,
                "volume_ratio": float,
                "ema200": float,
                "vwap": float,
                "current_price": float,
                "rationale": str
            }
        """
        if df.empty or len(df) < 20:
            return {
                "regime": MarketRegime.CHOPPY,
                "is_trading_locked": True,
                "adx": 0.0,
                "hurst": 0.50,
                "atr": 0.0,
                "atr_ratio": 1.0,
                "volume_ratio": 1.0,
                "ema200": 0.0,
                "vwap": 0.0,
                "current_price": 0.0,
                "rationale": "Insufficient historical data for market regime classification."
            }

        current_price = float(df["Close"].iloc[-1])
        current_open = float(df["Open"].iloc[-1]) if "Open" in df.columns else current_price
        current_volume = float(df["Volume"].iloc[-1]) if "Volume" in df.columns else 1000.0

        # 1. Trend Strength (ADX) & Persistence (Hurst)
        adx_val = cls.calculate_adx(df, period=14)
        hurst_val = cls.calculate_hurst_exponent(df["Close"].values)

        # 2. Volatility Indicators (ATR & Ratio)
        atr_series = cls.calculate_atr_series(df, period=14)
        current_atr = float(atr_series.iloc[-1])
        rolling_20_atr = float(atr_series.iloc[-20:].mean()) if len(atr_series) >= 20 else current_atr
        atr_ratio = round(current_atr / (rolling_20_atr + 1e-9), 2)

        # 3. Volume Surge Ratio
        if "Volume" in df.columns and len(df) >= 20:
            avg_volume_20 = float(df["Volume"].iloc[-20:].mean())
            volume_ratio = round(current_volume / (avg_volume_20 + 1e-9), 2)
        else:
            volume_ratio = 1.0

        # 4. Long-Term Trend Benchmark (200 EMA & VWAP)
        # Use available history if len(df) < 200, smoothing gracefully
        ema_span = min(200, len(df))
        ema200 = float(df["Close"].ewm(span=ema_span, adjust=False).mean().iloc[-1])

        vwap_series = InstitutionalVWAP.calculate(df)
        vwap_val = float(vwap_series.iloc[-1]) if not vwap_series.empty else current_price

        # ---------------------------------------------------------------------
        # Regime Decision Hierarchy
        # ---------------------------------------------------------------------

        # Condition C: MARKET_CRASH / BEAR EXPANSION
        # Real-time ATR expanding > 2.5x rolling 20-day average + heavy selling volume breakdown
        is_selling_breakdown = (current_price < current_open) and (volume_ratio >= cls.CRASH_VOLUME_SURGE_RATIO)
        is_severe_atr_expansion = atr_ratio >= cls.CRASH_ATR_EXPANSION_RATIO

        if is_severe_atr_expansion and is_selling_breakdown:
            regime = MarketRegime.MARKET_CRASH
            is_locked = False
            rationale = (
                f"MARKET_CRASH Detected: ATR expanded {atr_ratio}x (threshold {cls.CRASH_ATR_EXPANSION_RATIO}x) "
                f"with {volume_ratio}x volume selling breakdown. Fast short alpha engaged."
            )
            return {
                "regime": regime,
                "is_trading_locked": is_locked,
                "adx": adx_val,
                "hurst": hurst_val,
                "atr": round(current_atr, 2),
                "atr_ratio": atr_ratio,
                "volume_ratio": volume_ratio,
                "ema200": round(ema200, 2),
                "vwap": round(vwap_val, 2),
                "current_price": round(current_price, 2),
                "rationale": rationale
            }

        # Condition D: CHOPPY / SIDEWAYS -> INITIATE HARD TRADING LOCK
        # If ADX < 20 or (ADX < 22 and Hurst indicates anti-persistence / mean reversion)
        is_choppy = (adx_val < cls.ADX_CHOP_THRESHOLD) or (adx_val < cls.ADX_TREND_THRESHOLD and hurst_val < cls.HURST_MEAN_REV_THRESHOLD)

        if is_choppy:
            regime = MarketRegime.CHOPPY
            is_locked = True
            rationale = (
                f"HARD TRADING LOCK: Choppy/Sideways regime (ADX {adx_val:.1f} < {cls.ADX_CHOP_THRESHOLD}, "
                f"Hurst {hurst_val:.3f}). All trade dispatch blocked to eliminate statutory tax drag."
            )
            return {
                "regime": regime,
                "is_trading_locked": is_locked,
                "adx": adx_val,
                "hurst": hurst_val,
                "atr": round(current_atr, 2),
                "atr_ratio": atr_ratio,
                "volume_ratio": volume_ratio,
                "ema200": round(ema200, 2),
                "vwap": round(vwap_val, 2),
                "current_price": round(current_price, 2),
                "rationale": rationale
            }

        # Condition A: BULL_TREND (ADX > 22, Price > 200 EMA & Price > VWAP)
        if adx_val >= cls.ADX_TREND_THRESHOLD and current_price > ema200 and current_price > vwap_val:
            regime = MarketRegime.BULL_TREND
            is_locked = False
            rationale = (
                f"BULL_TREND: ADX {adx_val:.1f} >= {cls.ADX_TREND_THRESHOLD}, "
                f"Price ₹{current_price:.2f} > 200 EMA (₹{ema200:.2f}) & VWAP (₹{vwap_val:.2f})."
            )

        # Condition B: BEAR_TREND (ADX > 22, Price < 200 EMA & Price < VWAP)
        elif adx_val >= cls.ADX_TREND_THRESHOLD and current_price < ema200 and current_price < vwap_val:
            regime = MarketRegime.BEAR_TREND
            is_locked = False
            rationale = (
                f"BEAR_TREND: ADX {adx_val:.1f} >= {cls.ADX_TREND_THRESHOLD}, "
                f"Price ₹{current_price:.2f} < 200 EMA (₹{ema200:.2f}) & VWAP (₹{vwap_val:.2f})."
            )

        else:
            regime = MarketRegime.NEUTRAL
            is_locked = False
            rationale = f"NEUTRAL: Mixed indicators (ADX {adx_val:.1f}, Hurst {hurst_val:.3f})."

        return {
            "regime": regime,
            "is_trading_locked": is_locked,
            "adx": adx_val,
            "hurst": hurst_val,
            "atr": round(current_atr, 2),
            "atr_ratio": atr_ratio,
            "volume_ratio": volume_ratio,
            "ema200": round(ema200, 2),
            "vwap": round(vwap_val, 2),
            "current_price": round(current_price, 2),
            "rationale": rationale
        }
