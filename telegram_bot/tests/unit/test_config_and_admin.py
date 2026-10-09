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
