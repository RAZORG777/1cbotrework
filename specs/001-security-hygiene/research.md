# Research: Гигиена репозитория и безопасность ботов

**Feature**: [spec.md](./spec.md) · **Date**: 2026-09-25

## R1. Проверка личности пользователя в Telegram WebApp

- **Decision**: WebApp передаёт строку `Telegram.WebApp.initData` в заголовке
  `Authorization: tma <initData>` каждого запроса. Сервер проверяет подпись по стандартной схеме
  Telegram: `secret_key = HMAC_SHA256(key="WebAppData", msg=BOT_TOKEN)`,
  `hash = hex(HMAC_SHA256(secret_key, data_check_string))`, где `data_check_string` — пары
  `key=value` без `hash`, отсортированные по ключу и соединённые `\n`. Дополнительно
  `auth_date` должен быть не старше 24 ч (`INIT_DATA_MAX_AGE_HOURS`). Идентификатор пациента
  берётся из `user.id`. Сравнение подписей — `hmac.compare_digest`.
- **Rationale**: Официальный механизм Telegram Mini Apps. Подделать его без токена бота нельзя,
  отдельная сессия не нужна.
- **Alternatives considered**: собственные сессии или JWT после первого входа (лишнее состояние
  и та же исходная проверка); `initDataUnsafe` (не подписан, небезопасен).

## R2. Проверка личности пользователя в MAX

- **Decision**: Перевести запуск формы с кнопки-ссылки (`type: link`, `?user_id=` в URL) на мини-
  приложение MAX: зарегистрировать URL `https://1cmed.one-two.online/max/` в настройках бота
  на платформе MAX для партнёров, а в приветствии использовать кнопку `type: open_app`.
  В странице подключить `https://st.max.ru/js/max-web-app.js` и передавать `window.WebApp.initData`
  в `Authorization: tma <initData>`. Подпись проверяется по схеме MAX, такой же, как у Telegram:
  `secret_key = HMAC_SHA256("WebAppData", MAX_BOT_TOKEN)`, пары без `hash`, URL-декодированные,
  отсортированные, соединённые `\n`, hex-сравнение. `auth_date` не старше 24 ч.
- **Rationale**: Сейчас MAX-форма берёт `user_id` из адреса или `localStorage` и подставляет
  `'12345'`, если его нет. Это полностью подделываемо. Мини-приложение MAX даёт подписанные данные
  запуска (dev.max.ru/docs/webapps/validation).
- **Alternatives considered**: подписывать ссылку своим HMAC (`?user_id=…&sig=…`). Отклонено:
  ссылка живёт вечно и пересылается. Можно добавить срок жизни, но это собственная криптография
  вместо штатного механизма.
- **Риск**: регистрация мини-приложения требует доступа к кабинету MAX для партнёров
  (у ботов с 2025 года — только верифицированные юрлица РФ). Бот клиники уже опубликован,
  значит доступ есть. Действие выполняет владелец вручную; оно описано в quickstart.

## R3. Адрес MAX Bot API

- **Decision**: `MAX_API_URL` по умолчанию `https://platform-api2.max.ru`, токен только
  в заголовке `Authorization`.
- **Rationale**: Документация MAX с июля 2026 требует домен `platform-api2.max.ru`. Сейчас в `.env`
  стоит `platform-api.max.ru`, и в журнале на 24.08.2026 отправка ещё работает, но это
  переходное состояние. Смена — только настройкой, проверяется на тестовом боте.
- **Alternatives considered**: оставить старый домен — риск внезапной остановки уведомлений.

## R4. Защита вебхуков мессенджеров

- **Decision**:
  - Telegram: `setWebhook(url, secret_token=TG_WEBHOOK_SECRET)`. Входящие запросы без совпадающего
    заголовка `X-Telegram-Bot-Api-Secret-Token` → 401.
  - MAX: `POST /subscriptions {url, update_types, secret=MAX_WEBHOOK_SECRET}`. Проверяется
    заголовок `X-Max-Bot-Api-Secret`. Ответ 200 отдаётся сразу, тяжёлая работа уходит в фон
    (MAX повторяет доставку, если ответа нет 30 с).
  - Регистрация вебхуков — скриптом `scripts/register_webhook.py` каждого бота. Он читает URL
    и секрет из `.env`.
- **Rationale**: Штатные механизмы обеих платформ.
- **Alternatives considered**: белые списки IP (у Telegram и MAX диапазоны не гарантированы,
  к тому же TG идёт через Cloudflare-посредника).

## R5. Защита сигналов 1С

- **Decision**: 1С передаёт заголовок `X-Bot-Secret: <ONEC_WEBHOOK_SECRET>` в
  `POST /api/v1/internal/cancel-visit` и `/finish-visit` (для MAX — с префиксом `/max`).
  Сравнение через `hmac.compare_digest`, неверный или отсутствующий секрет → 401 и запись WARN
  в журнал без тела запроса. У каждого бота свой секрет.
- **Rationale**: Проще всего реализовать в 1С (`HTTPЗапрос.Заголовки.Вставить`). 1С у владельца,
  правку вносит он.
