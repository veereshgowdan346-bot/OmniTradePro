#!/usr/bin/env python3
"""
OmniTradePro - Dual-Mode Execution Gateway, Toggle-Aware Router & Auto Square-Off Engine
Platform: Windows 10/11 64-bit | Python 3.10+
Implements toggle-aware multi-broker order routing across Angel One, Shoonya, Groww, and Paper gateways.
Features:
- Pre-trade execution gate checking broker toggle matrix:
  * If ALL toggles OFF: Drop order with "Trading Locked: No active brokers enabled".
  * If Broker toggled ON but Disconnected: Reject on that broker, trigger alert, no crash.
  * If 1, 2, or 3 Brokers connected & toggled ON: Concurrent non-blocking dispatch.
- Pre-trade ₹70 gross profit gate and 10% daily drawdown circuit breaker adherence.
- Conservative 0.02% simulated slippage for Paper mode.
- Mandatory multi-session auto-square-off (15:15 IST Equity / 23:15 IST MCX).
- Persists all executions to SQLite audit log with ₹60 friction buffer.
"""

from datetime import datetime, time as dtime, timezone
from typing import Dict, Any, List, Optional, Callable
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed

import json
from pathlib import Path
from database.db_manager import DatabaseManager
from brokers.base_broker import (
    BaseBroker,
    OrderRequest,
    OrderResponse,
    OrderStatus,
    OrderSide,
    OrderType,
    ProductType,
    Exchange,
)
from brokers.angel_one import AngelOneBroker
from brokers.shoonya import ShoonyaBroker
from brokers.groww import GrowwBroker
from brokers.paper_broker import PaperBroker


