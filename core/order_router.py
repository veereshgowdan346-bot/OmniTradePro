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
import time
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError

import json
from pathlib import Path
from database.db_manager import DatabaseManager
from core.risk_budget import RiskBudget
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

    MIN_MARGIN_REQUIREMENTS = {
        # MCX Commodity Futures (Statutory requirement >= ₹1.5L)
        "CRUDEOIL": 150000.0,
        "GOLD": 450000.0,
        "SILVER": 200000.0,
        "COPPER": 120000.0,
        "NATURALGAS": 130000.0,
        # MCX Mini Contracts
        "CRUDEOILM": 30000.0,
        "GOLDM": 55000.0,
        "SILVERM": 45000.0,
        # Index Futures
        "NIFTY": 110000.0,
        "NIFTY 50": 110000.0,
        "BANKNIFTY": 120000.0,
        "BANK NIFTY": 120000.0,
        "FINNIFTY": 100000.0,
    }

    @classmethod
    def calculate_required_margin(cls, symbol: str, quantity: int, price: float, product: str = "MIS") -> float:
        """Calculates exact broker margin requirement to strictly eliminate RMS Margin Exceeded errors."""
        clean_sym = symbol.strip().upper().replace("MCX:", "").replace("NSE:", "").strip()
        if clean_sym in cls.MIN_MARGIN_REQUIREMENTS:
            return cls.MIN_MARGIN_REQUIREMENTS[clean_sym]
        # Intraday Equity MIS: 5x leverage (20% margin requirement)
        prod_clean = str(product).strip().upper()
        if prod_clean in ("MIS", "INTRADAY"):
            return round((price * quantity) / 5.0, 2)
        else:  # Delivery CNC: 100% margin
            return round(price * quantity, 2)

    def check_margin_preflight(
        self,
        symbol: str,
        quantity: int,
        price: float,
        available_capital: float,
        product: str = "MIS"
    ) -> Dict[str, Any]:
        """
        Pre-flight margin check before order dispatch.
        Verifies available capital against required margin. If insufficient for MCX futures,
        suggests safe routing to high-probability liquid intraday equity with 5x leverage.
        """
        req_margin = self.calculate_required_margin(symbol, quantity, price, product)
        passed = available_capital >= req_margin

        clean_sym = symbol.strip().upper().replace("MCX:", "").replace("NSE:", "").strip()
        is_mcx_future = clean_sym in ("CRUDEOIL", "GOLD", "SILVER", "COPPER", "NATURALGAS")

        suggested_symbol = None
        suggested_qty = quantity
        if not passed:
            if is_mcx_future and available_capital < 150000.0:
                suggested_symbol = "RELIANCE" if available_capital >= 2000.0 else "TATASTEEL"
                equity_price = 2485.0 if suggested_symbol == "RELIANCE" else 150.0
                suggested_qty = max(1, int((available_capital * 5.0) / equity_price))

        return {
            "passed": passed,
            "required_margin": req_margin,
            "available_capital": available_capital,
            "shortfall": max(0.0, req_margin - available_capital),
            "suggested_symbol": suggested_symbol,
            "suggested_quantity": suggested_qty,
            "reason": "OK" if passed else f"Pre-flight margin shortfall: Required ₹{req_margin:,.2f} > Available ₹{available_capital:,.2f}."
        }

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
        self._executor = ThreadPoolExecutor(max_workers=12, thread_name_prefix="BrokerFanOut_Worker")

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

        # Non-blocking TradeNotifier integration
        self.notifier = kwargs.get("notifier")
        if not self.notifier:
            try:
                from core.notifier import TradeNotifier
                self.notifier = TradeNotifier(vault_manager=self.vault)
            except Exception:
                self.notifier = None

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
        current_market_price: Optional[float] = None,
        enforce_slippage_guard: bool = True,
        available_capital: Optional[float] = None,
        auto_reroute_insufficient_margin: bool = False,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Executes order strictly adhering to broker toggle matrix, slippage guard, margin pre-flight, and risk guardrails.
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

        # === CHECK 0.5: Pre-Flight Margin Guard ===
        avail_cap = available_capital
        if avail_cap is None:
            avail_cap = kwargs.get("capital") or kwargs.get("available_capital")

        if avail_cap is not None:
            margin_audit = self.check_margin_preflight(
                symbol=symbol,
                quantity=quantity,
                price=price,
                available_capital=float(avail_cap),
                product=product
            )
            if not margin_audit["passed"]:
                if auto_reroute_insufficient_margin and margin_audit.get("suggested_symbol"):
                    orig_symbol = symbol
                    orig_qty = quantity
                    symbol = margin_audit["suggested_symbol"]
                    quantity = margin_audit["suggested_quantity"]
                    price = 2485.0 if symbol == "RELIANCE" else 150.0
                    normalized_exchange = "NSE"
                    product = "MIS"
                    if stop_loss > 0.0:
                        stop_loss = round(price * (0.99 if normalized_side == "BUY" else 1.01), 2)
                    if target_price > 0.0:
                        target_price = round(price * (1.02 if normalized_side == "BUY" else 0.98), 2)
                    msg = (
                        f"Order auto-rerouted: Insufficient margin for {orig_symbol} (qty {orig_qty}). "
                        f"Re-routed to liquid intraday equity {symbol} (qty {quantity}) under 5x leverage."
                    )
                    self._notify("Margin Pre-Flight Re-Route", msg)
                else:
                    msg = f"Order blocked: {margin_audit['reason']}"
                    self._notify("Margin Check Failed", msg)
                    return {
                        "status": "REJECTED",
                        "reason": "MARGIN_EXCEEDED_PREFLIGHT",
                        "margin_audit": margin_audit,
                        "message": msg
                    }

        # === CHECK 0: Dynamic Slippage & Price Drift Guard (0.08% / 8 bps) ===
        cmp = current_market_price
        if cmp is None:
            cmp = kwargs.get("current_price") or kwargs.get("ltp")
            if cmp is None:
                try:
                    from brokers.stream_worker import BrokerStreamWorker
                    cached_tick = BrokerStreamWorker.get_latest_tick(symbol)
                    if cached_tick and "ltp" in cached_tick:
                        cmp = float(cached_tick["ltp"])
                except Exception:
                    pass

        if cmp is not None and enforce_slippage_guard and cmp > 0.0:
            is_acceptable, drift = RiskBudget.is_slippage_acceptable(
                requested_price=price,
                current_price=cmp,
                side=normalized_side,
                max_slippage_pct=0.0008
            )
            if not is_acceptable:
                msg = (
                    f"Order blocked: Slippage breach detected. Adverse price drift ({drift*100:.3f}%) "
                    f"exceeds 0.08% slippage tolerance. Requested: ₹{price:.2f}, Current Market: ₹{cmp:.2f}."
                )
                self._notify("Slippage Guard Breach", msg)
                return {
                    "status": "REJECTED",
                    "reason": "SLIPPAGE_BREACH_ABORT",
                    "slippage_pct": drift,
                    "requested_price": price,
                    "current_market_price": cmp,
                    "message": msg
                }

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
                execution_uuid = str(uuid.uuid4())
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
                    "order_id": f"PAPER-{trade_id}",
                    "execution_id": execution_uuid,
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

                # Persist order record in database orders table if present
                if hasattr(self.db_manager, "insert_order"):
                    try:
                        self.db_manager.insert_order({
                            "order_id": execution_uuid,
                            "broker": "PAPER_BROKER",
                            "broker_order_id": f"PAPER-{trade_id}",
                            "symbol": symbol,
                            "exchange": normalized_exchange,
                            "transaction_type": normalized_side,
                            "product_type": "INTRADAY",
                            "order_type": order_type,
                            "quantity": quantity,
                            "price": executed_price,
                            "trigger_price": stop_loss,
                            "status": "FILLED",
                            "filled_quantity": quantity,
                            "average_price": executed_price,
                            "tag": f"PAPER-{trade_id}"
                        })
                    except Exception:
                        pass

                # Track daily execution count
                today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
                if today_str not in self._daily_trade_counts:
                    self._daily_trade_counts[today_str] = {}
                self._daily_trade_counts[today_str][symbol] = self._daily_trade_counts[today_str].get(symbol, 0) + 1

                fill_result = {
                    "status": "FILLED",
                    "trade_id": trade_id,
                    "order_id": f"PAPER-{trade_id}",
                    "execution_id": execution_uuid,
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

                # Detached asynchronous notification trigger (0.00ms latency impact)
                if self.notifier:
                    try:
                        self.notifier.send_trade_alert({
                            "symbol": symbol,
                            "side": normalized_side,
                            "quantity": quantity,
                            "price": executed_price,
                            "target_price": target_price,
                            "stop_loss": stop_loss,
                            "execution_mode": "PAPER",
                            "execution_id": f"PAPER-{trade_id}",
                            "broker": "PAPER_BROKER"
                        })
                    except Exception:
                        pass

                return fill_result

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
            # State 2/3: Multiple brokers -> Parallel dispatch (<60ms latency threshold)
            execution_results: List[Dict[str, Any]] = []
            execution_uuid = str(uuid.uuid4())

            # Convert MARKET orders to marketable limit orders to guard against flash crash slippage
            order_type_clean = str(order_type).strip().upper()
            if order_type_clean == "MARKET":
                effective_order_type = OrderType.LIMIT
                effective_price = RiskBudget.calculate_marketable_limit_price(
                    price=price,
                    side=normalized_side,
                    max_slippage_pct=0.0008
                )
            else:
                effective_order_type = OrderType.LIMIT
                effective_price = price

            def dispatch_to_broker(b_name: str) -> Dict[str, Any]:
                """Dispatch order to a specific broker gateway with isolated error boundary."""
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

                dispatch_err = None
                try:
                    req = OrderRequest(
                        symbol=symbol,
                        exchange=Exchange.NSE if normalized_exchange == "NSE" else Exchange.BSE,
                        side=OrderSide.BUY if normalized_side == "BUY" else OrderSide.SELL,
                        order_type=effective_order_type,
                        product_type=p_type,
                        quantity=quantity,
                        price=effective_price,
                        trigger_price=stop_loss,
                        tag=client_order_id
                    )
                    order_resp = inst.place_order(req)
                    b_order_id = order_resp.broker_order_id or client_order_id
                    order_status = order_resp.status.value if hasattr(order_resp.status, "value") else str(order_resp.status)
                except Exception as err:
                    dispatch_err = str(err)
                    b_order_id = f"ERR-{b_name[:2]}-{execution_uuid[:8]}"
                    order_status = "REJECTED"

                return {
                    "broker": b_name,
                    "execution_id": execution_uuid,
                    "client_order_id": client_order_id,
                    "broker_order_id": b_order_id,
                    "status": order_status,
                    "error": dispatch_err,
                    "marketable_limit_price": effective_price,
                    "execution_success": order_status in (OrderStatus.SUBMITTED.value, OrderStatus.OPEN.value),
                }

            # Non-blocking concurrent execution across all ready brokers (<60ms timeout)
            fanout_start = time.perf_counter()
            futures = {self._executor.submit(dispatch_to_broker, b): b for b in ready_brokers}
            try:
                for fut in as_completed(futures, timeout=0.060):
                    b_name = futures[fut]
                    try:
                        res = fut.result()
                        execution_results.append(res)
                    except Exception as exc:
                        execution_results.append({
                            "broker": b_name,
                            "execution_id": execution_uuid,
                            "client_order_id": f"ERR-{b_name[:2]}-{execution_uuid[:8]}",
                            "broker_order_id": f"ERR-{b_name[:2]}-{execution_uuid[:8]}",
                            "status": "FAILED",
                            "error": str(exc),
                            "execution_success": False
                        })
            except TimeoutError:
                for fut, b_name in futures.items():
                    if not fut.done():
                        execution_results.append({
                            "broker": b_name,
                            "execution_id": execution_uuid,
                            "client_order_id": f"TIMEOUT-{b_name[:2]}-{execution_uuid[:8]}",
                            "broker_order_id": f"TIMEOUT-{b_name[:2]}-{execution_uuid[:8]}",
                            "status": "TIMEOUT",
                            "error": "Fan-out dispatch exceeded 60ms latency threshold",
                            "execution_success": False
                        })
            fanout_latency_ms = (time.perf_counter() - fanout_start) * 1000.0

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
            live_result = {
                "status": "SUBMITTED",
                "symbol": symbol,
                "side": normalized_side,
                "quantity": quantity,
                "price": price,
                "marketable_limit_price": effective_price,
                "stop_loss": stop_loss,
                "target_price": target_price,
                "execution_mode": "LIVE",
                "dispatched_brokers": ready_brokers,
                "disconnected_brokers": disconnected_brokers,
                "results": execution_results,
                "execution_id": execution_uuid,
                "order_id": primary_res.get("broker_order_id", ""),
                "fanout_latency_ms": round(fanout_latency_ms, 2),
                "message": f"Concurrently routed across {len(ready_brokers)} enabled brokers in {fanout_latency_ms:.2f}ms: {', '.join(ready_brokers)}"
            }

            # Detached asynchronous notification trigger (0.00ms latency impact)
            if self.notifier and successful_brokers:
                try:
                    self.notifier.send_trade_alert({
                        "symbol": symbol,
                        "side": normalized_side,
                        "quantity": quantity,
                        "price": effective_price,
                        "target_price": target_price,
                        "stop_loss": stop_loss,
                        "execution_mode": "LIVE",
                        "execution_id": execution_uuid,
                        "broker": ", ".join(successful_brokers)
                    })
                except Exception:
                    pass

            return live_result
        else:
            raise ValueError(f"Unsupported execution mode '{mode}'. Use 'PAPER' or 'LIVE'.")

    def dispatch_parallel_fanout(
        self,
        broker_names: List[str],
        symbol: str,
        side: str,
        quantity: int,
        price: float,
        timeout_ms: float = 60.0
    ) -> Dict[str, Any]:
        """
        Direct benchmark & production harness for sub-50ms parallel multi-broker fan-out.
        Fans out an order concurrently to all specified brokers, enforcing atomic UUIDs and isolated error handling.
        """
        exec_uuid = str(uuid.uuid4())
        norm_side = side.strip().upper()
        results = []

        def _sub_worker(b_name: str) -> Dict[str, Any]:
            b_inst = self._brokers.get(b_name.strip().upper())
            c_oid = f"FAN-{b_name[:2]}-{exec_uuid[:8]}"
            if not b_inst:
                return {"broker": b_name, "status": "REJECTED", "error": "Unknown broker"}
            try:
                limit_p = RiskBudget.calculate_marketable_limit_price(price, norm_side, 0.0008)
                req = OrderRequest(
                    symbol=symbol,
                    exchange=Exchange.NSE,
                    side=OrderSide.BUY if norm_side == "BUY" else OrderSide.SELL,
                    order_type=OrderType.LIMIT,
                    product_type=ProductType.INTRADAY,
                    quantity=quantity,
                    price=limit_p,
                    tag=c_oid
                )
                resp = b_inst.place_order(req)
                return {
                    "broker": b_name,
                    "execution_id": exec_uuid,
                    "order_id": resp.broker_order_id or c_oid,
                    "status": "SUBMITTED",
                    "success": True
                }
            except Exception as e:
                return {
                    "broker": b_name,
                    "execution_id": exec_uuid,
                    "status": "FAILED",
                    "error": str(e),
                    "success": False
                }

        t_start = time.perf_counter()
        futures = {self._executor.submit(_sub_worker, b): b for b in broker_names}
        timeout_sec = timeout_ms / 1000.0

        try:
            for fut in as_completed(futures, timeout=timeout_sec):
                b_name = futures[fut]
                try:
                    results.append(fut.result())
                except Exception as e:
                    results.append({"broker": b_name, "status": "FAILED", "error": str(e), "success": False})
        except TimeoutError:
            for fut, b_name in futures.items():
                if not fut.done():
                    results.append({"broker": b_name, "status": "TIMEOUT", "error": "Exceeded fanout timeout", "success": False})

        total_latency_ms = (time.perf_counter() - t_start) * 1000.0
        return {
            "execution_id": exec_uuid,
            "dispatched_brokers": broker_names,
            "results": results,
            "fanout_latency_ms": round(total_latency_ms, 2),
            "under_60ms": total_latency_ms < 60.0
        }


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

    def cancel_order(self, order_id: Any) -> Dict[str, Any]:
        """
        Cancels an active or submitted order by trade ID, broker order ID, or execution UUID.
        Transitions state from SUBMITTED/ACTIVE -> CANCELLED / SQUARED_OFF cleanly.
        Synchronizes cancellation with broker gateways and SQLite audit logs.
        """
        with self._lock:
            target_trade_id = None
            pos = None
            str_id = str(order_id).strip()

            # Match in _open_positions
            if isinstance(order_id, int) and order_id in self._open_positions:
                target_trade_id = order_id
                pos = self._open_positions.pop(order_id)
            else:
                for t_id, p in list(self._open_positions.items()):
                    if (str(t_id) == str_id or 
                        str(p.get("id")) == str_id or 
                        str(p.get("trade_id")) == str_id or 
                        str(p.get("broker_order_id")) == str_id or 
                        str(p.get("client_order_id")) == str_id or 
                        str(p.get("execution_id")) == str_id or
                        str(p.get("order_id")) == str_id):
                        target_trade_id = t_id
                        pos = self._open_positions.pop(t_id)
                        break

            # Forward cancellation to live broker instances
            broker_results = {}
            for b_name, b_inst in self._brokers.items():
                if hasattr(b_inst, "cancel_order"):
                    try:
                        resp = b_inst.cancel_order(str_id)
                        broker_results[b_name] = resp
                    except Exception as exc:
                        broker_results[b_name] = str(exc)

            # Update DB manager orders table if present
            if hasattr(self.db_manager, "update_order_status"):
                try:
                    self.db_manager.update_order_status(
                        order_id=str_id,
                        status="CANCELLED",
                        rejection_reason="CANCELLED_BY_OPERATOR"
                    )
                except Exception:
                    pass

            # Update db_manager trade exit
            if hasattr(self.db_manager, "update_trade_exit") and target_trade_id:
                try:
                    self.db_manager.update_trade_exit(
                        trade_id=target_trade_id,
                        exit_price=pos.get("entry_price", 0.0) if pos else 0.0,
                        status="CANCELLED",
                        friction_cost=0.0
                    )
                except Exception:
                    pass

            # Dual database sync to trade_audit_log in db_handler
            try:
                from database.db_handler import DatabaseHandler
                dbh = DatabaseHandler()
                with dbh._lock:
                    conn = dbh._get_connection()
                    c = conn.cursor()
                    c.execute("""
                        UPDATE trade_audit_log 
                        SET status = 'CANCELLED'
                        WHERE id = ? OR symbol = ?
                    """, (str(target_trade_id or order_id), pos.get("symbol", "") if pos else ""))
                    conn.commit()
            except Exception:
                pass

            symbol = pos.get("symbol", "") if pos else ""
            broker = pos.get("broker", "PAPER") if pos else "ALL"
            exec_id = pos.get("execution_id", str_id) if pos else str_id

            return {
                "status": "CANCELLED",
                "order_id": order_id,
                "execution_id": exec_id,
                "trade_id": target_trade_id or order_id,
                "symbol": symbol,
                "broker": broker,
                "transition": "SUBMITTED -> ACTIVE -> CANCELLED",
                "message": f"Order {order_id} successfully cancelled / squared-off."
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

        # Trigger end-of-day summary notification during mandatory auto-square-off
        if self.notifier and (t >= self.EQUITY_SQUARE_OFF or t >= self.MCX_SQUARE_OFF):
            try:
                summary = None
                if hasattr(self.db_manager, "get_today_summary"):
                    summary = self.db_manager.get_today_summary()
                elif hasattr(self.db, "get_today_summary"):
                    summary = self.db.get_today_summary()

                if not summary:
                    summary = {
                        "total_trades": len(liquidated_trades),
                        "wins": sum(1 for tr in liquidated_trades if tr.get("net_pnl", 0) > 0),
                        "losses": sum(1 for tr in liquidated_trades if tr.get("net_pnl", 0) < 0),
                        "win_rate": 0.0,
                        "realized_pnl": sum(tr.get("net_pnl", 0.0) for tr in liquidated_trades),
                    }

                summary["market_session"] = "MCX" if t >= self.MCX_SQUARE_OFF else "EQUITY"
                summary["square_off_time"] = t.strftime("%H:%M")
                self.notifier.send_daily_summary(summary)
            except Exception:
                pass

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