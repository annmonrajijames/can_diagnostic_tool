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
            frames = self.can_interface.receive_batch(timeout=1, max_frames=50)
            for frame in frames:
                self.frame_received.emit(frame)
            # Short delay to prevent busy waiting
            self.msleep(1)

    def stop(self):
        self._running = False
        self.wait()
