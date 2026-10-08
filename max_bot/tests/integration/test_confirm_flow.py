"""Кнопки «Подтвердить визит / Отменить запись» в напоминаниях MAX (specs/003-visit-confirmation, 005)."""

import json

from sqlalchemy import select

from app.db import session_scope
from app.models import Appointment
from app.reminders import send_reminder
from tests.helpers import MAX_SECRET, PATIENT, auth, booking

HDR = {"X-Max-Bot-Api-Secret": MAX_SECRET}
_ids = iter(range(1000, 100000))


def press(payload: str, user_id: int = 5, text: str = "Напоминание") -> dict:
    n = next(_ids)
    return {
        "update_type": "message_callback",
        "timestamp": n,
        "callback": {
            "callback_id": f"cb-{n}",
            "payload": payload,
            "timestamp": n,
            "user": {"user_id": user_id, "name": "Анна"},
        },
        "message": {"body": {"mid": f"mid-{n}", "text": text}},
    }


def answers(mocks) -> list[dict]:
    return [json.loads(c.request.content) for c in mocks["answers"].calls]


def appt(app, appointment_id: str) -> Appointment:
    with session_scope(app.state.session_factory) as s:
        row = s.scalar(select(Appointment).where(Appointment.appointment_id == appointment_id))
        s.expunge(row)
        return row


async def test_confirm_replaces_message(client, app, mocks):
    await client.post("/max/book", json=booking(), headers=auth(5))
    await client.post("/max/webhook", json=press("confirm:appt-1"), headers=HDR)
    assert json.loads(mocks["confirm"].calls.last.request.content)["platform"] == "max"
    last = answers(mocks)[-1]
    assert last["notification"] == "Визит подтверждён"
    assert last["message"]["attachments"] == [] and "Напоминание" in last["message"]["text"]
    assert appt(app, "appt-1").confirmed_at is not None


async def test_confirm_onec_down_keeps_buttons(client, app, mocks):
    await client.post("/max/book", json=booking(), headers=auth(5))
    mocks["confirm"].respond(503)
    await client.post("/max/webhook", json=press("confirm:appt-1"), headers=HDR)
    assert "message" not in answers(mocks)[-1]
    assert "Нажмите кнопку ещё раз" in json.loads(mocks["msg"].calls.last.request.content)["text"]


async def test_confirm_cancelled_in_1c(client, app, mocks):
    await client.post("/max/book", json=booking(), headers=auth(5))
    mocks["confirm"].respond(json={"status": "error", "code": "CANCELLED", "error": "x"})
    await client.post("/max/webhook", json=press("confirm:appt-1"), headers=HDR)
    assert appt(app, "appt-1").status == "cancelled"
    assert app.state.scheduler.get_job("rem24h_appt-1") is None


async def test_cancel_button_and_stale(client, app, mocks):
    await client.post("/max/book", json=booking(), headers=auth(5))
    await client.post("/max/webhook", json=press("cancel:appt-1"), headers=HDR)
    assert mocks["cancel"].call_count == 1
    assert answers(mocks)[-1]["message"]["attachments"] == []
    await client.post("/max/webhook", json=press("confirm:appt-1"), headers=HDR)
    assert not mocks["confirm"].called


async def test_button_after_reschedule(client, app, mocks):
    await client.post("/max/book", json=booking(), headers=auth(5))
    await client.post(
        "/max/reschedule", json=booking(time_="11:00", old_id="appt-1"), headers=auth(5)
    )
    await client.post("/max/webhook", json=press("cancel:appt-1"), headers=HDR)
    await client.post("/max/webhook", json=press("confirm:appt-1"), headers=HDR)
    assert not mocks["cancel"].called and not mocks["confirm"].called
    assert appt(app, "appt-2").status == "active"


async def test_reminder_keyboard(client, app, mocks):
    await client.post("/max/book", json=booking(), headers=auth(5))
    await send_reminder("appt-1", "24h")
    body = json.loads(mocks["msg"].calls.last.request.content)
    rows = body["attachments"][0]["payload"]["buttons"]
    buttons = [(b["text"], b.get("payload"), b.get("intent")) for row in rows for b in row]
    assert buttons[:2] == [
        ("Подтвердить визит", "confirm:appt-1", "positive"),
        ("Отменить запись", "cancel:appt-1", "negative"),
    ]
    assert rows[2][0]["type"] == "link" and rows[2][0]["text"] == "Как добраться"
    assert PATIENT["last_name"] not in body["text"]
    await client.post("/max/webhook", json=press("confirm:appt-1"), headers=HDR)
    await send_reminder("appt-1", "2h")
    body = json.loads(mocks["msg"].calls.last.request.content)
    rows = body["attachments"][0]["payload"]["buttons"]
    assert [b["payload"] for row in rows for b in row if "payload" in b] == ["cancel:appt-1"]


async def test_admin_send_reminder(client, mocks):
    await client.post("/max/book", json=booking(), headers=auth(5))
    r = await client.post(
        "/max/admin/send-reminder?appointment_id=appt-1", auth=("admin", "admin-pass")
    )
    assert r.json() == {"status": "ok"}
    body = json.loads(mocks["msg"].calls.last.request.content)
    assert body["attachments"][0]["type"] == "inline_keyboard"
