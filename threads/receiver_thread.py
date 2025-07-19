# threads/receiver_thread.py
from PySide6.QtCore import QThread, Signal
import logging

class CANReceiverThread(QThread):
    frame_received = Signal(object)  # Emits: CANFrame object

    def __init__(self, can_interface):
        super().__init__()
        self.can_interface = can_interface
        self._running = True

    def run(self):
        while self._running:
            try:
                # Block for up to 10 ms, return earlier if a frame is available
                frame = self.can_interface.receive(timeout=10)
                if frame:
                    self.frame_received.emit(frame)
            except Exception:
                logging.exception("Receiver thread encountered an error")
                self._running = False

    def stop(self):
        self._running = False
        self.wait()
