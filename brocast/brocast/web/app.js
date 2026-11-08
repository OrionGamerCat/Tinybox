/* brocast listener GUI.
 * Page contents come from the air and are untrusted: everything is put into
 * the DOM with textContent / createElement only – never parsed as HTML.
 * Every write sends X-Brocast-Client: 1 (CSRF barrier, see webserver.py).
 */
"use strict";

const API = "/api/v1";
const POLL_MS = 15000;

const state = {
  mode: "cat",            // "cat" | "st"  (left pane)
  cat: null,              // selected rubric key
  station: null,          // selected station call
  sub: "*",               // second filter (station in cat mode, rubric in station mode)
  filter: "all",          // all | unread | fav
  q: "",                  // full-text search
  selected: null,         // {org, id} of the open page
  screen: "pages",        // pages | settings | status
  raw: false,
  view: "flow",           // page view: flow | teletext
  graphic: true,          // weather pages and tables: graphic view (false = plain text/table)
  dxSort: "abc",          // DX table: abc (alphabetical) | rel (relevance)
  rxFilter: null,         // receive log: {org, id} of one page, or null = all
  rxForeign: false,       // receive log: also show non-brocast frames
  settings: {},
  status: {},
  knownAlerts: null,      // Set of "org/id" of unread alerts already seen
  alertPage: null,
};

/* ---------- helpers ---------- */

const $ = (id) => document.getElementById(id);

function el(tag, cls, text) {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text !== undefined && text !== null) e.textContent = String(text);
  return e;
}

/* Text from the air with clickable web links. Only http(s) and www. are linked;
 * the visible text is always the full address, so a link cannot pretend to go
 * somewhere else. Opens in a new tab without referrer. */
const URL_RE = /\b(?:https?:\/\/|www\.)[^\s<>"']+/gi;

function linkified(tag, cls, text) {
  const e = el(tag, cls);
  const s = String(text == null ? "" : text);
  let last = 0;
  for (const m of s.matchAll(URL_RE)) {
    let url = m[0].replace(/[.,;:!?)\]]+$/, "");          // no trailing punctuation
    const start = m.index;
    e.append(s.slice(last, start));
    let href = url.toLowerCase().startsWith("www.") ? "http://" + url : url;
    let ok = false;
    try { ok = ["http:", "https:"].includes(new URL(href).protocol); } catch (err) { ok = false; }
    if (ok) {
      const a = el("a", "extlink", url);
      a.href = href;
      a.target = "_blank";
      a.rel = "noopener noreferrer";
      a.title = "Öffnet " + href + " in einem neuen Tab";
      e.append(a);
    } else {
      e.append(url);
    }
    last = start + url.length;
  }
  e.append(s.slice(last));
  return e;
}

function svg(tag, attrs) {
  const e = document.createElementNS("http://www.w3.org/2000/svg", tag);
  for (const [k, v] of Object.entries(attrs || {})) e.setAttribute(k, v);
  return e;
}

async function api(method, path, body) {
  const opts = { method, headers: { "X-Brocast-Client": "1" } };
  if (body !== undefined) {
    opts.headers["Content-Type"] = "application/json";
    opts.body = JSON.stringify(body);
  }
  const res = await fetch(API + path, opts);
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const err = new Error(data.error || ("HTTP " + res.status));
    err.status = res.status;
    throw err;
  }
  return data;
}

function qs(params) {
  const p = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) if (v !== null && v !== undefined && v !== "" && v !== false) p.set(k, v === true ? "1" : v);
  const s = p.toString();
  return s ? "?" + s : "";
}

let toastTimer = null;
function toast(text, isError) {
  const t = $("toast");
  t.textContent = text;
  t.className = "toast" + (isError ? " err" : "");
  t.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { t.hidden = true; }, 4000);
}

function num(v) {
  if (typeof v !== "number") return v === null || v === undefined ? "" : String(v);
  return v.toLocaleString("de-AT", { maximumFractionDigits: 3, useGrouping: false });
}

function fmtTime(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  const now = new Date();
  const hm = d.toLocaleTimeString("de-AT", { hour: "2-digit", minute: "2-digit" });
  if (d.toDateString() === now.toDateString()) return hm;
  return d.toLocaleDateString("de-AT", { day: "2-digit", month: "2-digit" }) + " " + hm;
}

function ttClock() {
  const d = new Date();
  const wd = d.toLocaleDateString("de-AT", { weekday: "short" }).replace(".", "").toUpperCase();
  const date = d.toLocaleDateString("de-AT", { day: "2-digit", month: "2-digit", year: "2-digit" });
  return `${wd} ${date} ${d.toLocaleTimeString("de-AT")}`;
}

function key(p) { return p.org + "/" + p.id; }

/* ---------- header, alert banner ---------- */

async function refreshStatus() {
  try {
    state.status = await api("GET", "/status");
  } catch (e) {
    $("hdr-kiss").textContent = "brocastd nicht erreichbar";
    $("hdr-dot").className = "dot bad";
    return;
  }
  const s = state.status;
  if (s.mode === "station") $("hdr-call").replaceChildren(s.callsign, el("span", "m-hide", " · Station"));
  else $("hdr-call").textContent = "Listener";
  $("hdr-dot").className = "dot " + (s.kiss_connected ? "ok" : "bad");
  // phone: "Direwolf" + green dot when connected; "getrennt" always spelled out
  $("hdr-kiss").replaceChildren("Direwolf",
    s.kiss_connected ? el("span", "m-hide", " verbunden") : " getrennt");
  $("hdr-unread").textContent = s.unread;
  $("hdr-stations").textContent = s.stations;

  const dict = s.dictionary || {};
  const bar = $("dictbar");
  $("dictbar-install").hidden = !dict.ready;
  $("dictbar-import").hidden = !!dict.ready;
  if (dict.ready) {                     // complete over the air, waiting for the user's OK
    $("dictbar-text").textContent = `Dictionary v${dict.ready.version} über Funk von ${dict.ready.station} ` +
      `vollständig empfangen und geprüft (installiert: v${dict.local}).`;
    bar.hidden = false;
  } else if (dict.radio && state.dictHidden !== dict.radio.version) {
    $("dictbar-text").textContent = `Dictionary v${dict.radio.version} wird über Funk empfangen ` +
      `(von ${dict.radio.station}): ${dict.radio.have} von ${dict.radio.total} Teilen. ` +
      "Fehlende Teile kommen mit der nächsten Aussendung.";
    bar.hidden = false;
  } else if (dict.outdated && state.dictHidden !== dict.newest_heard) {
    const src = dict.source || {};
    const ways = [];
    if (src.air_hours)                  // the station sends the dictionary itself over the air
      ways.push(`Kommt automatisch über Funk: ${src.station} sendet es alle ${src.air_hours} h, ` +
                "der Empfang läuft im Hintergrund, kein Rufzeichen nötig.");
    if (src.text) ways.push(`${src.air_hours ? "Sofort" : "Bezug"}: ${src.text}, dann hier „Importieren“.`);
    $("dictbar-text").textContent = ways.length
      ? `Dictionary v${dict.newest_heard} erhältlich (installiert: v${dict.local}). ${ways.join(" ")}`
      : `Dictionary veraltet: ${dict.heard_from} sendet mit Version ${dict.newest_heard}, ` +
        `hier ist Version ${dict.local} installiert. Seiten werden angezeigt, neue Felder aber nur roh.`;
    bar.hidden = false;
  } else bar.hidden = true;
}

async function refreshAlerts() {
  const pages = await api("GET", "/pages" + qs({ unread: true }));
  const alerts = pages.filter(p => p.alert);
  const banner = $("alert");
  if (!alerts.length) { banner.hidden = true; state.alertPage = null; }
  else {
    const a = alerts[0];
    state.alertPage = a;
    $("alert-text").textContent = `⚠ Warnung: ${a.ti || "Seite " + a.id} (${a.org}, Seite ${a.id})` +
      (alerts.length > 1 ? ` – und ${alerts.length - 1} weitere` : "");
    banner.hidden = false;
  }
  const keys = new Set(alerts.map(key));
  if (state.knownAlerts && state.settings.alert_sound && [...keys].some(k => !state.knownAlerts.has(k))) beep();
  state.knownAlerts = keys;
}

function beep() {
  try {
    const ctx = new (window.AudioContext || window.webkitAudioContext)();
    const o = ctx.createOscillator(), g = ctx.createGain();
    o.frequency.value = 880; g.gain.value = 0.15;
    o.connect(g); g.connect(ctx.destination);
    o.start(); o.stop(ctx.currentTime + 0.35);
  } catch (e) { /* no audio – ignore */ }
}

/* ---------- phone: one pane at a time ----------
 * body[data-pane] = nav | list | view; app.css shows only that pane below 700 px.
 * Every step goes into the browser history, so the iPhone back gesture works too.
 * On the desktop all panes are visible and data-pane is ignored. */

const PHONE = window.matchMedia("(max-width: 700px)");

function setPane(pane, push = true) {
  const cur = document.body.dataset.pane;
  document.body.dataset.pane = pane;
  if (push && PHONE.matches && cur !== pane) history.pushState({ pane, prev: cur }, "");
  updateBack();
}

function goBack(fallback) {
  const h = history.state;
  if (PHONE.matches && h && h.prev) history.back();
  else setPane(fallback, false);
}

function paneLabel(pane) {
  if (pane === "list") return $("list-title").textContent;
  if (pane === "view") return "Zurück";
  return state.mode === "cat" ? "Rubriken" : "Stationen";
}

function updateBack() {
  const h = history.state || {};
  const pane = document.body.dataset.pane;
  $("back-list").textContent = "‹ " + paneLabel(pane === "list" && h.prev ? h.prev : "nav");
  $("back-view").textContent = "‹ " + paneLabel(pane === "view" && h.prev ? h.prev : (state.screen === "pages" ? "list" : "nav"));
  // bottom bar: highlight what is open
  $("nav-fav").classList.toggle("mon", pane === "list" && state.filter === "fav" && !state.cat && !state.station);
  $("nav-rxlog").classList.toggle("mon", pane === "view" && state.screen === "rxlog");
  $("nav-status").classList.toggle("mon", pane === "view" && state.screen === "status");
  $("nav-tx").classList.toggle("mon", pane === "view" && state.screen === "tx");
}

/* ---------- left pane ---------- */

function countNode(unread, total) {
  const c = el("span", "count");
  if (unread) c.append(el("span", "u", unread + " neu"));
  c.append(String(total));
  c.title = `${total} ${total === 1 ? "Seite" : "Seiten"}, davon ${unread} ungelesen`;
  return c;
}

async function renderNav() {
  const nav = $("navlist");
  const items = [];
  if (state.mode === "cat") {
    const cats = await api("GET", "/categories");
    for (const c of cats) {
      const b = el("button", "nav" + (state.screen === "pages" && state.cat === c.key && !state.q ? " on" : ""));
      b.type = "button";
      const n = el("span", "name", c.name);
      if (c.custom) n.append(el("span", "own", "eigene"));
      if (c.withdrawn) n.append(el("span", "off", "zurückgezogen"));
      if (c.desc) b.title = c.desc;                 // from the station's rubric index
      b.append(n, countNode(c.unread, c.total));
      b.onclick = () => select({ cat: c.key, station: null });
      items.push(b);
    }
    if (!cats.length) items.push(el("div", "hint", "Noch keine Seiten empfangen."));
  } else {
    const stations = await api("GET", "/stations");
    for (const s of stations) {
      const b = el("button", "nav" + (state.screen === "pages" && state.station === s.call && !state.q ? " on" : ""));
      b.type = "button";
      const n = el("span", "name");
      n.append(el("span", "mono", s.call));
      if (!s.subscribed) n.append(el("span", "off", "abgewählt"));
      b.append(n, countNode(s.unread, s.pages));
      b.onclick = () => select({ station: s.call, cat: null });
      items.push(b);
    }
    if (stations.length) {
      items.push(el("div", "navhead", "zuletzt gehört"));
      for (const s of stations) items.push(el("div", "heard", `${s.call}  ${fmtTime(s.last_heard)} · ${s.frames} Fr.`));
    } else items.push(el("div", "hint", "Noch keine Station gehört."));
  }
  nav.replaceChildren(...items);
  const favs = await api("GET", "/pages" + qs({ favorite: true }));
  $("fav-count").textContent = favs.length || "";
}

function select(sel) {
  state.cat = sel.cat !== undefined ? sel.cat : state.cat;
  state.station = sel.station !== undefined ? sel.station : state.station;
  state.sub = "*";
  state.q = "";
  $("search").value = "";
  state.screen = "pages";
  if (state.filter === "fav" && (state.cat || state.station)) setFilter("all", false);
  setPane("list");
  refreshLists();
  if (!state.selected) renderEmpty();
}

/* ---------- middle pane ---------- */

function listParams() {
  const p = { cat: state.cat, station: state.station, q: state.q,
              unread: state.filter === "unread", favorite: state.filter === "fav" };
  if (state.sub !== "*") {
    if (state.mode === "cat") p.station = state.sub; else p.cat = state.sub;
  }
  return p;
}

async function renderSubFilter() {
  const s = $("sub-filter");
  const opts = [];
  if (state.mode === "cat" && state.cat) {
    opts.push(new Option("Alle Stationen", "*"));
    for (const st of await api("GET", "/stations" + qs({ cat: state.cat }))) opts.push(new Option(st.call, st.call));
  } else if (state.mode === "st" && state.station) {
    opts.push(new Option("Alle Rubriken", "*"));
    for (const c of await api("GET", "/categories" + qs({ station: state.station }))) opts.push(new Option(c.name, c.key));
  }
  s.replaceChildren(...opts);
  s.hidden = !opts.length;
  if (opts.some(o => o.value === state.sub)) s.value = state.sub; else state.sub = "*";
}

async function renderList() {
  const pages = await api("GET", "/pages" + qs(listParams()));
  let title = "Alle Seiten";
  if (state.q) title = `Suche „${state.q}“`;
  else if (state.cat) title = (await catName(state.cat));
  else if (state.station) title = state.station;
  else if (state.filter === "fav") title = "Gemerkt";
  if (state.filter === "unread" && title === "Alle Seiten") title = "Ungelesene Seiten";
  $("list-title").textContent = title;
  // Seitenzahl ohne den Filter Alle/Ungelesen/Gemerkt, damit klar ist, was der Filter ausblendet
  const all = state.filter === "all" ? pages
    : await api("GET", "/pages" + qs({ ...listParams(), unread: false, favorite: false }));
  const unread = all.filter(p => p.status === "unread").length;
  const n = (k) => `${k} ${k === 1 ? "Seite" : "Seiten"}`;
  $("list-sub").textContent =
    state.filter === "unread" ? `${unread} von ${n(all.length)} ungelesen`
    : state.filter === "fav" ? `${pages.length} von ${n(all.length)} gemerkt`
    : `${n(pages.length)} · ${unread} ungelesen`;

  const rows = pages.map(p => {
    const sel = state.selected && state.selected.org === p.org && state.selected.id === p.id;
    const r = el("div", "row" + (p.status === "unread" ? " unread" : "") + (sel ? " on" : ""));
    r.tabIndex = 0;
    const ti = el("div", "ti");
    if (p.alert) ti.append(el("span", "tag alarm", "Warnung"), " ");
    ti.append(p.ti || p.typ_name);
    r.append(ti, el("div", "time", fmtTime(p.t)));
    const meta = el("div", "meta");
    meta.append(el("span", "mono", p.org));
    if (p.updated) meta.append(el("span", "tag upd", "aktualisiert"));
    if (p.sub_total > 1) meta.append(el("span", "tag part", p.sub_present < p.sub_total ? `${p.sub_present}/${p.sub_total} Teile` : `${p.sub_total} Teile`));
    if (p.expired) meta.append(el("span", "tag old", "abgelaufen"));
    if (p.favorite) meta.append(el("span", "star", "★"));
    r.append(meta);
    const open = () => openPage(p.org, p.id);
    r.onclick = open;
    r.onkeydown = (e) => { if (e.key === "Enter") open(); };
    return r;
  });
  $("rows").replaceChildren(...(rows.length ? rows : [emptyList(all.length)]));
  updateBack();
}

function emptyList(total) {
  if (state.filter === "all" || !total) return el("div", "empty", state.q ? "Nichts gefunden." : "Keine Seiten.");
  const e = el("div", "empty", state.filter === "unread"
    ? `Keine ungelesenen Seiten – ${total} ${total === 1 ? "Seite ist" : "Seiten sind"} schon gelesen.`
    : "Hier ist keine Seite gemerkt.");
  const b = el("button", "btn", "Alle anzeigen");
  b.type = "button";
  b.onclick = () => setFilter("all");
  e.append(el("br"), b);
  return e;
}

