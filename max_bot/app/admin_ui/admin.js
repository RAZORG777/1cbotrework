/* Админка бота «ЯСНО ВИЖУ» — инструмент разработчика (specs/006-admin-devtool).
   Без фреймворков. Данные — JSON API рядом со страницей: <страница>/api/… */
"use strict";

const BASE = location.pathname.replace(/\/+$/, "");
const API = BASE + "/api";
const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));

/* ---------- Общие помощники ---------- */

function esc(value) {
  return String(value ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
}

class ApiError extends Error {
  constructor(status, body) {
    super((body && (body.error || body.detail)) || "HTTP " + status);
    this.status = status;
    this.body = body;
  }
}

async function api(path, { method = "GET", body, params } = {}) {
  let url = API + path;
  if (params) {
    const qs = new URLSearchParams(Object.entries(params).filter(([, v]) => v !== "" && v != null));
    if ([...qs].length) url += "?" + qs;
  }
  const headers = { Accept: "application/json" };
  if (method !== "GET") {
    headers["X-Admin-Request"] = "1";
    headers["Content-Type"] = "application/json";
  }
  const res = await fetch(url, { method, headers, body: body ? JSON.stringify(body) : method !== "GET" ? "{}" : undefined, credentials: "same-origin", cache: "no-store" });
  let data = null;
  try { data = await res.json(); } catch { /* пустой ответ */ }
  if (res.status === 401) {
    toast("Вход сброшен — обновите страницу и введите логин и пароль.", true);
  }
  if (!res.ok) throw new ApiError(res.status, data);
  return data;
}

function toast(text, isError = false) {
  const el = document.createElement("div");
  el.className = "toast" + (isError ? " err" : "");
  el.textContent = text;
  $("#toasts").append(el);
  setTimeout(() => el.remove(), isError ? 7000 : 3500);
}

function confirmAction(title, text, okLabel = "Да", danger = false) {
  const dlg = $("#confirm");
  $("#confirm-title").textContent = title;
  $("#confirm-text").textContent = text;
  const ok = $("#confirm-ok");
  ok.textContent = okLabel;
  ok.className = "btn " + (danger ? "danger" : "primary");
  dlg.returnValue = "";
  dlg.showModal();
  return new Promise((resolve) => dlg.addEventListener("close", () => resolve(dlg.returnValue === "ok"), { once: true }));
}

async function withBusy(button, fn) {
  if (button) button.disabled = true;
  try { return await fn(); }
  catch (e) { toast(describeError(e), true); }
  finally { if (button) button.disabled = false; }
}

function describeError(e) {
  if (!(e instanceof ApiError)) return "Нет связи с ботом";
  const code = e.body && (e.body.error || (e.body.detail && e.body.detail.error));
  const known = {
    NOT_FOUND: "Не найдено — возможно, уже изменилось. Обновите список.",
    ADMIN_HEADER_REQUIRED: "Запрос отклонён защитой",
    NOT_ADMIN_RECIPIENT: "Получатель не из ADMIN_IDS",
    SEND_FAILED: "Мессенджер не принял сообщение — подробности в журнале",
  };
  return known[code] || (code ? String(code) : "Ошибка HTTP " + e.status);
}

/* Время приходит по Москве без пояса: «2026-10-08T14:00:00». */
const pad = (n) => String(n).padStart(2, "0");
function parseTime(s) { return s ? new Date(s) : null; }
function fmtTime(s, withYear = false) {
  const d = parseTime(s);
  if (!d || isNaN(d)) return "—";
  return `${pad(d.getDate())}.${pad(d.getMonth() + 1)}${withYear ? "." + d.getFullYear() : ""} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
}
let serverSkew = 0; // разница часов браузера и бота (бот — по Москве)
function relTime(s) {
  const d = parseTime(s);
  if (!d) return "";
  const diff = Math.round((d - (Date.now() + serverSkew)) / 60000);
  const abs = Math.abs(diff);
  let text;
  if (abs < 1) text = "сейчас";
  else if (abs < 60) text = abs + " мин";
  else if (abs < 60 * 36) text = Math.round(abs / 60) + " ч";
  else text = Math.round(abs / 1440) + " дн";
  if (abs < 1) return text;
  return diff > 0 ? "через " + text : text + " назад";
}
function fmtUptime(sec) {
  const d = Math.floor(sec / 86400), h = Math.floor((sec % 86400) / 3600), m = Math.floor((sec % 3600) / 60);
  return (d ? d + " д " : "") + (d || h ? h + " ч " : "") + m + " мин";
}
function fmtBytes(n) {
  if (n < 1024) return n + " Б";
  if (n < 1024 * 1024) return (n / 1024).toFixed(1) + " КБ";
  return (n / 1024 / 1024).toFixed(1) + " МБ";
}

/* ---------- Тема ---------- */

function applyTheme(mode) {
  const root = document.documentElement;
  if (mode === "light" || mode === "dark") root.dataset.theme = mode;
  else delete root.dataset.theme;
  $$("[data-theme-set]").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.themeSet === mode)));
  try { localStorage.setItem("admin-theme", mode); } catch { /* приватный режим */ }
}
function initTheme() {
  let mode = "auto";
  try { mode = localStorage.getItem("admin-theme") || "auto"; } catch { /* нет хранилища */ }
  applyTheme(mode);
  $$("[data-theme-set]").forEach((b) => b.addEventListener("click", () => applyTheme(b.dataset.themeSet)));
}

/* ---------- Вкладки ---------- */

const loaders = {};
let currentTab = "overview";

function showTab(name) {
  if (!$("#tab-" + name)) name = "overview";
  currentTab = name;
  $$(".tabs [role=tab]").forEach((b) => b.setAttribute("aria-selected", String(b.dataset.tab === name)));
  $$(".tab-panel").forEach((p) => { p.hidden = p.id !== "tab-" + name; });
  if (location.hash !== "#" + name) history.replaceState(null, "", "#" + name);
  if (loaders[name]) loaders[name]();
  logs.setActive(name === "logs");
}

function initTabs() {
  $$(".tabs [role=tab]").forEach((b) => b.addEventListener("click", () => showTab(b.dataset.tab)));
  window.addEventListener("hashchange", () => showTab(location.hash.slice(1)));
}

/* ---------- Обзор ---------- */

const CHECK_TITLES = { db: "База данных", scheduler: "Планировщик", onec: "1С", bot: "Бот в мессенджере", webhook: "Вебхук" };
const COUNTER_TITLES = {
  webhook_updates: "Апдейтов вебхука",
  callbacks: "Нажатий кнопок",
  onec_signals: "Сигналов 1С",
  bookings: "Записей",
  reschedules: "Переносов",
  cancellations: "Отмен пациентом",
  messages_sent: "Сообщений отправлено",
  messages_failed: "Сообщений не доставлено",
  onec_errors: "Ошибок 1С",
  http_errors: "Ошибок сервера",
  admin_actions: "Действий в админке",
};

function renderHealth(checks) {
  const bad = checks.filter((c) => !c.ok);
  const top = $("#top-status");
  top.innerHTML = bad.length
    ? `<span class="dot dot-err"></span><span>Проблемы: ${esc(bad.map((c) => CHECK_TITLES[c.name] || c.name).join(", "))}</span>`
    : `<span class="dot dot-ok"></span><span>Всё работает</span>`;
  $("#health").innerHTML = checks.map((c) => {
    let extra = "";
    if (c.name === "webhook") {
      const mismatch = c.url && c.expected_url && c.url !== c.expected_url;
      extra += c.url ? `<div class="url">${esc(c.url)}</div>` : "";
      if (mismatch) extra += `<div class="check-detail">ожидается: <span class="url">${esc(c.expected_url)}</span></div>`;
      if (c.last_error) extra += `<div class="check-detail">последняя ошибка: ${esc(c.last_error)}</div>`;
      if (!c.ok) extra += `<button type="button" class="btn sm" data-op="webhook">Перерегистрировать вебхук</button>`;
    }
    return `<div class="card check ${c.ok ? "" : "bad"}">
      <div class="check-head"><span class="dot ${c.ok ? "dot-ok" : "dot-err"}"></span>${esc(CHECK_TITLES[c.name] || c.name)}<span class="ms">${esc(c.ms)} мс</span></div>
      <div class="check-detail">${esc(c.detail)}</div>${extra}</div>`;
  }).join("");
}

function renderOverview(o) {
  serverSkew = new Date(o.now) - Date.now();
  $("#bot-name").textContent = o.bot === "max" ? "MAX-бот" : "Telegram-бот";
  document.title = "Панель управления — " + (o.bot === "max" ? "MAX" : "Telegram");
  $("#admin-name").textContent = o.admin;
  $("#log-write-level").value = o.log_level;
  const a = o.appointments, j = o.jobs, errs = o.log_last_hour;
  const tiles = [
    ["Активные записи", a.active, `подтверждено: ${a.confirmed}`],
    ["Отменено", a.cancelled, "хранятся до очистки"],
    ["Завершено", a.finished, "хранятся до очистки"],
    ["Задания", j.total, j.next ? `ближайшее ${relTime(j.next.run_at)}` : "нет запланированных"],
    ["Ошибки за час", errs.ERROR, `предупреждений: ${errs.WARNING}`, errs.ERROR > 0],
    ["Работает", fmtUptime(o.uptime_s), "с " + fmtTime(o.started_at)],
  ];
  $("#tiles").innerHTML = tiles.map(([label, value, sub, alert]) =>
    `<div class="card tile ${alert ? "alert" : ""}"><div class="label">${esc(label)}</div><div class="value">${esc(value)}</div><div class="sub">${esc(sub)}</div></div>`).join("");
  $("#counters").innerHTML = Object.entries(o.counters).map(([k, v]) =>
    `<tr><td>${esc(COUNTER_TITLES[k] || k)}</td><td>${esc(v)}</td></tr>`).join("");
  const proc = [
    ["Версия", o.version], ["Python", o.python], ["PID", o.pid], ["Уровень журнала", o.log_level],
    ["База данных", `${o.db.path}, ${fmtBytes(o.db.size_bytes)}, схема ${o.db.schema}`],
    ["Заданий на паузе", j.paused], ["Время бота", fmtTime(o.now, true)],
  ];
  $("#process").innerHTML = proc.map(([k, v]) => `<tr><td>${esc(k)}</td><td>${esc(v)}</td></tr>`).join("");
  const badge = $('.tabs [data-tab="logs"] .badge');
  if (errs.ERROR > 0) {
    if (badge) badge.textContent = errs.ERROR;
    else $('.tabs [data-tab="logs"]').insertAdjacentHTML("beforeend", `<span class="badge err">${esc(errs.ERROR)}</span>`);
  } else if (badge) badge.remove();
}

async function loadOverview() {
  const [o, h] = await Promise.allSettled([api("/overview"), api("/health")]);
  if (o.status === "fulfilled") renderOverview(o.value);
  if (h.status === "fulfilled") renderHealth(h.value.checks);
  if (o.status === "rejected" && h.status === "rejected") {
    $("#top-status").innerHTML = `<span class="dot dot-err"></span><span>Бот не отвечает</span>`;
  }
  $("#overview-updated").textContent = "обновлено " + new Date().toLocaleTimeString("ru-RU");
}
loaders.overview = () => loadOverview();

/* ---------- Журнал ---------- */

const logs = {
  after: 0,
  timer: null,
  paused: false,
  active: false,
  source: "",
  maxLines: 3000,

  setActive(on) {
    this.active = on;
    clearTimeout(this.timer);
    if (on && !this.source && !this.paused) this.poll();
  },

  filters() {
    return { level: $("#log-level").value, q: $("#log-q").value.trim() };
  },

  line(r, fresh) {
    const f = this.filters();
    let msg = esc(r.message);
    if (f.q) {
      const re = new RegExp(f.q.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"), "gi");
      msg = msg.replace(re, (m) => `<mark>${m}</mark>`);
    }
    return `<div class="logline ${esc(r.level)}${fresh ? " fresh" : ""}"><span class="t">${esc(r.time)}</span><span class="l">${esc(r.level)}</span><span class="m">${msg}</span></div>`;
  },

  append(rows, fresh) {
    const box = $("#logbox");
    $(".log-empty", box)?.remove();
    box.insertAdjacentHTML("beforeend", rows.map((r) => this.line(r, fresh)).join(""));
    while (box.childElementCount > this.maxLines) box.firstElementChild.remove();
    if ($("#log-follow").checked) box.scrollTop = box.scrollHeight;
  },

  empty(text) {
    $("#logbox").innerHTML = `<div class="log-empty">${esc(text)}</div>`;
  },

  async poll() {
    clearTimeout(this.timer);
    if (!this.active || this.paused || this.source) return;
    try {
      const data = await api("/logs/tail", { params: { after: this.after, ...this.filters() } });
      const first = this.after === 0;
      this.after = data.seq;
      if (data.lines.length) this.append(data.lines, !first);
      else if (first) this.empty("Пока пусто. Новые строки появятся сами.");
      $("#log-status").textContent = `живой хвост · обновляется каждые 2 с · ${new Date().toLocaleTimeString("ru-RU")}`;
    } catch (e) {
      $("#log-status").textContent = "нет связи с ботом, повторю через 5 с";
      this.timer = setTimeout(() => this.poll(), 5000);
      return;
    }
    this.timer = setTimeout(() => this.poll(), 2000);
  },

  restartLive() {
    this.after = 0;
    $("#logbox").innerHTML = "";
    this.poll();
  },

  async loadFile() {
    const f = this.filters();
    $("#log-status").textContent = "читаю файл…";
    try {
      const data = await api("/logs/file", { params: { name: this.source, level: f.level, q: f.q, limit: 2000 } });
      const box = $("#logbox");
      box.innerHTML = data.lines.length
        ? data.lines.map((raw) => {
            const m = raw.match(/^(\S+ \S+) \| (\w+)\s*\| ([\s\S]*)$/);
            return m ? this.line({ time: m[1], level: m[2], message: m[3] }) : `<div class="logline raw"><span class="m">${esc(raw)}</span></div>`;
          }).join("")
        : `<div class="log-empty">Ничего не найдено.</div>`;
      box.scrollTop = box.scrollHeight;
      $("#log-status").textContent = `${data.name}: ${data.lines.length} строк${data.truncated ? " (показаны последние)" : ""}`;
    } catch (e) {
      this.empty(describeError(e));
    }
  },

  async loadFiles() {
    try {
      const { files } = await api("/logs/files");
      const sel = $("#log-source");
      const keep = sel.value;
      sel.innerHTML = `<option value="">Живой хвост</option>` + files.map((f) =>
        `<option value="${esc(f.name)}">${esc(f.name)} · ${fmtBytes(f.size_bytes)} · ${fmtTime(f.modified)}</option>`).join("");
      sel.value = files.some((f) => f.name === keep) ? keep : "";
    } catch { /* список файлов необязателен */ }
  },

  refresh() {
    this.source = $("#log-source").value;
    const dl = $("#log-download");
    dl.hidden = !this.source;
    if (this.source) dl.href = API + "/logs/download?name=" + encodeURIComponent(this.source);
    $("#log-pause").hidden = !!this.source;
    if (this.source) { clearTimeout(this.timer); this.loadFile(); }
    else this.restartLive();
  },

  init() {
    let debounce;
    $("#log-source").addEventListener("change", () => this.refresh());
    $("#log-level").addEventListener("change", () => this.refresh());
    $("#log-q").addEventListener("input", () => { clearTimeout(debounce); debounce = setTimeout(() => this.refresh(), 350); });
    $("#log-pause").addEventListener("click", (ev) => {
      this.paused = !this.paused;
      ev.currentTarget.textContent = this.paused ? "Продолжить" : "Пауза";
      $("#log-status").textContent = this.paused ? "на паузе" : "";
      if (!this.paused) this.poll();
    });
    $("#log-clear").addEventListener("click", () => this.empty("Экран очищен. Новые строки появятся сами."));
    $("#log-write-level").addEventListener("change", async (ev) => {
      const level = ev.currentTarget.value;
      try {
        await api("/logs/level", { method: "POST", body: { level } });
        toast(`Уровень записи: ${level}. После перезапуска — снова INFO.`);
      } catch (e) { toast(describeError(e), true); }
    });
  },
};
loaders.logs = () => logs.loadFiles();

/* ---------- Задания ---------- */

const JOB_KINDS = { reminder_24h: "Напоминание за сутки", reminder_2h: "Напоминание за 2 ч", feedback: "Просьба об отзыве", retention: "Очистка ПДн", other: "Другое" };

async function loadJobs() {
  const table = $("#jobs");
  try {
    const { jobs } = await api("/jobs");
    const head = `<tr><th>Задание</th><th>Тип</th><th>Запись</th><th>Запуск</th><th></th></tr>`;
    table.innerHTML = head + (jobs.length ? jobs.map((j) => `<tr>
      <td><code>${esc(j.id)}</code></td>
      <td>${esc(JOB_KINDS[j.kind] || j.kind)}</td>
      <td>${j.appointment_id ? `<a href="#appointments" data-find="${esc(j.appointment_id)}"><code>${esc(j.appointment_id)}</code></a>` : "—"}</td>
      <td class="nowrap">${j.paused ? `<span class="badge warn">пауза</span>` : `${esc(fmtTime(j.run_at))} <span class="muted small">${esc(relTime(j.run_at))}</span>`}</td>
      <td class="actions">
        <button type="button" class="btn sm" data-job="${esc(j.id)}" data-act="run">Выполнить сейчас</button>
        <button type="button" class="btn sm" data-job="${esc(j.id)}" data-act="${j.paused ? "resume" : "pause"}">${j.paused ? "Возобновить" : "Пауза"}</button>
        <button type="button" class="btn sm danger" data-job="${esc(j.id)}" data-act="delete">Удалить</button>
      </td></tr>`).join("") : `<tr><td colspan="5" class="empty">Заданий нет</td></tr>`);
  } catch (e) {
    table.innerHTML = `<tr><td class="empty">${esc(describeError(e))}</td></tr>`;
  }
}
loaders.jobs = loadJobs;

async function jobAction(button) {
  const id = button.dataset.job, act = button.dataset.act;
  if (act === "delete" && !(await confirmAction("Удалить задание?", `Задание ${id} не выполнится. Напоминания можно пересоздать во вкладке «Записи».`, "Удалить", true))) return;
  if (act === "run" && !(await confirmAction("Выполнить сейчас?", `Задание ${id} выполнится сразу. Если это напоминание — пациент получит сообщение.`, "Выполнить"))) return;
  await withBusy(button, async () => {
    await api(`/jobs/${encodeURIComponent(id)}/${act}`, { method: "POST" });
    toast({ run: "Задание запущено", pause: "Задание на паузе", resume: "Задание возобновлено", delete: "Задание удалено" }[act]);
    setTimeout(loadJobs, act === "run" ? 1200 : 0);
  });
}

/* ---------- Записи ---------- */

const JOB_SHORT = { rem24h: "за сутки", rem2h: "за 2 ч", feedback: "отзыв" };
const STATUS_BADGE = { active: ["активна", "ok"], cancelled: ["отменена", "err"], finished: ["завершена", ""] };

async function loadAppointments() {
  const table = $("#appointments");
  try {
    const data = await api("/appointments", { params: { status: $("#appt-status").value, q: $("#appt-q").value.trim() } });
    const head = `<tr><th>Визит</th><th>Статус</th><th>Филиал · врач · услуга</th><th>Запись 1С · пользователь</th><th>Напоминания</th><th></th></tr>`;
    table.innerHTML = head + (data.items.length ? data.items.map((a) => {
      const [label, cls] = STATUS_BADGE[a.status] || [a.status, ""];
      const confirmed = a.confirmed_at ? `<span class="badge accent">подтверждён</span>` : "";
      const actions = a.status === "active" ? `
        <button type="button" class="btn sm" data-appt="${esc(a.appointment_id)}" data-act="remind24">Напомнить (сутки)</button>
        <button type="button" class="btn sm" data-appt="${esc(a.appointment_id)}" data-act="remind2">Напомнить (2 ч)</button>
        <button type="button" class="btn sm" data-appt="${esc(a.appointment_id)}" data-act="rejobs">Пересоздать</button>
        <button type="button" class="btn sm danger" data-appt="${esc(a.appointment_id)}" data-act="close">Закрыть локально</button>` : `<span class="muted small">закрыта ${esc(fmtTime(a.closed_at))}</span>`;
      return `<tr>
        <td class="nowrap"><strong>${esc(fmtTime(a.visit_at, true))}</strong><div class="muted small">${esc(relTime(a.visit_at))}</div></td>
        <td><span class="badge ${cls}">${esc(label)}</span> ${confirmed}</td>
        <td>${esc(a.branch || "—")}<div class="muted small">${esc(a.doctor_name || "—")}</div><div class="muted small">${esc(a.service_name || "")}</div></td>
        <td><code>${esc(a.appointment_id)}</code><div class="muted small"><code>${esc(a.user_id)}</code> · создана ${esc(fmtTime(a.created_at))}</div></td>
        <td>${a.notify ? (a.jobs.length ? a.jobs.map((j) => `<span class="badge">${esc(JOB_SHORT[j.split("_")[0]] || j)}</span>`).join(" ") : `<span class="muted small">нет заданий</span>`) : `<span class="badge">выключены</span>`}</td>
        <td class="actions"><div class="act">${actions}</div></td></tr>`;
    }).join("") : `<tr><td colspan="6" class="empty">Записей нет</td></tr>`);
    if (data.total > data.items.length) table.insertAdjacentHTML("beforeend", `<tr><td colspan="6" class="empty">Показаны ${data.items.length} из ${data.total}. Уточните поиск.</td></tr>`);
  } catch (e) {
    table.innerHTML = `<tr><td class="empty">${esc(describeError(e))}</td></tr>`;
  }
}
loaders.appointments = loadAppointments;

async function appointmentAction(button) {
  const id = button.dataset.appt, act = button.dataset.act;
  if (act === "remind24" || act === "remind2") {
    const kind = act === "remind24" ? "24h" : "2h";
    if (!(await confirmAction("Отправить напоминание?", `Пациент записи ${id} получит напоминание ${kind === "24h" ? "за сутки" : "за 2 часа"} прямо сейчас.`, "Отправить"))) return;
    return withBusy(button, async () => { await api(`/appointments/${encodeURIComponent(id)}/remind`, { method: "POST", body: { kind } }); toast("Напоминание отправлено"); });
  }
  if (act === "rejobs") {
    return withBusy(button, async () => {
      const r = await api(`/appointments/${encodeURIComponent(id)}/reschedule-reminders`, { method: "POST" });
      toast(`Напоминаний запланировано: ${r.scheduled}`);
      loadAppointments();
    });
  }
  if (act === "close") {
    if (!(await confirmAction("Закрыть запись только в боте?", `Запись ${id} станет отменённой в боте, напоминания удалятся. В 1С ничего не меняется — используйте, если запись уже отменена в 1С, а сигнал не дошёл.`, "Закрыть", true))) return;
    return withBusy(button, async () => {
      await api(`/appointments/${encodeURIComponent(id)}/close`, { method: "POST", body: { status: "cancelled" } });
      toast("Запись закрыта в боте");
      loadAppointments();
    });
  }
}

/* ---------- 1С ---------- */

const ONEC_FIELDS = { ping: [], specialties: [], doctors: ["branch", "date"], services: ["doctor_id"], schedule: ["doctor_id", "branch", "date", "start_date", "end_date"] };

function syncOnecFields() {
  const fields = ONEC_FIELDS[$("#onec-method").value] || [];
  $$("#onec-form [data-param]").forEach((el) => { el.hidden = !fields.includes(el.dataset.param); });
}

function highlightJson(value) {
  return esc(JSON.stringify(value, null, 2))
    .replace(/(&quot;[^&]*?&quot;)(\s*:)/g, '<span class="k">$1</span>$2')
    .replace(/:\s(&quot;.*?&quot;)/g, ': <span class="s">$1</span>')
    .replace(/:\s(-?\d+(?:\.\d+)?)/g, ': <span class="n">$1</span>');
}

async function runOnec(ev) {
  ev.preventDefault();
  const method = $("#onec-method").value;
  const form = $("#onec-form");
  const params = {};
  for (const name of ONEC_FIELDS[method]) params[name] = form.elements[name].value;
  const btn = $("button[type=submit]", form);
  await withBusy(btn, async () => {
    $("#onec-meta").textContent = "запрос…";
    const r = await api("/onec/" + method, { params });
    $("#onec-title").textContent = "GET " + method;
    const ok = r.http_status === 200;
    $("#onec-meta").innerHTML = `<span class="badge ${ok ? "ok" : "err"}">${esc(r.http_status ?? r.error)}</span> <span class="muted">${esc(r.ms)} мс</span>`;
    $("#onec-body").innerHTML = "body" in r ? highlightJson(r.body) : esc(r.error);
    const pick = $("#onec-pick");
    pick.innerHTML = "";
    if (method === "doctors" && Array.isArray(r.body) && r.body.length) {
      pick.className = "pick";
      pick.innerHTML = `<span class="muted small">Подставить врача:</span>` + r.body.slice(0, 40).map((d) =>
        `<button type="button" class="btn sm" data-doctor="${esc(d.id)}">${esc(d.full_name || d.id)}</button>`).join("");
    }
  });
}

/* ---------- Сообщения ---------- */

function renderTelegramHtml(text) {
  return esc(text)
    .replace(/&lt;(\/?)(b|i|u|s|code)&gt;/g, "<$1$2>")
    .replace(/&lt;a href=&quot;(https?:\/\/[^&"]*)&quot;&gt;/g, '<a href="$1" target="_blank" rel="noopener noreferrer">')
    .replace(/&lt;\/a&gt;/g, "</a>");
}

async function loadTemplates() {
  try {
    const data = await api("/templates");
    const sel = $("#msg-recipient");
    sel.innerHTML = data.recipients.length ? data.recipients.map((r) => `<option>${esc(r)}</option>`).join("") : `<option value="">ADMIN_IDS пуст</option>`;
    sel.disabled = !data.recipients.length;
    if (!data.recipients.length) $("#msg-hint").textContent = "Чтобы отправлять шаблоны себе, добавьте свой id мессенджера в ADMIN_IDS в .env и перезапустите бот.";
    $("#templates").innerHTML = data.templates.map((t) => `<div class="card msg-card">
      <div class="row between"><h2>${esc(t.title)}</h2><button type="button" class="btn sm" data-template="${esc(t.key)}" ${data.recipients.length ? "" : "disabled"}>Отправить себе</button></div>
      <div class="bubble">${renderTelegramHtml(t.text)}</div>
      ${t.buttons.length ? `<div class="kb">${t.buttons.map((row) => `<div class="kb-row">${row.map((b) => `<span class="${esc(b.tone)}">${esc(b.text)}</span>`).join("")}</div>`).join("")}</div>` : ""}
    </div>`).join("");
  } catch (e) {
    $("#templates").innerHTML = `<div class="card muted">${esc(describeError(e))}</div>`;
  }
}
loaders.messages = loadTemplates;

/* ---------- Настройки и обслуживание ---------- */

async function loadSettings() {
  try {
    const { settings } = await api("/settings");
    $("#settings").innerHTML = settings.map((s) =>
      `<tr><td>${esc(s.name)}</td><td>${s.secret ? `<span class="badge ${s.value === "не задан" ? "err" : "accent"}">${esc(s.value)}</span>` : esc(s.value || "—")}</td></tr>`).join("");
  } catch (e) {
    $("#settings").innerHTML = `<tr><td>${esc(describeError(e))}</td></tr>`;
  }
}
loaders.settings = loadSettings;

async function runOp(button) {
  const op = button.dataset.op;
  if (op === "webhook") {
    return withBusy(button, async () => {
      const r = await api("/webhook/register", { method: "POST" });
      toast(r.ok ? "Вебхук зарегистрирован" : "Не удалось: " + (r.detail || "ошибка"), !r.ok);
      if (currentTab === "overview") loadOverview();
    });
  }
  if (op === "retention") {
    if (!(await confirmAction("Запустить очистку ПДн?", "Прошедшие активные записи станут завершёнными, закрытые старше срока хранения удалятся.", "Запустить"))) return;
    return withBusy(button, async () => {
      const r = await api("/maintenance/retention", { method: "POST" });
      toast(`Завершено: ${r.finished}, удалено записей: ${r.deleted}, событий: ${r.events}`);
    });
  }
  if (op === "restart") {
    if (!(await confirmAction("Перезапустить бот?", "Бот остановится на 5–10 секунд. Запросы пациентов в это время не пройдут.", "Перезапустить", true))) return;
    return withBusy(button, async () => {
      await api("/maintenance/restart", { method: "POST" });
      toast("Бот перезапускается…");
      waitForRestart();
    });
  }
}

async function waitForRestart() {
  $("#top-status").innerHTML = `<span class="dot dot-idle"></span><span>перезапуск…</span>`;
  await new Promise((r) => setTimeout(r, 3000));
  for (let i = 0; i < 30; i++) {
    try { await api("/overview"); toast("Бот снова работает"); loadOverview(); return; }
    catch { await new Promise((r) => setTimeout(r, 2000)); }
  }
  toast("Бот не поднялся за минуту. Если он запущен не службой, запустите его вручную.", true);
}

/* ---------- Старт ---------- */

document.addEventListener("click", (ev) => {
  const t = ev.target.closest("button, a");
  if (!t) return;
  if (t.dataset.job) jobAction(t);
  else if (t.dataset.appt) appointmentAction(t);
  else if (t.dataset.op) runOp(t);
  else if (t.dataset.template) {
    const chat = $("#msg-recipient").value;
    withBusy(t, async () => { await api(`/templates/${t.dataset.template}/send`, { method: "POST", body: { chat_id: chat } }); toast("Отправлено в " + chat); });
  } else if (t.dataset.doctor) {
    $("#onec-form").elements.doctor_id.value = t.dataset.doctor;
    $("#onec-method").value = "schedule";
    syncOnecFields();
    toast("doctor_id подставлен, метод — schedule");
  } else if (t.dataset.find) {
    ev.preventDefault();
    $("#appt-status").value = "all";
    $("#appt-q").value = t.dataset.find;
    showTab("appointments");
  }
});

document.addEventListener("DOMContentLoaded", () => {
  initTheme();
  initTabs();
  logs.init();
  $("#overview-refresh").addEventListener("click", loadOverview);
  $("#jobs-refresh").addEventListener("click", loadJobs);
  $("#appt-refresh").addEventListener("click", loadAppointments);
  $("#appt-status").addEventListener("change", loadAppointments);
  $("#appt-q").addEventListener("keydown", (e) => { if (e.key === "Enter") loadAppointments(); });
  $("#onec-method").addEventListener("change", syncOnecFields);
  $("#onec-form").addEventListener("submit", runOnec);
  syncOnecFields();
  showTab(location.hash.slice(1) || "overview");
  if (currentTab !== "overview") loadOverview();
  setInterval(() => { if (currentTab === "overview" && !document.hidden) loadOverview(); }, 15000);
});
