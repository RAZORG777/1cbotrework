"""Модель данных бота (data-model.md). Источник истины по записи — 1С."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Index, Integer, String, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

STATUS_ACTIVE = "active"
STATUS_CANCELLED = "cancelled"
STATUS_FINISHED = "finished"


class Base(DeclarativeBase):
    pass


class Appointment(Base):
    __tablename__ = "appointments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[str] = mapped_column(String, index=True)
    platform: Mapped[str] = mapped_column(String, default="max")
    appointment_id: Mapped[str] = mapped_column(String, index=True)
    branch: Mapped[str] = mapped_column(String, default="")
    doctor_id: Mapped[str] = mapped_column(String, default="")
    doctor_name: Mapped[str] = mapped_column(String, default="")
    service_id: Mapped[str] = mapped_column(String, default="")
    service_name: Mapped[str] = mapped_column(String, default="")
    visit_at: Mapped[datetime] = mapped_column(DateTime)
    first_name: Mapped[str] = mapped_column(String, default="")
    last_name: Mapped[str] = mapped_column(String, default="")
    middle_name: Mapped[str] = mapped_column(String, default="")
    phone: Mapped[str] = mapped_column(String, default="")
    birth_date: Mapped[str] = mapped_column(String, default="")
    notify: Mapped[bool] = mapped_column(Boolean, default=True)
    status: Mapped[str] = mapped_column(String, default=STATUS_ACTIVE)
    created_at: Mapped[datetime] = mapped_column(DateTime)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # Этап 2: пациент подтвердил визит кнопкой напоминания (сбрасывается при переносе).
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    __table_args__ = (
        Index(
            "ux_appointments_active_user",
            "user_id",
            unique=True,
            sqlite_where=text("status = 'active'"),
        ),
        Index("ix_appointments_status_closed", "status", "closed_at"),
    )

    @property
    def date_str(self) -> str:
        return self.visit_at.strftime("%Y-%m-%d")

    @property
    def time_str(self) -> str:
        return self.visit_at.strftime("%H:%M")

    @property
    def fio_short(self) -> str:
        return f"{self.first_name} {self.middle_name}".strip()


class ProcessedEvent(Base):
    __tablename__ = "processed_events"

    key: Mapped[str] = mapped_column(String, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime)


# --- Рассылки (specs/007-broadcasts) -------------------------------------------------------


class Subscriber(Base):
    """Пользователь бота: только id мессенджера и даты, без ФИО и телефона."""

    __tablename__ = "subscribers"

    user_id: Mapped[str] = mapped_column(String, primary_key=True)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime)
    # None — не спрашивали, True — согласен на новости и акции, False — отказался.
    news_consent: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    consent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    blocked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class Broadcast(Base):
    __tablename__ = "broadcasts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime)
    created_by: Mapped[str] = mapped_column(String, default="")
    kind: Mapped[str] = mapped_column(String)  # service | promo
    audience: Mapped[str] = mapped_column(String)  # all | active | branch
    branch: Mapped[str] = mapped_column(String, default="")
    text: Mapped[str] = mapped_column(String)
    image: Mapped[str] = mapped_column(String, default="")
    button_type: Mapped[str] = mapped_column(String, default="none")  # none | book | url
    button_text: Mapped[str] = mapped_column(String, default="")
    button_url: Mapped[str] = mapped_column(String, default="")
    status: Mapped[str] = mapped_column(String, default="sending")  # sending | done | stopped
    total: Mapped[int] = mapped_column(Integer, default=0)
    sent: Mapped[int] = mapped_column(Integer, default=0)
    failed: Mapped[int] = mapped_column(Integer, default=0)
    blocked: Mapped[int] = mapped_column(Integer, default=0)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class BroadcastRecipient(Base):
    """Получатели фиксируются при запуске; строки удаляются по завершении рассылки."""

    __tablename__ = "broadcast_recipients"

    broadcast_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[str] = mapped_column(String, primary_key=True)
    state: Mapped[str] = mapped_column(
        String, default="pending"
    )  # pending | sent | failed | blocked
