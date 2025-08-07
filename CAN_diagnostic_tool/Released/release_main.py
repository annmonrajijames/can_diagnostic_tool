# release_main.py
"""
Production entry-point: launches the Important-Parameters UI directly.

• No intermediate home window.
• Uses lazy import so imp_params (and its CAN bus) are loaded only once.
"""

from __future__ import annotations
import sys
import importlib
from PySide6.QtWidgets import QApplication


def main() -> None:
    app = QApplication(sys.argv)

    # Lazy-import the window class
    ImpParamsWindow = getattr(importlib.import_module("imp_params"), "MainWindow")

    win = ImpParamsWindow()
    win.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
