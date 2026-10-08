"""Рассылки из админки (specs/007-broadcasts/contracts/broadcasts.md).

Получатели фиксируются при запуске в broadcast_recipients. Фоновая задача отправляет по одному
сообщению, после каждого отмечает получателя — поэтому после перезапуска рассылка продолжается
с того же места. Скорость — не больше 20 сообщений в секунду (FR-006).
"""

from __future__ import annotations

import asyncio
import html
import json
import re
import secrets
from dataclasses import dataclass
from pathlib import Path

import httpx
from loguru import logger
from sqlalchemy import delete, func, select

from . import keyboards, subscribers, texts
from .config import BASE_DIR
from .db import now_msk, session_scope
from .models import STATUS_ACTIVE, Appointment, Broadcast, BroadcastRecipient, Subscriber

PLATFORM = "max"
MEDIA_DIR = BASE_DIR / "media" / "broadcasts"
BRANCHES = ("Профсоюзная", "Новые Ватутинки")
TEXT_LIMIT = 4000
CAPTION_LIMIT = 4000  # в MAX текст с картинкой не короче обычного
BUTTON_TEXT_LIMIT = 40
IMAGE_LIMIT = 5 * 1024 * 1024
PAUSE = 0.05  # 20 сообщений в секунду
BATCH = 25
IMAGE_RE = re.compile(r"^[0-9a-f]{32}\.(jpg|png)$")
IMAGE_TYPES = {b"\xff\xd8\xff": "jpg", b"\x89PNG\r\n\x1a\n": "png"}

# --- Текст -----------------------------------------------------------------------------------

TAG_RE = re.compile(r'</?(?:b|i|u|s|code)>|<a href="https?://[^"<>\s]+">|</a>')
TAG_NAME_RE = re.compile(r"</?([a-z]+)")
ENTITY_RE = re.compile(r"&(?:amp|lt|gt|quot|#\d+);")
UNKNOWN_TAG_RE = re.compile(r"</?[a-zA-Z][^>]*>")


def _escape_plain(segment: str) -> str:
    """Экранирует &, <, > вне тегов; готовые сущности (&amp; …) не трогает."""
    out, pos = [], 0
    for match in ENTITY_RE.finditer(segment):
        out.append(html.escape(segment[pos : match.start()], quote=False))
        out.append(match.group(0))
        pos = match.end()
    out.append(html.escape(segment[pos:], quote=False))
    return "".join(out)


def normalize_text(raw: str) -> tuple[str, str | None]:
    """Разметка HTML (format=html в MAX): только b, i, u, s, code, a href. → (html, ошибка)."""
    text = raw.replace("\r\n", "\n").strip()
    if not text:
        return "", "Напишите текст рассылки."
    parts, stack, pos = [], [], 0
    for match in TAG_RE.finditer(text):
        plain = text[pos : match.start()]
        bad = UNKNOWN_TAG_RE.search(plain)
        if bad:
            return "", f"Тег {bad.group(0)} не поддерживается: можно b, i, u, s, code и ссылки."
        parts.append(_escape_plain(plain))
        tag = match.group(0)
        name = TAG_NAME_RE.match(tag).group(1)
        if tag.startswith("</"):
            if not stack or stack[-1] != name:
                return "", f"Тег </{name}> закрыт не по порядку или лишний."
            stack.pop()
        else:
            if name in stack:
                return "", f"Тег <{name}> вложен сам в себя."
            stack.append(name)
        parts.append(tag)
        pos = match.end()
    tail = text[pos:]
    bad = UNKNOWN_TAG_RE.search(tail)
    if bad:
        return "", f"Тег {bad.group(0)} не поддерживается: можно b, i, u, s, code и ссылки."
    parts.append(_escape_plain(tail))
    if stack:
        return "", f"Не закрыт тег <{stack[-1]}>."
    return "".join(parts), None


def visible_length(markup: str) -> int:
    return len(html.unescape(TAG_RE.sub("", markup)))


@dataclass
class Draft:
    kind: str
    audience: str
    branch: str
    text: str
    image: str
    button_type: str
    button_text: str
    button_url: str


def check_draft(draft: Draft) -> str | None:
    """Ошибка черновика для администратора или None. text в draft уже нормализован."""
    if draft.kind not in ("service", "promo"):
        return "Неизвестный тип рассылки."
    if draft.audience not in ("all", "active", "branch"):
        return "Неизвестная аудитория."
    if draft.audience == "branch" and draft.branch not in BRANCHES:
        return "Выберите филиал."
    if draft.image and image_path(draft.image) is None:
        return "Картинка не найдена — загрузите её снова."
    limit = CAPTION_LIMIT if draft.image else TEXT_LIMIT
    length = visible_length(draft.text)
    if length > limit:
        where = "с картинкой" if draft.image else "без картинки"
        return f"Текст длиннее {limit} символов {where} ({length}). Сократите его."
    if draft.button_type not in ("none", "book", "url"):
        return "Неизвестный тип кнопки."
    if draft.button_type == "url":
        if not 1 <= len(draft.button_text.strip()) <= BUTTON_TEXT_LIMIT:
            return f"Подпись кнопки — от 1 до {BUTTON_TEXT_LIMIT} символов."
        if not re.match(r"^https://[^\s]+$", draft.button_url.strip()):
            return "Ссылка кнопки должна начинаться с https://"
    return None


