// Cloudflare Worker: принимает апдейты Telegram и пересылает их боту.
// Нужен, когда серверы Telegram не могут подключиться к серверу клиники напрямую
// (соединение режется по пути), а Cloudflare до сервера достаёт.
//
// Установка: Cloudflare → Workers & Pages → Create → Worker → вставить этот код → Deploy.
// Затем в telegram_bot/.env:  TG_WEBHOOK_URL=https://<имя-воркера>.<аккаунт>.workers.dev/telegram
// и в каталоге telegram_bot:  .venv\Scripts\python -m scripts.register_webhook
//
// Секрет вебхука воркер не знает и не проверяет: он пересылает заголовок как есть,
// проверяет его сам бот (TG_WEBHOOK_SECRET).

const ORIGIN = "https://1cmed.one-two.online/admin/webhook";

export default {
  async fetch(request) {
    const url = new URL(request.url);
    if (request.method !== "POST" || url.pathname !== "/telegram") {
      return new Response("Not found", { status: 404 });
    }
    const headers = { "Content-Type": "application/json" };
    const secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token");
    if (secret) headers["X-Telegram-Bot-Api-Secret-Token"] = secret;
    try {
      const response = await fetch(ORIGIN, {
        method: "POST",
        headers,
        body: await request.text(),
      });
      // Код ответа бота уходит Telegram: при ошибке Telegram повторит доставку.
      return new Response(await response.text(), {
        status: response.status,
        headers: { "Content-Type": "application/json" },
      });
    } catch (err) {
      return new Response("Bot unreachable", { status: 502 });
    }
  },
};
