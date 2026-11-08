#!/usr/bin/env python3
"""
OmniTradePro - Unified Sidebar Settings Page View (Page 11)
Platform: Windows 10/11 64-bit | Python 3.10+
Directly embeds the unified BrokerVaultWidget, synchronizing with VaultManager
and database/omnitrade_vault.db with AES-256 field-level encryption.

Features:
- Broker selector tabs (Angel One, Shoonya, Groww) with active pill styling
- Inputs: Client ID, 4-digit MPIN, 6-digit Trading PIN (TPIN with show/hide), 32-char TOTP Secret (show/hide), API Key, Secret/Vendor code
- Live Rolling TOTP Badge: Active 1-second QTimer calculating pyotp.TOTP(secret).now() with large monospace digits [ 4 8 2 9 1 0 ]
  and synchronized 30-second countdown bar
- [ ⚡ Test Live Auth ] asynchronous connection verification
- [ Save & Encrypt (AES-256) ] and [ Set Active ] buttons
"""

from ui.views import BasePageView
from ui.vault_dialog import BrokerVaultWidget


class SettingsView(BasePageView):
    """
    Page 11: Unified Sidebar Settings View
    Directly embeds the upgraded glassmorphic BrokerVaultWidget backed by AES-256 VaultManager.
    Eliminates all duplicate or divergent settings surfaces across the application.
    """

    def __init__(self, parent=None) -> None:
        super().__init__(
            "⚙ BROKER VAULT & DYNAMIC 2FA CREDENTIALS",
            "AES-256 encrypted credential management for Angel One, Shoonya, and Groww.",
            parent
        )
        self.vault_widget = BrokerVaultWidget(self.container)
        self.layout_main.addWidget(self.vault_widget)

        # Direct accessors for backward compatibility
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
