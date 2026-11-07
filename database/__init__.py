"""
OmniTradePro Database Subsystem.
Exports DatabaseHandler for AES-256 encrypted multi-broker credentials,
dynamic 2FA generation, and trade audit trail management.
"""

from database.db_handler import DatabaseHandler

__all__ = ["DatabaseHandler"]

