#!/usr/bin/env python3
# live_can_decoder.py
#
# (c) 2025 – drop‑in demo for Annmon

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple

import can                             # python‑can: PEAK backend
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QTableWidget, QTableWidgetItem,
    QVBoxLayout, QWidget
)

# ─────────────────── USER SETTINGS ──────────────────────────────
SIGNALS_CSV   = Path(r"C:\Users\annmo\Downloads\signals.csv")   # ← 1) change me
PCAN_CHANNEL  = "PCAN_USBBUS1"                    # ← 2) change me
BITRATE       = 500_000                           # ← 2) change me
# ────────────────────────────────────────────────────────────────


# ====== bit helpers ==========================================================
def _vbit(data: bytes, pos: int) -> int:
    """Return the value (0|1) of absolute bit *pos* (Vector numbering)."""
    byte_i, bit_i = divmod(pos, 8)
    return (data[byte_i] >> bit_i) & 1


def decode_signal(payload: bytes,
                  start: int,
                  length: int,
                  byte_order: str,
                  is_signed: bool,
                  scale: float,
                  offset: float) -> float:
    """
    Return the *physical* value using Vector numbering.

    • Intel (little)  → start bit is LSB, bits ascend
    • Motorola (big)  → start bit is MSB, bits descend within each byte
                        but jump +8 every full byte (Vector rule)
    """
    order_key = ''.join(byte_order.lower().split())
    motorola  = any(k in order_key for k in ("motorola", "big", "msb"))

    raw = 0
    if motorola:                                   # MSB‑first packing
        for i in range(length):
            bit = start + 8 * (i // 8) - (i % 8)   # Vector Motorola rule
            raw = (raw << 1) | _vbit(payload, bit)
    else:                                          # Intel / little‑endian
        for i in range(length):
            raw |= _vbit(payload, start + i) << i

    if is_signed and raw & (1 << (length - 1)):    # two’s‑complement
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
    """Load signals.csv → {msg_id: [SignalDef,…]} (handles UTF‑8 BOM)."""
    db: Dict[int, List[SignalDef]] = {}

    with csv_path.open(newline='', encoding='utf-8-sig') as f:  # ← HERE
        reader = csv.DictReader(f)

        for row in reader:
            raw_id = row["msg_id"].strip()      # now works ✔
            if not raw_id:
                continue

            msg_id = int(raw_id, 0)             # auto 0x / decimal
            sig = SignalDef(
                msg_id   = msg_id,
                name     = row["sig_name"],
                start    = int(row["start"]),
                length   = int(row["length"]),
                byte_order = row.get("byte_order", "Intel"),
                is_signed  = row.get("is_signed", "False").lower() in ("1","true","yes"),
                scale      = float(row.get("scale", 1)),
                offset     = float(row.get("offset", 0)),
            )
            db.setdefault(msg_id, []).append(sig)

    return db

# ====== CAN reader thread ====================================================
class CanReader(QThread):
    new_value = Signal(int, str, float)     # msg_id, sig_name, phys_val

    def __init__(self, sig_db: Dict[int, List[SignalDef]],
                 channel: str, bitrate: int):
        super().__init__()
        self.sig_db   = sig_db
        self.channel  = channel
        self.bitrate  = bitrate
        self._stop    = False

    def run(self) -> None:
        bus = can.Bus(interface="pcan",
                      channel=self.channel,
                      bitrate=self.bitrate)
        try:
            for msg in bus:
                if self._stop:
                    break
                defs = self.sig_db.get(msg.arbitration_id)
                if not defs:
                    continue
                payload = msg.data
                for d in defs:
                    value = decode_signal(payload, d.start, d.length,
                                          d.byte_order, d.is_signed,
                                          d.scale, d.offset)
                    self.new_value.emit(d.msg_id, d.name, value)
        finally:
            bus.shutdown()

    def stop(self):
        self._stop = True
        self.quit()
        self.wait()


# ====== GUI ==================================================================
class MainWindow(QMainWindow):
    headers = ["Msg ID (hex)", "Signal name", "Value"]

    def __init__(self, sig_db: Dict[int, List[SignalDef]]):
        super().__init__()
        self.setWindowTitle("Live CAN Decoder")
        self.resize(800, 600)

        self.table   = QTableWidget(0, len(self.headers))
        self.table.setHorizontalHeaderLabels(self.headers)
        self.table.horizontalHeader().setStretchLastSection(True)

        self.row_map: Dict[Tuple[int,str], int] = {}  # (id,name) → row

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
    def on_new_value(self, msg_id: int, name: str, value: float):
        key = (msg_id, name)
        row = self.row_map.get(key)
        if row is None:
            row = self.table.rowCount()
            self.table.insertRow(row)
            # static cells
            self.table.setItem(row, 0, QTableWidgetItem(f"0x{msg_id:08X}"))
            self.table.setItem(row, 1, QTableWidgetItem(name))
            self.row_map[key] = row
        # live value cell
        item = QTableWidgetItem(f"{value:.3f}")
        item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.table.setItem(row, 2, item)

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
