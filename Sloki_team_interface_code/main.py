# main.py
# ------------------------------------------------------------
# Entry point for the CAN Diagnostic Tool.
# Initializes PySide6 application and handles startup sequence.
# ------------------------------------------------------------

import sys
from PySide6.QtWidgets import QApplication, QMessageBox
from hardware.can_interface import CANInterface
from ui.main_window import MainWindow


def main():
    app = QApplication(sys.argv)

    try:
        # Try to load and initialize the CAN interface
        can_interface = CANInterface()

        try:
            # Try connecting (device should be plugged in)
            can_interface.connect()
        except Exception as conn_error:
            # Device not connected or runtime issue — treat as fatal
            QMessageBox.critical(None, "CAN Device Error", f"❌ Failed to connect to CAN device:\n{conn_error}")
            sys.exit(1)

    except FileNotFoundError as driver_error:
        # DLL not selected or not found — show GUI and go to hardware page
        can_interface = None
        window = MainWindow(can_interface)
        window.show()
        window.pages.setCurrentWidget(window.hardware_page)
        QMessageBox.warning(window, "Hardware Not Configured",
                            "⚠️ Driver not selected or invalid. Please configure hardware first.")
        sys.exit(app.exec())

    # All good — start GUI normally
    window = MainWindow(can_interface)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
