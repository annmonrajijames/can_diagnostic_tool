from __future__ import annotations
"""
Configurable DBC loader used across the Engineers app.

Behavior:
- Reads selected DBC path from settings.json in this folder.
- No predefined fallback path is used. If not configured, loading raises with
    a helpful message asking to set the path via the Settings page.
- Exposes get_dbc() to get a cached cantools database, and DBC_PATH for display.
"""

from pathlib import Path
import json
import cantools

APP_DIR = Path(__file__).resolve().parent
BASE_DIR = APP_DIR.parent
SETTINGS_PATH = APP_DIR / "settings.json"

_dbc_cache = None


def _load_config_path() -> Path | None:
    if SETTINGS_PATH.exists():
        try:
            cfg = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
            p = Path(cfg.get("dbc_path", "")).expanduser()
            if p:
                return p if p.exists() else None
        except Exception:
            pass
    return None


def get_dbc_path() -> Path | None:
    return _load_config_path()


def get_dbc():
    global _dbc_cache, DBC_PATH
    if _dbc_cache is None:
        DBC_PATH = get_dbc_path()
        if not DBC_PATH or not Path(DBC_PATH).exists():
            raise FileNotFoundError(
                "DBC file not configured. Open Settings and select a .dbc file."
            )
        _dbc_cache = cantools.database.load_file(Path(DBC_PATH))
    return _dbc_cache


# Back-compat exports (some modules import dbc and DBC_PATH directly)
DBC_PATH = get_dbc_path()
dbc = get_dbc()

__all__ = ["BASE_DIR", "DBC_PATH", "dbc", "get_dbc", "get_dbc_path"]
