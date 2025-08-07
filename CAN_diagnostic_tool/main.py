# main.py
"""
Home page launcher for the CAN Diagnostic GUI.

Buttons:
• Live Signal Viewer   → opens live_signal_viewer.MainWindow
• Important Parameters → opens imp_params.MainWindow  (currently empty)

Only one child window is shown at a time; when it closes, control
returns to the home page.
"""

from __future__ import annotations
import sys
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget,
    QVBoxLayout, QPushButton
)

from live_signal_viewer import MainWindow as LiveSignalViewer
from imp_params         import MainWindow as ImpParamsWindow


class HomeWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("CAN Diagnostic Tool – Home")
        self.resize(400, 250)

        # ── UI ────────────────────────────────────────────────────────────────
        self.viewer_btn = QPushButton("Live Signal Viewer")
        self.viewer_btn.setFixedHeight(50)
        self.viewer_btn.clicked.connect(self.open_viewer)

        self.params_btn = QPushButton("Important Parameters")
        self.params_btn.setFixedHeight(50)
        self.params_btn.clicked.connect(self.open_params)

        layout = QVBoxLayout()
        layout.addStretch()
        layout.addWidget(self.viewer_btn)
        layout.addWidget(self.params_btn)
        layout.addStretch()

        root = QWidget(); root.setLayout(layout)
        self.setCentralWidget(root)

        # keep references so the windows aren’t garbage-collected
        self._viewer:      LiveSignalViewer | None = None
        self._imp_params:  ImpParamsWindow | None = None

    # ── navigation helpers ───────────────────────────────────────────────────
    def open_viewer(self) -> None:
        if self._viewer is None:
            self._viewer = LiveSignalViewer()
            self._viewer.destroyed.connect(self._on_child_closed)
        self._viewer.show(); self.hide()

    def open_params(self) -> None:
        if self._imp_params is None:
            self._imp_params = ImpParamsWindow()
            self._imp_params.destroyed.connect(self._on_child_closed)
        self._imp_params.show(); self.hide()

    def _on_child_closed(self) -> None:
        """Return to home when any child window closes."""
        # Clean up dangling references
        if self.sender() is self._viewer:
            self._viewer = None
        elif self.sender() is self._imp_params:
            self._imp_params = None
        self.show()


def main() -> None:
    app = QApplication(sys.argv)
    home = HomeWindow(); home.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
