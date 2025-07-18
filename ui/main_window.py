# ui/main_window.py
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QStackedWidget, QLabel
)
from threads.receiver_thread import CANReceiverThread
from can_frame.frame_page import CANFramePage  # NEW IMPORT

class MainWindow(QMainWindow):
    def __init__(self, can_interface):
        super().__init__()
        self.setWindowTitle("Universal CAN Diagnostic Tool")
        self.resize(900, 600)
        self.can_interface = can_interface

        # === Layout ===
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QVBoxLayout(self.central_widget)

        nav_layout = QHBoxLayout()
        self.home_button = QPushButton("Home")
        self.can_frame_button = QPushButton("CAN Frame")
        nav_layout.addWidget(self.home_button)
        nav_layout.addWidget(self.can_frame_button)
        self.main_layout.addLayout(nav_layout)

        self.pages = QStackedWidget()
        self.main_layout.addWidget(self.pages)

        # === Page 0: Home ===
        self.home_page = QWidget()
        home_layout = QVBoxLayout()
        home_layout.addWidget(QLabel("Welcome to the CAN Diagnostic Tool!"))
        self.home_page.setLayout(home_layout)
        self.pages.addWidget(self.home_page)

        # === Page 1: CAN Frame ===
        self.can_frame_page = CANFramePage()
        self.pages.addWidget(self.can_frame_page)

        self.home_button.clicked.connect(lambda: self.pages.setCurrentWidget(self.home_page))
        self.can_frame_button.clicked.connect(lambda: self.pages.setCurrentWidget(self.can_frame_page))

        # === Receiver Thread ===
        self.receiver_thread = CANReceiverThread(self.can_interface)
        self.receiver_thread.frame_received.connect(self.can_frame_page.update_table)
        self.receiver_thread.start()

    def closeEvent(self, event):
        self.receiver_thread.stop()
        super().closeEvent(event)
