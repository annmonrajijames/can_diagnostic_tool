# threads/receiver_thread.py
from PySide6.QtCore import QThread
from queue import Queue

class CANReceiverThread(QThread):

    def __init__(self, can_interface):
        super().__init__()
        self.can_interface = can_interface
        self._running = True
        self._queue: Queue = Queue()

    def run(self):
        while self._running:
            # Block for up to 10 ms, return earlier if a frame is available
            frame = self.can_interface.receive(timeout=10)
            if frame:
                self._queue.put(frame)

    def stop(self):
        self._running = False
        self.wait()

    def get_all_frames(self):
        """Return a list of all frames currently queued."""
        frames = []
        while not self._queue.empty():
            frames.append(self._queue.get())
        return frames
