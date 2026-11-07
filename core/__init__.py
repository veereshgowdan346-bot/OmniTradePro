"""
OmniTradePro Quantitative Core Subsystem.
Exports RiskEngine, MarketScannerORB, SymbolNormalizer, MonteCarloTimeMachine,
institutional strategies (SMC, VWAP, DualEMA, SuperTrend, ATRTrailingStop),
ConsensusEngine, StagedProfitManager, CapitalAllocator, RiskBudget, and OrderRouter.
"""

from core.risk_engine import RiskEngine
from core.scanner_orb import SymbolNormalizer, MarketScannerORB
from core.time_machine import MonteCarloTimeMachine
from core.strategies import (
    SMCLiquiditySweep,
    InstitutionalVWAP,
    DualEMAMomentum,
    SuperTrendGate,
    ATRTrailingStop
)
from core.consensus import ConsensusEngine, StagedProfitManager
from core.capital_allocator import CapitalAllocator
from core.risk_budget import RiskBudget
from core.order_router import OrderRouter

__all__ = [
    "RiskEngine",
    "SymbolNormalizer",
    "MarketScannerORB",
    "MonteCarloTimeMachine",
    "SMCLiquiditySweep",
    "InstitutionalVWAP",
    "DualEMAMomentum",
    "SuperTrendGate",
    "ATRTrailingStop",
    "ConsensusEngine",
    "StagedProfitManager",
    "CapitalAllocator",
    "RiskBudget",
    "OrderRouter"
]
