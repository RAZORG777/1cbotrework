"""Кнопки «Подтвердить визит / Отменить запись» в напоминаниях (specs/003-visit-confirmation, 005)."""

import json

from sqlalchemy import select

from app.db import session_scope
from app.models import Appointment
from app.reminders import send_reminder
from tests.helpers import PATIENT, TG_SECRET, auth, booking

HDR = {"X-Telegram-Bot-Api-Secret-Token": TG_SECRET}
_update_id = iter(range(1000, 100000))


def press(data: str, user_id: int = 7) -> dict:
    return {
        "update_id": next(_update_id),
        "callback_query": {
            "id": "q1",
            "from": {"id": user_id},
            "message": {"message_id": 55, "chat": {"id": user_id}},
            "data": data,
        },
    }


def tg_calls(mocks, method: str) -> list[dict]:
    return [
        json.loads(c.request.content)
        for c in mocks["tg"].calls
        if c.request.url.path.endswith("/" + method)
    ]


def appt(app, appointment_id: str) -> Appointment:
    with session_scope(app.state.session_factory) as s:
        row = s.scalar(select(Appointment).where(Appointment.appointment_id == appointment_id))
        s.expunge(row)
        return row


async def test_confirm(client, app, mocks):
    await client.post("/book", json=booking(), headers=auth(7))
    r = await client.post("/admin/webhook", json=press("c:appt-1"), headers=HDR)
    assert r.json() == {"status": "ok"}
    assert json.loads(mocks["confirm"].calls.last.request.content) == {
        "appointment_id": "appt-1",
        "platform": "telegram",
    }
    assert tg_calls(mocks, "answerCallbackQuery")[-1]["text"] == "Визит подтверждён"
    assert tg_calls(mocks, "editMessageReplyMarkup")[-1]["message_id"] == 55
    assert tg_calls(mocks, "sendMessage")[-1]["text"].startswith("Спасибо, ждём вас")
    assert appt(app, "appt-1").confirmed_at is not None


async def test_confirm_repeat_is_idempotent(client, mocks):
    await client.post("/book", json=booking(), headers=auth(7))
    update = press("c:appt-1")
    await client.post("/admin/webhook", json=update, headers=HDR)
    await client.post("/admin/webhook", json=update, headers=HDR)  # повторная доставка
    assert mocks["confirm"].call_count == 1
    mocks["confirm"].respond(
        json={"status": "success", "appointment_id": "appt-1", "already": True}
    )
    await client.post("/admin/webhook", json=press("c:appt-1"), headers=HDR)
    assert "уже подтвердили" in tg_calls(mocks, "sendMessage")[-1]["text"]


async def test_confirm_onec_down_keeps_buttons(client, app, mocks):
    await client.post("/book", json=booking(), headers=auth(7))
    mocks["confirm"].respond(503)
    await client.post("/admin/webhook", json=press("c:appt-1"), headers=HDR)
    assert not tg_calls(mocks, "editMessageReplyMarkup")
    assert "Нажмите кнопку ещё раз" in tg_calls(mocks, "sendMessage")[-1]["text"]
    assert appt(app, "appt-1").confirmed_at is None


async def test_confirm_cancelled_in_1c(client, app, mocks):
    await client.post("/book", json=booking(), headers=auth(7))
    mocks["confirm"].respond(json={"status": "error", "code": "CANCELLED", "error": "x"})
    await client.post("/admin/webhook", json=press("c:appt-1"), headers=HDR)
    assert appt(app, "appt-1").status == "cancelled"
    assert app.state.scheduler.get_job("rem24h_appt-1") is None
    assert tg_calls(mocks, "editMessageReplyMarkup")


async def test_cancel_button(client, app, mocks):
    await client.post("/book", json=booking(), headers=auth(7))
    await client.post("/admin/webhook", json=press("x:appt-1"), headers=HDR)
    assert json.loads(mocks["cancel"].calls.last.request.content) == {"appointment_id": "appt-1"}
    assert tg_calls(mocks, "editMessageReplyMarkup")
    r = await client.get("/my_appointment", headers=auth(7))
    assert r.json()["has_appointment"] is False
    # Кнопка старого напоминания после отмены — ничего не меняет.
    await client.post("/admin/webhook", json=press("c:appt-1"), headers=HDR)
    assert not mocks["confirm"].called
    assert "уже изменилась" in tg_calls(mocks, "sendMessage")[-1]["text"]


async def test_button_after_reschedule(client, app, mocks):
    await client.post("/book", json=booking(), headers=auth(7))
    await client.post("/admin/webhook", json=press("c:appt-1"), headers=HDR)
    await client.post("/reschedule", json=booking(time_="11:00", old_id="appt-1"), headers=auth(7))
    assert appt(app, "appt-2").confirmed_at is None  # перенос — подтверждать заново
    calls = mocks["confirm"].call_count
    await client.post("/admin/webhook", json=press("x:appt-1"), headers=HDR)
    await client.post("/admin/webhook", json=press("c:appt-1"), headers=HDR)
    assert mocks["confirm"].call_count == calls and not mocks["cancel"].called
    assert appt(app, "appt-2").status == "active"


async def test_other_user_cannot_press(client, mocks):
    await client.post("/book", json=booking(), headers=auth(7))
    await client.post("/admin/webhook", json=press("x:appt-1", user_id=8), headers=HDR)
    assert not mocks["cancel"].called


async def test_reminder_keyboard(client, app, mocks):
    await client.post("/book", json=booking(), headers=auth(7))
    await send_reminder("appt-1", "24h")
    sent = tg_calls(mocks, "sendMessage")[-1]
    rows = sent["reply_markup"]["inline_keyboard"]
    buttons = [(b["text"], b.get("callback_data"), b.get("style")) for row in rows for b in row]
    assert buttons[:2] == [
        ("Подтвердить визит", "c:appt-1", "success"),
        ("Отменить запись", "x:appt-1", "danger"),
    ]
    assert buttons[2][0] == "Как добраться" and rows[2][0]["url"].startswith(
        "https://yandex.ru/maps/"
    )
    assert "Call-Центра" not in sent["text"] and PATIENT["last_name"] not in sent["text"]
    await client.post("/admin/webhook", json=press("c:appt-1"), headers=HDR)
    await send_reminder("appt-1", "2h")
    sent = tg_calls(mocks, "sendMessage")[-1]
    callbacks = [
        b["callback_data"]
        for row in sent["reply_markup"]["inline_keyboard"]
        for b in row
        if "callback_data" in b
    ]
    assert callbacks == ["x:appt-1"] and "ждём вас" in sent["text"]


async def test_reminder_not_sent_for_cancelled(client, mocks):
    await client.post("/book", json=booking(), headers=auth(7))
    await client.post("/cancel", headers=auth(7))
    before = len(tg_calls(mocks, "sendMessage"))
    await send_reminder("appt-1", "24h")
    assert len(tg_calls(mocks, "sendMessage")) == before


async def test_admin_send_reminder(client, mocks):
    await client.post("/book", json=booking(), headers=auth(7))
    r = await client.post("/admin/send-reminder?appointment_id=appt-1")
    assert r.status_code == 401
    r = await client.post(
        "/admin/send-reminder?appointment_id=appt-1", auth=("admin", "admin-pass")
    )
    assert r.json() == {"status": "ok"}
    assert tg_calls(mocks, "sendMessage")[-1]["reply_markup"]["inline_keyboard"]
