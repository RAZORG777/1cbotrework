# Установка и выкладка

[← К описанию проекта](../README.md)

Боты работают на Windows-сервере рядом с 1С; снаружи их публикует HTTPS-прокси
(NGINX Proxy Manager). Автозапуск, брандмауэр и проверки — в [security.md](security.md).

## Выкладка

```powershell
.\deploy\deploy.ps1 -NssmPath C:\tools\nssm.exe
```

Скрипт выполняет `git pull --ff-only`, собирает форму (`npm ci && npm run build` в `webapp/`,
пропустить — `-SkipWebApp`), ставит зависимости, перезапускает обе службы и проверяет
`/healthz` и `/max/healthz`. Если проверка не прошла, скрипт завершается с ненулевым кодом.

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
   ([deploy/cloudflare/tg-webhook-relay.js](../deploy/cloudflare/tg-webhook-relay.js)):
   в `telegram_bot/.env` — `TG_WEBHOOK_URL=https://<воркер>.workers.dev/telegram`.
   Исходящие запросы к Bot API идут через `tg-proxy-yasno` (`TELEGRAM_API_BASE`).
6. **MAX.** В кабинете партнёра MAX привяжите к боту мини-приложение `https://<домен>/max/`.
   Значение `MAX_MINIAPP` — то, что платформа ждёт в кнопке `open_app` (обычно ник бота).
7. **1С.** Установите расширение `Бот_Интеграция` по [onec/extension/README.md](../onec/extension/README.md)
   (там же отключается старая отправка из формы «Причины отмены заявок»).

8. **Этап 1 (пациент и медкарта).** Сначала 1С: загрузить `onec/TGBotAPI.cfe` и
   `onec/extension/Бот_Интеграция.cfe` (F7, перезапуск), проверить учётную политику («Основной вид
   медкарт») и филиал по умолчанию пользователя `api_bot`, затем выложить ботов. 1С принимает
   и старые форматы данных, поэтому порядок безопасен.

9. **Этап 3 (новая форма).** На сервер нужен Node.js 22 LTS: `deploy.ps1` собирает форму сам.
   Старые `static/index.html` и логотип удалены, форма берётся из `static/app`.

Порядок: сначала тестовые боты и тестовая копия УМЦ, потом прод
([quickstart](../specs/001-security-hygiene/quickstart.md)).
