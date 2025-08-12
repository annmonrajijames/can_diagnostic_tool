# hardware/can_interface.py

import json
from pathlib import Path
from hardware.driver_loader import J2534Driver, CANFrame

CONFIG_PATH = Path("config.json")


class CANInterface:
    def __init__(self):
        self.driver = None
        self.dll_path = None
        self.default_baudrate = 500000
        self._load_driver_from_config()

    def _load_driver_from_config(self):
        if not CONFIG_PATH.exists():
            raise FileNotFoundError("⚠️ config.json not found. Please configure hardware first.")

        with open(CONFIG_PATH, "r") as f:
            config = json.load(f)

        self.dll_path = config.get("dll_path", "")
        self.default_baudrate = config.get("baudrate", 500000)

        if not self.dll_path or not Path(self.dll_path).is_file():
            raise FileNotFoundError(f"⚠️ DLL path invalid or not found: {self.dll_path}")

        self.driver = J2534Driver(self.dll_path)

    def connect(self, baudrate=None):
        if not self.driver:
            raise Exception("⚠️ Driver not initialized.")

        baudrate = baudrate or self.default_baudrate

        self.driver.open()
        self.driver.connect(baudrate=baudrate)

    def disconnect(self):
        if self.driver:
            self.driver.disconnect()

    def send(self, can_id, data):
        if not self.driver:
            raise Exception("⚠️ Driver not connected.")

        frame = CANFrame()
        frame.CAN_ID = can_id
        frame.DLC = len(data)
        frame.data = data
        return self.driver.send(frame)

    def receive(self, timeout=10):
        if self.driver:
            return self.driver.read(timeout)
        return None
