#!/usr/bin/env python3
"""
OmniTradePro - Institutional Financial Candlestick & Volume Chart Engine
Platform: Windows 10/11 64-bit | Python 3.10+
High-performance TradingView-grade canvas:
- Precision OHLC candlesticks with 1px wicks (#10b981 Bull / #ef4444 Bear)
- Dynamic 10% geometric price padding preventing clipping or erratic bounces
- Smooth antialiased curves for VWAP (#00e5ff), EMA 9 (#fbbf24), and EMA 21 (#818cf8)
- Interactive crosshair, dynamic Y-axis price pill, X-axis time pill, and live OHLCV readout
- Proportional volume sub-panel in bottom 18% of canvas
- Double-buffered 60 FPS flicker-free tick ingestion
- Deterministic historical seed candles on startup (no blank black void)
"""

import math
import os
import random
import threading
from typing import Optional, List, Dict, Any
import numpy as np
import pandas as pd

try:
    from PySide6.QtWidgets import (
        QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QPushButton, QFrame
    )
    from PySide6.QtCore import Qt, QRectF, QPointF, QThread, QObject, Signal
    from PySide6.QtGui import (
        QPainter, QColor, QPen, QBrush, QFont
    )
except ImportError:
    class QWidget:
        def __init__(self, parent=None):
            self._parent = parent
            self._w = 900
            self._h = 500
        def setStyleSheet(self, s): pass
        def setProperty(self, k, v): pass
        def setMinimumHeight(self, h): self._h = max(self._h, h)
        def setMouseTracking(self, b): pass
        def update(self): pass
        def setLayout(self, l): pass
        def width(self): return self._w
        def height(self): return self._h
    class QFrame(QWidget): pass
    class QThread:
        """Minimal stand-in: runs the body inline when Qt is unavailable."""
        def __init__(self, *args, **kwargs): pass
        def start(self): self.run()
        def run(self): pass
        def isRunning(self): return False
        def wait(self, *args): return True
        def quit(self): pass
    class QObject:
        def __init__(self, *args, **kwargs): pass
    class Signal:
        def __init__(self, *args): self._cbs = []
        def connect(self, cb): self._cbs.append(cb)
        def emit(self, *args):
            for cb in list(self._cbs):
                try: cb(*args)
                except Exception: pass
    class QVBoxLayout:
        def __init__(self, *args): pass
        def addWidget(self, w, *args): pass
        def addLayout(self, l, *args): pass
        def setContentsMargins(self, *args): pass
        def setSpacing(self, s): pass
        def addSpacing(self, s): pass
        def addStretch(self, *args): pass
    class QHBoxLayout(QVBoxLayout): pass
    class _TextStr(str):
        def __call__(self): return str(self)
    class QLabel:
        def __init__(self, text="", parent=None): self.text = _TextStr(text)
        def setText(self, t): self.text = _TextStr(t)
        def setStyleSheet(self, s): pass
        def setAlignment(self, a): pass
        def setProperty(self, k, v): pass
    class QComboBox:
        def __init__(self, parent=None):
            self._items = []
            self._curr = 0
            self.currentTextChanged = Signal()
        def addItems(self, items): self._items.extend(items)
        def currentText(self): return self._items[self._curr] if self._items else "RELIANCE.NS"
        def setStyleSheet(self, s): pass
        def setProperty(self, k, v): pass
    class QPushButton:
        def __init__(self, text="", parent=None):
            self.text = text
            self._checked = False
            self.clicked = Signal()
        def setText(self, t): self.text = t
        def setStyleSheet(self, s): pass
        def setProperty(self, k, v): pass
        def setCheckable(self, b): pass
        def setChecked(self, b): self._checked = bool(b)
        def isChecked(self): return self._checked
    class QPointF:
        def __init__(self, x=0.0, y=0.0):
            self._x = float(x)
            self._y = float(y)
        def x(self): return self._x
        def y(self): return self._y
    class QRectF:
        def __init__(self, x=0.0, y=0.0, w=0.0, h=0.0):
            self._x, self._y, self._w, self._h = float(x), float(y), float(w), float(h)
        def x(self): return self._x
        def y(self): return self._y
        def width(self): return self._w
        def height(self): return self._h
        def contains(self, pt):
            px = pt.x() if hasattr(pt, "x") else pt[0]
            py = pt.y() if hasattr(pt, "y") else pt[1]
            return self._x <= px <= self._x + self._w and self._y <= py <= self._y + self._h
    class QColor:
        def __init__(self, *args): pass
        def setAlpha(self, a): pass
    class QPen:
        def __init__(self, *args): pass
    class QBrush:
        def __init__(self, *args): pass
    class QFont:
        Bold = 75
        def __init__(self, *args): pass
    class QPainter:
        Antialiasing = 1
        def __init__(self, *args): pass
        def setRenderHint(self, h): pass
        def setPen(self, p): pass
        def setBrush(self, b): pass
        def setFont(self, f): pass
        def drawLine(self, *args): pass
        def drawRect(self, *args): pass
        def drawRoundedRect(self, *args): pass
        def drawText(self, *args): pass
        def end(self): pass
    class Qt:
        AlignCenter = 0x0004
        AlignLeft = 0x0001
        AlignRight = 0x0002
        AlignVCenter = 0x0080
        DotLine = 3
        DashLine = 2
        SolidLine = 1
        NoPen = 0


# ---------------------------------------------------------------------------
# Module-level helper: deterministic realistic intraday candle seed generator
# ---------------------------------------------------------------------------

