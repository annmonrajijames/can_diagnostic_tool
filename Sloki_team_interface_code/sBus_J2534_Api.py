# sBus_J2534_Api.py
from J2534_Driver import J2534API, CANFrame

protocol = J2534API.Protocol_ID.CAN
baudrate = 500000
j2534_api = J2534API()

status = j2534_api.SBusCanOpen()
if status != 0:
    print(f"PassThruOpen failed with status: {status}")
    exit()

status = j2534_api.SBusCanConnect(protocol.value,baudrate)
if status != 0:
    print(f"PassThruconnect failed with status: {status}")
    exit()

status = j2534_api.SBusCanClearRxMsg()    
if status != 0:
    print(f"passThruIoctl failed with status: {status}")
    exit()

# status = j2534_api.SBusCanRxSetFilter(0x7F1)
# if status != 0:
#     print(f"startMsgFilter failed with status: {status}")
#     exit()

#  status = j2534_api.SBusCanRxSetFilter(0x7F0)
# if status != 0:
#     print(f"startMsgFilter failed with status: {status}")
#     exit()

# status = j2534_api.SBusCanRxSetFilter(0x123)
# if status != 0:
#     print(f"startMsgFilter failed with status: {status}")
#     exit()
# status = j2534_api.SBusCanRxSetFilter(0x12345)
# if status != 0:
#     print(f"startMsgFilter failed with status: {status}")
#     exit()    

CanFrame = CANFrame()
CanFrame.CAN_ID = 0x120
CanFrame.DLC = 0x8
CanFrame.data.append(0x01)
CanFrame.data.append(0x02)
CanFrame.data.append(0x03)
CanFrame.data.append(0x04)
CanFrame.data.append(0x05)
CanFrame.data.append(0x06)
CanFrame.data.append(0x07)
CanFrame.data.append(0x08)
status = j2534_api.SBusCanSendMgs(CanFrame)
CanFrame.CAN_ID = 0x700
status = j2534_api.SBusCanSendMgs(CanFrame)
CanFrame.CAN_ID = 0x180014
status = j2534_api.SBusCanSendMgs(CanFrame)
if status != 0:
    print(f"PassThruWrite failed with status: {status}")
    exit()


response = None
while(1):
    status, response = j2534_api.SBusCanReadMgs(timeout = 10)
    if status==0:
        pass
        print(hex(response.CAN_ID))
        print(hex(response.DLC))
        # Convert each number to hexadecimal and print
        hex_numbers = [hex(n) for n in response.data]
        print(hex_numbers)
    else:
        # print(f"PassThruRead failed with status: {status}")
        pass
        # exit()
pass 

status = j2534_api.SBusCanDisconnect() 
if status != 0:
    print(f"PassThruDisconnect failed with status: {status}")
    exit()

status = j2534_api.SBusCanClose()
if status != 0:
    print(f"PassThruClose failed with status: {status}")
    exit()

pass