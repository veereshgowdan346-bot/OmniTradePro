#!/usr/bin/env python3
"""
OmniTradePro - Multi-Broker Vault & 2FA Configuration Widget & Dialog
Platform: Windows 10/11 64-bit | Python 3.10+
Provides an institutional frosted glassmorphism interface to manage AES-256
encrypted credentials for Angel One, Shoonya, and Groww with live 2FA verification.
Features:
- Broker selector tabs (Angel One, Shoonya, Groww) with active pill styling
- Dedicated 6-digit Trading PIN / TPIN input with show/hide password toggle
- Real-time live rolling TOTP engine rotating every 30s with large monospace digits [ 4 8 2 9 1 0 ]
  and synchronized 30-second countdown bar
- Direct asynchronous live backend authentication testing [ ⚡ Test Live Auth ] with inline status banner
- Full AES-256 Fernet field-level encryption writing to database/omnitrade_vault.db
"""

import time
import threading
from typing import Optional, Dict, Any
import pyotp

from database.db_handler import DatabaseHandler
from database.vault_manager import VaultManager
from brokers.angel_one import AngelOneBroker
from brokers.shoonya import ShoonyaBroker
from brokers.groww import GrowwBroker

try:
    from PySide6.QtWidgets import (
        QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
        QPushButton, QComboBox, QFrame, QMessageBox, QGroupBox,
        QProgressBar, QScrollArea, QWidget, QCheckBox
    )
    from PySide6.QtCore import Qt, QTimer, Signal
    from PySide6.QtGui import QFont
except ImportError:
    # Graceful shim for environments where PySide6 is not in current path
    class QDialog:
        def __init__(self, parent=None): pass
        def setWindowTitle(self, t): pass
        def setMinimumSize(self, w, h): pass
        def resize(self, w, h): pass
        def setLayout(self, l): pass
        def setStyleSheet(self, s): pass
        def setProperty(self, k, v): pass
        def setVisible(self, v): pass
        def exec(self): return 1
        def accept(self): pass
        def reject(self): pass
    class QWidget:
        def __init__(self, parent=None): pass
        def setStyleSheet(self, s): pass
        def setProperty(self, k, v): pass
        def setVisible(self, v): pass
        def setLayout(self, l): pass
    class QCheckBox:
        def __init__(self, text="", parent=None):
            self.text = text
            self._checked = False
        def isChecked(self): return self._checked
        def setChecked(self, c): self._checked = bool(c)
        def setStyleSheet(self, s): pass
        def setProperty(self, k, v): pass
        def stateChanged(self): pass
    class QVBoxLayout:
        def __init__(self, *args): pass
        def addWidget(self, w, *args): pass
        def addLayout(self, l, *args): pass
        def addStretch(self, *args): pass
        def setContentsMargins(self, *args): pass
        def setSpacing(self, s): pass
        def addSpacing(self, *args): pass
    class QHBoxLayout(QVBoxLayout): pass
    class _TextStr(str):
        def __call__(self):
            return str(self)

    class QLabel:
        def __init__(self, text="", parent=None): self.text = _TextStr(text)
        def setText(self, t): self.text = _TextStr(t)
        def setStyleSheet(self, s): pass
        def setAlignment(self, a): pass
        def setProperty(self, k, v): pass
        def setVisible(self, v): pass
    class QLineEdit:
        Normal = 0
        Password = 1
        def __init__(self, parent=None):
            self._text = ""
            self._echo = 0
        def setEchoMode(self, m): self._echo = m
        def echoMode(self): return self._echo
        def setPlaceholderText(self, p): pass
        def text(self): return self._text
        def setText(self, t): self._text = t
        def setStyleSheet(self, s): pass
        def setProperty(self, k, v): pass
        def setVisible(self, v): pass
        def textChanged(self): pass
    class QPushButton:
        def __init__(self, text="", parent=None): self.text = text
        def setText(self, t): self.text = t
        def setProperty(self, k, v): pass
        def setStyleSheet(self, s): pass
        def setEnabled(self, e): pass
        def setFixedWidth(self, w): pass
        def setFixedHeight(self, h): pass
        def clicked(self): pass
    class QComboBox:
        def __init__(self, parent=None): self._items = []
        def addItems(self, items): self._items.extend(items)
        def currentText(self): return self._items[0] if self._items else ""
        def setCurrentText(self, t): pass
        def currentTextChanged(self): pass
        def setStyleSheet(self, s): pass
        def setProperty(self, k, v): pass
        def setVisible(self, v): pass
    class QFrame:
        NoFrame = 0
        def __init__(self, parent=None): pass
        def setFrameShape(self, s): pass
        def setProperty(self, k, v): pass
        def setStyleSheet(self, s): pass
        def setLayout(self, l): pass
    class QGroupBox:
        def __init__(self, title="", parent=None): pass
        def setStyleSheet(self, s): pass
        def setLayout(self, l): pass
    class QProgressBar:
        def __init__(self, parent=None): pass
        def setRange(self, mn, mx): pass
        def setValue(self, v): pass
        def setStyleSheet(self, s): pass
        def setTextVisible(self, v): pass
        def setFixedHeight(self, h): pass
    class QScrollArea:
        def __init__(self, parent=None): pass
        def setWidgetResizable(self, r): pass
        def setWidget(self, w): pass
        def setStyleSheet(self, s): pass
        def setFrameShape(self, s): pass
    class QMessageBox:
        @staticmethod
        def information(p, t, m): pass
        @staticmethod
        def warning(p, t, m): pass
        @staticmethod
        def critical(p, t, m): pass
    class QTimer:
        def __init__(self, parent=None): pass
        def timeout(self): pass
        def start(self, ms): pass
        def stop(self): pass
    class Signal:
        def __init__(self, *args): pass
        def connect(self, f): pass
        def emit(self, *args): pass
    class Qt:
        AlignCenter = 0x0004
        AlignVCenter = 0x0080


