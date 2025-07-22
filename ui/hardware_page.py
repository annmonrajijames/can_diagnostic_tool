# ui/hardware_page.py

import json
from pathlib import Path
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QPushButton,
    QFileDialog, QLineEdit, QMessageBox, QComboBox
)

CONFIG_PATH = Path("config.json")


class HardwarePage(QWidget):
    def __init__(self):
        super().__init__()

        self.setLayout(QVBoxLayout())
        self.layout().addWidget(QLabel("<b>Hardware Interface Configuration</b>"))

        # DLL Path Input
        self.dll_path_input = QLineEdit()
        self.dll_path_input.setPlaceholderText("Select J2534 DLL path...")
        self.layout().addWidget(QLabel("DLL Path:"))
        self.layout().addWidget(self.dll_path_input)

        # Browse DLL Button
        self.browse_button = QPushButton("Browse DLL")
        self.browse_button.clicked.connect(self.browse_dll)
        self.layout().addWidget(self.browse_button)

        # Baudrate Selection
        self.baudrate_input = QComboBox()
        self.baudrate_input.addItems(["125000", "250000", "500000", "1000000"])
        self.baudrate_input.setCurrentText("500000")
        self._current_baudrate = self.baudrate_input.currentText()
        self.baudrate_input.currentTextChanged.connect(self.on_baudrate_change)
        self.layout().addWidget(QLabel("Select Baudrate:"))
        self.layout().addWidget(self.baudrate_input)

        # Save Config Button
        self.save_button = QPushButton("Save Configuration")
        self.save_button.clicked.connect(self.save_path)
        self.layout().addWidget(self.save_button)

        # Status Label
        self.status_label = QLabel()
        self.layout().addWidget(self.status_label)

        # Load previous config if exists
        self.load_config()

    def browse_dll(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Select J2534 DLL", "", "DLL Files (*.dll)")
        if file_path:
            self.dll_path_input.setText(file_path)

    def save_path(self):
        path = self.dll_path_input.text().strip()
        baudrate = int(self.baudrate_input.currentText())

        if not Path(path).is_file():
            QMessageBox.warning(self, "Invalid Path", "Selected DLL path is not valid.")
            return

        with open(CONFIG_PATH, "w") as f:
            json.dump({
                "dll_path": path,
                "baudrate": baudrate
            }, f)

        self.status_label.setText("✅ Configuration saved successfully.")

    def load_config(self):
        if CONFIG_PATH.exists():
            try:
                with open(CONFIG_PATH, "r") as f:
                    config = json.load(f)
                    dll_path = config.get("dll_path", "")
                    baudrate = str(config.get("baudrate", "500000"))

                    self.dll_path_input.setText(dll_path)

                    if baudrate in [self.baudrate_input.itemText(i) for i in range(self.baudrate_input.count())]:
                        self.baudrate_input.setCurrentText(baudrate)

            except Exception as e:
                self.status_label.setText(f"⚠️ Failed to load config: {e}")

    def on_baudrate_change(self, new_baudrate):
        print(
            f"[DEBUG] Baudrate changed from {self._current_baudrate} to {new_baudrate}"
        )
        self._current_baudrate = new_baudrate
