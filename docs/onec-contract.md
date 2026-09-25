# Контракт с 1С УМЦ

Источник истины — код в `onec/` (принцип II конституции). Изменение контракта вносится одновременно
в `onec/`, в этот документ, в оба бота (`app/onec_client.py`) и в их контрактные тесты
(`tests/contract/test_onec_client.py`, `tests/contract/test_onec_signals.py`).

- Конфигурация: БИТ.Управление медицинским центром 2.0.49.101, платформа 8.3.27.
- База HTTP-сервиса — переменная `ONEC_URL` ботов; авторизация — Basic (`ONEC_USER`/`ONEC_PASSWORD`).
- Все ответы — JSON в UTF-8.
- HTTP-сервис `tgbot` публикуется расширением `TGBotAPI` (роль `TG_ОсновнаяРоль`), а не основной конфигурацией. Его модуль совпадает с `onec/http-service.bsl`; URL-шаблоны: `/ping`, `/specialties`, `/doctors`, `/schedule`, `/book`, `/services/*`, `/cancel`, `/reschedule`, `/update_note`.

## 1. Бот → 1С (HTTP-сервис, `onec/http-service.bsl`)

| Метод | Функция 1С | Параметры | Успешный ответ | Ошибка |
|-------|-----------|-----------|----------------|--------|
| `GET ping` | `PingGET` | — | `{"status":"success","message":"1C API is running!"}` | — |
| `GET specialties` | `SpecialtiesGET` | — | `{"status":"success","data":[{"id","name"}]}` | — |
| `GET doctors` | `DoctorsGET` | `branch`, `date` (необяз.) | **массив** `[{"id","full_name","specialty_name"}]` | HTTP 500 `{"detail":"…"}` |
| `GET services` | `ServicesGET` | `doctor_id` | **массив** `[{"id","name","price"}]` | в массиве `{"id":"empty",…}` — нет услуг; `{"id":"error","name":"ОШИБКА 1С: …"}` |
| `GET schedule` | `ScheduleGET` | `doctor_id`, `branch`, `start_date`+`end_date` **или** `date` (`YYYY-MM-DD`) | `{"status":"success","schedule":{"YYYY-MM-DD":["HH:MM",…]}}` | HTTP 500 `{"error":"…"}` |
| `POST book` | `BookPOST` | тело ниже | `{"status":"success","appointment_id":"<UUID заявки>"}` | HTTP 200 `{"status":"error","error":"…"}` |
| `POST reschedule` | `ReschedulePOST` | тело `book` + `old_appointment_id` | `{"status":"success","appointment_id":"<UUID>"}` | HTTP 200 `{"status":"error","error":"…"}` |
| `POST cancel` | `CancelPOST` | `{"appointment_id"}` | `{"status":"success"}` | HTTP 200 `{"status":"error","error":"…"}` |
| `POST update_note` | `UpdateNotePOST` | `{"appointment_id","note"}` | `{"status":"success"}` | HTTP 404 (нет заявки), HTTP 500 |

Тело `book` / `reschedule`, которое отправляют боты:

```json
{
  "branch": "Профсоюзная",
  "doctor_id": "<UUID Справочник.Сотрудники>",
  "doctor_name": "…",
  "service_id": "<UUID Справочник.Номенклатура>",
  "service_name": "Первичный прием …",
  "date": "YYYY-MM-DD",
  "time": "HH:MM",
  "patient": {"first_name": "…", "last_name": "…", "middle_name": "…",
              "phone": "+7 (999) 123-45-67", "birth_date": "ДД.ММ.ГГГГ"},
  "platform": "telegram | max",
  "old_appointment_id": "<UUID> (только reschedule)"
}
```

Особенности, которые учитывают боты:
- `appointment_id` — UUID документа «Заявка»; по нему приходят сигналы 1С.
- Текст ошибки 1С не показывается пациенту: «занято» → код `SLOT_TAKEN`, остальное → `ONEC_ERROR`.
- `doctors`/`services` отвечают массивом без обёртки; клиент ботов принимает и `{"data": […]}`.
- Статус записи в 1С бот выставляет через `BOT_Первичка` / `BOT_Повторка` по названию услуги,
  `Ответственный` — пользователь `api_bot`. По этому признаку расширение отличает заявки бота.
- Формат телефона и даты рождения меняется на этапе 1 (`+7XXXXXXXXXX`, `YYYY-MM-DD`).

## 2. 1С → боты (сигналы, расширение `onec/extension/`)

1С и боты работают на одном сервере, сигналы идут по loopback:

| Сигнал | Telegram | MAX |
|--------|----------|-----|
| отмена | `POST http://127.0.0.1:8001/api/v1/internal/cancel-visit` | `POST http://127.0.0.1:8002/max/api/v1/internal/cancel-visit` |
| визит состоялся | `POST http://127.0.0.1:8001/api/v1/internal/finish-visit` | `POST http://127.0.0.1:8002/max/api/v1/internal/finish-visit` |

Заголовок `X-Bot-Secret: <секрет бота>` (у каждого бота свой, `ONEC_WEBHOOK_SECRET`), тело
`{"appointment_id": "<UUID заявки>"}`. Ответы: `200 {"status":"success"}`, `200 {"status":"not_found"}`
(заявка не этого бота), `401` (нет или неверный секрет). Повтор безопасен.

| Сигнал | Событие в УМЦ |
|--------|---------------|
| `cancel-visit` | запись «Заявки», созданной ботом: состояние сменилось на тип «Отменена» или установлена пометка удаления |
| `finish-visit` | проведение документа «Прием», у которого `ДокументОснование` — «Заявка», созданная ботом |

Подробности и дефекты прежней реализации — `specs/001-security-hygiene/contracts/onec-signals.md`.
