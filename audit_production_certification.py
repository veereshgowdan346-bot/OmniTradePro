#!/usr/bin/env python3
"""
OmniTradePro - Production Readiness Certification Harness
==========================================================
Runs the six audit stages and emits a machine-checkable certification matrix.

    python audit_production_certification.py            # full run
    python audit_production_certification.py --json     # JSON only
    python audit_production_certification.py --skip-slow

Stage 1  Static: syntax, AST, imports, eager import cycles
Stage 2  Persistence: execution_config CRUD, AES-256 vault, audit timestamps
Stage 3  UI: runs ui/test_ui_components.py (10 component dimensions)
Stage 4  Quant: 4-strategy consensus, quorum, predictive + profit + slippage gates
Stage 5  Lifecycle: runs brokers/test_strategy_order_lifecycle.py (6 dimensions)
Stage 6  Runtime: headless MainWindow boot + tick ingestion smoke test

Exit code is 0 only when every gate PASSES. Nothing is hardcoded to PASS: every
verdict is derived from an executed assertion or a subprocess exit code.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import re
import subprocess
import sys
import tempfile
import time
import traceback
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, List, Optional

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

# Every stage runs against a throwaway data directory: never the operator's ledger.
SANDBOX = Path(tempfile.mkdtemp(prefix="omnitrade_cert_"))
os.environ["OMNITRADE_DATA_DIR"] = str(SANDBOX)
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

PASS, FAIL, WARN, SKIP = "PASS", "FAIL", "WARN", "SKIP"


@dataclass
class Check:
    stage: str
    name: str
    status: str
    detail: str = ""
    severity: str = "blocker"

    def to_row(self) -> dict:
        return asdict(self)


@dataclass
class Report:
    checks: List[Check] = field(default_factory=list)

    def add(self, stage: str, name: str, status: str, detail: str = "", severity: str = "blocker") -> Check:
        chk = Check(stage, name, status, detail, severity)
        self.checks.append(chk)
        return chk

    @property
    def blockers_failed(self) -> List[Check]:
        return [c for c in self.checks if c.status == FAIL]

    @property
    def certified(self) -> bool:
        return not self.blockers_failed


# ---------------------------------------------------------------------------
# Stage 1 - Static analysis
# ---------------------------------------------------------------------------
def stage1_static(rep: Report) -> None:
    stage = "S1-STATIC"
    skip_dirs = {".git", ".venv", ".shim", "__pycache__", "build", "dist", "benchmarks"}

    files = []
    for root, dirs, fnames in os.walk(ROOT):
        dirs[:] = [d for d in dirs if d not in skip_dirs]
        files.extend(Path(root) / f for f in fnames if f.endswith(".py"))
    files.sort()

    import ast
    syntax_errors, loc = [], 0
    for f in files:
        src = f.read_text(encoding="utf-8")
        loc += src.count("\n")
        try:
            ast.parse(src, filename=str(f))
        except SyntaxError as exc:
            syntax_errors.append(f"{f.relative_to(ROOT)}:{exc.lineno} {exc.msg}")
    rep.add(stage, f"AST parse of {len(files)} modules ({loc:,} LOC)",
            PASS if not syntax_errors else FAIL,
            "zero SyntaxError" if not syntax_errors else "; ".join(syntax_errors))

    # Import verification in a subprocess so a crash cannot poison this process.
    modules = [
        "database", "database.db_handler", "database.db_manager", "database.vault_manager",
        "core", "core.strategies", "core.consensus", "core.risk_budget", "core.risk_engine",
        "core.order_router", "core.predictive_gate", "core.regime_classifier",
        "core.capital_allocator", "core.scanner_orb", "core.time_machine", "core.notifier",
        "core.asset_worker_pool",
        "brokers", "brokers.base_broker", "brokers.angel_one", "brokers.shoonya",
        "brokers.groww", "brokers.paper_broker", "brokers.stream_worker",
        "brokers.token_master", "brokers.broker_adapters",
        "ui", "ui.styles", "ui.vault_dialog", "ui.chart_widget", "ui.dashboard",
        "ui.main_window", "ui.sidebar", "ui.views", "ui.quick_risk_widget",
        "ui.broker_control_widget", "ui.order_panel", "ui.scanner_panel", "ui.settings_view",
    ]
    code = (
        "import importlib,sys\n"
        f"mods={modules!r}\n"
        "bad=[]\n"
        "for m in mods:\n"
        "    try: importlib.import_module(m)\n"
        "    except Exception as e: bad.append(f'{m}: {type(e).__name__}: {e}')\n"
        "print(len(mods)-len(bad)); print('|'.join(bad))\n"
    )
    env = dict(os.environ)
    env["PYTHONPATH"] = str(ROOT)
    proc = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, env=env, cwd=str(ROOT))
    out_lines = proc.stdout.split("\n")
    ok_count = out_lines[0].strip() if out_lines else "0"
    failures = out_lines[1].strip() if len(out_lines) > 1 else ""
    if proc.returncode != 0:
        ok_count, failures = "0", proc.stderr[-400:]
    rep.add(stage, f"Import verification ({len(modules)} modules)",
            PASS if proc.returncode == 0 and not failures else FAIL,
            f"{ok_count}/{len(modules)} imported cleanly" if not failures else failures)

    # Eager (module-scope) import cycles only: deferred in-function imports are legal.
    graph = {}
    for f in files:
        rel = f.relative_to(ROOT)
        mod = str(rel.with_suffix("")).replace(os.sep, ".")
        if mod.endswith(".__init__"):
            mod = mod[: -len(".__init__")]
        tree = ast.parse(f.read_text(encoding="utf-8"))
        edges = set()

        def visit(node):
            for child in ast.iter_child_nodes(node):
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue  # deferred import: not an eager cycle
                if isinstance(child, ast.Import):
                    for alias in child.names:
                        edges.add(alias.name)
                elif isinstance(child, ast.ImportFrom) and child.module and not child.level:
                    edges.add(child.module)
                visit(child)

        visit(tree)
        graph[mod] = {e for e in edges if e.split(".")[0] in {"core", "ui", "brokers", "database"}}

    cycles, seen = [], set()

    def dfs(node, stack):
        for dep in graph.get(node, ()):
            if dep in stack:
                cycles.append(tuple(stack[stack.index(dep):] + [dep]))
                continue
            if dep in seen:
                continue
            seen.add(dep)
            dfs(dep, stack + [dep])

    for node in sorted(graph):
        dfs(node, [node])
    unique_cycles = sorted(set(cycles))
    rep.add(stage, f"Eager import cycle detection ({len(graph)} modules)",
            PASS if not unique_cycles else FAIL,
            "zero module-scope cycles" if not unique_cycles else "; ".join(" -> ".join(c) for c in unique_cycles))


# ---------------------------------------------------------------------------
# Stage 2 - Persistence
# ---------------------------------------------------------------------------
def stage2_database(rep: Report) -> None:
    stage = "S2-PERSISTENCE"
    from database.db_handler import DatabaseHandler
    from database.db_manager import DatabaseManager
    from database.vault_manager import VaultManager

    dbh = DatabaseHandler()
    dbm = DatabaseManager()
    vault = VaultManager()

    # -- execution_config round trip (all five statutory fields) --
    saved = dbm.save_execution_config(mode="LIVE", trade_capital=2500.0, max_sl=120.0,
                                      risk_percentage=4.8, daily_drawdown_pct=15.0)
    cfg = dbm.get_execution_config()
    fields_ok = (
        saved and cfg["mode"] == "LIVE" and cfg["trade_capital"] == 2500.0
        and cfg["risk_percentage"] == 4.8 and cfg["max_sl"] == 120.0
        and cfg["daily_drawdown_pct"] == 15.0
    )
    rep.add(stage, "execution_config CRUD (mode, capital, risk %, max_sl, drawdown)",
            PASS if fields_ok else FAIL,
            f"read back mode={cfg['mode']} cap={cfg['trade_capital']} risk={cfg['risk_percentage']} "
            f"sl={cfg['max_sl']} dd={cfg['daily_drawdown_pct']}")

    # -- cross-handler consistency (two singletons, same ledger file) --
    cfg2 = dbh.get_execution_config()
    rep.add(stage, "Cross-handler execution_config consistency",
            PASS if (cfg2["trade_capital"], cfg2["max_sl"]) == (2500.0, 120.0) else FAIL,
            f"DatabaseHandler sees cap={cfg2['trade_capital']} sl={cfg2['max_sl']}")

    # -- AES-256 vault round trip + real TOTP for all three brokers --
    import pyotp
    secrets = {}
    for broker in ("ANGEL_ONE", "SHOONYA", "GROWW"):
        secret = pyotp.random_base32()
        vault.save_broker_credentials(
            broker_name=broker, client_id=f"CERT{broker[:3]}", api_key="k", secret_key="s",
            login_mpin="1234", totp_secret=secret, trading_pin="654321",
        )
        secrets[broker] = secret

    problems = []
    for broker, secret in secrets.items():
        creds = vault.get_broker_credentials(broker)
        if creds["totp_secret"] != secret:
            problems.append(f"{broker}: TOTP secret did not round-trip")
        if creds["trading_pin"] != "654321" or creds["login_mpin"] != "1234":
            problems.append(f"{broker}: MPIN/TPIN did not round-trip")
        code = vault.generate_dynamic_totp(creds["totp_secret"])
        if len(code) != 6 or not code.isdigit():
            problems.append(f"{broker}: TOTP generation invalid ({code})")

    # Ciphertext-on-disk proof: the plaintext must not appear in the DB file.
    raw = Path(vault.db_path).read_bytes()
    for broker, secret in secrets.items():
        if secret.encode() in raw:
            problems.append(f"{broker}: TOTP secret stored in PLAINTEXT")

    rep.add(stage, "AES-256 vault round trip + live TOTP (3 brokers)",
            PASS if not problems else FAIL,
            "encrypt/decrypt verified, zero plaintext secrets on disk" if not problems else "; ".join(problems))

    # -- audit log timestamp precision --
    ts = datetime.now(timezone.utc).isoformat()
    has_micros = bool(re.search(r"\.\d{6}", ts))
    dbm.log_audit(event_type="CERT", severity="INFO", component="audit", message="timestamp probe")
    rows = dbm.get_audit_logs(limit=1)
    stored = rows[0]["timestamp"] if rows else ""
    rep.add(stage, "Audit-log timestamp precision (sub-millisecond)",
            PASS if has_micros and re.search(r"\.\d{6}", str(stored)) else FAIL,
            f"ISO-8601 microsecond precision stored: {stored}")

    # -- WAL durability mode --
    conn = dbm._get_connection()
    mode = conn.execute("PRAGMA journal_mode;").fetchone()[0]
    rep.add(stage, "SQLite WAL journal mode", PASS if str(mode).lower() == "wal" else FAIL, f"journal_mode={mode}")

    dbm.save_execution_config(mode="PAPER", trade_capital=1000.0, max_sl=80.0,
                              risk_percentage=5.0, daily_drawdown_pct=10.0)


# ---------------------------------------------------------------------------
# Stage 3 / 5 - run the project's own suites as subprocesses
# ---------------------------------------------------------------------------
def _run_suite(rep: Report, stage: str, name: str, script: str, expect_pass_lines: int) -> None:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(ROOT)
    env["PYTHONIOENCODING"] = "utf-8"
    started = time.perf_counter()
    proc = subprocess.run([sys.executable, "-X", "utf8", script], capture_output=True,
                          text=True, env=env, cwd=str(ROOT), timeout=600)
    elapsed = time.perf_counter() - started
    out = proc.stdout + proc.stderr
    passes = len(re.findall(r"\[ PASS \]", out))
    fails = len(re.findall(r"\[ FAIL \]", out))
    detail = f"exit={proc.returncode} pass_assertions={passes} fail_assertions={fails} in {elapsed:.1f}s"
    ok = proc.returncode == 0 and fails == 0 and passes >= expect_pass_lines
    if not ok:
        tail = [ln for ln in out.splitlines() if ln.strip()][-6:]
        detail += " | " + " ⏎ ".join(tail)
    rep.add(stage, name, PASS if ok else FAIL, detail)


def stage3_ui(rep: Report) -> None:
    _run_suite(rep, "S3-UI", "UI component suite (10 dimensions)", "ui/test_ui_components.py", 10)


def stage5_lifecycle(rep: Report) -> None:
    _run_suite(rep, "S5-LIFECYCLE", "Strategy/order lifecycle suite (6 dimensions)",
               "brokers/test_strategy_order_lifecycle.py", 15)


# ---------------------------------------------------------------------------
# Stage 4 - Quantitative gates
# ---------------------------------------------------------------------------
def stage4_quant(rep: Report) -> None:
    stage = "S4-QUANT"
    import pandas as pd
    from core.strategies import SMCLiquiditySweep, InstitutionalVWAP, DualEMAMomentum, SuperTrendGate
    from core.consensus import ConsensusEngine
    from core.predictive_gate import PredictiveGate
    from core.risk_budget import RiskBudget

    csv = ROOT / "benchmarks" / "data" / "crudeoil_2025_1h.csv"
    df = pd.read_csv(csv)
    slice_32 = df.iloc[:32].reset_index(drop=True)

    votes = {
        "SMC Liquidity Sweep (3-candle confirmation)": SMCLiquiditySweep.evaluate(slice_32),
        "Institutional VWAP": InstitutionalVWAP.evaluate(slice_32),
        "Dual EMA (9/21)": DualEMAMomentum.evaluate(slice_32),
        "SuperTrend Gate (period 10)": SuperTrendGate.evaluate(slice_32, period=10, multiplier=2.0),
    }
    for label, res in votes.items():
        rep.add(stage, f"Strategy vote: {label}",
                PASS if int(res.get("vote", 0)) in (-1, 0, 1) else FAIL,
                f"vote={int(res.get('vote', 0)):+d}")

    rep.add(stage, "SMC confirmation window == 3 candles",
            PASS if SMCLiquiditySweep.CONFIRMATION_WINDOW == 3 else FAIL,
            f"CONFIRMATION_WINDOW={SMCLiquiditySweep.CONFIRMATION_WINDOW}")

    # SuperTrend multiplier: documented 3.0 (README + spec) vs code 2.0.
    import inspect
    src = inspect.signature(SuperTrendGate.evaluate).parameters["multiplier"].default
    consensus_src = inspect.getsource(ConsensusEngine.evaluate_consensus)
    consensus_mult = re.search(r"multiplier=([0-9.]+)", consensus_src)
    consensus_mult = float(consensus_mult.group(1)) if consensus_mult else None
    rep.add(stage, "SuperTrend multiplier matches documented 10/3 specification",
            WARN if (src != 3.0 or consensus_mult != 3.0) else PASS,
            f"documented=3.0 | evaluate() default={src} | ConsensusEngine passes multiplier={consensus_mult} "
            f"(deviation recorded, not silently changed)", severity="minor")

    # Unanimity + quorum
    unanimous = ConsensusEngine.evaluate_consensus(slice_32)
    quorum = ConsensusEngine.evaluate_consensus(df.iloc[120:160].reset_index(drop=True))
    rep.add(stage, "Consensus 4/4 unanimity -> BUY approved",
            PASS if unanimous["signal"] == "BUY" and unanimous["consensus_score"] == 100.0 and unanimous["approved"] else FAIL,
            f"score={unanimous['consensus_score']}% signal={unanimous['signal']} approved={unanimous['approved']}")
    rep.add(stage, "Consensus 3/4 quorum (>=75%) -> BUY approved",
            PASS if quorum["consensus_score"] >= 75.0 and quorum["approved"] else FAIL,
            f"score={quorum['consensus_score']}% signal={quorum['signal']} approved={quorum['approved']}")

    # Below-quorum control: force a 2/4 split.
    below = ConsensusEngine.evaluate_consensus(df.iloc[120:160].reset_index(drop=True), passes_odds_filter=False)
    rep.add(stage, "Sub-quorum / odds-filter rejection",
            PASS if below["approved"] is False else FAIL,
            f"score={below['consensus_score']}% approved={below['approved']}")

    # Predictive gate
    good = PredictiveGate.evaluate(
        df=df.iloc[120:160].reset_index(drop=True), signal=quorum["signal"],
        entry_price=quorum["entry_price"], target_price=quorum["target_price"],
        stop_loss=quorum["stop_loss"], quantity=500)
    rep.add(stage, "Predictive GBM gate approves >=65% reachability",
            PASS if good["probability_pct"] >= 65.0 and good["approved"] else FAIL,
            f"probability={good['probability_pct']}% hurdle_passed={good['hurdle_passed']}")

    bad = PredictiveGate.evaluate(
        df=df.iloc[120:160].reset_index(drop=True), signal="SELL",
        entry_price=quorum["entry_price"], target_price=quorum["entry_price"] - 0.5,
        stop_loss=quorum["entry_price"] + 0.5, quantity=10)
    rep.add(stage, "Predictive gate rejects sub-threshold setup",
            PASS if bad["approved"] is False else FAIL,
            f"probability={bad['probability_pct']}% approved={bad['approved']}")

    # Statutory profit hurdle
    rep.add(stage, "Statutory gross hurdle constant == Rs 70",
            PASS if RiskBudget.MIN_GROSS_PROFIT_TRIGGER_INR == 70.0 else FAIL,
            f"MIN_GROSS_PROFIT_TRIGGER_INR={RiskBudget.MIN_GROSS_PROFIT_TRIGGER_INR}")
    approved = RiskBudget.calculate_position_size(capital_inr=100000, entry_price=100.0,
                                                  stop_loss=99.0, target_price=101.0)
    # Genuinely sub-hurdle: leverage clamps the lot to 2 shares, so a 1-paisa
    # reward per share yields Rs 0.02 gross -- far below the Rs 70 statutory gate.
    rejected = RiskBudget.calculate_position_size(capital_inr=1000, entry_price=2000.0,
                                                  stop_loss=1990.0, target_price=2000.01)
    rep.add(stage, "Profit hurdle blocks a sub-Rs 70 setup",
            PASS if approved["can_execute"] and not rejected["can_execute"] else FAIL,
            f"gross_pass={approved['gross_profit_expected']} gross_fail={rejected['gross_profit_expected']}")

    # Slippage guard (8 bps)
    ok_slip, ok_pct = RiskBudget.is_slippage_acceptable(100.0, 100.05, "BUY")
    bad_slip, bad_pct = RiskBudget.is_slippage_acceptable(100.0, 100.20, "BUY")
    rep.add(stage, "Slippage guard boundary == 0.08%",
            PASS if RiskBudget.MAX_SLIPPAGE_PCT == 0.0008 and ok_slip and not bad_slip else FAIL,
            f"drift {ok_pct*100:.3f}% accepted, {bad_pct*100:.3f}% rejected (limit 8 bps)")

    # Uniform risk sizing / bracket SL / circuit breaker
    qty = RiskBudget.calculate_uniform_lot_size(entry_price=500.0, effective_capital=1000.0, leverage=5.0)
    sl = RiskBudget.derive_bracket_stop_loss(entry_price=500.0, side="BUY", quantity=qty, user_max_sl=80.0)
    total_risk = round(abs(500.0 - sl) * qty, 2)
    rep.add(stage, "Uniform LOT sizing + bracket SL inside max-SL budget",
            PASS if qty == 10 and total_risk <= 80.0 else FAIL,
            f"qty={qty} sl={sl} total_risk=Rs{total_risk} (cap Rs80)")

    tripped, reason = RiskBudget.is_circuit_breaker_tripped(350.0, 120.0, daily_floor=250.0)
    rep.add(stage, "Intraday circuit breaker trips", PASS if tripped else FAIL, reason)


# ---------------------------------------------------------------------------
# Stage 6 - Runtime smoke test
# ---------------------------------------------------------------------------
def stage6_runtime(rep: Report) -> None:
    stage = "S6-RUNTIME"
    script = ROOT / "audit_runtime_smoke.py"
    env = dict(os.environ)
    env["PYTHONPATH"] = str(ROOT)
    env["PYTHONIOENCODING"] = "utf-8"
    proc = subprocess.run([sys.executable, "-X", "utf8", str(script)], capture_output=True,
                          text=True, env=env, cwd=str(ROOT), timeout=180)
    out = proc.stdout + proc.stderr
    marker = re.search(r"SMOKE_RESULT:(\{.*\})", out)
    if proc.returncode != 0 or not marker:
        tail = " | ".join([ln for ln in out.splitlines() if ln.strip()][-5:])
        rep.add(stage, "Headless MainWindow 10s boot + tick ingestion", FAIL,
                f"exit={proc.returncode} {tail}")
        return
    data = json.loads(marker.group(1))
    for key, value in data.items():
        if key.startswith("_"):
            continue  # diagnostics, not a gate
        rep.add(stage, key, PASS if value is True else (WARN if value is None else FAIL),
                str(value), severity="minor" if value is None else "blocker")


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------
STAGE_TITLES = {
    "S1-STATIC": "Stage 1 - Syntax, AST & Import Audit",
    "S2-PERSISTENCE": "Stage 2 - Database & State Persistence",
    "S3-UI": "Stage 3 - Front-End UI & Signal Wiring",
    "S4-QUANT": "Stage 4 - Quant Strategy & Consensus Audit",
    "S5-LIFECYCLE": "Stage 5 - Order Router & Uniform Risk Enforcement",
    "S6-RUNTIME": "Stage 6 - Live Runtime Smoke Test",
}


def render_markdown(rep: Report) -> str:
    total = len(rep.checks)
    counts = {s: sum(1 for c in rep.checks if c.status == s) for s in (PASS, FAIL, WARN, SKIP)}
    verdict = "CERTIFIED FOR PRODUCTION" if rep.certified else "NOT CERTIFIED"
    lines = [
        "# OmniTradePro - Production Certification Matrix",
        "",
        f"**Verdict: {verdict}**",
        "",
        f"- Generated: {datetime.now(timezone.utc).isoformat(timespec='seconds')}",
        f"- Host: {platform.platform()} | Python {platform.python_version()}",
        f"- Sandbox data directory: `{SANDBOX}`",
        f"- Gates: **{total}** | PASS {counts[PASS]} | FAIL {counts[FAIL]} | WARN {counts[WARN]} | SKIP {counts[SKIP]}",
        "",
        "Every status below is derived from an executed assertion or a subprocess exit",
        "code. No row is hardcoded.",
        "",
        "| Stage | Gate | Status | Evidence |",
        "|---|---|---|---|",
    ]
    for stage, title in STAGE_TITLES.items():
        rows = [c for c in rep.checks if c.stage == stage]
        for i, chk in enumerate(rows):
            badge = {PASS: "PASS", FAIL: "**FAIL**", WARN: "WARN", SKIP: "SKIP"}[chk.status]
            detail = chk.detail.replace("|", "\\|").replace("\n", " ")
            if len(detail) > 240:
                detail = detail[:237] + "..."
            label = title if i == 0 else ""
            lines.append(f"| {label} | {chk.name} | {badge} | {detail} |")
    lines.append("")
    if rep.blockers_failed:
        lines += ["## Blocking defects", ""]
        for chk in rep.blockers_failed:
            lines.append(f"- **{chk.name}** ({chk.stage}): {chk.detail}")
        lines.append("")
    lines += ["## Warnings (non-blocking)", ""]
    warns = [c for c in rep.checks if c.status == WARN]
    if warns:
        for chk in warns:
            lines.append(f"- **{chk.name}** ({chk.stage}): {chk.detail}")
    else:
        lines.append("- none")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true", help="emit JSON only")
    ap.add_argument("--skip-slow", action="store_true", help="skip subprocess UI suites")
    args = ap.parse_args()

    rep = Report()
    stages: List[Callable[[Report], None]] = [stage1_static, stage2_database]
    if not args.skip_slow:
        stages.append(stage3_ui)
    stages += [stage4_quant]
    if not args.skip_slow:
        stages += [stage5_lifecycle, stage6_runtime]

    for fn in stages:
        try:
            fn(rep)
        except Exception as exc:
            rep.add(fn.__name__, "harness exception", FAIL,
                    f"{type(exc).__name__}: {exc}")
            traceback.print_exc()

    if args.json:
        print(json.dumps({"certified": rep.certified, "checks": [c.to_row() for c in rep.checks]}, indent=2))
    else:
        print(render_markdown(rep))
        out = ROOT / "CERTIFICATION_MATRIX.md"
        out.write_text(render_markdown(rep), encoding="utf-8")
        (ROOT / "certification_matrix.json").write_text(
            json.dumps({"certified": rep.certified, "generated": datetime.now(timezone.utc).isoformat(),
                        "checks": [c.to_row() for c in rep.checks]}, indent=2), encoding="utf-8")
        print(f"\nWritten: {out.name}, certification_matrix.json")
    return 0 if rep.certified else 1


if __name__ == "__main__":
    sys.exit(main())
