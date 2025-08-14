import sys
from dataclasses import dataclass
from typing import Callable, Dict, Optional, Tuple

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QComboBox, QPushButton, QGroupBox, QFormLayout, QRadioButton,
    QButtonGroup, QSlider, QDoubleSpinBox, QMessageBox, QScrollArea
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
class SignalEditor:
    name: str
    widget: QWidget
    get_value: Callable[[], float]


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Live Signal Transmit")
        self.resize(1100, 700)

        # Top: message selector and info
        top_row = QHBoxLayout()
        top_row.addWidget(QLabel("Message:"))
        self.msg_combo = QComboBox()
        for m in dbc.messages:
            self.msg_combo.addItem(m.name)
        self.msg_combo.currentIndexChanged.connect(self._on_message_changed)
        top_row.addWidget(self.msg_combo, 1)

        self.msg_id_label = QLabel("")
        top_row.addWidget(self.msg_id_label)

        self.transmit_btn = QPushButton("Transmit")
        self.transmit_btn.clicked.connect(self._transmit_once)
        top_row.addWidget(self.transmit_btn)

        # Center: dynamic signal editors inside a scroll area
        self.form = QFormLayout()
        self.form_group = QGroupBox("Signals")
        self.form_group.setLayout(self.form)
        scroll = QScrollArea(); scroll.setWidgetResizable(True)
        container = QWidget(); v = QVBoxLayout(); v.addWidget(self.form_group); v.addStretch(); container.setLayout(v)
        scroll.setWidget(container)

        root_layout = QVBoxLayout()
        root_layout.addLayout(top_row)
        root_layout.addWidget(scroll)
        root = QWidget(); root.setLayout(root_layout)
        self.setCentralWidget(root)

        self._signal_editors: Dict[str, SignalEditor] = {}
        self._on_message_changed()

    # ---- UI builders ----------------------------------------------------
    def _clear_form(self):
        while self.form.rowCount():
            self.form.removeRow(0)
        self._signal_editors.clear()

    def _on_message_changed(self):
        self._clear_form()
        mdef = self._current_message()
        if mdef is None:
            return
        frame_id = mdef.frame_id
        self.msg_id_label.setText(f"ID: 0x{frame_id:X} {'(EXT)' if mdef.is_extended_frame else ''}")

        for sig in mdef.signals:
            editor = self._create_signal_editor(sig)
            self._signal_editors[editor.name] = editor
            self.form.addRow(QLabel(f"{sig.name} ({sig.length}b)"), editor.widget)

    def _create_signal_editor(self, sig) -> SignalEditor:
        # 1-bit → radio buttons (0/1)
        if sig.length == 1 and ((sig.scale == 1 and (sig.minimum, sig.maximum) == (0, 1)) or (sig.minimum is None and sig.maximum is None)):
            row = QWidget(); h = QHBoxLayout(); row.setLayout(h)
            zero = QRadioButton("0"); one = QRadioButton("1")
            zero.setChecked(True)
            group = QButtonGroup(row); group.addButton(zero, 0); group.addButton(one, 1)
            h.addWidget(zero); h.addWidget(one); h.addStretch()
            return SignalEditor(sig.name, row, lambda g=group: float(g.checkedId()))

        # General numeric → slider + spinbox
        scale = float(sig.scale or 1.0)
        offset = float(sig.offset or 0.0)
        pmin, pmax = _compute_physical_bounds(sig.length, sig.is_signed, scale, offset, sig.minimum, sig.maximum)
        if pmin == pmax:
            pmax = pmin + scale
        step = abs(scale) if scale != 0 else 1.0
        decimals = min(6, max(0, _decimals_for_step(step)))

        row = QWidget(); h = QHBoxLayout(); row.setLayout(h)
        slider = QSlider(Qt.Horizontal)
        spin = QDoubleSpinBox(); spin.setDecimals(decimals)
        spin.setRange(pmin, pmax)
        spin.setSingleStep(step)

        # Map slider positions to physical range with up to 1000 steps
        total_steps_exact = int(round((pmax - pmin) / step))
        slider_steps = max(1, min(1000, total_steps_exact))
        slider.setRange(0, slider_steps)

        def slider_to_phys(pos: int) -> float:
            if slider_steps == 0:
                return pmin
            ratio = pos / slider_steps
            val = pmin + ratio * (pmax - pmin)
            # snap to resolution
            snapped = round((val - pmin) / step) * step + pmin
            return max(pmin, min(pmax, snapped))

        def phys_to_slider(val: float) -> int:
            val = max(pmin, min(pmax, val))
            if pmax == pmin:
                return 0
            ratio = (val - pmin) / (pmax - pmin)
            return int(round(ratio * slider_steps))

        # sync both directions
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

        # initial
        on_spin_changed(pmin)

        h.addWidget(slider, 2)
        h.addWidget(spin, 1)

        return SignalEditor(sig.name, row, lambda s=spin: float(s.value()))

    # ---- actions ---------------------------------------------------------
    def _current_message(self):
        idx = self.msg_combo.currentIndex()
        if idx < 0:
            return None
        return dbc.messages[idx]

    def _transmit_once(self):
        mdef = self._current_message()
        if mdef is None:
            return
        values: Dict[str, float] = {}
        for name, editor in self._signal_editors.items():
            try:
                values[name] = editor.get_value()
            except Exception as ex:
                QMessageBox.warning(self, "Input Error", f"Failed to read value for {name}: {ex}")
                return
        try:
            payload = mdef.encode(values)
        except Exception as ex:
            QMessageBox.critical(self, "Encode Error", f"Failed to encode message:\n{ex}")
            return
        try:
            BUS.send(mdef.frame_id, mdef.is_extended_frame, bytes(payload))
        except Exception as ex:
            QMessageBox.critical(self, "Transmit Error", f"Hardware send failed:\n{ex}")
            return
        QMessageBox.information(self, "Transmit", "Message sent.")


def main():
    app = QApplication(sys.argv)
    win = MainWindow(); win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()


