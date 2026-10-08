"""specs/005-bot-messages SC-001: ни одно сообщение пациенту не содержит смайликов."""

import json
import re

from app.reminders import send_reminder
from tests.helpers import ONEC_SECRET, TG_SECRET, auth, booking

EMOJI = re.compile(r"[\U0001F000-\U0001FAFF☀-➿⬀-⯿️]")
SIGNAL = "/api/v1/internal/{}"


def sent(mocks) -> list[dict]:
    return [
        json.loads(c.request.content)
        for c in mocks["tg"].calls
        if c.request.url.path.endswith("/sendMessage")
    ]


async def test_whole_journey_without_emoji(client, mocks, app):
    await client.post(
        "/admin/webhook",
        json={
            "update_id": 1,
            "message": {"chat": {"id": 7}, "from": {"first_name": "Ольга"}, "text": "/start"},
        },
        headers={"X-Telegram-Bot-Api-Secret-Token": TG_SECRET},
    )
    await client.post("/book", json=booking(), headers=auth(7))
    await client.post("/reschedule", json=booking(time_="11:00", old_id="appt-1"), headers=auth(7))
    await send_reminder("appt-2", "24h")
    await send_reminder("appt-2", "2h")
    await client.post("/cancel", headers=auth(7))
    await client.post("/book", json=booking(), headers=auth(7))
    secret = {"X-Bot-Secret": ONEC_SECRET}
    await client.post(
        SIGNAL.format("cancel-visit"), json={"appointment_id": "appt-1"}, headers=secret
    )
    messages = sent(mocks)
    assert len(messages) == 8
    for m in messages:
        assert not EMOJI.search(m["text"]), m["text"]
        for row in (m.get("reply_markup") or {}).get("inline_keyboard", []):
            for button in row:
                assert not EMOJI.search(button["text"]), button["text"]
    booked = messages[1]
    assert booked["text"].startswith("Агриппина Ивановна, вы успешно записаны на приём.")
    labels = [b["text"] for row in booked["reply_markup"]["inline_keyboard"] for b in row]
    assert labels == ["Как добраться", "Моя запись"]
    assert "администраторами" in messages[-1]["text"]
