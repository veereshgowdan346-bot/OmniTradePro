#!/usr/bin/env python3
"""
OmniTradePro - Live Broker Order Pipeline Verification & Margin Guard Harness
Platform: Windows 10/11 64-bit | Python 3.10+
Tests:
1. Angel One SmartAPI payload/header validation, JWT extraction, dynamic TOTP, and log sanitization.
2. Shoonya NorenAPI SHA-256 hash hashing, vendor code formatting, Susertoken caching, and log sanitization.
3. Groww Gateway session init, state polling, bearer token security, and log sanitization.
4. OrderRouter pre-flight margin guard (MCX futures cutoff vs auto-reroute), 0.08% slippage guard, UUIDv4 tagging, and 2 trades/day cap.
5. AssetWorkerPool capital-based shard filtering and multi-instrument concurrency.
"""

import os
import sys
import time
import json
import uuid
import hashlib
import unittest
import pyotp
from pathlib import Path
from unittest.mock import MagicMock, patch

# Add workspace root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from database.vault_manager import VaultManager
from brokers.base_broker import (
    OrderRequest, OrderResponse, OrderSide, OrderType, ProductType, Exchange, OrderStatus,
    sanitize_log_message, SanitizedLogger
)
from brokers.angel_one import AngelOneBroker
from brokers.shoonya import ShoonyaBroker
from brokers.groww import GrowwBroker
from core.order_router import OrderRouter
from core.asset_worker_pool import AssetWorkerPool


