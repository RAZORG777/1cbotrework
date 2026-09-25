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
