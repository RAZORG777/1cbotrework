"""Кнопки напоминания «Подтверждаю / Отменить» (этап 2, specs/003-visit-confirmation).

Кнопка действует только на свою запись: UUID заявки из кнопки должен совпадать с активной записью
пользователя (R3). Исходы — data-model.md › «Исходы нажатия». В журнал — только идентификаторы.
"""

from __future__ import annotations

from dataclasses import dataclass

from loguru import logger
from sqlalchemy import select

from . import texts
from .db import now_msk, session_scope
from .models import STATUS_CANCELLED, Appointment
from .onec_client import OneCError
from .reminders import remove_reminders
from .routes.webapp import active_for, cancel_for_user

PLATFORM = "telegram"


@dataclass
class Outcome:
    text: str  # сообщение пациенту
    notice: str  # короткое всплывающее уведомление на кнопке
    remove_buttons: bool  # убрать кнопки у напоминания (финальный исход)
    result: str  # для журнала


def _find(state, user_id: str, appointment_id: str | None) -> Appointment | None:
    """Активная запись пользователя, если кнопка относится к ней; иначе None."""
    with session_scope(state.session_factory) as session:
        appt = active_for(session, user_id)
        if appt is None or (appointment_id and appt.appointment_id != appointment_id):
            return None
        return appt  # сессия без expire_on_commit: поля доступны после закрытия


def _close_cancelled(state, appointment_id: str) -> None:
    with session_scope(state.session_factory) as session:
        appt = session.scalar(
            select(Appointment).where(Appointment.appointment_id == appointment_id)
        )
        if appt is not None and appt.status != STATUS_CANCELLED:
            appt.status = STATUS_CANCELLED
            appt.closed_at = now_msk()
    remove_reminders(state.scheduler, appointment_id)


def _not_actual() -> Outcome:
    return Outcome(texts.NOT_ACTUAL, texts.NOTICE_NOT_ACTUAL, True, "not_actual")


async def confirm_visit(state, user_id: str, appointment_id: str | None) -> Outcome:
    appt = _find(state, user_id, appointment_id)
    if appt is None:
        return _not_actual()
    try:
        response = await state.onec.confirm(appt.appointment_id, PLATFORM)
    except OneCError:
        return Outcome(texts.RETRY_LATER, texts.NOTICE_RETRY, False, "onec_unavailable")

    if response.get("status") == "success":
        with session_scope(state.session_factory) as session:
            current = active_for(session, user_id)
            if current is not None and current.confirmed_at is None:
                current.confirmed_at = now_msk()
        if response.get("already"):
            return Outcome(texts.already_confirmed(appt), texts.NOTICE_ALREADY, True, "already")
        return Outcome(texts.confirmed(appt), texts.NOTICE_CONFIRMED, True, "confirmed")
    code = str(response.get("code") or "")
    if code in ("CANCELLED", "NOT_FOUND"):
        _close_cancelled(state, appt.appointment_id)
        return Outcome(texts.ALREADY_CANCELLED, texts.NOTICE_CANCELLED, True, code.lower())
    return Outcome(texts.RETRY_LATER, texts.NOTICE_RETRY, False, f"onec_{code or 'error'}")


async def cancel_visit(state, user_id: str, appointment_id: str | None) -> Outcome:
    appt = _find(state, user_id, appointment_id)
    if appt is None:
        return _not_actual()
    result = await cancel_for_user(state, user_id)
    if isinstance(result, dict):
        return Outcome(texts.cancelled_by_patient(appt), texts.NOTICE_CANCELLED, True, "cancelled")
    return Outcome(texts.CANCEL_FAILED, texts.NOTICE_CANCEL_FAILED, False, "cancel_failed")


def parse_callback(data: str) -> tuple[str, str] | None:
    """`c:<uuid>` → ("confirm", uuid), `x:<uuid>` → ("cancel", uuid)."""
    action, _, appointment_id = (data or "").partition(":")
    if action in ("c", "x") and appointment_id:
        return ("confirm" if action == "c" else "cancel"), appointment_id
    return None


async def handle_button(state, user_id: str, action: str, appointment_id: str | None) -> Outcome:
    handler = confirm_visit if action == "confirm" else cancel_visit
    outcome = await handler(state, user_id, appointment_id)
    logger.info(
        "Кнопка напоминания: user_id={} действие={} appointment_id={} итог={}",
        user_id,
        action,
        appointment_id or "-",
        outcome.result,
    )
    return outcome
