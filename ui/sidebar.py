#!/usr/bin/env python3
"""
OmniTradePro — Elite Institutional Navigation Sidebar v5.0
Platform: Windows 10/11 64-bit | Python 3.10+
Provides the vertical executive navigation sidebar embedded with the
compact Execution Config & Risk Controller Widget.
Design: Webull / TradingView dark-mode aesthetic.
"""

from typing import Optional, List

# ── Headless shims (tests run without PySide6) ────────────────────────────────
try:
    from PySide6.QtWidgets import (
        QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
        QFrame, QSizePolicy, QSpacerItem
    )
    from PySide6.QtCore import Qt, Signal
    from PySide6.QtGui import QFont
except ImportError:
    class QWidget:
        def __init__(self, parent=None): pass
        def setStyleSheet(self, s): pass
        def setFixedSize(self, w, h): pass
        def setFixedWidth(self, w): pass
        def setFixedHeight(self, h): pass
        def setProperty(self, k, v): pass
        def setEnabled(self, b): pass
        def setSizePolicy(self, *args): pass
        def setVisible(self, v): pass

    class QFrame(QWidget):
        NoFrame = 0
        HLine = 4
        Sunken = 2
        def __init__(self, parent=None): pass
        def setFrameShape(self, s): pass
        def setFrameShadow(self, s): pass
        def setEnabled(self, b): pass
        def setSizePolicy(self, *args): pass

    class QVBoxLayout:
        def __init__(self, *args): pass
        def addWidget(self, w, *args): pass
        def addLayout(self, l, *args): pass
        def addStretch(self, *args): pass
        def addSpacing(self, n): pass
        def setContentsMargins(self, *args): pass
        def setSpacing(self, s): pass

    class QHBoxLayout(QVBoxLayout):
        pass

    class QSpacerItem:
        def __init__(self, *args): pass

    class _TextStr(str):
        def __call__(self): return str(self)

    class QLabel:
        def __init__(self, text="", parent=None):
            self.text = _TextStr(text)
        def setText(self, t): self.text = _TextStr(t)
        def setStyleSheet(self, s): pass
        def setAlignment(self, a): pass
        def setVisible(self, v): pass
        def setFixedWidth(self, w): pass
        def setFixedHeight(self, h): pass
        def setFixedSize(self, w, h): pass
        def setEnabled(self, b): pass
        def setSizePolicy(self, *args): pass
        def setWordWrap(self, b): pass

    class QPushButton:
        def __init__(self, text="", parent=None):
            self.text = text
        def setStyleSheet(self, s): pass
        def setCheckable(self, b): pass
        def setChecked(self, b): pass
        def isChecked(self): return False
        def setProperty(self, k, v): pass
        def setFixedWidth(self, w): pass
        def setFixedHeight(self, h): pass
        def setEnabled(self, b): pass
        def setSizePolicy(self, *args): pass

    class Signal:
        def __init__(self, *types): pass
        def connect(self, f): pass
        def emit(self, *args): pass

    class Qt:
        AlignCenter    = 0x0004
        AlignLeft      = 0x0001
        AlignRight     = 0x0002
        AlignVCenter   = 0x0080

    class QFont:
        def __init__(self, *args): pass

    class QSizePolicy:
        Expanding = 7
        Fixed     = 0
        Minimum   = 1
        Preferred = 5

# ─────────────────────────────────────────────────────────────────────────────

from ui.quick_risk_widget import QuickRiskControlWidget


# ── Color constants (mirrors GlassmorphismTheme for local use) ─────────────
_BG_CANVAS   = "#080b10"
_BG_CARD     = "#141a24"
_BORDER      = "rgba(255, 255, 255, 0.07)"
_BORDER_DIV  = "rgba(255, 255, 255, 0.05)"
_CYAN        = "#00e5ff"
_TEXT_SEC    = "#94a3b8"
_TEXT_MUTED  = "#64748b"
_TEXT_PRI    = "#f8fafc"
_BULL        = "#10b981"


# ── Stylesheet helpers ─────────────────────────────────────────────────────
_BTN_INACTIVE = f"""
    QPushButton {{
        background-color: transparent;
        border: none;
        border-radius: 4px;
        color: {_TEXT_SEC};
        font-size: 12px;
        font-weight: 600;
        padding: 0px 10px;
        text-align: left;
        height: 36px;
    }}
    QPushButton:hover {{
        background-color: {_BG_CARD};
        color: {_TEXT_PRI};
    }}
"""

_BTN_ACTIVE = f"""
    QPushButton {{
        background-color: rgba(0, 229, 255, 0.10);
        border: none;
        border-left: 3px solid {_CYAN};
        border-radius: 0px;
        color: {_CYAN};
        font-size: 12px;
        font-weight: 700;
        padding: 0px 10px;
        text-align: left;
        height: 36px;
    }}
"""

_SIDEBAR_FRAME = f"""
    QFrame#LeftSidebarFrame {{
        background-color: {_BG_CANVAS};
        border-right: 1px solid {_BORDER};
    }}
"""

_SECTION_LABEL = f"""
    QLabel {{
        color: {_TEXT_MUTED};
        font-size: 9px;
        font-weight: 700;
        letter-spacing: 1px;
        padding: 0px 10px;
    }}
"""

_DIVIDER = f"background-color: {_BORDER_DIV}; border: none; max-height: 1px;"

