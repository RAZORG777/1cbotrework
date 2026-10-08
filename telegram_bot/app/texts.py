"""Тексты сообщений пациенту (specs/005-bot-messages/contracts/messages.md).

Модуль одинаков по содержанию в обоих ботах: тексты Telegram и MAX должны совпадать дословно
(принцип III). Кнопки собираются отдельно, в app/keyboards.py каждого бота. Смайликов нет.
"""

from __future__ import annotations

import html
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Protocol

CLINIC_PHONE = "8 (800) 301-01-67"
SITE_URL = "https://yasno-vizhu.com"


@dataclass(frozen=True)
class Branch:
    name: str
    address: str
    phone: str
    lat: float
    lon: float

    @property
    def route_url(self) -> str:
        """Маршрут общественным транспортом в Яндекс Картах (точка старта — где пациент)."""
        return f"https://yandex.ru/maps/?rtext=~{self.lat},{self.lon}&rtype=mt"


PROFSOYUZNAYA = Branch(
    "Профсоюзная", "ул. Профсоюзная, 76", "+7 (495) 101-20-25", 55.660638, 37.543529
)
VATUTINKI = Branch(
    "Новые Ватутинки",
    "ул. 3-я Нововатутинская, 13, корп. 2",
    "+7 (495) 101-01-77",
    55.518219,
    37.344904,
)


def branch_of(value: str | None) -> Branch:
    """Филиал по значению из записи («Профсоюзная», «Ватутинки», «Новые Ватутинки»)."""
    return VATUTINKI if "Ватутинки" in (value or "") else PROFSOYUZNAYA


class Visit(Protocol):
    """Что тексты берут из записи (модель Appointment обоих ботов)."""

    fio_short: str
    visit_at: datetime
    doctor_name: str
    service_name: str
    branch: str
    notify: bool
    confirmed_at: datetime | None


# --- Даты по-русски ---

_WEEKDAYS = ["понедельник", "вторник", "среда", "четверг", "пятница", "суббота", "воскресенье"]
_WEEKDAYS_ACC = ["понедельник", "вторник", "среду", "четверг", "пятницу", "субботу", "воскресенье"]
_MONTHS_GEN = [
    "января", "февраля", "марта", "апреля", "мая", "июня",
    "июля", "августа", "сентября", "октября", "ноября", "декабря",
]  # fmt: skip


def day_month(dt: datetime | date) -> str:
    """«2 октября»"""
    return f"{dt.day} {_MONTHS_GEN[dt.month - 1]}"


def hm(dt: datetime) -> str:
    return dt.strftime("%H:%M")


def heading(dt: datetime) -> str:
    """«Пятница, 2 октября, 14:30» — строка-заголовок визита."""
    return f"{_WEEKDAYS[dt.weekday()].capitalize()}, {day_month(dt)}, {hm(dt)}"


def on_day(dt: datetime) -> str:
    """«пятницу, 2 октября, 14:30» — после «запись на»."""
    return f"{_WEEKDAYS_ACC[dt.weekday()]}, {day_month(dt)}, {hm(dt)}"


def in_day(dt: datetime) -> str:
    """«в пятницу, 2 октября, в 14:30» («во вторник»)."""
    prep = "во" if dt.weekday() == 1 else "в"
    return f"{prep} {_WEEKDAYS_ACC[dt.weekday()]}, {day_month(dt)}, в {hm(dt)}"


def relative_day(dt: datetime, today: date) -> str:
    """«сегодня», «завтра» или «в пятницу»."""
    if dt.date() == today:
        return "сегодня"
    if dt.date() == today + timedelta(days=1):
        return "завтра"
    prep = "во" if dt.weekday() == 1 else "в"
    return f"{prep} {_WEEKDAYS_ACC[dt.weekday()]}"


# --- Вспомогательное ---

_SERVICE_ALIASES = {
    "Комплексная офтальмологическая диагностика с консультацией врача офтальмолога - к.м.н..": (
        "Комплексная диагностика (к.м.н.)"
    ),
    "Комплексная офтальмологическая диагностика с консультацией врача - офтальмолога при глаукоме": (
        "Комплексная диагностика (при глаукоме)"
    ),
    "Комплексная офтальмологическая диагностика с консультацией врача - офтальмолога..": (
        "Комплексная диагностика"
    ),
}


def service_title(name: str | None) -> str:
    """Название услуги как в форме: короткие псевдонимы, без «..» на конце."""
    name = (name or "").strip()
    return _SERVICE_ALIASES.get(name, name.rstrip(".").strip())


def esc(value: str | None) -> str:
    return html.escape((value or "").strip(), quote=False)


def b(value: str) -> str:
    return f"<b>{value}</b>"


def lead(fio: str | None, phrase: str) -> str:
    """«Ольга Петровна, вы записаны» или «Вы записаны», если имени нет."""
    fio = esc(fio)
    return f"{fio}, {phrase}" if fio else phrase[:1].upper() + phrase[1:]


def lines(*parts: str | None) -> str:
    """Строки через перевод строки; None пропускается, "" — пустая строка-разделитель."""
    return "\n".join(p for p in parts if p is not None)


def branch_line(v: Visit) -> str:
    br = branch_of(v.branch)
    return f"Филиал: {br.name}, {br.address}"


# --- Сообщения (номера — пункты контракта) ---


