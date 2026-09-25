# Implementation Plan: Гигиена репозитория и безопасность ботов

**Branch**: `001-security-hygiene` | **Date**: 2026-09-25 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/001-security-hygiene/spec.md`

## Summary

Закрыть дыры безопасности и блокирующий баг в двух независимых ботах (Telegram и MAX), не меняя
пользовательский сценарий записи.

- Пациент определяется по подписанным данным запуска формы (`initData` Telegram и мини-приложения
  MAX), а не по `tg_id` из запроса.
- Служебные входы закрываются секретами: сигналы 1С, вебхуки мессенджеров, админка.
- Записи получают статусы: прошедшие перестают блокировать запись, данные удаляются через
  `PD_RETENTION_DAYS`.
- Из журналов убираются ПДн, в форму добавляется явное согласие.
- Чинятся кнопки «Подтверждаю / Отменить» в MAX: сейчас нажатия до бота не доходят.
- Каждый бот раскладывается по модулям с тестами, CI и скриптами выкладки. Устаревшие копии
  удаляются.

Подробности решений — в [research.md](./research.md).

## Technical Context

**Language/Version**: Python 3.12 в CI, совместимость с ≥ 3.10; версия сервера фиксируется
в `.python-version` (R14)

**Primary Dependencies**: FastAPI, Uvicorn, httpx, SQLAlchemy 2, APScheduler 3.x, loguru,
pydantic 2, pydantic-settings. Dev: pytest, pytest-asyncio, respx, time-machine, ruff

**Storage**: SQLite — отдельный файл на каждый бот (`appointments.db`, `max_appointments.db`)
плюс APScheduler SQLAlchemyJobStore в той же БД. Миграции через `PRAGMA user_version` (R7)

**Testing**: pytest + ASGITransport; заглушки 1С, Telegram и MAX через respx

**Target Platform**: Windows Server, службы NSSM; HTTPS 443 → 8001 (TG) и 8002 (MAX, префикс
`/max`) через существующий обратный прокси

**Project Type**: два независимых веб-сервиса (бэкенд + статический WebApp) в одном репозитории

**Performance Goals**: как в текущей версии; проверка `initData` добавляет < 1 мс на запрос;
ответ на вебхук MAX < 1 с (работа в фоне)

**Constraints**: без изменения URL и портов; протокол 1С меняется только заголовком секрета;
не трогать боевую 1С в тестах; нулевая потеря активных записей и напоминаний при миграции

**Scale/Scope**: десятки записей в неделю на бот, 2 филиала, ~12 врачей; ~1 500 строк Python
на бот после разбиения

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Принцип | Проверка | Статус |
|---------|----------|--------|
| I. Защита ПДн | initData/подпись MAX вместо id из запроса (FR-001–004); секреты в `.env`, fail-fast (FR-012–013); `.gitignore` уже покрывает секреты; явное согласие (FR-014–016); журналы без ПДн (FR-017); `PD_RETENTION_DAYS` (FR-007) | ✅ |
| II. 1С — источник истины | Все вызовы 1С только через `onec_client`; локальная БД — связка и служебные данные; сигналы `cancel-visit`/`finish-visit` синхронизируют статус. Карточка пациента и нормализация полей — этап 1, не нарушается | ✅ |
| III. Независимые боты | Изменения делаются в `telegram_bot/` и `max_bot/` отдельно, без общих импортов; одинаковые правила описаны в `contracts/`; копии удаляются (FR-019); тест и прод отличаются `.env` (FR-025) | ✅ |
| IV. Надёжность | Таймауты и повторы для 1С, TG и MAX; `TELEGRAM_API_BASE` в `.env` (FR-021); персистентные задания; идемпотентность (R6); прошедшая запись не блокирует (FR-005) | ✅ |
| V. Тесты и наблюдаемость | pytest с заглушками, контрактные тесты вебхуков; CI на PR (FR-022–023); loguru с ротацией, без подмены `print` | ✅ |
| VI. WebApp в стиле клиники | Этап 0 меняет в форме только отправку `initData` и чекбокс согласия. Сборка Vite и отказ от CDN — этап 3 | ⚠️ отложено, см. Complexity Tracking |

**Post-design re-check (после Phase 1)**: без изменений. Контракты
([contracts/](./contracts/)) и модель ([data-model.md](./data-model.md)) не добавляют нарушений.

## Project Structure

### Documentation (this feature)

```text
specs/001-security-hygiene/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── webapp-api.md        # API формы записи (оба бота)
│   ├── onec-signals.md      # входящие сигналы 1С
│   └── messenger-webhooks.md
├── checklists/requirements.md
└── tasks.md                 # /speckit-tasks
```

### Source Code (repository root)

Одинаковая раскладка в двух каталогах, без общего кода (принцип III):

```text
telegram_bot/                      max_bot/
├── app/                           ├── app/
│   ├── main.py      # FastAPI, lifespan, роутеры
│   ├── config.py    # Settings (pydantic-settings), fail-fast
│   ├── logging.py   # loguru: файл с ротацией, буфер админки, маскирование
│   ├── db.py        # engine, сессии, миграции user_version
│   ├── models.py    # Appointment, ProcessedEvent
│   ├── auth.py      # проверка initData, секретов, Basic admin
│   ├── onec_client.py
│   ├── messenger.py # отправка сообщений (TG через TELEGRAM_API_BASE / MAX API)
│   ├── reminders.py # планировщик, напоминания, отзыв, очистка
│   ├── doctors_enricher.py
│   └── routes/
│       ├── webapp.py    # /, /config, /doctors, /services, /schedule, /book, /reschedule, /my_appointment, /cancel
│       ├── internal.py  # /api/v1/internal/cancel-visit, finish-visit
│       ├── webhook.py   # вебхук мессенджера
│       ├── admin.py     # /admin, /admin/logs
│       └── health.py    # /healthz
├── static/          # index.html, Логотип.png
├── scripts/         # register_webhook.py, send_onec_signal.py (+ MAX: set_menu_button.py)
├── tests/
│   ├── conftest.py, helpers.py   # фабрика initData, заглушка 1С
│   ├── contract/    # вебхуки 1С и мессенджера, webapp API
│   ├── integration/ # запись → напоминания → finish → повторная запись → очистка
│   └── unit/        # auth, config, миграция, маскирование логов
├── requirements.txt, requirements-dev.txt, pyproject.toml (ruff, pytest)
└── .env.example

deploy/
├── install-services.ps1
└── deploy.ps1

.github/workflows/ci.yml
docs/rework-plan.md
```

**Structure Decision**: Два независимых сервиса с одинаковой внутренней раскладкой, чтобы
правило, изменённое в одном боте, было легко найти в другом (принцип III). Структура `app/`
заменяет монолитные `main.py` (500–800 строк). Внешние URL не меняются: в MAX префикс `/max`
задаётся роутером. `static/` отдаётся как раньше, форма меняется точечно (R1, R2, R11).

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| VI: форма пока грузит Vue и Tailwind с CDN | Этап 0 не пересобирает WebApp: только `initData`, чекбокс согласия и подключение MAX Bridge | Перенос на Vite сейчас удвоил бы объём этапа и смешал безопасность с редизайном; сделан в этапе 3 (docs/rework-plan.md) |
