# hardware/driver_loader.py
# Dynamically loads and interacts with any J2534-compatible DLL

import ctypes
from enum import Enum
from pathlib import Path

# Custom exception for J2534-related errors
class J2534Error(Exception):
    pass

# Data structure to represent a decoded CAN frame
class CANFrame:
    def __init__(self):
        self.CAN_ID = 0
        self.DLC = 0
        self.data = []

    def __repr__(self):
        return f"CANFrame(CAN_ID={self.CAN_ID}, DLC={self.DLC}, data={self.data})"

# Supported Protocols (extendable)
class ProtocolID(Enum):
    CAN = 5
    ISO15765 = 0x40

class J2534Driver:
    def __init__(self, dll_path: str):
        if not Path(dll_path).is_file():
            raise FileNotFoundError(f"DLL not found at: {dll_path}")

        self.dll = ctypes.WinDLL(dll_path)
        self.device_id = ctypes.c_ulong()
        self.channel_id = ctypes.c_ulong()

        self._define_message_structure()

    def _define_message_structure(self):
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
        self.SMsg = SMsg

    def open(self):
        status = self.dll.PassThruOpen(None, ctypes.byref(self.device_id))
        if status != 0:
            raise J2534Error("PassThruOpen failed")
        return status

    def connect(self, protocol=ProtocolID.CAN.value, baudrate=500000):
        status = self.dll.PassThruConnect(
            self.device_id,
            protocol,
            0,
            baudrate,
            ctypes.byref(self.channel_id)
        )
        if status != 0:
            raise J2534Error("PassThruConnect failed")
        return status

    def disconnect(self):
        self.dll.PassThruDisconnect(self.channel_id)
        self.dll.PassThruClose(self.device_id)

    def send(self, frame: CANFrame):
        msg = self.SMsg()
        pNumMsgs = ctypes.c_ulong(1)

        # Frame flags
        CAN_29BIT_ID = 0x0100
        ISO15765_PAD = 0x40

        msg.ProtocolID = ProtocolID.CAN.value
        msg.TxFlags = CAN_29BIT_ID if frame.CAN_ID > 0x7FF else ISO15765_PAD
        msg.DataSize = frame.DLC + 4

        # Set CAN ID (first 4 bytes)
        msg.Data[0] = (frame.CAN_ID >> 24) & 0xFF
        msg.Data[1] = (frame.CAN_ID >> 16) & 0xFF
        msg.Data[2] = (frame.CAN_ID >> 8) & 0xFF
        msg.Data[3] = frame.CAN_ID & 0xFF

        # Set Data bytes
        for i in range(frame.DLC):
            msg.Data[4 + i] = frame.data[i]

        return self.dll.PassThruWriteMsgs(
            self.channel_id, ctypes.byref(msg), ctypes.byref(pNumMsgs), 0
        )

    def read(self, timeout=10):
        msg = self.SMsg()
        pNumMsgs = ctypes.c_ulong(1)

        status = self.dll.PassThruReadMsgs(
            self.channel_id, ctypes.byref(msg), ctypes.byref(pNumMsgs), timeout
        )
        if status != 0:
            return None

        raw_data = bytearray(msg.Data)
        can_id = (
            (raw_data[0] << 24) |
            (raw_data[1] << 16) |
            (raw_data[2] << 8) |
            raw_data[3]
        )

        dlc = msg.DataSize - 4
        data = [raw_data[4 + i] for i in range(dlc)]

        frame = CANFrame()
        frame.CAN_ID = can_id
        frame.DLC = dlc
        frame.data = data
        return frame
