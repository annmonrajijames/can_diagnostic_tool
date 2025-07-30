import sys
from pathlib import Path
from typing import Dict

import can
import cantools
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QTableWidget, QTableWidgetItem,
    QVBoxLayout, QWidget
)

# ─────────────── Settings ────────────────
DBC_PATH = Path(r"C:\Git_projects\can_diagnostic_tool\data\DBC_sample_cantools.dbc")
PCAN_CHANNEL = "PCAN_USBBUS1"
BITRATE = 500_000
# ─────────────────────────────────────────

def load_dbc(dbc_path: Path):
    return cantools.database.load_file(dbc_path)

# ───────────── CAN Reader Thread ─────────────
class CanReader(QThread):
    new_frame = Signal(int, bytes, float)

    def __init__(self, channel: str, bitrate: int):
        super().__init__()
        self.channel = channel
        self.bitrate = bitrate
        self._stop = False
        self._last_ts: Dict[int, float] = {}

    def run(self):
        bus = can.Bus(interface="pcan", channel=self.channel, bitrate=self.bitrate)
        try:
            for msg in bus:
                if self._stop:
                    break
                now = msg.timestamp
                can_id = msg.arbitration_id
                payload = msg.data

                cycle_ms = 0.0
                if can_id in self._last_ts:
                    cycle_ms = (now - self._last_ts[can_id]) * 1000.0
                self._last_ts[can_id] = now

                self.new_frame.emit(can_id, payload, cycle_ms)
        finally:
            bus.shutdown()

    def stop(self):
        self._stop = True
        self.quit()
        self.wait()

# ───────────── Main GUI ─────────────
class MainWindow(QMainWindow):
    headers = ["CAN ID (hex)", "Payload", "Cycle Time (ms)"]

    def __init__(self, dbc_db):
        super().__init__()
        self.setWindowTitle("Live CAN ID + Payload Viewer")
        self.resize(800, 600)

        self.dbc = dbc_db  # Loaded, not used yet
        self.table = QTableWidget(0, len(self.headers))
        self.table.setHorizontalHeaderLabels(self.headers)
        self.table.horizontalHeader().setStretchLastSection(True)

        self.row_map: Dict[int, int] = {}  # can_id → row index

        layout = QVBoxLayout()
        layout.addWidget(self.table)
        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)

        self.reader = CanReader(PCAN_CHANNEL, BITRATE)
        self.reader.new_frame.connect(self.on_new_frame)
        self.reader.start()

    def on_new_frame(self, can_id: int, payload: bytes, cycle_ms: float):
        row = self.row_map.get(can_id)

        payload_str = payload.hex(" ").upper()
        cycle_str = f"{cycle_ms:.1f}" if cycle_ms > 0 else "—"

        if row is None:
            # New CAN ID → Add row
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setItem(row, 0, QTableWidgetItem(f"0x{can_id:08X}"))
            self.table.setItem(row, 1, QTableWidgetItem(payload_str))
            self.table.setItem(row, 2, QTableWidgetItem(cycle_str))
            self.row_map[can_id] = row
        else:
            # Existing ID → update payload and cycle
            self.table.item(row, 1).setText(payload_str)
            self.table.item(row, 2).setText(cycle_str)

    def closeEvent(self, event):
        self.reader.stop()
        super().closeEvent(event)

# ───────────── Main Entrypoint ─────────────
def main():
    dbc_db = load_dbc(DBC_PATH)
    app = QApplication(sys.argv)
    win = MainWindow(dbc_db)
    win.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
