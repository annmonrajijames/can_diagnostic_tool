"""Utility to monitor PEAK CAN bus statistics.

The script connects to a PEAK interface using the :mod:`can` library and
prints basic throughput information such as the number of frames received
per second and the running total.  It is intended for quick benchmarking or
monitoring of a PEAK device and has no external dependencies besides
``python-can``.
"""

from __future__ import annotations

import time

import can


def monitor(channel: str = "PCAN_USBBUS1", bitrate: int = 500000) -> None:
    """Continuously print basic CAN bus statistics.

    Parameters
    ----------
    channel:
        Identifier for the PEAK hardware channel.
    bitrate:
        Bit rate of the CAN bus in bits per second.

    The function runs until interrupted (``Ctrl+C``).  Each second the number
    of frames received in the last interval along with the running total is
    displayed.
    """

    bus = can.Bus(bustype="pcan", channel=channel, bitrate=bitrate)
    input("Press Enter to start the statistics")
    total = 0
    count = 0
    last_report = time.time()

    try:
        while True:
            msg = bus.recv(timeout=1.0)
            if msg is None:
                continue

            total += 1
            count += 1
            now = time.time()
            if now - last_report >= 1.0:
                frames_per_second = count / (now - last_report)
                print(f"{frames_per_second:7.2f} frames/s  |  total: {total}")
                last_report = now
                count = 0
    except KeyboardInterrupt:  # pragma: no cover - user interruption
        pass
    finally:
        bus.shutdown()


def main() -> int:  # pragma: no cover - CLI entry point
    monitor()
    return 0


if __name__ == "__main__":  # pragma: no cover - module test
    raise SystemExit(main())
