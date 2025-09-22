"""
PEAK_API.py  –  one stop for hardware details.

Exposes
    get_config_and_bus() -> (settings_dict, bus_like_object)

The returned `bus.recv()` always yields a `SimpleMessage` with:
    arbitration_id • is_extended_id • data • timestamp
so the rest of the app never touches python-can directly.
"""
from pathlib import Path
from typing import Dict, Tuple
from collections import namedtuple
import sys
import os
import ctypes

# ---- user knob: run without hardware ----------------------
USE_DUMMY_BUS = False           # True → GUI runs, but no real frames
# -----------------------------------------------------------

SimpleMessage = namedtuple(
    "SimpleMessage",
    ["arbitration_id", "is_extended_id", "data", "timestamp"]
)

# -----------------------------------------------------------#
def _resolve_base_dir() -> Path:
    if hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def _preload_pcanbasic_dll() -> None:
    """Best-effort load of PCANBasic.dll from alongside the executable.

    In a frozen .exe, python-can's PCAN backend relies on the DLL being in the
    DLL search path. We try to add the folder and pre-load the DLL so subsequent
    imports succeed. Fails silently if the DLL isn't present.
    """
    try:
        base_dir = _resolve_base_dir()
        dll_path = base_dir / "PCANBasic.dll"
        if dll_path.exists():
            try:
                if hasattr(os, "add_dll_directory"):
                    os.add_dll_directory(str(base_dir))
                ctypes.WinDLL(str(dll_path))
                print(f"PCANBasic preloaded: {dll_path}")
            except OSError as e:
                print(f"Warning: Failed to load PCANBasic.dll: {e}")
        else:
            # Not fatal here; the user may have it in system PATH already
            print(f"PCANBasic.dll not found next to executable: {dll_path}")
    except Exception as e:
        print(f"Warning: PCANBasic preload error: {e}")


# -----------------------------------------------------------#
def _make_real_bus(settings):
    _preload_pcanbasic_dll()
    import can                       # local import only here
    kwargs = dict(interface="pcan",
                  channel=settings["PCAN_CHANNEL"],
                  bitrate=settings["BITRATE"])
    if settings["USE_CAN_FD"]:
        kwargs.update(fd=True, bitrate_fd=settings["DATA_PHASE"])
    real_bus = can.Bus(**kwargs)

    # Wrap to emit SimpleMessage
    class WrappedBus:
        def __init__(self):
            # capture outer scope references
            self._real = real_bus
            self._settings = settings
        def recv(self, timeout=0.1):
            msg = self._real.recv(timeout)
            if msg is None:
                return None
            return SimpleMessage(msg.arbitration_id,
                                 msg.is_extended_id,
                                 msg.data,
                                 msg.timestamp)
        def send(self, frame_id: int, is_extended: bool, data: bytes | bytearray):
            """Send a CAN (or CAN FD) frame.

            Arguments mirror usage in live_signal_transmit:
              - frame_id: arbitration ID (int)
              - is_extended: True for 29-bit ID, False for 11-bit
              - data: payload as bytes/bytearray
            """
            msg = can.Message(
                arbitration_id=frame_id,
                is_extended_id=bool(is_extended),
                data=bytes(data),
                is_fd=bool(self._settings.get("USE_CAN_FD", False)),
                bitrate_switch=bool(self._settings.get("USE_CAN_FD", False)),
            )
            return self._real.send(msg)
        def shutdown(self):
            self._real.shutdown()
    return WrappedBus()

# -----------------------------------------------------------#
class DummyBus:
    """Stand-in when hardware unavailable."""
    IS_DUMMY = True
    def recv(self, timeout: float = 0.1):
        import time; time.sleep(timeout)
        return None
    def send(self, frame_id: int, is_extended: bool, data: bytes | bytearray):
        # Simulate success; print for visibility when console is open
        try:
            print(f"[DummyBus] TX 0x{frame_id:X}{' (EXT)' if is_extended else ''} len={len(data)} data={[hex(b) for b in data]}")
        except Exception:
            pass
        return True
    def shutdown(self):
        pass

# -----------------------------------------------------------#
def get_config_and_bus() -> Tuple[Dict[str, object], object]:
    settings = {
        "PCAN_CHANNEL": "PCAN_USBBUS1",
        "BITRATE"     : 500_000,
        "USE_CAN_FD"  : False,
        "DATA_PHASE"  : "500K/2M",
    }

    print("\n========= Runtime Settings =========")
    for k, v in settings.items():
        print(f"{k:13}: {v}")
    print("====================================\n")

    if USE_DUMMY_BUS:
        return settings, DummyBus()

    try:
        bus = _make_real_bus(settings)
        return settings, bus
    except Exception as e:
        # Graceful fallback so the GUI still opens; surface the error via prints
        print("ERROR: Failed to initialize PCAN bus. Falling back to DummyBus.")
        print(f"       {type(e).__name__}: {e}")
        return settings, DummyBus()
if __name__ == "__main__":
    settings, bus = get_config_and_bus()
    
    print("Listening for 10 CAN messages...\n")
    count = 0
    while count < 10:
        msg = bus.recv()
        if msg is not None:
            print(f"[{count+1}] SimpleMessage:")
            print(f"  arbitration_id  : {hex(msg.arbitration_id)}")
            print(f"  is_extended_id  : {msg.is_extended_id}")
            print(f"  data            : {[hex(b) for b in msg.data]}")
            print(f"  timestamp       : {msg.timestamp}")
            print("-" * 40)
            count += 1

    bus.shutdown()
