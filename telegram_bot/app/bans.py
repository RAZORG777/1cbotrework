"""Запрет онлайн-записи (specs/009-booking-ban).

Администратор запрещает пользователю записываться через бота, например после повторных неявок.
Пользователь видит в форме просьбу записаться по телефону; отменить уже созданную запись может.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .models import Appointment, BookingBan

REASON_MAX = 200


def is_banned(session: Session, user_id: str) -> bool:
    return session.get(BookingBan, str(user_id)) is not None


def banned_among(session: Session, user_ids: set[str]) -> set[str]:
    if not user_ids:
        return set()
    rows = session.scalars(select(BookingBan.user_id).where(BookingBan.user_id.in_(user_ids)))
    return set(rows)


def add(session: Session, user_id: str, reason: str, admin: str, now: datetime) -> bool:
    """True — новый запрет, False — обновлена причина существующего."""
    ban = session.get(BookingBan, user_id)
    if ban is not None:
        ban.reason = reason[:REASON_MAX]
        return False
    session.add(
        BookingBan(user_id=user_id, reason=reason[:REASON_MAX], created_at=now, created_by=admin)
    )
    return True


def remove(session: Session, user_id: str) -> bool:
    ban = session.get(BookingBan, user_id)
    if ban is None:
        return False
    session.delete(ban)
    return True


def list_all(session: Session) -> list[dict]:
    counts = dict(
        session.execute(
            select(Appointment.user_id, func.count())
            .where(Appointment.user_id.in_(select(BookingBan.user_id)))
            .group_by(Appointment.user_id)
        ).all()
    )
    bans = session.scalars(select(BookingBan).order_by(BookingBan.created_at.desc())).all()
    return [
        {
            "user_id": b.user_id,
            "reason": b.reason,
            "created_at": b.created_at.isoformat(timespec="seconds"),
            "created_by": b.created_by,
            "appointments": counts.get(b.user_id, 0),
        }
        for b in bans
    ]