let rubricCache = null;
async function catName(k) {
  if (!rubricCache) rubricCache = await api("GET", "/rubrics");
  const r = rubricCache.find(r => r.key === k);
  if (r) return r.name;
  rubricCache = null;
  return k.startsWith("x:") ? k.slice(2) : k;
}

function setFilter(f, reload = true) {
  state.filter = f;
  document.querySelectorAll("[data-f]").forEach(b => b.classList.toggle("on", b.dataset.f === f));
  if (reload) refreshLists();
}

async function refreshLists() {
  try {
    await renderNav();
    await renderSubFilter();
    await renderList();
  } catch (e) {
    toast("Fehler beim Laden: " + e.message, true);
  }
}

/* ---------- page view ---------- */

function renderEmpty() {
  $("view").replaceChildren(el("div", "empty", "Rubrik und Seite wählen."));
}

async function openPage(org, id) {
  let page;
  try {
    page = await api("GET", `/pages/${encodeURIComponent(org)}/${id}` + qs({ raw: state.raw }));
  } catch (e) {
    toast(e.status === 404 ? `Seite ${id} von ${org} ist (noch) nicht empfangen.` : e.message, true);
    return;
  }
  state.selected = { org, id };
  state.screen = "pages";
  renderPage(page);
  setPane("view");
  refreshLists();
  refreshStatus();
  refreshAlerts().catch(() => {});
}

function metaItem(label, value) {
  const s = el("span");
  s.append(label + " ", el("b", null, value));
  return s;
}

function renderPage(p) {
  const v = $("view");
  const tt = el("div", "tt");
  tt.append(el("span", "c", p.org), el("span", "y", "S." + p.id), el("span", null, "brocast"),
            el("span", "grow"), el("span", "y", ttClock()));
  const w = el("div", "pagewrap");
  w.append(el("h1", "pagetitle", p.ti || `${p.typ_name} – Seite ${p.id}`));

  const m = el("div", "pmeta");
  m.append(metaItem("Station", p.org), metaItem("Rubrik", p.cats.map(c => c.name).join(", ")),
           metaItem("Typ", p.typ_name), metaItem("Stand", fmtTime(p.t)), metaItem("Revision", p.rev));
  if (p.exp_min) {
    const until = new Date(new Date(p.t).getTime() + p.exp_min * 60000);
    m.append(metaItem(p.expired ? "abgelaufen seit" : "gültig bis", fmtTime(until.toISOString())));
  }
  if (p.pri && p.pri !== "routine") m.append(metaItem("Priorität", p.pri_name));
  if (p.flags && p.flags.length) m.append(metaItem("Kennzeichen", p.flags.join(", ")));
  if (p.to) m.append(metaItem("An", Array.isArray(p.to) ? p.to.join(", ") : p.to));
  if (p.area) m.append(metaItem("Gebiet", p.area));
  if (Array.isArray(p.pos) && p.pos.length >= 2) m.append(metaItem("Ort", posText(p.pos)));
  if (p.airtime_s) m.append(metaItem("Sendezeit ca.", `${num(p.airtime_s)} s`));
  if (p.src) m.append(metaItem("Quelle", Array.isArray(p.src) ? p.src.join(", ") : p.src));
  w.append(m);

  const a = el("div", "actions");
  const fav = el("button", "btn sm", p.favorite ? "★ Gemerkt" : "☆ Merken");
  fav.onclick = () => action("POST", `/pages/${encodeURIComponent(p.org)}/${p.id}/favorite`, { favorite: !p.favorite }, p);
  const unr = el("button", "btn sm", "Als ungelesen markieren");
  unr.onclick = async () => {
    await action("POST", `/pages/${encodeURIComponent(p.org)}/${p.id}/read`, { read: false }, null);
    toast("Als ungelesen markiert.");
  };
  const raw = el("button", "btn sm" + (state.raw ? " on" : ""), "Rohansicht");
  raw.onclick = () => { state.raw = !state.raw; openPage(p.org, p.id); };
  // graphic/plain switch, only where the page has a graphic view (weather tiles, weather grid)
  const buttons = [fav, unr];
  if (hasGraphic(p)) {
    const gr = el("button", "btn sm" + (state.graphic ? " on" : ""), state.graphic ? "Grafisch" : "Text");
    gr.title = state.graphic ? "Umschalten auf reinen Text" : "Umschalten auf die grafische Darstellung";
    gr.onclick = () => { state.graphic = !state.graphic; saveGraphic(state.graphic); renderPage(p); };
    buttons.push(gr);
  }
  buttons.push(raw);
  const own = state.status.mode === "station" && p.org === state.status.callsign;
  const del = el("button", "btn sm danger", own ? "Nicht mehr senden" : "Löschen");
  del.onclick = async () => {
    if (own) {                            // our own page: off the air, not only out of the list
      if (!await takeOffAir(p.id, p.ti)) return;
    } else if (!confirm(`Seite ${p.id} von ${p.org} löschen?\nSie kommt erst mit einer neuen Revision wieder.`)) return;
    await action("DELETE", `/pages/${encodeURIComponent(p.org)}/${p.id}`, undefined, null);
    state.selected = null;
    renderEmpty();
  };
  const hist = el("button", "btn sm", "Empfangslog");
  hist.onclick = () => renderRxlog({ org: p.org, id: p.id }).catch(e => toast(e.message, true));
  for (const b of [...buttons, hist, del]) b.type = "button";
  a.append(...buttons, hist, el("span", "grow"), del);
  w.append(a);

  const holder = el("div");
  holder.replaceChildren(...viewBar(p), renderContent(p));
  w.append(holder);
  if (state.raw && p.raw) w.append(rawView(p.raw));
  v.replaceChildren(tt, w);
  v.scrollTop = 0;
}

/* A page can be shown in two ways (remembered in this browser):
 *   flow     – one continuous text in the normal page layout
 *   teletext – a teletext screen: pixel font on black, whole page
 */
const VIEWS = [["flow", "Fließtext"], ["teletext", "Teletext"]];

function loadView() {
  let view = "flow";
  try { view = localStorage.getItem("brocast.view") || "flow"; } catch (e) { /* private mode */ }
  return VIEWS.some(([key]) => key === view) ? view : "flow";   // e.g. the dropped "parts"
}

function saveView(view) {
  try { localStorage.setItem("brocast.view", view); } catch (e) { /* private mode */ }
}

function loadGraphic() {
  try { return localStorage.getItem("brocast.graphic") !== "0"; } catch (e) { return true; }
}

function saveGraphic(on) {
  try { localStorage.setItem("brocast.graphic", on ? "1" : "0"); } catch (e) { /* private mode */ }
}

function hasGraphic(p) {
  if (state.view === "teletext") return false;            // the teletext screen is always text
  return (p.typ === "wx" && Array.isArray(p.data) && p.data.length > 0)
    || (p.typ === "dxsum" && dxData(p) !== null)
    || p.blocks.some(b => b.k === "table" && wxgCols(b) !== null);
}

/* The bar above the page: the view switch. Both views show the whole page
 * (all subpages below one another) - there is no turning of subpages any more. */
function viewBar(p) {
  const bar = el("div", "subnav");

  const views = el("div", "segment");
  for (const [key, label] of VIEWS) {
    const b = el("button", state.view === key ? "on" : "", label);
    b.type = "button";
    b.onclick = () => { state.view = key; saveView(key); renderPage(p); };   // the buttons change too
    views.append(b);
  }
  bar.append(el("span", "grow"), el("span", "seglabel", "Ansicht"), views);
  return [bar];
}

/* Head of the teletext screen: the brocast wordmark (pixel graphic, as on the
 * teletext title pages), then rubric, page number and title - so the screen is
 * readable on its own. */
function ttHead(p) {
  const logo = el("img", "ttlogo");
  logo.src = "/brocast-logo.svg";
  logo.alt = "brocast";
  const head = el("div", "tthead");
  const cat = p.cats && p.cats.length ? p.cats.map(c => c.name).join(" ") : p.typ_name;
  head.append(el("span", "cat", cat), el("span", "grow"),
              el("span", "pg", `${p.org} S.${p.id}`));
  return [logo, head];
}

function renderContent(p) {
  const teletext = state.view === "teletext";
  const c = el("div", teletext ? "content ttscreen" : "content");
  if (p.dict_newer) {
    const local = state.status.dictionary ? state.status.dictionary.local : "?";
    c.append(el("div", "note warn", `Diese Seite verwendet Dictionary-Version ${p.dv}, installiert ist Version ${local}. ` +
      "Unbekannte Felder werden roh angezeigt."));
  }
  const showFirst = true;                               // whole page in both views
  if (teletext) c.append(...ttHead(p), el("div", "ttitle", p.ti || `${p.typ_name} – Seite ${p.id}`));
  if (showFirst && p.txt) c.append(linkified("p", null, p.txt));
  let used = new Set();                                 // blocks already shown by a special view
  if (showFirst && !teletext && state.graphic && p.typ === "wx" && p.data && p.data.length) {
    const wx = weatherView(p);
    c.append(wx.node);
    used = wx.used;
  } else if (p.typ === "dxsum" && dxData(p) !== null) {
    c.append(dxSummaryView(p, !teletext && state.graphic));
  } else if (showFirst && p.data && p.data.length) {
    const cards = el("div", "cards");
    for (const d of p.data) cards.append(card(d.label, d.value, d.unit));
    c.append(cards);
  }
  // teletext: no weather grid either (no column semantics -> the plain table)
  const semantics = teletext ? null : tableSemantics(p.blocks);
  let blocks = p.blocks;
  if (used.size) blocks = blocks.filter(b => !used.has(b));
  renderBlocks(c, blocks, p.sub_total, semantics, p);
  if (Array.isArray(p.lnk) && p.lnk.length && showFirst) {
    c.append(el("h4", null, "Verweise"));
    for (const ref of p.lnk) c.append(linkNode(null, ref));
  }
  return c;
}

async function action(method, path, body, page) {
  try {
    const res = await api(method, path, body);
    if (page) { Object.assign(page, res); renderPage(page); }
    refreshLists();
    refreshStatus();
  } catch (e) {
    toast(e.message, true);
  }
}

function posText(pos) {
  const [lat, lon] = pos;
  return `${Math.abs(lat).toFixed(5)}° ${lat >= 0 ? "N" : "S"}, ${Math.abs(lon).toFixed(5)}° ${lon >= 0 ? "E" : "W"}`;
}

function scaled(b) {
  if (typeof b.v === "number" && typeof b.sc === "number") return b.v * Math.pow(10, b.sc);
  return b.v;
}

function card(label, value, unit, stateName) {
  const c = el("div", "card" + (stateName === "warn" ? " warn" : stateName === "alarm" ? " alarm" : ""));
  c.append(el("div", "l", label));
  const v = el("div", "v", num(value));
  if (unit) v.append(el("small", null, unit));
  c.append(v);
  return c;
}

function linkNode(text, ref) {
  const lk = el("button", "link");
  lk.type = "button";
  const org = Array.isArray(ref) ? ref[0] : "", id = Array.isArray(ref) ? ref[1] : "";
  lk.append("→ " + (text || `Seite ${id}`), el("span", "mono", `${org} S.${id}`));
  lk.onclick = () => openPage(org, id);
  return lk;
}

/* hdr and n of a table block: its own, or inherited from the table block with
 * hdr that it continues (table blocks directly following each other). */
function tableSemantics(blocks) {
  const sem = new Map();
  let current = null;
  for (const b of blocks) {
    if (b.k !== "table") { current = null; continue; }
    if (b.hdr) current = { cols: wxgCols(b), hdr: b.hdr };
    if (current) sem.set(b, current);
  }
  return sem;
}

function scaledRows(b) {
  const sc = typeof b.sc === "number" ? Math.pow(10, b.sc) : 1;
  return (b.rows || []).map(r => (Array.isArray(r) ? r : [r]).map(x => typeof x === "number" ? x * sc : x));
}

/* A picture (brocast/mosaic.py) is plain text made of mosaic characters: the
 * sextants U+1FB00…U+1FB3B plus space, half and full block. Nothing in the page
 * says "picture" – the characters do, and the pixel font draws them edge to edge. */
function isMosaic(text) {
  let any = false;
  for (const ch of String(text || "")) {
    const cp = ch.codePointAt(0);
    if (cp === 10 || cp === 32) continue;                       // newline, space
    if (cp === 0x2588 || cp === 0x258C || cp === 0x2590 || (cp >= 0x1FB00 && cp <= 0x1FB3B)) {
      any = true;
      continue;
    }
    return false;
  }
  return any;
}

function renderBlocks(c, blocks, total, semantics, page) {
  let cards = null, lastTable = null, lastGrid = null, lastMosaic = null;
  for (const b of blocks) {
    if (b.k === "value") {
      if (!cards) { cards = el("div", "cards"); c.append(cards); }
      cards.append(card(b.n || "", scaled(b), b.unit, b.st));
      continue;
    }
    cards = null;
    // picture: mosaic blocks that follow each other are one picture (a long
    // picture is sent in several blocks so each one fits into a frame)
    if (b.k === "pre" && isMosaic(b.x)) {
      lastTable = null;
      lastGrid = null;
      if (lastMosaic) {
        lastMosaic.append("\n" + b.x);
        continue;
      }
      lastMosaic = el("pre", "mosaic", b.x);
      c.append(lastMosaic);
      continue;
    }
    lastMosaic = null;
    // a table with column semantics (n) is drawn as a weather grid in graphic mode
    const sem = b.k === "table" && semantics ? semantics.get(b) : null;
    if (sem && sem.cols && state.graphic) {
      lastTable = null;
      // first column "hour": a forecast (meteogram), otherwise a station grid
      const draw = rows => wxfIsForecast(sem.cols) ? wxForecast(rows, sem.cols, sem.hdr, page)
                                                   : wxGrid(rows, sem.cols, sem.hdr, true);
      if (!b.hdr && lastGrid) {                                  // continuation: redraw with all rows
        lastGrid.rows.push(...scaledRows(b));
        lastGrid.node.replaceChildren(draw(lastGrid.rows));
        continue;
      }
      const node = el("div");
      lastGrid = { rows: scaledRows(b), node };
      node.append(draw(lastGrid.rows));
      c.append(node);
      continue;
    }
    lastGrid = null;
    // a table block without its own header right after a table continues it
    // (long tables are sent in small blocks so each one fits into a frame)
    if (b.k === "table" && !b.hdr && lastTable) {
      tableRows(lastTable, b);
      continue;
    }
    lastTable = null;
    switch (b.k) {
      case "heading": c.append(el(b.v === 2 || b.v === 3 ? "h4" : "h3", null, b.x || "")); break;
      case "para": c.append(linkified("p", null, b.x || "")); break;
      case "list": {
        const ul = el("ul");
        for (const r of b.rows || []) ul.append(linkified("li", null, Array.isArray(r) ? r.join(" · ") : r));
        c.append(ul);
        break;
      }
      case "table": lastTable = table(b); c.append(lastTable); break;
      case "series": c.append(series(b)); break;
      case "link": c.append(linkNode(b.x, b.href)); break;
      case "note": c.append(linkified("div", "note" + (b.st === "warn" ? " warn" : b.st === "alarm" ? " alarm" : ""), b.x || "")); break;
      case "pre": c.append(el("pre", null, b.x || "")); break;
      case "mappoint": c.append(el("p", null, `Ort: ${b.x ? b.x + " – " : ""}${Array.isArray(b.pos) ? posText(b.pos) : ""}`)); break;
      case "sep": c.append(el("hr")); break;
      case "missing": c.append(el("div", "missing", `Teil ${b.sub}/${total} noch nicht empfangen – wird in der nächsten Runde ergänzt.`)); break;
      default: c.append(el("pre", null, JSON.stringify(b)));
    }
  }
}

function table(b) {
  const t = el("table", "tbl");
  if (Array.isArray(b.hdr) && b.hdr.length) {
    const tr = el("tr");
    for (const h of b.hdr) tr.append(el("th", null, h));
    t.append(tr);
  }
  tableRows(t, b);
  return t;
}

function tableRows(t, b) {
  const sc = typeof b.sc === "number" ? Math.pow(10, b.sc) : 1;   // scales every number cell (like series)
  const width = t.rows.length ? t.rows[0].cells.length : 0;
  for (const row of b.rows || []) {
    const tr = el("tr");
    if (Array.isArray(row) && row.length === 1 && typeof row[0] === "string" && width > 1) {
      const th = el("th", "grp", row[0]);                        // group heading inside the table
      th.colSpan = width;
      tr.append(th);
    } else {
      for (const cell of Array.isArray(row) ? row : [row]) tr.append(typeof cell === "string" ? linkified("td", null, cell) : el("td", null, typeof cell === "number" ? num(cell * sc) : num(cell)));
    }
    t.append(tr);
  }
}

