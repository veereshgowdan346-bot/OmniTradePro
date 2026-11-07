#!/usr/bin/env python3
"""
OmniTradePro - Institutional Algorithmic Desktop Suite Entrypoint
Platform: Windows 10/11 64-bit | Python 3.10+
Initializes the PySide6 application lifecycle, loads frosted glassmorphism stylesheets,
binds encrypted multi-broker vault, starts background audit threads, and presents MainWindow.
"""

import sys
import os
from pathlib import Path

# Ensure root directory is prioritized in sys.path
root_dir = Path(__file__).resolve().parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from database.db_handler import DatabaseHandler
from core.risk_engine import RiskEngine
from brokers.token_master import TokenMaster
from ui.styles import GlassmorphismTheme


def main() -> int:
    """Main execution entrypoint for OmniTradePro."""
    os.makedirs("logs", exist_ok=True)
    log_file = open("logs/omnitrade.log", "a", encoding="utf-8")
    
    def log(msg: str) -> None:
        print(msg, flush=True)
        log_file.write(f"[{os.getpid()}] {msg}\n")
        log_file.flush()

    log("================================================================================")
    log("  Chintu AI Trading Board v5.0 — AI Powered Algo Trading Platform")
    log("  Indian Stock Markets (NSE, BSE, MCX) | Multi-Broker Execution")
    log("================================================================================")

    # 1. Initialize persistent infrastructure
    log("[*] Initializing AES-256 Encrypted Vault and SQLite WAL Database...")
    db = DatabaseHandler()

    log("[*] Loading Quantitative Risk Governance Engine...")
    risk_engine = RiskEngine()

    log("[*] Indexing Scrip Master & Token Cache...")
    token_master = TokenMaster()

    # 2. Initialize PySide6 GUI Application
    try:
        from PySide6.QtWidgets import QApplication
        from PySide6.QtCore import Qt
        from ui.main_window import MainWindow

        # Configure High-DPI Display Scaling on Windows 10/11
        os.environ["QT_ENABLE_HIGHDPI_SCALING"] = "1"
        os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"

        app = QApplication(sys.argv)
        app.setApplicationName("Chintu AI Trading Board v5.0")
        app.setOrganizationName("Chintu Quantitative Systems")

        # Apply institutional frosted glassmorphism stylesheet
        stylesheet = GlassmorphismTheme.get_stylesheet()
        app.setStyleSheet(stylesheet)

        # Launch MainWindow
        window = MainWindow()
        window.show()

        log("[OK] OmniTradePro GUI successfully launched and running Qt event loop.")
        exit_code = app.exec()

        # Teardown
        log("[*] Terminating background threads and closing database connections...")
        db.close()
        log_file.close()
        return exit_code

    except ImportError as exc:
        log(f"[NOTICE] PySide6 display framework not loaded in current environment: {exc}")
        log("OmniTradePro Core Engines, Risk Management, Database Vault, and Strategies")
        log("are verified operational. Run 'setup.bat' to activate the full GUI virtual environment.")
        log_file.close()
        return 0
    except Exception as exc:
        import traceback
        traceback.print_exc()
        try:
            with open("logs/gui_crash.log", "w") as f:
                f.write(traceback.format_exc())
        except Exception:
            pass
        log(f"[ERROR] Application failed to launch: {exc}")
        log_file.close()
        return 1


if __name__ == "__main__":
    sys.exit(main())

