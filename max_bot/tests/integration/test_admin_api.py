"""Админка-инструмент разработчика (specs/006-admin-devtool/contracts/admin-api.md)."""

from __future__ import annotations

import asyncio
import json

import httpx
import pytest
from loguru import logger

from app import admin_tools
from tests.helpers import MAX, ONEC, PATIENT, auth, booking

ADMIN = ("admin", "admin-pass")
ACT = {"X-Admin-Request": "1"}
BASE = "/max/admin"
PII = [PATIENT["last_name"], PATIENT["first_name"], PATIENT["phone"], PATIENT["birth_date"]]


async def get(client, path, **kw):
    return await client.get(BASE + path, auth=ADMIN, **kw)


async def post(client, path, json_body=None, headers=ACT):
    return await client.post(BASE + path, auth=ADMIN, json=json_body or {}, headers=headers)


async def test_page_and_assets(client):
    r = await client.get(BASE, auth=ADMIN)
    assert r.status_code == 200 and "Панель управления" in r.text
    assert "frame-ancestors 'none'" in r.headers["content-security-policy"]
    assert r.headers["cache-control"] == "no-store"
    assert r.headers["x-frame-options"] == "DENY"
    for name in ("admin.css", "admin.js"):
        assert (await client.get(f"{BASE}/ui/{name}", auth=ADMIN)).status_code == 200
    assert (await client.get(f"{BASE}/ui/admin.css")).status_code == 401
    assert (await client.get(f"{BASE}/ui/..%2Fmain.py", auth=ADMIN)).status_code == 404


@pytest.mark.parametrize(
    "path",
    [
        "/api/overview",
        "/api/health",
        "/api/logs/tail",
        "/api/jobs",
        "/api/appointments",
        "/api/settings",
        "/api/templates",
        "/api/onec/ping",
        "/api/logs/files",
    ],
)
async def test_api_requires_auth(client, path):
    r = await client.get(BASE + path)
    assert r.status_code == 401 and r.headers["www-authenticate"] == "Basic"
    assert (await client.get(BASE + path, auth=("admin", "wrong"))).status_code == 401


async def test_post_requires_csrf_header(client):
    r = await client.post(f"{BASE}/api/logs/level", auth=ADMIN, json={"level": "DEBUG"})
    assert r.status_code == 403 and r.json() == {"error": "ADMIN_HEADER_REQUIRED"}
    r = await client.post(f"{BASE}/api/maintenance/restart", auth=ADMIN)
    assert r.status_code == 403


async def test_overview_counts_and_counters(client):
    await client.post("/max/book", json=booking(), headers=auth(5))
    o = (await get(client, "/api/overview")).json()
    assert o["bot"] == "max" and o["appointments"]["active"] == 1
    assert o["counters"]["bookings"] == 1 and o["counters"]["messages_sent"] >= 1
    assert o["jobs"]["total"] >= 3  # 2 напоминания + ночная очистка
    assert o["db"]["schema"] == 3 and o["log_level"] == "INFO"


async def test_health_checks(client, mocks):
    mocks.get(f"{ONEC}/ping", name="ping").respond(
        json={"status": "success", "message": "1C API is running!"}
    )
    mocks.get(f"{MAX}/me").respond(
        json={"user_id": 1, "name": "Ясно Вижу", "username": "yasno_vizhu_bot"}
    )
    mocks.get(f"{MAX}/subscriptions").respond(
        json={"subscriptions": [{"url": "https://old.trycloudflare.com/max/webhook", "time": 1}]}
    )
    checks = {c["name"]: c for c in (await get(client, "/api/health")).json()["checks"]}
    assert checks["db"]["ok"] and checks["scheduler"]["ok"]
    assert checks["onec"]["ok"] and checks["onec"]["detail"] == "1C API is running!"
    assert checks["bot"]["detail"] == "@yasno_vizhu_bot"
    wh = checks["webhook"]
    assert not wh["ok"] and wh["expected_url"] == "https://app.test/max/webhook"
    assert wh["url"] == "https://old.trycloudflare.com/max/webhook"


async def test_health_onec_down_is_fast(client, mocks, monkeypatch):
    monkeypatch.setattr(admin_tools, "CHECK_TIMEOUT", 0.2)
    mocks.get(f"{ONEC}/ping").mock(side_effect=httpx.ConnectError("down"))
    checks = {c["name"]: c for c in (await get(client, "/api/health")).json()["checks"]}
    assert not checks["onec"]["ok"] and checks["onec"]["detail"] == "нет соединения"


