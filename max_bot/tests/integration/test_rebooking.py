"""T047: завершённая, отменённая или прошедшая запись не мешает записаться снова (FR-005)."""

from datetime import timedelta

from sqlalchemy import update

from app.db import now_msk, session_scope
from app.models import Appointment
from tests.helpers import ONEC_SECRET, auth, booking

SIG = {"X-Bot-Secret": ONEC_SECRET}


async def test_finish_then_book_again(client, app, mocks):
    assert (await client.post("/max/book", json=booking(), headers=auth(5))).json()[
        "status"
    ] == "success"
    r = await client.post(
        "/max/api/v1/internal/finish-visit", json={"appointment_id": "appt-1"}, headers=SIG
    )
    assert r.json() == {"status": "success"}
    assert app.state.scheduler.get_job("feedback_appt-1") is not None
    assert app.state.scheduler.get_job("rem24h_appt-1") is None
    mocks["book"].respond(json={"status": "success", "appointment_id": "appt-9"})
    r = await client.post("/max/book", json=booking(), headers=auth(5))
    assert r.json() == {"status": "success", "appointment_id": "appt-9"}


async def test_cancel_then_book_again(client, mocks):
    await client.post("/max/book", json=booking(), headers=auth(5))
    assert (await client.post("/max/cancel", headers=auth(5))).json()["status"] == "success"
    mocks["book"].respond(json={"status": "success", "appointment_id": "appt-9"})
    assert (await client.post("/max/book", json=booking(), headers=auth(5))).json()[
        "status"
    ] == "success"


async def test_second_active_booking_blocked(client, mocks):
    await client.post("/max/book", json=booking(), headers=auth(5))
    r = await client.post("/max/book", json=booking(), headers=auth(5))
    assert r.json() == {"status": "error", "error": "SECOND_BOOKING_ERROR"}
    assert mocks["book"].call_count == 1


async def test_past_visit_does_not_block(client, app, mocks):
    await client.post("/max/book", json=booking(), headers=auth(5))
    with session_scope(app.state.session_factory) as s:
        s.execute(update(Appointment).values(visit_at=now_msk() - timedelta(hours=5)))
    assert (await client.get("/max/my_appointment", headers=auth(5))).json()[
        "has_appointment"
    ] is False
    mocks["book"].respond(json={"status": "success", "appointment_id": "appt-9"})
    assert (await client.post("/max/book", json=booking(), headers=auth(5))).json()[
        "status"
    ] == "success"
