# ui/main_window.py
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QLabel, QTableWidget, QTableWidgetItem
)
from PySide6.QtCore import Qt
from threads.receiver_thread import CANReceiverThread

class MainWindow(QMainWindow):
    def __init__(self, can_interface):
        super().__init__()
        self.can_interface = can_interface
        self.setWindowTitle("CAN Diagnostic Tool")
        self.resize(800, 600)

        # --- UI Setup ---
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.layout = QVBoxLayout()
        self.central_widget.setLayout(self.layout)

        self.status_label = QLabel("Connected to CAN Bus.")
        self.layout.addWidget(self.status_label)

        self.table = QTableWidget(1, 3)
        self.table.setHorizontalHeaderLabels(["CAN ID", "DLC", "Data"])
        self.layout.addWidget(self.table)

        # --- Start CAN Receiver Thread ---
        self.receiver_thread = CANReceiverThread(can_interface)
        self.receiver_thread.frame_received.connect(self.update_table)
        self.receiver_thread.start()

    def update_table(self, frame):
        self.table.setItem(0, 0, QTableWidgetItem(hex(frame.CAN_ID)))
        self.table.setItem(0, 1, QTableWidgetItem(str(frame.DLC)))
        self.table.setItem(0, 2, QTableWidgetItem(" ".join([hex(b) for b in frame.data])))

    def closeEvent(self, event):
        # Ensure thread stops cleanly on exit
        self.receiver_thread.stop()
        super().closeEvent(event)
