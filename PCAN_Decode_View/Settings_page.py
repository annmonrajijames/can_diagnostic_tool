"""
Settings_page.py
---------------------------------------------------------
All hardware-specific details live here.
If you change interface, channel, bitrate, or move to a
different CAN library, edit only this file.

It exposes one public function:

    get_config_and_bus() -> (settings_dict, bus_like_object)

The returned `bus` must provide:
    • recv(timeout)  -> message | None
    • shutdown()     (optional but nice to have)

For offline testing set USE_DUMMY_BUS = True – a synthetic
bus that yields no messages but lets the GUI run.
"""
from pathlib import Path
from typing import Dict, Tuple
import can

USE_DUMMY_BUS = False          # ← flip to True for hardware-free demo

# -------------------------------------------------- #
def _build_real_bus(settings) -> "can.Bus":
    import can                                        # local import only
    kwargs = dict(interface="pcan",
                  channel=settings["PCAN_CHANNEL"],
                  bitrate=settings["BITRATE"])
    if settings["USE_CAN_FD"]:
        kwargs.update(fd=True, bitrate_fd=settings["DATA_PHASE"])
    return can.Bus(**kwargs)

# -------------------------------------------------- #
class DummyBus:
    """Minimal stand-in so the viewer runs without hardware."""
    def recv(self, timeout: float = 0.1):
        import time
        time.sleep(timeout)
        return None
    def shutdown(self):
        pass

# -------------------------------------------------- #
def get_config_and_bus() -> Tuple[Dict[str, object], object]:
    settings = {
        "DBC_PATH"    : Path(r"C:\Git_projects\can_diagnostic_tool\data\DBC_sample_cantools.dbc"),
        "PCAN_CHANNEL": "PCAN_USBBUS1",
        "BITRATE"     : 500_000,
        "USE_CAN_FD"  : False,
        "DATA_PHASE"  : "500K/2M",
    }

    print("\n========= Runtime Settings =========")
    for k, v in settings.items():
        print(f"{k:13}: {v}")
    print("====================================\n")

    bus = DummyBus() if USE_DUMMY_BUS else _build_real_bus(settings)
    return settings, bus
