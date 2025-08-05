"""PySide6 GUI for displaying CAN frame statistics."""

from __future__ import annotations

import ctypes
import sys
import time
from dataclasses import dataclass
from enum import Enum
from threading import Lock
from typing import Dict

from PySide6.QtCore import QTimer, Qt, QThread
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QHeaderView,
    QMainWindow,
    QTableWidget,
    QTableWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


@dataclass
class _StatEntry:
    count: int = 0
    last_time: float | None = None
    cycle_time_ms: float = 0.0


class CANStats:
    """Track count and cycle time for CAN identifiers."""

    def __init__(self) -> None:
        self._stats: Dict[int, _StatEntry] = {}
        self._lock = Lock()

    def update(self, can_id: int) -> None:
        now = time.time()
        with self._lock:
            entry = self._stats.get(can_id)
            if entry is None:
                entry = _StatEntry(count=1, last_time=now, cycle_time_ms=0.0)
                self._stats[can_id] = entry
            else:
                if entry.last_time is not None:
                    entry.cycle_time_ms = (now - entry.last_time) * 1000.0
                entry.last_time = now
                entry.count += 1

    def snapshot(self) -> Dict[int, Dict[str, float | int]]:
        with self._lock:
            return {
                can_id: {
                    "count": entry.count,
                    "cycle_time_ms": entry.cycle_time_ms,
                }
                for can_id, entry in self._stats.items()
            }

    def reset(self) -> None:
        with self._lock:
            self._stats.clear()


class CANFrame:
    def __init__(self) -> None:
        self.CAN_ID = 0
        self.DLC = 0
        self.data: list[int] = []

    def __repr__(self) -> str:
        return f"CANFrame(CAN_ID={self.CAN_ID}, DLC={self.DLC}, data={self.data})"


class J2534API:
    class SMsg(ctypes.Structure):
        _fields_ = [
            ("ProtocolID", ctypes.c_ulong),
            ("RxStatus", ctypes.c_ulong),
            ("TxFlags", ctypes.c_ulong),
            ("Timestamp", ctypes.c_ulong),
            ("DataSize", ctypes.c_ulong),
            ("ExtraDataPtr", ctypes.c_ulong),
            ("Data", ctypes.c_ubyte * 4028),
        ]

    class Protocol_ID(Enum):
        J1850VPW = 1
        J1850PWM = 2
        ISO9141 = 3
        ISO14230 = 4
        CAN = 5
        SCI_A_ENGINE = 7
        SCI_A_TRANS = 8
        SCI_B_ENGINE = 9
        SCI_B_TRANS = 10
        ISO15765 = 0x40

    def __init__(self) -> None:
        self.j2534_dll = ctypes.WinDLL(
            r"C:\\Program Files (x86)\\Sloki\\SBUS\\lib\\x64\\sBus-J2534.dll"
        )
        self.device_id = ctypes.c_ulong()
        self.channel_id = ctypes.c_ulong()

    def SBusCanOpen(self):
        return self.j2534_dll.PassThruOpen(None, ctypes.byref(self.device_id))

    def SBusCanConnect(self, protocol, baudrate):
        return self.j2534_dll.PassThruConnect(
            self.device_id, protocol, 0, baudrate, ctypes.byref(self.channel_id)
        )

    def SBusCanClearRxMsg(self):
        DWORD = ctypes.c_ulong

        class SCONFIG(ctypes.Structure):
            _fields_ = [("Parameter", DWORD), ("Value", DWORD)]

        configList = SCONFIG()
        configList.Parameter = 0
        configList.Value = 0
        CLEAR_MSG_FILTERS = 0x0A
        return self.j2534_dll.PassThruIoctl(
            self.channel_id, CLEAR_MSG_FILTERS, ctypes.byref(configList), None
        )

    def SBusCanSendMgs(self, CanFrame):
        pNumMsgs = ctypes.c_ulong(1)
        CAN = 5
        ISO15765_FRAME_PAD = 0x40
        CAN_29BIT_ID = 0x0100

        TxMsg = self.SMsg()
        TxMsg.ProtocolID = CAN
        TxMsg.DataSize = CanFrame.DLC + 4

        if CanFrame.CAN_ID > 0x7FF:
            TxMsg.TxFlags = CAN_29BIT_ID
        else:
            TxMsg.TxFlags = ISO15765_FRAME_PAD

        c_byte_array = (ctypes.c_ubyte * 4028)()
        CanFrame.CAN_ID = CanFrame.CAN_ID & 0x1FFFFFFF
        c_byte_array[0] = (CanFrame.CAN_ID >> 24)
        c_byte_array[1] = (CanFrame.CAN_ID >> 16)
        c_byte_array[2] = (CanFrame.CAN_ID >> 8)
        c_byte_array[3] = CanFrame.CAN_ID & 0xFF
        for i in range(8):
            c_byte_array[4 + i] = CanFrame.data[i]

        TxMsg.Data = c_byte_array
        return self.j2534_dll.PassThruWriteMsgs(
            self.channel_id, ctypes.byref(TxMsg), ctypes.byref(pNumMsgs), 0
        )

    def SBusCanRxSetFilter(self, CAN_Id):
        msgMask = self.SMsg()
        msgPattern = self.SMsg()

        CAN = 5
        ISO15765_FRAME_PAD = 0x40
        PASS_FILTER = ctypes.c_ulong(1)
        filterId = ctypes.c_ulong(0)

        msgMask.ProtocolID = CAN
        msgMask.DataSize = 4
        for i in range(4):
            msgMask.Data[i] = 0xFF

        msgPattern.ProtocolID = CAN
        msgPattern.DataSize = 4
        CAN_Id = CAN_Id & 0x1FFFFFFF
        msgPattern.Data[0] = (CAN_Id >> 24)
        msgPattern.Data[1] = (CAN_Id >> 16)
        msgPattern.Data[2] = (CAN_Id >> 8)
        msgPattern.Data[3] = CAN_Id & 0xFF

        return self.j2534_dll.PassThruStartMsgFilter(
            self.channel_id,
            PASS_FILTER,
            ctypes.byref(msgMask),
            ctypes.byref(msgPattern),
            None,
            ctypes.byref(filterId),
        )

    def SBusCanReadMgs(self, timeout=0):
        CAN = 5
        Rx_Msg = self.SMsg()
        Rx_Msg.ProtocolID = CAN
        num_msgs = ctypes.c_ulong(1)
        status = self.j2534_dll.PassThruReadMsgs(
            self.channel_id, ctypes.byref(Rx_Msg), ctypes.byref(num_msgs), timeout
        )

        response = bytearray(Rx_Msg.Data)
        frame = CANFrame()
        frame.CAN_ID = (
            (response[0] << 24)
            | (response[1] << 16)
            | (response[2] << 8)
            | response[3]
        )
        frame.DLC = Rx_Msg.DataSize - 4
        frame.data = [response[4 + i] for i in range(frame.DLC)]
        return status, frame

    def SBusCanDisconnect(self):
        return self.j2534_dll.PassThruDisconnect(self.channel_id)

    def SBusCanClose(self):
        return self.j2534_dll.PassThruClose(self.device_id)


