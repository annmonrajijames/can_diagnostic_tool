#!/usr/bin/env python3
# live_can_decoder.py
#
# Real‑time CAN frame decoder for PEAK‑CAN + PySide6
# Adds a “Cycle time (ms)” column showing the interval between frames
# of the same CAN ID.
#
# (c) 2025 – Annmon’s diagnostic‑tool demo

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple

import can                                     # python‑can
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QTableWidget, QTableWidgetItem,
    QVBoxLayout, QWidget
)

# ─────────────────── USER SETTINGS ──────────────────────────────
SIGNALS_CSV   = Path(r"C:\Users\annmo\Downloads\signals.csv")   # ← update
PCAN_CHANNEL  = "PCAN_USBBUS1"                    # ← update
BITRATE       = 500_000                           # ← update
# ────────────────────────────────────────────────────────────────

def decode_signal(payload: bytes,
                  start: int,
                  length: int,
                  byte_order: str,
                  is_signed: bool,
                  scale: float,
                  offset: float):
    """
    Return the *physical* value using Vector numbering.
    • Intel  (little) → start bit is LSB, bits ascend
    • Motorola (big)  → start bit is MSB, bits descend **within each byte**
                         but jump +8 every full byte (Vector rule)
    """
    def get_bit(data: bytes, bit: int) -> int:
        return (data[bit // 8] >> (bit & 7)) & 1

    order_key = ''.join(byte_order.lower().split())
    motorola = any(k in order_key for k in ("motorola", "big", "msb"))
    raw = 0

    if motorola:
        for i in range(length):
            # Vector Motorola rule
            bit = start + 8 * (i // 8) - (i % 8)
            raw = (raw << 1) | get_bit(payload, bit)
    else:  # Intel / little-endian
        for i in range(length):
            raw |= get_bit(payload, start + i) << i

    if is_signed and raw & (1 << (length - 1)):
        raw -= 1 << length

    return raw * scale + offset

# ====== CSV → in‑memory definitions =========================================
@dataclass
class SignalDef:
    msg_id: int            # arbitration id (decimal)
    name: str
    start: int
    length: int
    byte_order: str
    is_signed: bool
    scale: float
    offset: float


def load_signal_db(csv_path: Path) -> Dict[int, List[SignalDef]]:
    """
    Load signals.csv → {msg_id: [SignalDef …]}.

    Handles UTF‑8 files that may begin with a BOM.
    """
    db: Dict[int, List[SignalDef]] = {}

    with csv_path.open(newline='', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)

        for row in reader:
            raw_id = row["msg_id"].strip()
            if not raw_id:                         # skip blanks
                continue

            msg_id = int(raw_id, 0)               # auto 0x / decimal
            sig = SignalDef(
                msg_id     = msg_id,
                name       = row["sig_name"],
                start      = int(row["start"]),
                length     = int(row["length"]),
                byte_order = row.get("byte_order", "Intel"),
                is_signed  = row.get("is_signed", "False").lower() in ("1","true","yes"),
                scale      = float(row.get("scale", 1)),
                offset     = float(row.get("offset", 0)),
            )
            db.setdefault(msg_id, []).append(sig)

    return db


# ====== CAN reader thread ====================================================
class CanReader(QThread):
    """
    Runs in the background, decodes frames and emits:
        new_value(msg_id, sig_name, physical_value, cycle_ms)
    """
    new_value = Signal(int, str, float, float)

    def __init__(self, sig_db: Dict[int, List[SignalDef]],
                 channel: str, bitrate: int):
        super().__init__()
        self.sig_db   = sig_db
        self.channel  = channel
        self.bitrate  = bitrate
        self._stop    = False
        self._last_ts: Dict[int, float] = {}   # msg_id → last timestamp (sec)

    def run(self) -> None:
        bus = can.Bus(interface="pcan",
                      channel=self.channel,
                      bitrate=self.bitrate)
        try:
            for msg in bus:
                if self._stop:
                    break

                defs = self.sig_db.get(msg.arbitration_id)
                if not defs:                     # ignore un‑known IDs
                    continue

                now = msg.timestamp              # float seconds
                cycle_ms = 0.0
                if msg.arbitration_id in self._last_ts:
                    cycle_ms = (now - self._last_ts[msg.arbitration_id]) * 1000.0
                self._last_ts[msg.arbitration_id] = now

                payload = msg.data
                for d in defs:
                    val = decode_signal(payload, d.start, d.length,
                                        d.byte_order, d.is_signed,
                                        d.scale, d.offset)
                    self.new_value.emit(d.msg_id, d.name, val, cycle_ms)
        finally:
            bus.shutdown()

    def stop(self):
        self._stop = True
        self.quit()
        self.wait()


# ====== GUI ==================================================================
class MainWindow(QMainWindow):
    headers = ["Msg ID (hex)", "Signal name", "Value", "Cycle time (ms)"]

    def __init__(self, sig_db: Dict[int, List[SignalDef]]):
        super().__init__()
        self.setWindowTitle("Live CAN Decoder")
        self.resize(900, 600)

        self.table   = QTableWidget(0, len(self.headers))
        self.table.setHorizontalHeaderLabels(self.headers)
        self.table.horizontalHeader().setStretchLastSection(True)

        self.row_map: Dict[Tuple[int, str], int] = {}  # (id, name) → row

        lay = QVBoxLayout()
        lay.addWidget(self.table)
        container = QWidget()
        container.setLayout(lay)
        self.setCentralWidget(container)

        # start CAN thread
        self.reader = CanReader(sig_db, PCAN_CHANNEL, BITRATE)
        self.reader.new_value.connect(self.on_new_value)
        self.reader.start()

    # ---------- slot ----------
    def on_new_value(self, msg_id: int, name: str,
                     value: float, cycle_ms: float):
        key = (msg_id, name)
        row = self.row_map.get(key)
        if row is None:
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setItem(row, 0, QTableWidgetItem(f"0x{msg_id:08X}"))
            self.table.setItem(row, 1, QTableWidgetItem(name))
            self.row_map[key] = row

        # value cell
        v_item = QTableWidgetItem(f"{value:.3f}")
        v_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.table.setItem(row, 2, v_item)

        # cycle‑time cell (show ‘—’ on first reception)
        if cycle_ms == 0:
            text = "—"
        else:
            text = f"{cycle_ms:.1f}"
        c_item = QTableWidgetItem(text)
        c_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.table.setItem(row, 3, c_item)

    def closeEvent(self, ev):
        self.reader.stop()
        super().closeEvent(ev)


# ====== main =================================================================
def main() -> None:
    sig_db = load_signal_db(SIGNALS_CSV)
    app    = QApplication([])
    win    = MainWindow(sig_db)
    win.show()
    app.exec()

if __name__ == "__main__":
    main()
