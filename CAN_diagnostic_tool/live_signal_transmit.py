import sys
import time
from dataclasses import dataclass
from typing import Callable, Dict, Optional, Tuple, List

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QComboBox, QPushButton, QGroupBox, QFormLayout, QRadioButton,
    QButtonGroup, QSlider, QDoubleSpinBox, QMessageBox, QScrollArea,
    QTableWidget, QTableWidgetItem, QCheckBox, QSpinBox, QHeaderView
)

from dbc_page import dbc
from PEAK_API import get_config_and_bus


cfg, BUS = get_config_and_bus()


def _compute_physical_bounds(length_bits: int, is_signed: bool, scale: float, offset: float,
                             smin: Optional[float], smax: Optional[float]) -> Tuple[float, float]:
    if smin is not None and smax is not None:
        return float(smin), float(smax)
    if is_signed:
        raw_min = -(2 ** (length_bits - 1))
        raw_max = (2 ** (length_bits - 1)) - 1
    else:
        raw_min = 0
        raw_max = (2 ** length_bits) - 1
    phys_min = raw_min * scale + offset
    phys_max = raw_max * scale + offset
    if phys_min > phys_max:
        phys_min, phys_max = phys_max, phys_min
    return float(phys_min), float(phys_max)


def _decimals_for_step(step: float) -> int:
    s = f"{step:.10f}".rstrip("0").split(".")
    return len(s[1]) if len(s) > 1 else 0


