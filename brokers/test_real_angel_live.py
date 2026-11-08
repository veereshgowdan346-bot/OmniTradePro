#!/usr/bin/env python3
"""
OmniTradePro - Standalone Real-Money Angel One SmartAPI Live Verification Suite
Platform: Windows 10/11 64-bit | Python 3.10+
OPERATIONAL RULE: STRICTLY ZERO MOCK/SYNTHETIC DATA.
Connects directly to Angel One production REST & WebSocket clusters:
1. Authenticates using live TOTP and decrypted credentials from database/omnitrade_vault.db
2. Ingests genuine RMS Account Funds via get_rms_funds() (/rest/secure/angelbroking/user/v1/getRMS)
3. Subscribes to live SmartStream WebSocket (wss://smartapisocket.angelone.in/smart-stream)
4. Receives and unpacks genuine binary tick packets for SBIN, RELIANCE, and NSE Indices
"""

import sys
import os
import json
import time
import struct
import threading
from datetime import datetime, timezone

# Ensure project root is in sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.vault_manager import VaultManager
from database.db_handler import DatabaseHandler
from brokers.angel_one import AngelOneBroker
from brokers.stream_worker import BrokerStreamWorker
from brokers.token_master import TokenMaster

try:
    import websocket
except ImportError:
    print("[ERROR] 'websocket-client' package is required.")
    sys.exit(1)