# --- Картинки --------------------------------------------------------------------------------


def save_image(body: bytes) -> str | None:
    """JPEG или PNG до 5 МБ → случайное имя файла; иначе None."""
    if not body or len(body) > IMAGE_LIMIT:
        return None
    ext = next((e for magic, e in IMAGE_TYPES.items() if body.startswith(magic)), None)
    if ext is None:
        return None
    MEDIA_DIR.mkdir(parents=True, exist_ok=True)
    name = f"{secrets.token_hex(16)}.{ext}"
    (MEDIA_DIR / name).write_bytes(body)
    return name


def image_path(name: str) -> Path | None:
    if not IMAGE_RE.match(name or ""):
        return None
    path = MEDIA_DIR / name
    return path if path.is_file() else None


# --- Получатели ------------------------------------------------------------------------------


def _branch_clause(branch: str):
    vatutinki = Appointment.branch.contains("Ватутинки")
    return vatutinki if "Ватутинки" in branch else ~vatutinki


def recipients_query(kind: str, audience: str, branch: str = ""):
    query = select(Subscriber.user_id).where(Subscriber.blocked_at.is_(None))
    if kind == "promo":
        query = query.where(Subscriber.news_consent.is_(True))
    if audience in ("active", "branch"):
        patients = select(Appointment.user_id).where(Appointment.status == STATUS_ACTIVE)
        if audience == "branch":
            patients = patients.where(_branch_clause(branch))
        query = query.where(Subscriber.user_id.in_(patients))
    return query


def count_recipients(session, kind: str, audience: str, branch: str = "") -> int:
    query = recipients_query(kind, audience, branch)
    return session.scalar(select(func.count()).select_from(query.subquery())) or 0


# --- Отправка (MAX Bot API) -----------------------------------------------------------------


def public_image_url(settings, name: str) -> str:
    """MAX берёт картинку по ссылке: routes/media.py раздаёт её без авторизации."""
    return f"{settings.WEBAPP_URL}/max/media/broadcasts/{name}"


class Sender:
    """Отправка одного сообщения рассылки через POST /messages."""

    def __init__(self, state, draft: Draft):
        self.messenger = state.messenger
        self.draft = draft
        keyboard = keyboards.broadcast(
            draft.button_type,
            draft.button_text,
            draft.button_url,
            state.settings.MAX_MINIAPP,
            draft.kind == "promo",
        )
        attachments = []
        if draft.image:
            attachments.append(
                {"type": "image", "payload": {"url": public_image_url(state.settings, draft.image)}}
            )
        if keyboard:
            attachments.append({"type": "inline_keyboard", "payload": {"buttons": keyboard}})
        self.payload = {"text": draft.text, "format": "html"}
        if attachments:
            self.payload["attachments"] = attachments
        self.client: httpx.AsyncClient | None = None

    async def __aenter__(self):
        self.client = httpx.AsyncClient(timeout=20.0, transport=self.messenger._transport)
        return self

    async def __aexit__(self, *exc):
        await self.client.aclose()

    async def send(self, user_id: str) -> tuple[str, str]:
        """→ (sent | blocked | failed, пояснение для журнала)."""
        headers = {"Authorization": self.messenger._token}
        for attempt in range(1, 4):
            try:
                response = await self.client.post(
                    f"{self.messenger.api_url}/messages",
                    params={"user_id": user_id},
                    json=self.payload,
                    headers=headers,
                )
            except httpx.TransportError as exc:
                if attempt == 3:
                    return "failed", type(exc).__name__
                await asyncio.sleep(1)
                continue
            if response.status_code == 200:
                return "sent", ""
            try:
                data = response.json()
            except ValueError:
                data = {}
            detail = str(data.get("message") or data.get("code") or f"HTTP {response.status_code}")
            if response.status_code == 429 or "not.ready" in json.dumps(data):
                await asyncio.sleep(1)
                continue
            if response.status_code in (403, 404):
                return "blocked", detail
            return "failed", detail
        return "failed", "превышен лимит повторов"


# --- Запуск, ход, остановка ------------------------------------------------------------------


def draft_of(bc: Broadcast) -> Draft:
    return Draft(
        bc.kind,
        bc.audience,
        bc.branch,
        bc.text,
        bc.image,
        bc.button_type,
        bc.button_text,
        bc.button_url,
    )


def _tasks(state) -> dict[int, asyncio.Task]:
    tasks = getattr(state, "broadcast_tasks", None)
    if tasks is None:
        tasks = {}
        state.broadcast_tasks = tasks
    return tasks


def is_running(state, broadcast_id: int) -> bool:
    task = _tasks(state).get(broadcast_id)
    return task is not None and not task.done()


