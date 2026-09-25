---

description: "Task list for 001-security-hygiene"
---

# Tasks: Гигиена репозитория и безопасность ботов

**Input**: Design documents from `/specs/001-security-hygiene/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: Обязательны. Этого требуют FR-022 и принцип V конституции. Тесты каждой истории пишутся
до реализации и должны сначала падать.

**Organization**: Задачи сгруппированы по User Stories. Боты независимы (принцип III), поэтому
почти каждое действие — пара задач: `telegram_bot/…` и `max_bot/…`. Такие пары помечены [P]:
они в разных каталогах и выполняются параллельно.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: можно выполнять параллельно (разные файлы, нет зависимости от незавершённых задач)
- **[Story]**: US1–US5 из spec.md
- Пути — от корня репозитория

## Path Conventions

- Telegram-бот: `telegram_bot/app/`, `telegram_bot/static/`, `telegram_bot/tests/`, `telegram_bot/scripts/`
- MAX-бот: `max_bot/app/`, `max_bot/static/`, `max_bot/tests/`, `max_bot/scripts/`
- Выкладка: `deploy/`, CI: `.github/workflows/`
- Раскладка модулей — plan.md › Project Structure

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Чистый репозиторий и каркас двух ботов

- [ ] T001 Проверить версию Python на боевом сервере (`python --version`), записать её в `.python-version` в корне репозитория и при необходимости поправить версию в плане (research.md › R14)
- [ ] T002 Удалить устаревшие файлы из корня и каталогов (research.md › R15): `main.py`, `main — копия.py`, `index.html`, `index — копия.html`, `index.html.bak`, `one_c_client.py`, `one_c_client.py.bak`, `bot.py`, `test.py`, `check_db.py`, `requirements.txt`, `Логотип.png` в корне, каталоги `1/` и `telegram_bot_test/`, все `*.bak` в `telegram_bot/` и `max_bot/`. Файлы вне git (`.env`, ключи, `*.db`, `1CBOT.7z`, `nssm.exe`) не трогать
- [ ] T003 [P] Создать каркас `telegram_bot/`: пакеты `app/`, `app/routes/`, `tests/{unit,contract,integration}/`, каталоги `static/`, `scripts/`; перенести `telegram_bot/index.html` и `telegram_bot/Логотип.png` в `telegram_bot/static/` через `git mv`
- [ ] T004 [P] Создать каркас `max_bot/` так же; `git mv max_bot/max_index.html max_bot/static/index.html`, `max_bot/Логотип.png` → `max_bot/static/`, `max_bot/1raz.py` → `max_bot/scripts/set_menu_button.py`
- [ ] T005 [P] Создать `telegram_bot/requirements.txt` с фиксированными версиями (fastapi, uvicorn, httpx, sqlalchemy 2, apscheduler 3, loguru, pydantic 2, pydantic-settings), `telegram_bot/requirements-dev.txt` (`-r requirements.txt` + pytest, pytest-asyncio, respx, time-machine, ruff) и `telegram_bot/pyproject.toml` с настройками ruff (line-length 100) и pytest (`asyncio_mode = "auto"`, `testpaths = ["tests"]`)
- [ ] T006 [P] То же для `max_bot/requirements.txt`, `max_bot/requirements-dev.txt`, `max_bot/pyproject.toml`
- [ ] T007 [P] Создать `telegram_bot/.env.example` со всеми переменными из research.md › R10 и комментариями, без реальных значений; `PD_POLICY_URL=https://yasno-vizhu.com/docs/Согласие_на_обработку_персональных_данных.pdf`
- [ ] T008 [P] Создать `max_bot/.env.example` так же (`MAX_API_URL=https://platform-api2.max.ru`, `PD_POLICY_URL` как у Telegram, `MAX_WEBHOOK_SECRET`, `MAX_MINIAPP` — ссылка/идентификатор мини-приложения)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Конфигурация, журналы, БД, клиенты внешних API и перенос текущих эндпоинтов в новую
структуру **без изменения поведения**