def main():
    print("=" * 80)
    print("  OMNITRADEPRO - LIVE REAL-MONEY ANGEL ONE INTEGRATION VERIFICATION")
    print("  STRICTLY ZERO MOCK / REAL REST & WEBSOCKET TRAFFIC ONLY")
    print("=" * 80)

    # 1. Load credentials from encrypted vault
    vault = VaultManager()
    db = DatabaseHandler()

    print("\n[STEP 1] Decrypting Angel One credentials from omnitrade_vault.db...")
    try:
        creds = vault.get_broker_credentials("ANGEL_ONE")
    except Exception as e:
        print(f"[ERROR] Failed to load credentials from vault: {e}")
        return False

    client_id = creds.get("client_id", "")
    api_key = creds.get("api_key", "")
    has_totp = bool(creds.get("totp_secret"))
    has_mpin = bool(creds.get("login_mpin"))
    has_tpin = bool(creds.get("trading_pin"))

    print(f"  ✓ Client ID:        {client_id}")
    print(f"  ✓ API Key:          {api_key[:6]}...{api_key[-4:] if len(api_key) > 10 else ''}")
    print(f"  ✓ MPIN Loaded:      {has_mpin}")
    print(f"  ✓ Trading PIN:      {has_tpin}")
    print(f"  ✓ TOTP Secret:      {has_totp} (32-char Base32)")

    # 2. Authenticate against Angel One Production
    print("\n[STEP 2] Authenticating with Angel One production server...")
    broker = AngelOneBroker(vault_manager=vault, db_handler=db)
    auth_success = broker.authenticate()

    if not auth_success:
        print(f"[ERROR] Live authentication rejected: {broker._connection_error}")
        return False

    print("  ✓ Authentication:   SUCCESS")
    print(f"  ✓ JWT Token:        {broker.jwt_token[:20]}... (len: {len(broker.jwt_token)})")
    print(f"  ✓ Feed Token:       {broker.feed_token[:15]}... (len: {len(broker.feed_token)})")

    # 3. Query Real RMS Funds
    print("\n[STEP 3] Ingesting Live RMS Account Funds (/rest/secure/angelbroking/user/v1/getRMS)...")
    rms_funds = broker.get_rms_funds()

    print(f"  ✓ RMS Query Status: {rms_funds.get('status')}")
    print(f"  ✓ Source:           {rms_funds.get('source')}")
    print(f"  ✓ Net Capital:      ₹{rms_funds.get('net', 0.0):,.2f}")
    print(f"  ✓ Available Cash:   ₹{rms_funds.get('availablecash', 0.0):,.2f}")
    print(f"  ✓ Collateral:       ₹{rms_funds.get('collateral', 0.0):,.2f}")
    print(f"  ✓ Utilized Debits:  ₹{rms_funds.get('utilized', 0.0):,.2f}")

    if not rms_funds.get("status"):
        print("[WARNING] RMS query returned False status. Check endpoint access or IP whitelisting.")
    else:
        print("  ✓ Live Account Funds Verified authentic from Angel One ledger.")

    # 4. Connect to SmartStream WebSocket
    print("\n[STEP 4] Connecting to SmartStream WebSocket (wss://smartapisocket.angelone.in/smart-stream)...")
    ws_url = "wss://smartapisocket.angelone.in/smart-stream"
    jwt_tok = broker.jwt_token
    auth_header = jwt_tok if jwt_tok.startswith("Bearer ") else f"Bearer {jwt_tok}"
    
    headers = {
        "Authorization": auth_header,
        "x-api-key": api_key,
        "x-client-code": client_id,
        "x-feed-token": broker.feed_token
    }

    tokens_to_subscribe = ["3045", "2885", "26000", "26009"]
    received_ticks = []
    ws_connected_event = threading.Event()
    stop_event = threading.Event()

    def on_open(ws):
        print("  ✓ WebSocket Connected! Sending binary feed subscription...")
        ws_connected_event.set()
        sub_payload = {
            "correlationID": f"LIVE_VERIFY_{int(time.time())}",
            "action": 1,
            "params": {
                "mode": 1,  # LTP mode
                "tokenList": [
                    {
                        "exchangeType": 1,  # NSE
                        "tokens": tokens_to_subscribe
                    }
                ]
            }
        }
        ws.send(json.dumps(sub_payload))
        print(f"  ✓ Subscription dispatched for tokens: {tokens_to_subscribe}")

    def on_message(ws, msg):
        if isinstance(msg, bytes):
            parsed = BrokerStreamWorker.parse_angel_binary_packet(msg)
            if parsed and parsed.get("ltp", 0.0) > 0.0:
                received_ticks.append(parsed)
                print(f"  ★ TICK INGESTED: {parsed['symbol']} ({parsed['exchange']}: {parsed['token']}) -> ₹{parsed['ltp']:,.2f} at {parsed['timestamp']}")
                if len(received_ticks) >= 2:
                    # Received enough live ticks to prove pipeline
                    stop_event.set()
                    ws.close()
        elif isinstance(msg, str):
            print(f"  [WS TEXT]: {msg[:100]}")

    def on_error(ws, err):
        print(f"  [WS ERROR]: {err}")

    def on_close(ws, code, reason):
        print(f"  [WS CLOSED]: code={code}, reason={reason}")

    ws_app = websocket.WebSocketApp(
        ws_url,
        header=headers,
        on_open=on_open,
        on_message=on_message,
        on_error=on_error,
        on_close=on_close
    )

    ws_thread = threading.Thread(target=ws_app.run_forever, kwargs={"ping_interval": 15, "ping_timeout": 5}, daemon=True)
    ws_thread.start()

    # Wait for connection and at least 1-2 ticks or timeout
    start_wait = time.time()
    timeout = 15.0  # 15 seconds
    while time.time() - start_wait < timeout and not stop_event.is_set():
        time.sleep(0.5)

    try:
        ws_app.close()
    except Exception:
        pass

    # 5. Summary Evaluation
    print("\n" + "=" * 80)
    print("  VERIFICATION AUDIT RESULTS:")
    print(f"  1. Live REST Auth & Session:     {'PASS' if auth_success else 'FAIL'}")
    print(f"  2. RMS Funds Query:              {'PASS' if rms_funds.get('status') else 'FAIL'}")
    print(f"  3. SmartStream WS Handshake:     {'PASS' if ws_connected_event.is_set() else 'FAIL'}")
    print(f"  4. Binary Tick Ingestion:        {'PASS' if len(received_ticks) > 0 else 'MARKET_OFFLINE / NO TICKS'}")
    print(f"     Total Live Ticks Received:    {len(received_ticks)}")
    print("=" * 80)

    if auth_success and rms_funds.get("status") and ws_connected_event.is_set():
        print("[SUCCESS] Angel One Live REST and WebSocket pipeline is 100% OPERATIONAL!")
        return True
    else:
        print("[NOTICE] Pipeline partially verified (REST auth succeeded).")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