def create(state, draft: Draft, admin: str) -> Broadcast | None:
    """Создать рассылку и зафиксировать получателей; None — получателей нет."""
    now = now_msk()
    with session_scope(state.session_factory) as session:
        users = list(session.scalars(recipients_query(draft.kind, draft.audience, draft.branch)))
        if not users:
            return None
        bc = Broadcast(
            created_at=now,
            created_by=admin,
            kind=draft.kind,
            audience=draft.audience,
            branch=draft.branch if draft.audience == "branch" else "",
            text=draft.text,
            image=draft.image,
            button_type=draft.button_type,
            button_text=draft.button_text.strip(),
            button_url=draft.button_url.strip(),
            status="sending",
            total=len(users),
            started_at=now,
        )
        session.add(bc)
        session.flush()
        session.add_all(BroadcastRecipient(broadcast_id=bc.id, user_id=u) for u in users)
    start(state, bc.id)
    return bc


def start(state, broadcast_id: int) -> None:
    if not is_running(state, broadcast_id):
        _tasks(state)[broadcast_id] = asyncio.create_task(run(state, broadcast_id))


def _finish(session, bc: Broadcast, status: str) -> None:
    bc.status = status
    bc.finished_at = bc.finished_at or now_msk()
    session.execute(delete(BroadcastRecipient).where(BroadcastRecipient.broadcast_id == bc.id))


async def run(state, broadcast_id: int) -> None:
    factory = state.session_factory
    try:
        with session_scope(factory) as session:
            bc = session.get(Broadcast, broadcast_id)
            if bc is None or bc.status != "sending":
                return
            draft = draft_of(bc)
        logger.info("Рассылка {}: отправка начата", broadcast_id)
        async with Sender(state, draft) as sender:
            while True:
                with session_scope(factory) as session:
                    bc = session.get(Broadcast, broadcast_id)
                    if bc.status != "sending":
                        _finish(session, bc, bc.status)
                        logger.info("Рассылка {}: остановлена", broadcast_id)
                        return
                    batch = list(
                        session.scalars(
                            select(BroadcastRecipient.user_id)
                            .where(
                                BroadcastRecipient.broadcast_id == broadcast_id,
                                BroadcastRecipient.state == "pending",
                            )
                            .limit(BATCH)
                        )
                    )
                    if not batch:
                        _finish(session, bc, "done")
                        logger.info(
                            "Рассылка {}: готово, отправлено {}, ошибок {}, заблокировали {}",
                            broadcast_id,
                            bc.sent,
                            bc.failed,
                            bc.blocked,
                        )
                        return
                for user_id in batch:
                    result, detail = await sender.send(user_id)
                    with session_scope(factory) as session:
                        rec = session.get(BroadcastRecipient, (broadcast_id, user_id))
                        if rec is not None:
                            rec.state = result
                        bc = session.get(Broadcast, broadcast_id)
                        setattr(bc, result, getattr(bc, result) + 1)
                        if result == "blocked":
                            subscribers.mark_blocked(session, user_id)
                    if result == "failed":
                        logger.warning(
                            "Рассылка {}: не доставлено user_id={} ({})",
                            broadcast_id,
                            user_id,
                            detail,
                        )
                    await asyncio.sleep(PAUSE)
    except asyncio.CancelledError:
        raise
    except Exception as exc:  # ошибка кода не должна крутить рассылку бесконечно
        logger.error("Рассылка {}: сбой {}", broadcast_id, type(exc).__name__)
        with session_scope(factory) as session:
            bc = session.get(Broadcast, broadcast_id)
            if bc is not None:
                _finish(session, bc, "stopped")
    finally:
        _tasks(state).pop(broadcast_id, None)


def stop(state, broadcast_id: int) -> bool:
    with session_scope(state.session_factory) as session:
        bc = session.get(Broadcast, broadcast_id)
        if bc is None:
            return False
        if bc.status == "sending":
            bc.status = "stopped"
            bc.finished_at = now_msk()
            if not is_running(state, broadcast_id):
                _finish(session, bc, "stopped")
    return True


def resume(state) -> int:
    """При старте бота: продолжить незавершённые рассылки (FR-007)."""
    with session_scope(state.session_factory) as session:
        ids = list(session.scalars(select(Broadcast.id).where(Broadcast.status == "sending")))
    for broadcast_id in ids:
        start(state, broadcast_id)
    if ids:
        logger.info("Продолжены рассылки: {}", ids)
    return len(ids)


async def shutdown(state) -> None:
    tasks = list(_tasks(state).values())
    for task in tasks:
        task.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)


async def send_test(state, draft: Draft, chat_id: str) -> tuple[bool, str]:
    async with Sender(state, draft) as sender:
        result, detail = await sender.send(chat_id)
    return result == "sent", detail


TEXTS_FOR_UI = {"unsubscribe": texts.BTN_UNSUBSCRIBE, "book": texts.BTN_BOOK}
