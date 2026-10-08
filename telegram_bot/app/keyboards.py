"""Кнопки сообщений Telegram (specs/005-bot-messages). Тексты кнопок — app/texts.py.

Цвет: `style` = primary (синяя), success (зелёная), danger (красная), Bot API 9.4;
старые клиенты показывают обычные кнопки.
"""

from __future__ import annotations

from . import texts


def inline(*rows: list[dict]) -> dict:
    return {"inline_keyboard": [list(row) for row in rows if row]}


def route(branch: str | None) -> dict:
    return {"text": texts.BTN_ROUTE, "url": texts.branch_of(branch).route_url}


def my_booking(webapp_url: str) -> dict:
    return {"text": texts.BTN_MY, "web_app": {"url": webapp_url}}


def book(webapp_url: str) -> dict:
    return {"text": texts.BTN_BOOK, "web_app": {"url": webapp_url}, "style": "primary"}


def visit(branch: str | None, webapp_url: str) -> dict:
    """После записи и переноса: «Как добраться», «Моя запись»."""
    return inline([route(branch)], [my_booking(webapp_url)])


def book_again(webapp_url: str) -> dict:
    return inline([book(webapp_url)])


def welcome(webapp_url: str, site_url: str) -> dict:
    return inline([book(webapp_url)], [{"text": texts.BTN_SITE, "url": site_url}])


def reminder(appointment_id: str, confirmed: bool, branch: str | None) -> dict:
    """Напоминание: «Приду» (если не подтверждено), «Отменить запись», «Как добраться».
    В данных кнопки — только UUID заявки (без ПДн)."""
    rows = []
    if not confirmed:
        rows.append(
            [
                {
                    "text": texts.BTN_CONFIRM,
                    "callback_data": f"c:{appointment_id}",
                    "style": "success",
                }
            ]
        )
    rows.append(
        [{"text": texts.BTN_CANCEL, "callback_data": f"x:{appointment_id}", "style": "danger"}]
    )
    rows.append([route(branch)])
    return inline(*rows)


def review(link: str) -> dict:
    return inline([{"text": texts.BTN_REVIEW, "url": link}])