**⚠️ CRITICAL**: Работа по историям начинается только после этой фазы

- [ ] T009 [P] Реализовать `telegram_bot/app/config.py`: `Settings(BaseSettings)` с `env_file` из каталога бота; обязательные и необязательные поля и валидация — data-model.md › Настройки; функция `get_settings()`; при `ValidationError` вывести имена полей и выйти с кодом 1
- [ ] T010 [P] Реализовать `max_bot/app/config.py` так же (поля MAX)
- [ ] T011 [P] Реализовать `telegram_bot/app/logging.py`: `setup_logging(settings)` — loguru, stdout + файл `LOG_DIR/telegram_bot.log` (rotation 10 MB, retention 10 days), кольцевой буфер на 200 строк для админки, `patcher`, маскирующий телефоны и даты `ДД.ММ.ГГГГ` (research.md › R9)
- [ ] T012 [P] Реализовать `max_bot/app/logging.py` так же (`max_bot.log`)
- [ ] T013 [P] Реализовать `telegram_bot/app/models.py` и `telegram_bot/app/db.py`: модели `Appointment` и `ProcessedEvent` по data-model.md (статусы, `visit_at`, `closed_at`, частичный уникальный индекс `user_id WHERE status='active'`), engine на `DB_PATH`, `session_scope()`, `init_db()` создаёт схему для новой БД и ставит `PRAGMA user_version=1`
- [ ] T014 [P] Реализовать `max_bot/app/models.py` и `max_bot/app/db.py` так же
- [ ] T015 [P] Перенести клиент 1С в `telegram_bot/app/onec_client.py`: методы `get_doctors`, `get_services`, `get_schedule(start_date/end_date/date)`, `create_booking`, `reschedule`, `cancel_booking`; общий `_request` с таймаутом 10 с, одним повтором при сетевой ошибке, исключениями `OneCUnavailable` и `OneCError`; тело запроса в журнал не пишется
- [ ] T016 [P] То же в `max_bot/app/onec_client.py` плюс метод `update_note(appointment_id, note)`
- [ ] T017 [P] Реализовать `telegram_bot/app/messenger.py`: `send_message(chat_id, text, reply_markup=None)` через `{TELEGRAM_API_BASE}/bot{token}/sendMessage`, 3 попытки с паузой 2 с на сетевых ошибках, журнал только `chat_id` и результат
- [ ] T018 [P] Реализовать `max_bot/app/messenger.py`: `send_message(user_id, text, keyboard=None)` через `{MAX_API_URL}/messages?user_id=` с заголовком `Authorization`, 3 попытки; `answer_callback(callback_id, notification)` через `POST /answers?callback_id=`
- [ ] T019 [P] Реализовать `telegram_bot/app/reminders.py`: `AsyncIOScheduler` с SQLAlchemyJobStore на `DB_PATH` и таймзоной Europe/Moscow; `schedule_reminders(appt)` (24 ч и 2 ч, id `rem24h_{appointment_id}`, `rem2h_{appointment_id}`, тексты как в текущем `telegram_bot/main.py`), `remove_reminders(appointment_id)`, `schedule_feedback(appt, text)` (+20 мин)
- [ ] T020 [P] Реализовать `max_bot/app/reminders.py` так же (24 ч — с клавиатурой «Подтверждаю»/«Отменить», как в текущем `max_bot/max_main.py`)
- [ ] T021 [P] Перенести `telegram_bot/doctors_enricher.py` в `telegram_bot/app/doctors_enricher.py` без изменений логики; добавить функцию `find_prodoctorov_url(doctor_name)` вместо поиска в `finish_visit`
- [ ] T022 [P] Перенести `max_bot/max_doctors_enricher.py` в `max_bot/app/doctors_enricher.py` так же
- [ ] T023 Собрать `telegram_bot/app/main.py` (`create_app()`, lifespan: init_db, scheduler.start, восстановление заданий; запуск `uvicorn` на `settings.HOST:settings.PORT`) и роутеры `telegram_bot/app/routes/{webapp,internal,webhook,admin,health}.py`, перенеся эндпоинты из `telegram_bot/main.py` с тем же поведением на новую схему БД (пока идентификация по `tg_id` из запроса, который пишется в `user_id`; без новых проверок); убрать дубль `/schedule`; `health.py` — `GET /healthz` → `{"status":"ok"}`; удалить `telegram_bot/main.py`, `telegram_bot/one_c_client.py`, `telegram_bot/doctors_enricher.py`
- [ ] T024 Собрать `max_bot/app/main.py` и роутеры так же (включая `HOST`/`PORT`), под префиксом `/max` (`APIRouter(prefix="/max")`), перенеся эндпоинты из `max_bot/max_main.py`; удалить `max_bot/max_main.py`, `max_bot/one_c_client.py`, `max_bot/max_doctors_enricher.py`
- [ ] T025 [P] Написать `telegram_bot/tests/conftest.py` и `telegram_bot/tests/helpers.py`: фикстуры `settings` (тестовые секреты, временные `DB_PATH` и `LOG_DIR`), `app`, `client` (httpx `ASGITransport`), `onec_mock` (respx на `ONEC_URL` со стандартными ответами doctors/services/schedule/book/cancel/reschedule), `tg_mock` (respx на `TELEGRAM_API_BASE`); `make_init_data(user_id, bot_token, auth_date=None)` по research.md › R1; respx в режиме `assert_all_mocked`
- [ ] T026 [P] Написать `max_bot/tests/conftest.py` и `max_bot/tests/helpers.py` так же (`max_mock` на `MAX_API_URL`, `make_init_data` по R2)
- [ ] T027 [P] Написать smoke-тест `telegram_bot/tests/integration/test_smoke.py`: `/healthz` 200, `/doctors` проксирует ответ заглушки 1С
- [ ] T028 [P] Написать smoke-тест `max_bot/tests/integration/test_smoke.py`: `/max/healthz`, `/max/doctors`
- [ ] T029 [P] Создать `docs/onec-contract.md` по `onec/http-service.bsl` (источник истины): методы `ping`, `specialties`, `doctors`, `services`, `schedule`, `book`, `reschedule`, `cancel`, `update_note` — параметры, тела, форматы ответов (включая ошибки внутри массивов `services` и HTTP 500 у `doctors`), плюс входящие сигналы с `X-Bot-Secret` (из contracts/onec-signals.md). Это база для этапа 1 (принцип II)
- [ ] T030 [P] `telegram_bot/tests/unit/test_migration.py`: создать БД со старой схемой (`tg_id UNIQUE`, `date`/`time` строками, 3 строки: будущая, вчерашняя, 40 дней назад) и задания `rem24h_{tg_id}` → `init_db()` → будущая `active`, прошедшие `finished`, задания пересозданы с id по `appointment_id`, создан `*.db.bak-v0`, `user_version=1`; после очистки строки старше 30 дней нет
- [ ] T031 [P] `max_bot/tests/unit/test_migration.py` — то же
- [ ] T032 [P] Добавить миграцию v0 → v1 в `telegram_bot/app/db.py` (data-model.md › Миграция): резервная копия файла, перенос в одной транзакции, пересоздание заданий из активных строк
- [ ] T033 [P] То же в `max_bot/app/db.py`
- [ ] T034 [P] Написать контрактный тест клиента 1С `telegram_bot/tests/contract/test_onec_client.py`: для каждого метода проверить HTTP-метод, путь, query-параметры и JSON-тело запроса и разбор ответов по `docs/onec-contract.md` (`doctors` — массив, `services` — массив с элементами `id="empty"|"error"`, `schedule` — `{"status","schedule":{дата:[время]}}`, `book`/`reschedule` — `status`+`appointment_id` или `status:"error"`); неожиданный формат → `OneCError` (принцип V)
- [ ] T035 [P] Написать `max_bot/tests/contract/test_onec_client.py` — то же плюс `update_note`