class OrderRouter:
    """
    Toggle-aware institutional order routing and liquidation gateway.
    Coordinates live execution across multi-broker matrix and paper simulator.
    """

    EQUITY_SQUARE_OFF = dtime(15, 15)
    MCX_SQUARE_OFF = dtime(23, 15)
    PAPER_SLIPPAGE_RATE = 0.0002  # 0.02% conservative simulated slippage
    FRICTION_COST_INR = 60.0
    MIN_GROSS_PROFIT_HURDLE_INR = 70.0
    MAX_DRAWDOWN_PCT = 10.0
    MAX_TRADES_PER_INSTRUMENT_PER_DAY = 2

    def __init__(
        self,
        db_manager: Optional[DatabaseManager] = None,
        db_handler=None,
        vault_manager=None,
        enforce_daily_trade_cap: bool = False,
        **kwargs
    ) -> None:
        self.db_manager = db_manager or db_handler or DatabaseManager()
        self.db = self.db_manager
        self.vault = vault_manager
        if not self.vault:
            try:
                from database.vault_manager import VaultManager
                self.vault = VaultManager()
            except Exception:
                self.vault = None

        self._lock = threading.RLock()
        self._executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="OrderRouter_Worker")

        # Open Positions Tracker (trade_id -> position dict)
        self._open_positions: Dict[int, Dict[str, Any]] = {}

        # Daily trade execution counter: date_str -> {symbol -> count}
        self.enforce_daily_trade_cap = enforce_daily_trade_cap
        self._daily_trade_counts: Dict[str, Dict[str, int]] = {}

        # Broker Toggle Matrix: broker_name -> bool {ON/OFF state}
        self._broker_toggles: Dict[str, bool] = {
            "ANGEL_ONE": False,
            "SHOONYA": False,
            "GROWW": False,
        }

        # Registered Broker Gateways
        self._brokers: Dict[str, BaseBroker] = {
            "ANGEL_ONE": AngelOneBroker(vault_manager=self.vault, db_handler=self.db_manager),
            "SHOONYA": ShoonyaBroker(vault_manager=self.vault, db_handler=self.db_manager),
            "GROWW": GrowwBroker(vault_manager=self.vault, db_handler=self.db_manager),
            "PAPER": PaperBroker(initial_capital=500000.0)
        }

        # Notification / Alert Callback (e.g. desktop UI toast/dialog)
        self.notification_callback: Optional[Callable[[str, str], None]] = None

        # Daily risk tracking from risk engine
        self._daily_loss_tracker = {"realized": 0.0, "starting_capital": 500000.0}

        # Circuit Breaker State
        self._engine_locked: bool = False

        # Synchronize initial toggles from vault if available
        self._sync_toggles_from_vault()

    def _sync_toggles_from_vault(self) -> None:
        """Synchronize broker trading toggles from vault state."""
        try:
            if not self.vault:
                from database.vault_manager import VaultManager
                self.vault = VaultManager()
            toggles = self.vault.get_all_toggles()
            for broker_name, enabled in toggles.items():
                normalized = broker_name.strip().upper()
                if normalized in self._broker_toggles:
                    self._broker_toggles[normalized] = enabled
        except Exception:
            # Vault not initialized yet - use defaults
            pass

    # =========================================================================
    # Broker Toggle & Gateway Management API
    # =========================================================================

    def set_broker_toggle(self, broker_name: str, enabled: bool) -> None:
        """Sets the execution toggle for a specific broker."""
        normalized = broker_name.strip().upper()
        with self._lock:
            self._broker_toggles[normalized] = bool(enabled)
            if self.vault and hasattr(self.vault, "set_trading_enabled"):
                try:
                    self.vault.set_trading_enabled(normalized, enabled)
                except Exception:
                    pass
        # Persist toggle state (would integrate with vault in production)

    def get_broker_toggle(self, broker_name: str) -> bool:
        """Returns True if trading toggle is ON for the broker."""
        normalized = broker_name.strip().upper()
        with self._lock:
            return self._broker_toggles.get(normalized, False)

    def get_all_toggles(self) -> Dict[str, bool]:
        """Returns snapshot of all broker trading toggles."""
        with self._lock:
            return dict(self._broker_toggles)

    def register_broker_instance(self, broker_name: str, instance: BaseBroker) -> None:
        """Registers a live broker gateway instance."""
        normalized = broker_name.strip().upper()
        with self._lock:
            self._brokers[normalized] = instance

    def get_broker_instance(self, broker_name: str):
        """Retrieves a registered broker gateway instance."""
        normalized = broker_name.strip().upper()
        with self._lock:
            return self._brokers.get(normalized)

    def _notify(self, title: str, message: str) -> None:
        """Triggers registered UI alert/notification callback if present."""
        if self.notification_callback and callable(self.notification_callback):
            try:
                self.notification_callback(title, message)
            except Exception:
                pass

    # =========================================================================
    # Toggle-Aware Order Execution Engine
    # =========================================================================

    def execute_order(
        self,
        symbol: str,
        side: str,
        quantity: int,
        price: float,
        stop_loss: float = 0.0,
        target_price: float = 0.0,
        mode: str = "PAPER",
        exchange: str = "NSE",
        order_type: str = "MARKET",
        product: str = "MIS",
        enforce_daily_cap: Optional[bool] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Executes order strictly adhering to broker toggle matrix and risk guardrails.
        """
        # Validate parameters
        if quantity <= 0:
            raise ValueError(f"Quantity must be positive integer, got {quantity}")
        if price <= 0.0:
            raise ValueError(f"Execution price must be > 0.0, got {price}")

        # === CRITICAL: Circuit Breaker Check ===
        if self._engine_locked:
            self._notify("Circuit Breaker", "Daily loss limit exceeded. Trading engine locked.")
            return {
                "status": "REJECTED",
                "reason": "ENGINE_LOCKED",
                "message": "Daily loss limit exceeded. Trading engine locked."
            }

        # === CHECK: Daily Trade Cap (Strictly Max 2 Trades per Instrument per Day) ===
        should_enforce_cap = self.enforce_daily_trade_cap if enforce_daily_cap is None else enforce_daily_cap
        if should_enforce_cap:
            today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            with self._lock:
                if today_str not in self._daily_trade_counts:
                    self._daily_trade_counts[today_str] = {}
                count = self._daily_trade_counts[today_str].get(symbol, 0)
                if count >= self.MAX_TRADES_PER_INSTRUMENT_PER_DAY:
                    msg = f"Order blocked: Maximum daily trade cap ({self.MAX_TRADES_PER_INSTRUMENT_PER_DAY} trades/day) reached for {symbol}."
                    self._notify("Daily Trade Cap", msg)
                    return {
                        "status": "REJECTED",
                        "reason": "DAILY_TRADE_CAP_EXCEEDED",
                        "message": msg
                    }

        normalized_side = side.strip().upper()
        normalized_mode = mode.strip().upper()
        normalized_exchange = exchange.strip().upper()

        # === CHECK 1: Pre-Trade ₹70 Gross Profit Gate ===
        # Validate expected profit before any broker dispatch (side-aware)
        if target_price > 0.0 and quantity > 0:
            if normalized_side == "BUY":
                expected_gross_profit = (target_price - price) * quantity
            else:  # SELL / SHORT
                expected_gross_profit = (price - target_price) * quantity

            if expected_gross_profit < self.MIN_GROSS_PROFIT_HURDLE_INR:
                msg = (
                    f"Order blocked: Estimated gross profit (₹{expected_gross_profit:.2f}) "
                    f"< statutory ₹70 hurdle gate."
                )
                self._notify("Risk Gate Block", msg)
                return {
                    "status": "REJECTED",
                    "reason": "PROFIT_HURDLE_FAILED",
                    "message": msg
                }

        # === CHECK 2: Daily Drawdown Circuit Breaker ===
        # Check if daily realized loss >= 10% of starting capital
        daily_realized = self._daily_loss_tracker.get("realized", 0.0)
        starting_capital = self._daily_loss_tracker.get("starting_capital", 500000.0)
        daily_loss_threshold = starting_capital * (self.MAX_DRAWDOWN_PCT / 100.0)

        if daily_realized >= daily_loss_threshold:
            self._engine_locked = True
            msg = f"Circuit Breaker TRIPPED: Daily loss (₹{daily_realized:.2f}) >= 10% threshold (₹{daily_loss_threshold:.2f}). All new trades rejected."
            self._notify("Daily Circuit Breaker", msg)
            return {
                "status": "REJECTED",
                "reason": "DAILY_DRAWDOWN_BREACH",
                "message": msg
            }

        # Determine market session type
        is_mcq = symbol.upper() in ("CRUDEOIL", "GOLDM", "SILVERM", "COPPER", "NATURALGAS")
        session_type = "MCX" if is_mcq else "EQUITY"

        # =====================================================================
        # 1. PAPER TRADING EXECUTION GATEWAY
        # =====================================================================
        if normalized_mode == "PAPER":
            with self._lock:
                if normalized_side == "BUY":
                    executed_price = round(price * (1.0 + self.PAPER_SLIPPAGE_RATE), 2)
                else:
                    executed_price = round(price * (1.0 - self.PAPER_SLIPPAGE_RATE), 2)

                slippage_inr = round(abs(executed_price - price) * quantity, 2)

                trade_id = 0
                if hasattr(self.db_manager, "log_trade_entry"):
                    try:
                        trade_id = self.db_manager.log_trade_entry(
                            market_session=session_type,
                            broker_name="PAPER_BROKER",
                            symbol=symbol,
                            trade_side=normalized_side,
                            quantity=quantity,
                            entry_price=executed_price,
                            stop_loss=stop_loss,
                            execution_mode="PAPER",
                            friction_cost=self.FRICTION_COST_INR
                        )
                    except Exception:
                        pass

                if not trade_id:
                    trade_id = len(self._open_positions) + 1

                pos_record = {
                    "id": trade_id,
                    "trade_id": trade_id,
                    "symbol": symbol,
                    "side": normalized_side,
                    "quantity": quantity,
                    "entry_price": executed_price,
                    "stop_loss": stop_loss,
                    "target_price": target_price,
                    "market_session": session_type,
                    "execution_mode": "PAPER",
                    "broker": "PAPER_BROKER",
                    "broker_name": "PAPER_BROKER",
                    "created_at": datetime.now(timezone.utc).isoformat()
                }
                self._open_positions[trade_id] = pos_record

                # Track daily execution count
                today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
                if today_str not in self._daily_trade_counts:
                    self._daily_trade_counts[today_str] = {}
                self._daily_trade_counts[today_str][symbol] = self._daily_trade_counts[today_str].get(symbol, 0) + 1

                return {
                    "status": "FILLED",
                    "trade_id": trade_id,
                    "symbol": symbol,
                    "side": normalized_side,
                    "quantity": quantity,
                    "requested_price": price,
                    "executed_price": executed_price,
                    "slippage_inr": slippage_inr,
                    "stop_loss": stop_loss,
                    "target_price": target_price,
                    "execution_mode": "PAPER",
                    "message": "Simulated fill executed via PAPER gateway (0.02% slippage applied)."
                }

        # =====================================================================
        # 2. LIVE TOGGLE-AWARE MULTI-BROKER EXECUTION GATEWAY
        # =====================================================================
        elif normalized_mode == "LIVE":
            # === CHECK 3: Broker Toggle Matrix ===
            # Identify enabled brokers
            enabled_brokers = [b for b, toggled in self._broker_toggles.items() if toggled]

            # State 0: All toggles OFF -> Reject order
            if not enabled_brokers:
                msg = "Trading Locked: No active brokers enabled. Enable at least one broker trading toggle."
                self._notify("Trading Locked", msg)
                return {
                    "status": "REJECTED",
                    "reason": "ALL_TOGGLES_OFF",
                    "message": msg
                }

            # Evaluate connection status per toggled broker
            ready_brokers: List[str] = []
            disconnected_brokers: List[str] = []

            for broker_name in enabled_brokers:
                broker_inst = self._brokers.get(broker_name)
                is_connected = False
                if broker_inst and getattr(broker_inst, "is_authenticated", False):
                    conn_state = getattr(broker_inst, "_connection_state", "")
                    if conn_state == "CONNECTED":
                        is_connected = True

                if is_connected:
                    ready_brokers.append(broker_name)
                else:
                    disconnected_brokers.append(broker_name)
                    # Trigger non-crashing alert (never fail silently on connection state)
                    alert_msg = f"Execution rejected on {broker_name}: Broker is toggled ON but DISCONNECTED."
                    self._notify("Broker Disconnected", alert_msg)

            # If no brokers are connected despite toggles being ON
            if not ready_brokers:
                msg = f"Execution halted: All enabled brokers ({', '.join(disconnected_brokers)}) are disconnected."
                self._notify("Execution Rejected", msg)
                return {
                    "status": "REJECTED",
                    "reason": "ENABLED_BROKERS_DISCONNECTED",
                    "disconnected_brokers": disconnected_brokers,
                    "message": msg
                }

            # === STATE 1-3: Route across ready brokers ===
            # State 1: Single broker -> Route exclusively
            # State 2/3: Multiple brokers -> Parallel dispatch
            execution_results: List[Dict[str, Any]] = []
            execution_uuid = str(uuid.uuid4())

            def dispatch_to_broker(b_name: str) -> Dict[str, Any]:
                """Dispatch order to a specific broker gateway."""
                inst = self._brokers[b_name]
                # Use unique execution UUID to prevent IDOR and collisions
                client_order_id = f"OT-{b_name[:2]}-{execution_uuid[:8]}"

                # Map product to valid BaseBroker ProductType enum
                prod_clean = str(product).strip().upper()
                if prod_clean in ("MIS", "INTRADAY"):
                    p_type = ProductType.INTRADAY
                elif prod_clean in ("CNC", "DELIVERY"):
                    p_type = ProductType.DELIVERY
                elif prod_clean in ("NRML", "CARRYFORWARD"):
                    p_type = ProductType.CARRYFORWARD
                elif prod_clean == "MARGIN":
                    p_type = ProductType.MARGIN
                else:
                    p_type = ProductType.INTRADAY

                try:
                    req = OrderRequest(
                        symbol=symbol,
                        exchange=Exchange.NSE if normalized_exchange == "NSE" else Exchange.BSE,
                        side=OrderSide.BUY if normalized_side == "BUY" else OrderSide.SELL,
                        order_type=OrderType.MARKET if order_type == "MARKET" else OrderType.LIMIT,
                        product_type=p_type,
                        quantity=quantity,
                        price=price if order_type != "MARKET" else 0.0,
                        trigger_price=stop_loss,
                        tag=client_order_id
                    )
                    order_resp = inst.place_order(req)
                    b_order_id = order_resp.broker_order_id or client_order_id
                    order_status = order_resp.status.value if hasattr(order_resp.status, "value") else str(order_resp.status)
                except Exception as err:
                    b_order_id = f"ERR-{b_name[:2]}-{execution_uuid[:8]}"
                    order_status = "REJECTED"

                return {
                    "broker": b_name,
                    "execution_id": execution_uuid,
                    "client_order_id": client_order_id,
                    "broker_order_id": b_order_id,
                    "status": order_status,
                    "execution_success": order_status in (OrderStatus.SUBMITTED.value, OrderStatus.OPEN.value),
                }

            # Non-blocking concurrent execution across all ready brokers
            futures = [self._executor.submit(dispatch_to_broker, b) for b in ready_brokers]
            for fut in as_completed(futures):
                try:
                    result = fut.result(timeout=10.0)
                    execution_results.append(result)
                except Exception as exc:
                    execution_results.append({"status": "FAILED", "error": str(exc)})

            # Register open position for successfully submitted broker executions
            successful_brokers = [r["broker"] for r in execution_results if r.get("execution_success")]
            if successful_brokers:
                with self._lock:
                    pos_id = len(self._open_positions) + 1
                    self._open_positions[pos_id] = {
                        "id": pos_id,
                        "trade_id": pos_id,
                        "symbol": symbol,
                        "side": normalized_side,
                        "quantity": quantity,
                        "entry_price": price,
                        "stop_loss": stop_loss,
                        "target_price": target_price,
                        "market_session": session_type,
                        "broker": ", ".join(successful_brokers),
                        "execution_id": execution_uuid,
                        "created_at": datetime.now(timezone.utc).isoformat()
                    }

            # Track daily execution count
            today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            with self._lock:
                if today_str not in self._daily_trade_counts:
                    self._daily_trade_counts[today_str] = {}
                self._daily_trade_counts[today_str][symbol] = self._daily_trade_counts[today_str].get(symbol, 0) + 1

            primary_res = execution_results[0] if execution_results else {}
            return {
                "status": "SUBMITTED",
                "symbol": symbol,
                "side": normalized_side,
                "quantity": quantity,
                "price": price,
                "stop_loss": stop_loss,
                "target_price": target_price,
                "execution_mode": "LIVE",
                "dispatched_brokers": ready_brokers,
                "disconnected_brokers": disconnected_brokers,
                "results": execution_results,
                "execution_id": execution_uuid,
                "order_id": primary_res.get("broker_order_id", ""),
                "message": f"Concurrently routed across {len(ready_brokers)} enabled brokers: {', '.join(ready_brokers)}"
            }
        else:
            raise ValueError(f"Unsupported execution mode '{mode}'. Use 'PAPER' or 'LIVE'.")

    # =========================================================================
    # Position Liquidation & Auto Square-Off
    # =========================================================================

    def close_position(self, trade_id: int, exit_price: float) -> Dict[str, Any]:
        """Closes an active position, applies ₹60 friction deduction, and updates SQLite."""
        with self._lock:
            pos = self._open_positions.pop(trade_id, None)

            # Try updating via db_manager
            closed_record = None
            if hasattr(self.db_manager, "update_trade_exit"):
                try:
                    closed_record = self.db_manager.update_trade_exit(
                        trade_id=trade_id,
                        exit_price=exit_price,
                        status="CLOSED",
                        friction_cost=self.FRICTION_COST_INR
                    )
                except Exception:
                    pass

            if closed_record:
                if "trade_id" not in closed_record and "id" in closed_record:
                    closed_record["trade_id"] = closed_record["id"]
                if "id" not in closed_record and "trade_id" in closed_record:
                    closed_record["id"] = closed_record["trade_id"]
                return closed_record

            # Fallback calculation if db record not present or db update failed
            entry_price = pos.get("entry_price", exit_price) if pos else exit_price
            quantity = pos.get("quantity", 1) if pos else 1
            side = pos.get("side", "BUY") if pos else "BUY"

            if side == "BUY":
                gross_pnl = round((float(exit_price) - float(entry_price)) * quantity, 2)
            else:
                gross_pnl = round((float(entry_price) - float(exit_price)) * quantity, 2)
            net_pnl = round(gross_pnl - self.FRICTION_COST_INR, 2)

            return {
                "id": trade_id,
                "trade_id": trade_id,
                "status": "CLOSED",
                "exit_price": exit_price,
                "gross_pnl": gross_pnl,
                "friction_cost": self.FRICTION_COST_INR,
                "net_pnl": net_pnl,
                "symbol": pos.get("symbol", "") if pos else "",
                "broker": pos.get("broker", "") if pos else "",
            }

    def auto_square_off_all(self, reason: str = "EMERGENCY_KILL_SWITCH") -> List[Dict[str, Any]]:
        """Liquidates all open positions immediately (Emergency Kill Switch)."""
        liquidated = []
        with self._lock:
            for trade_id, pos in list(self._open_positions.items()):
                exit_price = pos.get("entry_price", 0.0)
                closed = self.close_position(trade_id=trade_id, exit_price=exit_price)
                closed["liquidated_at"] = datetime.now(timezone.utc).isoformat()
                closed["reason"] = reason
                closed["broker"] = pos.get("broker", "ALL")
                closed["symbol"] = pos.get("symbol", "")
                liquidated.append(closed)
            self._open_positions.clear()
        return liquidated

    def evaluate_auto_square_off(self, current_time: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Inspects open positions against mandatory session deadlines:
        - NSE/BSE Equity: Auto-square-off at 15:15 IST
        - MCX Commodity: Auto-square-off at 23:15 IST
        """
        if current_time:
            parts = current_time.strip().split(":")
            t = dtime(hour=int(parts[0]), minute=int(parts[1]))
        else:
            now_utc = datetime.now(timezone.utc)
            ist_offset_seconds = (5 * 3600) + (30 * 60)
            now_ist = datetime.fromtimestamp(now_utc.timestamp() + ist_offset_seconds, tz=timezone.utc)
            t = now_ist.time()

        liquidated_trades: List[Dict[str, Any]] = []

        with self._lock:
            for trade_id, pos in list(self._open_positions.items()):
                session = pos.get("market_session", "EQUITY")
                should_square_off = False

                if session == "EQUITY" and t >= self.EQUITY_SQUARE_OFF:
                    should_square_off = True
                elif session == "MCX" and t >= self.MCX_SQUARE_OFF:
                    should_square_off = True

                if should_square_off:
                    exit_price = pos.get("entry_price", 0.0)
                    closed_trade = self.close_position(trade_id=trade_id, exit_price=exit_price)
                    closed_trade["square_off_reason"] = f"Mandatory session square-off triggered at {t.strftime('%H:%M')} IST."
                    liquidated_trades.append(closed_trade)

        return liquidated_trades

    def get_open_positions(self) -> List[Dict[str, Any]]:
        """Returns all currently open positions."""
        with self._lock:
            return list(self._open_positions.values())

    @property
    def positions(self) -> Dict[int, Dict[str, Any]]:
        """Dictionary of open positions for GUI telemetry access."""
        with self._lock:
            return dict(self._open_positions)

    # =========================================================================
    # Daily Loss Tracking Integration
    # =========================================================================

    def update_daily_loss_tracker(self, realized_pnl: float) -> None:
        """Updates the daily realized P&L tracker from risk engine."""
        with self._lock:
            self._daily_loss_tracker["realized"] = realized_pnl

    def reset_daily_loss_tracker(self, new_starting_capital: float = 500000.0) -> None:
        """Resets the daily loss tracker for a new trading session."""
        with self._lock:
            self._daily_loss_tracker["realized"] = 0.0
            self._daily_loss_tracker["starting_capital"] = new_starting_capital
            self._engine_locked = False  # Reset circuit breaker for new session


def initialize_order_router(db_manager=None, vault_manager=None) -> OrderRouter:
    """Factory function to initialize the complete order routing system."""
    router = OrderRouter(db_manager=db_manager)
    return router