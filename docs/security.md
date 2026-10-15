# Безопасность сервера

[← К описанию проекта](../README.md)

Меры по итогам аудита 09.10.2026.

- **Порты ботов** 8001 и 8002 закрыты от сети: `deploy\windows\firewall.ps1` (от администратора).
  Если NGINX Proxy Manager подключается к ботам не с этого же сервера, добавьте его адреса:
  `-AllowFrom 172.17.0.0/16`.
- **Автозапуск** без NSSM: `deploy\windows\install-tasks.ps1 -CreateUser` создаёт учётку
  `yasno-bots` без прав администратора и задания планировщика. Боты стартуют вместе с сервером
  и поднимаются после сбоя. Остановка — `deploy\windows\stop-bots.ps1`, обновление — `deploy\deploy.ps1`.
  Проверка и диагностика — `deploy\windows\check-tasks.ps1 -Start` (состояние заданий, причина
  ошибки из журнала планировщика, хвост runner.log, ответ /healthz).
- **Админка** блокирует адрес на 15 минут после 10 неудачных входов.
- **Резервные копии** `*.db.bak-*` удаляются автоматически через `PD_RETENTION_DAYS`.
- **Cloudflare:** `tg-webhook-yasno` принимает только адреса Telegram
  ([tg-webhook-relay.js](../deploy/cloudflare/tg-webhook-relay.js)), `tg-proxy-yasno` пропускает
  только наш бот ([tg-api-proxy.js](../deploy/cloudflare/tg-api-proxy.js)).
- **GitHub:** Settings → Code security → Dependabot alerts — включить; обновления зависимостей
  приходят PR по `.github/dependabot.yml`.
