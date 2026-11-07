#!/usr/bin/env python3
"""
OmniTradePro - Autonomous Capital Allocator & Multi-Session Router
Platform: Windows 10/11 64-bit | Python 3.10+
Routes institutional capital across Equity Cash, Large-Cap Nifty 50, and MCX Commodities
based on capital tiers, exchange operating sessions (NSE/BSE 09:15-15:15, MCX 15:15-23:15 IST),
and strict 10% segment risk ceilings.
"""

from datetime import datetime, time as dtime, timezone
from typing import Dict, Any, List, Optional


class CapitalAllocator:
    """
    Autonomous capital-to-asset allocation and multi-session routing engine.
    Calibrated to Indian market operating hours:
    - Equity Session: 09:15 to 15:15 IST
    - Commodity Session: 15:15 to 23:15 IST
    """
    EQUITY_OPEN = dtime(9, 15)
    EQUITY_CUTOFF = dtime(15, 15)
    MCX_CLOSE = dtime(23, 15)

    TIER1_UNIVERSE = ["TATASTEEL", "ITC", "ONGC", "IOC", "POWERGRID"]
    TIER2_UNIVERSE = ["RELIANCE", "INFY", "HDFCBANK", "ICICIBANK", "TCS", "TATAMOTORS"]
    TIER3_EQUITY_UNIVERSE = ["RELIANCE", "TCS", "HDFCBANK", "INFY", "TATAMOTORS", "SBIN"]
    TIER3_MCX_UNIVERSE = ["CRUDEOIL", "GOLDM", "SILVERM"]

    @classmethod
    def get_market_session(cls, check_time: Optional[str] = None) -> str:
        """
        Determines active Indian exchange market session (EQUITY or MCX).
        Accepts 'HH:MM' string or defaults to current Indian Standard Time.
        """
        if check_time:
            parts = check_time.strip().split(":")
            t = dtime(hour=int(parts[0]), minute=int(parts[1]))
        else:
            # Current time in IST (UTC+05:30)
            now_utc = datetime.now(timezone.utc)
            # Add 5 hours 30 mins
            ist_offset_seconds = (5 * 3600) + (30 * 60)
            now_ist = datetime.fromtimestamp(now_utc.timestamp() + ist_offset_seconds, tz=timezone.utc)
            t = now_ist.time()

        if cls.EQUITY_OPEN <= t < cls.EQUITY_CUTOFF:
            return "EQUITY"
        elif cls.EQUITY_CUTOFF <= t <= cls.MCX_CLOSE:
            return "MCX"
        else:
            # Off-market hours default to EQUITY for morning preparation
            return "EQUITY"

    @classmethod
    def allocate_asset(cls, capital_inr: float, current_time: Optional[str] = None) -> Dict[str, Any]:
        """
        Routes capital allocation to the optimal asset class and broker gateway.
        Enforces exact 10% maximum risk allocation.
        """
        if capital_inr <= 0.0:
            raise ValueError(f"Capital must be greater than 0, got {capital_inr}")

        session = cls.get_market_session(current_time)
        max_risk = round(capital_inr * 0.10, 2)

        # Tier 1: Micro/Small Capital (< ₹2,000) -> High-liquidity cash scrips
        if capital_inr < 2000.0:
            eligible_universe = cls.TIER1_UNIVERSE
            primary_symbol = "TATASTEEL"
            market_session = "EQUITY"
            broker_pref = "SHOONYA"  # Zero brokerage for micro equity turnover

        # Tier 2: Mid-tier Capital (₹2,000 to ₹5,000) -> Nifty 50 Large-Cap
        elif 2000.0 <= capital_inr <= 5000.0:
            eligible_universe = cls.TIER2_UNIVERSE
            primary_symbol = "RELIANCE"
            market_session = "EQUITY"
            broker_pref = "ANGEL_ONE"

        # Tier 3: Institutional Capital (> ₹5,000) -> Multi-Session Rotation
        else:
            if session == "MCX":
                eligible_universe = cls.TIER3_MCX_UNIVERSE
                primary_symbol = "CRUDEOIL"
                market_session = "MCX"
                broker_pref = "ANGEL_ONE"
            else:
                eligible_universe = cls.TIER3_EQUITY_UNIVERSE
                primary_symbol = "RELIANCE"
                market_session = "EQUITY"
                broker_pref = "ANGEL_ONE"

        return {
            "capital_inr": float(capital_inr),
            "market_session": market_session,
            "eligible_universe": eligible_universe,
            "primary_symbol": primary_symbol,
            "max_segment_risk_inr": max_risk,
            "broker_routing_preference": broker_pref
        }

