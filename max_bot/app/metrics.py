"""Счётчики активности с момента запуска (specs/006-admin-devtool, FR-003).

Хранятся только в памяти: при перезапуске обнуляются, история — в журнале.
"""

from __future__ import annotations

import time
from collections import Counter
from datetime import datetime

from .db import now_msk

COUNTERS = (
    "webhook_updates",
    "callbacks",
    "onec_signals",
    "bookings",
    "reschedules",
    "cancellations",
    "messages_sent",
    "messages_failed",
    "onec_errors",
    "http_errors",
    "admin_actions",
)

_counters: Counter[str] = Counter()
_started = {"at": now_msk(), "mono": time.monotonic()}


def inc(name: str, value: int = 1) -> None:
    _counters[name] += value


def snapshot() -> dict[str, int]:
    return {name: _counters.get(name, 0) for name in COUNTERS}


def mark_started() -> None:
    _counters.clear()
    _started["at"] = now_msk()
    _started["mono"] = time.monotonic()


def started_at() -> datetime:
    return _started["at"]


def uptime_seconds() -> int:
    return int(time.monotonic() - _started["mono"])
