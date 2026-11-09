#!/usr/bin/env python3
"""
OmniTradePro - Phase 6 Execution & Capital Routing Test Suite
Platform: Windows 10/11 64-bit | Python 3.10+
Validates autonomous capital routing across sessions, position sizing against 10% risk,
strict ₹70 gross profit hurdle with ₹60 friction, paper slippage, and 15:15 auto square-off.
"""

import sys
import tempfile
from pathlib import Path

# Add project root to sys.path
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from database.db_handler import DatabaseHandler
from core.capital_allocator import CapitalAllocator
from core.risk_budget import RiskBudget
from core.order_router import OrderRouter


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
    print("         CAPITAL ROUTING, RISK BUDGET & ORDER ROUTER - PHASE 6 TEST           ")
    print("=" * 80)
    print(f"{ANSI.RESET}")


def run_tests() -> bool:
    print_banner()
    all_passed = True
    test_dir = tempfile.TemporaryDirectory()

    try:
        # Isolated test database
        test_db_path = Path(test_dir.name) / "test_phase6.db"
        test_key_path = Path(test_dir.name) / ".test_phase6.key"
        
        # Reset singleton to test instance
        DatabaseHandler._instance = None
        db = DatabaseHandler(db_path=str(test_db_path), key_path=str(test_key_path))

        # =====================================================================
        # 1. Capital Allocator & Multi-Session Routing Test
        # =====================================================================
        print(f"{ANSI.YELLOW}{ANSI.BOLD}▶ 1. AUTONOMOUS CAPITAL ALLOCATION & MULTI-SESSION ROUTING{ANSI.RESET}")
        print(f"  {'-' * 76}")

        # Test A: ₹1,000 Capital (Tier 1) at 10:30 IST -> Equity Cash
        alloc_small = CapitalAllocator.allocate_asset(capital_inr=1000.0, current_time="10:30")
        assert alloc_small["market_session"] == "EQUITY"
        assert alloc_small["max_segment_risk_inr"] == 100.0, f"Expected 100.0, got {alloc_small['max_segment_risk_inr']}"
        assert alloc_small["primary_symbol"] == "TATASTEEL"
        assert alloc_small["broker_routing_preference"] == "SHOONYA"
        print(f"  {ANSI.GREEN}[ PASS ]{ANSI.RESET} Capital ₹1,000 routed: EQUITY Session | Primary: TATASTEEL | Max Risk: ₹100.00 | Broker: SHOONYA")

        # Test B: ₹10,000 Capital (Tier 3) at 18:00 IST -> MCX Commodities
        alloc_mcx = CapitalAllocator.allocate_asset(capital_inr=10000.0, current_time="18:00")
        assert alloc_mcx["market_session"] == "MCX"
        assert alloc_mcx["max_segment_risk_inr"] == 1000.0, f"Expected 1000.0, got {alloc_mcx['max_segment_risk_inr']}"
        assert alloc_mcx["primary_symbol"] == "CRUDEOIL"
        assert alloc_mcx["broker_routing_preference"] == "ANGEL_ONE"
        print(f"  {ANSI.GREEN}[ PASS ]{ANSI.RESET} Capital ₹10,000 @ 18:00 IST: MCX Session | Primary: CRUDEOIL | Max Risk: ₹1,000.00 | Broker: ANGEL_ONE")

        # =====================================================================
        # 2. Mathematical Risk Budget & ₹70 Gross Profit Hurdle
        # =====================================================================
        print(f"\n{ANSI.YELLOW}{ANSI.BOLD}▶ 2. RISK BUDGETING & MANDATORY ₹70 GROSS PROFIT HURDLE{ANSI.RESET}")
        print(f"  {'-' * 76}")

        # Setup A: Capital ₹500, Entry ₹100, SL ₹95 (Risk ₹5), Target ₹108 (Reward ₹8)
        # Max Risk = 500 * 0.10 = ₹50.0 -> Quantity = 50 / 5 = 10 shares
        # Gross Profit = 10 * 8 = ₹80.0 >= ₹70.0 hurdle! Net Profit = 80 - 60 = ₹20.0 >= ₹10.0!
        # The 10% ceiling is asserted explicitly: calculate_position_size otherwise
        # reads RiskBudget's process-global user risk percentage (default 5%), which
        # makes this test order-dependent on whatever ran earlier in the process.
        budget_pass = RiskBudget.calculate_position_size(
            capital_inr=500.0,
            entry_price=100.0,
            stop_loss=95.0,
            target_price=108.0,
            risk_ratio=0.10
        )
        assert budget_pass["quantity"] == 10
        assert budget_pass["gross_profit_expected"] == 80.0
        assert budget_pass["friction_buffer"] == 60.0
        assert budget_pass["net_profit_expected"] == 20.0
        assert budget_pass["can_execute"] is True
        print(f"  {ANSI.GREEN}[ PASS ]{ANSI.RESET} Hurdle Passed: Gross ₹{budget_pass['gross_profit_expected']:.2f} >= ₹70.0 | Net ₹{budget_pass['net_profit_expected']:.2f} | can_execute = True")

        # Setup B: Capital ₹500, Target ₹105 (Reward ₹5) -> Gross = 10 * 5 = ₹50.0 < ₹70.0 hurdle!
        # Net Profit = 50 - 60 = -₹10.0 < ₹10.0 -> REJECTED
        budget_fail = RiskBudget.calculate_position_size(
            capital_inr=500.0,
            entry_price=100.0,
            stop_loss=95.0,
            target_price=105.0,
            risk_ratio=0.10
        )
        assert budget_fail["gross_profit_expected"] == 50.0
        assert budget_fail["net_profit_expected"] == -10.0
        assert budget_fail["can_execute"] is False
        print(f"  {ANSI.GREEN}[ PASS ]{ANSI.RESET} Hurdle Blocked: Gross ₹{budget_fail['gross_profit_expected']:.2f} < ₹70.0 | Net ₹{budget_fail['net_profit_expected']:.2f} | can_execute = False")

        # Verify 10% risk ceiling compliance
        assert budget_pass["max_risk_inr"] <= 500.0 * 0.10
        print(f"  {ANSI.GREEN}[ PASS ]{ANSI.RESET} 10% Risk Ceiling: Max Risk (₹{budget_pass['max_risk_inr']:.2f}) <= 10% of Capital")

        # =====================================================================
        # 3. Dual-Mode Order Router & Auto Square-Off
        # =====================================================================
        print(f"\n{ANSI.YELLOW}{ANSI.BOLD}▶ 3. ORDER ROUTER (PAPER SLIPPAGE & 15:15 AUTO SQUARE-OFF){ANSI.RESET}")
        print(f"  {'-' * 76}")

        router = OrderRouter(db_handler=db)

        # Fund the scenario explicitly: the router now enforces the operator's
        # capital/risk ceiling by default, so a 10-share RELIANCE ticket must be
        # backed by an account envelope rather than an implicit bypass.
        router.update_risk_parameters(
            mode="PAPER", trade_capital=100_000.0, max_sl=500.0,
            risk_percentage=5.0, daily_drawdown_pct=10.0, enforce=True
        )

        # 3A. Open Paper Position with 0.02% slippage
        # Price ₹2500 -> executed_price = 2500 * 1.0002 = 2500.50
        order_fill = router.execute_order(
            symbol="RELIANCE.NS",
            side="BUY",
            quantity=10,
            price=2500.0,
            stop_loss=2480.0,
            target_price=2540.0,
            mode="PAPER"
        )
        assert order_fill["status"] == "FILLED"
        assert order_fill["executed_price"] == 2500.50
        assert order_fill["trade_id"] > 0
        print(f"  {ANSI.GREEN}[ PASS ]{ANSI.RESET} Paper Order Executed: BUY 10 RELIANCE.NS @ ₹{order_fill['executed_price']:.2f} (0.02% Slippage: +₹{order_fill['slippage_inr']:.2f})")

        # 3B. Close Position at ₹2510.50 (+₹10 gain per share)
        # Gross = (2510.50 - 2500.50) * 10 = ₹100.00
        # Friction = -₹60.00 -> Net PnL = ₹40.00
        closed_res = router.close_position(trade_id=order_fill["trade_id"], exit_price=2510.50)
        assert closed_res["gross_pnl"] == 100.0
        assert closed_res["friction_cost"] == 60.0
        assert closed_res["net_pnl"] == 40.0
        assert closed_res["status"] == "CLOSED"
        print(f"  {ANSI.GREEN}[ PASS ]{ANSI.RESET} Position Closed: Gross P&L ₹{closed_res['gross_pnl']:.2f} - Friction ₹{closed_res['friction_cost']:.2f} = Net P&L ₹{closed_res['net_pnl']:.2f}")

        # 3C. Auto Square-Off at 15:15 IST
        # Open an intraday position
        order_intraday = router.execute_order(
            symbol="TCS.NS",
            side="BUY",
            quantity=5,
            price=3500.0,
            stop_loss=3450.0,
            target_price=3600.0,
            mode="PAPER"
        )
        assert len(router.get_open_positions()) == 1

        # Trigger auto square-off at 15:15 IST
        liquidated = router.evaluate_auto_square_off(current_time="15:15")
        assert len(liquidated) == 1
        assert liquidated[0]["id"] == order_intraday["trade_id"]
        assert liquidated[0]["status"] == "CLOSED"
        assert len(router.get_open_positions()) == 0
        print(f"  {ANSI.GREEN}[ PASS ]{ANSI.RESET} Mandatory 15:15 IST Square-Off: Liquidated 1 open intraday position, 0 lingering positions")

        print("\n" + "=" * 80)
        print(f"{ANSI.BG_GREEN}{ANSI.WHITE}{ANSI.BOLD} PHASE 6 CERTIFIED: ALL 13 EXECUTION & ROUTING ASSERTIONS PASSED. {ANSI.RESET}\n")
        print(f"{ANSI.GREEN}Capital tier allocation, 10% risk floor, ₹70 fee hurdle gate, 0.02% slippage,")
        print(f"and 15:15 IST multi-session liquidation are fully operational for production.{ANSI.RESET}\n")

    except AssertionError as exc:
        all_passed = False
        print(f"\n{ANSI.BG_RED}{ANSI.WHITE}{ANSI.BOLD} ASSERTION FAILURE {ANSI.RESET}")
        print(f"{ANSI.RED}Error: {str(exc)}{ANSI.RESET}\n")
    except Exception as exc:
        all_passed = False
        print(f"\n{ANSI.BG_RED}{ANSI.WHITE}{ANSI.BOLD} UNEXPECTED EXCEPTION {ANSI.RESET}")
        print(f"{ANSI.RED}{exc.__class__.__name__}: {str(exc)}{ANSI.RESET}\n")
    finally:
        db.close()
        test_dir.cleanup()

    return all_passed


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)

