"""
Minimal DBC Converter and Tools window.
This page is launched from main.HomeWindow via lazy import.
"""
from __future__ import annotations
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QLabel, QPushButton, QMessageBox,
    QDialog, QLineEdit, QHBoxLayout, QFileDialog
)
from pathlib import Path


class ConvertDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Convert: csselectronicsDBC → cantoolsDBC")

        # Try to prefill defaults from converter module
        default_in = ""
        default_out = ""
        try:
            try:
                import csselectronicsDBC_to_cantoolsDBC as conv
            except ImportError:
                import importlib.util
                module_path = Path(__file__).resolve().parent / "csselectronicsDBC_to_cantoolsDBC.py"
                spec = importlib.util.spec_from_file_location("csselectronicsDBC_to_cantoolsDBC", module_path)
                if spec and spec.loader:
                    conv = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(conv)  # type: ignore[attr-defined]
                else:
                    conv = None  # type: ignore[assignment]
            if conv:
                default_in = str(conv.DEFAULT_IN_DBC)
                default_out = str(conv.DEFAULT_OUT_DBC)
        except Exception:
            pass

        # Input row
        self.in_edit = QLineEdit(default_in)
        in_browse = QPushButton("Browse…")
        in_browse.clicked.connect(self._browse_in)
        in_row = QHBoxLayout()
        in_row.addWidget(self.in_edit)
        in_row.addWidget(in_browse)

        # Output row
        self.out_edit = QLineEdit(default_out)
        out_browse = QPushButton("Browse…")
        out_browse.clicked.connect(self._browse_out)
        out_row = QHBoxLayout()
        out_row.addWidget(self.out_edit)
        out_row.addWidget(out_browse)

        # Action buttons
        convert_btn = QPushButton("CONVERT")
        convert_btn.clicked.connect(self._convert)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        action_row = QHBoxLayout()
        action_row.addStretch()
        action_row.addWidget(convert_btn)
        action_row.addWidget(cancel_btn)

        # Layout
        layout = QVBoxLayout()
        layout.addWidget(QLabel("Input DBC:"))
        layout.addLayout(in_row)
        layout.addWidget(QLabel("Output DBC:"))
        layout.addLayout(out_row)
        layout.addLayout(action_row)
        self.setLayout(layout)

    def _browse_in(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Select Input DBC", str(Path.cwd()), "DBC Files (*.dbc);;All Files (*.*)")
        if path:
            self.in_edit.setText(path)

    def _browse_out(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Select Output DBC", str(Path.cwd()), "DBC Files (*.dbc);;All Files (*.*)")
        if path:
            # Ensure .dbc extension
            p = Path(path)
            if p.suffix.lower() != ".dbc":
                p = p.with_suffix(".dbc")
            self.out_edit.setText(str(p))

    def _convert(self) -> None:
        in_path_text = self.in_edit.text().strip()
        out_path_text = self.out_edit.text().strip()
        if not in_path_text or not out_path_text:
            QMessageBox.warning(self, "Missing Paths", "Please choose both input and output DBC paths.")
            return
        in_path = Path(in_path_text)
        out_path = Path(out_path_text)
        try:
            try:
                import csselectronicsDBC_to_cantoolsDBC as conv
            except ImportError:
                import importlib.util
                module_path = Path(__file__).resolve().parent / "csselectronicsDBC_to_cantoolsDBC.py"
                spec = importlib.util.spec_from_file_location("csselectronicsDBC_to_cantoolsDBC", module_path)
                if spec is None or spec.loader is None:
                    raise
                conv = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(conv)  # type: ignore[attr-defined]

            conv.run_pipeline(in_path, out_path)
            QMessageBox.information(self, "Conversion Complete", f"Wrote cantools-compatible DBC to:\n{out_path}")
            self.accept()
        except FileNotFoundError as e:
            QMessageBox.critical(self, "Input DBC Not Found", f"Could not find input DBC file:\n{e}")
        except Exception as e:
            QMessageBox.critical(self, "Conversion Failed", f"An error occurred while converting the DBC:\n{e}")


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
        """Open a dialog for selecting input/output DBC and perform conversion."""
        dlg = ConvertDialog(self)
        dlg.exec()
