#!/usr/bin/env python3
"""
OmniTradePro - Multi-Broker Vault & 2FA Configuration Dialog
Platform: Windows 10/11 64-bit | Python 3.10+
Provides an institutional frosted glassmorphism interface to manage AES-256
encrypted credentials for Angel One, Shoonya, and Groww with live 2FA verification.
"""

from typing import Optional
from database.db_handler import DatabaseHandler

try:
    from PySide6.QtWidgets import (
        QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
        QPushButton, QComboBox, QFrame, QMessageBox, QGroupBox
    )
    from PySide6.QtCore import Qt
except ImportError:
    # Graceful shim for environments where PySide6 is not in current path
    class QDialog:
        def __init__(self, parent=None): pass
        def setWindowTitle(self, t): pass
        def setMinimumSize(self, w, h): pass
        def setLayout(self, l): pass
        def setStyleSheet(self, s): pass
        def setProperty(self, k, v): pass
        def exec(self): return 1
        def accept(self): pass
        def reject(self): pass
    class QWidget:
        def __init__(self, parent=None): pass
        def setStyleSheet(self, s): pass
        def setProperty(self, k, v): pass
        def setLayout(self, l): pass
    class QVBoxLayout:
        def __init__(self, *args): pass
        def addWidget(self, w): pass
        def addLayout(self, l): pass
        def addStretch(self, *args): pass
        def setContentsMargins(self, *args): pass
        def setSpacing(self, s): pass
    class QHBoxLayout(QVBoxLayout): pass
    class QLabel:
        def __init__(self, text="", parent=None): self.text = text
        def setText(self, t): self.text = t
        def setStyleSheet(self, s): pass
        def setAlignment(self, a): pass
        def setProperty(self, k, v): pass
    class QLineEdit:
        Normal = 0
        Password = 1
        def __init__(self, parent=None): self._text = ""
        def setEchoMode(self, m): pass
        def setPlaceholderText(self, p): pass
        def text(self): return self._text
        def setText(self, t): self._text = t
        def setStyleSheet(self, s): pass
        def setProperty(self, k, v): pass
    class QPushButton:
        def __init__(self, text="", parent=None): self.text = text
        def setProperty(self, k, v): pass
        def setStyleSheet(self, s): pass
        def setEnabled(self, e): pass
        def clicked(self): pass
    class QComboBox:
        def __init__(self, parent=None): self._items = []
        def addItems(self, items): self._items.extend(items)
        def currentText(self): return self._items[0] if self._items else ""
        def setCurrentText(self, t): pass
        def currentTextChanged(self): pass
        def setStyleSheet(self, s): pass
        def setProperty(self, k, v): pass
    class QFrame:
        def __init__(self, parent=None): pass
        def setFrameShape(self, s): pass
        def setProperty(self, k, v): pass
        def setStyleSheet(self, s): pass
        def setLayout(self, l): pass
    class QGroupBox:
        def __init__(self, title="", parent=None): pass
        def setStyleSheet(self, s): pass
        def setLayout(self, l): pass
    class QMessageBox:
        @staticmethod
        def information(p, t, m): pass
        @staticmethod
        def warning(p, t, m): pass
        @staticmethod
        def critical(p, t, m): pass
    class Qt:
        AlignCenter = 0x0004


