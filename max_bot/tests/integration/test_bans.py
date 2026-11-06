"""Запрет онлайн-записи (specs/009-booking-ban)."""

from __future__ import annotations

from tests.helpers import auth, booking

P = "/max"
ADMIN = ("admin", "admin-pass")
ACT = {"X-Admin-Request": "1"}


async def ban(client, user_id: str, reason: str = "3 неявки") -> dict:
    r = await client.post(
        f"{P}/admin/api/bans", json={"user_id": user_id, "reason": reason}, auth=ADMIN, headers=ACT
    )
    assert r.status_code == 200, r.text
    return r.json()


async def test_banned_user_cannot_book(client, mocks):
    assert (await ban(client, "77"))["created"] is True
    r = await client.post(f"{P}/book", json=booking(), headers=auth(77))
    body = r.json()
    assert body["status"] == "error" and body["error"] == "BOOKING_BLOCKED"
    assert "8 (800) 301-01-67" in body["message"]
    assert not mocks["book"].called
    mine = (await client.get(f"{P}/my_appointment", headers=auth(77))).json()
    assert mine["booking_blocked"] is True and mine["has_appointment"] is False


async def test_other_users_and_unban(client, mocks):
    await ban(client, "77")
    mine = (await client.get(f"{P}/my_appointment", headers=auth(78))).json()
    assert mine["booking_blocked"] is False
    r = await client.delete(f"{P}/admin/api/bans/77", auth=ADMIN, headers=ACT)
    assert r.status_code == 200
    r = await client.post(f"{P}/book", json=booking(), headers=auth(77))
    assert r.json()["status"] == "success"
    r = await client.delete(f"{P}/admin/api/bans/77", auth=ADMIN, headers=ACT)
    assert r.status_code == 404


async def test_existing_appointment_can_be_cancelled(client, mocks):
    await client.post(f"{P}/book", json=booking(), headers=auth(79))
    await ban(client, "79")
    mine = (await client.get(f"{P}/my_appointment", headers=auth(79))).json()
    assert mine["has_appointment"] is True and mine["booking_blocked"] is True
    r = await client.post(f"{P}/cancel", headers=auth(79))
    assert r.json()["status"] == "success"


async def test_admin_list_and_appointment_flag(client):
    await client.post(f"{P}/book", json=booking(), headers=auth(80))
    await ban(client, "80", "не приходит")
    assert (await ban(client, "80", "три неявки подряд"))["created"] is False
    items = (await client.get(f"{P}/admin/api/bans", auth=ADMIN)).json()["items"]
    assert len(items) == 1
    assert items[0]["user_id"] == "80" and items[0]["reason"] == "три неявки подряд"
    assert items[0]["appointments"] == 1 and items[0]["created_by"] == "admin"
    appts = (await client.get(f"{P}/admin/api/appointments", auth=ADMIN)).json()["items"]
    assert appts[0]["banned"] is True


async def test_ban_requires_action_header_and_valid_id(client):
    r = await client.post(f"{P}/admin/api/bans", json={"user_id": "77"}, auth=ADMIN)
    assert r.status_code == 403
    r = await client.post(f"{P}/admin/api/bans", json={"user_id": "abc"}, auth=ADMIN, headers=ACT)
    assert r.status_code == 422
