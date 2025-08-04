#!/usr/bin/env python3
"""Sloki_performance.py
---------------------------------
Single-file script that combines the functionality of the Sloki J2534 driver,
a high-level CAN interface and a simple main loop that prints unique CAN
frames received from the device.  It mirrors the behaviour of
`hardware/drivers/j2534_sloki_driver.py`, `hardware/can_interface.py` and the
basic start-up sequence from `main.py`.
"""

import ctypes
import sys
from enum import Enum


# ---------------------------------------------------------------------------
# Low-level Sloki J2534 driver definitions
# ---------------------------------------------------------------------------

class CANFrame:
    """Simple representation of a CAN frame."""

    def __init__(self):
        self.CAN_ID = 0
        self.DLC = 0
        self.data = []

    def __repr__(self) -> str:  # pragma: no cover - helper for debugging
        return f"CANFrame(CAN_ID={self.CAN_ID}, DLC={self.DLC}, data={self.data})"


class J2534API:
    """Minimal subset of the Sloki J2534 API used by the tool."""

    def __init__(self):
        # NOTE: The DLL path is hard-coded exactly as in the original driver.
        self.j2534_dll = ctypes.WinDLL(
            r"C:\\Program Files (x86)\\Sloki\\SBUS\\lib\\x64\\sBus-J2534.dll"
        )
        self.device_id = ctypes.c_ulong()
        self.channel_id = ctypes.c_ulong()

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
        J1850VPW = 1
        J1850PWM = 2
        ISO9141 = 3
        ISO14230 = 4
        CAN = 5
        SCI_A_ENGINE = 7
        SCI_A_TRANS = 8
        SCI_B_ENGINE = 9
        SCI_B_TRANS = 10
        ISO15765 = 0x40

    # ---- Hardware API wrappers (unchanged from original driver) ----
    def SBusCanOpen(self):
        return self.j2534_dll.PassThruOpen(None, ctypes.byref(self.device_id))

    def SBusCanConnect(self, protocol, baudrate):
        return self.j2534_dll.PassThruConnect(
            self.device_id, protocol, 0, baudrate, ctypes.byref(self.channel_id)
        )

    def SBusCanClearRxMsg(self):
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

    def SBusCanSendMgs(self, CanFrame):
        pNumMsgs = ctypes.c_ulong(1)
        CAN = 5
        ISO15765_FRAME_PAD = 0x40
        CAN_29BIT_ID = 0x0100

        tx_msg = self.SMsg()
        tx_msg.ProtocolID = CAN
        tx_msg.DataSize = CanFrame.DLC + 4

        if CanFrame.CAN_ID > 0x7FF:
            tx_msg.TxFlags = CAN_29BIT_ID
        else:
            tx_msg.TxFlags = ISO15765_FRAME_PAD

        c_byte_array = (ctypes.c_ubyte * 4028)()
        CanFrame.CAN_ID = CanFrame.CAN_ID & 0x1FFFFFFF
        c_byte_array[0] = CanFrame.CAN_ID >> 24
        c_byte_array[1] = CanFrame.CAN_ID >> 16
        c_byte_array[2] = CanFrame.CAN_ID >> 8
        c_byte_array[3] = CanFrame.CAN_ID
        for i in range(8):
            c_byte_array[4 + i] = CanFrame.data[i]

        tx_msg.Data = c_byte_array
        return self.j2534_dll.PassThruWriteMsgs(
            self.channel_id, ctypes.byref(tx_msg), ctypes.byref(pNumMsgs), 0
        )

    def SBusCanRxSetFilter(self, CAN_Id):
        msgMask = self.SMsg()
        msgPattern = self.SMsg()

        CAN = 5
        ISO15765_FRAME_PAD = 0x40
        PASS_FILTER = ctypes.c_ulong(1)
        filterId = ctypes.c_ulong(0)

        msgMask.ProtocolID = CAN
        msgMask.DataSize = 4
        for i in range(4):
            msgMask.Data[i] = 0xFF

        msgPattern.ProtocolID = CAN
        msgPattern.DataSize = 4
        CAN_Id = CAN_Id & 0x1FFFFFFF
        msgPattern.Data[0] = CAN_Id >> 24
        msgPattern.Data[1] = CAN_Id >> 16
        msgPattern.Data[2] = CAN_Id >> 8
        msgPattern.Data[3] = CAN_Id

        return self.j2534_dll.PassThruStartMsgFilter(
            self.channel_id,
            PASS_FILTER,
            ctypes.byref(msgMask),
            ctypes.byref(msgPattern),
            None,
            ctypes.byref(filterId),
        )

    def SBusCanReadMgs(self, timeout=0):
        CAN = 5
        rx_msg = self.SMsg()
        rx_msg.ProtocolID = CAN
        num_msgs = ctypes.c_ulong(1)
        status = self.j2534_dll.PassThruReadMsgs(
            self.channel_id, ctypes.byref(rx_msg), ctypes.byref(num_msgs), timeout
        )

        response = bytearray(rx_msg.Data)
        frame = CANFrame()
        frame.CAN_ID = (
            (response[0] << 24)
            | (response[1] << 16)
            | (response[2] << 8)
            | response[3]
        )
        frame.DLC = rx_msg.DataSize - 4
        frame.data = [response[4 + i] for i in range(frame.DLC)]
        return status, frame

    def SBusCanDisconnect(self):
        return self.j2534_dll.PassThruDisconnect(self.channel_id)

    def SBusCanClose(self):
        return self.j2534_dll.PassThruClose(self.device_id)


