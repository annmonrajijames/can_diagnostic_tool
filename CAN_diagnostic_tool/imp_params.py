# imp_params.py
"""
Live monitor for five signal groups:
1. Important Parameters
2. Battery Errors
3. MCU Errors
4. Cluster Errors
5. Charger Errors
"""

from __future__ import annotations
import sys
from typing import Dict

import cantools
from PySide6.QtCore    import QThread, Signal, Qt
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget,
    QVBoxLayout, QTableWidget, QTableWidgetItem,
    QGroupBox
)

from PEAK_API import get_config_and_bus
from dbc_page  import dbc, DBC_PATH


# ── Signal groups ────────────────────────────────────────────────────────────
IMPORTANT_PARAMS = {
    "IgnitionStatus", "Brake_Pulse", "PackCurr", "PackVol",
    "chgStatus_chg_idle", "ChgFetStatus", "DchgFetStatus",
}

BATTERY_ERRORS = {
    "CellUnderVolProt", "CellOverVolProt", "PackUnderVolProt", "PackOverVolProt",
    "ChgUnderTempProt", "ChgOverTempProt", "DchgUnderTempProt", "DchgOverTempProt",
    "CellOverDevProt", "ChgOverCurrProt", "DchgOverCurrProt", "FetTempProt",
    "ResSocProt", "FetFailure", "TempSenseFault", "PreChgFetStatus",
    "ResStatus", "ShortCktProt", "DschgPeakProt",
}

MCU_ERRORS = {
    "DriveError_Motor_hall", "Motor_Stalling", "Motor_Phase_loss",
    "Controller_Over_Temeprature", "Motor_Over_Temeprature", "Throttle_Error",
    "MOSFET_Protection", "DriveError_Controller_OverVoltag",
    "Controller_Undervoltage", "Overcurrent_Fault", "Drive_Error_Flag",
}

CLUSTER_ERRORS = {"Cluster_HeartBeat", "Mode_Ack"}

CHARGER_ERRORS = {"ChgAuth", "ChgPeakProt"}

# map every signal to its table key
SIG_TO_GROUP = (
    {s: "important" for s in IMPORTANT_PARAMS} |
    {s: "battery"   for s in BATTERY_ERRORS}   |
    {s: "mcu"       for s in MCU_ERRORS}       |
    {s: "cluster"   for s in CLUSTER_ERRORS}   |
    {s: "charger"   for s in CHARGER_ERRORS}
)


# ── Helper: frame-id → cantools message ──────────────────────────────────────
def _get_message(db: cantools.database.Database, frame_id: int, is_ext: bool):
    lookup_id = frame_id | 0x8000_0000 if is_ext else frame_id
    return db._frame_id_to_message.get(lookup_id)


# ── Background CAN reader thread ─────────────────────────────────────────────
class CanReader(QThread):
    new_signal = Signal(str, float, str)       # sig_name, value, unit

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


# ── Reusable 3-column table widget ───────────────────────────────────────────
class _SignalTable(QTableWidget):
    HEADERS = ["Signal", "Value", "Unit"]

    def __init__(self, signals: set[str]):
        super().__init__(len(signals), len(self.HEADERS))
        self.setHorizontalHeaderLabels(self.HEADERS)
        self.horizontalHeader().setStretchLastSection(True)
        self.verticalHeader().setVisible(False)
        self.setEditTriggers(QTableWidget.NoEditTriggers)

        # fixed row order
        self._row_for: Dict[str, int] = {}
        for row, sig in enumerate(sorted(signals)):
            self._row_for[sig] = row
            item = QTableWidgetItem(sig)
            item.setTextAlignment(Qt.AlignCenter)
            self.setItem(row, 0, item)

    def update_value(self, sig: str, value: float, unit: str):
        row = self._row_for[sig]

        val_item = self.item(row, 1) or QTableWidgetItem()
        val_item.setTextAlignment(Qt.AlignCenter)
        self.setItem(row, 1, val_item)
        val_item.setText(str(value))

        unit_item = self.item(row, 2) or QTableWidgetItem()
        unit_item.setTextAlignment(Qt.AlignCenter)
        self.setItem(row, 2, unit_item)
        unit_item.setText(unit)


# ── Main window ──────────────────────────────────────────────────────────────
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Live Monitor: Parameters & Error Flags")
        self.resize(750, 800)

        # tables
        self._tbl_imp     = _SignalTable(IMPORTANT_PARAMS)
        self._tbl_batt    = _SignalTable(BATTERY_ERRORS)
        self._tbl_mcu     = _SignalTable(MCU_ERRORS)
        self._tbl_cluster = _SignalTable(CLUSTER_ERRORS)
        self._tbl_chg     = _SignalTable(CHARGER_ERRORS)

        # group boxes
        box_imp  = self._wrap("Important Parameters", self._tbl_imp)
        box_batt = self._wrap("Battery Errors",       self._tbl_batt)
        box_mcu  = self._wrap("MCU Errors",           self._tbl_mcu)
        box_clu  = self._wrap("Cluster Errors",       self._tbl_cluster)
        box_chg  = self._wrap("Charger Errors",       self._tbl_chg)

        # layout
        layout = QVBoxLayout()
        layout.addWidget(box_imp)
        layout.addWidget(box_batt)
        layout.addWidget(box_mcu)
        layout.addWidget(box_clu)
        layout.addWidget(box_chg)
        root = QWidget(); root.setLayout(layout)
        self.setCentralWidget(root)

        # CAN reader
        _, bus = get_config_and_bus()
        print(f"Loaded DBC: {DBC_PATH}  (messages: {len(dbc.messages)})")
        self._reader = CanReader(bus)
        self._reader.new_signal.connect(self._dispatch_update)
        self._reader.start()

    @staticmethod
    def _wrap(title: str, widget: QWidget) -> QGroupBox:
        box = QGroupBox(title)
        lay = QVBoxLayout(); lay.addWidget(widget)
        box.setLayout(lay)
        return box

    # route incoming updates to the correct table
    def _dispatch_update(self, sig: str, value: float, unit: str):
        table_key = SIG_TO_GROUP[sig]
        if table_key == "important":
            self._tbl_imp.update_value(sig, value, unit)
        elif table_key == "battery":
            self._tbl_batt.update_value(sig, value, unit)
        elif table_key == "mcu":
            self._tbl_mcu.update_value(sig, value, unit)
        elif table_key == "cluster":
            self._tbl_cluster.update_value(sig, value, unit)
        else:  # charger
            self._tbl_chg.update_value(sig, value, unit)

    def closeEvent(self, event):
        self._reader.stop()
        super().closeEvent(event)


# ── Stand-alone run ──────────────────────────────────────────────────────────
if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = MainWindow(); win.show()
    sys.exit(app.exec())
