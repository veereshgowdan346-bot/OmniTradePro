#!/usr/bin/env python3
"""
OmniTradePro - Order Execution & Pre-Trade Risk Control Panel
Platform: Windows 10/11 64-bit | Python 3.10+
Provides real-time order dispatch, mathematical risk budget badging,
PAPER / LIVE mode switching, and active open positions tracking.
"""

from typing import Optional, Dict, Any, List

try:
    from PySide6.QtWidgets import (
        QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
        QPushButton, QComboBox, QSpinBox, QDoubleSpinBox,
        QTableWidget, QTableWidgetItem, QHeaderView, QFrame, QMessageBox
    )
    from PySide6.QtCore import Qt, Signal
except ImportError:
    # Graceful shim for environments without PySide6
    class QWidget:
        def __init__(self, parent=None): pass
        def setStyleSheet(self, s): pass
    class QVBoxLayout:
        def __init__(self, *args): pass
        def addWidget(self, w): pass
        def addLayout(self, l): pass
        def addStretch(self, *args): pass
        def setContentsMargins(self, *args): pass
        def setSpacing(self, s): pass
    class QHBoxLayout(QVBoxLayout): pass
    class QLabel:
        def __init__(self, text="", parent=None): pass
        def setText(self, t): pass
        def setStyleSheet(self, s): pass
    class QLineEdit:
        def __init__(self, parent=None): self._text = ""
        def setText(self, t): self._text = t
        def text(self): return self._text
        def setPlaceholderText(self, p): pass
    class QPushButton:
        def __init__(self, text="", parent=None): pass
        def setStyleSheet(self, s): pass
        def clicked(self): pass
    class QComboBox:
        def __init__(self, parent=None): self._items = []
        def addItems(self, items): self._items.extend(items)
        def currentText(self): return self._items[0] if self._items else ""
    class QSpinBox:
        def __init__(self, parent=None): self._val = 1
        def setRange(self, mn, mx): pass
        def setValue(self, v): self._val = v
        def value(self): return self._val
    class QDoubleSpinBox:
        def __init__(self, parent=None): self._val = 0.0
        def setRange(self, mn, mx): pass
        def setDecimals(self, d): pass
        def setValue(self, v): self._val = v
        def value(self): return self._val
    class QTableWidget:
        def __init__(self, r, c, parent=None): self._rows = r
        def setHorizontalHeaderLabels(self, l): pass
        def horizontalHeader(self): return self
        def setSectionResizeMode(self, m): pass
        def setRowCount(self, r): self._rows = r
        def rowCount(self): return self._rows
        def setItem(self, r, c, item): pass
        def setCellWidget(self, r, c, w): pass
    class QTableWidgetItem:
        def __init__(self, text=""): pass
    class QHeaderView:
        Stretch = 1
    class QFrame:
        def __init__(self, parent=None): pass
        def setProperty(self, k, v): pass
        def setStyleSheet(self, s): pass
    class QMessageBox:
        @staticmethod
        def information(p, t, m): pass
        @staticmethod
        def warning(p, t, m): pass
    class Signal:
        def __init__(self, *types): pass
        def connect(self, cb): pass
        def emit(self, *args): pass
    class Qt:
        AlignCenter = 0x0004

from core.risk_budget import RiskBudget
from core.order_router import OrderRouter
from core.risk_engine import RiskEngine


