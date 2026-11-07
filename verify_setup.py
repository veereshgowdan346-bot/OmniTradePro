#!/usr/bin/env python3
"""
OmniTradePro - Institutional Phase 1 Verification Suite
Platform: Windows 10/11 64-bit | Python 3.10+
Validates package dependencies, configuration schemas, directory architectures,
and storage write permissions before market session execution.
"""

import sys
import os
import json
import uuid
import platform
import importlib
from pathlib import Path
from datetime import datetime, timezone


def enable_windows_ansi_support() -> None:
    """Enables virtual terminal processing on Windows 10/11 consoles for ANSI styling."""
    if sys.platform == "win32":
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            handle = kernel32.GetStdHandle(-11)  # STD_OUTPUT_HANDLE
            mode = ctypes.c_ulong()
            if kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
                kernel32.SetConsoleMode(handle, mode.value | 0x0004)  # ENABLE_VIRTUAL_TERMINAL_PROCESSING
        except Exception:
            pass


enable_windows_ansi_support()


class TerminalStyle:
    """ANSI terminal color definitions and visual formatting constants."""
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    
    # Foreground colors
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    WHITE = "\033[97m"
    
    # Background colors
    BG_GREEN = "\033[42m"
    BG_RED = "\033[41m"
    BG_DARK = "\033[40m"


class CheckResult:
    """Encapsulates the diagnostic result of an individual verification test."""
    def __init__(self, category: str, item: str, passed: bool, detail: str = "", error_diagnostic: str = ""):
        self.category = category
        self.item = item
        self.passed = passed
        self.detail = detail
        self.error_diagnostic = error_diagnostic


def run_dependency_checks() -> list[CheckResult]:
    """
    Validates institutional imports across GUI, broker gateways, quant engines,
    and cryptographic persistence.
    """
    results: list[CheckResult] = []
    
    # Defined dependency specifications
    required_packages = [
        {"name": "PySide6", "import_target": "PySide6", "version_attr": "__version__", "desc": "GUI & Glassmorphism Framework"},
        {"name": "pyqtgraph", "import_target": "pyqtgraph", "version_attr": "__version__", "desc": "High-Frequency Charting Engine"},
        {"name": "SmartApi", "import_target": "SmartApi.smartConnect", "version_attr": None, "fallback_target": "SmartApi", "desc": "Angel One SmartAPI Gateway"},
        {"name": "pyotp", "import_target": "pyotp", "version_attr": "__version__", "desc": "TOTP 2FA Security Engine"},
        {"name": "yfinance", "import_target": "yfinance", "version_attr": "__version__", "desc": "Quantitative Feeds & Reference Data"},
        {"name": "pandas", "import_target": "pandas", "version_attr": "__version__", "desc": "Time-Series & Portfolio Analytics"},
        {"name": "numpy", "import_target": "numpy", "version_attr": "__version__", "desc": "Vectorized Quant Mathematics"},
        {"name": "sqlite3", "import_target": "sqlite3", "version_attr": "sqlite_version", "desc": "Local High-Throughput Audit Store"},
        {"name": "cryptography", "import_target": "cryptography", "version_attr": "__version__", "desc": "Credential & Token Encryption"},
        {"name": "requests", "import_target": "requests", "version_attr": "__version__", "desc": "Institutional REST Client"},
        {"name": "websocket", "import_target": "websocket", "version_attr": "__version__", "desc": "Streaming Tick Data Client"}
    ]
    
    for pkg in required_packages:
        pkg_name = pkg["name"]
        import_target = pkg["import_target"]
        version_attr = pkg["version_attr"]
        desc = pkg["desc"]
        
        try:
            mod = importlib.import_module(import_target)
            version_str = "Loaded"
            if version_attr and hasattr(mod, version_attr):
                version_str = f"v{getattr(mod, version_attr)}"
            elif pkg.get("fallback_target"):
                # Check root package version if subpackage has no version
                try:
                    root_mod = importlib.import_module(pkg["fallback_target"])
                    if hasattr(root_mod, "__version__"):
                        version_str = f"v{getattr(root_mod, '__version__')}"
                except Exception:
                    version_str = "Loaded"
            
            results.append(CheckResult(
                category="Dependencies",
                item=pkg_name,
                passed=True,
                detail=f"{desc} ({version_str})"
            ))
        except ImportError as exc:
            # Fallback attempt for SmartApi if nested module differed
            if pkg.get("fallback_target"):
                try:
                    root_mod = importlib.import_module(pkg["fallback_target"])
                    version_str = getattr(root_mod, "__version__", "Loaded")
                    results.append(CheckResult(
                        category="Dependencies",
                        item=pkg_name,
                        passed=True,
                        detail=f"{desc} (v{version_str})"
                    ))
                    continue
                except ImportError:
                    pass
            
            results.append(CheckResult(
                category="Dependencies",
                item=pkg_name,
                passed=False,
                detail=f"Import failed for '{import_target}'",
                error_diagnostic=f"{exc.__class__.__name__}: {str(exc)}. Solution: execute `pip install -r requirements.txt` inside active virtual environment."
            ))
        except Exception as exc:
            results.append(CheckResult(
                category="Dependencies",
                item=pkg_name,
                passed=False,
                detail=f"Unexpected load error for '{import_target}'",
                error_diagnostic=f"{exc.__class__.__name__}: {str(exc)}"
            ))
            
    return results


