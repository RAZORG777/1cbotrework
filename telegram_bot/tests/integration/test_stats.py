"""Дневные счётчики, воронка и ежедневная сводка (specs/008-daily-report-funnel)."""

from __future__ import annotations

import json
from datetime import timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select

from app import stats
from app.db import now_msk, session_scope
from app.models import DailyStat, FunnelMark
from app.reminders import DAILY_REPORT_JOB, register_daily_report, run_retention
from tests.helpers import ONEC_SECRET, TG_SECRET, auth, booking

P = ""
ADMIN = ("admin", "admin-pass")
ACT = {"X-Admin-Request": "1"}
HOOK = {"X-Telegram-Bot-Api-Secret-Token": TG_SECRET}
SIGNAL = {"X-Bot-Secret": ONEC_SECRET}
_update_id = iter(range(5000, 100000))


def sent(mocks, method: str = "sendMessage") -> list[dict]:
    return [
        json.loads(c.request.content)
        for c in mocks["tg"].calls
        if c.request.url.path.endswith("/" + method)
    ]


async def view(client, days: int = 7) -> dict:
    r = await client.get(f"{P}/admin/api/stats", params={"days": days}, auth=ADMIN)
    assert r.status_code == 200
    return r.json()


def funnel(data: dict) -> dict:
    return {f["step"]: f["count"] for f in data["funnel"]}


async def test_track_counts_unique_users(client):
    for user in (1, 1, 2):
        r = await client.post(f"{P}/track", json={"step": "open"}, headers=auth(user))
        assert r.json() == {"status": "ok"}
    await client.post(f"{P}/track", json={"step": "branch"}, headers=auth(1))
    assert (
        await client.post(f"{P}/track", json={"step": "booked"}, headers=auth(1))
    ).status_code == 422
    assert (await client.post(f"{P}/track", json={"step": "open"})).status_code == 401
    f = funnel(await view(client))
    assert (f["open"], f["branch"], f["booked"]) == (2, 1, 0)


async def test_events_and_funnel_from_booking_flow(client, app, mocks):
    await client.post(f"{P}/book", json=booking(), headers=auth(7))
    await client.post(
        f"{P}/reschedule", json=booking(time_="10:30", old_id="appt-1"), headers=auth(7)
    )
    # Подтверждение кнопкой — считается один раз.
    for _ in range(2):
        press = {
            "update_id": next(_update_id),
            "callback_query": {
                "id": "q1",
                "from": {"id": 7},
                "message": {"message_id": 55, "chat": {"id": 7}},
                "data": "c:appt-2",
            },
        }
        await client.post("/admin/webhook", json=press, headers=HOOK)
    await client.post(f"{P}/cancel", headers=auth(7))
    # Отмена клиникой: другая запись, сигнал 1С без отмены пациентом.
    mocks["book"].respond(json={"status": "success", "appointment_id": "appt-9"})
    await client.post(f"{P}/book", json=booking(), headers=auth(8))
    await client.post(
        "/api/v1/internal/cancel-visit", json={"appointment_id": "appt-9"}, headers=SIGNAL
    )

    data = await view(client)
    t = data["totals"]
    assert (t["booked"], t["rescheduled"], t["confirmed"]) == (2, 1, 1)
    assert (t["cancelled_patient"], t["cancelled_clinic"]) == (1, 1)
    assert t["new_users"] == 2
    f = funnel(data)
    assert (f["submit"], f["booked"]) == (2, 2)
    assert data["days"][0]["day"] == now_msk().strftime("%Y-%m-%d") and len(data["days"]) == 7
    assert data["report_time"] == "20:00"


async def test_patient_cancel_signal_not_counted_as_clinic(client, app, mocks):
    import httpx

    await client.post(f"{P}/book", json=booking(), headers=auth(41))

    async def onec_cancel(request):
        await client.post(
            "/api/v1/internal/cancel-visit", json={"appointment_id": "appt-1"}, headers=SIGNAL
        )
        return httpx.Response(200, json={"status": "success"})

    mocks["cancel"].side_effect = onec_cancel
    await client.post(f"{P}/cancel", headers=auth(41))
    t = (await view(client))["totals"]
    assert (t["cancelled_patient"], t["cancelled_clinic"]) == (1, 0)


async def test_report_to_admins(client, mocks):
    await client.post(f"{P}/track", json={"step": "open"}, headers=auth(5))
    await client.post(f"{P}/track", json={"step": "open"}, headers=auth(6))
    await client.post(f"{P}/book", json=booking(), headers=auth(5))
    r = await client.post(f"{P}/admin/api/stats/report", auth=ADMIN, headers=ACT)
    assert r.json() == {"status": "ok", "sent": 1}
    msg = sent(mocks)[-1]
    assert msg["chat_id"] == "100"
    text = msg["text"]
    assert text.startswith("<b>Сводка за ") and "· Telegram" in text
    assert "Новых записей: 1" in text and "Отменила клиника: 0" in text
    assert "Форма записи: открыли 2, записались 1 (50%)" in text
    assert "Записей на завтра:" in text
    assert (await client.post(f"{P}/admin/api/stats/report", auth=ADMIN)).status_code == 403


async def test_report_without_admins(client, app):
    app.state.settings = app.state.settings.model_copy(update={"ADMIN_IDS": ""})
    r = await client.post(f"{P}/admin/api/stats/report", auth=ADMIN, headers=ACT)
    assert r.status_code == 409


async def test_stats_bad_days(client):
    r = await client.get(f"{P}/admin/api/stats", params={"days": 0}, auth=ADMIN)
    assert r.status_code == 422


async def test_daily_job_registered(app):
    job = app.state.scheduler.get_job(DAILY_REPORT_JOB)
    assert job is not None and "hour='20'" in str(job.trigger)
    jobs = await _jobs(app)
    assert any(j["kind"] == "daily_report" for j in jobs)


async def _jobs(app):
    import httpx

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://bot.test") as c:
        return (await c.get(f"{P}/admin/api/jobs", auth=ADMIN)).json()["jobs"]


def test_register_daily_report_off():
    scheduler = AsyncIOScheduler()
    register_daily_report(scheduler, "08:15")
    assert scheduler.get_job(DAILY_REPORT_JOB) is not None
    register_daily_report(scheduler, "")
    assert scheduler.get_job(DAILY_REPORT_JOB) is None


def test_cleanup_old_marks(app):
    factory = app.state.session_factory
    now = now_msk()
    with session_scope(factory) as session:
        stats.mark_step(session, "1", "open", when=now - timedelta(days=1))
        stats.mark_step(session, "1", "open", when=now)
        stats.inc(session, "booked", when=now - timedelta(days=500))
    with session_scope(factory) as session:
        run_retention(session, 30, now)
    with session_scope(factory) as session:
        assert [m.day for m in session.scalars(select(FunnelMark))] == [now.strftime("%Y-%m-%d")]
        days = [s.day for s in session.scalars(select(DailyStat))]
        assert (now - timedelta(days=500)).strftime("%Y-%m-%d") not in days
        # Итог вчерашнего дня по воронке остаётся, удаляются только отметки.
        assert (now - timedelta(days=1)).strftime("%Y-%m-%d") in days


def test_marks_store_no_raw_ids(app):
    with session_scope(app.state.session_factory) as session:
        stats.mark_step(session, "123456789", "open")
        mark = session.scalars(select(FunnelMark)).one()
        assert "123456789" not in mark.uid
