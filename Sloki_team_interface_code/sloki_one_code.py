# sloki_can_tool.py

import ctypes
from enum import Enum


class CANFrame:
    def __init__(self):
        self.CAN_ID = 0
        self.DLC = 0
        self.data = []

    def __repr__(self):
        return f"CANFrame(CAN_ID={self.CAN_ID}, DLC={self.DLC}, data={self.data})"


class J2534API:
    def __init__(self):
        self.j2534_dll = ctypes.WinDLL(r'C:\Program Files (x86)\Sloki\SBUS\lib\x64\sBus-J2534.dll')
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
        ISO15765 = 0x40

    def SBusCanOpen(self):
        return self.j2534_dll.PassThruOpen(None, ctypes.byref(self.device_id))

    def SBusCanConnect(self, protocol, baudrate):
        return self.j2534_dll.PassThruConnect(self.device_id, protocol, 0, baudrate, ctypes.byref(self.channel_id))

    def SBusCanClearRxMsg(self):
        DWORD = ctypes.c_ulong

        class SCONFIG(ctypes.Structure):
            _fields_ = [("Parameter", DWORD), ("Value", DWORD)]

        configList = SCONFIG(Parameter=0, Value=0)
        CLEAR_MSG_FILTERS = 0x0A
        return self.j2534_dll.PassThruIoctl(self.channel_id, CLEAR_MSG_FILTERS, ctypes.byref(configList), None)

    def SBusCanSendMgs(self, CanFrame):
        pNumMsgs = ctypes.c_ulong(1)
        CAN = 5
        ISO15765_FRAME_PAD = 0x40
        CAN_29BIT_ID = 0x0100

        TxMsg = self.SMsg()
        TxMsg.ProtocolID = CAN
        TxMsg.DataSize = CanFrame.DLC + 4
        TxMsg.TxFlags = CAN_29BIT_ID if CanFrame.CAN_ID > 0x7FF else ISO15765_FRAME_PAD

        CanFrame.CAN_ID &= 0x1FFFFFFF
        c_byte_array = (ctypes.c_ubyte * 4028)()
        c_byte_array[0:4] = [(CanFrame.CAN_ID >> shift) & 0xFF for shift in (24, 16, 8, 0)]
        for i in range(CanFrame.DLC):
            c_byte_array[4 + i] = CanFrame.data[i]

        TxMsg.Data = c_byte_array
        return self.j2534_dll.PassThruWriteMsgs(self.channel_id, ctypes.byref(TxMsg), ctypes.byref(pNumMsgs), 0)

    def SBusCanRxSetFilter(self, CAN_Id):
        CAN = 5
        ISO15765_FRAME_PAD = 0x40
        PASS_FILTER = ctypes.c_ulong(1)
        filterId = ctypes.c_ulong(0)

        msgMask = self.SMsg()
        msgPattern = self.SMsg()

        for msg in (msgMask, msgPattern):
            msg.ProtocolID = CAN
            msg.RxStatus = 0
            msg.TxFlags = ISO15765_FRAME_PAD
            msg.Timestamp = 0
            msg.DataSize = 4

        msgMask.Data[0:4] = [0xFF] * 4
        CAN_Id &= 0x1FFFFFFF
        msgPattern.Data[0:4] = [(CAN_Id >> shift) & 0xFF for shift in (24, 16, 8, 0)]

        return self.j2534_dll.PassThruStartMsgFilter(
            self.channel_id, PASS_FILTER, ctypes.byref(msgMask), ctypes.byref(msgPattern), None, ctypes.byref(filterId)
        )

    def SBusCanReadMgs(self, timeout=10):
        CAN = 5
        Rx_Msg = self.SMsg()
        Rx_Msg.ProtocolID = CAN
        num_msgs = ctypes.c_ulong(1)

        status = self.j2534_dll.PassThruReadMsgs(
            self.channel_id, ctypes.byref(Rx_Msg), ctypes.byref(num_msgs), timeout
        )

        response = bytearray(Rx_Msg.Data)
        frame = CANFrame()
        frame.CAN_ID = sum([response[i] << shift for i, shift in zip(range(4), (24, 16, 8, 0))])
        frame.DLC = Rx_Msg.DataSize - 4
        frame.data = [response[4 + i] for i in range(frame.DLC)]

        return status, frame

    def SBusCanDisconnect(self):
        return self.j2534_dll.PassThruDisconnect(self.channel_id)

    def SBusCanClose(self):
        return self.j2534_dll.PassThruClose(self.device_id)


# -------------------------------
# Example Usage
# -------------------------------

if __name__ == "__main__":
    japi = J2534API()
    protocol = J2534API.Protocol_ID.CAN
    baudrate = 500000

    if japi.SBusCanOpen() != 0:
        print("Failed to open device")
        exit()

    if japi.SBusCanConnect(protocol.value, baudrate) != 0:
        print("Failed to connect")
        exit()

    if japi.SBusCanClearRxMsg() != 0:
        print("Failed to clear RX")
        exit()

    # Prepare a CAN frame
    frame = CANFrame()
    frame.CAN_ID = 0x120
    frame.DLC = 8
    frame.data = [1, 2, 3, 4, 5, 6, 7, 8]

    # Send to 3 different IDs
    for can_id in [0x120, 0x700, 0x180014]:
        frame.CAN_ID = can_id
        if japi.SBusCanSendMgs(frame) != 0:
            print(f"Failed to send to {hex(can_id)}")

    # Read loop
    try:
        print("Listening for messages (Press Ctrl+C to stop)...")
        while True:
            status, rx_frame = japi.SBusCanReadMgs(timeout=10)
            if status == 0:
                print(f"ID: {hex(rx_frame.CAN_ID)} | DLC: {rx_frame.DLC} | Data: {[hex(d) for d in rx_frame.data]}")
    except KeyboardInterrupt:
        print("Stopped listening.")

    # Disconnect and cleanup
    japi.SBusCanDisconnect()
    japi.SBusCanClose()
