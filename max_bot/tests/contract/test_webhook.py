"""T058: вебхук MAX — секрет, приветствие open_app, кнопки через message_callback, идемпотентность."""

import json

from tests.helpers import MAX_SECRET, ONEC_SECRET, auth, booking

HDR = {"X-Max-Bot-Api-Secret": MAX_SECRET}


def started(ts=1, user_id=500):
    return {
        "update_type": "bot_started",
        "timestamp": ts,
        "user_id": user_id,
        "user": {"user_id": user_id, "name": "Анна"},
    }


def callback(cb_id, payload, user_id=5):
    return {
        "update_type": "message_callback",
        "timestamp": 2,
        "callback": {
            "callback_id": cb_id,
            "payload": payload,
            "timestamp": 2,
            "user": {"user_id": user_id, "name": "Анна"},
        },
        "message": {"body": {"mid": "mid-1"}},
    }


async def test_requires_secret(client, mocks):
    assert (await client.post("/max/webhook", json=started())).status_code == 401
    r = await client.post("/max/webhook", json=started(), headers={"X-Max-Bot-Api-Secret": "wrong"})
    assert r.status_code == 401
    assert not mocks["msg"].called


async def test_get_webhook_removed(client):
    assert (await client.get("/max/webhook")).status_code == 405


async def test_welcome_open_app_and_duplicate(client, mocks):
    r = await client.post("/max/webhook", json=started(), headers=HDR)
    assert r.json() == {"status": "ok"}
    body = json.loads(mocks["msg"].calls.last.request.content)
    button = body["attachments"][0]["payload"]["buttons"][0][0]
    assert button == {"type": "open_app", "text": "Записаться ✅", "web_app": "yasno_bot"}
    assert "user_id=" not in json.dumps(body)
    assert mocks["msg"].calls.last.request.headers["authorization"] == "123456:TEST-TOKEN"
    await client.post("/max/webhook", json=started(), headers=HDR)
    assert mocks["msg"].call_count == 1


async def test_confirm_visit_button(client, mocks):
    await client.post("/max/book", json=booking(), headers=auth(5))
    await client.post("/max/webhook", json=callback("cb-1", "confirm_visit"), headers=HDR)
    note = json.loads(mocks["update_note"].calls.last.request.content)
    assert note["appointment_id"] == "appt-1"
    assert mocks["answers"].calls.last.request.url.params["callback_id"] == "cb-1"
    await client.post("/max/webhook", json=callback("cb-1", "confirm_visit"), headers=HDR)
    assert mocks["update_note"].call_count == 1


async def test_cancel_button_cancels_own_only(client, mocks):
    await client.post("/max/book", json=booking(), headers=auth(5))
    await client.post(
        "/max/webhook", json=callback("cb-2", "cancel_visit_btn", user_id=6), headers=HDR
    )
    assert not mocks["cancel"].called
    await client.post(
        "/max/webhook", json=callback("cb-3", "cancel_visit_btn", user_id=5), headers=HDR
    )
    assert mocks["cancel"].call_count == 1
    assert (await client.get("/max/my_appointment", headers=auth(5))).json()[
        "has_appointment"
    ] is False
    r = await client.post(
        "/max/api/v1/internal/cancel-visit",
        json={"appointment_id": "appt-1"},
        headers={"X-Bot-Secret": ONEC_SECRET},
    )
    assert r.json() == {"status": "not_found"}


async def test_message_from_user_gets_menu(client, mocks):
    upd = {
        "update_type": "message_created",
        "timestamp": 3,
        "message": {
            "sender": {"user_id": 7, "is_bot": False},
            "body": {"mid": "m-7", "text": "привет"},
        },
    }
    await client.post("/max/webhook", json=upd, headers=HDR)
    assert mocks["msg"].calls.last.request.url.params["user_id"] == "7"
