# live_signal_viewer.py
import sys
from typing import Dict

import cantools
from PySide6.QtCore    import QThread, Signal
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QTableWidget, QTableWidgetItem,
    QVBoxLayout, QWidget, QPushButton
)

from PEAK_API import get_config_and_bus
from dbc_page import dbc, DBC_PATH

cfg, BUS = get_config_and_bus()

print(f"Loaded DBC: {DBC_PATH}  (messages: {len(dbc.messages)})")

def get_message(dbc_db, frame_id: int, is_ext: bool):
    lookup_id = frame_id | 0x8000_0000 if is_ext else frame_id
    return dbc_db._frame_id_to_message.get(lookup_id)

class CanReader(QThread):
    new_signal = Signal(int, bool, str, str, float, str, float)
    def __init__(self, bus):       # <- receives ready-to-use bus
        super().__init__()
        self.bus = bus
        self._running = True
        self._last_ts: Dict[str, float] = {}
    def run(self):
        try:
            while self._running:
                msg = self.bus.recv(timeout=0.1)
                if msg is None:
                    continue
                mdef = get_message(dbc, msg.arbitration_id, msg.is_extended_id)
                if mdef is None:
                    continue
                try:
                    decoded = mdef.decode(msg.data,
                                          allow_truncated=False,
                                          decode_choices=True)
                except cantools.DecodeError:
                    continue
                now = msg.timestamp
                for sig_name, val in decoded.items():
                    qkey  = f"{mdef.name}.{sig_name}"
                    cycle = round((now - self._last_ts.get(qkey, now)) * 1000, 1)
                    self._last_ts[qkey] = now
                    unit = mdef.get_signal_by_name(sig_name).unit or ""
                    self.new_signal.emit(msg.arbitration_id,
                                         msg.is_extended_id,
                                         mdef.name, sig_name,
                                         val, unit, cycle)
        finally:
            if hasattr(self.bus, "shutdown"):
                self.bus.shutdown()
    def stop(self):
        self._running = False
        self.wait()

class MainWindow(QMainWindow):
    headers = ["Message ID", "Message Name", "Signal Name",
               "Value", "Unit", "Cycle Time (ms)", "Count"]
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Live CAN Signal Viewer")
        self.resize(1150, 650)

        self.table = QTableWidget(0, len(self.headers))
        self.table.setHorizontalHeaderLabels(self.headers)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)

        self.row_map:   Dict[str, int] = {}
        self.count_map: Dict[str, int] = {}

        self.restart_button = QPushButton("Restart Count")
        self.restart_button.clicked.connect(self.restart_counts)

        lay = QVBoxLayout(); lay.addWidget(self.table); lay.addWidget(self.restart_button)
        root = QWidget();   root.setLayout(lay); self.setCentralWidget(root)

        self.reader = CanReader(BUS)
        self.reader.new_signal.connect(self.update_row)
        self.reader.start()

    def restart_counts(self):
        self.count_map.clear()
        for row in range(self.table.rowCount()):
            self.table.item(row, 6).setText("0")

    def update_row(self, frame_id: int, is_ext: bool, msg_name: str, sig_name: str,
                   value: float, unit: str, cycle_ms: float):
        key  = f"{msg_name}.{sig_name}"
        row  = self.row_map.get(key)
        id_text  = f"0x{frame_id:X}" + (" (EXT)" if is_ext else "")
        val_text = str(value)
        cyc_text = f"{cycle_ms:.1f}" if cycle_ms else "—"
        count    = self.count_map.get(key, 0) + 1
        self.count_map[key] = count
        if row is None:
            row = self.table.rowCount()
            self.table.insertRow(row)
            for col, text in enumerate([id_text, msg_name, sig_name,
                                        val_text, unit, cyc_text, str(count)]):
                self.table.setItem(row, col, QTableWidgetItem(text))
            self.row_map[key] = row
        else:
            self.table.item(row, 0).setText(id_text)
            self.table.item(row, 3).setText(val_text)
            self.table.item(row, 5).setText(cyc_text)
            self.table.item(row, 6).setText(str(count))
    def closeEvent(self, event):
        self.reader.stop()
        super().closeEvent(event)

def main():
    app = QApplication(sys.argv)
    win = MainWindow(); win.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
