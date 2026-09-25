# Contract: вебхуки мессенджеров → бот

## Telegram — `POST /admin/webhook`

Путь сохраняется, чтобы не перерегистрировать URL без нужды. Регистрация —
`telegram_bot/scripts/register_webhook.py` через `TELEGRAM_API_BASE`:

```
setWebhook(url=<WEBAPP_URL>/admin/webhook, secret_token=<TG_WEBHOOK_SECRET>,
           allowed_updates=["message", "callback_query"])
```

| Проверка | Результат |
|----------|-----------|
| `X-Telegram-Bot-Api-Secret-Token` не совпадает с `TG_WEBHOOK_SECRET` | 401, апдейт не обрабатывается |
| `update_id` уже обработан | 200, без действий |
| `/start` | приветствие с кнопками WebApp «Записаться ✅» и «🌐 Наш сайт» (как сейчас) |
| `/stats` от `ADMIN_IDS` | количество активных записей и заданий (без ПДн) |

`callback_query` на этапе 0 принимается и подтверждается (`answerCallbackQuery`), но кнопок
пока нет. Подтверждение визита в Telegram — этап 2.

## MAX — `POST /max/webhook`

Регистрация — `max_bot/scripts/register_webhook.py`:

```
POST {MAX_API_URL}/subscriptions
Authorization: <MAX_BOT_TOKEN>
{"url": "<WEBAPP_URL>/max/webhook", "update_types": ["bot_started", "message_created", "message_callback"],
 "secret": "<MAX_WEBHOOK_SECRET>"}
```

`MAX_WEBHOOK_SECRET` — 5–256 символов `[A-Za-z0-9_-]`. URL — только HTTPS на порту 443
с доверенным сертификатом.

| Проверка | Результат |
|----------|-----------|
| `X-Max-Bot-Api-Secret` не совпадает | 401 |
| событие уже обработано (ключ из data-model › ProcessedEvent) | 200, без действий |
| `bot_started` или текст от пользователя | приветствие с кнопкой `{"type": "open_app", "text": "Записаться ✅", "web_app": "<ссылка/имя мини-приложения>"}` вместо `link` с `?user_id=` |
| `message_callback` с `callback.payload=confirm_visit` | поведение как задумано сейчас (`update_note` в 1С); перевод на статус — этап 2 |
| `message_callback` с `callback.payload=cancel_visit_btn` | отмена активной записи нажавшего (`callback.user.user_id`) |
| любой `message_callback` | ответ платформе `POST {MAX_API_URL}/answers?callback_id=…` с уведомлением, чтобы у пользователя не висела «загрузка» |

**Исправляемый дефект**: текущий код ищет `payload` в `message.payload` события `message_created`
и не подписан на `message_callback`. В журнале с мая по август 2026 нет ни одного
`message_callback`, поэтому кнопки «Подтверждаю / Отменить» в напоминаниях MAX не срабатывали.

Ответ 200 отдаётся сразу, отправка сообщений идёт в фоне. `GET /max/webhook` («Webhook active»)
удаляется: он был нужен для ручной проверки и раскрывает эндпоинт.

Сырые тела апдейтов в журнал не пишутся. Пишутся только `update_type`, `user_id` и результат.
