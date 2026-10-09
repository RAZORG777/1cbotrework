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

// Адреса, с которых Telegram присылает вебхуки (core.telegram.org/bots/webhooks).
// Остальным воркер отвечает 403 и ничего не пересылает.
const TELEGRAM_NETS = [
  ["149.154.160.0", 20],
  ["91.108.4.0", 22],
];

function ipv4ToInt(ip) {
  const parts = ip.split(".").map(Number);
  if (parts.length !== 4 || parts.some((p) => !(p >= 0 && p <= 255))) return null;
  return ((parts[0] << 24) | (parts[1] << 16) | (parts[2] << 8) | parts[3]) >>> 0;
}

function fromTelegram(ip) {
  const value = ipv4ToInt(ip || "");
  if (value === null) return false;
  return TELEGRAM_NETS.some(([net, bits]) => {
    const mask = bits === 0 ? 0 : (~0 << (32 - bits)) >>> 0;
    return (value & mask) === (ipv4ToInt(net) & mask);
  });
}

export default {
  async fetch(request) {
    const url = new URL(request.url);
    if (request.method !== "POST" || url.pathname !== "/telegram") {
      return new Response("Not found", { status: 404 });
    }
    if (!fromTelegram(request.headers.get("CF-Connecting-IP"))) {
      return new Response("Forbidden", { status: 403 });
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
