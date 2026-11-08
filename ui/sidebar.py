#!/usr/bin/env python3
"""
OmniTradePro - Sidebar Navigation & Risk Controller Integration
Platform: Windows 10/11 64-bit | Python 3.10+
Provides the vertical executive navigation sidebar embedded with the
compact front-page Execution Mode & Risk Controller Widget.
"""

from typing import Optional, List, Dict, Any

try:
    from PySide6.QtWidgets import (
        QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
        QFrame, QSizePolicy
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
        def setVisible(self, v): pass
        def setFixedWidth(self, w): pass
        def setFixedHeight(self, h): pass
        def setFixedSize(self, w, h): pass
    class QPushButton:
        def __init__(self, text="", parent=None): self.text = text
        def setStyleSheet(self, s): pass
        def setCheckable(self, b): pass
        def setChecked(self, b): pass
        def isChecked(self): return False
        def setProperty(self, k, v): pass
        def setFixedWidth(self, w): pass
        def setFixedHeight(self, h): pass
    class Signal:
        def __init__(self, *types): pass
        def connect(self, f): pass
        def emit(self, *args): pass
    class Qt:
        AlignCenter = 0x0004
        AlignLeft = 0x0001
        AlignRight = 0x0002

from ui.quick_risk_widget import QuickRiskControlWidget


class LeftSidebar(QFrame):
    """
    Vertical navigation sidebar with working QStackedWidget routing
    and embedded compact Execution Mode & Risk Controller widget.
    """
    nav_changed = Signal(int)

    NAV_ITEMS = [
        "⊞ Dashboard",
        "📈 Live Trading",
        "⚙ Trading Bots",
        "⚙ Strategies",
        "👁 Market Watch",
        "⚡ Auto Trade",
        "⏱ Backtest",
        "📊 Analytics",
        "💼 Portfolio",
        "🛡 Risk Manager",
        "📄 Reports",
        "⚙ Settings"
    ]

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setFixedWidth(160)
        self.setStyleSheet("""
            QFrame {
                background-color: #070d18;
                border-right: 1px solid #142236;
            }
        """)
        self.buttons: List[QPushButton] = []
        self.active_index: int = 0
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 8)
        layout.setSpacing(3)

        for idx, text in enumerate(self.NAV_ITEMS):
            btn = QPushButton(text, self)
            try:
                btn.clicked.connect(lambda checked=False, i=idx: self._on_btn_clicked(i))
            except Exception:
                pass
            layout.addWidget(btn)
            self.buttons.append(btn)

        self._refresh_styles()

        layout.addSpacing(6)

        # Embedded Compact Front-Page Execution & Risk Controller
        self.risk_controller = QuickRiskControlWidget(self)
        layout.addWidget(self.risk_controller)

        layout.addStretch()

        # Clean Institutional Executive System Badge
        brand_card = QFrame(self)
        brand_card.setStyleSheet("""
            QFrame {
                background-color: #0b1424;
                border: 1px solid #142236;
                border-radius: 6px;
                padding: 4px;
            }
        """)
        bc_layout = QVBoxLayout(brand_card)
        bc_layout.setContentsMargins(2, 2, 2, 2)
        bc_layout.setSpacing(1)
        lbl_v = QLabel("⚡ OmniTradePro", brand_card)
        lbl_v.setAlignment(Qt.AlignCenter)
        lbl_v.setStyleSheet("color: #00f0ff; font-size: 9px; font-weight: 800;")
        lbl_sub = QLabel("Institutional v5.0", brand_card)
        lbl_sub.setAlignment(Qt.AlignCenter)
        lbl_sub.setStyleSheet("color: #64748b; font-size: 8px;")
        bc_layout.addWidget(lbl_v)
        bc_layout.addWidget(lbl_sub)
        layout.addWidget(brand_card)

        # Invisible label for backward compatibility
        self.mascot_lbl = QLabel(self)
        self.mascot_lbl.setVisible(False)

        # Status Pill: '● System Online'
        status_pill = QLabel("● System Online", self)
        status_pill.setAlignment(Qt.AlignCenter)
        status_pill.setStyleSheet("""
            QLabel {
                background-color: rgba(0, 230, 118, 0.12);
                border: 1.5px solid #00e676;
                border-radius: 9px;
                color: #00e676;
                font-weight: 800;
                font-size: 10px;
                padding: 3px 4px;
            }
        """)
        layout.addWidget(status_pill)

    def _on_btn_clicked(self, index: int) -> None:
        self.set_active_index(index)
        try:
            self.nav_changed.emit(index)
        except Exception:
            pass

    def set_active_index(self, index: int) -> None:
        if 0 <= index < len(self.buttons):
            self.active_index = index
            self._refresh_styles()

    def _refresh_styles(self) -> None:
        for idx, btn in enumerate(self.buttons):
            if idx == self.active_index:
                btn.setStyleSheet("""
                    QPushButton {
                        background-color: rgba(0, 240, 255, 0.16);
                        border-left: 3px solid #00f0ff;
                        border-top: 1px solid #00f0ff;
                        border-right: 1px solid #00f0ff;
                        border-bottom: 1px solid #00f0ff;
                        border-radius: 6px;
                        color: #00f0ff;
                        font-weight: 800;
                        font-size: 11px;
                        padding: 6px 10px;
                        text-align: left;
                    }
                """)
            else:
                btn.setStyleSheet("""
                    QPushButton {
                        background-color: transparent;
                        border: 1px solid transparent;
                        border-radius: 6px;
                        color: #94a3b8;
                        font-weight: 600;
                        font-size: 11px;
                        padding: 6px 10px;
                        text-align: left;
                    }
                    QPushButton:hover {
                        background-color: #0d1726;
                        color: #f8fafc;
                        border: 1px solid #1e293b;
                    }
                """)
