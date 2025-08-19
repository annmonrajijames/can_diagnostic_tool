"""
Sloki_API.py
----------------------
Sloki J2534-backed bus that matches the PEAK Settings_page.py standard,
but with timestamp in **milliseconds** so cycle-time (ms) is a simple delta.

Public API:
    get_config_and_bus() -> (settings_dict, bus_like_object)

The returned `bus` provides:
    • recv(timeout)  -> SimpleMessage | None
    • send(arbitration_id, data, is_extended_id=False) -> int
    • shutdown()

SimpleMessage matches PEAK version by fields:
    arbitration_id • is_extended_id • data • timestamp

Differences:
    - timestamp is in **milliseconds** (float), not seconds.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Tuple, Optional, Sequence, Set
from collections import namedtuple
import ctypes
import time
from dbc_decode_input import dbc, DBC_PATH

print(f"Loaded DBC: {DBC_PATH}  (messages: {len(dbc.messages)})")

# ── SimpleMessage (shared shape with PEAK version) ────────────
SimpleMessage = namedtuple(
    "SimpleMessage",
    ["arbitration_id", "is_extended_id", "data", "timestamp"]  # timestamp in **ms**
)

# ── J2534 / Sloki bindings ────────────────────────────────────
DWORD = ctypes.c_ulong
ULONG = ctypes.c_ulong
BYTE  = ctypes.c_ubyte

PROTO_CAN         = 0x00000005
CAN_29BIT_ID      = 0x00000100   # flag bit for 29-bit frames
CAN_ID_BOTH       = 0x00000800   # connect flag: accept 11-bit & 29-bit
CLEAR_MSG_FILTERS = 0x0000000A

MAX_BYTES = 4028  # Sloki buffer size

class PASS_THRU_MSG(ctypes.Structure):
    _fields_ = [
        ("ProtocolID",     ULONG),
        ("RxStatus",       ULONG),
        ("TxFlags",        ULONG),
        ("Timestamp",      ULONG),     # µs since connect
        ("DataSize",       ULONG),
        ("ExtraDataIndex", ULONG),     # J2534 v04.04 name/type
        ("Data",           BYTE * MAX_BYTES),
    ]

class J2534API:
    """Thin ctypes wrapper for sBus-J2534.dll."""
    def __init__(self, dll_path: str):
        self.j2534 = ctypes.WinDLL(dll_path)
        self.device_id  = ULONG()
        self.channel_id = ULONG()

        self.j2534.PassThruOpen.argtypes      = [ctypes.c_void_p, ctypes.POINTER(ULONG)]
        self.j2534.PassThruOpen.restype       = ULONG
        self.j2534.PassThruConnect.argtypes   = [ULONG, ULONG, ULONG, ULONG, ctypes.POINTER(ULONG)]
        self.j2534.PassThruConnect.restype    = ULONG
        self.j2534.PassThruClose.argtypes     = [ULONG]
        self.j2534.PassThruClose.restype      = ULONG
        self.j2534.PassThruDisconnect.argtypes= [ULONG]
        self.j2534.PassThruDisconnect.restype = ULONG
        self.j2534.PassThruIoctl.argtypes     = [ULONG, ULONG, ctypes.c_void_p, ctypes.c_void_p]
        self.j2534.PassThruIoctl.restype      = ULONG
        self.j2534.PassThruReadMsgs.argtypes  = [ULONG, ctypes.POINTER(PASS_THRU_MSG), ctypes.POINTER(ULONG), ULONG]
        self.j2534.PassThruReadMsgs.restype   = ULONG
        self.j2534.PassThruWriteMsgs.argtypes = [ULONG, ctypes.POINTER(PASS_THRU_MSG), ctypes.POINTER(ULONG), ULONG]
        self.j2534.PassThruWriteMsgs.restype  = ULONG

    def open(self) -> int:
        return int(self.j2534.PassThruOpen(None, ctypes.byref(self.device_id)))

    def connect(self, protocol: int, flags: int, bitrate: int) -> int:
        return int(self.j2534.PassThruConnect(self.device_id, protocol, flags, bitrate, ctypes.byref(self.channel_id)))

    def disconnect(self) -> int:
        return int(self.j2534.PassThruDisconnect(self.channel_id))

    def close(self) -> int:
        return int(self.j2534.PassThruClose(self.device_id))

    def clear_filters(self) -> int:
        class SCONFIG(ctypes.Structure):
            _fields_ = [("Parameter", DWORD), ("Value", DWORD)]
        dummy = SCONFIG(0, 0)
        return int(self.j2534.PassThruIoctl(self.channel_id, CLEAR_MSG_FILTERS, ctypes.byref(dummy), None))

    def read_msg(self, timeout_ms: int) -> tuple[int, Optional[PASS_THRU_MSG]]:
        msg = PASS_THRU_MSG()
        num = ULONG(1)
        status = int(self.j2534.PassThruReadMsgs(self.channel_id, ctypes.byref(msg), ctypes.byref(num), timeout_ms))
        if status == 0 and num.value == 1:
            return status, msg
        return status, None

    def write_msg(self, msg: PASS_THRU_MSG, timeout_ms: int = 0) -> int:
        num = ULONG(1)
        return int(self.j2534.PassThruWriteMsgs(self.channel_id, ctypes.byref(msg), ctypes.byref(num), timeout_ms))

# ── High-level bus adapter (matches PEAK wrapper contract) ────
class SlokiBus:
    """
    recv() -> SimpleMessage(arbitration_id, is_extended_id, data, timestamp_ms)
    send() -> status int
    shutdown()
    """

    def __init__(self, dll_path: str, bitrate: int,
                 force_extended: bool = False,
                 dbc_path: Optional[Path] = None,
                 enable_dbc_assist: bool = True):
        self.api = J2534API(dll_path)
        st = self.api.open()
        if st != 0:
            raise RuntimeError(f"PassThruOpen failed: {st}")

        # Accept both 11-bit and 29-bit IDs.
        st = self.api.connect(PROTO_CAN, CAN_ID_BOTH, bitrate)
        if st != 0:
            raise RuntimeError(f"PassThruConnect failed: {st}")

        self.api.clear_filters()  # best-effort

        # Base in **milliseconds** to keep units consistent
        self._t0_ms = time.monotonic() * 1000.0
        self._force_extended = bool(force_extended)

        # Pre-compute ID type from DBC (optional)
        self._dbc_assist = bool(enable_dbc_assist)
        self._dbc_std_ids: Set[int] = set()
        self._dbc_ext_ids: Set[int] = set()
        if self._dbc_assist and dbc_path is not None and Path(dbc_path).exists():
            try:
                import cantools
                db = cantools.database.load_file(str(dbc_path))
                for msg in db.messages:
                    if getattr(msg, "is_extended_frame", False):
                        self._dbc_ext_ids.add(msg.frame_id & 0x1FFFFFFF)
                    else:
                        self._dbc_std_ids.add(msg.frame_id & 0x7FF)
            except Exception:
                self._dbc_assist = False  # fall back gracefully

    @staticmethod
    def _pack_tx(arbitration_id: int, data: bytes | Sequence[int], is_extended_id: bool) -> PASS_THRU_MSG:
        if not isinstance(data, (bytes, bytearray)):
            data = bytes(data)
        if len(data) > 8:
            raise ValueError("Classic CAN only (≤ 8 bytes).")

        msg = PASS_THRU_MSG()
        msg.ProtocolID = PROTO_CAN
        msg.RxStatus   = 0
        msg.TxFlags    = CAN_29BIT_ID if is_extended_id else 0
        msg.Timestamp  = 0
        msg.DataSize   = len(data) + 4

        arb = arbitration_id & 0x1FFFFFFF
        msg.Data[0] = (arb >> 24) & 0xFF
        msg.Data[1] = (arb >> 16) & 0xFF
        msg.Data[2] = (arb >> 8)  & 0xFF
        msg.Data[3] = (arb >> 0)  & 0xFF
        for i, b in enumerate(data):
            msg.Data[4 + i] = b
        return msg

    def _resolve_is_extended(self, raw: PASS_THRU_MSG, arb: int) -> bool:
        # 1) Spec flags first
        if self._force_extended:
            return True
        if (raw.RxStatus & CAN_29BIT_ID) or (raw.TxFlags & CAN_29BIT_ID):
            return True

        # 2) DBC assist
        if self._dbc_assist:
            in_ext = (arb in self._dbc_ext_ids)
            in_std = ((arb & 0x7FF) in self._dbc_std_ids)
            if in_ext and not in_std:
                return True
            if in_std and not in_ext:
                return False
            # if both/neither, fall through

        # 3) Heuristic
        return bool(arb > 0x7FF)

    def _unpack_rx(self, m: PASS_THRU_MSG) -> SimpleMessage:
        arb = ((m.Data[0] << 24) | (m.Data[1] << 16) | (m.Data[2] << 8) | m.Data[3]) & 0x1FFFFFFF
        dlc = max(0, int(m.DataSize) - 4)
        payload = bytes(m.Data[4:4+dlc])
        is_ext = self._resolve_is_extended(m, arb)

        # Convert J2534 µs into **milliseconds**, then add ms base
        ts_ms = self._t0_ms + (m.Timestamp / 1000.0)

        return SimpleMessage(arb, is_ext, payload, ts_ms)

    def recv(self, timeout: Optional[float] = None) -> Optional[SimpleMessage]:
        # timeout is given in seconds → convert to ms for J2534
        ms = 0 if timeout is None else max(0, int(timeout * 1000))
        status, msg = self.api.read_msg(ms)
        if status != 0 or msg is None:
            return None
        return self._unpack_rx(msg)

    def send(self, arbitration_id: int, data: bytes | Sequence[int], is_extended_id: bool = False) -> int:
        tx = self._pack_tx(arbitration_id, data, is_extended_id)
        return self.api.write_msg(tx, timeout_ms=0)

    def shutdown(self):
        try:
            self.api.disconnect()
        finally:
            self.api.close()

# ── Factory ───────────────────────────────────────────────────
def _make_real_bus(settings) -> SlokiBus:
    return SlokiBus(
        dll_path=settings["SLOKI_DLL"],
        bitrate=settings["BITRATE"],
        force_extended=settings.get("FORCE_EXTENDED", False),
        dbc_path=settings.get("DBC_PATH"),
        enable_dbc_assist=settings.get("DBC_ASSISTED_ID_TYPE", True),
    )

BASE_DIR = Path(__file__).resolve().parent.parent
def get_config_and_bus() -> Tuple[Dict, object]:
    settings: Dict = {
        # Keep same keys as PEAK version
        "DBC_PATH"    : DBC_PATH,
        "PCAN_CHANNEL" : "PCAN_USBBUS1",
        "BITRATE"      : 500_000,
        "USE_CAN_FD"   : False,
        "DATA_PHASE"   : "500K/2M",

        # Sloki-specific
        "SLOKI_DLL"    : r"C:\Program Files (x86)\Sloki\SBUS\lib\x64\sBus-J2534.dll",

        # Behavior
        "FORCE_EXTENDED"       : False,  # prefer flags/DBC
        "DBC_ASSISTED_ID_TYPE" : True,   # True → match PEAK behavior against your DBC
    }
    bus = _make_real_bus(settings)
    return settings, bus

# ── Optional: tiny standalone smoke test ──────────────────────
if __name__ == "__main__":
    settings, bus = get_config_and_bus()

    print("\n========= Runtime Settings =========")
    print(f"DBC_PATH     : {settings['DBC_PATH']}")
    print(f"PCAN_CHANNEL : {settings['PCAN_CHANNEL']}")
    print(f"BITRATE      : {settings['BITRATE']}")
    print(f"USE_CAN_FD   : {settings['USE_CAN_FD']}")
    print(f"DATA_PHASE   : {settings['DATA_PHASE']}")
    print("====================================\n")
    print("uptime library not available, timestamps are relative to boot time and not to Epoch UTC")
    print("Listening for 10 CAN messages...\n")

    try:
        cnt = 0
        while cnt < 10:
            m = bus.recv(timeout=0.05)
            if m is None:
                continue
            cnt += 1
            print(f"[{cnt}] SimpleMessage:")
            print(f"  arbitration_id  : {hex(m.arbitration_id)}")
            print(f"  is_extended_id  : {m.is_extended_id}")
            print(f"  data            : {[hex(b) for b in m.data]}")
            print(f"  timestamp (ms)  : {m.timestamp}")
            print("----------------------------------------")
    except KeyboardInterrupt:
        pass
    finally:
        bus.shutdown()
