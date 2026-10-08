"""JSON API админки (specs/006-admin-devtool/contracts/admin-api.md).

Чтение — под Basic-авторизацией, изменения — ещё и с заголовком X-Admin-Request.
ФИО, телефоны и даты рождения пациентов в ответы не попадают (FR-012).
"""

from __future__ import annotations

import asyncio
import os
import platform
import re
import signal
from collections import Counter
from datetime import datetime, timedelta
from typing import Literal

from apscheduler.jobstores.base import JobLookupError
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse
from loguru import logger
from pydantic import BaseModel
from sqlalchemy import func, or_, select

from .. import admin_tools, metrics
from ..auth import require_admin, require_admin_action
from ..db import MSK, SCHEMA_VERSION, now_msk, session_scope
from ..logging import current_level, level_no, log_records, set_level, tail
from ..models import STATUS_ACTIVE, STATUS_CANCELLED, STATUS_FINISHED, Appointment
from ..reminders import (
    remove_reminders,
    run_retention,
    schedule_reminders,
    send_reminder,
)

router = APIRouter(prefix="/admin/api")
VERSION = "006"


def _not_found() -> HTTPException:
    return HTTPException(status_code=404, detail={"error": "NOT_FOUND"})


def _audit(admin: str, action: str, *args) -> None:
    metrics.inc("admin_actions")
    logger.info("Админка: " + action + " ({})", *args, admin)


def _iso(value: datetime | None) -> str | None:
    """Время по Москве без пояса, как времена визитов в БД."""
    if value is None:
        return None
    if value.tzinfo is not None:
        value = value.astimezone(MSK).replace(tzinfo=None)
    return value.isoformat(timespec="seconds")


# --- Обзор и здоровье ----------------------------------------------------------------------


