# Tasks: Рассылки из админки

**Input**: [spec.md](spec.md), [plan.md](plan.md), [contracts/broadcasts.md](contracts/broadcasts.md)

## Phase 1: Модель (Telegram)

- [X] T001 Модели Subscriber, Broadcast, BroadcastRecipient; схема v3 и заполнение subscribers из appointments в `db.py`
- [X] T002 `app/subscribers.py`: touch, set_consent, mark_blocked; очистка заблокировавших в `run_retention`

## Phase 2: US1 Согласие (P1)

- [X] T003 [US1] Тексты и кнопки вопроса о новостях, отписки (`texts.py`, `keyboards.py`)
- [X] T004 [US1] Вебхук: /start → приветствие + вопрос (если не отвечал), /news, кнопки `n:yes|no|off`; touch при любом сообщении и при записи через форму

## Phase 3: US2 Рассылка (P1)

- [X] T005 [US2] `app/broadcasts.py`: получатели, проверка черновика, отправка с ограничением скорости, 429/403, остановка, продолжение после старта
- [X] T006 [US2] `routes/broadcasts_api.py`: список, аудитория, картинка, тест, запуск, прогресс, остановка
- [X] T007 [US2] Вкладка «Рассылки» в `admin_ui/`

## Phase 4: MAX-бот

- [X] T008 Перенести T001–T007 в `max_bot` (`news:*`, вложение-картинка по ссылке, `routes/media.py`)

## Phase 5: Проверка

- [X] T009 [P] Тесты `tests/integration/test_broadcasts.py` в обоих ботах
- [X] T010 Скриншоты вкладки, README, выкладка
