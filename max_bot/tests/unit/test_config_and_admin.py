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
    ["ADMIN_PASSWORD", "ONEC_WEBHOOK_SECRET", "MAX_WEBHOOK_SECRET", "MAX_BOT_TOKEN", "MAX_MINIAPP"],
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
