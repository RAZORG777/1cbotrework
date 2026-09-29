# Implementation Plan: Подтверждение визита из напоминания

**Branch**: `003-visit-confirmation` | **Date**: 2026-09-29 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/003-visit-confirmation/spec.md`

## Summary

Пациент подтверждает или отменяет визит кнопками в напоминаниях за 24 и за 2 часа, в обоих ботах.

- 1С: новый метод `confirm` (расширение `TGBotAPI`) — идемпотентная пометка «Пациент подтвердил
  запись (мессенджер), дата время» в примечании заявки; отменённая заявка → `CANCELLED` (R2).
- Кнопки несут идентификатор заявки и действуют только на неё (R3); прежние кнопки MAX работают.
- Напоминание собирается в момент отправки: текст и кнопки по текущему состоянию записи (R4).
- После действия кнопки убираются: Telegram — `editMessageReplyMarkup`, MAX — `message` в ответе
  на callback (R5).
- Бот хранит `confirmed_at` (схема v2), показывает подтверждение в админке (R6).

## Technical Context

**Language/Version**: Python 3.12 (CI), 1С:Предприятие 8.3.27 (расширение `TGBotAPI`)

**Primary Dependencies**: FastAPI, APScheduler 3, SQLAlchemy 2, httpx (без новых); Telegram Bot API
(`answerCallbackQuery`, `editMessageReplyMarkup`), MAX Bot API (`POST /answers` с `message`)

**Storage**: SQLite ботов — колонка `confirmed_at`, `PRAGMA user_version` 1 → 2; 1С — примечание заявки

**Testing**: pytest + respx (заглушки 1С, Telegram, MAX): контрактные тесты `confirm`, вебхуков,
напоминаний; миграция v1 → v2; 1С — quickstart на тестовой УМЦ

**Target Platform**: как этапы 0–1

**Project Type**: интеграция — HTTP-сервис 1С + два независимых бота

**Performance Goals**: ответ на нажатие ≤ 5 с (SC-001); вебхук MAX отвечает сразу, обработка в фоне

**Constraints**: без ПДн в журналах; совместимость с уже запланированными заданиями и отправленными
кнопками MAX; `update_note` не удаляется до выкладки

**Scale/Scope**: десятки напоминаний в день; 1 метод 1С, 2 бота

## Constitution Check

| Принцип | Проверка | Статус |
|---------|----------|--------|
| I. ПДн | в `callback_data`/`payload` только UUID заявки; журналы — `user_id`, `appointment_id` | ✅ |
| II. 1С — источник истины (v2.1.0) | отдельный идемпотентный метод `confirm` со стандартной пометкой; `update_note` для подтверждения не используется; контракт в `docs/onec-contract.md` и `onec/` | ✅ |
| III. Независимые боты | изменения в `telegram_bot/` и `max_bot/` отдельно; общий контракт — `contracts/onec-confirm.md` | ✅ |
| IV. Надёжность | идемпотентность нажатий (`processed_events`) и 1С (`already`); сбой 1С — кнопки остаются; задания по записи, а не по тексту | ✅ |
| V. Тесты | контрактные и интеграционные тесты обоих ботов, миграция | ✅ |
| VI. Стиль клиники | тексты напоминаний в прежнем тоне | ✅ |

Нарушений нет.

## Project Structure

```text
specs/003-visit-confirmation/  plan.md, research.md, data-model.md, contracts/onec-confirm.md,
                               quickstart.md, tasks.md
onec/http-service.bsl          ConfirmPOST; TGBotAPI.cfe — шаблон /confirm
docs/onec-contract.md          §1: confirm
telegram_bot/app/
  models.py, db.py             confirmed_at, миграция v1 → v2
  onec_client.py               confirm()
  messenger.py                 edit_reply_markup()
  reminders.py                 send_reminder(), клавиатура, schedule_reminders → send_reminder
  visit_actions.py             общая логика нажатий: confirm_visit(), cancel_visit()
  routes/webhook.py            callback_query → visit_actions
  routes/webapp.py             перенос сбрасывает confirmed_at
  routes/admin.py              «подтверждена» в списке
telegram_bot/tests/…           test_confirm_flow.py, test_migration.py, test_onec_client.py
max_bot/app/…                  то же: messenger.answer_callback(message=…), webhook message_callback
max_bot/tests/…
```

**Structure Decision**: логика нажатий выносится в `app/visit_actions.py` каждого бота (без общих
импортов между ботами, принцип III); вебхуки только разбирают апдейт и вызывают её.
