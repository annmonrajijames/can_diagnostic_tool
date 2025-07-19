# j2534_sloki_driver.py
# ------------------------------------------------------------
# This file implements the J2534 interface specific to the Sloki hardware device.
# It is tightly coupled to Sloki's DLL. The logic should not be changed.
# However, comments are added to help generalize this structure in the future.
# ------------------------------------------------------------

import ctypes
import os
from enum import Enum
import winreg

# Generic CAN frame structure
class CANFrame:
    def __init__(self):
        self.CAN_ID = 0  # Equivalent to uint32_t
        self.DLC = 0     # Equivalent to uint8_t
        self.data = []   # Equivalent to uint8_t[8]

    def __repr__(self):
        return f"CANFrame(CAN_ID={self.CAN_ID}, DLC={self.DLC}, data={self.data})"


class J2534API:
    def __init__(self):
        # --- NOTE: Hardcoded path for Sloki DLL. ---
        # TODO: Future improvement: Load DLL path from config or allow user selection.
        self.j2534_dll = ctypes.WinDLL(r'C:\Program Files (x86)\Sloki\SBUS\lib\x64\sBus-J2534.dll')
        self.device_id = ctypes.c_ulong()
        self.channel_id = ctypes.c_ulong()

    # C struct for CAN messages used by J2534 API
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
        # Supported protocols (only CAN is used here)
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

    # ------------------------------------------------------------
    # J2534 Hardware API Functions (DO NOT MODIFY)
    # ------------------------------------------------------------

    def SBusCanOpen(self):
        return self.j2534_dll.PassThruOpen(None, ctypes.byref(self.device_id))

    def SBusCanConnect(self, protocol, baudrate):
        return self.j2534_dll.PassThruConnect(self.device_id, protocol, 0, baudrate, ctypes.byref(self.channel_id))

    def SBusCanClearRxMsg(self):
        # Clears CAN receive filters (used before setting new filters)
        DWORD = ctypes.c_ulong
        class SCONFIG(ctypes.Structure):
            _fields_ = [("Parameter", DWORD), ("Value", DWORD)]

        configList = SCONFIG()
        configList.Parameter = 0  # TODO: Replace with correct parameter constant if defined
        configList.Value = 0
        CLEAR_MSG_FILTERS = 0x0A
        return self.j2534_dll.PassThruIoctl(self.channel_id, CLEAR_MSG_FILTERS, ctypes.byref(configList), None)

    def SBusCanSendMgs(self, CanFrame):
        # Sends a CAN message to the connected channel
        pNumMsgs = ctypes.c_ulong(1)
        CAN = 5
        ISO15765_FRAME_PAD = 0x40
        CAN_29BIT_ID = 0x0100

        TxMsg = self.SMsg()
        TxMsg.ProtocolID = CAN
        TxMsg.DataSize = CanFrame.DLC + 4

        if CanFrame.CAN_ID > 0x7FF:
            TxMsg.TxFlags = CAN_29BIT_ID
        else:
            TxMsg.TxFlags = ISO15765_FRAME_PAD

        # Construct data: [4-byte CAN_ID] + [8-byte payload]
        c_byte_array = (ctypes.c_ubyte * 4028)()
        CanFrame.CAN_ID = (CanFrame.CAN_ID & 0x1FFFFFFF)
        c_byte_array[0] = (CanFrame.CAN_ID >> 24)
        c_byte_array[1] = (CanFrame.CAN_ID >> 16)
        c_byte_array[2] = (CanFrame.CAN_ID >> 8)
        c_byte_array[3] = (CanFrame.CAN_ID >> 0)
        for i in range(8):
            c_byte_array[4 + i] = CanFrame.data[i]

        TxMsg.Data = c_byte_array
        return self.j2534_dll.PassThruWriteMsgs(self.channel_id, ctypes.byref(TxMsg), ctypes.byref(pNumMsgs), 0)

    def SBusCanRxSetFilter(self, CAN_Id):
        # Sets a receive filter to capture specific CAN IDs
        msgMask = self.SMsg()
        msgPattern = self.SMsg()

        CAN = 5
        ISO15765_FRAME_PAD = 0x40
        PASS_FILTER = ctypes.c_ulong(1)
        filterId = ctypes.c_ulong(0)

        # Mask: Accept all bits
        msgMask.ProtocolID = CAN
        msgMask.DataSize = 4
        for i in range(4):
            msgMask.Data[i] = 0xFF

        # Pattern: Match specific CAN ID
        msgPattern.ProtocolID = CAN
        msgPattern.DataSize = 4
        CAN_Id = (CAN_Id & 0x1FFFFFFF)
        msgPattern.Data[0] = (CAN_Id >> 24)
        msgPattern.Data[1] = (CAN_Id >> 16)
        msgPattern.Data[2] = (CAN_Id >> 8)
        msgPattern.Data[3] = (CAN_Id >> 0)

        return self.j2534_dll.PassThruStartMsgFilter(self.channel_id, PASS_FILTER,
                                                     ctypes.byref(msgMask), ctypes.byref(msgPattern),
                                                     None, ctypes.byref(filterId))

    def SBusCanReadMgs(self, timeout=0, num_msgs=1):
        """Read one or more CAN messages from the hardware interface.

        Parameters
        ----------
        timeout : int, optional
            Time to wait for messages in milliseconds.
        num_msgs : int, optional
            Maximum number of messages to read in a single call.

        Returns
        -------
        tuple
            (status, [CANFrame, ...]) where ``status`` is the underlying driver
            return code and the list contains all successfully read frames.
        """

        CAN = 5
        RxArray = (self.SMsg * num_msgs)()
        for msg in RxArray:
            msg.ProtocolID = CAN

        msgs_to_read = ctypes.c_ulong(num_msgs)
        status = self.j2534_dll.PassThruReadMsgs(self.channel_id,
                                                 RxArray,
                                                 ctypes.byref(msgs_to_read),
                                                 timeout)

        frames = []
        for i in range(msgs_to_read.value):
            Rx_Msg = RxArray[i]
            raw = bytes(Rx_Msg.Data[:Rx_Msg.DataSize])
            if len(raw) < 4:
                continue
            frame = CANFrame()
            frame.CAN_ID = (
                (raw[0] << 24)
                | (raw[1] << 16)
                | (raw[2] << 8)
                | raw[3]
            )
            frame.DLC = Rx_Msg.DataSize - 4
            frame.data = [raw[4 + j] for j in range(frame.DLC)]
            frames.append(frame)

        return status, frames

    def SBusCanDisconnect(self):
        return self.j2534_dll.PassThruDisconnect(self.channel_id)

    def SBusCanClose(self):
        return self.j2534_dll.PassThruClose(self.device_id)
