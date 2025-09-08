"""
Minimal DBC Converter and Tools window.
This page is launched from main.HomeWindow via lazy import.
"""
from __future__ import annotations
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QLabel, QPushButton, QMessageBox
)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("DBC Converter and Tools")
        self.resize(600, 400)

        # Header
        title = QLabel("DBC Converter and Tools")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size: 20px; font-weight: bold;")

        # Buttons
        back_btn = QPushButton("Back to Home")
        back_btn.clicked.connect(self.close)

        convert_btn = QPushButton("csselectronicsDBC TO PythonCantoolsDBC")
        convert_btn.clicked.connect(self.run_csselectronics_to_cantools)

        # Layout
        layout = QVBoxLayout()
        layout.addStretch()
        layout.addWidget(title)
        layout.addStretch()
        layout.addWidget(convert_btn)
        layout.addWidget(back_btn)

        root = QWidget()
        root.setLayout(layout)
        self.setCentralWidget(root)

    def run_csselectronics_to_cantools(self) -> None:
        """Run the in-repo converter with its default input/output paths."""
        try:
            # Lazy import; fall back to path-based import if needed
            try:
                import csselectronicsDBC_to_cantoolsDBC as conv
            except ImportError:
                import importlib.util
                from pathlib import Path
                module_path = Path(__file__).resolve().parent / "csselectronicsDBC_to_cantoolsDBC.py"
                spec = importlib.util.spec_from_file_location("csselectronicsDBC_to_cantoolsDBC", module_path)
                if spec is None or spec.loader is None:
                    raise
                conv = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(conv)

            in_path = conv.DEFAULT_IN_DBC
            out_path = conv.DEFAULT_OUT_DBC
            conv.run_pipeline(in_path, out_path)

            QMessageBox.information(
                self,
                "Conversion Complete",
                f"Wrote cantools-compatible DBC to:\n{out_path}"
            )
        except FileNotFoundError as e:
            QMessageBox.critical(
                self,
                "Input DBC Not Found",
                f"Could not find input DBC file:\n{e}"
            )
        except Exception as e:
            QMessageBox.critical(
                self,
                "Conversion Failed",
                f"An error occurred while converting the DBC:\n{e}"
            )
