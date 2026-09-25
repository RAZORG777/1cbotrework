"""Админ-панель: очередь заданий, счётчики и журнал. Без ФИО и телефонов (FR-017)."""

from __future__ import annotations

from html import escape

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, PlainTextResponse
from sqlalchemy import func, select

from ..auth import require_admin
from ..db import now_msk, session_scope
from ..logging import log_buffer
from ..models import Appointment

router = APIRouter(prefix="/admin")


@router.get("/logs", response_class=PlainTextResponse)
async def admin_logs(admin: str = Depends(require_admin)) -> str:
    return "\n".join(reversed(log_buffer)) if log_buffer else "Логи пусты..."


@router.get("", response_class=HTMLResponse)
async def admin_dashboard(request: Request, admin: str = Depends(require_admin)) -> str:
    state = request.app.state
    with session_scope(state.session_factory) as session:
        counts = dict(
            session.execute(
                select(Appointment.status, func.count()).group_by(Appointment.status)
            ).all()
        )
        by_branch = session.execute(
            select(Appointment.branch, func.count()).group_by(Appointment.branch)
        ).all()
        by_doctor = session.execute(
            select(Appointment.doctor_name, func.count())
            .group_by(Appointment.doctor_name)
            .order_by(func.count().desc())
            .limit(10)
        ).all()
    now = now_msk()
    jobs_html = ""
    for job in state.scheduler.get_jobs():
        when = job.next_run_time.strftime("%d.%m.%Y %H:%M") if job.next_run_time else "пауза"
        jobs_html += f"<li><b>{escape(job.id)}</b> — {escape(when)}</li>"
    logs_html = (
        "".join(f"<div class='log'>{escape(line)}</div>" for line in reversed(log_buffer))
        or "<div>Логи пусты...</div>"
    )
    stats = (
        "".join(
            f"<li>{escape(status)}: <b>{count}</b></li>" for status, count in sorted(counts.items())
        )
        or "<li>Записей нет</li>"
    )
    analytics = (
        "".join(f"<li>{escape(b or 'не указан')}: <b>{n}</b></li>" for b, n in by_branch)
        + "<li style='list-style:none'><br><b>Врачи (топ-10)</b></li>"
        + "".join(f"<li>{escape(d or 'не указан')}: <b>{n}</b></li>" for d, n in by_doctor)
    )
    return f"""<!doctype html>
<html lang="ru"><head><meta charset="utf-8"><title>Админ-панель MAX</title>
<style>
body {{ font-family: sans-serif; padding: 20px; background: #f9fafb; }}
h2 {{ color: #32a396; border-bottom: 2px solid #32a396; padding-bottom: 5px; }}
.container {{ display: flex; gap: 20px; flex-wrap: wrap; }}
.panel {{ background: #fff; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,.1); flex: 1 1 360px; }}
.logs {{ background: #1e1e1e; color: #0f0; font-family: monospace; font-size: 13px; height: 500px; overflow-y: auto; padding: 15px; border-radius: 5px; }}
.log {{ border-bottom: 1px solid #333; padding: 2px 0; }}
</style></head><body>
<h2>Панель управления (MAX) | {escape(admin)} | {now:%d.%m.%Y %H:%M}</h2>
<div class="container">
  <div class="panel"><h3>📊 Записи по статусам</h3><ul>{stats}</ul>
  <h3>🏥 По филиалам</h3><ul>{analytics}</ul>
  <h3>⚙️ Очередь заданий</h3><ul>{jobs_html or "<li>Нет запланированных задач</li>"}</ul></div>
  <div class="panel"><h3>📝 Журнал</h3><div class="logs">{logs_html}</div></div>
</div></body></html>"""