def _generate_seed_candles(symbol: str, n: int = 80):
    """
    Generates *n* realistic OHLCV 5-minute intraday candles using a seeded
    random walk anchored to a realistic base price for the given instrument.

    Returns
    -------
    tuple[list[dict], list[str]]
        (candles, times) where each candle has keys
        ``{"open", "high", "low", "close", "volume"}`` and times is a
        parallel list of ``"HH:MM"`` strings starting from 09:15 IST.
    """
    # --- Base price determination ---
    sym_up = symbol.upper()
    if "BANKNIFTY" in sym_up or ("BANK" in sym_up and "NIFTY" in sym_up):
        base = 51200.0
    elif "FINNIFTY" in sym_up:
        base = 23400.0
    elif "SENSEX" in sym_up:
        base = 81500.0
    elif "NIFTY" in sym_up:
        base = 24800.0
    elif "CRUDE" in sym_up:
        base = 6420.0
    elif "GOLD" in sym_up:
        base = 73500.0
    elif "SILVER" in sym_up:
        base = 90000.0
    else:
        base = 1490.0  # generic equity fallback

    # Deterministic seed so the chart looks the same every time for a symbol
    random.seed(hash(symbol) % (2 ** 31))

    candles: List[Dict[str, float]] = []
    times: List[str] = []

    # Market open: 09:15 IST
    hour = 9
    minute = 15
    prev_close = base

    for i in range(n):
        # --- Time label ---
        times.append(f"{hour:02d}:{minute:02d}")
        minute += 5
        if minute >= 60:
            minute -= 60
            hour += 1

        # --- Price walk ---
        body_pct = random.uniform(0.0015, 0.0035)   # 0.15–0.35 % body
        direction = 1 if random.random() > 0.48 else -1  # slight bullish bias
        wick_pct = random.uniform(0.0008, 0.0018)   # 0.08–0.18 % wick extension

        o = prev_close
        drift = o * body_pct * direction
        c = o + drift

        # High/low include body + wick extensions (always correct side)
        upper_wick = abs(o if direction > 0 else c) * wick_pct
        lower_wick = abs(c if direction > 0 else o) * wick_pct
        h = max(o, c) + upper_wick
        l = min(o, c) - lower_wick

        # Clamp to avoid negative / zero prices
        l = max(l, base * 0.80)

        # --- Volume ---
        vol = random.uniform(8000, 45000)
        if i < 15:
            vol *= random.uniform(1.4, 2.2)   # higher volume near open

        candles.append({
            "open":   round(o, 2),
            "high":   round(h, 2),
            "low":    round(l, 2),
            "close":  round(c, 2),
            "volume": round(vol, 0),
        })
        prev_close = c

    return candles, times


class _BackfillSignals(QObject):
    """Qt-side bridge for background backfill results (queued to the UI thread)."""

    loaded = Signal(int, object)   # (request_seq, dataframe)
    failed = Signal(int, str)      # (request_seq, error)


class _BackfillWorker:
    """
    Fetches *real* historical candles for a symbol on a daemon thread.

    Zero-Fake-Data: the provider is a caller-supplied callable that must return
    an authentic OHLCV ``pandas.DataFrame`` (DatetimeIndex + Open/High/Low/
    Close/Volume). When no provider is wired, nothing is drawn — the canvas
    stays in its explicit "Awaiting Feed" state rather than inventing candles.

    A daemon thread (not a QThread) is used deliberately: a slow provider must
    never keep the interpreter alive or abort shutdown, and results are still
    marshalled onto the UI thread through ``_BackfillSignals``.
    """

    def __init__(self, provider, symbol: str, timeframe: str, seq: int,
                 signals: "_BackfillSignals") -> None:
        self._provider = provider
        self._symbol = symbol
        self._timeframe = timeframe
        self._seq = seq
        self._signals = signals
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        self._thread = threading.Thread(
            target=self._run, name=f"backfill-{self._symbol}", daemon=True
        )
        self._thread.start()

    def is_alive(self) -> bool:
        return bool(self._thread and self._thread.is_alive())

    def join(self, timeout: float) -> None:
        if self._thread is not None:
            self._thread.join(timeout)

    def _run(self) -> None:  # daemon thread entry point
        try:
            df = self._provider(self._symbol, self._timeframe)
        except Exception as exc:  # provider/network failure -> no candles drawn
            try:
                self._signals.failed.emit(self._seq, str(exc))
            except Exception:
                pass
            return
        try:
            self._signals.loaded.emit(self._seq, df)
        except Exception:
            pass


