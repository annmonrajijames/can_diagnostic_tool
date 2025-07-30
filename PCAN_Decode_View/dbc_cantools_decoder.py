import sys, time
from pathlib import Path
from typing import Dict

import can, cantools
from PySide6.QtCore    import QThread, Signal
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QTableWidget, QTableWidgetItem,
    QVBoxLayout, QWidget, QPushButton, QHBoxLayout
)

# ─────────── User Settings ───────────
DBC_PATH     = Path(r"C:\Git_projects\can_diagnostic_tool\data\DBC_sample_cantools.dbc")
PCAN_CHANNEL = "PCAN_USBBUS1"
BITRATE      = 500_000
USE_CAN_FD   = False
DATA_PHASE   = "500K/2M"
# ─────────────────────────────────────

dbc = cantools.database.load_file(DBC_PATH)
print(f"Loaded DBC: {DBC_PATH}  (messages: {len(dbc.messages)})")

# ───────── CAN Reader Thread ─────────
class CanReader(QThread):
    """
    Emits: real_can_id, message_name, signal_name, value, unit, cycle_ms
    """
    new_signal = Signal(int, str, str, float, str, float)

    def __init__(self):
        super().__init__()
        self._running = True
        self._last_ts: Dict[str, float] = {}

        bus_kwargs = dict(interface="pcan",
                          channel=PCAN_CHANNEL,
                          bitrate=BITRATE)
        if USE_CAN_FD:
            bus_kwargs.update(fd=True, bitrate_fd=DATA_PHASE)
        self.bus = can.Bus(**bus_kwargs)

    def run(self):
        try:
            while self._running:
                msg = self.bus.recv(timeout=0.1)
                if msg is None:
                    continue

                raw_id = msg.arbitration_id
                can_id = raw_id | (0x8000_0000 if msg.is_extended_id else 0)

                try:
                    mdef = dbc.get_message_by_frame_id(can_id)
                except KeyError:
                    continue

                try:
                    decoded = mdef.decode(msg.data, allow_truncated=False,
                                          decode_choices=True)
                except cantools.DecodeError:
                    continue

                now = msg.timestamp
                for sig_name, val in decoded.items():
                    qkey  = f"{mdef.name}.{sig_name}"
                    cycle = 0.0
                    if qkey in self._last_ts:
                        cycle = round((now - self._last_ts[qkey]) * 1000, 1)
                    self._last_ts[qkey] = now
                    unit = mdef.get_signal_by_name(sig_name).unit or ""
                    self.new_signal.emit(raw_id, mdef.name, sig_name,
                                         val, unit, cycle)
        finally:
            self.bus.shutdown()

    def stop(self):
        self._running = False
        self.wait()

# ───────── GUI Window ─────────
class MainWindow(QMainWindow):
    """
    Columns:
        0  Msg ID
        1  Msg Name
        2  Signal Name
        3  Value
        4  Unit
        5  Cycle‑Time (ms)
        6  Count
    """
    headers = ["Message ID", "Message Name", "Signal Name",
               "Value", "Unit", "Cycle Time (ms)", "Count"]

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Live CAN Signal Viewer – with Count")
        self.resize(1150, 650)

        self.table = QTableWidget(0, len(self.headers))
        self.table.setHorizontalHeaderLabels(self.headers)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)

        self.row_map: Dict[str, int] = {}
        self.count_map: Dict[str, int] = {}

        self.restart_button = QPushButton("Restart Count")
        self.restart_button.clicked.connect(self.restart_counts)

        layout = QVBoxLayout()
        layout.addWidget(self.table)
        layout.addWidget(self.restart_button)
        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)

        self.reader = CanReader()
        self.reader.new_signal.connect(self.update_row)
        self.reader.start()

    def restart_counts(self):
        self.count_map = {}
        for row in range(self.table.rowCount()):
            self.table.item(row, 6).setText("0")

    def update_row(self, can_id: int, msg_name: str, sig_name: str,
                   value: float, unit: str, cycle_ms: float):
        key = f"{msg_name}.{sig_name}"
        row = self.row_map.get(key)

        try:
            id_text  = f"0x{can_id:X}"
            val_text = str(value)
            cyc_text = f"{cycle_ms:.1f}" if cycle_ms else "—"
            count    = self.count_map.get(key, 0) + 1
            self.count_map[key] = count

            if row is None:
                row = self.table.rowCount()
                self.table.insertRow(row)
                self.table.setItem(row, 0, QTableWidgetItem(id_text))
                self.table.setItem(row, 1, QTableWidgetItem(msg_name))
                self.table.setItem(row, 2, QTableWidgetItem(sig_name))
                self.table.setItem(row, 3, QTableWidgetItem(val_text))
                self.table.setItem(row, 4, QTableWidgetItem(unit))
                self.table.setItem(row, 5, QTableWidgetItem(cyc_text))
                self.table.setItem(row, 6, QTableWidgetItem(str(count)))
                self.row_map[key] = row
            else:
                self.table.item(row, 0).setText(id_text)
                self.table.item(row, 3).setText(val_text)
                self.table.item(row, 5).setText(cyc_text)
                self.table.item(row, 6).setText(str(count))

        except Exception as e:
            print(f"⚠️ GUI update error for {key}: {e}")

    def closeEvent(self, event):
        self.reader.stop()
        super().closeEvent(event)

# ───────── App Entrypoint ─────────
def main():
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
