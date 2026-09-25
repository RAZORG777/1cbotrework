"""T036: проверка подписи Telegram initData."""

import time

import pytest

from app.auth import OPEN_FROM_BOT, SESSION_EXPIRED, InitDataError, verify_init_data
from tests.helpers import TOKEN, make_init_data


def test_valid():
    user = verify_init_data(make_init_data(42), TOKEN, 24)
    assert user.id == "42"


@pytest.mark.parametrize(
    "raw",
    [
        "",
        make_init_data(42, bad_hash=True),
        make_init_data(42, token="999:OTHER"),
        make_init_data(42).replace("&hash=", "&nohash="),
    ],
)
def test_invalid(raw):
    with pytest.raises(InitDataError) as exc:
        verify_init_data(raw, TOKEN, 24)
    assert exc.value.code == OPEN_FROM_BOT


def test_tampered_user():
    raw = make_init_data(42).replace("%22id%22%3A42", "%22id%22%3A43")
    with pytest.raises(InitDataError):
        verify_init_data(raw, TOKEN, 24)


def test_expired():
    raw = make_init_data(42, auth_date=int(time.time()) - 25 * 3600)
    with pytest.raises(InitDataError) as exc:
        verify_init_data(raw, TOKEN, 24)
    assert exc.value.code == SESSION_EXPIRED
