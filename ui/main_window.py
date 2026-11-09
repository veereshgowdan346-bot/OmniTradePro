#!/usr/bin/env python3
"""
OmniTradePro / Chintu AI Trading Board v5.0 - Institutional Main Window Orchestrator
Platform: Windows 10/11 64-bit | Python 3.10+
Implements complete QStackedWidget multi-page architecture with 12 working views:
Page 0: DashboardView (Command board from reference screenshot, zero-fake compliant)
Page 1: LiveTradingView (Full chart canvas, DOM depth, fast buy/sell ladder)
Page 2: TradingBotsView (Consensus engine, bot weights, status controls)
Page 3: StrategiesView (SMC, VWAP, Dual EMA, SuperTrend parameters)
Page 4: MarketWatchView (Nifty 50 and MCX watchlist table)
Page 5: AutoTradeView (Autonomous switches, ₹70 profit hurdle gates)
Page 6: BacktestView (10,000-replay Monte Carlo Time Machine interface)
Page 7: AnalyticsView (P&L distribution, drawdown telemetry, Sharpe ratio)
Page 8: PortfolioView (Multi-tier capital routing, margin breakdown, open positions)
Page 9: RiskManagerView (RMS controls, ₹2,000 halt limit, circuit reset)
Page 10: ReportsView (Interactive SQLite trade_audit_log ledger with ₹60 fee audit)
Page 11: SettingsView (Embedded AES-256 Broker Vault & dynamic 2FA configuration)
"""

import threading
from datetime import datetime, timezone
import os
from typing import Optional, Dict, Any

try:
    from PySide6.QtWidgets import (
        QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QScrollArea,
        QStackedWidget, QMessageBox, QFrame, QSizePolicy
    )
    from PySide6.QtCore import Qt, QTimer
except ImportError:
    class QMainWindow:
        def __init__(self, parent=None): pass
        def setWindowTitle(self, t): pass
        def resize(self, w, h): pass
        def setMinimumSize(self, w, h): pass
        def setCentralWidget(self, w): pass
        def show(self): pass
    class QWidget:
        def __init__(self, parent=None): pass
        def setStyleSheet(self, s): pass
        def setFixedSize(self, w, h): pass
        def setFixedWidth(self, w): pass
        def setFixedHeight(self, h): pass
    class QFrame(QWidget):
        NoFrame = 0
        def setFrameShape(self, s): pass
    class QVBoxLayout:
        def __init__(self, *args): pass
        def addWidget(self, w, *args): pass
        def addLayout(self, l, *args): pass
        def addStretch(self, *args): pass
        def addSpacing(self, *args): pass
        def setContentsMargins(self, *args): pass
        def setSpacing(self, s): pass
    class QHBoxLayout(QVBoxLayout): pass
    class QScrollArea:
        def __init__(self, parent=None): pass
        def setWidgetResizable(self, b): pass
        def setWidget(self, w): pass
        def setFrameShape(self, s): pass
        def setStyleSheet(self, s): pass
    class QStackedWidget:
        def __init__(self, parent=None):
            self._widgets = []
            self._current_index = 0
        def addWidget(self, w, *args):
            self._widgets.append(w)
        def setCurrentIndex(self, i):
            self._current_index = i
        def currentIndex(self):
            return self._current_index
        def count(self):
            return len(self._widgets)
        def currentWidget(self):
            return self._widgets[self._current_index] if 0 <= self._current_index < len(self._widgets) else None
        def widget(self, i):
            return self._widgets[i] if 0 <= i < len(self._widgets) else None
    class QMessageBox:
        @staticmethod
        def warning(p, t, m): pass
        @staticmethod
        def information(p, t, m): pass
    class QTimer:
        def __init__(self, parent=None): pass
        def timeout(self): pass
        def start(self, ms): pass
    class Qt:
        Horizontal = 1
        NoFrame = 0

from ui.styles import GlassmorphismTheme
from ui.dashboard import (
    HeaderTopBar, SubHeaderNavBar, LeftSidebar, QuickTradeCard,
    ActiveBotsCard, PortfolioCard, LivePnLCard, TodaySummaryCard,
    RiskManagerCard, AISentimentGauge, SystemHealthCard
)
from ui.chart_widget import ChartWidget
from ui.views import (
    LiveTradingView, TradingBotsView, StrategiesView, MarketWatchView,
    AutoTradeView, BacktestView, AnalyticsView, PortfolioView,
    RiskManagerView, ReportsView, SettingsView, StrategyConsensusView
)
from ui.scanner_panel import ScannerPanel
from ui.broker_control_widget import BrokerControlWidget
from database.db_handler import DatabaseHandler
from core.risk_engine import RiskEngine
from core.order_router import OrderRouter
from core.risk_budget import RiskBudget
from core.consensus import ConsensusEngine
from brokers.stream_worker import BrokerStreamWorker


