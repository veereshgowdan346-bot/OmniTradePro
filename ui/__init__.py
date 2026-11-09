"""
OmniTradePro / Chintu AI Trading Board v5.0 - UI Module
Provides frosted glassmorphism interface components, charting, dashboard cards,
broker control matrix, 12 multi-page views, and main window orchestrator.
"""

from ui.styles import GlassmorphismTheme
from ui.vault_dialog import BrokerVaultDialog
from ui.chart_widget import ChartWidget, CandleCanvas
from ui.dashboard import (
    HeaderTopBar, SubHeaderNavBar, LeftSidebar, QuickTradeCard,
    ActiveBotsCard, PortfolioCard, LivePnLCard, TodaySummaryCard,
    RiskManagerCard, AISentimentGauge, SystemHealthCard
)
from ui.views import (
    LiveTradingView, TradingBotsView, StrategiesView, MarketWatchView,
    AutoTradeView, BacktestView, AnalyticsView, PortfolioView,
    RiskManagerView, ReportsView, SettingsView
)
from ui.scanner_panel import ScannerPanel, MonteCarloOddsDialog
from ui.order_panel import OrderPanel
from ui.broker_control_widget import BrokerControlWidget, BrokerCard, BrokerCredentialsDialog

# MainWindow / DashboardView are re-exported lazily (PEP 562). Importing them
# eagerly meant `python -m ui.main_window` loaded the module twice and emitted a
# runpy RuntimeWarning at launch.
_LAZY_EXPORTS = ("MainWindow", "DashboardView")


def __getattr__(name: str):
    """Lazily resolves the orchestrator exports without a double import."""
    if name in _LAZY_EXPORTS:
        from ui.main_window import DashboardView, MainWindow

        globals()["MainWindow"] = MainWindow
        globals()["DashboardView"] = DashboardView
        return globals()[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__all__ = [
    "GlassmorphismTheme",
    "BrokerVaultDialog",
    "ChartWidget",
    "CandleCanvas",
    "HeaderTopBar",
    "SubHeaderNavBar",
    "LeftSidebar",
    "QuickTradeCard",
    "ActiveBotsCard",
    "PortfolioCard",
    "LivePnLCard",
    "TodaySummaryCard",
    "RiskManagerCard",
    "AISentimentGauge",
    "SystemHealthCard",
    "DashboardView",
    "LiveTradingView",
    "TradingBotsView",
    "StrategiesView",
    "MarketWatchView",
    "AutoTradeView",
    "BacktestView",
    "AnalyticsView",
    "PortfolioView",
    "RiskManagerView",
    "ReportsView",
    "SettingsView",
    "ScannerPanel",
    "MonteCarloOddsDialog",
    "OrderPanel",
    "BrokerControlWidget",
    "BrokerCard",
    "BrokerCredentialsDialog",
    "MainWindow",
]
