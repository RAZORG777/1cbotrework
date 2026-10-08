"""Тексты сообщений по контракту specs/005-bot-messages/contracts/messages.md.

Этот файл одинаков в обоих ботах: одинаковые проверки = одинаковые тексты в Telegram и MAX.
"""

import re
from dataclasses import dataclass
from datetime import date, datetime

from app import texts

EMOJI = re.compile(r"[\U0001F000-\U0001FAFF☀-➿⬀-⯿️]")


@dataclass
class V:
    fio_short: str = "Ольга Петровна"
    visit_at: datetime = datetime(2026, 10, 2, 14, 30)  # пятница
    doctor_name: str = "Иванова Анна Сергеевна"
    service_name: str = "Консультация офтальмолога"
    branch: str = "Профсоюзная"
    notify: bool = True
    confirmed_at: datetime | None = None


THURSDAY = date(2026, 10, 1)


def test_booked():
    assert texts.booked(V()) == (
        "Ольга Петровна, вы успешно записаны на приём.\n\n"
        "<b>Пятница, 2 октября, 14:30</b>\n"
        "Врач: Иванова Анна Сергеевна\n"
        "Услуга: Консультация офтальмолога\n"
        "Филиал: Профсоюзная, ул. Профсоюзная, 76\n"
        "Телефон: +7 (495) 101-20-25\n\n"
        "Накануне и за 2 часа до приёма пришлём напоминание."
    )


def test_booked_without_reminders_and_service():
    text = texts.booked(V(notify=False, service_name=""))
    assert "напоминание" not in text and "Услуга" not in text


def test_moved():
    assert texts.moved(V()) == (
        "Ольга Петровна, запись успешно перенесена.\n\n"
        "<b>Пятница, 2 октября, 14:30</b>\n"
        "Врач: Иванова Анна Сергеевна\n"
        "Филиал: Профсоюзная, ул. Профсоюзная, 76\n\n"
        "Напоминания о приёме придут по новому назначенному времени."
    )


def test_cancelled():
    assert texts.cancelled_by_patient(V()) == (
        "Ольга Петровна, запись на пятницу, 2 октября, 14:30 отменена.\n\n"
        "Записаться на другое удобное время можно в любой момент."
    )
    assert texts.cancelled_by_admin(V(branch="Ватутинки")) == (
        "Ольга Петровна, ваша запись на пятницу, 2 октября, 14:30 отменена нашими администраторами."
        "\n\nЕсли вы этого не ожидали или хотите выбрать другое время, позвоните в филиал: "
        "+7 (495) 101-01-77. Или запишитесь заново."
    )


def test_reminder_24h():
    text = texts.reminder(V(), "24h", THURSDAY)
    assert text.startswith(
        "Ольга Петровна, напоминаем о приёме завтра, <b>2 октября, в 14:30</b>.\n\n"
        "Врач: Иванова Анна Сергеевна\nФилиал: Профсоюзная, ул. Профсоюзная, 76\n\n"
        "Пожалуйста, не приезжайте за рулём"
    )
    assert text.endswith("Подтвердите, пожалуйста, что придёте.")
    confirmed = texts.reminder(V(confirmed_at=datetime(2026, 10, 1)), "24h", THURSDAY)
    assert confirmed.endswith("Если планы изменились, запись можно отменить.")
    assert "в пятницу, <b>" in texts.reminder(V(), "24h", date(2026, 9, 29))


def test_reminder_2h():
    assert texts.reminder(V(), "2h", date(2026, 10, 2)) == (
        "Ольга Петровна, ждём вас сегодня в <b>14:30</b>.\n\n"
        "Филиал: Профсоюзная, ул. Профсоюзная, 76\nТелефон: +7 (495) 101-20-25"
    )


def test_confirm_and_feedback():
    assert texts.confirmed(V()) == "Спасибо, ждём вас в пятницу, 2 октября, в 14:30."
    assert texts.confirmed(V(visit_at=datetime(2026, 10, 6, 9, 0))).startswith(
        "Спасибо, ждём вас во вторник"
    )
    assert texts.already_confirmed(V()) == "Вы уже подтвердили визит. Ждём вас в 14:30."
    assert texts.feedback(V()).endswith("выбрать врача.\nВрач: Иванова Анна Сергеевна")


def test_welcome():
    assert texts.welcome("Ольга").startswith("Здравствуйте, Ольга!\n\nЭто бот клиники «Ясно Вижу».")
    assert texts.welcome(None).startswith("Здравствуйте!\n\n")


def test_no_emoji_anywhere():
    v = V()
    all_texts = [
        texts.welcome("Ольга"),
        texts.booked(v),
        texts.moved(v),
        texts.cancelled_by_patient(v),
        texts.cancelled_by_admin(v),
        texts.reminder(v, "24h", THURSDAY),
        texts.reminder(v, "2h", date(2026, 10, 2)),
        texts.confirmed(v),
        texts.already_confirmed(v),
        texts.feedback(v),
        texts.NOT_ACTUAL,
        texts.RETRY_LATER,
        texts.ALREADY_CANCELLED,
        texts.CANCEL_FAILED,
    ]
    labels = [getattr(texts, n) for n in dir(texts) if n.startswith(("BTN_", "NOTICE_"))]
    for t in all_texts + labels:
        assert not EMOJI.search(t), t


def test_escape_and_no_name():
    text = texts.booked(V(fio_short="", doctor_name="<b>Врач</b>"))
    assert text.startswith("Вы успешно записаны на приём.")
    assert "&lt;b&gt;Врач&lt;/b&gt;" in text


def test_branches_and_service_title():
    assert texts.branch_of("Ватутинки").name == "Новые Ватутинки"
    assert texts.branch_of("Профсоюзная").route_url == (
        "https://yandex.ru/maps/?rtext=~55.660638,37.543529&rtype=mt"
    )
    assert texts.service_title("Подбор очков..") == "Подбор очков"
