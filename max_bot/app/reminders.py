"""Напоминания, просьба об отзыве и ежедневная очистка ПДн (FR-005–FR-008, R8)."""

from __future__ import annotations

from datetime import datetime, timedelta

from apscheduler.jobstores.base import JobLookupError
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from loguru import logger
from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session, sessionmaker

from . import keyboards, stats, texts
from .db import MSK, cleanup_backups, now_msk, session_scope
from .models import (
    STATUS_ACTIVE,
    STATUS_CANCELLED,
    STATUS_FINISHED,
    Appointment,
    ProcessedEvent,
    Subscriber,
)

REMINDER_PREFIXES = ("rem24h_", "rem2h_")
REPORT_TITLE = "MAX"
DAILY_REPORT_JOB = "daily_report"
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
    cleanup_backups(settings.db_file, settings.PD_RETENTION_DAYS)


def make_scheduler(db_url: str) -> AsyncIOScheduler:
    return AsyncIOScheduler(jobstores={"default": SQLAlchemyJobStore(url=db_url)}, timezone=MSK)


def reminder_keyboard(appointment_id: str, confirmed: bool, branch: str | None = None):
    """Кнопки напоминания (specs/005-bot-messages): «Подтвердить визит», «Отменить запись», «Как добраться»."""
    return keyboards.reminder(appointment_id, confirmed, branch)


def reminder_text(appt: Appointment, kind: str) -> str:
    """Текст напоминания (contracts/messages.md, п. 5–6)."""
    return texts.reminder(appt, kind, now_msk().date())


async def send_reminder(appointment_id: str, kind: str) -> None:
    """Задание напоминания: текст и кнопки — по записи на момент отправки (R4)."""
    factory = _runtime.get("session_factory")
    messenger = _runtime.get("messenger")
    if factory is None or messenger is None:
        logger.error("send_reminder: зависимости не настроены")
        return
    with session_scope(factory) as session:
        appt = session.scalar(
            select(Appointment).where(
                Appointment.appointment_id == appointment_id,
                Appointment.status == STATUS_ACTIVE,
            )
        )
        if appt is None or not appt.notify:
            return
        user_id = appt.user_id
        text = reminder_text(appt, kind)
        keyboard = reminder_keyboard(
            appt.appointment_id, appt.confirmed_at is not None, appt.branch
        )
    await messenger.send_message(user_id, text, keyboard)


def schedule_reminders(scheduler: AsyncIOScheduler, appt: Appointment, now: datetime) -> int:
    """Напоминания за 24 ч и 2 ч с кнопками «Подтвердить визит / Отменить запись» (этапы 2 и 5)."""
    if not appt.notify:
        return 0
    count = 0
    for prefix, delta, kind in (
        ("rem24h_", timedelta(hours=24), "24h"),
        ("rem2h_", timedelta(hours=2), "2h"),
    ):
        run_at = appt.visit_at - delta
        if run_at > now:
            scheduler.add_job(
                send_reminder,
                "date",
                run_date=run_at,
                args=[appt.appointment_id, kind],
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
    scheduler: AsyncIOScheduler,
    appointment_id: str,
    chat_id: str,
    text: str,
    now: datetime,
    keyboard=None,
) -> None:
    scheduler.add_job(
        deliver,
        "date",
        run_date=now + FEEDBACK_DELAY,
        args=[chat_id, text, keyboard],
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
    # Заблокировавшие бота пользователи (specs/007-broadcasts, FR-010).
    users = session.execute(
        delete(Subscriber).where(Subscriber.blocked_at < now - timedelta(days=retention_days))
    ).rowcount
    stats.cleanup(session, now)  # отметки воронки прошлых дней, итоги старше 400 дней
    if finished or deleted or events or users:
        logger.info(
            "Очистка: завершено {}, удалено записей {}, событий {}, пользователей {}",
            finished,
            deleted,
            events,
            users,
        )
    return {"finished": finished, "deleted": deleted, "events": events, "users": users}


async def send_daily_report(messenger, factory, settings) -> int:
    """Сводка за сегодня всем администраторам (specs/008-daily-report-funnel). Возвращает число
    доставленных сообщений."""
    with session_scope(factory) as session:
        text = stats.report_text(session, REPORT_TITLE)
    sent = 0
    for admin_id in sorted(settings.admin_ids):
        if await messenger.send_message(admin_id, text):
            sent += 1
    logger.info("Сводка за день: доставлено администраторам {}", sent)
    return sent


async def daily_report_job() -> None:
    messenger = _runtime.get("messenger")
    factory = _runtime.get("session_factory")
    settings = _runtime.get("settings")
    if messenger is None or factory is None or settings is None:
        return
    await send_daily_report(messenger, factory, settings)


def register_daily_report(scheduler: AsyncIOScheduler, report_time: str) -> None:
    if not report_time:
        try:
            scheduler.remove_job(DAILY_REPORT_JOB)
        except JobLookupError:
            pass
        return
    hour, minute = (int(x) for x in report_time.split(":"))
    scheduler.add_job(
        daily_report_job,
        "cron",
        hour=hour,
        minute=minute,
        id=DAILY_REPORT_JOB,
        replace_existing=True,
        misfire_grace_time=1800,
        coalesce=True,
    )


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
