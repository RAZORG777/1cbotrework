"""Вебхук Telegram (contracts/messenger-webhooks.md). Сырые апдейты в журнал не пишутся."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from loguru import logger
from sqlalchemy import func, select

from ..auth import require_tg_webhook_secret
from ..db import mark_processed, session_scope
from ..models import STATUS_ACTIVE, Appointment

router = APIRouter()


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
            await state.messenger.answer_callback(str(update["callback_query"].get("id", "")))
            return {"status": "ok"}

        message = update.get("message") or {}
        chat_id = str((message.get("chat") or {}).get("id", ""))
        text = message.get("text") or ""
        if not chat_id:
            return {"status": "ok"}

        if text.startswith("/start"):
            first_name = (message.get("from") or {}).get("first_name") or "Гость"
            keyboard = {
                "inline_keyboard": [
                    [{"text": "Записаться ✅", "web_app": {"url": settings.WEBAPP_URL}}],
                    [{"text": "🌐 Наш сайт", "web_app": {"url": settings.WEBAPP_URL2}}],
                ]
            }
            await state.messenger.send_message(
                chat_id, "<i>Обновление меню...</i>", {"remove_keyboard": True}
            )
            await state.messenger.send_message(
                chat_id,
                f"Здравствуйте, {first_name}! 👋\n\nДобро пожаловать в бота клиники «ЯСНО ВИЖУ».",
                keyboard,
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
                "⚙️ <b>Панель управления (Telegram)</b>\n\n"
                f"👥 Активных записей: <b>{active}</b>\n🕒 Запланированных задач: <b>{jobs}</b>",
            )
    except Exception as exc:  # вебхук всегда отвечает 200, чтобы Telegram не повторял
        logger.error("Ошибка обработки вебхука: {}", type(exc).__name__)
    return {"status": "ok"}
