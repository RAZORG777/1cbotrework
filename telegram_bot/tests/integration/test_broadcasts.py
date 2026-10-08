"""Рассылки и согласие на новости (specs/007-broadcasts/contracts/broadcasts.md)."""

from __future__ import annotations

import asyncio
import json
from datetime import timedelta

import httpx
import pytest
from sqlalchemy import select

from app import broadcasts, texts
from app.db import init_db, make_engine, make_session_factory, now_msk, session_scope
from app.models import Appointment, Base, Broadcast, BroadcastRecipient, Subscriber
from app.reminders import run_retention
from tests.helpers import TG_SECRET, auth, booking

ADMIN = ("admin", "admin-pass")
ACT = {"X-Admin-Request": "1"}
API = "/admin/api/broadcasts"
HOOK = {"X-Telegram-Bot-Api-Secret-Token": TG_SECRET}
JPEG = b"\xff\xd8\xff\xe0" + b"0" * 64
_update = iter(range(1000, 100000))


@pytest.fixture(autouse=True)
def media(tmp_path, monkeypatch):
    monkeypatch.setattr(broadcasts, "MEDIA_DIR", tmp_path / "media")
    monkeypatch.setattr(broadcasts, "PAUSE", 0)


def message(chat_id: int, text: str = "/start") -> dict:
    return {
        "update_id": next(_update),
        "message": {"chat": {"id": chat_id}, "text": text, "from": {"first_name": "Тест"}},
    }


def callback(chat_id: int, data: str) -> dict:
    return {
        "update_id": next(_update),
        "callback_query": {
            "id": f"cb{chat_id}{data}",
            "data": data,
            "from": {"id": chat_id},
            "message": {"message_id": 5, "chat": {"id": chat_id}},
        },
    }


def tg_bodies(mocks, method: str) -> list[dict]:
    out = []
    for call in mocks["tg"].calls:
        if call.request.url.path.endswith("/" + method):
            content = call.request.content
            try:
                out.append(json.loads(content))
            except ValueError:
                out.append({"multipart": content})
    return out


async def users(client, *specs):
    """specs: (chat_id, ответ на вопрос: 'n:yes' | 'n:no' | None)."""
    for chat_id, answer in specs:
        await client.post("/admin/webhook", json=message(chat_id), headers=HOOK)
        if answer:
            await client.post("/admin/webhook", json=callback(chat_id, answer), headers=HOOK)


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


# --- Согласие ------------------------------------------------------------------------------


async def test_start_asks_once_and_saves_answer(client, mocks, app):
    await client.post("/admin/webhook", json=message(11), headers=HOOK)
    texts_sent = [b["text"] for b in tg_bodies(mocks, "sendMessage")]
    assert texts_sent[0].startswith("Здравствуйте") and texts_sent[1] == texts.NEWS_QUESTION
    question = tg_bodies(mocks, "sendMessage")[1]["reply_markup"]["inline_keyboard"][0]
    assert [b["callback_data"] for b in question] == ["n:yes", "n:no"]

    await client.post("/admin/webhook", json=callback(11, "n:yes"), headers=HOOK)
    assert tg_bodies(mocks, "sendMessage")[-1]["text"] == texts.NEWS_YES
    assert tg_bodies(mocks, "editMessageReplyMarkup")  # кнопки вопроса убраны
    with session_scope(app.state.session_factory) as s:
        sub = s.get(Subscriber, "11")
        assert sub.news_consent is True and sub.consent_at is not None

    before = len(tg_bodies(mocks, "sendMessage"))
    await client.post("/admin/webhook", json=message(11), headers=HOOK)
    assert len(tg_bodies(mocks, "sendMessage")) == before + 1  # только приветствие
    await client.post("/admin/webhook", json=message(11, "/news"), headers=HOOK)
    assert tg_bodies(mocks, "sendMessage")[-1]["text"] == texts.NEWS_QUESTION


async def test_unsubscribe_button(client, mocks, app):
    await users(client, (12, "n:yes"))
    await client.post("/admin/webhook", json=callback(12, "n:off"), headers=HOOK)
    assert tg_bodies(mocks, "sendMessage")[-1]["text"] == texts.UNSUBSCRIBED
    with session_scope(app.state.session_factory) as s:
        assert s.get(Subscriber, "12").news_consent is False


async def test_booking_adds_subscriber(client, app):
    await client.post("/book", json=booking(), headers=auth(77))
    with session_scope(app.state.session_factory) as s:
        sub = s.get(Subscriber, "77")
        assert sub is not None and sub.news_consent is None


# --- Текст ---------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Скидка <b>20%</b> & подарок", "Скидка <b>20%</b> &amp; подарок"),
        (
            '<a href="https://yasno-vizhu.com">сайт</a> 2 > 1',
            '<a href="https://yasno-vizhu.com">сайт</a> 2 &gt; 1',
        ),
        ("уже &amp; готово", "уже &amp; готово"),
    ],
)
def test_normalize_ok(raw, expected):
    assert broadcasts.normalize_text(raw) == (expected, None)