@dataclass
class RowWidgets:
    # Compact holder for widgets and metadata per row
    msg: any
    sig: any
    value_widget: QWidget
    get_value: Callable[[], float]
    enable_chk: QCheckBox
    cycle_spin: QSpinBox
    count_item: QTableWidgetItem
    next_due: Optional[float] = None


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Live Signal Transmit")
        self.resize(1200, 720)

        # Table with all signals across all messages
        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels([
            "Message ID", "Message Name", "Signal Name", "Value", "Unit", "Cycle time(ms)", "Count"
        ])
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setStretchLastSection(True)

        # Fill rows
        self._rows: List[RowWidgets] = []
        self._msg_values: Dict[int, Dict[str, float]] = {}  # key: frame_id -> {sig_name: value}
        self._populate_rows()

        # Controls row
        controls = QHBoxLayout()
        self.start_all_btn = QPushButton("Enable All")
        self.stop_all_btn = QPushButton("Disable All")
        self.clear_counts_btn = QPushButton("Clear Counts")
        controls.addWidget(self.start_all_btn)
        controls.addWidget(self.stop_all_btn)
        controls.addWidget(self.clear_counts_btn)
        controls.addStretch()
        self.status_lbl = QLabel("")
        controls.addWidget(self.status_lbl)
        self.start_all_btn.clicked.connect(self._enable_all)
        self.stop_all_btn.clicked.connect(self._disable_all)
        self.clear_counts_btn.clicked.connect(self._clear_counts)

        # Layout
        root_layout = QVBoxLayout()
        root_layout.addLayout(controls)
        root_layout.addWidget(self.table)
        root = QWidget(); root.setLayout(root_layout)
        self.setCentralWidget(root)

        # Timer for periodic transmission
        self._timer = QTimer(self)
        self._timer.setInterval(20)  # 50 Hz tick
        self._timer.timeout.connect(self._on_tick)
        self._timer.start()
        self._tx_total = 0

    # ---- UI builders ----------------------------------------------------
    def _populate_rows(self):
        # Count all signals
        total_signals = sum(len(m.signals) for m in dbc.messages)
        self.table.setRowCount(total_signals)
        row_idx = 0
        for m in dbc.messages:
            frame_id = m.frame_id
            self._msg_values.setdefault(frame_id, {})
            for sig in m.signals:
                # Columns 0-2: Message ID, Message Name, Signal Name
                msg_id_item = QTableWidgetItem(f"0x{frame_id:X}{' (EXT)' if m.is_extended_frame else ''}")
                msg_id_item.setFlags(msg_id_item.flags() ^ Qt.ItemIsEditable)
                self.table.setItem(row_idx, 0, msg_id_item)

                msg_name_item = QTableWidgetItem(m.name)
                msg_name_item.setFlags(msg_name_item.flags() ^ Qt.ItemIsEditable)
                self.table.setItem(row_idx, 1, msg_name_item)

                sig_name_item = QTableWidgetItem(sig.name)
                sig_name_item.setFlags(sig_name_item.flags() ^ Qt.ItemIsEditable)
                self.table.setItem(row_idx, 2, sig_name_item)

                # Column 3: Value editor (slider + spinbox compact)
                value_widget, getter, initial_val = self._create_value_editor(sig)
                self.table.setCellWidget(row_idx, 3, value_widget)
                # Save initial
                self._msg_values[frame_id][sig.name] = initial_val

                # Column 4: Unit
                unit_txt = sig.unit or ""
                unit_item = QTableWidgetItem(str(unit_txt))
                unit_item.setFlags(unit_item.flags() ^ Qt.ItemIsEditable)
                self.table.setItem(row_idx, 4, unit_item)

                # Column 5: Cycle time + enable checkbox
                cyc_widget, enable_chk, cyc_spin = self._create_cycle_widget()
                self.table.setCellWidget(row_idx, 5, cyc_widget)

                # Column 6: Count
                count_item = QTableWidgetItem("0")
                count_item.setTextAlignment(Qt.AlignCenter)
                count_item.setFlags(count_item.flags() ^ Qt.ItemIsEditable)
                self.table.setItem(row_idx, 6, count_item)

                # Track row
                rw = RowWidgets(
                    msg=m,
                    sig=sig,
                    value_widget=value_widget,
                    get_value=getter,
                    enable_chk=enable_chk,
                    cycle_spin=cyc_spin,
                    count_item=count_item,
                    next_due=None,
                )
                # Keep message values in sync when control changes
                self._wire_value_change(rw)
                # Start/stop scheduling when checkbox toggled
                enable_chk.toggled.connect(lambda checked, r=rw: self._on_enable_toggled(r, checked))
                self._rows.append(rw)

                row_idx += 1

        # Resize for readability
        self.table.resizeColumnsToContents()
        self.table.horizontalHeader().setStretchLastSection(True)

    def _create_value_editor(self, sig):
        # Build compact value editor (slider + spinbox)
        scale = float(sig.scale or 1.0)
        offset = float(sig.offset or 0.0)
        pmin, pmax = _compute_physical_bounds(sig.length, sig.is_signed, scale, offset, sig.minimum, sig.maximum)
        if pmin == pmax:
            pmax = pmin + max(scale, 1.0)
        step = abs(scale) if scale != 0 else 1.0
        decimals = min(6, max(0, _decimals_for_step(step)))

        row = QWidget(); h = QHBoxLayout(); h.setContentsMargins(4, 0, 4, 0); h.setSpacing(6); row.setLayout(h)
        slider = QSlider(Qt.Horizontal); slider.setFixedHeight(18)
        spin = QDoubleSpinBox(); spin.setDecimals(decimals); spin.setRange(pmin, pmax); spin.setSingleStep(step)

        total_steps_exact = int(round((pmax - pmin) / step))
        slider_steps = max(1, min(1000, total_steps_exact))
        slider.setRange(0, slider_steps)

        def slider_to_phys(pos: int) -> float:
            ratio = pos / slider_steps if slider_steps else 0
            val = pmin + ratio * (pmax - pmin)
            snapped = round((val - pmin) / step) * step + pmin
            return max(pmin, min(pmax, snapped))

        def phys_to_slider(val: float) -> int:
            v = max(pmin, min(pmax, val))
            ratio = 0 if pmax == pmin else (v - pmin) / (pmax - pmin)
            return int(round(ratio * slider_steps))

        def on_slider_changed(pos: int):
            spin.blockSignals(True)
            spin.setValue(slider_to_phys(pos))
            spin.blockSignals(False)

        def on_spin_changed(val: float):
            slider.blockSignals(True)
            slider.setValue(phys_to_slider(val))
            slider.blockSignals(False)

        slider.valueChanged.connect(on_slider_changed)
        spin.valueChanged.connect(on_spin_changed)

        # initial value = pmin
        on_spin_changed(pmin)

        h.addWidget(slider, 2)
        h.addWidget(spin, 1)
        return row, (lambda s=spin: float(s.value())), float(pmin)

    def _create_cycle_widget(self):
        w = QWidget(); h = QHBoxLayout(); h.setContentsMargins(6, 0, 6, 0); h.setSpacing(6); w.setLayout(h)
        chk = QCheckBox("Enable")
        spin = QSpinBox(); spin.setRange(1, 60000); spin.setSuffix(" ms"); spin.setValue(100)
        h.addWidget(chk)
        h.addWidget(spin)
        h.addStretch()
        return w, chk, spin

    def _wire_value_change(self, rw: 'RowWidgets'):
        # Update cached message value whenever the spin changes
        # Locate the QDoubleSpinBox inside value_widget
        spin: Optional[QDoubleSpinBox] = None
        for child in rw.value_widget.findChildren(QDoubleSpinBox):
            spin = child
            break
        if spin is None:
            return

        frame_id = rw.msg.frame_id

        def on_changed(val: float):
            self._msg_values[frame_id][rw.sig.name] = float(val)

        spin.valueChanged.connect(on_changed)
        # Set initial cached value
        self._msg_values[frame_id][rw.sig.name] = rw.get_value()

    # ---- actions ---------------------------------------------------------
    def _on_enable_toggled(self, rw: 'RowWidgets', checked: bool):
        if checked:
            now = time.monotonic()
            rw.next_due = now  # transmit immediately on next tick
        else:
            rw.next_due = None

    def _on_tick(self):
        if not self._rows:
            return
        now = time.monotonic()
        # For rows that are due, send message with current values
        for rw in self._rows:
            if not rw.enable_chk.isChecked() or rw.next_due is None:
                continue
            if now + 1e-6 < rw.next_due:
                continue
            # Prepare values for the message: use cached map
            frame_id = rw.msg.frame_id
            values = dict(self._msg_values.get(frame_id, {}))
            # Ensure at least this signal has current value
            values[rw.sig.name] = rw.get_value()
            try:
                payload = rw.msg.encode(values)
                BUS.send(rw.msg.frame_id, rw.msg.is_extended_frame, bytes(payload))
            except Exception as ex:
                # Show once and disable to avoid spamming
                QMessageBox.critical(self, "Transmit Error", f"Failed to send {rw.msg.name}/{rw.sig.name}:\n{ex}")
                rw.enable_chk.setChecked(False)
                rw.next_due = None
                continue
            # Increment count
            try:
                count = int(rw.count_item.text()) + 1
            except ValueError:
                count = 1
            rw.count_item.setText(str(count))
            # Update status
            self._tx_total += 1
            self.status_lbl.setText(f"Last TX: 0x{rw.msg.frame_id:X} {rw.msg.name}  len={len(payload)}  total={self._tx_total}")
            # Schedule next
            period_s = max(1, rw.cycle_spin.value()) / 1000.0
            rw.next_due = now + period_s

    def _enable_all(self):
        for rw in self._rows:
            rw.enable_chk.setChecked(True)

    def _disable_all(self):
        for rw in self._rows:
            rw.enable_chk.setChecked(False)

    def _clear_counts(self):
        for rw in self._rows:
            rw.count_item.setText("0")


def main():
    app = QApplication(sys.argv)
    win = MainWindow(); win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()


