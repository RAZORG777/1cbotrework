# Data Model: Новый WebApp записи

Схема БД ботов не меняется. Ниже — модели формы.

## BookingDraft (состояние пути, в памяти формы)

| Поле | Тип | Правила |
|------|-----|---------|
| branch | `"Профсоюзная" \| "Ватутинки"` | обязателен с шага 2 |
| path | `"doctor" \| "service"` | переключатель шага 2 |
| doctor | `{id, full_name, specialty?, photo_url?, experience?}` | обязателен с шага 3 |
| service | `{id, name, displayName, price?}` | обязателен с шага 3 |
| date | `YYYY-MM-DD` | из свободных дат врача |
| time | `HH:MM` | из слотов выбранной даты |
| patient | `PatientForm` | только для записи |
| remember | bool | по умолчанию true; пациент может снять галочку |
| notify | bool | по умолчанию true → `send_notifications` |
| consent | bool | по умолчанию false → `pd_consent` |
| mode | `"book" \| "reschedule"` | перенос пропускает шаг «Пациент» |
| takenSlots | `Set<"date time">` | времена, которые 1С вернула как занятые в этой сессии |

Переходы: `home → choose → (doctorServices | serviceDoctors) → time → patient → success`;
перенос: `my → time → success` (или `my → choose → … → time → success`).

## PatientForm

| Поле | Правило |
|------|---------|
| last_name, first_name | 1–100 символов, буквы, пробел, дефис; обрезка пробелов |
| middle_name | необязательно, до 100 |
| birth_date | маска `ДД.ММ.ГГГГ`; реальная дата, 1900 ≤ год, не в будущем |
| phone | маска `+7 (XXX) XXX-XX-XX`; ввод с 8 или 7 приводится к +7; ровно 10 цифр после 7 |

## SavedPatient (устройство пользователя)

Ключ хранилища `yasno_patients_v2`: массив `{key, label, last_name, first_name, middle_name,
birth_date, phone}`; `key = "me"` для «Я». При первом запуске переносятся старые ключи
`yasno_patient_data` и `yasno_family_profiles` (миграция на устройстве), старые ключи удаляются.

## ActiveAppointment (ответ `/my_appointment`)

`{appointment_id, branch, date, time, doctor_id, doctor_name, service_id, service_name, confirmed}`.

## ScheduleDay / Slot

`ScheduleDay = {date, weekday, dayNum, slots: string[]}`; части дня: утро `< 12:00`,
день `12:00–17:59`, вечер `≥ 18:00`. Страница дат — 6 дней; ближайшая свободная дата —
первый день с непустыми слотами после текущей страницы.

## ApiError

`{code, message?, status}`; коды — см. [contracts/webapp-api.md](contracts/webapp-api.md).
