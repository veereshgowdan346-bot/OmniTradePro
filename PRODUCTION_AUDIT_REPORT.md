# OmniTradePro — Production Readiness Audit & Certification Report

**Role:** Principal Quantitative Systems Auditor / Lead QA Architect
**Date:** 2026-11-09
**Commit under audit:** `c0523a7` (branch `arena/8f6af6b6-omnitradepro`)
**Verdict:** ✅ **CERTIFIED** — 38 gates: 37 PASS, 0 FAIL, 1 documented WARN
**Machine-readable evidence:** `CERTIFICATION_MATRIX.md`, `certification_matrix.json`

---

## 1. Executive summary

The full stack — static, persistence, UI, quant, order routing, runtime — executes
cleanly. Nothing in the audited surface produces a `SyntaxError`, an unresolved
import, an eager import cycle, an uncaught exception, or a layout-geometry breach.

The audit did **not** find the codebase in a certifiable state on arrival. Fourteen
defects were remediated, six of them material to capital safety or to the integrity of
the certification evidence itself. The most serious were **certification theater**
(the test harness printed an all-PASS matrix regardless of results), a **fabricated
execution price** on the primary manual order path, and a **fail-open risk ceiling**
that let manually routed orders bypass the operator's capital allocation entirely.

Every gate in the matrix is now derived from an executed assertion or a subprocess
exit code. No row is hardcoded.

---

## 2. Method

| Stage | What was actually executed |
|---|---|
| 1 — Static | `ast.parse` over 56 modules (23.5k LOC); 39-module import sweep in a clean subprocess; module-scope import-cycle DFS |
| 2 — Persistence | `execution_config` write/read across two independent handlers; AES-256 round-trip for 3 brokers with ciphertext-on-disk proof; live TOTP; audit timestamp precision; `PRAGMA journal_mode` |
| 3 — UI | `python -X utf8 ui/test_ui_components.py` (10 dimensions) |
| 4 — Quant | 4-strategy votes, 4/4 unanimity, 3/4 quorum, sub-quorum rejection, GBM gate accept **and** reject, ₹70 hurdle accept **and** reject, 8 bps slippage both sides, uniform sizing, bracket SL, circuit breaker |
| 5 — Lifecycle | `python -X utf8 brokers/test_strategy_order_lifecycle.py` (6 dimensions) |
| 6 — Runtime | Real `MainWindow` in a headless Qt loop for 10 s: 203 ticks injected through `tick_received`, 25 page switches, 30 FPS timer, disconnect purge |

**Environment note.** The audit host is a headless Linux container without
`libGL`/`libEGL`/`libxkbcommon`/`libdbus`. Those shims were required to run Qt at all
and are **test infrastructure only** — nothing about them affects the Windows target.
They are reproducible via `tools/build_headless_qt_shims.sh` and are gitignored.

---

## 3. Defects found and remediated

### 3.1 Critical

| # | Defect | Impact | Fix |
|---|---|---|---|
| C1 | `run_benchmark()` printed a **hardcoded all-PASS** certification matrix while the suite was failing and exiting 1 | The project's own certificate was meaningless; a real regression would have shipped looking certified | Matrix rows are now derived from `result.failures`/`result.errors`; a FAIL test renders `[ FAIL ]` |
| C2 | `ui/test_ui_components.py` ran `DELETE FROM trade_audit_log` against the **production ledger** | Every test run destroyed the operator's audit trail | Suite runs against a throwaway `OMNITRADE_DATA_DIR`; isolation asserted before any assertion runs |
| C3 | Quick-trade path substituted a **fabricated price of ₹24,857.30** when no tick was present | Would transmit a real order at an invented price — the single worst failure mode in a trading system | `_resolve_live_price()` uses canvas → stream cache → **hard reject**; no synthetic value exists any more |
| C4 | Quick-trade sent **no stop-loss and no target**, so the ₹70 gross-hurdle gate was skipped (`if target_price > 0.0`) and no bracket SL was attached | Manual orders executed unprotected and exempt from the statutory hurdle | Bracket SL derived from the operator's max-SL budget, target from the 1:2.5 R:R, both always supplied |
| C5 | `OrderRouter.enforce_user_risk_limits` defaulted to **`False`** | Every caller that did not opt in bypassed the operator's capital ceiling and risk % — including the primary manual order path | Defaults to `True` (fail-closed); callers may opt out explicitly via the new constructor kwarg |

### 3.2 High

| # | Defect | Impact | Fix |
|---|---|---|---|
| H1 | `AssetWorkerPool` called `consensus_engine.evaluate(...)`; `ConsensusEngine` only exposes `evaluate_consensus()` | Every automated evaluation raised `AttributeError`, swallowed by the worker loop — zero signals, zero orders, silent | Contract normalised (`evaluate_consensus` → `evaluate` fallback), errors now counted in `evaluation_errors` telemetry |
| H2 | The predictive GBM gate (`≥65%`) was **never enabled** on any runtime path (`enforce_predictive_gate` defaults to `False`, no production caller sets it) | A statutory control existed only in tests | Automated path sets `enforce_predictive_gate=True` by default |
| H3 | `ChartWidget` seeded **80 synthetic candles** at boot, contradicting the Zero-Fake-Data mandate | Fabricated prices displayed as market data on first launch | Seeding is opt-in (`OMNITRADE_DEMO_CHART=1`); canvas starts empty |
| H4 | `test_04` required the operator's **real encrypted broker credentials** to already exist in the production vault | Suite failed on any clean machine; on a dirty one it wrote over real secrets | Synthetic per-run profiles seeded into an isolated vault, with an isolation assertion |

