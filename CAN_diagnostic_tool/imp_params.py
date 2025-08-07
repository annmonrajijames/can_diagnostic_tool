# imp_params.py
"""Placeholder window for 'Important Parameters' – currently blank."""

import sys
from PySide6.QtCore    import Qt
from PySide6.QtWidgets import QApplication, QMainWindow, QLabel, QVBoxLayout, QWidget


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Important Parameters")
        self.resize(600, 400)

        # Simple placeholder content
        label = QLabel("Important-Parameters page – content coming soon.")
        label.setAlignment(Qt.AlignCenter)

        layout = QVBoxLayout()
        layout.addWidget(label)

        root = QWidget()
        root.setLayout(layout)
        self.setCentralWidget(root)


# Allows standalone testing:  python imp_params.py
if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())
