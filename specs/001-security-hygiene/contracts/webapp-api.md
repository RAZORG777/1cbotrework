# Contract: API формы записи

Одинаков для обоих ботов. База: Telegram — `https://1cmed.one-two.online/`, MAX —
`https://1cmed.one-two.online/max/`.

## Аутентификация

Каждый запрос, кроме `GET /`, `GET /Логотип.png`, `GET /healthz` и `GET /config`, несёт заголовок

```
Authorization: tma <initData>
```

- Telegram: `window.Telegram.WebApp.initData`.
- MAX: `window.WebApp.initData` (скрипт `https://st.max.ru/js/max-web-app.js`).

Ответы при ошибке проверки:

| Ситуация | Код | Тело |
|----------|-----|------|
| заголовка нет или `initData` пуст | 401 | `{"error": "OPEN_FROM_BOT"}` |
| подпись неверна | 401 | `{"error": "OPEN_FROM_BOT"}` |
| `auth_date` старше `INIT_DATA_MAX_AGE_HOURS` | 401 | `{"error": "SESSION_EXPIRED"}` |

Форма показывает на `OPEN_FROM_BOT` текст «Откройте запись через бота клиники», а на
`SESSION_EXPIRED` — «Сессия устарела, откройте форму из бота заново».

## Изменения относительно текущей версии

| Эндпоинт | Было | Стало |
|----------|------|-------|
| `GET /config` | — | **новый**, без авторизации: `{"pd_policy_url": "…"}` |
| `GET /doctors`, `/services`, `/schedule` | без авторизации | + `Authorization` (защита от выгрузки расписания ботами); параметры без изменений. Удаляется дубль роута `/schedule` |
| `GET /my_appointment?tg_id=` | `tg_id` в query | без параметров; пользователь берётся из `initData` |
| `POST /book` | тело с `tg_id`; `?send_notifications=` | тело без `tg_id`; `send_notifications` переезжает в тело; + `pd_consent` |
| `POST /reschedule` | то же + `old_appointment_id` | то же; `old_appointment_id` сверяется с активной записью пользователя |
| `POST /cancel` | `{"tg_id": …}` | пустое тело; отменяется активная запись пользователя |

## POST /book, POST /reschedule — тело

```json
{
  "branch": "Профсоюзная",
  "doctor_id": "…", "doctor_name": "…",
  "service_id": "…", "service_name": "…",
  "date": "2026-10-01", "time": "10:30",
  "patient": {"first_name": "…", "last_name": "…", "middle_name": "…",
              "phone": "+7 (999) 123-45-67", "birth_date": "01.02.1990"},
  "send_notifications": true,
  "pd_consent": true,
  "old_appointment_id": "…"
}
```

- `pd_consent` обязателен и равен `true`, иначе 422 `{"error": "PD_CONSENT_REQUIRED"}`.
- `old_appointment_id` передаётся только в `/reschedule`. Если он не совпадает с активной
  записью пользователя → 404 `{"error": "NOT_FOUND"}`.
- Формат `phone` и `birth_date` на этапе 0 не меняется: нормализацию под 1С вводит этап 1.

## Ответы

| Ситуация | Код | Тело |
|----------|-----|------|
| успех `/book` | 200 | `{"status": "success", "appointment_id": "…"}` (как отвечает 1С) |
| уже есть активная запись | 200 | `{"status": "error", "error": "SECOND_BOOKING_ERROR"}` (как сейчас) |
| 1С вернула ошибку | 200 | `{"status": "error", "error": "ONEC_ERROR"}` — без текста 1С |
| 1С недоступна или сбой | 502 | `{"status": "error", "error": "SERVICE_UNAVAILABLE"}` |
| `/my_appointment` | 200 | `{"status": "success", "has_appointment": bool, "data": {…}}` — поля `data` как сейчас, без ПДн |
| `/cancel` без активной записи | 404 | `{"status": "error", "error": "NOT_FOUND"}` |

Текст исключения (`str(e)`) в ответ не попадает никогда (FR-018).
