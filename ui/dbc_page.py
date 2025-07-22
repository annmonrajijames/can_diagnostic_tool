# ui/dbc_page.py

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QPushButton,
    QFileDialog, QTableWidget, QTableWidgetItem
)
from PySide6.QtCore import Qt
import cantools


class DBCDecodePage(QWidget):
    """Page for real time decoded DBC parameters."""

    def __init__(self):
        super().__init__()
        self.db = None
        self.signal_to_row = {}

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("<b>Real Time Decoded DBC Parameters</b>"))

        self.load_button = QPushButton("Load DBC File")
        self.load_button.clicked.connect(self.load_dbc)
        layout.addWidget(self.load_button)

        self.status_label = QLabel("No DBC loaded")
        layout.addWidget(self.status_label)

        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["Message", "Signal", "Value"])
        layout.addWidget(self.table)

    def load_dbc(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select DBC file", "", "DBC Files (*.dbc);;All Files (*)"
        )
        if file_path:
            try:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    text = f.read()

                import re

                # Strip completely malformed placeholder blocks.
                junk = re.compile(
                    r"^BO_\s+\d+\s*:\s*0\s+\S+(?:\n\s+SG_.*)*",
                    re.MULTILINE,
                )
                text = junk.sub("", text)

                text = text.replace(">>!<<", "")

                # Normalize message names and temporarily flag extended IDs so
                # cantools can parse them properly.
                pattern = re.compile(
                    r"^(BO_\s+)(\d+)\s+([^:]+):\s*(\d+)\s+(\S+)",
                    re.MULTILINE,
                )

                added = {}

                def fix(match: re.Match) -> str:
                    prefix, fid, name, dlc, node = match.groups()
                    fid_int = int(fid)
                    if fid_int > 0x7FF and fid_int < 0x80000000:
                        added[fid_int | 0x80000000] = fid_int
                        fid = str(fid_int | 0x80000000)
                    name = name.strip().replace(" ", "_")
                    return f"{prefix}{fid} {name}: {dlc} {node}"

                text = pattern.sub(fix, text)

                self.db = cantools.database.load_string(text, strict=False)

                # Restore original frame IDs for messages we flagged.
                for message in self.db.messages:
                    if message.frame_id in added:
                        message.frame_id = added[message.frame_id]
                        message.is_extended_frame = True

                self.status_label.setText(f"Loaded: {file_path}")
                self.signal_to_row.clear()
                self.table.setRowCount(0)
            except Exception as e:
                self.status_label.setText(f"Failed to load DBC: {e}")

    def update_signals(self, frame):
        if not self.db:
            return
        try:
            message = self.db.get_message_by_frame_id(frame.CAN_ID)
            if not message:
                return
            decoded = message.decode(bytes(frame.data))
            for sig_name, value in decoded.items():
                key = (message.name, sig_name)
                if key not in self.signal_to_row:
                    row = self.table.rowCount()
                    self.table.insertRow(row)
                    self.signal_to_row[key] = row
                    self.table.setItem(row, 0, QTableWidgetItem(message.name))
                    self.table.setItem(row, 1, QTableWidgetItem(sig_name))
                row = self.signal_to_row[key]
                self.table.setItem(row, 2, QTableWidgetItem(str(value)))
        except Exception:
            # Ignore decoding errors for malformed frames
            pass
