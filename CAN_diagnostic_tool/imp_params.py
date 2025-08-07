# imp_params.py
"""
Live monitor for two signal groups:

1. Important Parameters
2. Battery Errors
"""

from __future__ import annotations
import sys
from typing import Dict

import cantools
from PySide6.QtCore    import QThread, Signal, Qt
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget,
    QVBoxLayout, QTableWidget, QTableWidgetItem,
    QGroupBox, QHBoxLayout
)

from PEAK_API import get_config_and_bus
from dbc_page  import dbc, DBC_PATH


# ─────────────────────────────────────────────────────────────────────────────
# 1) Group definitions
# ─────────────────────────────────────────────────────────────────────────────
IMPORTANT_PARAMS = {
    "IgnitionStatus",
    "Brake_Pulse",
    "PackCurr",
    "PackVol",
    "chgStatus_chg_idle",
    "ChgFetStatus",
    "DchgFetStatus",
}

BATTERY_ERRORS = {
    "CellUnderVolProt",
    "CellOverVolProt",
    "PackUnderVolProt",
    "PackOverVolProt",
    "ChgUnderTempProt",
    "ChgOverTempProt",
    "DchgUnderTempProt",
    "DchgOverTempProt",
    "CellOverDevProt",
    "ChgOverCurrProt",
    "DchgOverCurrProt",
    "FetTempProt",
    "ResSocProt",
    "FetFailure",
    "TempSenseFault",
    "PreChgFetStatus",
    "ResStatus",
    "ShortCktProt",
    "DschgPeakProt",
}

# master lookup → which table to update
SIG_TO_GROUP = {**{s: "important" for s in IMPORTANT_PARAMS},
                **{s: "error"     for s in BATTERY_ERRORS}}


# ─────────────────────────────────────────────────────────────────────────────
# Helper: map frame-id → cantools message
# ─────────────────────────────────────────────────────────────────────────────
def _get_message(db: cantools.database.Database, frame_id: int, is_ext: bool):
    lookup_id = frame_id | 0x8000_0000 if is_ext else frame_id
    return db._frame_id_to_message.get(lookup_id)


# ─────────────────────────────────────────────────────────────────────────────
# CAN reader thread
# ─────────────────────────────────────────────────────────────────────────────
class CanReader(QThread):
    new_signal = Signal(str, float, str)   # sig_name, value, unit
    def __init__(self, bus):
        super().__init__()
        self._bus = bus
        self._running = True
    def run(self):
        try:
            while self._running:
                msg = self._bus.recv(timeout=0.1)
                if msg is None:
                    continue
                mdef = _get_message(dbc, msg.arbitration_id, msg.is_extended_id)
                if mdef is None:
                    continue
                try:
                    decoded = mdef.decode(msg.data,
                                          allow_truncated=False,
                                          decode_choices=True)
                except cantools.DecodeError:
                    continue
                for sig, val in decoded.items():
                    if sig not in SIG_TO_GROUP:
                        continue
                    unit = mdef.get_signal_by_name(sig).unit or ""
                    self.new_signal.emit(sig, val, unit)
        finally:
            if hasattr(self._bus, "shutdown"):
                self._bus.shutdown()
    def stop(self):
        self._running = False
        self.wait()


# ─────────────────────────────────────────────────────────────────────────────
# GUI window
# ─────────────────────────────────────────────────────────────────────────────
class _SignalTable(QTableWidget):
    """Reusable 2-column table (Signal | Value | Unit)."""
    HEADERS = ["Signal", "Value", "Unit"]
    def __init__(self, signals: set[str]):
        super().__init__(len(signals), len(self.HEADERS))
        self.setHorizontalHeaderLabels(self.HEADERS)
        self.horizontalHeader().setStretchLastSection(True)
        self.verticalHeader().setVisible(False)
        self.setEditTriggers(QTableWidget.NoEditTriggers)

        # row lookup
        self._row_for: Dict[str, int] = {}
        for row, sig in enumerate(sorted(signals)):
            self._row_for[sig] = row
            item = QTableWidgetItem(sig)
            item.setTextAlignment(Qt.AlignCenter)
            self.setItem(row, 0, item)

    # public update API
    def update_value(self, sig: str, value: float, unit: str):
        row = self._row_for[sig]

        # value
        vitem = self.item(row, 1)
        if vitem is None:
            vitem = QTableWidgetItem(); vitem.setTextAlignment(Qt.AlignCenter)
            self.setItem(row, 1, vitem)
        vitem.setText(str(value))

        # unit
        uitem = self.item(row, 2)
        if uitem is None:
            uitem = QTableWidgetItem(); uitem.setTextAlignment(Qt.AlignCenter)
            self.setItem(row, 2, uitem)
        uitem.setText(unit)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Important Parameters & Battery Errors")
        self.resize(650, 500)

        # ── Build two tables inside group boxes ────────────────────────────
        self._table_imp   = _SignalTable(IMPORTANT_PARAMS)
        self._table_error = _SignalTable(BATTERY_ERRORS)

        box_imp   = QGroupBox("Important Parameters")
        box_err   = QGroupBox("Battery Errors")

        lay_imp = QVBoxLayout(); lay_imp.addWidget(self._table_imp)
        lay_err = QVBoxLayout(); lay_err.addWidget(self._table_error)
        box_imp.setLayout(lay_imp); box_err.setLayout(lay_err)

        # stack vertically
        layout = QVBoxLayout()
        layout.addWidget(box_imp)
        layout.addWidget(box_err)
        root = QWidget(); root.setLayout(layout)
        self.setCentralWidget(root)

        # ── Start CAN thread ───────────────────────────────────────────────
        _, bus = get_config_and_bus()
        print(f"Loaded DBC: {DBC_PATH}  (messages: {len(dbc.messages)})")
        self._reader = CanReader(bus)
        self._reader.new_signal.connect(self._dispatch_update)
        self._reader.start()

    # route signal to correct table
    def _dispatch_update(self, sig: str, value: float, unit: str):
        group = SIG_TO_GROUP[sig]
        if group == "important":
            self._table_imp.update_value(sig, value, unit)
        else:
            self._table_error.update_value(sig, value, unit)

    def closeEvent(self, event):
        self._reader.stop()
        super().closeEvent(event)


# ─────────────────────────────────────────────────────────────────────────────
# Stand-alone run
# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = MainWindow(); win.show()
    sys.exit(app.exec())