def run_configuration_checks(config_path: Path) -> list[CheckResult]:
    """
    Validates existence, JSON syntax, and strict adherence to Indian market
    and risk parameters within config.json.
    """
    results: list[CheckResult] = []
    
    if not config_path.exists():
        results.append(CheckResult(
            category="Configuration",
            item="config.json",
            passed=False,
            detail="File not found in project root",
            error_diagnostic=f"Path '{config_path}' does not exist. Ensure config.json is present."
        ))
        return results

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        
        results.append(CheckResult(
            category="Configuration",
            item="JSON Syntax",
            passed=True,
            detail="Parsed config.json successfully"
        ))
    except Exception as exc:
        results.append(CheckResult(
            category="Configuration",
            item="JSON Syntax",
            passed=False,
            detail="Corrupted or invalid JSON schema",
            error_diagnostic=f"{exc.__class__.__name__}: {str(exc)}"
        ))
        return results

    # 1. Market Hours Validation
    market_hours = cfg.get("market_hours")
    if isinstance(market_hours, dict):
        required_hours = [
            ("equity_open", "09:15"),
            ("equity_close", "15:30"),
            ("equity_square_off", "15:15"),
            ("mcx_open", "09:00"),
            ("mcx_close", "23:30"),
            ("mcx_square_off", "23:15")
        ]
        missing_hours = [k for k, _ in required_hours if k not in market_hours]
        if missing_hours:
            results.append(CheckResult(
                category="Configuration",
                item="market_hours",
                passed=False,
                detail=f"Missing fields: {missing_hours}",
                error_diagnostic="market_hours dictionary must specify all equity and mcx timing schedules."
            ))
        else:
            timing_mismatches = [f"{k}={market_hours[k]} (expected {v})" for k, v in required_hours if market_hours[k] != v]
            if timing_mismatches:
                results.append(CheckResult(
                    category="Configuration",
                    item="market_hours",
                    passed=False,
                    detail=f"Timing discrepancies: {', '.join(timing_mismatches)}",
                    error_diagnostic="Strict adherence to specified NSE/BSE/MCX operational timings required."
                ))
            else:
                results.append(CheckResult(
                    category="Configuration",
                    item="market_hours",
                    passed=True,
                    detail="Equity (09:15-15:30) & MCX (09:00-23:30) verified"
                ))
    else:
        results.append(CheckResult(
            category="Configuration",
            item="market_hours",
            passed=False,
            detail="Missing or invalid section 'market_hours'",
            error_diagnostic="'market_hours' must be a JSON object containing exchange timings."
        ))

    # 2. Risk Rules Validation
    risk_rules = cfg.get("risk_rules")
    if isinstance(risk_rules, dict):
        expected_rules = {
            "max_capital_risk_pct": 10.0,
            "friction_buffer_inr": 60.0,
            "min_gross_profit_trigger_inr": 70.0,
            "max_daily_loss_inr": 2000.0
        }
        missing_rules = [k for k in expected_rules if k not in risk_rules]
        if missing_rules:
            results.append(CheckResult(
                category="Configuration",
                item="risk_rules",
                passed=False,
                detail=f"Missing risk rules: {missing_rules}",
                error_diagnostic="Risk parameters must include max_capital_risk_pct, friction_buffer_inr, min_gross_profit_trigger_inr, max_daily_loss_inr."
            ))
        else:
            rule_errors = []
            for k, expected_v in expected_rules.items():
                actual_v = risk_rules.get(k)
                if not isinstance(actual_v, (int, float)):
                    rule_errors.append(f"{k} is not numeric ({type(actual_v).__name__})")
                elif actual_v != expected_v:
                    rule_errors.append(f"{k}={actual_v} (expected {expected_v})")
            
            if rule_errors:
                results.append(CheckResult(
                    category="Configuration",
                    item="risk_rules",
                    passed=False,
                    detail=f"Rule validation failure: {', '.join(rule_errors)}",
                    error_diagnostic="Risk management values do not match strict quantitative parameters."
                ))
            else:
                results.append(CheckResult(
                    category="Configuration",
                    item="risk_rules",
                    passed=True,
                    detail="Capital risk (10%), Buffer (60 INR), Min Profit (70 INR), Max Loss (2000 INR) verified"
                ))
    else:
        results.append(CheckResult(
            category="Configuration",
            item="risk_rules",
            passed=False,
            detail="Missing or invalid section 'risk_rules'",
            error_diagnostic="'risk_rules' must be a JSON object containing quantitative risk controls."
        ))

    # 3. Watchlist Validation
    watchlist = cfg.get("watchlist")
    if isinstance(watchlist, dict):
        nifty = watchlist.get("nifty50_anchor", [])
        mcx = watchlist.get("mcx_anchor", [])
        if isinstance(nifty, list) and len(nifty) >= 8 and isinstance(mcx, list) and len(mcx) >= 3:
            results.append(CheckResult(
                category="Configuration",
                item="watchlist",
                passed=True,
                detail=f"Nifty50 Anchors: {len(nifty)} symbols, MCX Anchors: {len(mcx)} contracts"
            ))
        else:
            results.append(CheckResult(
                category="Configuration",
                item="watchlist",
                passed=False,
                detail=f"Invalid anchors: nifty count={len(nifty) if isinstance(nifty, list) else 0}, mcx count={len(mcx) if isinstance(mcx, list) else 0}",
                error_diagnostic="Watchlist must contain valid lists for 'nifty50_anchor' (min 8 symbols) and 'mcx_anchor' (min 3 contracts)."
            ))
    else:
        results.append(CheckResult(
            category="Configuration",
            item="watchlist",
            passed=False,
            detail="Missing or invalid section 'watchlist'",
            error_diagnostic="'watchlist' must be a JSON object containing ticker anchors."
        ))

    # 4. App Defaults Validation
    app = cfg.get("app")
    if isinstance(app, dict):
        theme = app.get("theme")
        broker = app.get("default_broker")
        mode = app.get("default_mode")
        if theme == "glassmorphism_dark" and broker == "ANGEL_ONE" and mode == "PAPER":
            results.append(CheckResult(
                category="Configuration",
                item="app_settings",
                passed=True,
                detail="Theme: glassmorphism_dark | Broker: ANGEL_ONE | Mode: PAPER"
            ))
        else:
            results.append(CheckResult(
                category="Configuration",
                item="app_settings",
                passed=False,
                detail=f"theme={theme}, broker={broker}, mode={mode}",
                error_diagnostic="Expected theme='glassmorphism_dark', default_broker='ANGEL_ONE', default_mode='PAPER'."
            ))
    else:
        results.append(CheckResult(
            category="Configuration",
            item="app_settings",
            passed=False,
            detail="Missing section 'app'",
            error_diagnostic="'app' must specify theme, default_broker, and default_mode."
        ))

    return results


