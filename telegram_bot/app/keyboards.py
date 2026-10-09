"""Кнопки сообщений Telegram (specs/005-bot-messages). Тексты кнопок — app/texts.py.

Цвет: `style` = primary (синяя), success (зелёная), danger (красная), Bot API 9.4;
старые клиенты показывают обычные кнопки.
"""

from __future__ import annotations

from . import texts
from .config import BASE_DIR

BUILD_INDEX = BASE_DIR / "static" / "app" / "index.html"


def app_url(webapp_url: str) -> str:
    """Адрес формы с версией сборки: Telegram кэширует страницу мини-приложения, и без
    параметра пациенты после обновления видели бы старую форму."""
    try:
        version = int(BUILD_INDEX.stat().st_mtime)
    except OSError:
        return webapp_url
    return f"{webapp_url.rstrip('/')}/?v={version}"


def inline(*rows: list[dict]) -> dict:
    return {"inline_keyboard": [list(row) for row in rows if row]}


def route(branch: str | None) -> dict:
    return {"text": texts.BTN_ROUTE, "url": texts.branch_of(branch).route_url}


def my_booking(webapp_url: str) -> dict:
    return {"text": texts.BTN_MY, "web_app": {"url": app_url(webapp_url)}}


def book(webapp_url: str) -> dict:
    return {"text": texts.BTN_BOOK, "web_app": {"url": app_url(webapp_url)}, "style": "primary"}


def visit(branch: str | None, webapp_url: str) -> dict:
    """После записи и переноса: «Как добраться», «Моя запись»."""
    return inline([route(branch)], [my_booking(webapp_url)])


def book_again(webapp_url: str) -> dict:
    return inline([book(webapp_url)])


def welcome(webapp_url: str, site_url: str) -> dict:
    return inline([book(webapp_url)], [{"text": texts.BTN_SITE, "url": site_url}])


def reminder(appointment_id: str, confirmed: bool, branch: str | None) -> dict:
    """Напоминание: «Подтвердить визит» (если не подтверждено), «Отменить запись», «Как добраться».
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


# --- Новости и рассылки (specs/007-broadcasts) ---

NEWS_YES, NEWS_NO, NEWS_OFF = "n:yes", "n:no", "n:off"


def news_question() -> dict:
    return inline(
        [
            {"text": texts.BTN_NEWS_YES, "callback_data": NEWS_YES, "style": "success"},
            {"text": texts.BTN_NEWS_NO, "callback_data": NEWS_NO},
        ]
    )


def broadcast(button_type: str, button_text: str, button_url: str, webapp_url: str, promo: bool):
    """Кнопки рассылки: «Записаться» или ссылка; у новостей и акций — «Отписаться»."""
    rows = []
    if button_type == "book":
        rows.append([book(webapp_url)])
    elif button_type == "url" and button_url:
        rows.append([{"text": button_text or texts.BTN_SITE, "url": button_url}])
    if promo:
        rows.append([{"text": texts.BTN_UNSUBSCRIBE, "callback_data": NEWS_OFF}])
    return inline(*rows) if rows else None
