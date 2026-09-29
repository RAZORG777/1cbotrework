# Contract: адаптер платформы формы

Экраны работают только через этот интерфейс; реализации — Telegram и MAX, в тестах — заглушка.

| Возможность | Telegram (`window.Telegram.WebApp`) | MAX (`window.WebApp`) |
|-------------|-------------------------------------|------------------------|
| `initData` | `initData` | `initData` |
| тема | `colorScheme`, событие `themeChanged` | `prefers-color-scheme` устройства |
| цвета оболочки | `setHeaderColor`, `setBackgroundColor`, `setBottomBarColor` из токенов темы | — |
| главная кнопка | `MainButton`: `setParams({text,color,text_color,is_active,is_visible})`, `showProgress`/`hideProgress`, `onClick`/`offClick` | своя, закреплённая внизу страницы |
| «Назад» | `BackButton` show/hide/onClick/offClick | `BackButton` если есть, иначе своя в шапке |
| вибрация | `HapticFeedback` impact/notification/selectionChanged | то же, если есть |
| хранилище | `CloudStorage` (колбэки) + `localStorage` | `DeviceStorage` если есть + `localStorage` |
| прочее | `ready`, `expand`, `disableVerticalSwipes`, `openLink`, `close` | `ready`/`close`/`openLink` если есть |

Правила:

- Каждая возможность проверяется на наличие; отсутствие — не ошибка.
- Главная кнопка одна: экран задаёт `{text, enabled, loading, onClick}`; при уходе с экрана
  кнопка скрывается, обработчик снимается.
- Вибрация: `select` (выбор даты, времени, строки), `success`, `error`, `warning`.
