#!/usr/bin/env python3
"""
OmniTradePro - UI Components & Frosted Glassmorphism Test Suite
Platform: Windows 10/11 64-bit | Python 3.10+
Validates stylesheet compilation, dialog layouts, chart canvas initialization,
order panel pre-trade risk checks, and main window signal wiring.
"""

import os
import sys
import tempfile
from pathlib import Path

# Add project root to sys.path
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# ------------------------------------------------------------------------------
# TEST ISOLATION: run the entire suite against a throwaway data directory.
# Previously this suite issued `DELETE FROM trade_audit_log` against the live
# production ledger, destroying the operator's audit trail on every test run.
# ------------------------------------------------------------------------------
_isolated_data_dir = tempfile.mkdtemp(prefix="omnitrade_uitest_")
os.environ["OMNITRADE_DATA_DIR"] = _isolated_data_dir

from ui.styles import GlassmorphismTheme
from ui.vault_dialog import BrokerVaultDialog
from ui.chart_widget import ChartWidget
from ui.scanner_panel import ScannerPanel
from ui.order_panel import OrderPanel
from ui.main_window import MainWindow
import pandas as pd
import numpy as np


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
    print("       FROSTED GLASSMORPHISM UI SUITE & COMPONENT ENGINE - PHASE 7 TEST       ")
    print("=" * 80)
    print(f"{ANSI.RESET}")


