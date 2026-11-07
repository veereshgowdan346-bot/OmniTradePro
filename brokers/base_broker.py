#!/usr/bin/env python3
"""
OmniTradePro - Abstract Base Broker Gateway & Unified Domain Models
Platform: Windows 10/11 64-bit | Python 3.10+
Defines standard institutional data contracts, enumerations, and the abstract
interface for multi-broker execution across Indian exchanges (NSE, BSE, NFO, MCX).
"""

from abc import ABC, abstractmethod
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List, Callable


# =============================================================================
# Institutional Market Enumerations
# =============================================================================

class OrderSide(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class OrderType(str, Enum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOPLOSS_LIMIT = "STOPLOSS_LIMIT"
    STOPLOSS_MARKET = "STOPLOSS_MARKET"


class ProductType(str, Enum):
    INTRADAY = "INTRADAY"      # MIS
    DELIVERY = "DELIVERY"      # CNC
    MARGIN = "MARGIN"          # MTF / NRML
    CARRYFORWARD = "CARRYFORWARD"  # NRML for F&O / MCX


class Exchange(str, Enum):
    NSE = "NSE"
    BSE = "BSE"
    NFO = "NFO"
    MCX = "MCX"


class OrderStatus(str, Enum):
    PENDING = "PENDING"
    SUBMITTED = "SUBMITTED"
    OPEN = "OPEN"
    TRIGGER_PENDING = "TRIGGER_PENDING"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    COMPLETE = "COMPLETE"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"


class MarketSession(str, Enum):
    EQUITY = "EQUITY"
    MCX = "MCX"


# =============================================================================
# Unified Domain Data Contracts
# =============================================================================

@dataclass
class OrderRequest:
    """Standardized order placement and routing request payload."""
    symbol: str
    exchange: Exchange
    side: OrderSide
    order_type: OrderType
    product_type: ProductType
    quantity: int
    price: float = 0.0
    trigger_price: float = 0.0
    disclosed_quantity: int = 0
    tag: str = "OMNITRADE"
    client_order_id: str = field(default_factory=lambda: f"ORD_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')}")

    def validate(self) -> None:
        """Validates order parameters against institutional execution rules."""
        if not self.symbol or not isinstance(self.symbol, str):
            raise ValueError("OrderRequest 'symbol' must be a non-empty string.")
        if self.quantity <= 0:
            raise ValueError(f"OrderRequest 'quantity' must be > 0, got {self.quantity}")
        if self.order_type in (OrderType.LIMIT, OrderType.STOPLOSS_LIMIT) and self.price <= 0.0:
            raise ValueError(f"OrderRequest 'price' must be > 0.0 for limit orders, got {self.price}")
        if self.order_type in (OrderType.STOPLOSS_LIMIT, OrderType.STOPLOSS_MARKET) and self.trigger_price <= 0.0:
            raise ValueError(f"OrderRequest 'trigger_price' must be > 0.0 for stop-loss orders, got {self.trigger_price}")


@dataclass
class OrderResponse:
    """Standardized broker order placement and update response."""
    client_order_id: str
    broker_order_id: str
    symbol: str
    exchange: Exchange
    side: OrderSide
    order_type: OrderType
    product_type: ProductType
    quantity: int
    price: float
    trigger_price: float
    status: OrderStatus
    filled_quantity: int = 0
    average_price: float = 0.0
    message: str = ""
    rejection_reason: str = ""
    raw_response: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class Position:
    """Standardized portfolio position tracking."""
    symbol: str
    exchange: Exchange
    product_type: ProductType
    net_quantity: int
    buy_quantity: int
    sell_quantity: int
    buy_average_price: float
    sell_average_price: float
    realized_pnl: float
    unrealized_pnl: float
    last_price: float
    multiplier: int = 1
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class AccountFunds:
    """Standardized account funds and margin telemetry."""
    net_available: float
    utilized: float
    collateral: float = 0.0
    cash: float = 0.0
    realized_pnl: float = 0.0
    unrealized_pnl: float = 0.0
    currency: str = "INR"
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class MarketTick:
    """Institutional tick data snapshot received from live exchange feeds."""
    symbol: str
    exchange: Exchange
    token: str
    ltp: float
    volume: int = 0
    bid_price: float = 0.0
    bid_quantity: int = 0
    ask_price: float = 0.0
    ask_quantity: int = 0
    open: float = 0.0
    high: float = 0.0
    low: float = 0.0
    close: float = 0.0
    change_pct: float = 0.0
    open_interest: int = 0
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class ScripMasterEntry:
    """Instrument definition mapping symbols to broker exchange tokens."""
    symbol: str
    trading_symbol: str
    exchange: Exchange
    token: str
    lot_size: int = 1
    tick_size: float = 0.05
    instrument_type: str = "EQUITY"
    expiry: str = ""
    strike_price: float = 0.0


# =============================================================================
# Abstract Base Broker Interface
# =============================================================================

class BaseBroker(ABC):
    """
    Abstract Base Class defining the unified broker interface for OmniTradePro.
    Implemented by AngelOneBroker, ShoonyaBroker, GrowwBroker, and PaperBroker.
    """

    def __init__(self, broker_name: str) -> None:
        self.broker_name = broker_name.upper()
        self.is_authenticated = False
        self._market_data_callback: Optional[Callable[[MarketTick], None]] = None

    @abstractmethod
    def authenticate(self) -> bool:
        """
        Establishes institutional session with the broker using credentials
        stored in the encrypted database vault, executing dynamic TOTP generation.
        """
        pass

    @abstractmethod
    def get_profile(self) -> Dict[str, Any]:
        """Retrieves user profile, account settings, and exchange permissions."""
        pass

    @abstractmethod
    def get_funds(self) -> AccountFunds:
        """Fetches live balance, margin utilization, and available limits in INR."""
        pass

    @abstractmethod
    def place_order(self, order: OrderRequest) -> OrderResponse:
        """Places a new order with the broker gateway."""
        pass

    @abstractmethod
    def modify_order(
        self,
        broker_order_id: str,
        quantity: int,
        price: float,
        trigger_price: float = 0.0
    ) -> OrderResponse:
        """Modifies price, trigger price, or quantity for an existing open order."""
        pass

    @abstractmethod
    def cancel_order(self, broker_order_id: str) -> OrderResponse:
        """Cancels an existing pending or open order."""
        pass

    @abstractmethod
    def get_order_book(self) -> List[OrderResponse]:
        """Retrieves the full order book for the current trading day."""
        pass

    @abstractmethod
    def get_positions(self) -> List[Position]:
        """Retrieves current open and closed intraday / delivery positions."""
        pass

    @abstractmethod
    def get_holdings(self) -> List[Dict[str, Any]]:
        """Retrieves long-term demat portfolio equity holdings."""
        pass

    @abstractmethod
    def get_ltp(self, symbol: str, exchange: Exchange) -> float:
        """Retrieves the real-time Last Traded Price (LTP) directly from the exchange."""
        pass

    @abstractmethod
    def get_quote(self, symbol: str, exchange: Exchange) -> Dict[str, Any]:
        """Fetches full market depth (5-best bid/ask), volume, and OHLC data."""
        pass

    @abstractmethod
    def start_market_data(
        self,
        tokens: List[str],
        on_tick_callback: Callable[[MarketTick], None]
    ) -> bool:
        """Initiates high-frequency streaming WebSocket connection for tick updates."""
        pass

    @abstractmethod
    def stop_market_data(self) -> None:
        """Terminates active WebSocket streaming connection."""
        pass