@pytest.mark.parametrize(
    ("raw", "word"),
    [
        ("", "Напишите"),
        ("<b>не закрыт", "Не закрыт"),
        ("<b><i>криво</b></i>", "не по порядку"),
        ("строка<br>строка", "не поддерживается"),
        ('<a href="javascript:x">x</a>', "не поддерживается"),
    ],
)
def test_normalize_errors(raw, word):
    markup, error = broadcasts.normalize_text(raw)
    assert markup == "" and word in error


# --- Аудитория и запуск -------------------------------------------------------------------


async def test_audience_counts(client, mocks):
    await users(client, (21, "n:yes"), (22, "n:no"), (23, None))
    await client.post("/book", json=booking(), headers=auth(21))

    async def count(**params):
        r = await client.get(f"{API}/audience", params=params, auth=ADMIN)
        return r.json()["count"]

    assert await count(kind="service") == 3
    assert await count(kind="promo") == 1
    assert await count(kind="service", audience="active") == 1
    assert await count(kind="service", audience="branch", branch="Профсоюзная") == 1
    assert await count(kind="service", audience="branch", branch="Новые Ватутинки") == 0


async def test_promo_broadcast_only_to_consented(client, mocks, app):
    await users(client, (31, "n:yes"), (32, "n:no"), (33, None), (34, "n:yes"))
    mocks["tg"].reset()
    body = draft(kind="promo", text="Акция <b>недели</b>", button={"type": "book"})
    r = await client.post(API, json=body, auth=ADMIN, headers=ACT)
    assert r.status_code == 200 and r.json()["total"] == 2
    data = await wait_done(client, r.json()["id"])
    assert data["status"] == "done" and data["sent"] == 2 and data["failed"] == 0
    sent = tg_bodies(mocks, "sendMessage")
    assert sorted(b["chat_id"] for b in sent) == ["31", "34"]
    rows = sent[0]["reply_markup"]["inline_keyboard"]
    assert rows[0][0]["text"] == "Записаться" and "web_app" in rows[0][0]
    assert rows[1][0] == {"text": "Отписаться", "callback_data": "n:off"}
    assert sent[0]["text"] == "Акция <b>недели</b>"
    with session_scope(app.state.session_factory) as s:
        assert s.scalars(select(BroadcastRecipient)).all() == []  # строки получателей удалены


async def test_service_broadcast_and_blocked_user(client, mocks, app):
    await users(client, (41, None), (42, "n:no"))

    def respond(request):
        body = json.loads(request.content) if request.content.startswith(b"{") else {}
        if body.get("chat_id") == "42":
            return httpx.Response(
                403, json={"ok": False, "description": "Forbidden: bot was blocked by the user"}
            )
        return httpx.Response(200, json={"ok": True, "result": {}})

    mocks["tg"].side_effect = respond
    r = await client.post(
        API,
        json=draft(button={"type": "url", "text": "Подробнее", "url": "https://x.ru"}),
        auth=ADMIN,
        headers=ACT,
    )
    data = await wait_done(client, r.json()["id"])
    assert (data["sent"], data["blocked"]) == (1, 1)
    sent = [b for b in tg_bodies(mocks, "sendMessage") if b["chat_id"] == "41"][-1]
    assert sent["reply_markup"]["inline_keyboard"] == [
        [{"text": "Подробнее", "url": "https://x.ru"}]
    ]
    with session_scope(app.state.session_factory) as s:
        assert s.get(Subscriber, "42").blocked_at is not None
    count = (await client.get(f"{API}/audience", auth=ADMIN)).json()["count"]
    assert count == 1
    # Пользователь написал боту снова — отметка блокировки снимается.
    mocks["tg"].side_effect = None
    await client.post("/admin/webhook", json=message(42, "привет"), headers=HOOK)
    assert (await client.get(f"{API}/audience", auth=ADMIN)).json()["count"] == 2


async def test_rate_limit_retry(client, mocks):
    await users(client, (51, None))
    answers = iter(
        [
            httpx.Response(429, json={"ok": False, "parameters": {"retry_after": 0}}),
            httpx.Response(200, json={"ok": True, "result": {}}),
        ]
    )
    mocks["tg"].side_effect = lambda request: next(answers)
    r = await client.post(API, json=draft(), auth=ADMIN, headers=ACT)
    data = await wait_done(client, r.json()["id"])
    assert data["sent"] == 1 and data["failed"] == 0


async def test_draft_validation_and_no_recipients(client):
    r = await client.post(API, json=draft(text="<b>x"), auth=ADMIN, headers=ACT)
    assert r.status_code == 422 and r.json()["error"] == "BAD_DRAFT"
    r = await client.post(API, json=draft(kind="promo"), auth=ADMIN, headers=ACT)
    assert r.status_code == 409 and r.json()["error"] == "NO_RECIPIENTS"
    r = await client.post(
        API, json=draft(audience="branch", branch="Луна"), auth=ADMIN, headers=ACT
    )
    assert r.status_code == 422
    long_caption = draft(text="а" * 1100, image="0" * 32 + ".jpg")
    assert (await client.post(API, json=long_caption, auth=ADMIN, headers=ACT)).status_code == 422
    assert (await client.post(API, json=draft(), auth=ADMIN)).status_code == 403  # без заголовка


