#!/usr/bin/env python3
"""
OmniTradePro - Database & Audit Persistence Engine
Institutional transactional storage layer utilizing SQLite in WAL mode
with ACID compliance, thread safety, and millisecond query execution.
"""

import sqlite3
import threading
import json
import os
from pathlib import Path
from datetime import datetime, timezone
from typing import Any, Optional, Dict, List


class DatabaseManager:
    """
    Thread-safe SQLite database manager engineered for high-frequency order
    auditing, execution tracking, tick telemetry, and risk limit enforcement.
    """
    _instance: Optional["DatabaseManager"] = None
    _init_lock = threading.Lock()

    def __new__(cls, db_path: Optional[str] = None) -> "DatabaseManager":
        with cls._init_lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self, db_path: Optional[str] = None) -> None:
        if self._initialized:
            return
            
        if db_path is None:
            base_dir = Path(__file__).resolve().parent.parent
            self.db_path = base_dir / "database" / "omnitrade.db"
        else:
            self.db_path = Path(db_path)
            
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._local = threading.local()
        
        self._initialize_schema()
        self._initialized = True

    def _get_connection(self) -> sqlite3.Connection:
        """Retrieves or creates a thread-isolated SQLite connection with WAL mode."""
        if not hasattr(self._local, "connection") or self._local.connection is None:
            conn = sqlite3.connect(
                str(self.db_path),
                timeout=15.0,
                check_same_thread=False
            )
            conn.row_factory = sqlite3.Row
            # Configure high-performance production PRAGMAs
            cursor = conn.cursor()
            cursor.execute("PRAGMA journal_mode = WAL;")
            cursor.execute("PRAGMA synchronous = NORMAL;")
            cursor.execute("PRAGMA busy_timeout = 5000;")
            cursor.execute("PRAGMA foreign_keys = ON;")
            cursor.close()
            self._local.connection = conn
            
        return self._local.connection

    def _initialize_schema(self) -> None:
        """Generates the institutional database schema if not already constructed."""
        with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.executescript("""
            CREATE TABLE IF NOT EXISTS orders (
                order_id TEXT PRIMARY KEY,
                broker TEXT NOT NULL,
                broker_order_id TEXT,
                symbol TEXT NOT NULL,
                exchange TEXT NOT NULL,
                transaction_type TEXT NOT NULL,
                product_type TEXT NOT NULL,
                order_type TEXT NOT NULL,
                quantity INTEGER NOT NULL,
                price REAL NOT NULL,
                trigger_price REAL DEFAULT 0.0,
                status TEXT NOT NULL,
                filled_quantity INTEGER DEFAULT 0,
                average_price REAL DEFAULT 0.0,
                rejection_reason TEXT DEFAULT '',
                tag TEXT DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_orders_symbol ON orders(symbol);
            CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status);
            CREATE INDEX IF NOT EXISTS idx_orders_created ON orders(created_at);

            CREATE TABLE IF NOT EXISTS trades (
                trade_id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id TEXT NOT NULL,
                broker_order_id TEXT,
                symbol TEXT NOT NULL,
                exchange TEXT NOT NULL,
                transaction_type TEXT NOT NULL,
                quantity INTEGER NOT NULL,
                price REAL NOT NULL,
                turnover REAL NOT NULL,
                brokerage_est REAL NOT NULL,
                taxes_est REAL NOT NULL,
                net_amount REAL NOT NULL,
                executed_at TEXT NOT NULL,
                FOREIGN KEY (order_id) REFERENCES orders(order_id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_trades_symbol ON trades(symbol);
            CREATE INDEX IF NOT EXISTS idx_trades_executed ON trades(executed_at);

            CREATE TABLE IF NOT EXISTS positions (
                position_id TEXT PRIMARY KEY,
                broker TEXT NOT NULL,
                symbol TEXT NOT NULL,
                exchange TEXT NOT NULL,
                product_type TEXT NOT NULL,
                buy_qty INTEGER DEFAULT 0,
                buy_avg_price REAL DEFAULT 0.0,
                sell_qty INTEGER DEFAULT 0,
                sell_avg_price REAL DEFAULT 0.0,
                net_qty INTEGER DEFAULT 0,
                realized_pnl REAL DEFAULT 0.0,
                unrealized_pnl REAL DEFAULT 0.0,
                last_price REAL DEFAULT 0.0,
                updated_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_positions_symbol ON positions(symbol);

            CREATE TABLE IF NOT EXISTS ticks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                exchange TEXT NOT NULL,
                ltp REAL NOT NULL,
                change_pct REAL DEFAULT 0.0,
                volume INTEGER DEFAULT 0,
                bid_price REAL DEFAULT 0.0,
                bid_qty INTEGER DEFAULT 0,
                ask_price REAL DEFAULT 0.0,
                ask_qty INTEGER DEFAULT 0,
                open_interest INTEGER DEFAULT 0,
                timestamp TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_ticks_symbol_time ON ticks(symbol, timestamp);

            CREATE TABLE IF NOT EXISTS audit_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_type TEXT NOT NULL,
                severity TEXT NOT NULL,
                component TEXT NOT NULL,
                message TEXT NOT NULL,
                metadata_json TEXT DEFAULT '{}',
                timestamp TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_audit_time ON audit_logs(timestamp);
            CREATE INDEX IF NOT EXISTS idx_audit_severity ON audit_logs(severity);

            CREATE TABLE IF NOT EXISTS daily_risk_summary (
                date_key TEXT PRIMARY KEY,
                allocated_capital REAL NOT NULL,
                max_capital_risk_inr REAL NOT NULL,
                realized_pnl REAL DEFAULT 0.0,
                unrealized_pnl REAL DEFAULT 0.0,
                total_friction_inr REAL DEFAULT 0.0,
                peak_pnl REAL DEFAULT 0.0,
                max_drawdown_inr REAL DEFAULT 0.0,
                is_halted INTEGER DEFAULT 0,
                halt_reason TEXT DEFAULT '',
                updated_at TEXT NOT NULL
            );
            """)
            conn.commit()
            cursor.close()

    # =========================================================================
    # Order Management Interface
    # =========================================================================

    def insert_order(self, order_data: Dict[str, Any]) -> str:
        """Inserts a newly staged or routed order into persistent storage."""
        now_iso = datetime.now(timezone.utc).isoformat()
        with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("""
            INSERT INTO orders (
                order_id, broker, broker_order_id, symbol, exchange,
                transaction_type, product_type, order_type, quantity, price,
                trigger_price, status, filled_quantity, average_price,
                rejection_reason, tag, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                order_data["order_id"],
                order_data.get("broker", "ANGEL_ONE"),
                order_data.get("broker_order_id", ""),
                order_data["symbol"],
                order_data["exchange"],
                order_data["transaction_type"],
                order_data["product_type"],
                order_data["order_type"],
                int(order_data["quantity"]),
                float(order_data["price"]),
                float(order_data.get("trigger_price", 0.0)),
                order_data.get("status", "SUBMITTED"),
                int(order_data.get("filled_quantity", 0)),
                float(order_data.get("average_price", 0.0)),
                order_data.get("rejection_reason", ""),
                order_data.get("tag", ""),
                order_data.get("created_at", now_iso),
                now_iso
            ))
            conn.commit()
            cursor.close()
            return order_data["order_id"]

    def update_order_status(
        self,
        order_id: str,
        status: str,
        broker_order_id: Optional[str] = None,
        filled_quantity: Optional[int] = None,
        average_price: Optional[float] = None,
        rejection_reason: Optional[str] = None
    ) -> bool:
        """Updates the status and execution fills for an active order."""
        now_iso = datetime.now(timezone.utc).isoformat()
        with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            updates = ["status = ?", "updated_at = ?"]
            params: List[Any] = [status, now_iso]
            
            if broker_order_id is not None:
                updates.append("broker_order_id = ?")
                params.append(broker_order_id)
            if filled_quantity is not None:
                updates.append("filled_quantity = ?")
                params.append(int(filled_quantity))
            if average_price is not None:
                updates.append("average_price = ?")
                params.append(float(average_price))
            if rejection_reason is not None:
                updates.append("rejection_reason = ?")
                params.append(rejection_reason)
                
            params.append(order_id)
            query = f"UPDATE orders SET {', '.join(updates)} WHERE order_id = ?"
            cursor.execute(query, params)
            rows_affected = cursor.rowcount
            conn.commit()
            cursor.close()
            return rows_affected > 0

    def get_order(self, order_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves an order by internal order ID."""
        with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM orders WHERE order_id = ?", (order_id,))
            row = cursor.fetchone()
            cursor.close()
            return dict(row) if row else None

    def get_open_orders(self) -> List[Dict[str, Any]]:
        """Returns all open, pending, or partially filled orders."""
        with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("""
            SELECT * FROM orders 
            WHERE status IN ('PENDING', 'SUBMITTED', 'OPEN', 'PARTIALLY_FILLED')
            ORDER BY created_at DESC
            """)
            rows = cursor.fetchall()
            cursor.close()
            return [dict(r) for r in rows]

    def get_orders_by_date(self, start_date_iso: str, end_date_iso: str) -> List[Dict[str, Any]]:
        """Retrieves orders within a specified timestamp interval."""
        with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("""
            SELECT * FROM orders 
            WHERE created_at >= ? AND created_at <= ?
            ORDER BY created_at DESC
            """, (start_date_iso, end_date_iso))
            rows = cursor.fetchall()
            cursor.close()
            return [dict(r) for r in rows]

    # =========================================================================
    # Trade Execution Interface
    # =========================================================================

    def insert_trade(self, trade_data: Dict[str, Any]) -> int:
        """Records an individual execution fill with turnover and statutory friction costs."""
        now_iso = datetime.now(timezone.utc).isoformat()
        with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("""
            INSERT INTO trades (
                order_id, broker_order_id, symbol, exchange, transaction_type,
                quantity, price, turnover, brokerage_est, taxes_est, net_amount, executed_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                trade_data["order_id"],
                trade_data.get("broker_order_id", ""),
                trade_data["symbol"],
                trade_data["exchange"],
                trade_data["transaction_type"],
                int(trade_data["quantity"]),
                float(trade_data["price"]),
                float(trade_data["turnover"]),
                float(trade_data.get("brokerage_est", 20.0)),
                float(trade_data.get("taxes_est", 0.0)),
                float(trade_data["net_amount"]),
                trade_data.get("executed_at", now_iso)
            ))
            trade_id = cursor.lastrowid
            conn.commit()
            cursor.close()
            return trade_id

    def get_trades_for_order(self, order_id: str) -> List[Dict[str, Any]]:
        """Retrieves all execution fills associated with an order."""
        with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM trades WHERE order_id = ? ORDER BY executed_at ASC", (order_id,))
            rows = cursor.fetchall()
            cursor.close()
            return [dict(r) for r in rows]

    # =========================================================================
    # Position Tracking Interface
    # =========================================================================

    def upsert_position(self, pos: Dict[str, Any]) -> None:
        """Updates or registers a live portfolio position."""
        position_id = f"{pos.get('broker', 'ANGEL_ONE')}_{pos['exchange']}_{pos['symbol']}_{pos['product_type']}"
        now_iso = datetime.now(timezone.utc).isoformat()
        with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("""
            INSERT INTO positions (
                position_id, broker, symbol, exchange, product_type,
                buy_qty, buy_avg_price, sell_qty, sell_avg_price,
                net_qty, realized_pnl, unrealized_pnl, last_price, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(position_id) DO UPDATE SET
                buy_qty = excluded.buy_qty,
                buy_avg_price = excluded.buy_avg_price,
                sell_qty = excluded.sell_qty,
                sell_avg_price = excluded.sell_avg_price,
                net_qty = excluded.net_qty,
                realized_pnl = excluded.realized_pnl,
                unrealized_pnl = excluded.unrealized_pnl,
                last_price = excluded.last_price,
                updated_at = excluded.updated_at
            """, (
                position_id,
                pos.get("broker", "ANGEL_ONE"),
                pos["symbol"],
                pos["exchange"],
                pos["product_type"],
                int(pos.get("buy_qty", 0)),
                float(pos.get("buy_avg_price", 0.0)),
                int(pos.get("sell_qty", 0)),
                float(pos.get("sell_avg_price", 0.0)),
                int(pos.get("net_qty", 0)),
                float(pos.get("realized_pnl", 0.0)),
                float(pos.get("unrealized_pnl", 0.0)),
                float(pos.get("last_price", 0.0)),
                now_iso
            ))
            conn.commit()
            cursor.close()

    def get_all_positions(self) -> List[Dict[str, Any]]:
        """Retrieves all current portfolio positions."""
        with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM positions ORDER BY symbol ASC")
            rows = cursor.fetchall()
            cursor.close()
            return [dict(r) for r in rows]

    def update_position_ltp(self, symbol: str, exchange: str, ltp: float) -> None:
        """Recalculates unrealized PnL across active positions on incoming market tick."""
        now_iso = datetime.now(timezone.utc).isoformat()
        with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            # Fetch active net positions for symbol
            cursor.execute("""
            SELECT position_id, net_qty, buy_avg_price, sell_avg_price 
            FROM positions 
            WHERE symbol = ? AND exchange = ? AND net_qty != 0
            """, (symbol, exchange))
            rows = cursor.fetchall()
            
            for row in rows:
                pos_id = row["position_id"]
                net_qty = row["net_qty"]
                unrealized = 0.0
                if net_qty > 0:
                    unrealized = (ltp - row["buy_avg_price"]) * net_qty
                elif net_qty < 0:
                    unrealized = (row["sell_avg_price"] - ltp) * abs(net_qty)
                    
                cursor.execute("""
                UPDATE positions 
                SET last_price = ?, unrealized_pnl = ?, updated_at = ?
                WHERE position_id = ?
                """, (float(ltp), float(unrealized), now_iso, pos_id))
                
            conn.commit()
            cursor.close()

    # =========================================================================
    # Tick Telemetry Interface
    # =========================================================================

    def record_tick(self, tick: Dict[str, Any]) -> None:
        """Stores a high-frequency market tick snapshot for analytics and auditing."""
        now_iso = datetime.now(timezone.utc).isoformat()
        with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("""
            INSERT INTO ticks (
                symbol, exchange, ltp, change_pct, volume,
                bid_price, bid_qty, ask_price, ask_qty, open_interest, timestamp
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                tick["symbol"],
                tick.get("exchange", "NSE"),
                float(tick["ltp"]),
                float(tick.get("change_pct", 0.0)),
                int(tick.get("volume", 0)),
                float(tick.get("bid_price", 0.0)),
                int(tick.get("bid_qty", 0)),
                float(tick.get("ask_price", 0.0)),
                int(tick.get("ask_qty", 0)),
                int(tick.get("open_interest", 0)),
                tick.get("timestamp", now_iso)
            ))
            conn.commit()
            cursor.close()

    def get_recent_ticks(self, symbol: str, limit: int = 100) -> List[Dict[str, Any]]:
        """Retrieves recent price ticks for charting and indicator computations."""
        with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("""
            SELECT * FROM ticks 
            WHERE symbol = ? 
            ORDER BY timestamp DESC LIMIT ?
            """, (symbol, limit))
            rows = cursor.fetchall()
            cursor.close()
            # Return in chronological order
            return [dict(r) for r in reversed(rows)]

    # =========================================================================
    # Audit Logging Interface
    # =========================================================================

    def log_audit(
        self,
        event_type: str,
        severity: str,
        component: str,
        message: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """Writes an institutional audit trail entry."""
        now_iso = datetime.now(timezone.utc).isoformat()
        meta_str = json.dumps(metadata) if metadata else "{}"
        with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("""
            INSERT INTO audit_logs (
                event_type, severity, component, message, metadata_json, timestamp
            ) VALUES (?, ?, ?, ?, ?, ?)
            """, (event_type, severity.upper(), component, message, meta_str, now_iso))
            conn.commit()
            cursor.close()

    def get_audit_logs(self, limit: int = 100, severity: Optional[str] = None) -> List[Dict[str, Any]]:
        """Fetches the latest system audit events."""
        with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            if severity:
                cursor.execute("""
                SELECT * FROM audit_logs 
                WHERE severity = ? 
                ORDER BY timestamp DESC LIMIT ?
                """, (severity.upper(), limit))
            else:
                cursor.execute("""
                SELECT * FROM audit_logs 
                ORDER BY timestamp DESC LIMIT ?
                """, (limit,))
            rows = cursor.fetchall()
            cursor.close()
            return [dict(r) for r in rows]

    # =========================================================================
    # Risk & Daily Capital Summary Interface
    # =========================================================================

    def get_daily_risk_summary(self, date_key: str) -> Optional[Dict[str, Any]]:
        """Retrieves the daily risk management state for a specific date (YYYY-MM-DD)."""
        with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM daily_risk_summary WHERE date_key = ?", (date_key,))
            row = cursor.fetchone()
            cursor.close()
            return dict(row) if row else None

    def upsert_daily_risk_summary(self, summary: Dict[str, Any]) -> None:
        """Updates or initializes daily PnL, drawdowns, and trading halt flags."""
        now_iso = datetime.now(timezone.utc).isoformat()
        with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("""
            INSERT INTO daily_risk_summary (
                date_key, allocated_capital, max_capital_risk_inr, realized_pnl,
                unrealized_pnl, total_friction_inr, peak_pnl, max_drawdown_inr,
                is_halted, halt_reason, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(date_key) DO UPDATE SET
                allocated_capital = excluded.allocated_capital,
                max_capital_risk_inr = excluded.max_capital_risk_inr,
                realized_pnl = excluded.realized_pnl,
                unrealized_pnl = excluded.unrealized_pnl,
                total_friction_inr = excluded.total_friction_inr,
                peak_pnl = excluded.peak_pnl,
                max_drawdown_inr = excluded.max_drawdown_inr,
                is_halted = excluded.is_halted,
                halt_reason = excluded.halt_reason,
                updated_at = excluded.updated_at
            """, (
                summary["date_key"],
                float(summary["allocated_capital"]),
                float(summary["max_capital_risk_inr"]),
                float(summary.get("realized_pnl", 0.0)),
                float(summary.get("unrealized_pnl", 0.0)),
                float(summary.get("total_friction_inr", 0.0)),
                float(summary.get("peak_pnl", 0.0)),
                float(summary.get("max_drawdown_inr", 0.0)),
                1 if summary.get("is_halted", False) else 0,
                summary.get("halt_reason", ""),
                now_iso
            ))
            conn.commit()
            cursor.close()

    def get_today_summary(self) -> Dict[str, Any]:
        """
        Calculates today's real trading summary from persistent trade_audit_log records:
        Total Trades, Winning Trades, Losing Trades, Win Rate %, Realized P&L,
        Unrealized P&L, Total Net P&L.
        """
        today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            try:
                cursor.execute(
                    "SELECT * FROM trade_audit_log WHERE timestamp LIKE ?",
                    (f"{today_str}%",)
                )
                rows = [dict(r) for r in cursor.fetchall()]
            except Exception:
                rows = []
            finally:
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
        """Closes the current thread's connection if active."""
        if hasattr(self._local, "connection") and self._local.connection is not None:
            self._local.connection.close()
            self._local.connection = None

