#!/usr/bin/env python3
"""
OmniTradePro - 10,000-Replay Monte Carlo Time Machine
Platform: Windows 10/11 64-bit | Python 3.10+
Executes high-density empirical permutation simulations across 5-minute candle distributions.
Quantifies concrete statistical odds of reaching 1:2 Risk-Reward target vs stop-loss
before the mandatory 15:15 PM IST square-off deadline.
"""

from typing import Dict, Any, Optional
import numpy as np
import pandas as pd
import yfinance as yf

from core.scanner_orb import SymbolNormalizer


class MonteCarloTimeMachine:
    """
    Quantitative Monte Carlo simulator and historical odds calculator.
    Simulates 10,000 forward price trajectories using the asset's empirical
    intraday 5-minute return distribution and volatility structure.
    """
    DEFAULT_HORIZON_STEPS = 69  # Number of 5-min intervals from 09:30 to 15:15 IST
    TARGET_FILTER_THRESHOLD = 65.0  # 65% minimum target hit probability

    def __init__(self) -> None:
        self.normalizer = SymbolNormalizer()

    def fetch_historical_candles(self, symbol: str, period: str = "60d") -> pd.DataFrame:
        """
        Extracts 60 days of 5-minute historical candles from Yahoo Finance.
        Preserves exact .NS formatting.
        """
        norm_sym = self.normalizer.normalize(symbol)
        ticker = yf.Ticker(norm_sym)
        df = ticker.history(period=period, interval="5m")

        if df.empty:
            return pd.DataFrame()

        if isinstance(df.columns, pd.MultiIndex):
            df.columns = [c[0] for c in df.columns]

        return df

    def run_simulation(
        self,
        symbol: str,
        entry_price: float,
        stop_loss: float,
        target_price: float,
        iterations: int = 10000,
        df_history: Optional[pd.DataFrame] = None,
        horizon_steps: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Executes a 10,000-iteration Monte Carlo permutation replay.
        Evaluates whether target_price or stop_loss is triggered first before 15:15 IST.
        
        Returns:
            {
                "symbol": str,
                "iterations": 10000,
                "target_hit_pct": float,
                "stop_hit_pct": float,
                "stagnant_pct": float,
                "win_odds_ratio": float,
                "passes_odds_filter": bool
            }
        """
        norm_sym = self.normalizer.normalize(symbol)
        steps = horizon_steps or self.DEFAULT_HORIZON_STEPS

        # 1. Acquire historical candle distribution
        if df_history is None or df_history.empty:
            df_history = self.fetch_historical_candles(norm_sym, period="60d")

        if df_history.empty or len(df_history) < 30:
            # Fallback to analytical random walk if history is unavailable
            returns = np.random.normal(loc=0.0001, scale=0.004, size=500)
        else:
            # Compute empirical 5-minute log returns
            closes = df_history["Close"].dropna().values
            returns = np.diff(np.log(closes))
            returns = returns[np.isfinite(returns)]
            if len(returns) < 20:
                returns = np.random.normal(loc=0.0001, scale=0.004, size=500)

        # 2. Vectorized Monte Carlo Path Generation (iterations x steps)
        # Sample directly from empirical return distribution to retain real kurtosis and skew
        random_sample_indices = np.random.choice(len(returns), size=(iterations, steps), replace=True)
        sampled_returns = returns[random_sample_indices]

        # Calculate forward cumulative price paths
        cum_returns = np.cumsum(sampled_returns, axis=1)
        price_paths = entry_price * np.exp(cum_returns)

        # Determine trade direction
        is_long = target_price > entry_price

        target_hits = 0
        stop_hits = 0
        stagnant = 0

        # 3. Path-by-path evaluation of barrier crossings
        if is_long:
            target_mask = price_paths >= target_price
            stop_mask = price_paths <= stop_loss
        else:  # Short trade
            target_mask = price_paths <= target_price
            stop_mask = price_paths >= stop_loss

        # Find first step where condition is met (or steps if never met)
        first_target_step = np.where(target_mask.any(axis=1), np.argmax(target_mask, axis=1), steps)
        first_stop_step = np.where(stop_mask.any(axis=1), np.argmax(stop_mask, axis=1), steps)

        for i in range(iterations):
            t_idx = first_target_step[i]
            s_idx = first_stop_step[i]

            if t_idx < steps and s_idx < steps:
                if t_idx < s_idx:
                    target_hits += 1
                elif s_idx < t_idx:
                    stop_hits += 1
                else:
                    # Same candle cross: conservative bias favors stop-loss
                    stop_hits += 1
            elif t_idx < steps:
                target_hits += 1
            elif s_idx < steps:
                stop_hits += 1
            else:
                stagnant += 1

        # 4. Statistical Metrics Aggregation
        target_hit_pct = round((target_hits / iterations) * 100.0, 2)
        stop_hit_pct = round((stop_hits / iterations) * 100.0, 2)
        stagnant_pct = round((stagnant / iterations) * 100.0, 2)

        # Ensure probabilities sum to 100.0% within rounding
        total_pct = target_hit_pct + stop_hit_pct + stagnant_pct
        if abs(total_pct - 100.0) > 0.001:
            stagnant_pct = round(100.0 - target_hit_pct - stop_hit_pct, 2)

        resolved_pct = target_hit_pct + stop_hit_pct
        win_odds_ratio = round(target_hit_pct / resolved_pct, 4) if resolved_pct > 0.0 else 0.0
        passes_odds_filter = bool(target_hit_pct >= self.TARGET_FILTER_THRESHOLD)

        return {
            "symbol": norm_sym,
            "iterations": int(iterations),
            "target_hit_pct": target_hit_pct,
            "stop_hit_pct": stop_hit_pct,
            "stagnant_pct": stagnant_pct,
            "win_odds_ratio": win_odds_ratio,
            "passes_odds_filter": passes_odds_filter
        }

