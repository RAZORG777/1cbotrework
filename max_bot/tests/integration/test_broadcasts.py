"""Рассылки и согласие на новости в MAX (specs/007-broadcasts/contracts/broadcasts.md)."""

from __future__ import annotations

import asyncio
import json
from datetime import timedelta
from itertools import count

import httpx
import pytest
from sqlalchemy import select

from app import broadcasts
from app.db import init_db, make_engine, make_session_factory, now_msk, session_scope
from app.models import Appointment, Base, Broadcast, BroadcastRecipient, Subscriber
from app.reminders import run_retention
from tests.helpers import MAX_SECRET, auth, booking

ADMIN = ("admin", "admin-pass")
ACT = {"X-Admin-Request": "1"}
API = "/max/admin/api/broadcasts"
HOOK = {"X-Max-Bot-Api-Secret": MAX_SECRET}
JPEG = b"\xff\xd8\xff\xe0" + b"0" * 64
_n = count(1000)


@pytest.fixture(autouse=True)
def media(tmp_path, monkeypatch):
    monkeypatch.setattr(broadcasts, "MEDIA_DIR", tmp_path / "media")
    monkeypatch.setattr(broadcasts, "PAUSE", 0)


def started(user_id: int) -> dict:
    return {
        "update_type": "bot_started",
        "timestamp": next(_n),
        "user_id": user_id,
        "user": {"user_id": user_id, "name": "Тест"},
    }


def text_message(user_id: int, text: str) -> dict:
    return {
        "update_type": "message_created",
        "timestamp": next(_n),
        "message": {
            "sender": {"user_id": user_id, "name": "Тест"},
            "body": {"mid": f"m{next(_n)}", "text": text},
        },
    }


def callback(user_id: int, payload: str) -> dict:
    n = next(_n)
    return {
        "update_type": "message_callback",
        "timestamp": n,
        "callback": {"callback_id": f"cb-{n}", "payload": payload, "user": {"user_id": user_id}},
        "message": {"body": {"mid": f"mid-{n}", "text": "Присылать вам новости…"}},
    }


def sent(mocks) -> list[tuple[str, dict]]:
    """(user_id, тело) всех POST /messages."""
    return [
        (c.request.url.params.get("user_id"), json.loads(c.request.content))
        for c in mocks["msg"].calls
    ]


def buttons(body: dict) -> list:
    for att in body.get("attachments", []):
        if att["type"] == "inline_keyboard":
            return att["payload"]["buttons"]
    return []


async def users(client, *specs):
    for user_id, answer in specs:
        await client.post("/max/webhook", json=started(user_id), headers=HOOK)
        if answer:
            await client.post("/max/webhook", json=callback(user_id, answer), headers=HOOK)


async def wait_done(client, broadcast_id: int) -> dict:
    for _ in range(200):
        data = (await client.get(f"{API}/{broadcast_id}", auth=ADMIN)).json()
        if data["status"] != "sending" and not data["running"]:
            return data
        await asyncio.sleep(0.02)
    raise AssertionError("рассылка не завершилась")


def draft(**kw) -> dict:
    body = {"kind": "service", "audience": "all", "text": "Технические работы <b>завтра</b>"}
    body.update(kw)
    return body


async def test_start_asks_once_and_saves_answer(client, mocks, app):
    await client.post("/max/webhook", json=started(11), headers=HOOK)
    msgs = sent(mocks)
    assert msgs[0][1]["text"].startswith("Здравствуйте")
    assert msgs[1][1]["text"].startswith("Присылать")
    assert [b["payload"] for b in buttons(msgs[1][1])[0]] == ["news:yes", "news:no"]

    await client.post("/max/webhook", json=callback(11, "news:yes"), headers=HOOK)
    answer = json.loads(mocks["answers"].calls.last.request.content)
    assert answer["message"]["text"].endswith(
        "Отписаться можно кнопкой в любой рассылке или командой /news."
    )
    assert answer["message"]["attachments"] == []  # кнопки вопроса убраны
    with session_scope(app.state.session_factory) as s:
        assert s.get(Subscriber, "11").news_consent is True

    before = mocks["msg"].call_count
    await client.post("/max/webhook", json=started(11), headers=HOOK)
    assert mocks["msg"].call_count == before + 1  # только приветствие
    await client.post("/max/webhook", json=text_message(11, "/news"), headers=HOOK)
    assert sent(mocks)[-1][1]["text"].startswith("Присылать")


async def test_unsubscribe_button(client, mocks, app):
    await users(client, (12, "news:yes"))
    await client.post("/max/webhook", json=callback(12, "news:off"), headers=HOOK)
    assert sent(mocks)[-1][1]["text"].startswith("Вы отписались")
    with session_scope(app.state.session_factory) as s:
        assert s.get(Subscriber, "12").news_consent is False


async def test_booking_adds_subscriber(client, app):
    await client.post("/max/book", json=booking(), headers=auth(77))
    with session_scope(app.state.session_factory) as s:
        assert s.get(Subscriber, "77") is not None


async def test_audience_counts(client):
    await users(client, (21, "news:yes"), (22, "news:no"), (23, None))
    await client.post("/max/book", json=booking(), headers=auth(21))

    async def n(**params):
        return (await client.get(f"{API}/audience", params=params, auth=ADMIN)).json()["count"]

    assert await n(kind="service") == 3
    assert await n(kind="promo") == 1
    assert await n(kind="service", audience="active") == 1
    assert await n(kind="service", audience="branch", branch="Новые Ватутинки") == 0


