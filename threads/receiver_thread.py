# threads/receiver_thread.py
from PySide6.QtCore import QThread, Signal
import time

class CANReceiverThread(QThread):
    frame_received = Signal(object)  # Will emit CANFrame objects

    def __init__(self, can_interface, poll_interval_ms=10):
        super().__init__()
        self.can_interface = can_interface
        self.poll_interval = poll_interval_ms / 1000  # convert ms to seconds
        self._running = True

    def run(self):
        while self._running:
            frame = self.can_interface.receive(timeout=0)
            if frame:
                self.frame_received.emit(frame)
            time.sleep(self.poll_interval)

    def stop(self):
        self._running = False
        self.wait()
