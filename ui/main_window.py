# ui/main_window.py

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QStackedWidget, QLabel
)
from threads.receiver_thread import CANReceiverThread
from can_frame.frame_page import CANFramePage
from ui.hardware_page import HardwarePage
from ui.dbc_page import DBCDecodePage


class MainWindow(QMainWindow):
    def __init__(self, can_interface):
        super().__init__()
        self.setWindowTitle("Universal CAN Diagnostic Tool")
        self.resize(900, 600)
        self.can_interface = can_interface

        # === Central Widget ===
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QVBoxLayout(self.central_widget)

        # === Navigation Buttons ===
        nav_layout = QHBoxLayout()
        self.home_button = QPushButton("Home")
        self.can_frame_button = QPushButton("CAN Frame")
        self.decoded_button = QPushButton("Decoded Parameters")
        self.hardware_button = QPushButton("Hardware Interface")

        nav_layout.addWidget(self.home_button)
        nav_layout.addWidget(self.can_frame_button)
        nav_layout.addWidget(self.decoded_button)
        nav_layout.addWidget(self.hardware_button)
        self.main_layout.addLayout(nav_layout)

        # === Pages Stack ===
        self.pages = QStackedWidget()
        self.main_layout.addWidget(self.pages)

        # === Page 0: Home ===
        self.home_page = QWidget()
        home_layout = QVBoxLayout()
        home_layout.addWidget(QLabel("Welcome to the CAN Diagnostic Tool!"))
        self.home_page.setLayout(home_layout)
        self.pages.addWidget(self.home_page)

        # === Page 1: CAN Frame Page ===
        self.can_frame_page = CANFramePage()
        self.pages.addWidget(self.can_frame_page)

        # === Page 2: Decoded DBC Page ===
        self.dbc_page = DBCDecodePage()
        self.pages.addWidget(self.dbc_page)

        # === Page 3: Hardware Interface Page ===
        self.hardware_page = HardwarePage()
        self.pages.addWidget(self.hardware_page)

        # === Navigation Connections ===
        self.home_button.clicked.connect(self.show_home)
        self.can_frame_button.clicked.connect(self.show_can_frame)
        self.decoded_button.clicked.connect(self.show_decoded)
        self.hardware_button.clicked.connect(self.show_hardware)

        # === CAN Receiver Thread ===
        self.receiver_thread = CANReceiverThread(self.can_interface)
        self.receiver_thread.frame_received.connect(self.can_frame_page.update_table)
        self.receiver_thread.start()

    # ---- Page Navigation Helpers ----
    def _switch_connection(self, slot):
        try:
            self.receiver_thread.frame_received.disconnect()
        except Exception:
            pass
        if slot:
            self.receiver_thread.frame_received.connect(slot)

    def show_home(self):
        self._switch_connection(None)
        self.pages.setCurrentWidget(self.home_page)

    def show_can_frame(self):
        self._switch_connection(self.can_frame_page.update_table)
        self.pages.setCurrentWidget(self.can_frame_page)

    def show_decoded(self):
        self._switch_connection(self.dbc_page.update_signals)
        self.pages.setCurrentWidget(self.dbc_page)

    def show_hardware(self):
        self._switch_connection(None)
        self.pages.setCurrentWidget(self.hardware_page)

    def closeEvent(self, event):
        self.receiver_thread.stop()
        super().closeEvent(event)
