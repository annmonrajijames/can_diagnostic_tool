# imp_params.py
"""
GUI page: "Important Parameters"
--------------------------------
Displays live values for a fixed set of critical CAN signals.

Columns:
    Signal Name | Value | Unit
"""

from __future__ import annotations
import sys
from typing import Dict

import cantools
from PySide6.QtCore    import QThread, Signal, Qt
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget,
    QVBoxLayout, QTableWidget, QTableWidgetItem
)

from PEAK_API import get_config_and_bus      # opens PEAK or dummy bus
from dbc_page  import dbc, DBC_PATH


# --------------------------------------------------------------------------- #
# Configuration: which signals to display
# --------------------------------------------------------------------------- #
INTEREST_SIGNALS = {
    "IgnitionStatus",
    "Brake_Pulse",
    "PackCurr",
    "PackVol",
    "chgStatus_chg_idle",
    "ChgFetStatus",
    "DchgFetStatus",
}


# --------------------------------------------------------------------------- #
# Helper: fast lookup frame-id → cantools message
# --------------------------------------------------------------------------- #
def _get_message(db: cantools.database.Database, frame_id: int, is_ext: bool):
    lookup_id = frame_id | 0x8000_0000 if is_ext else frame_id
    return db._frame_id_to_message.get(lookup_id)


# --------------------------------------------------------------------------- #
# Background thread that receives CAN frames and emits only the signals we need
# --------------------------------------------------------------------------- #
class CanReader(QThread):
    new_signal = Signal(str, float, str)          # sig_name, value, unit

    def __init__(self, bus):
        super().__init__(parent=None)
        self._bus      = bus
        self._running  = True

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

                for sig_name, val in decoded.items():
                    if sig_name not in INTEREST_SIGNALS:
                        continue
                    unit = mdef.get_signal_by_name(sig_name).unit or ""
                    self.new_signal.emit(sig_name, val, unit)
        finally:
            # Ensure hardware channel is closed when thread exits
            if hasattr(self._bus, "shutdown"):
                self._bus.shutdown()

    def stop(self):
        self._running = False
        self.wait()


# --------------------------------------------------------------------------- #
# GUI window
# --------------------------------------------------------------------------- #
class MainWindow(QMainWindow):
    HEADERS = ["Signal Name", "Value", "Unit"]

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Important Parameters")
        self.resize(500, 350)

        # --- Table setup -----------------------------------------------------
        self.table = QTableWidget(len(INTEREST_SIGNALS), len(self.HEADERS))
        self.table.setHorizontalHeaderLabels(self.HEADERS)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)

        # Fixed row order (alphabetical)
        self._row_for: Dict[str, int] = {}
        for row, sig in enumerate(sorted(INTEREST_SIGNALS)):
            self._row_for[sig] = row
            item = QTableWidgetItem(sig)
            item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, 0, item)

        # Layout
        layout = QVBoxLayout(); layout.addWidget(self.table)
        root = QWidget(); root.setLayout(layout)
        self.setCentralWidget(root)

        # --- Start CAN capture ----------------------------------------------
        cfg, bus = get_config_and_bus()
        print(f"Loaded DBC: {DBC_PATH}  (messages: {len(dbc.messages)})")
        self._reader = CanReader(bus)
        self._reader.new_signal.connect(self._update_value)
        self._reader.start()

    # Slot: update table cells
    def _update_value(self, sig_name: str, value: float, unit: str):
        row = self._row_for[sig_name]

        # Value column
        val_item = self.table.item(row, 1)
        if val_item is None:
            val_item = QTableWidgetItem(); val_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, 1, val_item)
        val_item.setText(str(value))

        # Unit column
        unit_item = self.table.item(row, 2)
        if unit_item is None:
            unit_item = QTableWidgetItem(); unit_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, 2, unit_item)
        unit_item.setText(unit)

    def closeEvent(self, event):
        """Ensure background thread (and bus) cleanly shut down."""
        self._reader.stop()
        super().closeEvent(event)


# --------------------------------------------------------------------------- #
# Optional standalone run: `python imp_params.py`
# --------------------------------------------------------------------------- #
if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = MainWindow(); win.show()
    sys.exit(app.exec())
