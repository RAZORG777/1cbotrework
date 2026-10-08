# Contract: рассылки

## Тексты бота (одинаковые в обоих ботах, `app/texts.py`)

| Ключ | Текст |
|------|-------|
| `NEWS_QUESTION` | Присылать вам новости и акции клиники «Ясно Вижу»? Это могут быть акции, изменения в графике работы и другие новости. Отписаться можно в любой момент. |
| `BTN_NEWS_YES` / `BTN_NEWS_NO` | «Да, присылать» / «Нет, спасибо» |
| `NEWS_YES` | Спасибо! Будем присылать новости и акции. Отписаться можно кнопкой в любой рассылке или командой /news. |
| `NEWS_NO` | Хорошо, не будем. Напоминания о приёмах будут приходить как раньше. Если передумаете — отправьте /news. |
| `BTN_UNSUBSCRIBE` | «Отписаться» |
| `UNSUBSCRIBED` | Вы отписались от новостей и акций. Напоминания о приёмах будут приходить как раньше. Подписаться снова — /news. |
| `NOTICE_NEWS_SAVED` | «Готово» (всплывающее уведомление на кнопке) |

Данные кнопок: Telegram `n:yes`, `n:no`, `n:off`; MAX `news:yes`, `news:no`, `news:off`.

## Модель (миграция схемы v2 → v3)

**subscribers**: `user_id` PK, `first_seen_at`, `last_seen_at`, `news_consent` (NULL — не
спрашивали, 1 — да, 0 — нет), `consent_at`, `blocked_at`.

**broadcasts**: `id`, `created_at`, `created_by`, `kind` (`service` | `promo`), `audience`
(`all` | `active` | `branch`), `branch`, `text`, `image`, `button_type` (`none` | `book` | `url`),
`button_text`, `button_url`, `status` (`sending` | `done` | `stopped`), `total`, `sent`, `failed`,
`blocked`, `started_at`, `finished_at`.

**broadcast_recipients**: (`broadcast_id`, `user_id`) PK, `state` (`pending` | `sent` | `failed` |
`blocked`). Строки удаляются, когда рассылка завершена или остановлена; итоги остаются в `broadcasts`.

## Получатели

| Тип | Аудитория | Кто получает |
|-----|-----------|--------------|
| `service` | `all` | все пользователи без `blocked_at` |
| `promo` | `all` | без `blocked_at` и с `news_consent = 1` |
| любой | `active` | то же, и есть активная запись |
| любой | `branch` | то же, и активная запись в выбранном филиале |

## API админки (база `/admin/api`, MAX — `/max/admin/api`)

| Метод | Путь | Тело / параметры | Ответ |
|-------|------|------------------|-------|
| GET | `/broadcasts` | — | `{"items": [рассылка без текста целиком], "subscribers": {"total","consent_yes","consent_no","not_asked","blocked"}, "branches": [...]}` |
| GET | `/broadcasts/audience` | `kind`, `audience`, `branch` | `{"count": 12}` |
| POST | `/broadcasts/image` | тело — файл, `Content-Type: image/jpeg` или `image/png`, до 5 МБ | `{"image": "a1b2….jpg"}`; иначе 422 `BAD_IMAGE` |
| GET | `/broadcasts/image/{name}` | — | картинка (для предпросмотра) |
| POST | `/broadcasts/test` | черновик + `chat_id` из `ADMIN_IDS` | `{"status":"ok"}`; 403 `NOT_ADMIN_RECIPIENT`; 502 `SEND_FAILED` |
| POST | `/broadcasts` | черновик | `{"id": 3, "total": 120}`; 422 `BAD_DRAFT` + `message`; 409 `NO_RECIPIENTS` |
| GET | `/broadcasts/{id}` | — | рассылка целиком с прогрессом |
| POST | `/broadcasts/{id}/stop` | — | `{"status":"ok"}` |

Черновик:

```json
{"kind": "promo", "audience": "branch", "branch": "Профсоюзная",
 "text": "<b>Скидка 20%</b> на подбор очков до 31 октября",
 "image": "a1b2c3.jpg",
 "button": {"type": "url", "text": "Подробнее", "url": "https://yasno-vizhu.com/akcii"}}
```

Проверки черновика: текст не пустой; теги только `b i u s a code`, `a` только с `href` на
`https://` или `http://`, все теги закрыты; длина текста ≤ 1024 с картинкой в Telegram, иначе
≤ 4000; подпись кнопки 1–40 символов, ссылка `https://`; филиал — из списка.

## Картинки для MAX

MAX берёт картинку по ссылке: `GET /max/media/broadcasts/{name}` без авторизации, имя — 32
случайных hex-символа. Telegram получает файл загрузкой (`sendPhoto` multipart), дальше — по
`file_id`.