class BrokerVaultDialog(QDialog):
    """
    Modal dialog allowing users to securely input, encrypt, test, and activate
    credentials across institutional broker gateways.
    """

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("OmniTradePro — Multi-Broker Security Vault & 2FA")
        self.setMinimumSize(560, 520)
        self.db = DatabaseHandler()
        self._init_ui()
        self._load_selected_broker_credentials()

    def _init_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 24, 24, 24)
        main_layout.setSpacing(16)

        # Header Title
        title_label = QLabel("INSTITUTIONAL BROKER VAULT", self)
        title_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #00e5ff; letter-spacing: 1px;")
        subtitle_label = QLabel("AES-256 field-level encrypted storage for live market gateways.", self)
        subtitle_label.setStyleSheet("font-size: 11px; color: #94a3b8;")

        main_layout.addWidget(title_label)
        main_layout.addWidget(subtitle_label)

        # Broker Selector
        sel_layout = QHBoxLayout()
        sel_label = QLabel("Target Gateway:", self)
        sel_label.setStyleSheet("font-weight: 600; color: #f0f4f8;")
        self.broker_combo = QComboBox(self)
        self.broker_combo.addItems(["ANGEL_ONE", "SHOONYA", "GROWW"])
        try:
            self.broker_combo.currentTextChanged.connect(self._on_broker_changed)
        except Exception:
            pass

        sel_layout.addWidget(sel_label)
        sel_layout.addWidget(self.broker_combo)
        sel_layout.addStretch()
        main_layout.addLayout(sel_layout)

        # Input Card Panel
        form_frame = QFrame(self)
        form_frame.setProperty("class", "cardPanel")
        form_frame.setStyleSheet("background-color: rgba(22, 30, 48, 0.65); border: 1px solid rgba(255, 255, 255, 0.12); border-radius: 8px; padding: 16px;")
        form_layout = QVBoxLayout(form_frame)
        form_layout.setSpacing(10)

        # Client ID / User Code
        form_layout.addWidget(QLabel("Client ID / User Code:", self))
        self.client_id_edit = QLineEdit(self)
        self.client_id_edit.setPlaceholderText("e.g. A100982 (Angel One) or FA55421 (Shoonya)")
        form_layout.addWidget(self.client_id_edit)

        # 4-Digit Login MPIN
        form_layout.addWidget(QLabel("Login Password / 4-Digit MPIN:", self))
        self.mpin_edit = QLineEdit(self)
        self.mpin_edit.setEchoMode(QLineEdit.Password)
        self.mpin_edit.setPlaceholderText("Enter 4-digit numeric MPIN")
        form_layout.addWidget(self.mpin_edit)

        # 32-Character TOTP Secret
        form_layout.addWidget(QLabel("32-Character Base32 TOTP Secret:", self))
        self.totp_edit = QLineEdit(self)
        self.totp_edit.setEchoMode(QLineEdit.Password)
        self.totp_edit.setPlaceholderText("e.g. JBSWY3DPEHPK3PXPJBSWY3DPEHPK3PXP")
        form_layout.addWidget(self.totp_edit)

        # 2FA Test & Verify Row
        totp_verify_layout = QHBoxLayout()
        self.btn_test_totp = QPushButton("Verify Live 2FA Code", self)
        try:
            self.btn_test_totp.clicked.connect(self._verify_live_totp)
        except Exception:
            pass

        self.totp_preview_label = QLabel("Status: Unverified", self)
        self.totp_preview_label.setStyleSheet("color: #94a3b8; font-weight: 600;")
        totp_verify_layout.addWidget(self.btn_test_totp)
        totp_verify_layout.addWidget(self.totp_preview_label)
        totp_verify_layout.addStretch()
        form_layout.addLayout(totp_verify_layout)

        # API Key
        form_layout.addWidget(QLabel("Broker API Key (SmartAPI / App Key):", self))
        self.api_key_edit = QLineEdit(self)
        self.api_key_edit.setPlaceholderText("Enter developer API key")
        form_layout.addWidget(self.api_key_edit)

        # Secret Key / Vendor Code
        form_layout.addWidget(QLabel("Secret Key / Vendor Code (Optional):", self))
        self.secret_key_edit = QLineEdit(self)
        self.secret_key_edit.setEchoMode(QLineEdit.Password)
        self.secret_key_edit.setPlaceholderText("Enter Secret Key if provided")
        form_layout.addWidget(self.secret_key_edit)

        main_layout.addWidget(form_frame)

        # Active Status Indicator
        self.status_badge = QLabel("Gateway Status: Inactive", self)
        self.status_badge.setStyleSheet("font-weight: 700; color: #ffab00;")
        main_layout.addWidget(self.status_badge)

        # Action Buttons
        btn_layout = QHBoxLayout()
        self.btn_save = QPushButton("Save & Encrypt Credentials", self)
        self.btn_save.setStyleSheet("background-color: #2979ff; color: white; font-weight: bold;")
        try:
            self.btn_save.clicked.connect(self._save_credentials)
        except Exception:
            pass

        self.btn_set_active = QPushButton("Set As Active Gateway", self)
        self.btn_set_active.setStyleSheet("background-color: #00c853; color: white; font-weight: bold;")
        try:
            self.btn_set_active.clicked.connect(self._set_active_gateway)
        except Exception:
            pass

        self.btn_close = QPushButton("Close", self)
        try:
            self.btn_close.clicked.connect(self.accept)
        except Exception:
            pass

        btn_layout.addWidget(self.btn_save)
        btn_layout.addWidget(self.btn_set_active)
        btn_layout.addWidget(self.btn_close)
        main_layout.addLayout(btn_layout)

    def _on_broker_changed(self, broker_name: str) -> None:
        """Loads credentials when the user changes selected broker."""
        self._load_selected_broker_credentials()

    def _load_selected_broker_credentials(self) -> None:
        """Pulls decrypted credentials from vault if present."""
        broker = self.broker_combo.currentText().strip().upper()
        try:
            creds = self.db.get_broker_credentials(broker)
            self.client_id_edit.setText(creds.get("client_id", ""))
            self.mpin_edit.setText(creds.get("login_mpin", ""))
            self.totp_edit.setText(creds.get("totp_secret", ""))
            self.api_key_edit.setText(creds.get("api_key", ""))
            self.secret_key_edit.setText(creds.get("secret_key", ""))

            if creds.get("is_active"):
                self.status_badge.setText(f"Gateway Status: ACTIVE ({broker})")
                self.status_badge.setStyleSheet("font-weight: 700; color: #00e676;")
            else:
                self.status_badge.setText("Gateway Status: Inactive")
                self.status_badge.setStyleSheet("font-weight: 700; color: #94a3b8;")
            self.totp_preview_label.setText("Status: Loaded from vault")
            self.totp_preview_label.setStyleSheet("color: #00e5ff; font-weight: 600;")
        except Exception:
            # Clear fields if not yet configured
            self.client_id_edit.setText("")
            self.mpin_edit.setText("")
            self.totp_edit.setText("")
            self.api_key_edit.setText("")
            self.secret_key_edit.setText("")
            self.status_badge.setText("Gateway Status: Not Configured")
            self.status_badge.setStyleSheet("font-weight: 700; color: #ffab00;")
            self.totp_preview_label.setText("Status: Unverified")
            self.totp_preview_label.setStyleSheet("color: #94a3b8;")

    def _verify_live_totp(self) -> None:
        """Generates real-time 6-digit TOTP to verify secret correctness."""
        secret = self.totp_edit.text().strip()
        if not secret:
            self.totp_preview_label.setText("Error: TOTP Secret is empty")
            self.totp_preview_label.setStyleSheet("color: #ff3d71; font-weight: 600;")
            return

        try:
            token = DatabaseHandler.generate_dynamic_totp(secret)
            self.totp_preview_label.setText(f"Live 6-Digit TOTP: {token} (Valid)")
            self.totp_preview_label.setStyleSheet("color: #00e676; font-weight: 700;")
        except Exception as exc:
            self.totp_preview_label.setText(f"Invalid Secret: {str(exc)[:25]}")
            self.totp_preview_label.setStyleSheet("color: #ff3d71; font-weight: 600;")

    def _save_credentials(self) -> None:
        """Encrypts and commits credentials to database.db_handler."""
        broker = self.broker_combo.currentText().strip().upper()
        client_id = self.client_id_edit.text().strip()
        mpin = self.mpin_edit.text().strip()
        totp = self.totp_edit.text().strip()
        api_key = self.api_key_edit.text().strip()
        secret_key = self.secret_key_edit.text().strip()

        if not client_id or not mpin or not totp:
            QMessageBox.warning(self, "Validation Error", "Client ID, MPIN, and TOTP Secret are mandatory.")
            return

        try:
            self.db.save_broker_credentials(
                broker_name=broker,
                client_id=client_id,
                login_mpin=mpin,
                totp_secret=totp,
                api_key=api_key,
                secret_key=secret_key
            )
            QMessageBox.information(
                self,
                "Vault Updated",
                f"Credentials for {broker} successfully encrypted with AES-256 and committed to vault."
            )
            self._load_selected_broker_credentials()
        except Exception as exc:
            QMessageBox.critical(self, "Encryption Error", f"Failed to save credentials: {str(exc)}")

    def _set_active_gateway(self) -> None:
        """Marks the selected broker as the primary active gateway."""
        broker = self.broker_combo.currentText().strip().upper()
        success = self.db.set_active_broker(broker)
        if success:
            QMessageBox.information(self, "Active Gateway Updated", f"{broker} is now the active market gateway.")
            self._load_selected_broker_credentials()
        else:
            QMessageBox.warning(self, "Action Failed", f"Could not activate {broker}. Ensure credentials are saved first.")

