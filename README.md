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
  static/            WebApp (index.html) и логотип
  scripts/           register_webhook.py, send_onec_signal.py
  tests/             unit / contract / integration (pytest, заглушки 1С и Telegram)
max_bot/             MAX-бот (порт 8002, все пути под /max) — та же раскладка, свой код
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

## Тесты и проверки

```bash
ruff check . && ruff format --check .
pytest -q
```

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
6. **MAX.** В кабинете партнёра MAX привяжите к боту мини-приложение `https://<домен>/max/`.
   Значение `MAX_MINIAPP` — то, что платформа ждёт в кнопке `open_app` (обычно ник бота).
7. **1С.** Установите расширение `Бот_Интеграция` по [onec/extension/README.md](onec/extension/README.md)
   (там же отключается старая отправка из формы «Причины отмены заявок»).

8. **Этап 1 (пациент и медкарта).** Сначала 1С: загрузить `onec/TGBotAPI.cfe` и
   `onec/extension/Бот_Интеграция.cfe` (F7, перезапуск), проверить учётную политику («Основной вид
   медкарт») и филиал по умолчанию пользователя `api_bot`, затем выложить ботов. 1С принимает
   и старые форматы данных, поэтому порядок безопасен.

Порядок: сначала тестовые боты и тестовая копия УМЦ, потом прод
([quickstart](specs/001-security-hygiene/quickstart.md)).

## Выкладка

```powershell
.\deploy\deploy.ps1 -NssmPath C:\tools\nssm.exe
```

Скрипт выполняет `git pull --ff-only`, ставит зависимости, перезапускает обе службы и проверяет
`/healthz` и `/max/healthz`. Если проверка не прошла, скрипт завершается с ненулевым кодом.

## Администрирование

- `https://<домен>/admin` и `https://<домен>/max/admin` — очередь напоминаний, записи по статусам
  и журнал. Логин и пароль берутся из `.env`, ФИО и телефонов на этих страницах нет.
- Журналы лежат в `<бот>/logs/`, ротация 10 МБ, хранение 10 дней. ПДн в журналы не пишутся.
- Данные записей удаляются через `PD_RETENTION_DAYS` (30) дней после визита или отмены.
