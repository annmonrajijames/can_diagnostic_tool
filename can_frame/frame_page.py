# can_frame/frame_page.py
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QTableWidget, QTableWidgetItem

class CANFramePage(QWidget):
    def __init__(self):
        super().__init__()
        self.layout = QVBoxLayout(self)

        self.status_label = QLabel("Connected to CAN Bus.")
        self.layout.addWidget(self.status_label)

        self.table = QTableWidget(1, 3)
        self.table.setHorizontalHeaderLabels(["CAN ID", "DLC", "Data"])
        self.layout.addWidget(self.table)

    def update_table(self, frame):
        self.table.setItem(0, 0, QTableWidgetItem(hex(frame.CAN_ID)))
        self.table.setItem(0, 1, QTableWidgetItem(str(frame.DLC)))
        self.table.setItem(0, 2, QTableWidgetItem(" ".join([hex(b) for b in frame.data])))