- **Alternatives considered**: Basic-auth (равноценно, но заголовок нагляднее в коде 1С);
  IP-whitelist (сервер 1С может стоять за NAT, хрупко).

## R6. Идемпотентность

- **Decision**: Таблица `processed_events(key PRIMARY KEY, created_at)`. Ключи: сигналы 1С —
  `onec:{type}:{appointment_id}`; Telegram — `tg:{update_id}`; MAX — `max:{callback_id}` или
  `max:{update_type}:{message.mid}`. Повтор → 200 без действий. Записи старше 7 дней удаляются
  ежедневной задачей.
- **Rationale**: Покрывает повторы MAX (до 10 попыток), повторы Telegram и повторные сигналы 1С.
- **Alternatives considered**: проверка «в памяти» — теряется при перезапуске.

## R7. Схема хранения и миграция

- **Decision**: SQLite, SQLAlchemy. В `appointments` снимается уникальность `tg_id`, добавляются
  `status` (`active|cancelled|finished`), `visit_at` (дата и время визита), `closed_at`
  (когда запись перестала быть активной) и `created_at`. Правило «одна активная запись» —
  частичный уникальный индекс `UNIQUE(user_id) WHERE status='active'`. Миграции — встроенный
  механизм на `PRAGMA user_version`: версия 0 → 1 переносит старую таблицу. Строки с датой визита
  в прошлом получают `status='finished'`, `closed_at = visit_at`.
- **Rationale**: 10–11 строк, один процесс на БД. Alembic для такой схемы избыточен, а встроенная
  миграция тестируется юнит-тестом на копии старой схемы.
- **Alternatives considered**: Alembic (лишняя зависимость и каталог миграций на 1 изменение);
  пересоздание БД (потеря активных записей и напоминаний).

## R8. Срок хранения и очистка

- **Decision**: `PD_RETENTION_DAYS` (int ≥ 1, по умолчанию 30). Задание APScheduler `cron` каждый
  день в 03:30 Europe/Moscow плюс запуск при старте (догоняет пропуск). Логика: (1) активные
  записи с `visit_at` < сейчас − 1 день → `finished`; (2) строки с `closed_at` <
  сейчас − `PD_RETENTION_DAYS` удаляются вместе с заданиями; (3) `processed_events` старше 7 дней
  удаляются. Задание отзыва хранит в аргументах только текст сообщения и id чата.
- **Rationale**: Выполняет SC-004 (срок + 1 сутки) и FR-005–FR-008.
- **Alternatives considered**: удаление сразу по `finish-visit` — отклонено владельцем (30 дней).

## R9. Журналы без ПДн

- **Decision**: loguru с глобальным `patcher`, который маскирует в сообщении телефоны
  (`\+?7[\d\s\-()]{10,}`) и даты `\d{2}\.\d{2}\.\d{4}` как страховку. Основное правило — не
  передавать ПДн в логгер: логируются `user_id`, `appointment_id`, статус. Сырые апдейты MAX
  и Telegram не логируются. Ответы 1С с ошибкой логируются без тела запроса. Буфер для панели
  администратора использует тот же форматтер. Пациенту ошибки показываются общими сообщениями,
  а подробности идут в журнал с id корреляции.
- **Rationale**: FR-017, FR-018, принцип I.
- **Alternatives considered**: только маскирование регулярками — ФИО так не поймать.

## R10. Конфигурация

- **Decision**: `pydantic-settings` в каждом боте, класс `Settings` с обязательными полями:
  `BOT_TOKEN`/`MAX_BOT_TOKEN`, `ONEC_URL`, `ONEC_USER`, `ONEC_PASSWORD`, `ONEC_WEBHOOK_SECRET`,
  `TG_WEBHOOK_SECRET`/`MAX_WEBHOOK_SECRET`, `ADMIN_USERNAME`, `ADMIN_PASSWORD`, `WEBAPP_URL`,
  `PD_POLICY_URL`; для MAX дополнительно `MAX_MINIAPP` (ссылка или идентификатор мини-приложения
  для кнопки `open_app`). Необязательные с умолчаниями: `TELEGRAM_API_BASE`
  (по умолчанию `https://api.telegram.org`; в проде — адрес Cloudflare Worker), `MAX_API_URL`,
  `PD_RETENTION_DAYS=30`, `INIT_DATA_MAX_AGE_HOURS=24`, `ADMIN_IDS`, `DB_PATH`, `LOG_DIR`, `PORT`.
  Ошибка валидации → процесс завершается с именем поля. Каждый бот читает `.env` из своего
  каталога (сейчас — общий `.env` в корне).
- **Rationale**: FR-012, FR-013, FR-020, FR-021, FR-025.

## R11. Согласие на ПДн

- **Decision**: В форме появляется отдельный чекбокс «Я даю согласие на обработку персональных
  данных» со ссылкой на `PD_POLICY_URL`. По умолчанию он снят. Чекбокс «Напоминать о визите»
  остаётся, по умолчанию отмечен. В запросе `/book` и `/reschedule` передаётся
  `pd_consent: true`, иначе сервер отвечает 422 (FR-016). Адрес политики отдаёт эндпоинт
  `/config` или он встраивается в страницу при отдаче. Обе формы ссылаются на один документ.
