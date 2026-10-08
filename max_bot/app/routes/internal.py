"""Сигналы 1С → бот (contracts/onec-signals.md): только с секретом, идемпотентно."""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, Request
from loguru import logger
from pydantic import BaseModel, Field
from sqlalchemy import select

from .. import keyboards, texts
from ..auth import require_onec_secret
from ..db import mark_processed, now_msk, session_scope
from ..doctors_enricher import find_prodoctorov_url
from ..models import STATUS_ACTIVE, STATUS_CANCELLED, STATUS_FINISHED, Appointment, ProcessedEvent
from ..reminders import remove_reminders, schedule_feedback
from .webapp import user_cancelling

router = APIRouter(prefix="/api/v1/internal", dependencies=[Depends(require_onec_secret)])

REVIEWS_LINKS = {
    "Профсоюзная": "https://yandex.ru/maps/213/moscow/?ll=37.543560%2C55.660760&mode=poi&poi%5Bpoint%5D=37.543529%2C55.660638&poi%5Buri%5D=ymapsbm1%3A%2F%2Forg%3Foid%3D196039112145&z=17",
    "Новые Ватутинки": "https://yandex.ru/maps/213/moscow/?indoorLevel=1&ll=37.345203%2C55.518301&mode=poi&poi%5Bpoint%5D=37.344904%2C55.518219&poi%5Buri%5D=ymapsbm1%3A%2F%2Forg%3Foid%3D200998099919&z=17",
}


class Signal(BaseModel):
    appointment_id: str = Field(min_length=1)


def _already(session, key: str) -> bool:
    return session.scalar(select(ProcessedEvent).where(ProcessedEvent.key == key)) is not None


def review_link(appt: Appointment) -> str:
    """Отзыв о враче на ПроДокторов, если он там есть; иначе о филиале на Яндекс Картах."""
    link = find_prodoctorov_url((appt.doctor_name or "").strip())
    if link:
        return link
    key = "Новые Ватутинки" if "Ватутинки" in (appt.branch or "") else "Профсоюзная"
    return REVIEWS_LINKS[key]


def feedback_text(appt: Appointment) -> str:
    return texts.feedback(appt)


@router.post("/cancel-visit")
async def cancel_visit(signal: Signal, request: Request, background: BackgroundTasks) -> dict:
    state = request.app.state
    key = f"onec:cancel:{signal.appointment_id}"
    with session_scope(state.session_factory) as session:
        appt = session.scalar(
            select(Appointment).where(
                Appointment.appointment_id == signal.appointment_id,
                Appointment.status == STATUS_ACTIVE,
            )
        )
        if appt is None:
            return {"status": "success"} if _already(session, key) else {"status": "not_found"}
        if not mark_processed(session, key):
            return {"status": "success"}
        appt.status = STATUS_CANCELLED
        appt.closed_at = now_msk()
        chat_id = appt.user_id
    remove_reminders(state.scheduler, signal.appointment_id)
    if signal.appointment_id in user_cancelling(state):
        # Отменил сам пациент (форма или кнопка напоминания): ему уже ответил бот.
        logger.info(
            "Сигнал 1С cancel-visit на отмену пациента: appointment_id={}", signal.appointment_id
        )
        return {"status": "success"}
    background.add_task(
        state.messenger.send_message,
        chat_id,
        texts.cancelled_by_admin(appt),
        keyboards.book_again(state.settings.MAX_MINIAPP),
    )
    logger.info("Сигнал 1С cancel-visit: appointment_id={}", signal.appointment_id)
    return {"status": "success"}


@router.post("/finish-visit")
async def finish_visit(signal: Signal, request: Request) -> dict:
    state = request.app.state
    key = f"onec:finish:{signal.appointment_id}"
    now = now_msk()
    with session_scope(state.session_factory) as session:
        appt = session.scalar(
            select(Appointment).where(
                Appointment.appointment_id == signal.appointment_id,
                Appointment.status == STATUS_ACTIVE,
            )
        )
        if appt is None:
            return {"status": "success"} if _already(session, key) else {"status": "not_found"}
        if not mark_processed(session, key):
            return {"status": "success"}
        appt.status = STATUS_FINISHED
        appt.closed_at = now
        text = feedback_text(appt)
        review = keyboards.review(review_link(appt))
        chat_id = appt.user_id
    remove_reminders(state.scheduler, signal.appointment_id)
    schedule_feedback(state.scheduler, signal.appointment_id, chat_id, text, now, review)
    logger.info("Сигнал 1С finish-visit: appointment_id={}", signal.appointment_id)
    return {"status": "success"}
