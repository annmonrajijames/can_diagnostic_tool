import ctypes
import os
from enum import Enum
import winreg

class CANFrame:
    def __init__(self):
        self.CAN_ID = 0  # Equivalent to uint32_t
        self.DLC = 0        # Equivalent to uint8_t
        self.data = []      # Equivalent to uint8_t[8]

    def __repr__(self):
        return f"CANFrame(CAN_ID={self.CAN_ID}, DLC={self.DLC}, data={self.data})"
    



class J2534API:
    def __init__(self):
        # self.current_directory = os.getcwd()
        # self.j2534_dll = ctypes.WinDLL(self.current_directory + '/J2534.dll')
        # self.j2534_dll = ctypes.WinDLL('C:\Program Files (x86)\Sloki\SBUS\lib\sBus-J2534.dll')
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
            ("Data", ctypes.c_ubyte * 4028),  # Array of 4028 bytes (uint8_t)
        ]
    
    class Protocol_ID(Enum):
        J1850VPW = 1
        J1850PWM = 2
        ISO9141 = 3
        ISO14230 = 4
        CAN = 5
        SCI_A_ENGINE = 7  # OP2.0: Not supported
        SCI_A_TRANS = 8  # OP2.0: Not supported
        SCI_B_ENGINE = 9  # OP2.0: Not supported
        SCI_B_TRANS = 10  # OP2.0: Not supported
        ISO15765 = 0x40  # 6

    def SBusCanOpen(self):
        status = self.j2534_dll.PassThruOpen(None, ctypes.byref(self.device_id))
        return status

    def SBusCanConnect(self, protocol, baudrate):
        status = self.j2534_dll.PassThruConnect(self.device_id, protocol, 0, baudrate, ctypes.byref(self.channel_id))
        return status

    def SBusCanClearRxMsg(self):
        # Implement this method as per your existing logic
        # Create a structure for the configList
        DWORD = ctypes.c_ulong
        class SCONFIG(ctypes.Structure):
         _fields_ = [
        ("Parameter", DWORD),
        ("Value", DWORD),
          ]
        configList = SCONFIG()
        configList.Parameter = 0  # Replace with the correct parameter value
        configList.Value = 0     # Replace with the correct value
        CLEAR_MSG_FILTERS = 0x0A
        status = self.j2534_dll.PassThruIoctl(self.channel_id, CLEAR_MSG_FILTERS, ctypes.byref(configList), None)
        return status

        pass

    def SBusCanSendMgs(self, CanFrame):
    # def SBusCanSendMgs(self, CAN_ID, DLC, data):
        # Implement this method as per your existing logic
        pNumMsgs = ctypes.c_ulong(1)
        CAN = 5
        ISO15765_FRAME_PAD = 0x40
        CAN_29BIT_ID = 0x0100
        TxMsg = self.SMsg()
        TxMsg.ProtocolID = CAN
        # TxMsg.TxFlags = ISO15765_FRAME_PAD
        TxMsg.DataSize = CanFrame.DLC+4
        if(CanFrame.CAN_ID >0x7FF):
            TxMsg.TxFlags = CAN_29BIT_ID
        else:
             TxMsg.TxFlags = ISO15765_FRAME_PAD     


        length_of_data = 4028  # Assuming you know the length
        c_byte_array = (ctypes.c_ubyte * length_of_data)()
        CanFrame.CAN_ID = (CanFrame.CAN_ID & 0x1FFFFFFF)
        c_byte_array[0] = (CanFrame.CAN_ID>>24)
        c_byte_array[1] = (CanFrame.CAN_ID>>16)
        c_byte_array[2] = (CanFrame.CAN_ID>>8)
        c_byte_array[3] = (CanFrame.CAN_ID>>0)
        c_byte_array[4] = CanFrame.data[0]
        c_byte_array[5] = CanFrame.data[1]
        c_byte_array[6] = CanFrame.data[2]
        c_byte_array[7] = CanFrame.data[3]
        c_byte_array[8] = CanFrame.data[4]
        c_byte_array[9] = CanFrame.data[5]
        c_byte_array[10] = CanFrame.data[6]
        c_byte_array[11] = CanFrame.data[7]

        TxMsg.Data = c_byte_array
        # Call PassThruWriteMsgs with a pointer to tx_msg
        status = self.j2534_dll.PassThruWriteMsgs(self.channel_id, ctypes.byref(TxMsg), ctypes.byref(pNumMsgs), 0)
        return status
        
    def SBusCanRxSetFilter(self,CAN_Id):
        msgMask =self.SMsg()
        msgPattern = self.SMsg()
        # msgflow = self.SMsg()
        
        CAN = 5
        ISO15765_FRAME_PAD = 0x40
        PASS_FILTER = ctypes.c_ulong(1)
        filterId = ctypes.c_ulong(0)
        msgMask.ProtocolID = CAN
        msgMask.RxStatus = 0
        msgMask.TxFlags = ISO15765_FRAME_PAD
        msgMask.Timestamp = 0
        msgMask.DataSize = 4
        for i in range(0, 4):
            msgMask.Data[i] = 0xFF
        
        msgPattern.ProtocolID = CAN
        msgPattern.RxStatus = 0
        msgPattern.TxFlags = ISO15765_FRAME_PAD
        msgPattern.Timestamp = 0
        msgPattern.DataSize = 4
       
        # msgflow.ProtocolID = CAN
        # msgflow.RxStatus = 0
        # msgflow.TxFlags = ISO15765_FRAME_PAD
        # msgflow.Timestamp = 0
        # msgflow.DataSize = 4
        CAN_Id = (CAN_Id&0x1FFFFFFF)
        msgPattern.Data[0]= (CAN_Id>>24)
        msgPattern.Data[1]= (CAN_Id>>16)
        msgPattern.Data[2]= (CAN_Id>>8)
        msgPattern.Data[3]= (CAN_Id>>0)

        status = self.j2534_dll.PassThruStartMsgFilter(self.channel_id,PASS_FILTER,ctypes.byref(msgMask),ctypes.byref(msgPattern),None,ctypes.byref(filterId))
        return status

    def SBusCanReadMgs(self,timeout=0):
        # Implement this method as per your existing logic
        CAN = 5
        Rx_Msg = self.SMsg()
        Rx_Msg.ProtocolID = CAN
        num_msgs = ctypes.c_ulong(1)
        status  = self.j2534_dll.PassThruReadMsgs(self.channel_id, ctypes.byref(Rx_Msg), ctypes.byref(num_msgs), timeout)#0
        response = bytearray(Rx_Msg.Data)
        frame = CANFrame()
        CAN_Id = response[3] << 0
        CAN_Id = CAN_Id | response[2] << 8
        CAN_Id = CAN_Id | response[1] << 16
        CAN_Id = CAN_Id | response[0] << 24
        frame.CAN_ID = CAN_Id
        frame.DLC = Rx_Msg.DataSize - 4
        for i in range(0,frame.DLC):
            frame.data.append(response[4+i])
        return status,frame
    

    def SBusCanDisconnect(self):
        status = self.j2534_dll.PassThruDisconnect(self.channel_id)
        return status

    def SBusCanClose(self):
        status = self.j2534_dll.PassThruClose(self.device_id)
        return status


