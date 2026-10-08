# Tasks: Админка как инструмент разработчика

**Input**: [spec.md](spec.md), [plan.md](plan.md), [contracts/admin-api.md](contracts/admin-api.md)

Формат: `[ID] [P?] [Story] Описание`. `[P]` — можно параллельно (разные файлы).

## Phase 1: Основа (Telegram)

- [X] T001 Структурированный буфер журнала и смена уровня на лету в `telegram_bot/app/logging.py`
- [X] T002 [P] Счётчики активности и время старта в `telegram_bot/app/metrics.py`; инкременты в webhook, internal, webapp, messenger, onec_client
- [X] T003 Проверка `X-Admin-Request` (`require_admin_action`) в `telegram_bot/app/auth.py`

## Phase 2: US1 Обзор и здоровье (P1)

- [X] T004 [US1] `admin_tools.health_checks` (БД, планировщик, 1С, getMe, getWebhookInfo) с таймаутом 5 с
- [X] T005 [US1] `GET /admin/api/overview`, `GET /admin/api/health` в `routes/admin_api.py`

## Phase 3: US2 Журнал (P1)

- [X] T006 [US2] Чтение файлов журнала с хвоста, фильтр, список, скачивание (защита от `..`)
- [X] T007 [US2] `GET /api/logs/tail|files|file|download`, `POST /api/logs/level`

## Phase 4: US3–US4 Задания и записи (P2)

- [X] T008 [US3] `GET /api/jobs`, `POST run|pause|resume|delete`
- [X] T009 [US4] `GET /api/appointments` без ПДн; `remind`, `reschedule-reminders`, `close`

## Phase 5: US5–US6 1С, сообщения, настройки, обслуживание (P2–P3)

- [X] T010 [US5] Консоль 1С только для чтения `GET /api/onec/{method}`
- [X] T011 [US5] Шаблоны с примером и отправка только в `ADMIN_IDS`
- [X] T012 [US6] Настройки с маской секретов; вебхук, очистка, перезапуск

## Phase 6: Интерфейс

- [X] T013 `app/admin_ui/` — index.html, admin.css, admin.js: вкладки, тема, живой журнал, 375 px
- [X] T014 `routes/admin.py` — страница, статика, заголовки безопасности, совместимость `/logs`, `/send-reminder`

## Phase 7: MAX-бот (принцип III)

- [X] T015 Перенести T001–T014 в `max_bot` (префикс `/max`, `GET /me`, `GET /subscriptions`, `POST /subscriptions`)

## Phase 8: Проверка

- [X] T016 [P] Тесты `tests/integration/test_admin_api.py` в обоих ботах: авторизация, CSRF, нет секретов и ПДн, журнал, задания, записи, 1С, шаблоны
- [X] T017 Скриншоты интерфейса (Playwright, 1280 и 375 px, светлая и тёмная тема)
- [X] T018 README: раздел «Админка»
