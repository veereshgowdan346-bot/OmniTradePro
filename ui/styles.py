#!/usr/bin/env python3
"""
OmniTradePro / Chintu AI Trading Board v5.0 - Institutional Dark Cyber Styling
Platform: Windows 10/11 64-bit | Python 3.10+
High-precision pixel-perfect stylesheet adhering to the screenshot reference:
Cyber slate backdrop, neon emerald active highlights, translucent acrylic card backplates,
cyan glow borders, and clean typography.
"""

class GlassmorphismTheme:
    """Institutional dark cyber glassmorphism color palette and style definitions."""

    # Core Canvas & Background Tokens
    BG_CANVAS = "#060b13"
    BG_SIDEBAR = "#070d18"
    BG_CARD = "#0d1726"
    BG_CARD_TRANSLUCENT = "rgba(13, 23, 38, 0.92)"
    BG_SUB_CARD = "#0a121f"
    BG_INPUT = "#09101b"

    # Border Tokens
    BORDER_CARD = "1px solid #16243a"
    BORDER_CARD_HIGHLIGHT = "1px solid rgba(0, 242, 254, 0.18)"
    BORDER_CARD_GREEN = "1px solid rgba(0, 230, 118, 0.25)"
    BORDER_INPUT = "1px solid #1c2e48"

    # Quantitative Semantic Accents
    NEON_GREEN = "#00e676"
    NEON_GREEN_HOVER = "#00ff88"
    NEON_CYAN = "#00f2fe"
    ACCENT_CYAN = "#00e5ff"
    NEON_RED = "#ff1744"
    LOSS_RED = "#ff3d71"
    NEON_RED_GLOW = "#ff5252"
    NEON_BLUE = "#2979ff"
    GOLD_YELLOW = "#ffd600"

    # Typography Palette
    TEXT_WHITE = "#ffffff"
    TEXT_PRIMARY = "#e0e6ed"
    TEXT_MUTED = "#78909c"
    TEXT_SUBTLE = "#455a64"

    @classmethod
    def get_stylesheet(cls) -> str:
        """Returns the complete institutional PySide6 QSS stylesheet."""
        return f"""
        /* Global Canvas Defaults */
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

        /* Scroll Area Base */
        QScrollArea {{
            background: transparent;
            border: none;
        }}

        QScrollArea > QWidget > QWidget {{
            background: transparent;
        }}

        /* Translucent Cyber Cards */
        QFrame.cyberCard {{
            background-color: {cls.BG_CARD};
            border: 1px solid #17263c;
            border-radius: 10px;
        }}

        QFrame.cyberCard:hover {{
            border: 1px solid {cls.ACCENT_CYAN};
        }}

        QFrame.subCard {{
            background-color: {cls.BG_SUB_CARD};
            border: 1px solid #142234;
            border-radius: 6px;
        }}

        /* Headings & Badges */
        QLabel.cardHeader {{
            color: {cls.TEXT_WHITE};
            font-weight: 700;
            font-size: 13px;
        }}

        QLabel.metricLarge {{
            color: {cls.NEON_GREEN};
            font-weight: 800;
            font-size: 24px;
        }}

        QLabel.lossText {{
            color: {cls.LOSS_RED};
        }}

        QLabel.metricLabel {{
            color: {cls.TEXT_MUTED};
            font-size: 11px;
            font-weight: 500;
        }}

        QLabel.metricValue {{
            color: {cls.TEXT_WHITE};
            font-size: 12px;
            font-weight: 700;
        }}

        /* Navigation Pills */
        QPushButton.navPill {{
            background-color: #101c2e;
            color: #cfd8dc;
            border: 1px solid #1a2a40;
            border-radius: 6px;
            padding: 6px 14px;
            font-size: 12px;
            font-weight: 600;
        }}

        QPushButton.navPill:hover {{
            background-color: #172840;
            color: #ffffff;
            border: 1px solid #233956;
        }}

        QPushButton.activePill {{
            background-color: {cls.NEON_GREEN};
            color: #060b13;
            border: 1px solid {cls.NEON_GREEN};
            border-radius: 6px;
            padding: 6px 14px;
            font-size: 12px;
            font-weight: 800;
        }}

        /* Sidebar Navigation Item */
        QPushButton.sidebarBtn {{
            background-color: transparent;
            color: #90a4ae;
            border: none;
            border-radius: 6px;
            padding: 8px 12px;
            text-align: left;
            font-size: 12px;
            font-weight: 600;
        }}

        QPushButton.sidebarBtn:hover {{
            background-color: rgba(22, 38, 62, 0.6);
            color: #ffffff;
        }}

        QPushButton.sidebarBtnActive {{
            background-color: {cls.NEON_GREEN};
            color: #060b13;
            border: none;
            border-radius: 6px;
            padding: 8px 12px;
            text-align: left;
            font-size: 12px;
            font-weight: 800;
        }}

        /* Action Buttons */
        QPushButton.btnBuy {{
            background-color: {cls.NEON_GREEN};
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
            background-color: #162438;
            color: #ffffff;
            border: 1px solid #223752;
            border-radius: 6px;
            padding: 10px;
            font-size: 13px;
            font-weight: 700;
        }}

        QPushButton.btnSell:hover {{
            background-color: #1c2e46;
        }}

        QPushButton.btnPlaceOrder {{
            background-color: {cls.NEON_GREEN};
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

        /* Emergency Kill Switch */
        QPushButton.btnKillSwitch {{
            background-color: rgba(255, 23, 68, 0.15);
            border: 1.5px solid {cls.NEON_RED};
            border-radius: 8px;
            color: #ff5252;
            font-weight: 800;
            font-size: 11px;
            padding: 6px 14px;
        }}

        QPushButton.btnKillSwitch:hover {{
            background-color: rgba(255, 23, 68, 0.35);
            color: #ffffff;
        }}

        /* Inputs & Combos */
        QComboBox, QLineEdit, QSpinBox, QDoubleSpinBox {{
            background-color: {cls.BG_INPUT};
            border: 1px solid #1c2e48;
            border-radius: 6px;
            padding: 5px 8px;
            color: #ffffff;
            font-size: 12px;
            font-weight: 600;
        }}

        QComboBox:focus, QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus {{
            border: 1px solid {cls.NEON_GREEN};
        }}

        QComboBox::drop-down {{
            subcontrol-origin: padding;
            subcontrol-position: top right;
            width: 20px;
            border-left: none;
        }}

        QComboBox QAbstractItemView {{
            background-color: #0b1422;
            border: 1px solid #1f3350;
            selection-background-color: #15253c;
            selection-color: {cls.NEON_GREEN};
            color: #ffffff;
            padding: 4px;
        }}

        /* Modern Tables */
        QTableWidget {{
            background-color: transparent;
            gridline-color: transparent;
            border: none;
            color: #ffffff;
            selection-background-color: #142236;
        }}

        QTableWidget::item {{
            padding: 4px;
            border-bottom: 1px solid #142236;
        }}

        QHeaderView::section {{
            background-color: transparent;
            color: {cls.TEXT_MUTED};
            border: none;
            border-bottom: 1px solid #1a2a40;
            padding: 4px 6px;
            font-weight: 600;
            font-size: 11px;
        }}

        /* Progress Bar (Portfolio Margin) */
        QProgressBar {{
            background-color: #101c2e;
            border: 1px solid #182a42;
            border-radius: 4px;
            height: 8px;
            text-align: center;
        }}

        QProgressBar::chunk {{
            background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {cls.NEON_CYAN}, stop:1 {cls.NEON_GREEN});
            border-radius: 3px;
        }}

        /* Sleek Cyber Scrollbars */
        QScrollBar:vertical {{
            background: #070d18;
            width: 6px;
            margin: 0px;
            border-radius: 3px;
        }}

        QScrollBar::handle:vertical {{
            background: #192a40;
            min-height: 20px;
            border-radius: 3px;
        }}

        QScrollBar::handle:vertical:hover {{
            background: {cls.NEON_GREEN};
        }}

        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
            height: 0px;
        }}

        QScrollBar:horizontal {{
            background: #070d18;
            height: 6px;
            margin: 0px;
            border-radius: 3px;
        }}

        QScrollBar::handle:horizontal {{
            background: #192a40;
            min-width: 20px;
            border-radius: 3px;
        }}

        QScrollBar::handle:horizontal:hover {{
            background: {cls.NEON_GREEN};
        }}

        QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
            width: 0px;
        }}
        """
