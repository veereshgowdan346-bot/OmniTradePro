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
from ui.main_window import MainWindow, DashboardView

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
