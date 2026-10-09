# 1CBOT — боты записи клиники «ЯСНО ВИЖУ»

Два независимых бота записи пациентов на приём, **Telegram** и **MAX**, с интеграцией
с 1С: БИТ.Управление медицинским центром. В боте пациент выбирает филиал, врача, услугу и время,
записывается, переносит и отменяет запись, получает напоминания и просьбу оставить отзыв.

- Правила проекта — [конституция](.specify/memory/constitution.md) (обязательна к соблюдению).
- План реворка — [docs/rework-plan.md](docs/rework-plan.md).
- Контракт с 1С — [docs/onec-contract.md](docs/onec-contract.md).
- Этап 0 (безопасность и гигиена) — [specs/001-security-hygiene/](specs/001-security-hygiene/).

## Структура

```text
telegram_bot/        Telegram-бот (порт 8001)
  app/               FastAPI: config, auth, db, models, onec_client, messenger, reminders, routes/
  static/app/        сборка формы записи (из webapp/, в git не хранится)
  scripts/           register_webhook.py, send_onec_signal.py
  tests/             unit / contract / integration (pytest, заглушки 1С и Telegram)
max_bot/             MAX-бот (порт 8002, все пути под /max) — та же раскладка, свой код
webapp/              форма записи: Vite + Vue 3 + TypeScript + Tailwind, сборка на каждый бот
onec/                код 1С: HTTP-сервис, модуль «Заявки», расширение Бот_Интеграция
deploy/              install-services.ps1, deploy.ps1 (Windows + NSSM)
docs/, specs/        план, контракт, спецификации Spec Kit
```

Боты не импортируют код друг друга (принцип III). Общие правила описаны в `docs/`
и соблюдаются обоими.

## Запуск локально

```bash
cd telegram_bot                    # или max_bot
python -m venv .venv
.venv\Scripts\activate             # Linux/macOS: source .venv/bin/activate
pip install -r requirements-dev.txt
copy .env.example .env             # заполнить значения
python -m app.main
```

Без обязательных переменных бот не запустится и сообщит, каких не хватает.

Форма записи собирается отдельно (нужен Node.js 22 LTS):

```bash
cd webapp
npm ci
npm run build        # → telegram_bot/static/app и max_bot/static/app
npm run dev          # разработка; вне мессенджера форма покажет «Откройте запись через бота»
```

Без сборки бот работает, но `GET /` (`/max/`) отвечает 503 «Форма не собрана».

## Тесты и проверки

```bash
ruff check . && ruff format --check .
pytest -q
```

Форма: `cd webapp && npm run typecheck && npm test && npm run build && npm run e2e`
(Playwright идёт по обеим сборкам с заглушками SDK и API, снимки экранов 320/390/430 px в светлой
и тёмной теме — в `webapp/e2e/screenshots/`).

Тесты не обращаются к настоящей 1С и мессенджерам. На каждый PR их запускает GitHub Actions
(`.github/workflows/ci.yml`). Мерж в `main` возможен только при зелёном CI: включите в GitHub
Settings → Branches → Branch protection для `main` обязательную проверку `CI`.

## Переход со старой версии (один раз на сервере)

1. **Настройки.** Раньше был один `.env` в корне, теперь у каждого бота свой:
   `telegram_bot/.env` и `max_bot/.env`. Возьмите `.env.example`, перенесите старые значения
   и добавьте новые обязательные:
   - Telegram: `TG_WEBHOOK_SECRET`, `ONEC_WEBHOOK_SECRET`, `ADMIN_PASSWORD`, `PD_POLICY_URL`,
     `TELEGRAM_API_BASE` (адрес посредника Cloudflare, без `/bot…`);
   - MAX: `MAX_WEBHOOK_SECRET`, `MAX_MINIAPP`, `ONEC_WEBHOOK_SECRET`, `ADMIN_PASSWORD`,
     `PD_POLICY_URL`, `MAX_API_URL=https://platform-api2.max.ru`.

   Секреты — случайные строки `A-Za-z0-9_-`, для каждого бота свои.
2. **Базы.** Файлы `appointments.db` и `max_appointments.db` остаются в каталогах ботов.
   При первом запуске схема мигрирует автоматически, рядом появится копия `*.db.bak-v0`.
3. **Службы.** Остановите и удалите старые службы NSSM (`nssm stop <имя>`, `nssm remove <имя> confirm`),
   затем выполните `deploy\install-services.ps1 -NssmPath C:\путь\nssm.exe`.
4. **Сеть.** Боты слушают `127.0.0.1` (`HOST`). HTTPS-прокси на порту 443 должен стоять на том же
   сервере; если он на другом, укажите `HOST` явно.
5. **Вебхуки.** В каталоге каждого бота выполните `python -m scripts.register_webhook`.
   Серверы Telegram не достают до сервера клиники напрямую (соединение режется по пути),
   поэтому апдейты Telegram идут через Cloudflare Worker `tg-webhook-yasno`
   ([deploy/cloudflare/tg-webhook-relay.js](deploy/cloudflare/tg-webhook-relay.js)):
   в `telegram_bot/.env` — `TG_WEBHOOK_URL=https://tg-webhook-yasno.danicimo08.workers.dev/telegram`.
   Исходящие запросы к Bot API идут через `tg-proxy-yasno` (`TELEGRAM_API_BASE`).
6. **MAX.** В кабинете партнёра MAX привяжите к боту мини-приложение `https://<домен>/max/`.
   Значение `MAX_MINIAPP` — то, что платформа ждёт в кнопке `open_app` (обычно ник бота).