_BRAND_TITLE = f"color: {_CYAN}; font-size: 10px; font-weight: 800;"
_BRAND_SUB   = f"color: {_TEXT_MUTED}; font-size: 8px;"
_STATUS_PILL = f"""
    QLabel {{
        background-color: rgba(16, 185, 129, 0.12);
        border: 1px solid {_BULL};
        border-radius: 8px;
        color: {_BULL};
        font-size: 9px;
        font-weight: 700;
        padding: 2px 8px;
    }}
"""


class LeftSidebar(QFrame):
    """
    Elite institutional navigation sidebar.
    Vertical navigation with embedded QuickRiskControlWidget and brand footer.

    Public interface (preserved):
        nav_changed  : Signal(int)
        set_active_index(index: int)
        self.buttons : List[QPushButton]
        self.risk_controller : QuickRiskControlWidget
        self.mascot_lbl : QLabel  (invisible, backward-compat)
    """

    nav_changed = Signal(int)

    # 12 navigation destinations — icon, label, page-index
    NAV_ITEMS: List[tuple] = [
        ("⊞", "Dashboard",     0),
        ("📈", "Live Trading",  1),
        ("🤖", "Trading Bots", 2),
        ("⚙",  "Strategies",   3),
        ("👁",  "Market Watch", 4),
        ("⚡", "Auto Trade",   5),
        ("⏱",  "Backtest",     6),
        ("📊", "Analytics",    7),
        ("💼", "Portfolio",    8),
        ("🛡",  "Risk Manager", 9),
        ("📄", "Reports",     10),
        ("⚙",  "Settings",    11),
    ]

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("LeftSidebarFrame")
        self.setFixedWidth(190)
        self.setStyleSheet(_SIDEBAR_FRAME)

        self.buttons: List[QPushButton] = []
        self.active_index: int = 0

        self._init_ui()

    # ── UI construction ───────────────────────────────────────────────────────

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 10, 0, 8)
        layout.setSpacing(1)

        # ── Navigation buttons ──────────────────────────────────────────────
        for icon, label, idx in self.NAV_ITEMS:
            btn = QPushButton(f"  {icon}  {label}", self)
            btn.setFixedHeight(36)
            try:
                btn.clicked.connect(
                    lambda checked=False, i=idx: self._on_btn_clicked(i)
                )
            except Exception:
                pass
            layout.addWidget(btn)
            self.buttons.append(btn)

        self._refresh_styles()

        # ── Section divider ─────────────────────────────────────────────────
        layout.addSpacing(6)
        divider = QFrame(self)
        try:
            divider.setFrameShape(QFrame.HLine)
        except Exception:
            pass
        divider.setStyleSheet(_DIVIDER)
        layout.addWidget(divider)
        layout.addSpacing(6)

        # ── "EXECUTION CONFIG" section header ───────────────────────────────
        exec_lbl = QLabel("EXECUTION CONFIG", self)
        exec_lbl.setStyleSheet(_SECTION_LABEL)
        layout.addWidget(exec_lbl)
        layout.addSpacing(4)

        # ── Embedded Compact Risk Controller ────────────────────────────────
        self.risk_controller = QuickRiskControlWidget(self)
        layout.addWidget(self.risk_controller)

        layout.addStretch()

        # ── Brand footer ────────────────────────────────────────────────────
        self._build_footer(layout)

        # ── Invisible mascot label (backward compat) ─────────────────────────
        self.mascot_lbl = QLabel(self)
        self.mascot_lbl.setVisible(False)

    def _build_footer(self, layout: QVBoxLayout) -> None:
        """Builds the ⚡ OmniTradePro brand footer with status pill."""
        footer = QFrame(self)
        footer.setStyleSheet(
            f"QFrame {{ background-color: transparent; padding: 0px; }}"
        )
        fl = QVBoxLayout(footer)
        fl.setContentsMargins(8, 6, 8, 4)
        fl.setSpacing(3)

        # Brand title
        lbl_title = QLabel("⚡ OmniTradePro", footer)
        lbl_title.setStyleSheet(_BRAND_TITLE)
        try:
            lbl_title.setAlignment(Qt.AlignCenter)
        except Exception:
            pass
        fl.addWidget(lbl_title)

        # Subtitle
        lbl_sub = QLabel("Institutional v5.0", footer)
        lbl_sub.setStyleSheet(_BRAND_SUB)
        try:
            lbl_sub.setAlignment(Qt.AlignCenter)
        except Exception:
            pass
        fl.addWidget(lbl_sub)

        layout.addWidget(footer)
        layout.addSpacing(4)

        # Status pill
        status_pill = QLabel("● Live", self)
        status_pill.setStyleSheet(_STATUS_PILL)
        try:
            status_pill.setAlignment(Qt.AlignCenter)
        except Exception:
            pass
        layout.addWidget(status_pill)

    # ── Event handling ────────────────────────────────────────────────────────

    def _on_btn_clicked(self, index: int) -> None:
        self.set_active_index(index)
        try:
            self.nav_changed.emit(index)
        except Exception:
            pass

    # ── Public API ────────────────────────────────────────────────────────────

    def set_active_index(self, index: int) -> None:
        """Highlight the button at *index* and clear all others."""
        if 0 <= index < len(self.buttons):
            self.active_index = index
            self._refresh_styles()

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _refresh_styles(self) -> None:
        """Apply active / inactive QSS to every nav button."""
        for idx, btn in enumerate(self.buttons):
            btn.setStyleSheet(_BTN_ACTIVE if idx == self.active_index else _BTN_INACTIVE)