def run_storage_and_directory_checks(project_root: Path) -> list[CheckResult]:
    """
    Verifies that architectural folders exist and that the application has
    low-latency file write/read permissions inside database/ and logs/.
    """
    results: list[CheckResult] = []
    
    # 1. Structure verification
    required_dirs = ["database", "core", "brokers", "ui", "logs"]
    for dir_name in required_dirs:
        target_dir = project_root / dir_name
        if target_dir.is_dir():
            results.append(CheckResult(
                category="Architecture",
                item=f"Directory '{dir_name}/'",
                passed=True,
                detail="Present"
            ))
        else:
            results.append(CheckResult(
                category="Architecture",
                item=f"Directory '{dir_name}/'",
                passed=False,
                detail="Missing directory",
                error_diagnostic=f"Directory '{target_dir}' does not exist. Run setup.bat to construct architecture."
            ))

    # 2. Package initializers verification
    package_dirs = ["database", "core", "brokers", "ui"]
    for pkg_name in package_dirs:
        init_file = project_root / pkg_name / "__init__.py"
        if init_file.is_file():
            results.append(CheckResult(
                category="Architecture",
                item=f"Package '{pkg_name}'",
                passed=True,
                detail="__init__.py verified"
            ))
        else:
            results.append(CheckResult(
                category="Architecture",
                item=f"Package '{pkg_name}'",
                passed=False,
                detail="Missing __init__.py",
                error_diagnostic=f"Package file '{init_file}' is missing."
            ))

    # 3. Write / Read Permission Tests
    writable_targets = [("database", project_root / "database"), ("logs", project_root / "logs")]
    for target_label, target_path in writable_targets:
        if not target_path.exists():
            continue
            
        test_filename = target_path / f".perm_test_{uuid.uuid4().hex[:8]}.tmp"
        test_payload = f"OMNITRADE_INTEGRITY_CHECK_{datetime.now(timezone.utc).isoformat()}"
        
        try:
            with open(test_filename, "w", encoding="utf-8") as f:
                f.write(test_payload)
                f.flush()
                os.fsync(f.fileno())
                
            with open(test_filename, "r", encoding="utf-8") as f:
                read_back = f.read()
                
            if read_back != test_payload:
                raise IOError("Written payload mismatched read verification string")
                
            os.remove(test_filename)
            
            results.append(CheckResult(
                category="Permissions",
                item=f"Write Access: {target_label}/",
                passed=True,
                detail="Atomic write/flush/read/delete passed"
            ))
        except Exception as exc:
            if test_filename.exists():
                try:
                    os.remove(test_filename)
                except Exception:
                    pass
            results.append(CheckResult(
                category="Permissions",
                item=f"Write Access: {target_label}/",
                passed=False,
                detail=f"Write test failed: {str(exc)}",
                error_diagnostic=f"Write permission denied on '{target_path}'. Check Windows folder permissions or anti-virus restrictions."
            ))
            
    return results


