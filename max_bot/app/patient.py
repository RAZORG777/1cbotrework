"""Нормализация данных пациента перед отправкой в 1С (этап 1, contracts/onec-book.md).

Телефон — `+7XXXXXXXXXX`, дата рождения — `YYYY-MM-DD` (принцип II конституции).
Ошибки не содержат введённых значений: в них могут быть ПДн.
"""

from __future__ import annotations

import re
from datetime import date

MIN_BIRTH_DATE = date(1900, 1, 1)

BAD_PHONE = "BAD_PHONE"
BAD_BIRTH_DATE = "BAD_BIRTH_DATE"

MESSAGES = {
    BAD_PHONE: "Проверьте номер телефона: нужен российский номер из 10 цифр после +7.",
    BAD_BIRTH_DATE: "Проверьте дату рождения: формат ДД.ММ.ГГГГ, не позже сегодняшнего дня.",
}

_ISO = re.compile(r"^(\d{4})-(\d{2})-(\d{2})$")
_RU = re.compile(r"^(\d{2})\.(\d{2})\.(\d{4})$")


def normalize_phone(value: str) -> str:
    """`+7 (999) 123-45-67`, `89991234567`, `9991234567` → `+79991234567`."""
    digits = re.sub(r"\D", "", value or "")
    if len(digits) == 11 and digits[0] in "78":
        digits = digits[1:]
    if len(digits) != 10:
        raise ValueError(BAD_PHONE)
    return "+7" + digits


def normalize_birth_date(value: str, today: date | None = None) -> str:
    """`31.12.1990` или `1990-12-31` → `1990-12-31`; невозможные даты — ошибка."""
    text = (value or "").strip()
    if m := _ISO.match(text):
        year, month, day = (int(g) for g in m.groups())
    elif m := _RU.match(text):
        day, month, year = (int(g) for g in m.groups())
    else:
        raise ValueError(BAD_BIRTH_DATE)
    try:
        parsed = date(year, month, day)
    except ValueError:
        raise ValueError(BAD_BIRTH_DATE) from None
    if parsed < MIN_BIRTH_DATE or parsed > (today or date.today()):
        raise ValueError(BAD_BIRTH_DATE)
    return parsed.isoformat()