# ---------------------------------------------------------------------------
# High-level CAN interface
# ---------------------------------------------------------------------------

class CANInterface:
    """High-level wrapper around the low-level J2534 API."""

    def __init__(self, baudrate: int = 500000):
        self.api = J2534API()
        self.protocol = J2534API.Protocol_ID.CAN
        self.baudrate = baudrate

    def connect(self):
        if self.api.SBusCanOpen() != 0:
            raise ConnectionError("Failed to open CAN device")
        if self.api.SBusCanConnect(self.protocol.value, self.baudrate) != 0:
            raise ConnectionError("Failed to connect to CAN bus")
        self.api.SBusCanClearRxMsg()

    def disconnect(self):
        self.api.SBusCanDisconnect()
        self.api.SBusCanClose()

    def transmit(self, can_id, data):
        frame = CANFrame()
        frame.CAN_ID = can_id
        frame.DLC = len(data)
        frame.data = data
        return self.api.SBusCanSendMgs(frame)

    def receive(self, timeout: int = 10):
        status, frame = self.api.SBusCanReadMgs(timeout)
        if status == 0:
            return frame
        return None

    def set_filter(self, can_id):
        return self.api.SBusCanRxSetFilter(can_id)


# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------

def print_table(frames):
    """Prints collected CAN frames as a simple table."""
    print(f"{'CAN ID':<10} {'DLC':<5} {'DATA'}")
    print("-" * 32)
    for frame in frames:
        data_str = " ".join(f"{byte:02X}" for byte in frame.data)
        print(f"{frame.CAN_ID:08X} {frame.DLC:<5} {data_str}")


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

def main():
    interface = CANInterface(baudrate=500000)
    try:
        interface.connect()
    except Exception as exc:  # pragma: no cover - runtime safeguard
        print(f"Failed to connect to CAN device: {exc}", file=sys.stderr)
        sys.exit(1)

    unique_frames = {}
    try:
        while True:
            frame = interface.receive(timeout=10)
            if frame is None:
                continue
            key = (frame.CAN_ID, tuple(frame.data))
            if key not in unique_frames:
                unique_frames[key] = frame
    except KeyboardInterrupt:
        pass
    finally:
        interface.disconnect()

    print_table(unique_frames.values())


if __name__ == "__main__":
    main()
