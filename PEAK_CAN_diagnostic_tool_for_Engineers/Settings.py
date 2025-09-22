# Settings.py
from __future__ import annotations
import json
import sys
from pathlib import Path

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QLabel, QLineEdit, QPushButton,
    QFileDialog, QHBoxLayout, QVBoxLayout, QMessageBox
)

def _resolve_app_dir() -> Path:
    """Return folder for app-local config.

    - Frozen (PyInstaller one-dir/one-file): use parent of sys.executable
    - Dev: use folder of this file
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent

# Local config path (next to the EXE when frozen)
APP_DIR = _resolve_app_dir()
CONFIG_PATH = APP_DIR / "settings.json"

# No predefined DBC defaults here; selection and fallback are handled in dbc_decode_input.py


def load_settings() -> dict:
    if CONFIG_PATH.exists():
        try:
            return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"dbc_path": ""}


def save_settings(d: dict) -> None:
    try:
        CONFIG_PATH.write_text(json.dumps(d, indent=2), encoding="utf-8")
    except Exception as ex:
        QMessageBox.critical(None, "Save Error", f"Failed to save settings:\n{ex}")


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Settings")
        self.resize(600, 150)

        cfg = load_settings()
        self.path_edit = QLineEdit(cfg.get("dbc_path", ""))
        self.path_edit.setPlaceholderText("Select a .dbc file path…")

        browse_btn = QPushButton("Browse…")
        browse_btn.clicked.connect(self.on_browse)

        save_btn = QPushButton("Save")
        save_btn.clicked.connect(self.on_save)

        back_btn = QPushButton("Back")
        back_btn.clicked.connect(self.close)

        row = QHBoxLayout()
        row.addWidget(QLabel("DBC file:"))
        row.addWidget(self.path_edit, 1)
        row.addWidget(browse_btn)

        btns = QHBoxLayout()
        btns.addStretch()
        btns.addWidget(save_btn)
        btns.addWidget(back_btn)

        root_layout = QVBoxLayout()
        root_layout.addLayout(row)
        root_layout.addStretch()
        root_layout.addLayout(btns)
        root = QWidget()
        root.setLayout(root_layout)
        self.setCentralWidget(root)

    def on_browse(self):
        txt = self.path_edit.text().strip()
        start_dir = str(Path(txt).parent) if txt else str(Path.home())
        path, _ = QFileDialog.getOpenFileName(self, "Select DBC file", start_dir, "DBC files (*.dbc);;All files (*.*)")
        if path:
            self.path_edit.setText(path)

    def on_save(self):
        p = Path(self.path_edit.text()).expanduser()
        if not p.exists() or p.suffix.lower() != ".dbc":
            QMessageBox.warning(self, "Invalid Path", "Please select a valid .dbc file.")
            return
        save_settings({"dbc_path": str(p)})
        QMessageBox.information(self, "Saved", "Settings saved. Restart views to reload DBC.")
