"""Utility to monitor Sloki CAN bus statistics.

The script connects to a Sloki J2534 interface and prints basic throughput
information such as the number of frames received per second and the running
throughput total.  It is intended for quick benchmarking or monitoring of a
Sloki device and relies only on the J2534 DLL provided by the vendor.
"""

from __future__ import annotations

import ctypes
import time
from enum import Enum


class J2534API:
    """Minimal wrapper around the Sloki J2534 DLL."""

    class SMsg(ctypes.Structure):
        _fields_ = [
            ("ProtocolID", ctypes.c_ulong),
            ("RxStatus", ctypes.c_ulong),
            ("TxFlags", ctypes.c_ulong),
            ("Timestamp", ctypes.c_ulong),
            ("DataSize", ctypes.c_ulong),
            ("ExtraDataPtr", ctypes.c_ulong),
            ("Data", ctypes.c_ubyte * 4028),
        ]

    class Protocol_ID(Enum):
        CAN = 5

    def __init__(self) -> None:
        self.j2534_dll = ctypes.WinDLL(
            r"C:\\Program Files (x86)\\Sloki\\SBUS\\lib\\x64\\sBus-J2534.dll"
        )
        self.device_id = ctypes.c_ulong()
        self.channel_id = ctypes.c_ulong()

    def open(self) -> int:
        return self.j2534_dll.PassThruOpen(None, ctypes.byref(self.device_id))

    def connect(self, protocol: int, baudrate: int) -> int:
        return self.j2534_dll.PassThruConnect(
            self.device_id, protocol, 0, baudrate, ctypes.byref(self.channel_id)
        )

    def clear_rx(self) -> int:
        DWORD = ctypes.c_ulong

        class SCONFIG(ctypes.Structure):
            _fields_ = [("Parameter", DWORD), ("Value", DWORD)]

        config_list = SCONFIG()
        config_list.Parameter = 0
        config_list.Value = 0
        CLEAR_MSG_FILTERS = 0x0A
        return self.j2534_dll.PassThruIoctl(
            self.channel_id, CLEAR_MSG_FILTERS, ctypes.byref(config_list), None
        )

    def read_msg(self, timeout: int = 0) -> tuple[int, "J2534API.SMsg"]:
        msg = self.SMsg()
        msg.ProtocolID = self.Protocol_ID.CAN.value
        num_msgs = ctypes.c_ulong(1)
        status = self.j2534_dll.PassThruReadMsgs(
            self.channel_id, ctypes.byref(msg), ctypes.byref(num_msgs), timeout
        )
        return status, msg

    def disconnect(self) -> int:
        return self.j2534_dll.PassThruDisconnect(self.channel_id)

    def close(self) -> int:
        return self.j2534_dll.PassThruClose(self.device_id)


def monitor(baudrate: int = 500000) -> None:
    """Continuously print basic CAN bus statistics."""

    api = J2534API()
    if api.open() != 0:
        raise RuntimeError("Failed to open Sloki device")
    if api.connect(J2534API.Protocol_ID.CAN.value, baudrate) != 0:
        raise RuntimeError("Failed to connect to Sloki device")
    api.clear_rx()

    input("Press Enter to start the statistics")

    total = 0
    count = 0
    last_report = time.time()

    try:
        while True:
            status, _ = api.read_msg(10)
            if status != 0:
                continue

            total += 1
            count += 1
            now = time.time()
            if now - last_report >= 1.0:
                frames_per_second = count / (now - last_report)
                print(f"{frames_per_second:7.2f} frames/s  |  total: {total}")
                last_report = now
                count = 0
    except KeyboardInterrupt:  # pragma: no cover - user interruption
        pass
    finally:
        api.disconnect()
        api.close()


def main() -> int:  # pragma: no cover - CLI entry point
    monitor()
    return 0


if __name__ == "__main__":  # pragma: no cover - module test
    raise SystemExit(main())
