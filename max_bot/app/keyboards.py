"""Кнопки сообщений MAX (specs/005-bot-messages). Тексты кнопок — app/texts.py.

Цвет callback-кнопок — `intent`: positive (зелёная), negative (красная).
"""

from __future__ import annotations

from . import texts


def rows(*items: list[dict]) -> list[list[dict]]:
    return [list(row) for row in items if row]


def route(branch: str | None) -> dict:
    return {"type": "link", "text": texts.BTN_ROUTE, "url": texts.branch_of(branch).route_url}


def my_booking(miniapp: str) -> dict:
    return {"type": "open_app", "text": texts.BTN_MY, "web_app": miniapp}


def book(miniapp: str) -> dict:
    return {"type": "open_app", "text": texts.BTN_BOOK, "web_app": miniapp}


def visit(branch: str | None, miniapp: str) -> list:
    """После записи и переноса: «Как добраться», «Моя запись»."""
    return rows([route(branch)], [my_booking(miniapp)])


def book_again(miniapp: str) -> list:
    return rows([book(miniapp)])


def welcome(miniapp: str, site_url: str) -> list:
    return rows([book(miniapp)], [{"type": "link", "text": texts.BTN_SITE, "url": site_url}])


def reminder(appointment_id: str, confirmed: bool, branch: str | None) -> list:
    """Напоминание: «Подтвердить визит» (если не подтверждено), «Отменить запись», «Как добраться».
    В payload — только UUID заявки (без ПДн)."""
    items = []
    if not confirmed:
        items.append(
            [
                {
                    "type": "callback",
                    "text": texts.BTN_CONFIRM,
                    "payload": f"confirm:{appointment_id}",
                    "intent": "positive",
                }
            ]
        )
    items.append(
        [
            {
                "type": "callback",
                "text": texts.BTN_CANCEL,
                "payload": f"cancel:{appointment_id}",
                "intent": "negative",
            }
        ]
    )
    items.append([route(branch)])
    return rows(*items)


def review(link: str) -> list:
    return rows([{"type": "link", "text": texts.BTN_REVIEW, "url": link}])


# --- Новости и рассылки (specs/007-broadcasts) ---

NEWS_YES, NEWS_NO, NEWS_OFF = "news:yes", "news:no", "news:off"


def news_question() -> list:
    return rows(
        [
            {
                "type": "callback",
                "text": texts.BTN_NEWS_YES,
                "payload": NEWS_YES,
                "intent": "positive",
            },
            {"type": "callback", "text": texts.BTN_NEWS_NO, "payload": NEWS_NO},
        ]
    )


def broadcast(button_type: str, button_text: str, button_url: str, miniapp: str, promo: bool):
    """Кнопки рассылки: «Записаться» или ссылка; у новостей и акций — «Отписаться»."""
    items = []
    if button_type == "book":
        items.append([book(miniapp)])
    elif button_type == "url" and button_url:
        items.append([{"type": "link", "text": button_text or texts.BTN_SITE, "url": button_url}])
    if promo:
        items.append([{"type": "callback", "text": texts.BTN_UNSUBSCRIBE, "payload": NEWS_OFF}])
    return rows(*items) if items else None