- **Rationale**: Сейчас TG ссылается на `yasno-vizhu.com/privacy-policy/`, а MAX — на PDF
  политики. Какой документ единый, решает владелец, значением `PD_POLICY_URL`.

## R12. Тестирование и CI

- **Decision**: pytest + pytest-asyncio; `httpx.AsyncClient(transport=ASGITransport(app))`;
  `respx` подменяет 1С, Telegram и MAX API; `time-machine` управляет временем для очистки.
  Генератор валидного `initData` в `tests/helpers.py` по тестовому токену. ruff для линтинга
  и форматирования. GitHub Actions `.github/workflows/ci.yml`: матрица `bot: [telegram_bot, max_bot]`,
  Python 3.12, шаги `pip install -r requirements-dev.txt` → `ruff check` →
  `ruff format --check` → `pytest`. Защита `main` (required status checks) включается
  вручную в настройках GitHub.
- **Rationale**: FR-022, FR-023, SC-006; тесты не трогают боевую 1С (принцип V).

## R13. Выкладка на Windows

- **Decision**: `deploy/install-services.ps1` один раз ставит службы `yasno-telegram-bot`
  и `yasno-max-bot` через NSSM: venv на бот, `AppDirectory` — каталог бота, stdout/stderr — в `logs/`,
  автозапуск, перезапуск при падении. `deploy/deploy.ps1`: `git pull --ff-only` →
  `pip install -r requirements.txt` для каждого бота → `nssm restart` → проверка
  `GET /healthz` (и `/max/healthz`) с таймаутом. При ошибке — ненулевой код и сообщение.
  `nssm.exe` в git не хранится: путь задаётся параметром скрипта или берётся из PATH.
- **Rationale**: FR-024, SC-007; текущая эксплуатация через NSSM сохраняется.
- **Открыто**: как HTTPS 443 проксируется на порты 8001/8002 на сервере (IIS/nginx/другое).
  Это вне репозитория, и этап 0 его не меняет. Владелец подтверждает при выкладке.

## R14. Версия Python

- **Decision**: Целевая версия — 3.12 (CI), совместимость с ≥ 3.10 не ломаем. Фактическая версия
  на сервере проверяется в первой задаче и фиксируется в `.python-version`. Если на сервере
  3.10/3.11, CI-матрица подстраивается под неё.

## R15. Состав удаляемых файлов

- **Decision**: Удаляются `main.py`, `main — копия.py`, `index.html`, `index — копия.html`,
  `index.html.bak`, `one_c_client.py`, `one_c_client.py.bak`, `bot.py`, `test.py`, `check_db.py`,
  `1/`, `telegram_bot_test/`, все `*.bak` в каталогах ботов, корневой `requirements.txt`
  и `Логотип.png` в корне (у ботов свои копии). `max_bot/1raz.py` переносится
  в `max_bot/scripts/set_menu_button.py`. `test.py` заменяется тестами и скриптом
  `scripts/send_onec_signal.py` с секретом (только для тестового стенда). Файлы вне git
  (`.env`, ключи, БД, `1CBOT.7z`, `nssm.exe`) не трогаются.
- **Rationale**: FR-019, принцип III (никаких копий).

## R16. HTTP-сервис 1С (`onec/http-service.bsl`)

- **Decision**: Модуль HTTP-сервиса УМЦ (методы `BookPOST`, `CancelPOST`, `ReschedulePOST`,
  `ScheduleGET`, `DoctorsGET`, `ServicesGET`, `SpecialtiesGET`, `PingGET`, `UpdateNotePOST`)
  версионируется в `onec/http-service.bsl` и служит источником истины для `docs/onec-contract.md`
  и контрактных тестов клиента 1С (T029, T034, T035). Вызовы `cancel-visit`/`finish-visit` в этом
  модуле **отсутствуют**: они отправляются из другого места конфигурации и выгружаются в `onec/`
  задачей T063.
- **Наблюдения для этапа 1 (ЭМК)**, в этапе 0 не исправляются:
  - клиент создаётся с `ОбменДанными.Загрузка = Истина` — отключаются обработчики УМЦ при
    записи; наиболее вероятная причина, почему пациенту не присваивается номер (код) и ЭМК
    не оформляется;
  - поиск клиента — только точное `Наименование` + `ДатаРождения`, без телефона и ё/е; при
    нераспознанной дате рождения используется `01.01.0001`, что может привязать запись
    к чужому клиенту с тем же ФИО;
  - медкарта нумеруется вручную «максимум + 1» (риск дублей при одновременной записи),
    ошибки её создания молча подавляются, резервная запись — снова в режиме `Загрузка`;
  - перенос всегда ставит длительность 30 мин (комментарий говорит 15) и примечание
    «Перенос из Telegram» даже для MAX;
  - ошибки возвращают боту `ОписаниеОшибки()` — внутренние тексты 1С уходят наружу.