7. **1С.** Установите расширение `Бот_Интеграция` по [onec/extension/README.md](onec/extension/README.md)
   (там же отключается старая отправка из формы «Причины отмены заявок»).

8. **Этап 1 (пациент и медкарта).** Сначала 1С: загрузить `onec/TGBotAPI.cfe` и
   `onec/extension/Бот_Интеграция.cfe` (F7, перезапуск), проверить учётную политику («Основной вид
   медкарт») и филиал по умолчанию пользователя `api_bot`, затем выложить ботов. 1С принимает
   и старые форматы данных, поэтому порядок безопасен.

9. **Этап 3 (новая форма).** На сервер нужен Node.js 22 LTS: `deploy.ps1` собирает форму сам.
   Старые `static/index.html` и логотип удалены, форма берётся из `static/app`.

Порядок: сначала тестовые боты и тестовая копия УМЦ, потом прод
([quickstart](specs/001-security-hygiene/quickstart.md)).

## Выкладка

```powershell
.\deploy\deploy.ps1 -NssmPath C:\tools\nssm.exe
```

Скрипт выполняет `git pull --ff-only`, собирает форму (`npm ci && npm run build` в `webapp/`,
пропустить — `-SkipWebApp`), ставит зависимости, перезапускает обе службы и проверяет
`/healthz` и `/max/healthz`. Если проверка не прошла, скрипт завершается с ненулевым кодом.

## Безопасность сервера (аудит 09.10.2026)

- **Порты ботов** 8001 и 8002 закрыты от сети: `deploy\windows\firewall.ps1` (от администратора).
  Если NGINX Proxy Manager подключается к ботам не с этого же сервера, добавьте его адреса:
  `-AllowFrom 172.17.0.0/16`.
- **Автозапуск** без NSSM: `deploy\windows\install-tasks.ps1 -CreateUser` создаёт учётку
  `yasno-bots` без прав администратора и задания планировщика. Боты стартуют вместе с сервером
  и поднимаются после сбоя. Остановка — `deploy\windows\stop-bots.ps1`, обновление — `deploy\deploy.ps1`.
  Проверка и диагностика — `deploy\windows\check-tasks.ps1 -Start` (состояние заданий, причина
  ошибки из журнала планировщика, хвост runner.log, ответ /healthz).
- **Админка** блокирует адрес на 15 минут после 10 неудачных входов.
- **Резервные копии** `*.db.bak-*` удаляются автоматически через `PD_RETENTION_DAYS`.
- **Cloudflare:** `tg-webhook-yasno` принимает только адреса Telegram
  ([tg-webhook-relay.js](deploy/cloudflare/tg-webhook-relay.js)), `tg-proxy-yasno` пропускает
  только наш бот ([tg-api-proxy.js](deploy/cloudflare/tg-api-proxy.js)).
- **GitHub:** Settings → Code security → Dependabot alerts — включить; обновления зависимостей
  приходят PR по `.github/dependabot.yml`.

## Администрирование

Админка — инструмент разработчика ([specs/006-admin-devtool](specs/006-admin-devtool/spec.md)):
`https://<домен>/admin` (Telegram) и `https://<домен>/max/admin` (MAX), на тестовом стенде —
`http://127.0.0.1:8001/admin` и `http://127.0.0.1:8002/max/admin`. Логин и пароль —
`ADMIN_USERNAME` и `ADMIN_PASSWORD` из `.env`. ФИО, телефонов и секретов в админке нет.

| Вкладка | Что там |
|---------|---------|
| Обзор | проверки БД, планировщика, 1С, бота и вебхука; записи по статусам; ошибки за час; счётчики с запуска |
| Журнал | живой хвост (обновляется каждые 2 с), файлы журнала с поиском и фильтром, скачивание; уровень DEBUG на лету (до перезапуска) |
| Задания | напоминания, отзывы, ночная очистка: выполнить сейчас, пауза, удалить |
| Записи | поиск по номеру записи 1С или id пользователя; напомнить сейчас, пересоздать напоминания, закрыть запись только в боте |
| 1С | консоль только для чтения: ping, specialties, doctors, services, schedule |
| Рассылки | сообщение пользователям бота: текст, картинка, кнопка; тип «Важное» (всем) или «Новости и акции» (только согласившимся, с кнопкой «Отписаться»); аудитория — все, с активной записью, филиал; пробная отправка себе, ход рассылки, остановка |
| Сообщения | все шаблоны уведомлений на примере; отправка себе (только id из `ADMIN_IDS`) |
| Настройки | `.env` без секретов; перерегистрация вебхука, очистка ПДн, перезапуск службы |

Рассылки ([specs/007-broadcasts](specs/007-broadcasts/spec.md)): бот ведёт список пользователей
(только id мессенджера) — тех, кто нажал «Старт» или записался. После приветствия бот один раз
спрашивает согласие на новости и акции; /news — спросить снова. Рассылка идёт не быстрее
20 сообщений в секунду и после перезапуска продолжается с того же места. Картинки лежат в
`<бот>/media/broadcasts/` (в git не попадают); MAX берёт их по ссылке
`https://<домен>/max/media/broadcasts/…`, поэтому домен должен быть доступен из интернета.

Чтобы отправлять шаблоны себе, впишите свой id мессенджера в `ADMIN_IDS`. Каждое действие в
админке пишется в журнал: «Админка: … (логин)». Прежние `GET /admin/logs` и
`POST /admin/send-reminder` работают как раньше.

- Журналы лежат в `<бот>/logs/`, ротация 10 МБ, хранение 10 дней. ПДн в журналы не пишутся.
- Данные записей удаляются через `PD_RETENTION_DAYS` (30) дней после визита или отмены.
