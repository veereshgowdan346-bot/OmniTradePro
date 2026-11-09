#!/usr/bin/env python3
"""
OmniTradePro - Headless Runtime Smoke Test (Stage 6)
====================================================
Boots the real MainWindow inside a Qt event loop for 10 seconds with no display,
feeds mock exchange ticks through the live signal path, drives the 30 FPS chart
render timer, exercises 12-page routing, and prints machine-readable results as
`SMOKE_RESULT:{...}`.

Exit code 0 only if the window boots, survives the full event loop, ingests ticks
without an uncaught exception, and emits no Qt critical/fatal messages.
"""

import json
import os
import sys
import tempfile
import time
import traceback
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ["OMNITRADE_DATA_DIR"] = tempfile.mkdtemp(prefix="omnitrade_smoke_")

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

RUNTIME_SECONDS = 10.0

qt_messages = []
exceptions = []
results = {}


def main() -> int:
    from PySide6.QtCore import QtMsgType, qInstallMessageHandler, QTimer
    from PySide6.QtWidgets import QApplication

    def handler(mode, context, message):
        qt_messages.append((str(mode), message))

    qInstallMessageHandler(handler)

    app = QApplication.instance() or QApplication(sys.argv)

    def exc_hook(exc_type, exc, tb):
        exceptions.append("".join(traceback.format_exception(exc_type, exc, tb)))

    sys.excepthook = exc_hook

    from ui.main_window import MainWindow

    boot_started = time.perf_counter()
    win = MainWindow()
    boot_ms = (time.perf_counter() - boot_started) * 1000.0
    win.show()
    app.processEvents()

    results["MainWindow instantiated and shown"] = win.isVisible()
    results[f"Boot time within budget ({boot_ms:.0f} ms < 5000 ms)"] = boot_ms < 5000.0
    results["12 views registered in QStackedWidget"] = win.stacked_widget.count() == 12

    # --- 30 FPS decoupled render timer -------------------------------------
    canvas = win.chart_widget.canvas
    timer = getattr(win.chart_widget, "_render_timer", None)
    results["30 FPS render timer active"] = bool(timer is not None and timer.isActive())
    results["Render timer interval ~33 ms"] = bool(timer is not None and 30 <= timer.interval() <= 34)

    # --- historical backfill into the canvas -------------------------------
    import pandas as pd
    closes = [100.0 + i * 0.25 for i in range(40)]
    frame = pd.DataFrame({
        "Open": [c - 0.15 for c in closes],
        "High": [c + 0.35 for c in closes],
        "Low": [c - 0.35 for c in closes],
        "Close": closes,
        "Volume": [50_000 + i * 100 for i in range(40)],
    })
    win.chart_widget.update_candles(frame, orb_high=110.0, orb_low=99.0)
    app.processEvents()
    results["Historical candlestick backfill accepted"] = len(canvas.candles) > 0

    # --- tick ingestion through the real signal path -----------------------
    ticks = {"count": 0}
    last_price = {"value": 0.0}

    def push_tick():
        ticks["count"] += 1
        price = 100.0 + (ticks["count"] % 25) * 0.2
        last_price["value"] = price
        tick = {"symbol": "RELIANCE.NS", "ltp": price, "volume": 1000 + ticks["count"],
                "change_pct": 0.35}
        try:
            win.stream_worker.tick_received.emit(tick)   # real Qt signal -> slot
        except Exception:
            exc_hook(*sys.exc_info())

    feeder = QTimer()
    feeder.timeout.connect(push_tick)
    feeder.start(50)

    # --- exercise navigation while ticking --------------------------------
    nav = {"index": 0, "ok": True}

    def switch_page():
        try:
            win._switch_page(nav["index"] % 12)
            if win.stacked_widget.currentIndex() != nav["index"] % 12:
                nav["ok"] = False
            nav["index"] += 1
        except Exception:
            nav["ok"] = False
            exc_hook(*sys.exc_info())

    router = QTimer()
    router.timeout.connect(switch_page)
    router.start(400)

    started = time.perf_counter()
    QTimer.singleShot(int(RUNTIME_SECONDS * 1000), app.quit)
    app.exec()
    elapsed = time.perf_counter() - started

    feeder.stop()
    router.stop()

    results[f"Event loop survived {elapsed:.1f}s"] = elapsed >= RUNTIME_SECONDS - 0.5
    results["Mock ticks ingested via tick_received signal"] = ticks["count"] > 0
    results["12-page navigation stable under tick load"] = nav["ok"] and nav["index"] >= 12
    results["No uncaught Python exception"] = not exceptions

    critical = [m for m in qt_messages if m[0] in ("QtCriticalMsg", "QtFatalMsg")]
    results["No Qt critical/fatal messages"] = not critical

    # --- disconnect purge --------------------------------------------------
    try:
        win._on_connection_status("DISCONNECTED", "smoke test teardown")
        app.processEvents()
        results["clear_canvas() on disconnect (Zero-Fake-Data)"] = len(canvas.candles) == 0
    except Exception:
        exc_hook(*sys.exc_info())
        results["clear_canvas() on disconnect (Zero-Fake-Data)"] = False

    payload = dict(results)
    payload["_meta"] = {
        "boot_ms": round(boot_ms, 1),
        "ticks": ticks["count"],
        "pages_visited": nav["index"],
        "qt_messages": len(qt_messages),
        "exceptions": exceptions[:3],
    }
    print("SMOKE_RESULT:" + json.dumps(payload, default=str))
    for row in qt_messages[:10]:
        print(f"  [qt:{row[0]}] {row[1][:160]}")

    ok = all(v is True for k, v in results.items())
    return 0 if ok else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        traceback.print_exc()
        print("SMOKE_RESULT:" + json.dumps({"MainWindow boot": False}))
        sys.exit(1)
