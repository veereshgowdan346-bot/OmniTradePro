#!/usr/bin/env python3
"""
OmniTradePro - Executive Dark-Mode Glassmorphic Execution Mode & Risk Controller Widget
Platform: Windows 10/11 64-bit | Python 3.10+

Compact front-page control block providing:
1. Seamless Dual Mode Pill Switch: [ 📄 PAPER ] vs [ 🔴 LIVE ]
2. Trade Capital Limit SpinBox: Min ₹500, Max ₹5,00,000, Default ₹1,000, Step ₹500
3. Max Stop-Loss Limit SpinBox: Min ₹20, Max ₹10,000, Default ₹80, Step ₹10
4. [ 🔒 Apply & Lock Rules ] with visual confirmation badge and global parameter broadcast
5. Persistent SQLite storage in `execution_config` and synchronized instances
"""

from typing import Optional, Dict, Any, List
from datetime import datetime, timezone

try:
    from PySide6.QtWidgets import (
        QFrame, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
        QPushButton, QDoubleSpinBox, QButtonGroup, QSizePolicy
    )
    from PySide6.QtCore import Qt, Signal, QTimer
    from PySide6.QtGui import QFont
except ImportError:
    # High-fidelity headless shims
    class QWidget:
        def __init__(self, parent=None): pass
        def setStyleSheet(self, s): pass
        def setFixedSize(self, w, h): pass
        def setFixedWidth(self, w): pass
        def setFixedHeight(self, h): pass
        def setProperty(self, k, v): pass
        def setSizePolicy(self, *args): pass
    class QFrame(QWidget):
        NoFrame = 0
        def __init__(self, parent=None): pass
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
    class QPushButton:
        def __init__(self, text="", parent=None):
            self.text = text
            self._checked = False
            self.clicked = Signal()
        def setText(self, t): self.text = t
        def setStyleSheet(self, s): pass
        def setCheckable(self, b): pass
        def setChecked(self, b): self._checked = bool(b)
        def isChecked(self): return self._checked
        def setProperty(self, k, v): pass
        def setFixedWidth(self, w): pass
        def setFixedHeight(self, h): pass
    class QDoubleSpinBox:
        def __init__(self, parent=None):
            self._val = 0.0
            self._min = 0.0
            self._max = 1000000.0
            self._step = 1.0
            self._prefix = ""
            self._suffix = ""
            self._decimals = 2
            self.valueChanged = Signal()
        def setRange(self, mn, mx): self._min = mn; self._max = mx
        def setSingleStep(self, s): self._step = s
        def setPrefix(self, p): self._prefix = p
        def setSuffix(self, s): self._suffix = s
        def setDecimals(self, d): self._decimals = d
        def setValue(self, v):
            self._val = float(v)
            try:
                self.valueChanged.emit(self._val)
            except Exception:
                pass
        def value(self): return self._val
        def setStyleSheet(self, s): pass
        def setFixedHeight(self, h): pass
        def setFixedWidth(self, w): pass
        def setFixedSize(self, w, h): pass
    class QButtonGroup:
        def __init__(self, parent=None): self._btns = []
        def addButton(self, b): self._btns.append(b)
    class Signal:
        def __init__(self, *args):
            self._callbacks = []
        def connect(self, f):
            self._callbacks.append(f)
        def emit(self, *args):
            for cb in list(self._callbacks):
                try:
                    cb(*args)
                except Exception:
                    pass
    class Qt:
        AlignCenter = 0x0004
        AlignLeft = 0x0001
        AlignRight = 0x0002

from database.db_manager import DatabaseManager
from core.risk_budget import RiskBudget


