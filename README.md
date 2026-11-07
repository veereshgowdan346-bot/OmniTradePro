# OmniTradePro / Chintu AI Trading Board v5.0

![Platform](https://img.shields.io/badge/Platform-Windows%2010%2F11%20x64-blue)
![Python](https://img.shields.io/badge/Python-3.10%2B-brightgreen)
![GUI](https://img.shields.io/badge/GUI-PySide6%20%7C%20PyQtGraph-cyan)
![Markets](https://img.shields.io/badge/Markets-NSE%20%7C%20BSE%20%7C%20MCX-orange)
![Security](https://img.shields.io/badge/Security-AES--256%20Fernet%20Vault-red)
![License](https://img.shields.io/badge/License-Proprietary-darkred)

OmniTradePro (Chintu AI Trading Board v5.0) is a high-performance, institutional algorithmic trading desktop application engineered specifically for the Indian Financial Markets (NSE, BSE, MCX). Built with PySide6, PyQtGraph, and a cyber-glassmorphism dark UI, it bridges multi-broker gateway execution (Angel One SmartAPI, Finvasia Shoonya, Groww) with algorithmic consensus, intraday scanners, risk management systems (RMS), and real-time execution telemetry.

---

## Key Highlights

- **Zero-Fake-Data Mandate**: Pure exchange-driven reality. Unconnected states display clean, uncorrupted zeros and live exchange connection triggers without synthetic mock number generators.
- **Multi-Broker Database Vault**: AES-256 Fernet-encrypted dynamic credential management with automated TOTP (pyotp) generation and secure local key isolation.
- **WebSocket Streaming Engine**: High-throughput threaded market data feeds (`QThread`) processing live ticks across NSE and MCX.
- **4-Algorithm Consensus Matrix**:
  - SMC Liquidity Sweep (Smart Money Concepts)
  - EMA Dynamic Crossover (9 / 21 / 50 EMA)
  - SuperTrend Volatility Engine (ATR 10, Multiplier 3.0)
  - VWAP Momentum Flow with Intraday Volume Profile
- **Autonomous Capital Routing & RMS**:
  - Dynamic capital tiering (Micro, Standard, Institutional)
  - Hardened risk floor (10% max allocation per trade, dynamic ATR trailing stops)
  - Friction-aware execution (₹60.0 round-trip fee buffer)
  - Multi-session auto square-off: 15:15 IST (NSE/BSE) and 23:15 IST (MCX)
  - Global One-Click Emergency Kill Switch
- **15-Min Opening Range Breakout (ORB) & Monte Carlo Engine**: 10,000-permutation distribution modeling for statistical win-odds validation.

---

## Architectural Subsystems

```
shiva/
├── brokers/                    # Multi-Broker Gateway & Data Ingestion
│   ├── base_broker.py          # Abstract Base Class for Broker Gateways
│   ├── broker_adapters.py      # Angel One SmartAPI & Shoonya Implementations
│   ├── paper_broker.py         # Institutional Simulated Paper Execution
│   ├── stream_worker.py        # Threaded Live WebSocket Tick Processor
│   ├── token_master.py         # Official Scrip Master Caching & Translation
│   └── test_stream.py          # Gateway Verification Tests
├── core/                       # Quantitative Strategy & Execution Engines
│   ├── capital_allocator.py    # Autonomous Capital-to-Asset Routing Engine
│   ├── consensus.py            # 4-Strategy Democratic Voting & Order Staging
│   ├── order_router.py         # Multi-Broker Gateway Routing & Square-Off
│   ├── risk_budget.py          # Mathematical Sizing & Fee Deduction Filter
│   ├── risk_engine.py          # Real-time RMS, Drawdown & Margin Guardrails
│   ├── scanner_orb.py          # Intraday 15-Minute Nifty 50 ORB Scanner
│   ├── strategies.py           # Institutional Indicator Calculations
│   └── time_machine.py         # 10,000-Replay Monte Carlo Permutation Engine
├── database/                   # Persistent State & Cryptographic Vault
│   ├── db_handler.py           # SQLite Engine & AES-256 Fernet Encryption
│   ├── db_manager.py           # Centralized Database Connection Lifecycle
│   └── test_vault.py           # Cryptographic Security Audit Tests
├── ui/                         # Chintu AI Glassmorphic Presentation Layer
│   ├── assets/                 # Custom 3D Robot Mascot & Avatars
│   ├── chart_widget.py         # Real-time Candlestick & Volume Canvas
│   ├── dashboard.py            # Main Operations Cockpit
│   ├── main_window.py          # Central Routing Host with QStackedWidget
│   ├── order_panel.py          # Instant Manual Order Entry Dock
│   ├── scanner_panel.py        # High-Speed Market Scanner Dock
│   ├── styles.py               # Cyber Slate & Neon Emerald QSS Theme
│   ├── vault_dialog.py         # Encrypted Broker Authentication Modal
│   ├── views.py                # 11 Dedicated Application Views
│   └── test_ui_components.py   # UI Component Integrity Tests
├── config.json                 # Market Hours, Watchlists & Risk Parameters
├── main.py                     # Application Entry Point & Lifecycle Orchestrator
├── requirements.txt            # Production Pinned Dependencies
├── run.bat                     # Instant Desktop Launcher
├── setup.bat                   # Automated Virtualenv & Dependency Provisioner
└── verify_setup.py             # System Pre-flight Diagnostic Suite
```

---

## 12 Modular Workspaces

1. **Dashboard**: Live Cockpit with Top Tickers, Active Bots, Portfolio Card, Live P&L, RMS Card, and AI Sentiment.
2. **Live Trading**: Direct Level-2 Market Depth, Order Execution, and Live Tape.
3. **Trading Bots**: Bot Fleet Management (Alpha Trend Scalper, BankNifty Breakout, Mean Reversion Pro, Gamma Squeeze).
4. **Strategies**: Mathematical parameter tuning for SMC, EMA, SuperTrend, and VWAP.
5. **Market Watch**: High-speed watchlists across NSE, BSE, and MCX.
6. **Auto Trade**: Autonomous execution master switch and execution audit trail.
7. **Backtest**: Walk-forward backtesting against historical tick datasets.
8. **Analytics**: Sharpe, Sortino, Profit Factor, and Drawdown performance analytics.
9. **Portfolio**: Real-time margin utilization, equity curves, and position breakdown.
10. **Risk Manager (RMS)**: Hard stop limits, daily loss threshold, and trailing stop trackers.
11. **Logs & Reports**: Trade books, order books, and forensic audit event trails.
12. **Settings**: Broker API credentials vault, notification webhooks, and theme customization.

---

## Security & Vault Architecture

- **Zero Secret Ingestion**: All sensitive credentials (API Keys, MPINs, TOTP Secrets) are stored encrypted in SQLite using AES-256 (Fernet).
- **Git Lockdown Isolation**: `.gitignore` enforces strict zero-leakage boundaries against:
  - Encryption keys (`*.key`, `.vault.key`)
  - Local database files (`*.db`, `*.db-wal`, `*.db-shm`)
  - Virtual environments (`.venv/`)
  - Runtime execution logs (`logs/`)

---

## Installation & Launch

### Prerequisites
- Windows 10 / 11 (64-bit)
- Python 3.10 or higher
- C++ Build Tools (for compiled dependencies)

### Quick Start
1. Clone the repository:
   ```bash
   git clone https://github.com/veereshgowdan346-bot/OmniTradePro.git
   cd OmniTradePro
   ```
2. Double-click `run.bat` or launch via command line:
   ```cmd
   run.bat
   ```
   *The launcher automatically verifies `.venv`, installs requirements if missing, and boots the application.*

3. Run the complete test suite:
   ```cmd
   .venv\Scripts\python.exe -m unittest discover database
   .venv\Scripts\python.exe -m unittest discover core
   .venv\Scripts\python.exe -m unittest discover brokers
   .venv\Scripts\python.exe -m unittest discover ui
   ```

---

## Disclaimer

*Trading financial instruments in Indian markets (NSE, BSE, MCX) involves substantial risk of loss. OmniTradePro is an institutional trading system. Users are responsible for configuring their own risk thresholds and broker authorizations.*
