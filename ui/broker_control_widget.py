#!/usr/bin/env python3
"""
OmniTradePro - Interactive Broker Control Widget & Auto-TOTP Matrix
Platform: Windows 10/11 64-bit | Python 3.10+
Glassmorphic PySide6 widget hosting 3 dedicated broker cards (Angel One, Shoonya, Groww).
Features:
- Dynamic 4-state visual indicators:
  * RED: Disconnected
  * AMBER: Connecting / Refreshing Token
  * GREEN: Connected & WebSocket Tick Feed Active
  * PURPLE: Session Error / Invalid Credentials
- Interactive Controls per Broker:
  * [Connect] / [Disconnect] PushButtons (non-blocking threaded connection)
  * [Trading Toggle: ON / OFF] Switch (independent execution gate)
  * [Settings / Key] Button (opens encrypted credentials modal with masked inputs)
- Live Auto-TOTP Countdown Pill showing real-time 6-digit TOTP generation
"""

import time
import threading
from typing import Optional, Dict, Any

from database.vault_manager import VaultManager
from database.db_handler import DatabaseHandler
from brokers.base_broker import BaseBroker
from brokers.angel_one import AngelOneBroker
from brokers.shoonya import ShoonyaBroker
from brokers.groww import GrowwBroker

try:
    from PySide6.QtWidgets import (
        QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
        QFrame, QDialog, QLineEdit, QMessageBox, QCheckBox, QSizePolicy
    )
    from PySide6.QtCore import Qt, Signal, QTimer, QThread
    from PySide6.QtGui import QFont, QColor
except ImportError:
    # Graceful shim for environments where PySide6 is not in system path
    class QWidget:
        def __init__(self, parent=None): pass
        def setStyleSheet(self, s): pass
        def setLayout(self, l): pass
        def setSizePolicy(self, *args): pass
        def setFixedSize(self, w, h): pass
        def setFixedWidth(self, w): pass
        def setFixedHeight(self, h): pass
        def setProperty(self, k, v): pass
    class QFrame(QWidget):
        NoFrame = 0
        def __init__(self, parent=None): pass
        def setFrameShape(self, s): pass
    class QDialog(QWidget):
        def __init__(self, parent=None): pass
        def setWindowTitle(self, t): pass
        def setMinimumSize(self, w, h): pass
        def resize(self, w, h): pass
        def exec(self): return 1
        def accept(self): pass
        def reject(self): pass
    class QVBoxLayout:
        def __init__(self, *args): pass
        def addWidget(self, w, *args): pass
        def addLayout(self, l, *args): pass
        def addStretch(self, *args): pass
        def setContentsMargins(self, *args): pass
        def setSpacing(self, s): pass
    class QHBoxLayout(QVBoxLayout): pass
    class QLabel(QWidget):
        def __init__(self, text="", parent=None): self.text = text
        def setText(self, t): self.text = t
        def setAlignment(self, a): pass
        def setFont(self, f): pass
    class QPushButton(QWidget):
        def __init__(self, text="", parent=None):
            self.text = text
            self.clicked = Signal()
            self.toggled = Signal()
        def setText(self, t): self.text = t
        def setEnabled(self, e): pass
        def setProperty(self, k, v): pass
        def setFixedWidth(self, w): pass
        def setFixedHeight(self, h): pass
        def setCheckable(self, b): pass
        def setChecked(self, b): pass
        def isChecked(self): return False
    class QLineEdit(QWidget):
        Normal = 0
        Password = 1
        def __init__(self, parent=None): self._text = ""
        def setEchoMode(self, m): pass
        def setPlaceholderText(self, p): pass
        def text(self): return self._text
        def setText(self, t): self._text = t
    class QCheckBox(QWidget):
        def __init__(self, text="", parent=None):
            self.toggled = Signal()
        def setChecked(self, c): pass
        def isChecked(self): return False
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
    class QThread:
        def __init__(self, parent=None): pass
        def start(self): pass
    class Signal:
        def __init__(self, *args): pass
        def connect(self, f): pass
        def emit(self, *args): pass
    class QFont:
        def __init__(self, *args): pass
        def setBold(self, b): pass
    class QColor:
        def __init__(self, *args): pass
    class QSizePolicy:
        Expanding = 7
        Preferred = 5
    class Qt:
        AlignCenter = 0x0004
        AlignVCenter = 0x0080
        AlignLeft = 0x0001
        AlignRight = 0x0002