function series(b) {
  const box = el("div", "series");
  const vals = (Array.isArray(b.v) ? b.v : []).filter(x => typeof x === "number")
    .map(x => typeof b.sc === "number" ? x * Math.pow(10, b.sc) : x);
  const l = el("div", "l");
  const unit = b.unit ? " " + b.unit : "";
  l.append(el("span", null, b.n || "Verlauf"),
           el("span", "mono", vals.length ? `${num(vals[0])} → ${num(vals[vals.length - 1])}${unit}` : ""));
  box.append(l);
  if (vals.length >= 2) {
    const W = 760, H = 70, min = Math.min(...vals), max = Math.max(...vals), span = (max - min) || 1;
    const d = vals.map((x, i) => `${i ? "L" : "M"}${(i / (vals.length - 1) * W).toFixed(1)},${(H - (x - min) / span * H).toFixed(1)}`).join(" ");
    const s = svg("svg", { viewBox: `0 -4 ${W} ${H + 8}`, preserveAspectRatio: "none", role: "img", "aria-label": b.n || "Verlauf" });
    s.append(svg("path", { d }));
    box.append(s);
  }
  return box;
}

/* ---------- weather page (typ wx) ----------
 * Builds tiles from the known dat fields (dictionary "wx"); every tile only
 * appears when its values are there. Unknown or extra fields fall back to the
 * plain value cards below the tiles. A temperature series block is drawn as
 * a tile, all other blocks are rendered as usual. */

const WX_DIRS = ["N", "NNO", "NO", "ONO", "O", "OSO", "SO", "SSO",
                 "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"];
const WX_TILE_KEYS = ["temp", "dew", "tmin", "tmax", "wdir", "wspd", "gust", "gust10", "gmax",
                      "qff", "qnh", "qfe", "ptnd", "hum", "r10m", "r1h", "rday", "r24h"];

function wxDir(deg) { return WX_DIRS[Math.round(((deg % 360) + 360) % 360 / 22.5) % 16]; }
function wxBft(ms) {
  const limits = [0.3, 1.6, 3.4, 5.5, 8.0, 10.8, 13.9, 17.2, 20.8, 24.5, 28.5, 32.7];
  const i = limits.findIndex(g => ms < g);
  return i < 0 ? 12 : i;
}
function wxNum(v, digits = 1) {
  return v.toLocaleString("de-AT", { minimumFractionDigits: digits, maximumFractionDigits: digits, useGrouping: false });
}
function wxClamp(x) { return Math.max(0, Math.min(100, x)); }

function wxTile(cls, title, note) {
  const t = el("section", "wx-tile " + cls);
  const h = el("h5", null, title);
  if (note) h.append(el("span", null, note));
  t.append(h);
  return t;
}
function wxValue(cls, value, unit) {
  const v = el("div", cls, value);
  if (unit) v.append(el("small", null, unit));
  return v;
}
function wxSub(parts) {           // parts: [text, bold, text, bold, ...]
  const s = el("div", "wx-sub");
  parts.forEach((p, i) => s.append(i % 2 ? el("b", null, p) : p));
  return s;
}
function wxKv(rows) {
  const dl = el("dl", "wx-kv");
  for (const [k, v] of rows) dl.append(el("dt", null, k), el("dd", null, v));
  return dl;
}
function wxGauge(pct, filled) {
  const g = el("div", "wx-gauge");
  if (filled) { const i = el("i"); i.style.width = wxClamp(pct) + "%"; g.append(i); }
  else { const m = el("div", "mk"); m.style.left = wxClamp(pct) + "%"; g.append(m); }
  return g;
}
function wxScale(labels) {
  const s = el("div", "wx-scale");
  for (const l of labels) s.append(el("span", null, l));
  return s;
}

function wxCompass(deg, speed) {
  const s = svg("svg", { viewBox: "-110 -110 220 220", class: "wx-compass", role: "img",
                         "aria-label": deg === null ? "Windrichtung unbekannt" : `Wind aus ${wxDir(deg)}, ${Math.round(deg)} Grad` });
  s.append(svg("circle", { r: 96, class: "ring" }), svg("circle", { r: 70, class: "inner" }));
  for (let a = 0; a < 360; a += 45) {
    const long = a % 90 === 0;
    s.append(svg("line", { y1: -96, y2: long ? -82 : -88, class: long ? "tick" : "tick minor",
                           transform: `rotate(${a})` }));
  }
  for (const [txt, x, y] of [["N", 0, -60], ["O", 60, 0], ["S", 0, 60], ["W", -60, 0]]) {
    const t = svg("text", { x, y, dy: 6, class: "cardinal" });
    t.textContent = txt;
    s.append(t);
  }
  if (deg !== null) {            // marker on the ring where the wind comes from, pointing inwards
    s.append(svg("path", { d: "M0,-34 L-15,-100 L0,-88 L15,-100 Z", class: "arrow",
                           transform: `rotate(${deg})` }));
  }
  s.append(svg("circle", { r: 27, class: "hub" }));
  const v = svg("text", { y: 3, class: "speed" });
  v.textContent = speed === null ? "–" : wxNum(speed);
  const u = svg("text", { y: 18, class: "unit" });
  u.textContent = "m/s";
  s.append(v, u);
  return s;
}

function wxNiceStep(range, maxTicks) {   // 1-2-5 steps, at most maxTicks intervals
  const raw = range / maxTicks, mag = Math.pow(10, Math.floor(Math.log10(raw)));
  for (const m of [1, 2, 5, 10]) if (m * mag >= raw) return m * mag;
  return 10 * mag;
}

function wxSpark(b, pageTime) {
  const sc = typeof b.sc === "number" ? Math.pow(10, b.sc) : 1;
  const vals = (Array.isArray(b.v) ? b.v : []).map(x => typeof x === "number" ? x * sc : null);
  const ok = vals.filter(x => x !== null);
  const unit = b.u === "Cel" || b.unit === "°C" ? "°C" : (b.unit || "");
  // the series is thinned out (e.g. one value per 2 h), so its own min/max is not
  // the true 24-h extreme: the note shows the step instead
  const step = typeof b.dt === "number" ? (b.dt >= 3600 ? `${num(b.dt / 3600)} h` : `${num(b.dt / 60)} min`) : "";
  const t = wxTile("wx-spark", b.n || "Verlauf", step ? `ein Wert je ${step}` : "");
  const W = 760, H = 96, n = vals.length;

  // y axis: rounded limits and 1-2-5 ticks
  const yStep = wxNiceStep((Math.max(...ok) - Math.min(...ok)) || 1, 5);
  const min = Math.floor(Math.min(...ok) / yStep) * yStep;
  let max = Math.ceil(Math.max(...ok) / yStep) * yStep;
  if (max === min) max = min + yStep;
  const x = i => (i / (n - 1) * W).toFixed(1);
  const y = v => (H - (v - min) / (max - min) * H).toFixed(1);
  const yTicks = [];
  for (let v = min; v <= max + yStep / 2; v += yStep) yTicks.push(+v.toFixed(6));
  const yDigits = yStep < 1 ? 1 : 0;

  const s = svg("svg", { viewBox: `0 0 ${W} ${H}`, preserveAspectRatio: "none", role: "img",
                         "aria-label": b.n || "Verlauf" });
  for (const v of yTicks) s.append(svg("line", { x1: 0, x2: W, y1: y(v), y2: y(v), class: "grid" }));
  // the line breaks at missing values; the area is drawn per connected run
  let line = "", runs = [], run = [];
  vals.forEach((v, i) => {
    if (v === null) { if (run.length) runs.push(run); run = []; return; }
    line += `${run.length ? "L" : "M"}${x(i)},${y(v)} `;
    run.push([x(i), y(v)]);
  });
  if (run.length) runs.push(run);
  for (const r of runs) {
    if (r.length < 2) continue;
    s.append(svg("path", { d: `M${r[0][0]},${H} L` + r.map(p => p.join(",")).join(" L") +
                              ` L${r[r.length - 1][0]},${H} Z`, class: "area" }));
  }
  s.append(svg("path", { d: line, class: "line" }));

  const yax = el("div", "wx-yax");
  for (const v of yTicks) {
    const lb = el("span", null, wxNum(v, yDigits));
    lb.style.top = (y(v) / H * 100) + "%";
    yax.append(lb);
  }
  yax.append(el("span", "u", unit));

  // x axis: clock times; the last value is the measurement at page time,
  // rounded down to the 10-min grid of the TAWES stations
  const xax = el("div", "wx-xax");
  const end = pageTime ? Math.floor(new Date(pageTime).getTime() / 600000) * 600000 : NaN;
  if (typeof b.dt === "number" && !isNaN(end)) {
    const every = Math.max(1, Math.ceil((n - 1) / 6));   // at most ~7 labels
    for (let i = n - 1; i >= 0; i -= every) {
      const d = new Date(end - (n - 1 - i) * b.dt * 1000);
      const lb = el("span", null, d.toLocaleTimeString("de-AT", { hour: "2-digit", minute: "2-digit" }));
      lb.style.left = (i / (n - 1) * 100) + "%";
      if (i === n - 1) lb.style.transform = "translateX(-100%)";   // keep the edge labels inside
      else if (i === 0) lb.style.transform = "none";
      xax.append(lb);
      s.append(svg("line", { x1: x(i), x2: x(i), y1: 0, y2: H, class: "vgrid" }));
    }
  }

  const chart = el("div", "wx-chart");
  chart.append(yax, s, el("div"), xax);
  t.append(chart);
  return t;
}

function weatherView(p) {
  const D = {};
  for (const d of p.data) D[d.key] = d;
  const val = k => (D[k] && typeof D[k].value === "number") ? D[k].value : null;
  const used = new Set();
  const grid = el("div", "wx");

  // temperature
  const temp = val("temp"), dew = val("dew"), tmin = val("tmin"), tmax = val("tmax");
  if (temp !== null) {
    const t = wxTile("wx-hero", "Temperatur");
    const left = el("div");
    left.append(wxValue("wx-big", wxNum(temp), "°C"));
    if (dew !== null) left.append(wxSub(["Taupunkt ", `${wxNum(dew)} °C`, " · Spread ", `${wxNum(temp - dew)} K`]));
    t.append(left);
    if (tmin !== null && tmax !== null) {
      const r = el("div", "wx-range");
      r.append(el("div", "wx-cap", "Letzte 24 h"));
      const bar = el("div", "bar");
      const mk = el("div", "mk");
      mk.style.left = wxClamp(tmax > tmin ? (temp - tmin) / (tmax - tmin) * 100 : 50) + "%";
      mk.title = `jetzt ${wxNum(temp)} °C`;
      bar.append(mk);
      const ends = el("div", "ends");
      ends.append(el("span", "lo", `▼ ${wxNum(tmin)} °C`), el("span", "hi", `▲ ${wxNum(tmax)} °C`));
      r.append(bar, ends);
      t.append(r);
    }
    grid.append(t);
  }

  // wind
  const wdir = val("wdir"), wspd = val("wspd"), gust = val("gust10") ?? val("gust"), gmax = val("gmax");
  if (wspd !== null || wdir !== null) {
    const t = wxTile("wx-wind", "Wind", wdir !== null ? `aus ${wxDir(wdir)}, ${Math.round(wdir)}°` : "");
    t.append(wxCompass(wdir, wspd));
    const rows = [];
    if (wspd !== null) rows.push(["Mittel", `${Math.round(wspd * 3.6)} km/h · Bft ${wxBft(wspd)}`]);
    if (gust !== null) rows.push(["Spitze", `${wxNum(gust)} m/s · ${Math.round(gust * 3.6)} km/h`]);
    if (gmax !== null) rows.push(["Böe 24 h", `${wxNum(gmax)} m/s · ${Math.round(gmax * 3.6)} km/h`]);
    if (rows.length) t.append(wxKv(rows));
    if (wspd !== null) {
      const now = wxBft(wspd), peak = gmax !== null ? wxBft(gmax) : 0;
      const bft = el("div", "wx-bft");
      bft.title = "Beaufort 1–12";
      for (let i = 1; i <= 12; i++) bft.append(el("i", i <= now ? "on" : i === peak ? "gust" : null));
      t.append(bft, wxScale(["Bft 1", "6", "12"]));
      const lg = el("div", "wx-legend");
      lg.append(el("span", "a", "jetzt"));
      if (peak > now) lg.append(el("span", "g", "max. Böe 24 h"));
      t.append(lg);
    }
    grid.append(t);
  }

  // pressure: QFF or QNH (sea level) on a gauge, station pressure as a note
  const pKey = ["qff", "qnh", "qfe"].find(k => val(k) !== null);
  if (pKey) {
    const pv = val(pKey), ptnd = val("ptnd");
    const t = wxTile("wx-press", "Luftdruck", pKey.toUpperCase());
    t.append(wxValue("wx-mid", wxNum(pv), "hPa"));
    if (ptnd !== null) {
      const [sym, word] = ptnd > 0.5 ? ["↗", "steigend"] : ptnd < -0.5 ? ["↘", "fallend"] : ["→", "gleichbleibend"];
      t.append(el("div", "wx-trend", `${sym} ${word}`),
               wxSub(["Tendenz ", `${ptnd > 0 ? "+" : ptnd < 0 ? "−" : "±"}${wxNum(Math.abs(ptnd))} hPa / 3 h`]));
    }
    if (pKey !== "qfe") {
      t.append(wxGauge((pv - 980) / 60 * 100, false), wxScale(["980", "1010", "1040"]));
      if (val("qfe") !== null) t.append(wxSub(["Stationsdruck ", `${wxNum(val("qfe"))} hPa`]));
    }
    grid.append(t);
  }

  // humidity
  const hum = val("hum");
  if (hum !== null) {
    const t = wxTile("wx-hum", "Relative Feuchte", hum < 40 ? "trocken" : hum > 85 ? "feucht" : "");
    t.append(wxValue("wx-mid", Math.round(hum), "%"), wxGauge(hum, true), wxScale(["0", "50", "100 %"]));
    if (dew !== null) t.append(wxSub(["Taupunkt ", `${wxNum(dew)} °C`]));
    grid.append(t);
  }

  // temperature series (block "series" in °C), drawn as its own tile
  const series = p.blocks.find(b => b.k === "series" && (b.u === "Cel" || b.unit === "°C")
    && Array.isArray(b.v) && b.v.filter(x => typeof x === "number").length >= 2);
  if (series) { grid.append(wxSpark(series, p.t)); used.add(series); }

  // precipitation: the shortest period is the main value
  const rain = [["r10m", "letzte 10 min"], ["r1h", "letzte Stunde"], ["rday", "seit Mitternacht"], ["r24h", "letzte 24 h"]]
    .filter(([k]) => val(k) !== null);
  if (rain.length) {
    const t = wxTile("wx-rain", "Niederschlag");
    const [k0, l0] = rain[0];
    t.append(wxValue("wx-mid", wxNum(val(k0)), "mm"), el("div", "wx-sub", l0));
    if (rain.length > 1) t.append(wxKv(rain.slice(1).map(([k, l]) => [l, `${wxNum(val(k))} mm`])));
    grid.append(t);
  }

  const node = el("div", "wx-wrap");
  node.append(grid);
  // everything else (sun, UV, snow, fields from a newer dictionary ...) as plain cards
  const rest = p.data.filter(d => !WX_TILE_KEYS.includes(d.key) || typeof d.value !== "number");
  if (rest.length) {
    const cards = el("div", "cards");
    for (const d of rest) cards.append(card(d.label, d.value, d.unit));
    node.append(cards);
  }
  return { node, used };
}

/* ---------- weather grid (table block with column semantics) ----------
 * A table block whose "n" is a list of column meanings – dat keys of the
 * weather dictionary such as "temp", "wdir", "wspd", "gust", "r24h"; any other
 * entry (e.g. "name") is a plain text column – is drawn as a weather grid:
 * temperature bars coloured by value, wind arrows, rain bars and a summary of
 * the extremes above. Rows with a single text cell are group headings
 * ("Weinviertel"). Continuation blocks (no hdr) inherit hdr and n of the last
 * table block that had them, as they do in the plain table. The plain table
 * stays available with the "Text" button (state.graphic). */

const WXG_TEMP = ["temp", "dew", "tmin", "tmax"];
const WXG_SPEED = ["wspd", "gust", "gust10", "gmax"];
const WXG_RAIN = ["r10m", "r1h", "rday", "r24h"];
const WXG_KEYS = [...WXG_TEMP, ...WXG_SPEED, ...WXG_RAIN, "wdir", "hum"];

function wxgCols(b) {
  return Array.isArray(b.n) && b.n.some(k => WXG_KEYS.includes(k)) ? b.n : null;
}

