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
            # Read up to 50 frames at a time. The driver will block for up to
            # ``timeout`` milliseconds if no frames are immediately available.
            frames = self.can_interface.receive(timeout=10, num_msgs=50)
            for frame in frames:
                self.frame_received.emit(frame)

    def stop(self):
        self._running = False
        self.wait()
