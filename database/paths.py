#!/usr/bin/env python3
"""
OmniTradePro - Persistence Path Resolution
Single source of truth for where the SQLite ledger and encrypted vault live.

Default: the `database/` package directory (unchanged production behaviour).
Override: set the `OMNITRADE_DATA_DIR` environment variable to relocate all
persistence (custom data directories, portable installs, hermetic test runs).
"""

import os
from pathlib import Path

#: Environment variable that relocates every SQLite database and key file.
ENV_DATA_DIR = "OMNITRADE_DATA_DIR"

#: Default persistence directory (the `database/` package folder).
DEFAULT_DATA_DIR = Path(__file__).resolve().parent

#: Canonical file names.
LEDGER_FILENAME = "omnitrade.db"
VAULT_FILENAME = "omnitrade_vault.db"
KEY_FILENAME = ".vault.key"


def resolve_data_dir() -> Path:
    """Returns the active persistence directory, honouring OMNITRADE_DATA_DIR."""
    override = os.environ.get(ENV_DATA_DIR, "").strip()
    if override:
        target = Path(override).expanduser().resolve()
        target.mkdir(parents=True, exist_ok=True)
        return target
    return DEFAULT_DATA_DIR


def resolve_path(explicit: "str | Path | None", filename: str) -> Path:
    """Resolves an explicit path, else `<data_dir>/<filename>`."""
    if explicit is not None:
        return Path(explicit)
    return resolve_data_dir() / filename