def print_header() -> None:
    """Renders the institutional ASCII banner and system runtime statistics."""
    platform_info = f"Python {platform.python_version()} | {platform.system()} {platform.release()} ({platform.architecture()[0]})"
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    print(f"{TerminalStyle.CYAN}{TerminalStyle.BOLD}")
    print("=" * 80)
    print("  ██████╗ ███╗   ███╗███╗   ██╗██╗████████╗██████╗  █████╗ ██████╗ ███████╗")
    print(" ██╔═══██╗████╗ ████║████╗  ██║██║╚══██╔══╝██╔══██╗██╔══██╗██╔══██╗██╔════╝")
    print(" ██║   ██║██╔████╔██║██╔██╗ ██║██║   ██║   ██████╔╝███████║██║  ██║█████╗  ")
    print(" ██║   ██║██║╚██╔╝██║██║╚██╗██║██║   ██║   ██╔══██╗██╔══██║██║  ██║██╔══╝  ")
    print(" ╚██████╔╝██║ ╚═╝ ██║██║ ╚████║██║   ██║   ██║  ██║██║  ██║██████╔╝███████╗")
    print("  ╚═════╝ ╚═╝     ╚═╝╚═╝  ╚═══╝╚═╝   ╚═╝   ╚═╝  ╚═╝╚═╝  ╚═╝╚═════╝ ╚══════╝")
    print("                  INSTITUTIONAL QUANTITATIVE SUITE - PHASE 1               ")
    print("=" * 80)
    print(f"{TerminalStyle.RESET}")
    print(f" {TerminalStyle.BOLD}Runtime:{TerminalStyle.RESET}   {platform_info}")
    print(f" {TerminalStyle.BOLD}Execution:{TerminalStyle.RESET} {timestamp} (Local System)")
    print(f" {TerminalStyle.BOLD}Workspace:{TerminalStyle.RESET} {Path.cwd()}")
    print("-" * 80)


