"""
live_signal_viewer_multiplex.py
• Handles multiplexed signals safely
• Shows all 157 signals as soon as they appear
• Updates value + individual cycle‑time every time the specific
  signal is present in a frame
"""
import sys, time
from pathlib import Path
from typing import Dict

import can, cantools
from PySide6.QtCore    import QThread, Signal
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QTableWidget, QTableWidgetItem,
    QVBoxLayout, QWidget
)

# ───────── user settings ─────────
DBC_PATH     = Path(r"C:\Git_projects\can_diagnostic_tool\data\DBC_sample_cantools.dbc")
PCAN_CHANNEL = "PCAN_USBBUS1"
BITRATE      = 500_000
USE_CAN_FD   = False
DATA_PHASE   = "500K/2M"
# ──────────────────────────────────

dbc = cantools.database.load_file(DBC_PATH)
print(f"Loaded DBC: {DBC_PATH}  (messages: {len(dbc.messages)})")

# ───────── CAN reader thread ─────────
class CanReader(QThread):
    new_signal = Signal(str, float, str, float)   # qname, value, unit, cycle‑ms

    def __init__(self):
        super().__init__()
        self._last_ts: Dict[str, float] = {}
        bus_kwargs = dict(interface="pcan",
                          channel=PCAN_CHANNEL,
                          bitrate=BITRATE)
        if USE_CAN_FD:
            bus_kwargs.update(fd=True, bitrate_fd=DATA_PHASE)
        self.bus = can.Bus(**bus_kwargs)

    def run(self):
        try:
            for msg in self.bus:
                can_id = msg.arbitration_id | (0x8000_0000 if msg.is_extended_id else 0)
                try:
                    mdef = dbc.get_message_by_frame_id(can_id)
                except KeyError:
                    continue                              # ID not in DBC → ignore

                try:
                    decoded = mdef.decode(msg.data, allow_truncated=False,
                                          decode_choices=True)
                except cantools.DecodeError:
                    continue                              # length / format issue

                now = msg.timestamp
                for sig_name, val in decoded.items():     # only signals truly present
                    qname = f"{mdef.name}.{sig_name}"
                    unit  = mdef.get_signal_by_name(sig_name).unit or ""
                    cycle = 0.0
                    if qname in self._last_ts:
                        cycle = round((now - self._last_ts[qname])*1000, 1)
                    self._last_ts[qname] = now
                    self.new_signal.emit(qname, val, unit, cycle)
        finally:
            self.bus.shutdown()

    def stop(self):
        self.quit()
        self.wait()

# ───────── Qt GUI ─────────
class MainWindow(QMainWindow):
    headers = ["Signal", "Value", "Unit", "Cycle Time (ms)"]

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Live CAN Signal Viewer – multiplex‑safe")
        self.resize(950, 600)

        self.table   = QTableWidget(0, len(self.headers))
        self.table.setHorizontalHeaderLabels(self.headers)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)

        self.row_map: Dict[str, int] = {}

        lay  = QVBoxLayout(); lay.addWidget(self.table)
        root = QWidget();     root.setLayout(lay); self.setCentralWidget(root)

        self.reader = CanReader()
        self.reader.new_signal.connect(self.update_row)
        self.reader.start()

    def update_row(self, qname: str, value: float, unit: str, cycle_ms: float):
        row = self.row_map.get(qname)
        val_txt   = f"{value:g}"
        cycle_txt = f"{cycle_ms:.1f}" if cycle_ms else "—"

        if row is None:                           # first time this signal appears
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setItem(row, 0, QTableWidgetItem(qname))
            self.table.setItem(row, 1, QTableWidgetItem(val_txt))
            self.table.setItem(row, 2, QTableWidgetItem(unit))
            self.table.setItem(row, 3, QTableWidgetItem(cycle_txt))
            self.row_map[qname] = row
        else:                                     # update existing row
            self.table.item(row, 1).setText(val_txt)
            self.table.item(row, 3).setText(cycle_txt)

    def closeEvent(self, event):
        self.reader.stop()
        super().closeEvent(event)

# ───────── run app ─────────
def main():
    app = QApplication(sys.argv)
    win = MainWindow(); win.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