class CandleCanvas(QWidget):
    """
    Hardware-accelerated TradingView-grade Candlestick & Volume Chart Canvas.
    - Full 60 FPS double-buffered rendering
    - Dynamic geometric auto-scaling with 10% vertical padding
    - Capped candle bodies (never deformed across screen width)
    - Precision VWAP, EMA 9, EMA 21 overlays
    - Interactive crosshair with real-time price & time projection pills
    """

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.parent_widget = parent
        self.setMinimumHeight(280)
        self.setMouseTracking(True)

        self.is_connected: bool = False
        self.candles: List[Dict[str, float]] = []
        self.times: List[str] = []

        # Technical indicator series
        self.ema9: List[float] = []
        self.ema21: List[float] = []
        self.ema20: List[float] = []
        self.ema50: List[float] = []
        self.vwap: List[float] = []
        self.current_price: float = 0.0

        # ── Damped Y-axis scale state ──────────────────────────────────────
        self._scale_min: float = 0.0        # Current rendered Y-axis floor
        self._scale_max: float = 0.0        # Current rendered Y-axis ceiling
        self._scale_dirty: bool = False     # True when candle data has changed and needs repaint

        # ── 30 FPS render timer (set up in ChartWidget, not here) ─────────
        # Data mutations mark _scale_dirty=True; the timer drives update()

        # Viewport and interaction
        self.mouse_pos: Optional[QPointF] = None
        self.show_vwap: bool = True
        self.show_ema: bool = True
        self.show_volume: bool = True

        try:
            self.setAttribute(Qt.WA_OpaquePaintEvent)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Damped Y-axis scale computation
    # ------------------------------------------------------------------

    def _compute_scale(self) -> tuple:
        """
        Computes a stable, hysteresis-damped Y-axis [min, max] from the
        current candle set.

        Algorithm:
        1. Find raw_min/raw_max across all visible candle highs/lows.
        2. Apply a fixed 15% headroom pad above and below.
        3. Snap both bounds to the nearest ₹5 quantum step to suppress
           sub-step micro-oscillations.
        4. Only expand (never contract) the current rendered scale unless
           the new raw range differs from the existing scale by more than
           2% — this is the hysteresis gate that kills bouncing.
        """
        if not self.candles:
            return (0.0, 1.0)

        raw_min = min(c["low"]  for c in self.candles)
        raw_max = max(c["high"] for c in self.candles)
        span    = raw_max - raw_min if raw_max > raw_min else max(raw_max * 0.01, 1.0)

        pad        = span * 0.15          # 15% headroom padding
        target_min = raw_min - pad
        target_max = raw_max + pad

        # ── Quantum snapping: round DOWN for floor, UP for ceiling ──────
        step = 5.0 if span > 50 else 1.0   # ₹5 step for large spans, ₹1 for small
        target_min = math.floor(target_min / step) * step
        target_max = math.ceil(target_max  / step) * step

        # ── Hysteresis gate: only update scale if breach > 2% ───────────
        if self._scale_min == 0.0 and self._scale_max == 0.0:
            # First population — accept immediately
            return (target_min, target_max)

        current_range = max(self._scale_max - self._scale_min, 1.0)
        expand_min    = target_min < self._scale_min - current_range * 0.02
        expand_max    = target_max > self._scale_max + current_range * 0.02

        new_min = target_min if expand_min else self._scale_min
        new_max = target_max if expand_max else self._scale_max

        return (new_min, new_max)

    # ------------------------------------------------------------------
    # Historical seed population
    # ------------------------------------------------------------------

    def seed_historical(self, symbol: str, n: int = 80) -> None:
        """
        LEGACY / NOT USED BY PRODUCTION PATHS.

        Superseded by ``ChartWidget.set_history_provider()`` +
        ``ChartWidget.request_backfill()``, which load authentic candles. Kept
        only so historical callers do not break; nothing in the live terminal
        invokes it any more (Zero-Fake-Data policy).

        Populates the canvas with *n* deterministically generated realistic
        intraday seed candles for *symbol* so the chart is never blank on
        startup.  ``is_connected`` is left False — the first live tick will
        clear these and begin real aggregation.

        Parameters
        ----------
        symbol : str
            Instrument name used to pick a realistic base price and to seed
            the PRNG for reproducibility.
        n : int, optional
            Number of 5-minute candles to generate (default 80).
        """
        candles, times = _generate_seed_candles(symbol, n)
        self.candles      = candles
        self.times        = times
        self._scale_min   = 0.0   # Reset so _compute_scale accepts fresh bounds
        self._scale_max   = 0.0
        self._scale_dirty = True
        self._calculate_indicators()
        self.update()
        self.is_connected = False   # still seed data, not live

    def _calculate_indicators(self) -> None:
        """Calculates authentic VWAP, EMA 9, EMA 21, EMA 20, and EMA 50 series."""
        if not self.candles:
            self.ema9 = []
            self.ema21 = []
            self.ema20 = []
            self.ema50 = []
            self.vwap = []
            return

        closes = pd.Series([c["close"] for c in self.candles], dtype=float)
        highs = pd.Series([c["high"] for c in self.candles], dtype=float)
        lows = pd.Series([c["low"] for c in self.candles], dtype=float)
        volumes = pd.Series([c.get("volume", 1000.0) for c in self.candles], dtype=float)

        # EMAs
        self.ema9 = closes.ewm(span=min(9, len(closes)), adjust=False).mean().tolist()
        self.ema21 = closes.ewm(span=min(21, len(closes)), adjust=False).mean().tolist()
        self.ema20 = closes.ewm(span=min(20, len(closes)), adjust=False).mean().tolist()
        self.ema50 = closes.ewm(span=min(50, len(closes)), adjust=False).mean().tolist()

        # Institutional Intraday VWAP: Cumulative(Typical Price * Volume) / Cumulative(Volume)
        typical_price = (highs + lows + closes) / 3.0
        cum_pv = (typical_price * volumes).cumsum()
        cum_vol = volumes.cumsum()
        cum_vol_safe = cum_vol.replace(0, 1.0)
        self.vwap = (cum_pv / cum_vol_safe).tolist()

        if self.candles:
            self.current_price = self.candles[-1]["close"]

    def update_tick(self, ltp: float) -> None:
        """
        Ingests a live exchange tick into the in-memory candle array.
        Does NOT trigger a repaint — the 30 FPS render timer does that.
        """
        if ltp <= 0:
            return

        # Transition seed → live on first real tick
        if not self.is_connected:
            self.candles = []
            self.times   = []
            self._scale_min = 0.0
            self._scale_max = 0.0
            self.is_connected = True

        self.current_price = ltp

        if not self.candles:
            self.candles.append({
                "open": ltp, "high": ltp, "low": ltp,
                "close": ltp, "volume": 1000.0
            })
            self.times.append("Now")
        else:
            last = self.candles[-1]
            last["close"] = ltp
            if ltp > last["high"]: last["high"] = ltp
            if ltp < last["low"]:  last["low"]  = ltp
            last["volume"] += 50.0

        self._scale_dirty = True   # Signal render timer — do NOT call update() here

    def set_historical_data(self, df: pd.DataFrame) -> None:
        """Populates canvas with authentic historical candle dataframe."""
        if df.empty or "Close" not in df.columns:
            return
        self.is_connected = True
        new_candles = []
        self.times = []
        for idx, row in df.iterrows():
            c_val = float(row["Close"])
            o_val = float(row.get("Open", c_val))
            h_val = float(row.get("High", max(o_val, c_val)))
            l_val = float(row.get("Low", min(o_val, c_val)))
            v_val = float(row.get("Volume", 1500.0))
            new_candles.append({
                "open": o_val,
                "high": h_val,
                "low": l_val,
                "close": c_val,
                "volume": v_val
            })
            time_str = str(idx)
            if len(time_str) >= 16:
                self.times.append(time_str[11:16])
            else:
                self.times.append(f"{len(new_candles)}m")

        self.candles = new_candles
        self._scale_min = 0.0
        self._scale_max = 0.0
        self._scale_dirty = True
        self._calculate_indicators()
        self.update()

    def mouseMoveEvent(self, event) -> None:
        """Updates crosshair coordinates and triggers live hover tooltip."""
        try:
            pos = event.position() if hasattr(event, "position") else event.pos()
            self.mouse_pos = QPointF(pos.x(), pos.y())
            self._update_hover_info()
            self.update()
        except Exception:
            pass

    def leaveEvent(self, event) -> None:
        """Clears crosshair when mouse leaves canvas and restores latest tick metrics."""
        self.mouse_pos = None
        if self.parent_widget and hasattr(self.parent_widget, "restore_default_ohlc"):
            try:
                self.parent_widget.restore_default_ohlc()
            except Exception:
                pass
        self.update()

    def _update_hover_info(self) -> None:
        """Transmits hovered candle data to top information bar."""
        if not self.mouse_pos or not self.candles:
            return
        w = self.width()
        left = 12.0
        right = 72.0
        chart_w = max(100.0, w - left - right)
        n = len(self.candles)

        # Slot layout math matching paintEvent
        if n <= 35:
            slot_w = min(18.0, chart_w / max(1, n))
            start_x = max(left, left + chart_w - (n * slot_w) - 30.0)
        else:
            slot_w = chart_w / n
            start_x = left

        idx = int((self.mouse_pos.x() - start_x) / slot_w)
        if 0 <= idx < n:
            c = self.candles[idx]
            v_val = self.vwap[idx] if idx < len(self.vwap) else c["close"]
            if self.parent_widget and hasattr(self.parent_widget, "set_hover_ohlcv"):
                try:
                    self.parent_widget.set_hover_ohlcv(c, v_val)
                except Exception:
                    pass

    def paintEvent(self, event) -> None:
        """Institutional TradingView-grade QPainter rendering pipeline."""
        try:
            painter = QPainter(self)
            painter.setRenderHint(QPainter.Antialiasing)
        except Exception:
            return

        w = float(self.width())
        h = float(self.height())

        # Geometry coordinates
        left = 12.0
        right = 72.0    # Right Y-axis width
        top = 10.0
        bottom = 22.0   # Bottom X-axis height

        chart_w = max(100.0, w - left - right)
        chart_h = max(120.0, h - top - bottom)

        # Split: Price canvas (78%) & Volume sub-panel (18%) with 4% buffer
        vol_h = max(24.0, chart_h * 0.18)
        price_h = chart_h - vol_h - 10.0
        vol_top = top + price_h + 10.0

        # 1. Background Grid & Outer Slate Separators
        grid_pen = QPen(QColor(255, 255, 255, 12), 1, Qt.DotLine)
        painter.setPen(grid_pen)

        # Horizontal price gridlines (5 steps)
        for y_step in np.linspace(top, top + price_h, 6):
            painter.drawLine(int(left), int(y_step), int(left + chart_w), int(y_step))

        # Volume separator line
        sep_pen = QPen(QColor(255, 255, 255, 20), 1, Qt.SolidLine)
        painter.setPen(sep_pen)
        painter.drawLine(int(left), int(vol_top - 5), int(left + chart_w), int(vol_top - 5))

        # Y-Axis separator line (Right rail divider)
        painter.drawLine(int(left + chart_w), int(top), int(left + chart_w), int(top + chart_h))

        # 2. IF NO CANDLE DATA: Render Elegant Institutional Standby Grid
        if not self.candles:
            # Subtle standby watermark card
            center_x = left + chart_w / 2.0
            center_y = top + price_h / 2.0

            box_w = 440.0
            box_h = 76.0
            box_rect = QRectF(center_x - box_w / 2.0, center_y - box_h / 2.0, box_w, box_h)

            painter.setBrush(QBrush(QColor(11, 16, 26, 230)))
            painter.setPen(QPen(QColor(0, 229, 255, 60), 1))
            painter.drawRoundedRect(box_rect, 6, 6)

            painter.setPen(QColor("#00e5ff"))
            painter.setFont(QFont("Segoe UI", 10, QFont.Bold))
            painter.drawText(
                QRectF(box_rect.x(), box_rect.y() + 14, box_w, 20),
                Qt.AlignCenter,
                "⚡ AWAITING LIVE EXCHANGE FEED"
            )

            painter.setPen(QColor("#78909c"))
            painter.setFont(QFont("Segoe UI", 8))
            painter.drawText(
                QRectF(box_rect.x(), box_rect.y() + 38, box_w, 20),
                Qt.AlignCenter,
                "Connect broker stream or select watchlist instrument to ingest ticks."
            )

            painter.end()
            return

        # 3. Damped/Hysteresis Y-axis scale (never bounces on micro-ticks)
        self._scale_min, self._scale_max = self._compute_scale()
        min_p   = self._scale_min
        max_p   = self._scale_max
        p_range = max_p - min_p if max_p > min_p else 1.0

        # Volume scale headroom
        max_vol = max([c.get("volume", 1000.0) for c in self.candles]) or 1.0
        max_vol_scaled = max_vol * 1.15

        # 4. Y-Axis Price Ticks & Labels (Right Scale)
        painter.setFont(QFont("Consolas", 8))
        price_steps = np.linspace(min_p, max_p, 6)
        for p_val in price_steps:
            y_coord = top + price_h - ((p_val - min_p) / p_range) * price_h
            painter.setPen(QColor("#64748b"))
            painter.drawText(
                QRectF(left + chart_w + 6, y_coord - 7, right - 10, 14),
                Qt.AlignLeft | Qt.AlignVCenter,
                f"{p_val:,.1f}"
            )

        # 5. Candlestick Slot Spacing & Proportional Capping
        n = len(self.candles)
        if n <= 35:
            slot_w = min(18.0, chart_w / max(1, n))
            candle_w = max(3.0, slot_w * 0.70)
            start_x = max(left, left + chart_w - (n * slot_w) - 30.0)
        else:
            slot_w = chart_w / n
            candle_w = max(2.5, min(14.0, slot_w * 0.70))
            start_x = left

        bull_col = QColor("#10b981")  # Institutional Emerald Green
        bear_col = QColor("#ef4444")  # Institutional Ruby Red

        vwap_pts = []
        ema9_pts = []
        ema21_pts = []

        # 6. Render Volume Bars & Candlesticks
        for i, c in enumerate(self.candles):
            cx = start_x + i * slot_w + slot_w / 2.0
            y_open = top + price_h - ((c["open"] - min_p) / p_range) * price_h
            y_close = top + price_h - ((c["close"] - min_p) / p_range) * price_h
            y_high = top + price_h - ((c["high"] - min_p) / p_range) * price_h
            y_low = top + price_h - ((c["low"] - min_p) / p_range) * price_h

            is_bull = c["close"] >= c["open"]
            col = bull_col if is_bull else bear_col

            # A. Volume Bar (Bottom Sub-Panel)
            if self.show_volume:
                v = c.get("volume", 1000.0)
                bar_h = (v / max_vol_scaled) * vol_h
                bar_y = vol_top + vol_h - bar_h
                v_col = QColor(16, 185, 129, 110) if is_bull else QColor(239, 68, 68, 110)
                painter.setBrush(QBrush(v_col))
                painter.setPen(Qt.NoPen)
                painter.drawRect(QRectF(cx - candle_w / 2.0, bar_y, candle_w, max(1.0, bar_h)))

            # B. Candlestick Thin 1px Wick
            painter.setPen(QPen(col, 1.0))
            painter.drawLine(QPointF(cx, y_high), QPointF(cx, y_low))

            # C. Candlestick Body (Strictly Capped & Antialiased)
            body_top = min(y_open, y_close)
            body_h = max(1.5, abs(y_close - y_open))
            painter.setBrush(QBrush(col))
            painter.setPen(QPen(col, 1.0))
            painter.drawRect(QRectF(cx - candle_w / 2.0, body_top, candle_w, body_h))

            # D. Collect Overlay Curve Points
            if self.show_vwap and i < len(self.vwap):
                y_v = top + price_h - ((self.vwap[i] - min_p) / p_range) * price_h
                vwap_pts.append(QPointF(cx, y_v))

            if self.show_ema:
                if i < len(self.ema9):
                    y_e9 = top + price_h - ((self.ema9[i] - min_p) / p_range) * price_h
                    ema9_pts.append(QPointF(cx, y_e9))
                if i < len(self.ema21):
                    y_e21 = top + price_h - ((self.ema21[i] - min_p) / p_range) * price_h
                    ema21_pts.append(QPointF(cx, y_e21))

        # 7. Render Moving Average & VWAP Curves (Smooth 1.5px antialiased curves)
        if self.show_vwap and len(vwap_pts) > 1:
            painter.setPen(QPen(QColor("#00e5ff"), 1.5))  # Cyan VWAP
            for k in range(len(vwap_pts) - 1):
                painter.drawLine(vwap_pts[k], vwap_pts[k + 1])

        if self.show_ema:
            if len(ema9_pts) > 1:
                painter.setPen(QPen(QColor("#fbbf24"), 1.4))  # Neon Amber EMA 9
                for k in range(len(ema9_pts) - 1):
                    painter.drawLine(ema9_pts[k], ema9_pts[k + 1])

            if len(ema21_pts) > 1:
                painter.setPen(QPen(QColor("#818cf8"), 1.4))  # Royal Purple EMA 21
                for k in range(len(ema21_pts) - 1):
                    painter.drawLine(ema21_pts[k], ema21_pts[k + 1])

        # 8. Latest Price Horizontal Reference Line & Right Pill
        latest_p = self.current_price
        if latest_p > 0:
            y_curr = top + price_h - ((latest_p - min_p) / p_range) * price_h
            last_candle = self.candles[-1]
            is_bull_last = last_candle["close"] >= last_candle["open"]
            pill_col = bull_col if is_bull_last else bear_col

            # Dotted price pulse line
            painter.setPen(QPen(pill_col, 1, Qt.DashLine))
            painter.drawLine(int(left), int(y_curr), int(left + chart_w), int(y_curr))

            # Right axis badge pill
            badge_rect = QRectF(left + chart_w + 3, y_curr - 9, 64, 18)
            painter.setBrush(QBrush(pill_col))
            painter.setPen(Qt.NoPen)
            painter.drawRoundedRect(badge_rect, 3, 3)

            painter.setPen(QColor("#ffffff"))
            painter.setFont(QFont("Consolas", 8, QFont.Bold))
            painter.drawText(badge_rect, Qt.AlignCenter, f"{latest_p:,.1f}")

        # 9. Time Axis Labels (Bottom Rail)
        painter.setPen(QColor("#64748b"))
        painter.setFont(QFont("Segoe UI", 8))
        time_step = max(1, n // 7)
        for i in range(0, n, time_step):
            cx = start_x + i * slot_w + slot_w / 2.0
            if i < len(self.times):
                t_str = self.times[i]
                painter.drawText(QRectF(cx - 24, h - bottom + 4, 48, 16), Qt.AlignCenter, t_str)

        # 10. Interactive Crosshair & Tooltip Overlay
        if self.mouse_pos:
            mx = self.mouse_pos.x()
            my = self.mouse_pos.y()
            if left <= mx <= left + chart_w and top <= my <= top + chart_h:
                cross_pen = QPen(QColor(148, 163, 184, 130), 1, Qt.DashLine)
                painter.setPen(cross_pen)

                # Crosshair Lines
                painter.drawLine(int(left), int(my), int(left + chart_w), int(my))
                painter.drawLine(int(mx), int(top), int(mx), int(vol_top + vol_h))

                # Hover Price Badge on Right Axis
                if top <= my <= top + price_h:
                    hover_p = min_p + ((top + price_h - my) / price_h) * p_range
                    h_badge = QRectF(left + chart_w + 3, my - 9, 64, 18)
                    painter.setBrush(QBrush(QColor(15, 23, 42)))
                    painter.setPen(QPen(QColor("#00e5ff"), 1))
                    painter.drawRoundedRect(h_badge, 3, 3)

                    painter.setPen(QColor("#00e5ff"))
                    painter.setFont(QFont("Consolas", 8, QFont.Bold))
                    painter.drawText(h_badge, Qt.AlignCenter, f"{hover_p:,.1f}")

                # Hover Time Badge on Bottom Axis
                hover_idx = int((mx - start_x) / slot_w)
                if 0 <= hover_idx < len(self.times):
                    t_str = self.times[hover_idx]
                    t_badge = QRectF(mx - 25, h - bottom + 2, 50, 18)
                    painter.setBrush(QBrush(QColor(15, 23, 42)))
                    painter.setPen(QPen(QColor("#00e5ff"), 1))
                    painter.drawRoundedRect(t_badge, 3, 3)

                    painter.setPen(QColor("#ffffff"))
                    painter.setFont(QFont("Segoe UI", 8, QFont.Bold))
                    painter.drawText(t_badge, Qt.AlignCenter, t_str)

        painter.end()


class ChartWidget(QFrame):
    """
    Institutional TradingView-grade Terminal Chart Card.
    Features modern dark obsidian container, timeframe selectors, indicator toggles,
    live OHLCV statistics header, and hardware-accelerated candle canvas.
    """

    #: Emitted with the authenticated OHLCV frame of a completed real backfill.
    backfill_loaded = Signal(object)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.current_symbol: str = "RELIANCE.NS"
        self.current_timeframe: str = "15m"
        self.setProperty("class", "cyberCard")
        self.setStyleSheet("""
            QFrame.cyberCard {
                background-color: #0b0e14;
                border: 1px solid rgba(255, 255, 255, 0.07);
                border-radius: 8px;
            }
        """)
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(6)

        # 1. TradingView-Style Controls Top Bar
        top_bar = QHBoxLayout()
        top_bar.setSpacing(6)

        self.symbol_combo = QComboBox(self)
        self.symbol_combo.addItems([
            "NIFTY 50", "BANK NIFTY", "FINNIFTY", "SENSEX",
            "MCX CRUDE OIL", "MCX GOLD", "MCX SILVER",
            "RELIANCE.NS", "TCS.NS", "INFY.NS", "HDFCBANK.NS"
        ])
        self.symbol_combo.setStyleSheet("""
            QComboBox {
                background-color: #121824;
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 5px;
                padding: 4px 10px;
                color: #ffffff;
                font-weight: 700;
                font-size: 12px;
            }
            QComboBox:hover {
                border: 1px solid #00e5ff;
            }
        """)
        try:
            self.symbol_combo.currentTextChanged.connect(self.set_symbol)
        except Exception:
            pass
        top_bar.addWidget(self.symbol_combo)
        top_bar.addSpacing(10)

        # Timeframe Selector Pills
        self.tf_buttons: Dict[str, QPushButton] = {}
        for tf in ["1m", "5m", "15m", "1H", "4H", "1D"]:
            btn = QPushButton(tf, self)
            btn.setCheckable(True)
            if tf == self.current_timeframe:
                btn.setChecked(True)
                btn.setStyleSheet("""
                    QPushButton {
                        background-color: rgba(0, 229, 255, 0.15);
                        color: #00e5ff;
                        font-weight: 700;
                        border-radius: 4px;
                        padding: 3px 8px;
                        font-size: 11px;
                        border: 1px solid #00e5ff;
                    }
                """)
            else:
                btn.setStyleSheet("""
                    QPushButton {
                        background-color: #121824;
                        color: #94a3b8;
                        font-weight: 600;
                        border-radius: 4px;
                        padding: 3px 8px;
                        font-size: 11px;
                        border: 1px solid rgba(255, 255, 255, 0.06);
                    }
                    QPushButton:hover {
                        background-color: #1a2332;
                        color: #ffffff;
                    }
                """)
            try:
                btn.clicked.connect(lambda checked, t=tf: self._on_timeframe_selected(t))
            except Exception:
                pass
            self.tf_buttons[tf] = btn
            top_bar.addWidget(btn)

        top_bar.addSpacing(12)

        # Technical Indicator Overlays Toggle Pills
        self.btn_vwap = QPushButton("VWAP", self)
        self.btn_vwap.setCheckable(True)
        self.btn_vwap.setChecked(True)
        self.btn_vwap.setStyleSheet("background-color: rgba(0, 229, 255, 0.12); color: #00e5ff; border: 1px solid #00e5ff; border-radius: 4px; padding: 3px 8px; font-size: 11px; font-weight: bold;")

        self.btn_ema = QPushButton("EMA 9/21", self)
        self.btn_ema.setCheckable(True)
        self.btn_ema.setChecked(True)
        self.btn_ema.setStyleSheet("background-color: rgba(251, 191, 36, 0.12); color: #fbbf24; border: 1px solid #fbbf24; border-radius: 4px; padding: 3px 8px; font-size: 11px; font-weight: bold;")

        try:
            self.btn_vwap.clicked.connect(self._toggle_vwap)
            self.btn_ema.clicked.connect(self._toggle_ema)
        except Exception:
            pass

        top_bar.addWidget(self.btn_vwap)
        top_bar.addWidget(self.btn_ema)

        top_bar.addStretch()

        # Tools: Fullscreen, Chart Settings, Camera
        for icon in ["📐 Measure", "⚙", "⛶"]:
            ibtn = QPushButton(icon, self)
            ibtn.setStyleSheet("background: transparent; color: #64748b; font-size: 11px; font-weight: 600; border: none; padding: 2px 6px;")
            top_bar.addWidget(ibtn)

        layout.addLayout(top_bar)

        # 2. Dynamic Live Header: Symbol, OHLCV, and Technicals Readout Bar
        sub_bar = QHBoxLayout()
        sub_bar.setContentsMargins(2, 2, 2, 2)
        sub_bar.setSpacing(12)

        self.sym_lbl = QLabel(f"{self.current_symbol} • NSE", self)
        self.sym_lbl.setStyleSheet("color: #ffffff; font-weight: 800; font-size: 12px; font-family: 'Segoe UI', Inter, sans-serif;")

        self.ohlc_lbl = QLabel("O --   H --   L --   C --   <span style='color:#64748b;'>(Awaiting Feed)</span>", self)
        self.ohlc_lbl.setStyleSheet("color: #94a3b8; font-size: 11px; font-family: 'Consolas', monospace;")

        self.vwap_lbl = QLabel("VWAP <span style='color:#00e5ff; font-weight:bold;'>--</span>", self)
        self.vwap_lbl.setStyleSheet("color: #94a3b8; font-size: 11px; font-family: 'Consolas', monospace;")

        self.ema20_lbl = QLabel("EMA(9) <span style='color:#fbbf24; font-weight:bold;'>--</span>", self)
        self.ema20_lbl.setStyleSheet("color: #94a3b8; font-size: 11px; font-family: 'Consolas', monospace;")

        self.ema50_lbl = QLabel("EMA(21) <span style='color:#818cf8; font-weight:bold;'>--</span>", self)
        self.ema50_lbl.setStyleSheet("color: #94a3b8; font-size: 11px; font-family: 'Consolas', monospace;")

        sub_bar.addWidget(self.sym_lbl)
        sub_bar.addWidget(self.ohlc_lbl)
        sub_bar.addStretch()
        sub_bar.addWidget(self.vwap_lbl)
        sub_bar.addWidget(self.ema20_lbl)
        sub_bar.addWidget(self.ema50_lbl)

        layout.addLayout(sub_bar)

        # 3. Candlestick Canvas — stretch=1 so the canvas always fills the card
        #    (a fixed-size canvas leaves an empty band above it and looks broken).
        self.canvas = CandleCanvas(self)
        try:
            self.canvas.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            self.canvas.setMinimumHeight(320)
        except Exception:
            pass
        layout.addWidget(self.canvas, 1)

        # 30 FPS render timer — decouples tick data from Qt paint events
        try:
            from PySide6.QtCore import QTimer
            self._render_timer = QTimer(self)
            self._render_timer.setInterval(33)   # ~30 FPS
            self._render_timer.timeout.connect(self._on_render_tick)
            self._render_timer.start()
        except Exception:
            pass

        # Zero-Fake-Data mandate: the canvas starts EMPTY and only ever displays
        # exchange-sourced candles. Deterministic demo candles are opt-in for
        # screenshots/design work and must be requested explicitly.
        #   OMNITRADE_DEMO_CHART=1
        if os.environ.get("OMNITRADE_DEMO_CHART", "0").strip() == "1":
            try:
                self.canvas.seed_historical(self.current_symbol)
                self.restore_default_ohlc()
            except Exception:
                pass

    def _on_render_tick(self) -> None:
        """30 FPS render loop: only repaints when new tick data has arrived."""
        if self.canvas._scale_dirty:
            self.canvas._scale_dirty = False
            self.canvas._calculate_indicators()
            self.canvas.update()
            self.restore_default_ohlc()

    def _toggle_vwap(self) -> None:
        self.canvas.show_vwap = not self.canvas.show_vwap
        if self.canvas.show_vwap:
            self.btn_vwap.setStyleSheet("background-color: rgba(0, 229, 255, 0.12); color: #00e5ff; border: 1px solid #00e5ff; border-radius: 4px; padding: 3px 8px; font-size: 11px; font-weight: bold;")
        else:
            self.btn_vwap.setStyleSheet("background-color: #121824; color: #64748b; border: 1px solid rgba(255, 255, 255, 0.06); border-radius: 4px; padding: 3px 8px; font-size: 11px;")
        self.canvas.update()

    def _toggle_ema(self) -> None:
        self.canvas.show_ema = not self.canvas.show_ema
        if self.canvas.show_ema:
            self.btn_ema.setStyleSheet("background-color: rgba(251, 191, 36, 0.12); color: #fbbf24; border: 1px solid #fbbf24; border-radius: 4px; padding: 3px 8px; font-size: 11px; font-weight: bold;")
        else:
            self.btn_ema.setStyleSheet("background-color: #121824; color: #64748b; border: 1px solid rgba(255, 255, 255, 0.06); border-radius: 4px; padding: 3px 8px; font-size: 11px;")
        self.canvas.update()

    def _on_timeframe_selected(self, tf: str) -> None:
        self.current_timeframe = tf
        for name, btn in self.tf_buttons.items():
            if name == tf:
                btn.setChecked(True)
                btn.setStyleSheet("""
                    QPushButton {
                        background-color: rgba(0, 229, 255, 0.15);
                        color: #00e5ff;
                        font-weight: 700;
                        border-radius: 4px;
                        padding: 3px 8px;
                        font-size: 11px;
                        border: 1px solid #00e5ff;
                    }
                """)
            else:
                btn.setChecked(False)
                btn.setStyleSheet("""
                    QPushButton {
                        background-color: #121824;
                        color: #94a3b8;
                        font-weight: 600;
                        border-radius: 4px;
                        padding: 3px 8px;
                        font-size: 11px;
                        border: 1px solid rgba(255, 255, 255, 0.06);
                    }
                    QPushButton:hover {
                        background-color: #1a2332;
                        color: #ffffff;
                    }
                """)

        # Zero-Fake-Data: a timeframe switch re-requests real history for the
        # active instrument instead of generating time-scaled seed candles.
        self._timeframe = tf
        self._request_backfill(self.current_symbol, tf)

    # ── Real-data backfill (Zero-Fake-Data) ──────────────────────────────────

    def set_history_provider(self, provider) -> None:
        """
        Registers the real-market-data hook used to backfill the canvas.

        ``provider(symbol, timeframe) -> pandas.DataFrame`` must return an
        authentic OHLCV frame (or an empty frame when unavailable). Nothing is
        ever synthesised locally.
        """
        self._history_provider = provider

    def request_backfill(self, symbol: Optional[str] = None,
                         timeframe: Optional[str] = None) -> None:
        """Public entry point: refresh the chart from the real-data provider."""
        self._request_backfill(
            symbol or self.current_symbol,
            timeframe or getattr(self, "_timeframe", self.current_timeframe),
        )

    def _request_backfill(self, symbol: str, timeframe: str) -> None:
        """
        Clears the canvas, then asynchronously loads real history.

        Older in-flight requests are invalidated by the monotonically
        increasing ``_backfill_seq`` so a slow symbol switch can never
        overwrite a newer one.
        """
        self._backfill_seq = getattr(self, "_backfill_seq", 0) + 1
        seq = self._backfill_seq
        self._timeframe = timeframe

        # Stale seed/live candles from the previous instrument must go first.
        try:
            self.clear_canvas()
        except Exception:
            pass
        self.restore_default_ohlc()

        provider = getattr(self, "_history_provider", None)
        if provider is None:
            return  # no real feed wired -> explicit "Awaiting Feed" state

        try:
            signals = _BackfillSignals(self)   # parented: lives on the UI thread
            signals.loaded.connect(self._on_backfill_loaded)
            signals.failed.connect(self._on_backfill_failed)
            self._backfill_signals = signals
            worker = _BackfillWorker(provider, symbol, timeframe, seq, signals)
            worker.start()
            self._backfill_worker = worker  # keep a strong reference alive
        except Exception:
            pass

    def _on_backfill_loaded(self, seq: int, df) -> None:
        """Applies a completed real-history fetch (ignoring stale responses)."""
        if seq != getattr(self, "_backfill_seq", 0):
            return
        if df is None or getattr(df, "empty", True):
            # Keep any live candles that arrived while the fetch was in flight.
            if not self.canvas.candles:
                try:
                    self.clear_canvas()
                except Exception:
                    pass
            self.restore_default_ohlc()
            return
        try:
            self.canvas.set_historical_data(df)
        except Exception:
            return
        self.restore_default_ohlc()
        try:
            self.backfill_loaded.emit(df)   # engine/telemetry fan-out (real data)
        except Exception:
            pass

    def shutdown_backfill(self, timeout_ms: int = 2000) -> None:
        """Joins any in-flight provider thread (called on window teardown)."""
        worker = getattr(self, "_backfill_worker", None)
        if worker is None:
            return
        try:
            if worker.is_alive():
                worker.join(max(0.0, timeout_ms / 1000.0))
        except Exception:
            pass
        self._backfill_worker = None

    def _on_backfill_failed(self, seq: int, error: str) -> None:
        """Provider/network failure: leave the canvas honestly empty."""
        if seq != getattr(self, "_backfill_seq", 0):
            return
        # Never wipe live candles that already streamed in: a failed history
        # fetch must not destroy real ticks.
        if not self.canvas.candles:
            try:
                self.clear_canvas()
            except Exception:
                pass
        self.restore_default_ohlc()

    def set_symbol(self, symbol: str) -> None:
        self.current_symbol = symbol
        exchange = "MCX" if any(k in symbol.upper() for k in ["CRUDE", "GOLD", "SILVER", "COPPER", "NATURALGAS"]) else "NSE"
        self.sym_lbl.setText(f"{symbol} • {exchange}")

        # Zero-Fake-Data: never synthesise candles for a new instrument.
        # Clear the canvas and request an authentic backfill from the wired
        # provider (a real market-data source). With no provider the panel
        # stays in its explicit "Awaiting Feed" state.
        self._request_backfill(symbol, getattr(self, "_timeframe", "5m"))

    def update_candles(self, df: pd.DataFrame, orb_high: float = 0.0, orb_low: float = 0.0) -> None:
        """Loads historical candles and sets live indicators."""
        self.canvas.set_historical_data(df)
        self.restore_default_ohlc()

    def restore_default_ohlc(self) -> None:
        """Restores the header readout to the most recent candle data."""
        if not self.canvas.candles:
            self.ohlc_lbl.setText("O --   H --   L --   C --   <span style='color:#64748b;'>(Awaiting Feed)</span>")
            return
        last = self.canvas.candles[-1]
        col = "#10b981" if last["close"] >= last["open"] else "#ef4444"
        chg = ((last["close"] - last["open"]) / last["open"] * 100.0) if last["open"] > 0 else 0.0
        sign = "+" if chg >= 0 else ""
        self.ohlc_lbl.setText(
            f"O <span style='color:#ffffff;'>{last['open']:,.2f}</span>  "
            f"H <span style='color:#ffffff;'>{last['high']:,.2f}</span>  "
            f"L <span style='color:#ffffff;'>{last['low']:,.2f}</span>  "
            f"C <span style='color:{col}; font-weight:bold;'>{last['close']:,.2f}</span>  "
            f"<span style='color:{col}; font-weight:bold;'>({sign}{chg:.2f}%)</span>  "
            f"Vol <span style='color:#94a3b8;'>{last.get('volume', 0):,.0f}</span>"
        )
        if self.canvas.vwap:
            self.vwap_lbl.setText(f"VWAP <span style='color:#00e5ff; font-weight:bold;'>{self.canvas.vwap[-1]:,.2f}</span>")
        if self.canvas.ema9:
            self.ema20_lbl.setText(f"EMA(9) <span style='color:#fbbf24; font-weight:bold;'>{self.canvas.ema9[-1]:,.2f}</span>")
        if self.canvas.ema21:
            self.ema50_lbl.setText(f"EMA(21) <span style='color:#818cf8; font-weight:bold;'>{self.canvas.ema21[-1]:,.2f}</span>")

    def set_hover_ohlcv(self, c: dict, vwap_val: float) -> None:
        """Displays stats for the specific candle directly under the cursor."""
        col = "#10b981" if c["close"] >= c["open"] else "#ef4444"
        chg = ((c["close"] - c["open"]) / c["open"] * 100.0) if c["open"] > 0 else 0.0
        sign = "+" if chg >= 0 else ""
        self.ohlc_lbl.setText(
            f"O <span style='color:#ffffff;'>{c['open']:,.2f}</span>  "
            f"H <span style='color:#ffffff;'>{c['high']:,.2f}</span>  "
            f"L <span style='color:#ffffff;'>{c['low']:,.2f}</span>  "
            f"C <span style='color:{col}; font-weight:bold;'>{c['close']:,.2f}</span>  "
            f"<span style='color:{col}; font-weight:bold;'>({sign}{chg:.2f}%)</span>  "
            f"Vol <span style='color:#94a3b8;'>{c.get('volume', 0):,.0f}</span>"
        )
        self.vwap_lbl.setText(f"VWAP <span style='color:#00e5ff; font-weight:bold;'>{vwap_val:,.2f}</span>")

    def on_tick_received(self, tick: dict) -> None:
        """Real-time SmartStream tick receiver."""
        ltp = float(tick.get("ltp", 0.0))
        if ltp > 0:
            self.canvas.update_tick(ltp)
            self.restore_default_ohlc()

    def clear_canvas(self) -> None:
        """
        Clears all candle data and resets the canvas to disconnected/standby state.
        Called when broker stream disconnects to satisfy the Zero-Fake-Data guarantee:
        no seed candles must be visible in the disconnected/unauthenticated state.
        """
        self.canvas.candles = []
        self.canvas.times = []
        self.canvas.ema9 = []
        self.canvas.ema21 = []
        self.canvas.ema20 = []
        self.canvas.ema50 = []
        self.canvas.vwap = []
        self.canvas.current_price = 0.0
        self.canvas.is_connected = False
        self.canvas._scale_min = 0.0
        self.canvas._scale_max = 0.0
        self.canvas._scale_dirty = False
        try:
            self.canvas.update()
        except Exception:
            pass
        self.restore_default_ohlc()