@router.get("/overview")
async def overview(request: Request, admin: str = Depends(require_admin)) -> dict:
    state = request.app.state
    settings = state.settings
    with session_scope(state.session_factory) as session:
        counts = dict(
            session.execute(
                select(Appointment.status, func.count()).group_by(Appointment.status)
            ).all()
        )
        confirmed = session.scalar(
            select(func.count())
            .select_from(Appointment)
            .where(Appointment.status == STATUS_ACTIVE, Appointment.confirmed_at.is_not(None))
        )
    jobs = state.scheduler.get_jobs()
    upcoming = sorted((j for j in jobs if j.next_run_time), key=lambda j: j.next_run_time)
    hour_ago = (now_msk() - timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S")
    recent = Counter(r["level"] for r in log_records if r["time"] >= hour_ago)
    db_file = settings.db_file
    return {
        "bot": admin_tools.PLATFORM,
        "admin": admin,
        "now": _iso(now_msk()),
        "started_at": _iso(metrics.started_at()),
        "uptime_s": metrics.uptime_seconds(),
        "version": VERSION,
        "python": platform.python_version(),
        "pid": os.getpid(),
        "log_level": current_level(),
        "db": {
            "path": db_file.name,
            "size_bytes": db_file.stat().st_size if db_file.exists() else 0,
            "schema": SCHEMA_VERSION,
        },
        "appointments": {
            "active": counts.get(STATUS_ACTIVE, 0),
            "cancelled": counts.get(STATUS_CANCELLED, 0),
            "finished": counts.get(STATUS_FINISHED, 0),
            "confirmed": confirmed or 0,
        },
        "jobs": {
            "total": len(jobs),
            "paused": sum(1 for j in jobs if j.next_run_time is None),
            "next": (
                {"id": upcoming[0].id, "run_at": _iso(upcoming[0].next_run_time)}
                if upcoming
                else None
            ),
        },
        "counters": metrics.snapshot(),
        "log_last_hour": {"ERROR": recent.get("ERROR", 0), "WARNING": recent.get("WARNING", 0)},
    }


@router.get("/health")
async def health(request: Request, admin: str = Depends(require_admin)) -> dict:
    return {"checks": await admin_tools.health_checks(request.app.state)}


# --- Журнал --------------------------------------------------------------------------------


@router.get("/logs/tail")
async def logs_tail(
    after: int = 0,
    level: str | None = None,
    q: str | None = None,
    admin: str = Depends(require_admin),
) -> dict:
    rows = tail(after)
    last_seq = rows[-1]["seq"] if rows else after
    if level:
        min_no = level_no(level)
        rows = [r for r in rows if level_no(r["level"]) >= min_no]
    if q:
        needle = q.lower()
        rows = [r for r in rows if needle in r["message"].lower()]
    return {"seq": last_seq, "lines": rows}


@router.get("/logs/files")
async def logs_files(request: Request, admin: str = Depends(require_admin)) -> dict:
    return {"files": admin_tools.list_log_files(request.app.state.settings.log_dir)}


@router.get("/logs/file")
async def logs_file(
    request: Request,
    name: str,
    level: str | None = None,
    q: str | None = None,
    limit: int = 500,
    admin: str = Depends(require_admin),
) -> dict:
    path = admin_tools.resolve_log_file(request.app.state.settings.log_dir, name)
    if path is None:
        raise _not_found()
    return await asyncio.to_thread(admin_tools.read_log_file, path, level, q, limit)


@router.get("/logs/download")
async def logs_download(request: Request, name: str, admin: str = Depends(require_admin)):
    path = admin_tools.resolve_log_file(request.app.state.settings.log_dir, name)
    if path is None:
        raise _not_found()
    return FileResponse(path, media_type="text/plain; charset=utf-8", filename=path.name)


class LevelBody(BaseModel):
    level: Literal["DEBUG", "INFO", "WARNING"]


@router.post("/logs/level")
async def logs_level(body: LevelBody, admin: str = Depends(require_admin_action)) -> dict:
    set_level(body.level)
    _audit(admin, "уровень журнала {}", body.level)
    return {"level": current_level()}


# --- Задания -------------------------------------------------------------------------------


def _job_kind(job_id: str) -> tuple[str, str | None]:
    for prefix, kind in (
        ("rem24h_", "reminder_24h"),
        ("rem2h_", "reminder_2h"),
        ("feedback_", "feedback"),
    ):
        if job_id.startswith(prefix):
            return kind, job_id[len(prefix) :]
    if job_id == "retention_cleanup":
        return "retention", None
    return "other", None


def _job_view(job) -> dict:
    kind, appointment_id = _job_kind(job.id)
    return {
        "id": job.id,
        "kind": kind,
        "appointment_id": appointment_id,
        "run_at": _iso(job.next_run_time),
        "paused": job.next_run_time is None,
        "trigger": str(job.trigger),
    }


@router.get("/jobs")
async def jobs_list(request: Request, admin: str = Depends(require_admin)) -> dict:
    jobs = request.app.state.scheduler.get_jobs()
    jobs.sort(
        key=lambda j: (j.next_run_time is None, j.next_run_time and j.next_run_time.timestamp())
    )
    return {"jobs": [_job_view(j) for j in jobs]}


def _job_or_404(scheduler, job_id: str):
    job = scheduler.get_job(job_id)
    if job is None:
        raise _not_found()
    return job


@router.post("/jobs/{job_id}/{action}")
async def jobs_action(
    job_id: str,
    action: Literal["run", "pause", "resume", "delete"],
    request: Request,
    admin: str = Depends(require_admin_action),
) -> dict:
    scheduler = request.app.state.scheduler
    _job_or_404(scheduler, job_id)
    try:
        if action == "run":
            scheduler.modify_job(job_id, next_run_time=datetime.now(MSK))
            scheduler.wakeup()
        elif action == "pause":
            scheduler.pause_job(job_id)
        elif action == "resume":
            scheduler.resume_job(job_id)
        else:
            scheduler.remove_job(job_id)
    except JobLookupError:
        raise _not_found() from None
    _audit(admin, "задание {} {}", job_id, action)
    return {"status": "ok"}


# --- Записи --------------------------------------------------------------------------------


def _appointment_view(appt: Appointment, job_ids: set[str]) -> dict:
    jobs = [
        f"{prefix}{appt.appointment_id}"
        for prefix in ("rem24h_", "rem2h_", "feedback_")
        if f"{prefix}{appt.appointment_id}" in job_ids
    ]
    return {
        "appointment_id": appt.appointment_id,
        "user_id": appt.user_id,
        "status": appt.status,
        "branch": appt.branch,
        "doctor_name": appt.doctor_name,
        "service_name": appt.service_name,
        "visit_at": _iso(appt.visit_at),
        "created_at": _iso(appt.created_at),
        "closed_at": _iso(appt.closed_at),
        "confirmed_at": _iso(appt.confirmed_at),
        "notify": bool(appt.notify),
        "jobs": jobs,
    }


@router.get("/appointments")
async def appointments_list(
    request: Request,
    status: Literal["active", "cancelled", "finished", "all"] = "active",
    q: str | None = None,
    limit: int = 100,
    admin: str = Depends(require_admin),
) -> dict:
    state = request.app.state
    query = select(Appointment)
    if status != "all":
        query = query.where(Appointment.status == status)
    if q:
        needle = f"%{q.strip()}%"
        query = query.where(
            or_(Appointment.appointment_id.like(needle), Appointment.user_id.like(needle))
        )
    job_ids = {j.id for j in state.scheduler.get_jobs()}
    with session_scope(state.session_factory) as session:
        total = session.scalar(select(func.count()).select_from(query.subquery()))
        rows = session.scalars(
            query.order_by(Appointment.visit_at.desc()).limit(max(1, min(limit, 500)))
        ).all()
        items = [_appointment_view(a, job_ids) for a in rows]
    return {"items": items, "total": total or 0}


def _active(session, appointment_id: str) -> Appointment:
    appt = session.scalar(
        select(Appointment).where(
            Appointment.appointment_id == appointment_id, Appointment.status == STATUS_ACTIVE
        )
    )
    if appt is None:
        raise _not_found()
    return appt


class RemindBody(BaseModel):
    kind: Literal["24h", "2h"] = "24h"


@router.post("/appointments/{appointment_id}/remind")
async def appointment_remind(
    appointment_id: str,
    body: RemindBody,
    request: Request,
    admin: str = Depends(require_admin_action),
) -> dict:
    with session_scope(request.app.state.session_factory) as session:
        _active(session, appointment_id)
    await send_reminder(appointment_id, body.kind)
    _audit(admin, "напоминание {} для {}", body.kind, appointment_id)
    return {"status": "ok"}


@router.post("/appointments/{appointment_id}/reschedule-reminders")
async def appointment_reschedule(
    appointment_id: str, request: Request, admin: str = Depends(require_admin_action)
) -> dict:
    state = request.app.state
    with session_scope(state.session_factory) as session:
        appt = _active(session, appointment_id)
        remove_reminders(state.scheduler, appointment_id)
        scheduled = schedule_reminders(state.scheduler, appt, now_msk())
    _audit(admin, "пересозданы напоминания {}", appointment_id)
    return {"status": "ok", "scheduled": scheduled}


class CloseBody(BaseModel):
    status: Literal["cancelled", "finished"]


@router.post("/appointments/{appointment_id}/close")
async def appointment_close(
    appointment_id: str,
    body: CloseBody,
    request: Request,
    admin: str = Depends(require_admin_action),
) -> dict:
    """Закрыть запись только в боте (1С не вызывается) — для «зависших» записей."""
    state = request.app.state
    with session_scope(state.session_factory) as session:
        appt = _active(session, appointment_id)
        appt.status = body.status
        appt.closed_at = now_msk()
    remove_reminders(state.scheduler, appointment_id)
    _audit(admin, "запись {} закрыта локально: {}", appointment_id, body.status)
    return {"status": "ok"}


# --- 1С ------------------------------------------------------------------------------------


GUID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def onec_params_problem(method: str, params: dict) -> str | None:
    """Проверка до вызова 1С: пустой или кривой doctor_id 1С не разбирает и отвечает 500."""
    if method in ("services", "schedule"):
        doctor_id = params.get("doctor_id", "")
        if not doctor_id:
            return "Укажите doctor_id — GUID врача. Его можно взять из ответа метода doctors."
        if not GUID_RE.match(doctor_id):
            return "doctor_id должен быть GUID вида 8f2c1a4e-2b7d-11ef-a1b3-005056b0c0de."
    if method == "schedule":
        has_day = bool(params.get("date"))
        has_range = bool(params.get("start_date") and params.get("end_date"))
        if not (has_day or has_range):
            return "Для schedule укажите дату или обе даты периода «С» и «По»."
    for key in ("date", "start_date", "end_date"):
        if params.get(key) and not DATE_RE.match(params[key]):
            return f"{key}: дата в формате ГГГГ-ММ-ДД."
    return None


@router.get("/onec/{method}")
async def onec_console(method: str, request: Request, admin: str = Depends(require_admin)) -> dict:
    if method not in admin_tools.ONEC_READ_METHODS:
        raise _not_found()
    params = {k: v for k, v in request.query_params.items() if k in admin_tools.ONEC_PARAMS and v}
    problem = onec_params_problem(method, params)
    if problem:
        raise HTTPException(status_code=422, detail={"error": "BAD_PARAMS", "message": problem})
    return await admin_tools.onec_request(request.app.state, method, params)


# --- Сообщения -----------------------------------------------------------------------------


@router.get("/templates")
async def templates_list(request: Request, admin: str = Depends(require_admin)) -> dict:
    settings = request.app.state.settings
    items = [
        {k: v for k, v in t.items() if k != "keyboard"} for t in admin_tools.templates(settings)
    ]
    return {"templates": items, "recipients": sorted(settings.admin_ids)}


class SendBody(BaseModel):
    chat_id: str


@router.post("/templates/{key}/send")
async def templates_send(
    key: str, body: SendBody, request: Request, admin: str = Depends(require_admin_action)
) -> dict:
    state = request.app.state
    if body.chat_id not in state.settings.admin_ids:
        raise HTTPException(status_code=403, detail={"error": "NOT_ADMIN_RECIPIENT"})
    template = next((t for t in admin_tools.templates(state.settings) if t["key"] == key), None)
    if template is None:
        raise _not_found()
    ok = await state.messenger.send_message(body.chat_id, template["text"], template["keyboard"])
    _audit(admin, "шаблон {} отправлен в {}", key, body.chat_id)
    if not ok:
        raise HTTPException(status_code=502, detail={"error": "SEND_FAILED"})
    return {"status": "ok"}


# --- Настройки и обслуживание --------------------------------------------------------------


@router.get("/settings")
async def settings_list(request: Request, admin: str = Depends(require_admin)) -> dict:
    return {"settings": admin_tools.settings_view(request.app.state.settings)}


@router.post("/webhook/register")
async def webhook_register(request: Request, admin: str = Depends(require_admin_action)) -> dict:
    try:
        ok, detail = await admin_tools.register_webhook(request.app.state)
    except Exception as exc:  # сеть или прокси
        ok, detail = False, type(exc).__name__
    _audit(admin, "регистрация вебхука: {}", "успешно" if ok else detail)
    return {"ok": ok, "detail": detail}


@router.post("/maintenance/retention")
async def maintenance_retention(
    request: Request, admin: str = Depends(require_admin_action)
) -> dict:
    state = request.app.state
    with session_scope(state.session_factory) as session:
        result = run_retention(session, state.settings.PD_RETENTION_DAYS, now_msk())
    _audit(admin, "очистка ПДн: {}", result)
    return result


def stop_process() -> None:
    """uvicorn штатно останавливается по SIGINT; служба NSSM поднимает бот снова."""
    signal.raise_signal(signal.SIGINT)


@router.post("/maintenance/restart")
async def maintenance_restart(request: Request, admin: str = Depends(require_admin_action)) -> dict:
    _audit(admin, "перезапуск бота")
    asyncio.get_running_loop().call_later(0.5, request.app.state.stop_process)
    return {"status": "restarting"}
