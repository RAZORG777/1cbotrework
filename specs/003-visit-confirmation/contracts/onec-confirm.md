# Контракт: `POST confirm` (этап 2)

Метод HTTP-сервиса `tgbot` (расширение `TGBotAPI`), функция `ConfirmPOST`, URL-шаблон `/confirm`,
метод POST. Дополняет `docs/onec-contract.md` §1.

## Запрос

```json
{ "appointment_id": "<UUID заявки>", "platform": "telegram | max" }
```

## Ответы (HTTP 200)

```json
{ "status": "success", "appointment_id": "<UUID>", "already": false }
{ "status": "error", "code": "CANCELLED", "error": "Заявка отменена." }
```

| `code` | Когда |
|--------|-------|
| `BAD_REQUEST` | нет `appointment_id` или неверный UUID |
| `NOT_FOUND` | заявки нет |
| `CANCELLED` | пометка удаления или состояние из «отменённых» |
| `INTERNAL` | прочее; подробности — журнал регистрации, событие `Бот.Запись` |

Идемпотентность: строка «Пациент подтвердил запись» ищется в примечании; найдена → `already: true`,
заявка не записывается повторно. Состояние заявки не меняется. `update_note` остаётся до выкладки
обоих ботов, затем не используется.
