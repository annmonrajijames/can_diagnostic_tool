"""PySide6 GUI for displaying CAN frame statistics."""

from __future__ import annotations

import sys
from PySide6.QtCore import QTimer, Qt, QThread
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QTableWidget,
    QTableWidgetItem,
    QAbstractItemView,
    QHeaderView,
)

from hardware.drivers.j2534_sloki_driver import J2534API
from Sloki_performance import CANStats


class CANReaderThread(QThread):
    """Background thread that reads CAN frames and updates statistics."""

    def __init__(self, stats: CANStats, japi: J2534API, parent=None) -> None:
        super().__init__(parent)
        self._stats = stats
        self._japi = japi
        self._running = True

    def run(self) -> None:
        if self._japi.SBusCanOpen() != 0:
            return
        if self._japi.SBusCanConnect(J2534API.Protocol_ID.CAN.value, 500000) != 0:
            return
        self._japi.SBusCanClearRxMsg()
        while self._running:
            status, frame = self._japi.SBusCanReadMgs(10)
            if status == 0:
                self._stats.update(frame.CAN_ID)

    def stop(self) -> None:
        self._running = False


class StatsWindow(QMainWindow):
    """Main window displaying CAN statistics in a table."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Sloki CAN Performance")

        self._stats = CANStats()
        self._japi = J2534API()
        self._reader = CANReaderThread(self._stats, self._japi)

        self._table = QTableWidget(0, 3, self)
        self._table.setHorizontalHeaderLabels(["CAN ID", "Cycle Time (ms)", "Count"])
        self._table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.setCentralWidget(self._table)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._refresh)
        self._timer.start(300)

        self._reader.start()

    def _refresh(self) -> None:
        data = self._stats.snapshot()
        self._table.setRowCount(len(data))
        for row, (can_id, info) in enumerate(sorted(data.items())):
            can_item = QTableWidgetItem(f"{can_id:08X}")
            cycle_item = QTableWidgetItem(f"{info['cycle_time_ms']:.2f}")
            count_item = QTableWidgetItem(str(info['count']))
            can_item.setTextAlignment(Qt.AlignCenter)
            cycle_item.setTextAlignment(Qt.AlignCenter)
            count_item.setTextAlignment(Qt.AlignCenter)
            self._table.setItem(row, 0, can_item)
            self._table.setItem(row, 1, cycle_item)
            self._table.setItem(row, 2, count_item)

    def closeEvent(self, event) -> None:  # type: ignore[override]
        self._timer.stop()
        self._reader.stop()
        self._reader.wait()
        self._japi.SBusCanDisconnect()
        self._japi.SBusCanClose()
        super().closeEvent(event)


def main() -> None:
    app = QApplication(sys.argv)
    window = StatsWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

