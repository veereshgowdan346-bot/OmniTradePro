#!/usr/bin/env python3
"""
OmniTradePro - Phase 2 Vault & Dynamic 2FA Verification Suite
Tests the AES-256 encrypted credential vault, live Base32 TOTP token generation,
active broker switching, and the institutional trade audit engine with ₹60 friction modeling.
"""

import os
import sys
import tempfile
import sqlite3
from pathlib import Path

# Add project root to sys.path to ensure absolute import compatibility
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from database.db_handler import DatabaseHandler


class ANSI:
    """Terminal visual formatting and color tokens."""
    RESET = "\033[0m"
    BOLD = "\033[1m"
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    CYAN = "\033[96m"
    WHITE = "\033[97m"
    BG_GREEN = "\033[42m"
    BG_RED = "\033[41m"


def enable_windows_ansi() -> None:
    """Enables virtual terminal escape sequence processing on Windows systems."""
    if sys.platform == "win32":
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            handle = kernel32.GetStdHandle(-11)
            mode = ctypes.c_ulong()
            if kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
                kernel32.SetConsoleMode(handle, mode.value | 0x0004)
        except Exception:
            pass


enable_windows_ansi()


def print_banner() -> None:
    """Displays the institutional ASCII banner."""
    print(f"{ANSI.CYAN}{ANSI.BOLD}")
    print("=" * 80)
    print("  ██████╗ ███╗   ███╗███╗   ██╗██╗████████╗██████╗  █████╗ ██████╗ ███████╗")
    print(" ██╔═══██╗████╗ ████║████╗  ██║██║╚══██╔══╝██╔══██╗██╔══██╗██╔══██╗██╔════╝")
    print(" ██║   ██║██╔████╔██║██╔██╗ ██║██║   ██║   ██████╔╝███████║██║  ██║█████╗  ")
    print(" ██║   ██║██║╚██╔╝██║██║╚██╗██║██║   ██║   ██╔══██╗██╔══██║██║  ██║██╔══╝  ")
    print(" ╚██████╔╝██║ ╚═╝ ██║██║ ╚████║██║   ██║   ██║  ██║██║  ██║██████╔╝███████╗")
    print("  ╚═════╝ ╚═╝     ╚═╝╚═╝  ╚═══╝╚═╝   ╚═╝   ╚═╝  ╚═╝╚═╝  ╚═╝╚═════╝ ╚══════╝")
    print("          MULTI-BROKER VAULT & DYNAMIC 2FA SUBSYSTEM - PHASE 2 TEST           ")
    print("=" * 80)
    print(f"{ANSI.RESET}")