**Checkpoint**: оба бота запускаются из новой структуры (`python -m app.main`), старая БД
мигрирует без потерь, smoke-тесты, тесты миграции и контрактные тесты клиента 1С зелёные,
поведение для пациента не изменилось

---

## Phase 3: User Story 1 — Пациент управляет только своей записью (Priority: P1) 🎯 MVP

**Goal**: Пациент определяется только по подписанным данным запуска формы (FR-001–FR-004)

**Independent Test**: Запросы с подставленным чужим или поддельным id → 401; свои действия
работают (quickstart.md › US1)

### Tests for User Story 1

- [ ] T036 [P] [US1] `telegram_bot/tests/unit/test_auth.py`: валидный `initData` → user_id; неверный hash, отсутствие hash, `auth_date` старше 24 ч, пустая строка → соответствующие ошибки; сравнение через `compare_digest`
- [ ] T037 [P] [US1] `max_bot/tests/unit/test_auth.py` — то же для схемы MAX (URL-декодирование значений)
- [ ] T038 [P] [US1] `telegram_bot/tests/contract/test_webapp_api.py`: для `/my_appointment`, `/book`, `/reschedule`, `/cancel`, `/doctors` — без заголовка → 401 `OPEN_FROM_BOT`, чужой/поддельный → 401, устаревший → 401 `SESSION_EXPIRED`; пользователь A не видит и не отменяет запись B; `/config` доступен без заголовка (contracts/webapp-api.md)
- [ ] T039 [P] [US1] `max_bot/tests/contract/test_webapp_api.py` — то же под `/max`

