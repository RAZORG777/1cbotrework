"""T059: fail-fast по обязательным секретам и Basic-авторизация админки."""

import pytest
from pydantic import ValidationError

from app.config import Settings, load_settings

BASE = dict(
    MAX_BOT_TOKEN="t",
    MAX_WEBHOOK_SECRET="secret",
    MAX_MINIAPP="bot",
    WEBAPP_URL="https://a.test",
    PD_POLICY_URL="https://p.test",
    ONEC_URL="http://1c",
    ONEC_USER="u",
    ONEC_PASSWORD="p",
    ONEC_WEBHOOK_SECRET="x",
    ADMIN_PASSWORD="a",
)


@pytest.mark.parametrize(
    "missing",
    ["ADMIN_PASSWORD", "ONEC_WEBHOOK_SECRET", "MAX_WEBHOOK_SECRET", "MAX_BOT_TOKEN"],
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
    assert (await client.get("/max/admin")).status_code == 401
    assert (await client.get("/max/admin", auth=("admin", "wrong"))).status_code == 401
    assert (await client.get("/max/admin", auth=("admin", "5069522709"))).status_code == 401
    r = await client.get("/max/admin", auth=("admin", "admin-pass"))
    assert r.status_code == 200 and "Панель управления" in r.text
    assert (await client.get("/max/admin/logs", auth=("admin", "admin-pass"))).status_code == 200


async def test_miniapp_resolved_from_me(settings, mocks):
    """MAX_MINIAPP пуст или указана ссылка — кнопка open_app получает ник бота из GET /me."""
    from app.main import create_app
    from tests.helpers import MAX

    mocks.get(f"{MAX}/me").respond(json={"user_id": 1, "username": "yasno_vizhu_bot"})
    for value in ("", "https://1cmed.one-two.online/max"):
        s = settings.model_copy(update={"MAX_MINIAPP": value})
        app = create_app(s, retry_pause=0)
        async with app.router.lifespan_context(app):
            assert s.MAX_MINIAPP == "yasno_vizhu_bot"


async def test_max_error_body_logged(app, mocks):
    from app.logging import log_records
    from tests.helpers import MAX

    mocks.post(f"{MAX}/messages").respond(
        400, json={"code": "proto.payload", "message": "bad button"}
    )
    assert await app.state.messenger.send_message("5", "текст") is False
    assert any("proto.payload bad button" in r["message"] for r in log_records)


async def test_admin_lockout_after_failures(client):
    """10 неудачных входов с одного адреса — блокировка (429), даже с верным паролем."""
    hdr = {"X-Real-IP": "203.0.113.7"}
    for _ in range(10):
        r = await client.get("/max/admin", auth=("admin", "wrong"), headers=hdr)
        assert r.status_code == 401
    r = await client.get("/max/admin", auth=("admin", "admin-pass"), headers=hdr)
    assert r.status_code == 429 and int(r.headers["retry-after"]) > 0
    other = await client.get(
        "/max/admin", auth=("admin", "admin-pass"), headers={"X-Real-IP": "198.51.100.1"}
    )
    assert other.status_code == 200


async def test_security_headers(client):
    r = await client.get("/max/healthz")
    assert r.headers["x-content-type-options"] == "nosniff"
    assert "max-age" in r.headers["strict-transport-security"]
    assert "https://web.max.ru" in r.headers["content-security-policy"]
    a = await client.get("/max/admin", auth=("admin", "admin-pass"))
    assert a.headers["x-frame-options"] == "DENY"
    assert "frame-ancestors 'none'" in a.headers["content-security-policy"]


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
