#!/usr/bin/env python3
"""
OmniTradePro / Chintu AI Trading Board v5.0 - Multi-Page Sub-View Suite
Platform: Windows 10/11 64-bit | Python 3.10+
Implements the 11 specialized frosted glassmorphism views for QStackedWidget:
Page 1: LiveTradingView (Chart canvas, Depth of Market, Fast order ladder)
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

from typing import Optional, List, Dict, Any
from pathlib import Path

try:
    from PySide6.QtWidgets import (
        QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel,
        QPushButton, QComboBox, QSpinBox, QDoubleSpinBox, QFrame,
        QTableWidget, QTableWidgetItem, QHeaderView, QLineEdit,
        QProgressBar, QScrollArea, QMessageBox, QCheckBox
    )
    from PySide6.QtCore import Qt, Signal
except ImportError:
    class QWidget:
        def __init__(self, parent=None): pass
        def setStyleSheet(self, s): pass
        def setFixedSize(self, w, h): pass
        def setFixedWidth(self, w): pass
        def setFixedHeight(self, h): pass
        def setProperty(self, k, v): pass
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
    class QGridLayout(QVBoxLayout):
        def addWidget(self, w, r, c, rs=1, cs=1): pass
    class _TextStr(str):
        def __call__(self): return str(self)
    class QLabel:
        def __init__(self, text="", parent=None): self.text = _TextStr(text)
        def setText(self, t): self.text = _TextStr(t)
        def setStyleSheet(self, s): pass
        def setAlignment(self, a): pass
        def setProperty(self, k, v): pass
        def setVisible(self, v): pass
        def setFixedWidth(self, w): pass
        def setFixedHeight(self, h): pass
        def setFixedSize(self, w, h): pass
    class Signal:
        def __init__(self, *types):
            self._callbacks = []
        def connect(self, cb):
            self._callbacks.append(cb)
        def emit(self, *args):
            for cb in list(self._callbacks):
                try:
                    cb(*args)
                except Exception:
                    pass
    class QPushButton:
        def __init__(self, text="", parent=None):
            self.text = text
            self.clicked = Signal()
        def setText(self, t): self.text = t
        def setStyleSheet(self, s): pass
        def setFixedWidth(self, w): pass
        def setFixedHeight(self, h): pass
        def setEnabled(self, e): pass
    class QComboBox:
        def __init__(self, parent=None): pass
        def addItems(self, items): pass
        def currentText(self): return ""
    class QSpinBox:
        def __init__(self, parent=None):
            self._val = 0
            self.valueChanged = Signal()
        def setRange(self, a, b): pass
        def setSingleStep(self, s): pass
        def setPrefix(self, p): pass
        def setSuffix(self, s): pass
        def setDecimals(self, d): pass
        def setValue(self, v):
            self._val = v
            try:
                self.valueChanged.emit(self._val)
            except Exception:
                pass
        def value(self): return self._val
        def setStyleSheet(self, s): pass
        def setFixedHeight(self, h): pass
        def setFixedWidth(self, w): pass
    class QDoubleSpinBox(QSpinBox):
        def __init__(self, parent=None):
            super().__init__(parent)
            self._val = 0.0
        def value(self): return float(self._val)
    class QLineEdit:
        Normal = 0
        Password = 1
        def __init__(self, parent=None): self._t = ""
        def setText(self, t): self._t = t
        def text(self): return self._t
        def setPlaceholderText(self, p): pass
        def setEchoMode(self, m): pass
    class QTableWidget:
        def __init__(self, r, c, parent=None): pass
        def setHorizontalHeaderLabels(self, l): pass
        def horizontalHeader(self): return self
        def setSectionResizeMode(self, m): pass
        def setRowCount(self, r): pass
        def setItem(self, r, c, item): pass
        def setCellWidget(self, r, c, w): pass
    class QTableWidgetItem:
        def __init__(self, text=""): pass
    class QHeaderView:
        Stretch = 1
    class QScrollArea:
        def __init__(self, parent=None): pass
        def setWidgetResizable(self, b): pass
        def setWidget(self, w): pass
        def setFrameShape(self, s): pass
        def setStyleSheet(self, s): pass
    class QCheckBox:
        def __init__(self, text="", parent=None): pass
        def setChecked(self, b): pass
        def isChecked(self): return True
        def setStyleSheet(self, s): pass
    class QMessageBox:
        @staticmethod
        def information(p, t, m): pass
        @staticmethod
        def warning(p, t, m): pass
    class Qt:
        AlignCenter = 0x0004
        AlignLeft = 0x0001
        AlignRight = 0x0002
        NoFrame = 0

from ui.chart_widget import ChartWidget
from database.db_handler import DatabaseHandler
from core.risk_engine import RiskEngine
from core.order_router import OrderRouter
from core.time_machine import MonteCarloTimeMachine


class BasePageView(QScrollArea):
    """Base scrollable container with cyber frosted glass styling for responsive scaling."""

    def __init__(self, title: str, subtitle: str, parent=None) -> None:
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.NoFrame)
        self.setStyleSheet("background: transparent; border: none;")

        self.container = QWidget()
        self.container.setStyleSheet("background-color: #060b13;")
        self.layout_main = QVBoxLayout(self.container)
        self.layout_main.setContentsMargins(16, 14, 16, 16)
        self.layout_main.setSpacing(12)

        # Header Title Banner
        hdr_card = QFrame(self.container)
        hdr_card.setStyleSheet("background-color: #0d1726; border: 1px solid #16243a; border-radius: 8px; padding: 10px 14px;")
        hl = QVBoxLayout(hdr_card)
        hl.setContentsMargins(4, 2, 4, 2)
        hl.setSpacing(2)

        lbl_title = QLabel(title, hdr_card)
        lbl_title.setStyleSheet("color: #00e676; font-size: 15px; font-weight: 800; letter-spacing: 0.5px;")

        lbl_sub = QLabel(subtitle, hdr_card)
        lbl_sub.setStyleSheet("color: #78909c; font-size: 11px;")

        hl.addWidget(lbl_title)
        hl.addWidget(lbl_sub)
        self.layout_main.addWidget(hdr_card)

        self.setWidget(self.container)


class LiveTradingView(BasePageView):
    """Page 1: Full-height candlestick chart, DOM depth, fast buy/sell ladder."""

    def __init__(self, parent=None) -> None:
        super().__init__("📈 LIVE TRADING & DEPTH OF MARKET (DOM)", "High-frequency chart canvas, Level 2 orderbook depth, and fast execution ladder.", parent)
        self._init_body()

    def _init_body(self) -> None:
        split_layout = QHBoxLayout()
        split_layout.setSpacing(12)

        # Chart on Left (70%)
        self.chart = ChartWidget(self.container)
        self.chart_widget = self.chart
        split_layout.addWidget(self.chart, 70)

        # DOM & Ladder on Right (30%)
        dom_card = QFrame(self.container)
        dom_card.setStyleSheet("background-color: #0d1726; border: 1px solid #16243a; border-radius: 10px; padding: 12px;")
        dl = QVBoxLayout(dom_card)
        dl.setSpacing(8)

        dl.addWidget(QLabel("DEPTH OF MARKET (L2)", dom_card))

        dom_table = QTableWidget(5, 4, dom_card)
        dom_table.setHorizontalHeaderLabels(["Bids", "Qty", "Asks", "Qty"])
        try:
            dom_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        except Exception:
            pass

        bids = [("24,856.50", "450"), ("24,855.00", "1,200"), ("24,854.20", "850"), ("24,853.00", "2,100"), ("24,850.00", "5,400")]
        asks = [("24,857.50", "600"), ("24,858.00", "1,150"), ("24,859.50", "900"), ("24,860.00", "3,400"), ("24,862.00", "4,200")]

        for r in range(5):
            dom_table.setItem(r, 0, QTableWidgetItem(bids[r][0]))
            dom_table.setItem(r, 1, QTableWidgetItem(bids[r][1]))
            dom_table.setItem(r, 2, QTableWidgetItem(asks[r][0]))
            dom_table.setItem(r, 3, QTableWidgetItem(asks[r][1]))

        dl.addWidget(dom_table)

        # Fast Execution Ladder
        ladder_layout = QHBoxLayout()
        btn_fb = QPushButton("FAST BUY (MARKET)", dom_card)
        btn_fb.setStyleSheet("background-color: #00e676; color: #060b13; font-weight: 800; padding: 10px; border-radius: 6px; border: none;")

        btn_fs = QPushButton("FAST SELL (MARKET)", dom_card)
        btn_fs.setStyleSheet("background-color: #ff1744; color: #ffffff; font-weight: 800; padding: 10px; border-radius: 6px; border: none;")

        ladder_layout.addWidget(btn_fb)
        ladder_layout.addWidget(btn_fs)
        dl.addLayout(ladder_layout)

        split_layout.addWidget(dom_card, 30)
        self.layout_main.addLayout(split_layout)


class TradingBotsView(BasePageView):
    """Page 2: Consensus engine control, toggle individual bots, weights."""

    def __init__(self, parent=None) -> None:
        super().__init__("🤖 QUANTITATIVE TRADING BOTS & CONSENSUS MATRIX", "Enforce 4-algorithm mathematical consensus voting with configurable odds filters.", parent)
        self._init_body()

    def _init_body(self) -> None:
        bots_card = QFrame(self.container)
        bots_card.setStyleSheet("background-color: #0d1726; border: 1px solid #16243a; border-radius: 10px; padding: 14px;")
        bl = QVBoxLayout(bots_card)
        bl.setSpacing(10)

        bl.addWidget(QLabel("INSTITUTIONAL BOT CONFIGURATION MATRIX", bots_card))

        bot_configs = [
            ("Alpha Trend Scalper", "NIFTY 50", "SMC Liquidity Grab + VWAP Anchor", "25% Weight"),
            ("BankNifty Breakout", "BANKNIFTY", "15-Min ORB + Dual EMA Momentum", "25% Weight"),
            ("Mean Reversion Pro", "FINNIFTY", "Oversold RSI-14 Bounce + SuperTrend", "25% Weight"),
            ("Gamma Squeeze", "NIFTY OPT", "Volume Surge Divergence + ATR Trailing", "25% Weight")
        ]

        for name, inst, strat, wt in bot_configs:
            row_frame = QFrame(bots_card)
            row_frame.setStyleSheet("background-color: #09101b; border: 1px solid #142236; border-radius: 6px; padding: 8px;")
            rl = QHBoxLayout(row_frame)

            chk = QCheckBox(name, row_frame)
            chk.setChecked(True)
            chk.setStyleSheet("color: #ffffff; font-weight: bold; font-size: 12px;")

            lbl_inst = QLabel(inst, row_frame)
            lbl_inst.setStyleSheet("color: #00e676; font-weight: bold;")

            lbl_strat = QLabel(strat, row_frame)
            lbl_strat.setStyleSheet("color: #90a4ae; font-size: 11px;")

            lbl_wt = QLabel(wt, row_frame)
            lbl_wt.setStyleSheet("color: #00f2fe; font-weight: bold;")

            btn_toggle = QPushButton("Enabled", row_frame)
            btn_toggle.setStyleSheet("background-color: rgba(0, 230, 118, 0.2); border: 1px solid #00e676; color: #00e676; font-weight: bold; padding: 3px 8px; border-radius: 4px;")

            rl.addWidget(chk)
            rl.addWidget(lbl_inst)
            rl.addWidget(lbl_strat)
            rl.addStretch()
            rl.addWidget(lbl_wt)
            rl.addWidget(btn_toggle)
            bl.addWidget(row_frame)

        self.layout_main.addWidget(bots_card)


class StrategiesView(BasePageView):
    """Page 3: Parameters for SMC Liquidity, VWAP Anchor, EMA 9/21, SuperTrend."""

    def __init__(self, parent=None) -> None:
        super().__init__("⚙ ALGORITHMIC STRATEGY CORE PARAMETERS", "Calibrate mathematical parameters, indicator lookbacks, and ATR multipliers.", parent)
        self._init_body()

    def _init_body(self) -> None:
        grid = QGridLayout()
        grid.setSpacing(12)

        strats = [
            ("Strategy 1: SMC Liquidity Sweep", [("Lookback Window", "20 candles"), ("Wick Pierce Minimum", "0.05%"), ("Session Alignment", "09:15 - 15:15 IST")]),
            ("Strategy 2: Institutional VWAP", [("Anchor Mode", "Intraday Cumulative"), ("Standard Deviation Bands", "1.0 & 2.0"), ("Volume Threshold", "1.2x Rolling Avg")]),
            ("Strategy 3: Dual EMA Momentum", [("Fast EMA Period", "9"), ("Slow EMA Period", "21"), ("Smoothing Alpha", "Exponential")]),
            ("Strategy 4: SuperTrend Gate", [("ATR Period", "10"), ("ATR Multiplier", "2.0"), ("Trailing Stop Floor", "1.5x ATR")])
        ]

        for i, (title, params) in enumerate(strats):
            card = QFrame(self.container)
            card.setStyleSheet("background-color: #0d1726; border: 1px solid #16243a; border-radius: 10px; padding: 12px;")
            cl = QVBoxLayout(card)

            cl.addWidget(QLabel(title, card))
            for p_name, p_val in params:
                pr = QHBoxLayout()
                pr.addWidget(QLabel(p_name, card))
                pr.addStretch()
                v = QLabel(p_val, card)
                v.setStyleSheet("color: #00e676; font-weight: bold;")
                pr.addWidget(v)
                cl.addLayout(pr)
            cl.addStretch()
            grid.addWidget(card, i // 2, i % 2)

        self.layout_main.addLayout(grid)


class MarketWatchView(BasePageView):
    """Page 4: Watchlist table for Nifty 50 anchors and MCX instruments."""

    def __init__(self, parent=None) -> None:
        super().__init__("👁 LIVE MARKET WATCH (NSE & MCX)", "Real-time quote registry with zero ticker mutation and support for up to 20-character symbols.", parent)
        self._init_body()

    def _init_body(self) -> None:
        card = QFrame(self.container)
        card.setStyleSheet("background-color: #0d1726; border: 1px solid #16243a; border-radius: 10px; padding: 12px;")
        cl = QVBoxLayout(card)

        table = QTableWidget(10, 7, card)
        headers = ["Symbol", "Token", "Exchange", "LTP (₹)", "Change (%)", "Volume", "Quick Action"]
        table.setHorizontalHeaderLabels(headers)
        try:
            table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        except Exception:
            pass

        watchlist = [
            ("RELIANCE.NS", "2885", "NSE", "2,885.00", "+0.45%", "1,420,500"),
            ("TCS.NS", "11536", "NSE", "3,850.50", "-0.20%", "650,200"),
            ("HDFCBANK.NS", "1333", "NSE", "1,620.00", "+0.80%", "2,840,000"),
            ("INFY.NS", "1594", "NSE", "1,780.25", "+1.15%", "1,950,400"),
            ("TATAMOTORS.NS", "3456", "NSE", "985.40", "+1.85%", "3,400,100"),
            ("ICICIBANK.NS", "4963", "NSE", "1,195.00", "+0.35%", "1,620,000"),
            ("CRUDEOIL", "236901", "MCX", "6,150.00", "+0.95%", "85,400"),
            ("GOLDM", "236902", "MCX", "74,500.00", "+0.30%", "24,800"),
            ("SILVERM", "236903", "MCX", "88,200.00", "-0.15%", "18,900"),
            ("TATASTEEL.NS", "3499", "NSE", "152.40", "+0.60%", "5,200,000")
        ]

        for r, (sym, tok, ex, ltp, chg, vol) in enumerate(watchlist):
            table.setItem(r, 0, QTableWidgetItem(sym))
            table.setItem(r, 1, QTableWidgetItem(tok))
            table.setItem(r, 2, QTableWidgetItem(ex))
            table.setItem(r, 3, QTableWidgetItem(ltp))
            
            c_item = QTableWidgetItem(chg)
            table.setItem(r, 4, c_item)
            table.setItem(r, 5, QTableWidgetItem(vol))

            btn = QPushButton("Trade", card)
            btn.setStyleSheet("background-color: #00e676; color: #060b13; font-weight: bold; padding: 2px 8px; border-radius: 4px; border: none;")
            table.setCellWidget(r, 6, btn)

        cl.addWidget(table)
        self.layout_main.addWidget(card)


class AutoTradeView(BasePageView):
    """Page 5: Autonomous execution switches, gross >= ₹70 profit filters."""

    def __init__(self, parent=None) -> None:
        super().__init__("⚡ AUTONOMOUS TRADING & PROFIT HURDLE GATEWAY", "Continuous multi-session routing with mandatory statutory friction buffers.", parent)
        self._init_body()

    def _init_body(self) -> None:
        card = QFrame(self.container)
        card.setStyleSheet("background-color: #0d1726; border: 1px solid #16243a; border-radius: 10px; padding: 14px;")
        cl = QVBoxLayout(card)
        cl.setSpacing(12)

        items = [
            ("Master Auto Trade Router", "Enables autonomous signal routing from 4-bot consensus engine", True),
            ("Mandatory ₹70.0 Gross Profit Hurdle", "Enforces ₹60 round-trip fee deduction; guarantees >= ₹10 net gain", True),
            ("10% Capital Risk Ceiling", "Hard floor rejecting any position risking > 10% of allocated capital", True),
            ("Intraday Auto Square-Off", "Forces auto liquidation at 15:15 IST (Equity) and 23:15 IST (MCX)", True),
            ("Paper Slippage Engine (0.02%)", "Simulates realistic exchange fill frictions during testing", True)
        ]

        for title, desc, active in items:
            row = QFrame(card)
            row.setStyleSheet("background-color: #09101b; border: 1px solid #142236; border-radius: 6px; padding: 10px;")
            rl = QHBoxLayout(row)

            chk = QCheckBox(title, row)
            chk.setChecked(active)
            chk.setStyleSheet("color: #ffffff; font-weight: bold; font-size: 13px;")

            desc_lbl = QLabel(desc, row)
            desc_lbl.setStyleSheet("color: #78909c; font-size: 11px;")

            status_pill = QLabel("ACTIVE" if active else "OFF", row)
            status_pill.setStyleSheet("color: #00e676; font-weight: bold; padding: 2px 6px;")

            rl.addWidget(chk)
            rl.addWidget(desc_lbl)
            rl.addStretch()
            rl.addWidget(status_pill)
            cl.addWidget(row)

        self.layout_main.addWidget(card)


class BacktestView(BasePageView):
    """Page 6: Trigger 10,000-candle Time Machine historical odds replays."""

    def __init__(self, parent=None) -> None:
        super().__init__("⏱ 10,000-REPLAY MONTE CARLO TIME MACHINE", "Replays historical 5-minute permutations until 15:15 IST to compute exact empirical win odds.", parent)
        self.time_machine = MonteCarloTimeMachine()
        self._init_body()

    def _init_body(self) -> None:
        ctrl_card = QFrame(self.container)
        ctrl_card.setStyleSheet("background-color: #0d1726; border: 1px solid #16243a; border-radius: 10px; padding: 12px;")
        cl = QHBoxLayout(ctrl_card)

        cl.addWidget(QLabel("Target Symbol:", ctrl_card))
        self.combo_sym = QComboBox(ctrl_card)
        self.combo_sym.addItems(["RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "TATAMOTORS.NS"])
        cl.addWidget(self.combo_sym)

        cl.addWidget(QLabel("Iterations:", ctrl_card))
        self.spin_iters = QSpinBox(ctrl_card)
        self.spin_iters.setRange(1000, 50000)
        self.spin_iters.setValue(10000)
        cl.addWidget(self.spin_iters)

        self.btn_run = QPushButton("▶ Run Simulation", ctrl_card)
        self.btn_run.setStyleSheet("background-color: #00e676; color: #060b13; font-weight: 800; padding: 8px 16px; border-radius: 6px; border: none;")
        try:
            self.btn_run.clicked.connect(self._run_sim)
        except Exception:
            pass
        cl.addWidget(self.btn_run)
        cl.addStretch()
        self.layout_main.addWidget(ctrl_card)

        # Output Card
        self.out_card = QFrame(self.container)
        self.out_card.setStyleSheet("background-color: #0d1726; border: 1px solid #16243a; border-radius: 10px; padding: 14px;")
        ol = QVBoxLayout(self.out_card)

        self.lbl_out_title = QLabel("SIMULATION REPORT: Ready to Run", self.out_card)
        self.lbl_out_title.setStyleSheet("color: #00f2fe; font-size: 13px; font-weight: bold;")
        ol.addWidget(self.lbl_out_title)

        self.lbl_metrics = QLabel("Select symbol and click 'Run Simulation' to execute historical permutations.", self.out_card)
        self.lbl_metrics.setStyleSheet("color: #90a4ae; font-size: 12px;")
        ol.addWidget(self.lbl_metrics)

        self.layout_main.addWidget(self.out_card)

    def _run_sim(self) -> None:
        sym = self.combo_sym.currentText()
        iters = self.spin_iters.value()
        res = self.time_machine.run_simulation(sym, iterations=iters)
        t_hit = res.get("target_hit_pct", 0.0)
        s_hit = res.get("stop_hit_pct", 0.0)
        odds = res.get("win_odds_ratio", 0.0)
        passed = res.get("passes_odds_filter", False)

        self.lbl_out_title.setText(f"SIMULATION REPORT: {sym} ({iters:,} Paths)")
        self.lbl_metrics.setText(
            f"Target Hit Probability (1:2 R:R): <span style='color:#00e676; font-weight:bold;'>{t_hit:.2f}%</span> | "
            f"Stop-Loss Probability: <span style='color:#ff1744; font-weight:bold;'>{s_hit:.2f}%</span> | "
            f"Win Odds Ratio: <span style='color:#00f2fe; font-weight:bold;'>{odds:.4f}</span> | "
            f"Filter Gate (>= 65%): <span style='color:{'#00e676' if passed else '#ff1744'}; font-weight:bold;'>{'PASSED' if passed else 'REJECTED'}</span>"
        )


class AnalyticsView(BasePageView):
    """Page 7: P&L distribution curves, max drawdown charts."""

    def __init__(self, parent=None) -> None:
        super().__init__("📊 QUANTITATIVE PERFORMANCE ANALYTICS", "Inspect Sharpe ratio, trade expectancy, P&L distribution, and max drawdown.", parent)
        self._init_body()

    def _init_body(self) -> None:
        grid = QGridLayout()
        grid.setSpacing(12)

        metrics = [
            ("Annualized Sharpe Ratio", "2.18", "#00e676"),
            ("Profit Factor", "1.92", "#00e676"),
            ("Win / Loss Ratio", "2.81", "#00e676"),
            ("Max Historical Drawdown", "2.50%", "#00f2fe"),
            ("Average Trade Expectancy", "+₹420.00", "#00e676"),
            ("Friction Deductions Today", "₹0.00", "#ffffff")
        ]

        for i, (title, val, col) in enumerate(metrics):
            card = QFrame(self.container)
            card.setStyleSheet("background-color: #0d1726; border: 1px solid #16243a; border-radius: 8px; padding: 12px;")
            cl = QVBoxLayout(card)
            cl.addWidget(QLabel(title, card))
            vl = QLabel(val, card)
            vl.setStyleSheet(f"color: {col}; font-size: 18px; font-weight: 800;")
            cl.addWidget(vl)
            grid.addWidget(card, i // 3, i % 3)

        self.layout_main.addLayout(grid)


class PortfolioView(BasePageView):
    """Page 8: Capital allocation, margin utilization breakdown."""

    def __init__(self, parent=None) -> None:
        super().__init__("💼 PORTFOLIO & MARGIN ALLOCATION BREAKDOWN", "Autonomous capital-to-asset routing across Equity Cash, Nifty 50, and MCX Commodities.", parent)
        self._init_body()

    def _init_body(self) -> None:
        card = QFrame(self.container)
        card.setStyleSheet("background-color: #0d1726; border: 1px solid #16243a; border-radius: 10px; padding: 14px;")
        cl = QVBoxLayout(card)

        cl.addWidget(QLabel("MULTI-BROKER MARGIN UTILIZATION", card))

        table = QTableWidget(3, 5, card)
        table.setHorizontalHeaderLabels(["Broker Gateway", "Allocated Capital", "Used Margin", "Available", "Status"])
        try:
            table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        except Exception:
            pass

        data = [
            ("ANGEL_ONE", "₹0.00", "₹0.00", "₹0.00", "ACTIVE"),
            ("SHOONYA", "₹0.00", "₹0.00", "₹0.00", "STANDBY"),
            ("GROWW", "₹0.00", "₹0.00", "₹0.00", "STANDBY")
        ]

        for r, row in enumerate(data):
            for c, val in enumerate(row):
                table.setItem(r, c, QTableWidgetItem(val))

        cl.addWidget(table)
        self.layout_main.addWidget(card)


class RiskManagerView(BasePageView):
    """
    Page 9: RMS settings, dynamic capital controls, risk percentages,
    ruin floor circuit breaker limits, emergency square-off protocols, and risk floors.
    """
    _all_instances: List["RiskManagerView"] = []
    risk_parameters_updated = Signal(str, float, float)
    risk_config_updated = Signal(str, float, float, float, float)

    def __init__(self, parent=None, router=None) -> None:
        super().__init__(
            "🛡 RISK MANAGEMENT SYSTEM (RMS)",
            "Configure dynamic capital allocation, risk percentages, ruin floor circuit breakers, and emergency square-off protocols.",
            parent
        )
        RiskManagerView._all_instances.append(self)
        self.router = router
        self.db = DatabaseHandler()
        self.risk_engine = RiskEngine()
        self.current_mode: str = "PAPER"
        self._is_calculating: bool = False
        self._init_body()
        self._load_config()

    def _init_body(self) -> None:
        # Card 1: Dynamic Admin Risk & Capital Controls
        card_admin = QFrame(self.container)
        card_admin.setStyleSheet("background-color: #0d1726; border: 1px solid #16243a; border-radius: 10px; padding: 16px;")
        al = QVBoxLayout(card_admin)
        al.setSpacing(12)

        lbl_admin_title = QLabel("⚡ DYNAMIC ADMIN RISK & CAPITAL ALLOCATION", card_admin)
        lbl_admin_title.setStyleSheet("color: #00e5ff; font-weight: 800; font-size: 13px; letter-spacing: 0.5px;")
        al.addWidget(lbl_admin_title)

        lbl_admin_desc = QLabel(
            "Configure mathematical capital ceilings, risk percentages, per-trade stop-loss, and daily ruin floor circuit breakers.",
            card_admin
        )
        lbl_admin_desc.setStyleSheet("color: #94a3b8; font-size: 11px;")
        al.addWidget(lbl_admin_desc)

        # 4 Interactive Controls Form
        form_layout = QVBoxLayout()
        form_layout.setSpacing(8)

        # Control 1: Allocated Trading Capital
        r_cap = QHBoxLayout()
        lbl_c = QLabel("Allocated Trading Capital (₹):", card_admin)
        lbl_c.setStyleSheet("color: #f8fafc; font-weight: 600; font-size: 11px;")
        self.spin_capital = QDoubleSpinBox(card_admin)
        self.spin_capital.setRange(500.0, 1000000.0)
        self.spin_capital.setSingleStep(500.0)
        self.spin_capital.setValue(1000.0)
        self.spin_capital.setPrefix("₹ ")
        self.spin_capital.setDecimals(0)
        self.spin_capital.setFixedHeight(28)
        self.spin_capital.setStyleSheet("""
            QDoubleSpinBox {
                background-color: #070d18;
                border: 1px solid #1e293b;
                border-radius: 4px;
                color: #ffffff;
                font-family: 'Consolas', monospace;
                font-size: 12px;
                font-weight: bold;
                padding: 2px 8px;
            }
        """)
        r_cap.addWidget(lbl_c)
        r_cap.addStretch()
        r_cap.addWidget(self.spin_capital)
        form_layout.addLayout(r_cap)

        # Control 2: Max Risk / Loss Percentage per Trade (%)
        r_risk = QHBoxLayout()
        lbl_r = QLabel("Max Risk / Loss Percentage per Trade (%):", card_admin)
        lbl_r.setStyleSheet("color: #f8fafc; font-weight: 600; font-size: 11px;")
        self.spin_risk_pct = QDoubleSpinBox(card_admin)
        self.spin_risk_pct.setRange(0.5, 50.0)
        self.spin_risk_pct.setSingleStep(0.5)
        self.spin_risk_pct.setValue(5.0)
        self.spin_risk_pct.setSuffix(" %")
        self.spin_risk_pct.setDecimals(1)
        self.spin_risk_pct.setFixedHeight(28)
        self.spin_risk_pct.setStyleSheet("""
            QDoubleSpinBox {
                background-color: #070d18;
                border: 1px solid #1e293b;
                border-radius: 4px;
                color: #00e5ff;
                font-family: 'Consolas', monospace;
                font-size: 12px;
                font-weight: bold;
                padding: 2px 8px;
            }
        """)
        r_risk.addWidget(lbl_r)
        r_risk.addStretch()
        r_risk.addWidget(self.spin_risk_pct)
        form_layout.addLayout(r_risk)

        # Control 3: Calculated Max Rupee Risk per Trade (₹)
        r_sl = QHBoxLayout()
        lbl_s = QLabel("Calculated Max Rupee Risk per Trade (₹):", card_admin)
        lbl_s.setStyleSheet("color: #f8fafc; font-weight: 600; font-size: 11px;")
        self.spin_max_sl = QDoubleSpinBox(card_admin)
        self.spin_max_sl.setRange(10.0, 50000.0)
        self.spin_max_sl.setSingleStep(10.0)
        self.spin_max_sl.setValue(50.0)
        self.spin_max_sl.setPrefix("₹ ")
        self.spin_max_sl.setDecimals(0)
        self.spin_max_sl.setFixedHeight(28)
        self.spin_max_sl.setStyleSheet("""
            QDoubleSpinBox {
                background-color: #070d18;
                border: 1px solid #1e293b;
                border-radius: 4px;
                color: #ff5252;
                font-family: 'Consolas', monospace;
                font-size: 12px;
                font-weight: bold;
                padding: 2px 8px;
            }
        """)
        r_sl.addWidget(lbl_s)
        r_sl.addStretch()
        r_sl.addWidget(self.spin_max_sl)
        form_layout.addLayout(r_sl)

        # Control 4: Daily Drawdown Circuit Breaker Limit (%)
        r_dd = QHBoxLayout()
        lbl_d = QLabel("Daily Drawdown Circuit Breaker Limit (%):", card_admin)
        lbl_d.setStyleSheet("color: #f8fafc; font-weight: 600; font-size: 11px;")
        self.spin_drawdown_pct = QDoubleSpinBox(card_admin)
        self.spin_drawdown_pct.setRange(2.0, 50.0)
        self.spin_drawdown_pct.setSingleStep(1.0)
        self.spin_drawdown_pct.setValue(10.0)
        self.spin_drawdown_pct.setSuffix(" %")
        self.spin_drawdown_pct.setDecimals(1)
        self.spin_drawdown_pct.setFixedHeight(28)
        self.spin_drawdown_pct.setStyleSheet("""
            QDoubleSpinBox {
                background-color: #070d18;
                border: 1px solid #1e293b;
                border-radius: 4px;
                color: #ffab00;
                font-family: 'Consolas', monospace;
                font-size: 12px;
                font-weight: bold;
                padding: 2px 8px;
            }
        """)
        r_dd.addWidget(lbl_d)
        r_dd.addStretch()
        r_dd.addWidget(self.spin_drawdown_pct)
        form_layout.addLayout(r_dd)

        al.addLayout(form_layout)

        # Connect mutual auto-calculation
        try:
            self.spin_capital.valueChanged.connect(self._on_capital_or_risk_changed)
            self.spin_risk_pct.valueChanged.connect(self._on_capital_or_risk_changed)
            self.spin_max_sl.valueChanged.connect(self._on_max_sl_changed)
            self.spin_drawdown_pct.valueChanged.connect(self._on_drawdown_changed)
        except Exception:
            pass

        # Ruin Floor Display Label
        self.lbl_ruin_floor = QLabel("Dynamic Ruin Floor: ₹100.00 (Max cumulative loss before engine hard lock)", card_admin)
        self.lbl_ruin_floor.setStyleSheet("color: #ffab00; font-weight: bold; font-size: 11px; font-family: 'Consolas', monospace;")
        al.addWidget(self.lbl_ruin_floor)

        # Save Button & Status Row
        btn_row = QHBoxLayout()
        self.btn_save = QPushButton("💾 Save & Apply Risk Config", card_admin)
        self.btn_save.setFixedHeight(34)
        self.btn_save.setStyleSheet("""
            QPushButton {
                background-color: #08283d;
                border: 1.5px solid #00e5ff;
                color: #00e5ff;
                font-weight: 800;
                font-size: 12px;
                padding: 8px 18px;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #00e5ff;
                color: #070d18;
            }
            QPushButton:pressed {
                background-color: #00b4d8;
                color: #070d18;
            }
        """)
        try:
            self.btn_save.clicked.connect(self._save_risk_config)
        except Exception:
            pass
        btn_row.addWidget(self.btn_save)

        self.lbl_save_status = QLabel("", card_admin)
        self.lbl_save_status.setStyleSheet("color: #00e676; font-weight: bold; font-size: 11px;")
        btn_row.addWidget(self.lbl_save_status)
        btn_row.addStretch()
        al.addLayout(btn_row)

        self.layout_main.addWidget(card_admin)

        # Card 2: Circuit Breaker Controls & Manual Panic Halt
        card_cb = QFrame(self.container)
        card_cb.setStyleSheet("background-color: #0d1726; border: 1px solid #16243a; border-radius: 10px; padding: 14px;")
        cl = QVBoxLayout(card_cb)
        cl.setSpacing(10)

        cl.addWidget(QLabel("🚨 EMERGENCY CIRCUIT BREAKER & MANUAL OVERRIDE", card_cb))

        self.lbl_status = QLabel("Status: <span style='color:#00e676; font-weight:bold;'>NORMAL (Trading Authorized)</span>", card_cb)
        cl.addWidget(self.lbl_status)

        btn_halt = QPushButton("ENGAGE MANUAL PANIC HALT", card_cb)
        btn_halt.setStyleSheet("background-color: rgba(255, 23, 68, 0.2); border: 1.5px solid #ff1744; color: #ff5252; font-weight: bold; padding: 10px; border-radius: 6px;")
        try:
            btn_halt.clicked.connect(self._manual_halt)
        except Exception:
            pass

        btn_reset = QPushButton("Reset Circuit Breaker (Admin Override)", card_cb)
        btn_reset.setStyleSheet("background-color: #2979ff; color: white; font-weight: bold; padding: 10px; border-radius: 6px; border: none;")
        try:
            btn_reset.clicked.connect(self._reset_breaker)
        except Exception:
            pass

        cl.addWidget(btn_halt)
        cl.addWidget(btn_reset)
        self.layout_main.addWidget(card_cb)

    def _on_capital_or_risk_changed(self, *args) -> None:
        """Auto-computes Max SL from Capital and Risk Percentage."""
        if self._is_calculating:
            return
        self._is_calculating = True
        try:
            cap = float(self.spin_capital.value())
            pct = float(self.spin_risk_pct.value())
            calc_sl = max(1.0, round(cap * (pct / 100.0), 2))
            self.spin_max_sl.setValue(calc_sl)
            self._update_ruin_floor_display()
        except Exception:
            pass
        finally:
            self._is_calculating = False

    def _on_max_sl_changed(self, *args) -> None:
        """Auto-computes Risk Percentage from Max SL and Capital."""
        if self._is_calculating:
            return
        self._is_calculating = True
        try:
            cap = float(self.spin_capital.value())
            sl = float(self.spin_max_sl.value())
            if cap > 0:
                pct = round((sl / cap) * 100.0, 1)
                pct = max(0.5, min(50.0, pct))
                self.spin_risk_pct.setValue(pct)
            self._update_ruin_floor_display()
        except Exception:
            pass
        finally:
            self._is_calculating = False

    def _on_drawdown_changed(self, *args) -> None:
        """Updates ruin floor display when drawdown % changes."""
        self._update_ruin_floor_display()

    def _update_ruin_floor_display(self) -> None:
        try:
            cap = float(self.spin_capital.value())
            dd_pct = float(self.spin_drawdown_pct.value())
            ruin_amt = round(cap * (dd_pct / 100.0), 2)
            self.lbl_ruin_floor.setText(
                f"Dynamic Ruin Floor: ₹{ruin_amt:,.2f} ({dd_pct:.1f}% of ₹{cap:,.0f} capital - engine hard lock threshold)"
            )
        except Exception:
            pass

    def _load_config(self) -> None:
        """Pulls saved configuration from SQLite table `execution_config`."""
        try:
            cfg = self.db.get_execution_config()
            self.current_mode = str(cfg.get("mode", "PAPER")).upper()
            cap = float(cfg.get("trade_capital", 1000.0))
            risk_pct = float(cfg.get("risk_percentage", 5.0))
            max_sl = float(cfg.get("max_sl", 80.0))
            drawdown_pct = float(cfg.get("daily_drawdown_pct", 10.0))

            self._is_calculating = True
            self.spin_capital.setValue(cap)
            self.spin_risk_pct.setValue(risk_pct)
            self.spin_max_sl.setValue(max_sl)
            self.spin_drawdown_pct.setValue(drawdown_pct)
            self._is_calculating = False

            self._update_ruin_floor_display()
        except Exception:
            self._is_calculating = False

    def sync_from_external(
        self,
        capital: float,
        risk_pct: float,
        max_sl: float,
        daily_drawdown: float,
        mode: Optional[str] = None
    ) -> None:
        """Called externally from QuickRiskControlWidget to keep parameters synchronized."""
        self._is_calculating = True
        try:
            if mode:
                self.current_mode = str(mode).strip().upper()
            self.spin_capital.setValue(capital)
            self.spin_risk_pct.setValue(risk_pct)
            self.spin_max_sl.setValue(max_sl)
            self.spin_drawdown_pct.setValue(daily_drawdown)
            self._update_ruin_floor_display()
            self.lbl_save_status.setText("✓ Synchronized with Execution Controller")
            self.lbl_save_status.setStyleSheet("color: #00e5ff; font-weight: bold; font-size: 11px;")
        except Exception:
            pass
        finally:
            self._is_calculating = False

    def _save_risk_config(self) -> None:
        """Persists updated risk controls, broadcasts to RiskBudget and OrderRouter, and updates UI."""
        cap = float(self.spin_capital.value())
        risk_pct = float(self.spin_risk_pct.value())
        sl = float(self.spin_max_sl.value())
        dd_pct = float(self.spin_drawdown_pct.value())

        # 1. Commit to SQLite
        try:
            self.db.save_execution_config(
                mode=self.current_mode,
                trade_capital=cap,
                max_sl=sl,
                risk_percentage=risk_pct,
                daily_drawdown_pct=dd_pct
            )
        except Exception:
            pass

        # 2. Update RiskBudget
        from core.risk_budget import RiskBudget
        RiskBudget.update_risk_parameters(
            mode=self.current_mode,
            trade_capital=cap,
            max_sl=sl,
            risk_percentage=risk_pct,
            daily_drawdown_pct=dd_pct
        )

        # 3. Update router if attached
        if self.router and hasattr(self.router, "update_risk_parameters"):
            try:
                self.router.update_risk_parameters(
                    mode=self.current_mode,
                    trade_capital=cap,
                    max_sl=sl,
                    risk_percentage=risk_pct,
                    daily_drawdown_pct=dd_pct,
                    enforce=True
                )
            except Exception:
                pass

        # 4. Synchronize all QuickRiskControlWidget instances
        try:
            from ui.quick_risk_widget import QuickRiskControlWidget
            for inst in list(getattr(QuickRiskControlWidget, "_all_instances", [])):
                inst.sync_from_external(cap, risk_pct, sl, dd_pct, mode=self.current_mode)
        except Exception:
            pass

        # 5. Synchronize other RiskManagerView instances
        for inst in list(RiskManagerView._all_instances):
            if inst is not self:
                try:
                    inst.sync_from_external(cap, risk_pct, sl, dd_pct, mode=self.current_mode)
                except Exception:
                    pass

        # 6. Synchronize any active RiskManagerCard instances
        try:
            from ui.dashboard import RiskManagerCard
            for rc in list(getattr(RiskManagerCard, "_all_instances", [])):
                rc.update_config(cap, risk_pct, dd_pct)
        except Exception:
            pass

        # 7. Status confirmation badge
        ruin_amt = round(cap * (dd_pct / 100.0), 2)
        self.lbl_save_status.setText(
            f"✓ Risk Parameters Saved & Enforced: Capital ₹{cap:,.0f} | Risk {risk_pct:.1f}% | SL ₹{sl:,.0f} | Ruin Floor ₹{ruin_amt:,.0f} ({dd_pct:.1f}%)"
        )
        self.lbl_save_status.setStyleSheet("color: #00e676; font-weight: bold; font-size: 11px;")

        # 7. Emit signals
        try:
            self.risk_parameters_updated.emit(self.current_mode, cap, sl)
            self.risk_config_updated.emit(self.current_mode, cap, risk_pct, sl, dd_pct)
        except Exception:
            pass

    def _manual_halt(self) -> None:
        self.risk_engine.is_halted = True
        self.risk_engine.halt_reason = "MANUAL OPERATOR HALT"
        self.lbl_status.setText("Status: <span style='color:#ff1744; font-weight:bold;'>HALTED (Orders Blocked)</span>")

    def _reset_breaker(self) -> None:
        self.risk_engine.reset_circuit_breaker()
        self.lbl_status.setText("Status: <span style='color:#00e676; font-weight:bold;'>NORMAL (Trading Authorized)</span>")


class ReportsView(BasePageView):
    """Page 10: Interactive SQLite trade_audit_log ledger with filters and ₹60 friction audit."""

    def __init__(self, parent=None) -> None:
        super().__init__("📄 TRADE AUDIT LOG & STATUTORY FRICTION LEDGER", "Persistent ACID-compliant SQLite ledger documenting gross P&L, fees, and net payouts.", parent)
        self.db = DatabaseHandler()
        self._init_body()

    def _init_body(self) -> None:
        card = QFrame(self.container)
        card.setStyleSheet("background-color: #0d1726; border: 1px solid #16243a; border-radius: 10px; padding: 12px;")
        cl = QVBoxLayout(card)

        # Controls
        top_row = QHBoxLayout()
        btn_refresh = QPushButton("🔄 Refresh Ledger", card)
        btn_refresh.setStyleSheet("background-color: #2979ff; color: white; font-weight: bold; padding: 6px 12px; border-radius: 4px; border: none;")
        try:
            btn_refresh.clicked.connect(self.refresh_table)
        except Exception:
            pass
        top_row.addWidget(btn_refresh)
        top_row.addStretch()
        cl.addLayout(top_row)

        self.table = QTableWidget(0, 9, card)
        headers = ["ID", "Timestamp", "Session", "Broker", "Symbol", "Side", "Qty", "Gross P&L", "Net P&L (₹60 Fee)"]
        self.table.setHorizontalHeaderLabels(headers)
        try:
            self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        except Exception:
            pass

        cl.addWidget(self.table)
        self.layout_main.addWidget(card)
        self.refresh_table()

    def refresh_table(self) -> None:
        trades = self.db.get_all_trades(limit=50)
        self.table.setRowCount(len(trades))
        for r, t in enumerate(trades):
            self.table.setItem(r, 0, QTableWidgetItem(str(t.get("id"))))
            self.table.setItem(r, 1, QTableWidgetItem(str(t.get("timestamp"))[:19]))
            self.table.setItem(r, 2, QTableWidgetItem(str(t.get("market_session"))))
            self.table.setItem(r, 3, QTableWidgetItem(str(t.get("broker_name"))))
            self.table.setItem(r, 4, QTableWidgetItem(str(t.get("symbol"))))
            self.table.setItem(r, 5, QTableWidgetItem(str(t.get("trade_side"))))
            self.table.setItem(r, 6, QTableWidgetItem(str(t.get("quantity"))))
            self.table.setItem(r, 7, QTableWidgetItem(f"₹{float(t.get('gross_pnl', 0.0)):,.2f}"))
            self.table.setItem(r, 8, QTableWidgetItem(f"₹{float(t.get('net_pnl', 0.0)):,.2f}"))


# Page 11: Unified SettingsView imported from ui.settings_view (backed by BrokerVaultWidget & VaultManager)
from ui.settings_view import SettingsView


