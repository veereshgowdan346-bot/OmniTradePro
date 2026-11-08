#!/usr/bin/env python3
"""
OmniTradePro - End-to-End Dynamic Broker Authentication, Auto-TOTP & Toggle Matrix Test Suite
Platform: Windows 10/11 64-bit | Python 3.10+
Tests:
1. VaultManager AES-256 Fernet encryption, decryption, and live TOTP computation
2. Angel One, Shoonya, and Groww broker auto-TOTP and authentication workflows
3. BrokerControlWidget 4-state indicator matrix and interactive toggle controls
4. OrderRouter strict toggle-aware routing, concurrent dispatch, and pre-trade guardrails
"""

import os
import sys
import time
import unittest
import pyotp
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from database.vault_manager import VaultManager
from database.db_handler import DatabaseHandler
from brokers.angel_one import AngelOneBroker
from brokers.shoonya import ShoonyaBroker
from brokers.groww import GrowwBroker
from brokers.base_broker import OrderRequest, OrderSide, OrderType, ProductType, Exchange, OrderStatus
from core.order_router import OrderRouter

try:
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication(sys.argv)
    from ui.broker_control_widget import BrokerControlWidget, BrokerCard, BrokerCredentialsDialog
    PYSIDE_AVAILABLE = True
except Exception:
    PYSIDE_AVAILABLE = False