async def test_logs_tail_filters_and_level(client):
    logger.info("строка-маркер-один")
    logger.warning("предупреждение-маркер")
    data = (await get(client, "/api/logs/tail")).json()
    assert any("строка-маркер-один" in r["message"] for r in data["lines"])
    seq = data["seq"]
    logger.info("строка-после")
    newer = (await get(client, "/api/logs/tail", params={"after": seq})).json()["lines"]
    assert [r["message"] for r in newer] == ["строка-после"]
    warn = (await get(client, "/api/logs/tail", params={"level": "WARNING"})).json()["lines"]
    assert warn and all(r["level"] in ("WARNING", "ERROR") for r in warn)

    logger.debug("отладка-не-видна")
    assert "отладка-не-видна" not in (await get(client, "/api/logs/tail")).text
    r = await post(client, "/api/logs/level", {"level": "DEBUG"})
    assert r.json() == {"level": "DEBUG"}
    logger.debug("отладка-видна")
    assert "отладка-видна" in (await get(client, "/api/logs/tail")).text
    assert (await post(client, "/api/logs/level", {"level": "TRACE"})).status_code == 422


async def test_log_files_read_and_download(client):
    logger.error("ошибка-для-файла")
    files = (await get(client, "/api/logs/files")).json()["files"]
    name = files[0]["name"]
    assert name == "max_bot.log"
    data = (await get(client, "/api/logs/file", params={"name": name, "q": "ошибка-для"})).json()
    assert len(data["lines"]) == 1 and "| ERROR" in data["lines"][0]
    only_err = (await get(client, "/api/logs/file", params={"name": name, "level": "ERROR"})).json()
    assert all("| ERROR" in line for line in only_err["lines"])
    r = await get(client, "/api/logs/download", params={"name": name})
    assert r.status_code == 200 and "attachment" in r.headers["content-disposition"]
    for bad in ("../.env", "..\\.env", "/etc/passwd", "max_bot.log/../x"):
        assert (await get(client, "/api/logs/file", params={"name": bad})).status_code == 404
        assert (await get(client, "/api/logs/download", params={"name": bad})).status_code == 404


async def test_jobs_list_run_pause_delete(client, mocks):
    await client.post("/max/book", json=booking(), headers=auth(5))
    jobs = {j["id"]: j for j in (await get(client, "/api/jobs")).json()["jobs"]}
    assert jobs["rem24h_appt-1"]["kind"] == "reminder_24h"
    assert jobs["rem24h_appt-1"]["appointment_id"] == "appt-1"
    assert jobs["retention_cleanup"]["kind"] == "retention"

    assert (await post(client, "/api/jobs/rem2h_appt-1/pause")).status_code == 200
    jobs = {j["id"]: j for j in (await get(client, "/api/jobs")).json()["jobs"]}
    assert jobs["rem2h_appt-1"]["paused"] and jobs["rem2h_appt-1"]["run_at"] is None
    assert (await post(client, "/api/jobs/rem2h_appt-1/resume")).status_code == 200
    assert (await post(client, "/api/jobs/rem2h_appt-1/delete")).status_code == 200
    assert (await post(client, "/api/jobs/rem2h_appt-1/delete")).status_code == 404

    sent = mocks["msg"].call_count
    assert (await post(client, "/api/jobs/rem24h_appt-1/run")).status_code == 200
    for _ in range(50):
        await asyncio.sleep(0.05)
        if mocks["msg"].call_count > sent:
            break
    assert mocks["msg"].call_count > sent
    ids = {j["id"] for j in (await get(client, "/api/jobs")).json()["jobs"]}
    assert "rem24h_appt-1" not in ids
    assert (await post(client, "/api/jobs/nope/explode")).status_code == 422


async def test_appointments_without_pii_and_actions(client, mocks):
    await client.post("/max/book", json=booking(), headers=auth(5))
    r = await get(client, "/api/appointments")
    item = r.json()["items"][0]
    assert item["appointment_id"] == "appt-1" and item["user_id"] == "5"
    assert set(item["jobs"]) == {"rem24h_appt-1", "rem2h_appt-1"}
    for value in PII:
        assert value not in r.text
    assert (await get(client, "/api/appointments", params={"q": "zzz"})).json()["total"] == 0

    sent = mocks["msg"].call_count
    assert (
        await post(client, "/api/appointments/appt-1/remind", {"kind": "2h"})
    ).status_code == 200
    assert mocks["msg"].call_count == sent + 1
    body = json.loads(mocks["msg"].calls[-1].request.content)
    assert "callback" in json.dumps(body["attachments"])

    await post(client, "/api/jobs/rem24h_appt-1/delete")
    r = await post(client, "/api/appointments/appt-1/reschedule-reminders")
    assert r.json() == {"status": "ok", "scheduled": 2}

    r = await post(client, "/api/appointments/appt-1/close", {"status": "cancelled"})
    assert r.status_code == 200
    item = (await get(client, "/api/appointments", params={"status": "all"})).json()["items"][0]
    assert item["status"] == "cancelled" and item["jobs"] == []
    assert mocks["cancel"].call_count == 0  # 1С не вызывается
    assert (
        await post(client, "/api/appointments/appt-1/close", {"status": "finished"})
    ).status_code == 404


