"""БД бота: engine, сессии, миграция схемы v0 → v1 (data-model.md › Миграция)."""

from __future__ import annotations

import shutil
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from loguru import logger
from sqlalchemy import create_engine, event, inspect, select, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from .models import STATUS_ACTIVE, STATUS_FINISHED, Base, ProcessedEvent

MSK = ZoneInfo("Europe/Moscow")
SCHEMA_VERSION = 1


def now_msk() -> datetime:
    """Текущее время по Москве без tzinfo — так же хранятся времена визитов из 1С."""
    return datetime.now(MSK).replace(tzinfo=None)


def make_engine(db_file: Path) -> Engine:
    engine = create_engine(f"sqlite:///{db_file}", connect_args={"check_same_thread": False})

    @event.listens_for(engine, "connect")
    def _pragma(dbapi_conn, _):  # pragma: no cover - служебное
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA journal_mode=WAL")
        cur.close()

    return engine


def make_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


@contextmanager
def session_scope(factory: sessionmaker[Session]) -> Iterator[Session]:
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def _user_version(conn) -> int:
    return conn.exec_driver_sql("PRAGMA user_version").scalar() or 0


def _parse_visit(date_s: str | None, time_s: str | None) -> datetime | None:
    try:
        return datetime.strptime(f"{date_s} {time_s}", "%Y-%m-%d %H:%M")
    except (TypeError, ValueError):
        return None


def _migrate_v0(engine: Engine, db_file: Path) -> None:
    """Старая схема: tg_id UNIQUE, date/time строками. Переносит строки в новую схему."""
    backup = db_file.with_name(db_file.name + ".bak-v0")
    if db_file.exists() and not backup.exists():
        shutil.copy2(db_file, backup)
    now = now_msk()
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    with engine.begin() as conn:
        conn.exec_driver_sql("ALTER TABLE appointments RENAME TO appointments_v0")
        Base.metadata.create_all(conn)
        rows = conn.exec_driver_sql("SELECT * FROM appointments_v0").mappings().all()
        moved = 0
        for row in rows:
            visit_at = _parse_visit(row.get("date"), row.get("time"))
            if visit_at is None:
                continue
            active = visit_at >= today
            conn.execute(
                text(
                    "INSERT INTO appointments (user_id, platform, appointment_id, branch, doctor_id,"
                    " doctor_name, service_id, service_name, visit_at, first_name, last_name,"
                    " middle_name, phone, birth_date, notify, status, created_at, closed_at)"
                    " VALUES (:user_id, :platform, :appointment_id, :branch, :doctor_id,"
                    " :doctor_name, :service_id, :service_name, :visit_at, :first_name, :last_name,"
                    " :middle_name, :phone, :birth_date, 1, :status, :created_at, :closed_at)"
                ),
                {
                    "user_id": str(row.get("tg_id") or ""),
                    "platform": row.get("platform") or "telegram",
                    "appointment_id": row.get("appointment_id") or "",
                    "branch": row.get("branch") or "",
                    "doctor_id": row.get("doctor_id") or "",
                    "doctor_name": row.get("doctor_name") or "",
                    "service_id": row.get("service_id") or "",
                    "service_name": row.get("service_name") or "",
                    "visit_at": visit_at,
                    "first_name": row.get("first_name") or "",
                    "last_name": row.get("last_name") or "",
                    "middle_name": row.get("middle_name") or "",
                    "phone": row.get("phone") or "",
                    "birth_date": row.get("birth_date") or "",
                    "status": STATUS_ACTIVE if active else STATUS_FINISHED,
                    "created_at": now,
                    "closed_at": None if active else visit_at,
                },
            )
            moved += 1
        conn.exec_driver_sql("DROP TABLE appointments_v0")
        # Задания старого кода ссылаются на удалённые функции — пересоздаются при старте.
        if inspect(conn).has_table("apscheduler_jobs"):
            conn.exec_driver_sql("DELETE FROM apscheduler_jobs")
        conn.exec_driver_sql(f"PRAGMA user_version = {SCHEMA_VERSION}")
    logger.info("Миграция БД v0 → v1: перенесено строк {}", moved)


def init_db(engine: Engine, db_file: Path) -> None:
    with engine.connect() as conn:
        version = _user_version(conn)
        insp = inspect(conn)
        old_schema = (
            version == 0
            and insp.has_table("appointments")
            and "tg_id" in {c["name"] for c in insp.get_columns("appointments")}
        )
    if old_schema:
        _migrate_v0(engine, db_file)
        return
    Base.metadata.create_all(engine)
    with engine.begin() as conn:
        if _user_version(conn) < SCHEMA_VERSION:
            conn.exec_driver_sql(f"PRAGMA user_version = {SCHEMA_VERSION}")


def mark_processed(session: Session, key: str) -> bool:
    """True — событие новое и отмечено; False — уже обрабатывалось (идемпотентность, R6)."""
    if session.scalar(select(ProcessedEvent).where(ProcessedEvent.key == key)):
        return False
    session.add(ProcessedEvent(key=key, created_at=now_msk()))
    try:
        session.flush()
    except IntegrityError:
        session.rollback()
        return False
    return True