async def test_image_upload_and_photo_send(client, mocks):
    bad = await client.post(f"{API}/image", content=b"GIF89a", auth=ADMIN, headers=ACT)
    assert bad.status_code == 422 and bad.json()["error"] == "BAD_IMAGE"
    r = await client.post(
        f"{API}/image", content=JPEG, auth=ADMIN, headers={**ACT, "Content-Type": "image/jpeg"}
    )
    name = r.json()["image"]
    assert broadcasts.IMAGE_RE.match(name)
    assert (await client.get(f"{API}/image/{name}", auth=ADMIN)).content == JPEG
    assert (await client.get(f"{API}/image/..%2F..%2Fbot.db", auth=ADMIN)).status_code == 404

    await users(client, (61, None), (62, None))

    def respond(request):
        result = {"photo": [{"file_id": "small"}, {"file_id": "BIG"}]}
        return httpx.Response(200, json={"ok": True, "result": result})

    mocks["tg"].side_effect = respond
    r = await client.post(API, json=draft(image=name), auth=ADMIN, headers=ACT)
    await wait_done(client, r.json()["id"])
    photos = tg_bodies(mocks, "sendPhoto")
    assert "multipart" in photos[0] and b"Content-Disposition" in photos[0]["multipart"]
    assert photos[1]["photo"] == "BIG"  # картинка загружена один раз


async def test_test_send_only_to_admins(client, mocks):
    r = await client.post(f"{API}/test", json={**draft(), "chat_id": "5"}, auth=ADMIN, headers=ACT)
    assert r.status_code == 403
    r = await client.post(
        f"{API}/test", json={**draft(), "chat_id": "100"}, auth=ADMIN, headers=ACT
    )
    assert r.status_code == 200
    assert tg_bodies(mocks, "sendMessage")[-1]["chat_id"] == "100"


async def test_stop_and_resume(client, mocks, app, monkeypatch):
    state = app.state
    with session_scope(state.session_factory) as s:
        now = now_msk()
        for i in range(30):
            s.add(Subscriber(user_id=str(900 + i), first_seen_at=now, last_seen_at=now))
    monkeypatch.setattr(broadcasts, "PAUSE", 0.02)
    r = await client.post(API, json=draft(), auth=ADMIN, headers=ACT)
    bid = r.json()["id"]
    await asyncio.sleep(0.1)
    assert (await client.post(f"{API}/{bid}/stop", auth=ADMIN, headers=ACT)).status_code == 200
    data = await wait_done(client, bid)
    assert data["status"] == "stopped" and 0 < data["sent"] < 30

    # «Перезапуск»: незавершённая рассылка с отмеченными получателями продолжается.
    with session_scope(state.session_factory) as s:
        bc = Broadcast(
            created_at=now,
            kind="service",
            audience="all",
            text="Продолжение",
            status="sending",
            total=3,
            sent=1,
            started_at=now,
        )
        s.add(bc)
        s.flush()
        bid = bc.id
        s.add(BroadcastRecipient(broadcast_id=bid, user_id="900", state="sent"))
        s.add(BroadcastRecipient(broadcast_id=bid, user_id="901", state="pending"))
        s.add(BroadcastRecipient(broadcast_id=bid, user_id="902", state="pending"))
    mocks["tg"].reset()
    assert broadcasts.resume(state) == 1
    data = await wait_done(client, bid)
    assert data["status"] == "done" and data["sent"] == 3
    assert sorted(b["chat_id"] for b in tg_bodies(mocks, "sendMessage")) == ["901", "902"]


async def test_list_shows_stats(client):
    await users(client, (71, "n:yes"), (72, "n:no"), (73, None))
    data = (await client.get(API, auth=ADMIN)).json()
    assert data["subscribers"] == {
        "total": 3,
        "consent_yes": 1,
        "consent_no": 1,
        "not_asked": 1,
        "blocked": 0,
    }
    assert data["branches"] == ["Профсоюзная", "Новые Ватутинки"]


# --- Хранение ------------------------------------------------------------------------------


def test_retention_removes_long_blocked(tmp_path):
    engine = make_engine(tmp_path / "r.db")
    init_db(engine, tmp_path / "r.db")
    factory = make_session_factory(engine)
    now = now_msk()
    with session_scope(factory) as s:
        s.add(
            Subscriber(
                user_id="1",
                first_seen_at=now,
                last_seen_at=now,
                blocked_at=now - timedelta(days=40),
            )
        )
        s.add(
            Subscriber(
                user_id="2", first_seen_at=now, last_seen_at=now, blocked_at=now - timedelta(days=2)
            )
        )
        s.add(Subscriber(user_id="3", first_seen_at=now, last_seen_at=now, news_consent=False))
    with session_scope(factory) as s:
        assert run_retention(s, 30, now)["users"] == 1
    with session_scope(factory) as s:
        assert sorted(s.scalars(select(Subscriber.user_id))) == ["2", "3"]


def test_migration_v3_seeds_from_appointments(tmp_path):
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
    with engine.connect() as conn:
        assert conn.exec_driver_sql("PRAGMA user_version").scalar() == 3