/* diverging around the freezing point: blue below 0 °C, warm hues above,
 * neutral grey at 0 – darker the further from zero */
function wxgTempColor(t) {
  if (t <= 0) { const k = Math.min(1, -t / 20); return `hsl(214 ${40 + 45 * k}% ${66 - 32 * k}%)`; }
  const k = Math.min(1, t / 35);
  return `hsl(${34 - 18 * k} ${50 + 40 * k}% ${66 - 30 * k}%)`;
}

function wxgArrow(deg) {            // points where the wind blows to (from deg + 180)
  const s = svg("svg", { viewBox: "-12 -12 24 24", class: "wxg-arrow", role: "img",
                         "aria-label": `Wind aus ${wxDir(deg)}` });
  s.append(svg("path", { d: "M0,-10 L5,2 L1.5,0.5 L1.5,10 L-1.5,10 L-1.5,0.5 L-5,2 Z",
                         transform: `rotate(${(deg + 180) % 360})` }));
  return s;
}

function wxgBar(pct, color) {
  const b = el("div", "wxg-bar");
  const i = el("i");
  i.style.width = wxClamp(pct) + "%";
  if (color) i.style.background = color;
  b.append(i);
  return b;
}

/* rows: [[cell, ...], ...] already scaled; cols: the n list; hdr: header texts */
function wxGrid(rows, cols, hdr, withSummary) {
  const idx = k => cols.indexOf(k);
  const col = (keys) => keys.map(idx).find(i => i >= 0) ?? -1;
  const cTemp = col(WXG_TEMP), cDir = idx("wdir"), cSpd = col(["wspd"]), cGust = col(["gust", "gust10", "gmax"]),
        cRain = col(WXG_RAIN), cHum = idx("hum");
  const textCols = cols.map((k, i) => WXG_KEYS.includes(k) ? -1 : i).filter(i => i >= 0);
  const data = rows.filter(r => Array.isArray(r) && r.length > 1);
  const numsOf = c => c < 0 ? [] : data.map(r => r[c]).filter(x => typeof x === "number");
  const temps = numsOf(cTemp), gusts = numsOf(cGust), rains = numsOf(cRain), spds = numsOf(cSpd);
  const tMin = Math.min(...temps), tMax = Math.max(...temps);
  const gMax = Math.max(0, ...gusts), rMax = Math.max(0, ...rains);
  const name = r => textCols.map(i => r[i]).filter(x => x !== null && x !== undefined).join(" ");
  const label = (c, fallback) => (Array.isArray(hdr) && typeof hdr[c] === "string") ? hdr[c] : fallback;

  const wrap = el("div", "wxg");

  // summary: the extremes of the whole table
  if (withSummary && data.length > 1) {
    const sum = el("div", "wxg-sum");
    const tile = (title, r, value, unit, note) => {
      const t = el("div", "wxg-tile");
      t.append(el("div", "wxg-cap", title), el("div", "wxg-st", name(r)));
      const v = el("div", "wxg-val", value);
      v.append(el("small", null, unit));
      t.append(v);
      if (note) t.append(el("div", "wxg-note", note));
      return t;
    };
    const pick = (c, fn) => data.filter(r => typeof r[c] === "number").reduce((a, r) => a === null || fn(r[c], a[c]) ? r : a, null);
    if (temps.length) {
      const hi = pick(cTemp, (x, y) => x > y), lo = pick(cTemp, (x, y) => x < y);
      sum.append(tile("Wärmste Station", hi, wxNum(hi[cTemp]), "°C"),
                 tile("Kälteste Station", lo, wxNum(lo[cTemp]), "°C",
                      `Spanne ${wxNum(hi[cTemp] - lo[cTemp])} K`));
    }
    if (gusts.length) {
      const g = pick(cGust, (x, y) => x > y);
      sum.append(tile("Stärkste Böe", g, wxNum(g[cGust]), "m/s", `${Math.round(g[cGust] * 3.6)} km/h · Bft ${wxBft(g[cGust])}`));
    }
    if (rains.length) {
      const r = pick(cRain, (x, y) => x > y);
      const wet = rains.filter(x => x > 0).length;
      sum.append(tile("Meiste Regen", r, wxNum(r[cRain]), "mm",
                      r[cRain] > 0 ? `an ${wet} von ${rains.length} Stationen` : "überall trocken"));
    }
    wrap.append(sum);
  }

  // header row of the grid; the column template follows the columns present
  const grid = el("div", "wxg-grid");
  // (wide / narrow pane – the narrow template applies below 640px container width)
  const tpl = ["minmax(118px, 1.1fr)"], narrow = ["minmax(84px, 1.1fr)"];
  if (cTemp >= 0) { tpl.push("minmax(150px, 2fr)"); narrow.push("minmax(96px, 2fr)"); }
  if (cSpd >= 0 || cDir >= 0) { tpl.push("minmax(150px, 1.6fr)"); narrow.push("minmax(86px, 1.4fr)"); }
  if (cGust >= 0) { tpl.push("minmax(96px, 1fr)"); narrow.push("minmax(70px, 1fr)"); }
  if (cHum >= 0) { tpl.push("minmax(110px, 1.2fr)"); narrow.push("minmax(80px, 1.2fr)"); }
  if (cRain >= 0) { tpl.push("minmax(110px, 1.4fr)"); narrow.push("minmax(80px, 1.4fr)"); }
  grid.style.setProperty("--wxg-cols", tpl.join(" "));
  grid.style.setProperty("--wxg-cols-narrow", narrow.join(" "));
  const head = el("div", "wxg-row wxg-head");
  head.append(el("span", null, textCols.length ? label(textCols[0], "Station") : "Station"));
  if (cTemp >= 0) {
    const h = el("span", null, label(cTemp, "Temperatur"));
    if (temps.length > 1) h.append(el("small", null, ` ${wxNum(tMin)} … ${wxNum(tMax)}`));
    head.append(h);
  }
  if (cSpd >= 0 || cDir >= 0) head.append(el("span", null, label(cSpd >= 0 ? cSpd : cDir, "Wind")));
  if (cGust >= 0) head.append(el("span", null, label(cGust, "Böe")));
  if (cHum >= 0) head.append(el("span", null, label(cHum, "Feuchte")));
  if (cRain >= 0) head.append(el("span", null, label(cRain, "Niederschlag")));
  grid.append(head);

  for (const r of rows) {
    if (!Array.isArray(r)) continue;
    if (r.length === 1) {                                  // group heading
      grid.append(el("div", "wxg-group", String(r[0])));
      continue;
    }
    const row = el("div", "wxg-row");
    row.append(el("span", "wxg-name", name(r) || "–"));
    if (cTemp >= 0) {
      const cell = el("span", "wxg-temp");
      const t = r[cTemp];
      if (typeof t === "number") {
        // 4 % minimum so the coldest station still shows a stub, not an empty bar
        cell.append(wxgBar(tMax > tMin ? 4 + (t - tMin) / (tMax - tMin) * 96 : 50, wxgTempColor(t)),
                    el("b", null, wxNum(t)));
      } else cell.append(el("b", "dim", "–"));
      row.append(cell);
    }
    if (cSpd >= 0 || cDir >= 0) {
      const cell = el("span", "wxg-wind");
      const dir = cDir >= 0 ? r[cDir] : null, spd = cSpd >= 0 ? r[cSpd] : null;
      const deg = typeof dir === "number" ? dir : (typeof dir === "string" && WX_DIRS.includes(dir) ? WX_DIRS.indexOf(dir) * 22.5 : null);
      if (deg !== null) cell.append(wxgArrow(deg), el("span", "wxg-dir", typeof dir === "string" ? dir : wxDir(deg)));
      else cell.append(el("span", "wxg-dir dim", typeof dir === "string" ? dir : "–"));
      if (typeof spd === "number") {
        cell.append(el("b", null, wxNum(spd)), el("small", null, `${Math.round(spd * 3.6)} km/h`));
      }
      row.append(cell);
    }
    if (cGust >= 0) {
      const cell = el("span", "wxg-gust");
      const g = r[cGust];
      if (typeof g === "number") {
        cell.append(el("b", null, wxNum(g)), el("span", "wxg-bft" + (wxBft(g) >= 6 ? " strong" : ""), `Bft ${wxBft(g)}`));
      } else cell.append(el("b", "dim", "–"));
      row.append(cell);
    }
    if (cHum >= 0) {
      const cell = el("span", "wxg-hum");
      const h = r[cHum];
      if (typeof h === "number") cell.append(wxgBar(h, "var(--accent)"), el("b", null, Math.round(h)));
      else cell.append(el("b", "dim", "–"));
      row.append(cell);
    }
    if (cRain >= 0) {
      const cell = el("span", "wxg-rain");
      const x = r[cRain];
      if (typeof x === "number" && x > 0) cell.append(wxgBar(rMax > 0 ? x / rMax * 100 : 0, "var(--accent)"), el("b", null, wxNum(x)));
      else if (typeof x === "number") cell.append(el("b", "dim", "0"));
      else cell.append(el("b", "dim", "–"));
      row.append(cell);
    }
    grid.append(row);
  }
  const scroll = el("div", "wxg-scroll");
  scroll.append(grid);
  wrap.append(scroll);
  return wrap;
}

/* ---------- forecast (table block whose first column meaning is "hour") ----------
 * geosphere_prognose.py sends the forecast for a locator as a table with the
 * column meanings ["hour", "sky", "temp", "wdir", "wspd", "gust", "rr"]: local
 * hour as text, cloud cover in eighths, temperature, wind from (compass text),
 * mean wind and strongest gust in the step (m/s), precipitation in the step (mm).
 * Rows with one text cell are day headings ("Sa 24.10."). In graphic mode it is
 * drawn as a meteogram: day and hour bar, sky symbols, temperature curve, rain
 * bars, wind arrows and gusts - one column per time step. Nothing extra is sent
 * over the air; the plain table stays available with the "Text" button. */

function wxfIsForecast(cols) { return Array.isArray(cols) && cols[0] === "hour"; }

/* sunrise/sunset (local clock hours of this browser) for the date of t at pos,
 * NOAA approximation; null in polar day/night or without a position */
function wxfSun(t, pos) {
  if (!Array.isArray(pos) || pos.length < 2 || isNaN(new Date(t))) return null;
  const d = new Date(t), rad = Math.PI / 180;
  const start = Date.UTC(d.getUTCFullYear(), 0, 1);
  const doy = Math.floor((d.getTime() - start) / 86400000) + 1;
  const g = 2 * Math.PI / 365 * (doy - 1);
  const eqt = 229.18 * (0.000075 + 0.001868 * Math.cos(g) - 0.032077 * Math.sin(g)
              - 0.014615 * Math.cos(2 * g) - 0.040849 * Math.sin(2 * g));
  const decl = 0.006918 - 0.399912 * Math.cos(g) + 0.070257 * Math.sin(g) - 0.006758 * Math.cos(2 * g)
             + 0.000907 * Math.sin(2 * g) - 0.002697 * Math.cos(3 * g) + 0.00148 * Math.sin(3 * g);
  const lat = pos[0] * rad;
  const cosH = (Math.cos(90.833 * rad) - Math.sin(lat) * Math.sin(decl)) / (Math.cos(lat) * Math.cos(decl));
  if (cosH > 1 || cosH < -1) return null;
  const ha = Math.acos(cosH) / rad;
  const noonUtcMin = 720 - 4 * pos[1] - eqt;
  const offsetMin = -d.getTimezoneOffset();                    // browser's local time
  const local = m => (((m + offsetMin) / 60) % 24 + 24) % 24;
  return { rise: local(noonUtcMin - 4 * ha), set: local(noonUtcMin + 4 * ha) };
}

/* sky symbol from cloud cover (eighths), night and rain in the step */
function wxfSky(eighths, night, rain) {
  const s = svg("svg", { viewBox: "0 0 48 40", class: "wxf-sky", role: "img",
                         "aria-label": wxfSkyText(eighths, night, rain) });
  const cloud = (x, y, k, dark) => s.append(svg("path", {
    d: "M10,30 a8,8 0 0 1 1,-15.9 a11,11 0 0 1 21,-3 a8,8 0 0 1 6,18.9 Z",
    transform: `translate(${x} ${y}) scale(${k})`, class: dark ? "cloud dark" : "cloud" }));
  const body = (x, y, r) => {
    if (night) {
      s.append(svg("path", { d: `M${x + r * 0.3},${y - r} a${r},${r} 0 1 0 ${r * 0.7},${r * 1.75} a${r * 0.8},${r * 0.8} 0 0 1 ${-r * 0.7},${-r * 1.75} Z`,
                             class: "moon" }));
    } else {
      for (let a = 0; a < 360; a += 45) {
        s.append(svg("line", { x1: x, y1: y - r - 3, x2: x, y2: y - r - 7, class: "ray",
                               transform: `rotate(${a} ${x} ${y})` }));
      }
      s.append(svg("circle", { cx: x, cy: y, r, class: "sun" }));
    }
  };
  const e = typeof eighths === "number" ? eighths : null;
  const wet = typeof rain === "number" && rain >= 0.1;
  if (e === null && !wet) return s;
  if (!wet && e <= 1) body(24, 20, 9);
  else if (!wet && e <= 5) { body(17, 14, 7.5); cloud(8, 9, 0.85, false); }
  else cloud(4, wet ? 1 : 5, 1, e !== null && e >= 8 || wet);
  if (wet) {
    const n = rain >= 2 ? 3 : rain >= 0.5 ? 2 : 1;
    for (let i = 0; i < n; i++) {
      const x = 24 + (i - (n - 1) / 2) * 9;
      s.append(svg("line", { x1: x, y1: 32, x2: x - 3, y2: 38, class: "drop" }));
    }
  }
  return s;
}

function wxfSkyText(eighths, night, rain) {
  const parts = [];
  if (typeof eighths === "number") {
    parts.push(eighths <= 1 ? (night ? "klar" : "sonnig") : eighths <= 3 ? "leicht bewölkt"
               : eighths <= 5 ? "wolkig" : eighths <= 7 ? "stark bewölkt" : "bedeckt");
  }
  if (typeof rain === "number" && rain >= 0.1) parts.push(`Regen ${wxNum(rain)} mm`);
  return parts.join(", ") || "unbekannt";
}

