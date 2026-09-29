"""Этап 3: выдача сборки формы, данные «Моей записи», перенос без данных пациента."""

import json

import httpx
import pytest
from sqlalchemy import select

from app.main import create_app
from app.models import Appointment
from app.routes import webapp
from tests.helpers import auth, booking

P = ""


def no_patient(body: dict) -> dict:
    body = dict(body)
    body.pop("patient")
    body["pd_consent"] = False
    return body


# --- Выдача формы (contracts/webapp-api.md › Выдача формы) ---


@pytest.fixture
async def built_client(settings, mocks, tmp_path, monkeypatch):
    app_dir = tmp_path / "app"
    (app_dir / "assets").mkdir(parents=True)
    (app_dir / "index.html").write_text("<!doctype html><title>Форма</title>", encoding="utf-8")
    (app_dir / "assets" / "index-abc.js").write_text("console.log(1)", encoding="utf-8")
    monkeypatch.setattr(webapp, "APP_DIR", app_dir)
    application = create_app(settings, retry_pause=0)
    async with application.router.lifespan_context(application):
        transport = httpx.ASGITransport(app=application)
        async with httpx.AsyncClient(transport=transport, base_url="http://bot.test") as c:
            yield c


async def test_index_from_build_not_cached(built_client):
    r = await built_client.get(f"{P}/")
    assert r.status_code == 200 and "Форма" in r.text
    assert r.headers["cache-control"] == "no-cache"


async def test_assets_from_build(built_client):
    r = await built_client.get(f"{P}/assets/index-abc.js")
    assert r.status_code == 200 and r.text == "console.log(1)"


async def test_no_build_503(settings, mocks, tmp_path, monkeypatch):
    monkeypatch.setattr(webapp, "APP_DIR", tmp_path / "missing")
    application = create_app(settings, retry_pause=0)
    async with application.router.lifespan_context(application):
        transport = httpx.ASGITransport(app=application)
        async with httpx.AsyncClient(transport=transport, base_url="http://bot.test") as c:
            r = await c.get(f"{P}/")
            assert r.status_code == 503
            assert (await c.get(f"{P}/healthz")).status_code == 200


async def test_old_logo_removed(client):
    r = await client.get(f"{P}/Логотип.png")
    assert r.status_code in (404, 405)


# --- «Моя запись» ---


async def test_my_appointment_has_doctor_service_confirmed(client, app):
    await client.post(f"{P}/book", json=booking(), headers=auth(31))
    data = (await client.get(f"{P}/my_appointment", headers=auth(31))).json()["data"]
    assert data["doctor_id"] == "doc-1" and data["service_id"] == "srv-1"
    assert data["confirmed"] is False
    assert not {"phone", "birth_date", "first_name", "last_name"} & data.keys()

    with app.state.session_factory() as s:
        appt = s.scalar(select(Appointment).where(Appointment.user_id == "31"))
        appt.confirmed_at = appt.created_at
        s.commit()
    data = (await client.get(f"{P}/my_appointment", headers=auth(31))).json()["data"]
    assert data["confirmed"] is True


# --- Перенос без повторной передачи данных пациента ---


async def test_reschedule_without_patient_uses_stored(client, mocks, app):
    await client.post(f"{P}/book", json=booking(notify=False), headers=auth(32))
    body = no_patient(booking(time_="11:00", old_id="appt-1"))
    r = await client.post(f"{P}/reschedule", json=body, headers=auth(32))
    assert r.json() == {"status": "success", "appointment_id": "appt-2"}
    sent = json.loads(mocks["reschedule"].calls.last.request.content)
    assert sent["patient"]["phone"] == "+79991234567"
    assert sent["patient"]["last_name"] and sent["patient"]["birth_date"]
    with app.state.session_factory() as s:
        appt = s.scalar(select(Appointment).where(Appointment.user_id == "32"))
        assert appt.time_str == "11:00" and appt.phone == "+79991234567"
        assert appt.notify is False  # выбор пациента о напоминаниях сохраняется


async def test_reschedule_with_patient_still_needs_consent(client, mocks):
    await client.post(f"{P}/book", json=booking(), headers=auth(33))
    body = booking(time_="11:00", old_id="appt-1", consent=False)
    r = await client.post(f"{P}/reschedule", json=body, headers=auth(33))
    assert r.status_code == 422 and r.json()["error"] == "PD_CONSENT_REQUIRED"
    assert not mocks["reschedule"].called


async def test_reschedule_without_patient_needs_active(client, mocks):
    body = no_patient(booking(time_="11:00", old_id="appt-1"))
    r = await client.post(f"{P}/reschedule", json=body, headers=auth(34))
    assert r.status_code == 404 and not mocks["reschedule"].called
