"""Utilities for measuring CAN frame statistics.

This module exposes the :class:`CANStats` class which tracks the count and
cycle time for each CAN identifier observed on the bus.  The class is
thread-safe so it can be updated from a background thread while a GUI displays
the statistics.
"""

from __future__ import annotations

from dataclasses import dataclass
from threading import Lock
from typing import Dict
import time


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
        """Record reception of *can_id* at the current time."""
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
        """Return a snapshot of the collected statistics.

        The result maps CAN identifiers to dictionaries containing ``count`` and
        ``cycle_time_ms`` entries.  The snapshot is safe to use without holding
        the internal lock.
        """

        with self._lock:
            return {
                can_id: {
                    "count": entry.count,
                    "cycle_time_ms": entry.cycle_time_ms,
                }
                for can_id, entry in self._stats.items()
            }


__all__ = ["CANStats"]

