#!/usr/bin/env python3
"""
OmniTradePro - Nifty 50 15-Minute ORB & Multi-Setup Scanner
Platform: Windows 10/11 64-bit | Python 3.10+
Implements Indian Market (IST: 09:15 to 15:30) intraday setup detection:
1. 15-Min Opening Range Breakout (ORB) with volume surge confirmation
2. 20-Day High Breakout resistance clearance
3. Oversold Mean-Reversion Bounce (RSI-14 < 30)
Preserves exact Yahoo Finance '.NS' ticker formatting without dot mutilation.
"""

import re
from datetime import datetime, time as dtime, timezone
from typing import Dict, Any, List, Optional
import pandas as pd
import numpy as np
import yfinance as yf


class SymbolNormalizer:
    """
    Normalizes Indian market ticker symbols to exact Yahoo Finance compliance.
    Ensures '.NS' suffix is preserved and dots are never converted to hyphens.
    Supports symbol identifiers up to 20 characters in length.
    """
    MAX_SYMBOL_LENGTH = 20

    @classmethod
    def normalize(cls, symbol: str) -> str:
        """
        Normalizes a ticker to standard Yahoo Finance '.NS' format.
        Examples:
            'RELIANCE'       -> 'RELIANCE.NS'
            'RELIANCE.NS'    -> 'RELIANCE.NS'
            'TATAMOTORS.NS'  -> 'TATAMOTORS.NS'
            'BAJFINANCE'     -> 'BAJFINANCE.NS'
            'M&M'            -> 'M&M.NS'
        """
        clean_sym = symbol.strip().upper()

        if len(clean_sym) > cls.MAX_SYMBOL_LENGTH:
            raise ValueError(
                f"Symbol '{clean_sym}' exceeds maximum supported length of {cls.MAX_SYMBOL_LENGTH} characters."
            )

        # Do not mutilate dot if already present with .NS or .BO
        if clean_sym.endswith(".NS") or clean_sym.endswith(".BO"):
            return clean_sym

        # Append .NS default for Indian equities
        return f"{clean_sym}.NS"


