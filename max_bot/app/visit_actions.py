"""Кнопки напоминания «Подтверждаю / Отменить» (этап 2, specs/003-visit-confirmation).

Кнопка действует только на свою запись: UUID заявки из кнопки должен совпадать с активной записью
пользователя (R3). Исходы — data-model.md › «Исходы нажатия». В журнал — только идентификаторы.
"""

from __future__ import annotations

from dataclasses import dataclass

from loguru import logger
from sqlalchemy import select

from .db import now_msk, session_scope
from .models import STATUS_CANCELLED, Appointment
from .onec_client import OneCError
from .reminders import remove_reminders
from .routes.webapp import active_for, cancel_for_user, cancelled_text

PLATFORM = "max"
NOT_ACTUAL = "Эта запись изменена или уже неактуальна. Актуальное напоминание придёт отдельно."


RETRY_LATER = "⚠️ Не удалось связаться с клиникой. Попробуйте нажать кнопку ещё раз чуть позже."


@dataclass
class Outcome:
    text: str  # сообщение пациенту
    notice: str  # короткое всплывающее уведомление на кнопке
    remove_buttons: bool  # убрать кнопки у напоминания (финальный исход)
    result: str  # для журнала


def _find(state, user_id: str, appointment_id: str | None):
    """Активная запись пользователя, если кнопка относится к ней; иначе None."""
    with session_scope(state.session_factory) as session:
        appt = active_for(session, user_id)
        if appt is None or (appointment_id and appt.appointment_id != appointment_id):
            return None
        return appt.appointment_id, appt.fio_short


def _close_cancelled(state, appointment_id: str) -> None:
    with session_scope(state.session_factory) as session:
        appt = session.scalar(
            select(Appointment).where(Appointment.appointment_id == appointment_id)
        )
        if appt is not None and appt.status != STATUS_CANCELLED:
            appt.status = STATUS_CANCELLED
            appt.closed_at = now_msk()
    remove_reminders(state.scheduler, appointment_id)


async def confirm_visit(state, user_id: str, appointment_id: str | None) -> Outcome:
    found = _find(state, user_id, appointment_id)
    if found is None:
        return Outcome(NOT_ACTUAL, "Запись неактуальна", True, "not_actual")
    appt_id, _ = found
    try:
        response = await state.onec.confirm(appt_id, PLATFORM)
    except OneCError:
        return Outcome(RETRY_LATER, "Не удалось, попробуйте позже", False, "onec_unavailable")

    if response.get("status") == "success":
        with session_scope(state.session_factory) as session:
            appt = active_for(session, user_id)
            if appt is not None and appt.confirmed_at is None:
                appt.confirmed_at = now_msk()
        if response.get("already"):
            return Outcome(
                "Ваш визит уже подтверждён. Ждём вас! 🏥", "Уже подтверждено", True, "already"
            )
        return Outcome(
            "✅ <b>Спасибо! Ваш визит подтверждён.</b> Ждём вас в клинике «ЯСНО ВИЖУ»!",
            "Визит подтверждён",
            True,
            "confirmed",
        )
    code = str(response.get("code") or "")
    if code in ("CANCELLED", "NOT_FOUND"):
        _close_cancelled(state, appt_id)
        return Outcome("🚫 Эта запись уже отменена.", "Запись отменена", True, code.lower())
    return Outcome(RETRY_LATER, "Не удалось, попробуйте позже", False, f"onec_{code or 'error'}")


async def cancel_visit(state, user_id: str, appointment_id: str | None) -> Outcome:
    found = _find(state, user_id, appointment_id)
    if found is None:
        return Outcome(NOT_ACTUAL, "Запись неактуальна", True, "not_actual")
    _, fio = found
    result = await cancel_for_user(state, user_id)
    if isinstance(result, dict):
        return Outcome(cancelled_text(fio), "Запись отменена", True, "cancelled")
    return Outcome(
        "⚠️ Не удалось отменить запись. Попробуйте ещё раз или позвоните в клинику.",
        "Не удалось отменить",
        False,
        "cancel_failed",
    )


LEGACY_PAYLOADS = {"confirm_visit": "confirm", "cancel_visit_btn": "cancel"}


def parse_callback(payload: str) -> tuple[str, str | None] | None:
    """`confirm:<uuid>` / `cancel:<uuid>`; прежние `confirm_visit` / `cancel_visit_btn` —
    по активной записи (FR-008), идентификатор None."""
    if payload in LEGACY_PAYLOADS:
        return LEGACY_PAYLOADS[payload], None
    action, _, appointment_id = (payload or "").partition(":")
    if action in ("confirm", "cancel") and appointment_id:
        return action, appointment_id
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
