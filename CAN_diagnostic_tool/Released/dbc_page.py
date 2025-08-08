# dbc_page.py
"""Central place to load and share the DBC database.

• Looks for the file right next to this script (same folder).
• Raises a clear error if it’s missing.
• Exports: BASE_DIR, DBC_PATH, load_dbc
"""

from pathlib import Path
import cantools

# ------------------------- configuration ------------------------------------
DBC_FILENAME = "DBC_sample_cantools.dbc"   # change here if you rename the file
# ----------------------------------------------------------------------------

# Folder where this .py file lives (e.g., CAN_diagnostic_tool/)
BASE_DIR = Path(__file__).resolve().parent
DBC_PATH = BASE_DIR / DBC_FILENAME

if not DBC_PATH.exists():
    raise FileNotFoundError(f"DBC file not found: {DBC_PATH}")

_dbc_cache = None


def load_dbc():
    """Return the loaded DBC database, loading it on first use."""
    global _dbc_cache
    if _dbc_cache is None:
        _dbc_cache = cantools.database.load_file(DBC_PATH)
    return _dbc_cache


__all__ = ["BASE_DIR", "DBC_PATH", "load_dbc"]