class QuickRiskControlWidget(QFrame):
    """
    Compact Executive Front-Facing Execution Mode & Risk Controller Widget.
    Designed for embedding in LeftSidebar or on Dashboard next to Broker Control.
    """
    mode_changed = Signal(str)
    risk_parameters_updated = Signal(str, float, float)
    risk_config_updated = Signal(str, float, float, float, float)
    _all_instances: List["QuickRiskControlWidget"] = []

    def __init__(self, parent=None, router=None) -> None:
        super().__init__(parent)
        QuickRiskControlWidget._all_instances.append(self)
        self.router = router
        self.db = DatabaseManager()
        self.current_mode: str = "PAPER"
        self._daily_drawdown_pct: float = 10.0
        self._is_calculating: bool = False
        self._init_ui()
        self._load_config()

    def _init_ui(self) -> None:
        self.setStyleSheet("""
            QuickRiskControlWidget {
                background-color: #0b1424;
                border: 1px solid #142236;
                border-radius: 8px;
            }
        """)
        # Compact styling: ~195px height to comfortably fit 3 inputs + mode pills + button
        self.setFixedHeight(195)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 5, 8, 5)
        layout.setSpacing(3)

        # 1. Title Header: ⚡ EXECUTION & RISK CONTROLLER
        self.lbl_title = QLabel("⚡ EXECUTION & RISK", self)
        self.lbl_title.setAlignment(Qt.AlignCenter)
        self.lbl_title.setStyleSheet("""
            color: #00e5ff;
            font-size: 10px;
            font-weight: 800;
            letter-spacing: 0.5px;
            font-family: 'Segoe UI', Inter, sans-serif;
        """)
        layout.addWidget(self.lbl_title)

        # 2. Dual Mode Toggle Switch: [ 📄 PAPER ] vs [ 🔴 LIVE ]
        mode_layout = QHBoxLayout()
        mode_layout.setSpacing(4)

        self.btn_paper = QPushButton("📄 PAPER", self)
        self.btn_paper.setCheckable(True)
        self.btn_paper.setFixedHeight(22)

        self.btn_live = QPushButton("🔴 LIVE", self)
        self.btn_live.setCheckable(True)
        self.btn_live.setFixedHeight(22)

        try:
            self.btn_paper.clicked.connect(lambda: self._on_mode_selected("PAPER"))
            self.btn_live.clicked.connect(lambda: self._on_mode_selected("LIVE"))
        except Exception:
            pass

        mode_layout.addWidget(self.btn_paper)
        mode_layout.addWidget(self.btn_live)
        layout.addLayout(mode_layout)

        # 3. Input 1 - Capital per Trade
        row_cap = QHBoxLayout()
        row_cap.setSpacing(2)
        lbl_cap = QLabel("Cap:", self)
        lbl_cap.setStyleSheet("color: #94a3b8; font-size: 9px; font-weight: 600;")
        lbl_cap.setFixedWidth(28)

        self.spin_capital = QDoubleSpinBox(self)
        self.spin_capital.setRange(500.0, 1000000.0)
        self.spin_capital.setSingleStep(500.0)
        self.spin_capital.setValue(1000.0)
        self.spin_capital.setPrefix("₹")
        self.spin_capital.setDecimals(0)
        self.spin_capital.setFixedHeight(20)
        self.spin_capital.setStyleSheet("""
            QDoubleSpinBox {
                background-color: #070d18;
                border: 1px solid #1e293b;
                border-radius: 4px;
                color: #f8fafc;
                font-family: 'Consolas', monospace;
                font-size: 10px;
                padding: 1px 4px;
            }
        """)
        row_cap.addWidget(lbl_cap)
        row_cap.addWidget(self.spin_capital)
        layout.addLayout(row_cap)

        # 4. Input 2 - Max Risk / Loss Percentage per Trade (%)
        row_risk = QHBoxLayout()
        row_risk.setSpacing(2)
        lbl_risk = QLabel("Risk:", self)
        lbl_risk.setStyleSheet("color: #94a3b8; font-size: 9px; font-weight: 600;")
        lbl_risk.setFixedWidth(28)

        self.spin_risk_pct = QDoubleSpinBox(self)
        self.spin_risk_pct.setRange(0.5, 50.0)
        self.spin_risk_pct.setSingleStep(0.5)
        self.spin_risk_pct.setValue(5.0)
        self.spin_risk_pct.setSuffix(" %")
        self.spin_risk_pct.setDecimals(1)
        self.spin_risk_pct.setFixedHeight(20)
        self.spin_risk_pct.setStyleSheet("""
            QDoubleSpinBox {
                background-color: #070d18;
                border: 1px solid #1e293b;
                border-radius: 4px;
                color: #00e5ff;
                font-family: 'Consolas', monospace;
                font-size: 10px;
                font-weight: bold;
                padding: 1px 4px;
            }
        """)
        row_risk.addWidget(lbl_risk)
        row_risk.addWidget(self.spin_risk_pct)
        layout.addLayout(row_risk)

        # 5. Input 3 - Max Stop-Loss Limit
        row_sl = QHBoxLayout()
        row_sl.setSpacing(2)
        lbl_sl = QLabel("SL:", self)
        lbl_sl.setStyleSheet("color: #94a3b8; font-size: 9px; font-weight: 600;")
        lbl_sl.setFixedWidth(28)

        self.spin_max_sl = QDoubleSpinBox(self)
        self.spin_max_sl.setRange(10.0, 50000.0)
        self.spin_max_sl.setSingleStep(10.0)
        self.spin_max_sl.setValue(50.0)
        self.spin_max_sl.setPrefix("₹")
        self.spin_max_sl.setDecimals(0)
        self.spin_max_sl.setFixedHeight(20)
        self.spin_max_sl.setStyleSheet("""
            QDoubleSpinBox {
                background-color: #070d18;
                border: 1px solid #1e293b;
                border-radius: 4px;
                color: #f8fafc;
                font-family: 'Consolas', monospace;
                font-size: 10px;
                padding: 1px 4px;
            }
        """)
        row_sl.addWidget(lbl_sl)
        row_sl.addWidget(self.spin_max_sl)
        layout.addLayout(row_sl)

        # Two-way mutual auto-calculation connections
        try:
            self.spin_capital.valueChanged.connect(self._on_capital_or_risk_changed)
            self.spin_risk_pct.valueChanged.connect(self._on_capital_or_risk_changed)
            self.spin_max_sl.valueChanged.connect(self._on_max_sl_changed)
        except Exception:
            pass

        # 6. Action Button: [ 🔒 Apply & Lock Rules ]
        self.btn_apply = QPushButton("🔒 Apply & Lock", self)
        self.btn_apply.setFixedHeight(24)
        self.btn_apply.setStyleSheet("""
            QPushButton {
                background-color: #064e3b;
                border: 1px solid #059669;
                border-radius: 4px;
                color: #34d399;
                font-weight: 700;
                font-size: 10px;
            }
            QPushButton:hover {
                background-color: #059669;
                color: #ffffff;
            }
            QPushButton:pressed {
                background-color: #047857;
            }
        """)
        try:
            self.btn_apply.clicked.connect(self._on_apply_clicked)
        except Exception:
            pass
        layout.addWidget(self.btn_apply)

        # 7. Status Confirmation Badge
        self.lbl_status = QLabel("✓ Ready", self)
        self.lbl_status.setAlignment(Qt.AlignCenter)
        self.lbl_status.setStyleSheet("color: #64748b; font-size: 8px; font-weight: 600;")
        layout.addWidget(self.lbl_status)

        self._refresh_mode_ui()

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
                calc_pct = round((sl / cap) * 100.0, 1)
                calc_pct = max(0.5, min(50.0, calc_pct))
                self.spin_risk_pct.setValue(calc_pct)
        except Exception:
            pass
        finally:
            self._is_calculating = False

    def _on_mode_selected(self, mode: str) -> None:
        """Updates internal selection and button visual pill highlighting."""
        self.current_mode = mode.upper()
        self._refresh_mode_ui()
        try:
            self.mode_changed.emit(self.current_mode)
        except Exception:
            pass

    def _refresh_mode_ui(self) -> None:
        """Applies active glow border vs inactive dark style."""
        if self.current_mode == "PAPER":
            self.btn_paper.setStyleSheet("""
                QPushButton {
                    background-color: rgba(16, 185, 129, 0.18);
                    border: 1px solid #10b981;
                    border-radius: 4px;
                    color: #10b981;
                    font-weight: 800;
                    font-size: 9px;
                }
            """)
            self.btn_live.setStyleSheet("""
                QPushButton {
                    background-color: #070d18;
                    border: 1px solid #1e293b;
                    border-radius: 4px;
                    color: #64748b;
                    font-weight: 600;
                    font-size: 9px;
                }
            """)
        else:
            self.btn_paper.setStyleSheet("""
                QPushButton {
                    background-color: #070d18;
                    border: 1px solid #1e293b;
                    border-radius: 4px;
                    color: #64748b;
                    font-weight: 600;
                    font-size: 9px;
                }
            """)
            self.btn_live.setStyleSheet("""
                QPushButton {
                    background-color: rgba(239, 68, 68, 0.22);
                    border: 1px solid #ef4444;
                    border-radius: 4px;
                    color: #ef4444;
                    font-weight: 800;
                    font-size: 9px;
                }
            """)

    def _load_config(self) -> None:
        """Pulls saved configuration from SQLite table `execution_config`."""
        try:
            cfg = self.db.get_execution_config()
            self.current_mode = cfg.get("mode", "PAPER").upper()
            cap = float(cfg.get("trade_capital", 1000.0))
            risk_pct = float(cfg.get("risk_percentage", 5.0))
            max_sl = float(cfg.get("max_sl", 80.0))
            self._daily_drawdown_pct = float(cfg.get("daily_drawdown_pct", 10.0))

            self._is_calculating = True
            self.spin_capital.setValue(cap)
            self.spin_risk_pct.setValue(risk_pct)
            self.spin_max_sl.setValue(max_sl)
            self._is_calculating = False

            self._refresh_mode_ui()
            self.lbl_status.setText(f"✓ Locked: ₹{cap:,.0f} ({risk_pct:.1f}%) / SL ₹{max_sl:,.0f}")
            self.lbl_status.setStyleSheet("color: #10b981; font-size: 8px; font-weight: bold;")
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
        """Called externally to update widget state without re-triggering save loops."""
        self._is_calculating = True
        try:
            if mode:
                clean_mode = str(mode).strip().upper()
                if clean_mode in ("PAPER", "LIVE"):
                    self.current_mode = clean_mode
                    self._refresh_mode_ui()
            self.spin_capital.setValue(capital)
            self.spin_risk_pct.setValue(risk_pct)
            self.spin_max_sl.setValue(max_sl)
            self._daily_drawdown_pct = daily_drawdown
            badge_text = f"✓ Locked: ₹{capital:,.0f} ({risk_pct:.1f}%) / SL ₹{max_sl:,.0f}"
            self.lbl_status.setText(badge_text)
            self.lbl_status.setStyleSheet("color: #10b981; font-size: 8px; font-weight: bold;")
        except Exception:
            pass
        finally:
            self._is_calculating = False

    def _on_apply_clicked(self) -> None:
        """Commits updated rules to SQLite and broadcasts globally to RiskBudget and OrderRouter."""
        mode = self.current_mode
        capital = float(self.spin_capital.value())
        risk_pct = float(self.spin_risk_pct.value())
        max_sl = float(self.spin_max_sl.value())
        daily_drawdown = float(self._daily_drawdown_pct)

        # 1. Commit to SQLite
        try:
            self.db.save_execution_config(
                mode=mode,
                trade_capital=capital,
                max_sl=max_sl,
                risk_percentage=risk_pct,
                daily_drawdown_pct=daily_drawdown
            )
        except Exception:
            pass

        # 2. Global RiskBudget Broadcast
        RiskBudget.update_risk_parameters(
            mode=mode,
            trade_capital=capital,
            max_sl=max_sl,
            risk_percentage=risk_pct,
            daily_drawdown_pct=daily_drawdown
        )

        # 3. Router update if attached
        if self.router and hasattr(self.router, "update_risk_parameters"):
            try:
                self.router.update_risk_parameters(
                    mode=mode,
                    trade_capital=capital,
                    max_sl=max_sl,
                    risk_percentage=risk_pct,
                    daily_drawdown_pct=daily_drawdown,
                    enforce=True
                )
            except Exception:
                pass

        # 4. Update status badge
        badge_text = f"✓ Locked: ₹{capital:,.0f} ({risk_pct:.1f}%) / SL ₹{max_sl:,.0f}"
        self.lbl_status.setText(badge_text)
        self.lbl_status.setStyleSheet("color: #10b981; font-size: 8px; font-weight: bold;")

        # 5. Emit signal
        try:
            self.risk_parameters_updated.emit(mode, capital, max_sl)
            self.risk_config_updated.emit(mode, capital, risk_pct, max_sl, daily_drawdown)
        except Exception:
            pass

        # 6. Synchronize any other active widget instances
        for inst in list(QuickRiskControlWidget._all_instances):
            if inst is not self:
                try:
                    inst.sync_from_external(capital, risk_pct, max_sl, daily_drawdown, mode=mode)
                except Exception:
                    pass

        # 7. Synchronize any active RiskManagerView instances
        try:
            from ui.views import RiskManagerView
            for rm in list(getattr(RiskManagerView, "_all_instances", [])):
                rm.sync_from_external(capital, risk_pct, max_sl, daily_drawdown)
        except Exception:
            pass

        # 8. Synchronize any active RiskManagerCard instances
        try:
            from ui.dashboard import RiskManagerCard
            for rc in list(getattr(RiskManagerCard, "_all_instances", [])):
                rc.update_config(capital, risk_pct, daily_drawdown)
        except Exception:
            pass
