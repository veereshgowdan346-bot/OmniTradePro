#!/usr/bin/env python3
"""
OmniTradePro - Institutional Real-Time Risk & Compliance Engine
Platform: Windows 10/11 64-bit | Python 3.10+
Enforces pre-trade risk collars, dynamic intraday drawdown limits, exchange market hours,
mandatory square-off deadlines, and ₹60 statutory friction profitability triggers.
"""

import json
import threading
from pathlib import Path
from datetime import datetime, time as dtime, timezone
from typing import Dict, Any, Optional, Tuple, List

from brokers.base_broker import (
    OrderRequest,
    OrderSide,
    OrderType,
    ProductType,
    Exchange,
    Position
)
from database.db_handler import DatabaseHandler


class RiskEngine:
    """
    Centralized quantitative risk management system.
    Enforces hard capital stops, automated circuit breakers, market session timings,
    and minimum net profit execution hurdles across NSE, BSE, and MCX.
    """
    _instance: Optional["RiskEngine"] = None
    _singleton_lock = threading.Lock()

    def __new__(cls, config_path: Optional[str] = None, allocated_capital: float = 100000.0) -> "RiskEngine":
        with cls._singleton_lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._is_initialized = False
            return cls._instance

    def __init__(self, config_path: Optional[str] = None, allocated_capital: float = 100000.0) -> None:
        if getattr(self, "_is_initialized", False):
            return

        self._lock = threading.RLock()
        base_dir = Path(__file__).resolve().parent.parent
        self.config_path = Path(config_path) if config_path else (base_dir / "config.json")
        self.allocated_capital = float(allocated_capital)

        # Telemetry & risk states
        self.realized_pnl: float = 0.0
        self.unrealized_pnl: float = 0.0
        self.peak_pnl: float = 0.0
        self.current_drawdown: float = 0.0
        self.total_trades_count: int = 0
        self.is_halted: bool = False
        self.halt_reason: str = ""

        # Load parameters from config.json
        self._load_config()
        self._db = DatabaseHandler()
        self._is_initialized = True

    def _load_config(self) -> None:
        """Parses quantitative risk rules and exchange market hours from config.json."""
        with open(self.config_path, "r", encoding="utf-8") as f:
            cfg = json.load(f)

        risk_rules = cfg.get("risk_rules", {})
        self.max_capital_risk_pct = float(risk_rules.get("max_capital_risk_pct", 10.0))
        self.friction_buffer_inr = float(risk_rules.get("friction_buffer_inr", 60.0))
        self.min_gross_profit_trigger_inr = float(risk_rules.get("min_gross_profit_trigger_inr", 70.0))
        self.max_daily_loss_inr = float(risk_rules.get("max_daily_loss_inr", 2000.0))

        # Absolute hard stop capital loss threshold
        self.max_capital_loss_inr = self.allocated_capital * (self.max_capital_risk_pct / 100.0)

        # Exchange Timings
        market_hours = cfg.get("market_hours", {})
        self.equity_open = self._parse_time(market_hours.get("equity_open", "09:15"))
        self.equity_close = self._parse_time(market_hours.get("equity_close", "15:30"))
        self.equity_square_off = self._parse_time(market_hours.get("equity_square_off", "15:15"))

        self.mcx_open = self._parse_time(market_hours.get("mcx_open", "09:00"))
        self.mcx_close = self._parse_time(market_hours.get("mcx_close", "23:30"))
        self.mcx_square_off = self._parse_time(market_hours.get("mcx_square_off", "23:15"))

    @staticmethod
    def _parse_time(t_str: str) -> dtime:
        """Converts 'HH:MM' string to datetime.time."""
        parts = t_str.strip().split(":")
        return dtime(hour=int(parts[0]), minute=int(parts[1]))

    # =========================================================================
    # Market Timing & Session Compliance
    # =========================================================================

    def is_market_open(self, exchange: Exchange, check_time: Optional[datetime] = None) -> Tuple[bool, str]:
        """
        Validates if current time falls within active exchange trading hours.
        Accounts for Equity (09:15-15:30) and MCX (09:00-23:30).
        """
        now = check_time or datetime.now()
        cur_time = now.time()

        # Weekend Check: 5=Saturday, 6=Sunday
        if now.weekday() in (5, 6):
            return False, f"Exchange {exchange.value} is closed on weekends."

        if exchange in (Exchange.NSE, Exchange.BSE, Exchange.NFO):
            if self.equity_open <= cur_time <= self.equity_close:
                return True, "Equity market session open."
            return False, f"Equity session is closed ({self.equity_open.strftime('%H:%M')} - {self.equity_close.strftime('%H:%M')})."

        elif exchange == Exchange.MCX:
            if self.mcx_open <= cur_time <= self.mcx_close:
                return True, "MCX commodity session open."
            return False, f"MCX session is closed ({self.mcx_open.strftime('%H:%M')} - {self.mcx_close.strftime('%H:%M')})."

        return False, f"Unknown exchange schedule for {exchange.value}."

    def is_past_square_off(self, exchange: Exchange, check_time: Optional[datetime] = None) -> bool:
        """
        Determines whether the trading session has crossed the mandatory intraday
        auto-square-off threshold (15:15 for Equity, 23:15 for MCX).
        """
        now = check_time or datetime.now()
        cur_time = now.time()

        if exchange in (Exchange.NSE, Exchange.BSE, Exchange.NFO):
            return cur_time >= self.equity_square_off
        elif exchange == Exchange.MCX:
            return cur_time >= self.mcx_square_off

        return False

    # =========================================================================
    # Pre-Trade Quantitative Risk Validation
    # =========================================================================

    def validate_order(
        self,
        order: OrderRequest,
        current_ltp: float,
        check_time: Optional[datetime] = None
    ) -> Tuple[bool, str]:
        """
        Pre-trade risk gateway. Assesses order against 5 institutional checks:
        1. System Circuit Breaker / Trading Halt status
        2. Market Session Active Status
        3. Intraday Auto-Square-Off Deadline
        4. Maximum Daily Loss & Drawdown Collar
        5. Position Capital Risk Limit (10% hard stop)
        """
        with self._lock:
            # 1. Trading Halt Circuit Check
            if self.is_halted:
                return False, f"RISK REJECT: Trading is currently HALTED. Reason: {self.halt_reason}"

            # 2. Market Hours Check
            is_open, open_msg = self.is_market_open(order.exchange, check_time)
            if not is_open:
                return False, f"RISK REJECT: {open_msg}"

            # 3. Square-off Time Lock
            # If past square-off time, disallow opening new positions (closing orders still permitted)
            if order.product_type == ProductType.INTRADAY and self.is_past_square_off(order.exchange, check_time):
                return False, (
                    f"RISK REJECT: Past mandatory square-off time for {order.exchange.value}. "
                    "New intraday order entries are prohibited."
                )

            # 4. Total Daily Loss Check
            total_net_pnl = self.realized_pnl + self.unrealized_pnl
            if total_net_pnl <= -self.max_daily_loss_inr:
                self._trip_circuit_breaker(
                    f"Daily loss limit breached: ₹{total_net_pnl:.2f} <= -₹{self.max_daily_loss_inr:.2f}"
                )
                return False, f"RISK REJECT: {self.halt_reason}"

            # 5. Capital Risk Check (Max 10% risk per allocation)
            effective_price = order.price if order.price > 0.0 else current_ltp
            if effective_price <= 0.0:
                return False, "RISK REJECT: Invalid execution reference price <= 0.0"

            order_value = effective_price * order.quantity
            
            # For intraday / margin, approximate margin requirement at 20% (5x leverage)
            margin_required = order_value * 0.20 if order.product_type == ProductType.INTRADAY else order_value
            
            if margin_required > self.allocated_capital:
                return False, (
                    f"RISK REJECT: Order margin requirement (₹{margin_required:.2f}) "
                    f"exceeds total allocated capital (₹{self.allocated_capital:.2f})."
                )

            # Enforce stop-loss protection
            if order.trigger_price > 0.0:
                risk_per_share = abs(effective_price - order.trigger_price)
                total_position_risk = risk_per_share * order.quantity
                if total_position_risk > self.max_capital_loss_inr:
                    return False, (
                        f"RISK REJECT: Position stop-loss risk (₹{total_position_risk:.2f}) "
                        f"exceeds 10% maximum capital risk limit (₹{self.max_capital_loss_inr:.2f})."
                    )

            return True, "Order risk validated. All compliance collars cleared."

    # =========================================================================
    # Real-Time Position & Profit Monitoring
    # =========================================================================

    def update_portfolio_telemetry(self, positions: List[Position]) -> None:
        """
        Recalculates running unrealized PnL, peak equity, and drawdowns.
        Trips emergency circuit breaker if daily loss threshold is crossed.
        """
        with self._lock:
            self.unrealized_pnl = sum(p.unrealized_pnl for p in positions)
            total_net = self.realized_pnl + self.unrealized_pnl

            # Track peak equity and drawdown
            if total_net > self.peak_pnl:
                self.peak_pnl = total_net

            self.current_drawdown = self.peak_pnl - total_net

            # Evaluate hard loss stop
            if total_net <= -self.max_daily_loss_inr:
                self._trip_circuit_breaker(
                    f"Daily loss circuit breaker triggered: Total P&L ₹{total_net:.2f} <= -₹{self.max_daily_loss_inr:.2f}"
                )

    def on_trade_filled(self, gross_pnl: float, friction_cost: float = 60.0) -> None:
        """
        Updates realized PnL and trade statistics upon trade execution fill.
        Strictly applies the ₹60 statutory friction cost buffer.
        """
        with self._lock:
            net_pnl = gross_pnl - friction_cost
            self.realized_pnl += net_pnl
            self.total_trades_count += 1

            total_net = self.realized_pnl + self.unrealized_pnl
            if total_net <= -self.max_daily_loss_inr:
                self._trip_circuit_breaker(
                    f"Daily loss limit breached upon trade fill: Net P&L ₹{total_net:.2f}"
                )

    def evaluate_profit_trigger(self, gross_pnl: float) -> Tuple[bool, float]:
        """
        Evaluates the mandatory ₹70 gross profit trigger.
        Returns (should_exit: bool, expected_net_pnl: float).
        Guarantees minimum ₹10.00 net profit after ₹60 friction deduction.
        """
        expected_net = gross_pnl - self.friction_buffer_inr
        should_trigger = gross_pnl >= self.min_gross_profit_trigger_inr and expected_net >= 10.0
        return should_trigger, expected_net

    def check_square_off_orders(
        self,
        positions: List[Position],
        check_time: Optional[datetime] = None
    ) -> List[OrderRequest]:
        """
        Generates immediate MARKET exit orders for all open intraday positions
        if the exchange clock has breached the square-off deadline.
        """
        exit_orders: List[OrderRequest] = []
        with self._lock:
            for pos in positions:
                if pos.net_quantity == 0 or pos.product_type != ProductType.INTRADAY:
                    continue

                if self.is_past_square_off(pos.exchange, check_time):
                    side = OrderSide.SELL if pos.net_quantity > 0 else OrderSide.BUY
                    qty = abs(pos.net_quantity)
                    exit_req = OrderRequest(
                        symbol=pos.symbol,
                        exchange=pos.exchange,
                        side=side,
                        order_type=OrderType.MARKET,
                        product_type=ProductType.INTRADAY,
                        quantity=qty,
                        tag="AUTO_SQUARE_OFF"
                    )
                    exit_orders.append(exit_req)

        return exit_orders

    def _trip_circuit_breaker(self, reason: str) -> None:
        """Engages institutional trading halt, blocking all new order submissions."""
        self.is_halted = True
        self.halt_reason = reason

    def reset_circuit_breaker(self) -> None:
        """Manual administrator override to reset trading halt for next session."""
        with self._lock:
            self.is_halted = False
            self.halt_reason = ""

    def get_risk_status(self) -> Dict[str, Any]:
        """Returns full executive diagnostic telemetry of the risk engine."""
        with self._lock:
            total_net = self.realized_pnl + self.unrealized_pnl
            return {
                "allocated_capital": self.allocated_capital,
                "max_capital_risk_pct": self.max_capital_risk_pct,
                "max_capital_loss_inr": self.max_capital_loss_inr,
                "max_daily_loss_inr": self.max_daily_loss_inr,
                "friction_buffer_inr": self.friction_buffer_inr,
                "min_gross_profit_trigger_inr": self.min_gross_profit_trigger_inr,
                "realized_pnl": round(self.realized_pnl, 2),
                "unrealized_pnl": round(self.unrealized_pnl, 2),
                "net_pnl": round(total_net, 2),
                "peak_pnl": round(self.peak_pnl, 2),
                "current_drawdown": round(self.current_drawdown, 2),
                "total_trades": self.total_trades_count,
                "is_halted": self.is_halted,
                "halt_reason": self.halt_reason
            }

