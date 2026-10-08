"""specs/005-bot-messages SC-001: ни одно сообщение пациенту не содержит смайликов."""

import json
import re

from app.reminders import send_reminder
from tests.helpers import MAX_SECRET, ONEC_SECRET, auth, booking

EMOJI = re.compile(r"[\U0001F000-\U0001FAFF☀-➿⬀-⯿️]")
SIGNAL = "/max/api/v1/internal/{}"


def sent(mocks) -> list[dict]:
    return [json.loads(c.request.content) for c in mocks["msg"].calls]


def buttons(message: dict) -> list[dict]:
    rows = []
    for att in message.get("attachments") or []:
        rows += att.get("payload", {}).get("buttons", [])
    return [b for row in rows for b in row]


async def test_whole_journey_without_emoji(client, mocks, app):
    await client.post(
        "/max/webhook",
        json={
            "update_type": "bot_started",
            "timestamp": 1,
            "user_id": 5,
            "user": {"user_id": 5, "first_name": "Ольга"},
        },
        headers={"X-Max-Bot-Api-Secret": MAX_SECRET},
    )
    await client.post("/max/book", json=booking(), headers=auth(5))
    await client.post(
        "/max/reschedule", json=booking(time_="11:00", old_id="appt-1"), headers=auth(5)
    )
    await send_reminder("appt-2", "24h")
    await send_reminder("appt-2", "2h")
    await client.post("/max/cancel", headers=auth(5))
    await client.post("/max/book", json=booking(), headers=auth(5))
    secret = {"X-Bot-Secret": ONEC_SECRET}
    await client.post(
        SIGNAL.format("cancel-visit"), json={"appointment_id": "appt-1"}, headers=secret
    )
    messages = sent(mocks)
    assert len(messages) == 8
    assert messages[0]["text"].startswith("Здравствуйте, Ольга!")
    for m in messages:
        assert not EMOJI.search(m["text"]), m["text"]
        for button in buttons(m):
            assert not EMOJI.search(button["text"]), button["text"]
    booked = messages[1]
    assert booked["text"].startswith("Агриппина Ивановна, вы успешно записаны на приём.")
    assert [b["text"] for b in buttons(booked)] == ["Как добраться", "Моя запись"]
    assert "администраторами" in messages[-1]["text"]
