"""
Settings_page.py  –  one stop for hardware details.

Exposes
    get_config_and_bus() -> (settings_dict, bus_like_object)

The returned `bus.recv()` always yields a `SimpleMessage` with:
    arbitration_id • is_extended_id • data • timestamp
so the rest of the app never touches python-can directly.
"""
from pathlib import Path
from typing import Dict, Tuple
from collections import namedtuple

# ---- user knob: run without hardware ----------------------
USE_DUMMY_BUS = False           # True → GUI runs, but no real frames
# -----------------------------------------------------------

SimpleMessage = namedtuple(
    "SimpleMessage",
    ["arbitration_id", "is_extended_id", "data", "timestamp"]
)

# -----------------------------------------------------------#
def _make_real_bus(settings):
    import can                       # local import only here
    kwargs = dict(interface="pcan",
                  channel=settings["PCAN_CHANNEL"],
                  bitrate=settings["BITRATE"])
    if settings["USE_CAN_FD"]:
        kwargs.update(fd=True, bitrate_fd=settings["DATA_PHASE"])
    real_bus = can.Bus(**kwargs)

    # Wrap to emit SimpleMessage
    class WrappedBus:
        def recv(self, timeout=0.1):
            msg = real_bus.recv(timeout)
            if msg is None:
                return None
            return SimpleMessage(msg.arbitration_id,
                                 msg.is_extended_id,
                                 msg.data,
                                 msg.timestamp)
        def shutdown(self):
            real_bus.shutdown()
    return WrappedBus()

# -----------------------------------------------------------#
class DummyBus:
    """Stand-in when hardware unavailable."""
    def recv(self, timeout: float = 0.1):
        import time; time.sleep(timeout)
        return None
    def shutdown(self):
        pass

# -----------------------------------------------------------#
BASE_DIR = Path(__file__).resolve().parent.parent
def get_config_and_bus() -> Tuple[Dict[str, object], object]:
    settings = {
        "DBC_PATH"    : BASE_DIR / "data" / "DBC_sample_cantools.dbc",
        "PCAN_CHANNEL": "PCAN_USBBUS1",
        "BITRATE"     : 500_000,
        "USE_CAN_FD"  : False,
        "DATA_PHASE"  : "500K/2M",
    }

    print("\n========= Runtime Settings =========")
    for k, v in settings.items():
        print(f"{k:13}: {v}")
    print("====================================\n")

    bus = DummyBus() if USE_DUMMY_BUS else _make_real_bus(settings)
    return settings, bus