### Implementation for User Story 1

- [ ] T040 [P] [US1] Реализовать `telegram_bot/app/auth.py`: `verify_init_data(raw, bot_token, max_age_hours) -> WebAppUser` и FastAPI-зависимость `current_user` (заголовок `Authorization: tma …`, ошибки 401 с кодами из контракта)
- [ ] T041 [P] [US1] Реализовать `max_bot/app/auth.py` так же по схеме MAX
- [ ] T042 [US1] Переделать `telegram_bot/app/routes/webapp.py` по contracts/webapp-api.md: все эндпоинты кроме `/`, `/Логотип.png`, `/config`, `/healthz` требуют `current_user`; убрать `tg_id` из query и тел; `send_notifications` — поле тела; добавить `GET /config` (`pd_policy_url`); ответы об ошибках — коды из контракта без текста исключений
- [ ] T043 [US1] То же в `max_bot/app/routes/webapp.py`
- [ ] T044 [P] [US1] Обновить `telegram_bot/static/index.html`: обёртка `api(path, opts)` добавляет `Authorization: tma ${Telegram.WebApp.initData}`; убрать передачу `tg_id`; при пустом `initData` или ответах 401 — экраны «Откройте запись через бота клиники» и «Сессия устарела…»
- [ ] T045 [P] [US1] Обновить `max_bot/static/index.html`: подключить `https://st.max.ru/js/max-web-app.js`; брать `window.WebApp.initData`; удалить чтение `user_id` из URL, `localStorage.max_user_id` и значение `'12345'`; та же обёртка `api()` и экраны ошибок; префикс путей `/max/`
- [ ] T046 [US1] В `max_bot/app/routes/webhook.py` заменить кнопку приветствия `type: link` с `?user_id=` на `{"type": "open_app", "text": "Записаться ✅", "web_app": settings.MAX_MINIAPP}` (contracts/messenger-webhooks.md)

**Checkpoint**: US1 проверяется отдельно; T036–T039 зелёные

---

## Phase 4: User Story 2 — Повторная запись после визита и срок хранения (Priority: P1)

**Goal**: Прошедшие, завершённые и отменённые записи не блокируют новую; данные удаляются
через `PD_RETENTION_DAYS` (FR-005–FR-008)

**Independent Test**: запись → `finish-visit` → новая запись успешна; очистка удаляет строки
старше срока (quickstart.md › US2)

### Tests for User Story 2

