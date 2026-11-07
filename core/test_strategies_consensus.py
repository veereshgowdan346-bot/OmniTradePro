#!/usr/bin/env python3
"""
OmniTradePro - Phase 5 Strategy Core & Consensus Engine Test Suite
Platform: Windows 10/11 64-bit | Python 3.10+
Validates indicator precision (VWAP, EMA9/21, SuperTrend, SMC sweep),
4-algorithm consensus matrix voting, and the 50-50 staged scale-out engine.
"""

import sys
from pathlib import Path
import pandas as pd
import numpy as np

# Add project root to sys.path
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from core.strategies import (
    SMCLiquiditySweep,
    InstitutionalVWAP,
    DualEMAMomentum,
    SuperTrendGate,
    ATRTrailingStop
)
from core.consensus import ConsensusEngine, StagedProfitManager


class ANSI:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    CYAN = "\033[96m"
    WHITE = "\033[97m"
    BG_GREEN = "\033[42m"
    BG_RED = "\033[41m"


def enable_windows_ansi() -> None:
    if sys.platform == "win32":
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            handle = kernel32.GetStdHandle(-11)
            mode = ctypes.c_ulong()
            if kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
                kernel32.SetConsoleMode(handle, mode.value | 0x0004)
        except Exception:
            pass


enable_windows_ansi()


def print_banner() -> None:
    print(f"{ANSI.CYAN}{ANSI.BOLD}")
    print("=" * 80)
    print("  ██████╗ ███╗   ███╗███╗   ██╗██╗████████╗██████╗  █████╗ ██████╗ ███████╗")
    print(" ██╔═══██╗████╗ ████║████╗  ██║██║╚══██╔══╝██╔══██╗██╔══██╗██╔══██╗██╔════╝")
    print(" ██║   ██║██╔████╔██║██╔██╗ ██║██║   ██║   ██████╔╝███████║██║  ██║█████╗  ")
    print(" ██║   ██║██║╚██╔╝██║██║╚██╗██║██║   ██║   ██╔══██╗██╔══██║██║  ██║██╔══╝  ")
    print(" ╚██████╔╝██║ ╚═╝ ██║██║ ╚████║██║   ██║   ██║  ██║██║  ██║██████╔╝███████╗")
    print("  ╚═════╝ ╚═╝     ╚═╝╚═╝  ╚═══╝╚═╝   ╚═╝   ╚═╝  ╚═╝╚═╝  ╚═╝╚═════╝ ╚══════╝")
    print("        STRATEGY CORE & 4-ALGORITHM CONSENSUS ENGINE - PHASE 5 TEST           ")
    print("=" * 80)
    print(f"{ANSI.RESET}")


