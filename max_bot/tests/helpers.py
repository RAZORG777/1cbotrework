"""Вспомогательные функции тестов: подписанный initData и тела запросов."""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from urllib.parse import urlencode

TOKEN = "123456:TEST-TOKEN"
ONEC = "https://onec.test/hs/bot"
MAX = "https://max.test"
ONEC_SECRET = "onec-secret"
MAX_SECRET = "max-secret"

# Тестовые ПДн: по ним тест журналов проверяет, что они не утекли.
PATIENT = {
    "first_name": "Агриппина",
    "last_name": "Тестовая-Фамилия",
    "middle_name": "Ивановна",
    "phone": "+7 (999) 123-45-67",
    "birth_date": "01.02.1990",
}


def make_init_data(
    user_id: int | str, token: str = TOKEN, auth_date: int | None = None, bad_hash: bool = False
) -> str:
    pairs = {
        "auth_date": str(int(time.time()) if auth_date is None else auth_date),
        "query_id": "AAHdF6IQAAAAAN0XohDhrOrc",
        "user": json.dumps({"id": int(user_id), "first_name": "Test"}, separators=(",", ":")),
    }
    check = "\n".join(f"{k}={pairs[k]}" for k in sorted(pairs))
    secret = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
    pairs["hash"] = (
        "0" * 64 if bad_hash else hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    )
    return urlencode(pairs)


def auth(user_id: int | str, **kwargs) -> dict:
    return {"Authorization": f"tma {make_init_data(user_id, **kwargs)}"}


def booking(
    date: str = "2030-01-10",
    time_: str = "10:00",
    consent: bool | None = True,
    old_id: str | None = None,
    notify: bool = True,
) -> dict:
    body = {
        "branch": "Профсоюзная",
        "doctor_id": "doc-1",
        "doctor_name": "Иванов Иван Иванович",
        "service_id": "srv-1",
        "service_name": "Первичный прием",
        "date": date,
        "time": time_,
        "patient": dict(PATIENT),
        "send_notifications": notify,
    }
    if consent is not None:
        body["pd_consent"] = consent
    if old_id:
        body["old_appointment_id"] = old_id
    return body