- [ ] T047 [P] [US2] `telegram_bot/tests/integration/test_rebooking.py`: book → finish-visit → book снова успешна; book → cancel → book успешна; book с прошедшей датой (time-machine) → book успешна; две одновременные активные невозможны (`SECOND_BOOKING_ERROR`)
- [ ] T048 [P] [US2] `max_bot/tests/integration/test_rebooking.py` — то же
- [ ] T049 [P] [US2] `telegram_bot/tests/unit/test_retention.py`: активная с `visit_at` вчера-позавчера → `finished`; `closed_at` старше `PD_RETENTION_DAYS` → удалена вместе с заданиями; `processed_events` старше 7 дней удалены; значение `PD_RETENTION_DAYS` берётся из настроек
- [ ] T050 [P] [US2] `max_bot/tests/unit/test_retention.py` — то же

### Implementation for User Story 2

- [ ] T051 [P] [US2] В `telegram_bot/app/reminders.py` добавить `run_retention(session, settings, now)` и регистрацию cron-задания `retention_cleanup` (03:30 Europe/Moscow) плюс вызов в lifespan при старте (research.md › R8)
- [ ] T052 [P] [US2] То же в `max_bot/app/reminders.py`
- [ ] T053 [US2] В `telegram_bot/app/routes/webapp.py` и `telegram_bot/app/routes/internal.py` перейти на статусы: `/book` проверяет только `status='active'`; `/cancel` и `cancel-visit` → `cancelled` + `closed_at`; `finish-visit` → `finished` + `closed_at` + удаление напоминаний + `schedule_feedback`; `/reschedule` обновляет строку и пересоздаёт задания
- [ ] T054 [US2] То же в `max_bot/app/routes/webapp.py`, `max_bot/app/routes/internal.py` и в обработке кнопки `cancel_visit_btn`

**Checkpoint**: US1 и US2 работают вместе — это MVP для выкладки на тестовый стенд

---

## Phase 5: User Story 3 — Защищённые служебные входы (Priority: P2)

**Goal**: Сигналы 1С, вебхуки мессенджеров и админка доступны только с секретами; повторы
безопасны; кнопки MAX работают (FR-009–FR-013a)

**Independent Test**: quickstart.md › US3 и строка «US4 (MAX) … Подтверждаю»

### Tests for User Story 3

- [ ] T055 [P] [US3] `telegram_bot/tests/contract/test_onec_signals.py` по contracts/onec-signals.md: без `X-Bot-Secret` и с неверным → 401 и запись не изменилась; неизвестный id → `not_found`; повтор `cancel-visit` → одно сообщение пациенту; `finish-visit` → `finished` и задание `feedback_*`
- [ ] T056 [P] [US3] `max_bot/tests/contract/test_onec_signals.py` — то же под `/max`
- [ ] T057 [P] [US3] `telegram_bot/tests/contract/test_webhook.py`: без `X-Telegram-Bot-Api-Secret-Token` → 401; повтор `update_id` не шлёт второе приветствие; `/start` → 2 вызова `sendMessage`; `/stats` не от админа игнорируется
- [ ] T058 [P] [US3] `max_bot/tests/contract/test_webhook.py`: без `X-Max-Bot-Api-Secret` → 401; `bot_started` → приветствие с кнопкой `open_app`; `message_callback` `confirm_visit` → `update_note` в 1С + `answers`; `cancel_visit_btn` отменяет запись нажавшего (`callback.user.user_id`); повтор `callback_id` не обрабатывается дважды
- [ ] T059 [P] [US3] `telegram_bot/tests/unit/test_config_and_admin.py`: без `ADMIN_PASSWORD` или `ONEC_WEBHOOK_SECRET` → выход с именем поля; `/admin` с неверным паролем → 401, с верным → 200
- [ ] T060 [P] [US3] `max_bot/tests/unit/test_config_and_admin.py` — то же

### Implementation for User Story 3

