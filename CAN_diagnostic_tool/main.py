# main.py
"""
Home page launcher for the CAN Diagnostic GUI.

• Shows a single button:  "Live Signal Viewer"
• Clicking the button opens the live-signal viewer window defined in
  live_signal_viewer.py and hides this home window.
• When the viewer window is closed, control returns to the home page.
"""

from __future__ import annotations

import sys
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget,
    QVBoxLayout, QPushButton
)

# ── import just the viewer class, *not* its standalone main() helper ────────────
from live_signal_viewer import MainWindow as LiveSignalViewer


class HomeWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("CAN Diagnostic Tool – Home")
        self.resize(400, 200)

        # --- UI ----------------------------------------------------------------
        self.viewer_btn = QPushButton("Live Signal Viewer")
        self.viewer_btn.setFixedHeight(50)
        self.viewer_btn.clicked.connect(self.open_viewer)

        layout = QVBoxLayout()
        layout.addStretch()
        layout.addWidget(self.viewer_btn)
        layout.addStretch()

        root = QWidget()
        root.setLayout(layout)
        self.setCentralWidget(root)

        # keep a reference so it isn’t garbage-collected
        self._viewer: LiveSignalViewer | None = None

    # --------------------------------------------------------------------------
    def open_viewer(self) -> None:
        """Instantiate and show the live-signal viewer, hiding the home page."""
        if self._viewer is None:
            self._viewer = LiveSignalViewer()
            # When viewer closes, redisplay home and clean up reference
            self._viewer.destroyed.connect(self._on_viewer_closed)
        self._viewer.show()
        self.hide()

    def _on_viewer_closed(self) -> None:
        """Called automatically when the viewer window is destroyed."""
        self._viewer = None
        self.show()


def main() -> None:
    app = QApplication(sys.argv)
    home = HomeWindow()
    home.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
