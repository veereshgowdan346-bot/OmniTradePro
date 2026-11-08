#!/usr/bin/env python3
"""
OmniTradePro - Dimension 1: 2025 Historical Data Backtest & Profitability Metrics
Simulates full consensus evaluation and execution against authentic 2025 intraday data.
"""

import sys
import math
from pathlib import Path
from typing import Dict, Any, List
import pandas as pd
import numpy as np

# Apply runtime typing shim for clean import of repository modules
import typing, builtins
builtins.List = typing.List
builtins.DatabaseConnectionManager = object

# Repository imports
from core.consensus import ConsensusEngine
from core.risk_budget import RiskBudget
from core.strategies import ATRTrailingStop

DATA_DIR = Path(__file__).resolve().parent / "data"

STATUTORY_RATES = {
    "EQUITY_INTRADAY": {
        "brokerage_per_order": 20.0,      # ₹20 per executed order (₹40 round-trip)
        "stt_sell_pct": 0.00025,           # 0.025% on sell turnover
        "exchange_turnover_pct": 0.0000297,# 0.00297% on both buy & sell
        "sebi_turnover_pct": 0.000001,     # ₹10 per crore (0.0001%)
        "stamp_duty_buy_pct": 0.00003,     # 0.003% on buy turnover
        "gst_pct": 0.18                    # 18% on (brokerage + exchange + sebi)
    },
    "COMMODITY_FUTURES": {
        "brokerage_per_order": 20.0,
        "ctt_sell_pct": 0.0001,            # 0.01% on sell turnover
        "exchange_turnover_pct": 0.000021, # 0.0021% on both
        "sebi_turnover_pct": 0.000001,
        "stamp_duty_buy_pct": 0.00002,
        "gst_pct": 0.18
    }
}

def compute_statutory_friction(symbol_type: str, buy_price: float, sell_price: float, qty: int) -> float:
    rates = STATUTORY_RATES["COMMODITY_FUTURES"] if symbol_type == "MCX" else STATUTORY_RATES["EQUITY_INTRADAY"]
    buy_turnover = buy_price * qty
    sell_turnover = sell_price * qty
    total_turnover = buy_turnover + sell_turnover
    
    brokerage = rates["brokerage_per_order"] * 2.0
    stt_ctt = sell_turnover * (rates.get("stt_sell_pct", 0.0) or rates.get("ctt_sell_pct", 0.0))
    exchange_charges = total_turnover * rates["exchange_turnover_pct"]
    sebi_charges = total_turnover * rates["sebi_turnover_pct"]
    stamp_duty = buy_turnover * rates["stamp_duty_buy_pct"]
    gst = (brokerage + exchange_charges + sebi_charges) * rates["gst_pct"]
    
    total_tax = brokerage + stt_ctt + exchange_charges + sebi_charges + stamp_duty + gst
    return round(total_tax, 2)