/* rows: already scaled; cols: the n list; hdr: header texts; p: the page (t, pos) */
function wxForecast(rows, cols, hdr, p) {
  const idx = k => cols.indexOf(k);
  const cH = idx("hour"), cSky = idx("sky"), cT = idx("temp"), cDir = idx("wdir"), cSpd = idx("wspd"),
        cGust = idx("gust"), cRr = idx("rr");
  const at = (r, c) => (c >= 0 && typeof r[c] === "number") ? r[c] : null;
  const steps = [];
  let day = "";
  for (const r of rows) {
    if (!Array.isArray(r)) continue;
    if (r.length === 1) { day = String(r[0]); continue; }
    const dir = cDir >= 0 ? r[cDir] : null;
    steps.push({
      day, hour: cH >= 0 && r[cH] !== null && r[cH] !== undefined ? String(r[cH]) : "",
      sky: at(r, cSky), temp: at(r, cT), spd: at(r, cSpd), gust: at(r, cGust), rr: at(r, cRr),
      dir: typeof dir === "number" ? dir : (typeof dir === "string" && WX_DIRS.includes(dir) ? WX_DIRS.indexOf(dir) * 22.5 : null),
      dirText: typeof dir === "string" ? dir : (typeof dir === "number" ? wxDir(dir) : ""),
    });
  }
  const wrap = el("div", "wxg wxf");
  if (!steps.length) return wrap;

  // step length from the hour labels (the first step may be shorter: it starts now)
  const hours = steps.map(s => parseInt(s.hour, 10));
  const stepLen = i => {
    const a = hours[i], b = hours[i + 1];
    if (isNaN(a)) return 1;
    if (i + 1 < hours.length && !isNaN(b)) return ((b - a) % 24 + 24) % 24 || 24;
    return i > 0 && !isNaN(hours[i - 1]) ? ((a - hours[i - 1]) % 24 + 24) % 24 || 1 : 1;
  };
  const sun = wxfSun(p && p.t, p && p.pos);
  const night = i => {
    const mid = (hours[i] + stepLen(i) / 2) % 24;
    if (isNaN(mid)) return false;
    return sun ? (mid < sun.rise || mid > sun.set) : (mid < 6.5 || mid > 18);
  };
  const when = s => `${s.day.split(" ")[0]} ${s.hour} Uhr`;
  // typical step (the first one may be shorter), for the units of rain and gusts
  const lens = steps.map((s, i) => stepLen(i));
  const step = lens.length > 1 ? Math.max(...lens.slice(1)) : lens[0];
  const per = step > 1 ? ` / ${step} h` : " / h";

  // summary: temperature range, strongest gust, precipitation
  const sum = el("div", "wxg-sum");
  const tile = (title, value, unit, note) => {
    const t = el("div", "wxg-tile");
    t.append(el("div", "wxg-cap", title));
    const v = el("div", "wxg-val", value);
    v.append(el("small", null, unit));
    t.append(v);
    if (note) t.append(el("div", "wxg-note", note));
    return t;
  };
  const best = (key, fn) => steps.filter(s => s[key] !== null).reduce((a, s) => a === null || fn(s[key], a[key]) ? s : a, null);
  const lo = best("temp", (x, y) => x < y), hi = best("temp", (x, y) => x > y);
  if (lo && hi) sum.append(tile("Temperatur", `${wxNum(lo.temp)} … ${wxNum(hi.temp)}`, "°C",
                                `tiefste ${when(lo)} · höchste ${when(hi)}`));
  const g = best("gust", (x, y) => x > y);
  if (g) sum.append(tile("Stärkste Böe", String(Math.round(g.gust * 3.6)), "km/h",
                         `Bft ${wxBft(g.gust)} · ${when(g)}${g.dirText ? ", aus " + g.dirText : ""}`));
  const rains = steps.filter(s => s.rr !== null);
  if (rains.length) {
    const total = rains.reduce((a, s) => a + s.rr, 0), first = rains.find(s => s.rr >= 0.1);
    sum.append(tile("Niederschlag", wxNum(total), "mm", first ? `ab ${when(first)}` : "trocken"));
  }
  wrap.append(sum);

  // the meteogram: one column per step
  const n = steps.length;
  const grid = el("div", "wxf-grid");
  grid.style.setProperty("--wxf-n", n);
  const newDay = i => i > 0 && steps[i].day !== steps[i - 1].day;
  const label = (text, unit) => {
    const l = el("div", "wxf-lab", text);
    if (unit) l.append(el("small", null, unit));
    return l;
  };
  const cell = (i, cls) => {
    const c = el("div", "wxf-c" + (cls ? " " + cls : "") + (newDay(i) ? " d0" : "") + (night(i) ? " night" : ""));
    return c;
  };

  // days (one cell spanning the steps of the day) and hours
  grid.append(el("div", "wxf-lab wxf-dayl"));
  for (let i = 0; i < n;) {
    let k = 1;
    while (i + k < n && steps[i + k].day === steps[i].day) k++;
    const d = el("div", "wxf-day" + (i > 0 ? " d0" : ""), steps[i].day);
    d.style.gridColumn = `span ${k}`;
    grid.append(d);
    i += k;
  }
  grid.append(label("Uhr"));
  steps.forEach((s, i) => grid.append(Object.assign(cell(i, "wxf-hour"), { textContent: s.hour })));

  // sky
  grid.append(label(""));
  steps.forEach((s, i) => {
    const c = cell(i, "wxf-skyc");
    c.append(wxfSky(s.sky, night(i), s.rr));
    c.title = wxfSkyText(s.sky, night(i), s.rr) + (s.sky !== null ? ` (${Math.round(s.sky)}/8)` : "");
    grid.append(c);
  });

  // temperature: values, then the curve across all columns
  const temps = steps.map(s => s.temp), ok = temps.filter(x => x !== null);
  if (ok.length) {
    grid.append(label("Temp.", "°C"));
    steps.forEach((s, i) => {
      const c = cell(i, "wxf-temp");
      const b = el("b", null, s.temp === null ? "–" : wxNum(s.temp));
      if (s.temp !== null) b.style.color = s.temp <= 0 ? "#1F4E9A" : "var(--ink)";
      c.append(b);
      grid.append(c);
    });
    // the curve row: one empty cell per step (day rule and night shading exactly as
    // in the other rows, from the same grid tracks) and the curve laid over them.
    // Placed explicitly in row 5 (day, hour, sky, temperature come before it).
    const CURVE_ROW = 5;
    const lab = el("div", "wxf-lab");
    lab.style.gridArea = `${CURVE_ROW} / 1`;
    grid.append(lab);
    steps.forEach((st, i) => {
      const c = cell(i, "wxf-curvecell");
      c.style.gridArea = `${CURVE_ROW} / ${i + 2}`;
      grid.append(c);
    });
    const W = n * 100, H = 64, pad = 8;
    const tMin = Math.min(...ok), tMax = Math.max(...ok), span = (tMax - tMin) || 1;
    const x = i => i * 100 + 50, y = v => (pad + (1 - (v - tMin) / span) * (H - 2 * pad)).toFixed(1);
    const s = svg("svg", { viewBox: `0 0 ${W} ${H}`, preserveAspectRatio: "none", class: "wxf-curve",
                           role: "img", "aria-label": `Temperaturverlauf ${wxNum(tMin)} bis ${wxNum(tMax)} °C` });
    if (tMin < 0 && tMax > 0) s.append(svg("line", { x1: 0, x2: W, y1: y(0), y2: y(0), class: "zero" }));
    let line = "", run = [];
    const runs = [];
    temps.forEach((v, i) => {
      if (v === null) { if (run.length) runs.push(run); run = []; return; }
      line += `${run.length ? "L" : "M"}${x(i)},${y(v)} `;
      run.push([x(i), y(v)]);
    });
    if (run.length) runs.push(run);
    for (const r of runs) {
      if (r.length < 2) continue;
      s.append(svg("path", { d: `M${r[0][0]},${H} L` + r.map(q => q.join(",")).join(" L") + ` L${r[r.length - 1][0]},${H} Z`,
                             class: "area" }));
    }
    s.append(svg("path", { d: line, class: "line" }));
    const holder = el("div", "wxf-curvec");
    holder.style.gridArea = `${CURVE_ROW} / 2 / ${CURVE_ROW + 1} / -1`;
    holder.append(s);
    // dots as HTML so they stay round (the svg is stretched)
    temps.forEach((v, i) => {
      if (v === null) return;
      const dot = el("i", "wxf-dot");
      dot.style.left = ((i + 0.5) / n * 100) + "%";
      dot.style.top = (y(v) / H * 100) + "%";
      holder.append(dot);
    });
    grid.append(holder);
  }

  // precipitation bars (scale at least 2 mm, so drizzle stays small)
  if (cRr >= 0) {
    const rMax = Math.max(2, ...steps.map(s => s.rr || 0));
    grid.append(label("Regen", "mm" + per));
    steps.forEach((s, i) => {
      const c = cell(i, "wxf-rain");
      const bar = el("div", "wxf-rbar");
      const fill = el("i");
      fill.style.height = (s.rr ? Math.max(4, s.rr / rMax * 100) : 0) + "%";
      bar.append(fill);
      c.append(bar, el("span", s.rr >= 0.1 ? null : "dim", s.rr === null ? "–" : s.rr >= 0.1 ? wxNum(s.rr) : "0"));
      grid.append(c);
    });
  }

  // wind: arrow (where it blows to), direction, mean speed
  if (cSpd >= 0 || cDir >= 0) {
    grid.append(label("Wind", "km/h"));
    steps.forEach((s, i) => {
      const c = cell(i, "wxf-wind");
      if (s.dir !== null) c.append(wxgArrow(s.dir));
      c.append(el("span", "wxf-dir", s.dirText || "–"),
               el("b", null, s.spd === null ? "–" : String(Math.round(s.spd * 3.6))));
      if (s.spd !== null) c.title = `${wxNum(s.spd)} m/s · Bft ${wxBft(s.spd)}`;
      grid.append(c);
    });
  }

  // gusts with Beaufort, from Bft 6 highlighted
  if (cGust >= 0) {
    grid.append(label("Böen", "km/h"));
    steps.forEach((s, i) => {
      const c = cell(i, "wxf-gust");
      if (s.gust === null) c.append(el("b", "dim", "–"));
      else {
        const bft = wxBft(s.gust);
        c.append(el("b", bft >= 6 ? "strong" : null, String(Math.round(s.gust * 3.6))),
                 el("span", "wxg-bft" + (bft >= 6 ? " strong" : ""), `Bft ${bft}`));
        c.title = `${wxNum(s.gust)} m/s`;
      }
      grid.append(c);
    });
  }

  const scroll = el("div", "wxf-scroll");
  scroll.append(grid);
  wrap.append(scroll);
  return wrap;
}

/* ---------- DX summary (typ dxsum, dictionary v4, PLANUNG 16a/16b) ----------
 * dxfeed sends two pages, both with their data in p.data (the listener has
 * already turned the numbers into names and adds display texts):
 *   st   stations: tier call dxcc sp mw t0 t1 cw ssb ft8 oth om
 *        dxcc = dictionary name ("7P", texts.dxcc["7P"].t = "Lesotho") or text,
 *        t0/t1 = minutes before end, cw..oth = bands as bit masks (bits.cw = band
 *        names by bit), om = other modes
 *   act  band activity: band cw ssb ft8 oth peak om (om = [[mode, count], ...])
 *   end calls spots conts tiers cov win: the frame around it
 * Grid, heat map and plain lists are all drawn here; nothing extra goes over the air. */

const DX_BANDS = ["160m", "80m", "60m", "40m", "30m", "20m", "17m", "15m", "12m", "10m",
                  "6m", "4m", "2m", "70cm"];
const DX_MODES = [["cw", "CW"], ["ssb", "SSB"], ["ft8", "FT8"], ["oth", "Andere"]];
const DX_TIERS = ["A", "B", "C"];

function dxData(p) {
  if (!Array.isArray(p.data)) return null;
  const by = Object.fromEntries(p.data.map(d => [d.key, d]));
  if (!by.st && !by.act && !by.path) return null;
  const val = k => by[k] ? by[k].value : undefined;
  return { st: by.st, act: by.act, path: by.path, kind: val("kind") || "day",
           end: val("end"), calls: val("calls"), spots: val("spots"),
           conts: val("conts"), tiers: val("tiers"), cov: val("cov"), win: val("win") || 1440 };
}

/* rows of a rows item -> objects by column name */
function dxRecords(item) {
  if (!item || !Array.isArray(item.value) || !Array.isArray(item.cols)) return [];
  return item.value.filter(r => Array.isArray(r)).map(r => {
    const o = {};
    item.cols.forEach((k, i) => { o[k] = r[i] ?? null; });
    return o;
  });
}

// modes sent as text by dxfeed (not in the dictionary list)
const DX_MODE_TEXT = { "?": "ohne Angabe", "DIGI": "Digi" };

function dxText(item, col, v) {                 // display text of a list value
  const t = item && item.texts && item.texts[col] ? item.texts[col][v] : null;
  if (t && t.t) return t.t;
  if (col === "om" && typeof v === "string" && DX_MODE_TEXT[v]) return DX_MODE_TEXT[v];
  return typeof v === "number" ? `#${v}` : String(v ?? "");
}

function dxBands(item) {                        // band names by bit, from the dictionary
  const b = item && item.bits && Array.isArray(item.bits.cw) ? item.bits.cw : null;
  return b && b.length ? b : DX_BANDS;
}

function dxBandLabel(band) { return band === "70cm" ? "70c" : String(band).replace(/m$/, ""); }

function dxTier(o) { return typeof o.tier === "string" ? o.tier : (DX_TIERS[o.tier] || "?"); }

function dxBandsOf(o, bands) {
  const all = DX_MODES.reduce((m, [k]) => m | (Number(o[k]) || 0), 0);
  return bands.filter((_, i) => all & (1 << i));
}

function dxOthers(item, o) {
  return (Array.isArray(o.om) ? o.om : []).map(m => dxText(item, "om", m)).join(" ") || "Andere";
}

function dxModesOn(item, o, i) {
  const out = [];
  for (const [k, name] of DX_MODES)
    if ((Number(o[k]) || 0) & (1 << i)) out.push(k === "oth" ? dxOthers(item, o) : name);
  return out;
}

function dxModeList(item, o) {
  const out = DX_MODES.slice(0, 3).filter(([k]) => Number(o[k])).map(([, name]) => name);
  if (Number(o.oth)) out.push(dxOthers(item, o));
  return out.join(" ");
}

function dxTime(end, minutesBefore) {
  if (typeof end !== "number" || typeof minutesBefore !== "number") return null;
  const d = new Date((end - minutesBefore * 60) * 1000);
  const p2 = x => String(x).padStart(2, "0");
  return { day: p2(d.getUTCDate()), hm: p2(d.getUTCHours()) + p2(d.getUTCMinutes()) };
}

/* short windows (DX jetzt, neu): time of the last spot only */
function dxWhen(dx, o) {
  if (dx.kind === "day") return dxSpan(dx.end, o);
  const b = dxTime(dx.end, o.t1);
  return b ? `${b.hm.slice(0, 2)}:${b.hm.slice(2)}` : "";
}

function dxHasQrg(recs) { return recs.some(o => typeof o.qrg === "number"); }

function dxSpan(end, o) {
  const a = dxTime(end, o.t0), b = dxTime(end, o.t1);
  if (!a) return "";
  if (!b || (a.day === b.day && a.hm === b.hm)) return `${a.day}/${a.hm}`;
  return a.day === b.day ? `${a.day}/${a.hm}-${b.hm}` : `${a.day}/${a.hm}-${b.day}/${b.hm}`;
}

function dxTierBadge(t) {
  const s = el("span", "dx-tier t" + t, t);
  s.title = { A: "Relevanz A: selten – sofort hinschauen", B: "Relevanz B: interessant",
              C: "Relevanz C: Alltag" }[t] || "Relevanz unbekannt";
  return s;
}

/* the score of dxfeed (mostwanted.py), only for the order; the tier comes from dxfeed */
function dxScore(o) {
  const r = typeof o.mw === "number" ? Math.min(340, Math.max(1, o.mw)) : 170;
  return (1 + 9 * ((341 - r) / 340) ** 2) * Math.log2(1 + (Number(o.sp) || 0));
}

function dxSorted(recs) {
  const byCall = (a, b) => String(a.call).localeCompare(String(b.call));
  if (state.dxSort !== "rel") return [...recs].sort(byCall);
  const rank = o => DX_TIERS.indexOf(dxTier(o)) + 1 || 9;
  return [...recs].sort((a, b) => rank(a) - rank(b) || dxScore(b) - dxScore(a) || byCall(a, b));
}

/* "vor 12 min", "vor 3 h", "vor 2 Tagen" */
function dxAgo(ts) {
  const min = Math.max(0, Math.round((Date.now() / 1000 - ts) / 60));
  if (min < 1) return "gerade eben";
  if (min < 90) return `vor ${min} min`;
  const h = Math.round(min / 60);
  return h < 36 ? `vor ${h} h` : `vor ${Math.round(h / 24)} Tagen`;
}

function dxSummaryView(p, graphic) {
  const dx = dxData(p);
  const box = el("div", "dxsum dxk-" + dx.kind);
  if (dx.end) {               // how old: the point of the "jetzt" pages (PLANUNG 16c)
    const age = Date.now() / 1000 - dx.end;
    const stale = age > (dx.kind === "day" ? 4 * 3600 : 2 * 3600);
    box.append(el("div", "dx-age" + (stale ? " stale" : ""),
                  `Stand ${dxAgo(dx.end)}` + (stale ? " – nicht mehr aktuell" : "")));
  }
  if (dx.kind === "new" && dx.st) box.append(dxNewHead(dx));
  const conts = dx.conts ? ` aus ${dx.conts}` : "";
  const parts = [];
  if (typeof dx.calls === "number" && dx.kind !== "new") parts.push(`${dx.calls} DX-Rufzeichen`);
  if (typeof dx.spots === "number" && dx.kind !== "new")
    parts.push(dx.path ? `${dx.spots} Spots${conts}, alle Gebiete, nach Kontinent der DX-Station`
               : dx.st ? `${dx.spots} Spots${conts}`
               : `${dx.spots} Spots${conts}, dieselben wie in der DX-Zusammenfassung`);
  if (dx.st && dx.kind !== "new") {
    const recs = dxRecords(dx.st);
    if (!dx.tiers) parts.push(`${recs.length} Stationen nach Spottern (ohne Most-Wanted-Liste)`);
    else {
      const extra = recs.filter(o => !dx.tiers.includes(dxTier(o))).length;
      parts.push(`gezeigt: Relevanz ${dx.tiers.split("").join("/")}` +
                 (extra ? `, aufgefüllt auf ${recs.length} nach Relevanz` : ""));
    }
  }
  if (dx.end) {               // UTC like the times in the table
    const fmt = t => {
      const d = new Date(t * 1000), p2 = x => String(x).padStart(2, "0");
      return `${p2(d.getUTCDate())}.${p2(d.getUTCMonth() + 1)}. ${p2(d.getUTCHours())}:${p2(d.getUTCMinutes())}`;
    };
    parts.unshift(`${fmt(dx.end - dx.win * 60)} – ${fmt(dx.end)} UTC`);
  }
  if (parts.length) box.append(el("p", "dimtext", parts.join(" · ")));
  if (typeof dx.cov === "number")
    box.append(el("div", "note warn", `Cluster nur ${(dx.cov / 60).toFixed(1)} von ${dx.win / 60} h verbunden – unvollständig.`));
  if (dx.st) {
    const node = el("div");
    const draw = () => node.replaceChildren(graphic ? dxStationGrid(dx, draw) : dxStationPlain(dx));
    draw();
    box.append(node);
  }
  if (dx.act) box.append(graphic ? dxActivityGrid(dx.act) : dxActivityPlain(dx.act));
  if (dx.path) box.append(graphic ? dxPathGrid(dx.path) : dxPathPlain(dx.path));
  return box;
}

