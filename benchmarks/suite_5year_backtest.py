#!/usr/bin/env python3
"""
OmniTradePro - 5-Year Historical Multi-Cycle Institutional Benchmark Suite (2020–2025)
Platform: Windows 10/11 64-bit | Python 3.10+
Evaluates:
1. 2020: COVID-19 Crash & Historic Recovery
2. 2021: Broad Institutional Bull Run
3. 2022: Inflation / Interest Rate Choppy Correction
4. 2023–2024: New All-Time High Expansions
5. 2025: High-Friction Volatility
Target Assets: NSE NIFTY 50, NSE BANK NIFTY, MCX CRUDE OIL, MCX GOLD
Features:
- Multi-Regime Classification (BULL_TREND, BEAR_TREND, MARKET_CRASH, CHOPPY hard lock)
- 6-Strategy Consensus (SMC, VWAP, Dual EMA, SuperTrend, CrashLiquidityShort, VolatilityBreakout)
- Predictive Probability Gate (>= 65% forward target confidence)
- Strictly Maximum 2 Trades/Day Cap per instrument
- Dynamic 1:2.5 Risk-to-Reward & 1:1 Break-Even Capital Lock (+₹5 buffer)
- Full statutory friction deduction (Brokerage, STT/CTT, Exchange, SEBI, Stamp Duty, GST)
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import math
from pathlib import Path
from typing import Dict, Any, List, Tuple
import pandas as pd
import numpy as np

# Runtime shims
import typing, builtins
builtins.List = typing.List
builtins.DatabaseConnectionManager = object

# Repository imports
from core.regime_classifier import RegimeClassifier, MarketRegime
from core.predictive_gate import PredictiveGate
from core.strategies import (
    SMCLiquiditySweep,
    InstitutionalVWAP,
    DualEMAMomentum,
    SuperTrendGate,
    ATRTrailingStop,
    CrashLiquidityShort,
    VolatilityBreakoutEngine
)
from core.risk_budget import RiskBudget

DATA_5YEAR_DIR = Path(__file__).resolve().parent / "data" / "5year"

STATUTORY_RATES = {
    "EQUITY_INTRADAY": {
        "brokerage_per_order": 20.0,
        "stt_sell_pct": 0.00025,
        "exchange_turnover_pct": 0.0000297,
        "sebi_turnover_pct": 0.000001,
        "stamp_duty_buy_pct": 0.00003,
        "gst_pct": 0.18
    },
    "COMMODITY_FUTURES": {
        "brokerage_per_order": 20.0,
        "ctt_sell_pct": 0.0001,
        "exchange_turnover_pct": 0.000021,
        "sebi_turnover_pct": 0.000001,
        "stamp_duty_buy_pct": 0.00002,
        "gst_pct": 0.18
    }
}

def compute_statutory_taxes(asset_type: str, buy_price: float, sell_price: float, qty: int) -> float:
    rates = STATUTORY_RATES["COMMODITY_FUTURES"] if asset_type == "MCX" else STATUTORY_RATES["EQUITY_INTRADAY"]
    buy_turnover = buy_price * qty
    sell_turnover = sell_price * qty
    total_turnover = buy_turnover + sell_turnover

    brokerage = rates["brokerage_per_order"] * 2.0
    stt_ctt = sell_turnover * (rates.get("stt_sell_pct", 0.0) or rates.get("ctt_sell_pct", 0.0))
    exchange_charges = total_turnover * rates["exchange_turnover_pct"]
    sebi_charges = total_turnover * rates["sebi_turnover_pct"]
    stamp_duty = buy_turnover * rates["stamp_duty_buy_pct"]
    gst = (brokerage + exchange_charges + sebi_charges) * rates["gst_pct"]

    return round(brokerage + stt_ctt + exchange_charges + sebi_charges + stamp_duty + gst, 2)


def run_5year_backtest_for_symbol(
    file_name: str,
    symbol_name: str,
    asset_type: str = "EQUITY",
    initial_capital: float = 500000.0,
    daily_cap: int = 2,
    rr_multiplier: float = 2.5
) -> Dict[str, Any]:
    csv_path = DATA_5YEAR_DIR / file_name
    if not csv_path.exists():
        raise FileNotFoundError(f"Missing 5-year data file: {csv_path}")

    df = pd.read_csv(csv_path, index_col=0, parse_dates=True)

    capital = initial_capital
    peak_capital = capital
    max_drawdown_pct = 0.0

    daily_trades_counter: Dict[str, int] = {}
    daily_equity_curves: Dict[str, float] = {}
    executed_trades: List[Dict[str, Any]] = []

    LOOKBACK = 30
    i = LOOKBACK
    n = len(df)

    while i < n - 1:
        window = df.iloc[max(0, i - LOOKBACK):i]
        cur_row = df.iloc[i]
        timestamp = str(cur_row.name)
        date_str = timestamp.split(" ")[0] if " " in timestamp else timestamp.split("T")[0]
        year_str = date_str.split("-")[0]

        # Daily loss circuit breaker check (10% daily limit)
        if date_str not in daily_equity_curves:
            daily_equity_curves[date_str] = capital
        day_start_capital = daily_equity_curves[date_str]
        daily_loss = day_start_capital - capital
        if day_start_capital > 0 and (daily_loss / day_start_capital) >= 0.10:
            i += 1
            continue

        # Daily trade cap check (Max 2 trades/day per instrument)
        if daily_cap > 0 and daily_trades_counter.get(date_str, 0) >= daily_cap:
            i += 1
            continue

        # 1. Market Regime Evaluation
        regime_info = RegimeClassifier.classify(window)
        regime = regime_info["regime"]

        # Hard trading lock during CHOPPY markets to prevent friction decay
        if regime_info["is_trading_locked"]:
            i += 1
            continue

        # 2. Multi-Strategy Voting Matrix
        cur_price = float(cur_row["Close"])
        smc_res = SMCLiquiditySweep.evaluate(window)
        vwap_res = InstitutionalVWAP.evaluate(window)
        ema_res = DualEMAMomentum.evaluate(window)
        st_res = SuperTrendGate.evaluate(window, period=10, multiplier=2.0)
        crash_res = CrashLiquidityShort.evaluate(window)
        vb_res = VolatilityBreakoutEngine.evaluate(window)

        smc_vote = int(smc_res["vote"])
        vwap_vote = int(vwap_res["vote"])
        ema_vote = int(ema_res["vote"])
        st_vote = int(st_res["vote"])
        crash_vote = int(crash_res["vote"])
        vb_vote = int(vb_res["vote"])

        core_votes = [smc_vote, vwap_vote, ema_vote, st_vote]
        bullish_count = sum(1 for v in core_votes if v == 1)
        bearish_count = sum(1 for v in core_votes if v == -1)

        signal = "NEUTRAL"
        is_crash_trade = False

        # Crash Short priority execution
        if crash_res.get("is_crash_short", False) or (regime == MarketRegime.MARKET_CRASH and bearish_count >= 2):
            signal = "SELL"
            is_crash_trade = True
        elif vb_res["vote"] == 1 and bullish_count >= 2:
            signal = "BUY"
        elif vb_res["vote"] == -1 and bearish_count >= 2:
            signal = "SELL"
        elif bullish_count >= 3:
            signal = "BUY"
        elif bearish_count >= 3:
            signal = "SELL"

        if signal not in ("BUY", "SELL"):
            i += 1
            continue

        # 3. Dynamic Stop Loss & 1:2.5 R:R Target
        entry_price = cur_price
        atr_val = ATRTrailingStop.calculate_atr(window, period=14)
        risk_dist = round(max(atr_val * 1.5, entry_price * 0.005), 2)

        if signal == "BUY":
            stop_loss = round(entry_price - risk_dist, 2)
            target_price = round(entry_price + (rr_multiplier * risk_dist), 2)
        else:
            stop_loss = round(entry_price + risk_dist, 2)
            target_price = round(entry_price - (rr_multiplier * risk_dist), 2)

        # 4. Position Sizing
        try:
            sizing = RiskBudget.calculate_position_size(
                capital_inr=capital,
                entry_price=entry_price,
                stop_loss=stop_loss,
                target_price=target_price,
                margin_leverage=5.0 if asset_type == "EQUITY" else 2.0
            )
        except Exception:
            i += 1
            continue

        if not sizing["can_execute"] or sizing["gross_profit_expected"] < 70.0:
            i += 1
            continue

        quantity = sizing["quantity"]
        if quantity <= 0:
            i += 1
            continue

        # 5. Predictive Probability Gate Evaluation (>= 65% target probability)
        pred_res = PredictiveGate.evaluate(
            df=window,
            signal=signal,
            entry_price=entry_price,
            target_price=target_price,
            stop_loss=stop_loss,
            quantity=quantity,
            horizon_bars=15
        )
        if not pred_res["approved"] and not is_crash_trade:
            # Sub-65% forward target confidence (skip unless institutional crash short)
            i += 1
            continue

        # 6. Execute Forward Simulation with 1:1 Break-Even Lock & 50-50 Staged Scale-Out
        half_qty = math.floor(quantity / 2.0)
        remaining_qty = quantity - half_qty
        m1_reached = False
        m1_exit_price = 0.0
        m2_exit_price = 0.0
        be_locked = False
        active_stop_loss = stop_loss
        exit_reason = ""

        j = i + 1
        max_holding_bars = min(i + 15, n)

        while j < max_holding_bars:
            future_bar = df.iloc[j]
            f_high = float(future_bar["High"])
            f_low = float(future_bar["Low"])
            f_close = float(future_bar["Close"])

            if signal == "BUY":
                # 1:1 R:R Break-Even Stop Lock (+₹5 buffer)
                if not be_locked and f_high >= entry_price + risk_dist:
                    active_stop_loss = round(entry_price + 5.0, 2)
                    be_locked = True

                # Milestone 1: 1:2.5 Target reached
                if not m1_reached and f_high >= target_price:
                    m1_reached = True
                    m1_exit_price = target_price
                    active_stop_loss = round(entry_price + 5.0, 2)

                # Stop loss check
                if f_low <= active_stop_loss:
                    exit_reason = "STOP_LOSS_HIT" if not be_locked else "BREAK_EVEN_STOP_HIT"
                    if not m1_reached:
                        m1_exit_price = active_stop_loss
                        m2_exit_price = active_stop_loss
                    else:
                        m2_exit_price = active_stop_loss
                    break

            elif signal == "SELL":
                # 1:1 R:R Break-Even Stop Lock (+₹5 buffer)
                if not be_locked and f_low <= entry_price - risk_dist:
                    active_stop_loss = round(entry_price - 5.0, 2)
                    be_locked = True

                # Milestone 1: 1:2.5 Target reached
                if not m1_reached and f_low <= target_price:
                    m1_reached = True
                    m1_exit_price = target_price
                    active_stop_loss = round(entry_price - 5.0, 2)

                # Stop loss check
                if f_high >= active_stop_loss:
                    exit_reason = "STOP_LOSS_HIT" if not be_locked else "BREAK_EVEN_STOP_HIT"
                    if not m1_reached:
                        m1_exit_price = active_stop_loss
                        m2_exit_price = active_stop_loss
                    else:
                        m2_exit_price = active_stop_loss
                    break

            j += 1

        if j >= max_holding_bars or not exit_reason:
            exit_reason = "TIME_EXPIRY_SQUARE_OFF"
            timeout_bar = df.iloc[min(j, n - 1)]
            timeout_close = float(timeout_bar["Close"])
            if not m1_reached:
                m1_exit_price = timeout_close
                m2_exit_price = timeout_close
            else:
                m2_exit_price = timeout_close

        # Calculate Gross P&L
        if signal == "BUY":
            gross_m1 = half_qty * (m1_exit_price - entry_price)
            gross_m2 = remaining_qty * (m2_exit_price - entry_price)
        else:
            gross_m1 = half_qty * (entry_price - m1_exit_price)
            gross_m2 = remaining_qty * (entry_price - m2_exit_price)

        gross_pnl = round(gross_m1 + gross_m2, 2)
        avg_exit = ((m1_exit_price * half_qty) + (m2_exit_price * remaining_qty)) / quantity
        statutory_tax = compute_statutory_taxes(asset_type, entry_price, avg_exit, quantity)
        net_pnl = round(gross_pnl - statutory_tax, 2)
        capital += net_pnl

        if capital > peak_capital:
            peak_capital = capital
        dd = ((peak_capital - capital) / peak_capital) * 100.0 if peak_capital > 0 else 0.0
        if dd > max_drawdown_pct:
            max_drawdown_pct = dd

        daily_trades_counter[date_str] = daily_trades_counter.get(date_str, 0) + 1

        executed_trades.append({
            "timestamp": timestamp,
            "date": date_str,
            "year": year_str,
            "symbol": symbol_name,
            "signal": signal,
            "entry_price": entry_price,
            "exit_reason": exit_reason,
            "quantity": quantity,
            "gross_pnl": gross_pnl,
            "tax": statutory_tax,
            "net_pnl": net_pnl,
            "capital_after": round(capital, 2),
            "is_win": net_pnl > 0.0,
            "is_crash_trade": is_crash_trade,
            "regime": str(regime.value) if hasattr(regime, "value") else str(regime)
        })

        i = max(j, i + 1)

    return {
        "symbol": symbol_name,
        "asset_type": asset_type,
        "initial_capital": initial_capital,
        "ending_capital": round(capital, 2),
        "total_net_pnl": round(capital - initial_capital, 2),
        "max_drawdown_pct": round(max_drawdown_pct, 2),
        "trades": executed_trades
    }


def main():
    print("=" * 80)
    print("OMNITRADEPRO - 5-YEAR MULTI-CYCLE INSTITUTIONAL BENCHMARK (2020–2025)")
    print("=" * 80)

    benchmarks = [
        ("nifty50_5year.csv", "NIFTY 50", "EQUITY"),
        ("banknifty_5year.csv", "BANK NIFTY", "EQUITY"),
        ("crudeoil_5year.csv", "MCX CRUDE OIL", "MCX"),
        ("gold_5year.csv", "MCX GOLD", "MCX"),
    ]

    all_symbol_results = []
    all_trades = []

    for f, sym, a_type in benchmarks:
        print(f"\n[RUNNING 5-YEAR BACKTEST] Simulating {sym} (2020–2025 Multi-Cycle History)...")
        res = run_5year_backtest_for_symbol(f, sym, a_type)
        all_symbol_results.append(res)
        all_trades.extend(res["trades"])

    # Aggregate across 5 years
    all_trades_df = pd.DataFrame(all_trades)
    years = sorted(list(all_trades_df["year"].unique()))

    print("\n" + "=" * 80)
    print("YEAR-BY-YEAR MULTI-REGIME PERFORMANCE SCORECARD (2020–2025):")
    print("=" * 80)
    print(f"{'YEAR':<6} | {'TRADES':<7} | {'WIN RATE':<9} | {'GROSS P&L':<15} | {'TAXES PAID':<14} | {'NET REALIZED P&L':<18} | {'PF':<5}")
    print("-" * 80)

    for yr in years:
        yr_df = all_trades_df[all_trades_df["year"] == yr]
        t_count = len(yr_df)
        wins = yr_df[yr_df["is_win"]]
        losses = yr_df[~yr_df["is_win"]]
        wr = round(len(wins) / t_count * 100.0, 2) if t_count > 0 else 0.0
        gw = sum(wins["gross_pnl"])
        gl = abs(sum(losses["gross_pnl"]))
        gpnl = round(gw - gl, 2)
        taxes = round(sum(yr_df["tax"]), 2)
        net_pnl = round(sum(yr_df["net_pnl"]), 2)
        pf = round(gw / gl, 2) if gl > 0 else 99.0

        print(f"{yr:<6} | {t_count:<7} | {wr:<8}% | ₹{gpnl:>13,.2f} | ₹{taxes:>12,.2f} | ₹{net_pnl:>16,.2f} | {pf:<5}")

    print("=" * 80)

    # 5-Year Aggregate Summary
    total_trades = len(all_trades_df)
    total_wins = len(all_trades_df[all_trades_df["is_win"]])
    total_losses = len(all_trades_df[~all_trades_df["is_win"]])
    comb_wr = round(total_wins / total_trades * 100.0, 2) if total_trades > 0 else 0.0
    total_gw = sum(all_trades_df[all_trades_df["is_win"]]["gross_pnl"])
    total_gl = abs(sum(all_trades_df[~all_trades_df["is_win"]]["gross_pnl"]))
    comb_gross_pnl = round(total_gw - total_gl, 2)
    comb_taxes = round(sum(all_trades_df["tax"]), 2)
    comb_net_pnl = round(sum(all_trades_df["net_pnl"]), 2)
    comb_pf = round(total_gw / total_gl, 2) if total_gl > 0 else 0.0
    comb_peak_mdd = max(r["max_drawdown_pct"] for r in all_symbol_results)

    print("\n" + "=" * 80)
    print("5-YEAR AGGREGATE INSTITUTIONAL PORTFOLIO RESULTS (2020–2025):")
    print("=" * 80)
    print(f"Total Trades Executed Across 5 Years : {total_trades} ({total_wins} Wins / {total_losses} Losses)")
    print(f"Overall 5-Year Win Rate              : {comb_wr}%")
    print(f"Total Gross P&L Generated            : ₹{comb_gross_pnl:,.2f}")
    print(f"Total Statutory Indian Taxes Paid    : ₹{comb_taxes:,.2f}")
    print(f"Total Net Realized P&L (Alpha)       : ₹{comb_net_pnl:,.2f}")
    print(f"Aggregate Profit Factor              : {comb_pf}")
    print(f"Peak Multi-Cycle Maximum Drawdown    : {comb_peak_mdd}%")
    print("=" * 80)

    # 2020 COVID Crash Short Deep Dive
    print("\n" + "=" * 80)
    print("2020 COVID-19 CRASH SHORT ALPHA DEEP DIVE (FEB 15 - APR 30, 2020):")
    print("=" * 80)
    crash_2020_df = all_trades_df[(all_trades_df["date"] >= "2020-02-15") & (all_trades_df["date"] <= "2020-04-30")]
    c_trades = len(crash_2020_df)
    c_shorts = crash_2020_df[crash_2020_df["signal"] == "SELL"]
    c_short_count = len(c_shorts)
    c_short_wins = len(c_shorts[c_shorts["is_win"]])
    c_short_wr = round(c_short_wins / c_short_count * 100.0, 2) if c_short_count > 0 else 0.0
    c_short_gross = sum(c_shorts["gross_pnl"])
    c_short_net = sum(c_shorts["net_pnl"])

    print(f"Total Setups during 2020 Panic Crash : {c_trades}")
    print(f"Crash Short / Put Trades Executed   : {c_short_count} ({c_short_wins} Wins / {c_short_count - c_short_wins} Losses)")
    print(f"Crash Short Win Rate                : {c_short_wr}%")
    print(f"Crash Short Gross P&L               : ₹{c_short_gross:,.2f}")
    print(f"Crash Short Net Realized P&L        : ₹{c_short_net:,.2f}")
    print("=" * 80)

if __name__ == "__main__":
    main()