- [ ] T061 [P] [US3] В `telegram_bot/app/auth.py` добавить зависимости `require_onec_secret` (`X-Bot-Secret`), `require_tg_webhook_secret`, `require_admin` (Basic из `ADMIN_USERNAME`/`ADMIN_PASSWORD`, `compare_digest`, WARN в журнал при неудаче); в `telegram_bot/app/db.py` — `mark_processed(session, key) -> bool`
- [ ] T062 [P] [US3] То же в `max_bot/app/auth.py` (`require_max_webhook_secret` по `X-Max-Bot-Api-Secret`) и `max_bot/app/db.py`
- [ ] T063 [US3] Перенести отправку `cancel-visit` из модуля формы регистра «ПричиныОтменыЗаявок» в расширение конфигурации: `&После("ПриЗаписи")` документа «Заявка» по условиям из contracts/onec-signals.md (тип состояния «Отменена» или пометка удаления, заявка создана `api_bot`; без проверки слова «бот»); общая процедура отправки обоим ботам (`127.0.0.1:8001` и `127.0.0.1:8002/max`) с `X-Bot-Secret` (отдельный секрет на бот), адреса и секреты — из констант, таймаут 5 с, `Попытка` с записью в журнал регистрации; удалить старый код из формы; выгрузить расширение в `onec/`; применить сначала в тестовой УМЦ (принцип II)
- [ ] T064 [US3] Добавить в то же расширение отправку `finish-visit`, которой в конфигурации нет: `&После("ОбработкаПроведения")` документа «Прием» — если `ДокументОснование` является «Заявкой», созданной `api_bot`, отправить её UUID обоим ботам общей процедурой из T063; перепроведение безопасно (идемпотентность на стороне ботов); проверить в тестовой УМЦ, что проведение приёма приводит к просьбе об отзыве через 20 минут
- [ ] T065 [US3] Подключить `require_onec_secret` и идемпотентность (`onec:{type}:{id}`) в `telegram_bot/app/routes/internal.py`; унифицировать ответы по contracts/onec-signals.md
- [ ] T066 [US3] То же в `max_bot/app/routes/internal.py`
- [ ] T067 [US3] В `telegram_bot/app/routes/webhook.py` подключить `require_tg_webhook_secret` и идемпотентность (`tg:{update_id}`); `/stats` — только число активных записей и заданий; `callback_query` → `answerCallbackQuery`
- [ ] T068 [US3] Переписать `max_bot/app/routes/webhook.py`: `require_max_webhook_secret`; ответ 200 сразу, обработка через `BackgroundTasks`; разбор `message_callback` из `update["callback"]["payload"]` и `update["callback"]["user"]["user_id"]` + `answer_callback`; идемпотентность по `callback_id` / `mid`; удалить `GET /max/webhook`
- [ ] T069 [US3] Подключить `require_admin` в `telegram_bot/app/routes/admin.py` и `max_bot/app/routes/admin.py`; убрать пароль `5069522709` и значения по умолчанию `ADMIN_IDS` из кода
- [ ] T070 [P] [US3] `telegram_bot/scripts/register_webhook.py`: `setWebhook` с `secret_token` и `allowed_updates` через `TELEGRAM_API_BASE`; вывод результата без токена
- [ ] T071 [P] [US3] `max_bot/scripts/register_webhook.py`: `POST /subscriptions` с `secret` и `update_types=[bot_started, message_created, message_callback]`
- [ ] T072 [P] [US3] `telegram_bot/scripts/send_onec_signal.py` и `max_bot/scripts/send_onec_signal.py`: CLI `cancel|finish <appointment_id>` с `X-Bot-Secret` из `.env`, только для тестового стенда (замена удалённого `test.py`)

**Checkpoint**: US1–US3 работают независимо

---

## Phase 6: User Story 4 — Явное согласие и журналы без ПДн (Priority: P2)

**Goal**: FR-014–FR-018

**Independent Test**: quickstart.md › US4

### Tests for User Story 4