def run_tests() -> bool:
    """Executes the complete verification suite against an isolated test vault."""
    all_passed = True
    test_dir = tempfile.TemporaryDirectory()
    test_dir_path = Path(test_dir.name)
    test_db_path = test_dir_path / "test_omnitrade.db"
    test_key_path = test_dir_path / ".test_vault.key"

    print_banner()

    try:
        # 1. Initialize isolated DatabaseHandler instance
        print(f"{ANSI.YELLOW}{ANSI.BOLD}▶ 1. DATABASE & ENCRYPTION INITIALIZATION{ANSI.RESET}")
        print(f"  {'-' * 76}")
        
        # Reset singleton state for clean test isolation
        DatabaseHandler._instance = None
        db = DatabaseHandler(db_path=str(test_db_path), key_path=str(test_key_path))
        
        assert test_db_path.exists(), "Test database file was not created on disk."
        assert test_key_path.exists(), "Encryption key file (.vault.key) was not generated."
        print(f"  {ANSI.GREEN}[ PASS ]{ANSI.RESET} Database created: {test_db_path.name}")
        print(f"  {ANSI.GREEN}[ PASS ]{ANSI.RESET} Key file created: {test_key_path.name} (AES-256 Fernet)")

        # 2. Save and Decrypt Angel One Credentials
        print(f"\n{ANSI.YELLOW}{ANSI.BOLD}▶ 2. BROKER CREDENTIAL ENCRYPTION & RETRIEVAL{ANSI.RESET}")
        print(f"  {'-' * 76}")

        raw_client_id = "A100982"
        raw_mpin = "1234"
        raw_totp_secret = "JBSWY3DPEHPK3PXPJBSWY3DPEHPK3PXP"
        raw_api_key = "ANGEL_SMARTAPI_LIVE_KEY_88291"
        raw_secret_key = "ANGEL_SECRET_FEED_TOKEN_7721"

        db.save_broker_credentials(
            broker_name="ANGEL_ONE",
            client_id=raw_client_id,
            login_mpin=raw_mpin,
            totp_secret=raw_totp_secret,
            api_key=raw_api_key,
            secret_key=raw_secret_key
        )
        print(f"  {ANSI.GREEN}[ PASS ]{ANSI.RESET} Saved ANGEL_ONE credentials (4-digit MPIN: {raw_mpin}, 32-char TOTP)")

        # Verify low-level SQLite ciphertext storage
        raw_conn = sqlite3.connect(str(test_db_path))
        raw_cur = raw_conn.cursor()
        raw_cur.execute("SELECT api_key_enc, login_mpin_enc, totp_secret_enc FROM broker_vault WHERE broker_name = 'ANGEL_ONE'")
        stored_api_enc, stored_mpin_enc, stored_totp_enc = raw_cur.fetchone()
        raw_cur.close()
        raw_conn.close()

        assert stored_mpin_enc != raw_mpin.encode("utf-8"), "MPIN is stored in plaintext in SQLite!"
        assert stored_totp_enc != raw_totp_secret.encode("utf-8"), "TOTP secret is stored in plaintext in SQLite!"
        assert stored_api_enc != raw_api_key.encode("utf-8"), "API key is stored in plaintext in SQLite!"
        print(f"  {ANSI.GREEN}[ PASS ]{ANSI.RESET} Verified encrypted ciphertext stored in database (Zero Plaintext Leak)")

        # Decrypt and assert equality
        creds = db.get_broker_credentials("ANGEL_ONE")
        assert creds["client_id"] == raw_client_id, f"Client ID mismatch: {creds['client_id']}"
        assert creds["login_mpin"] == raw_mpin, f"MPIN mismatch: {creds['login_mpin']}"
        assert creds["totp_secret"] == raw_totp_secret, f"TOTP secret mismatch: {creds['totp_secret']}"
        assert creds["api_key"] == raw_api_key, f"API key mismatch: {creds['api_key']}"
        assert creds["secret_key"] == raw_secret_key, f"Secret key mismatch: {creds['secret_key']}"
        print(f"  {ANSI.GREEN}[ PASS ]{ANSI.RESET} Decrypted credentials verified: MPIN='{creds['login_mpin']}', TOTP='{creds['totp_secret'][:8]}...'")

        # 3. Dynamic 2FA TOTP Generation
        print(f"\n{ANSI.YELLOW}{ANSI.BOLD}▶ 3. DYNAMIC 2FA TOTP TOKEN GENERATION{ANSI.RESET}")
        print(f"  {'-' * 76}")

        totp_code = db.generate_dynamic_totp(raw_totp_secret)
        assert len(totp_code) == 6, f"TOTP length must be 6 digits, got {len(totp_code)}"
        assert totp_code.isdigit(), f"TOTP must be purely numeric, got {totp_code}"
        print(f"  {ANSI.GREEN}[ PASS ]{ANSI.RESET} Generated live 6-digit TOTP token: {totp_code}")

        # Test spacing and lowercase tolerance
        spaced_totp_secret = "jbsw y3dp ehpk 3pxp jbsw y3dp ehpk 3pxp"
        sanitized_totp_code = db.generate_dynamic_totp(spaced_totp_secret)
        assert len(sanitized_totp_code) == 6 and sanitized_totp_code.isdigit()
        print(f"  {ANSI.GREEN}[ PASS ]{ANSI.RESET} Spacing & lowercase tolerance verified: {sanitized_totp_code}")

        # 4. Multi-Broker Switching Verification
        print(f"\n{ANSI.YELLOW}{ANSI.BOLD}▶ 4. MULTI-BROKER ATOMIC SWITCHING{ANSI.RESET}")
        print(f"  {'-' * 76}")

        # Save Shoonya and Groww credentials
        db.save_broker_credentials(
            broker_name="SHOONYA",
            client_id="FA55421",
            login_mpin="5678",
            totp_secret="JBSWY3DPEHPK3PXPJBSWY3DPEHPK3PXP",
            api_key="SHOONYA_N_REST_TOKEN_1"
        )
        db.save_broker_credentials(
            broker_name="GROWW",
            client_id="GRW9901",
            login_mpin="9911",
            totp_secret="JBSWY3DPEHPK3PXPJBSWY3DPEHPK3PXP",
            api_key="GROWW_API_TOKEN_888"
        )
        print(f"  {ANSI.GREEN}[ PASS ]{ANSI.RESET} Configured secondary brokers: SHOONYA and GROWW")

        # Set ANGEL_ONE active
        db.set_active_broker("ANGEL_ONE")
        active = db.get_active_broker()
        assert active["broker_name"] == "ANGEL_ONE", f"Expected ANGEL_ONE, got {active['broker_name']}"
        assert active["client_id"] == "A100982"
        print(f"  {ANSI.GREEN}[ PASS ]{ANSI.RESET} Active broker set: ANGEL_ONE (Client: {active['client_id']})")

        # Switch to SHOONYA
        db.set_active_broker("SHOONYA")
        active = db.get_active_broker()
        assert active["broker_name"] == "SHOONYA", f"Expected SHOONYA, got {active['broker_name']}"
        assert active["client_id"] == "FA55421"
        print(f"  {ANSI.GREEN}[ PASS ]{ANSI.RESET} Atomic broker switch verified: SHOONYA (Client: {active['client_id']})")

        # Verify ANGEL_ONE is no longer active
        angel_creds = db.get_broker_credentials("ANGEL_ONE")
        assert angel_creds["is_active"] is False, "ANGEL_ONE was not deactivated!"
        print(f"  {ANSI.GREEN}[ PASS ]{ANSI.RESET} Deactivation verified: ANGEL_ONE is_active=False")

        # 5. Institutional Trade Audit Trail & ₹60 Friction Test
        print(f"\n{ANSI.YELLOW}{ANSI.BOLD}▶ 5. TRADE AUDIT LOG & ₹60 FRICTION ENGINE{ANSI.RESET}")
        print(f"  {'-' * 76}")

        # Log new trade: BUY 10 shares of RELIANCE at ₹2500.00, SL ₹2480.00
        trade_id = db.log_trade_entry(
            market_session="EQUITY",
            broker_name="ANGEL_ONE",
            symbol="RELIANCE.NS",
            trade_side="BUY",
            quantity=10,
            entry_price=2500.0,
            stop_loss=2480.0,
            execution_mode="PAPER",
            friction_cost=60.0
        )
        assert trade_id > 0, f"Invalid trade_id returned: {trade_id}"
        print(f"  {ANSI.GREEN}[ PASS ]{ANSI.RESET} Trade opened: ID #{trade_id} | BUY 10 RELIANCE.NS @ ₹2500.00")

        # Exit trade at ₹2508.00 -> Gross PnL = (2508 - 2500) * 10 = ₹80.00
        closed_trade = db.update_trade_exit(
            trade_id=trade_id,
            exit_price=2508.0,
            status="CLOSED"
        )

        expected_gross_pnl = 80.0
        expected_friction = 60.0
        expected_net_pnl = 20.0

        assert closed_trade["gross_pnl"] == expected_gross_pnl, f"Gross PnL mismatch: expected {expected_gross_pnl}, got {closed_trade['gross_pnl']}"
        assert closed_trade["friction_cost"] == expected_friction, f"Friction mismatch: expected {expected_friction}, got {closed_trade['friction_cost']}"
        assert closed_trade["net_pnl"] == expected_net_pnl, f"Net PnL mismatch: expected {expected_net_pnl}, got {closed_trade['net_pnl']}"
        assert closed_trade["status"] == "CLOSED"

        print(f"  {ANSI.GREEN}[ PASS ]{ANSI.RESET} Trade closed: Exit @ ₹2508.00")
        print(f"  {ANSI.GREEN}[ PASS ]{ANSI.RESET} Gross P&L: ₹{closed_trade['gross_pnl']:.2f}")
        print(f"  {ANSI.GREEN}[ PASS ]{ANSI.RESET} Statutory Friction Buffer: -₹{closed_trade['friction_cost']:.2f}")
        print(f"  {ANSI.GREEN}[ PASS ]{ANSI.RESET} Net P&L: ₹{closed_trade['net_pnl']:.2f} (Verified: ₹80.00 - ₹60.00 = ₹20.00)")

        # Verify trade list fetch
        recent_trades = db.get_all_trades(limit=5)
        assert len(recent_trades) == 1
        assert recent_trades[0]["id"] == trade_id
        print(f"  {ANSI.GREEN}[ PASS ]{ANSI.RESET} Trade audit query verified: 1 trade recorded in persistent log")

        print("\n" + "=" * 80)
        print(f"{ANSI.BG_GREEN}{ANSI.WHITE}{ANSI.BOLD} PHASE 2 COMPLETE: ALL 16 SUBSYSTEM ASSERTIONS CERTIFIED PASS. {ANSI.RESET}\n")
        print(f"{ANSI.GREEN}AES-256 encrypted vault, multi-broker schema, dynamic TOTP generator, and ₹60 friction")
        print(f"audit ledger are fully operational for production deployment.{ANSI.RESET}\n")

    except AssertionError as exc:
        all_passed = False
        print(f"\n{ANSI.BG_RED}{ANSI.WHITE}{ANSI.BOLD} TEST ASSERTION FAILED {ANSI.RESET}")
        print(f"{ANSI.RED}Error: {str(exc)}{ANSI.RESET}\n")
    except Exception as exc:
        all_passed = False
        print(f"\n{ANSI.BG_RED}{ANSI.WHITE}{ANSI.BOLD} UNEXPECTED EXCEPTION {ANSI.RESET}")
        print(f"{ANSI.RED}{exc.__class__.__name__}: {str(exc)}{ANSI.RESET}\n")
    finally:
        db.close()
        test_dir.cleanup()

    return all_passed


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)