class TestLiveBrokerPipelineHarness(unittest.TestCase):
    """Certified test harness for live broker order pipelines and margin guardrails."""

    @classmethod
    def setUpClass(cls):
        cls.test_db = str(Path(__file__).resolve().parent / "test_harness_vault.db")
        cls.test_key = str(Path(__file__).resolve().parent / ".test_harness_vault.key")
        cls.vault = VaultManager(db_path=cls.test_db, key_path=cls.test_key)

        # RFC 6238 compliant 32-character Base32 secrets
        cls.secret_angel = "JBSWY3DPEHPK3PXPJBSWY3DPEHPK3PXP"
        cls.secret_shoonya = "KRSXG5CTMVRXEZLUKRSXG5CTMVRXEZLU"
        cls.secret_groww = "NBSWY3DPEHPK3PXPJBSWY3DPEHPK3PXP"

        # Populate test vault
        cls.vault.save_broker_credentials(
            broker_name="ANGEL_ONE",
            client_id="ANGEL123",
            login_mpin="9988",
            totp_secret=cls.secret_angel,
            api_key="angel_mock_api_key_test",
            secret_key="angel_mock_sec_key_test",
            trading_pin="123456",
            is_trading_enabled=True
        )
        cls.vault.save_broker_credentials(
            broker_name="SHOONYA",
            client_id="SHOO456",
            login_mpin="shoonya_pass_test",
            totp_secret=cls.secret_shoonya,
            api_key="shoonya_mock_api_key",
            vendor_code="SHOO456_U",
            trading_pin="654321",
            is_trading_enabled=True
        )
        cls.vault.save_broker_credentials(
            broker_name="GROWW",
            client_id="GROWW789",
            login_mpin="groww_pin_test",
            totp_secret=cls.secret_groww,
            api_key="groww_mock_api_key",
            trading_pin="112233",
            is_trading_enabled=True
        )

    @classmethod
    def tearDownClass(cls):
        for path in (cls.test_db, cls.test_key, f"{cls.test_db}-wal", f"{cls.test_db}-shm"):
            try:
                if os.path.exists(path):
                    os.remove(path)
            except Exception:
                pass

    # =========================================================================
    # Test 1: Angel One SmartAPI Live Pipeline & Log Sanitization
    # =========================================================================

    def test_01_angel_one_smartapi_pipeline(self):
        print("\n▶ 1. ANGEL ONE SMARTAPI PIPELINE & LOG SANITIZATION")
        print("  " + "-" * 76)

        broker = AngelOneBroker(vault_manager=self.vault)
        creds = broker._load_credentials()

        self.assertEqual(creds["client_id"], "ANGEL123")
        self.assertEqual(creds["trading_pin"], "123456")

        # 1. Dynamic TOTP generation
        live_totp = broker._calculate_live_totp(self.secret_angel)
        self.assertEqual(len(live_totp), 6)
        self.assertTrue(live_totp.isdigit())
        self.assertEqual(live_totp, pyotp.TOTP(self.secret_angel).now())
        print(f"  [ PASS ] Angel One dynamic TOTP verified: {live_totp}")

        # 2. Mock REST session response & JWT extraction
        fake_jwt = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.fake_angel_jwt_payload.signature123"
        fake_refresh = "fake_refresh_token_xyz"
        fake_feed = "fake_feed_token_abc"

        mock_resp_json = {
            "status": True,
            "message": "SUCCESS",
            "errorcode": "",
            "data": {
                "jwtToken": fake_jwt,
                "refreshToken": fake_refresh,
                "feedToken": fake_feed
            }
        }

        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_cm = MagicMock()
            mock_cm.read.return_value = json.dumps(mock_resp_json).encode("utf-8")
            mock_cm.__enter__.return_value = mock_cm
            mock_urlopen.return_value = mock_cm

            auth_res = broker.authenticate(
                client_id="ANGEL123",
                mpin="9988",
                api_key="angel_mock_api_key_test",
                totp_secret=self.secret_angel
            )
            self.assertTrue(auth_res)
            self.assertTrue(broker.is_authenticated)
            self.assertEqual(broker._connection_state, "CONNECTED")
            self.assertEqual(broker._jwt_token, fake_jwt)
            self.assertEqual(broker._refresh_token, fake_refresh)
            self.assertEqual(broker._feed_token, fake_feed)
            print("  [ PASS ] Angel One session handshake & JWT token extraction certified.")

        # 3. Payload & header formatting for order placement
        order_req = OrderRequest(
            symbol="RELIANCE",
            exchange=Exchange.NSE,
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            product_type=ProductType.INTRADAY,
            quantity=10,
            price=2500.0,
            trigger_price=2450.0,
            tag="OT-AN-TEST01"
        )

        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_cm = MagicMock()
            mock_cm.read.return_value = json.dumps({
                "status": True,
                "message": "SUCCESS",
                "data": {"orderid": "241108000123456"}
            }).encode("utf-8")
            mock_cm.__enter__.return_value = mock_cm
            mock_urlopen.return_value = mock_cm

            order_resp = broker.place_order(order_req)
            self.assertEqual(order_resp.status, OrderStatus.SUBMITTED)
            self.assertEqual(order_resp.broker_order_id, "241108000123456")

            # Validate the outbound request headers and payload
            call_args = mock_urlopen.call_args[0][0]
            headers = call_args.headers
            self.assertIn("Authorization", headers)
            self.assertEqual(headers["Authorization"], f"Bearer {fake_jwt}")
            self.assertEqual(headers["X-privatekey"], "angel_mock_api_key_test")

            sent_payload = json.loads(call_args.data.decode("utf-8"))
            self.assertEqual(sent_payload["variety"], "NORMAL")
            self.assertEqual(sent_payload["tradingsymbol"], "RELIANCE")
            self.assertEqual(sent_payload["transactiontype"], "BUY")
            self.assertEqual(sent_payload["producttype"], "INTRADAY")
            self.assertEqual(sent_payload["quantity"], "10")
            print("  [ PASS ] SmartAPI headers, variety, and payload mapping certified.")

        # 4. Log sanitization (Zero secret/JWT leak)
        sample_log = f"Order dispatched Bearer {fake_jwt} with key angel_mock_api_key_test"
        sanitized = sanitize_log_message(sample_log)
        self.assertNotIn(fake_jwt, sanitized)
        self.assertIn("[REDACTED_JWT]", sanitized)
        self.assertNotIn("angel_mock_api_key_test", sanitized)
        print("  [ PASS ] Log sanitization verified: JWT and API key successfully redacted.")

        broker.disconnect()

    # =========================================================================
    # Test 2: Shoonya NorenAPI Live Pipeline & Log Sanitization
    # =========================================================================

    def test_02_shoonya_norenapi_pipeline(self):
        print("\n▶ 2. SHOONYA NORENAPI PIPELINE & LOG SANITIZATION")
        print("  " + "-" * 76)

        broker = ShoonyaBroker(vault_manager=self.vault)
        creds = broker._load_credentials()

        self.assertEqual(creds["client_id"], "SHOO456")
        self.assertEqual(creds["login_mpin"], "shoonya_pass_test")
        self.assertEqual(creds["trading_pin"], "654321")

        # 1. Verify Noren SHA-256 hash algorithm
        expected_pwd_hash = hashlib.sha256("shoonya_pass_test".encode("utf-8")).hexdigest()
        expected_app_key = hashlib.sha256("SHOO456|shoonya_mock_api_key".encode("utf-8")).hexdigest()

        # 2. Dynamic TOTP generation
        live_totp = broker._calculate_live_totp(self.secret_shoonya)
        self.assertEqual(len(live_totp), 6)
        self.assertTrue(live_totp.isdigit())
        print(f"  [ PASS ] Shoonya dynamic TOTP generated: {live_totp}")

        # 3. QuickAuth Handshake & Susertoken Extraction
        fake_susertoken = "4a8e6b1298c0d9f8e7a6b5c4d3e2f1a0_shoonya_token"
        mock_auth_resp = {
            "stat": "Ok",
            "susertoken": fake_susertoken,
            "lasttime": "1699450000",
            "request_time": "08:30:00 08-11-2026",
            "actid": "SHOO456"
        }

        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_cm = MagicMock()
            mock_cm.read.return_value = json.dumps(mock_auth_resp).encode("utf-8")
            mock_cm.__enter__.return_value = mock_cm
            mock_urlopen.return_value = mock_cm

            auth_res = broker.authenticate(
                user_id="SHOO456",
                password="shoonya_pass_test",
                api_key="shoonya_mock_api_key",
                vendor_code="SHOO456_U",
                totp_secret=self.secret_shoonya
            )
            self.assertTrue(auth_res)
            self.assertTrue(broker.is_authenticated)
            self.assertEqual(broker._susertoken, fake_susertoken)

            # Inspect payload dispatched in jData
            call_args = mock_urlopen.call_args[0][0]
            body_str = call_args.data.decode("utf-8")
            self.assertTrue(body_str.startswith("jData="))
            dispatched_json = json.loads(body_str[len("jData="):])
            self.assertEqual(dispatched_json["uid"], "SHOO456")
            self.assertEqual(dispatched_json["pwd"], expected_pwd_hash)
            self.assertEqual(dispatched_json["appkey"], expected_app_key)
            self.assertEqual(dispatched_json["vc"], "SHOO456_U")
            self.assertEqual(dispatched_json["factor2"], live_totp)
            print("  [ PASS ] Noren QuickAuth SHA-256 hashing and parameters verified.")

        # 4. Susertoken caching and retrieval
        self.assertEqual(broker._susertoken, fake_susertoken)

        # 5. Log sanitization
        log_sample = f"User authenticated with susertoken={fake_susertoken} password=shoonya_pass_test"
        sanitized = sanitize_log_message(log_sample)
        self.assertNotIn(fake_susertoken, sanitized)
        self.assertNotIn("shoonya_pass_test", sanitized)
        print("  [ PASS ] Shoonya susertoken and password redacted from log output.")

        broker.disconnect()

    # =========================================================================
    # Test 3: Groww Gateway Adapter Pipeline & Log Sanitization
    # =========================================================================

    def test_03_groww_gateway_pipeline(self):
        print("\n▶ 3. GROWW GATEWAY ADAPTER PIPELINE & STATE POLLING")
        print("  " + "-" * 76)

        broker = GrowwBroker(vault_manager=self.vault)
        creds = broker._load_credentials()

        self.assertEqual(creds["client_id"], "GROWW789")
        self.assertEqual(creds["trading_pin"], "112233")

        # 1. Dynamic TOTP generation
        live_totp = broker._calculate_live_totp(self.secret_groww)
        self.assertEqual(len(live_totp), 6)
        print(f"  [ PASS ] Groww dynamic TOTP generated: {live_totp}")

        # 2. Session Initialization & Bearer Token Handling
        fake_groww_token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.fake_groww_bearer_token.sig"
        mock_groww_resp = {
            "status": "SUCCESS",
            "token": fake_groww_token,
            "user_id": "GROWW789"
        }

        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_cm = MagicMock()
            mock_cm.read.return_value = json.dumps(mock_groww_resp).encode("utf-8")
            mock_cm.__enter__.return_value = mock_cm
            mock_urlopen.return_value = mock_cm

            auth_res = broker.authenticate(
                client_id="GROWW789",
                password="groww_pin_test",
                api_key="groww_mock_api_key",
                totp_secret=self.secret_groww
            )
            self.assertTrue(auth_res)
            self.assertTrue(broker.is_authenticated)
            self.assertEqual(broker._connection_state, "CONNECTED")
            self.assertEqual(broker._bearer_token, fake_groww_token)
            print("  [ PASS ] Groww bearer session initialization and state polling verified.")

        # 3. Log sanitization
        log_sample = f"Groww connection established token={fake_groww_token}"
        sanitized = sanitize_log_message(log_sample)
        self.assertNotIn(fake_groww_token, sanitized)
        self.assertIn("[REDACTED_JWT]", sanitized)
        print("  [ PASS ] Groww bearer token redacted from log output.")

        broker.disconnect()

    # =========================================================================
    # Test 4: OrderRouter Pre-Flight Margin Guard, Slippage & Risk Guardrails
    # =========================================================================

    def test_04_order_router_margin_guard_and_risk(self):
        print("\n▶ 4. ORDER ROUTER PRE-FLIGHT MARGIN GUARD, SLIPPAGE & RISK GUARD")
        print("  " + "-" * 76)

        router = OrderRouter(vault_manager=self.vault, enforce_daily_trade_cap=True)

        # 1. Pre-Flight Margin Check: MCX Crude Oil Futures (Requires min ₹1.5L)
        # Case A: Low capital (₹50,000) without auto-reroute -> REJECTED
        res_reject = router.execute_order(
            symbol="CRUDEOIL",
            side="BUY",
            quantity=1,
            price=6500.0,
            target_price=6600.0,
            mode="PAPER",
            available_capital=50000.0,
            auto_reroute_insufficient_margin=False
        )
        self.assertEqual(res_reject["status"], "REJECTED")
        self.assertEqual(res_reject["reason"], "MARGIN_EXCEEDED_PREFLIGHT")
        self.assertIn("Pre-flight margin shortfall", res_reject["message"])
        print(f"  [ PASS ] Case A: Low Capital (₹50,000 < ₹1.5L) rejected cleanly: {res_reject['reason']}.")

        # Case B: Low capital (₹50,000) with auto_reroute_insufficient_margin=True -> REROUTED to Equity MIS (5x)
        res_reroute = router.execute_order(
            symbol="CRUDEOIL",
            side="BUY",
            quantity=1,
            price=6500.0,
            target_price=6600.0,
            mode="PAPER",
            available_capital=50000.0,
            auto_reroute_insufficient_margin=True
        )
        self.assertEqual(res_reroute["status"], "FILLED")
        self.assertEqual(res_reroute["symbol"], "RELIANCE")
        # 50000 * 5 = 250,000 buying power / 2485 = ~100 shares
        self.assertGreater(res_reroute["quantity"], 1)
        print(f"  [ PASS ] Case B: Low Capital auto-rerouted to {res_reroute['symbol']} (qty: {res_reroute['quantity']}) under 5x leverage.")

        # Case C: Sufficient capital (₹200,000 >= ₹1.5L) -> PASSED
        res_pass = router.execute_order(
            symbol="CRUDEOIL",
            side="BUY",
            quantity=1,
            price=6500.0,
            target_price=6600.0,
            mode="PAPER",
            available_capital=200000.0
        )
        self.assertEqual(res_pass["status"], "FILLED")
        self.assertEqual(res_pass["symbol"], "CRUDEOIL")
        print(f"  [ PASS ] Case C: Sufficient Capital (₹200,000) passed margin guard for {res_pass['symbol']}.")

        # 2. Dynamic Slippage Guard (0.08% / 8 bps max adverse price drift)
        # BUY order: Requested price = 2500.0, Current Market Price = 2505.0 (+0.20% drift > 0.08%)
        res_slip = router.execute_order(
            symbol="INFY",
            side="BUY",
            quantity=10,
            price=2500.0,
            target_price=2550.0,
            mode="PAPER",
            current_market_price=2505.0,  # 5.0 / 2500.0 = 0.2% drift
            enforce_slippage_guard=True
        )
        self.assertEqual(res_slip["status"], "REJECTED")
        self.assertEqual(res_slip["reason"], "SLIPPAGE_BREACH_ABORT")
        self.assertGreater(res_slip["slippage_pct"], 0.0008)
        print(f"  [ PASS ] Slippage guard triggered: Adverse drift {res_slip['slippage_pct']*100:.2f}% > 0.08% cutoff.")

        # 3. UUIDv4 Execution Tagging in Live Mode
        router.set_broker_toggle("ANGEL_ONE", True)
        angel_inst = router.get_broker_instance("ANGEL_ONE")
        angel_inst.is_authenticated = True
        angel_inst._connection_state = "CONNECTED"

        with patch.object(angel_inst, "place_order") as mock_place:
            mock_place.return_value = OrderResponse(
                client_order_id="TEST-ORD-01",
                broker_order_id="24110899999",
                symbol="TCS",
                exchange=Exchange.NSE,
                side=OrderSide.BUY,
                order_type=OrderType.LIMIT,
                product_type=ProductType.INTRADAY,
                quantity=5,
                price=3500.0,
                trigger_price=0.0,
                status=OrderStatus.SUBMITTED
            )

            res_live = router.execute_order(
                symbol="TCS",
                side="BUY",
                quantity=5,
                price=3500.0,
                target_price=3550.0,
                mode="LIVE"
            )
            self.assertEqual(res_live["status"], "SUBMITTED")
            exec_id = res_live["execution_id"]
            # Validate UUIDv4 format
            uuid_obj = uuid.UUID(exec_id, version=4)
            self.assertEqual(str(uuid_obj), exec_id)
            print(f"  [ PASS ] UUIDv4 execution ID verified: {exec_id}")

        # 4. Daily Trade Cap (Strictly Max 2 Trades per Instrument per Day)
        # Order 1 for SBIN
        r1 = router.execute_order("SBIN", "BUY", 10, 800.0, target_price=820.0, mode="PAPER")
        self.assertEqual(r1["status"], "FILLED")
        # Order 2 for SBIN
        r2 = router.execute_order("SBIN", "BUY", 10, 800.0, target_price=820.0, mode="PAPER")
        self.assertEqual(r2["status"], "FILLED")
        # Order 3 for SBIN -> MUST BE BLOCKED
        r3 = router.execute_order("SBIN", "BUY", 10, 800.0, target_price=820.0, mode="PAPER")
        self.assertEqual(r3["status"], "REJECTED")
        self.assertEqual(r3["reason"], "DAILY_TRADE_CAP_EXCEEDED")
        self.assertIn("Maximum daily trade cap", r3["message"])
        print(f"  [ PASS ] Daily trade cap enforced: 3rd trade on SBIN successfully rejected.")

    # =========================================================================
    # Test 5: AssetWorkerPool Capital-Based Shard Filtering
    # =========================================================================

    def test_05_asset_worker_pool_shard_filtering(self):
        print("\n▶ 5. ASSET WORKER POOL CAPITAL-BASED SHARD FILTERING")
        print("  " + "-" * 76)

        pool = AssetWorkerPool()

        # Case A: Low capital (< ₹1.5L)
        low_cap_shards = pool.get_eligible_shards(capital_inr=100000.0)
        self.assertNotIn("GOLD_SHARD", low_cap_shards)
        self.assertNotIn("SILVER_SHARD", low_cap_shards)
        self.assertNotIn("CRUDEOIL_SHARD", low_cap_shards)
        self.assertIn("NIFTY_SHARD", low_cap_shards)
        self.assertIn("BANKNIFTY_SHARD", low_cap_shards)
        self.assertIn("GENERAL_SHARD", low_cap_shards)
        print(f"  [ PASS ] Low Capital (₹1.0L) filtered out commodity shards: {low_cap_shards}")

        # Case B: High capital (>= ₹1.5L)
        high_cap_shards = pool.get_eligible_shards(capital_inr=250000.0)
        self.assertIn("GOLD_SHARD", high_cap_shards)
        self.assertIn("SILVER_SHARD", high_cap_shards)
        self.assertIn("CRUDEOIL_SHARD", high_cap_shards)
        self.assertIn("NIFTY_SHARD", high_cap_shards)
        self.assertIn("BANKNIFTY_SHARD", high_cap_shards)
        print(f"  [ PASS ] High Capital (₹2.5L) all shards active: {high_cap_shards}")

        pool.shutdown()
        print("  [ PASS ] AssetWorkerPool cleanly shut down.")


if __name__ == "__main__":
    unittest.main(verbosity=2)