class DashboardView(QScrollArea):
    """
    Page 0: The primary command board matching the screenshot,
    encapsulated in a responsive scroll area and wired to real zero/live state.
    """

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.NoFrame)
        self.setStyleSheet("background: transparent; border: none;")

        self.container = QWidget()
        self.container.setStyleSheet(f"background-color: #080b10;")
        self.layout_canvas = QVBoxLayout(self.container)
        self.layout_canvas.setContentsMargins(10, 8, 10, 10)
        self.layout_canvas.setSpacing(10)

        # TIER 1: Upper Row (Chart Canvas 72% + Quick Trade 28%)
        # setContentsMargins(0,0,0,0) + setSpacing(0) on tier1 to anchor the
        # chart container rigidly — no vertical displacement from price updates.
        tier1_layout = QHBoxLayout()
        tier1_layout.setSpacing(10)
        tier1_layout.setContentsMargins(0, 0, 0, 0)

        self.chart_widget = ChartWidget(self.container)
        self.quick_trade = QuickTradeCard(self.container)

        tier1_layout.addWidget(self.chart_widget, 72)
        tier1_layout.addWidget(self.quick_trade, 28)
        self.layout_canvas.addLayout(tier1_layout, 1)

        # INTERACTIVE BROKER MATRIX: 3 Dedicated Cards (Angel One, Shoonya, Groww)
        self.broker_control = BrokerControlWidget(parent=self.container)
        self.layout_canvas.addWidget(self.broker_control)

        # TIER 2: Middle Row (Active Bots 48% + Portfolio 26% + Live P&L 26%)
        tier2_layout = QHBoxLayout()
        tier2_layout.setSpacing(10)

        self.active_bots_card = ActiveBotsCard(self.container)
        self.portfolio_card = PortfolioCard(self.container)
        self.live_pnl_card = LivePnLCard(self.container)

        tier2_layout.addWidget(self.active_bots_card, 48)
        tier2_layout.addWidget(self.portfolio_card, 26)
        tier2_layout.addWidget(self.live_pnl_card, 26)
        self.layout_canvas.addLayout(tier2_layout)

        # TIER 3: Bottom Row (Today's Summary + Risk RMS + AI Sentiment + System Health)
        tier3_layout = QHBoxLayout()
        tier3_layout.setSpacing(10)

        self.summary_card = TodaySummaryCard(self.container)
        self.risk_card = RiskManagerCard(self.container)
        self.ai_sentiment_card = AISentimentGauge(self.container)
        self.system_health_card = SystemHealthCard(self.container)

        tier3_layout.addWidget(self.summary_card, 25)
        tier3_layout.addWidget(self.risk_card, 25)
        tier3_layout.addWidget(self.ai_sentiment_card, 25)
        tier3_layout.addWidget(self.system_health_card, 25)
        self.layout_canvas.addLayout(tier3_layout)

        self.setWidget(self.container)