class OrderPanel(QWidget):
    """
    Real-time order entry, risk gating, and position tracking panel.
    """
    order_executed = Signal(dict)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.router = OrderRouter()
        self.risk_engine = RiskEngine()
        self._init_ui()

    def _init_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(10)

        # Header Title
        title = QLabel("ORDER EXECUTION & RISK GATEWAY", self)
        title.setStyleSheet("font-size: 14px; font-weight: bold; color: #00e5ff;")
        main_layout.addWidget(title)

        # Form Container
        form_frame = QFrame(self)
        form_frame.setStyleSheet("background-color: rgba(22, 30, 48, 0.65); border: 1px solid rgba(255, 255, 255, 0.12); border-radius: 6px; padding: 10px;")
        form_layout = QVBoxLayout(form_frame)
        form_layout.setSpacing(8)

        # Row 1: Symbol & Exchange
        r1 = QHBoxLayout()
        r1.addWidget(QLabel("Symbol:", self))
        self.sym_edit = QLineEdit(self)
        self.sym_edit.setText("RELIANCE.NS")
        r1.addWidget(self.sym_edit)

        r1.addWidget(QLabel("Exchange:", self))
        self.exch_combo = QComboBox(self)
        self.exch_combo.addItems(["NSE", "BSE", "MCX"])
        r1.addWidget(self.exch_combo)
        form_layout.addLayout(r1)

        # Row 2: Side & Mode
        r2 = QHBoxLayout()
        r2.addWidget(QLabel("Side:", self))
        self.side_combo = QComboBox(self)
        self.side_combo.addItems(["BUY", "SELL"])
        r2.addWidget(self.side_combo)

        r2.addWidget(QLabel("Mode:", self))
        self.mode_combo = QComboBox(self)
        self.mode_combo.addItems(["PAPER", "LIVE"])
        r2.addWidget(self.mode_combo)
        form_layout.addLayout(r2)

        # Row 3: Product & Order Type
        r3 = QHBoxLayout()
        r3.addWidget(QLabel("Product:", self))
        self.prod_combo = QComboBox(self)
        self.prod_combo.addItems(["INTRADAY", "DELIVERY", "MARGIN"])
        r3.addWidget(self.prod_combo)

        r3.addWidget(QLabel("Type:", self))
        self.type_combo = QComboBox(self)
        self.type_combo.addItems(["MARKET", "LIMIT", "STOPLOSS_LIMIT"])
        r3.addWidget(self.type_combo)
        form_layout.addLayout(r3)

        # Row 4: Quantity & Price
        r4 = QHBoxLayout()
        r4.addWidget(QLabel("Quantity:", self))
        self.qty_spin = QSpinBox(self)
        self.qty_spin.setRange(1, 100000)
        self.qty_spin.setValue(10)
        r4.addWidget(self.qty_spin)

        r4.addWidget(QLabel("Price (₹):", self))
        self.price_spin = QDoubleSpinBox(self)
        self.price_spin.setRange(0.05, 500000.0)
        self.price_spin.setDecimals(2)
        self.price_spin.setValue(2500.0)
        r4.addWidget(self.price_spin)
        form_layout.addLayout(r4)

        # Row 5: Stop-Loss & Target
        r5 = QHBoxLayout()
        r5.addWidget(QLabel("Stop-Loss (₹):", self))
        self.sl_spin = QDoubleSpinBox(self)
        self.sl_spin.setRange(0.0, 500000.0)
        self.sl_spin.setDecimals(2)
        self.sl_spin.setValue(2480.0)
        r5.addWidget(self.sl_spin)

        r5.addWidget(QLabel("Target (₹):", self))
        self.tp_spin = QDoubleSpinBox(self)
        self.tp_spin.setRange(0.0, 500000.0)
        self.tp_spin.setDecimals(2)
        self.tp_spin.setValue(2540.0)
        r5.addWidget(self.tp_spin)
        form_layout.addLayout(r5)

        # Pre-Trade Compliance Status Badge
        self.risk_badge = QLabel("Risk Status: Compliant (1:2 R:R | ₹60 Friction Cleared)", self)
        self.risk_badge.setStyleSheet("color: #00e676; font-weight: bold; font-size: 11px;")
        form_layout.addWidget(self.risk_badge)

        # Submit Button
        self.btn_submit = QPushButton("DISPATCH ORDER", self)
        self.btn_submit.setStyleSheet("background-color: #00c853; color: white; font-weight: bold; padding: 10px; font-size: 13px;")
        try:
            self.btn_submit.clicked.connect(self._on_submit_order)
        except Exception:
            pass
        form_layout.addWidget(self.btn_submit)

        main_layout.addWidget(form_frame)

        # Active Positions Table
        main_layout.addWidget(QLabel("OPEN POSITIONS & EXECUTION LOG", self))
        self.pos_table = QTableWidget(0, 7, self)
        self.pos_table.setHorizontalHeaderLabels(["ID", "Symbol", "Side", "Qty", "Entry (₹)", "Status", "Action"])
        try:
            self.pos_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        except Exception:
            pass
        main_layout.addWidget(self.pos_table)

    def _on_submit_order(self) -> None:
        """Validates risk budget and executes trade via OrderRouter."""
        sym = self.sym_edit.text().strip().upper()
        side = self.side_combo.currentText()
        mode = self.mode_combo.currentText()
        qty = self.qty_spin.value()
        price = self.price_spin.value()
        sl = self.sl_spin.value()
        tp = self.tp_spin.value()

        # 1. Evaluate Risk Budget hurdle
        budget_res = RiskBudget.calculate_position_size(
            capital_inr=10000.0,
            entry_price=price,
            stop_loss=sl,
            target_price=tp
        )

        if not budget_res["can_execute"]:
            self.risk_badge.setText(f"BLOCKED: {budget_res['reason']}")
            self.risk_badge.setStyleSheet("color: #ff3d71; font-weight: bold;")
            QMessageBox.warning(self, "Risk Rejection", budget_res["reason"])
            return

        # 2. Execute order via OrderRouter
        try:
            fill = self.router.execute_order(
                symbol=sym,
                side=side,
                quantity=qty,
                price=price,
                stop_loss=sl,
                target_price=tp,
                mode=mode
            )
            self.risk_badge.setText(f"FILLED #{fill['trade_id']}: ₹{fill['executed_price']:.2f} ({mode})")
            self.risk_badge.setStyleSheet("color: #00e676; font-weight: bold;")
            self._refresh_positions()
        except Exception as exc:
            self.risk_badge.setText(f"EXECUTION ERROR: {str(exc)}")
            self.risk_badge.setStyleSheet("color: #ff3d71; font-weight: bold;")

    def _refresh_positions(self) -> None:
        """Refreshes positions table from router state."""
        positions = self.router.get_open_positions()
        self.pos_table.setRowCount(len(positions))

        for row, pos in enumerate(positions):
            tid = str(pos["trade_id"])
            self.pos_table.setItem(row, 0, QTableWidgetItem(tid))
            self.pos_table.setItem(row, 1, QTableWidgetItem(pos["symbol"]))
            self.pos_table.setItem(row, 2, QTableWidgetItem(pos["side"]))
            self.pos_table.setItem(row, 3, QTableWidgetItem(str(pos["quantity"])))
            self.pos_table.setItem(row, 4, QTableWidgetItem(f"₹{pos['entry_price']:.2f}"))
            self.pos_table.setItem(row, 5, QTableWidgetItem(pos["status"]))

            btn_exit = QPushButton("Square-Off", self)
            btn_exit.setStyleSheet("background-color: rgba(213, 0, 0, 0.4); color: #ff3d71; font-weight: bold;")
            # Previously an orphan button: now closes the position at its real
            # live LTP (never a fabricated exit price).
            try:
                btn_exit.clicked.connect(
                    lambda checked=False, t=pos["trade_id"], sym=pos["symbol"]: self._square_off(t, sym)
                )
            except Exception:
                pass
            self.pos_table.setCellWidget(row, 6, btn_exit)

    def _square_off(self, trade_id, symbol: str) -> None:
        """One-click square-off using the genuine cached tick price."""
        ltp = None
        try:
            from brokers.stream_worker import BrokerStreamWorker
            tick = BrokerStreamWorker.get_latest_tick(symbol)
            if tick:
                ltp = float(tick.get("ltp", 0.0)) or None
        except Exception:
            ltp = None
        if not ltp:
            try:
                self.risk_badge.setText(f"SQUARE-OFF BLOCKED: no live quote for {symbol}")
                self.risk_badge.setStyleSheet("color: #ff3d71; font-weight: bold;")
            except Exception:
                pass
            return
        try:
            self.router.close_position(int(trade_id), float(ltp))
            self._refresh_positions()
        except Exception as exc:
            try:
                self.risk_badge.setText(f"SQUARE-OFF ERROR: {exc}")
                self.risk_badge.setStyleSheet("color: #ff3d71; font-weight: bold;")
            except Exception:
                pass