/* "Neu auf dem Band": the one station in large letters */
function dxNewHead(dx) {
  const o = dxRecords(dx.st)[0] || {};
  const head = el("div", "dx-newhead");
  head.append(el("div", "dx-new-call", String(o.call ?? "")),
              el("div", "dx-new-ent", dxText(dx.st, "dxcc", o.dxcc)));
  const facts = [];
  if (typeof o.qrg === "number") facts.push(`${o.qrg} kHz`);
  const modes = dxModeList(dx.st, o);
  if (modes) facts.push(modes);
  if (typeof o.sp === "number") facts.push(`${o.sp} Spotter`);
  if (typeof o.mw === "number") facts.push(`Most Wanted ${o.mw}`);
  if (dx.end && typeof o.t1 === "number") facts.push(`zuletzt ${dxAgo(dx.end - o.t1 * 60)}`);
  head.append(el("div", "dx-new-facts", facts.join(" · ")));
  return head;
}

const DX_CONTS = [["af", "AF", "Afrika"], ["an", "AN", "Antarktis"], ["as", "AS", "Asien"],
                  ["eu", "EU", "Europa"], ["na", "NA", "Nordamerika"], ["oc", "OC", "Ozeanien"],
                  ["sa", "SA", "Südamerika"]];

/* "Bänder jetzt": spots of the last hour, band x continent of the DX station */
function dxPathGrid(item) {
  const recs = dxRecords(item);
  const byBand = new Map(recs.map(o => [o.band, o]));
  const counts = DX_BANDS.map(b => byBand.get(b) || {});
  const top = Math.max(1, ...counts.flatMap(o => DX_CONTS.map(([k]) => Number(o[k]) || 0)));
  const vhf = i => DX_BANDS[i] === "6m" ? "vhf" : null;
  const wrap = el("div", "dxa");
  wrap.append(el("h4", null, "Bänder jetzt: Spots der letzten Stunde nach Kontinent"));
  const t = el("table", "dxa-tbl dxp-tbl");
  const head = el("tr");
  head.append(el("th"));
  DX_BANDS.forEach((b, i) => head.append(el("th", vhf(i), dxBandLabel(b))));
  t.append(head);
  for (const [k, short, name] of DX_CONTS) {
    if (k === "an" && !counts.some(o => Number(o.an))) continue;      // Antarctica only when heard
    const tr = el("tr");
    const lab = el("th", "dxa-mode", short);
    lab.title = name;
    tr.append(lab);
    counts.forEach((o, i) => {
      const n = Number(o[k]) || 0;
      const td = el("td", vhf(i));
      const cell = el("span", "dxa-cell path" + (n ? "" : " zero"), n ? String(n) : "");
      if (n) cell.style.setProperty("--a", Math.round(Math.max(0.18, Math.log(n + 1) / Math.log(top + 1)) * 100) + "%");
      td.title = `${DX_BANDS[i]} → ${name}: ${n} Spots`;
      td.append(cell);
      tr.append(td);
    });
    t.append(tr);
  }
  const scroll = el("div", "dxg-scroll");
  scroll.append(t);
  wrap.append(scroll);
  return wrap;
}

function dxPathPlain(item) {
  return dxPlainTable(["Band", ...DX_CONTS.map(c => c[1])],
    dxRecords(item).map(o => [dxText(item, "band", o.band), ...DX_CONTS.map(([k]) => o[k] || "")]));
}

function dxPlainTable(head, rows) {
  const t = el("table", "tbl");
  const tr = el("tr");
  for (const h of head) tr.append(el("th", null, h));
  t.append(tr);
  for (const r of rows) {
    const row = el("tr");
    for (const x of r) row.append(el("td", null, String(x ?? "")));
    t.append(row);
  }
  return t;
}

/* plain table; the teletext screen has 40 columns, so there only R, call,
 * entity (12 characters) and bands - modes and times stay in the flow view */
function dxStationPlain(dx) {
  const item = dx.st, bands = dxBands(item), recs = dxRecords(item);
  const bandText = o => dxBandsOf(o, bands).map(dxBandLabel).join(" ");
  const ent = o => dxText(item, "dxcc", o.dxcc);
  if (state.view === "teletext") {
    return dxPlainTable(["R", "Call", "Gebiet", "Bänder"],
      dxSorted(recs).map(o => [dxTier(o), o.call, ent(o).slice(0, 12), bandText(o)]));
  }
  const qrg = dxHasQrg(recs);
  return dxPlainTable(["R", "Call", "Gebiet", ...(qrg ? ["QRG"] : []), "Bänder", "Modes",
                       dx.kind === "day" ? "Zeit UTC" : "zuletzt UTC", "Sp", "MW"],
    dxSorted(recs).map(o => [dxTier(o), o.call, ent(o), ...(qrg ? [o.qrg ?? ""] : []), bandText(o),
                             dxModeList(item, o), dxWhen(dx, o), o.sp, o.mw ?? "–"]));
}

function dxOtherCounts(item, o) {
  return (Array.isArray(o.om) ? o.om : []).map(x => Array.isArray(x)
    ? `${dxText(item, "om", x[0])} ${x[1]}` : String(x)).join(" ");
}

function dxActivityPlain(item) {
  const recs = dxRecords(item);
  const peak = o => typeof o.peak === "number" ? String(o.peak).padStart(2, "0") + "z" : "";
  const band = o => dxText(item, "band", o.band);
  if (state.view === "teletext") {
    const box = el("div");
    box.append(dxPlainTable(["Band", "CW", "SSB", "FT8", "And", "Spz"],
                            recs.map(o => [band(o), o.cw, o.ssb, o.ft8, o.oth, peak(o)])));
    const others = recs.filter(o => Array.isArray(o.om) && o.om.length);
    if (others.length) {
      box.append(el("h4", null, "Andere Modes"));
      const ul = el("ul");
      for (const o of others) ul.append(el("li", null, `${band(o)} ${dxOtherCounts(item, o)}`));
      box.append(ul);
    }
    return box;
  }
  return dxPlainTable(["Band", "CW", "SSB", "FT8", "Andere", "Spitze UTC", "Andere Modes"],
    recs.map(o => [band(o), o.cw, o.ssb, o.ft8, o.oth, peak(o), dxOtherCounts(item, o)]));
}

function dxLegend() {
  const l = el("div", "dx-legend");
  for (const [k, name] of DX_MODES) {
    const i = el("span", "dx-key");
    i.append(el("i", "dx-m " + k), name);
    l.append(i);
  }
  return l;
}

function dxStationGrid(dx, redraw) {
  const item = dx.st, bands = dxBands(item), recs = dxRecords(item);
  const wrap = el("div", "dxg");
  const bar = el("div", "dxg-bar");
  const sortBtn = (key, label) => {
    const b = el("button", "btn sm" + (state.dxSort === key ? " on" : ""), label);
    b.type = "button";
    b.onclick = () => { state.dxSort = key; saveDxSort(key); redraw(); };
    return b;
  };
  bar.append(el("span", "dxg-cap", "Sortierung"), sortBtn("abc", "Alphabetisch"), sortBtn("rel", "Relevanz"),
             el("span", "grow"), dxLegend());
  wrap.append(bar);

  const t = el("table", "dxg-tbl");
  const head = el("tr");
  head.append(el("th", "dx-r", "R"), el("th", "dx-call", "Call"), el("th", "dx-ent", "Gebiet"));
  bands.forEach(b => head.append(el("th", "dx-b" + (b === "6m" ? " vhf" : ""), dxBandLabel(b))));
  const qrg = dxHasQrg(recs);
  if (qrg) head.append(el("th", "dx-num qrg", "QRG"));
  head.append(el("th", "dx-num mw", "MW"), el("th", "dx-time", dx.kind === "day" ? "Zeit UTC" : "zuletzt"),
              el("th", "dx-num", "Sp"));
  t.append(head);
  for (const o of dxSorted(recs)) {
    const tier = dxTier(o);
    const tr = el("tr", "dx-row t" + tier);
    const r = el("td", "dx-r");
    r.append(dxTierBadge(tier));
    const entName = dxText(item, "dxcc", o.dxcc);
    const info = item.texts && item.texts.dxcc ? item.texts.dxcc[o.dxcc] : null;
    const ent = el("td", "dx-ent", entName);
    ent.title = info ? `${entName} (${o.dxcc}, ${info.cont || "?"}, CQ ${info.cq ?? "?"})` : entName;
    const call = el("td", "dx-call", String(o.call ?? ""));
    call.title = `${o.call}: ${dxSpan(dx.end, o)} UTC, ${o.sp ?? "?"} Spotter, Most Wanted ${o.mw ?? "unbekannt"}`;
    tr.append(r, call, ent);
    bands.forEach((band, i) => {
      const td = el("td", "dx-b" + (band === "6m" ? " vhf" : ""));
      const q = el("span", "dx-q");
      for (const [k] of DX_MODES) q.append(el("i", ((Number(o[k]) || 0) & (1 << i)) ? "dx-m " + k : null));
      const modes = dxModesOn(item, o, i);
      if (modes.length) td.title = `${band}: ${modes.join(", ")}`;
      td.append(q);
      tr.append(td);
    });
    if (qrg) tr.append(el("td", "dx-num qrg", typeof o.qrg === "number" ? String(o.qrg) : ""));
    tr.append(el("td", "dx-num mw", o.mw ?? "–"), el("td", "dx-time", dxWhen(dx, o)),
              el("td", "dx-num sp", String(o.sp ?? "")));
    t.append(tr);
  }
  const scroll = el("div", "dxg-scroll");
  scroll.append(t);
  wrap.append(scroll);
  if (!recs.length) wrap.append(el("p", "dimtext", "Keine DX-Station dieser Relevanz im Zeitraum."));
  return wrap;
}

function dxActivityGrid(item) {
  const recs = dxRecords(item);
  const wrap = el("div", "dxa");
  wrap.append(el("h4", null, "Bandaktivität nach Mode"));
  const byBand = new Map(recs.map(o => [o.band, o]));
  const counts = DX_BANDS.map(b => byBand.get(b) || {});
  const top = Math.max(1, ...counts.flatMap(o => DX_MODES.map(([k]) => Number(o[k]) || 0)));
  const vhf = i => DX_BANDS[i] === "6m" ? "vhf" : null;
  const t = el("table", "dxa-tbl");
  const head = el("tr");
  head.append(el("th"));
  DX_BANDS.forEach((b, i) => head.append(el("th", vhf(i), dxBandLabel(b))));
  t.append(head);
  for (const [k, name] of DX_MODES) {
    const tr = el("tr");
    const lab = el("th", "dxa-mode");
    lab.append(el("i", "dx-m " + k), name);
    tr.append(lab);
    counts.forEach((o, i) => {
      const n = Number(o[k]) || 0;
      const td = el("td", vhf(i));
      const cell = el("span", "dxa-cell " + k);
      // log scale, so 3 spots on 4 m do not vanish next to 600 on 20 m
      if (n) cell.style.setProperty("--a", Math.round(Math.max(0.14, Math.log(n + 1) / Math.log(top + 1)) * 100) + "%");
      else cell.classList.add("zero");
      const others = k === "oth" ? dxOtherCounts(item, o) : "";
      td.title = `${DX_BANDS[i]} ${name}: ${n} Spots` + (others ? ` (${others})` : "");
      td.append(cell);
      tr.append(td);
    });
    t.append(tr);
  }
  const sum = el("tr", "dxa-sum");
  sum.append(el("th", null, "Summe"));
  counts.forEach((o, i) => sum.append(el("td", vhf(i),
    String(DX_MODES.reduce((s, [k]) => s + (Number(o[k]) || 0), 0) || ""))));
  const peak = el("tr", "dxa-peak");
  peak.append(el("th", null, "Spitze UTC"));
  counts.forEach((o, i) => peak.append(el("td", vhf(i),
    typeof o.peak === "number" ? String(o.peak).padStart(2, "0") : "")));
  t.append(sum, peak);
  const scroll = el("div", "dxg-scroll");
  scroll.append(t);
  wrap.append(scroll);
  const others = recs.filter(o => Array.isArray(o.om) && o.om.length);
  if (others.length) {
    wrap.append(el("div", "dxa-cap", "Andere Modes im Detail"));
    const list = el("div", "dxa-others");
    for (const o of others) {
      const i = el("div");
      i.append(el("b", null, dxText(item, "band", o.band)), " " + dxOtherCounts(item, o));
      list.append(i);
    }
    wrap.append(list);
  }
  return wrap;
}

function loadDxSort() {
  try { return localStorage.getItem("brocast.dxsort") === "rel" ? "rel" : "abc"; } catch (e) { return "abc"; }
}

function saveDxSort(v) {
  try { localStorage.setItem("brocast.dxsort", v); } catch (e) { /* private mode */ }
}

function rawView(raws) {
  const r = el("div", "raw");
  for (const x of raws) {
    r.append(el("span", "h", `Unterseite ${x.sub} · rev ${x.rev} · ${x.bytes} Bytes · gehört von ${x.heard_from} · ${fmtTime(x.received)}\n`));
    r.append(x.hex.replace(/(..)/g, "$1 ").trim() + "\n\n");
    r.append(el("span", "h", "dekodiert\n"), JSON.stringify(x.decoded, null, 1) + "\n\n");
  }
  return r;
}

/* ---------- settings ---------- */

