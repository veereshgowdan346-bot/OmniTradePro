#!/usr/bin/env python3
"""
OmniTradePro - Multi-Broker Database Vault & Dynamic 2FA Authentication Engine
Platform: Windows 10/11 64-bit | Python 3.10+
Implements AES-256 (Fernet) field-level encryption for broker credentials,
secure local key management, dynamic Base32 TOTP token generation,
and institutional trade execution audit logging with friction modeling.
"""

import os
import sys
import sqlite3
import threading
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List

import pyotp
from cryptography.fernet import Fernet


class DatabaseHandler:
    """
    Thread-safe database handler managing the encrypted broker credential vault,
    dynamic 2FA authentication, and the institutional trade audit trail.
    """
    _instance: Optional["DatabaseHandler"] = None
    _singleton_lock = threading.Lock()

    SUPPORTED_BROKERS = ("ANGEL_ONE", "SHOONYA", "GROWW")
    MARKET_SESSIONS = ("EQUITY", "MCX")
    TRADE_SIDES = ("BUY", "SELL")
    EXECUTION_MODES = ("PAPER", "LIVE")
    TRADE_STATUSES = ("OPEN", "CLOSED", "CANCELLED")

    def __new__(cls, db_path: Optional[str] = None, key_path: Optional[str] = None) -> "DatabaseHandler":
        with cls._singleton_lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._is_initialized = False
            return cls._instance

    def __init__(self, db_path: Optional[str] = None, key_path: Optional[str] = None) -> None:
        if getattr(self, "_is_initialized", False):
            # If explicit paths provided to re-initialize an instance, allow updating
            if db_path is not None and Path(db_path) != self.db_path:
                self._configure_paths(db_path, key_path)
                self.initialize_database()
            return

        self._lock = threading.RLock()
        self._thread_local = threading.local()
        self._configure_paths(db_path, key_path)
        self._init_encryption_engine()
        self.initialize_database()
        self._is_initialized = True

    def _configure_paths(self, db_path: Optional[str], key_path: Optional[str]) -> None:
        """Sets up filesystem paths for the SQLite database and Fernet key file."""
        base_dir = Path(__file__).resolve().parent
        
        if db_path is None:
            self.db_path = base_dir / "omnitrade.db"
        else:
            self.db_path = Path(db_path)
            
        if key_path is None:
            self.key_path = base_dir / ".vault.key"
        else:
            self.key_path = Path(key_path)

        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.key_path.parent.mkdir(parents=True, exist_ok=True)

    def _init_encryption_engine(self) -> None:
        """
        Initializes the AES-256 Fernet cipher suite.
        Generates and secures the local key file (.vault.key) if absent.
        """
        with self._lock:
            if not self.key_path.exists():
                new_key = Fernet.generate_key()
                # Write key with strict atomic write
                with open(self.key_path, "wb") as kf:
                    kf.write(new_key)
                    kf.flush()
                    os.fsync(kf.fileno())
                # Restrict permissions on Windows/POSIX
                try:
                    os.chmod(self.key_path, 0o600)
                except Exception:
                    pass
                self._cipher_key = new_key
            else:
                with open(self.key_path, "rb") as kf:
                    self._cipher_key = kf.read().strip()

            self._cipher = Fernet(self._cipher_key)

    def _encrypt(self, plaintext: str) -> bytes:
        """Encrypts a plaintext string into Fernet ciphertext bytes."""
        if not plaintext:
            return b""
        return self._cipher.encrypt(plaintext.encode("utf-8"))

    def _decrypt(self, ciphertext: Optional[bytes]) -> str:
        """Decrypts Fernet ciphertext bytes back into a UTF-8 plaintext string."""
        if not ciphertext or len(ciphertext) == 0:
            return ""
        return self._cipher.decrypt(ciphertext).decode("utf-8")

    def _get_connection(self) -> sqlite3.Connection:
        """Provides a thread-isolated SQLite connection configured with WAL mode."""
        if not hasattr(self._thread_local, "connection") or self._thread_local.connection is None:
            conn = sqlite3.connect(
                str(self.db_path),
                timeout=20.0,
                check_same_thread=False
            )
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("PRAGMA journal_mode = WAL;")
            cursor.execute("PRAGMA synchronous = NORMAL;")
            cursor.execute("PRAGMA busy_timeout = 5000;")
            cursor.execute("PRAGMA foreign_keys = ON;")
            cursor.close()
            self._thread_local.connection = conn
            
        return self._thread_local.connection

    # =========================================================================
    # Schema Architecture
    # =========================================================================

    def initialize_database(self) -> None:
        """
        Constructs the institutional database tables and indexes idempotently.
        Creates table `broker_vault` and table `trade_audit_log`.
        """
        with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.executescript("""
            CREATE TABLE IF NOT EXISTS broker_vault (
                broker_name TEXT PRIMARY KEY,
                client_id TEXT NOT NULL,
                api_key_enc BLOB,
                secret_key_enc BLOB,
                login_mpin_enc BLOB NOT NULL,
                totp_secret_enc BLOB NOT NULL,
                is_active INTEGER DEFAULT 0,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS trade_audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                market_session TEXT NOT NULL,
                broker_name TEXT NOT NULL,
                symbol TEXT NOT NULL,
                trade_side TEXT NOT NULL,
                quantity INTEGER NOT NULL,
                entry_price REAL NOT NULL,
                exit_price REAL,
                stop_loss REAL NOT NULL,
                gross_pnl REAL DEFAULT 0.0,
                friction_cost REAL DEFAULT 60.0,
                net_pnl REAL DEFAULT 0.0,
                execution_mode TEXT NOT NULL,
                status TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_vault_active ON broker_vault(is_active);
            CREATE INDEX IF NOT EXISTS idx_audit_symbol ON trade_audit_log(symbol);
            CREATE INDEX IF NOT EXISTS idx_audit_broker ON trade_audit_log(broker_name);
            CREATE INDEX IF NOT EXISTS idx_audit_session ON trade_audit_log(market_session);
            CREATE INDEX IF NOT EXISTS idx_audit_status ON trade_audit_log(status);
            CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON trade_audit_log(timestamp);
            """)
            conn.commit()
            cursor.close()

    # =========================================================================
    # Multi-Broker Encrypted Vault API
    # =========================================================================

    def save_broker_credentials(
        self,
        broker_name: str,
        client_id: str,
        login_mpin: str,
        totp_secret: str,
        api_key: str = "",
        secret_key: str = ""
    ) -> bool:
        """
        Encrypts and upserts broker credentials into broker_vault.
        Accommodates Angel One, Shoonya, and Groww credential models.
        """
        normalized_broker = broker_name.strip().upper()
        if normalized_broker not in self.SUPPORTED_BROKERS:
            raise ValueError(
                f"Unsupported broker '{broker_name}'. Must be one of: {', '.join(self.SUPPORTED_BROKERS)}"
            )

        clean_client_id = client_id.strip()
        clean_mpin = login_mpin.strip()
        clean_totp = totp_secret.replace(" ", "").strip().upper()

        if not clean_client_id:
            raise ValueError("client_id cannot be empty.")
        if not clean_mpin:
            raise ValueError("login_mpin cannot be empty.")
        if not clean_totp:
            raise ValueError("totp_secret cannot be empty.")

        # Test TOTP validity before encrypting
        try:
            padded_totp = clean_totp
            missing_padding = len(padded_totp) % 8
            if missing_padding:
                padded_totp += "=" * (8 - missing_padding)
            pyotp.TOTP(padded_totp).now()
        except Exception as exc:
            raise ValueError(f"Invalid Base32 TOTP secret format: {str(exc)}")

        # Perform field-level encryption
        api_key_enc = self._encrypt(api_key.strip())
        secret_key_enc = self._encrypt(secret_key.strip())
        login_mpin_enc = self._encrypt(clean_mpin)
        totp_secret_enc = self._encrypt(clean_totp)

        with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("""
            INSERT INTO broker_vault (
                broker_name, client_id, api_key_enc, secret_key_enc,
                login_mpin_enc, totp_secret_enc, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(broker_name) DO UPDATE SET
                client_id = excluded.client_id,
                api_key_enc = excluded.api_key_enc,
                secret_key_enc = excluded.secret_key_enc,
                login_mpin_enc = excluded.login_mpin_enc,
                totp_secret_enc = excluded.totp_secret_enc,
                updated_at = CURRENT_TIMESTAMP
            """, (
                normalized_broker,
                clean_client_id,
                api_key_enc,
                secret_key_enc,
                login_mpin_enc,
                totp_secret_enc
            ))
            conn.commit()
            cursor.close()
            return True

    def get_broker_credentials(self, broker_name: str) -> Dict[str, Any]:
        """
        Retrieves and decrypts credentials for a specified broker.
        Returns a clean plaintext dictionary.
        """
        normalized_broker = broker_name.strip().upper()
        with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM broker_vault WHERE broker_name = ?",
                (normalized_broker,)
            )
            row = cursor.fetchone()
            cursor.close()

            if not row:
                raise ValueError(f"Broker '{normalized_broker}' credentials not found in vault.")

            return {
                "broker_name": row["broker_name"],
                "client_id": row["client_id"],
                "login_mpin": self._decrypt(row["login_mpin_enc"]),
                "totp_secret": self._decrypt(row["totp_secret_enc"]),
                "api_key": self._decrypt(row["api_key_enc"]),
                "secret_key": self._decrypt(row["secret_key_enc"]),
                "is_active": bool(row["is_active"]),
                "updated_at": row["updated_at"]
            }

    def set_active_broker(self, broker_name: str) -> bool:
        """
        Deactivates all brokers and activates the specified target broker.
        Returns True if successful, False if the target broker is not configured.
        """
        normalized_broker = broker_name.strip().upper()
        with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            # Verify broker exists in vault
            cursor.execute("SELECT broker_name FROM broker_vault WHERE broker_name = ?", (normalized_broker,))
            if not cursor.fetchone():
                cursor.close()
                return False

            # Transactional atomic switch
            cursor.execute("UPDATE broker_vault SET is_active = 0 WHERE is_active = 1;")
            cursor.execute(
                "UPDATE broker_vault SET is_active = 1, updated_at = CURRENT_TIMESTAMP WHERE broker_name = ?;",
                (normalized_broker,)
            )
            conn.commit()
            cursor.close()
            return True

    def get_active_broker(self) -> Dict[str, Any]:
        """
        Retrieves and decrypts the credentials of the currently active broker.
        Returns empty dictionary if no broker is active.
        """
        with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM broker_vault WHERE is_active = 1 LIMIT 1;")
            row = cursor.fetchone()
            cursor.close()

            if not row:
                return {}

            return {
                "broker_name": row["broker_name"],
                "client_id": row["client_id"],
                "login_mpin": self._decrypt(row["login_mpin_enc"]),
                "totp_secret": self._decrypt(row["totp_secret_enc"]),
                "api_key": self._decrypt(row["api_key_enc"]),
                "secret_key": self._decrypt(row["secret_key_enc"]),
                "is_active": True,
                "updated_at": row["updated_at"]
            }

    def list_configured_brokers(self) -> List[Dict[str, Any]]:
        """Returns metadata for all configured brokers in the vault without decrypting keys."""
        with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT broker_name, client_id, is_active, updated_at FROM broker_vault ORDER BY broker_name ASC;")
            rows = cursor.fetchall()
            cursor.close()
            return [
                {
                    "broker_name": r["broker_name"],
                    "client_id": r["client_id"],
                    "is_active": bool(r["is_active"]),
                    "updated_at": r["updated_at"]
                }
                for r in rows
            ]

    # =========================================================================
    # Dynamic 2FA TOTP Generation
    # =========================================================================

    @staticmethod
    def generate_dynamic_totp(totp_secret: str) -> str:
        """
        Generates a live 6-digit Time-based One-Time Password (TOTP) from the secret.
        Cleans spacing and normalizes Base32 padding to ensure 100% reliable generation.
        """
        if not totp_secret:
            raise ValueError("TOTP secret cannot be empty.")

        clean_secret = totp_secret.replace(" ", "").strip().upper()
        
        # Enforce proper RFC 3548 / RFC 4648 Base32 padding if missing
        missing_padding = len(clean_secret) % 8
        if missing_padding != 0:
            clean_secret += "=" * (8 - missing_padding)

        totp = pyotp.TOTP(clean_secret)
        token = str(totp.now())

        # Ensure guaranteed 6-digit output padded with leading zeros if necessary
        return token.zfill(6)

    # =========================================================================
    # Trade Execution Audit Trail Interface
    # =========================================================================

    def log_trade_entry(
        self,
        market_session: str,
        broker_name: str,
        symbol: str,
        trade_side: str,
        quantity: int,
        entry_price: float,
        stop_loss: float,
        execution_mode: str = "PAPER",
        friction_cost: float = 60.0
    ) -> int:
        """
        Logs a newly initiated trade entry into trade_audit_log with status 'OPEN'.
        Returns the unique trade ID.
        """
        normalized_session = market_session.strip().upper()
        normalized_side = trade_side.strip().upper()
        normalized_mode = execution_mode.strip().upper()

        if normalized_session not in self.MARKET_SESSIONS:
            raise ValueError(f"Invalid market_session '{market_session}'. Expected: {self.MARKET_SESSIONS}")
        if normalized_side not in self.TRADE_SIDES:
            raise ValueError(f"Invalid trade_side '{trade_side}'. Expected: {self.TRADE_SIDES}")
        if normalized_mode not in self.EXECUTION_MODES:
            raise ValueError(f"Invalid execution_mode '{execution_mode}'. Expected: {self.EXECUTION_MODES}")
        if quantity <= 0:
            raise ValueError(f"Quantity must be positive integer, got {quantity}")
        if entry_price <= 0.0:
            raise ValueError(f"Entry price must be positive, got {entry_price}")
        if stop_loss <= 0.0:
            raise ValueError(f"Stop loss must be positive, got {stop_loss}")

        timestamp_iso = datetime.now(timezone.utc).isoformat()

        with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("""
            INSERT INTO trade_audit_log (
                timestamp, market_session, broker_name, symbol, trade_side,
                quantity, entry_price, exit_price, stop_loss, gross_pnl,
                friction_cost, net_pnl, execution_mode, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, NULL, ?, 0.0, ?, 0.0, ?, 'OPEN')
            """, (
                timestamp_iso,
                normalized_session,
                broker_name.strip().upper(),
                symbol.strip().upper(),
                normalized_side,
                int(quantity),
                float(entry_price),
                float(stop_loss),
                float(friction_cost),
                normalized_mode
            ))
            trade_id = cursor.lastrowid
            conn.commit()
            cursor.close()
            return trade_id

    def update_trade_exit(
        self,
        trade_id: int,
        exit_price: float,
        status: str = "CLOSED",
        friction_cost: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Closes or updates an existing trade entry, calculating Gross P&L,
        applying statutory friction costs (default ₹60.0), and determining Net P&L.
        """
        if exit_price <= 0.0:
            raise ValueError(f"Exit price must be positive, got {exit_price}")

        normalized_status = status.strip().upper()
        if normalized_status not in self.TRADE_STATUSES:
            raise ValueError(f"Invalid status '{status}'. Expected: {self.TRADE_STATUSES}")

        with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM trade_audit_log WHERE id = ?", (trade_id,))
            row = cursor.fetchone()

            if not row:
                cursor.close()
                raise ValueError(f"Trade record with ID {trade_id} does not exist.")

            quantity = row["quantity"]
            entry_price = row["entry_price"]
            trade_side = row["trade_side"]
            
            effective_friction = float(friction_cost) if friction_cost is not None else float(row["friction_cost"])

            # Compute gross P&L based on direction
            if trade_side == "BUY":
                gross_pnl = (float(exit_price) - float(entry_price)) * quantity
            else:  # SELL (short)
                gross_pnl = (float(entry_price) - float(exit_price)) * quantity

            net_pnl = gross_pnl - effective_friction

            cursor.execute("""
            UPDATE trade_audit_log SET
                exit_price = ?,
                gross_pnl = ?,
                friction_cost = ?,
                net_pnl = ?,
                status = ?
            WHERE id = ?
            """, (
                float(exit_price),
                float(gross_pnl),
                float(effective_friction),
                float(net_pnl),
                normalized_status,
                trade_id
            ))
            conn.commit()

            cursor.execute("SELECT * FROM trade_audit_log WHERE id = ?", (trade_id,))
            updated_row = cursor.fetchone()
            cursor.close()
            return dict(updated_row)

    def get_trade(self, trade_id: int) -> Optional[Dict[str, Any]]:
        """Retrieves a single trade audit entry by ID."""
        with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM trade_audit_log WHERE id = ?", (trade_id,))
            row = cursor.fetchone()
            cursor.close()
            return dict(row) if row else None

    def get_all_trades(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Retrieves the most recent trade audit log records."""
        with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM trade_audit_log ORDER BY id DESC LIMIT ?",
                (limit,)
            )
            rows = cursor.fetchall()
            cursor.close()
            return [dict(r) for r in rows]

    def get_today_summary(self) -> Dict[str, Any]:
        """
        Calculates today's real trading summary from persistent trade_audit_log records:
        Total Trades, Winning Trades, Losing Trades, Win Rate %, Realized P&L,
        Unrealized P&L, Total Net P&L.
        """
        with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            cursor.execute(
                "SELECT * FROM trade_audit_log WHERE timestamp LIKE ?",
                (f"{today_str}%",)
            )
            rows = [dict(r) for r in cursor.fetchall()]
            cursor.close()

            total_trades = len(rows)
            wins = 0
            losses = 0
            realized_pnl = 0.0
            unrealized_pnl = 0.0

            for r in rows:
                status = r.get("status", "OPEN")
                net = float(r.get("net_pnl") or 0.0)
                if status == "CLOSED":
                    realized_pnl += net
                    if net > 0:
                        wins += 1
                    elif net < 0:
                        losses += 1
                elif status == "OPEN":
                    unrealized_pnl += net

            win_rate = (wins / total_trades * 100.0) if total_trades > 0 else 0.0

            return {
                "total_trades": total_trades,
                "wins": wins,
                "losses": losses,
                "win_rate": win_rate,
                "realized_pnl": realized_pnl,
                "unrealized_pnl": unrealized_pnl,
                "total_pnl": realized_pnl + unrealized_pnl
            }

    def close(self) -> None:
        """Closes the thread-local database connection if active."""
        if hasattr(self._thread_local, "connection") and self._thread_local.connection is not None:
            self._thread_local.connection.close()
            self._thread_local.connection = None

