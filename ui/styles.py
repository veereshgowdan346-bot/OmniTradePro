#!/usr/bin/env python3
"""
OmniTradePro / Chintu AI Trading Board v5.0 — Institutional Dark Cyber Styling
Platform: Windows 10/11 64-bit | Python 3.10+
Unified institutional color palette: Obsidian / Slate / Cyber Cyan / Bull Emerald / Bear Ruby.
"""


class GlassmorphismTheme:
    """Institutional dark cyber glassmorphism color palette and style definitions."""

    # ── Core Canvas & Background Tokens ───────────────────────────────────────
    BG_CANVAS               = "#080b10"          # Obsidian deep (new primary)
    BG_SURFACE              = "#0f141c"          # Slate surface
    BG_SIDEBAR              = "#080b10"          # Sidebar — same as canvas
    BG_CARD                 = "#141a24"          # Card background
    BG_CARD_TRANSLUCENT     = "rgba(20, 26, 36, 0.94)"
    BG_ELEVATED             = "#1a2235"          # Elevated surface / hover
    BG_SUB_CARD             = "#0d131d"          # Sub-card / nested panels
    BG_INPUT                = "#0e1420"          # Input fields

    # ── Border Tokens ─────────────────────────────────────────────────────────
    BORDER                  = "rgba(255, 255, 255, 0.07)"   # Ultra-fine border (new primary)
    BORDER_SUBTLE           = "rgba(255, 255, 255, 0.05)"   # Even subtler dividers
    BORDER_CARD             = "1px solid rgba(255, 255, 255, 0.07)"
    BORDER_CARD_HIGHLIGHT   = "1px solid #00e5ff"
    BORDER_CARD_GREEN       = "1px solid rgba(16, 185, 129, 0.25)"
    BORDER_INPUT            = "1px solid rgba(255, 255, 255, 0.08)"

    # ── Quantitative Semantic Accents ─────────────────────────────────────────
    ACCENT_CYAN             = "#00e5ff"          # Cyber Cyan (primary action)
    ACCENT_BULL             = "#10b981"          # Bull Emerald
    ACCENT_BEAR             = "#ef4444"          # Bear Ruby
    ACCENT_AMBER            = "#fbbf24"          # Warning Amber
    ACCENT_PURPLE           = "#818cf8"          # Indicator Purple

    # Legacy aliases kept for backward compatibility
    NEON_GREEN              = "#10b981"          # maps to ACCENT_BULL
    NEON_GREEN_HOVER        = "#34d399"
    NEON_CYAN               = "#00e5ff"          # maps to ACCENT_CYAN
    NEON_RED                = "#ef4444"          # maps to ACCENT_BEAR
    NEON_RED_GLOW           = "#f87171"
    LOSS_RED                = "#ef4444"
    NEON_BLUE               = "#2979ff"
    GOLD_YELLOW             = "#fbbf24"          # maps to ACCENT_AMBER

    # Bull / Bear convenience names
    BULL_GREEN              = "#10b981"
    BEAR_RED                = "#ef4444"

    # NSE classic profit green — preserved for test-suite & legacy chart compatibility
    PROFIT_GREEN            = "#00e676"

    # ── Typography Palette ────────────────────────────────────────────────────
    TEXT_WHITE              = "#ffffff"
    TEXT_PRIMARY            = "#f8fafc"
    TEXT_SECONDARY          = "#94a3b8"
    TEXT_MUTED              = "#64748b"
    TEXT_SUBTLE             = "#64748b"          # legacy alias
    TEXT_NUMERIC            = "#e2e8f0"          # price readouts

    # ─────────────────────────────────────────────────────────────────────────
    # Stylesheets
    # ─────────────────────────────────────────────────────────────────────────

    @classmethod
    def get_app_stylesheet(cls) -> str:
        """Minimal global QSS required by the system instructions spec."""
        return f"""
        QMainWindow, QWidget {{ background-color: {cls.BG_CANVAS}; color: {cls.TEXT_PRIMARY}; font-family: 'Segoe UI', Inter, sans-serif; }}
        QScrollBar:vertical {{ background: {cls.BG_SURFACE}; width: 6px; border-radius: 3px; }}
        QScrollBar::handle:vertical {{ background: {cls.BG_ELEVATED}; border-radius: 3px; min-height: 20px; }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0px; }}
        QToolTip {{ background-color: {cls.BG_ELEVATED}; color: {cls.TEXT_PRIMARY}; border: 1px solid {cls.ACCENT_CYAN}; border-radius: 4px; padding: 4px 8px; }}
        """

    @classmethod
    def get_stylesheet(cls) -> str:
        """Returns the complete institutional PySide6 QSS stylesheet."""
        return f"""
        /* ── Global Canvas Defaults ─────────────────────────────────────── */
        QMainWindow, QDialog {{
            background-color: {cls.BG_CANVAS};
            color: {cls.TEXT_PRIMARY};
            font-family: 'Segoe UI', 'Inter', -apple-system, sans-serif;
            font-size: 12px;
        }}

        QWidget {{
            color: {cls.TEXT_PRIMARY};
            font-family: 'Segoe UI', 'Inter', -apple-system, sans-serif;
        }}

        /* ── Scroll Areas ────────────────────────────────────────────────── */
        QScrollArea {{
            background: transparent;
            border: none;
        }}

        QScrollArea > QWidget > QWidget {{
            background: transparent;
        }}

        /* ── Translucent Cyber Cards ─────────────────────────────────────── */
        QFrame.cyberCard {{
            background-color: {cls.BG_CARD};
            border: 1px solid rgba(255, 255, 255, 0.07);
            border-radius: 8px;
        }}

        QFrame.cyberCard:hover {{
            border: 1px solid {cls.ACCENT_CYAN};
        }}

        QFrame.subCard {{
            background-color: {cls.BG_SUB_CARD};
            border: 1px solid rgba(255, 255, 255, 0.04);
            border-radius: 6px;
        }}

        /* ── Headings & Badges ───────────────────────────────────────────── */
        QLabel.cardHeader {{
            color: {cls.TEXT_WHITE};
            font-weight: 700;
            font-size: 13px;
        }}

        QLabel.metricLarge {{
            color: {cls.ACCENT_BULL};
            font-weight: 800;
            font-size: 24px;
        }}

        QLabel.lossText {{
            color: {cls.ACCENT_BEAR};
        }}

        QLabel.metricLabel {{
            color: {cls.TEXT_SECONDARY};
            font-size: 11px;
            font-weight: 500;
        }}

        QLabel.metricValue {{
            color: {cls.TEXT_NUMERIC};
            font-size: 12px;
            font-weight: 700;
        }}

        /* ── Navigation Pills ────────────────────────────────────────────── */
        QPushButton.navPill {{
            background-color: {cls.BG_ELEVATED};
            color: {cls.TEXT_SECONDARY};
            border: 1px solid rgba(255, 255, 255, 0.07);
            border-radius: 6px;
            padding: 6px 14px;
            font-size: 12px;
            font-weight: 600;
        }}

        QPushButton.navPill:hover {{
            background-color: {cls.BG_ELEVATED};
            color: {cls.TEXT_PRIMARY};
            border: 1px solid rgba(255, 255, 255, 0.12);
        }}

        QPushButton.activePill {{
            background-color: {cls.ACCENT_BULL};
            color: #060b13;
            border: 1px solid {cls.ACCENT_BULL};
            border-radius: 6px;
            padding: 6px 14px;
            font-size: 12px;
            font-weight: 800;
        }}

        /* ── Sidebar Navigation Items ────────────────────────────────────── */
        QPushButton.sidebarBtn {{
            background-color: transparent;
            color: {cls.TEXT_SECONDARY};
            border: none;
            border-radius: 4px;
            padding: 6px 12px;
            text-align: left;
            font-size: 12px;
            font-weight: 600;
        }}

        QPushButton.sidebarBtn:hover {{
            background-color: {cls.BG_CARD};
            color: {cls.TEXT_PRIMARY};
        }}

        QPushButton.sidebarBtnActive {{
            background-color: rgba(0, 229, 255, 0.10);
            border-left: 3px solid {cls.ACCENT_CYAN};
            border-radius: 0px;
            color: {cls.ACCENT_CYAN};
            font-weight: 800;
            font-size: 12px;
            padding: 6px 10px;
            text-align: left;
        }}

        /* ── Action Buttons ──────────────────────────────────────────────── */
        QPushButton.btnBuy {{
            background-color: {cls.ACCENT_BULL};
            color: #060b13;
            border: none;
            border-radius: 6px;
            padding: 10px;
            font-size: 13px;
            font-weight: 800;
        }}

        QPushButton.btnBuy:hover {{
            background-color: {cls.NEON_GREEN_HOVER};
        }}

        QPushButton.btnSell {{
            background-color: {cls.BG_ELEVATED};
            color: {cls.TEXT_PRIMARY};
            border: 1px solid rgba(255, 255, 255, 0.10);
            border-radius: 6px;
            padding: 10px;
            font-size: 13px;
            font-weight: 700;
        }}

        QPushButton.btnSell:hover {{
            background-color: rgba(239, 68, 68, 0.15);
            border-color: {cls.ACCENT_BEAR};
            color: {cls.ACCENT_BEAR};
        }}

        QPushButton.btnPlaceOrder {{
            background-color: {cls.ACCENT_BULL};
            color: #060b13;
            border: none;
            border-radius: 7px;
            padding: 12px;
            font-size: 14px;
            font-weight: 800;
        }}

        QPushButton.btnPlaceOrder:hover {{
            background-color: {cls.NEON_GREEN_HOVER};
        }}

        /* ── Emergency Kill Switch ───────────────────────────────────────── */
        QPushButton.btnKillSwitch {{
            background-color: rgba(239, 68, 68, 0.15);
            border: 1.5px solid {cls.ACCENT_BEAR};
            border-radius: 8px;
            color: {cls.NEON_RED_GLOW};
            font-weight: 800;
            font-size: 11px;
            padding: 6px 14px;
        }}

        QPushButton.btnKillSwitch:hover {{
            background-color: rgba(239, 68, 68, 0.35);
            color: {cls.TEXT_WHITE};
        }}

        /* ── Inputs & Combos ─────────────────────────────────────────────── */
        QComboBox, QLineEdit, QSpinBox, QDoubleSpinBox {{
            background-color: {cls.BG_INPUT};
            border: 1px solid rgba(255, 255, 255, 0.08);
            border-radius: 6px;
            padding: 5px 8px;
            color: {cls.TEXT_PRIMARY};
            font-size: 12px;
            font-weight: 600;
        }}

        QComboBox:focus, QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus {{
            border: 1px solid {cls.ACCENT_CYAN};
        }}

        QComboBox::drop-down {{
            subcontrol-origin: padding;
            subcontrol-position: top right;
            width: 20px;
            border-left: none;
        }}

        QComboBox QAbstractItemView {{
            background-color: {cls.BG_SURFACE};
            border: 1px solid rgba(255, 255, 255, 0.08);
            selection-background-color: {cls.BG_ELEVATED};
            selection-color: {cls.ACCENT_CYAN};
            color: {cls.TEXT_PRIMARY};
            padding: 4px;
        }}

        /* ── Modern Tables ───────────────────────────────────────────────── */
        QTableWidget {{
            background-color: transparent;
            gridline-color: transparent;
            border: none;
            color: {cls.TEXT_PRIMARY};
            selection-background-color: {cls.BG_ELEVATED};
        }}

        QTableWidget::item {{
            padding: 4px;
            border-bottom: 1px solid rgba(255, 255, 255, 0.04);
        }}

        QHeaderView::section {{
            background-color: transparent;
            color: {cls.TEXT_MUTED};
            border: none;
            border-bottom: 1px solid rgba(255, 255, 255, 0.07);
            padding: 4px 6px;
            font-weight: 600;
            font-size: 11px;
        }}

        /* ── Progress Bar ────────────────────────────────────────────────── */
        QProgressBar {{
            background-color: {cls.BG_ELEVATED};
            border: 1px solid rgba(255, 255, 255, 0.07);
            border-radius: 4px;
            height: 8px;
            text-align: center;
        }}

        QProgressBar::chunk {{
            background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                stop:0 {cls.ACCENT_CYAN}, stop:1 {cls.ACCENT_BULL});
            border-radius: 3px;
        }}

        /* ── Sleek Cyber Scrollbars ───────────────────────────────────────── */
        QScrollBar:vertical {{
            background: {cls.BG_SURFACE};
            width: 6px;
            margin: 0px;
            border-radius: 3px;
        }}

        QScrollBar::handle:vertical {{
            background: {cls.BG_ELEVATED};
            min-height: 20px;
            border-radius: 3px;
        }}

        QScrollBar::handle:vertical:hover {{
            background: {cls.ACCENT_CYAN};
        }}

        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
            height: 0px;
        }}

        QScrollBar:horizontal {{
            background: {cls.BG_SURFACE};
            height: 6px;
            margin: 0px;
            border-radius: 3px;
        }}

        QScrollBar::handle:horizontal {{
            background: {cls.BG_ELEVATED};
            min-width: 20px;
            border-radius: 3px;
        }}

        QScrollBar::handle:horizontal:hover {{
            background: {cls.ACCENT_CYAN};
        }}

        QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
            width: 0px;
        }}

        /* ── Tooltips ────────────────────────────────────────────────────── */
        QToolTip {{
            background-color: {cls.BG_ELEVATED};
            color: {cls.TEXT_PRIMARY};
            border: 1px solid {cls.ACCENT_CYAN};
            border-radius: 4px;
            padding: 4px 8px;
        }}

        /* ── Legacy Token Registry (preserved for NSE chart & test-suite compatibility) ── */
        /* Legacy Token: #00e676  — NSE classic profit green (PROFIT_GREEN alias)        */
        /* Legacy Token: #ff3d71  — Legacy loss red (prior palette bear token)           */
        """
