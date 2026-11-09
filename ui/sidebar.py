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
        height: 34px;
    }}
    QPushButton:hover {{
        background-color: {_BG_CARD};
        color: {_TEXT_PRI};
        border-left: 3px solid rgba(0, 229, 255, 0.35);
    }}
"""

_BTN_ACTIVE = f"""
    QPushButton {{
        background-color: rgba(0, 229, 255, 0.12);
        border: none;
        border-left: 3px solid {_CYAN};
        border-radius: 0px;
        color: {_CYAN};
        font-size: 12px;
        font-weight: 700;
        letter-spacing: 0.3px;
        padding: 0px 10px;
        text-align: left;
        height: 34px;
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

    # 9 primary navigation tabs, grouped over the 12-page QStackedWidget.
    # Each entry: (icon, label, tuple of page indices this tab opens).
    # The stack keeps all 12 certified views; tabs are the presentation layer.
    NAV_TABS: List[tuple] = [
        ("📊", "Dashboard",            (0,)),
        ("⚡", "Live Trading View",    (1, 5)),
        ("🛡", "Risk Management",      (9,)),
        ("👁", "Live Market Watch",    (4,)),
        ("📋", "Orders & Trades",      (10,)),
        ("💼", "Portfolio & Positions", (8,)),
        ("🧠", "Strategy Consensus",   (3, 2, 6, 7)),
        ("🏦", "Manage Accounts",      (11,)),
        ("⚙", "System Settings",       (11,)),
    ]

    #: Page -> owning tab index (first tab in NAV_TABS that opens the page).
    @classmethod
    def tab_for_page(cls, page: int) -> int:
        for idx, (_, _, pages) in enumerate(cls.NAV_TABS):
            if page in pages:
                return idx
        return 0

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("LeftSidebarFrame")
        self.setFixedWidth(220)
        self.setStyleSheet(_SIDEBAR_FRAME)

        self.buttons: List[QPushButton] = []
        self.active_index: int = 0
        self._active_tab: int = 0

        self._init_ui()

    # ── UI construction ───────────────────────────────────────────────────────

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 10, 0, 8)
        layout.setSpacing(1)

        # ── Navigation tabs (9 grouped destinations) ───────────────────────
        for tab_idx, (icon, label, pages) in enumerate(self.NAV_TABS):
            btn = QPushButton(f"  {icon}  {label}", self)
            btn.setFixedHeight(34)
            btn.setToolTip(f"Opens page {pages[0]}")
            try:
                btn.clicked.connect(
                    lambda checked=False, i=tab_idx: self._on_btn_clicked(i)
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
        """Builds the ⚡ OmniTradePro brand footer with connection status and margin dock."""
        footer = QFrame(self)
        footer.setStyleSheet(
            f"QFrame {{ background-color: {_BG_CARD}; border: 1px solid {_BORDER}; border-radius: 6px; padding: 2px; }}"
        )
        fl = QVBoxLayout(footer)
        fl.setContentsMargins(8, 6, 8, 6)
        fl.setSpacing(4)

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

        # Thin divider
        div = QFrame(footer)
        div.setStyleSheet(_DIVIDER)
        fl.addWidget(div)

        # Connection status row (live: driven by the stream + RMS telemetry)
        conn_row = QHBoxLayout()
        conn_row.setSpacing(4)
        self.conn_dot = QLabel("●", footer)
        self.conn_dot.setStyleSheet("color: #ef4444; font-size: 9px;")
        self.conn_lbl = QLabel("DISCONNECTED", footer)
        self.conn_lbl.setStyleSheet("color: #ef4444; font-size: 9px; font-weight: 700;")
        conn_row.addWidget(self.conn_dot)
        conn_row.addWidget(self.conn_lbl)
        conn_row.addStretch()
        self.latency_lbl = QLabel("-- ms", footer)
        self.latency_lbl.setStyleSheet(f"color: {_TEXT_MUTED}; font-size: 9px;")
        conn_row.addWidget(self.latency_lbl)
        fl.addLayout(conn_row)

        # Ledger margin row
        margin_row = QHBoxLayout()
        margin_row.setSpacing(4)
        margin_cap = QLabel("Available", footer)
        margin_cap.setStyleSheet(f"color: {_TEXT_MUTED}; font-size: 8px;")
        self.margin_lbl = QLabel("Margin: --", footer)
        self.margin_lbl.setStyleSheet(f"color: {_TEXT_SEC}; font-size: 9px; font-weight: 700;")
        try:
            self.margin_lbl.setAlignment(Qt.AlignRight)
        except Exception:
            pass
        margin_row.addWidget(margin_cap)
        margin_row.addStretch()
        margin_row.addWidget(self.margin_lbl)
        fl.addLayout(margin_row)

        layout.addWidget(footer)
        layout.addSpacing(4)

    # ── Event handling ────────────────────────────────────────────────────────

    def _on_btn_clicked(self, tab_index: int) -> None:
        """Tab click: remember the exact tab, then route to its primary page."""
        if 0 <= tab_index < len(self.buttons):
            self._active_tab = tab_index
            page = self.NAV_TABS[tab_index][2][0]
            self.active_index = page
            self._refresh_styles()
            try:
                self.nav_changed.emit(page)
            except Exception:
                pass

    # ── Public API ────────────────────────────────────────────────────────────

    def set_active_index(self, index: int) -> None:
        """
        Highlight the tab that owns *index* (a page number, 0-11).

        ``active_index`` keeps the raw page value so programmatic routing stays
        1:1 with the QStackedWidget; the glow is applied to the owning tab.
        """
        if 0 <= index < 12:
            self.active_index = index
            self._active_tab = self.tab_for_page(index)
            self._refresh_styles()

    # ── Live telemetry dock ───────────────────────────────────────────────────

    def set_connection_state(self, connected: bool, latency_ms=None) -> None:
        """Drives the bottom-dock connection pulse + latency readout."""
        try:
            if connected:
                self.conn_dot.setStyleSheet(f"color: {_BULL}; font-size: 9px;")
                self.conn_lbl.setText("CONNECTED")
                self.conn_lbl.setStyleSheet(f"color: {_BULL}; font-size: 9px; font-weight: 700;")
                self.latency_lbl.setText(f"{latency_ms} ms" if latency_ms is not None else "-- ms")
                self.latency_lbl.setStyleSheet(f"color: {_TEXT_SEC}; font-size: 9px;")
            else:
                self.conn_dot.setStyleSheet("color: #ef4444; font-size: 9px;")
                self.conn_lbl.setText("DISCONNECTED")
                self.conn_lbl.setStyleSheet("color: #ef4444; font-size: 9px; font-weight: 700;")
                self.latency_lbl.setText("-- ms")
                self.latency_lbl.setStyleSheet(f"color: {_TEXT_MUTED}; font-size: 9px;")
        except Exception:
            pass

    def set_margin(self, available) -> None:
        """Drives the bottom-dock ledger margin readout (None -> unknown)."""
        try:
            if available is None:
                self.margin_lbl.setText("Margin: --")
                return
            self.margin_lbl.setText(f"Margin: ₹{float(available):,.2f}")
        except Exception:
            pass

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _refresh_styles(self) -> None:
        """Apply active / inactive QSS to every nav tab."""
        for idx, btn in enumerate(self.buttons):
            btn.setStyleSheet(_BTN_ACTIVE if idx == self._active_tab else _BTN_INACTIVE)
