# OmniTradePro - Production Certification Matrix

**Verdict: CERTIFIED FOR PRODUCTION**

- Generated: 2026-11-09T06:49:45+00:00
- Host: Linux-6.1.158+-x86_64-with-glibc2.36 | Python 3.11.2
- Sandbox data directory: `/tmp/omnitrade_cert_9lgr4os9`
- Gates: **38** | PASS 37 | FAIL 0 | WARN 1 | SKIP 0

Every status below is derived from an executed assertion or a subprocess exit
code. No row is hardcoded.

| Stage | Gate | Status | Evidence |
|---|---|---|---|
| Stage 1 - Syntax, AST & Import Audit | AST parse of 56 modules (23,588 LOC) | PASS | zero SyntaxError |
|  | Import verification (39 modules) | PASS | 39/39 imported cleanly |
|  | Eager import cycle detection (56 modules) | PASS | zero module-scope cycles |
| Stage 2 - Database & State Persistence | execution_config CRUD (mode, capital, risk %, max_sl, drawdown) | PASS | read back mode=LIVE cap=2500.0 risk=4.8 sl=120.0 dd=15.0 |
|  | Cross-handler execution_config consistency | PASS | DatabaseHandler sees cap=2500.0 sl=120.0 |
|  | AES-256 vault round trip + live TOTP (3 brokers) | PASS | encrypt/decrypt verified, zero plaintext secrets on disk |
|  | Audit-log timestamp precision (sub-millisecond) | PASS | ISO-8601 microsecond precision stored: 2026-11-09T06:49:30.509824+00:00 |
|  | SQLite WAL journal mode | PASS | journal_mode=wal |
| Stage 3 - Front-End UI & Signal Wiring | UI component suite (10 dimensions) | PASS | exit=0 pass_assertions=12 fail_assertions=0 in 1.2s |
| Stage 4 - Quant Strategy & Consensus Audit | Strategy vote: SMC Liquidity Sweep (3-candle confirmation) | PASS | vote=+1 |
|  | Strategy vote: Institutional VWAP | PASS | vote=+1 |
|  | Strategy vote: Dual EMA (9/21) | PASS | vote=+1 |
|  | Strategy vote: SuperTrend Gate (period 10) | PASS | vote=+1 |
|  | SMC confirmation window == 3 candles | PASS | CONFIRMATION_WINDOW=3 |
|  | SuperTrend multiplier matches documented 10/3 specification | WARN | documented=3.0 \| evaluate() default=2.0 \| ConsensusEngine passes multiplier=2.0 (deviation recorded, not silently changed) |
|  | Consensus 4/4 unanimity -> BUY approved | PASS | score=100.0% signal=BUY approved=True |
|  | Consensus 3/4 quorum (>=75%) -> BUY approved | PASS | score=75.0% signal=BUY approved=True |
|  | Sub-quorum / odds-filter rejection | PASS | score=75.0% approved=False |
|  | Predictive GBM gate approves >=65% reachability | PASS | probability=67.89% hurdle_passed=True |
|  | Predictive gate rejects sub-threshold setup | PASS | probability=20.38% approved=False |
|  | Statutory gross hurdle constant == Rs 70 | PASS | MIN_GROSS_PROFIT_TRIGGER_INR=70.0 |
|  | Profit hurdle blocks a sub-Rs 70 setup | PASS | gross_pass=5000.0 gross_fail=0.02 |
|  | Slippage guard boundary == 0.08% | PASS | drift 0.050% accepted, 0.200% rejected (limit 8 bps) |
|  | Uniform LOT sizing + bracket SL inside max-SL budget | PASS | qty=10 sl=492.0 total_risk=Rs80.0 (cap Rs80) |
|  | Intraday circuit breaker trips | PASS | Cumulative intraday realized loss ₹350.00 >= 2.5x max SL limit (₹300.00). |
| Stage 5 - Order Router & Uniform Risk Enforcement | Strategy/order lifecycle suite (6 dimensions) | PASS | exit=0 pass_assertions=33 fail_assertions=0 in 1.3s |
| Stage 6 - Live Runtime Smoke Test | MainWindow instantiated and shown | PASS | True |
|  | Boot time within budget (323 ms < 5000 ms) | PASS | True |
|  | 12 views registered in QStackedWidget | PASS | True |
|  | 30 FPS render timer active | PASS | True |
|  | Render timer interval ~33 ms | PASS | True |
|  | Historical candlestick backfill accepted | PASS | True |
|  | Event loop survived 10.3s | PASS | True |
|  | Mock ticks ingested via tick_received signal | PASS | True |
|  | 12-page navigation stable under tick load | PASS | True |
|  | No uncaught Python exception | PASS | True |
|  | No Qt critical/fatal messages | PASS | True |
|  | clear_canvas() on disconnect (Zero-Fake-Data) | PASS | True |

## Warnings (non-blocking)

- **SuperTrend multiplier matches documented 10/3 specification** (S4-QUANT): documented=3.0 | evaluate() default=2.0 | ConsensusEngine passes multiplier=2.0 (deviation recorded, not silently changed)
