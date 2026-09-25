"""T038: API формы принимает пользователя только из подписанного initData."""

import time

import pytest

from tests.helpers import auth, booking, make_init_data

PROTECTED = [
    ("GET", "/my_appointment", None),
    ("GET", "/doctors", None),
    ("GET", "/services", None),
    ("GET", "/schedule?doctor_id=doc-1", None),
    ("POST", "/book", booking()),
    ("POST", "/reschedule", booking(old_id="appt-1")),
    ("POST", "/cancel", {}),
]


@pytest.mark.parametrize("method,path,body", PROTECTED)
async def test_no_header_401(client, method, path, body):
    r = await client.request(method, "/max" + path, json=body)
    assert r.status_code == 401 and r.json() == {"error": "OPEN_FROM_BOT"}


@pytest.mark.parametrize("method,path,body", PROTECTED)
async def test_forged_401(client, method, path, body):
    r = await client.request(method, "/max" + path, json=body, headers=auth(1, bad_hash=True))
    assert r.status_code == 401


async def test_expired_401(client):
    headers = {"Authorization": "tma " + make_init_data(1, auth_date=int(time.time()) - 90000)}
    r = await client.get("/max/my_appointment", headers=headers)
    assert r.status_code == 401 and r.json() == {"error": "SESSION_EXPIRED"}


async def test_old_query_param_ignored(client):
    await client.post("/max/book", json=booking(), headers=auth(1))
    # Пользователь 2 подставляет tg_id=1 — видит только своё (ничего).
    r = await client.get("/max/my_appointment?tg_id=1", headers=auth(2))
    assert r.json()["has_appointment"] is False


async def test_user_cannot_cancel_other(client, mocks):
    await client.post("/max/book", json=booking(), headers=auth(1))
    r = await client.post("/max/cancel", json={"tg_id": "1"}, headers=auth(2))
    assert r.status_code == 404
    assert not mocks["cancel"].called
    r = await client.get("/max/my_appointment", headers=auth(1))
    assert r.json()["has_appointment"] is True


async def test_reschedule_other_id_404(client, mocks):
    await client.post("/max/book", json=booking(), headers=auth(1))
    r = await client.post("/max/reschedule", json=booking(old_id="someone-else"), headers=auth(1))
    assert r.status_code == 404 and not mocks["reschedule"].called


async def test_config_public(client):
    r = await client.get("/max/config")
    assert r.json() == {"pd_policy_url": "https://policy.test/consent.pdf"}


async def test_own_flow(client, app):
    r = await client.post("/max/book", json=booking(), headers=auth(7))
    assert r.json() == {"status": "success", "appointment_id": "appt-1"}
    assert app.state.scheduler.get_job("rem24h_appt-1") is not None
    r = await client.get("/max/my_appointment", headers=auth(7))
    assert r.json()["data"]["time"] == "10:00"
    r = await client.post(
        "/max/reschedule", json=booking(time_="11:00", old_id="appt-1"), headers=auth(7)
    )
    assert r.json()["appointment_id"] == "appt-2"
    assert app.state.scheduler.get_job("rem24h_appt-1") is None
    assert app.state.scheduler.get_job("rem24h_appt-2") is not None
    r = await client.post("/max/cancel", headers=auth(7))
    assert r.json() == {"status": "success"}
    assert app.state.scheduler.get_job("rem24h_appt-2") is None


async def test_onec_slot_taken_message(client, mocks):
    mocks["book"].respond(json={"status": "error", "error": "Извините, это время уже занято."})
    r = await client.post("/max/book", json=booking(), headers=auth(3))
    assert r.json()["error"] == "SLOT_TAKEN"


async def test_onec_internal_error_hidden(client, mocks):
    mocks["book"].respond(json={"status": "error", "error": "ОШИБКА 1С: {Модуль}: Поле не найдено"})
    r = await client.post("/max/book", json=booking(), headers=auth(3))
    assert r.json()["error"] == "ONEC_ERROR" and "Модуль" not in r.text


async def test_onec_down_502(client, mocks):
    mocks["book"].respond(503)
    r = await client.post("/max/book", json=booking(), headers=auth(3))
    assert r.status_code == 502 and r.json()["error"] == "SERVICE_UNAVAILABLE"