def welcome(first_name: str | None) -> str:  # 1
    name = esc(first_name)
    hello = f"Здравствуйте, {name}!" if name else "Здравствуйте!"
    return (
        f"{hello}\n\nЭто бот клиники «Ясно Вижу». Здесь можно записаться к офтальмологу, "
        "перенести или отменить визит. Напоминания о приёме тоже придут сюда."
    )


def booked(v: Visit) -> str:  # 2
    br = branch_of(v.branch)
    service = service_title(v.service_name)
    body = lines(
        b(heading(v.visit_at)),
        f"Врач: {esc(v.doctor_name)}" if v.doctor_name else None,
        f"Услуга: {esc(service)}" if service else None,
        branch_line(v),
        f"Телефон: {br.phone}",
    )
    tail = "\n\nНакануне и за 2 часа до приёма пришлём напоминание." if v.notify else ""
    return f"{lead(v.fio_short, 'вы успешно записаны на приём.')}\n\n{body}{tail}"


def moved(v: Visit) -> str:  # 3
    body = lines(
        b(heading(v.visit_at)),
        f"Врач: {esc(v.doctor_name)}" if v.doctor_name else None,
        branch_line(v),
    )
    return (
        f"{lead(v.fio_short, 'запись успешно перенесена.')}\n\n{body}\n\n"
        "Напоминания о приёме придут по новому назначенному времени."
    )


def cancelled_by_patient(v: Visit) -> str:  # 4
    return (
        f"{lead(v.fio_short, f'запись на {on_day(v.visit_at)} отменена.')}\n\n"
        "Записаться на другое удобное время можно в любой момент."
    )


MEMO = (
    "Пожалуйста, не приезжайте за рулём и не надевайте в этот день контактные линзы: после "
    "диагностики зрение несколько часов может быть нечётким. Возьмите очки и прошлые заключения, "
    "если они есть."
)


def reminder(v: Visit, kind: str, today: date) -> str:  # 5, 6
    confirmed = v.confirmed_at is not None
    if kind == "2h":
        when = (
            f"сегодня в {b(hm(v.visit_at))}"
            if v.visit_at.date() == today
            else b(in_day(v.visit_at))
        )
        br = branch_of(v.branch)
        return lines(
            f"{lead(v.fio_short, f'ждём вас {when}.')}",
            "",
            branch_line(v),
            f"Телефон: {br.phone}",
        )
    when = f"{relative_day(v.visit_at, today)}, {b(f'{day_month(v.visit_at)}, в {hm(v.visit_at)}')}"
    ask = (
        "Если планы изменились, запись можно отменить."
        if confirmed
        else "Подтвердите, пожалуйста, что придёте."
    )
    return lines(
        lead(v.fio_short, f"напоминаем о приёме {when}."),
        "",
        f"Врач: {esc(v.doctor_name)}" if v.doctor_name else None,
        branch_line(v),
        "",
        MEMO,
        "",
        ask,
    )


def confirmed(v: Visit) -> str:  # 7
    return f"Спасибо, ждём вас {in_day(v.visit_at)}."


def already_confirmed(v: Visit) -> str:  # 7
    return f"Вы уже подтвердили визит. Ждём вас в {hm(v.visit_at)}."


def cancelled_by_admin(v: Visit) -> str:  # 8
    br = branch_of(v.branch)
    return (
        f"{lead(v.fio_short, f'ваша запись на {on_day(v.visit_at)} отменена нашими администраторами.')}"
        "\n\nЕсли вы этого не ожидали или хотите выбрать другое время, позвоните в филиал: "
        f"{br.phone}. Или запишитесь заново."
    )


def feedback(v: Visit) -> str:  # 9
    doctor = f"\nВрач: {esc(v.doctor_name)}" if v.doctor_name else ""
    return (
        f"{lead(v.fio_short, 'спасибо, что пришли к нам.')}\n\n"
        "Если найдёте минуту, оставьте отзыв о приёме. Это помогает другим пациентам выбрать врача."
        f"{doctor}"
    )


# 10. Ответы кнопок напоминаний при сбоях
NOT_ACTUAL = "Эта запись уже изменилась. Актуальное напоминание придёт отдельным сообщением."
RETRY_LATER = (
    "Не получилось связаться с клиникой. Нажмите кнопку ещё раз через пару минут "
    f"или позвоните: {CLINIC_PHONE}."
)
ALREADY_CANCELLED = "Эта запись уже отменена."
CANCEL_FAILED = f"Не получилось отменить запись. Попробуйте ещё раз или позвоните: {CLINIC_PHONE}."

# Всплывающие подсказки над чатом
NOTICE_CONFIRMED = "Визит подтверждён"
NOTICE_ALREADY = "Уже подтверждено"
NOTICE_CANCELLED = "Запись отменена"
NOTICE_NOT_ACTUAL = "Запись изменилась"
NOTICE_RETRY = "Не удалось, попробуйте позже"
NOTICE_CANCEL_FAILED = "Не удалось отменить"

# Подписи кнопок (цвет задают keyboards.py платформ)
BTN_BOOK = "Записаться"
BTN_SITE = "Сайт клиники"
BTN_ROUTE = "Как добраться"
BTN_MY = "Моя запись"
BTN_CONFIRM = "Приду"
BTN_CANCEL = "Отменить запись"
BTN_REVIEW = "Оставить отзыв"