async def test_onec_console_read_only(client, mocks):
    r = (await get(client, "/api/onec/doctors", params={"branch": "Профсоюзная", "x": "1"})).json()
    assert r["http_status"] == 200 and r["body"][0]["id"] == "doc-1"
    assert mocks["doctors"].calls[-1].request.url.params.get("x") is None
    for method in ("book", "cancel", "reschedule", "confirm", "update_note"):
        assert (await get(client, f"/api/onec/{method}")).status_code == 404


async def test_templates_preview_and_send(client, mocks):
    data = (await get(client, "/api/templates")).json()
    keys = {t["key"] for t in data["templates"]}
    assert {"welcome", "booked", "reminder_24h", "cancelled_by_admin", "feedback"} <= keys
    assert data["recipients"] == ["100"]
    reminder = next(t for t in data["templates"] if t["key"] == "reminder_24h")
    assert reminder["buttons"][0] == [{"text": "Подтвердить визит", "tone": "success"}]

    r = await post(client, "/api/templates/booked/send", {"chat_id": "5"})
    assert r.status_code == 403 and r.json() == {"error": "NOT_ADMIN_RECIPIENT"}
    sent = mocks["msg"].call_count
    assert (await post(client, "/api/templates/booked/send", {"chat_id": "100"})).status_code == 200
    assert mocks["msg"].call_count == sent + 1
    assert (await post(client, "/api/templates/nope/send", {"chat_id": "100"})).status_code == 404


async def test_settings_hide_secrets(client, settings):
    r = await get(client, "/api/settings")
    rows = {s["name"]: s for s in r.json()["settings"]}
    assert rows["MAX_BOT_TOKEN"]["secret"] and rows["MAX_BOT_TOKEN"]["value"] == "задан"
    assert rows["ONEC_URL"]["value"] == ONEC
    for secret in admin_tools.secret_values(settings):
        assert secret not in r.text


async def test_no_secrets_or_pii_anywhere(client, settings, mocks):
    await client.post("/max/book", json=booking(), headers=auth(5))
    blobs = []
    for path in (
        "/api/overview",
        "/api/health",
        "/api/logs/tail",
        "/api/jobs",
        "/api/appointments?status=all",
        "/api/settings",
        "/api/templates",
    ):
        blobs.append((await get(client, path)).text)
    name = (await get(client, "/api/logs/files")).json()["files"][0]["name"]
    blobs.append((await get(client, "/api/logs/file", params={"name": name})).text)
    text = "\n".join(blobs)
    for value in PII + admin_tools.secret_values(settings):
        assert value not in text, value


async def test_webhook_register_and_maintenance(client, app, mocks):
    route = mocks.post(f"{MAX}/subscriptions").respond(json={"success": True})
    r = await post(client, "/api/webhook/register")
    assert r.json() == {"ok": True, "detail": ""}
    sent = json.loads(route.calls[-1].request.content)
    assert sent["url"] == "https://app.test/max/webhook" and sent["secret"]
    assert "message_callback" in sent["update_types"]

    r = await post(client, "/api/maintenance/retention")
    assert set(r.json()) == {"finished", "deleted", "events", "users"}

    stopped = []
    app.state.stop_process = lambda: stopped.append(True)
    assert (await post(client, "/api/maintenance/restart")).json() == {"status": "restarting"}
    await asyncio.sleep(0.7)
    assert stopped == [True]
    logs = (await get(client, "/api/logs/tail", params={"q": "Админка"})).json()["lines"]
    assert any("перезапуск бота (admin)" in r["message"] for r in logs)


async def test_legacy_endpoints_still_work(client):
    assert (await client.get(f"{BASE}/logs", auth=ADMIN)).status_code == 200
    await client.post("/max/book", json=booking(), headers=auth(5))
    r = await client.post(f"{BASE}/send-reminder?appointment_id=appt-1&kind=2h", auth=ADMIN)
    assert r.json() == {"status": "ok"}


async def test_onec_console_checks_params_before_1c(client, mocks):
    """Пустой или кривой doctor_id 1С не разбирает (HTTP 500) — запрос в 1С не уходит."""
    calls = mocks["schedule"].call_count
    for params, word in (
        ({}, "doctor_id"),
        ({"doctor_id": "1"}, "GUID"),
        ({"doctor_id": "8f2c1a4e-2b7d-11ef-a1b3-005056b0c0de"}, "дату"),
        ({"doctor_id": "8f2c1a4e-2b7d-11ef-a1b3-005056b0c0de", "date": "10.01.2030"}, "ГГГГ"),
    ):
        r = await get(client, "/api/onec/schedule", params=params)
        assert r.status_code == 422 and r.json()["error"] == "BAD_PARAMS"
        assert word in r.json()["message"]
    assert (await get(client, "/api/onec/services")).status_code == 422
    assert mocks["schedule"].call_count == calls
    ok = await get(
        client,
        "/api/onec/schedule",
        params={"doctor_id": "8f2c1a4e-2b7d-11ef-a1b3-005056b0c0de", "date": "2030-01-10"},
    )
    assert ok.json()["http_status"] == 200 and mocks["schedule"].call_count == calls + 1
