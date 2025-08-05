"""PySide6 GUI displaying CAN frames via PEAK hardware using python-can.

This module connects to a PEAK CAN interface using the :mod:`can` library and
shows all unique CAN identifiers along with their payload, cycle time in
milliseconds and reception count.  The information is rendered in a
``QTableWidget`` and refreshed periodically.
"""

from __future__ import annotations

import sys
import time
from dataclasses import dataclass
from threading import Lock
from typing import Dict

import can
from PySide6.QtCore import QThread, QTimer, Signal, Qt
from PySide6.QtWidgets import (
    QApplication,
    QAbstractItemView,
    QHeaderView,
    QMainWindow,
    QTableWidget,
    QTableWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


@dataclass
class _StatEntry:
    """Internal book keeping for :class:`CANStats`."""
    count: int = 0
    last_time: float | None = None
    cycle_time_ms: float = 0.0


class CANStats:
    """Track occurrence count and cycle time for CAN identifiers."""

    def __init__(self) -> None:
        self._stats: Dict[int, _StatEntry] = {}
        self._lock = Lock()

    def update(self, can_id: int) -> None:
        now = time.time()
        with self._lock:
            entry = self._stats.get(can_id)
            if entry is None:
                entry = _StatEntry(count=1, last_time=now)
                self._stats[can_id] = entry
            else:
                if entry.last_time is not None:
                    entry.cycle_time_ms = (now - entry.last_time) * 1000.0
                entry.last_time = now
                entry.count += 1

    def snapshot(self) -> Dict[int, Dict[str, float | int]]:
        with self._lock:
            return {
                can_id: {
                    "count": entry.count,
                    "cycle_time_ms": entry.cycle_time_ms,
                }
                for can_id, entry in self._stats.items()
            }


class CANReader(QThread):
    """Background thread receiving frames from a PEAK CAN interface."""

    frame_received = Signal(object)

    def __init__(self, channel: str = "PCAN_USBBUS1", bitrate: int = 500000) -> None:
        super().__init__()
        self._channel = channel
        self._bitrate = bitrate
        self._running = True

    def run(self) -> None:  # pragma: no cover - involves I/O
        bus = can.Bus(bustype="pcan", channel=self._channel, bitrate=self._bitrate)
        while self._running:
            msg = bus.recv(timeout=0.1)
            if msg is not None:
                self.frame_received.emit(msg)

    def stop(self) -> None:  # pragma: no cover - involves I/O
        self._running = False
        self.wait()


class MainWindow(QMainWindow):
    """Main application window displaying frame statistics."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("PEAK CAN Performance")

        self._stats = CANStats()
        self._payloads: Dict[int, bytes] = {}

        # Layout
        central_widget = QWidget()
        layout = QVBoxLayout(central_widget)

        # Table
        self._table = QTableWidget(0, 4, self)
        self._table.setHorizontalHeaderLabels(
            ["CAN ID", "Payload", "Cycle Time [ms]", "Count"]
        )
        self._table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)

        # Restart Button
        self._restart_button = QPushButton("Restart Counters")
        self._restart_button.clicked.connect(self._reset_stats)

        # Add widgets to layout
        layout.addWidget(self._table)
        layout.addWidget(self._restart_button)

        self.setCentralWidget(central_widget)

        # CAN Reader
        self._reader = CANReader()
        self._reader.frame_received.connect(self._process_frame)
        self._reader.start()

        # Timer to refresh table
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._refresh)
        self._timer.start(200)

    def closeEvent(self, event) -> None:  # pragma: no cover - Qt hook
        self._reader.stop()
        super().closeEvent(event)

    # ---------------------- Helpers ----------------------

    def _reset_stats(self) -> None:
        """Clear all statistics and payloads, and reset the table."""
        self._stats = CANStats()
        self._payloads.clear()
        self._table.setRowCount(0)

    def _process_frame(self, msg: can.Message) -> None:
        self._stats.update(msg.arbitration_id)
        self._payloads[msg.arbitration_id] = bytes(msg.data)

    def _refresh(self) -> None:
        snapshot = self._stats.snapshot()
        self._table.setRowCount(len(snapshot))
        for row, (can_id, info) in enumerate(sorted(snapshot.items())):
            payload = self._payloads.get(can_id, b"")

            id_item = QTableWidgetItem(f"{can_id:03X}")
            payload_item = QTableWidgetItem(" ".join(f"{b:02X}" for b in payload))
            cycle_item = QTableWidgetItem(f"{info['cycle_time_ms']:.2f}")
            count_item = QTableWidgetItem(str(info["count"]))

            for item in (id_item, payload_item, cycle_item, count_item):
                item.setTextAlignment(Qt.AlignCenter)

            self._table.setItem(row, 0, id_item)
            self._table.setItem(row, 1, payload_item)
            self._table.setItem(row, 2, cycle_item)
            self._table.setItem(row, 3, count_item)


def main() -> int:  # pragma: no cover - entry point
    app = QApplication(sys.argv)
    window = MainWindow()
    window.resize(600, 400)
    window.show()
    return app.exec()


if __name__ == "__main__":  # pragma: no cover - module test
    raise SystemExit(main())
