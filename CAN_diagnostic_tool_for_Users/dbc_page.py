# dbc_page.py
"""
Central place to load and share the DBC database.

• Looks for the file right next to this script (same folder).
• Raises a clear error if it’s missing.
• Exports: BASE_DIR, DBC_PATH, get_dbc
"""

from pathlib import Path
import sys
from functools import lru_cache
import cantools

# ------------------------- configuration ------------------------------------
DBC_FILENAME = "DBC_sample_cantools.dbc"   # change here if you rename the file
# ----------------------------------------------------------------------------

def _resolve_base_dir() -> Path:
    # PyInstaller one-file → _MEIPASS is extraction dir
    if hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)
    # PyInstaller one-dir → use executable directory
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    # Normal interpreter → alongside this file
    return Path(__file__).resolve().parent

BASE_DIR = _resolve_base_dir()
DBC_PATH = BASE_DIR / DBC_FILENAME

if not DBC_PATH.exists():
    raise FileNotFoundError(f"DBC file not found: {DBC_PATH}")

# Lazily load on first use; keeps import time fast for the .exe
@lru_cache(maxsize=1)
def get_dbc():
    return cantools.database.load_file(DBC_PATH)

__all__ = ["BASE_DIR", "DBC_PATH", "get_dbc"]
