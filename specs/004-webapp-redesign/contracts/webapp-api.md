# Contract: API ботов для новой формы (этап 3)

Дополняет [001 webapp-api](../../001-security-hygiene/contracts/webapp-api.md). Одинаково для
обоих ботов; у MAX все пути с префиксом `/max`. Аутентификация без изменений
(`Authorization: tma <initData>`).

## Выдача формы

| Запрос | Ответ |
|--------|-------|
| `GET /` | `static/app/index.html`, `Cache-Control: no-cache`; нет сборки → 503 `Форма не собрана` |
| `GET /assets/<file>` | файл сборки (JS, CSS, шрифт, логотип) |
| `GET /Логотип.png` | **удаляется** (логотип внутри сборки) |

## GET /my_appointment — изменено

```json
{"status": "success", "has_appointment": true,
 "data": {"appointment_id": "…", "branch": "Профсоюзная", "date": "2026-10-02", "time": "14:30",
          "doctor_id": "…", "doctor_name": "…", "service_id": "…", "service_name": "…",
          "confirmed": true}}
```

Новые поля: `doctor_id`, `service_id`, `confirmed` (визит подтверждён из напоминания).
ПДн пациента по-прежнему не отдаются.

## POST /reschedule — изменено

Тело как у `/book`, но `patient` **необязательно**:

- `patient` нет → бот берёт данные пациента из активной записи; `pd_consent` не проверяется.
- `patient` есть → как раньше, `pd_consent: true` обязателен, иначе 422 `PD_CONSENT_REQUIRED`.
- `old_appointment_id` обязателен и должен совпадать с активной записью, иначе 404 `NOT_FOUND`.

Ответы без изменений: `{"status":"success","appointment_id":"…"}` или ошибки по кодам.

## Коды ошибок, которые обрабатывает форма

| Код | Где | Реакция формы |
|-----|-----|---------------|
| `OPEN_FROM_BOT` (401) | любой | экран «Откройте запись через бота клиники» |
| `SESSION_EXPIRED` (401) | любой | экран «Сессия устарела…» |
| `SLOT_TAKEN` | book, reschedule | назад на «Дата и время», баннер, слот недоступен |
| `SECOND_BOOKING_ERROR` | book | «Моя запись» |
| `BAD_PHONE`, `BAD_BIRTH_DATE` | book, reschedule | ошибка у поля |
| `PD_CONSENT_REQUIRED` (422) | book | ошибка у согласия |
| `NOT_FOUND` (404) | reschedule, cancel | обновить «Мою запись» |
| `SERVICE_UNAVAILABLE` (502), `ONEC_ERROR`, прочее, сеть, таймаут 20 с | любой | общее сообщение с телефоном клиники, «Повторить» |

Для справочников (`/doctors`, `/services`, `/schedule`) форма игнорирует служебные элементы
`{"id":"empty"}` и `{"id":"error"}` и показывает пустое состояние или общую ошибку.
