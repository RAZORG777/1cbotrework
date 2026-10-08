"""Журналы: файл с ротацией, буфер для админки, маскирование ПДн как страховка (R9).

Админка (specs/006-admin-devtool) читает структурированный буфер `log_records` и может
временно сменить уровень журнала без перезапуска (`set_level`).
"""

from __future__ import annotations

import re
import sys
from collections import deque
from itertools import count
from zoneinfo import ZoneInfo

from loguru import logger

PHONE_RE = re.compile(r"(?:\+7|\b[78])[\s\-()]*\d{3}[\s\-()]*\d{3}[\s\-]*\d{2}[\s\-]*\d{2}\b")
DATE_RE = re.compile(r"\b\d{2}\.\d{2}\.\d{4}\b")

LEVELS = ("DEBUG", "INFO", "WARNING", "ERROR")
DEFAULT_LEVEL = "INFO"
LOG_FORMAT = "{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {message}"

# Текстовый буфер (GET /admin/logs, как раньше) и структурированный — для живого хвоста.
log_buffer: deque[str] = deque(maxlen=200)
log_records: deque[dict] = deque(maxlen=1000)
_seq = count(1)
_state = {"level": DEFAULT_LEVEL}
MSK = ZoneInfo("Europe/Moscow")


def mask_pii(text: str) -> str:
    text = PHONE_RE.sub("[phone]", text)
    return DATE_RE.sub("[date]", text)


def _patcher(record) -> None:
    record["message"] = mask_pii(record["message"])


def level_no(name: str) -> int:
    try:
        return logger.level(name.upper()).no
    except ValueError:
        return logger.level(DEFAULT_LEVEL).no


def _level_filter(record) -> bool:
    return record["level"].no >= level_no(_state["level"])


def current_level() -> str:
    return _state["level"]


def set_level(name: str) -> str:
    name = name.upper()
    if name not in LEVELS:
        raise ValueError(name)
    _state["level"] = name
    return name


def _buffer_sink(message) -> None:
    record = message.record
    text = record["message"]
    if record["exception"] is not None:
        # Трассировка — в живой хвост тоже, чтобы ошибку было видно без чтения файла.
        text = str(message).rstrip().split(" | ", 2)[-1]
    log_buffer.append(f"[{record['time']:%H:%M:%S}] {record['level'].name} {record['message']}")
    log_records.append(
        {
            "seq": next(_seq),
            # По Москве, как остальные времена админки (часы сервера могут быть в UTC).
            "time": record["time"].astimezone(MSK).strftime("%Y-%m-%d %H:%M:%S"),
            "level": record["level"].name,
            "message": text,
        }
    )


def tail(after: int = 0) -> list[dict]:
    return [r for r in log_records if r["seq"] > after]


def setup_logging(log_dir, name: str) -> None:
    log_dir.mkdir(parents=True, exist_ok=True)
    _state["level"] = DEFAULT_LEVEL
    logger.remove()
    logger.configure(patcher=_patcher)
    logger.add(sys.stdout, format=LOG_FORMAT, level="DEBUG", filter=_level_filter, diagnose=False)
    logger.add(
        log_dir / f"{name}.log",
        format=LOG_FORMAT,
        level="DEBUG",
        filter=_level_filter,
        diagnose=False,
        rotation="10 MB",
        retention="10 days",
        encoding="utf-8",
    )
    logger.add(_buffer_sink, format=LOG_FORMAT, level="DEBUG", filter=_level_filter, diagnose=False)
