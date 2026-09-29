"""Пациент отменяет сам: 1С присылает сигнал cancel-visit ещё до ответа на отмену —
пациент получает одно сообщение об отмене, без «отменена нашими администраторами»."""

import json

import httpx

from tests.helpers import ONEC_SECRET, auth, booking

P = ""
SIGNAL = f"{P}/api/v1/internal/cancel-visit"


def sent_texts(mocks) -> list[str]:
    return [json.loads(c.request.content).get("text", "") for c in mocks["tg"].calls]


async def test_patient_cancel_one_message(client, mocks, app):
    await client.post(f"{P}/book", json=booking(), headers=auth(41))
    seen = []

    async def onec_cancel(request):
        # Так ведёт себя расширение 1С: сигнал уходит при записи заявки, до ответа боту.
        seen.append("appt-1" in app.state.user_cancelling)
        r = await client.post(
            SIGNAL, json={"appointment_id": "appt-1"}, headers={"X-Bot-Secret": ONEC_SECRET}
        )
        assert r.json() == {"status": "success"}
        return httpx.Response(200, json={"status": "success"})

    mocks["cancel"].side_effect = onec_cancel
    before = len(sent_texts(mocks))
    r = await client.post(f"{P}/cancel", headers=auth(41))
    assert r.json()["status"] == "success"
    assert seen == [True]
    texts = sent_texts(mocks)[before:]
    assert len(texts) == 1, texts
    assert "администратор" not in texts[0]
    assert not app.state.user_cancelling
    r = await client.get(f"{P}/my_appointment", headers=auth(41))
    assert r.json()["has_appointment"] is False


async def test_admin_cancel_still_notifies(client, mocks, app):
    await client.post(f"{P}/book", json=booking(), headers=auth(42))
    before = len(sent_texts(mocks))
    r = await client.post(
        SIGNAL, json={"appointment_id": "appt-1"}, headers={"X-Bot-Secret": ONEC_SECRET}
    )
    assert r.json() == {"status": "success"}
    texts = sent_texts(mocks)[before:]
    assert len(texts) == 1 and "администратор" in texts[0]


async def test_mark_cleared_when_onec_fails(client, mocks, app):
    await client.post(f"{P}/book", json=booking(), headers=auth(43))
    mocks["cancel"].respond(502)
    r = await client.post(f"{P}/cancel", headers=auth(43))
    assert r.status_code == 502
    assert not getattr(app.state, "user_cancelling", set())