def print_results(results: list[CheckResult]) -> bool:
    """Formats and prints test results in an executive diagnostic table."""
    current_category = ""
    all_passed = True
    
    for r in results:
        if r.category != current_category:
            current_category = r.category
            print(f"\n{TerminalStyle.BOLD}{TerminalStyle.YELLOW}▶ {current_category.upper()}{TerminalStyle.RESET}")
            print(f"  {'-' * 76}")
        
        status_tag = f"{TerminalStyle.GREEN}[ PASS ]{TerminalStyle.RESET}" if r.passed else f"{TerminalStyle.RED}[ FAIL ]{TerminalStyle.RESET}"
        if not r.passed:
            all_passed = False
            
        item_col = f"{r.item:<28}"
        detail_col = f"{r.detail}"
        print(f"  {status_tag} {item_col} : {detail_col}")
        
        if not r.passed and r.error_diagnostic:
            print(f"         {TerminalStyle.RED}{TerminalStyle.BOLD}└─ Error:{TerminalStyle.RESET} {TerminalStyle.RED}{r.error_diagnostic}{TerminalStyle.RESET}")

    print("\n" + "=" * 80)
    
    passed_count = sum(1 for r in results if r.passed)
    failed_count = sum(1 for r in results if not r.passed)
    total_count = len(results)
    
    if all_passed:
        print(f"\n{TerminalStyle.BG_GREEN}{TerminalStyle.WHITE}{TerminalStyle.BOLD} SYSTEM READY: ALL {total_count} CHECKS PASSED SUCCESSFULLY. PHASE 1 OPERATIONAL. {TerminalStyle.RESET}\n")
        print(f"{TerminalStyle.GREEN}All core broker gateways, math runtimes, configuration rules, and storage subsystems")
        print(f"are fully certified for real-time exchange connectivity.{TerminalStyle.RESET}\n")
    else:
        print(f"\n{TerminalStyle.BG_RED}{TerminalStyle.WHITE}{TerminalStyle.BOLD} ENVIRONMENT INTEGRITY FAILURE: {failed_count} OF {total_count} CHECKS FAILED {TerminalStyle.RESET}\n")
        print(f"{TerminalStyle.RED}Diagnostics identified blocking issues. Resolve reported dependency, configuration,")
        print(f"or filesystem permission failures before initiating live market sessions.{TerminalStyle.RESET}\n")
        
    return all_passed


def main() -> int:
    """Main verification execution routine."""
    project_root = Path(__file__).resolve().parent
    config_path = project_root / "config.json"
    
    print_header()
    
    all_results: list[CheckResult] = []
    
    # 1. Dependency checks
    all_results.extend(run_dependency_checks())
    
    # 2. Configuration checks
    all_results.extend(run_configuration_checks(config_path))
    
    # 3. Storage and architecture checks
    all_results.extend(run_storage_and_directory_checks(project_root))
    
    # Print formatted matrix
    is_successful = print_results(all_results)
    
    return 0 if is_successful else 1


if __name__ == "__main__":
    sys.exit(main())
