"""Этап 1 (T006): нормализация телефона и даты рождения до отправки в 1С."""

from datetime import date

import pytest

from app.patient import BAD_BIRTH_DATE, BAD_PHONE, normalize_birth_date, normalize_phone

TODAY = date(2026, 9, 25)


@pytest.mark.parametrize(
    "raw",
    [
        "+7 (999) 123-45-67",
        "89991234567",
        "79991234567",
        "+79991234567",
        "9991234567",
        " 8 999 123 45 67 ",
    ],
)
def test_phone_normalized(raw):
    assert normalize_phone(raw) == "+79991234567"


@pytest.mark.parametrize(
    "raw", ["", "+7 (999) 123-45", "999123456", "+1 (999) 123-45-67", "123456789012"]
)
def test_phone_bad(raw):
    with pytest.raises(ValueError, match=BAD_PHONE):
        normalize_phone(raw)


@pytest.mark.parametrize("raw", ["31.12.1990", "1990-12-31", " 31.12.1990 "])
def test_birth_date_normalized(raw):
    assert normalize_birth_date(raw, TODAY) == "1990-12-31"


def test_birth_date_today_allowed():
    assert normalize_birth_date("25.09.2026", TODAY) == "2026-09-25"


@pytest.mark.parametrize(
    "raw", ["", "31.02.2000", "26.09.2026", "1899-12-31", "01.01.0001", "1990/12/31", "31-12-1990"]
)
def test_birth_date_bad(raw):
    with pytest.raises(ValueError, match=BAD_BIRTH_DATE):
        normalize_birth_date(raw, TODAY)