def run_backtest_for_symbol(file_name: str, symbol_name: str, asset_type: str = "EQUITY", initial_capital: float = 500000.0) -> Dict[str, Any]:
    csv_path = DATA_DIR / file_name
    if not csv_path.exists():
        raise FileNotFoundError(f"Missing data file: {csv_path}")
        
    df = pd.read_csv(csv_path, index_col=0, parse_dates=True)
    
    total_setups_evaluated = 0
    filtered_sub_hurdle = 0
    executed_trades = []
    
    capital = initial_capital
    daily_equity_curves: Dict[str, float] = {}
    peak_capital = capital
    max_drawdown_pct = 0.0
    daily_circuit_breaker_breached = False
    
    LOOKBACK = 25
    i = LOOKBACK
    n = len(df)
    
    while i < n - 1:
        window = df.iloc[max(0, i - LOOKBACK):i]
        cur_row = df.iloc[i]
        timestamp = str(cur_row.name)
        date_str = timestamp.split(" ")[0] if " " in timestamp else timestamp.split("T")[0]
        
        # Daily loss tracking
        if date_str not in daily_equity_curves:
            daily_equity_curves[date_str] = capital
            
        day_start_capital = daily_equity_curves[date_str]
        daily_loss = day_start_capital - capital
        if day_start_capital > 0 and (daily_loss / day_start_capital) >= 0.10:
            daily_circuit_breaker_breached = True
            # Skip trading for remainder of day
            i += 1
            continue
            
        res = ConsensusEngine.evaluate_consensus(window, passes_odds_filter=True, current_tick_ltp=float(cur_row["Close"]))
        total_setups_evaluated += 1
        
        if not res["approved"] or res["signal"] not in ("BUY", "SELL"):
            i += 1
            continue
            
        entry_price = res["entry_price"]
        stop_loss = res["stop_loss"]
        target_price = res["target_price"]
        signal = res["signal"]
        
        # RiskBudget Position Sizing & Pre-Trade ₹70 Gross Profit Gate
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
            filtered_sub_hurdle += 1
            i += 1
            continue
            
        quantity = sizing["quantity"]
        if quantity <= 0:
            filtered_sub_hurdle += 1
            i += 1
            continue
            
        # Simulate trade execution forward
        trade_entry_idx = i
        pos_qty = quantity
        half_qty = math.floor(pos_qty / 2.0)
        remaining_qty = pos_qty - half_qty
        
        m1_reached = False
        m1_exit_price = 0.0
        m2_exit_price = 0.0
        active_stop_loss = stop_loss
        exit_reason = ""
        
        j = i + 1
        while j < min(i + 15, n):  # Max holding 15 hours / session
            future_bar = df.iloc[j]
            f_high = float(future_bar["High"])
            f_low = float(future_bar["Low"])
            f_close = float(future_bar["Close"])
            
            if signal == "BUY":
                # Milestone 1: 1:2 R:R Target check
                if not m1_reached and f_high >= target_price:
                    m1_reached = True
                    m1_exit_price = target_price
                    active_stop_loss = entry_price  # Move SL to Break-Even
                    
                # Stop loss check
                if f_low <= active_stop_loss:
                    exit_reason = "STOP_LOSS_HIT" if not m1_reached else "BREAK_EVEN_TRAIL_HIT"
                    if not m1_reached:
                        m1_exit_price = active_stop_loss
                        m2_exit_price = active_stop_loss
                    else:
                        m2_exit_price = active_stop_loss
                    break
            elif signal == "SELL":
                # Milestone 1: 1:2 R:R Target check
                if not m1_reached and f_low <= target_price:
                    m1_reached = True
                    m1_exit_price = target_price
                    active_stop_loss = entry_price  # Move SL to Break-Even
                    
                # Stop loss check
                if f_high >= active_stop_loss:
                    exit_reason = "STOP_LOSS_HIT" if not m1_reached else "BREAK_EVEN_TRAIL_HIT"
                    if not m1_reached:
                        m1_exit_price = active_stop_loss
                        m2_exit_price = active_stop_loss
                    else:
                        m2_exit_price = active_stop_loss
                    break
            j += 1
            
        if j >= min(i + 15, n) or not exit_reason:
            exit_reason = "TIME_EXPIRY_SQUARE_OFF"
            timeout_bar = df.iloc[min(j, n - 1)]
            timeout_close = float(timeout_bar["Close"])
            if not m1_reached:
                m1_exit_price = timeout_close
                m2_exit_price = timeout_close
            else:
                m2_exit_price = timeout_close
                
        # Calculate Gross Realized P&L
        if signal == "BUY":
            gross_pnl_m1 = half_qty * (m1_exit_price - entry_price)
            gross_pnl_m2 = remaining_qty * (m2_exit_price - entry_price)
        else:
            gross_pnl_m1 = half_qty * (entry_price - m1_exit_price)
            gross_pnl_m2 = remaining_qty * (entry_price - m2_exit_price)
            
        gross_pnl = round(gross_pnl_m1 + gross_pnl_m2, 2)
        
        # Calculate Exact Statutory Charges
        avg_exit_price = ((m1_exit_price * half_qty) + (m2_exit_price * remaining_qty)) / pos_qty if pos_qty > 0 else entry_price
        statutory_tax = compute_statutory_friction(asset_type, entry_price, avg_exit_price, pos_qty)
        
        # Net Realized P&L (Gross - Taxes)
        net_pnl = round(gross_pnl - statutory_tax, 2)
        capital += net_pnl
        
        if capital > peak_capital:
            peak_capital = capital
        drawdown_pct = ((peak_capital - capital) / peak_capital) * 100.0 if peak_capital > 0 else 0.0
        if drawdown_pct > max_drawdown_pct:
            max_drawdown_pct = drawdown_pct
            
        executed_trades.append({
            "timestamp": timestamp,
            "signal": signal,
            "entry_price": entry_price,
            "target_price": target_price,
            "stop_loss": stop_loss,
            "quantity": pos_qty,
            "exit_reason": exit_reason,
            "gross_pnl": gross_pnl,
            "statutory_tax": statutory_tax,
            "net_pnl": net_pnl,
            "capital_after": round(capital, 2),
            "is_win": net_pnl > 0.0
        })
        
        # Advance index to exit index to avoid overlapping executions on same bar
        i = max(j, i + 1)
        
    # Summary Metrics Calculation
    total_executed = len(executed_trades)
    winning_trades = [t for t in executed_trades if t["is_win"]]
    losing_trades = [t for t in executed_trades if not t["is_win"]]
    
    win_rate_pct = round((len(winning_trades) / total_executed * 100.0), 2) if total_executed > 0 else 0.0
    gross_profits = sum(t["gross_pnl"] for t in winning_trades)
    gross_losses = abs(sum(t["gross_pnl"] for t in losing_trades))
    profit_factor = round(gross_profits / gross_losses, 2) if gross_losses > 0 else (99.0 if gross_profits > 0 else 0.0)
    
    total_net_pnl_inr = round(capital - initial_capital, 2)
    total_net_pnl_pct = round((total_net_pnl_inr / initial_capital) * 100.0, 2)
    total_statutory_paid = round(sum(t["statutory_tax"] for t in executed_trades), 2)
    
    return {
        "symbol": symbol_name,
        "candles_analyzed": len(df),
        "total_setups_evaluated": total_setups_evaluated,
        "filtered_sub_hurdle": filtered_sub_hurdle,
        "executed_trades_count": total_executed,
        "winning_trades_count": len(winning_trades),
        "losing_trades_count": len(losing_trades),
        "win_rate_pct": win_rate_pct,
        "gross_profits": round(gross_profits, 2),
        "gross_losses": round(gross_losses, 2),
        "total_statutory_paid": total_statutory_paid,
        "total_net_pnl_inr": total_net_pnl_inr,
        "total_net_pnl_pct": total_net_pnl_pct,
        "profit_factor": profit_factor,
        "max_drawdown_pct": round(max_drawdown_pct, 2),
        "daily_circuit_breaker_breached": daily_circuit_breaker_breached,
        "starting_capital": initial_capital,
        "ending_capital": round(capital, 2)
    }