async function renderSettings() {
  state.screen = "settings";
  state.selected = null;
  const [settings, rubrics, stations, subs] = await Promise.all([
    api("GET", "/settings"), api("GET", "/rubrics"), api("GET", "/stations"), api("GET", "/subscriptions")]);
  state.settings = settings;
  const off = new Set(subs.optout.map(o => o.station + "|" + o.cat));

  const s = el("div", "settings");
  s.append(el("h2", null, "Einstellungen"),
           el("p", "hint", "Gilt nur für diese brocastd-Instanz. Warnungen und Notfall-Seiten werden immer angezeigt."),
           el("h3", null, "Abo – was soll angezeigt werden?"),
           el("p", "hint", "Grundsätzlich wird alles empfangen, auch von neu gehörten Stationen. Haken entfernen = abwählen. Die Auswahl gilt für neu ankommende Seiten."));

  const calls = ["*", ...new Set([...stations.map(x => x.call), ...subs.optout.map(o => o.station).filter(x => x !== "*")])];
  const t = el("table", "abo");
  const head = el("tr");
  head.append(el("th", null, "Station"), el("th", null, "alle Rubriken"));
  for (const r of rubrics) {
    const th = el("th", null, r.name);
    if (r.desc) th.title = r.desc;
    if (r.stations && r.stations.length) th.title = (r.desc ? r.desc + " – " : "") + "angeboten von " + r.stations.join(", ");
    head.append(th);
  }
  t.append(head);
  const boxes = [];
  for (const call of calls) {
    const tr = el("tr");
    tr.append(el("td", call === "*" ? null : "mono", call === "*" ? "alle Stationen" : call));
    const rowBoxes = [];
    const mk = (cat) => {
      const td = el("td");
      const cb = document.createElement("input");
      cb.type = "checkbox";
      cb.checked = !off.has(call + "|" + cat);
      cb.dataset.station = call;
      cb.dataset.cat = cat;
      cb.setAttribute("aria-label", `${call === "*" ? "alle Stationen" : call} – ${cat === "*" ? "alle Rubriken" : cat}`);
      if (call === "*" && cat === "*") { cb.checked = true; cb.disabled = true; }
      td.append(cb);
      tr.append(td);
      boxes.push(cb);
      return cb;
    };
    const all = mk("*");
    for (const r of rubrics) rowBoxes.push(mk(r.key));
    const sync = () => rowBoxes.forEach(b => { b.disabled = call !== "*" && !all.checked; });
    all.onchange = sync;
    sync();
    t.append(tr);
  }
  const matrix = el("div", "matrix");
  matrix.append(t);
  s.append(matrix, el("h3", null, "Speicher und Anzeige"));

  const f = el("div", "fields");
  const numField = (label, name, min, max) => {
    const i = document.createElement("input");
    i.type = "number"; i.min = min; i.max = max; i.value = settings[name]; i.id = "set-" + name;
    const l = el("label", null, label); l.htmlFor = i.id;
    f.append(l, i);
    return i;
  };
  const total = numField("Höchstzahl Seiten gesamt", "max_pages_total", 10, 100000);
  const perCat = numField("Höchstzahl Seiten je Rubrik", "max_pages_per_cat", 1, 100000);
  const age = numField("Maximales Alter (Tage)", "max_age_days", 1, 3650);
  const lang = document.createElement("select");
  lang.id = "set-lang";
  lang.append(new Option("Deutsch", "de"), new Option("English", "en"));
  lang.value = settings.lang;
  const ll = el("label", null, "Sprache der Anzeige"); ll.htmlFor = lang.id;
  const sound = document.createElement("select");
  sound.id = "set-sound";
  sound.append(new Option("ein", "1"), new Option("aus", "0"));
  sound.value = settings.alert_sound ? "1" : "0";
  const sl = el("label", null, "Hinweiston bei Warnungen"); sl.htmlFor = sound.id;
  f.append(ll, lang, sl, sound);
  const trust = document.createElement("input");
  trust.type = "text"; trust.id = "set-trust"; trust.className = "mono";
  trust.placeholder = "z. B. OE3GAS-5"; trust.autocomplete = "off";
  trust.value = (settings.dict_trusted || []).join(", ");
  const tl = el("label", null, "Dictionary über Funk automatisch übernehmen von"); tl.htmlFor = trust.id;
  f.append(tl, trust);
  s.append(f, el("p", "hint", "Rufzeichen mit Komma trennen. Von anderen Stationen wird ein über Funk " +
    "empfangenes Dictionary erst nach deiner Bestätigung installiert. Geprüft wird immer: vollständig, " +
    "Prüfsumme, neuere Version, nur Ergänzungen."));

  const save = el("button", "btn primary", "Speichern");
  save.type = "button";
  save.onclick = async () => {
    try {
      state.settings = await api("PUT", "/settings", {
        max_pages_total: parseInt(total.value, 10), max_pages_per_cat: parseInt(perCat.value, 10),
        max_age_days: parseInt(age.value, 10), lang: lang.value, alert_sound: sound.value === "1",
        dict_trusted: trust.value.split(/[\s,;]+/).map(x => x.trim().toUpperCase()).filter(Boolean) });
      const optout = boxes.filter(b => !b.checked && !b.disabled).map(b => ({ station: b.dataset.station, cat: b.dataset.cat }));
      await api("PUT", "/subscriptions", { optout });
      rubricCache = null;
      toast("Gespeichert.");
      refreshLists();
    } catch (e) {
      toast("Nicht gespeichert: " + e.message, true);
    }
  };
  const p = el("p", "hint", "Gelöschte Seiten bleiben gelöscht, bis die Station eine neue Revision sendet. Gemerkte Seiten werden nie verdrängt.");
  p.style.marginTop = "14px";
  s.append(save, p);
  $("view").replaceChildren(s);
  refreshLists();
}

/* ---------- status ---------- */

async function renderStatus() {
  state.screen = "status";
  state.selected = null;
  await refreshStatus();
  const st = state.status;
  const s = el("div", "settings");
  s.append(el("h2", null, "Status"));
  const f = el("div", "fields");
  const rows = [
    ["Version", st.version],
    ["Modus", st.mode === "station" ? `Station ${st.callsign}` : "Listener"],
    [`Direwolf (${st.interface || "KISS"})`, st.kiss_connected ? "verbunden" : "getrennt"],
    ["Frames empfangen", st.rx_frames], ["brocast-Seiten empfangen", st.rx_pages],
    ["Dekodierfehler", st.rx_errors], ["Frames gesendet", st.tx_frames],
    ["Dictionary installiert", st.dictionary ? `v${st.dictionary.local} · ${st.dictionary.hash}` : ""],
    ["Dictionary auf der Frequenz", !st.dictionary ? "" : st.dictionary.outdated
      ? `v${st.dictionary.newest_heard} von ${st.dictionary.heard_from} (zuletzt ${fmtTime(st.dictionary.last_heard)}) – Update nötig`
      : "keine neuere Version gehört"],
    ["Seiten gespeichert", st.pages], ["davon ungelesen", st.unread], ["Stationen gehört", st.stations],
  ];
  if (st.release)                                                 // PLANUNG 24
    rows.splice(1, 0, ["TinyBox-Release", st.release.newer
      ? `${st.release.current} – neuer Release ${st.release.latest} auf GitHub (git pull)`
      : `${st.release.current}` + (st.release.latest ? " – aktuell" : "")]);
  if (st.mode === "station") {
    rows.push(["Eigene Seiten im Karussell", st.pages_station !== undefined ? st.pages_station : ""]);
    rows.push(["Airtime (Fenster)", `${num(st.airtime_used_s)} s von ${num(st.airtime_limit_s)} s`]);
  }
  if (st.wire) {
    if (st.mode === "station")
      rows.push(["Frame-Format", `${st.wire.format}` +
                 (st.wire.format === 2 ? (st.wire.compress ? " (Inhalt gepackt)" : " (ungepackt)") : " (alt)")]);
    rows.push(["Preset-Wörterbuch", st.wire.zdict]);
    rows.push(["Seiten zusammengesetzt", st.wire.assembled]);
    const w = st.wire.waiting || [];
    if (w.length)
      rows.push(["Wartet auf Fragmente", w.map(p => `${p.station} Seite ${p.id}: ` +
                 `${p.have.length}/${p.total} (seit ${p.age_s} s)`).join(", ")]);
    if (st.wire.incomplete)
      rows.push(["Unvollständig verfallen", st.wire.incomplete]);
  }
  if (st.dictionary && st.dictionary.source) rows.push(["Bezugsquelle", st.dictionary.source.text]);
  if (st.dictionary && st.dictionary.radio)
    rows.push(["Dictionary über Funk", `v${st.dictionary.radio.version} von ${st.dictionary.radio.station}: ` +
                                       `${st.dictionary.radio.have}/${st.dictionary.radio.total} Teile`]);
  if (st.dictionary && st.dictionary.ready)
    rows.push(["Dictionary über Funk", `v${st.dictionary.ready.version} von ${st.dictionary.ready.station} ` +
                                       "vollständig – wartet auf Freigabe"]);
  if (st.dictionary && st.dictionary.hash_mismatch)
    rows.push(["Achtung", "Station sendet gleiche Version mit anderer Prüfsumme"]);
  for (const [k, v] of rows) f.append(el("span", null, k), el("b", "mono", v === undefined ? "" : v));
  const imp = el("button", "btn", "Dictionary importieren …");
  imp.type = "button";
  imp.style.marginTop = "18px";
  imp.onclick = () => renderImport();
  s.append(f, imp);
  if (st.mode === "station") {
    const now = el("button", "btn", "Dictionary jetzt über Funk senden");
    now.type = "button";
    now.style.margin = "18px 0 0 10px";
    now.title = "Sendet das gepackte Dictionary sofort (ca. 30 s), Wiederholung nach 15 min";
    now.onclick = async () => {
      try { toast((await api("POST", "/dictionary/broadcast", {})).message); }
      catch (e) { toast(e.message, true); }
    };
    s.append(now);
  }
  $("view").replaceChildren(s);
  refreshLists();
}

/* ---------- dictionary import ---------- */

function renderImport() {
  state.screen = "import";
  state.selected = null;
  const s = el("div", "settings");
  s.append(el("h2", null, "Dictionary importieren"),
           el("p", "hint", "Mailbox connecten (z. B. OE3GAS-1), Befehl DICT eingeben und die Ausgabe " +
              "im Terminalprogramm mitschneiden. Den Mitschnitt hier als Datei wählen oder einfügen – " +
              "Begrüßung und Prompts davor oder danach stören nicht."));
  const file = document.createElement("input");
  file.type = "file";
  file.accept = ".txt,.log,.cap,.yaml,text/plain";
  const fileLabel = el("label", "check", "Mitschnitt-Datei: ");
  fileLabel.append(file);
  const area = el("textarea", "importtext");
  area.placeholder = "#BROCAST-DICT BEGIN v2 lines=… sha256=…\n…\n#BROCAST-DICT END";
  area.spellcheck = false;
  const out = el("div", "importresult");
  let fileB64 = null;
  file.onchange = () => {
    const f = file.files && file.files[0];
    if (!f) { fileB64 = null; return; }
    const reader = new FileReader();
    reader.onload = () => {
      const bytes = new Uint8Array(reader.result);
      let bin = "";
      for (let i = 0; i < bytes.length; i += 8192) bin += String.fromCharCode.apply(null, bytes.subarray(i, i + 8192));
      fileB64 = btoa(bin);
      area.value = "";
      out.replaceChildren(el("p", "hint", `Datei „${f.name}“ geladen (${bytes.length} Bytes).`));
    };
    reader.readAsArrayBuffer(f);
  };
  area.oninput = () => { if (area.value) { fileB64 = null; file.value = ""; } };

  const send = async (dryRun) => {
    const body = fileB64 ? { data_b64: fileB64 } : { text: area.value };
    body.dry_run = dryRun;
    if (!fileB64 && !area.value.trim()) { toast("Bitte Datei wählen oder Text einfügen.", true); return; }
    let res;
    try {
      res = await api("POST", "/dictionary/import", body);
    } catch (e) {
      out.replaceChildren(el("div", "note alarm", e.message));
      return;
    }
    const box = el("div", "note" + (res.installed ? "" : " warn"), res.message);
    out.replaceChildren(box);
    if (res.added && Object.keys(res.added).length) {
      const ul = el("ul");
      for (const [k, v] of Object.entries(res.added)) ul.append(el("li", null, `${k}: +${v}`));
      out.append(ul);
    }
    if (res.installed) {
      rubricCache = null;
      await refreshStatus();
      refreshLists();
      toast(res.message);
    }
  };
  const check = el("button", "btn", "Prüfen");
  check.type = "button";
  check.onclick = () => send(true);
  const install = el("button", "btn primary", "Prüfen und installieren");
  install.type = "button";
  install.onclick = () => send(false);
  const btns = el("div", "actions");
  btns.append(check, install);
  s.append(fileLabel, el("p", "hint", "oder einfügen:"), area, btns, out);
  $("view").replaceChildren(s);
  refreshLists();
}

/* ---------- receive log ---------- */

async function renderRxlog(filter) {
  if (filter !== undefined) state.rxFilter = filter;          // {org, id} or null
  state.screen = "rxlog";
  if (filter && filter.org) state.selected = null;
  const f = state.rxFilter;
  const rows = await api("GET", "/rxlog" + qs({
    limit: 300, org: f && f.org, id: f && f.id, brocast: !state.rxForeign }));

  const s = el("div", "settings wide");
  const head = el("div", "loghead");
  head.append(el("h2", null, f ? `Empfangslog – Seite ${f.id} (${f.org})` : "Empfangslog"));
  if (f) {
    const all = el("button", "btn sm", "Alle Einträge");
    all.type = "button";
    all.onclick = () => renderRxlog(null);
    head.append(all);
  }
  const lbl = el("label", "check");
  const cb = document.createElement("input");
  cb.type = "checkbox";
  cb.checked = !!state.rxForeign;
  cb.onchange = () => { state.rxForeign = cb.checked; renderRxlog(); };
  lbl.append(cb, " auch andere Frames (APRS, Mailbox …)");
  head.append(el("span", "grow"), lbl);
  s.append(head, el("p", "hint",
    "Jeder gehörte Frame, neueste zuerst. „Wiederholung“ heißt: die Seite ist schon da und ändert " +
    "sich nicht. Mit der Maus über dem Ergebnis steht der genaue Grund."));

  const t = el("table", "tbl log");
  const hr = el("tr");
  for (const h of ["Zeit", "Von", "Seite", "Teil", "Rev", "Titel", "Ergebnis"]) hr.append(el("th", null, h));
  t.append(hr);
  for (const r of rows) {
    const tr = el("tr", r.kind === "foreign" ? "dim" : "");
    const d = new Date(r.time);
    tr.append(el("td", "mono", d.toLocaleTimeString("de-AT") + "." + String(d.getMilliseconds()).padStart(3, "0")
      + (d.toDateString() !== new Date().toDateString()
      ? " " + d.toLocaleDateString("de-AT", { day: "2-digit", month: "2-digit" }) : "")));
    const from = el("td", "mono", r.heard_from);
    if (r.result === "foreign" && r.dest) from.append(el("span", "dimtext", " > " + r.dest));
    tr.append(from);
    tr.append(el("td", "mono", r.id === null ? "" : r.id));
    tr.append(el("td", "mono", r.sub_total > 1 ? `${r.sub}/${r.sub_total}` : ""));
    tr.append(el("td", "mono", r.rev === null ? "" : r.rev));
    tr.append(el("td", null, r.ti));
    const res = el("td");
    if (r.kind === "foreign") res.append(el("span", "dimtext", r.chip));
    else {
      const chip = el("span", "rchip " + r.kind, r.chip);
      chip.title = r.text;                         // exact reason on hover
      res.append(chip);
    }
    tr.append(res);
    if (r.visible_now) {
      tr.classList.add("click");
      tr.title = "Seite öffnen";
      tr.onclick = () => openPage(r.org, r.id);
    }
    t.append(tr);
  }
  if (!rows.length) s.append(el("div", "empty", "Noch nichts empfangen."));
  else s.append(t);
  $("view").replaceChildren(s);
}

/* ---------- search, goto, wiring ---------- */

let searchTimer = null;
function onSearch() {
  clearTimeout(searchTimer);
  searchTimer = setTimeout(() => {
    state.q = $("search").value.trim();
    if (state.q) { state.cat = null; state.station = null; state.sub = "*"; setPane("list"); }
    state.screen = "pages";
    refreshLists();
  }, 300);
}

async function onGoto(e) {
  if (e.key !== "Enter") return;
  const n = parseInt($("goto").value, 10);
  if (!n) return;
  const all = await api("GET", "/pages");
  const hits = all.filter(p => p.id === n);
  if (!hits.length) { toast(`Seite ${n} ist nicht vorhanden.`, true); return; }
  const prefer = state.station || (state.selected && state.selected.org);
  const hit = hits.find(p => p.org === prefer) || hits[0];
  $("goto").value = "";
  openPage(hit.org, hit.id);
}

function setMode(mode) {
  state.mode = mode;
  $("tab-cat").classList.toggle("on", mode === "cat");
  $("tab-st").classList.toggle("on", mode === "st");
  state.cat = null; state.station = null; state.sub = "*";
  refreshLists();
}

async function poll() {
  await refreshStatus();
  try { await refreshAlerts(); } catch (e) { /* offline */ }
  if (state.screen === "status") renderStatus();
  else if (state.screen === "rxlog") { renderRxlog().catch(() => {}); refreshLists(); }
  else if (document.activeElement && document.activeElement.tagName !== "SELECT") refreshLists();
}

/* ---------- Sendung: what the station sends right now (08.11.2026) ----------
 * /tx is updated by brocastd with every frame handed to Direwolf (AGW/KISS).
 * Polled every second while something is on the air or the view is open,
 * else every 5 s. Only for a station. */

const TX_FAST_MS = 1000, TX_SLOW_MS = 5000;
let txTimer = null;

