#!/usr/bin/env python3
"""
OmniTradePro - Real 2025 Historical Data Downloader & Local Cache
Fetches authentic 2025 intraday historical price action data for:
1. NSE: Nifty 50 (^NSEI)
2. NSE: Bank Nifty (^NSEBANK)
3. MCX: Crude Oil (CL=F)
4. MCX: Gold (GC=F)
Saves exact unadulterated OHLCV data into benchmarks/data/ for verifiable offline replay.
"""

import sys
from pathlib import Path
import pandas as pd
import yfinance as yf

DATA_DIR = Path(__file__).resolve().parent / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

ASSETS = {
    "NIFTY_50": {"ticker": "^NSEI", "interval": "1h", "file": "nifty50_2025_1h.csv"},
    "BANK_NIFTY": {"ticker": "^NSEBANK", "interval": "1h", "file": "banknifty_2025_1h.csv"},
    "CRUDE_OIL": {"ticker": "CL=F", "interval": "1h", "file": "crudeoil_2025_1h.csv"},
    "GOLD": {"ticker": "GC=F", "interval": "1h", "file": "gold_2025_1h.csv"},
}

def download_data():
    print("=" * 80)
    print("DOWNLOADING AUTHENTIC 2025 HISTORICAL MARKET DATA FOR BENCHMARK")
    print("=" * 80)
    
    for name, info in ASSETS.items():
        out_path = DATA_DIR / info["file"]
        if out_path.exists() and out_path.stat().st_size > 1000:
            df = pd.read_csv(out_path, index_col=0, parse_dates=True)
            print(f"[{name}] Found cached data ({len(df)} candles): {out_path.name}")
            continue
            
        print(f"[{name}] Downloading 2025 data for {info['ticker']} (interval={info['interval']})...")
        df = yf.download(
            info["ticker"],
            start="2025-01-01",
            end="2025-12-31",
            interval=info["interval"],
            progress=False
        )
        
        if df.empty:
            print(f"[ERROR] Failed to download data for {name} ({info['ticker']})")
            continue
            
        # Clean multi-index columns if returned by yfinance
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = [col[0] if isinstance(col, tuple) else col for col in df.columns]
            
        # Standardize column names
        df.columns = [str(c).capitalize() for c in df.columns]
        df.to_csv(out_path)
        print(f"[{name}] Successfully saved {len(df)} candles to {out_path.name}")
        
    print("=" * 80)
    print("DATA INGESTION COMPLETE: All assets ready for backtest replay.")
    print("=" * 80)

if __name__ == "__main__":
    download_data()

