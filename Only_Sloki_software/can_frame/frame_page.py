# can_frame/frame_page.py
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QTableWidget,
    QTableWidgetItem, QPushButton, QHBoxLayout
)
from PySide6.QtCore import Qt
import time

class CANFramePage(QWidget):
    def __init__(self):
        super().__init__()
        self.layout = QVBoxLayout(self)

        self.status_label = QLabel("Connected to CAN Bus.")
        self.layout.addWidget(self.status_label)

        # --- Table ---
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["CAN ID", "DLC", "Data", "Cycle Time (ms)", "Count"])
        self.layout.addWidget(self.table)

        # --- Control Button Layout ---
        button_layout = QHBoxLayout()
        self.reset_button = QPushButton("Restart Count")
        self.reset_button.clicked.connect(self.reset_counts)
        button_layout.addStretch()
        button_layout.addWidget(self.reset_button)
        self.layout.addLayout(button_layout)

        # --- Data Structures ---
        self.can_id_to_row = {}
        self.last_timestamp = {}
        self.frame_count = {}

    def update_table(self, frame):
        can_id = frame.CAN_ID
        dlc = frame.DLC
        data_str = " ".join([f"{b:02X}" for b in frame.data])
        now = time.time() * 1000  # ms

        if can_id in self.can_id_to_row:
            row = self.can_id_to_row[can_id]
        else:
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.can_id_to_row[can_id] = row
            self.table.setItem(row, 0, QTableWidgetItem(hex(can_id)))

        self.table.setItem(row, 1, QTableWidgetItem(str(dlc)))
        self.table.setItem(row, 2, QTableWidgetItem(data_str))

        cycle_time = 0
        if can_id in self.last_timestamp:
            cycle_time = int(now - self.last_timestamp[can_id])
        self.last_timestamp[can_id] = now
        self.table.setItem(row, 3, QTableWidgetItem(str(cycle_time)))

        # Update count
        self.frame_count[can_id] = self.frame_count.get(can_id, 0) + 1
        self.table.setItem(row, 4, QTableWidgetItem(str(self.frame_count[can_id])))

    def reset_counts(self):
        # Reset the count values
        for can_id, row in self.can_id_to_row.items():
            self.frame_count[can_id] = 0
            self.table.setItem(row, 4, QTableWidgetItem("0"))