- [ ] T073 [P] [US4] `telegram_bot/tests/contract/test_consent.py`: `/book` и `/reschedule` без `pd_consent` или с `false` → 422 `PD_CONSENT_REQUIRED`, в 1С ничего не ушло
- [ ] T074 [P] [US4] `max_bot/tests/contract/test_consent.py` — то же
- [ ] T075 [P] [US4] `telegram_bot/tests/integration/test_no_pii_in_logs.py`: прогнать book → reschedule → cancel → book → finish-visit → вебхук `/start` с тестовыми ФИО, телефоном, датой рождения, в том числе при ошибке 1С (500) → в файле журнала, буфере админки и HTML `/admin` нет ни одной из этих строк
- [ ] T076 [P] [US4] `max_bot/tests/integration/test_no_pii_in_logs.py` — то же плюс входящий апдейт MAX с `user.name` не попадает в журнал

### Implementation for User Story 4

- [ ] T077 [P] [US4] В модель запроса `telegram_bot/app/routes/webapp.py` добавить `pd_consent: bool`, проверка → 422; то же в `max_bot/app/routes/webapp.py`
- [ ] T078 [P] [US4] В `telegram_bot/static/index.html` добавить отдельный чекбокс согласия (по умолчанию снят, ссылка из `/config`), визуально отделить его от «Напоминать о визите»; кнопка отправки проверяет согласие и показывает подсказку; убрать фразу «Нажимая кнопку…»; `pd_consent` в теле
- [ ] T079 [P] [US4] То же в `max_bot/static/index.html` (ссылка на политику из `/max/config`, открытие через `WebApp.openLink`)
- [ ] T080 [US4] Вычистить ПДн из вызовов логгера в `telegram_bot/app/**` и `max_bot/app/**`: вместо фамилии и имени — `user_id` и `appointment_id`; удалить логирование сырого апдейта MAX; `HTTPException(detail=str(e))` заменить кодами из контракта (FR-017, FR-018)
- [ ] T081 [US4] В `telegram_bot/app/routes/admin.py` и `max_bot/app/routes/admin.py` убрать из аналитики и списков ФИО и телефоны: оставить даты, филиалы, врачей, количество и статусы

**Checkpoint**: US1–US4 работают независимо

---

## Phase 7: User Story 5 — Безопасная выкладка (Priority: P3)

**Goal**: FR-019–FR-025, SC-006, SC-007

**Independent Test**: quickstart.md › US5

- [ ] T082 [P] [US5] Создать `.github/workflows/ci.yml`: триггеры `pull_request` и `push` в `main`; матрица `bot: [telegram_bot, max_bot]`; Python из `.python-version`; `pip install -r requirements-dev.txt`; `ruff check .`; `ruff format --check .`; `pytest -q`; job называется `CI`
- [ ] T083 [P] [US5] Создать `deploy/install-services.ps1`: параметры `-NssmPath`, `-RepoRoot`; для каждого бота — venv `.venv` в каталоге бота, `pip install -r requirements.txt`, `nssm install yasno-telegram-bot|yasno-max-bot <venv>\Scripts\python.exe -m app.main`, `AppDirectory`, `AppStdout`/`AppStderr` в `logs\`, `Start SERVICE_AUTO_START`, `AppExit Default Restart`; идемпотентен (повторный запуск обновляет параметры)
- [ ] T084 [P] [US5] Создать `deploy/deploy.ps1`: `git pull --ff-only` → `pip install -r requirements.txt` в venv каждого бота → `nssm restart` обеих служб → опрос `http://127.0.0.1:8001/healthz` и `http://127.0.0.1:8002/max/healthz` до 30 с → ненулевой код и понятное сообщение при сбое
- [ ] T085 [US5] Переписать `README.md` в корне (UTF-8): назначение, структура репозитория, запуск локально, тесты, ссылки на конституцию, `docs/rework-plan.md`, quickstart и скрипты `deploy/`; раздел «Первичная настройка стенда» — ручные шаги из quickstart.md › 3

**Checkpoint**: все истории готовы, выкладка воспроизводима

---

## Phase 8: Polish & Cross-Cutting Concerns

