"""T038: API формы принимает пользователя только из подписанного initData."""

import json
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
    r = await client.request(method, path, json=body)
    assert r.status_code == 401 and r.json() == {"error": "OPEN_FROM_BOT"}


@pytest.mark.parametrize("method,path,body", PROTECTED)
async def test_forged_401(client, method, path, body):
    r = await client.request(method, path, json=body, headers=auth(1, bad_hash=True))
    assert r.status_code == 401


async def test_expired_401(client):
    headers = {"Authorization": "tma " + make_init_data(1, auth_date=int(time.time()) - 90000)}
    r = await client.get("/my_appointment", headers=headers)
    assert r.status_code == 401 and r.json() == {"error": "SESSION_EXPIRED"}


async def test_old_query_param_ignored(client):
    await client.post("/book", json=booking(), headers=auth(1))
    # Пользователь 2 подставляет tg_id=1 — видит только своё (ничего).
    r = await client.get("/my_appointment?tg_id=1", headers=auth(2))
    assert r.json()["has_appointment"] is False


async def test_user_cannot_cancel_other(client, mocks):
    await client.post("/book", json=booking(), headers=auth(1))
    r = await client.post("/cancel", json={"tg_id": "1"}, headers=auth(2))
    assert r.status_code == 404
    assert not mocks["cancel"].called
    r = await client.get("/my_appointment", headers=auth(1))
    assert r.json()["has_appointment"] is True


async def test_reschedule_other_id_404(client, mocks):
    await client.post("/book", json=booking(), headers=auth(1))
    r = await client.post("/reschedule", json=booking(old_id="someone-else"), headers=auth(1))
    assert r.status_code == 404 and not mocks["reschedule"].called


async def test_config_public(client):
    r = await client.get("/config")
    assert r.json() == {"pd_policy_url": "https://policy.test/consent.pdf"}


async def test_own_flow(client, app):
    r = await client.post("/book", json=booking(), headers=auth(7))
    assert r.json() == {"status": "success", "appointment_id": "appt-1"}
    assert app.state.scheduler.get_job("rem24h_appt-1") is not None
    r = await client.get("/my_appointment", headers=auth(7))
    assert r.json()["data"]["time"] == "10:00"
    r = await client.post(
        "/reschedule", json=booking(time_="11:00", old_id="appt-1"), headers=auth(7)
    )
    assert r.json()["appointment_id"] == "appt-2"
    assert app.state.scheduler.get_job("rem24h_appt-1") is None
    assert app.state.scheduler.get_job("rem24h_appt-2") is not None
    r = await client.post("/cancel", headers=auth(7))
    assert r.json() == {"status": "success"}
    assert app.state.scheduler.get_job("rem24h_appt-2") is None


async def test_onec_slot_taken_message(client, mocks):
    mocks["book"].respond(json={"status": "error", "error": "Извините, это время уже занято."})
    r = await client.post("/book", json=booking(), headers=auth(3))
    assert r.json()["error"] == "SLOT_TAKEN"


async def test_onec_internal_error_hidden(client, mocks):
    mocks["book"].respond(json={"status": "error", "error": "ОШИБКА 1С: {Модуль}: Поле не найдено"})
    r = await client.post("/book", json=booking(), headers=auth(3))
    assert r.json()["error"] == "ONEC_ERROR" and "Модуль" not in r.text


async def test_onec_down_502(client, mocks):
    mocks["book"].respond(503)
    r = await client.post("/book", json=booking(), headers=auth(3))
    assert r.status_code == 502 and r.json()["error"] == "SERVICE_UNAVAILABLE"


# --- Этап 1: нормализация данных пациента и коды 1С (contracts/onec-book.md) ---


async def test_patient_normalized_for_onec(client, mocks):
    await client.post("/book", json=booking(), headers=auth(11))
    sent = json.loads(mocks["book"].calls.last.request.content)["patient"]
    assert sent["phone"] == "+79991234567" and sent["birth_date"] == "1990-02-01"


@pytest.mark.parametrize(
    "field,value,code",
    [
        ("phone", "+7 (999) 123-45", "BAD_PHONE"),
        ("birth_date", "31.02.2000", "BAD_BIRTH_DATE"),
        ("birth_date", "01.01.2999", "BAD_BIRTH_DATE"),
    ],
)
async def test_bad_patient_field_422_without_onec(client, mocks, field, value, code):
    body = booking()
    body["patient"][field] = value
    r = await client.post("/book", json=body, headers=auth(12))
    assert r.status_code == 422 and r.json()["error"] == code and r.json()["message"]
    assert value not in r.text
    assert not mocks["book"].called


@pytest.mark.parametrize(
    "onec_code,expected",
    [
        ("SLOT_TAKEN", "SLOT_TAKEN"),
        ("BAD_PHONE", "BAD_PHONE"),
        ("BAD_BIRTH_DATE", "BAD_BIRTH_DATE"),
        ("STATE_NOT_CONFIGURED", "ONEC_ERROR"),
        ("BAD_REQUEST", "ONEC_ERROR"),
        ("INTERNAL", "ONEC_ERROR"),
        ("SOMETHING_NEW", "ONEC_ERROR"),
    ],
)
async def test_onec_code_mapping(client, mocks, onec_code, expected):
    # Текст 1С не влияет, если есть code: «занято» в тексте не превращает ошибку в SLOT_TAKEN.
    mocks["book"].respond(json={"status": "error", "code": onec_code, "error": "Время занято"})
    r = await client.post("/book", json=booking(), headers=auth(13))
    assert r.json()["error"] == expected and r.json()["message"]
    assert "Время занято" not in r.text


async def test_onec_success_with_patient_fields(client, mocks, settings):
    mocks["book"].respond(
        json={
            "status": "success",
            "appointment_id": "appt-9",
            "patient_id": "p-1",
            "patient": "created",
            "medical_card": "missing",
        }
    )
    r = await client.post("/book", json=booking(), headers=auth(14))
    assert r.json() == {"status": "success", "appointment_id": "appt-9"}
    log_text = "".join(p.read_text(encoding="utf-8") for p in settings.log_dir.glob("*.log"))
    assert "appointment_id=appt-9 пациент=created медкарта=missing" in log_text
    assert "не создала медкарту: appointment_id=appt-9" in log_text


async def test_reschedule_onec_codes(client, mocks):
    await client.post("/book", json=booking(), headers=auth(15))
    for onec_code, expected in (
        ("NOT_FOUND", "ONEC_ERROR"),
        ("SLOT_TAKEN", "SLOT_TAKEN"),
        ("STATE_NOT_CONFIGURED", "ONEC_ERROR"),
    ):
        mocks["reschedule"].respond(json={"status": "error", "code": onec_code, "error": "x"})
        r = await client.post(
            "/reschedule", json=booking(time_="11:00", old_id="appt-1"), headers=auth(15)
        )
        assert r.json()["error"] == expected
    mocks["reschedule"].respond(
        json={
            "status": "success",
            "appointment_id": "appt-1",
            "patient_id": "p-1",
            "patient": "found",
            "medical_card": "created",
        }
    )
    r = await client.post(
        "/reschedule", json=booking(time_="11:00", old_id="appt-1"), headers=auth(15)
    )
    assert r.json() == {"status": "success", "appointment_id": "appt-1"}
    sent = json.loads(mocks["reschedule"].calls.last.request.content)
    assert sent["platform"] == "telegram" and sent["patient"]["phone"] == "+79991234567"
