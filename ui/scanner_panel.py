#!/usr/bin/env python3
"""
OmniTradePro - Nifty 50 & MCX Quantitative Scanner & Odds Inspector Panel
Platform: Windows 10/11 64-bit | Python 3.10+
Integrates 15-Min ORB setup scanning, 10,000-replay Monte Carlo Time Machine odds,
and 4-algorithm consensus signal evaluation in a frosted glassmorphism interface.
"""

from typing import Optional, List, Dict, Any

try:
    from PySide6.QtWidgets import (
        QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
        QTableWidget, QTableWidgetItem, QHeaderView, QDialog,
        QProgressBar, QMessageBox
    )
    from PySide6.QtCore import Qt, QTimer, Signal
except ImportError:
    # Graceful shim for environments without PySide6
    class QWidget:
        def __init__(self, parent=None): pass
        def setStyleSheet(self, s): pass
        def setLayout(self, l): pass
    class QVBoxLayout:
        def __init__(self, *args): pass
        def addWidget(self, w): pass
        def addLayout(self, l): pass
        def addStretch(self, *args): pass
        def setContentsMargins(self, *args): pass
        def setSpacing(self, s): pass
    class QHBoxLayout(QVBoxLayout): pass
    class QLabel:
        def __init__(self, text="", parent=None): pass
        def setText(self, t): pass
        def setStyleSheet(self, s): pass
    class QPushButton:
        def __init__(self, text="", parent=None): pass
        def setStyleSheet(self, s): pass
        def clicked(self): pass
    class QTableWidget:
        def __init__(self, r, c, parent=None): self._rows = r; self._cols = c
        def setHorizontalHeaderLabels(self, l): pass
        def horizontalHeader(self): return self
        def setSectionResizeMode(self, m): pass
        def setRowCount(self, r): self._rows = r
        def rowCount(self): return self._rows
        def setItem(self, r, c, item): pass
        def setCellWidget(self, r, c, w): pass
    class QTableWidgetItem:
        def __init__(self, text=""): self.text = text
        def setTextAlignment(self, a): pass
        def setForeground(self, b): pass
    class QHeaderView:
        Stretch = 1
        ResizeToContents = 2
    class QDialog:
        def __init__(self, parent=None): pass
        def setWindowTitle(self, t): pass
        def setMinimumSize(self, w, h): pass
        def setLayout(self, l): pass
        def setStyleSheet(self, s): pass
        def exec(self): return 1
        def accept(self): pass
    class QProgressBar:
        def __init__(self, parent=None): pass
        def setValue(self, v): pass
    class QMessageBox:
        @staticmethod
        def information(p, t, m): pass
    class QTimer:
        def __init__(self, parent=None): pass
        def timeout(self): pass
        def start(self, ms): pass
        def stop(self): pass
    class Signal:
        def __init__(self, *types): pass
        def connect(self, cb): pass
        def emit(self, *args): pass
    class Qt:
        AlignCenter = 0x0004
        AlignLeft = 0x0001
        AlignVCenter = 0x0080

from core.scanner_orb import MarketScannerORB, SymbolNormalizer
from core.time_machine import MonteCarloTimeMachine
from core.consensus import ConsensusEngine