- [ ] T086 [P] Обновить `docs/rework-plan.md`: отметить этап 0 выполненным, добавить найденный дефект кнопок MAX и переход на `platform-api2.max.ru`
- [ ] T087 Прогнать `ruff format` и полный `pytest` в обоих ботах; убедиться, что `git ls-files` не содержит `.env`, `*.key`, `*.crt`, `*.db`, `*.log`, архивов
- [ ] T088 Выполнить quickstart.md целиком на тестовом стенде (тестовые боты + тестовая УМЦ), замерить: время CI на PR (SC-006, ≤ 10 мин), время `deploy/install-services.ps1` + `deploy/deploy.ps1` на чистом сервере (SC-007, ≤ 15 мин), время полного сценария записи до и после (SC-008); затем выкладка в прод по quickstart.md › 5 и проверка в `/admin`, что после миграции активных записей столько же, сколько будущих визитов

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (1)** → **Foundational (2)** → истории. T002 делается до T003/T004. T023 и T024 зависят
  от T009–T022 своего бота. Миграция (T032/T033) идёт после моделей (T013/T014) и до первого
  запуска на старой БД. Контрактные тесты клиента 1С (T034/T035) — после T029 и T015/T016
- **US1 (3)** и **US2 (4)** — P1, после фазы 2. Их можно делать параллельно, но T053/T054 правят
  те же файлы, что T042/T043, поэтому US2 после US1 для одного бота
- **US3 (5)** — после фазы 2. Файлы `internal.py`/`webhook.py` пересекаются с T053/T054/T046,
  значит после US2 для одного бота
- **US4 (6)** — после US1 (правит `index.html` и `webapp.py`)
- **US5 (7)** — после фазы 1; CI (T082) имеет смысл включить сразу после T025–T028
- **Polish (8)** — после всех историй

### User Story Dependencies

```text
Phase 1 ─► Phase 2 ─┬─► US1 ─► US2 ─► US3 ─┐
                    │     └───► US4 ───────┼─► Polish
                    └─► US5 (CI, deploy) ──┘
```

### Within Each User Story

- Тесты пишутся первыми и падают, потом идёт реализация
- `auth.py`/`db.py` → роуты → статика
- Внутри истории пары TG/MAX независимы

### Parallel Opportunities

- Почти все пары задач TG/MAX помечены [P] и идут параллельно (разные каталоги)
- В фазе 2 параллельны T009–T022, T025–T035 (с учётом зависимостей выше)
- В US5 T082–T084 не зависят друг от друга

---

## Parallel Example: User Story 1

```text
# Тесты обоих ботов одновременно:
T036 telegram_bot/tests/unit/test_auth.py
T037 max_bot/tests/unit/test_auth.py
T038 telegram_bot/tests/contract/test_webapp_api.py
T039 max_bot/tests/contract/test_webapp_api.py

# Затем реализация проверки подписи одновременно:
T040 telegram_bot/app/auth.py
T041 max_bot/app/auth.py
```

---

## Implementation Strategy

### MVP First (US1 + US2)

1. Фаза 1 + фаза 2: новая структура, поведение то же, smoke-тесты зелёные
2. US1: закрыть подмену id — главная уязвимость
3. US2: разблокировать повторную запись — главный баг для пациентов
4. **STOP and VALIDATE**: quickstart.md › US1, US2 на тестовом стенде. После этого возможна
   первая выкладка в прод. Правка 1С для этого не нужна: секрет 1С появляется в US3

### Incremental Delivery

1. MVP (US1 + US2) → тест → прод
2. US3 (секреты + кнопки MAX) → в 1С переделать `cancel-visit` и сделать `finish-visit` (T063, T064, код 1С — в `onec/`) → тест → прод
3. US4 (согласие, журналы) → тест → прод
4. US5 (CI, скрипты) — CI включается как можно раньше, скрипты выкладки — к первой выкладке

### Notes

- Каждый PR — один бот или одна пара TG/MAX с зелёным CI (конституция › Процесс разработки)
- Коммит после каждой задачи или логической группы
- Боевую 1С в тестах не использовать
