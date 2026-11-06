"""Условия приёма ребёнка до 18 лет (specs/010-child-visit-notice)."""

from __future__ import annotations

import pytest

from app.patient import is_minor
from tests.helpers import auth, booking

P = "/max"


def child_booking(birth: str, ack: bool | None = None) -> dict:
    body = booking(date="2030-01-10")
    body["patient"] = {**body["patient"], "birth_date": birth}
    if ack is not None:
        body["guardian_ack"] = ack
    return body


async def test_child_without_ack_is_refused(client, mocks):
    r = await client.post(f"{P}/book", json=child_booking("15.03.2020"), headers=auth(90))
    assert r.status_code == 422
    assert r.json()["error"] == "GUARDIAN_ACK_REQUIRED"
    assert not mocks["book"].called


async def test_child_with_ack_is_booked(client, mocks):
    r = await client.post(f"{P}/book", json=child_booking("15.03.2020", ack=True), headers=auth(91))
    assert r.json()["status"] == "success"
    assert "guardian_ack" not in mocks["book"].calls.last.request.content.decode()


async def test_adult_needs_no_ack(client):
    r = await client.post(f"{P}/book", json=child_booking("10.01.2012"), headers=auth(92))
    assert r.json()["status"] == "success"


@pytest.mark.parametrize(
    ("birth", "visit", "minor"),
    [
        ("2012-01-10", "2030-01-10", False),  # 18 в день приёма
        ("2012-01-11", "2030-01-10", True),  # 18 исполнится завтра
        ("2012-02-29", "2030-02-28", True),
        ("1990-05-01", "2030-01-10", False),
        ("bad", "2030-01-10", False),
    ],
)
def test_is_minor(birth, visit, minor):
    assert is_minor(birth, visit) is minor
