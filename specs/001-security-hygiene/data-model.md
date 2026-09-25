# Data Model: Гигиена репозитория и безопасность ботов

Модель одинакова для обоих ботов, но у каждого своя БД (`telegram_bot/appointments.db`,
`max_bot/max_appointments.db`). Источник истины по записи — 1С (принцип II).

## Appointment (`appointments`)

| Поле | Тип | Правила |
|------|-----|---------|
| `id` | int PK | |
| `user_id` | str | id пользователя мессенджера из проверенного `initData`/вебхука. Колонка переименовывается из `tg_id`, в API наружу не отдаётся |
| `platform` | str | `telegram` \| `max` |
| `appointment_id` | str, index | id записи 1С; уникален среди строк со `status='active'` |
| `branch`, `doctor_id`, `doctor_name`, `service_id`, `service_name` | str | как сейчас |
| `visit_at` | datetime (Europe/Moscow) | вычисляется из `date` + `time` 1С; заменяет строковые `date` и `time` |
| `first_name`, `last_name`, `middle_name`, `phone`, `birth_date` | str | ПДн, нужны для текстов уведомлений и переноса; удаляются вместе со строкой |
| `status` | str | `active` \| `cancelled` \| `finished` |
| `created_at` | datetime | |
| `closed_at` | datetime, null | от него считается срок хранения; null, пока `active` |

**Индексы**: `UNIQUE(user_id) WHERE status='active'` (одна активная запись на пациента,
FR-005); `INDEX(status, closed_at)` для очистки.

**Переходы состояний**

```text
            /book (1С success)
                  │
                  ▼
   ┌────────── active ───────────┐
   │   /reschedule: поля          │
   │   обновляются, остаётся      │
   │   active, задания            │
   │   пересоздаются              │
   │                              │
/cancel (пациент)       finish-visit (1С)
cancel-visit (1С)       или visit_at < now − 1 день (очистка)
   │                              │
   ▼                              ▼
cancelled                     finished
(closed_at = now)             (closed_at = now | visit_at)
   │                              │
   └────── closed_at < now − PD_RETENTION_DAYS ──► строка удалена
```

- Переход из `cancelled`/`finished` обратно в `active` невозможен. Новая запись — новая строка.
- При переходе в `cancelled`/`finished` удаляются задания `rem24h_*` и `rem2h_*`. Задание
  `feedback_*` остаётся: оно хранит только chat id и готовый текст.

## ProcessedEvent (`processed_events`)

| Поле | Тип | Правила |
|------|-----|---------|
| `key` | str PK | `onec:{type}:{appointment_id}`, `tg:{update_id}`, `max:{callback_id}` или `max:{update_type}:{mid}` |
| `created_at` | datetime | удаляется через 7 дней |

## Задания планировщика (APScheduler SQLAlchemyJobStore)

| id | Когда | Аргументы |
|----|-------|-----------|
| `rem24h_{appointment_id}` | `visit_at − 24 ч` | chat id, текст (MAX: + клавиатура) |
| `rem2h_{appointment_id}` | `visit_at − 2 ч` | chat id, текст |
| `feedback_{appointment_id}` | `finish + 20 мин` | chat id, текст |
| `retention_cleanup` | ежедневно 03:30 MSK + при старте | — |

Ключ заданий меняется с `{prefix}_{tg_id}` на `{prefix}_{appointment_id}`. Так удаление по
сигналу 1С становится точным и не цепляет чужие задания подстрокой, как `str(tg_id) in job.id`
сейчас.

## Настройки (Settings)

Полный список и умолчания — [research.md › R10](./research.md#r10-конфигурация). Правила валидации:
- обязательные строки непустые (для MAX также `MAX_MINIAPP`);
- `PD_RETENTION_DAYS` ≥ 1 и `INIT_DATA_MAX_AGE_HOURS` ≥ 1 — целые числа;
- URL начинаются с `https://` (для `ONEC_URL` допускается `http://` в локальной сети);
- при любой ошибке процесс завершается и печатает имя поля (FR-013).

## Миграция v0 → v1 (при старте, `PRAGMA user_version`)

1. `user_version = 0` и есть старая таблица `appointments` → создать новую таблицу, перенести
   строки: `user_id ← tg_id`, `visit_at ← date + time`, `status = 'active'`, если `visit_at` ≥
   начала сегодняшнего дня, иначе `'finished'` с `closed_at = visit_at`.
2. Переименовать задания `rem*_{tg_id}` в `rem*_{appointment_id}`: пересоздать их из активных строк.
3. `user_version = 1`. Миграция идёт в одной транзакции; перед ней создаётся копия файла БД
   `*.db.bak-v0` (в `.gitignore`).
4. Сразу после миграции выполняется очистка. Строки с `closed_at` старше срока удаляются (FR-008).