async def test_promo_broadcast_with_image(client, mocks):
    await users(client, (31, "news:yes"), (32, "news:no"), (33, "news:yes"))
    r = await client.post(
        f"{API}/image", content=JPEG, auth=ADMIN, headers={**ACT, "Content-Type": "image/jpeg"}
    )
    name = r.json()["image"]
    public = await client.get(f"/max/media/broadcasts/{name}")  # без авторизации — для MAX
    assert public.status_code == 200 and public.content == JPEG
    assert (await client.get("/max/media/broadcasts/..%2Fbot.db")).status_code == 404

    mocks["msg"].reset()
    body = draft(kind="promo", image=name, button={"type": "book"}, text="Акция " + "а" * 1500)
    r = await client.post(API, json=body, auth=ADMIN, headers=ACT)  # в MAX подпись не 1024
    assert r.status_code == 200 and r.json()["total"] == 2
    data = await wait_done(client, r.json()["id"])
    assert data["status"] == "done" and data["sent"] == 2
    msgs = sent(mocks)
    assert sorted(u for u, _ in msgs) == ["31", "33"]
    att = msgs[0][1]["attachments"]
    assert att[0] == {
        "type": "image",
        "payload": {"url": f"https://app.test/max/media/broadcasts/{name}"},
    }
    rows = buttons(msgs[0][1])
    assert rows[0][0]["type"] == "open_app" and rows[0][0]["text"] == "Записаться"
    assert rows[1][0] == {"type": "callback", "text": "Отписаться", "payload": "news:off"}


async def test_blocked_and_rate_limit(client, mocks, app):
    await users(client, (41, None), (42, None))
    first = {"41": True}

    def respond(request):
        uid = request.url.params.get("user_id")
        if uid == "42":
            return httpx.Response(403, json={"code": "chat.denied", "message": "chat.denied"})
        if first.pop(uid, False):
            return httpx.Response(429, json={"code": "too.many.requests"})
        return httpx.Response(200, json={"message": {}})

    mocks["msg"].side_effect = respond
    r = await client.post(API, json=draft(), auth=ADMIN, headers=ACT)
    data = await wait_done(client, r.json()["id"])
    assert (data["sent"], data["blocked"], data["failed"]) == (1, 1, 0)
    with session_scope(app.state.session_factory) as s:
        assert s.get(Subscriber, "42").blocked_at is not None


async def test_test_send_and_validation(client, mocks):
    r = await client.post(f"{API}/test", json={**draft(), "chat_id": "5"}, auth=ADMIN, headers=ACT)
    assert r.status_code == 403
    r = await client.post(
        f"{API}/test", json={**draft(), "chat_id": "100"}, auth=ADMIN, headers=ACT
    )
    assert r.status_code == 200 and sent(mocks)[-1][0] == "100"
    r = await client.post(API, json=draft(text="<i>x"), auth=ADMIN, headers=ACT)
    assert r.status_code == 422
    assert (
        await client.post(API, json=draft(kind="promo"), auth=ADMIN, headers=ACT)
    ).status_code == 409


async def test_stop_and_resume(client, mocks, app, monkeypatch):
    state = app.state
    now = now_msk()
    with session_scope(state.session_factory) as s:
        for i in range(30):
            s.add(Subscriber(user_id=str(900 + i), first_seen_at=now, last_seen_at=now))
    monkeypatch.setattr(broadcasts, "PAUSE", 0.02)
    bid = (await client.post(API, json=draft(), auth=ADMIN, headers=ACT)).json()["id"]
    await asyncio.sleep(0.1)
    await client.post(f"{API}/{bid}/stop", auth=ADMIN, headers=ACT)
    data = await wait_done(client, bid)
    assert data["status"] == "stopped" and 0 < data["sent"] < 30

    with session_scope(state.session_factory) as s:
        bc = Broadcast(
            created_at=now,
            kind="service",
            audience="all",
            text="Дальше",
            status="sending",
            total=2,
            started_at=now,
        )
        s.add(bc)
        s.flush()
        bid = bc.id
        s.add(BroadcastRecipient(broadcast_id=bid, user_id="900", state="sent"))
        s.add(BroadcastRecipient(broadcast_id=bid, user_id="901", state="pending"))
    mocks["msg"].reset()
    assert broadcasts.resume(state) == 1
    await wait_done(client, bid)
    assert [u for u, _ in sent(mocks)] == ["901"]


def test_retention_and_migration(tmp_path):
    db = tmp_path / "m.db"
    engine = make_engine(db)
    Base.metadata.create_all(engine)
    factory = make_session_factory(engine)
    now = now_msk()
    with session_scope(factory) as s:
        s.add(Appointment(user_id="555", appointment_id="a", visit_at=now, created_at=now))
    with engine.begin() as conn:
        conn.exec_driver_sql("PRAGMA user_version = 2")
    init_db(engine, db)
    with session_scope(factory) as s:
        assert s.get(Subscriber, "555") is not None
        s.get(Subscriber, "555").blocked_at = now - timedelta(days=40)
    with session_scope(factory) as s:
        assert run_retention(s, 30, now)["users"] == 1
        assert s.scalars(select(Subscriber)).all() == []
