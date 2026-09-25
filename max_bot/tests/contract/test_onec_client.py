"""T034: контракт запросов к HTTP-сервису 1С (docs/onec-contract.md)."""

import json

import httpx
import pytest
import respx

from app.onec_client import OneCClient, OneCError, OneCUnavailable

BASE = "https://onec.test/hs/bot"


@pytest.fixture
def client():
    return OneCClient(BASE, ("bot", "pwd"))


@respx.mock
async def test_doctors(client):
    route = respx.get(f"{BASE}/doctors").respond(
        json=[{"id": "1", "full_name": "A", "specialty_name": "B"}]
    )
    data = await client.get_doctors("Профсоюзная", "2030-01-10")
    req = route.calls.last.request
    assert req.url.params["branch"] == "Профсоюзная" and req.url.params["date"] == "2030-01-10"
    assert req.headers["authorization"].startswith("Basic ")
    assert data[0]["id"] == "1"


@respx.mock
async def test_services_with_error_items(client):
    respx.get(f"{BASE}/services").respond(json=[{"id": "empty", "name": "Нет доступных услуг"}])
    data = await client.get_services("doc")
    assert data[0]["id"] == "empty"


@respx.mock
async def test_schedule_range(client):
    route = respx.get(f"{BASE}/schedule").respond(
        json={"status": "success", "schedule": {"2030-01-10": ["10:00"]}}
    )
    data = await client.get_schedule(
        "doc", branch="Ф", start_date="2030-01-10", end_date="2030-01-20"
    )
    params = route.calls.last.request.url.params
    assert params["doctor_id"] == "doc" and params["start_date"] == "2030-01-10"
    assert "date" not in params
    assert data["schedule"]["2030-01-10"] == ["10:00"]


@respx.mock
async def test_book_body(client):
    route = respx.post(f"{BASE}/book").respond(json={"status": "success", "appointment_id": "a1"})
    payload = {"doctor_id": "d", "date": "2030-01-10", "time": "10:00", "patient": {"phone": "+7"}}
    assert (await client.create_booking(payload))["appointment_id"] == "a1"
    assert json.loads(route.calls.last.request.content) == payload


@respx.mock
async def test_reschedule_and_cancel(client):
    respx.post(f"{BASE}/reschedule").respond(json={"status": "error", "error": "Время занято!"})
    assert (await client.reschedule({"old_appointment_id": "x"}))["status"] == "error"
    route = respx.post(f"{BASE}/cancel").respond(json={"status": "success"})
    await client.cancel_booking("a1")
    assert json.loads(route.calls.last.request.content) == {"appointment_id": "a1"}


@respx.mock
async def test_unexpected_format(client):
    respx.get(f"{BASE}/doctors").respond(json={"detail": "boom"})
    with pytest.raises(OneCError):
        await client.get_doctors()


@respx.mock
async def test_http_500_is_unavailable(client):
    respx.get(f"{BASE}/doctors").respond(500, json={"detail": "ОШИБКА"})
    with pytest.raises(OneCUnavailable):
        await client.get_doctors()


@respx.mock
async def test_connect_error_retried_once(client):
    route = respx.get(f"{BASE}/services").mock(side_effect=httpx.ConnectError("down"))
    with pytest.raises(OneCUnavailable):
        await client.get_services()
    assert route.call_count == 2


@respx.mock
async def test_update_note(client):
    route = respx.post(f"{BASE}/update_note").respond(json={"status": "success"})
    await client.update_note("a1", "✅ Визит подтвержден пациентом (MAX)")
    body = json.loads(route.calls.last.request.content)
    assert body == {"appointment_id": "a1", "note": "✅ Визит подтвержден пациентом (MAX)"}