class MonteCarloOddsDialog(QDialog):
    """
    Modal dialog displaying detailed statistical results of a 10,000-replay
    Monte Carlo Time Machine simulation for an individual candidate.
    """

    def __init__(self, odds_data: Dict[str, Any], parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"Monte Carlo Time Machine — {odds_data.get('symbol', 'N/A')}")
        self.setMinimumSize(480, 360)
        self.odds_data = odds_data
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)

        sym = self.odds_data.get("symbol", "N/A")
        iters = self.odds_data.get("iterations", 10000)
        target_pct = self.odds_data.get("target_hit_pct", 0.0)
        stop_pct = self.odds_data.get("stop_hit_pct", 0.0)
        stagnant_pct = self.odds_data.get("stagnant_pct", 0.0)
        win_odds = self.odds_data.get("win_odds_ratio", 0.0)
        passed = self.odds_data.get("passes_odds_filter", False)

        title = QLabel(f"SIMULATION REPORT: {sym}", self)
        title.setStyleSheet("font-size: 15px; font-weight: bold; color: #00e5ff;")
        layout.addWidget(title)

        sub = QLabel(f"Historical Permutation Replay: {iters:,} Paths | Horizon: 15:15 IST", self)
        sub.setStyleSheet("font-size: 11px; color: #94a3b8;")
        layout.addWidget(sub)

        # Metrics display
        metrics_box = QVBoxLayout()
        metrics_box.setSpacing(8)

        t_lbl = QLabel(f"Target Hit Probability (1:2 R:R): {target_pct:.2f}%", self)
        t_lbl.setStyleSheet("color: #00e676; font-size: 13px; font-weight: bold;")
        s_lbl = QLabel(f"Stop-Loss Hit Probability: {stop_pct:.2f}%", self)
        s_lbl.setStyleSheet("color: #ff3d71; font-size: 13px; font-weight: bold;")
        st_lbl = QLabel(f"Stagnant (Uncompleted by 15:15 IST): {stagnant_pct:.2f}%", self)
        st_lbl.setStyleSheet("color: #ffab00; font-size: 13px;")
        w_lbl = QLabel(f"Empirical Win Odds Ratio: {win_odds:.4f}", self)
        w_lbl.setStyleSheet("color: #00e5ff; font-size: 13px; font-weight: bold;")

        metrics_box.addWidget(t_lbl)
        metrics_box.addWidget(s_lbl)
        metrics_box.addWidget(st_lbl)
        metrics_box.addWidget(w_lbl)
        layout.addLayout(metrics_box)

        # Status Badge
        badge = QLabel(f"Odds Filter Threshold (65.0%): {'QUALIFIED (>= 65%)' if passed else 'REJECTED (< 65%)'}", self)
        badge_color = "#00e676" if passed else "#ff3d71"
        badge.setStyleSheet(f"background-color: rgba(16, 22, 34, 0.95); border: 1px solid {badge_color}; color: {badge_color}; padding: 8px; border-radius: 4px; font-weight: bold;")
        layout.addWidget(badge)

        btn_ok = QPushButton("Close", self)
        try:
            btn_ok.clicked.connect(self.accept)
        except Exception:
            pass
        layout.addWidget(btn_ok)


