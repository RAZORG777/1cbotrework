"""T059: fail-fast по обязательным секретам и Basic-авторизация админки."""

import pytest
from pydantic import ValidationError

from app.config import Settings, load_settings

BASE = dict(
    BOT_TOKEN="t",
    TG_WEBHOOK_SECRET="s",
    WEBAPP_URL="https://a.test",
    PD_POLICY_URL="https://p.test",
    ONEC_URL="http://1c",
    ONEC_USER="u",
    ONEC_PASSWORD="p",
    ONEC_WEBHOOK_SECRET="x",
    ADMIN_PASSWORD="a",
)


@pytest.mark.parametrize(
    "missing", ["ADMIN_PASSWORD", "ONEC_WEBHOOK_SECRET", "TG_WEBHOOK_SECRET", "BOT_TOKEN"]
)
def test_missing_required_exits(monkeypatch, capsys, missing):
    for k in list(BASE) + ["PD_RETENTION_DAYS"]:
        monkeypatch.delenv(k, raising=False)
    for k, v in BASE.items():
        if k != missing:
            monkeypatch.setenv(k, v)
    monkeypatch.setattr(Settings, "model_config", {**Settings.model_config, "env_file": None})
    with pytest.raises(SystemExit):
        load_settings()
    assert missing in capsys.readouterr().err


@pytest.mark.parametrize("value", ["0", "-1", "abc"])
def test_bad_retention(value):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **BASE, PD_RETENTION_DAYS=value)


def test_http_webapp_rejected():
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **{**BASE, "WEBAPP_URL": "http://a.test"})


def test_host_defaults_to_localhost():
    assert Settings(_env_file=None, **BASE).HOST == "127.0.0.1"


async def test_admin_auth(client):
    assert (await client.get("/admin")).status_code == 401
    assert (await client.get("/admin", auth=("admin", "wrong"))).status_code == 401
    assert (await client.get("/admin", auth=("admin", "5069522709"))).status_code == 401
    r = await client.get("/admin", auth=("admin", "admin-pass"))
    assert r.status_code == 200 and "Панель управления" in r.text
    assert (await client.get("/admin/logs", auth=("admin", "admin-pass"))).status_code == 200


def test_webhook_url_override(settings):
    """TG_WEBHOOK_URL — адрес воркера-посредника; пусто — прямой адрес сервера."""
    assert settings.webhook_url == "https://app.test/admin/webhook"
    relay = settings.model_copy(update={"TG_WEBHOOK_URL": "https://relay.workers.dev/telegram"})
    assert relay.webhook_url == "https://relay.workers.dev/telegram"


async def test_menu_button_set_on_start(settings, mocks):
    """При старте бот выставляет кнопку меню «Записаться» со ссылкой на форму."""
    import json

    from app.main import create_app

    s = settings.model_copy(update={"TG_SET_MENU_BUTTON": True})
    app = create_app(s, retry_pause=0)
    async with app.router.lifespan_context(app):
        await app.state.menu_task
    calls = [c for c in mocks["tg"].calls if c.request.url.path.endswith("/setChatMenuButton")]
    body = json.loads(calls[0].request.content)["menu_button"]
    assert body["type"] == "web_app" and body["text"] == "Записаться"
    assert body["web_app"]["url"].startswith("https://app.test")


async def test_bot_profile_set_on_start(settings, mocks):
    """Команды и описания выставляются при старте; совпадающее описание повторно не меняется."""
    import json

    import httpx

    from app import texts
    from app.main import create_app

    def respond(request):
        if request.url.path.endswith("/getMyDescription"):
            return httpx.Response(
                200, json={"ok": True, "result": {"description": texts.BOT_DESCRIPTION}}
            )
        if request.url.path.endswith("/getMyShortDescription"):
            return httpx.Response(200, json={"ok": True, "result": {"short_description": "старое"}})
        return httpx.Response(200, json={"ok": True, "result": True})

    mocks["tg"].side_effect = respond
    s = settings.model_copy(update={"TG_SET_MENU_BUTTON": True})
    app = create_app(s, retry_pause=0)
    async with app.router.lifespan_context(app):
        await app.state.menu_task
    sent = {
        c.request.url.path.rsplit("/", 1)[1]: json.loads(c.request.content)
        for c in mocks["tg"].calls
    }
    assert [c["command"] for c in sent["setMyCommands"]["commands"]] == ["start", "news"]
    assert sent["setMyShortDescription"] == {"short_description": texts.BOT_SHORT_DESCRIPTION}
    assert "setMyDescription" not in sent
    assert len(texts.BOT_SHORT_DESCRIPTION) <= 120 and len(texts.BOT_DESCRIPTION) <= 512


async def test_admin_lockout_after_failures(client):
    """10 неудачных входов с одного адреса — блокировка (429), даже с верным паролем."""
    hdr = {"X-Real-IP": "203.0.113.7"}
    for _ in range(10):
        r = await client.get("/admin", auth=("admin", "wrong"), headers=hdr)
        assert r.status_code == 401
    r = await client.get("/admin", auth=("admin", "admin-pass"), headers=hdr)
    assert r.status_code == 429 and int(r.headers["retry-after"]) > 0
    # Другой адрес не затронут.
    other = await client.get(
        "/admin", auth=("admin", "admin-pass"), headers={"X-Real-IP": "198.51.100.1"}
    )
    assert other.status_code == 200


async def test_security_headers(client):
    r = await client.get("/healthz")
    assert r.headers["x-content-type-options"] == "nosniff"
    assert "max-age" in r.headers["strict-transport-security"]
    assert "https://web.telegram.org" in r.headers["content-security-policy"]
    a = await client.get("/admin", auth=("admin", "admin-pass"))
    assert (
        a.headers["x-frame-options"] == "DENY"
        and "frame-ancestors 'none'" in a.headers["content-security-policy"]
    )


def test_backup_cleanup(tmp_path):
    import os
    import time

    from app.db import cleanup_backups

    db = tmp_path / "bot.db"
    old, fresh = tmp_path / "bot.db.bak-v0", tmp_path / "bot.db.bak-v1"
    old.write_text("x")
    fresh.write_text("x")
    long_ago = time.time() - 40 * 86400
    os.utime(old, (long_ago, long_ago))
    assert cleanup_backups(db, 30) == 1
    assert not old.exists() and fresh.exists()
