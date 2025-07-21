# can_interface.py
# ------------------------------------------------------------
# This file acts as a generic high-level wrapper for CAN communication
# using a specific vendor driver (e.g., J2534 Sloki).
# This allows future replacement with any other hardware backend.
# ------------------------------------------------------------

from hardware.drivers.j2534_sloki_driver import J2534API, CANFrame

class CANInterface:
    def __init__(self, baudrate=500000):
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


    def receive(self, timeout=10):
        status, frames = self.api.SBusCanReadMgs(timeout=timeout, max_msgs=1)
        if status == 0 and frames:
            return frames[0]
        return None

    def receive_batch(self, timeout=10, max_frames=50):
        """Return a list of received CANFrame objects."""
        status, frames = self.api.SBusCanReadMgs(timeout=timeout, max_msgs=max_frames)
        if status == 0:
            return frames
        return []

    def set_filter(self, can_id):
        return self.api.SBusCanRxSetFilter(can_id)
