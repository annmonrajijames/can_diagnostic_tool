# imp_params.py
"""
Live monitor with compact side-by-side rows:

SignalName   Value Unit
"""

from __future__ import annotations
import sys
from typing import Dict

import cantools
from PySide6.QtCore    import Qt, Signal, QThread
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QLabel,
    QVBoxLayout, QHBoxLayout, QGroupBox, QScrollArea
)

from PEAK_API import get_config_and_bus
from dbc_page  import dbc, DBC_PATH


# ─────────────────────────── Signal groups ──────────────────────────────────
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

GROUPS: Dict[str, set[str]] = {
    "Important Parameters": IMPORTANT_PARAMS,
    "Battery Errors":        BATTERY_ERRORS,
    "MCU Errors":            MCU_ERRORS,
    "Cluster Errors":        CLUSTER_ERRORS,
    "Charger Errors":        CHARGER_ERRORS,
}

SIG_TO_GROUP = {sig: grp for grp, sset in GROUPS.items() for sig in sset}


# ───────────────────── Helper: frame-id → message ───────────────────────────
def _msg(db, fid: int, ext: bool):
    fid = fid | 0x8000_0000 if ext else fid
    return db._frame_id_to_message.get(fid)


# ──────────────────────────── CAN reader thread ─────────────────────────────
class CanReader(QThread):
    new_val = Signal(str, float, str)      # sig, value, unit
    def __init__(self, bus): super().__init__(); self.bus, self._run = bus, True
    def run(self):
        try:
            while self._run:
                m = self.bus.recv(0.1)
                if not m: continue
                d = _msg(dbc, m.arbitration_id, m.is_extended_id)
                if not d: continue
                try:
                    dec = d.decode(m.data, allow_truncated=False, decode_choices=True)
                except cantools.DecodeError:
                    continue
                for s, v in dec.items():
                    if s in SIG_TO_GROUP:
                        unit = d.get_signal_by_name(s).unit or ""
                        self.new_val.emit(s, v, unit)
        finally:
            if hasattr(self.bus, "shutdown"): self.bus.shutdown()
    def stop(self): self._run = False; self.wait()


# ───────────────────────────── UI widgets ───────────────────────────────────
class SignalRow(QWidget):
    """Single row: SignalName   Value Unit"""
    def __init__(self, name: str):
        super().__init__()
        self.lbl_name  = QLabel(name)
        self.lbl_val   = QLabel("—")
        self.lbl_name.setStyleSheet("font-weight:500;")
        lay = QHBoxLayout(); lay.setContentsMargins(2,0,2,0); lay.setSpacing(8)
        lay.addWidget(self.lbl_name); lay.addWidget(self.lbl_val); lay.addStretch()
        self.setLayout(lay)
    def update(self, value: float, unit: str):
        self.lbl_val.setText(f"{value} {unit}".rstrip())


class SignalGroup(QGroupBox):
    def __init__(self, title: str, signals: set[str]):
        super().__init__(title)
        self.rows: Dict[str, SignalRow] = {}
        vbox = QVBoxLayout(); vbox.setSpacing(2); vbox.setContentsMargins(4,4,4,4)
        for s in sorted(signals):
            row = SignalRow(s); self.rows[s] = row; vbox.addWidget(row)
        vbox.addStretch(); self.setLayout(vbox)
    def update(self, s: str, v: float, u: str): self.rows[s].update(v,u)


# ───────────────────────────── Main window ──────────────────────────────────
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Live Monitor")
        self.resize(520, 620)

        # build group widgets
        self._groups: Dict[str, SignalGroup] = {}
        v_main = QVBoxLayout()
        for title, sigs in GROUPS.items():
            g = SignalGroup(title, sigs); self._groups[title] = g; v_main.addWidget(g)
        v_main.addStretch()

        wrapper = QWidget(); wrapper.setLayout(v_main)
        scroll  = QScrollArea(); scroll.setWidgetResizable(True); scroll.setWidget(wrapper)
        self.setCentralWidget(scroll)

        # CAN
        _, bus = get_config_and_bus()
        print(f"Loaded DBC: {DBC_PATH} (messages: {len(dbc.messages)})")
        self._reader = CanReader(bus)
        self._reader.new_val.connect(self._route); self._reader.start()

    def _route(self, s, v, u): self._groups[SIG_TO_GROUP[s]].update(s,v,u)
    def closeEvent(self,e): self._reader.stop(); super().closeEvent(e)


# ───────────────────────────── Stand-alone run ──────────────────────────────
if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = MainWindow(); win.show()
    sys.exit(app.exec())