class MarketScannerORB:
    """
    Quantitative intraday market scanner calibrated to Indian Standard Time (IST: 09:15-15:30).
    Screens Nifty 50 and custom watchlists for structural price momentum.
    """
    MARKET_OPEN = dtime(9, 15)
    ORB_CUTOFF = dtime(9, 30)
    MARKET_CLOSE = dtime(15, 30)

    def __init__(self) -> None:
        self.normalizer = SymbolNormalizer()

    def fetch_intraday_data(
        self,
        symbol: str,
        period: str = "5d",
        interval: str = "5m"
    ) -> pd.DataFrame:
        """
        Downloads clean 5-minute candle history for the normalized ticker.
        Handles MultiIndex headers and time-zone localization.
        """
        norm_sym = self.normalizer.normalize(symbol)
        ticker = yf.Ticker(norm_sym)
        df = ticker.history(period=period, interval=interval)

        if df.empty:
            return pd.DataFrame()

        # Flatten multi-level columns if emitted by newer yfinance versions
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = [c[0] for c in df.columns]

        # Convert index to Indian Standard Time (UTC+05:30) if timezone-aware
        if df.index.tz is not None:
            df.index = df.index.tz_convert("Asia/Kolkata")
        else:
            df.index = df.index.tz_localize("UTC").tz_convert("Asia/Kolkata")

        return df

    @staticmethod
    def calculate_rsi(series: pd.Series, period: int = 14) -> pd.Series:
        """Computes Wilder's Relative Strength Index (RSI)."""
        delta = series.diff()
        gain = delta.clip(lower=0.0)
        loss = -delta.clip(upper=0.0)

        avg_gain = gain.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()
        avg_loss = loss.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()

        rs = avg_gain / avg_loss.replace(0.0, np.nan)
        rsi = 100.0 - (100.0 / (1.0 + rs))
        return rsi.fillna(50.0)

    def scan_symbol(
        self,
        symbol: str,
        df_intraday: Optional[pd.DataFrame] = None,
        df_daily: Optional[pd.DataFrame] = None
    ) -> Dict[str, Any]:
        """
        Evaluates an individual stock across the 3 core quantitative setups:
        1. 15-Minute Opening Range Breakout (ORB)
        2. 20-Day High Breakout
        3. Oversold Mean-Reversion Bounce
        """
        norm_sym = self.normalizer.normalize(symbol)
        now_iso = datetime.now(timezone.utc).isoformat()

        # Fetch intraday data if not provided
        if df_intraday is None or df_intraday.empty:
            df_intraday = self.fetch_intraday_data(norm_sym, period="5d", interval="5m")

        if df_intraday.empty or len(df_intraday) < 4:
            return {
                "symbol": norm_sym,
                "setup_type": "NONE",
                "breakout_level": 0.0,
                "current_price": 0.0,
                "volume_spike": False,
                "timestamp": now_iso,
                "rationale": "Insufficient intraday candle data (minimum 4 candles required)."
            }

        latest_bar = df_intraday.iloc[-1]
        current_price = round(float(latest_bar["Close"]), 2)
        latest_time = df_intraday.index[-1].time()
        current_date = df_intraday.index[-1].date()

        # Calculate 20-period average volume for spike confirmation
        vol_window = min(20, len(df_intraday))
        avg_vol = df_intraday["Volume"].iloc[-vol_window:].mean()
        current_vol = float(latest_bar["Volume"])
        volume_spike = bool(current_vol >= (avg_vol * 1.20) and current_vol > 0)

        # =====================================================================
        # 1. 15-Min Opening Range Breakout (ORB) Evaluation
        # =====================================================================
        # Filter candles for current date
        today_mask = df_intraday.index.date == current_date
        today_bars = df_intraday[today_mask]

        if len(today_bars) >= 3:
            # 09:15 to 09:30 comprises the first three 5-minute candles
            opening_15m = today_bars.iloc[:3]
            orb_high = round(float(opening_15m["High"].max()), 2)
            orb_low = round(float(opening_15m["Low"].min()), 2)

            # Check for breakout occurring after 09:30 AM IST
            if latest_time >= self.ORB_CUTOFF:
                # Bullish Breakout above 15-min Opening High
                if current_price > orb_high and volume_spike:
                    return {
                        "symbol": norm_sym,
                        "setup_type": "ORB_BULLISH_BREAKOUT",
                        "breakout_level": orb_high,
                        "current_price": current_price,
                        "volume_spike": True,
                        "timestamp": now_iso,
                        "rationale": f"Price ₹{current_price} crossed above 15-min Opening High ₹{orb_high} with 1.2x volume surge."
                    }
                # Bearish Breakout below 15-min Opening Low
                elif current_price < orb_low and volume_spike:
                    return {
                        "symbol": norm_sym,
                        "setup_type": "ORB_BEARISH_BREAKOUT",
                        "breakout_level": orb_low,
                        "current_price": current_price,
                        "volume_spike": True,
                        "timestamp": now_iso,
                        "rationale": f"Price ₹{current_price} broke below 15-min Opening Low ₹{orb_low} with 1.2x volume surge."
                    }

        # =====================================================================
        # 2. 20-Day High Resistance Breakout
        # =====================================================================
        # Use daily dataframe if passed, else fetch
        if df_daily is None or df_daily.empty:
            try:
                df_daily = yf.Ticker(norm_sym).history(period="3mo", interval="1d")
            except Exception:
                df_daily = pd.DataFrame()

        if not df_daily.empty and len(df_daily) >= 21:
            # Previous 20 completed daily sessions
            prev_20_days = df_daily.iloc[-21:-1]
            twenty_day_high = round(float(prev_20_days["High"].max()), 2)

            if current_price > twenty_day_high:
                return {
                    "symbol": norm_sym,
                    "setup_type": "20_DAY_HIGH_BREAKOUT",
                    "breakout_level": twenty_day_high,
                    "current_price": current_price,
                    "volume_spike": volume_spike,
                    "timestamp": now_iso,
                    "rationale": f"Intraday price ₹{current_price} breached 20-session resistance at ₹{twenty_day_high}."
                }

        # =====================================================================
        # 3. Oversold Mean-Reversion Bounce
        # =====================================================================
        rsi_series = self.calculate_rsi(df_intraday["Close"], period=14)
        if len(rsi_series) >= 2:
            prev_rsi = rsi_series.iloc[-2]
            cur_rsi = rsi_series.iloc[-1]
            prev_bar = df_intraday.iloc[-2]

            # Condition: Previous candle was oversold (<30) and current bar forms bullish candle
            is_bullish_candle = float(latest_bar["Close"]) > float(latest_bar["Open"])
            if prev_rsi < 30.0 and is_bullish_candle and cur_rsi >= prev_rsi:
                support_level = round(float(min(prev_bar["Low"], latest_bar["Low"])), 2)
                return {
                    "symbol": norm_sym,
                    "setup_type": "OVERSOLD_MEAN_REVERSION_BOUNCE",
                    "breakout_level": support_level,
                    "current_price": current_price,
                    "volume_spike": volume_spike,
                    "timestamp": now_iso,
                    "rationale": f"RSI rebounded from oversold ({prev_rsi:.1f} -> {cur_rsi:.1f}) with bullish reversal candle."
                }

        # No active trigger
        return {
            "symbol": norm_sym,
            "setup_type": "NONE",
            "breakout_level": 0.0,
            "current_price": current_price,
            "volume_spike": volume_spike,
            "timestamp": now_iso,
            "rationale": "No structural breakout setup triggered."
        }

    def scan_watchlist(self, symbols: List[str]) -> List[Dict[str, Any]]:
        """
        Scans an entire watchlist (e.g. Nifty 50), filtering active trade setups.
        """
        active_candidates: List[Dict[str, Any]] = []

        for sym in symbols:
            try:
                result = self.scan_symbol(sym)
                if result["setup_type"] != "NONE":
                    active_candidates.append(result)
            except Exception:
                continue

        return active_candidates
