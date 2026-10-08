# Contract: API админки

База: Telegram — `/admin`, MAX — `/max/admin`. Все адреса — под HTTP Basic (`ADMIN_USERNAME`,
`ADMIN_PASSWORD`), 401 с `WWW-Authenticate: Basic` при ошибке. Изменяющие запросы (POST) требуют
заголовок `X-Admin-Request: 1`, иначе 403 `{"error": "ADMIN_HEADER_REQUIRED"}`.

Ответы страницы и API: `Cache-Control: no-store`, `X-Frame-Options: DENY`,
`Referrer-Policy: no-referrer`; страница — `Content-Security-Policy: default-src 'self'; img-src 'self' data:; frame-ancestors 'none'`.

## Страница

| Метод | Путь | Ответ |
|-------|------|-------|
| GET | `` (база) | HTML интерфейса |
| GET | `/ui/admin.css`, `/ui/admin.js` | статика интерфейса |
| GET | `/logs` | текст: живой хвост, новые сверху (как раньше) |
| POST | `/send-reminder?appointment_id=&kind=24h\|2h` | `{"status":"ok"}` (как раньше, без заголовка) |

## Обзор и здоровье

`GET /api/overview`

```json
{
  "bot": "telegram", "admin": "admin", "now": "2026-10-08T14:00:00+03:00",
  "started_at": "…", "uptime_s": 3600, "version": "006", "python": "3.13.12",
  "pid": 1234, "log_level": "INFO",
  "db": {"path": "appointments.db", "size_bytes": 81920, "schema": 2},
  "appointments": {"active": 3, "cancelled": 1, "finished": 4, "confirmed": 1},
  "jobs": {"total": 7, "paused": 0, "next": {"id": "rem2h_…", "run_at": "…"}},
  "counters": {"webhook_updates": 10, "callbacks": 2, "onec_signals": 1, "bookings": 1,
               "reschedules": 0, "cancellations": 0, "messages_sent": 5, "messages_failed": 0,
               "onec_errors": 0, "admin_actions": 1},
  "log_last_hour": {"ERROR": 0, "WARNING": 1}
}
```

`GET /api/health` — проверки параллельно, каждая с таймаутом 5 с:

```json
{"checks": [
  {"name": "db", "ok": true, "ms": 1, "detail": "schema 2"},
  {"name": "scheduler", "ok": true, "ms": 0, "detail": "запущен, заданий: 7"},
  {"name": "onec", "ok": false, "ms": 5000, "detail": "таймаут"},
  {"name": "bot", "ok": true, "ms": 120, "detail": "@yasno_test_bot"},
  {"name": "webhook", "ok": true, "ms": 130, "detail": "…",
   "url": "https://…/admin/webhook", "expected_url": "https://…/admin/webhook",
   "pending": 0, "last_error": null}
]}
```

`webhook.ok = false`, если адрес не совпадает с ожидаемым или есть ошибка доставки за последние 10 минут.

## Журнал

| Метод | Путь | Параметры | Ответ |
|-------|------|-----------|-------|
| GET | `/api/logs/tail` | `after` (seq, по умолч. 0), `level`, `q` | `{"seq": 120, "lines": [{"seq","time","level","message"}]}` — по возрастанию, до 1000 |
| GET | `/api/logs/files` | — | `{"files": [{"name","size_bytes","modified"}]}` — только `*.log*` из `LOG_DIR` |
| GET | `/api/logs/file` | `name`, `level`, `q`, `limit` (≤ 2000, по умолч. 500) | `{"name","lines":[…строки…],"truncated":bool}` — последние подходящие; читается не больше 5 МБ с конца |
| GET | `/api/logs/download` | `name` | файл `text/plain`, `Content-Disposition: attachment` |
| POST | `/api/logs/level` | `{"level": "DEBUG"\|"INFO"\|"WARNING"}` | `{"level": "DEBUG"}` |

Имя файла — только из списка `/api/logs/files`, иначе 404 `{"error":"NOT_FOUND"}`.
Фильтр по уровню: строка проходит, если её уровень не ниже выбранного.

## Задания

| Метод | Путь | Ответ |
|-------|------|-------|
| GET | `/api/jobs` | `{"jobs": [{"id","kind","appointment_id","run_at","paused","trigger"}]}` |
| POST | `/api/jobs/{id}/run` | `{"status":"ok"}` — запуск в течение секунды |
| POST | `/api/jobs/{id}/pause` | `{"status":"ok"}` |
| POST | `/api/jobs/{id}/resume` | `{"status":"ok"}` |
| POST | `/api/jobs/{id}/delete` | `{"status":"ok"}` |

`kind`: `reminder_24h`, `reminder_2h`, `feedback`, `retention`, `other`. Неизвестный id → 404.

## Записи

`GET /api/appointments?status=active|cancelled|finished|all&q=&limit=100`

```json
{"items": [{"appointment_id": "…", "user_id": "…", "status": "active",
            "branch": "Профсоюзная", "doctor_name": "…", "service_name": "…",
            "visit_at": "…", "created_at": "…", "closed_at": null, "confirmed_at": null,
            "notify": true, "jobs": ["rem24h_…", "rem2h_…"]}], "total": 1}
```

ФИО, телефон и дата рождения в ответ не входят. `q` ищет по `appointment_id` и `user_id`.

| Метод | Путь | Тело | Ответ |
|-------|------|------|-------|
| POST | `/api/appointments/{id}/remind` | `{"kind": "24h"\|"2h"}` | `{"status":"ok"}` |
| POST | `/api/appointments/{id}/reschedule-reminders` | — | `{"status":"ok","scheduled":2}` |
| POST | `/api/appointments/{id}/close` | `{"status": "cancelled"\|"finished"}` | `{"status":"ok"}` — только активная запись; 1С не вызывается |

Нет активной записи с таким номером → 404.

## 1С (только чтение)

`GET /api/onec/{method}` — `method` ∈ `ping`, `specialties`, `doctors`, `services`, `schedule`;
параметры передаются в 1С как есть (`branch`, `date`, `doctor_id`, `start_date`, `end_date`).

```json
{"method": "doctors", "http_status": 200, "ms": 340, "body": […]}
```

Сетевая ошибка → `{"method", "http_status": null, "ms", "error": "ConnectTimeout"}`. Прочие методы → 404.

## Сообщения

| Метод | Путь | Ответ |
|-------|------|-------|
| GET | `/api/templates` | `{"templates": [{"key","title","text","buttons":[[{"text","tone"}]]}], "recipients": ["…ADMIN_IDS…"]}` |
| POST | `/api/templates/{key}/send` | тело `{"chat_id": "…"}`; `{"status":"ok"}` или 502 `{"error":"SEND_FAILED"}`; chat_id не из `ADMIN_IDS` → 403 `{"error":"NOT_ADMIN_RECIPIENT"}` |

Шаблоны заполняются вымышленным пациентом «Анна Сергеевна» и записью на завтра.

## Настройки и обслуживание

`GET /api/settings` → `{"settings": [{"name","value","secret"}]}`. Для секретов `value` —
`"задан"` или `"не задан"`. Секреты: токен бота, секреты вебхуков, пароли.

| Метод | Путь | Ответ |
|-------|------|-------|
| POST | `/api/webhook/register` | `{"ok": bool, "detail": "…"}` |
| POST | `/api/maintenance/retention` | `{"finished","deleted","events"}` |
| POST | `/api/maintenance/restart` | `{"status":"restarting"}`; через 0,5 с процесс штатно завершается |
