# main.py  –  lazy-import version
"""
Home page launcher for the CAN Diagnostic GUI.

Buttons:
• Live Signal Viewer   → opens live_signal_viewer.MainWindow
• Important Parameters → opens imp_params.MainWindow

Only one child window is visible at a time; when it closes, control
returns to the home page.
"""

from __future__ import annotations
import sys
import importlib
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget,
    QVBoxLayout, QPushButton
)


class HomeWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("CAN Diagnostic Tool – Home")
        self.resize(400, 250)

        # ── UI ───────────────────────────────────────────────────────────────
        self.viewer_btn = QPushButton("Live Signal Viewer", clicked=self.open_viewer)
        self.viewer_btn.setFixedHeight(50)

        self.params_btn = QPushButton("Important Parameters", clicked=self.open_params)
        self.params_btn.setFixedHeight(50)

        self.tx_btn = QPushButton("Live Signal Transmit", clicked=self.open_transmit)
        self.tx_btn.setFixedHeight(50)

        layout = QVBoxLayout()
        layout.addStretch()
        layout.addWidget(self.viewer_btn)
        layout.addWidget(self.params_btn)
        layout.addWidget(self.tx_btn)
        layout.addStretch()

        root = QWidget(); root.setLayout(layout)
        self.setCentralWidget(root)

        # keep references so the windows aren’t garbage-collected
        self._viewer    = None    # type: ignore
        self._imp_param = None    # type: ignore
        self._tx_window = None    # type: ignore

    # ── helpers ─────────────────────────────────────────────────────────────
    def _load_window(self, module_name: str, attr: str):
        """Dynamically import *module_name* and return the attr (class) asked for."""
        module = importlib.import_module(module_name)
        return getattr(module, attr)

    def open_viewer(self):
        if self._viewer is None:
            ViewerClass = self._load_window("live_signal_viewer", "MainWindow")
            self._viewer = ViewerClass()
            self._viewer.destroyed.connect(self._child_closed)
        self._viewer.show(); self.hide()

    def open_params(self):
        if self._imp_param is None:
            ParamClass = self._load_window("imp_params", "MainWindow")
            self._imp_param = ParamClass()
            self._imp_param.destroyed.connect(self._child_closed)
        self._imp_param.show(); self.hide()

    def open_transmit(self):
        if self._tx_window is None:
            TxClass = self._load_window("live_signal_transmit", "MainWindow")
            self._tx_window = TxClass()
            self._tx_window.destroyed.connect(self._child_closed)
        self._tx_window.show(); self.hide()

    def _child_closed(self):
        """Called when either child window is destroyed."""
        if self.sender() is self._viewer:
            self._viewer = None
        elif self.sender() is self._imp_param:
            self._imp_param = None
        elif self.sender() is self._tx_window:
            self._tx_window = None
        self.show()


def main() -> None:
    app = QApplication(sys.argv)
    home = HomeWindow(); home.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
