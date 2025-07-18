# can_frame/frame_page.py
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QTableWidget, QTableWidgetItem
from PySide6.QtCore import Qt

class CANFramePage(QWidget):
    def __init__(self):
        super().__init__()
        self.layout = QVBoxLayout(self)

        self.status_label = QLabel("Connected to CAN Bus.")
        self.layout.addWidget(self.status_label)

        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["CAN ID", "DLC", "Data"])
        self.layout.addWidget(self.table)

        self.can_id_to_row = {}  # Track CAN ID → row index

    def update_table(self, frame):
        can_id = frame.CAN_ID

        # Format data as hex bytes
        data_str = " ".join([f"{byte:02X}" for byte in frame.data])

        if can_id in self.can_id_to_row:
            # Update existing row
            row = self.can_id_to_row[can_id]
        else:
            # Insert new row
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.can_id_to_row[can_id] = row
            self.table.setItem(row, 0, QTableWidgetItem(hex(can_id)))  # Set CAN ID once

        # Always update DLC and Data
        self.table.setItem(row, 1, QTableWidgetItem(str(frame.DLC)))
        self.table.setItem(row, 2, QTableWidgetItem(data_str))
