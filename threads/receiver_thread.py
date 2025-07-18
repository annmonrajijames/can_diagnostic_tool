# threads/receiver_thread.py
from PySide6.QtCore import QThread, Signal

class CANReceiverThread(QThread):
    frame_received = Signal(object)  # Emits: CANFrame object

    def __init__(self, can_interface):
        super().__init__()
        self.can_interface = can_interface
        self._running = True

    def run(self):
        while self._running:
            # Block for up to 10 ms, return earlier if frames are available
            frames = self.can_interface.receive(timeout=10, max_msgs=10)
            for frame in frames:
                self.frame_received.emit(frame)

    def stop(self):
        self._running = False
        self.wait()
