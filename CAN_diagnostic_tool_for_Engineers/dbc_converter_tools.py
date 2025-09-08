"""
Minimal DBC Converter and Tools window.
This page is launched from main.HomeWindow via lazy import.
"""
from __future__ import annotations
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QLabel, QPushButton
)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("DBC Converter and Tools")
        self.resize(600, 400)

        # Content
        title = QLabel("DBC Converter and Tools")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size: 20px; font-weight: bold;")

        back_btn = QPushButton("Back to Home")
        back_btn.clicked.connect(self.close)

        layout = QVBoxLayout()
        layout.addStretch()
        layout.addWidget(title)
        layout.addStretch()
        layout.addWidget(back_btn)

        root = QWidget()
        root.setLayout(layout)
        self.setCentralWidget(root)
