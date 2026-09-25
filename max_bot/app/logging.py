"""Журналы: файл с ротацией, буфер для админки, маскирование ПДн как страховка (R9)."""

from __future__ import annotations

import re
import sys
from collections import deque

from loguru import logger

PHONE_RE = re.compile(r"(?:\+7|\b[78])[\s\-()]*\d{3}[\s\-()]*\d{3}[\s\-]*\d{2}[\s\-]*\d{2}\b")
DATE_RE = re.compile(r"\b\d{2}\.\d{2}\.\d{4}\b")

log_buffer: deque[str] = deque(maxlen=200)


def mask_pii(text: str) -> str:
    text = PHONE_RE.sub("[phone]", text)
    return DATE_RE.sub("[date]", text)


def _patcher(record) -> None:
    record["message"] = mask_pii(record["message"])


def _buffer_sink(message) -> None:
    log_buffer.append(str(message).rstrip())


def setup_logging(log_dir, name: str) -> None:
    log_dir.mkdir(parents=True, exist_ok=True)
    logger.remove()
    logger.configure(patcher=_patcher)
    fmt = "{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {message}"
    logger.add(sys.stdout, format=fmt)
    logger.add(
        log_dir / f"{name}.log",
        format=fmt,
        rotation="10 MB",
        retention="10 days",
        encoding="utf-8",
    )
    logger.add(_buffer_sink, format="[{time:HH:mm:ss}] {level} {message}")