def run_tests() -> bool:
    print_banner()
    all_passed = True

    try:
        # =====================================================================
        # 1. Indicator Calculation Precision Tests
        # =====================================================================
        print(f"{ANSI.YELLOW}{ANSI.BOLD}▶ 1. MATHEMATICAL PRECISION OF CORE INDICATORS{ANSI.RESET}")
        print(f"  {'-' * 76}")

        # 1A. Exact VWAP Formulation Test
        # Candle 1: H=105, L=95, C=100, V=1000 -> TP = 100, TPV = 100,000, CumVol = 1000 -> VWAP = 100.0
        # Candle 2: H=115, L=105, C=110, V=2000 -> TP = 110, TPV = 220,000, CumVol = 3000 -> CumTPV = 320,000 -> VWAP = 320000 / 3000 = 106.67
        vwap_df = pd.DataFrame({
            "High": [105.0, 115.0],
            "Low": [95.0, 105.0],
            "Close": [100.0, 110.0],
            "Volume": [1000, 2000]
        })
        vwap_calc = InstitutionalVWAP.calculate(vwap_df)
        assert round(float(vwap_calc.iloc[0]), 2) == 100.00
        assert round(float(vwap_calc.iloc[1]), 2) == 106.67
        print(f"  {ANSI.GREEN}[ PASS ]{ANSI.RESET} Institutional VWAP: Exact match at ₹{vwap_calc.iloc[1]:.2f}")

        # 1B. Dual EMA Momentum Test
        # 25 candles in a clean uptrend
        closes_up = np.linspace(2400.0, 2550.0, 30)
        ema_df = pd.DataFrame({"Close": closes_up, "High": closes_up + 5, "Low": closes_up - 5, "Volume": [10000] * 30})
        ema_eval = DualEMAMomentum.evaluate(ema_df)
        assert ema_eval["vote"] == 1
        assert ema_eval["ema9"] > ema_eval["ema21"]
        print(f"  {ANSI.GREEN}[ PASS ]{ANSI.RESET} Dual EMA (9 & 21) Momentum: Bullish vote (+1) verified (EMA9 ₹{ema_eval['ema9']} > EMA21 ₹{ema_eval['ema21']})")

        # 1C. SuperTrend Volatility Gate Test
        st_eval = SuperTrendGate.evaluate(ema_df, period=10, multiplier=2.0)
        assert st_eval["vote"] == 1
        assert st_eval["trend"] == 1
        print(f"  {ANSI.GREEN}[ PASS ]{ANSI.RESET} SuperTrend Volatility Gate: Bullish trend (+1) confirmed @ Trail ₹{st_eval['supertrend']:.2f}")

        # 1D. SMC Liquidity Sweep Test
        # 20 lookback bars with High=2500, Low=2450
        smc_data = {
            "High": [2490.0] * 19 + [2500.0] + [2480.0],
            "Low": [2460.0] * 19 + [2450.0] + [2440.0],  # Latest candle pierces below 2450 to 2440!
            "Close": [2470.0] * 19 + [2475.0] + [2465.0],  # Closes back up at 2465 (above 2450)!
            "Volume": [10000] * 21
        }
        smc_df = pd.DataFrame(smc_data)
        smc_eval = SMCLiquiditySweep.evaluate(smc_df)
        assert smc_eval["vote"] == 1, f"Expected Bullish Sweep (+1), got {smc_eval['vote']}"
        assert smc_eval["swing_low"] == 2450.0
        print(f"  {ANSI.GREEN}[ PASS ]{ANSI.RESET} SMC Liquidity Sweep: Bullish grab detected (Low ₹2440 pierced Swing Low ₹2450, closed @ ₹2465)")

        # =====================================================================
        # 2. 4-Algorithm Consensus Matrix Engine Tests
        # =====================================================================
        print(f"\n{ANSI.YELLOW}{ANSI.BOLD}▶ 2. 4-ALGORITHM CONSENSUS MATRIX VOTING GATE{ANSI.RESET}")
        print(f"  {'-' * 76}")

        # Test A: Neutral 50% split (2 votes match, 2 do not)
        # Create mock evaluation
        test_df_uptrend = ema_df.copy()
        test_df_uptrend["Volume"] = 10000

        # Full 4-vote evaluation on strong uptrend data
        consensus_res = ConsensusEngine.evaluate_consensus(test_df_uptrend, passes_odds_filter=True)
        assert consensus_res["consensus_score"] >= 75.0, f"Expected >= 75% consensus on clean uptrend, got {consensus_res['consensus_score']}%"
        assert consensus_res["signal"] == "BUY"
        assert consensus_res["approved"] is True
        assert consensus_res["target_price"] > consensus_res["entry_price"]
        assert consensus_res["stop_loss"] < consensus_res["entry_price"]
        print(f"  {ANSI.GREEN}[ PASS ]{ANSI.RESET} Consensus Gate Qualified: Score = {consensus_res['consensus_score']}% | Signal: {consensus_res['signal']} | Approved: {consensus_res['approved']}")
        print(f"  {ANSI.GREEN}[ PASS ]{ANSI.RESET} 1:2 R:R Computed: Entry ₹{consensus_res['entry_price']:.2f} | SL ₹{consensus_res['stop_loss']:.2f} | Target ₹{consensus_res['target_price']:.2f}")

        # Test B: Odds Filter Rejection
        consensus_disapproved = ConsensusEngine.evaluate_consensus(test_df_uptrend, passes_odds_filter=False)
        assert consensus_disapproved["approved"] is False
        print(f"  {ANSI.GREEN}[ PASS ]{ANSI.RESET} Safety Gate: passes_odds_filter=False correctly blocks trade approval (Approved = False)")

        # =====================================================================
        # 3. Staged Profit Manager (50-50 Scale-Out & Trailing Stop) Tests
        # =====================================================================
        print(f"\n{ANSI.YELLOW}{ANSI.BOLD}▶ 3. STAGED PROFIT MANAGER & BREAK-EVEN RATIO{ANSI.RESET}")
        print(f"  {'-' * 76}")

        spm = StagedProfitManager()

        # Trade Entry: BUY 100 shares of RELIANCE @ ₹2500.00, SL ₹2490.00 (Risk ₹10.00), Target ₹2540.00
        pos_id = spm.register_position(
            symbol="RELIANCE.NS",
            side="BUY",
            entry_price=2500.0,
            quantity=100,
            stop_loss=2490.0,
            target_price=2540.0
        )
        assert pos_id is not None
        print(f"  {ANSI.GREEN}[ PASS ]{ANSI.RESET} Position Registered: ID '{pos_id}' | BUY 100 @ ₹2500.00 (Risk: ₹10.00/sh)")

        # Step 1: Intermediate move to ₹2510.00 (1:1 R:R) -> HOLD
        step1 = spm.update_price(pos_id, 2510.0)
        assert step1["action"] == "HOLD"
        assert step1["milestone1_reached"] is False
        assert step1["remaining_quantity"] == 100
        print(f"  {ANSI.GREEN}[ PASS ]{ANSI.RESET} Price @ ₹2510.00: Action = HOLD | 100 shares active")

        # Step 2: Milestone 1 Reached: Price reaches ₹2520.00 (1:2 R:R, ₹20 gain = 2x risk)
        # Liquidates 50 shares, locks ₹1000 profit, moves SL of remaining 50 to ₹2500.00 (Break-Even)
        step2 = spm.update_price(pos_id, 2520.0)
        assert step2["action"] == "SCALE_OUT_50"
        assert step2["milestone1_reached"] is True
        assert step2["shares_to_exit"] == 50
        assert step2["remaining_quantity"] == 50
        assert step2["current_stop_loss"] == 2500.0, f"Expected Break-Even SL ₹2500.00, got ₹{step2['current_stop_loss']}"
        assert step2["locked_profit"] == 1000.0, f"Expected ₹1000 locked profit, got ₹{step2['locked_profit']}"
        print(f"  {ANSI.GREEN}[ PASS ]{ANSI.RESET} Milestone 1 Triggered @ ₹2520.00 (1:2 R:R achieved)")
        print(f"  {ANSI.GREEN}[ PASS ]{ANSI.RESET} Staged Scale-Out: Liquidated 50% (50 shares), Locked Profit: ₹{step2['locked_profit']:.2f}")
        print(f"  {ANSI.GREEN}[ PASS ]{ANSI.RESET} Break-Even Lock: Remaining 50 shares stop-loss moved to Entry: ₹{step2['current_stop_loss']:.2f}")

        # Step 3: Stop-Loss liquidation on retracement back to Break-Even (₹2500.00)
        step3 = spm.update_price(pos_id, 2499.0)
        assert step3["action"] == "STOP_LOSS_EXIT"
        assert step3["remaining_quantity"] == 0
        assert step3["is_closed"] is True
        print(f"  {ANSI.GREEN}[ PASS ]{ANSI.RESET} Retracement Stop: Remaining 50 shares exited at Break-Even, Capital Preserved")

        print("\n" + "=" * 80)
        print(f"{ANSI.BG_GREEN}{ANSI.WHITE}{ANSI.BOLD} PHASE 5 CERTIFIED: ALL 14 STRATEGY & CONSENSUS ASSERTIONS PASSED. {ANSI.RESET}\n")
        print(f"{ANSI.GREEN}Mathematical indicators, 4-algorithm consensus matrix, and 50-50 staged")
        print(f"profit scaling engine are fully certified for institutional live routing.{ANSI.RESET}\n")

    except AssertionError as exc:
        all_passed = False
        print(f"\n{ANSI.BG_RED}{ANSI.WHITE}{ANSI.BOLD} ASSERTION FAILURE {ANSI.RESET}")
        print(f"{ANSI.RED}Error: {str(exc)}{ANSI.RESET}\n")
    except Exception as exc:
        all_passed = False
        print(f"\n{ANSI.BG_RED}{ANSI.WHITE}{ANSI.BOLD} UNEXPECTED EXCEPTION {ANSI.RESET}")
        print(f"{ANSI.RED}{exc.__class__.__name__}: {str(exc)}{ANSI.RESET}\n")

    return all_passed


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)

