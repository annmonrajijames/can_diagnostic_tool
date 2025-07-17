# ui/main_window.py
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QLabel, QPushButton, QTableWidget, QTableWidgetItem
)
from PySide6.QtCore import Qt

class MainWindow(QMainWindow):
    def __init__(self, can_interface):
        super().__init__()
        self.can_interface = can_interface
        self.setWindowTitle("CAN Diagnostic Tool")
        self.resize(800, 600)

        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)

        self.layout = QVBoxLayout()
        self.central_widget.setLayout(self.layout)

        self.status_label = QLabel("Connected to CAN Bus.")
        self.layout.addWidget(self.status_label)

        self.refresh_button = QPushButton("Read CAN Frame")
        self.refresh_button.clicked.connect(self.read_can_frame)
        self.layout.addWidget(self.refresh_button)

        self.table = QTableWidget(1, 3)
        self.table.setHorizontalHeaderLabels(["CAN ID", "DLC", "Data"])
        self.layout.addWidget(self.table)

    def read_can_frame(self):
        frame = self.can_interface.receive()
        if frame:
            self.table.setItem(0, 0, QTableWidgetItem(hex(frame.CAN_ID)))
            self.table.setItem(0, 1, QTableWidgetItem(str(frame.DLC)))
            self.table.setItem(0, 2, QTableWidgetItem(" ".join([hex(b) for b in frame.data])))
        else:
            self.status_label.setText("No frame received.")
