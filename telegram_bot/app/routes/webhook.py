"""Вебхук Telegram (contracts/messenger-webhooks.md). Сырые апдейты в журнал не пишутся."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from loguru import logger
from sqlalchemy import func, select

from .. import keyboards, texts
from ..auth import require_tg_webhook_secret
from ..db import mark_processed, session_scope
from ..models import STATUS_ACTIVE, Appointment
from ..visit_actions import handle_button, parse_callback

router = APIRouter()


async def handle_callback(state, query: dict) -> None:
    """Кнопки напоминания (этап 2); прочие нажатия только подтверждаются."""
    query_id = str(query.get("id", ""))
    parsed = parse_callback(str(query.get("data") or ""))
    user_id = str((query.get("from") or {}).get("id") or "")
    if parsed is None or not user_id:
        await state.messenger.answer_callback(query_id)
        return
    action, appointment_id = parsed
    outcome = await handle_button(state, user_id, action, appointment_id)
    await state.messenger.answer_callback(query_id, outcome.notice)
    message = query.get("message") or {}
    chat_id = str((message.get("chat") or {}).get("id") or user_id)
    if outcome.remove_buttons and message.get("message_id") is not None:
        await state.messenger.edit_reply_markup(chat_id, message["message_id"])
    await state.messenger.send_message(chat_id, outcome.text)


@router.post("/admin/webhook", dependencies=[Depends(require_tg_webhook_secret)])
async def telegram_webhook(request: Request) -> dict:
    state = request.app.state
    settings = state.settings
    try:
        update = await request.json()
    except ValueError:
        return {"status": "ok"}
    update_id = update.get("update_id")
    if update_id is not None:
        with session_scope(state.session_factory) as session:
            if not mark_processed(session, f"tg:{update_id}"):
                return {"status": "ok"}

    try:
        if "callback_query" in update:
            await handle_callback(state, update["callback_query"])
            return {"status": "ok"}

        message = update.get("message") or {}
        chat_id = str((message.get("chat") or {}).get("id", ""))
        text = message.get("text") or ""
        if not chat_id:
            return {"status": "ok"}

        if text.startswith("/start"):
            first_name = (message.get("from") or {}).get("first_name")
            await state.messenger.send_message(
                chat_id,
                texts.welcome(first_name),
                keyboards.welcome(settings.WEBAPP_URL, settings.WEBAPP_URL2),
            )
            logger.info("/start: chat_id={}", chat_id)
        elif text.startswith("/stats") and chat_id in settings.admin_ids:
            with session_scope(state.session_factory) as session:
                active = session.scalar(
                    select(func.count())
                    .select_from(Appointment)
                    .where(Appointment.status == STATUS_ACTIVE)
                )
            jobs = len(state.scheduler.get_jobs())
            await state.messenger.send_message(
                chat_id,
                "<b>Панель управления (Telegram)</b>\n\n"
                f"Активных записей: <b>{active}</b>\nЗапланированных задач: <b>{jobs}</b>",
            )
    except Exception as exc:  # вебхук всегда отвечает 200, чтобы Telegram не повторял
        logger.error("Ошибка обработки вебхука: {}", type(exc).__name__)
    return {"status": "ok"}
