# Implementation Plan: Ежедневная сводка и воронка

**Spec**: [spec.md](spec.md) · **Contracts**: [contracts/stats.md](contracts/stats.md)

## Технический подход

- `app/stats.py` (одинаковый в обоих ботах): события, шаги воронки, `inc`, `mark_step`,
  `collect`, `report_text`, очистка.
- Модели `daily_stats (day, name, value)` и `funnel_marks (day, step, uid)`; схема БД v3 → v4
  (таблицы создаёт create_all, данные не переносятся).
- Хуки событий: webapp.book/reschedule/cancel, visit_actions.confirm/cancel, internal.cancel-visit
  (только отмены клиникой), internal.finish-visit, subscribers.touch (новый пользователь).
- Сводка — задание планировщика `daily_report` (cron по DAILY_REPORT_TIME), функция в
  `reminders.py` рядом с очисткой; при пустом времени задание снимается.
- Очистка ПДн (03:30) удаляет отметки воронки прошлых дней и итоги старше 400 дней.
- Админка: вкладка «Статистика» (без сборки, как остальные).
- Форма: `api.track(step)` без ожидания ответа; App.vue следит за сменой экрана в режиме записи.

## Constitution Check

- Принцип III (независимые боты): модуль копируется, у каждого бота своя БД и сводка.
- ПДн: в итогах только числа; в отметках воронки — хэш id, живёт до следующей ночи.
