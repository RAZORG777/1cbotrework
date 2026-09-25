"""T057: вебхук Telegram — только с секретом, повтор update_id не обрабатывается."""

import json

from tests.helpers import TG_SECRET

HDR = {"X-Telegram-Bot-Api-Secret-Token": TG_SECRET}


def start(update_id=1, chat_id=500, text="/start"):
    return {
        "update_id": update_id,
        "message": {"chat": {"id": chat_id}, "from": {"first_name": "Анна"}, "text": text},
    }


async def test_requires_secret(client, mocks):
    r = await client.post("/admin/webhook", json=start())
    assert r.status_code == 401
    r = await client.post(
        "/admin/webhook", json=start(), headers={"X-Telegram-Bot-Api-Secret-Token": "x"}
    )
    assert r.status_code == 401
    assert not mocks["tg"].called


async def test_start_and_duplicate(client, mocks):
    r = await client.post("/admin/webhook", json=start(), headers=HDR)
    assert r.json() == {"status": "ok"}
    assert mocks["tg"].call_count == 2
    body = json.loads(mocks["tg"].calls.last.request.content)
    assert body["reply_markup"]["inline_keyboard"][0][0]["web_app"]["url"] == "https://app.test"
    await client.post("/admin/webhook", json=start(), headers=HDR)
    assert mocks["tg"].call_count == 2


async def test_stats_only_for_admin(client, mocks):
    await client.post("/admin/webhook", json=start(2, 999, "/stats"), headers=HDR)
    assert not mocks["tg"].called
    await client.post("/admin/webhook", json=start(3, 100, "/stats"), headers=HDR)
    assert mocks["tg"].call_count == 1


async def test_callback_answered(client, mocks):
    upd = {"update_id": 9, "callback_query": {"id": "cb1", "data": "x"}}
    await client.post("/admin/webhook", json=upd, headers=HDR)
    assert mocks["tg"].calls.last.request.url.path.endswith("/answerCallbackQuery")
