# dbc_page.py
from pathlib import Path
import cantools

# Project root: one level above this file's folder
BASE_DIR = Path(__file__).resolve().parent.parent

# Absolute path to your DBC file
DBC_PATH = BASE_DIR / "data" / "DBC_sample_cantools.dbc"

if not DBC_PATH.exists():
    raise FileNotFoundError(f"DBC not found at: {DBC_PATH}")

_dbc_cache = None


def load_dbc():
    """Return the loaded DBC database, loading it on first use."""
    global _dbc_cache
    if _dbc_cache is None:
        _dbc_cache = cantools.database.load_file(DBC_PATH)
    return _dbc_cache


__all__ = ["BASE_DIR", "DBC_PATH", "load_dbc"]
