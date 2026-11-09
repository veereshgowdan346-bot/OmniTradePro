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
    RiskManagerView, ReportsView, SettingsView
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
                            if hasattr(self, "top_bar") and hasattr(self.top_bar, "update_nav"):
                                self.top_bar.update_nav(net_cap)
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

            # 5. Real OS CPU & RAM Telemetry
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

    def _on_emergency_kill_switch(self) -> None:
        """
        Engages Emergency Kill Switch across the entire application:
        Blocks orders in RiskEngine, auto liquidates open positions via OrderRouter,
        and displays an institutional confirmation alert.
        """
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

    def _on_tick_received(self, tick: dict) -> None:
        """Ingests live exchange ticks into chart and index ticker cards."""
        self.chart_widget.on_tick_received(tick)
        sym = tick.get("symbol", "")
        ltp = float(tick.get("ltp", 0.0))
        if ltp > 0:
            self.top_bar.update_ticker(sym, ltp, 0.0)

    def _on_connection_status(self, status: str, msg: str) -> None:
        """Updates health telemetry when broker connects or disconnects."""
        is_conn = (status == "CONNECTED")
        self.system_health_card.update_telemetry(
            broker_connected=is_conn,
            broker_name=self.stream_worker.broker_name,
            latency=self.stream_worker.get_dispatch_latency_ms() if is_conn else None
        )
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
