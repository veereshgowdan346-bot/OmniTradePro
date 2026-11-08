#!/usr/bin/env python3
"""
OmniTradePro - Institutional Trading Strategy Core & Indicators
Platform: Windows 10/11 64-bit | Python 3.10+
Implements 4 institutional alpha generators:
1. SMC Liquidity Sweep (Smart Money Concepts)
2. Institutional VWAP Anchor (Volume-Weighted Average Price)
3. Dual EMA (9 & 21) Momentum Engine
4. SuperTrend Volatility Gate (Period=10, Multiplier=2.0)
Plus ATR Dynamic Trailing Stop-Loss Engine.
"""

from typing import Dict, Any, Tuple, Optional
import numpy as np
import pandas as pd


class SMCLiquiditySweep:
    """
    Smart Money Concepts (SMC) Liquidity Sweep Detector.
    Scans a rolling 20-candle lookback window for key structural swing highs/lows.
    Identifies liquidity grabs where price wicks beyond a swing level within a
    3-candle confirmation window, but closes back within the interior boundary.
    """
    LOOKBACK = 20
    CONFIRMATION_WINDOW = 3

    @classmethod
    def evaluate(cls, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Evaluates liquidity sweep structure on the latest candle with a 3-candle confirmation window.
        Returns:
            {
                "vote": int (+1 for Bullish Sweep, -1 for Bearish Sweep, 0 for Neutral),
                "swing_high": float,
                "swing_low": float,
                "description": str
            }
        """
        if len(df) < cls.LOOKBACK + 1:
            return {"vote": 0, "swing_high": 0.0, "swing_low": 0.0, "description": "Insufficient candle lookback."}

        # Determine confirmation window (up to 3 candles)
        conf_len = min(cls.CONFIRMATION_WINDOW, max(1, len(df) - cls.LOOKBACK))

        # Swing lookback window strictly prior to the confirmation window
        lookback_window = df.iloc[-(cls.LOOKBACK + conf_len):-conf_len]
        if lookback_window.empty:
            lookback_window = df.iloc[-(cls.LOOKBACK + 1):-1]

        swing_high = round(float(lookback_window["High"].max()), 2)
        swing_low = round(float(lookback_window["Low"].min()), 2)

        recent_window = df.iloc[-conf_len:]
        cur_bar = df.iloc[-1]
        cur_close = float(cur_bar["Close"])

        min_recent_low = float(recent_window["Low"].min())
        max_recent_high = float(recent_window["High"].max())

        swept_low = (min_recent_low < swing_low) and (cur_close > swing_low)
        swept_high = (max_recent_high > swing_high) and (cur_close < swing_high)

        # Bullish Sweep: Price took out swing low within confirmation window but current bar closes back above
        if swept_low and not swept_high:
            return {
                "vote": 1,
                "swing_high": swing_high,
                "swing_low": swing_low,
                "description": f"Bullish SMC Sweep: Low ₹{min_recent_low:.2f} grabbed liquidity below ₹{swing_low:.2f}, confirmed close @ ₹{cur_close:.2f}"
            }

        # Bearish Sweep: Price pierced swing high within confirmation window but current bar closes back below
        if swept_high and not swept_low:
            return {
                "vote": -1,
                "swing_high": swing_high,
                "swing_low": swing_low,
                "description": f"Bearish SMC Sweep: High ₹{max_recent_high:.2f} grabbed liquidity above ₹{swing_high:.2f}, confirmed close @ ₹{cur_close:.2f}"
            }

        if swept_low and swept_high:
            # Reversal direction based on latest bar momentum
            if cur_close > float(cur_bar["Open"]):
                return {
                    "vote": 1,
                    "swing_high": swing_high,
                    "swing_low": swing_low,
                    "description": f"Bullish SMC Sweep (Dual Expansion): Confirmed close @ ₹{cur_close:.2f}"
                }
            else:
                return {
                    "vote": -1,
                    "swing_high": swing_high,
                    "swing_low": swing_low,
                    "description": f"Bearish SMC Sweep (Dual Expansion): Confirmed close @ ₹{cur_close:.2f}"
                }

        return {
            "vote": 0,
            "swing_high": swing_high,
            "swing_low": swing_low,
            "description": "Neutral SMC structure: No liquidity sweep detected."
        }


class InstitutionalVWAP:
    """
    Intraday Volume Weighted Average Price (VWAP) Anchor.
    Formula: VWAP = sum(Typical_Price * Volume) / sum(Volume)
    Typical_Price = (High + Low + Close) / 3
    """

    @classmethod
    def calculate(cls, df: pd.DataFrame) -> pd.Series:
        """Computes cumulative session VWAP line."""
        typical_price = (df["High"] + df["Low"] + df["Close"]) / 3.0
        tpv = typical_price * df["Volume"]

        cum_tpv = tpv.cumsum()
        cum_vol = df["Volume"].cumsum()

        vwap = cum_tpv / cum_vol.replace(0, np.nan)
        return vwap.ffill()

    @classmethod
    def evaluate(cls, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Evaluates current price relationship and divergence relative to VWAP.
        Returns:
            {"vote": int (+1 or -1), "vwap": float, "divergence": float, "description": str}
        """
        if df.empty or "Volume" not in df.columns:
            return {"vote": 0, "vwap": 0.0, "divergence": 0.0, "description": "Invalid dataframe for VWAP."}

        vwap_series = cls.calculate(df)
        cur_vwap = round(float(vwap_series.iloc[-1]), 2)
        cur_price = round(float(df["Close"].iloc[-1]), 2)
        divergence = round(cur_price - cur_vwap, 2)

        if cur_price > cur_vwap:
            return {
                "vote": 1,
                "vwap": cur_vwap,
                "divergence": divergence,
                "description": f"Bullish: Price ₹{cur_price:.2f} > VWAP ₹{cur_vwap:.2f} (+₹{divergence:.2f})"
            }
        elif cur_price < cur_vwap:
            return {
                "vote": -1,
                "vwap": cur_vwap,
                "divergence": divergence,
                "description": f"Bearish: Price ₹{cur_price:.2f} < VWAP ₹{cur_vwap:.2f} (₹{divergence:.2f})"
            }

        return {"vote": 0, "vwap": cur_vwap, "divergence": 0.0, "description": "Price equal to VWAP"}


class DualEMAMomentum:
    """
    Institutional Dual Exponential Moving Average (9 & 21) Momentum Engine.
    Uses exponential alpha weighting (2 / (span + 1)) to identify direction & crossovers.
    """

    @classmethod
    def calculate(cls, df: pd.DataFrame) -> Tuple[pd.Series, pd.Series]:
        """Calculates EMA(9) and EMA(21)."""
        ema9 = df["Close"].ewm(span=9, adjust=False).mean()
        ema21 = df["Close"].ewm(span=21, adjust=False).mean()
        return ema9, ema21

    @classmethod
    def evaluate(cls, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Evaluates trend alignment and recent crossover state.
        Returns:
            {"vote": int (+1 or -1), "ema9": float, "ema21": float, "crossover": bool, "description": str}
        """
        if len(df) < 21:
            return {"vote": 0, "ema9": 0.0, "ema21": 0.0, "crossover": False, "description": "Insufficient candles for EMA(21)."}

        ema9, ema21 = cls.calculate(df)
        e9_cur = round(float(ema9.iloc[-1]), 2)
        e21_cur = round(float(ema21.iloc[-1]), 2)
        e9_prev = round(float(ema9.iloc[-2]), 2)
        e21_prev = round(float(ema21.iloc[-2]), 2)

        crossover = (e9_prev <= e21_prev and e9_cur > e21_cur) or (e9_prev >= e21_prev and e9_cur < e21_cur)

        if e9_cur > e21_cur:
            return {
                "vote": 1,
                "ema9": e9_cur,
                "ema21": e21_cur,
                "crossover": crossover,
                "description": f"Bullish: EMA9 (₹{e9_cur}) > EMA21 (₹{e21_cur}) | Crossover: {crossover}"
            }
        elif e9_cur < e21_cur:
            return {
                "vote": -1,
                "ema9": e9_cur,
                "ema21": e21_cur,
                "crossover": crossover,
                "description": f"Bearish: EMA9 (₹{e9_cur}) < EMA21 (₹{e21_cur}) | Crossover: {crossover}"
            }

        return {"vote": 0, "ema9": e9_cur, "ema21": e21_cur, "crossover": False, "description": "EMA convergence"}


class SuperTrendGate:
    """
    Institutional SuperTrend Volatility Gate (Period=10, Multiplier=2.0).
    Computes exact Average True Range (ATR 10) and dynamic upper/lower band ratchet logic.
    """

    @classmethod
    def calculate(
        cls,
        df: pd.DataFrame,
        period: int = 10,
        multiplier: float = 2.0
    ) -> Tuple[pd.Series, pd.Series]:
        """
        Calculates SuperTrend trailing stop line and trend direction (+1 or -1).
        """
        high = df["High"]
        low = df["Low"]
        close = df["Close"]

        # 1. Compute True Range (TR)
        prev_close = close.shift(1)
        tr1 = high - low
        tr2 = (high - prev_close).abs().fillna(tr1)
        tr3 = (low - prev_close).abs().fillna(tr1)
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

        # 2. Wilder's Average True Range (ATR)
        atr = tr.ewm(alpha=1.0 / period, adjust=False).mean()

        # 3. Basic Bands
        hl2 = (high + low) / 2.0
        basic_upper = (hl2 + (multiplier * atr)).bfill()
        basic_lower = (hl2 - (multiplier * atr)).bfill()

        n = len(df)
        final_upper = np.zeros(n)
        final_lower = np.zeros(n)
        supertrend = np.zeros(n)
        trend = np.zeros(n, dtype=int)

        # Vector conversion for fast iteration
        b_up = basic_upper.values
        b_low = basic_lower.values
        c = close.values

        # Initialize first valid values
        final_upper[0] = b_up[0]
        final_lower[0] = b_low[0]
        supertrend[0] = b_up[0]
        trend[0] = 1

        for i in range(1, n):
            # Final Upper Band
            if b_up[i] < final_upper[i - 1] or c[i - 1] > final_upper[i - 1]:
                final_upper[i] = b_up[i]
            else:
                final_upper[i] = final_upper[i - 1]

            # Final Lower Band
            if b_low[i] > final_lower[i - 1] or c[i - 1] < final_lower[i - 1]:
                final_lower[i] = b_low[i]
            else:
                final_lower[i] = final_lower[i - 1]

            # Trend Directional Switching
            if supertrend[i - 1] == final_upper[i - 1]:
                if c[i] > final_upper[i]:
                    trend[i] = 1
                    supertrend[i] = final_lower[i]
                else:
                    trend[i] = -1
                    supertrend[i] = final_upper[i]
            else:
                if c[i] < final_lower[i]:
                    trend[i] = -1
                    supertrend[i] = final_upper[i]
                else:
                    trend[i] = 1
                    supertrend[i] = final_lower[i]

        return pd.Series(supertrend, index=df.index), pd.Series(trend, index=df.index)

    @classmethod
    def evaluate(cls, df: pd.DataFrame, period: int = 10, multiplier: float = 2.0) -> Dict[str, Any]:
        """
        Evaluates current SuperTrend trend and stop line.
        Returns:
            {"vote": int (+1 or -1), "supertrend": float, "trend": int, "description": str}
        """
        if len(df) < period:
            return {"vote": 0, "supertrend": 0.0, "trend": 0, "description": "Insufficient candles for SuperTrend."}

        st_series, trend_series = cls.calculate(df, period=period, multiplier=multiplier)
        cur_st = round(float(st_series.iloc[-1]), 2)
        cur_trend = int(trend_series.iloc[-1])
        cur_close = round(float(df["Close"].iloc[-1]), 2)

        desc = f"SuperTrend {'Bullish (+1)' if cur_trend == 1 else 'Bearish (-1)'}: Trail @ ₹{cur_st:.2f} (Close ₹{cur_close:.2f})"
        return {
            "vote": cur_trend,
            "supertrend": cur_st,
            "trend": cur_trend,
            "description": desc
        }


class ATRTrailingStop:
    """
    Dynamic Average True Range (ATR) Trailing Stop-Loss Calculator.
    Enforces adaptive volatility trails:
        Long Trail: max(current_trail, current_price - (multiplier * ATR))
        Short Trail: min(current_trail, current_price + (multiplier * ATR))
    """

    @staticmethod
    def calculate_atr(df: pd.DataFrame, period: int = 14) -> float:
        """Calculates current ATR(14) scalar value."""
        if len(df) < 2:
            return 1.0

        high = df["High"]
        low = df["Low"]
        close = df["Close"]
        prev_close = close.shift(1)

        tr = pd.concat([high - low, (high - prev_close).abs(), (low - prev_close).abs()], axis=1).max(axis=1)
        atr_series = tr.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()
        return float(atr_series.iloc[-1])

    @classmethod
    def update_trailing_stop(
        cls,
        side: str,
        current_price: float,
        current_stop: float,
        df: pd.DataFrame,
        multiplier: float = 1.5,
        period: int = 14
    ) -> float:
        """
        Advances the trailing stop loss in the direction of profit.
        Never moves stop loss backwards.
        """
        atr_val = cls.calculate_atr(df, period=period)
        distance = atr_val * multiplier

        if side.upper() == "BUY":
            candidate_stop = round(current_price - distance, 2)
            return max(current_stop, candidate_stop)
        elif side.upper() == "SELL":
            candidate_stop = round(current_price + distance, 2)
            if current_stop <= 0.0:
                return candidate_stop
            return min(current_stop, candidate_stop)

        return current_stop


class CrashLiquidityShort:
    """
    Strategy 5: Institutional Crash & Liquidity Vacuum Short.
    Triggered during high-volatility bear expansion and market crashes.
    Conditions:
    1. Price breaches the rolling 24-period (or previous session) low.
    2. Severe volume surge: Volume >= 2.5x the 20-period moving average volume.
    3. Severe negative VWAP deviation: Price < VWAP by at least 1.5% or 1.5 * ATR.
    Vote: -1 (Aggressive Short / PE setup), 0 (Neutral).
    """
    LOOKBACK_LOW = 24
    VOLUME_SURGE_RATIO = 2.5
    VWAP_DEVIATION_PCT = 0.015

    @classmethod
    def evaluate(cls, df: pd.DataFrame) -> Dict[str, Any]:
        if len(df) < cls.LOOKBACK_LOW + 1:
            return {"vote": 0, "is_crash_short": False, "description": "Insufficient candles for CrashLiquidityShort."}

        cur_close = float(df["Close"].iloc[-1])
        cur_volume = float(df["Volume"].iloc[-1]) if "Volume" in df.columns else 1000.0

        # Prior lookback low
        prior_low = float(df["Low"].iloc[-(cls.LOOKBACK_LOW + 1):-1].min())
        avg_volume_20 = float(df["Volume"].iloc[-21:-1].mean()) if "Volume" in df.columns else 1000.0
        volume_ratio = cur_volume / (avg_volume_20 + 1e-9)

        # VWAP calculation
        vwap_series = InstitutionalVWAP.calculate(df)
        cur_vwap = float(vwap_series.iloc[-1]) if not vwap_series.empty else cur_close
        vwap_dev = (cur_vwap - cur_close) / (cur_vwap + 1e-9)

        # Check breach of prior low, volume surge >= 2.5x, and negative VWAP deviation
        breached_low = cur_close < prior_low
        surge_confirmed = volume_ratio >= cls.VOLUME_SURGE_RATIO
        vwap_deviated = vwap_dev >= cls.VWAP_DEVIATION_PCT

        if breached_low and surge_confirmed and vwap_deviated:
            desc = (
                f"Crash Short Confirmed: Prior Low ₹{prior_low:.2f} breached @ ₹{cur_close:.2f} "
                f"with {volume_ratio:.1f}x volume surge & {vwap_dev*100:.1f}% VWAP negative deviation."
            )
            return {
                "vote": -1,
                "is_crash_short": True,
                "volume_ratio": round(volume_ratio, 2),
                "vwap_deviation_pct": round(vwap_dev * 100.0, 2),
                "prior_low": prior_low,
                "description": desc
            }

        return {
            "vote": 0,
            "is_crash_short": False,
            "volume_ratio": round(volume_ratio, 2),
            "vwap_deviation_pct": round(vwap_dev * 100.0, 2),
            "prior_low": prior_low,
            "description": "No crash liquidity short pattern."
        }


class VolatilityBreakoutEngine:
    """
    Strategy 6: Adaptive Volatility Breakout.
    Designed for MCX Gold, Crude Oil, and Index momentum to capture multi-hour
    directional expansion while filtering out false breakout chop.
    Conditions:
    - Upper Breakout: Close > 20-period High, Volume > 1.2x average, ATR expanding.
    - Lower Breakout: Close < 20-period Low, Volume > 1.2x average, ATR expanding.
    Vote: +1 (BUY), -1 (SELL), 0 (NEUTRAL).
    """
    CHANNEL_PERIOD = 20
    VOLUME_EXPANSION_RATIO = 1.2

    @classmethod
    def evaluate(cls, df: pd.DataFrame) -> Dict[str, Any]:
        if len(df) < cls.CHANNEL_PERIOD + 2:
            return {"vote": 0, "breakout_type": "NONE", "description": "Insufficient candles for VolatilityBreakout."}

        cur_close = float(df["Close"].iloc[-1])
        cur_volume = float(df["Volume"].iloc[-1]) if "Volume" in df.columns else 1000.0

        # Rolling 20-period Donchian Channels (strictly prior to current candle)
        window = df.iloc[-(cls.CHANNEL_PERIOD + 1):-1]
        channel_high = float(window["High"].max())
        channel_low = float(window["Low"].min())
        avg_vol = float(window["Volume"].mean()) if "Volume" in df.columns else 1000.0
        vol_ratio = cur_volume / (avg_vol + 1e-9)

        # ATR Expansion check
        atr_cur = ATRTrailingStop.calculate_atr(df, period=14)
        atr_prior = ATRTrailingStop.calculate_atr(df.iloc[:-5], period=14) if len(df) >= 20 else atr_cur
        atr_expanding = atr_cur >= atr_prior

        if cur_close > channel_high and vol_ratio >= cls.VOLUME_EXPANSION_RATIO and atr_expanding:
            desc = f"Bullish Volatility Breakout: Close ₹{cur_close:.2f} > Channel High ₹{channel_high:.2f} (Vol: {vol_ratio:.1f}x)"
            return {
                "vote": 1,
                "breakout_type": "BULLISH_BREAKOUT",
                "channel_high": channel_high,
                "channel_low": channel_low,
                "description": desc
            }
        elif cur_close < channel_low and vol_ratio >= cls.VOLUME_EXPANSION_RATIO and atr_expanding:
            desc = f"Bearish Volatility Breakout: Close ₹{cur_close:.2f} < Channel Low ₹{channel_low:.2f} (Vol: {vol_ratio:.1f}x)"
            return {
                "vote": -1,
                "breakout_type": "BEARISH_BREAKOUT",
                "channel_high": channel_high,
                "channel_low": channel_low,
                "description": desc
            }

        return {
            "vote": 0,
            "breakout_type": "NONE",
            "channel_high": channel_high,
            "channel_low": channel_low,
            "description": "Inside channel. No volatility breakout."
        }
