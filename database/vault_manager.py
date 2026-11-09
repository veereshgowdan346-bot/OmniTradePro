#!/usr/bin/env python3
"""
OmniTradePro - Multi-Broker Encrypted Vault Manager
Platform: Windows 10/11 64-bit | Python 3.10+
Provides AES-256 (Fernet) encrypted storage and retrieval for broker credentials
(Angel One, Shoonya, Groww) stored inside `database/omnitrade_vault.db` with SQLite WAL mode.
Zero plaintext credentials in files or logs.
"""

import os
import sqlite3
import threading
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

import pyotp
from cryptography.fernet import Fernet

from database.paths import KEY_FILENAME, VAULT_FILENAME, resolve_path


class VaultManager:
    """
    Production AES-256 Fernet encrypted credential vault manager.
    Operates on `omnitrade_vault.db` with thread-safe SQLite WAL mode.
    Encrypted fields: API Key, Secret Key, Login MPIN/Password, TOTP Secret, Trading PIN, Vendor Code, IMEI.
    """

    SUPPORTED_BROKERS = ("ANGEL_ONE", "SHOONYA", "GROWW")
    SCHEMA_VERSION = "1.0"

    def __init__(
        self,
        db_path: Optional[str] = None,
        key_path: Optional[str] = None,
        db_handler: Optional[Any] = None,
        vault_path: Optional[Any] = None,
        **kwargs
    ) -> None:
        self._lock = threading.RLock()
        self._thread_local = threading.local()
        effective_db_path = db_path or vault_path
        self._configure_paths(effective_db_path, key_path)
        self.db = db_handler
        self._init_encryption_engine()
        self._init_database()

    def _configure_paths(self, db_path: Optional[Any], key_path: Optional[Any]) -> None:
        """Sets up filesystem paths for the SQLite vault database and Fernet key file."""
        self.db_path = resolve_path(db_path, VAULT_FILENAME)
        self.key_path = resolve_path(key_path, KEY_FILENAME)

        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.key_path.parent.mkdir(parents=True, exist_ok=True)

    def _init_encryption_engine(self) -> None:
        """
        Initializes the AES-256 Fernet cipher suite.
        Reuses or generates and secures the local key file (.vault.key).
        """
        with self._lock:
            if not self.key_path.exists():
                new_key = Fernet.generate_key()
                with open(self.key_path, "wb") as kf:
                    kf.write(new_key)
                    kf.flush()
                    os.fsync(kf.fileno())
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
        try:
            return self._cipher.decrypt(ciphertext).decode("utf-8")
        except Exception:
            return ""

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

    def _init_database(self) -> None:
        """Creates the vault schema idempotently with field-level encryption support."""
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
                vendor_code_enc BLOB,
                imei_enc BLOB,
                trading_pin_enc BLOB,
                notes TEXT,
                is_active INTEGER DEFAULT 0,
                is_trading_enabled INTEGER DEFAULT 0,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS trading_toggles (
                broker_name TEXT PRIMARY KEY,
                is_trading_enabled INTEGER DEFAULT 0,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                schema_version TEXT,
                notes TEXT
            );

            CREATE TABLE IF NOT EXISTS vault_audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                broker_name TEXT NOT NULL,
                action TEXT NOT NULL,
                details TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS notification_vault (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                recipient_email TEXT,
                sender_email TEXT,
                smtp_server TEXT,
                smtp_port INTEGER DEFAULT 587,
                smtp_password_enc BLOB,
                trade_alerts_enabled INTEGER DEFAULT 1,
                daily_summary_enabled INTEGER DEFAULT 1,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """)

            # Upgrade columns safely if migrating from older schema
            for col_sql in [
                "ALTER TABLE broker_vault ADD COLUMN trading_pin_enc BLOB;",
                "ALTER TABLE broker_vault ADD COLUMN notes TEXT;",
            ]:
                try:
                    cursor.execute(col_sql)
                except Exception:
                    pass

            conn.commit()
            cursor.close()

    def save_broker_credentials(
        self,
        broker_name: str,
        client_id: str,
        login_mpin: str = "",
        totp_secret: str = "",
        api_key: str = "",
        secret_key: str = "",
        vendor_code: str = "",
        imei: str = "",
        is_active: bool = False,
        is_trading_enabled: bool = False,
        trading_pin: str = "",
        notes: str = "",
        **kwargs
    ) -> bool:
        """
        Encrypts and upserts credentials for any supported broker.
        Validates TOTP secret format and enforces field-level AES-256 encryption.
        """
        normalized_broker = broker_name.strip().upper()
        if normalized_broker not in self.SUPPORTED_BROKERS:
            raise ValueError(
                f"Unsupported broker '{broker_name}'. Must be one of: {', '.join(self.SUPPORTED_BROKERS)}"
            )

        clean_client_id = client_id.strip()
        clean_mpin = login_mpin.strip()
        clean_totp = totp_secret.replace(" ", "").strip().upper()
        clean_trading_pin = (trading_pin or "").strip()

        if not clean_client_id:
            raise ValueError("client_id cannot be empty.")
        if not clean_mpin:
            raise ValueError("login_mpin cannot be empty.")
        if not clean_totp:
            raise ValueError("totp_secret cannot be empty.")

        # Test TOTP validity before encrypting
        try:
            self.generate_dynamic_totp(clean_totp)
        except Exception as exc:
            raise ValueError(f"Invalid Base32 TOTP secret format: {str(exc)}")

        # Perform field-level encryption
        api_key_enc = self._encrypt(api_key.strip())
        secret_key_enc = self._encrypt(secret_key.strip())
        login_mpin_enc = self._encrypt(clean_mpin)
        totp_secret_enc = self._encrypt(clean_totp)
        vendor_code_enc = self._encrypt(vendor_code.strip())
        imei_enc = self._encrypt(imei.strip())
        trading_pin_enc = self._encrypt(clean_trading_pin)

        with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("""
            INSERT INTO broker_vault (
                broker_name, client_id, api_key_enc, secret_key_enc,
                login_mpin_enc, totp_secret_enc, vendor_code_enc, imei_enc,
                trading_pin_enc, notes, is_active, is_trading_enabled, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(broker_name) DO UPDATE SET
                client_id = excluded.client_id,
                api_key_enc = excluded.api_key_enc,
                secret_key_enc = excluded.secret_key_enc,
                login_mpin_enc = excluded.login_mpin_enc,
                totp_secret_enc = excluded.totp_secret_enc,
                vendor_code_enc = excluded.vendor_code_enc,
                imei_enc = excluded.imei_enc,
                trading_pin_enc = excluded.trading_pin_enc,
                notes = excluded.notes,
                is_active = excluded.is_active,
                is_trading_enabled = excluded.is_trading_enabled,
                updated_at = CURRENT_TIMESTAMP
            """, (
                normalized_broker,
                clean_client_id,
                api_key_enc,
                secret_key_enc,
                login_mpin_enc,
                totp_secret_enc,
                vendor_code_enc,
                imei_enc,
                trading_pin_enc,
                notes,
                1 if is_active else 0,
                1 if is_trading_enabled else 0
            ))

            cursor.execute("""
            INSERT INTO trading_toggles (broker_name, is_trading_enabled, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(broker_name) DO UPDATE SET
                is_trading_enabled = excluded.is_trading_enabled,
                updated_at = CURRENT_TIMESTAMP
            """, (normalized_broker, 1 if is_trading_enabled else 0))

            conn.commit()
            cursor.close()

            # Dual-database synchronization with database/omnitrade.db if handler present
            if self.db and hasattr(self.db, "store_broker_credentials"):
                try:
                    self.db.store_broker_credentials(
                        broker_name=normalized_broker,
                        client_id=clean_client_id,
                        api_key=api_key.strip(),
                        secret_key=secret_key.strip(),
                        login_mpin=clean_mpin,
                        trading_pin=clean_trading_pin,
                        totp_secret=clean_totp,
                        is_active=is_active,
                        notes=notes
                    )
                except Exception:
                    pass

            return True

    def store_broker_credentials(self, *args, **kwargs) -> bool:
        """Alias for save_broker_credentials."""
        return self.save_broker_credentials(*args, **kwargs)

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
                # Try fallback from database handler if available
                if self.db and hasattr(self.db, "get_broker_credentials"):
                    try:
                        return self.db.get_broker_credentials(normalized_broker)
                    except Exception:
                        pass
                raise ValueError(f"Broker '{normalized_broker}' credentials not found in vault.")

            keys = row.keys() if hasattr(row, "keys") else []
            trading_pin = self._decrypt(row["trading_pin_enc"]) if "trading_pin_enc" in keys else ""
            notes = row["notes"] if "notes" in keys and row["notes"] else ""

            return {
                "broker_name": row["broker_name"],
                "client_id": row["client_id"],
                "login_mpin": self._decrypt(row["login_mpin_enc"]),
                "totp_secret": self._decrypt(row["totp_secret_enc"]),
                "api_key": self._decrypt(row["api_key_enc"]),
                "secret_key": self._decrypt(row["secret_key_enc"]),
                "vendor_code": self._decrypt(row["vendor_code_enc"]),
                "imei": self._decrypt(row["imei_enc"]),
                "trading_pin": trading_pin,
                "notes": notes,
                "is_active": bool(row["is_active"]),
                "is_trading_enabled": bool(row["is_trading_enabled"]),
                "updated_at": row["updated_at"]
            }

    def has_broker_credentials(self, broker_name: str) -> bool:
        """Returns True if credentials for the broker are saved in the vault."""
        normalized_broker = broker_name.strip().upper()
        with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM broker_vault WHERE broker_name = ?", (normalized_broker,))
            row = cursor.fetchone()
            cursor.close()
            if row is not None:
                return True
            if self.db and hasattr(self.db, "has_broker_credentials"):
                try:
                    return self.db.has_broker_credentials(normalized_broker)
                except Exception:
                    pass
            return False

    def get_all_credentials(self) -> Dict[str, Dict[str, Any]]:
        """Retrieves and decrypts credentials for all configured brokers."""
        result = {}
        for broker in self.SUPPORTED_BROKERS:
            try:
                result[broker] = self.get_broker_credentials(broker)
            except ValueError:
                pass
        return result

    def get_all_toggles(self) -> Dict[str, bool]:
        """Returns a dictionary mapping each broker name to its trading toggle state."""
        return {broker: self.is_trading_enabled(broker) for broker in self.SUPPORTED_BROKERS}

    def set_trading_enabled(self, broker_name: str, enabled: bool) -> bool:
        """
        Toggles the trading execution switch for a specific broker.
        Even if connected, no orders are sent unless this is True.
        """
        normalized_broker = broker_name.strip().upper()
        with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE broker_vault SET is_trading_enabled = ?, updated_at = CURRENT_TIMESTAMP WHERE broker_name = ?",
                (1 if enabled else 0, normalized_broker)
            )
            rows = cursor.rowcount

            cursor.execute("""
            INSERT INTO trading_toggles (broker_name, is_trading_enabled, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(broker_name) DO UPDATE SET
                is_trading_enabled = excluded.is_trading_enabled,
                updated_at = CURRENT_TIMESTAMP
            """, (normalized_broker, 1 if enabled else 0))

            conn.commit()
            cursor.close()

            # Sync to DatabaseHandler if present
            if self.db and hasattr(self.db, "set_trading_enabled"):
                try:
                    self.db.set_trading_enabled(normalized_broker, enabled)
                except Exception:
                    pass

            return rows > 0 or True

    def is_trading_enabled(self, broker_name: str) -> bool:
        """Checks if the trading toggle is enabled for a specific broker."""
        normalized_broker = broker_name.strip().upper()
        with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute(
                "SELECT is_trading_enabled FROM broker_vault WHERE broker_name = ?",
                (normalized_broker,)
            )
            row = cursor.fetchone()
            if row:
                val = bool(row["is_trading_enabled"])
                cursor.close()
                return val

            cursor.execute(
                "SELECT is_trading_enabled FROM trading_toggles WHERE broker_name = ?",
                (normalized_broker,)
            )
            t_row = cursor.fetchone()
            cursor.close()
            if t_row:
                return bool(t_row["is_trading_enabled"])

            return False

    def get_enabled_trading_brokers(self) -> List[str]:
        """Returns list of broker names where trading toggle is enabled."""
        with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute(
                "SELECT broker_name FROM broker_vault WHERE is_trading_enabled = 1"
            )
            rows = cursor.fetchall()
            cursor.close()
            return [row["broker_name"] for row in rows]

    def set_active_broker(self, broker_name: str) -> bool:
        """Activates the specified primary broker and deactivates others."""
        normalized_broker = broker_name.strip().upper()
        with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM broker_vault WHERE broker_name = ?", (normalized_broker,))
            if not cursor.fetchone():
                cursor.close()
                return False

            cursor.execute("UPDATE broker_vault SET is_active = 0 WHERE is_active = 1;")
            cursor.execute(
                "UPDATE broker_vault SET is_active = 1, updated_at = CURRENT_TIMESTAMP WHERE broker_name = ?;",
                (normalized_broker,)
            )
            conn.commit()
            cursor.close()
            return True

    def delete_broker_credentials(self, broker_name: str) -> bool:
        """Permanently deletes broker credentials from the encrypted vault."""
        normalized_broker = broker_name.strip().upper()
        with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("DELETE FROM broker_vault WHERE broker_name = ?", (normalized_broker,))
            cursor.execute("DELETE FROM trading_toggles WHERE broker_name = ?", (normalized_broker,))
            rows = cursor.rowcount
            conn.commit()
            cursor.close()
            return rows > 0

    # =========================================================================
    # Auto-TOTP Generation Engine
    # =========================================================================

    @staticmethod
    def generate_dynamic_totp(totp_secret: str) -> str:
        """
        Calculates the real-time 6-digit TOTP token using pyotp.
        Handles Base32 padding, whitespace removal, and uppercase normalization.
        """
        if not totp_secret:
            raise ValueError("TOTP secret cannot be empty.")

        clean_secret = totp_secret.replace(" ", "").strip().upper()
        missing_padding = len(clean_secret) % 8
        if missing_padding:
            clean_secret += "=" * (8 - missing_padding)

        totp = pyotp.TOTP(clean_secret)
        return totp.now()

    def get_live_totp(self, broker_name: str) -> str:
        """
        Decrypts the stored TOTP secret for the broker and generates
        the current live 6-digit TOTP immediately.
        """
        creds = self.get_broker_credentials(broker_name)
        return self.generate_dynamic_totp(creds["totp_secret"])

    # =========================================================================
    # Encrypted Email & Notification Settings
    # =========================================================================

    def save_notification_settings(
        self,
        recipient_email: str,
        smtp_password: str = "",
        sender_email: str = "",
        smtp_server: str = "",
        smtp_port: int = 587,
        trade_alerts_enabled: bool = True,
        daily_summary_enabled: bool = True
    ) -> bool:
        """
        Persists email notification credentials with AES-256 field encryption.
        Guarantees zero plaintext exposure of SMTP passwords or API keys.
        """
        with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            pwd_enc = self._encrypt(smtp_password) if smtp_password else None
            cursor.execute("""
            INSERT INTO notification_vault (
                id, recipient_email, sender_email, smtp_server, smtp_port,
                smtp_password_enc, trade_alerts_enabled, daily_summary_enabled, updated_at
            ) VALUES (1, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(id) DO UPDATE SET
                recipient_email = excluded.recipient_email,
                sender_email = excluded.sender_email,
                smtp_server = excluded.smtp_server,
                smtp_port = excluded.smtp_port,
                smtp_password_enc = COALESCE(excluded.smtp_password_enc, notification_vault.smtp_password_enc),
                trade_alerts_enabled = excluded.trade_alerts_enabled,
                daily_summary_enabled = excluded.daily_summary_enabled,
                updated_at = CURRENT_TIMESTAMP;
            """, (
                recipient_email.strip(),
                sender_email.strip() or recipient_email.strip(),
                smtp_server.strip(),
                int(smtp_port) if smtp_port else 587,
                pwd_enc,
                1 if trade_alerts_enabled else 0,
                1 if daily_summary_enabled else 0
            ))
            conn.commit()
            cursor.close()
            return True

    def get_notification_settings(self) -> Dict[str, Any]:
        """
        Retrieves and decrypts notification credentials and alert flags from vault.
        """
        with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("""
            SELECT recipient_email, sender_email, smtp_server, smtp_port,
                   smtp_password_enc, trade_alerts_enabled, daily_summary_enabled
            FROM notification_vault WHERE id = 1;
            """)
            row = cursor.fetchone()
            cursor.close()
            if not row:
                return {
                    "recipient_email": "",
                    "sender_email": "",
                    "smtp_server": "",
                    "smtp_port": 587,
                    "smtp_password": "",
                    "trade_alerts_enabled": False,
                    "daily_summary_enabled": False
                }
            return {
                "recipient_email": row["recipient_email"] or "",
                "sender_email": row["sender_email"] or "",
                "smtp_server": row["smtp_server"] or "",
                "smtp_port": row["smtp_port"] or 587,
                "smtp_password": self._decrypt(row["smtp_password_enc"]),
                "trade_alerts_enabled": bool(row["trade_alerts_enabled"]),
                "daily_summary_enabled": bool(row["daily_summary_enabled"])
            }