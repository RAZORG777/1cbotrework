---
description: "Задачи этапа 2: подтверждение визита из напоминания"
---

# Tasks: Подтверждение визита из напоминания

**Input**: plan.md, spec.md, research.md (R1–R6), data-model.md, contracts/onec-confirm.md, quickstart.md

**Tests**: обязательны для ботов (принцип V); 1С — сценарии quickstart.

## Format: `[ID] [P?] [Story] Description`

---

## Phase 1: Setup

- [X] T001 Создать в тестовой УМЦ URL-шаблон `/confirm` (POST → `ConfirmPOST`) в расширении `TGBotAPI` после T004 и пройти quickstart.md › 0
  > ✅ 29.09: `/confirm` в тестовой УМЦ; миграция БД v1 → v2 прошла при старте; «Подтверждаю» → пометка «Пациент подтвердил запись (Telegram), 29.09 12:59» в заявке.

## Phase 2: Foundational

- [X] T002 [P] Схема v2: колонка `confirmed_at` в `telegram_bot/app/models.py`, миграция v1 → v2 в `telegram_bot/app/db.py` (`ALTER TABLE … ADD COLUMN`, `SCHEMA_VERSION = 2`), тест в `telegram_bot/tests/unit/test_migration.py`
- [X] T003 [P] То же в `max_bot/app/models.py`, `max_bot/app/db.py`, `max_bot/tests/unit/test_migration.py`
- [X] T004 `ConfirmPOST` в `onec/http-service.bsl` по contracts/onec-confirm.md (коды `BAD_REQUEST`, `NOT_FOUND`, `CANCELLED`, `INTERNAL`, `already`); раздел `confirm` в `docs/onec-contract.md`
- [X] T005 [P] `confirm(appointment_id, platform)` в `telegram_bot/app/onec_client.py` + контрактный тест в `telegram_bot/tests/contract/test_onec_client.py`
- [X] T006 [P] То же в `max_bot/app/onec_client.py`, `max_bot/tests/contract/test_onec_client.py`
- [X] T007 [P] `edit_reply_markup(chat_id, message_id)` в `telegram_bot/app/messenger.py`; `answer_callback(callback_id, notification, message=None)` с полем `message` в `max_bot/app/messenger.py`

## Phase 3: US1 — подтверждение (P1) 🎯 MVP

- [X] T008 [P] [US1] `telegram_bot/app/reminders.py`: клавиатура `c:<id>`/`x:<id>`, задание `send_reminder(appointment_id, kind)` (чтение записи при срабатывании, «Подтверждаю» скрыта при `confirmed_at`), `schedule_reminders` планирует `send_reminder` для 24 ч и 2 ч; новый текст 24 ч без обещания звонка; старые задания `deliver` работают
- [X] T009 [P] [US1] То же в `max_bot/app/reminders.py` (payload `confirm:<id>`/`cancel:<id>`)
- [X] T010 [US1] `telegram_bot/app/visit_actions.py`: `handle_confirm(state, user_id, appointment_id)` → исходы по data-model.md › «Исходы»; `telegram_bot/app/routes/webhook.py`: разбор `callback_query` (`c:`/`x:`), ответ на callback, `edit_reply_markup` при финальном исходе, сообщение пациенту
- [X] T011 [US1] `max_bot/app/visit_actions.py` и `max_bot/app/routes/webhook.py`: `confirm:<id>` и прежний `confirm_visit` → `onec.confirm` вместо `update_note`; убрать кнопки через `answer_callback(message=…)`
- [X] T012 [P] [US1] Тесты `telegram_bot/tests/integration/test_confirm_flow.py`: подтверждение, повтор (`already`), сбой 1С (кнопки не убираются), `CANCELLED`, без ПДн в журналах
- [X] T013 [P] [US1] То же `max_bot/tests/integration/test_confirm_flow.py`, включая прежний payload `confirm_visit`

## Phase 4: US2 — отмена из напоминания (P1)

- [X] T014 [US2] Telegram: `x:<id>` → `cancel_for_user` после проверки id; кнопки убрать; сообщение об отмене; тест в `telegram_bot/tests/integration/test_confirm_flow.py`
- [X] T015 [US2] MAX: `cancel:<id>` и прежний `cancel_visit_btn`; тест в `max_bot/tests/integration/test_confirm_flow.py`

## Phase 5: US3 — кнопка своей записи (P2)

- [X] T016 [US3] Проверка совпадения `appointment_id` с активной записью в обоих `visit_actions.py`; перенос сбрасывает `confirmed_at` в `*/app/routes/webapp.py`; тесты «кнопка после переноса» в обоих `test_confirm_flow.py`

## Phase 6: Polish

- [X] T017 [P] Админка: признак «подтверждена» в `telegram_bot/app/routes/admin.py` и `max_bot/app/routes/admin.py`
- [X] T018 [P] Отправка напоминания сейчас для quickstart — вместо скрипта защищённый `POST /admin/send-reminder?appointment_id=…&kind=24h|2h` в обоих ботах (задания планировщика живут в процессе бота)
- [ ] T019 `ruff` и `pytest` в обоих ботах; quickstart.md › 1–4 на тестовом стенде; `onec/TGBotAPI.cfe` пересобрать