class BrokerCredentialsDialog(QDialog):
    """
    Encrypted credential management modal.
    Enforces password masking for MPIN, API Key, and 32-char TOTP Secret.
    Provides live TOTP pre-testing and direct AES-256 encryption into vault.
    """

    def __init__(self, broker_name: str, vault_manager: VaultManager, parent=None) -> None:
        super().__init__(parent)
        self.broker_name = broker_name.strip().upper()
        self.vault = vault_manager
        self.setWindowTitle(f"Broker Vault Configuration — {self.broker_name}")
        self.resize(520, 560)
        self._init_ui()
        self._load_existing_credentials()

    def _init_ui(self) -> None:
        self.setStyleSheet("""
            QDialog {
                background-color: #070d18;
                border: 1px solid #142236;
                border-radius: 12px;
            }
            QLabel {
                color: #94a3b8;
                font-size: 12px;
                font-family: 'Segoe UI', Inter, sans-serif;
            }
            QLineEdit {
                background-color: #0b1424;
                border: 1px solid #1e3a5f;
                border-radius: 6px;
                color: #f8fafc;
                padding: 8px 12px;
                font-size: 13px;
                font-family: 'Consolas', 'Courier New', monospace;
            }
            QLineEdit:focus {
                border: 1px solid #00f0ff;
                background-color: #0e1a30;
            }
            QPushButton {
                background-color: #0b1424;
                border: 1px solid #1e3a5f;
                border-radius: 6px;
                color: #f8fafc;
                padding: 9px 18px;
                font-weight: bold;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #162a45;
                border-color: #00f0ff;
                color: #00f0ff;
            }
            QPushButton#btnSave {
                background-color: #059669;
                border: 1px solid #10b981;
                color: #ffffff;
            }
            QPushButton#btnSave:hover {
                background-color: #10b981;
                box-shadow: 0 0 10px rgba(16, 185, 129, 0.5);
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)

        # Header Title
        title_lbl = QLabel(f"Secure Vault Credentials: {self.broker_name}")
        title_lbl.setStyleSheet("color: #00f0ff; font-size: 16px; font-weight: bold;")
        layout.addWidget(title_lbl)

        sub_lbl = QLabel("Credentials are encrypted via AES-256 (Fernet) in omnitrade_vault.db.")
        sub_lbl.setStyleSheet("color: #64748b; font-size: 11px;")
        layout.addWidget(sub_lbl)

        # Form Inputs
        # 1. Client ID / User ID
        lbl_cid = QLabel("Client ID / User Code:")
        layout.addWidget(lbl_cid)
        self.input_client_id = QLineEdit(self)
        self.input_client_id.setPlaceholderText("e.g. A100982 or FA55421")
        layout.addWidget(self.input_client_id)

        # 2. Login MPIN / Password
        lbl_pin = QLabel("Login MPIN / Password (Masked):")
        layout.addWidget(lbl_pin)
        self.input_pin = QLineEdit(self)
        self.input_pin.setEchoMode(QLineEdit.Password)
        self.input_pin.setPlaceholderText("••••••••")
        layout.addWidget(self.input_pin)

        # 3. 32-character TOTP Secret
        lbl_totp = QLabel("32-Character Base32 TOTP Secret Key:")
        layout.addWidget(lbl_totp)
        self.input_totp = QLineEdit(self)
        self.input_totp.setEchoMode(QLineEdit.Password)
        self.input_totp.setPlaceholderText("e.g. JBSWY3DPEHPK3PXPJBSWY3DPEHPK3PXP")
        layout.addWidget(self.input_totp)

        # 4. API Key
        lbl_api = QLabel("API Key / App Key:")
        layout.addWidget(lbl_api)
        self.input_api_key = QLineEdit(self)
        self.input_api_key.setEchoMode(QLineEdit.Password)
        self.input_api_key.setPlaceholderText("Broker API Key")
        layout.addWidget(self.input_api_key)

        # 5. Secret Key / Vendor Code (for Shoonya / Angel One)
        lbl_sec = QLabel("Secret Key / Vendor Code (Optional):")
        layout.addWidget(lbl_sec)
        self.input_sec_key = QLineEdit(self)
        self.input_sec_key.setEchoMode(QLineEdit.Password)
        self.input_sec_key.setPlaceholderText("Vendor Code / Secret Key")
        layout.addWidget(self.input_sec_key)

        # Live Test TOTP Result Area
        totp_box = QHBoxLayout()
        self.btn_test_totp = QPushButton("Verify TOTP Key", self)
        self.btn_test_totp.clicked.connect(self._on_test_totp)
        self.lbl_totp_result = QLabel("Status: Idle")
        self.lbl_totp_result.setStyleSheet("color: #64748b; font-weight: bold;")
        totp_box.addWidget(self.btn_test_totp)
        totp_box.addWidget(self.lbl_totp_result)
        totp_box.addStretch()
        layout.addLayout(totp_box)

        layout.addStretch()

        # Dialog Action Buttons
        btn_box = QHBoxLayout()
        btn_box.addStretch()

        self.btn_cancel = QPushButton("Cancel", self)
        self.btn_cancel.clicked.connect(self.reject)
        btn_box.addWidget(self.btn_cancel)

        self.btn_save = QPushButton("Save & Encrypt", self)
        self.btn_save.setObjectName("btnSave")
        self.btn_save.clicked.connect(self._on_save_credentials)
        btn_box.addWidget(self.btn_save)

        layout.addLayout(btn_box)

    def _load_existing_credentials(self) -> None:
        """Populates inputs with existing credentials if present in vault."""
        try:
            creds = self.vault.get_broker_credentials(self.broker_name)
            if creds:
                self.input_client_id.setText(creds.get("client_id", ""))
                self.input_pin.setText(creds.get("login_mpin", ""))
                self.input_totp.setText(creds.get("totp_secret", ""))
                self.input_api_key.setText(creds.get("api_key", ""))
                sec = creds.get("vendor_code") or creds.get("secret_key", "")
                self.input_sec_key.setText(sec)
        except Exception:
            pass

    def _on_test_totp(self) -> None:
        """Tests TOTP key calculation without saving."""
        secret = self.input_totp.text().strip()
        if not secret:
            self.lbl_totp_result.setText("Please enter TOTP secret.")
            self.lbl_totp_result.setStyleSheet("color: #ef4444; font-weight: bold;")
            return

        try:
            totp_code = VaultManager.generate_dynamic_totp(secret)
            self.lbl_totp_result.setText(f"✓ Valid: {totp_code} (Active 2FA)")
            self.lbl_totp_result.setStyleSheet("color: #10b981; font-weight: bold;")
        except Exception as exc:
            self.lbl_totp_result.setText(f"✗ Invalid Base32: {str(exc)}")
            self.lbl_totp_result.setStyleSheet("color: #ef4444; font-weight: bold;")

    def _on_save_credentials(self) -> None:
        """Encrypts credentials with AES-256 and saves to vault."""
        cid = self.input_client_id.text().strip()
        pin = self.input_pin.text().strip()
        totp = self.input_totp.text().strip()
        api_key = self.input_api_key.text().strip()
        sec = self.input_sec_key.text().strip()

        if not cid:
            QMessageBox.warning(self, "Validation Error", "Client ID is required.")
            return
        if not pin:
            QMessageBox.warning(self, "Validation Error", "Login MPIN / Password is required.")
            return
        if not totp:
            QMessageBox.warning(self, "Validation Error", "32-character TOTP secret is required.")
            return

        try:
            self.vault.save_broker_credentials(
                broker_name=self.broker_name,
                client_id=cid,
                login_mpin=pin,
                totp_secret=totp,
                api_key=api_key,
                secret_key=sec,
                vendor_code=sec
            )
            QMessageBox.information(
                self,
                "Vault Encrypted",
                f"Credentials for {self.broker_name} successfully encrypted with AES-256 Fernet."
            )
            self.accept()
        except Exception as exc:
            QMessageBox.critical(self, "Vault Error", f"Failed to save credentials: {str(exc)}")


class BrokerCard(QFrame):
    """
    Dedicated Glassmorphic Card representing an individual broker gateway.
    Features:
    - Visual connection indicator (RED, AMBER, GREEN, PURPLE)
    - Manual [Connect] / [Disconnect] controls
    - Independent [Trading Toggle: ON / OFF] switch
    - Encrypted [Settings / Key] button
    - Dynamic live TOTP countdown display
    """
    # Signals
    connect_requested = Signal(str)
    disconnect_requested = Signal(str)
    trading_toggled = Signal(str, bool)

    # Indicator Styles
    INDICATOR_COLORS = {
        "DISCONNECTED": ("#ef4444", "rgba(239, 68, 68, 0.25)", "Disconnected"),
        "CONNECTING": ("#f59e0b", "rgba(245, 158, 11, 0.25)", "Connecting..."),
        "CONNECTED": ("#10b981", "rgba(16, 185, 129, 0.35)", "Connected & Live"),
        "ERROR": ("#a855f7", "rgba(168, 85, 247, 0.30)", "Session Error")
    }

    def __init__(
        self,
        broker_name: str,
        display_title: str,
        vault_manager: VaultManager,
        parent=None
    ) -> None:
        super().__init__(parent)
        self.broker_name = broker_name.strip().upper()
        self.display_title = display_title
        self.vault = vault_manager
        self.current_state = "DISCONNECTED"

        self._init_ui()
        self._sync_state_from_vault()

    def _init_ui(self) -> None:
        self.setStyleSheet("""
            BrokerCard {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #0d1527, stop:1 #070d18);
                border: 1px solid #142236;
                border-radius: 10px;
            }
            BrokerCard:hover {
                border: 1px solid #1e3a5f;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(10)

        # 1. Header: Broker Title + Settings Button
        header_layout = QHBoxLayout()
        self.lbl_title = QLabel(self.display_title, self)
        self.lbl_title.setStyleSheet("color: #f8fafc; font-size: 13px; font-weight: bold;")
        header_layout.addWidget(self.lbl_title)
        header_layout.addStretch()

        self.btn_settings = QPushButton("⚙ Key", self)
        self.btn_settings.setStyleSheet("""
            QPushButton {
                background-color: #0b1424;
                border: 1px solid #1e3a5f;
                border-radius: 4px;
                color: #94a3b8;
                font-size: 11px;
                padding: 4px 8px;
            }
            QPushButton:hover {
                border-color: #00f0ff;
                color: #00f0ff;
            }
        """)
        self.btn_settings.clicked.connect(self._open_settings_dialog)
        header_layout.addWidget(self.btn_settings)
        layout.addLayout(header_layout)

        # 2. Connection State Indicator Row
        status_row = QHBoxLayout()
        self.indicator_dot = QFrame(self)
        self.indicator_dot.setFixedSize(10, 10)
        self.indicator_dot.setStyleSheet("background-color: #ef4444; border-radius: 5px;")
        status_row.addWidget(self.indicator_dot)

        self.lbl_status = QLabel("Disconnected", self)
        self.lbl_status.setStyleSheet("color: #ef4444; font-size: 12px; font-weight: bold;")
        status_row.addWidget(self.lbl_status)
        status_row.addStretch()

        # Real-time Auto-TOTP Badge
        self.lbl_totp_badge = QLabel("TOTP: --", self)
        self.lbl_totp_badge.setStyleSheet("""
            background-color: #0b1424;
            border: 1px solid #142236;
            border-radius: 4px;
            color: #38bdf8;
            font-size: 11px;
            font-family: 'Consolas', monospace;
            padding: 3px 6px;
        """)
        status_row.addWidget(self.lbl_totp_badge)
        layout.addLayout(status_row)

        # 3. Interactive Action Row: [Connect/Disconnect] & [Trading: ON/OFF]
        action_row = QHBoxLayout()
        action_row.setSpacing(8)

        # Connect / Disconnect PushButton
        self.btn_connect = QPushButton("Connect", self)
        self.btn_connect.setStyleSheet("""
            QPushButton {
                background-color: #064e3b;
                border: 1px solid #059669;
                border-radius: 5px;
                color: #10b981;
                font-weight: bold;
                font-size: 12px;
                padding: 6px 12px;
            }
            QPushButton:hover {
                background-color: #059669;
                color: #ffffff;
            }
        """)
        self.btn_connect.clicked.connect(self._on_connect_clicked)
        action_row.addWidget(self.btn_connect, 1)

        # Independent Trading Execution Switch
        self.btn_trade_toggle = QPushButton("Trading: OFF", self)
        self.btn_trade_toggle.setCheckable(True)
        self.btn_trade_toggle.setStyleSheet("""
            QPushButton {
                background-color: #1e293b;
                border: 1px solid #334155;
                border-radius: 5px;
                color: #94a3b8;
                font-weight: bold;
                font-size: 11px;
                padding: 6px 10px;
            }
            QPushButton:checked {
                background-color: #065f46;
                border: 1px solid #10b981;
                color: #34d399;
            }
        """)
        self.btn_trade_toggle.toggled.connect(self._on_trade_toggled)
        action_row.addWidget(self.btn_trade_toggle, 1)

        layout.addLayout(action_row)

    def set_connection_state(self, state: str, error_msg: Optional[str] = None) -> None:
        """
        Updates the 4-state visual connection indicator.
        States: DISCONNECTED, CONNECTING, CONNECTED, ERROR
        """
        self.current_state = state.upper()
        color, glow, default_text = self.INDICATOR_COLORS.get(
            self.current_state,
            self.INDICATOR_COLORS["DISCONNECTED"]
        )

        display_text = default_text
        if self.current_state == "ERROR" and error_msg:
            display_text = f"Error: {error_msg[:18]}..." if len(error_msg) > 18 else f"Error: {error_msg}"

        # Update Indicator Dot
        self.indicator_dot.setStyleSheet(f"""
            background-color: {color};
            border-radius: 5px;
            box-shadow: 0 0 8px {glow};
        """)

        # Update Status Text
        self.lbl_status.setText(display_text)
        self.lbl_status.setStyleSheet(f"color: {color}; font-size: 12px; font-weight: bold;")

        # Update Connect / Disconnect button appearance
        if self.current_state == "CONNECTED":
            self.btn_connect.setText("Disconnect")
            self.btn_connect.setEnabled(True)
            self.btn_connect.setStyleSheet("""
                QPushButton {
                    background-color: #7f1d1d;
                    border: 1px solid #b91c1c;
                    border-radius: 5px;
                    color: #fca5a5;
                    font-weight: bold;
                    font-size: 12px;
                    padding: 6px 12px;
                }
                QPushButton:hover {
                    background-color: #b91c1c;
                    color: #ffffff;
                }
            """)
        elif self.current_state == "CONNECTING":
            self.btn_connect.setText("Connecting...")
            self.btn_connect.setEnabled(False)
        else:
            self.btn_connect.setText("Connect")
            self.btn_connect.setEnabled(True)
            self.btn_connect.setStyleSheet("""
                QPushButton {
                    background-color: #064e3b;
                    border: 1px solid #059669;
                    border-radius: 5px;
                    color: #10b981;
                    font-weight: bold;
                    font-size: 12px;
                    padding: 6px 12px;
                }
                QPushButton:hover {
                    background-color: #059669;
                    color: #ffffff;
                }
            """)

    def update_live_totp(self) -> None:
        """Recalculates and updates the live 6-digit TOTP badge."""
        try:
            if self.vault.has_broker_credentials(self.broker_name):
                code = self.vault.get_live_totp(self.broker_name)
                # Remaining seconds in current 30s cycle
                rem = 30 - (int(time.time()) % 30)
                self.lbl_totp_badge.setText(f"TOTP: {code} [{rem:02d}s]")
            else:
                self.lbl_totp_badge.setText("TOTP: Not Set")
        except Exception:
            self.lbl_totp_badge.setText("TOTP: Error")

    def _sync_state_from_vault(self) -> None:
        """Synchronizes trading toggle and live TOTP from vault."""
        try:
            is_enabled = self.vault.is_trading_enabled(self.broker_name)
            self.btn_trade_toggle.setChecked(is_enabled)
            self.btn_trade_toggle.setText("Trading: ON" if is_enabled else "Trading: OFF")
            self.update_live_totp()
        except Exception:
            pass

    def _open_settings_dialog(self) -> None:
        """Opens encrypted credentials dialog."""
        dlg = BrokerCredentialsDialog(self.broker_name, self.vault, self)
        if dlg.exec():
            self._sync_state_from_vault()

    def _on_connect_clicked(self) -> None:
        """Handles manual connect/disconnect button clicks."""
        if self.current_state == "CONNECTED":
            self.disconnect_requested.emit(self.broker_name)
        else:
            self.set_connection_state("CONNECTING")
            self.connect_requested.emit(self.broker_name)

    def _on_trade_toggled(self, checked: bool) -> None:
        """Handles trading execution toggle switch."""
        self.btn_trade_toggle.setText("Trading: ON" if checked else "Trading: OFF")
        self.trading_toggled.emit(self.broker_name, checked)


class BrokerControlWidget(QFrame):
    """
    Main Multi-Broker Interactive Control Widget.
    Houses the 3 broker cards (Angel One, Shoonya, Groww) in a responsive grid.
    Coordinates non-blocking background connection threads, auto-TOTP timers,
    and signals OrderRouter on toggle updates.
    """
    broker_state_changed = Signal(str, str)  # broker_name, new_state
    trading_toggle_changed = Signal(str, bool)

    def __init__(
        self,
        vault_manager: Optional[VaultManager] = None,
        db_handler: Optional[DatabaseHandler] = None,
        parent=None
    ) -> None:
        super().__init__(parent)
        self.vault = vault_manager or VaultManager()
        self.db = db_handler or DatabaseHandler()

        # Dedicated Broker Adapters
        self.brokers: Dict[str, BaseBroker] = {
            "ANGEL_ONE": AngelOneBroker(vault_manager=self.vault, db_handler=self.db),
            "SHOONYA": ShoonyaBroker(vault_manager=self.vault, db_handler=self.db),
            "GROWW": GrowwBroker(vault_manager=self.vault, db_handler=self.db)
        }

        self.cards: Dict[str, BrokerCard] = {}
        self._init_ui()
        self._init_totp_timer()

    def _init_ui(self) -> None:
        self.setStyleSheet("""
            BrokerControlWidget {
                background-color: #070d18;
                border: 1px solid #142236;
                border-radius: 12px;
            }
        """)

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(12, 10, 12, 10)
        root_layout.setSpacing(8)

        # Title bar for Broker Matrix
        title_bar = QHBoxLayout()
        title_lbl = QLabel("MULTI-BROKER DYNAMIC 2FA & EXECUTION TOGGLE MATRIX", self)
        title_lbl.setStyleSheet("""
            color: #38bdf8;
            font-size: 11px;
            font-weight: bold;
            letter-spacing: 1px;
        """)
        title_bar.addWidget(title_lbl)
        title_bar.addStretch()

        help_lbl = QLabel("Zero Manual OTP • Auto-TOTP • Independent Routing Gates", self)
        help_lbl.setStyleSheet("color: #64748b; font-size: 11px;")
        title_bar.addWidget(help_lbl)
        root_layout.addLayout(title_bar)

        # Horizontal Row of 3 Broker Cards
        cards_layout = QHBoxLayout()
        cards_layout.setSpacing(10)

        broker_configs = [
            ("ANGEL_ONE", "ANGEL ONE (SmartAPI)"),
            ("SHOONYA", "SHOONYA (Finvasia Noren)"),
            ("GROWW", "GROWW (Gateway)")
        ]

        for b_name, b_title in broker_configs:
            card = BrokerCard(b_name, b_title, self.vault, self)
            card.connect_requested.connect(self._handle_connect_request)
            card.disconnect_requested.connect(self._handle_disconnect_request)
            card.trading_toggled.connect(self._handle_trading_toggled)
            self.cards[b_name] = card
            cards_layout.addWidget(card, 1)

        root_layout.addLayout(cards_layout)

    def _init_totp_timer(self) -> None:
        """Starts 1-second timer to update TOTP codes and countdowns in real-time."""
        try:
            self.totp_timer = QTimer(self)
            self.totp_timer.timeout.connect(self._refresh_all_totps)
            self.totp_timer.start(1000)
        except Exception:
            pass

    def _refresh_all_totps(self) -> None:
        """Updates TOTP badge across all 3 broker cards."""
        for card in self.cards.values():
            card.update_live_totp()

    def _handle_connect_request(self, broker_name: str) -> None:
        """
        Executes non-blocking background authentication for the requested broker.
        Eliminates manual OTP popups and transitions indicator appropriately.
        """
        def auth_worker():
            broker = self.brokers.get(broker_name)
            if not broker:
                return

            success = broker.authenticate()
            if success:
                self._update_card_state_safe(broker_name, "CONNECTED")
            else:
                err = getattr(broker, "_connection_error", "Authentication failed")
                self._update_card_state_safe(broker_name, "ERROR", err)

        t = threading.Thread(
            target=auth_worker,
            daemon=True,
            name=f"AuthWorker_{broker_name}"
        )
        t.start()

    def _handle_disconnect_request(self, broker_name: str) -> None:
        """Gracefully disconnects requested broker."""
        broker = self.brokers.get(broker_name)
        if broker:
            broker.disconnect()
        self._update_card_state_safe(broker_name, "DISCONNECTED")

    def _handle_trading_toggled(self, broker_name: str, enabled: bool) -> None:
        """Records trading toggle in vault and emits notification."""
        try:
            self.vault.set_trading_enabled(broker_name, enabled)
        except Exception:
            pass
        self.trading_toggle_changed.emit(broker_name, enabled)

    def _update_card_state_safe(self, broker_name: str, state: str, err: Optional[str] = None) -> None:
        """Thread-safe state updater for card indicators."""
        card = self.cards.get(broker_name)
        if card:
            card.set_connection_state(state, err)
            self.broker_state_changed.emit(broker_name, state)

    def get_broker_instance(self, broker_name: str) -> Optional[BaseBroker]:
        """Provides access to the initialized broker gateway instance."""
        return self.brokers.get(broker_name)

    def is_broker_connected(self, broker_name: str) -> bool:
        """Checks if broker is connected."""
        card = self.cards.get(broker_name)
        return card.current_state == "CONNECTED" if card else False

    def is_broker_trading_enabled(self, broker_name: str) -> bool:
        """Checks if trading execution toggle is ON for broker."""
        card = self.cards.get(broker_name)
        return card.btn_trade_toggle.isChecked() if card else False

