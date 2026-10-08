"""Инструменты админки Telegram-бота (specs/006-admin-devtool).

Здесь всё, что зависит от платформы и внешних систем: проверки здоровья, вебхук, консоль 1С,
шаблоны сообщений, чтение файлов журнала. Маршруты — app/routes/admin_api.py.
"""

from __future__ import annotations

import asyncio
import re
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
from sqlalchemy import text

from . import keyboards, texts
from .db import MSK, now_msk
from .logging import LEVELS, level_no

PLATFORM = "telegram"
CHECK_TIMEOUT = 5.0
SECRET_FIELDS = {
    "BOT_TOKEN",
    "TG_WEBHOOK_SECRET",
    "ONEC_PASSWORD",
    "ONEC_WEBHOOK_SECRET",
    "ADMIN_PASSWORD",
}
ONEC_READ_METHODS = ("ping", "specialties", "doctors", "services", "schedule")
ONEC_PARAMS = ("branch", "date", "doctor_id", "start_date", "end_date")


# --- Настройки -----------------------------------------------------------------------------


def settings_view(settings) -> list[dict]:
    rows = []
    for name in type(settings).model_fields:
        value = getattr(settings, name)
        secret = name in SECRET_FIELDS
        if secret:
            shown = "задан" if value else "не задан"
        else:
            shown = "" if value is None else str(value)
        rows.append({"name": name, "value": shown, "secret": secret})
    return rows


def secret_values(settings) -> list[str]:
    """Значения секретов — для тестов, что они не утекают в ответы админки."""
    return [str(getattr(settings, n)) for n in SECRET_FIELDS if getattr(settings, n, "")]


# --- Проверки здоровья ---------------------------------------------------------------------


@dataclass
class Check:
    name: str
    ok: bool
    ms: int
    detail: str
    extra: dict | None = None

    def as_dict(self) -> dict:
        data = {"name": self.name, "ok": self.ok, "ms": self.ms, "detail": self.detail}
        data.update(self.extra or {})
        return data


def _error_text(exc: BaseException) -> str:
    if isinstance(exc, (asyncio.TimeoutError, httpx.TimeoutException)):
        return "таймаут"
    if isinstance(exc, httpx.ConnectError):
        return "нет соединения"
    return type(exc).__name__


async def _timed(name: str, coro) -> Check:
    start = time.monotonic()
    try:
        ok, detail, extra = await asyncio.wait_for(coro, CHECK_TIMEOUT)
    except Exception as exc:  # проверка не должна ронять страницу
        ok, detail, extra = False, _error_text(exc), None
    return Check(name, ok, int((time.monotonic() - start) * 1000), detail, extra)


async def _check_db(state) -> tuple[bool, str, None]:
    with state.session_factory() as session:
        schema = session.execute(text("PRAGMA user_version")).scalar()
    return True, f"схема {schema}", None


async def _check_scheduler(state) -> tuple[bool, str, None]:
    scheduler = state.scheduler
    jobs = len(scheduler.get_jobs())
    return (
        bool(scheduler.running),
        f"{'запущен' if scheduler.running else 'остановлен'}, заданий: {jobs}",
        None,
    )


async def onec_request(state, method: str, params: dict | None = None) -> dict:
    """GET к HTTP-сервису 1С без повторов: статус, время, тело (консоль и проверка)."""
    onec = state.onec
    start = time.monotonic()
    try:
        async with httpx.AsyncClient(
            auth=onec.auth, timeout=CHECK_TIMEOUT, transport=onec._transport
        ) as client:
            response = await client.get(f"{onec.base_url}/{method}", params=params or {})
    except httpx.HTTPError as exc:
        return {
            "method": method,
            "http_status": None,
            "ms": int((time.monotonic() - start) * 1000),
            "error": _error_text(exc),
        }
    try:
        body: Any = response.json()
    except ValueError:
        body = response.text[:2000]
    return {
        "method": method,
        "http_status": response.status_code,
        "ms": int((time.monotonic() - start) * 1000),
        "body": body,
    }


