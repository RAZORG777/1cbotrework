"""Вебхук MAX (contracts/messenger-webhooks.md).

Ответ 200 отдаётся сразу, обработка — в фоне (MAX повторяет доставку при долгом ответе).
Нажатия кнопок приходят событием `message_callback`: payload и пользователь — в `callback`;
обработка кнопок напоминания — app/visit_actions.py (этап 2).
Сырые апдейты в журнал не пишутся.
"""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, Request
from loguru import logger

from .. import keyboards, metrics, subscribers, texts
from ..auth import require_max_webhook_secret
from ..db import mark_processed, session_scope
from ..visit_actions import handle_button, parse_callback

router = APIRouter()


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


def first_name_of(user: dict) -> str:
    """Имя из профиля MAX: first_name или первое слово name."""
    name = (user.get("first_name") or user.get("name") or "").strip()
    return name.split()[0] if name else ""


async def send_news_question(state, user_id: str) -> None:
    await state.messenger.send_message(user_id, texts.NEWS_QUESTION, keyboards.news_question())


async def send_welcome(state, user_id: str, first_name: str = "") -> None:
    """Приветствие; вопрос о новостях — если пользователь ещё не отвечал (specs/007-broadcasts)."""
    with session_scope(state.session_factory) as session:
        subscribers.touch(session, user_id)
        ask = subscribers.needs_question(session, user_id)
    await state.messenger.send_message(
        user_id,
        texts.welcome(first_name),
        keyboards.welcome(state.settings.MAX_MINIAPP, texts.SITE_URL),
    )
    if ask:
        await send_news_question(state, user_id)


NEWS_ANSWERS = {
    keyboards.NEWS_YES: (True, texts.NEWS_YES),
    keyboards.NEWS_NO: (False, texts.NEWS_NO),
    keyboards.NEWS_OFF: (False, texts.UNSUBSCRIBED),
}


async def handle_news(state, update: dict, callback_id: str, user_id: str, payload: str) -> None:
    """Ответ на вопрос о новостях или «Отписаться» из рассылки."""
    consent, reply = NEWS_ANSWERS[payload]
    with session_scope(state.session_factory) as session:
        subscribers.set_consent(session, user_id, consent)
    if payload == keyboards.NEWS_OFF:
        await state.messenger.answer_callback(callback_id, texts.NOTICE_NEWS_SAVED)
        await state.messenger.send_message(user_id, reply)
        return
    # Вопрос заменяется ответом — кнопки исчезают.
    original = ((update.get("message") or {}).get("body") or {}).get("text") or ""
    text = f"{original}\n\n{reply}" if original else reply
    await state.messenger.answer_callback(
        callback_id, texts.NOTICE_NEWS_SAVED, {"text": text, "format": "html", "attachments": []}
    )


async def handle_callback(state, update: dict) -> None:
    """Кнопки напоминания (этап 2). Финальный исход заменяет сообщение — кнопки исчезают."""
    metrics.inc("callbacks")
    callback = update.get("callback") or {}
    callback_id = str(callback.get("callback_id") or "")
    user_id = str((callback.get("user") or {}).get("user_id") or "")
    if not user_id:
        return
    payload = str(callback.get("payload") or "")
    if payload in NEWS_ANSWERS:
        await handle_news(state, update, callback_id, user_id, payload)
        return
    parsed = parse_callback(payload)
    if parsed is None:
        await state.messenger.answer_callback(callback_id)
        return
    action, appointment_id = parsed
    outcome = await handle_button(state, user_id, action, appointment_id)
    if outcome.remove_buttons:
        original = ((update.get("message") or {}).get("body") or {}).get("text") or ""
        text = f"{original}\n\n{outcome.text}" if original else outcome.text
        await state.messenger.answer_callback(
            callback_id, outcome.notice, {"text": text, "format": "html", "attachments": []}
        )
    else:
        await state.messenger.answer_callback(callback_id, outcome.notice)
        await state.messenger.send_message(user_id, outcome.text)


async def process(state, update: dict) -> None:
    try:
        kind = update.get("update_type")
        if kind == "message_callback":
            await handle_callback(state, update)
        elif kind == "bot_started":
            user_id = str(update.get("user_id") or (update.get("user") or {}).get("user_id") or "")
            if user_id:
                await send_welcome(state, user_id, first_name_of(update.get("user") or {}))
                logger.info("bot_started: user_id={}", user_id)
        elif kind == "message_created":
            sender = (update.get("message") or {}).get("sender") or {}
            user_id = str(sender.get("user_id") or "")
            if user_id and not sender.get("is_bot"):
                body = (update.get("message") or {}).get("body") or {}
                if str(body.get("text") or "").strip().startswith("/news"):
                    with session_scope(state.session_factory) as session:
                        subscribers.touch(session, user_id)
                    await send_news_question(state, user_id)
                else:
                    await send_welcome(state, user_id, first_name_of(sender))
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
    metrics.inc("webhook_updates")
    background.add_task(process, state, update)
    return {"status": "ok"}
