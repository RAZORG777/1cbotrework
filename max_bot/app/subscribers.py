"""Список пользователей бота и согласие на новости (specs/007-broadcasts).

Хранится только id мессенджера и даты (FR-001). В журнал — только id.
"""

from __future__ import annotations

from loguru import logger
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .db import now_msk
from .models import Subscriber


def touch(session: Session, user_id: str) -> Subscriber:
    """Отметить, что пользователь пишет боту; новый — добавить. Снимает отметку блокировки."""
    now = now_msk()
    sub = session.get(Subscriber, user_id)
    if sub is None:
        sub = Subscriber(user_id=user_id, first_seen_at=now, last_seen_at=now)
        session.add(sub)
        session.flush()
        logger.info("Новый пользователь бота: user_id={}", user_id)
    else:
        sub.last_seen_at = now
        sub.blocked_at = None
    return sub


def needs_question(session: Session, user_id: str) -> bool:
    sub = session.get(Subscriber, user_id)
    return sub is None or sub.news_consent is None


def set_consent(session: Session, user_id: str, consent: bool) -> None:
    sub = touch(session, user_id)
    sub.news_consent = consent
    sub.consent_at = now_msk()
    logger.info("Новости: user_id={} согласие={}", user_id, "да" if consent else "нет")


def mark_blocked(session: Session, user_id: str) -> None:
    sub = session.get(Subscriber, user_id)
    if sub is not None and sub.blocked_at is None:
        sub.blocked_at = now_msk()
        logger.info("Пользователь заблокировал бота: user_id={}", user_id)


def stats(session: Session) -> dict:
    rows = session.execute(
        select(Subscriber.news_consent, Subscriber.blocked_at.is_(None), func.count()).group_by(
            Subscriber.news_consent, Subscriber.blocked_at.is_(None)
        )
    ).all()
    result = {"total": 0, "consent_yes": 0, "consent_no": 0, "not_asked": 0, "blocked": 0}
    for consent, reachable, n in rows:
        result["total"] += n
        if not reachable:
            result["blocked"] += n
            continue
        key = "not_asked" if consent is None else ("consent_yes" if consent else "consent_no")
        result[key] += n
    return result
