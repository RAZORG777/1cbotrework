"""Проверка личности пользователя WebApp и секретов служебных входов (FR-001–FR-004, FR-009–FR-012)."""

from __future__ import annotations

import hashlib
import hmac
import ipaddress
import json
import secrets
import time
from dataclasses import dataclass
from urllib.parse import parse_qsl

from fastapi import Depends, Header, HTTPException, Request
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from loguru import logger

OPEN_FROM_BOT = "OPEN_FROM_BOT"
SESSION_EXPIRED = "SESSION_EXPIRED"


class InitDataError(Exception):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class WebAppUser:
    id: str
    first_name: str = ""


def verify_init_data(
    raw: str, bot_token: str, max_age_hours: int, now: float | None = None
) -> WebAppUser:
    """Проверка initData мини-приложения MAX: HMAC-SHA256, ключ HMAC("WebAppData", token) (R2).

    Значения URL-декодируются, пары без hash сортируются и соединяются переводом строки.
    """
    if not raw:
        raise InitDataError(OPEN_FROM_BOT)
    pairs = dict(parse_qsl(raw, keep_blank_values=True, strict_parsing=False))
    received = pairs.pop("hash", None)
    if not received:
        raise InitDataError(OPEN_FROM_BOT)
    # Все поля, кроме hash (включая signature), входят в строку проверки.
    check_string = "\n".join(f"{k}={pairs[k]}" for k in sorted(pairs))
    secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    expected = hmac.new(secret_key, check_string.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, received):
        raise InitDataError(OPEN_FROM_BOT)
    try:
        auth_date = int(pairs.get("auth_date", "0"))
    except ValueError as exc:
        raise InitDataError(OPEN_FROM_BOT) from exc
    now = time.time() if now is None else now
    if now - auth_date > max_age_hours * 3600:
        raise InitDataError(SESSION_EXPIRED)
    try:
        user = json.loads(pairs.get("user", "{}"))
        user_id = str(user["id"])
    except (ValueError, KeyError, TypeError) as exc:
        raise InitDataError(OPEN_FROM_BOT) from exc
    return WebAppUser(id=user_id, first_name=str(user.get("first_name", "")))


def current_user(request: Request, authorization: str | None = Header(default=None)) -> WebAppUser:
    settings = request.app.state.settings
    raw = ""
    if authorization and authorization.lower().startswith("tma "):
        raw = authorization[4:].strip()
    try:
        return verify_init_data(raw, settings.MAX_BOT_TOKEN, settings.INIT_DATA_MAX_AGE_HOURS)
    except InitDataError as exc:
        raise HTTPException(status_code=401, detail={"error": exc.code}) from None


def _secret_ok(given: str | None, expected: str) -> bool:
    return bool(given) and secrets.compare_digest(given.encode(), expected.encode())


def require_onec_secret(request: Request, x_bot_secret: str | None = Header(default=None)) -> None:
    if not _secret_ok(x_bot_secret, request.app.state.settings.ONEC_WEBHOOK_SECRET):
        client = request.client.host if request.client else "?"
        logger.warning("Отклонён сигнал 1С без верного секрета: {} {}", client, request.url.path)
        raise HTTPException(status_code=401, detail={"status": "unauthorized"})


def require_max_webhook_secret(
    request: Request,
    x_max_bot_api_secret: str | None = Header(default=None),
) -> None:
    if not _secret_ok(x_max_bot_api_secret, request.app.state.settings.MAX_WEBHOOK_SECRET):
        logger.warning("Отклонён вебхук MAX без верного секрета")
        raise HTTPException(status_code=401, detail={"status": "unauthorized"})


_basic = HTTPBasic()


# Защита от подбора пароля (аудит 09.10.2026): после LOGIN_MAX_FAILS неудач за LOGIN_WINDOW
# секунд адрес блокируется на LOGIN_BLOCK секунд. Состояние — в памяти процесса.
LOGIN_MAX_FAILS = 10
LOGIN_WINDOW = 15 * 60
LOGIN_BLOCK = 15 * 60


def client_ip(request: Request) -> str:
    """Адрес клиента. За NGINX Proxy Manager прямой адрес — прокси, настоящий — в X-Real-IP."""
    peer = request.client.host if request.client else "?"
    try:
        trusted = ipaddress.ip_address(peer).is_private or ipaddress.ip_address(peer).is_loopback
    except ValueError:
        trusted = False
    if trusted:
        forwarded = request.headers.get("X-Real-IP") or request.headers.get("X-Forwarded-For", "")
        forwarded = forwarded.split(",")[0].strip()
        if forwarded:
            return forwarded
    return peer


def _login_state(request: Request) -> dict:
    state = getattr(request.app.state, "login_failures", None)
    if state is None:
        state = {}
        request.app.state.login_failures = state
    return state


def require_admin(request: Request, credentials: HTTPBasicCredentials = Depends(_basic)) -> str:
    settings = request.app.state.settings
    ip = client_ip(request)
    failures = _login_state(request)
    now = time.monotonic()
    entry = failures.get(ip)
    if entry and entry.get("blocked_until", 0) > now:
        retry = int(entry["blocked_until"] - now) + 1
        raise HTTPException(
            status_code=429,
            detail={"error": "TOO_MANY_ATTEMPTS"},
            headers={"Retry-After": str(retry)},
        )
    ok_user = secrets.compare_digest(
        credentials.username.encode(), settings.ADMIN_USERNAME.encode()
    )
    ok_pass = secrets.compare_digest(
        credentials.password.encode(), settings.ADMIN_PASSWORD.encode()
    )
    if not (ok_user and ok_pass):
        if not entry or now - entry["first"] > LOGIN_WINDOW:
            entry = {"first": now, "count": 0}
        entry["count"] += 1
        if entry["count"] >= LOGIN_MAX_FAILS:
            entry["blocked_until"] = now + LOGIN_BLOCK
            logger.warning(
                "Админка: {} заблокирован на 15 минут после {} неудачных входов", ip, entry["count"]
            )
        failures[ip] = entry
        logger.warning("Неудачный вход в админку с {}", ip)
        raise HTTPException(
            status_code=401,
            detail="Неверный логин или пароль",
            headers={"WWW-Authenticate": "Basic"},
        )
    failures.pop(ip, None)
    return credentials.username


def require_admin_action(request: Request, admin: str = Depends(require_admin)) -> str:
    """Изменяющие запросы админки: нужен заголовок X-Admin-Request (защита от CSRF).

    Браузер сохраняет вход Basic и отправит его и с чужого сайта, но поставить свой заголовок
    чужой сайт не может без CORS, а CORS бот не разрешает (specs/006-admin-devtool, FR-002).
    """
    if request.headers.get("X-Admin-Request") != "1":
        raise HTTPException(status_code=403, detail={"error": "ADMIN_HEADER_REQUIRED"})
    return admin
