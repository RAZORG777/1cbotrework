// Cloudflare Worker: посредник к Telegram Bot API для исходящих запросов бота
// (TELEGRAM_API_BASE). Пропускает только запросы ботов из ALLOWED_BOT_IDS — иначе через воркер
// мог бы ходить в Telegram кто угодно со своим токеном (аудит 09.10.2026, п.6).
//
// ID бота — число до двоеточия в BOT_TOKEN (это не секрет, секрет — часть после двоеточия).
// Установка: Cloudflare → Workers & Pages → tg-proxy-yasno → Edit code → вставить → Deploy.

const ALLOWED_BOT_IDS = ["ВПИШИТЕ_ID_БОТА"];

export default {
  async fetch(request) {
    const url = new URL(request.url);
    const match = url.pathname.match(/^\/(?:file\/)?bot(\d+):[A-Za-z0-9_-]+\//);
    if (!match || !ALLOWED_BOT_IDS.includes(match[1])) {
      return new Response("Forbidden", { status: 403 });
    }
    const target = "https://api.telegram.org" + url.pathname + url.search;
    return fetch(new Request(target, request));
  },
};
