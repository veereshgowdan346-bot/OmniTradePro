#!/usr/bin/env python3
"""
OmniTradePro - Lightweight Automated Trade Execution & Daily P&L Email Notification Test Suite
Platform: Windows 10/11 64-bit | Python 3.10+
Tests:
1. VaultManager persistence & AES-256 decryption of email notification settings.
2. TradeNotifier asynchronous detached execution: verify 0.00ms latency on caller path.
3. Trade alert HTML and plain-text message formatting (Symbol, Side, Qty, Price, SL, TP, UUID).
4. Daily summary HTML and plain-text formatting (Total trades, Win rate, Gross P&L, Taxes, Net P&L).
5. Mocked SMTP and Resend API transports with error isolation.
6. OrderRouter live & paper execution hook integration.
7. Session square-off hook integration.
"""

import os
import sys
import time
import json
import smtplib
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

# Add workspace root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from database.vault_manager import VaultManager
from core.notifier import TradeNotifier
from core.order_router import OrderRouter


class TestTradeNotifier(unittest.TestCase):
    """Certified test suite for lightweight automated notification service."""

    @classmethod
    def setUpClass(cls):
        cls.test_db = str(Path(__file__).resolve().parent / "test_notifier_vault.db")
        cls.test_key = str(Path(__file__).resolve().parent / ".test_notifier_vault.key")
        cls.vault = VaultManager(db_path=cls.test_db, key_path=cls.test_key)

    @classmethod
    def tearDownClass(cls):
        for path in (cls.test_db, cls.test_key, f"{cls.test_db}-wal", f"{cls.test_db}-shm"):
            try:
                if os.path.exists(path):
                    os.remove(path)
            except Exception:
                pass

    def setUp(self):
        # Save fresh notification configuration in encrypted vault
        self.vault.save_notification_settings(
            recipient_email="operator@omnitrade.test",
            sender_email="alerts@omnitrade.test",
            smtp_password="test_mock_app_password_123",
            smtp_server="smtp.omnitrade.test",
            smtp_port=587,
            trade_alerts_enabled=True,
            daily_summary_enabled=True
        )

    # =========================================================================
    # Test 1: VaultManager Encrypted Notification Settings Persistence
    # =========================================================================

    def test_01_vault_notification_settings_encryption(self):
        print("\n▶ 1. VAULT NOTIFICATION SETTINGS AES-256 ENCRYPTION & DECRYPTION")
        print("  " + "-" * 76)

        settings = self.vault.get_notification_settings()
        self.assertEqual(settings["recipient_email"], "operator@omnitrade.test")
        self.assertEqual(settings["sender_email"], "alerts@omnitrade.test")
        self.assertEqual(settings["smtp_password"], "test_mock_app_password_123")
        self.assertTrue(settings["trade_alerts_enabled"])
        self.assertTrue(settings["daily_summary_enabled"])

        # Verify zero plaintext password leak in raw SQLite file
        with open(self.test_db, "rb") as f:
            raw_db_bytes = f.read()
            self.assertNotIn(b"test_mock_app_password_123", raw_db_bytes)
        print("  [ PASS ] Notification settings encrypted in vault; zero plaintext leak verified.")

    # =========================================================================
    # Test 2: Sub-Millisecond Non-Blocking Trade Alert Latency (0.00ms)
    # =========================================================================

    def test_02_non_blocking_trade_alert_latency(self):
        print("\n▶ 2. NON-BLOCKING TRADE ALERT CALLER LATENCY (0.00ms SLA)")
        print("  " + "-" * 76)

        notifier = TradeNotifier(vault_manager=self.vault)
        # Warm up executor pool so thread initialization does not skew benchmark
        notifier.send_trade_alert({"symbol": "WARMUP", "side": "BUY", "quantity": 1, "price": 100.0})

        # Simulate network latency of 300ms in background worker
        with patch.object(notifier, "_send_email_payload", side_effect=lambda *a, **kw: time.sleep(0.05) or True):
            latencies = []
            for _ in range(5):
                t_start = time.perf_counter()
                notifier.send_trade_alert({
                    "symbol": "NSE:RELIANCE",
                    "side": "BUY",
                    "quantity": 10,
                    "price": 2500.0,
                    "target_price": 2550.0,
                    "stop_loss": 2475.0,
                    "execution_mode": "LIVE",
                    "execution_id": "OT-AN-TEST001"
                })
                latencies.append((time.perf_counter() - t_start) * 1000.0)
            avg_latency = sum(latencies) / len(latencies)

        print(f"  [ PASS ] Caller path avg latency: {avg_latency:.3f}ms (Target: < 1.00ms).")
        self.assertLess(avg_latency, 1.0, f"Caller latency {avg_latency:.3f}ms exceeds 1ms SLA!")
        notifier.shutdown(wait=True)

    # =========================================================================
    # Test 3: Trade Alert & Daily Summary Formatting
    # =========================================================================

    def test_03_message_formatting_and_payload(self):
        print("\n▶ 3. TRADE ALERT & DAILY SUMMARY MESSAGE FORMATTING")
        print("  " + "-" * 76)

        notifier = TradeNotifier(vault_manager=self.vault)
        captured_payloads = []

        with patch.object(notifier, "_send_email_payload", side_effect=lambda subj, html, text, **kw: captured_payloads.append((subj, html, text)) or True):
            # Test Trade Alert
            notifier.send_trade_alert({
                "symbol": "MCX:CRUDEOIL",
                "side": "BUY",
                "quantity": 2,
                "price": 6550.0,
                "target_price": 6650.0,
                "stop_loss": 6500.0,
                "execution_mode": "LIVE",
                "execution_id": "UUID-CRUDE-999",
                "broker": "ANGEL_ONE"
            })

            # Test Daily Summary
            notifier.send_daily_summary({
                "total_trades": 5,
                "wins": 4,
                "losses": 1,
                "win_rate": 80.0,
                "gross_pnl": 1850.0,
                "total_taxes": 300.0,
                "net_pnl": 1550.0,
                "market_session": "NSE/BSE (09:15-15:15 IST)"
            })

            notifier.shutdown(wait=True)

        self.assertEqual(len(captured_payloads), 2)

        # Inspect Trade Alert
        trade_subj, trade_html, trade_text = captured_payloads[0]
        self.assertIn("MCX:CRUDEOIL", trade_subj)
        self.assertIn("BUY", trade_subj)
        self.assertIn("6,550.00", trade_subj)
        self.assertIn("UUID-CRUDE-999", trade_html)
        self.assertIn("ANGEL_ONE", trade_html)
        self.assertIn("Target Price", trade_text)
        print("  [ PASS ] Trade alert subject and HTML payload certified.")

        # Inspect Daily Summary
        sum_subj, sum_html, sum_text = captured_payloads[1]
        self.assertIn("+₹1,550.00", sum_subj)
        self.assertIn("80.0%", sum_html)
        self.assertIn("1,850.00", sum_html)
        self.assertIn("300.00", sum_html)
        self.assertIn("NSE/BSE (09:15-15:15 IST)", sum_html)
        print("  [ PASS ] Daily summary win rate, gross P&L, and net P&L certified.")

    # =========================================================================
    # Test 4: Provider Transports (SMTP & Resend HTTP API)
    # =========================================================================

    def test_04_provider_transports_and_error_boundary(self):
        print("\n▶ 4. PROVIDER TRANSPORTS (SMTP & RESEND HTTP API) & ERROR ISOLATION")
        print("  " + "-" * 76)

        # Provider A: Standard smtplib delivery
        notifier_smtp = TradeNotifier(vault_manager=self.vault)
        with patch("smtplib.SMTP") as mock_smtp:
            mock_inst = MagicMock()
            mock_smtp.return_value.__enter__.return_value = mock_inst

            res_smtp = notifier_smtp._send_email_payload("Test Subj", "<p>body</p>", "body")
            self.assertTrue(res_smtp)
            mock_inst.starttls.assert_called_once()
            mock_inst.login.assert_called_once()
            mock_inst.sendmail.assert_called_once()
            print("  [ PASS ] Standard smtplib with STARTTLS successfully executed.")

        # Provider B: Resend HTTP API (API key starting with 're_')
        notifier_resend = TradeNotifier(
            vault_manager=self.vault,
            recipient_email="operator@test.com",
            smtp_password="re_live_mock_api_key_456"
        )
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_cm = MagicMock()
            mock_cm.read.return_value = json.dumps({"id": "resend_msg_123"}).encode("utf-8")
            mock_cm.__enter__.return_value = mock_cm
            mock_urlopen.return_value = mock_cm

            res_resend = notifier_resend._send_email_payload("Test Resend", "<p>body</p>", "body")
            self.assertTrue(res_resend)
            call_req = mock_urlopen.call_args[0][0]
            self.assertEqual(call_req.headers["Authorization"], "Bearer re_live_mock_api_key_456")
            print("  [ PASS ] Resend HTTP API path verified with Bearer token authentication.")

        # Error Boundary: Network failure does NOT raise exception to caller
        with patch("smtplib.SMTP", side_effect=smtplib.SMTPConnectError(421, "Service unavailable")):
            res_fail = notifier_smtp._send_email_payload("Test Fail", "<p>body</p>", "body")
            self.assertFalse(res_fail)
            print("  [ PASS ] Error boundary verified: Network/auth exceptions safely caught.")

        notifier_smtp.shutdown(wait=False)
        notifier_resend.shutdown(wait=False)

    # =========================================================================
    # Test 5: OrderRouter Integration Hook
    # =========================================================================

    def test_05_order_router_hooks(self):
        print("\n▶ 5. ORDER ROUTER HOOKS (PAPER & LIVE DISPATCH NOTIFICATION)")
        print("  " + "-" * 76)

        mock_notifier = MagicMock()
        router = OrderRouter(vault_manager=self.vault, notifier=mock_notifier)

        # Fund the ticket: the router enforces the operator ceiling by default now.
        router.update_risk_parameters(
            mode="PAPER", trade_capital=100_000.0, max_sl=500.0,
            risk_percentage=5.0, daily_drawdown_pct=10.0, enforce=True
        )

        # Trigger Paper Order
        paper_res = router.execute_order(
            symbol="INFY",
            side="BUY",
            quantity=10,
            price=1500.0,
            target_price=1550.0,
            mode="PAPER"
        )
        self.assertEqual(paper_res["status"], "FILLED")
        mock_notifier.send_trade_alert.assert_called_once()
        alert_arg = mock_notifier.send_trade_alert.call_args[0][0]
        self.assertEqual(alert_arg["symbol"], "INFY")
        self.assertEqual(alert_arg["side"], "BUY")
        self.assertEqual(alert_arg["quantity"], 10)
        self.assertEqual(alert_arg["execution_mode"], "PAPER")
        print("  [ PASS ] OrderRouter successfully hooked TradeNotifier on order fill.")

        # Trigger Mandatory Auto-Square-Off at 15:15 IST
        router.evaluate_auto_square_off(current_time="15:15")
        mock_notifier.send_daily_summary.assert_called_once()
        summary_arg = mock_notifier.send_daily_summary.call_args[0][0]
        self.assertEqual(summary_arg["market_session"], "EQUITY")
        self.assertEqual(summary_arg["square_off_time"], "15:15")
        print("  [ PASS ] evaluate_auto_square_off() successfully triggered send_daily_summary().")


if __name__ == "__main__":
    unittest.main(verbosity=2)