async def _check_onec(state) -> tuple[bool, str, None]:
    result = await onec_request(state, "ping")
    if result["http_status"] is None:
        return False, result["error"], None
    if result["http_status"] != 200:
        return False, f"HTTP {result['http_status']}", None
    body = result["body"]
    message = body.get("message") if isinstance(body, dict) else None
    return True, message or "ответила", None


async def bot_api(state, method: str, payload: dict | None = None) -> dict:
    """Вызов Telegram Bot API без повторов (для админки). Токен в ответ не попадает."""
    messenger = state.messenger
    async with httpx.AsyncClient(timeout=CHECK_TIMEOUT, transport=messenger._transport) as client:
        response = await client.post(
            f"{messenger.api_base}/bot{messenger._token}/{method}", json=payload or {}
        )
    try:
        return response.json()
    except ValueError:
        return {"ok": False, "description": f"HTTP {response.status_code}"}


def expected_webhook_url(settings) -> str:
    return settings.webhook_url


async def _check_bot(state) -> tuple[bool, str, None]:
    data = await bot_api(state, "getMe")
    if not data.get("ok"):
        return False, str(data.get("description") or "ошибка"), None
    username = (data.get("result") or {}).get("username")
    return True, f"@{username}" if username else "ответил", None


async def _check_webhook(state) -> tuple[bool, str, dict]:
    data = await bot_api(state, "getWebhookInfo")
    if not data.get("ok"):
        return False, str(data.get("description") or "ошибка"), {}
    info = data.get("result") or {}
    url = info.get("url") or ""
    expected = expected_webhook_url(state.settings)
    last_error = None
    recent_error = False
    if info.get("last_error_date"):
        when = datetime.fromtimestamp(info["last_error_date"], MSK).replace(tzinfo=None)
        last_error = f"{when:%d.%m %H:%M} {info.get('last_error_message', '')}".strip()
        recent_error = now_msk() - when < timedelta(minutes=10)
    extra = {
        "url": url,
        "expected_url": expected,
        "pending": info.get("pending_update_count", 0),
        "last_error": last_error,
    }
    if not url:
        return False, "вебхук не задан", extra
    if url != expected:
        return False, "адрес вебхука не совпадает с WEBAPP_URL", extra
    if recent_error:
        return False, "ошибка доставки за последние 10 минут", extra
    return True, f"в очереди: {extra['pending']}", extra


async def health_checks(state) -> list[dict]:
    checks = await asyncio.gather(
        _timed("db", _check_db(state)),
        _timed("scheduler", _check_scheduler(state)),
        _timed("onec", _check_onec(state)),
        _timed("bot", _check_bot(state)),
        _timed("webhook", _check_webhook(state)),
    )
    return [c.as_dict() for c in checks]


async def register_webhook(state) -> tuple[bool, str]:
    settings = state.settings
    data = await bot_api(
        state,
        "setWebhook",
        {
            "url": expected_webhook_url(settings),
            "secret_token": settings.TG_WEBHOOK_SECRET,
            "allowed_updates": ["message", "callback_query"],
            "drop_pending_updates": False,
        },
    )
    return bool(data.get("ok")), str(data.get("description") or "")


# --- Шаблоны сообщений ---------------------------------------------------------------------


@dataclass
class SampleVisit:
    """Вымышленная запись для предпросмотра шаблонов (без реальных ПДн)."""

    visit_at: datetime
    appointment_id: str = "demo-0000"
    fio_short: str = "Анна Сергеевна"
    doctor_name: str = "Петрова Мария Ивановна"
    service_name: str = "Первичный приём офтальмолога"
    branch: str = "Профсоюзная"
    notify: bool = True
    confirmed_at: datetime | None = None


def sample_visit() -> SampleVisit:
    tomorrow = (now_msk() + timedelta(days=1)).replace(hour=10, minute=30, second=0, microsecond=0)
    return SampleVisit(visit_at=tomorrow)


