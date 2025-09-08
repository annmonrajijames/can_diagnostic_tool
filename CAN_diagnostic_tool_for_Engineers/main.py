# main.py  –  lazy-import version
"""
Home page launcher for the CAN Diagnostic GUI.

Buttons:
• Live Signal Viewer   → opens live_signal_viewer.MainWindow
• Live Signal Transmit → opens live_signal_transmit.MainWindow
• Settings             → opens Settings.MainWindow

Only one child window is visible at a time; when it closes, control
returns to the home page.
"""

from __future__ import annotations
import sys
import importlib
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget,
    QVBoxLayout, QPushButton
)
from shiboken6 import isValid


class HomeWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("CAN Diagnostic Tool – Home")
        self.resize(400, 280)

        # ── UI ───────────────────────────────────────────────────────────────
        self.viewer_btn = QPushButton("Live Signal Viewer", clicked=self.open_viewer)
        self.viewer_btn.setFixedHeight(50)

        self.tx_btn = QPushButton("Live Signal Transmit", clicked=self.open_transmit)
        self.tx_btn.setFixedHeight(50)

        self.settings_btn = QPushButton("Settings", clicked=self.open_settings)
        self.settings_btn.setFixedHeight(40)

        layout = QVBoxLayout()
        layout.addStretch()
        layout.addWidget(self.viewer_btn)
        layout.addWidget(self.tx_btn)
        layout.addWidget(self.settings_btn)
        layout.addStretch()

        root = QWidget()
        root.setLayout(layout)
        self.setCentralWidget(root)

        # keep references so the windows aren’t garbage-collected
        self._viewer    = None    # type: ignore
        self._imp_param = None    # type: ignore
        self._tx_window = None    # type: ignore
        self._settings  = None    # type: ignore

    # ── helpers ─────────────────────────────────────────────────────────────
    def _load_window(self, module_name: str, attr: str):
        """Dynamically import *module_name* and return the attr (class) asked for."""
        module = importlib.import_module(module_name)
        return getattr(module, attr)

    def open_viewer(self):
        if self._viewer is None or not isValid(self._viewer):
            ViewerClass = self._load_window("live_signal_viewer", "MainWindow")
            self._viewer = ViewerClass()
            self._viewer.setAttribute(Qt.WA_DeleteOnClose, True)
            self._viewer.destroyed.connect(self._child_closed)
        self._viewer.show(); self.hide()

    def open_transmit(self):
        if self._tx_window is None or not isValid(self._tx_window):
            TxClass = self._load_window("live_signal_transmit", "MainWindow")
            self._tx_window = TxClass()
            self._tx_window.setAttribute(Qt.WA_DeleteOnClose, True)
            self._tx_window.destroyed.connect(self._child_closed)
        self._tx_window.show(); self.hide()

    def open_settings(self):
        if self._settings is None or not isValid(self._settings):
            SettingsClass = self._load_window("Settings", "MainWindow")
            self._settings = SettingsClass()
            self._settings.setAttribute(Qt.WA_DeleteOnClose, True)
            self._settings.destroyed.connect(self._child_closed)
        self._settings.show(); self.hide()

    def _child_closed(self):
        """Called when either child window is destroyed."""
        s = self.sender()
        if s is self._viewer:
            self._viewer = None
        elif s is self._tx_window:
            self._tx_window = None
        elif s is self._settings:
            self._settings = None
        self.show()


def main() -> None:
    app = QApplication(sys.argv)
    home = HomeWindow(); home.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
