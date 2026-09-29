# Tasks: Новый WebApp записи

**Input**: Design documents from `specs/004-webapp-redesign/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: требуются конституцией (принцип V): Vitest для логики, Playwright для сценариев,
pytest для изменённого контракта ботов.

## Phase 1: Setup

- [X] T001 Создать проект `webapp/` (package.json со скриптами dev/build/build:telegram/build:max/typecheck/test/e2e, tsconfig, vite.config.ts с режимами telegram|max: base, outDir, SDK-тег) в webapp/
- [X] T002 [P] Добавить `telegram_bot/static/app/`, `max_bot/static/app/`, `webapp/dist/`, `webapp/e2e/screenshots/`, `webapp/test-results/` в .gitignore
- [X] T003 [P] Токены, темы, шрифт Onest, анимации и reduced motion в webapp/src/styles/main.css; логотип в webapp/src/assets/logo.png

## Phase 2: Foundational

- [X] T004 Адаптер платформы (types, telegram, max, выбор по режиму) в webapp/src/platform/
- [X] T005 [P] Клиент API (initData, база из BASE_URL, таймаут 20 с, коды ошибок, повтор GET при сбое сети) в webapp/src/api/client.ts и webapp/src/api/types.ts
- [X] T006 [P] Чистая логика: маски и проверка телефона и даты рождения, ФИО (webapp/src/lib/patient.ts), расписание (части дня, страницы, ближайшая дата — webapp/src/lib/schedule.ts), услуги (псевдонимы, группы — webapp/src/lib/services.ts), форматирование дат по-русски (webapp/src/lib/format.ts)
- [X] T007 [P] Vitest для T006 и кодов ошибок в webapp/src/lib/*.test.ts
- [X] T008 Состояние пути записи и стек экранов в webapp/src/state/booking.ts; хранилище сохранённых пациентов с миграцией старых ключей в webapp/src/state/patients.ts
- [X] T009 Каркас App.vue: тема, переходы по направлению, главная кнопка (нативная/своя), «Назад» (нативная/своя), экран доступа в webapp/src/App.vue и webapp/src/components/
- [X] T010 [P] Бот Telegram: выдача static/app (503 без сборки), /assets, удалить /Логотип.png, старый static/index.html и Логотип.png в telegram_bot/app/routes/webapp.py и telegram_bot/app/main.py
- [X] T011 [P] Бот MAX: то же с префиксом /max в max_bot/app/routes/webapp.py и max_bot/app/main.py
- [X] T012 [P] pytest выдачи формы (index, 503, assets) в telegram_bot/tests/contract/test_webapp_static.py и max_bot/tests/contract/test_webapp_static.py

## Phase 3: User Story 1 — запись (P1) 🎯 MVP

**Goal**: запись от филиала до «Вы записаны».

**Independent Test**: Playwright-сценарий записи в обеих сборках; живой тест в Telegram.

- [X] T013 [P] [US1] Компоненты: StepProgress, ListRow, Avatar, SearchField, Segmented, Field, CheckRow, Skeleton, EyeLoader, SendingDots, Banner в webapp/src/components/
- [X] T014 [US1] Экран «Филиал» в webapp/src/screens/Home.vue
- [X] T015 [US1] Экран «Врач или услуга» (переключатель, поиск, пустые состояния) в webapp/src/screens/Choose.vue
- [X] T016 [US1] Экран «Услуга врача» и «Врачи услуги» в webapp/src/screens/DoctorServices.vue и webapp/src/screens/ServiceDoctors.vue
- [X] T017 [US1] Экран «Дата и время» (страницы дат, части дня, пусто, ближайшая дата) в webapp/src/screens/Time.vue
- [X] T018 [US1] Экран «Пациент» (сводка, профили, поля с масками, галочки, ошибки у полей, отправка) в webapp/src/screens/Patient.vue
- [X] T019 [US1] Экран «Вы записаны» с анимацией в webapp/src/screens/Success.vue
- [X] T020 [US1] Playwright: заглушки SDK/API, сценарий записи по врачу и по услуге, обе сборки в webapp/e2e/

## Phase 4: User Story 2 — «Моя запись», перенос, отмена (P1)

**Goal**: просмотр, перенос без повторного ввода данных, отмена на странице.

**Independent Test**: Playwright-сценарии переноса и отмены; pytest нового контракта.

- [X] T021 [P] [US2] Telegram: `/my_appointment` + doctor_id, service_id, confirmed; `/reschedule` с необязательным patient в telegram_bot/app/routes/webapp.py
- [X] T022 [P] [US2] MAX: то же в max_bot/app/routes/webapp.py
- [X] T023 [P] [US2] pytest контракта (поля my_appointment, перенос без patient, перенос с patient без согласия → 422) в telegram_bot/tests/contract/test_webapp_api.py и max_bot/tests/contract/test_webapp_api.py
- [X] T024 [US2] Экран «Моя запись» (статус подтверждения, перенос, отмена на странице, «Запись отменена») в webapp/src/screens/MyBooking.vue
- [X] T025 [US2] Режим переноса в состоянии и на экране «Дата и время» (главная кнопка «Перенести на …») в webapp/src/state/booking.ts и webapp/src/screens/Time.vue
- [X] T026 [US2] Playwright: перенос и отмена, вход с активной записью, SECOND_BOOKING_ERROR в webapp/e2e/

## Phase 5: User Story 3 — ожидание и ошибки (P2)

- [X] T027 [US3] SLOT_TAKEN: возврат на время, баннер, занятый слот с кольцом, сохранение данных пациента в webapp/src/screens/Time.vue и webapp/src/state/booking.ts
- [X] T028 [US3] Общая ошибка с телефоном и «Повторить», экраны доступа OPEN_FROM_BOT/SESSION_EXPIRED в webapp/src/components/ErrorState.vue и webapp/src/screens/Access.vue
- [X] T029 [US3] Playwright: занятое время, ошибки полей от сервера, 502, 401 в webapp/e2e/

## Phase 6: User Story 4 — мессенджер и доступность (P2)

- [X] T030 [US4] Смена темы на лету, цвета оболочки Telegram, вибрация по событиям в webapp/src/platform/ и webapp/src/App.vue
- [X] T031 [US4] Playwright: 320/390/430 × светлая/тёмная — нет горизонтальной прокрутки, кнопки ≥ 44 px, снимки; reduced motion в webapp/e2e/layout.spec.ts

## Phase 7: Polish

- [X] T032 [P] CI: задание webapp (npm ci, typecheck, vitest, build, e2e) в .github/workflows/ci.yml
- [X] T033 [P] Сборка формы в deploy/deploy.ps1 (npm ci && npm run build, понятная ошибка без Node)
- [X] T034 [P] README (раздел WebApp: сборка, тесты, выкладка), docs/rework-plan.md (статус этапа 3)
- [X] T035 Проверка бюджета веса (≤ 250 КБ gzip без фото) и контраста токенов
- [ ] T036 Живая проверка на тестовом контуре по quickstart.md (Telegram) и сборка MAX

## Dependencies

- Setup → Foundational → US1 → US2 (использует экраны US1) → US3, US4 → Polish.
- T010–T012 и T021–T023 (боты) не зависят от фронтенда и идут параллельно.

## Parallel Example

```text
T005, T006, T010, T011 — разные файлы, после T001.
T021, T022, T023 — оба бота одновременно.
```

## Implementation Strategy

MVP — US1 (запись) на Telegram-сборке; затем US2 (обязателен для готовности этапа), затем
состояния ошибок и проверка тем/ширин. Выкладка на тестовый контур — после T031.