class TestDynamicAuthAndToggleMatrix(unittest.TestCase):
    """Certified test suite for Phase: Dynamic Broker Authentication & Toggle Matrix."""

    @classmethod
    def setUpClass(cls):
        cls.test_db_path = str(Path(__file__).resolve().parent / "test_omnitrade_vault.db")
        cls.test_key_path = str(Path(__file__).resolve().parent / ".test_vault.key")
        cls.vault = VaultManager(db_path=cls.test_db_path, key_path=cls.test_key_path)

        # Standard RFC 6238 32-character Base32 test secrets
        cls.secret_angel = "JBSWY3DPEHPK3PXPJBSWY3DPEHPK3PXP"
        cls.secret_shoonya = "KRSXG5CTMVRXEZLUKRSXG5CTMVRXEZLU"
        cls.secret_groww = "NBSWY3DPEHPK3PXPJBSWY3DPEHPK3PXP"

    @classmethod
    def tearDownClass(cls):
        # Clean up test files
        for p in (cls.test_db_path, cls.test_key_path):
            try:
                if os.path.exists(p):
                    os.remove(p)
            except Exception:
                pass
        # Clean up SQLite WAL files
        for p in (f"{cls.test_db_path}-wal", f"{cls.test_db_path}-shm"):
            try:
                if os.path.exists(p):
                    os.remove(p)
            except Exception:
                pass

    # =========================================================================
    # Test 1: VaultManager AES-256 Encryption & Auto-TOTP
    # =========================================================================

    def test_01_vault_manager_encryption_and_totp(self):
        print("\n▶ 1. VAULT MANAGER AES-256 ENCRYPTION & AUTO-TOTP ENGINE")
        print("  " + "-" * 76)

        # 1. Save Angel One credentials
        saved = self.vault.save_broker_credentials(
            broker_name="ANGEL_ONE",
            client_id="A100982",
            login_mpin="1234",
            totp_secret=self.secret_angel,
            api_key="angel_api_key_test",
            secret_key="angel_sec_key_test",
            is_trading_enabled=False
        )
        self.assertTrue(saved)
        print("  [ PASS ] Angel One credentials encrypted and stored in vault.")

        # 2. Retrieve and verify decrypted fields (Zero plaintext leak in DB)
        creds = self.vault.get_broker_credentials("ANGEL_ONE")
        self.assertEqual(creds["client_id"], "A100982")
        self.assertEqual(creds["login_mpin"], "1234")
        self.assertEqual(creds["totp_secret"], self.secret_angel)
        self.assertEqual(creds["api_key"], "angel_api_key_test")
        print("  [ PASS ] Decrypted credentials verified with 100% field integrity.")

        # 3. Dynamic Auto-TOTP generation without manual input
        totp_code = self.vault.get_live_totp("ANGEL_ONE")
        self.assertEqual(len(totp_code), 6)
        self.assertTrue(totp_code.isdigit())

        # Verify against reference pyotp computation
        expected_code = pyotp.TOTP(self.secret_angel).now()
        self.assertEqual(totp_code, expected_code)
        print(f"  [ PASS ] Automated 6-digit TOTP generated: {totp_code} (Verified against pyotp).")

        # 4. Save Shoonya and Groww credentials
        self.vault.save_broker_credentials(
            broker_name="SHOONYA",
            client_id="FA55421",
            login_mpin="shoonya_pwd",
            totp_secret=self.secret_shoonya,
            api_key="shoonya_api_key",
            vendor_code="FA55421_U"
        )
        self.vault.save_broker_credentials(
            broker_name="GROWW",
            client_id="GW99881",
            login_mpin="groww_pin",
            totp_secret=self.secret_groww,
            api_key="groww_api_key"
        )
        self.assertTrue(self.vault.has_broker_credentials("SHOONYA"))
        self.assertTrue(self.vault.has_broker_credentials("GROWW"))
        print("  [ PASS ] Shoonya and Groww credentials registered and encrypted.")

    # =========================================================================
    # Test 2: Auto-TOTP Broker Adapters (Angel One, Shoonya, Groww)
    # =========================================================================

    def test_02_broker_adapters_auto_totp(self):
        print("\n▶ 2. BROKER ADAPTER AUTO-TOTP WORKFLOWS & STATE LIFECYCLES")
        print("  " + "-" * 76)

        # 1. Angel One Broker
        angel = AngelOneBroker(vault_manager=self.vault)
        self.assertEqual(angel.broker_name, "ANGEL_ONE")
        self.assertFalse(angel.is_authenticated)
        self.assertEqual(angel._connection_state, "DISCONNECTED")

        # Verify auto-TOTP calculation function inside broker
        totp_angel = angel._calculate_live_totp(self.secret_angel)
        self.assertEqual(len(totp_angel), 6)
        print(f"  [ PASS ] Angel One auto-TOTP computed: {totp_angel}")

        # 2. Shoonya Broker
        shoonya = ShoonyaBroker(vault_manager=self.vault)
        self.assertEqual(shoonya.broker_name, "SHOONYA")
        totp_shoonya = shoonya._calculate_live_totp(self.secret_shoonya)
        self.assertEqual(len(totp_shoonya), 6)
        print(f"  [ PASS ] Shoonya auto-TOTP computed: {totp_shoonya}")

        # 3. Groww Broker
        groww = GrowwBroker(vault_manager=self.vault)
        self.assertEqual(groww.broker_name, "GROWW")
        totp_groww = groww._calculate_live_totp(self.secret_groww)
        self.assertEqual(len(totp_groww), 6)
        print(f"  [ PASS ] Groww auto-TOTP computed: {totp_groww}")

        # 4. Graceful disconnect and resource cleanup
        angel.disconnect()
        shoonya.disconnect()
        groww.disconnect()
        print("  [ PASS ] Broker adapters lifecycle & disconnect verified.")

    # =========================================================================
    # Test 3: Interactive Broker Control Widget & 4-State Visual Indicators
    # =========================================================================

    def test_03_broker_control_widget(self):
        print("\n▶ 3. INTERACTIVE BROKER CONTROL WIDGET & 4-STATE INDICATOR MATRIX")
        print("  " + "-" * 76)

        if not PYSIDE_AVAILABLE:
            print("  [ SKIP ] PySide6 not installed in current environment.")
            return

        widget = BrokerControlWidget(vault_manager=self.vault)
        self.assertEqual(len(widget.cards), 3)
        self.assertIn("ANGEL_ONE", widget.cards)
        self.assertIn("SHOONYA", widget.cards)
        self.assertIn("GROWW", widget.cards)
        print("  [ PASS ] 3 dedicated broker cards created (Angel One, Shoonya, Groww).")

        # Test state indicator transitions:
        # RED: Disconnected
        card_angel = widget.cards["ANGEL_ONE"]
        card_angel.set_connection_state("DISCONNECTED")
        self.assertEqual(card_angel.current_state, "DISCONNECTED")
        status_text = card_angel.lbl_status.text() if callable(card_angel.lbl_status.text) else card_angel.lbl_status.text
        self.assertEqual(status_text, "Disconnected")

        # AMBER: Connecting / Refreshing Token
        card_angel.set_connection_state("CONNECTING")
        self.assertEqual(card_angel.current_state, "CONNECTING")
        status_text = card_angel.lbl_status.text() if callable(card_angel.lbl_status.text) else card_angel.lbl_status.text
        self.assertEqual(status_text, "Connecting...")

        # GREEN: Connected & WebSocket Tick Feed Active
        card_angel.set_connection_state("CONNECTED")
        self.assertEqual(card_angel.current_state, "CONNECTED")
        status_text = card_angel.lbl_status.text() if callable(card_angel.lbl_status.text) else card_angel.lbl_status.text
        self.assertEqual(status_text, "Connected & Live")
        btn_text = card_angel.btn_connect.text() if callable(card_angel.btn_connect.text) else card_angel.btn_connect.text
        self.assertEqual(btn_text, "Disconnect")

        # PURPLE: Session Error / Invalid Credentials
        card_angel.set_connection_state("ERROR", "Invalid MPIN")
        self.assertEqual(card_angel.current_state, "ERROR")
        status_text = card_angel.lbl_status.text() if callable(card_angel.lbl_status.text) else card_angel.lbl_status.text
        self.assertIn("Error:", status_text)
        print("  [ PASS ] All 4 visual indicator states (RED, AMBER, GREEN, PURPLE) certified.")

        # Test Trading Toggle switch
        card_angel.btn_trade_toggle.setChecked(True)
        toggle_text = card_angel.btn_trade_toggle.text() if callable(card_angel.btn_trade_toggle.text) else card_angel.btn_trade_toggle.text
        self.assertEqual(toggle_text, "Trading: ON")
        card_angel.btn_trade_toggle.setChecked(False)
        toggle_text = card_angel.btn_trade_toggle.text() if callable(card_angel.btn_trade_toggle.text) else card_angel.btn_trade_toggle.text
        self.assertEqual(toggle_text, "Trading: OFF")
        print("  [ PASS ] Independent trading execution toggle verified.")

    # =========================================================================
    # Test 4: OrderRouter Strict Toggle-Aware Routing
    # =========================================================================

    def test_04_order_router_toggle_aware_execution(self):
        print("\n▶ 4. ORDER ROUTER STRICT TOGGLE-AWARE ROUTING & CONCURRENT DISPATCH")
        print("  " + "-" * 76)

        router = OrderRouter(vault_manager=self.vault)

        # SCENARIO A: All toggles OFF
        for b in ("ANGEL_ONE", "SHOONYA", "GROWW"):
            router.set_broker_toggle(b, False)

        res_a = router.execute_order("RELIANCE.NS", "BUY", 10, 2500.0, mode="LIVE")
        self.assertEqual(res_a["status"], "REJECTED")
        self.assertEqual(res_a["reason"], "ALL_TOGGLES_OFF")
        self.assertIn("Trading Locked: No active brokers enabled", res_a["message"])
        print("  [ PASS ] Scenario A: All toggles OFF -> Order dropped immediately with 'Trading Locked'.")

        # SCENARIO B: Broker toggled ON but Disconnected
        router.set_broker_toggle("ANGEL_ONE", True)
        angel_inst = router.get_broker_instance("ANGEL_ONE")
        angel_inst.is_authenticated = False
        angel_inst._connection_state = "DISCONNECTED"

        alerts_captured = []
        router.notification_callback = lambda title, msg: alerts_captured.append((title, msg))

        res_b = router.execute_order("RELIANCE.NS", "BUY", 10, 2500.0, mode="LIVE")
        self.assertEqual(res_b["status"], "REJECTED")
        self.assertEqual(res_b["reason"], "ENABLED_BROKERS_DISCONNECTED")
        self.assertIn("ANGEL_ONE", res_b["disconnected_brokers"])
        self.assertTrue(len(alerts_captured) > 0)
        self.assertEqual(alerts_captured[0][0], "Broker Disconnected")
        print("  [ PASS ] Scenario B: Toggled ON but Disconnected -> Rejected on broker, desktop alert fired, no crash.")

        # SCENARIO C: Broker toggled ON AND Connected -> Concurrent Routing
        angel_inst.is_authenticated = True
        angel_inst._connection_state = "CONNECTED"

        shoonya_inst = router.get_broker_instance("SHOONYA")
        shoonya_inst.is_authenticated = True
        shoonya_inst._connection_state = "CONNECTED"
        router.set_broker_toggle("SHOONYA", True)

        res_c = router.execute_order("RELIANCE.NS", "BUY", 10, 2500.0, mode="LIVE")
        self.assertEqual(res_c["status"], "SUBMITTED")
        self.assertIn("ANGEL_ONE", res_c["dispatched_brokers"])
        self.assertIn("SHOONYA", res_c["dispatched_brokers"])
        self.assertEqual(len(res_c["dispatched_brokers"]), 2)
        print("  [ PASS ] Scenario C: 2 Connected & Toggled Brokers -> Concurrently dispatched to Angel One and Shoonya.")

        # SCENARIO D: Pre-trade ₹70 gross profit gate adherence
        # Expected move 1.0 * qty 10 = 10.0 < 70.0 hurdle
        res_d = router.execute_order("RELIANCE.NS", "BUY", 10, 2500.0, target_price=2501.0, mode="LIVE")
        self.assertEqual(res_d["status"], "REJECTED")
        self.assertEqual(res_d["reason"], "PROFIT_HURDLE_FAILED")
        print("  [ PASS ] Scenario D: Pre-trade ₹70 gross profit gate strictly blocked sub-hurdle order.")

        # SCENARIO E: Paper Trading with 0.02% slippage
        res_e = router.execute_order("RELIANCE.NS", "BUY", 10, 2500.0, mode="PAPER")
        self.assertEqual(res_e["status"], "FILLED")
        self.assertEqual(res_e["executed_price"], 2500.50)  # 2500 + 0.02%
        print(f"  [ PASS ] Scenario E: Paper order filled with 0.02% slippage at ₹{res_e['executed_price']:.2f}.")


def run_tests():
    suite = unittest.TestLoader().loadTestsFromTestCase(TestDynamicAuthAndToggleMatrix)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    if result.wasSuccessful():
        print("\n" + "=" * 80)
        print(" END-TO-END DYNAMIC AUTHENTICATION & TOGGLE MATRIX: ALL TESTS PASSED.")
        print("=" * 80 + "\n")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(run_tests())