### 3.3 Medium

| # | Defect | Fix |
|---|---|---|
| M1 | Health card displayed a fabricated latency: `latency or 42` in the card, hardcoded `38` at four call sites in `MainWindow` | Real ingest→dispatch latency measured in `BrokerStreamWorker`; shows `-- ms` until measured |
| M2 | Quick-trade confirmation reported the **requested** quantity, not the filled quantity (showed 50 when 2 filled) | Reports filled qty/price/SL/target from the execution response |
| M3 | Bracket SL derived from pre-clamp quantity, then from pre-slippage price — realised risk landed at ₹81–₹105 against an ₹80 cap | Stop is budgeted against the post-clamp quantity and the worst admissible fill (8 bps) |
| M4 | `QMessageBox` on successful vault save blocked headless runs forever (modal nested event loop) | Patched in the suite; this is why the lifecycle suite previously "passed" in 0.3 s — it aborted before ever reaching that code |

### 3.4 Low

| # | Defect | Fix |
|---|---|---|
| L1 | Dimension 7 of the UI suite asserted correctness but printed no result, and never checked the 56px/36px geometry contract | Explicit PASS line + rigid min/max height and card-parenting assertions |
| L2 | Latent `ui.views → ui.settings_view → ui.views` module-level cycle, masked only by package `__init__` import order | `SettingsView` re-exported lazily via PEP 562 `__getattr__`; eager cycle count is now zero |
| L3 | `QuickTradeCard._on_place_order` defined twice | Duplicate removed |
| L4 | UI suite swallowed `QApplication` construction failure and would "pass" in stub mode | Now fails loudly |
| L5 | `core/test_phase6_execution.py` (pre-existing failure at base commit) depended on process-global `RiskBudget` state | Risk ratio passed explicitly |

---

## 4. Open item requiring a product decision (not changed unilaterally)

**SuperTrend multiplier — documented 3.0 vs implemented 2.0.**

| Source | Value |
|---|---|
| README / audit specification | `ATR 10, Multiplier 3.0` |
| `SuperTrendGate.evaluate()` default | `2.0` |
| `ConsensusEngine.evaluate_consensus()` call site | `multiplier=2.0` |

Changing this alters live signal generation and the historical quorum outcomes the
benchmarks assert against, so it is reported as **non-conformance** rather than
silently patched. Either the documentation or the parameter must be reconciled by the
strategy owner; the audit re-runs automatically once one side is changed.

---

## 5. Residual risks (accepted, documented)

1. **Two persistence layers over one file.** `DatabaseHandler` and `DatabaseManager`
   are independent singletons both bound to `database/omnitrade.db`, each with its own
   thread-local connection. Schemas are compatible today (verified), but nothing
   prevents divergence. Recommendation: collapse to one owner.
2. **Naming drift.** The brief refers to `omnitrade_live.db`; the code writes
   `omnitrade.db`. No such file exists.
3. **Singleton path stickiness.** `DatabaseManager.__init__` ignores a new `db_path`
   once constructed. Mitigated for testing by `OMNITRADE_DATA_DIR`.
4. **Global mutable risk state.** `RiskBudget` holds class-level `_user_*` fields
   written from the Qt thread and read from worker threads. Not a race in the audited
   flows, but it is shared state without a lock.
5. **Silent Qt fallback shims.** Several UI modules define no-op Qt stand-ins when
   `PySide6` is missing. This makes import succeed while providing non-functional
   widgets — a good way to hide a broken deployment. Recommendation: fail fast outside
   tests.
6. **`test_real_angel_live.py`** requires live credentials and network; it was not
   executed and is out of scope for this certificate.

---

## 6. Reproducing this certificate

**Windows (target platform):**
```cmd
.venv\Scripts\python.exe ui\test_ui_components.py
.venv\Scripts\python.exe -X utf8 brokers\test_strategy_order_lifecycle.py
.venv\Scripts\python.exe audit_production_certification.py
```

**Headless Linux / CI:**
```bash
bash tools/build_headless_qt_shims.sh
export LD_LIBRARY_PATH="$PWD/.shim:$LD_LIBRARY_PATH"
export QT_QPA_PLATFORM=offscreen
python audit_production_certification.py        # writes CERTIFICATION_MATRIX.md
python audit_production_certification.py --json # machine-readable
```

The harness exits non-zero if any gate fails, so it is CI-gateable as-is. All suites
run against a temporary `OMNITRADE_DATA_DIR`; no run touches the operator's ledger or
vault.

---

## 7. Sign-off

The system is certified for production use **on the Windows target platform**, subject
to the single open non-conformance in §4 and the accepted risks in §5. The evidence
chain is reproducible end-to-end: every PASS in `CERTIFICATION_MATRIX.md` corresponds
to an assertion that executed during this run.
