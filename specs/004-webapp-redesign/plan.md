# Implementation Plan: Новый WebApp записи

**Branch**: `004-webapp-redesign` | **Date**: 2026-09-29 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/004-webapp-redesign/spec.md`

## Summary

Старая форма записи (один `index.html` на Vue из CDN, Tailwind из CDN, Inter) заменяется
приложением на Vite + Vue 3 + TypeScript + Tailwind v4 по согласованным макетам. Исходники
лежат в `webapp/`, каждый бот получает свою сборку в `<бот>/static/app/` (Telegram — база `/`,
MAX — `/max/`). Различия каналов закрыты адаптером платформы: Telegram — нативные MainButton,
BackButton, тема, CloudStorage, вибрация; MAX — BackButton и вибрация из SDK, главная кнопка
и тема — свои. На стороне ботов: выдача сборки, `/my_appointment` отдаёт врача, услугу и
признак подтверждения, `/reschedule` работает без повторной передачи данных пациента.

## Technical Context

**Language/Version**: TypeScript 5 (браузер), Python 3.13 (боты)

**Primary Dependencies**: Vue 3.5, Vite 8, Tailwind CSS 4 (`@tailwindcss/vite`),
`@fontsource-variable/onest`, `@phosphor-icons/vue`; боты — FastAPI, pydantic 2 (без новых
зависимостей)

**Storage**: хранилище мессенджера (Telegram CloudStorage, MAX DeviceStorage) с запасным
`localStorage` — только сохранённые пациенты на устройстве; SQLite ботов без изменений схемы

**Testing**: Vitest (чистая логика: маски, проверка полей, группировка слотов и услуг, коды
ошибок), Playwright (сценарии на собранной форме с заглушкой SDK и API, 320/390/430 px, обе
темы), pytest ботов (контракт `/my_appointment`, `/reschedule`, выдача сборки)

**Target Platform**: Telegram WebApp (iOS, Android, Desktop) и MAX WebApp; сервер — Windows +
NSSM, выкладка `deploy/deploy.ps1`

**Project Type**: web — фронтенд `webapp/` + два независимых бэкенда

**Performance Goals**: первый экран ≤ 2 с на мобильном интернете; ресурсы формы ≤ 250 КБ gzip
(SC-006)

**Constraints**: без CDN (кроме SDK мессенджера); ширина от 320 px; нажимаемые элементы
≥ 44 px; `prefers-reduced-motion`; ПДн только на устройстве и в запросе записи

**Scale/Scope**: 9 экранов, 2 сборки, ~2 изменённых эндпоинта в каждом боте

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Принцип | Проверка | Статус |
|---------|----------|--------|
| I. ПДн | Личность по подписанному initData (без изменений); `/my_appointment` расширяется только врачом, услугой и признаком подтверждения, без ПДн; перенос без повторной передачи ПДн; сохранённые пациенты только на устройстве и только с галочкой; согласие по умолчанию не отмечено | ✅ |
| II. 1С — источник истины | Расписание, врачи, услуги из 1С через ботов; перенос и отмена — существующие методы 1С; данные пациента для переноса берутся из записи бота, в 1С уходят в нормализованном виде | ✅ |
| III. Независимые боты | Python-код ботов не импортирует друг друга; изменения эндпоинтов вносятся в оба бота одним PR; общая только исходная форма `webapp/`, из которой собираются две отдельные сборки (см. Complexity Tracking) | ✅ с обоснованием |
| IV. Надёжность | Таймауты и повтор при сбое сети в клиенте API; блокировка повторной отправки; понятные сообщения по кодам | ✅ |
| V. Тестируемость | Vitest + Playwright для формы, pytest для изменённого контракта; CI собирает форму и запускает её тесты | ✅ |
| VI. Стиль клиники | Токены из логотипа и макетов, тема мессенджера, 320 px, 44 px, Vite + Vue 3 + TS + Tailwind, шрифт и иконки в сборке | ✅ |
| Процесс | Старая форма удаляется, не копируется; `static/app/` и `node_modules/` в `.gitignore`; deploy собирает форму | ✅ |

Повторная проверка после Phase 1: без изменений, нарушений нет.

## Project Structure

### Documentation (this feature)

```text
specs/004-webapp-redesign/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── webapp-api.md        # изменения API ботов для формы
│   └── platform-adapter.md  # что форма берёт у Telegram и MAX
└── tasks.md
```

### Source Code (repository root)

```text
webapp/
├── package.json, vite.config.ts, tsconfig.json, playwright.config.ts
├── index.html                  # SDK мессенджера подставляется по режиму сборки
├── src/
│   ├── main.ts, App.vue        # экранный автомат, переходы, тема
│   ├── platform/               # types.ts, telegram.ts, max.ts, index.ts
│   ├── api/                    # client.ts (initData, таймаут, коды), types.ts
│   ├── state/booking.ts        # состояние пути записи
│   ├── lib/                    # phone, birthDate, schedule, services, format, errors
│   ├── screens/                # Home, Choose, DoctorServices, Time, Patient, Success, MyBooking, Access
│   ├── components/             # StepProgress, MainAction, ListRow, Skeleton, Banner, Field, …
│   ├── assets/logo.png
│   └── styles/main.css         # токены (@theme), темы, анимации, reduced motion
└── e2e/                        # Playwright: заглушка SDK и API, сценарии, снимки

telegram_bot/app/routes/webapp.py   # выдача static/app, my_appointment, reschedule
telegram_bot/app/main.py            # /assets из сборки
telegram_bot/tests/…                # контракт
max_bot/…                           # то же с префиксом /max
deploy/deploy.ps1                   # npm ci && npm run build перед перезапуском
.github/workflows/ci.yml            # задание webapp: typecheck, vitest, build, e2e
```

**Structure Decision**: web-приложение — один источник формы и две сборки; бэкенды остаются
раздельными копиями по принципу III.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| Общий исходник формы `webapp/` для двух ботов | План реворка («отдельная сборка на каждый бот») и единые макеты; поведение формы — часть единого контракта (принцип III требует одинакового поведения) | Две копии Vue-приложения неизбежно разойдутся и удвоят правки; сборки всё равно раздельные, отказ одной сборки не затрагивает другого бота |
