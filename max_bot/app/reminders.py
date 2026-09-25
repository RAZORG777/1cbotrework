"""Напоминания, просьба об отзыве и ежедневная очистка ПДн (FR-005–FR-008, R8)."""

from __future__ import annotations

from datetime import datetime, timedelta

from apscheduler.jobstores.base import JobLookupError
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from loguru import logger
from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session, sessionmaker

from .db import MSK, now_msk, session_scope
from .models import (
    STATUS_ACTIVE,
    STATUS_CANCELLED,
    STATUS_FINISHED,
    Appointment,
    ProcessedEvent,
)

REMINDER_PREFIXES = ("rem24h_", "rem2h_")
FEEDBACK_DELAY = timedelta(minutes=20)
PROCESSED_EVENTS_TTL = timedelta(days=7)

# Зависимости для заданий планировщика. Задания хранятся в БД (pickle), поэтому вызывают
# функции уровня модуля, а те берут отправителя и настройки отсюда.
_runtime: dict = {}


def set_runtime(**kwargs) -> None:
    _runtime.update(kwargs)


async def deliver(chat_id: str, text: str, keyboard: list | None = None) -> None:
    messenger = _runtime.get("messenger")
    if messenger is None:
        logger.error("deliver: отправитель не настроен")
        return
    await messenger.send_message(chat_id, text, keyboard)


async def retention_job() -> None:
    factory = _runtime.get("session_factory")
    settings = _runtime.get("settings")
    if factory is None or settings is None:
        return
    with session_scope(factory) as session:
        run_retention(session, settings.PD_RETENTION_DAYS, now_msk())


def make_scheduler(db_url: str) -> AsyncIOScheduler:
    return AsyncIOScheduler(jobstores={"default": SQLAlchemyJobStore(url=db_url)}, timezone=MSK)


CONFIRM_KEYBOARD = [
    [{"type": "callback", "text": "✅ Подтверждаю", "payload": "confirm_visit"}],
    [{"type": "callback", "text": "❌ Отменить", "payload": "cancel_visit_btn"}],
]


def schedule_reminders(scheduler: AsyncIOScheduler, appt: Appointment, now: datetime) -> int:
    """Напоминания за 24 ч (с кнопками подтверждения) и 2 ч. Тексты — как в прежней версии."""
    if not appt.notify:
        return 0
    fio = appt.fio_short
    plan = [
        (
            "rem24h_",
            timedelta(hours=24),
            f"<b>{fio}</b>,\n🔔 Напоминаем: завтра в <b>{appt.time_str}</b> вы записаны в клинику "
            f"«ЯСНО ВИЖУ».\n🏥 Филиал: {appt.branch}\n👨‍⚕️ Врач: {appt.doctor_name}\n\n"
            "Пожалуйста, подтвердите визит 👇",
            CONFIRM_KEYBOARD,
        ),
        (
            "rem2h_",
            timedelta(hours=2),
            f"<b>{fio}</b>,\n🔔 Напоминаем: через 2 часа у вас прием в клинике «ЯСНО ВИЖУ».\n"
            f"🏥 Филиал: {appt.branch}\n👨‍⚕️ Врач: {appt.doctor_name}",
            None,
        ),
    ]
    count = 0
    for prefix, delta, text, keyboard in plan:
        run_at = appt.visit_at - delta
        if run_at > now:
            scheduler.add_job(
                deliver,
                "date",
                run_date=run_at,
                args=[appt.user_id, text, keyboard],
                id=f"{prefix}{appt.appointment_id}",
                replace_existing=True,
            )
            count += 1
    return count


def remove_reminders(scheduler: AsyncIOScheduler, appointment_id: str) -> None:
    for prefix in REMINDER_PREFIXES:
        try:
            scheduler.remove_job(f"{prefix}{appointment_id}")
        except JobLookupError:
            pass


def schedule_feedback(
    scheduler: AsyncIOScheduler, appointment_id: str, chat_id: str, text: str, now: datetime
) -> None:
    scheduler.add_job(
        deliver,
        "date",
        run_date=now + FEEDBACK_DELAY,
        args=[chat_id, text],
        id=f"feedback_{appointment_id}",
        replace_existing=True,
    )


def restore_reminders(scheduler: AsyncIOScheduler, session: Session, now: datetime) -> int:
    total = 0
    for appt in session.scalars(select(Appointment).where(Appointment.status == STATUS_ACTIVE)):
        total += schedule_reminders(scheduler, appt, now)
    return total


def run_retention(session: Session, retention_days: int, now: datetime) -> dict:
    """1) прошедшие активные → finished; 2) закрытые старше срока — удалить; 3) старые события."""
    finished = session.execute(
        update(Appointment)
        .where(Appointment.status == STATUS_ACTIVE, Appointment.visit_at < now - timedelta(days=1))
        .values(status=STATUS_FINISHED, closed_at=Appointment.visit_at)
    ).rowcount
    deleted = session.execute(
        delete(Appointment).where(
            Appointment.status.in_([STATUS_CANCELLED, STATUS_FINISHED]),
            Appointment.closed_at < now - timedelta(days=retention_days),
        )
    ).rowcount
    events = session.execute(
        delete(ProcessedEvent).where(ProcessedEvent.created_at < now - PROCESSED_EVENTS_TTL)
    ).rowcount
    if finished or deleted or events:
        logger.info(
            "Очистка: завершено {}, удалено записей {}, удалено событий {}",
            finished,
            deleted,
            events,
        )
    return {"finished": finished, "deleted": deleted, "events": events}


def register_retention(scheduler: AsyncIOScheduler) -> None:
    scheduler.add_job(
        retention_job,
        "cron",
        hour=3,
        minute=30,
        id="retention_cleanup",
        replace_existing=True,
        misfire_grace_time=3600,
        coalesce=True,
    )


def run_retention_now(factory: sessionmaker[Session], retention_days: int) -> None:
    with session_scope(factory) as session:
        run_retention(session, retention_days, now_msk())