function mmss(s) {
  s = Math.max(0, Math.round(s));
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
}
function hms(ts) {
  return new Date(ts * 1000).toLocaleTimeString("de-AT", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}
function secs(v) { return num(Math.round(v * 10) / 10).replace(".", ","); }
function mins(s) { return (Math.round(s / 6) / 10).toLocaleString("de-AT", { minimumFractionDigits: 1 }); }

async function refreshTx() {
  clearTimeout(txTimer);
  let tx = null;
  if (state.status.mode === "station") {
    try { tx = await api("GET", "/tx"); } catch (e) { tx = null; }
  }
  state.tx = tx && tx.station ? tx : null;
  renderTxHeader();
  if (state.screen === "tx" && document.body.dataset.pane === "view") renderTxView();
  const fast = state.tx && (state.tx.current || state.screen === "tx");
  txTimer = setTimeout(() => refreshTx().catch(() => {}), fast ? TX_FAST_MS : TX_SLOW_MS);
}

function renderTxHeader() {
  const tx = state.tx, pill = $("hdr-tx"), air = $("hdr-air");
  $("nav-tx").hidden = !tx;
  pill.hidden = air.hidden = !tx;
  document.body.classList.toggle("tx-on", !!tx);      // the top bar makes room (CSS)
  if (!tx) return;
  $("nav-tx-count").textContent = tx.pages;
  $("nav-tx-dot").className = "txdot" + (tx.current ? " on" : "");
  const cur = tx.current, bl = tx.blocked;
  pill.className = "txpill";
  if (!tx.connected) {
    pill.classList.add("down");
    pill.replaceChildren(el("b", null, "✕ KEIN SENDER"),
      el("span", "t", bl && bl.page ? `P${bl.page} wartet – neuer Versuch in ${mmss(bl.until - tx.now)}` : "Direwolf getrennt"));
  } else if (cur) {
    pill.classList.add("onair");
    const bar = el("span", "bar");
    bar.style.width = Math.round((100 * cur.sent) / Math.max(cur.total, 1)) + "%";
    pill.replaceChildren(el("span", "rec", "ON AIR"), el("span", "y", `P${cur.id}`),
      el("span", "t", cur.title || cur.typ), el("span", "c", `${cur.sent}/${cur.total}`), bar);
  } else if (bl && (bl.reason === "busy" || bl.reason === "channel")) {   // real traffic first
    pill.classList.add("pause");
    pill.replaceChildren(el("b", null, "⏸ ZURÜCKGESTELLT"),
      el("span", "t", `${bl.why}${bl.waiting ? ` – ${bl.waiting} Seite${bl.waiting === 1 ? "" : "n"} warten` : ""}`));
  } else if (bl && bl.reason === "budget") {
    pill.classList.add("pause");
    pill.replaceChildren(el("b", null, "⏸ PAUSE"),
      el("span", "t", `Airtime-Budget voll – ${bl.waiting} Seite${bl.waiting === 1 ? "" : "n"} warten, frei in ${mmss(bl.until - tx.now)}`));
  } else {
    const n = tx.next.find((p) => p.next_tx);
    pill.classList.add("idle");
    pill.replaceChildren(el("span", "ring"), el("span", "m", "nächste"),
      ...(n ? [el("span", "y", `P${n.id}`), el("span", "t", n.title || n.typ),
               el("b", null, n.next_tx <= tx.now ? "gleich" : `in ${mmss(n.next_tx - tx.now)}`)]
            : [el("span", "t", "nichts geplant")]));
  }
  const b = tx.budget, pct = b.limit_s ? Math.min(100, (100 * b.used_s) / b.limit_s) : 0;
  const gauge = el("span", "gauge"), fill = el("span", "fill");
  fill.style.width = pct + "%";
  gauge.append(fill);
  air.className = "stat m-hide airmini" + (pct >= 100 ? " full" : "");
  air.replaceChildren("Airtime ", gauge, el("b", "mono", `${mins(b.used_s)}/${mins(b.limit_s)} min`));
}

/* The sysop takes one of the station's pages off the air: the listeners get the
 * withdrawal, the same content from the provider (TinyBox sync, dxfeed) stays
 * off; new content brings it back - or "Wieder senden". */
async function takeOffAir(id, title) {
  if (!confirm(`Seite ${id}${title ? " „" + title + "“" : ""} nicht mehr senden?\n\n` +
               "Die Hörer bekommen die Rücknahme und löschen sie. Schickt die Quelle (TinyBox, dxfeed) " +
               "denselben Inhalt wieder, bleibt sie aus der Sendung – erst ein geänderter Inhalt kommt wieder. " +
               "Endgültig weg ist ein Bulletin erst, wenn es auch in der TinyBox gelöscht ist.")) return false;
  try {
    await api("POST", "/tx/off", { id });
    toast(`Seite ${id} wird nicht mehr gesendet.`);
    await refreshTx();
    return true;
  } catch (e) { toast(e.message, true); return false; }
}

async function renderTx() {
  state.screen = "tx";
  state.selected = null;
  await refreshStatus();
  await refreshTx();
  renderTxView();
}

function partChips(cur) {
  const row = el("div", "txparts");
  row.append(el("span", "lbl", "Teil"));
  for (let i = 1; i <= cur.total && i <= 40; i++) {
    row.append(el("span", "pc" + (i < cur.sent ? " done" : i === cur.sent ? " now" : ""), i));
  }
  if (cur.bursts > 1) row.append(el("span", "lbl2", `${cur.bursts} Aussendungen`));
  return row;
}

function renderTxView() {
  const tx = state.tx, v = $("view");
  if (!tx) { v.replaceChildren(el("p", "empty", "Nur eine Station sendet.")); return; }
  const w = el("div", "txwrap");
  const h = el("div", "txhead");
  h.append(el("h2", null, "Sendung"), el("span", "sub",
    `Station ${state.status.callsign || ""} · ${tx.pages} Seiten im Karussell · Zeit = Übergabe an Direwolf (wie im Sendeprotokoll)`));
  w.append(h);

  const top = el("div", "txgrid");
  // now on the air
  const now = el("section", "txnow");
  const cur = tx.current;
  const nh = el("div", "nh");
  nh.append(el("span", cur ? "rec" : "rec off", cur ? "JETZT AUF SENDUNG" : (tx.connected ? "KEINE AUSSENDUNG" : "DIREWOLF GETRENNT")),
    el("span", "grow"), el("span", "c", hms(tx.now)));
  now.append(nh);
  const nb = el("div", "nb");
  if (cur) {
    const t = el("div", "nt");
    t.append(el("span", "y", `P${cur.id}`), el("span", "ti", cur.title || cur.typ));
    const parts = [`Rev ${cur.rev}`, cur.typ, `${cur.provider}/${cur.pkey}`, `Ziel ${cur.dest}`];
    if (cur.withdrawn) parts.push("zurückgezogen");
    const bar = el("div", "pbar"), fill = el("div");
    fill.style.width = Math.round((100 * cur.sent) / Math.max(cur.total, 1)) + "%";
    bar.append(fill);
    const kv = el("div", "kv");
    const cell = (k, val, cls) => { const c = el("div"); c.append(el("div", "k", k), el("div", "v" + (cls ? " " + cls : ""), val)); return c; };
    kv.append(cell("Bytes", cur.bytes.toLocaleString("de-AT")), cell("Airtime", `≈ ${secs(cur.air)} s`),
      cell(tx.agw ? "noch" : "noch (berechnet)", `≈ ${secs(cur.left_s)} s`, "y"),
      cell("bei Direwolf", tx.agw ? (tx.queue === null ? "?" : `${tx.queue} Frames`) : "KISS: keine Rückmeldung"));
    nb.append(t, el("div", "nm", parts.join(" · ")), partChips(cur), bar, kv);
  } else {
    const bl = tx.blocked;
    const n = tx.next.find((p) => p.next_tx);
    nb.append(el("div", "nidle", bl && (bl.reason === "busy" || bl.reason === "channel")
      ? `Zurückgestellt: ${bl.why}. brocast wartet, bis der Betrieb ruhiger ist – Notfall-Seiten gehen trotzdem.`
      : bl && bl.reason === "budget"
      ? `Airtime-Budget aufgebraucht – frei in ${mmss(bl.until - tx.now)}. Notfall-Seiten gehen trotzdem.`
      : !tx.connected ? "Direwolf ist nicht verbunden – die Sendung wartet."
        : n ? `Als Nächstes: P${n.id} ${n.title || n.typ} ${n.next_tx <= tx.now ? "gleich" : "in " + mmss(n.next_tx - tx.now)}`
          : "Im Karussell ist nichts geplant."));
  }
  now.append(nb);
  // budget
  const bud = el("section", "txcard");
  const b = tx.budget, pct = b.limit_s ? Math.min(100, (100 * b.used_s) / b.limit_s) : 0;
  const big = el("div", "big");
  big.append(el("span", "n", mins(b.used_s)), el("span", "s", `von ${mins(b.limit_s)} min in den letzten ${b.window_min} min (${num(b.percent)} %)`));
  const g = el("div", "gauge big" + (pct >= 100 ? " full" : "")), gf = el("span", "fill");
  gf.style.width = pct + "%"; g.append(gf);
  const facts = el("div", "facts");
  const fact = (k, val) => facts.append(el("span", "k", k), el("b", null, val));
  fact("Schnittstelle", tx.agw ? `${tx.interface} · Queue wird abgefragt` : `${tx.interface} · Ende berechnet`);
  fact("Heute gesendet", `${tx.today.pages} Seiten · ${tx.today.frames} Frames`);
  fact("Pause zwischen Aussendungen", `${num(tx.gap_s)} s · ${tx.burst_frames} Frame${tx.burst_frames === 1 ? "" : "s"} je Aussendung`);
  if (tx.traffic) fact("Betrieb", (["frei", "Benutzer verbunden", "Forward / Datenübertragung"][tx.traffic.level] || "?")
    + (tx.traffic.why ? ` (${tx.traffic.why})` : "") + (tx.traffic.channel_wait ? ` · ${tx.traffic.channel}, noch ${tx.traffic.channel_wait} s` : ""));
  if (tx.beacon) fact("Bake", `alle ${tx.beacon.interval_min} min · nächste ${tx.beacon.next <= tx.now ? "gleich" : "in " + mmss(tx.beacon.next - tx.now)}`);
  bud.append(el("h3", null, "Airtime-Budget"), big, g,
    el("div", "bnote", "Wird es eng, warten normale Seiten; Notfall-Seiten (Priorität 3) gehen trotzdem."), facts);
  top.append(now, bud);
  w.append(top);

  const low = el("div", "txgrid even");
  // next up
  const nx = el("section", "txcard flush");
  nx.append(el("h3", "bar", "Als Nächstes"));
  const nl = el("div", "txlist next");
  if (!tx.next.length) nl.append(el("div", "none", "keine Seiten im Karussell"));
  for (const p of tx.next) {
    const row = el("div", "r" + (p.resting ? " rest" : "") + (p.withdrawn ? " wd" : ""));
    const ti = el("span", "ti");
    if (p.withdrawn) {                       // only the short withdrawal goes out, not the page
      const n = Math.max(1, (p.withdraw_of || 1) - (p.withdraw_left || 0) + 1);
      ti.append(el("span", "tag wdtag", `Rücknahme ${Math.min(n, p.withdraw_of || n)}/${p.withdraw_of || n}`), " ",
        el("s", null, p.title || p.typ));
      ti.title = "Nur die kurze Rücknahme geht hinaus, die Hörer löschen die Seite; danach ist sie weg";
    } else ti.append((p.title || p.typ) + (p.resting ? " – ruht" : ""));
    if (p.new && !p.resting && !p.withdrawn) ti.append(" ", el("span", "tag upd", "neu"));
    if (p.pri >= 3) ti.append(" ", el("span", "tag alarm", "Notfall"));
    const off = el("button", "offbtn", "✕");
    off.type = "button";
    off.title = "Nicht mehr senden";
    off.setAttribute("aria-label", `Seite ${p.id} nicht mehr senden`);
    off.onclick = () => takeOffAir(p.id, p.title);
    const keep = p.provider === "brocastd" || p.withdrawn;      // own index/dictionary; already going
    row.append(el("span", "pg", `P${p.id}`), ti, el("span", "meta", `${p.parts} Tl`),
      el("span", "when", p.resting ? "–" : p.next_tx <= tx.now ? "gleich" : mmss(p.next_tx - tx.now)),
      keep ? el("span") : off);
    nl.append(row);
  }
  nx.append(nl);
  if (tx.off_air && tx.off_air.length) {            // taken off the air by the sysop
    nx.append(el("h3", "bar sub", "Nicht gesendet (vom Sysop genommen)"));
    const ol = el("div", "txlist off");
    for (const b of tx.off_air) {
      const row = el("div", "r");
      const again = el("button", "btn sm", "Wieder senden");
      again.type = "button";
      again.title = "Kommt mit dem nächsten Abgleich der Quelle wieder ins Karussell";
      again.onclick = async () => {
        try { await api("POST", "/tx/restore", { provider: b.provider, key: b.pkey }); toast("Kommt mit dem nächsten Abgleich der Quelle wieder."); refreshTx(); }
        catch (e) { toast(e.message, true); }
      };
      const left = b.withdraw_left;
      row.append(el("span", "pg", b.id ? `P${b.id}` : ""), el("span", "ti", b.title || `${b.provider}/${b.pkey}`),
        el("span", "meta", `noch ${left} Rücknahme${left === 1 ? "" : "n"}`), again);
      ol.append(row);
    }
    nx.append(ol);
  }
  // last sent
  const ls = el("section", "txcard flush");
  ls.append(el("h3", "bar", "Zuletzt gesendet"));
  const ll = el("div", "txlist last");
  if (!tx.recent.length) ll.append(el("div", "none", "seit dem Start noch nichts gesendet"));
  for (const p of tx.recent) {
    const row = el("div", "r");
    if (p.typ === "beacon") {                       // [beacon]: plain text, no page
      const ti = el("span", "ti beacon", p.title);
      ti.title = p.title;
      row.append(el("span", "tm", hms(p.t)), el("span", "pg", "Bake"), ti, el("span", "res ok", "✓"));
      ll.append(row);
      continue;
    }
    const ti = el("span", "ti");
    if (p.result === "withdrawn") ti.append(el("span", "tag wdtag", "Rücknahme"), " ", el("s", null, p.title || p.typ));
    else ti.append(p.title || p.typ);
    if (p.pri >= 3) ti.append(" ", el("span", "tag alarm", "Notfall"));
    const res = p.result === "ok" ? ["ok", `${p.sent}/${p.total} ✓`] : p.result === "withdrawn"
      ? ["old", `${p.sent}/${p.total} ✕`] : ["part", `${p.sent}/${p.total} ⏸`];
    const r = el("span", "res " + res[0], res[1]);
    r.title = p.result === "ok" ? "vollständig an Direwolf übergeben" : p.result === "withdrawn"
      ? "Rückzug gesendet" : "abgebrochen (Direwolf getrennt), kommt wieder";
    row.append(el("span", "tm", hms(p.t)), el("span", "pg", `P${p.id}`), ti, r);
    ll.append(row);
  }
  ls.append(ll);
  low.append(nx, ls);
  w.append(low);
  v.replaceChildren(w);
}

async function init() {
  state.view = loadView();
  state.graphic = loadGraphic();
  state.dxSort = loadDxSort();
  $("tab-cat").onclick = () => setMode("cat");
  $("tab-st").onclick = () => setMode("st");
  $("sub-filter").onchange = () => { state.sub = $("sub-filter").value; renderList().catch(e => toast(e.message, true)); };
  document.querySelectorAll("[data-f]").forEach(b => { b.onclick = () => setFilter(b.dataset.f); });
  const show = (render) => async () => {
    try { await render(); setPane("view"); } catch (e) { toast(e.message, true); }
  };
  $("btn-settings").onclick = show(renderSettings);
  $("nav-status").onclick = show(renderStatus);
  $("nav-tx").onclick = show(renderTx);
  $("hdr-tx").onclick = show(renderTx);
  $("nav-rxlog").onclick = show(() => renderRxlog(null));
  $("dictbar-details").onclick = show(renderStatus);
  $("dictbar-import").onclick = show(renderImport);
  $("back-list").onclick = () => goBack("nav");
  $("back-view").onclick = () => goBack(state.screen === "pages" && state.selected ? "list" : "nav");
  window.addEventListener("popstate", (e) => setPane((e.state && e.state.pane) || "nav", false));
  document.body.dataset.pane = "nav";
  history.replaceState({ pane: "nav" }, "");
  $("dictbar-install").onclick = async () => {
    const r = state.status.dictionary && state.status.dictionary.ready;
    if (!r || !confirm(`Dictionary v${r.version} von ${r.station} installieren?\n` +
                       "Die bisherige Datei bleibt als Sicherung erhalten.")) return;
    try {
      const res = await api("POST", "/dictionary/install-received", {});
      toast(res.message);
      await refreshStatus();
      refreshLists();
    } catch (e) { toast(e.message, true); }
  };
  $("dictbar-hide").onclick = () => {          // hidden until an even newer version is heard
    state.dictHidden = state.status.dictionary && state.status.dictionary.newest_heard;
    $("dictbar").hidden = true;
  };
  $("nav-fav").onclick = () => { state.cat = null; state.station = null; state.q = ""; setFilter("fav"); setPane("list"); };
  $("alert-open").onclick = () => { if (state.alertPage) openPage(state.alertPage.org, state.alertPage.id); };
  $("search").oninput = onSearch;
  $("goto").onkeydown = (e) => onGoto(e).catch(err => toast(err.message, true));

  try { state.settings = await api("GET", "/settings"); } catch (e) { /* shown by status */ }
  await refreshStatus();
  await refreshAlerts().catch(() => {});
  await refreshLists();
  renderEmpty();
  refreshTx().catch(() => {});                  // keeps itself going (1 s / 5 s)
  setInterval(() => { poll().catch(() => {}); }, POLL_MS);
}

document.addEventListener("DOMContentLoaded", init);
