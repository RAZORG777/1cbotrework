"""T055: сигналы 1С — только с секретом, идемпотентно (contracts/onec-signals.md)."""

import pytest

from tests.helpers import ONEC_SECRET, auth, booking

URL = "/max/api/v1/internal/{}"


@pytest.mark.parametrize("kind", ["cancel-visit", "finish-visit"])
@pytest.mark.parametrize("headers", [{}, {"X-Bot-Secret": "wrong"}])
async def test_requires_secret(client, kind, headers):
    await client.post("/max/book", json=booking(), headers=auth(5))
    r = await client.post(URL.format(kind), json={"appointment_id": "appt-1"}, headers=headers)
    assert r.status_code == 401 and r.json() == {"status": "unauthorized"}
    r = await client.get("/max/my_appointment", headers=auth(5))
    assert r.json()["has_appointment"] is True


@pytest.mark.parametrize("kind", ["cancel-visit", "finish-visit"])
async def test_unknown(client, kind):
    r = await client.post(
        URL.format(kind), json={"appointment_id": "nope"}, headers={"X-Bot-Secret": ONEC_SECRET}
    )
    assert r.json() == {"status": "not_found"}


async def test_cancel_idempotent(client, mocks):
    await client.post("/max/book", json=booking(), headers=auth(5))
    before = mocks["msg"].call_count
    for _ in range(2):
        r = await client.post(
            URL.format("cancel-visit"),
            json={"appointment_id": "appt-1"},
            headers={"X-Bot-Secret": ONEC_SECRET},
        )
        assert r.json() == {"status": "success"}
    assert mocks["msg"].call_count == before + 1
    assert (await client.get("/max/my_appointment", headers=auth(5))).json()[
        "has_appointment"
    ] is False


async def test_finish_schedules_feedback(client, app):
    await client.post("/max/book", json=booking(), headers=auth(5))
    for _ in range(2):
        r = await client.post(
            URL.format("finish-visit"),
            json={"appointment_id": "appt-1"},
            headers={"X-Bot-Secret": ONEC_SECRET},
        )
        assert r.json() == {"status": "success"}
    job = app.state.scheduler.get_job("feedback_appt-1")
    assert job is not None and "отзыв" in job.args[1]


async def test_validation(client):
    r = await client.post(
        URL.format("cancel-visit"), json={}, headers={"X-Bot-Secret": ONEC_SECRET}
    )
    assert r.status_code == 422