class BrokerVaultWidget(QWidget):
    """
    Unified institutional frosted glassmorphism credentials & 2FA management widget.
    Embedded in both the Sidebar Settings Page and the BrokerVaultDialog popup.
    """

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.db = DatabaseHandler()
        self.vault = VaultManager()
        self._current_broker: str = "ANGEL_ONE"

        self._init_ui()
        self._init_totp_timer()
        self._load_selected_broker_credentials()
        self._load_notification_settings()

    def _init_ui(self) -> None:
        self.setStyleSheet("""
            QWidget {
                color: #94a3b8;
                font-family: 'Segoe UI', Inter, -apple-system, sans-serif;
            }
            QLabel {
                color: #94a3b8;
                font-size: 12px;
            }
            QLineEdit {
                background-color: #0b1424;
                border: 1px solid #1e3a5f;
                border-radius: 6px;
                color: #f8fafc;
                padding: 7px 10px;
                font-size: 13px;
                font-family: 'Consolas', monospace;
            }
            QLineEdit:focus {
                border: 1px solid #00f0ff;
                background-color: #0e1a30;
            }
            QComboBox {
                background-color: #0b1424;
                border: 1px solid #1e3a5f;
                border-radius: 6px;
                color: #00e5ff;
                font-weight: bold;
                font-size: 13px;
                padding: 6px 12px;
            }
            QPushButton {
                background-color: #0b1424;
                border: 1px solid #1e3a5f;
                border-radius: 6px;
                color: #f8fafc;
                padding: 8px 14px;
                font-size: 12px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #162a45;
                border-color: #00f0ff;
                color: #00f0ff;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(12)

        # 1. Header Banner
        header_box = QVBoxLayout()
        header_box.setSpacing(2)
        title_label = QLabel("INSTITUTIONAL BROKER VAULT & DYNAMIC 2FA", self)
        title_label.setStyleSheet("font-size: 15px; font-weight: bold; color: #00e5ff; letter-spacing: 1px;")
        subtitle_label = QLabel("AES-256 field-level encrypted storage, auto-TOTP rotation & live API handshake.", self)
        subtitle_label.setStyleSheet("font-size: 11px; color: #64748b;")
        header_box.addWidget(title_label)
        header_box.addWidget(subtitle_label)
        layout.addLayout(header_box)

        # 2. Broker Selector Tabs (Active Pills)
        tabs_box = QHBoxLayout()
        tabs_box.setSpacing(8)

        self.btn_tab_angel = QPushButton("Angel One (SmartAPI)", self)
        self.btn_tab_shoonya = QPushButton("Shoonya (NorenAPI)", self)
        self.btn_tab_groww = QPushButton("Groww Gateway", self)

        for btn in (self.btn_tab_angel, self.btn_tab_shoonya, self.btn_tab_groww):
            btn.setFixedHeight(34)
            tabs_box.addWidget(btn)

        try:
            self.btn_tab_angel.clicked.connect(lambda: self._select_broker("ANGEL_ONE"))
            self.btn_tab_shoonya.clicked.connect(lambda: self._select_broker("SHOONYA"))
            self.btn_tab_groww.clicked.connect(lambda: self._select_broker("GROWW"))
        except Exception:
            pass

        tabs_box.addStretch()

        # Gateway Active Status Badge
        self.status_badge = QLabel("Gateway Status: Inactive", self)
        self.status_badge.setStyleSheet("font-weight: 700; color: #ffab00; font-size: 12px;")
        tabs_box.addWidget(self.status_badge)
        layout.addLayout(tabs_box)

        # Compatibility broker combo (hidden or synchronized)
        self.broker_combo = QComboBox(self)
        self.broker_combo.addItems(["ANGEL_ONE", "SHOONYA", "GROWW"])
        self.broker_combo.setVisible(False)

        # 3. Main Input Card Panel
        form_frame = QFrame(self)
        form_frame.setStyleSheet("""
            QFrame {
                background-color: rgba(13, 21, 39, 0.85);
                border: 1px solid #142236;
                border-radius: 8px;
            }
        """)
        form_layout = QVBoxLayout(form_frame)
        form_layout.setContentsMargins(16, 14, 16, 14)
        form_layout.setSpacing(9)

        # Row A: Client ID / User Code
        form_layout.addWidget(QLabel("Client ID / User Code:", self))
        self.client_id_edit = QLineEdit(self)
        self.client_id_edit.setPlaceholderText("e.g. A100982 (Angel One) or FA55421 (Shoonya)")
        form_layout.addWidget(self.client_id_edit)

        # Row B: 4-Digit Login MPIN / Password
        form_layout.addWidget(QLabel("Login Password / 4-Digit MPIN:", self))
        mpin_box = QHBoxLayout()
        self.mpin_edit = QLineEdit(self)
        self.mpin_edit.setEchoMode(QLineEdit.Password)
        self.mpin_edit.setPlaceholderText("Enter 4-digit numeric MPIN")
        self.btn_toggle_mpin = QPushButton("👁 Show", self)
        self.btn_toggle_mpin.setFixedWidth(70)
        try:
            self.btn_toggle_mpin.clicked.connect(lambda: self._toggle_echo(self.mpin_edit, self.btn_toggle_mpin))
        except Exception:
            pass
        mpin_box.addWidget(self.mpin_edit)
        mpin_box.addWidget(self.btn_toggle_mpin)
        form_layout.addLayout(mpin_box)

        # Row C: 6-Digit Trading PIN / TPIN
        form_layout.addWidget(QLabel("Trading PIN / TPIN (6-Digit Authorization PIN):", self))
        tpin_box = QHBoxLayout()
        self.trading_pin_edit = QLineEdit(self)
        self.trading_pin_edit.setEchoMode(QLineEdit.Password)
        self.trading_pin_edit.setPlaceholderText("Enter 6-digit numeric Trading PIN (TPIN)")
        self.btn_toggle_tpin = QPushButton("👁 Show", self)
        self.btn_toggle_tpin.setFixedWidth(70)
        try:
            self.btn_toggle_tpin.clicked.connect(lambda: self._toggle_echo(self.trading_pin_edit, self.btn_toggle_tpin))
        except Exception:
            pass
        tpin_box.addWidget(self.trading_pin_edit)
        tpin_box.addWidget(self.btn_toggle_tpin)
        form_layout.addLayout(tpin_box)

        # Row D: 32-Character Base32 TOTP Secret
        form_layout.addWidget(QLabel("32-Character Base32 TOTP Secret:", self))
        totp_box = QHBoxLayout()
        self.totp_edit = QLineEdit(self)
        self.totp_edit.setEchoMode(QLineEdit.Password)
        self.totp_edit.setPlaceholderText("e.g. JBSWY3DPEHPK3PXPJBSWY3DPEHPK3PXP")
        try:
            self.totp_edit.textChanged.connect(self._on_totp_secret_changed)
        except Exception:
            pass
        self.btn_toggle_totp = QPushButton("👁 Show", self)
        self.btn_toggle_totp.setFixedWidth(70)
        try:
            self.btn_toggle_totp.clicked.connect(lambda: self._toggle_echo(self.totp_edit, self.btn_toggle_totp))
        except Exception:
            pass
        totp_box.addWidget(self.totp_edit)
        totp_box.addWidget(self.btn_toggle_totp)
        form_layout.addLayout(totp_box)

        # Row E: Real-Time Live Rolling TOTP Badge
        live_totp_frame = QFrame(self)
        live_totp_frame.setStyleSheet("""
            QFrame {
                background-color: #070d18;
                border: 1px solid #1e3a5f;
                border-radius: 6px;
                padding: 6px;
            }
        """)
        live_totp_layout = QVBoxLayout(live_totp_frame)
        live_totp_layout.setContentsMargins(10, 8, 10, 8)
        live_totp_layout.setSpacing(4)

        totp_header_row = QHBoxLayout()
        lbl_totp_title = QLabel("LIVE 2FA TOTP AUTHENTICATOR (RFC 6238)", self)
        lbl_totp_title.setStyleSheet("color: #38bdf8; font-size: 11px; font-weight: bold; letter-spacing: 1px;")
        totp_header_row.addWidget(lbl_totp_title)
        totp_header_row.addStretch()

        self.lbl_totp_timer = QLabel("Expires in 30s...", self)
        self.lbl_totp_timer.setStyleSheet("color: #f59e0b; font-size: 11px; font-weight: 600;")
        totp_header_row.addWidget(self.lbl_totp_timer)
        live_totp_layout.addLayout(totp_header_row)

        totp_display_row = QHBoxLayout()
        self.lbl_live_totp_code = QLabel("[ - - - - - - ]", self)
        self.lbl_live_totp_code.setStyleSheet("""
            color: #00ff88;
            font-size: 22px;
            font-weight: bold;
            font-family: 'Consolas', monospace;
            letter-spacing: 5px;
        """)
        self.lbl_live_totp_code.setAlignment(Qt.AlignCenter)
        totp_display_row.addWidget(self.lbl_live_totp_code)
        live_totp_layout.addLayout(totp_display_row)

        # Visual progress bar for 30s cycle
        self.totp_progress = QProgressBar(self)
        self.totp_progress.setRange(0, 30)
        self.totp_progress.setValue(30)
        self.totp_progress.setTextVisible(False)
        self.totp_progress.setFixedHeight(4)
        self.totp_progress.setStyleSheet("""
            QProgressBar {
                background-color: #1e293b;
                border: none;
                border-radius: 2px;
            }
            QProgressBar::chunk {
                background-color: #00f0ff;
                border-radius: 2px;
            }
        """)
        live_totp_layout.addWidget(self.totp_progress)
        form_layout.addWidget(live_totp_frame)

        # Row F: API Key
        form_layout.addWidget(QLabel("Broker API Key (SmartAPI / App Key):", self))
        self.api_key_edit = QLineEdit(self)
        self.api_key_edit.setPlaceholderText("Enter developer API key")
        form_layout.addWidget(self.api_key_edit)

        # Row G: Secret Key / Vendor Code
        form_layout.addWidget(QLabel("Secret Key / Vendor Code (Optional):", self))
        self.secret_key_edit = QLineEdit(self)
        self.secret_key_edit.setEchoMode(QLineEdit.Password)
        self.secret_key_edit.setPlaceholderText("Enter Secret Key / Vendor Code if provided")
        form_layout.addWidget(self.secret_key_edit)

        layout.addWidget(form_frame)

        # 3.5. Alerts & Notifications (Email Service)
        notify_frame = QFrame(self)
        notify_frame.setStyleSheet("""
            QFrame {
                background-color: rgba(13, 21, 39, 0.85);
                border: 1px solid #142236;
                border-radius: 8px;
            }
        """)
        notify_layout = QVBoxLayout(notify_frame)
        notify_layout.setContentsMargins(16, 14, 16, 14)
        notify_layout.setSpacing(9)

        notify_hdr_box = QHBoxLayout()
        lbl_notify_title = QLabel("ALERTS & EMAIL NOTIFICATIONS", self)
        lbl_notify_title.setStyleSheet("font-size: 13px; font-weight: bold; color: #00e5ff; letter-spacing: 0.5px;")
        notify_hdr_box.addWidget(lbl_notify_title)
        notify_hdr_box.addStretch()
        notify_layout.addLayout(notify_hdr_box)

        # Checkboxes
        chk_box = QHBoxLayout()
        chk_box.setSpacing(16)
        self.chk_trade_alerts = QCheckBox("Enable Instant Trade Email Alerts", self)
        self.chk_trade_alerts.setStyleSheet("color: #f8fafc; font-size: 12px; font-weight: 600;")
        self.chk_trade_alerts.setChecked(True)

        self.chk_daily_summary = QCheckBox("Enable Daily 15:15 / 23:15 P&L Summary", self)
        self.chk_daily_summary.setStyleSheet("color: #f8fafc; font-size: 12px; font-weight: 600;")
        self.chk_daily_summary.setChecked(True)

        chk_box.addWidget(self.chk_trade_alerts)
        chk_box.addWidget(self.chk_daily_summary)
        chk_box.addStretch()
        notify_layout.addLayout(chk_box)

        # Input: Recipient Email
        notify_layout.addWidget(QLabel("Recipient Email (Operator Alert Destination):", self))
        self.recipient_email_edit = QLineEdit(self)
        self.recipient_email_edit.setPlaceholderText("e.g. operator@domain.com")
        notify_layout.addWidget(self.recipient_email_edit)

        # Input: Sender Email (Optional)
        notify_layout.addWidget(QLabel("Sender Email / SMTP Username (Optional):", self))
        self.sender_email_edit = QLineEdit(self)
        self.sender_email_edit.setPlaceholderText("e.g. alerts@domain.com (defaults to Recipient Email if blank)")
        notify_layout.addWidget(self.sender_email_edit)

        # Input: Email API Key / SMTP App Password
        notify_layout.addWidget(QLabel("Email API Key / SMTP App Password:", self))
        smtp_key_box = QHBoxLayout()
        self.smtp_key_edit = QLineEdit(self)
        self.smtp_key_edit.setEchoMode(QLineEdit.Password)
        self.smtp_key_edit.setPlaceholderText("Enter 16-character Gmail App Password or Resend API key (re_...)")
        self.btn_toggle_smtp_key = QPushButton("👁 Show", self)
        self.btn_toggle_smtp_key.setFixedWidth(70)
        try:
            self.btn_toggle_smtp_key.clicked.connect(lambda: self._toggle_echo(self.smtp_key_edit, self.btn_toggle_smtp_key))
        except Exception:
            pass
        smtp_key_box.addWidget(self.smtp_key_edit)
        smtp_key_box.addWidget(self.btn_toggle_smtp_key)
        notify_layout.addLayout(smtp_key_box)

        # Action: Test Notification
        notify_action_row = QHBoxLayout()
        self.btn_test_notify = QPushButton("✉ Test Notification", self)
        self.btn_test_notify.setStyleSheet("""
            QPushButton {
                background-color: #0369a1;
                border: 1px solid #38bdf8;
                color: #ffffff;
                font-weight: bold;
                padding: 7px 14px;
            }
            QPushButton:hover {
                background-color: #0284c7;
            }
        """)
        try:
            self.btn_test_notify.clicked.connect(self._test_notification)
        except Exception:
            pass
        notify_action_row.addWidget(self.btn_test_notify)

        self.lbl_notify_status = QLabel("", self)
        self.lbl_notify_status.setStyleSheet("color: #94a3b8; font-size: 11px;")
        notify_action_row.addWidget(self.lbl_notify_status)
        notify_action_row.addStretch()
        notify_layout.addLayout(notify_action_row)

        layout.addWidget(notify_frame)

        # 4. Live Authentication Status Banner
        self.auth_status_banner = QLabel("", self)
        self.auth_status_banner.setStyleSheet("""
            background-color: #0b1424;
            border: 1px solid #142236;
            border-radius: 6px;
            color: #94a3b8;
            font-size: 12px;
            font-weight: 600;
            padding: 8px 12px;
        """)
        self.auth_status_banner.setAlignment(Qt.AlignCenter)
        self.auth_status_banner.setText("Ready: Test broker authentication handshake or save credentials.")
        layout.addWidget(self.auth_status_banner)

        # 5. Action Buttons (Test Live Auth, Save & Encrypt, Set Active)
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)

        self.btn_test_auth = QPushButton("⚡ Test Live Auth", self)
        self.btn_test_auth.setStyleSheet("""
            QPushButton {
                background-color: #b45309;
                border: 1px solid #f59e0b;
                color: #ffffff;
                font-weight: bold;
                padding: 9px 16px;
            }
            QPushButton:hover {
                background-color: #d97706;
            }
        """)
        try:
            self.btn_test_auth.clicked.connect(self._test_live_authentication)
        except Exception:
            pass

        self.btn_save = QPushButton("Save & Encrypt (AES-256)", self)
        self.btn_save.setStyleSheet("""
            QPushButton {
                background-color: #065f46;
                border: 1px solid #10b981;
                color: #ffffff;
                font-weight: bold;
                padding: 9px 16px;
            }
            QPushButton:hover {
                background-color: #059669;
            }
        """)
        try:
            self.btn_save.clicked.connect(self._save_credentials)
        except Exception:
            pass

        self.btn_set_active = QPushButton("Set Active", self)
        self.btn_set_active.setStyleSheet("""
            QPushButton {
                background-color: #1e3a5f;
                border: 1px solid #00e5ff;
                color: #00e5ff;
                font-weight: bold;
                padding: 9px 14px;
            }
            QPushButton:hover {
                background-color: #0e243d;
            }
        """)
        try:
            self.btn_set_active.clicked.connect(self._set_active_gateway)
        except Exception:
            pass

        btn_layout.addWidget(self.btn_test_auth)
        btn_layout.addWidget(self.btn_save)
        btn_layout.addWidget(self.btn_set_active)
        layout.addLayout(btn_layout)

        # Update tab visual state
        self._update_tab_styles()

    def _select_broker(self, broker_name: str) -> None:
        """Switches active broker tab."""
        self._current_broker = broker_name.strip().upper()
        self.broker_combo.setCurrentText(self._current_broker)
        self._update_tab_styles()
        self._load_selected_broker_credentials()
        self._update_realtime_totp()

    def _update_tab_styles(self) -> None:
        """Applies active neon glow styling to selected broker tab."""
        active_style = """
            QPushButton {
                background-color: rgba(0, 229, 255, 0.15);
                border: 1px solid #00f0ff;
                border-radius: 6px;
                color: #00f0ff;
                font-weight: bold;
                padding: 6px 14px;
            }
        """
        inactive_style = """
            QPushButton {
                background-color: #0b1424;
                border: 1px solid #1e3a5f;
                border-radius: 6px;
                color: #94a3b8;
                font-weight: 600;
                padding: 6px 14px;
            }
            QPushButton:hover {
                background-color: #162a45;
                color: #f8fafc;
            }
        """
        self.btn_tab_angel.setStyleSheet(active_style if self._current_broker == "ANGEL_ONE" else inactive_style)
        self.btn_tab_shoonya.setStyleSheet(active_style if self._current_broker == "SHOONYA" else inactive_style)
        self.btn_tab_groww.setStyleSheet(active_style if self._current_broker == "GROWW" else inactive_style)

    # =========================================================================
    # Live Real-Time TOTP Timer Engine (1-Second Ticking & 30-Second Rotation)
    # =========================================================================

    def _init_totp_timer(self) -> None:
        """Initializes 1-second interval timer for live TOTP calculation and countdown."""
        try:
            self.totp_timer = QTimer(self)
            self.totp_timer.timeout.connect(self._update_realtime_totp)
            self.totp_timer.start(1000)
        except Exception:
            pass

    def _update_realtime_totp(self) -> None:
        """
        Calculates and refreshes the live 6-digit TOTP token in real-time.
        Updates progress bar and countdown indicator every 1 second.
        """
        secret = self.totp_edit.text().strip()
        if not secret:
            self.lbl_live_totp_code.setText("[ - - - - - - ]")
            self.lbl_live_totp_code.setStyleSheet("color: #64748b; font-size: 22px; font-weight: bold; letter-spacing: 5px;")
            self.lbl_totp_timer.setText("TOTP: Enter Secret Key")
            self.lbl_totp_timer.setStyleSheet("color: #64748b; font-size: 11px;")
            try:
                self.totp_progress.setValue(0)
            except Exception:
                pass
            return

        try:
            clean_secret = secret.replace(" ", "").strip().upper()
            missing_padding = len(clean_secret) % 8
            if missing_padding:
                clean_secret += "=" * (8 - missing_padding)

            # Auto calculate live 6-digit TOTP
            token = pyotp.TOTP(clean_secret).now()

            # Calculate seconds remaining in current 30s cycle
            rem_seconds = 30 - (int(time.time()) % 30)

            # Format code as [ 4 8 2 9 1 0 ]
            spaced_code = " ".join(list(token))
            self.lbl_live_totp_code.setText(f"[ {spaced_code} ]")
            self.lbl_live_totp_code.setStyleSheet("""
                color: #00ff88;
                font-size: 22px;
                font-weight: bold;
                font-family: 'Consolas', monospace;
                letter-spacing: 4px;
            """)

            # Countdown text & progress
            self.lbl_totp_timer.setText(f"Expires in {rem_seconds:02d}s...")
            if rem_seconds <= 5:
                self.lbl_totp_timer.setStyleSheet("color: #ef4444; font-size: 11px; font-weight: bold;")
            else:
                self.lbl_totp_timer.setStyleSheet("color: #f59e0b; font-size: 11px; font-weight: 600;")

            try:
                self.totp_progress.setValue(rem_seconds)
            except Exception:
                pass

        except Exception:
            self.lbl_live_totp_code.setText("[ INVALID KEY ]")
            self.lbl_live_totp_code.setStyleSheet("color: #ef4444; font-size: 18px; font-weight: bold;")
            self.lbl_totp_timer.setText("Invalid Base32 Secret")
            self.lbl_totp_timer.setStyleSheet("color: #ef4444; font-size: 11px;")

    def _on_totp_secret_changed(self) -> None:
        """Immediately recalculates TOTP when secret is edited or pasted."""
        self._update_realtime_totp()

    def _toggle_echo(self, line_edit: QLineEdit, button: QPushButton) -> None:
        """Toggles between masked Password and visible Normal text."""
        try:
            if line_edit.echoMode() == QLineEdit.Password:
                line_edit.setEchoMode(QLineEdit.Normal)
                button.setText("🔒 Hide")
            else:
                line_edit.setEchoMode(QLineEdit.Password)
                button.setText("👁 Show")
        except Exception:
            pass

    # =========================================================================
    # Data Loading & Persistence
    # =========================================================================

    def _load_selected_broker_credentials(self) -> None:
        """Pulls decrypted credentials from vault and populates all form fields."""
        broker = self._current_broker
        try:
            creds = None
            try:
                creds = self.vault.get_broker_credentials(broker)
            except Exception:
                creds = self.db.get_broker_credentials(broker)

            self.client_id_edit.setText(creds.get("client_id", ""))
            self.mpin_edit.setText(creds.get("login_mpin", ""))
            self.trading_pin_edit.setText(creds.get("trading_pin", ""))
            self.totp_edit.setText(creds.get("totp_secret", ""))
            self.api_key_edit.setText(creds.get("api_key", ""))
            sec = creds.get("vendor_code") or creds.get("secret_key", "")
            self.secret_key_edit.setText(sec)

            if creds.get("is_active"):
                self.status_badge.setText(f"Gateway: ACTIVE ({broker})")
                self.status_badge.setStyleSheet("font-weight: 700; color: #00e676; font-size: 12px;")
            else:
                self.status_badge.setText("Gateway: Standby")
                self.status_badge.setStyleSheet("font-weight: 700; color: #94a3b8; font-size: 12px;")

            self.auth_status_banner.setText(f"Vault Loaded: {broker} credentials decrypted successfully.")
            self.auth_status_banner.setStyleSheet("""
                background-color: #0b1424;
                border: 1px solid #142236;
                border-radius: 6px;
                color: #38bdf8;
                font-size: 12px;
                font-weight: 600;
                padding: 8px 12px;
            """)
        except Exception:
            self.client_id_edit.setText("")
            self.mpin_edit.setText("")
            self.trading_pin_edit.setText("")
            self.totp_edit.setText("")
            self.api_key_edit.setText("")
            self.secret_key_edit.setText("")
            self.status_badge.setText("Gateway: Not Configured")
            self.status_badge.setStyleSheet("font-weight: 700; color: #ffab00; font-size: 12px;")
            self.auth_status_banner.setText("Ready: Enter credentials for " + broker + ".")
            self.auth_status_banner.setStyleSheet("""
                background-color: #0b1424;
                border: 1px solid #142236;
                border-radius: 6px;
                color: #94a3b8;
                font-size: 12px;
                font-weight: 600;
                padding: 8px 12px;
            """)

        self._update_realtime_totp()

    def _save_credentials(self) -> None:
        """Encrypts credentials with AES-256 and saves to database/omnitrade_vault.db."""
        broker = self._current_broker
        client_id = self.client_id_edit.text().strip()
        mpin = self.mpin_edit.text().strip()
        trading_pin = self.trading_pin_edit.text().strip()
        totp = self.totp_edit.text().strip()
        api_key = self.api_key_edit.text().strip()
        secret_key = self.secret_key_edit.text().strip()

        if not client_id or not mpin or not totp:
            QMessageBox.warning(self, "Validation Error", "Client ID, MPIN, and TOTP Secret are mandatory.")
            return

        if trading_pin and (not trading_pin.isdigit() or len(trading_pin) != 6):
            QMessageBox.warning(
                self,
                "Trading PIN Validation",
                "Trading PIN / TPIN must be exactly 6 numeric digits (e.g. 123456)."
            )
            return

        try:
            # 1. Save to VaultManager (omnitrade_vault.db)
            self.vault.save_broker_credentials(
                broker_name=broker,
                client_id=client_id,
                login_mpin=mpin,
                trading_pin=trading_pin,
                totp_secret=totp,
                api_key=api_key,
                secret_key=secret_key,
                vendor_code=secret_key
            )
            # 2. Synchronize with DatabaseHandler
            self.db.save_broker_credentials(
                broker_name=broker,
                client_id=client_id,
                login_mpin=mpin,
                trading_pin=trading_pin,
                totp_secret=totp,
                api_key=api_key,
                secret_key=secret_key
            )

            # 3. Save Notification Settings if configured
            recip = self.recipient_email_edit.text().strip()
            if recip:
                self.vault.save_notification_settings(
                    recipient_email=recip,
                    sender_email=self.sender_email_edit.text().strip(),
                    smtp_password=self.smtp_key_edit.text().strip(),
                    trade_alerts_enabled=self.chk_trade_alerts.isChecked(),
                    daily_summary_enabled=self.chk_daily_summary.isChecked()
                )

            self.auth_status_banner.setText(f"✓ Saved & Encrypted: {broker} credentials stored via AES-256 Fernet.")
            self.auth_status_banner.setStyleSheet("""
                background-color: #064e3b;
                border: 1px solid #10b981;
                border-radius: 6px;
                color: #34d399;
                font-size: 12px;
                font-weight: bold;
                padding: 8px 12px;
            """)

            QMessageBox.information(
                self,
                "Vault Encrypted",
                f"Credentials for {broker} (including 6-digit Trading PIN) successfully encrypted with AES-256 and stored in vault."
            )
            self._load_selected_broker_credentials()
        except Exception as exc:
            QMessageBox.critical(self, "Encryption Error", f"Failed to save credentials: {str(exc)}")

    def _set_active_gateway(self) -> None:
        """Marks the selected broker as the primary active gateway."""
        broker = self._current_broker
        success = self.vault.set_active_broker(broker) or self.db.set_active_broker(broker)
        if success:
            QMessageBox.information(self, "Active Gateway Updated", f"{broker} is now set as the primary market gateway.")
            self._load_selected_broker_credentials()
        else:
            QMessageBox.warning(self, "Action Failed", f"Could not activate {broker}. Ensure credentials are saved first.")

    def _load_notification_settings(self) -> None:
        """Pulls decrypted notification settings from vault and populates notification fields."""
        try:
            settings = self.vault.get_notification_settings()
            self.recipient_email_edit.setText(settings.get("recipient_email", ""))
            self.sender_email_edit.setText(settings.get("sender_email", ""))
            self.smtp_key_edit.setText(settings.get("smtp_password", ""))
            self.chk_trade_alerts.setChecked(settings.get("trade_alerts_enabled", True))
            self.chk_daily_summary.setChecked(settings.get("daily_summary_enabled", True))
        except Exception:
            pass

    def _test_notification(self) -> None:
        """Tests email delivery asynchronously in a background thread."""
        recip = self.recipient_email_edit.text().strip()
        pwd = self.smtp_key_edit.text().strip()
        sender = self.sender_email_edit.text().strip()

        if not recip:
            self.lbl_notify_status.setText("⚠ Enter Recipient Email first.")
            self.lbl_notify_status.setStyleSheet("color: #f59e0b; font-size: 11px; font-weight: bold;")
            return
        if not pwd:
            self.lbl_notify_status.setText("⚠ Enter Email API / App Password.")
            self.lbl_notify_status.setStyleSheet("color: #f59e0b; font-size: 11px; font-weight: bold;")
            return

        self.lbl_notify_status.setText("Dispatching test alert...")
        self.lbl_notify_status.setStyleSheet("color: #38bdf8; font-size: 11px;")
        self.btn_test_notify.setEnabled(False)

        def worker():
            try:
                from core.notifier import TradeNotifier
                notifier = TradeNotifier(
                    vault_manager=self.vault,
                    recipient_email=recip,
                    sender_email=sender,
                    smtp_password=pwd
                )
                success, msg = notifier.send_test_notification(
                    recipient_override=recip,
                    password_override=pwd,
                    sender_override=sender
                )
                if success:
                    self.lbl_notify_status.setText("✓ Test email sent successfully!")
                    self.lbl_notify_status.setStyleSheet("color: #34d399; font-size: 11px; font-weight: bold;")
                else:
                    clean_msg = msg[:40] + "..." if len(msg) > 40 else msg
                    self.lbl_notify_status.setText(f"✗ Failed: {clean_msg}")
                    self.lbl_notify_status.setStyleSheet("color: #ef4444; font-size: 11px; font-weight: bold;")
            except Exception as exc:
                self.lbl_notify_status.setText(f"✗ Error: {str(exc)[:35]}")
                self.lbl_notify_status.setStyleSheet("color: #ef4444; font-size: 11px;")
            finally:
                self.btn_test_notify.setEnabled(True)

        threading.Thread(target=worker, daemon=True, name="TestNotificationThread").start()

    # =========================================================================
    # Live Asynchronous Backend Authentication Testing
    # =========================================================================

    def _test_live_authentication(self) -> None:
        """
        Dispatches asynchronous test handshake to broker API servers with live auto-generated TOTP.
        Displays immediate inline feedback (GREEN banner on success, RED banner on failure).
        """
        broker = self._current_broker
        client_id = self.client_id_edit.text().strip()
        mpin = self.mpin_edit.text().strip()
        trading_pin = self.trading_pin_edit.text().strip()
        totp = self.totp_edit.text().strip()
        api_key = self.api_key_edit.text().strip()
        secret_key = self.secret_key_edit.text().strip()

        if not client_id or not mpin or not totp:
            self.auth_status_banner.setText("✗ Validation Error: Client ID, MPIN, and TOTP Secret are required for testing.")
            self.auth_status_banner.setStyleSheet("""
                background-color: #7f1d1d;
                border: 1px solid #ef4444;
                border-radius: 6px;
                color: #fca5a5;
                font-size: 12px;
                font-weight: bold;
                padding: 8px 12px;
            """)
            return

        self.auth_status_banner.setText(f"⏳ Connecting to {broker} gateway with live TOTP...")
        self.auth_status_banner.setStyleSheet("""
            background-color: #78350f;
            border: 1px solid #f59e0b;
            border-radius: 6px;
            color: #fde68a;
            font-size: 12px;
            font-weight: bold;
            padding: 8px 12px;
        """)
        self.btn_test_auth.setEnabled(False)

        def run_auth_handshake():
            try:
                success = False
                err_msg = ""

                if broker == "ANGEL_ONE":
                    inst = AngelOneBroker(vault_manager=self.vault, db_handler=self.db)
                    success = inst.authenticate(
                        client_id=client_id,
                        mpin=mpin,
                        api_key=api_key,
                        totp_secret=totp,
                        trading_pin=trading_pin
                    )
                    err_msg = inst._connection_error or "Angel One SmartAPI handshake rejected"
                    inst.disconnect()

                elif broker == "SHOONYA":
                    inst = ShoonyaBroker(vault_manager=self.vault, db_handler=self.db)
                    success = inst.authenticate(
                        user_id=client_id,
                        password=mpin,
                        api_key=api_key,
                        vendor_code=secret_key or f"{client_id}_U",
                        totp_secret=totp,
                        trading_pin=trading_pin
                    )
                    err_msg = inst._connection_error or "Shoonya NorenAPI handshake rejected"
                    inst.disconnect()

                elif broker == "GROWW":
                    inst = GrowwBroker(vault_manager=self.vault, db_handler=self.db)
                    success = inst.authenticate(
                        client_id=client_id,
                        password=mpin,
                        api_key=api_key,
                        totp_secret=totp,
                        trading_pin=trading_pin
                    )
                    err_msg = inst._connection_error or "Groww gateway handshake rejected"
                    inst.disconnect()

                self._apply_test_auth_result(success, err_msg, broker)

            except Exception as exc:
                self._apply_test_auth_result(False, str(exc), broker)

        t = threading.Thread(target=run_auth_handshake, daemon=True, name="TestLiveAuth_Thread")
        t.start()

    def _apply_test_auth_result(self, success: bool, error_msg: str, broker: str) -> None:
        """Inline banner updater reflecting test result."""
        try:
            self.btn_test_auth.setEnabled(True)
            if success:
                self.auth_status_banner.setText(f"✓ Connected Successfully! Session Active (JWT/Token Acquired for {broker}).")
                self.auth_status_banner.setStyleSheet("""
                    background-color: #064e3b;
                    border: 1px solid #10b981;
                    border-radius: 6px;
                    color: #34d399;
                    font-size: 12px;
                    font-weight: bold;
                    padding: 8px 12px;
                """)
            else:
                clean_err = error_msg[:60] + "..." if len(error_msg) > 60 else error_msg
                self.auth_status_banner.setText(f"✗ Connection Failed: {clean_err}")
                self.auth_status_banner.setStyleSheet("""
                    background-color: #7f1d1d;
                    border: 1px solid #ef4444;
                    border-radius: 6px;
                    color: #fca5a5;
                    font-size: 12px;
                    font-weight: bold;
                    padding: 8px 12px;
                """)
        except Exception:
            pass


class BrokerVaultDialog(QDialog):
    """
    Modal dialog wrapper around BrokerVaultWidget.
    Provides identical upgraded credentials and dynamic 2FA controls in a popup window.
    """

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("OmniTradePro — Multi-Broker Security Vault & Dynamic 2FA")
        self.resize(640, 780)
        self.setMinimumSize(580, 680)

        self.setStyleSheet("""
            QDialog {
                background-color: #070d18;
                border: 1px solid #142236;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("background: transparent; border: none;")
        self.vault_widget = BrokerVaultWidget(scroll)
        scroll.setWidget(self.vault_widget)
        layout.addWidget(scroll)

        # Close button at dialog bottom
        bottom_box = QHBoxLayout()
        bottom_box.addStretch()
        self.btn_close = QPushButton("Close", self)
        self.btn_close.setFixedWidth(100)
        try:
            self.btn_close.clicked.connect(self.accept)
        except Exception:
            pass
        bottom_box.addWidget(self.btn_close)
        layout.addLayout(bottom_box)

        # Mirror references for complete backwards compatibility
        self.db = self.vault_widget.db
        self.vault = self.vault_widget.vault
        self.client_id_edit = self.vault_widget.client_id_edit
        self.mpin_edit = self.vault_widget.mpin_edit
        self.trading_pin_edit = self.vault_widget.trading_pin_edit
        self.totp_edit = self.vault_widget.totp_edit
        self.api_key_edit = self.vault_widget.api_key_edit
        self.secret_key_edit = self.vault_widget.secret_key_edit
        self.broker_combo = self.vault_widget.broker_combo
        self.lbl_live_totp_code = self.vault_widget.lbl_live_totp_code
        self.auth_status_banner = self.vault_widget.auth_status_banner
        self.btn_test_auth = self.vault_widget.btn_test_auth
        self.btn_save = self.vault_widget.btn_save
        self.btn_set_active = self.vault_widget.btn_set_active

        # Notification controls accessors
        self.chk_trade_alerts = self.vault_widget.chk_trade_alerts
        self.chk_daily_summary = self.vault_widget.chk_daily_summary
        self.recipient_email_edit = self.vault_widget.recipient_email_edit
        self.sender_email_edit = self.vault_widget.sender_email_edit
        self.smtp_key_edit = self.vault_widget.smtp_key_edit
        self.btn_test_notify = self.vault_widget.btn_test_notify
        self.lbl_notify_status = self.vault_widget.lbl_notify_status
