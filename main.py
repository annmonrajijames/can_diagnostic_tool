# main.py
# ------------------------------------------------------------
# Entry point for the CAN Diagnostic Tool.
# Initializes PySide6 application and handles startup sequence.
# ------------------------------------------------------------

import sys
import logging
from PySide6.QtWidgets import QApplication, QMessageBox
from hardware.can_interface import CANInterface
from ui.main_window import MainWindow

def main():
    logging.basicConfig(level=logging.INFO)
    app = QApplication(sys.argv)

    try:
        # Initialize CAN interface
        can_interface = CANInterface(baudrate=500000)
        can_interface.connect()
    except Exception as e:
        QMessageBox.critical(None, "CAN Device Error", f"Failed to connect to CAN device:\n{e}")
        sys.exit(1)

    # Start main GUI window
    window = MainWindow(can_interface)
    window.show()

    # Exit on close
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
