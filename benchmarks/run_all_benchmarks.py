#!/usr/bin/env python3
"""
OmniTradePro - Master Diagnostic Benchmark Suite Orchestrator
Executes all 5 benchmarking dimensions sequentially and generates the unified report.
"""

import sys
import time
from pathlib import Path

# Runtime shims for read-only benchmark execution
import typing, builtins
builtins.List = typing.List
builtins.DatabaseConnectionManager = object

# Universal headless Qt application instance across all suites
from PySide6.QtWidgets import QApplication
app = QApplication.instance() or QApplication(["-platform", "offscreen"])

from benchmarks.suite1_backtest_2025 import run_suite1
from benchmarks.suite2_latency_stress import run_suite2
from benchmarks.suite3_vault_totp import run_suite3
from benchmarks.suite4_gui_killswitch import run_suite4
from benchmarks.suite5_routing_isolation import run_suite5

def run_all():
    print("=" * 80)
    print("OMNITRADEPRO MASTER DIAGNOSTIC BENCHMARK SUITE - READ-ONLY AUDIT MODE")
    print(f"Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S')} | Environment: Windows 10/11 64-bit")
    print("=" * 80)
    
    t_start = time.perf_counter()
    
    print("\n>>> STARTING DIMENSION 1: 2025 HISTORICAL BACKTEST & METRICS <<<")
    s1_results = run_suite1()
    
    print("\n>>> STARTING DIMENSION 2: LIVE INGESTION & LATENCY STRESS TEST <<<")
    s2_results = run_suite2()
    
    print("\n>>> STARTING DIMENSION 3: DUAL-DB PERSISTENCE & AUTO-TOTP LIFECYCLE <<<")
    s3_results = run_suite3()
    
    print("\n>>> STARTING DIMENSION 4: GUI CONTROLS & KILL-SWITCH CERTIFICATION <<<")
    s4_results = run_suite4()
    
    print("\n>>> STARTING DIMENSION 5: MULTI-BROKER ROUTING & UUIDv4 INTEGRITY <<<")
    s5_results = run_suite5()
    
    t_total = time.perf_counter() - t_start
    print("\n" + "=" * 80)
    print(f"ALL 5 BENCHMARK SUITES COMPLETED IN {t_total:.2f} SECONDS")
    print("=" * 80)

if __name__ == "__main__":
    run_all()