class MainWindow(QMainWindow):
    """
    Central orchestrator with working QStackedWidget multi-page navigation across 12 views.
    Preserves frosted glassmorphism standards, full-screen/half-screen elasticity,
    and global top-bar emergency kill switch.
    """

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("OmniTradePro — Institutional Trading Platform")
        self.resize(1380, 860)
        self.setMinimumSize(960, 620)

        # Core Backend Subsystems
        self.db = DatabaseHandler()
        self.risk_engine = RiskEngine()
        self.order_router = OrderRouter()
        self.stream_worker = BrokerStreamWorker()

        self._init_ui()
        self._init_telemetry_timer()
        self._wire_signals()
        self._refresh_real_database_metrics()

    def _init_ui(self) -> None:
        central = QWidget(self)
        central.setStyleSheet(f"background-color: {GlassmorphismTheme.BG_CANVAS};")
        self.setCentralWidget(central)

        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # 1. Top Header Bar (Global across all 12 views)
        self.top_bar = HeaderTopBar(self)
        root_layout.addWidget(self.top_bar)

        # 2. Sub-Header Navigation Pills ([Chart], [Trade], [Positions], [Orders], [Bots], [Analytics], [Reports])
        self.sub_navbar = SubHeaderNavBar(self)
        root_layout.addWidget(self.sub_navbar)

        # 3. Main Body Split: Left Sidebar + QStackedWidget
        body_layout = QHBoxLayout()
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(0)

        # Left Sidebar (12 navigation buttons, robot mascot, '● System Online')
        self.sidebar = LeftSidebar(self)
        body_layout.addWidget(self.sidebar)

        # Central Multi-Page Stack
        self.stacked_widget = QStackedWidget(self)

        # Instantiate all 12 views
        self.dashboard_view = DashboardView(self)                 # Page 0
        self.live_trading_view = LiveTradingView(self)             # Page 1
        self.trading_bots_view = TradingBotsView(self)             # Page 2
        self.strategies_view = StrategiesView(self)                 # Page 3
        self.market_watch_view = MarketWatchView(self)             # Page 4
        self.auto_trade_view = AutoTradeView(self)                 # Page 5
        self.backtest_view = BacktestView(self)                     # Page 6
        self.analytics_view = AnalyticsView(self)                   # Page 7
        self.portfolio_view = PortfolioView(self)                   # Page 8
        self.risk_manager_view = RiskManagerView(self)             # Page 9
        self.reports_view = ReportsView(self)                       # Page 10
        self.settings_view = SettingsView(self)                     # Page 11

        # Convenience references for backwards compatibility & tests
        self.chart_widget = self.dashboard_view.chart_widget

        # Real-data provider registration (no network call happens here). The
        # canvas only fetches once a genuine live tick proves the feed is up.
        try:
            self.chart_widget.set_history_provider(self._fetch_history_backfill)
        except Exception:
            pass
        self._backfill_started = False
        self.quick_trade = self.dashboard_view.quick_trade
        self.order_panel = self.dashboard_view.quick_trade
        self.broker_control = self.dashboard_view.broker_control
        self.active_bots_card = self.dashboard_view.active_bots_card
        self.portfolio_card = self.dashboard_view.portfolio_card
        self.live_pnl_card = self.dashboard_view.live_pnl_card
        self.summary_card = self.dashboard_view.summary_card
        self.risk_card = self.dashboard_view.risk_card
        self.ai_sentiment_card = self.dashboard_view.ai_sentiment_card
        self.system_health_card = self.dashboard_view.system_health_card
        self.scanner_panel = ScannerPanel(self)

        # Mount the scanner grid inside the Live Market Watch page (page 4) so
        # it is actually reachable — previously it was instantiated but never
        # added to any layout.
        try:
            self.market_watch_view.layout_main.addWidget(self.scanner_panel)
        except Exception:
            pass

        # The Live Trading View owns a second chart: same real-data provider, no
        # synthetic seeding, same backfill pipeline.
        try:
            self.live_trading_view.chart.set_history_provider(self._fetch_history_backfill)
        except Exception:
            pass

        # Mount the 4-engine consensus matrix into the Strategies page (page 3)
        # so the "🧠 Strategy Consensus" tab lands on a real quorum/GBM meter —
        # previously StrategyConsensusView was defined but never instantiated.
        self.consensus_view = None
        try:
            self.consensus_view = StrategyConsensusView(self.strategies_view)
            # Nested inside a QScrollArea already: avoid a second scrollbar.
            for _policy in ("setVerticalScrollBarPolicy", "setHorizontalScrollBarPolicy"):
                try:
                    getattr(self.consensus_view, _policy)(Qt.ScrollBarAlwaysOff)
                except Exception:
                    pass
            self.strategies_view.layout_main.addWidget(self.consensus_view)
        except Exception:
            self.consensus_view = None

        # Add all 12 pages to stack
        self.stacked_widget.addWidget(self.dashboard_view)          # 0
        self.stacked_widget.addWidget(self.live_trading_view)      # 1
        self.stacked_widget.addWidget(self.trading_bots_view)      # 2
        self.stacked_widget.addWidget(self.strategies_view)        # 3
        self.stacked_widget.addWidget(self.market_watch_view)      # 4
        self.stacked_widget.addWidget(self.auto_trade_view)        # 5
        self.stacked_widget.addWidget(self.backtest_view)          # 6
        self.stacked_widget.addWidget(self.analytics_view)         # 7
        self.stacked_widget.addWidget(self.portfolio_view)          # 8
        self.stacked_widget.addWidget(self.risk_manager_view)      # 9
        self.stacked_widget.addWidget(self.reports_view)           # 10
        self.stacked_widget.addWidget(self.settings_view)          # 11

        body_layout.addWidget(self.stacked_widget, 1)
        root_layout.addLayout(body_layout, 1)

    def _wire_signals(self) -> None:
        """Wires working navigation routes, broker stream hooks, and order dispatchers."""
        try:
            # 1. Sidebar 12-page navigation routing
            self.sidebar.nav_changed.connect(self._switch_page)

            # 2. Sub-Navbar pills route to corresponding views
            self.sub_navbar.nav_selected.connect(self._switch_page)

            # 3. Settings gear on top bar routes to SettingsView (Page 11)
            self.top_bar.btn_settings.clicked.connect(lambda: self._switch_page(11))

            # 3b. Scanner / Market-Watch row clicks sync the primary chart
            for _src in ("scanner_panel", "market_watch_view"):
                obj = getattr(self, _src, None)
                if obj is not None and hasattr(obj, "symbol_selected"):
                    try:
                        obj.symbol_selected.connect(self._on_symbol_sync)
                    except Exception:
                        pass

            # 3b2. Top-bar index pills -> global instrument selection
            if hasattr(self.top_bar, "ticker_clicked"):
                try:
                    self.top_bar.ticker_clicked.connect(self._on_pill_selected)
                except Exception:
                    pass

            # 3b3. Live Trading View: symbol requests + fast-ladder dispatch
            if hasattr(self.live_trading_view, "symbol_selected"):
                try:
                    self.live_trading_view.symbol_selected.connect(self._on_symbol_sync)
                except Exception:
                    pass
            if hasattr(self.live_trading_view, "order_requested"):
                try:
                    self.live_trading_view.order_requested.connect(self._on_fast_order)
                except Exception:
                    pass

            # 3b4. Authentic history -> 4-engine consensus / quorum / GBM telemetry
            if hasattr(self.chart_widget, "backfill_loaded") and self.consensus_view is not None:
                try:
                    self.chart_widget.backfill_loaded.connect(self._on_history_loaded)
                except Exception:
                    pass
            if hasattr(self.live_trading_view.chart, "backfill_loaded") and self.consensus_view is not None:
                try:
                    self.live_trading_view.chart.backfill_loaded.connect(self._on_history_loaded)
                except Exception:
                    pass

            # 3c. Portfolio 1-click square-off -> live router close at real LTP
            if hasattr(self.portfolio_view, "square_off_requested"):
                try:
                    self.portfolio_view.square_off_requested.connect(self._on_square_off_position)
                except Exception:
                    pass

            # 4. Emergency Kill Switch (Global across all 12 views)
            self.top_bar.kill_switch_triggered.connect(self._on_emergency_kill_switch)

            # 5. Quick Trade Order placement
            self.quick_trade.order_requested.connect(self._on_quick_trade_order)

            # 6. Stream tick receiver updates chart canvas & index tickers
            self.stream_worker.tick_received.connect(self._on_tick_received)
            self.stream_worker.connection_status.connect(self._on_connection_status)

            # 7. Multi-Broker Dynamic 2FA & Execution Toggle Matrix Wiring
            self.broker_control.trading_toggle_changed.connect(self._on_broker_trading_toggle_changed)
            self.broker_control.broker_state_changed.connect(self._on_broker_state_changed)
            self.order_router.notification_callback = self._on_router_notification

            # 8. Execution Mode & Front-Page Risk Controller Wiring
            if hasattr(self.sidebar, "risk_controller") and self.sidebar.risk_controller:
                self.sidebar.risk_controller.router = self.order_router
                try:
                    self.sidebar.risk_controller.risk_parameters_updated.connect(
                        lambda m, c, s: self.order_router.update_risk_parameters(m, c, s, enforce=True)
                    )
                    self.sidebar.risk_controller.risk_config_updated.connect(
                        lambda m, c, r, s, d: self.order_router.update_risk_parameters(m, c, s, risk_percentage=r, daily_drawdown_pct=d, enforce=True)
                    )
                except Exception:
                    pass
            if hasattr(self.broker_control, "risk_controller") and self.broker_control.risk_controller:
                self.broker_control.risk_controller.router = self.order_router
                try:
                    self.broker_control.risk_controller.risk_parameters_updated.connect(
                        lambda m, c, s: self.order_router.update_risk_parameters(m, c, s, enforce=True)
                    )
                    self.broker_control.risk_controller.risk_config_updated.connect(
                        lambda m, c, r, s, d: self.order_router.update_risk_parameters(m, c, s, risk_percentage=r, daily_drawdown_pct=d, enforce=True)
                    )
                except Exception:
                    pass
            if hasattr(self, "risk_manager_view") and self.risk_manager_view:
                self.risk_manager_view.router = self.order_router
                try:
                    self.risk_manager_view.risk_parameters_updated.connect(
                        lambda m, c, s: self.order_router.update_risk_parameters(m, c, s, enforce=True)
                    )
                    self.risk_manager_view.risk_config_updated.connect(
                        lambda m, c, r, s, d: self.order_router.update_risk_parameters(m, c, s, risk_percentage=r, daily_drawdown_pct=d, enforce=True)
                    )
                except Exception:
                    pass
        except Exception:
            pass

    def _on_broker_trading_toggle_changed(self, broker_name: str, enabled: bool) -> None:
        """Synchronizes GUI broker execution switch into OrderRouter."""
        self.order_router.set_broker_toggle(broker_name, enabled)
        inst = self.broker_control.get_broker_instance(broker_name)
        if inst:
            self.order_router.register_broker_instance(broker_name, inst)

    def _on_broker_state_changed(self, broker_name: str, new_state: str) -> None:
        """Updates OrderRouter gateway registration, RMS funds, and health telemetry."""
        inst = self.broker_control.get_broker_instance(broker_name)
        if inst:
            self.order_router.register_broker_instance(broker_name, inst)

        if new_state == "CONNECTED":
            self.system_health_card.update_telemetry(
                broker_connected=True,
                broker_name=broker_name,
                latency=self.stream_worker.get_dispatch_latency_ms()
            )
            # Update top bar latency pill to live
            if hasattr(self.top_bar, "update_latency"):
                try:
                    self.top_bar.update_latency(
                        latency_ms=self.stream_worker.get_dispatch_latency_ms(),
                        connected=True
                    )
                except Exception:
                    pass
            # Query authentic RMS funds from live broker
            if broker_name == "ANGEL_ONE" and inst and hasattr(inst, "get_rms_funds"):
                def fetch_rms():
                    try:
                        rms = inst.get_rms_funds()
                        if rms.get("status"):
                            self.portfolio_card.update_rms_funds(rms, len(self.order_router.positions))
                            net_cap = float(rms.get("net", 0.0) or 0.0)
                            self._rms_available = net_cap
                            if hasattr(self, "top_bar") and hasattr(self.top_bar, "update_nav"):
                                self.top_bar.update_nav(net_cap)
                            if hasattr(self, "sidebar") and hasattr(self.sidebar, "set_margin"):
                                self.sidebar.set_margin(net_cap)
                    except Exception:
                        pass
                threading.Thread(target=fetch_rms, daemon=True, name="RMSFundsFetcher").start()

            # Automatically start streaming worker if not already running
            if not self.stream_worker.isRunning():
                self.stream_worker.connect_stream(broker_name, ["3045", "2885", "26000", "26009"])
        elif new_state == "DISCONNECTED":
            any_conn = any(self.broker_control.is_broker_connected(b) for b in ("ANGEL_ONE", "SHOONYA", "GROWW"))
            if not any_conn:
                self.system_health_card.update_telemetry(
                    broker_connected=False,
                    broker_name="DISCONNECTED",
                    latency=None
                )
                self.portfolio_card.update_portfolio(0.0, 0.0, len(self.order_router.positions))
                if hasattr(self, "top_bar") and hasattr(self.top_bar, "update_nav"):
                    self.top_bar.update_nav(0.0)

    def _on_router_notification(self, title: str, message: str) -> None:
        """Surfaces non-blocking desktop warnings and execution alerts."""
        QMessageBox.warning(self, title, message)

    def _switch_page(self, index: int) -> None:
        """Switches active view in QStackedWidget and synchronizes sidebar active highlights."""
        if 0 <= index < self.stacked_widget.count():
            self.stacked_widget.setCurrentIndex(index)
            self.sidebar.set_active_index(index)
            if index == 10:
                self.reports_view.refresh_table()

    def _init_telemetry_timer(self) -> None:
        """Periodically refreshes real OS hardware load and SQLite ledger state."""
        try:
            self.telemetry_timer = QTimer(self)
            self.telemetry_timer.timeout.connect(self._refresh_real_database_metrics)
            self.telemetry_timer.start(2000)
        except Exception:
            pass

    def _refresh_real_database_metrics(self) -> None:
        """Zero-fake-data updater: queries real SQLite audit records and OS metrics."""
        try:
            # 1. Real SQLite Today's Summary
            summary = self.db.get_today_summary()
            self.summary_card.update_summary(
                trades=summary.get("total_trades", 0),
                wins=summary.get("wins", 0),
                losses=summary.get("losses", 0),
                win_rate=summary.get("win_rate", 0.0)
            )

            # 2. Real SQLite Live P&L
            realized = summary.get("realized_pnl", 0.0)
            unrealized = summary.get("unrealized_pnl", 0.0)
            self.live_pnl_card.update_pnl(realized, unrealized)

            # 3. Synchronize Top Bar Net Day P&L
            net_pnl = realized + unrealized
            if hasattr(self, "top_bar") and hasattr(self.top_bar, "update_net_pnl"):
                self.top_bar.update_net_pnl(net_pnl)

            # 4. Real Open Positions from OrderRouter
            open_pos_count = len(self.order_router.positions)
            self.portfolio_card.val_pos.setText(str(open_pos_count))

            # 5. Sidebar dock: connection pulse + ledger margin
            if hasattr(self, "sidebar"):
                if hasattr(self.sidebar, "set_connection_state"):
                    self.sidebar.set_connection_state(
                        self.stream_worker.isRunning(),
                        self.stream_worker.get_dispatch_latency_ms()
                    )
                if hasattr(self.sidebar, "set_margin"):
                    self.sidebar.set_margin(getattr(self, "_rms_available", None))

            # 6. Real OS CPU & RAM Telemetry
            is_conn = self.stream_worker.isRunning()
            active_broker = self.db.get_active_broker()
            b_name = active_broker.get("broker_name", "ANGEL_ONE") if active_broker else "DISCONNECTED"
            self.system_health_card.update_telemetry(
                broker_connected=is_conn,
                broker_name=b_name,
                latency=self.stream_worker.get_dispatch_latency_ms() if is_conn else None
            )
        except Exception:
            pass

    def _on_emergency_kill_switch(self, confirm: Optional[bool] = None) -> None:
        """
        Engages Emergency Kill Switch across the entire application:
        Blocks orders in RiskEngine, auto liquidates open positions via OrderRouter,
        and displays an institutional confirmation alert.

        A destructive, irreversible action must be confirmed BEFORE it is executed.
        Previously the halt + square-off ran first and only then showed a warning.
        """
        try:
            open_positions = len(self.order_router.positions)
        except Exception:
            open_positions = 0
        # confirm is None on the live UI path (modal), or an explicit
        # True/False when driven programmatically (benchmarks, automation).
        if confirm is None:
            choice = QMessageBox.question(
                self,
                "Confirm Emergency Kill Switch",
                f"Engage the global kill switch?\n\n"
                f"• All new orders will be blocked immediately\n"
                f"• {open_positions} open position(s) will be squared off at market\n"
                f"• This action is not reversible from the terminal",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if choice != QMessageBox.Yes:
                self._on_router_notification(
                    "Kill Switch Cancelled", "Operator declined the emergency halt."
                )
                return
        elif confirm is False:
            pass  # pre-authorised by the caller

        self.risk_engine.is_halted = True
        self.risk_engine.halt_reason = "EMERGENCY KILL SWITCH ENGAGED BY OPERATOR"
        liquidated = self.order_router.auto_square_off_all("EMERGENCY_KILL_SWITCH")
        self._refresh_real_database_metrics()

        QMessageBox.warning(
            self,
            "EMERGENCY KILL SWITCH ENGAGED",
            f"SYSTEM HALTED: All active orders blocked.\n"
            f"Positions squared off: {len(liquidated)}.\n"
            f"Statutory friction & risk boundaries preserved."
        )

    def _resolve_live_price(self, symbol: str) -> float:
        """
        Zero-Fake-Data price resolution: chart canvas tick, then real stream cache.
        Returns 0.0 when no genuine exchange price is available — never a synthetic anchor.
        """
        try:
            price = float(self.chart_widget.canvas.current_price or 0.0)
        except Exception:
            price = 0.0
        if price > 0.0:
            return price
        try:
            cached = BrokerStreamWorker.get_latest_tick(symbol)
            if cached:
                return float(cached.get("ltp") or 0.0)
        except Exception:
            pass
        return 0.0

    def _on_quick_trade_order(self, order_data: dict) -> None:
        """Dispatches order through OrderRouter with pre-trade risk verification and broker toggle matrix."""
        sym = order_data.get("symbol", "NIFTY 50")
        side = str(order_data.get("side", "BUY")).strip().upper()
        qty = int(order_data.get("quantity") or 0)
        if qty <= 0:
            qty = 1

        price = self._resolve_live_price(sym)
        if price <= 0.0:
            # Zero-Fake-Data mandate: refuse to fabricate an execution price.
            QMessageBox.warning(
                self,
                "No Live Market Price",
                f"Order rejected: no genuine exchange price is available for {sym}.\n"
                f"Connect a broker data stream (or wait for the first tick) before transmitting."
            )
            return

        if self.risk_engine.is_halted:
            QMessageBox.warning(self, "Risk Halt", f"Order rejected: {self.risk_engine.halt_reason}")
            return

        # Determine routing mode: If any broker trading toggle is ON, route LIVE through active matrix
        enabled_toggles = [b for b, toggled in self.order_router.get_all_toggles().items() if toggled]
        target_mode = "LIVE" if enabled_toggles else "PAPER"

        # Size the ticket against the operator's capital ceiling FIRST, then derive the
        # protective bracket from the quantity that will actually be filled. Deriving
        # the bracket from the pre-clamp quantity produces a stop that is too tight
        # after sizing, which silently fails the ₹70 gross hurdle gate downstream.
        effective_capital = RiskBudget.calculate_effective_capital(
            mode=target_mode,
            user_allocated_capital=self.order_router.user_trade_capital
        )
        max_qty = RiskBudget.calculate_uniform_lot_size(
            entry_price=price, effective_capital=effective_capital, leverage=5.0
        )
        if max_qty < 1:
            QMessageBox.warning(
                self,
                "Capital Limit",
                f"Order rejected: {sym} @ ₹{price:,.2f} requires more margin than the "
                f"allocated trade capital (₹{effective_capital:,.2f} at 5x leverage)."
            )
            return
        qty = min(qty, max_qty)

        # Budget the stop against the worst admissible fill (statutory 8 bps slippage
        # guard), otherwise an adverse fill pushes realised risk past the max-SL cap.
        worst_case_entry = round(
            price * (1.0 + RiskBudget.MAX_SLIPPAGE_PCT) if side == "BUY"
            else price * (1.0 - RiskBudget.MAX_SLIPPAGE_PCT),
            2
        )
        stop_loss = RiskBudget.derive_bracket_stop_loss(
            entry_price=worst_case_entry,
            side=side,
            quantity=qty,
            user_max_sl=self.order_router.user_max_sl
        )
        risk_distance = abs(price - stop_loss)
        target_price = round(
            price + (ConsensusEngine.DEFAULT_RR_MULTIPLIER * risk_distance) if side == "BUY"
            else price - (ConsensusEngine.DEFAULT_RR_MULTIPLIER * risk_distance),
            2
        )

        res = self.order_router.execute_order(
            symbol=sym,
            exchange="NSE",
            side=side,
            quantity=qty,
            price=price,
            stop_loss=stop_loss,
            target_price=target_price,
            order_type="MARKET",
            product="MIS",
            mode=target_mode
        )

        self._refresh_real_database_metrics()

        if res.get("status") in ("FILLED", "SUBMITTED", "OPEN"):
            b_info = res.get("broker") or ", ".join(res.get("dispatched_brokers", [])) or "PAPER"
            order_id = res.get("order_id") or res.get("trade_id")
            # Report the FILLED economics (the router clamps size and derives the
            # bracket stop), never the requested ticket values.
            filled_qty = int(res.get("quantity", qty))
            fill_price = float(res.get("executed_price", price))
            filled_sl = float(res.get("stop_loss", stop_loss))
            filled_tgt = float(res.get("target_price", target_price))
            QMessageBox.information(
                self,
                "Order Executed",
                f"Order {order_id} successfully executed!\n"
                f"Mode: {target_mode} | Gateway: {b_info}\n"
                f"Side: {side} | Qty: {filled_qty} | Price: ₹{fill_price:,.2f}\n"
                f"Bracket SL: ₹{filled_sl:,.2f} | Target: ₹{filled_tgt:,.2f}\n"
                f"Statutory Friction Buffer: ₹60.00 Applied."
            )
        elif res.get("status") == "REJECTED":
            QMessageBox.warning(
                self,
                "Order Blocked / Rejected",
                f"Execution Gate Notice:\n{res.get('message', 'Order rejected')}"
            )

    def _on_symbol_sync(self, symbol: str, ltp: Optional[float] = None,
                        navigate: bool = True) -> None:
        """
        Global instrument bus: one selection updates every telemetry surface.

        Fan-out: primary chart, Live Trading chart + DOM header, order ticket
        (symbol + live price + capital-aware quantity), and the watch grid.
        """
        if not symbol:
            return
        if ltp is None:
            try:
                tick = type(self.stream_worker).get_latest_tick(symbol)
                if tick:
                    ltp = float(tick.get("ltp", 0.0)) or None
            except Exception:
                ltp = None

        try:
            self.chart_widget.set_symbol(symbol)
        except Exception:
            pass
        if hasattr(self, "live_trading_view") and hasattr(self.live_trading_view, "set_symbol"):
            try:
                self.live_trading_view.set_symbol(symbol)
            except Exception:
                pass
        if hasattr(self, "quick_trade") and hasattr(self.quick_trade, "set_symbol"):
            try:
                self.quick_trade.set_symbol(symbol, ltp)
            except Exception:
                pass
        if hasattr(self, "consensus_view") and self.consensus_view is not None:
            try:
                self.consensus_view.reset()
            except Exception:
                pass
        if navigate:
            try:
                self._switch_page(1)   # Live Trading View
            except Exception:
                pass

    def _on_pill_selected(self, symbol: str) -> None:
        """Top-bar index pill click: sync every surface, stay on the current page."""
        self._on_symbol_sync(symbol, navigate=False)

    def _on_history_loaded(self, df) -> None:
        """Paints the 4-engine matrix from an authentic backfill frame."""
        if self.consensus_view is None:
            return
        try:
            symbol = getattr(self.chart_widget, "current_symbol", "") or ""
            self.consensus_view.update_from_df(df, symbol)
        except Exception:
            pass

    def _on_fast_order(self, order: dict) -> None:
        """Fast-ladder order: confirmed, then dispatched through the risk gate."""
        if not isinstance(order, dict) or not order.get("symbol"):
            return
        sym = order.get("symbol")
        side = str(order.get("side", "")).upper()
        try:
            choice = QMessageBox.question(
                self,
                f"Confirm Fast {side}",
                f"Transmit a MARKET {side} order for {sym}?\n\n"
                f"Quantity is sized by the router's uniform lot sizer and must pass "
                f"the consensus, GBM and ₹70 statutory hurdles.",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if choice != QMessageBox.Yes:
                self._on_router_notification("Fast Order Cancelled", f"{side} {sym} not transmitted.")
                return
        except Exception:
            pass
        try:
            self._on_quick_trade_order(order)   # same risk-gated dispatch path
        except Exception as exc:
            self._on_router_notification("Fast Order Failed", str(exc))

    def _on_square_off_position(self, trade_id: int) -> None:
        """
        Closes a single position at its real live LTP.

        Refuses to act without a genuine quote: never invent an exit price.
        """
        router = getattr(self, "order_router", None)
        if router is None:
            return
        pos = None  # locate the position so we can quote its symbol
        try:
            for p in router.get_open_positions():
                if int(p.get("trade_id", -1)) == int(trade_id):
                    pos = p
                    break
        except Exception:
            pos = None
        if pos is None:
            return
        ltp = None
        try:
            tick = type(self.stream_worker).get_latest_tick(pos.get("symbol", ""))
            if tick:
                ltp = float(tick.get("ltp", 0.0)) or None
        except Exception:
            ltp = None
        if not ltp:
            try:
                QMessageBox.warning(
                    self, "Square-Off Blocked",
                    f"No live quote available for {pos.get('symbol')}. "
                    f"Position left open — the terminal will not fabricate an exit price."
                )
            except Exception:
                pass
            return
        try:
            res = router.close_position(int(trade_id), float(ltp))
            status = res.get("status", "OK") if isinstance(res, dict) else "OK"
            self._on_router_notification(
                "Position Squared Off",
                f"Trade {trade_id} closed at ₹{float(ltp):,.2f} ({status})."
            )
        except Exception as exc:
            self._on_router_notification("Square-Off Failed", str(exc))
        try:
            self.portfolio_view.refresh_positions()
            self.quick_trade._refresh_positions()
        except Exception:
            pass

    def _on_tick_received(self, tick: dict) -> None:
        """Ingests live exchange ticks into chart and index ticker cards."""
        self.chart_widget.on_tick_received(tick)
        sym = tick.get("symbol", "")
        ltp = float(tick.get("ltp", 0.0))
        if ltp > 0 and not getattr(self, "_backfill_started", False):
            # First genuine tick: the feed is demonstrably live, so request the
            # real historical backfill once (never synthetic, never at boot).
            self._backfill_started = True
            try:
                self.chart_widget.request_backfill(sym)
            except Exception:
                pass
        if ltp > 0:
            # Level-1 depth + ticket price for the charted instrument.
            try:
                self.live_trading_view.update_depth(
                    sym,
                    best_bid=tick.get("best_bid"),
                    best_ask=tick.get("best_ask"),
                    ltp=ltp,
                )
            except Exception:
                pass
            try:
                if str(sym).strip().upper() == str(self.chart_widget.current_symbol).strip().upper():
                    self.quick_trade.update_ltp(ltp, symbol=sym)
            except Exception:
                pass
        if ltp > 0:
            # Fan the genuine tick out to the watch grid and scanner.
            try:
                self.market_watch_view.update_quote(
                    sym, ltp,
                    chg_pct=tick.get("chg_pct", tick.get("change_pct")),
                    volume=tick.get("volume"),
                )
            except Exception:
                pass
            try:
                self.scanner_panel.update_quote(sym, ltp)
            except Exception:
                pass
        if ltp > 0:
            # Real references only; absent fields render as an em dash.
            self.top_bar.update_ticker(
                sym,
                ltp,
                chg_pct=tick.get("chg_pct", tick.get("change_pct")),
                prev_close=tick.get("prev_close", tick.get("previous_close")),
            )

    def _fetch_history_backfill(self, symbol: str, timeframe: str = "5m"):
        """
        Real market-data provider for the chart backfill (runs off the UI thread).

        Returns an authentic OHLCV ``pandas.DataFrame`` or an empty frame when
        the upstream source is unavailable. Nothing is ever synthesised here —
        a funding/auth/network gap must leave the chart empty rather than fake.
        """
        import time as _time
        import pandas as pd
        key = (str(symbol).strip().upper(), str(timeframe))
        cache = getattr(self, "_history_cache", None)
        if cache is None:
            cache = self._history_cache = {}
        now = _time.monotonic()
        hit = cache.get(key)
        # 5-minute positive cache, 60-second negative cache: a dead upstream must
        # never be hammered on every symbol switch, and stale quotes are never
        # served beyond the window.
        if hit is not None and now - hit[0] < (300.0 if len(hit[1]) else 60.0):
            return hit[1]
        try:
            from core.time_machine import MonteCarloTimeMachine
            period = {"1m": "7d", "5m": "60d", "15m": "60d", "1H": "60d",
                      "4H": "60d", "1D": "1y"}.get(timeframe, "60d")
            df = MonteCarloTimeMachine().fetch_historical_candles(symbol, period=period)
            if df is None or not hasattr(df, "empty") or df.empty:
                cache[key] = (now, pd.DataFrame())
                return pd.DataFrame()
            frame = df.tail(240)
            cache[key] = (now, frame)
            return frame
        except Exception:
            cache[key] = (now, pd.DataFrame())
            return pd.DataFrame()

    def closeEvent(self, event) -> None:  # noqa: N802 - Qt override
        """Deterministic teardown: join backfill/stream threads before exit."""
        try:
            if hasattr(self, "chart_widget") and hasattr(self.chart_widget, "shutdown_backfill"):
                self.chart_widget.shutdown_backfill()
        except Exception:
            pass
        try:
            sw = getattr(self, "stream_worker", None)
            if sw is not None and sw.isRunning():
                if hasattr(sw, "disconnect_stream"):
                    sw.disconnect_stream()
                sw.quit()
                sw.wait(2000)
        except Exception:
            pass
        try:
            super().closeEvent(event)
        except Exception:
            try:
                event.accept()
            except Exception:
                pass

    def _on_connection_status(self, status: str, msg: str) -> None:
        """Updates health telemetry when broker connects or disconnects."""
        is_conn = (status == "CONNECTED")
        measured_latency = self.stream_worker.get_dispatch_latency_ms() if is_conn else None
        self.system_health_card.update_telemetry(
            broker_connected=is_conn,
            broker_name=self.stream_worker.broker_name,
            latency=measured_latency
        )
        # Sidebar dock: live connection pulse + latency readout
        if hasattr(self, "sidebar") and hasattr(self.sidebar, "set_connection_state"):
            self.sidebar.set_connection_state(is_conn, measured_latency)
        # Update top bar latency pill
        if hasattr(self.top_bar, "update_latency"):
            try:
                self.top_bar.update_latency(latency_ms=self.stream_worker.get_dispatch_latency_ms() if is_conn else None, connected=is_conn)
            except Exception:
                pass
        # Zero-Fake-Data guarantee: clear seed candles when broker disconnects
        if not is_conn:
            try:
                self.chart_widget.clear_canvas()
            except Exception:
                pass


# ─────────────────────────────────────────────────────────────────────────────
# Direct module entry point:  python -m ui.main_window
# Mirrors main.py's boot sequence (theme → window → event loop) so the terminal
# can be launched straight from this module during QA.
# ─────────────────────────────────────────────────────────────────────────────
def _launch() -> int:
    import sys
    from PySide6.QtWidgets import QApplication
    from ui.styles import GlassmorphismTheme

    os.environ.setdefault("QT_ENABLE_HIGHDPI_SCALING", "1")
    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("OmniTradePro Institutional Terminal v5.0")
    app.setOrganizationName("OmniTradePro Quantitative Systems")
    try:
        app.setStyleSheet(GlassmorphismTheme.get_stylesheet())
    except Exception:
        pass
    window = MainWindow()
    window.setWindowTitle("OmniTradePro v5.0 — Institutional Multi-Broker Terminal")
    window.showMaximized()
    return app.exec()


if __name__ == "__main__":
    import sys as _sys
    _sys.exit(_launch())