def templates(settings) -> list[dict]:
    from .routes.internal import REVIEWS_LINKS

    v = sample_visit()
    today = now_msk().date()
    url = settings.WEBAPP_URL
    items = [
        (
            "welcome",
            "Приветствие (/start)",
            texts.welcome("Анна"),
            keyboards.welcome(url, settings.WEBAPP_URL2),
        ),
        ("booked", "Запись создана", texts.booked(v), keyboards.visit(v.branch, url)),
        ("moved", "Запись перенесена", texts.moved(v), keyboards.visit(v.branch, url)),
        (
            "cancelled_by_patient",
            "Отменена пациентом",
            texts.cancelled_by_patient(v),
            keyboards.book_again(url),
        ),
        (
            "reminder_24h",
            "Напоминание за сутки",
            texts.reminder(v, "24h", today),
            keyboards.reminder(v.appointment_id, False, v.branch),
        ),
        (
            "reminder_2h",
            "Напоминание за 2 часа",
            texts.reminder(v, "2h", today),
            keyboards.reminder(v.appointment_id, False, v.branch),
        ),
        ("confirmed", "Визит подтверждён", texts.confirmed(v), None),
        ("already_confirmed", "Уже подтверждён", texts.already_confirmed(v), None),
        (
            "cancelled_by_admin",
            "Отменена клиникой",
            texts.cancelled_by_admin(v),
            keyboards.book_again(url),
        ),
        (
            "feedback",
            "Просьба об отзыве",
            texts.feedback(v),
            keyboards.review(REVIEWS_LINKS["Профсоюзная"]),
        ),
    ]
    return [
        {"key": key, "title": title, "text": body, "buttons": button_labels(kb), "keyboard": kb}
        for key, title, body, kb in items
    ]


def button_labels(keyboard: dict | None) -> list[list[dict]]:
    """Подписи и цвет кнопок для предпросмотра: tone = primary | success | danger | ""."""
    if not keyboard:
        return []
    return [
        [{"text": b.get("text", ""), "tone": b.get("style", "")} for b in row]
        for row in keyboard.get("inline_keyboard", [])
    ]


# --- Файлы журнала -------------------------------------------------------------------------

LINE_RE = re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) \| (\w+)\s*\| (.*)$")
MAX_READ_BYTES = 5 * 1024 * 1024
MAX_LINES = 2000


def list_log_files(log_dir: Path) -> list[dict]:
    if not log_dir.is_dir():
        return []
    files = [p for p in log_dir.iterdir() if p.is_file() and ".log" in p.name]
    files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return [
        {
            "name": p.name,
            "size_bytes": p.stat().st_size,
            "modified": datetime.fromtimestamp(p.stat().st_mtime, MSK)
            .replace(tzinfo=None)
            .isoformat(timespec="seconds"),
        }
        for p in files
    ]


def resolve_log_file(log_dir: Path, name: str) -> Path | None:
    """Только файл из списка LOG_DIR: защита от `..` и чужих путей."""
    names = {f["name"] for f in list_log_files(log_dir)}
    return log_dir / name if name in names else None


def _entries(raw: str) -> list[tuple[str, str]]:
    """(уровень, текст) по записям; строки без заголовка приклеиваются к предыдущей записи."""
    entries: list[list[str]] = []
    for line in raw.splitlines():
        match = LINE_RE.match(line)
        if match:
            entries.append([match.group(2).upper(), line])
        elif entries:
            entries[-1][1] += "\n" + line
        else:
            entries.append(["INFO", line])
    return [(lvl, body) for lvl, body in entries]


def read_log_file(path: Path, level: str | None, query: str | None, limit: int) -> dict:
    limit = max(1, min(limit, MAX_LINES))
    size = path.stat().st_size
    with path.open("rb") as fh:
        if size > MAX_READ_BYTES:
            fh.seek(size - MAX_READ_BYTES)
            fh.readline()  # первая строка обрезана
        raw = fh.read().decode("utf-8", errors="replace")
    min_no = level_no(level) if level and level.upper() in LEVELS else 0
    needle = (query or "").lower()
    picked = [
        body
        for lvl, body in _entries(raw)
        if level_no(lvl) >= min_no and (not needle or needle in body.lower())
    ]
    return {
        "name": path.name,
        "lines": picked[-limit:],
        "truncated": len(picked) > limit or size > MAX_READ_BYTES,
    }