class ScannerPanel(QWidget):
    """
    Live Nifty 50 & MCX Setup Scanner Table with auto-refresh and Monte Carlo inspector.
    """
    symbol_selected = Signal(str)

    DEFAULT_WATCHLIST = [
        "RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "INFY.NS",
        "ICICIBANK.NS", "TATAMOTORS.NS", "SBIN.NS", "BHARTIARTL.NS",
        "TATASTEEL.NS", "ITC.NS"
    ]

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.scanner = MarketScannerORB()
        self.time_machine = MonteCarloTimeMachine()
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)

        # Header controls
        hdr_layout = QHBoxLayout()
        title = QLabel("QUANTITATIVE SETUP SCANNER (NIFTY 50 & MCX)", self)
        title.setStyleSheet("font-size: 14px; font-weight: bold; color: #00e5ff;")

        self.btn_scan = QPushButton("Run Full Scan", self)
        self.btn_scan.setStyleSheet("background-color: #2979ff; color: white; font-weight: bold;")
        try:
            self.btn_scan.clicked.connect(self.run_scan)
        except Exception:
            pass

        hdr_layout.addWidget(title)
        hdr_layout.addStretch()
        hdr_layout.addWidget(self.btn_scan)
        layout.addLayout(hdr_layout)

        # Table of candidates
        self.table = QTableWidget(0, 8, self)
        headers = [
            "Symbol", "Setup Type", "Breakout Level", "LTP",
            "Vol Surge", "MC Odds (%)", "Signal", "Action"
        ]
        self.table.setHorizontalHeaderLabels(headers)
        try:
            self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        except Exception:
            pass

        layout.addWidget(self.table)

        # Row-click -> symbol sync with the primary chart (was an unlinked signal)
        for _sig in ("cellClicked", "itemDoubleClicked"):
            try:
                getattr(self.table, _sig).connect(
                    lambda r, c=0, *_: self._on_row_clicked(r)
                )
            except Exception:
                pass

    def update_quote(self, symbol: str, ltp: float, chg_pct=None) -> None:
        """Refreshes a scanned row's LTP from a genuine exchange tick."""
        try:
            for row in range(self.table.rowCount()):
                item = self.table.item(row, 0)
                if item is not None and item.text().strip().upper() == symbol.strip().upper():
                    self.table.setItem(row, 3, QTableWidgetItem(f"₹{float(ltp):,.2f}"))
                    return
        except Exception:
            pass

    def run_scan(self) -> None:
        """Runs scan across watchlist and populates candidate table."""
        candidates = self.scanner.scan_watchlist(self.DEFAULT_WATCHLIST)
        self.table.setRowCount(len(candidates))

        for row, item in enumerate(candidates):
            sym = item.get("symbol", "")
            setup = item.get("setup_type", "NONE")
            b_level = item.get("breakout_level", 0.0)
            ltp = item.get("current_price", 0.0)
            vol = "YES (1.2x)" if item.get("volume_spike") else "NORMAL"

            self.table.setItem(row, 0, QTableWidgetItem(sym))
            self.table.setItem(row, 1, QTableWidgetItem(setup))
            self.table.setItem(row, 2, QTableWidgetItem(f"₹{b_level:.2f}"))
            self.table.setItem(row, 3, QTableWidgetItem(f"₹{ltp:.2f}"))
            self.table.setItem(row, 4, QTableWidgetItem(vol))
            # Zero-Fake-Data: odds are computed on demand by the real Monte
            # Carlo engine; until then the cell states "Not run", not a number.
            self.table.setItem(row, 5, QTableWidgetItem("Not run"))
            self.table.setItem(row, 6, QTableWidgetItem(str(item.get("signal", "—") or "—")))

            # Inspect odds button -> real 10,000-path Monte Carlo replay
            btn_inspect = QPushButton("Inspect Odds", self)
            btn_inspect.setStyleSheet("background-color: rgba(0, 229, 255, 0.2); color: #00e5ff; font-weight: bold;")
            try:
                btn_inspect.clicked.connect(
                    lambda checked=False, r=row: self._inspect_odds(r)
                )
            except Exception:
                pass
            self.table.setCellWidget(row, 7, btn_inspect)

    # ── Interaction ───────────────────────────────────────────────────────────

    def _selected_symbol(self, row: int):
        item = self.table.item(row, 0)
        return item.text().strip() if item is not None else ""

    def _on_row_clicked(self, row: int, column: int = 0) -> None:
        """Row click publishes the symbol so the chart can sync to it."""
        sym = self._selected_symbol(row)
        if sym:
            try:
                self.symbol_selected.emit(sym)
            except Exception:
                pass

    def _inspect_odds(self, row: int) -> None:
        """
        Runs the real Monte Carlo engine for the selected row and opens the
        report dialog. Network/history failure surfaces an explicit error
        instead of fabricated probabilities.
        """
        sym = self._selected_symbol(row)
        if not sym:
            return
        ltp_item = self.table.item(row, 3)
        try:
            entry = float(str(ltp_item.text()).replace("₹", "").replace(",", "")) if ltp_item else 0.0
        except Exception:
            entry = 0.0
        if entry <= 0.0:
            self.table.setItem(row, 5, QTableWidgetItem("No live quote"))
            return
        try:
            odds = self.time_machine.run_simulation(
                sym, entry_price=entry,
                stop_loss=entry * 0.99, target_price=entry * 1.02,
            )
        except Exception as exc:
            self.table.setItem(row, 5, QTableWidgetItem(f"Engine error: {exc}"))
            return
        if not odds:
            self.table.setItem(row, 5, QTableWidgetItem("Unavailable"))
            return
        try:
            self.table.setItem(row, 5, QTableWidgetItem(f"{float(odds.get('target_hit_pct', 0.0)):.2f}%"))
            self.table.setItem(row, 6, QTableWidgetItem(
                "QUALIFIED" if odds.get("passes_odds_filter") else "REJECTED"
            ))
        except Exception:
            pass
        try:
            dialog = MonteCarloOddsDialog(odds, self)
            dialog.exec()
        except Exception:
            pass