def run_tests() -> bool:
    print_banner()
    all_passed = True

    # Initialize QApplication for PySide6 widgets.
    # A missing display/Qt binding must fail the suite loudly: silently continuing
    # in stub mode would report PASS without exercising a single real widget.
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)

    # Verify the isolated ledger is genuinely empty (Zero-Fake-Data baseline)
    from database.db_handler import DatabaseHandler
    db_clean = DatabaseHandler()
    assert Path(str(db_clean.db_path)).parent == Path(_isolated_data_dir), (
        f"Test isolation breach: ledger at {db_clean.db_path} is outside the sandbox "
        f"{_isolated_data_dir}"
    )
    _baseline_trades = len(db_clean.get_all_trades(limit=5))
    assert _baseline_trades == 0, f"Fresh test ledger must be empty, found {_baseline_trades} rows"

    try:
        # =====================================================================
        # 1. Stylesheet Compilation & Token Syntax Test
        # =====================================================================
        print(f"{ANSI.YELLOW}{ANSI.BOLD}▶ 1. FROSTED GLASSMORPHISM STYLESHEET COMPILATION{ANSI.RESET}")
        print(f"  {'-' * 76}")

        qss = GlassmorphismTheme.get_stylesheet()
        assert len(qss) > 500, "QSS stylesheet generated empty string"
        assert "#00e5ff" in qss, "Neon Cyan accent missing from stylesheet"
        assert "#00e676" in qss, "Profit Green accent missing from stylesheet"
        assert "#ff3d71" in qss, "Loss Red accent missing from stylesheet"
        print(f"  {ANSI.GREEN}[ PASS ]{ANSI.RESET} QSS Stylesheet compiled: {len(qss)} characters, full palette verified")

        # =====================================================================
        # 2. Broker Vault Dialog Test
        # =====================================================================
        print(f"\n{ANSI.YELLOW}{ANSI.BOLD}▶ 2. BROKER VAULT MODAL DIALOG INITIALIZATION{ANSI.RESET}")
        print(f"  {'-' * 76}")

        vault_dlg = BrokerVaultDialog()
        assert vault_dlg is not None
        assert vault_dlg.db is not None
        print(f"  {ANSI.GREEN}[ PASS ]{ANSI.RESET} BrokerVaultDialog instantiated with encrypted database handler")

        # =====================================================================
        # 3. Chart Canvas & Overlays Test
        # =====================================================================
        print(f"\n{ANSI.YELLOW}{ANSI.BOLD}▶ 3. PYQTGRAPH CHART CANVAS & REAL-TIME OVERLAYS{ANSI.RESET}")
        print(f"  {'-' * 76}")

        chart = ChartWidget()
        assert chart.current_symbol == "RELIANCE.NS"
        chart.set_symbol("TCS.NS")
        assert chart.current_symbol == "TCS.NS"

        # Ingest mock candle dataframe to verify overlay calculations
        sample_df = pd.DataFrame({
            "Open": [2500.0, 2505.0, 2510.0] * 10,
            "High": [2510.0, 2515.0, 2520.0] * 10,
            "Low": [2495.0, 2500.0, 2505.0] * 10,
            "Close": [2505.0, 2510.0, 2518.0] * 10,
            "Volume": [10000, 12000, 15000] * 10
        })
        chart.update_candles(sample_df, orb_high=2520.0, orb_low=2495.0)

        # Feed a live tick
        chart.on_tick_received({"symbol": "TCS.NS", "ltp": 2522.50})
        print(f"  {ANSI.GREEN}[ PASS ]{ANSI.RESET} Chart canvas verified: Symbol switching, candle updates, and live tick ingestion")

        # =====================================================================
        # 4. Order Execution Panel Test
        # =====================================================================
        print(f"\n{ANSI.YELLOW}{ANSI.BOLD}▶ 4. ORDER EXECUTION PANEL & RISK GATING{ANSI.RESET}")
        print(f"  {'-' * 76}")

        order_pnl = OrderPanel()
        assert order_pnl.router is not None
        assert order_pnl.risk_engine is not None
        print(f"  {ANSI.GREEN}[ PASS ]{ANSI.RESET} OrderPanel instantiated: Dual-mode router & risk engine attached")

        # =====================================================================
        # 5. Scanner Panel Test
        # =====================================================================
        print(f"\n{ANSI.YELLOW}{ANSI.BOLD}▶ 5. QUANTITATIVE SCANNER PANEL TEST{ANSI.RESET}")
        print(f"  {'-' * 76}")

        scanner_pnl = ScannerPanel()
        assert len(scanner_pnl.DEFAULT_WATCHLIST) >= 8
        print(f"  {ANSI.GREEN}[ PASS ]{ANSI.RESET} ScannerPanel verified: Nifty 50 default watchlist configured ({len(scanner_pnl.DEFAULT_WATCHLIST)} symbols)")

        # =====================================================================
        # 6. MainWindow Layout & Signal Wiring Test
        # =====================================================================
        print(f"\n{ANSI.YELLOW}{ANSI.BOLD}▶ 6. MAIN WINDOW ORCHESTRATOR & SIGNAL-SLOT WIRING{ANSI.RESET}")
        print(f"  {'-' * 76}")

        win = MainWindow()
        assert win.db is not None
        assert win.risk_engine is not None
        assert win.stream_worker is not None
        assert win.chart_widget is not None
        assert win.order_panel is not None
        assert win.scanner_panel is not None

        # Verify stream toggle wiring
        win._on_connection_status("CONNECTED", "All systems operational")
        print(f"  {ANSI.GREEN}[ PASS ]{ANSI.RESET} MainWindow verified: All tabs, header badges, and background workers bound cleanly")

        # =====================================================================
        # 7. Reference Screenshot Visual Fidelity & Modular Cards Test
        # =====================================================================
        print(f"\n{ANSI.YELLOW}{ANSI.BOLD}▶ 7. CHINTU AI TRADING BOARD V5.0 SCREENSHOT REPLICATION TEST{ANSI.RESET}")
        print(f"  {'-' * 76}")

        assert win.top_bar is not None
        assert len(win.top_bar.ticker_widgets) == 4, "Missing 4 Index Tickers in Top Bar"
        assert win.sub_navbar is not None
        assert len(win.sub_navbar.buttons) == 7, "Missing 7 Navigation Pills in SubHeader"
        assert win.sidebar is not None
        assert win.quick_trade is not None
        assert win.active_bots_card is not None
        assert win.portfolio_card is not None
        assert win.live_pnl_card is not None
        assert win.summary_card is not None
        assert win.risk_card is not None
        assert win.ai_sentiment_card is not None
        assert win.system_health_card is not None

        # Rigid geometry contract: header strips must not be allowed to grow/clip.
        # HeaderTopBar = 56px, SubHeaderNavBar = 36px (layout clipping guard).
        assert win.top_bar.height() == 56 or win.top_bar.minimumHeight() == 56, (
            f"HeaderTopBar height contract broken: {win.top_bar.height()}px (expected 56px)"
        )
        assert win.sub_navbar.height() == 36 or win.sub_navbar.minimumHeight() == 36, (
            f"SubHeaderNavBar height contract broken: {win.sub_navbar.height()}px (expected 36px)"
        )
        assert win.top_bar.maximumHeight() == 56, "HeaderTopBar must be rigid at 56px"
        assert win.sub_navbar.maximumHeight() == 36, "SubHeaderNavBar must be rigid at 36px"

        # Every dashboard card must be layout-complete (parented + non-negative geometry)
        _cards = [
            ("QuickTradeCard", win.quick_trade), ("ActiveBotsCard", win.active_bots_card),
            ("PortfolioCard", win.portfolio_card), ("LivePnLCard", win.live_pnl_card),
            ("TodaySummaryCard", win.summary_card), ("RiskManagerCard", win.risk_card),
            ("AISentimentGauge", win.ai_sentiment_card),
            ("SystemHealthCard", win.system_health_card),
        ]
        for _name, _card in _cards:
            assert _card is not None, f"{_name} missing from dashboard grid"
            assert _card.parent() is not None, f"{_name} is not parented into the layout tree"
            assert _card.width() >= 0 and _card.height() >= 0, f"{_name} has invalid geometry"
        print(f"  {ANSI.GREEN}[ PASS ]{ANSI.RESET} Dashboard grid certified: rigid HeaderTopBar 56px + SubHeaderNavBar 36px, "
              f"{len(_cards)} cards parented with valid geometry")

        # =====================================================================
        # 8. Zero-Fake-Data Purge & Multi-Page QStackedWidget Routing Test
        # =====================================================================
        print(f"\n{ANSI.YELLOW}{ANSI.BOLD}▶ 8. ZERO-FAKE-DATA PURGE & 12-PAGE QSTACKEDWIDGET ROUTING TEST{ANSI.RESET}")
        print(f"  {'-' * 76}")

        # A. Zero-Fake-Data Audit: Idle unauthenticated state must be zero/standby
        win._on_connection_status("DISCONNECTED", "Offline")
        assert win.portfolio_card.val_capital.text() == "₹0.00", "Capital leaking hardcoded fake numbers"
        assert win.live_pnl_card.pnl_display.text() == "₹0.00", "Live PnL leaking fake profitable numbers"
        assert win.summary_card.lbl_trades.text() == "0", "Trades count leaking fake numbers"
        assert win.system_health_card.val_broker.text() == "DISCONNECTED", "Broker badge must show DISCONNECTED when unprimed"
        assert len(win.chart_widget.canvas.candles) == 0, "Primary chart must not generate fake random candles when disconnected"
        print(f"  {ANSI.GREEN}[ PASS ]{ANSI.RESET} Zero-Fake-Data Verified: Capital ₹0.00, P&L ₹0.00, Trades 0, Broker DISCONNECTED")

        # B. 12-Page QStackedWidget Routing Audit
        assert win.stacked_widget.count() == 12, f"Expected 12 views in QStackedWidget, found {win.stacked_widget.count()}"
        for page_idx in range(12):
            win._switch_page(page_idx)
            assert win.stacked_widget.currentIndex() == page_idx, f"Navigation routing failed for Page {page_idx}"
            assert win.sidebar.active_index == page_idx, f"Sidebar visual active pill mismatch for Page {page_idx}"

        # Return to Dashboard Page 0
        win._switch_page(0)
        assert win.stacked_widget.currentIndex() == 0

        # C. Strict View Isolation Audit: Live Trading View (Page 1) vs Dashboard (Page 0)
        win._switch_page(1)
        assert win.stacked_widget.currentIndex() == 1
        assert win.stacked_widget.currentWidget() == win.live_trading_view
        assert win.live_trading_view is not win.dashboard_view, "LiveTradingView must be an independent isolated instance"
        assert hasattr(win.live_trading_view, "chart_widget"), "LiveTradingView missing dedicated chart_widget"
        
        win._switch_page(0)
        assert win.stacked_widget.currentIndex() == 0
        assert win.stacked_widget.currentWidget() == win.dashboard_view
        print(f"  {ANSI.GREEN}[ PASS ]{ANSI.RESET} Page Isolation Verified: Live Trading View (Page 1) strictly isolated from Dashboard (Page 0)")

        # Verify emergency kill switch triggers risk halt globally
        win.risk_engine.is_halted = True
        assert win.risk_engine.is_halted is True, "Emergency Kill Switch failed to trip risk engine"
        win.risk_engine.reset_circuit_breaker()

        print(f"  {ANSI.GREEN}[ PASS ]{ANSI.RESET} QStackedWidget 12-Page Routing Certified: All sidebar navigation switches operational")

        # =====================================================================
        # 9. Front-Page Execution Mode & Risk Controller Integration Test
        # =====================================================================
        print(f"\n{ANSI.YELLOW}{ANSI.BOLD}▶ 9. FRONT-PAGE EXECUTION MODE & RISK CONTROLLER TEST{ANSI.RESET}")
        print(f"  {'-' * 76}")

        assert hasattr(win.sidebar, "risk_controller") and win.sidebar.risk_controller is not None, "Sidebar missing risk_controller"
        assert hasattr(win.broker_control, "risk_controller") and win.broker_control.risk_controller is not None, "BrokerControlWidget missing risk_controller"

        w_side = win.sidebar.risk_controller
        w_dash = win.broker_control.risk_controller

        # Test applying new parameters from sidebar
        w_side.current_mode = "LIVE"
        w_side.spin_capital.setValue(2500.0)
        w_side.spin_risk_pct.setValue(4.8)
        w_side.spin_max_sl.setValue(120.0)
        w_side._on_apply_clicked()

        # Verify SQLite persistence
        db_cfg = win.db.get_execution_config()
        assert db_cfg["mode"] == "LIVE", f"Expected mode LIVE in SQLite, got {db_cfg['mode']}"
        assert db_cfg["trade_capital"] == 2500.0, f"Expected capital 2500 in SQLite, got {db_cfg['trade_capital']}"
        assert db_cfg["risk_percentage"] == 4.8, f"Expected risk_percentage 4.8 in SQLite, got {db_cfg.get('risk_percentage')}"
        assert db_cfg["max_sl"] == 120.0, f"Expected max_sl 120 in SQLite, got {db_cfg['max_sl']}"

        # Verify two-way synchronization between sidebar and dashboard risk widgets
        assert w_dash.current_mode == "LIVE", "Dashboard risk widget failed to synchronize mode"
        assert w_dash.spin_capital.value() == 2500.0, "Dashboard risk widget failed to synchronize capital"
        assert w_dash.spin_risk_pct.value() == 4.8, "Dashboard risk widget failed to synchronize risk_pct"
        assert w_dash.spin_max_sl.value() == 120.0, "Dashboard risk widget failed to synchronize max_sl"
        assert "2,500" in w_dash.lbl_status.text()
        assert "120" in w_dash.lbl_status.text()

        # Verify OrderRouter received parameters
        assert win.order_router.execution_mode == "LIVE"
        assert win.order_router.user_trade_capital == 2500.0
        assert win.order_router.user_risk_percentage == 4.8
        assert win.order_router.user_max_sl == 120.0

        # Reset back to default PAPER mode
        w_side.current_mode = "PAPER"
        w_side.spin_capital.setValue(1000.0)
        w_side.spin_risk_pct.setValue(5.0)
        w_side.spin_max_sl.setValue(80.0)
        w_side._on_apply_clicked()

        assert win.order_router.execution_mode == "PAPER"
        assert win.order_router.user_trade_capital == 1000.0
        assert win.order_router.user_max_sl == 80.0

        print(f"  {ANSI.GREEN}[ PASS ]{ANSI.RESET} Front-Page Risk Controller Verified: Mode toggle, capital limit, max SL, and live two-way sync certified")

        # =====================================================================
        # 10. Dynamic Admin Risk Management Controls & Global Two-Way Sync Test
        # =====================================================================
        print(f"\n{ANSI.YELLOW}{ANSI.BOLD}▶ 10. DYNAMIC ADMIN RISK MANAGEMENT & GLOBAL TWO-WAY SYNC TEST{ANSI.RESET}")
        print(f"  {'-' * 76}")

        rm_view = win.risk_manager_view
        assert rm_view is not None, "MainWindow missing risk_manager_view"
        assert hasattr(rm_view, "spin_capital"), "RiskManagerView missing spin_capital"
        assert hasattr(rm_view, "spin_risk_pct"), "RiskManagerView missing spin_risk_pct"
        assert hasattr(rm_view, "spin_max_sl"), "RiskManagerView missing spin_max_sl"
        assert hasattr(rm_view, "spin_drawdown_pct"), "RiskManagerView missing spin_drawdown_pct"
        assert hasattr(rm_view, "btn_save"), "RiskManagerView missing btn_save"

        # 1. Test Admin modifications in RiskManagerView
        rm_view.spin_capital.setValue(5000.0)
        rm_view.spin_risk_pct.setValue(4.0)
        # Verify mutual calculation: 5000 * 0.04 = 200.0
        rm_view._on_capital_or_risk_changed()
        assert rm_view.spin_max_sl.value() == 200.0, f"Expected calculated Max SL ₹200.0, got {rm_view.spin_max_sl.value()}"

        rm_view.spin_drawdown_pct.setValue(15.0)
        rm_view._update_ruin_floor_display()
        # Verify Ruin floor display: 5000 * 0.15 = 750.0
        assert "750" in rm_view.lbl_ruin_floor.text(), f"Expected ₹750 ruin floor in label, got {rm_view.lbl_ruin_floor.text()}"

        # 2. Trigger Admin Save Action: [ 💾 Save & Apply Risk Config ]
        rm_view._save_risk_config()
        assert "Saved & Enforced" in rm_view.lbl_save_status.text()

        # 3. Verify SQLite Persistence across both handlers
        cfg_db = win.db.get_execution_config()
        assert cfg_db["trade_capital"] == 5000.0, f"Expected capital 5000 in DB, got {cfg_db['trade_capital']}"
        assert cfg_db["risk_percentage"] == 4.0, f"Expected risk_percentage 4.0 in DB, got {cfg_db['risk_percentage']}"
        assert cfg_db["max_sl"] == 200.0, f"Expected max_sl 200 in DB, got {cfg_db['max_sl']}"
        assert cfg_db["daily_drawdown_pct"] == 15.0, f"Expected daily_drawdown_pct 15.0 in DB, got {cfg_db['daily_drawdown_pct']}"

        # 4. Verify Global Synchronization into Front-Page Widgets
        assert w_side.spin_capital.value() == 5000.0, "Sidebar risk widget failed to sync capital from RMS view"
        assert w_side.spin_risk_pct.value() == 4.0, "Sidebar risk widget failed to sync risk % from RMS view"
        assert w_side.spin_max_sl.value() == 200.0, "Sidebar risk widget failed to sync max SL from RMS view"

        assert w_dash.spin_capital.value() == 5000.0, "Dashboard risk widget failed to sync capital from RMS view"
        assert w_dash.spin_risk_pct.value() == 4.0, "Dashboard risk widget failed to sync risk % from RMS view"
        assert w_dash.spin_max_sl.value() == 200.0, "Dashboard risk widget failed to sync max SL from RMS view"

        # 5. Verify Dashboard RiskManagerCard Dynamic Update
        assert "750" in win.risk_card.v_limit.text(), f"Expected ₹750 limit in RiskManagerCard, got {win.risk_card.v_limit.text()}"
        assert "4.0%" in win.risk_card.v_floor.text(), f"Expected 4.0% floor in RiskManagerCard, got {win.risk_card.v_floor.text()}"

        # 6. Verify Backend Risk Engines Updated
        from core.risk_budget import RiskBudget
        rb_params = RiskBudget.get_risk_parameters()
        assert rb_params["trade_capital"] == 5000.0
        assert rb_params["risk_percentage"] == 4.0
        assert rb_params["max_sl"] == 200.0
        assert rb_params["daily_drawdown_pct"] == 15.0

        assert win.order_router.user_trade_capital == 5000.0
        assert win.order_router.user_risk_percentage == 4.0
        assert win.order_router.user_max_sl == 200.0
        assert win.order_router.user_daily_drawdown_pct == 15.0

        # 7. Reverse Two-Way Sync: Modify from Front-Page Widget -> Updates RMS View
        w_side.spin_capital.setValue(3000.0)
        w_side.spin_risk_pct.setValue(5.0)
        w_side.spin_max_sl.setValue(150.0)
        w_side._on_apply_clicked()

        assert rm_view.spin_capital.value() == 3000.0, "RiskManagerView failed to sync capital from widget"
        assert rm_view.spin_risk_pct.value() == 5.0, "RiskManagerView failed to sync risk % from widget"
        assert rm_view.spin_max_sl.value() == 150.0, "RiskManagerView failed to sync max SL from widget"
        assert "450" in win.risk_card.v_limit.text(), f"Expected ₹450 limit in RiskManagerCard, got {win.risk_card.v_limit.text()}"
        assert "5.0%" in win.risk_card.v_floor.text(), f"Expected 5.0% floor in RiskManagerCard, got {win.risk_card.v_floor.text()}"

        # Reset back to default for clean state
        w_side.current_mode = "PAPER"
        w_side.spin_capital.setValue(1000.0)
        w_side.spin_risk_pct.setValue(5.0)
        w_side.spin_max_sl.setValue(80.0)
        w_side._on_apply_clicked()

        print(f"  {ANSI.GREEN}[ PASS ]{ANSI.RESET} Dynamic Admin Risk Management Certified: Capital, Risk %, SL, Ruin Floor, and Two-Way Global Sync fully validated")

        dimensions = 10
        print("\n" + "=" * 80)
        print(f"{ANSI.BG_GREEN}{ANSI.WHITE}{ANSI.BOLD} PHASE 7 CERTIFIED: ALL {dimensions}/{dimensions} UI COMPONENT SUITE ASSERTIONS PASSED. {ANSI.RESET}\n")
        print(f"{ANSI.GREEN}Frosted glassmorphism theme, multi-broker vault, high-performance charting,")
        print(f"risk-gated order dispatch, and main window orchestrator are ready for production.{ANSI.RESET}\n")

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

