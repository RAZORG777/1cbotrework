"""Дневные счётчики, воронка формы записи и ежедневная сводка (specs/008-daily-report-funnel).

Модуль одинаков в обоих ботах. В БД — только числа и хэши id (FR-001, FR-002).
"""

from __future__ import annotations

import hashlib
from datetime import date, datetime, timedelta

from loguru import logger
from sqlalchemy import delete, func, select
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.orm import Session

from . import texts
from .db import now_msk, session_scope
from .models import STATUS_ACTIVE, Appointment, DailyStat, FunnelMark

EVENTS = (
    ("booked", "Новых записей"),
    ("rescheduled", "Переносов"),
    ("cancelled_patient", "Отменили пациенты"),
    ("cancelled_clinic", "Отменила клиника"),
    ("confirmed", "Подтвердили визит"),
    ("visited", "Пришли на приём"),
    ("new_users", "Новых пользователей"),
)
FUNNEL = (
    ("open", "Открыли форму"),
    ("branch", "Выбрали филиал"),
    ("doctor", "Выбрали врача и услугу"),
    ("time", "Выбрали время"),
    ("submit", "Отправили данные"),
    ("booked", "Записались"),
)
# Шаги, которые отмечает сама форма; submit и booked — сервер.
CLIENT_STEPS = ("open", "branch", "doctor", "time")
KEEP_DAYS = 400
EVENT_NAMES = {name for name, _ in EVENTS}
STEP_NAMES = {name for name, _ in FUNNEL}


def _day(when: datetime | date | None = None) -> str:
    when = when or now_msk()
    return when.strftime("%Y-%m-%d")


def inc(session: Session, name: str, value: int = 1, when: datetime | None = None) -> None:
    """Прибавить к счётчику дня. Ошибка счётчика не должна ломать основное действие."""
    if name not in EVENT_NAMES and not name.startswith("funnel:"):
        raise ValueError(f"неизвестный счётчик {name}")
    stmt = insert(DailyStat).values(day=_day(when), name=name, value=value)
    session.execute(
        stmt.on_conflict_do_update(
            index_elements=["day", "name"], set_={"value": DailyStat.value + value}
        )
    )


def _uid(user_id: str) -> str:
    return hashlib.sha256(f"yasno-funnel:{user_id}".encode()).hexdigest()[:20]


def mark_step(session: Session, user_id: str, step: str, when: datetime | None = None) -> bool:
    """Шаг воронки: считается один раз на пользователя за день. True — отмечен впервые."""
    if step not in STEP_NAMES:
        raise ValueError(f"неизвестный шаг {step}")
    day = _day(when)
    added = session.execute(
        insert(FunnelMark)
        .values(day=day, step=step, uid=_uid(user_id))
        .on_conflict_do_nothing(index_elements=["day", "step", "uid"])
    ).rowcount
    if added:
        inc(session, f"funnel:{step}", when=when)
    return bool(added)


def safe(fn, *args, **kwargs) -> None:
    """Вызов счётчика в отдельной транзакции: сбой статистики только в журнал."""
    try:
        fn(*args, **kwargs)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Статистика: не удалось записать ({})", type(exc).__name__)


def add(session: Session, name: str) -> None:
    """Счётчик внутри чужой транзакции — через точку сохранения, чтобы сбой её не откатил."""
    try:
        with session.begin_nested():
            inc(session, name)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Статистика: не удалось записать ({})", type(exc).__name__)


def record(factory, name: str) -> None:
    def _run() -> None:
        with session_scope(factory) as session:
            inc(session, name)

    safe(_run)


def record_step(factory, user_id: str, step: str) -> None:
    def _run() -> None:
        with session_scope(factory) as session:
            mark_step(session, user_id, step)

    safe(_run)


def collect(session: Session, days: int, today: date | None = None) -> dict:
    """Итоги за последние `days` дней, включая сегодня."""
    today = today or now_msk().date()
    start = today - timedelta(days=days - 1)
    rows = session.execute(
        select(DailyStat.day, DailyStat.name, DailyStat.value).where(
            DailyStat.day >= _day(start), DailyStat.day <= _day(today)
        )
    ).all()
    by_day: dict[str, dict[str, int]] = {}
    totals: dict[str, int] = {}
    for day, name, value in rows:
        by_day.setdefault(day, {})[name] = value
        totals[name] = totals.get(name, 0) + value
    day_list = []
    for i in range(days):
        day = _day(today - timedelta(days=i))
        values = by_day.get(day, {})
        day_list.append({"day": day, **{name: values.get(name, 0) for name, _ in EVENTS}})
    return {
        "days": day_list,
        "totals": {name: totals.get(name, 0) for name, _ in EVENTS},
        "funnel": [
            {"step": step, "title": title, "count": totals.get(f"funnel:{step}", 0)}
            for step, title in FUNNEL
        ],
        "events": [{"name": name, "title": title} for name, title in EVENTS],
    }


def visits_on(session: Session, day: date) -> int:
    start = datetime.combine(day, datetime.min.time())
    return session.scalar(
        select(func.count())
        .select_from(Appointment)
        .where(
            Appointment.status == STATUS_ACTIVE,
            Appointment.visit_at >= start,
            Appointment.visit_at < start + timedelta(days=1),
        )
    )


def report_text(session: Session, platform_title: str, now: datetime | None = None) -> str:
    now = now or now_msk()
    data = collect(session, 1, now.date())
    totals = data["totals"]
    funnel = {f["step"]: f["count"] for f in data["funnel"]}
    lines = [f"<b>Сводка за {texts.day_month(now.date())}</b> · {platform_title}", ""]
    lines += [f"{title}: {totals[name]}" for name, title in EVENTS]
    opened, booked = funnel["open"], funnel["booked"]
    share = f" ({round(booked * 100 / opened)}%)" if opened else ""
    lines += [
        "",
        f"Форма записи: открыли {opened}, записались {booked}{share}",
        f"Записей на завтра: {visits_on(session, now.date() + timedelta(days=1))}",
    ]
    return "\n".join(lines)


def cleanup(session: Session, now: datetime) -> dict:
    """Отметки воронки прошлых дней и итоги старше KEEP_DAYS."""
    marks = session.execute(delete(FunnelMark).where(FunnelMark.day < _day(now))).rowcount
    old = session.execute(
        delete(DailyStat).where(DailyStat.day < _day(now - timedelta(days=KEEP_DAYS)))
    ).rowcount
    return {"marks": marks, "stats": old}
