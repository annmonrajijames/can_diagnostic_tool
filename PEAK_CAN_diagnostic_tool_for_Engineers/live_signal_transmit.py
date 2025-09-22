import sys
import time
from dataclasses import dataclass
from typing import Callable, Dict, Optional, Tuple, List

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QComboBox, QPushButton, QGroupBox, QFormLayout, QRadioButton,
    QButtonGroup, QSlider, QDoubleSpinBox, QMessageBox, QScrollArea,
    QTableWidget, QTableWidgetItem, QCheckBox, QSpinBox, QHeaderView, QLineEdit
)

from dbc_decode_input import dbc
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
    row_index: int
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

        # Fill rows and set up per-message state
        self._rows: List[RowWidgets] = []
        self._msg_values: Dict[int, Dict[str, float]] = {}  # key: frame_id -> {sig_name: value}
        self._msg_group: Dict[int, List[RowWidgets]] = {}
        # Per-message scheduler: frame_id -> {enabled, cycle_ms, next_due, mdef}
        self._msg_sched: Dict[int, Dict[str, object]] = {}
        self._populate_rows()

        # Controls row
        controls = QHBoxLayout()
        # Search bar for Signal Name
        controls.addWidget(QLabel("Search Signal:"))
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Type to filter signal name…")
        try:
            self.search_edit.setClearButtonEnabled(True)
        except Exception:
            pass
        self.search_edit.textChanged.connect(self._apply_signal_filter)
        controls.addWidget(self.search_edit, 1)
        # Enabled-only filter
        self.only_enabled_chk = QCheckBox("Show Enabled Signals")
        self.only_enabled_chk.toggled.connect(self._apply_filters)
        controls.addWidget(self.only_enabled_chk)
        # Bulk buttons
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

        # Initialize filter to show all
        self._apply_filters()

    # ---- UI builders ----------------------------------------------------
    def _populate_rows(self):
        # Count all signals
        total_signals = sum(len(m.signals) for m in dbc.messages)
        self.table.setRowCount(total_signals)
        row_idx = 0
        for m in dbc.messages:
            frame_id = m.frame_id
            self._msg_values.setdefault(frame_id, {})
            self._msg_group.setdefault(frame_id, [])
            self._msg_sched.setdefault(frame_id, {
                "enabled": False,
                "cycle_ms": 100,
                "next_due": None,
                "mdef": m,
            })
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
                    row_index=row_idx,
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
                # Cycle time changed → take this row's cycle for the message
                cyc_spin.valueChanged.connect(lambda _val, r=rw: self._on_cycle_changed(r))
                self._rows.append(rw)
                self._msg_group[frame_id].append(rw)

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

    def _apply_signal_filter(self, _text: str):
        # Back-compat slot; use unified filters
        self._apply_filters()

    def _apply_filters(self):
        pattern = (self.search_edit.text() or "").strip().lower()
        only_enabled = self.only_enabled_chk.isChecked()
        rc = self.table.rowCount()
        for r in range(rc):
            # search filter
            item = self.table.item(r, 2)  # Signal Name column
            name = item.text().lower() if item is not None else ""
            matches = (pattern in name) if pattern else True
            # enabled filter
            enabled_ok = True
            if only_enabled:
                if 0 <= r < len(self._rows):
                    enabled_ok = self._rows[r].enable_chk.isChecked()
                else:
                    enabled_ok = False
            visible = matches and enabled_ok
            self.table.setRowHidden(r, not visible)

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
            # Update value cache
            self._msg_values[frame_id][rw.sig.name] = float(val)

        spin.valueChanged.connect(on_changed)
        # Set initial cached value
        self._msg_values[frame_id][rw.sig.name] = rw.get_value()

    # ---- actions ---------------------------------------------------------
    def _on_enable_toggled(self, rw: 'RowWidgets', checked: bool):
        # Recompute message enabled if any row under same frame is enabled
        frame_id = rw.msg.frame_id
        group = self._msg_group.get(frame_id, [])
        enabled = any(r.enable_chk.isChecked() for r in group)
        sched = self._msg_sched[frame_id]
        sched["enabled"] = enabled
        if enabled:
            sched["next_due"] = time.monotonic()  # send ASAP
        else:
            sched["next_due"] = None

    def _on_cycle_changed(self, rw: 'RowWidgets'):
        # Take this row's cycle for the message and reset schedule
        self._set_msg_cycle_from_row(rw)

    def _set_msg_cycle_from_row(self, rw: 'RowWidgets'):
        frame_id = rw.msg.frame_id
        sched = self._msg_sched[frame_id]
        sched["cycle_ms"] = int(max(1, rw.cycle_spin.value()))
        sched["next_due"] = time.monotonic()

    def _on_tick(self):
        if not self._rows:
            return
        now = time.monotonic()
        # For messages that are due, send once per message with merged values
        for frame_id, sched in self._msg_sched.items():
            if not sched["enabled"] or sched["next_due"] is None:
                continue
            if now + 1e-6 < sched["next_due"]:
                continue
            mdef = sched["mdef"]
            # Values: use cached map
            values = dict(self._msg_values.get(frame_id, {}))
            # Ensure cached reflects the current widgets state for enabled rows
            for r in self._msg_group.get(frame_id, []):
                if r.enable_chk.isChecked():
                    values[r.sig.name] = r.get_value()
            try:
                payload = mdef.encode(values)
                BUS.send(mdef.frame_id, mdef.is_extended_frame, bytes(payload))
            except Exception as ex:
                # Disable all rows for this message to avoid spamming
                for r in self._msg_group.get(frame_id, []):
                    r.enable_chk.setChecked(False)
                sched["enabled"] = False
                sched["next_due"] = None
                QMessageBox.critical(self, "Transmit Error", f"Failed to send {mdef.name}:\n{ex}")
                continue
            # Increment count for enabled rows
            for r in self._msg_group.get(frame_id, []):
                if r.enable_chk.isChecked():
                    try:
                        count = int(r.count_item.text()) + 1
                    except ValueError:
                        count = 1
                    r.count_item.setText(str(count))
            # Update status
            self._tx_total += 1
            self.status_lbl.setText(f"Last TX: 0x{mdef.frame_id:X} {mdef.name} len={len(payload)} total={self._tx_total}")
            # Schedule next
            period_s = max(1, int(sched["cycle_ms"])) / 1000.0
            sched["next_due"] = now + period_s

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


