"""Вебхук MAX (contracts/messenger-webhooks.md).

Ответ 200 отдаётся сразу, обработка — в фоне (MAX повторяет доставку при долгом ответе).
Нажатия кнопок приходят событием `message_callback`: payload и пользователь — в `callback`.
Сырые апдейты в журнал не пишутся.
"""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, Request
from loguru import logger

from ..auth import require_max_webhook_secret
from ..db import mark_processed, session_scope
from ..onec_client import OneCError
from .webapp import active_for, cancel_for_user, cancelled_text

router = APIRouter()

WELCOME = (
    "<b>Добро пожаловать в клинику «ЯСНО ВИЖУ»!</b> 👋\n\n"
    "Нажмите кнопку ниже, чтобы выбрать врача и время для записи. "
    "Кнопка всегда будет здесь, просто напишите мне любое слово, если потеряете её!"
)


def event_key(update: dict) -> str | None:
    kind = update.get("update_type", "")
    if kind == "message_callback":
        callback_id = (update.get("callback") or {}).get("callback_id")
        return f"max:cb:{callback_id}" if callback_id else None
    mid = ((update.get("message") or {}).get("body") or {}).get("mid")
    if mid:
        return f"max:{kind}:{mid}"
    user_id = update.get("user_id") or (update.get("user") or {}).get("user_id")
    if kind == "bot_started" and user_id and update.get("timestamp"):
        return f"max:bot_started:{user_id}:{update['timestamp']}"
    return None


async def send_welcome(state, user_id: str) -> None:
    keyboard = [
        [{"type": "open_app", "text": "Записаться ✅", "web_app": state.settings.MAX_MINIAPP}]
    ]
    await state.messenger.send_message(user_id, WELCOME, keyboard)


async def handle_callback(state, update: dict) -> None:
    callback = update.get("callback") or {}
    callback_id = str(callback.get("callback_id") or "")
    payload = callback.get("payload") or ""
    user_id = str((callback.get("user") or {}).get("user_id") or "")
    if not user_id:
        return

    if payload == "confirm_visit":
        with session_scope(state.session_factory) as session:
            appt = active_for(session, user_id)
            appointment_id = appt.appointment_id if appt else None
        if appointment_id is None:
            await state.messenger.answer_callback(callback_id, "Активная запись не найдена")
            return
        try:
            await state.onec.update_note(appointment_id, "✅ Визит подтвержден пациентом (MAX)")
            text = "✅ <b>Спасибо! Ваш визит подтвержден.</b> Ждем вас в клинике!"
        except OneCError:
            text = "⚠️ Произошла ошибка связи с клиникой, но мы зафиксировали ваше подтверждение."
        await state.messenger.answer_callback(callback_id, "Визит подтверждён")
        await state.messenger.send_message(user_id, text)
        logger.info("Подтверждение визита: user_id={} appointment_id={}", user_id, appointment_id)

    elif payload == "cancel_visit_btn":
        result = await cancel_for_user(state, user_id)
        if isinstance(result, dict):
            await state.messenger.answer_callback(callback_id, "Запись отменена")
            await state.messenger.send_message(user_id, cancelled_text(result["fio"]))
        else:
            await state.messenger.answer_callback(callback_id, "Не удалось отменить запись")
    else:
        await state.messenger.answer_callback(callback_id)


async def process(state, update: dict) -> None:
    try:
        kind = update.get("update_type")
        if kind == "message_callback":
            await handle_callback(state, update)
        elif kind == "bot_started":
            user_id = str(update.get("user_id") or (update.get("user") or {}).get("user_id") or "")
            if user_id:
                await send_welcome(state, user_id)
                logger.info("bot_started: user_id={}", user_id)
        elif kind == "message_created":
            sender = (update.get("message") or {}).get("sender") or {}
            user_id = str(sender.get("user_id") or "")
            if user_id and not sender.get("is_bot"):
                await send_welcome(state, user_id)
    except Exception as exc:  # фоновая задача не должна ронять процесс
        logger.error("Ошибка обработки события MAX: {}", type(exc).__name__)


@router.post("/webhook", dependencies=[Depends(require_max_webhook_secret)])
async def max_webhook(request: Request, background: BackgroundTasks) -> dict:
    state = request.app.state
    try:
        update = await request.json()
    except ValueError:
        return {"status": "ok"}
    key = event_key(update)
    if key:
        with session_scope(state.session_factory) as session:
            if not mark_processed(session, key):
                return {"status": "ok"}
    logger.info("Событие MAX: {}", update.get("update_type"))
    background.add_task(process, state, update)
    return {"status": "ok"}