class CANReaderThread(QThread):
    def __init__(self, stats: CANStats, japi: J2534API, parent=None) -> None:
        super().__init__(parent)
        self._stats = stats
        self._japi = japi
        self._running = True

    def run(self) -> None:
        if self._japi.SBusCanOpen() != 0:
            return
        if self._japi.SBusCanConnect(J2534API.Protocol_ID.CAN.value, 500000) != 0:
            return
        self._japi.SBusCanClearRxMsg()
        while self._running:
            status, frame = self._japi.SBusCanReadMgs(10)
            if status == 0:
                self._stats.update(frame.CAN_ID)

    def stop(self) -> None:
        self._running = False


class StatsWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Sloki CAN Performance")

        self._stats = CANStats()
        self._japi = J2534API()
        self._reader = CANReaderThread(self._stats, self._japi)

        # Layout
        central_widget = QWidget()
        layout = QVBoxLayout()

        self._table = QTableWidget(0, 3)
        self._table.setHorizontalHeaderLabels(["CAN ID", "Cycle Time (ms)", "Count"])
        self._table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)

        # Restart Button
        restart_btn = QPushButton("Restart")
        restart_btn.clicked.connect(self._restart_stats)

        layout.addWidget(self._table)
        layout.addWidget(restart_btn)
        central_widget.setLayout(layout)
        self.setCentralWidget(central_widget)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._refresh)
        self._timer.start(300)

        self._reader.start()

    def _refresh(self) -> None:
        data = self._stats.snapshot()
        self._table.setRowCount(len(data))
        for row, (can_id, info) in enumerate(sorted(data.items())):
            can_item = QTableWidgetItem(f"{can_id:08X}")
            cycle_item = QTableWidgetItem(f"{info['cycle_time_ms']:.2f}")
            count_item = QTableWidgetItem(str(info["count"]))
            can_item.setTextAlignment(Qt.AlignCenter)
            cycle_item.setTextAlignment(Qt.AlignCenter)
            count_item.setTextAlignment(Qt.AlignCenter)
            self._table.setItem(row, 0, can_item)
            self._table.setItem(row, 1, cycle_item)
            self._table.setItem(row, 2, count_item)

    def _restart_stats(self) -> None:
        self._stats.reset()
        self._table.clearContents()
        self._table.setRowCount(0)

    def closeEvent(self, event) -> None:
        self._timer.stop()
        self._reader.stop()
        self._reader.wait()
        self._japi.SBusCanDisconnect()
        self._japi.SBusCanClose()
        super().closeEvent(event)


def main() -> None:
    app = QApplication(sys.argv)
    window = StatsWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