def run_suite1():
    print("=" * 80)
    print("SUITE 1: 2025 HISTORICAL DATA BACKTEST & PROFITABILITY BENCHMARK")
    print("=" * 80)
    
    benchmarks = [
        ("nifty50_2025_1h.csv", "NIFTY 50", "EQUITY"),
        ("banknifty_2025_1h.csv", "BANK NIFTY", "EQUITY"),
        ("crudeoil_2025_1h.csv", "MCX CRUDE OIL", "MCX"),
        ("gold_2025_1h.csv", "MCX GOLD", "MCX"),
    ]
    
    all_results = []
    for file_name, sym, a_type in benchmarks:
        print(f"\n[RUNNING BACKTEST] Evaluating {sym} (2025 Authentic Intraday Series)...")
        res = run_backtest_for_symbol(file_name, sym, a_type)
        all_results.append(res)
        
        print(f"  * Candles Analyzed           : {res['candles_analyzed']}")
        print(f"  * Consensus Setups Evaluated : {res['total_setups_evaluated']}")
        print(f"  * Filtered by ₹70 Gate       : {res['filtered_sub_hurdle']}")
        print(f"  * Executed Trades            : {res['executed_trades_count']}")
        print(f"  * Win Rate Percentage        : {res['win_rate_pct']}% ({res['winning_trades_count']}W / {res['losing_trades_count']}L)")
        print(f"  * Gross Profits              : ₹{res['gross_profits']:,.2f}")
        print(f"  * Gross Losses               : ₹{res['gross_losses']:,.2f}")
        print(f"  * Statutory Friction Deducted: ₹{res['total_statutory_paid']:,.2f}")
        print(f"  * Net Realized Profit (INR)  : ₹{res['total_net_pnl_inr']:,.2f} ({res['total_net_pnl_pct']}%)")
        print(f"  * Profit Factor              : {res['profit_factor']}")
        print(f"  * Maximum Drawdown           : {res['max_drawdown_pct']}%")
        print(f"  * 10% Daily Breaker Breached : {res['daily_circuit_breaker_breached']}")
        print(f"  * Starting / Ending Capital  : ₹{res['starting_capital']:,.2f} -> ₹{res['ending_capital']:,.2f}")
        
    print("\n" + "=" * 80)
    print("COMBINED PORTFOLIO 2025 PERFORMANCE SUMMARY:")
    print("=" * 80)
    total_executed = sum(r["executed_trades_count"] for r in all_results)
    total_wins = sum(r["winning_trades_count"] for r in all_results)
    total_losses = sum(r["losing_trades_count"] for r in all_results)
    comb_win_rate = round(total_wins / total_executed * 100.0, 2) if total_executed > 0 else 0.0
    comb_net_pnl = sum(r["total_net_pnl_inr"] for r in all_results)
    comb_statutory = sum(r["total_statutory_paid"] for r in all_results)
    comb_gross_profit = sum(r["gross_profits"] for r in all_results)
    comb_gross_loss = sum(r["gross_losses"] for r in all_results)
    comb_pf = round(comb_gross_profit / comb_gross_loss, 2) if comb_gross_loss > 0 else 99.0
    comb_mdd = max(r["max_drawdown_pct"] for r in all_results)
    any_circuit_breach = any(r["daily_circuit_breaker_breached"] for r in all_results)
    
    print(f"Total Trades Executed Across 2025: {total_executed} ({total_wins} Wins / {total_losses} Losses)")
    print(f"Combined Win Rate                : {comb_win_rate}%")
    print(f"Total Net Realized P&L           : ₹{comb_net_pnl:,.2f}")
    print(f"Total Statutory Friction Paid    : ₹{comb_statutory:,.2f}")
    print(f"Overall Profit Factor            : {comb_pf}")
    print(f"Peak Maximum Drawdown            : {comb_mdd}%")
    print(f"Daily Circuit Breaker Breached   : {any_circuit_breach}")
    print("=" * 80)
    
    return all_results

if __name__ == "__main__":
    run_suite1()

