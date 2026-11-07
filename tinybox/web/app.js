/* TinyBox sysop GUI.
 * Security: every piece of data is inserted with textContent / text nodes,
 * never innerHTML - message texts come from the air and are untrusted.
 */
"use strict";

const S = {
  csrf: "",
  status: null,
  messages: [],
  sessions: [],
  feed: [],
  filter: "all",
  search: "",
  rubric: "",          // show only the bulletins of this rubric (nav or rubrics card)
  rubrics: [],         // [rubrics] of tinybox.conf plus the ones only used by bulletins
  monQ: "",            // CR52: monitor filter text
  monKind: "",         // CR52: monitor selection (see MON_KINDS)
  monHex: (() => { try { return localStorage.getItem("tinybox.monhex") === "1"; }
                   catch (e) { return false; } })(),   // payload as hex instead of text
  view: null,        // references to live parts of the current view
  currentId: null,
  prefill: null,     // CR51: Reply -> #/compose with this
};

const ERRORS = {
  invalid_call: "Invalid callsign",
  too_large: "Message too long",
  not_found: "No such message",
  not_allowed: "Not allowed",
  invalid_value: "Invalid value",
  invalid_address: "Invalid @ address",
  duplicate: "BID already known",
  no_forward: "Forwarding is off - no private mail to another mailbox",
};

// ---- helpers ---------------------------------------------------------------

function h(tag, attrs, ...kids) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v === null || v === undefined || v === false) continue;
    if (k === "class") el.className = v;
    else if (k === "text") el.textContent = v;
    else if (k.startsWith("on")) el.addEventListener(k.slice(2), v);
    else if (k === "style") el.style.cssText = v;  // CSSOM: allowed by the CSP
    else if (k === "value") el.value = v;
    else if (k === "checked") el.checked = !!v;
    else el.setAttribute(k, v === true ? "" : v);
  }
  for (const kid of kids.flat()) {
    if (kid === null || kid === undefined || kid === false) continue;
    el.append(kid instanceof Node ? kid : document.createTextNode(String(kid)));
  }
  return el;
}

const $ = (id) => document.getElementById(id);

async function api(path, body) {
  const opts = { credentials: "same-origin", headers: {} };
  if (body !== undefined) {
    opts.method = "POST";
    opts.headers["Content-Type"] = "application/json";
    opts.headers["X-CSRF-Token"] = S.csrf;
    opts.body = JSON.stringify(body);
  }
  let res;
  try {
    res = await fetch("/api/" + path, opts);
  } catch (e) {
    throw new Error("TinyBox is not reachable");
  }
  if (res.status === 401) { location.href = "/login"; throw new Error("login required"); }
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const base = ERRORS[data.error] || data.error || ("HTTP " + res.status);
    throw new Error(data.detail && data.detail !== data.error ? base + ": " + data.detail : base);
  }
  return data;
}

let toastTimer = null;
function toast(text, bad) {
  const t = $("toast");
  t.textContent = text;
  t.className = "show" + (bad ? " bad" : "");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { t.className = ""; }, 3500);
}

function listDate(iso) {  // 2026-09-28T08:41:00Z -> 260928 08:41
  return iso.slice(2, 4) + iso.slice(5, 7) + iso.slice(8, 10) + " " + iso.slice(11, 16);
}
function fullDate(iso) { return iso.slice(0, 10) + " " + iso.slice(11, 16); }
function shortTime(iso) { return iso.slice(11, 16) + " UTC"; }
function sinceText(iso) {
  const d = new Date(iso);
  const mon = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"][d.getUTCMonth()];
  return d.getUTCDate() + " " + mon + " " + iso.slice(11, 16) + " UTC";
}
function baseCall(c) { return c.split("-")[0]; }

// ---- data refresh --------------------------------------------------------------

async function refreshStatus() {
  S.status = await api("status");
  const st = S.status;
  $("hdr-mailbox").textContent = st.mailbox;
  $("hdr-sysop").textContent = st.sysop;
  // how TinyBox reaches the radio: Direwolf does AX.25 (AGW) or TinyBox itself (KISS)
  const [label, value, ok, tip] = radioText(st);
  $("hdr-radio").textContent = label;
  $("hdr-agw").textContent = value;
  $("hdr-via").textContent = st.interface ? " via " + st.interface.toUpperCase() : "";
  $("hdr-dot").className = "dot " + (ok ? "ok" : "bad");
  $("hdr-dot").parentElement.title = tip;
  $("hdr-users").textContent = st.users + " / " + st.max_users;
  $("hdr-msgs").textContent = st.messages;
  $("hdr-unread").textContent = st.unread + " unread";
  $("hdr-since").textContent = sinceText(st.started);
  const fwdBox = $("hdr-fwd-box");
  fwdBox.hidden = !st.forward;
  if (st.forward) {
    $("hdr-fwd").textContent = st.forward.queued + " queued" +
      (st.forward.held ? " · " + st.forward.held + " held" : "");
    fwdBox.title = st.forward.lines.join("\n");   // partners and last session on hover
  }
  $("nav-msgs").textContent = st.messages;
  $("nav-ver").replaceChildren("TinyBox " + st.version, h("br"), st.web + " · local only",
                               updateHint(st.update));
  document.title = "TinyBox " + st.mailbox;
  setShutdown(st.shutdown_in, st.restart_pending);
}

// PLANUNG 24: new release on GitHub - a link under the version, nothing else.
function updateHint(u) {
  if (!u || !u.newer) return "";
  const url = String(u.url || "");
  const safe = url.startsWith("https://github.com/") ? url : "https://github.com/oe3gas/Tinybox/releases";
  return [h("br"), h("a", {class: "upd", href: safe, target: "_blank", rel: "noopener noreferrer",
                           title: u.announced ? "Bulletin in TBNEWS is out" : "No bulletin yet ([update] announce = no)",
                           text: "Update " + u.latest + " available"})];
}

// Header: AGW -> "Direwolf connected"; KISS (CR41) -> the TNC behind kisshub, e.g.
// "PK-232 ready", red while kisshub is not connected or the TNC is not in KISS.
function radioText(st) {
  const r = st.radio;
  if (!r) return ["Direwolf", st.agw, st.agw === "connected", ""];
  if (!r.connected) return ["kisshub", "not connected", false, "TinyBox has no KISS-TCP link to kisshub"];
  if (!r.tnc_state) {
    return [r.tnc || "KISS TNC", "connected", true,
            r.hub === "unreachable" ? "kisshub status query not available - TNC state unknown" : ""];
  }
  const words = { kiss: "ready", init: "initialising", down: "down" };
  return [r.tnc || "TNC", words[r.tnc_state] || r.tnc_state, r.tnc_state === "kiss", r.tnc_error || ""];
}

async function refreshMessages() {
  S.messages = await api("messages");
  await refreshRubrics();
  if (S.view && S.view.updateMessages) S.view.updateMessages();
}

/* The rubrics come from the server (order and descriptions of [rubrics], counts
 * per rubric); the nav and the dashboard card both read S.rubrics. */
async function refreshRubrics() {
  try {
    S.rubrics = await api("rubrics");
  } catch (e) { /* keep the previous list, the nav stays as it is */ }
  renderRubricNav();
}

// ---- rubrics in the nav ------------------------------------------------------------

function openRubric(name) {
  S.filter = "B";
  S.rubric = name;
  S.search = "";
  setRubricsOpen(true);
  if (location.hash === "#/messages") {
    if (S.view && S.view.updateMessages) S.view.updateMessages();
    renderRubricNav();
  } else {
    location.hash = "#/messages";                  // route() draws the list and the nav
  }
}

function setRubricsOpen(open) {
  $("nav-rubrics-list").hidden = !open;
  $("nav-rubrics").setAttribute("aria-expanded", open ? "true" : "false");
  $("nav-rubrics").querySelector(".caret").textContent = open ? "▾" : "▸";
  try { localStorage.setItem("tinybox.rubrics", open ? "1" : "0"); } catch (e) { /* private mode */ }
}

/* How long the rubric keeps its bulletins (CR40: [rubrics] NAME = desc | days). */
function keepText(r) {
  if (r.status === "refused" || r.expire_days === undefined) return "";
  return r.expire_days ? " · kept " + r.expire_days + " d" : " · kept forever";
}

function renderRubricNav() {
  const box = $("nav-rubrics-list");
  const rows = S.rubrics || [];
  const onMessages = (location.hash || "#/dashboard").startsWith("#/messages");
  box.replaceChildren(...rows.map((r) => h("a", {
    href: "#/messages",
    class: (onMessages && S.rubric === r.name ? "active" : "") + (r.status === "refused" ? " off" : ""),
    title: (r.description || r.name) + keepText(r)
           + (r.status === "refused" ? " · refused: no bulletins are taken" : "")
           + (r.status === "unlisted" ? " · not in [rubrics] of tinybox.conf" : ""),
    onclick: (e) => { e.preventDefault(); openRubric(r.name); },
  },
    h("span", { class: "nm", text: r.name }),
    h("span", { class: "count", text: r.count ? r.count + (r.unread ? " (" + r.unread + ")" : "") : "" }))));
  if (!rows.length) box.append(h("div", { class: "none", text: "No rubrics." }));
  $("nav-rubrics-count").textContent = rows.length || "";
}

async function refreshSessions() {
  S.sessions = await api("sessions");
  if (S.view && S.view.updateSessions) S.view.updateSessions();
}

const pending = { status: false, messages: false, sessions: false };
let refreshTimer = null;
function scheduleRefresh(...what) {
  for (const w of what) pending[w] = true;
  clearTimeout(refreshTimer);
  refreshTimer = setTimeout(async () => {
    const todo = { ...pending };
    pending.status = pending.messages = pending.sessions = false;
    try {
      if (todo.status) await refreshStatus();
      if (todo.messages) await refreshMessages();
      if (todo.sessions) await refreshSessions();
    } catch (e) { /* shown via header state */ }
  }, 250);
}

// ---- live feed (server-sent events) ----------------------------------------------

function startFeed() {
  const es = new EventSource("/api/feed");
  es.onopen = () => {  // the server re-sends its backlog after a reconnect
    S.feed = [];
    if (S.view && S.view.monitorBody) S.view.monitorBody.replaceChildren();
    scheduleRefresh("status", "messages", "sessions");
  };
  es.onerror = () => {
    $("hdr-dot").className = "dot bad";
    $("hdr-radio").textContent = "";
    $("hdr-agw").textContent = "TinyBox unreachable";
    $("hdr-via").textContent = "";
  };
  es.onmessage = (e) => {
    const item = JSON.parse(e.data);
    if (item.type === "event") {
      if (item.name.startsWith("message.")) scheduleRefresh("status", "messages");
      else if (item.name === "link.quality") scheduleRefresh("sessions");
      else scheduleRefresh("status", "sessions");
      return;
    }
    S.feed.push(item);
    if (S.feed.length > 600) S.feed.splice(0, S.feed.length - 500);
    if (S.view && S.view.monitorBody) appendLine(S.view.monitorBody, item);
    if (item.type === "mon") scheduleRefresh("sessions");
    else scheduleRefresh("status");
  };
}

// ---- monitor (CR52, like the client's monitor CR50) -------------------------------
// Three kinds of lines: "frame" = an AX.25 frame on the channel (KISS mode, also our
// own), "mon" = session text TinyBox sends to / gets from a station, "log" = TinyBox log.
// Every call has a colour of its own - the same call always the same colour.
const MON_KINDS = [["", "Everything"], ["frame", "Channel frames"], ["tx", "Own frames (TX)"],
  ["aprs", "APRS frames"], ["mon", "Session text"], ["log", "Log"], ["tb", "All TinyBox special frames"],
  ["chat", "chat (TBCHAT)"], ["quality", "quality (%Q)"], ["mail", "mail (TBMAIL)"],
  ["beacon", "beacon"], ["proto", "proto (//...)"]];

function callColor(call) {
  let x = 2166136261;
  for (const ch of call.replace(/\*$/, "")) x = Math.imul(x ^ ch.charCodeAt(0), 16777619) >>> 0;
  return `hsl(${x % 360}, 70%, ${62 + (x >> 9) % 12}%)`;    // light on the dark monitor
}
function callSpan(call) {
  return h("span", { class: "mc", style: "color: " + callColor(call), text: call });
}
function myCall() { return (S.status && S.status.mailbox) || "TINYBOX"; }

// Frame types in fixed colours: "I 3,5+" -> class "ft-I", "RR 4" -> "ft-RR", "U7F" -> "ft-U"
function frameClass(typ) {
  const name = String(typ || "").split(/[ +]/)[0];
  return "ft-" + (/^U[0-9A-F]{2}$/.test(name) ? "U" : name);
}
// payload as hex: "48 61 6C 6C 6F  0D ..." - a wider gap after every 8 bytes
function hexText(hex) {
  const b = (hex || "").toUpperCase().match(/../g) || [];
  return b.map((x, i) => (i && i % 8 === 0 ? " " : "") + x).join(" ");
}

function monText(it) {
  if (it.type === "frame")
    return `${it.t} ${it.tx ? "tx " : ""}${it.src} ${it.dst} ${(it.via || []).join(",")} <${it.typ}>` +
      `${it.len != null ? ` [${it.len}]` : ""} ${it.kind} ${S.monHex && it.hex ? hexText(it.hex) : it.text}` +
      (it.aprs ? " aprs" + AprsView.searchText(it) : "");
  if (it.type === "mon") return `${it.t} ${it.call} ${myCall()} ${it.text}`;
  return `${it.t} ${it.text}${S.monHex && it.hex ? " " + hexText(it.hex) : ""}`;
}
function monMatch(it) {
  const k = S.monKind;
  if (k === "frame" || k === "mon" || k === "log") { if (it.type !== k) return false; }
  else if (k === "tx") { if (it.type !== "frame" || !it.tx) return false; }
  else if (k === "aprs") { if (it.type !== "frame" || !it.aprs) return false; }
  else if (k === "tb") { if (it.type !== "frame" || !it.kind) return false; }
  else if (k) { if (it.type !== "frame" || it.kind !== k) return false; }
  const q = S.monQ.trim().toLowerCase();
  return !q || monText(it).toLowerCase().includes(q);
}

function feedLine(item) {
  if (item.type === "frame") {
    const ap = !S.monHex && AprsView.active(item);     // HEX view: raw bytes, no APRS card
    const head = h(ap ? "span" : "div", { class: ap ? "" : "line frame" + (item.tx ? " tx" : "") },
      h("span", { class: "t", text: item.t }), " ",
      h("span", { class: "rt", text: item.tx ? "TX" : "RX" }), " ",
      callSpan(item.src), " → ", ap ? AprsView.dest(item) : callSpan(item.dst));
    if (item.via && item.via.length) {
      head.append(" via ");
      item.via.forEach((v, i) => { if (i) head.append(","); head.append(callSpan(v)); });
    }
    head.append(" ", h("span", { class: "typ " + frameClass(item.typ), text: "<" + item.typ + ">" }));
    if (item.len != null) head.append(" ", h("span", { class: "plen", text: `[${item.len}]` }));  // PacLen
    if (item.kind) head.append(" ", h("span", { class: "kind " + item.kind, text: item.kind }));
    if (ap) return AprsView.card(item, head, "line frame" + (item.tx ? " tx" : ""));   // CR62
    if (S.monHex && item.hex) head.append(": ", h("span", { class: "hex", text: hexText(item.hex) }));
    else if (item.text) head.append(": " + item.text);
    return Insp.clickable(head, item);
  }
  if (item.type === "mon") {                     // ">" TinyBox to the station, "<" back
    const [a, b] = item.dir === "<" ? [item.call, myCall()] : [myCall(), item.call];
    return h("div", { class: "line mon" },
      h("span", { class: "t", text: item.t }), " ",
      h("span", { class: "rt", text: "TXT" }), " ",
      callSpan(a), " → ", callSpan(b), ": ", item.text);
  }
  const cls = item.level === "WARNING" || item.level === "ERROR" ? "warn" : "sys";
  if (S.monHex && item.hex != null)               // a UI frame TinyBox sent (also AGW mode)
    return Insp.clickable(h("div", { class: "line log" },
      h("span", { class: "t", text: item.t }), " ", h("span", { class: cls, text: `UI ${item.dst} > ` }),
      h("span", { class: "hex", text: hexText(item.hex) })), item);
  return h("div", { class: "line log" },
    h("span", { class: "t", text: item.t }), " ", h("span", { class: cls, text: item.text }));
}

// ---- frame inspector (HEX view): a click on a frame opens a bar below the monitor
// with all its bytes - offset, 16 bytes hex, decoded text; address bytes are shown
// shifted back (AX.25 stores each callsign character << 1)
const PID_NAMES = { 0xF0: "no layer 3", 0xCF: "NET/ROM", 0xCC: "IP", 0xCD: "ARP", 0x08: "segment" };
const Insp = {
  bar: null, item: null,
  clickable(line, item) {
    if (!S.monHex || !(item.raw || item.hex != null)) return line;
    line.classList.add("inspectable");
    if (item === this.item) line.classList.add("sel");
    line.title = "Inspect this frame";
    line.addEventListener("click", () => {
      this.show(item, line);
      if (item.aprs && AprsView.lensOn()) AprsView.select(item);   // HEX + lens: an APRS frame also goes to the lens
    });
    return line;
  },
  // what every byte is: [{cls, what}] - from the raw frame, or only the payload
  regions(item) {
    const b = (item.raw || item.hex || "").match(/../g)?.map((x) => parseInt(x, 16)) || [];
    if (!item.raw) return { b, map: b.map((_, i) => ({ cls: "r-info", what: "Info byte " + i, info: 0 })) };
    const ctl = item.ctl, po = item.len != null ? b.length - item.len : null;
    const map = [];
    for (let i = 0; i < b.length; i++) {
      if (i < ctl) {
        const a = Math.floor(i / 7), k = i % 7;
        const name = a === 0 ? "Destination" : a === 1 ? "Source" : "Digipeater " + (a - 1);
        const call = [item.dst, item.src, ...(item.via || [])][a] || "";
        if (k < 6) map.push({ cls: "r-addr" + (a % 2), what: `${name} ${call} · character '${String.fromCharCode(b[i] >> 1)}'`, addr: 1 });
        else map.push({ cls: "r-addr" + (a % 2), what: `${name} ${call} · SSID ${(b[i] >> 1) & 15} · ` +
          `${a < 2 ? "C" : "H"} bit ${b[i] >> 7} · reserved ${(b[i] >> 5) & 3} · last address ${b[i] & 1}`, ssid: 1 });
      } else if (po != null && i === po - 1) {
        map.push({ cls: "r-pid", what: `PID 0x${b[i].toString(16).toUpperCase().padStart(2, "0")}` +
          (PID_NAMES[b[i]] ? " · " + PID_NAMES[b[i]] : "") });
      } else if (po != null ? i < po - 1 : i < ctl + (/^(I|RR|RNR|REJ|SREJ)\b/.test(item.typ) && b.length - ctl === 2 ? 2 : 1)) {
        map.push({ cls: "r-ctl", what: `Control · <${item.typ}>` });
      } else {
        map.push({ cls: "r-info", what: "Info byte " + (i - (po != null ? po : ctl + 1)), info: 1 });
      }
    }
    return { b, map };
  },
  show(item, line) {
    if (!this.bar) return;
    this.item = item;
    document.querySelectorAll(".monitor .line.sel").forEach((x) => x.classList.remove("sel"));
    if (line) line.classList.add("sel");
    const { b, map } = this.regions(item);
    const hx = (n, w = 2) => n.toString(16).toUpperCase().padStart(w, "0");
    const detail = h("div", { class: "insp-detail", text: "Point at a byte for details." });
    const cells = [];                              // [hex span, text span] per byte
    const mark = (i, on) => cells[i].forEach((c) => c.classList.toggle("hot", on));
    const point = (i) => {
      const v = b[i];
      detail.textContent = `Offset 0x${hx(i, 4)} (${i}) · 0x${hx(v)} · ${v} · ${v.toString(2).padStart(8, "0")} · ${map[i].what}`;
    };
    const rows = [h("div", { class: "insp-row insp-colhead" },
      h("span", { class: "insp-off", text: "Offset(h)" }),
      h("span", { class: "insp-hex" }, ...Array.from({ length: 16 }, (_, k) => h("span", { class: "insp-b", text: hx(k) }))),
      h("span", { class: "insp-txt", text: "Decoded text" }))];
    for (let r = 0; r < b.length; r += 16) {
      const hexs = [], txts = [];
      for (let i = r; i < Math.min(r + 16, b.length); i++) {
        const m = map[i], v = b[i];
        const ch = m.addr ? String.fromCharCode(v >> 1) : m.ssid ? hx((v >> 1) & 15, 1) : (v >= 32 && v < 127 ? String.fromCharCode(v) : ".");
        const a = h("span", { class: "insp-b " + m.cls, text: hx(v) });
        const t = h("span", { class: "insp-c " + m.cls + (m.addr || m.ssid ? " shifted" : ""), text: ch });
        cells[i] = [a, t];
        for (const c of [a, t]) {
          c.addEventListener("mouseenter", () => { mark(i, true); point(i); });
          c.addEventListener("mouseleave", () => mark(i, false));
        }
        hexs.push(a); txts.push(t);
      }
      rows.push(h("div", { class: "insp-row" }, h("span", { class: "insp-off", text: hx(r, 8) }),
        h("span", { class: "insp-hex" }, ...hexs), h("span", { class: "insp-txt" }, ...txts)));
    }
    const title = item.type === "frame"
      ? `${item.t} ${item.tx ? "TX" : "RX"} ${item.src} → ${item.dst}${item.via && item.via.length ? " via " + item.via.join(",") : ""} <${item.typ}>`
      : `${item.t} TX UI → ${item.dst} (payload only)`;
    const legend = item.raw ? [["r-addr0", "Address"], ["r-ctl", "Control"], ["r-pid", "PID"], ["r-info", "Info"]] : [["r-info", "Info"]];
    this.bar.replaceChildren(
      h("div", { class: "insp-head" },
        h("strong", { class: "grow", text: title }),
        h("span", { class: "insp-n", text: b.length + " bytes" }),
        h("span", { class: "insp-legend" }, ...legend.map(([c, t]) => h("span", { class: "insp-key " + c, text: t }))),
        h("button", { class: "btn sm", type: "button", title: "Close (Esc)", onclick: () => this.hide() }, "Close")),
      h("div", { class: "insp-grid" }, ...rows),
      detail);
    this.bar.hidden = false;
  },
  hide() {
    this.item = null;
    if (this.bar) this.bar.hidden = true;
    document.querySelectorAll(".monitor .line.sel").forEach((x) => x.classList.remove("sel"));
  },
};
document.addEventListener("keydown", (e) => { if (e.key === "Escape" && Insp.item) Insp.hide(); });

function appendLine(box, item) {
  if (!monMatch(item)) return;
  const atBottom = box.scrollHeight - box.scrollTop - box.clientHeight < 40;
  box.append(feedLine(item));
  while (box.childElementCount > 500) box.firstChild.remove();
  if (atBottom) box.scrollTop = box.scrollHeight;
}

// ---- building blocks ---------------------------------------------------------------

function filteredMessages() {
  const q = S.search.trim().toUpperCase();
  return S.messages.filter((m) => {
    if (S.filter === "P" && m.type !== "P") return false;
    if (S.filter === "B" && m.type !== "B") return false;
    if (S.filter === "N" && m.status !== "N") return false;
    if (S.rubric && (m.type !== "B" || m.to !== S.rubric)) return false;
    if (!q) return true;
    return m.to.includes(q) || m.from.includes(q) || m.subject.toUpperCase().includes(q)
      || (S.textHits && S.textHitsFor === S.search.trim() && S.textHits.has(m.id));   // CR49
  });
}

// CR49: the text of the messages is searched in TinyBox (the list has no texts)
let textSearchTimer = 0;
function searchTexts(update) {
  clearTimeout(textSearchTimer);
  const q = S.search.trim();
  if (q.length < 2) { S.textHits = null; S.textHitsFor = ""; return; }
  textSearchTimer = setTimeout(() => {
    api("messages?q=" + encodeURIComponent(q)).then((rows) => {
      if (S.search.trim() !== q) return;
      S.textHits = new Set(rows.map((m) => m.id));
      S.textHitsFor = q;
      update();
    }).catch(() => {});
  }, 300);
}

function messagesCard(opts) {
  const compact = opts && opts.compact;
  const tbody = h("tbody");
  const foot = h("span");
  const btns = {};
  const filters = [["all", "All"], ["P", "Private"], ["B", "Bulletins"], ["N", "Unread"]];
  const seg = h("div", { class: "seg", role: "group", "aria-label": "Filter" },
    filters.map(([key, label]) => (btns[key] = h("button", {
      type: "button", "aria-pressed": String(S.filter === key),
      onclick: () => {
        S.filter = key;
        // Rubrics hold only bulletins: "Private" with a rubric still set showed nothing.
        if (key === "P" && S.rubric) { S.rubric = ""; renderRubricNav(); }
        update();
      },
    }, label))));
  const search = h("input", {
    type: "search", placeholder: "Search call, subject or text", value: S.search,
    oninput: (e) => { S.search = e.target.value; update(); searchTexts(update); },
  });
  const chip = h("button", { class: "btn sm", type: "button", title: "Show all again",
                             onclick: () => { S.rubric = ""; update(); renderRubricNav(); } });
  const head = compact ? ["Msg#", "TS", "From", "Date (UTC)", "Subject"]
                       : ["Msg#", "TS", "Size", "To", "From", "Date (UTC)", "Subject", "Origin"];

  function update() {
    const all = S.messages;
    const counts = { all: all.length, P: all.filter((m) => m.type === "P").length,
                     B: all.filter((m) => m.type === "B").length,
                     N: all.filter((m) => m.status === "N").length };
    for (const [key, label] of filters) {
      btns[key].textContent = label + " " + counts[key];
      btns[key].setAttribute("aria-pressed", String(S.filter === key));
    }
    const list = filteredMessages();
    tbody.replaceChildren(...list.map((m) => {
      const open = () => { location.hash = "#/message/" + m.id; };
      const subject = h("td", { class: "subject" },
        h("a", { href: "#/message/" + m.id, text: m.subject }));
      const cells = compact
        ? [h("td", { class: "mono", text: m.id }), h("td", { class: "mono", text: m.type + m.status }),
           h("td", { class: "mono", text: m.from }), h("td", { class: "mono", text: listDate(m.created) }), subject]
        : [h("td", { class: "mono", text: m.id }), h("td", { class: "mono", text: m.type + m.status }),
           h("td", { class: "mono", text: m.size }), h("td", { class: "mono", text: m.to }),
           h("td", { class: "mono", text: m.from }), h("td", { class: "mono", text: listDate(m.created) }),
           subject, h("td", { text: m.origin })];
      const cls = ["click", m.status === "N" ? "unread" : "", m.id === S.currentId ? "current" : ""].join(" ");
      return h("tr", { class: cls, onclick: (e) => { if (e.target.tagName !== "A") open(); } }, cells);
    }));
    if (!list.length) {
      tbody.append(h("tr", {}, h("td", { colspan: head.length, class: "subject", text: "No messages." })));
    }
    foot.textContent = "Showing " + list.length + " of " + all.length;
    chip.style.display = S.rubric ? "" : "none";      // .btn sets display: hidden is not enough
    chip.replaceChildren("Rubric " + S.rubric + " ", h("span", { "aria-hidden": "true", text: "✕" }));
  }

  const card = h("section", { class: "card", style: "flex-grow: 1" },
    h("div", { class: "card-head" },
      h("h2", { text: "Messages" }), seg, chip,
      h("label", { class: "search" }, h("span", { class: "sr-only", text: "Search" }), search),
      h("a", { class: "btn primary", href: "#/compose", text: "New message" })),
    h("div", { class: "scroll" },
      h("table", { class: "data" }, h("thead", {}, h("tr", {}, head.map((t) => h("th", { text: t })))), tbody)),
    h("div", { class: "card-foot" },
      h("span", {}, h("strong", { text: "TS" }),
        " = Type (P private, B bulletin) + Status (N new, Y read) · bold = unread"),
      foot));
  update();
  return { card, update };
}

// ---- link quality bars (PLANUNG.md 14) --------------------------------------------
// q = session.quality from the API: bars 0..5 (0 = one red bar), null = no result yet.
function barsEl(q, big) {
  const bars = q ? q.bars : null;
  const cls = "bars" + (big ? " big" : "") + (bars === null ? " none" : bars === 0 ? " red" : "")
    + (q && q.tentative ? " tent" : "");
  const kids = [];
  for (let i = 1; i <= 5; i++)
    kids.push(h("i", { class: bars !== null && i > Math.max(bars, 1) ? "off" : "" }));
  return h("span", { class: cls, title: barsTitle(q) }, ...kids);
}
function barsTitle(q) {
  if (!q) return "no link quality data";
  if (q.bars === null) return "no frames yet";
  if (q.tentative) return q.bars + " of 5 bars, tentative: fewer than " + q.min_frames + " frames, each repeat costs a bar";
  return q.bars + " of 5 bars" + (q.worst ? " - worst: " + q.worst.dir + " " + q.worst.loss + " %" : "");
}
// short text next to the bars: the direction that set them, or how many frames are missing
function barsNote(q) {
  if (!q) return "";
  if (q.bars === null || q.tentative) {
    const f = Math.max(q.frames.outgoing, q.frames.incoming);
    return f + " / " + q.min_frames + " frames" + (q.tentative ? ", tentative" : "");
  }
  return q.worst ? q.worst.dir + " " + q.worst.loss + " %" : "";
}
function clientText(c) { return c ? "TBClient+ " + (c.version || c.proto) + (c.ui ? " (UI)" : "") : ""; }
function hhmm(iso) { return iso.slice(11, 16); }
function durationText(iso) {
  const min = Math.max(0, Math.floor((Date.now() - new Date(iso).getTime()) / 60000));
  return min < 60 ? min + " min" : Math.floor(min / 60) + " h " + (min % 60) + " min";
}

function sessionsCard() {
  const count = h("span", { class: "mono", style: "font-weight: 700" });
  const list = h("div");
  function update() {
    count.textContent = S.sessions.length + " / " + (S.status ? S.status.max_users : "-");
    if (!S.sessions.length) { list.replaceChildren(h("div", { class: "empty", text: "No users connected." })); return; }
    list.replaceChildren(...S.sessions.map((s) => {
      const open = () => { location.hash = "#/user/" + encodeURIComponent(s.call); };
      const meta = [s.origin, "connect time " + hhmm(s.since), s.state];
      return h("div", { class: "srow click", tabindex: 0, role: "link",
                        onclick: (e) => { if (e.target.tagName !== "BUTTON") open(); },
                        onkeydown: (e) => { if (e.key === "Enter") open(); } },
        h("div", { class: "grow" },
          h("div", { class: "who-call", text: s.call }),
          h("div", { class: "meta", text: meta.join(" \u00b7 ") },
            s.client ? [" \u00b7 ", h("span", { class: "client", text: clientText(s.client) })] : [])),
        s.origin === "axudp" ? "" :                 // local station: no link quality
          h("div", { class: "qcell" }, barsEl(s.quality),
            h("span", { class: "sub", text: barsNote(s.quality) })),
        h("button", { class: "btn sm danger", type: "button", onclick: () => disconnect(s.call) }, "Disconnect"));
    }));
  }
  const card = h("section", { class: "card", style: "flex-shrink: 0" },
    h("div", { class: "card-head" }, h("h2", { class: "grow", text: "Connected" }), count), list);
  update();
  return { card, update };
}

async function disconnect(call) {
  if (!confirm("Disconnect " + call + "?")) return;
  try {
    await api("sessions/" + encodeURIComponent(call) + "/disconnect", {});
    toast(call + " disconnected.");
    scheduleRefresh("sessions", "status");
  } catch (e) { toast(e.message, true); }
}

// Rubrics (CR19 groundwork): [rubrics] from tinybox.conf plus the ones that only
// exist because bulletins are addressed to them. Click = show its bulletins.
const RUBRIC_STATUS = { accepted: ["ok", "accepted"], refused: ["bad", "refused"],
                        system: ["sys", "system"], unlisted: ["warn", "not in conf"] };

function rubricsCard() {
  const tbody = h("tbody");
  const foot = h("span");
  async function update() {
    if (!S.rubrics.length) await refreshRubrics();
    const rows = S.rubrics;
    tbody.replaceChildren(...rows.map((r) => {
      const [cls, label] = RUBRIC_STATUS[r.status] || ["", r.status];
      return h("tr", { class: "click", title: "Show the bulletins of " + r.name,
                       onclick: () => openRubric(r.name) },
        h("td", { class: "mono", style: "font-weight: 700", text: r.name }),
        h("td", { class: "subject", text: (r.description || "-") + keepText(r) }),
        h("td", { class: "mono", text: r.count ? r.count + (r.unread ? " (" + r.unread + " new)" : "") : "-" }),
        h("td", {}, h("span", { class: "rstat " + cls, text: label })));
    }));
    if (!rows.length) tbody.append(h("tr", {}, h("td", { colspan: 4, class: "subject", text: "No rubrics." })));
    const unlisted = rows.filter((r) => r.status === "unlisted").length;
    foot.textContent = rows.length + " rubric(s)" +
      (unlisted ? " · " + unlisted + " not in [rubrics] of tinybox.conf" : "");
  }
  const card = h("section", { class: "card", style: "flex-shrink: 0; max-height: 40vh" },
    h("div", { class: "card-head" }, h("h2", { class: "grow", text: "Rubrics" })),
    h("div", { class: "scroll" },
      h("table", { class: "data" },
        h("thead", {}, h("tr", {}, ["Rubric", "Description", "Bulletins", "Status"].map((t) => h("th", { text: t })))),
        tbody)),
    h("div", { class: "card-foot" }, foot));
  update();
  return { card, update };
}

// ---- channel (CR41, KISS mode only) ------------------------------------------------
// From the KISS stream TinyBox estimates how busy the channel is; kisshub tells the
// state of the TNC and how long frames waited in its queue. A KISS TNC reports no
// carrier detect, no signal level and no bad frames: only valid frames are counted.

const CH_OWN = "#2A6CB8", CH_OTHER = "#B07A12";     // validated pair (dataviz check)
const pctTxt = (x) => x === null || x === undefined ? "-" : (x * 100).toFixed(x < 0.1 ? 1 : 0) + " %";
const msTxt = (x) => x === null || x === undefined ? "-" : x < 1000 ? x + " ms" : (x / 1000).toFixed(1) + " s";
const clock = (t) => { const d = new Date(t * 1000); return d.toISOString().slice(11, 16); };

function loadSpark(perMin) {
  // 60 one-minute bars, own and others stacked; hover = the numbers of that minute
  const W = 360, H = 56, n = perMin.length, bw = W / n;
  const NS = "http://www.w3.org/2000/svg";
  const svg = document.createElementNS(NS, "svg");
  svg.setAttribute("viewBox", "0 0 " + W + " " + H);
  svg.setAttribute("class", "spark");
  svg.setAttribute("preserveAspectRatio", "none");
  svg.setAttribute("role", "img");
  const max = Math.max(0.05, ...perMin.map((m) => m.own + m.other));
  const base = document.createElementNS(NS, "line");
  for (const [k, v] of [["x1", 0], ["x2", W], ["y1", H - 0.5], ["y2", H - 0.5], ["class", "base"]]) base.setAttribute(k, v);
  svg.append(base);
  perMin.forEach((m, i) => {
    const x = i * bw + 1, w = Math.max(1, bw - 2);       // 2px gap between bars
    let y = H - 1;
    const g = document.createElementNS(NS, "g");
    const tip = document.createElementNS(NS, "title");
    const ago = n - 1 - i;
    tip.textContent = (ago ? ago + " min ago" : "this minute") + ": " + m.frames + " frames, busy " +
      pctTxt(m.own + m.other) + " (TinyBox " + pctTxt(m.own) + ", others " + pctTxt(m.other) + ")";
    g.append(tip);
    const hit = document.createElementNS(NS, "rect");     // hit target: the full column
    for (const [k, v] of [["x", i * bw], ["y", 0], ["width", bw], ["height", H], ["fill", "transparent"]]) hit.setAttribute(k, v);
    g.append(hit);
    for (const [val, col] of [[m.own, CH_OWN], [m.other, CH_OTHER]]) {
      if (!val) continue;
      const hgt = Math.max(1.5, val / max * (H - 4));
      const r = document.createElementNS(NS, "rect");
      for (const [k, v] of [["x", x], ["y", y - hgt], ["width", w], ["height", hgt], ["fill", col]]) r.setAttribute(k, v);
      g.append(r);
      y -= hgt + (hgt > 3 ? 1 : 0);
    }
    svg.append(g);
  });
  return svg;
}

function channelCard() {
  const state = h("span", { class: "mono", style: "font-weight: 700" });
  const body = h("div", { class: "chan" }, h("div", { class: "empty", text: "Loading ..." }));
  async function update() {
    let d;
    try { d = await api("channel"); }
    catch (e) { body.replaceChildren(h("div", { class: "empty", text: e.message })); return; }
    const r = d.radio, hub = d.hub, l1 = d.load_1min, l10 = d.load_10min;
    const [label, value, ok] = radioText({ radio: r });
    state.textContent = label + " " + value;
    state.className = "mono " + (ok ? "okt" : "badt");
    const tile = (lbl, big, sub) => h("div", { class: "tile" }, h("div", { class: "lbl", text: lbl }),
      h("div", { class: "big", text: big }), h("div", { class: "sub", text: sub }));
    const tiles = h("div", { class: "tiles" },
      tile("Busy 1 min", pctTxt(l1.total), "TinyBox " + pctTxt(l1.own) + " · others " + pctTxt(l1.other)),
      tile("Busy 10 min", pctTxt(l10.total), l10.frames + " frames" + (l10.span_sec < 600 ? " (since " + Math.round(l10.span_sec / 60) + " min)" : "")),
      tile("Wait in kisshub", hub ? msTxt(hub.queue.wait_10min.control.max_ms) : "-",
           hub ? "longest ack wait (10 min) · I frames " + msTxt(hub.queue.wait_10min.i.max_ms)
               : "no status from kisshub"));
    const legend = h("div", { class: "legend-row" },
      h("span", {}, h("i", { style: "background:" + CH_OWN }), "TinyBox"),
      h("span", { title: "stations heard and the other kisshub clients (brocastd)" },
        h("i", { style: "background:" + CH_OTHER }), "others"),
      h("span", { class: "grow" }), h("span", { class: "muted", text: "busy per minute · 60 min" }));
    const parts = [tiles, legend, loadSpark(d.per_minute)];

    if (hub) {
      const t = hub.tnc, q = hub.queue;
      const kv = (k, v) => h("div", { class: "kv2" }, h("span", { text: k }), h("strong", { class: "mono", text: v }));
      parts.push(h("h3", { class: "chan-h", text: "kisshub" }),
        h("div", { class: "kvs" },
          kv("TNC", t.name + " · " + t.state + " since " + clock(t.since) + " UTC"),
          kv("Port", t.port),
          kv("Initialised / lost", t.inits + " / " + t.port_losses),
          kv("Frames rx / tx", t.rx_frames + " / " + t.tx_frames),
          kv("Queued now", q.queued.control + " ctl · " + q.queued.i + " I · " + q.queued.ui + " UI"),
          kv("Wait avg (10 min)", "ctl " + msTxt(q.wait_10min.control.avg_ms) + " · I " + msTxt(q.wait_10min.i.avg_ms) +
                                  " · UI " + msTxt(q.wait_10min.ui.avg_ms)),
          kv("Dropped / invalid", q.dropped + " / " + (q.invalid != null ? q.invalid : "-")),   // CR74: invalid = noise from the TNC
          kv("Clients", hub.clients.length ? hub.clients.map((c) => (c.calls[0] || "client") + " (" + c.rx + "/" + c.tx + ")").join(", ") : "none")),
        ...(t.last_error ? [h("div", { class: "warnline", text: t.last_error })] : []),
        h("details", { class: "initlog" }, h("summary", { text: "TNC dialog (last " + t.init_log.length + " lines)" }),
          h("table", { class: "raw" }, h("tbody", {}, ...t.init_log.map((x) =>
            h("tr", { class: x.ok ? "" : "dim" }, h("td", { class: "mono", text: clock(x.t) }),
              h("td", { class: "mono", text: x.send }), h("td", { class: "mono desc", text: x.answer }),
              h("td", { text: x.ok ? "ok" : "-" })))))));
    } else {
      parts.push(h("div", { class: "muted pad", text: "No status from kisshub" + (d.hub_error ? ": " + d.hub_error : "") +
        " - TNC state, queue and clients unknown ([kiss] status_port)." }));
    }

    parts.push(h("h3", { class: "chan-h", text: "Heard" }),
      d.heard.length ? h("table", { class: "data" },
        h("thead", {}, h("tr", {}, ["Call", "Frames", "On air", "Last", "Via"].map((x) => h("th", { text: x })))),
        h("tbody", {}, ...d.heard.slice(0, 12).map((x) => h("tr", {},
          h("td", { class: "mono", style: "font-weight:700", text: x.call + (x.own ? " (own)" : "") }),
          h("td", { class: "mono", text: String(x.frames) }), h("td", { class: "mono", text: x.air_sec + " s" }),
          h("td", { class: "mono", text: clock(x.last) }), h("td", { class: "mono", text: x.via || "direct" })))))
        : h("div", { class: "muted pad", text: "Nothing heard yet." }));
    body.replaceChildren(...parts);
  }
  const card = h("section", { class: "card", style: "flex-shrink: 0" },
    h("div", { class: "card-head" }, h("h2", { class: "grow", text: "Channel" }), state), body,
    h("div", { class: "card-foot" }, h("span", { class: "muted",
      text: "KISS: only valid frames are counted - no carrier detect, no signal level. Air time is estimated." })));
  update();
  return { card, update };
}

function monitorCard(withLens) {
  const body = h("div", { class: "monitor" });
  const lens = withLens ? h("aside", { class: "ar-lens", "aria-label": "APRS Lense" }) : null;   // CR55
  function redraw() {
    body.replaceChildren(...S.feed.filter(monMatch).map(feedLine));
    body.scrollTop = body.scrollHeight;
  }
  const q = h("input", { type: "search", placeholder: "Filter: call, text, I, REJ ...", value: S.monQ,
                         oninput: (e) => { S.monQ = e.target.value; redraw(); } });
  const kind = h("select", { title: "Show only", onchange: (e) => { S.monKind = e.target.value; redraw(); } },
    MON_KINDS.map(([v, t]) => h("option", { value: v, text: t })));
  kind.value = S.monKind;
  const hex = h("button", { class: "btn sm hex-btn" + (S.monHex ? " on" : ""), type: "button",
                             "aria-pressed": S.monHex ? "true" : "false",
                             title: "Payload of I and UI frames as hex bytes - click a frame to inspect all its bytes" }, "HEX");
  hex.onclick = () => {
    S.monHex = !S.monHex;
    hex.classList.toggle("on", S.monHex);
    hex.setAttribute("aria-pressed", S.monHex ? "true" : "false");
    try { localStorage.setItem("tinybox.monhex", S.monHex ? "1" : "0"); } catch (e) { /* private mode */ }
    if (!S.monHex) Insp.hide();
    redraw();
  };
  const inspBar = h("div", { class: "insp", hidden: true, "aria-label": "Frame inspector" });
  Insp.bar = inspBar;
  if (Insp.item && S.monHex) queueMicrotask(() => Insp.show(Insp.item));   // page switched back
  else Insp.item = null;
  const clear = async () => {
    Insp.hide();
    S.feed = []; body.replaceChildren(); AprsView.forget();
    try { await api("monitor/clear", {}); } catch (e) { /* only this tab then */ }
  };
  const card = h("section", { class: "card", style: "flex-grow: 1" },
    h("div", { class: "card-head" },
      h("h2", { class: "grow", text: "Live monitor" }),
      h("label", { class: "search mon-q" }, h("span", { class: "sr-only", text: "Filter" }), q),
      h("label", {}, h("span", { class: "sr-only", text: "Show only" }), kind),
      AprsView.toggleButton("btn sm aprs-btn"),
      hex,
      h("button", { class: "btn sm", type: "button", onclick: clear }, "Clear")),
    lens ? h("div", { class: "mon-split" }, body, lens) : body,
    inspBar);
  const showLens = () => { if (lens) lens.hidden = !AprsView.lensOn(); };   // CR62: only in step 2
  if (lens) AprsView.attachLens(lens);
  AprsView.onChange(() => { if (card.isConnected) { showLens(); redraw(); } });
  showLens();
  redraw();
  requestAnimationFrame(() => { body.scrollTop = body.scrollHeight; });
  return { card, body };
}

function composeCard(prefill) {
  const p = prefill || {};
  let type = p.type || "P";
  const err = h("div", { class: "error", role: "alert" });
  const to = h("input", { type: "text", class: "mono", value: p.to || "", autocomplete: "off", required: true });
  const subject = h("input", { type: "text", value: p.subject || "", maxlength: "60" });
  const body = h("textarea", { rows: "12" });
  body.value = p.body || "";
  const bytes = h("span", { class: "bytes" });
  const labelP = h("label", {}, h("input", { type: "radio", name: "type", value: "P" }), "Private (P)");
  const labelB = h("label", {}, h("input", { type: "radio", name: "type", value: "B" }), "Bulletin (B)");

  function setType(t) {
    type = t;
    labelP.classList.toggle("on", t === "P"); labelP.firstChild.checked = t === "P";
    labelB.classList.toggle("on", t === "B"); labelB.firstChild.checked = t === "B";
    to.placeholder = t === "B" ? "ALL  or  TEST @ WW" : "Callsign  or  OE1ABC @ OE1XAB.#WIE.AUT.EU";
  }
  labelP.firstChild.addEventListener("change", () => setType("P"));
  labelB.firstChild.addEventListener("change", () => setType("B"));
  function count() {
    const max = S.status ? S.status.max_msg_bytes : 8192;
    const n = new TextEncoder().encode(body.value).length;
    bytes.textContent = n + " / " + max + " bytes";
    bytes.classList.toggle("over", n > max);
  }
  body.addEventListener("input", count);

  const send = h("button", { class: "btn primary", type: "submit" }, "Send");
  const form = h("form", { class: "form", onsubmit: async (e) => {
    e.preventDefault();
    err.textContent = "";
    send.disabled = true;
    try {
      const r = await api("messages", { type, to: to.value.trim().toUpperCase(),
                                         subject: subject.value, body: body.value });
      toast("Msg " + r.id + " saved.");
      location.hash = "#/message/" + r.id;
    } catch (ex) { err.textContent = ex.message; }
    finally { send.disabled = false; }
  } },
    h("fieldset", {}, h("legend", { class: "label", text: "Type" }), h("div", { class: "radios" }, labelP, labelB)),
    h("label", { class: "field" }, h("span", { class: "label", text: "To" }), to),
    h("label", { class: "field" }, h("span", { class: "label", text: "Subject" }), subject),
    h("label", { class: "field grow" }, h("span", { class: "label", text: "Message" }), body),
    err,
    h("div", { class: "form-foot" }, bytes,
      h("button", { class: "btn", type: "button", onclick: () => history.back() }, "Cancel"), send));
  setType(type);
  count();
  const card = h("section", { class: "card" },
    h("div", { class: "card-head" }, h("h2", { text: p.to ? "Reply" : "New message" })), form);
  return { card, focus: () => (p.to ? body : to).focus() };
}

// ---- views ------------------------------------------------------------------------

const main = () => $("main");

// Dashboard cards can be folded: click the title (or the caret). Which ones are
// folded is kept in the browser. Live updates only replace what is inside a card,
// so a folded card stays folded; its head (count, state) keeps updating.
const FOLD_KEY = "tinybox.folded";
function foldedSet() {
  try { return new Set(JSON.parse(localStorage.getItem(FOLD_KEY) || "[]")); }
  catch (e) { return new Set(); }
}
function foldable(card, key) {
  const head = card.querySelector(".card-head");
  const title = head.querySelector("h2");
  const btn = h("button", { class: "fold", type: "button", title: "Fold / unfold" },
    h("span", { class: "caret", "aria-hidden": "true" }));
  const set = (folded) => {
    card.classList.toggle("folded", folded);
    btn.setAttribute("aria-expanded", String(!folded));
    btn.firstChild.textContent = folded ? "\u25b8" : "\u25be";
  };
  const toggle = () => {
    const folded = !card.classList.contains("folded");
    set(folded);
    const keys = foldedSet();
    if (folded) keys.add(key); else keys.delete(key);
    try { localStorage.setItem(FOLD_KEY, JSON.stringify([...keys])); } catch (e) { /* private mode */ }
  };
  btn.addEventListener("click", toggle);
  title.classList.add("foldtitle");
  title.addEventListener("click", toggle);
  head.prepend(btn);
  set(foldedSet().has(key));
  return card;
}

function viewDashboard() {
  const msgs = messagesCard();
  const sess = sessionsCard();
  const rub = rubricsCard();
  const mon = monitorCard();
  const conn = connlogCard();
  const jlog = jlogCard();
  const kiss = S.status && S.status.interface === "kiss";
  const chan = kiss ? channelCard() : null;
  foldable(msgs.card, "messages");
  foldable(conn.card, "connlog");
  foldable(jlog.card, "jlog");
  foldable(sess.card, "connected");
  if (chan) foldable(chan.card, "channel");
  foldable(rub.card, "rubrics");
  foldable(mon.card, "monitor");
  msgs.card.classList.add("dash-msgs");
  main().className = "two";
  main().replaceChildren(h("div", { class: "col" }, msgs.card, conn.card, jlog.card),
                         h("div", { class: "col" }, sess.card, ...(chan ? [chan.card] : []), rub.card, mon.card));
  // connection log and JLOG change only when a station connects or disconnects
  let calls = S.sessions.map((s) => s.call).join(" ");
  const updateSessions = () => {
    sess.update();
    const now = S.sessions.map((s) => s.call).join(" ");
    if (now === calls) return;
    calls = now;
    conn.update();
    jlog.update();
  };
  if (chan) live(chan.update, 10);                 // also when folded: its head shows the TNC state
  return { updateMessages: () => { msgs.update(); rub.update(); }, updateSessions,
           monitorBody: mon.body };
}

function viewMessages() {
  const msgs = messagesCard();
  main().className = "one";
  main().replaceChildren(msgs.card);
  return { updateMessages: msgs.update };
}

function viewCompose() {
  const msgs = messagesCard({ compact: true });
  const comp = composeCard(S.prefill);              // CR51: Reply comes here with a prefill
  S.prefill = null;
  main().className = "two wide-right";
  main().replaceChildren(msgs.card, comp.card);
  comp.focus();
  return { updateMessages: msgs.update };
}

// CR51: list on top, the open message below it - the overview stays visible. Writing
// (New message, Reply) is its own view (#/compose), not a panel beside the reader.
function viewMessage(id) {
  const msgs = messagesCard();
  msgs.card.classList.add("list-pane");
  const article = h("article", { class: "card reader-pane" });
  main().className = "split";
  main().replaceChildren(msgs.card, article);

  function show(id) {
    S.currentId = id;
    msgs.update();                                   // mark the row
    const row = msgs.card.querySelector("tr.current");
    if (row) row.scrollIntoView({ block: "nearest" });
    article.replaceChildren(h("div", { class: "empty", text: "Loading ..." }));
    api("messages/" + id).then((m) => {
      if (S.currentId !== id) return;                // already clicked further
      renderReader(article, m, (prefill) => {
        S.prefill = prefill;
        location.hash = "#/compose";
      });
      scheduleRefresh("status", "messages");
    }).catch((e) => {
      article.replaceChildren(h("div", { class: "empty", text: e.message }));
    });
  }
  show(id);
  // another message from the list: only the reader changes, the list keeps its scroll
  return { updateMessages: msgs.update, showMessage: show };
}

function renderReader(article, m, onReply) {
  const kv = (label, value, mono, cls) =>
    h("div", { class: "kv" + (cls ? " " + cls : "") }, h("span", { class: "label", text: label }),
      h("span", { class: "v" + (mono ? " mono" : "") }, value));
  const statusTag = h("span", { class: "tag" + (m.status === "Y" ? " read" : ""),
                                text: m.status === "N" ? "NEW" : "READ" });
  const editSlot = h("div");

  const reply = () => {
    const subj = /^re:/i.test(m.subject) ? m.subject : "Re: " + m.subject;
    onReply({ type: "P", to: baseCall(m.from), subject: subj.slice(0, 60) });
  };
  const kill = async () => {
    if (!confirm("Kill message " + m.id + "?")) return;
    try {
      await api("messages/" + m.id + "/kill", {});
      toast("Msg " + m.id + " killed.");
      location.hash = "#/messages";
    } catch (e) { toast(e.message, true); }
  };
  const toggleEdit = () => {
    if (editSlot.firstChild) { editSlot.replaceChildren(); return; }
    const field = h("select", {},
      [["SUBJ", "Subject"], ["TO", "To"], ["FROM", "From"], ["TYPE", "Type (P/B)"], ["STATUS", "Status (N/Y)"]]
        .map(([v, t]) => h("option", { value: v, text: t })));
    const value = h("input", { type: "text", value: m.subject });
    const current = { SUBJ: m.subject, TO: m.to, FROM: m.from, TYPE: m.type, STATUS: m.status };
    field.addEventListener("change", () => { value.value = current[field.value]; });
    const err = h("span", { class: "error" });
    editSlot.replaceChildren(h("form", { class: "editbar", onsubmit: async (e) => {
      e.preventDefault();
      try {
        const upd = await api("messages/" + m.id + "/edit", { field: field.value, value: value.value });
        toast("Msg " + m.id + " updated.");
        renderReader(article, upd, onReply);
      } catch (ex) { err.textContent = ex.message; }
    } },
      h("label", { class: "field" }, h("span", { class: "label", text: "Field" }), field),
      h("label", { class: "field grow" }, h("span", { class: "label", text: "New value" }), value),
      h("button", { class: "btn primary", type: "submit" }, "Save"), err));
    value.focus();
  };

  article.replaceChildren(
    h("div", { class: "card-head" },
      h("div", { class: "crumb grow" }, h("a", { href: "#/messages", text: "Messages" }), "›",
        h("span", { class: "mono", text: "#" + m.id })),
      h("button", { class: "btn sm", type: "button", onclick: reply }, "Reply"),
      h("button", { class: "btn sm", type: "button", onclick: toggleEdit }, "Edit header"),
      h("button", { class: "btn sm danger", type: "button", onclick: kill }, "Kill")),
    editSlot,
    h("div", { class: "scroll" },
      h("div", { class: "reader-top" },
        h("h1", { text: m.subject }),
        h("div", { class: "meta-grid" },
          kv("From", m.from, true), kv("To", m.at ? m.to + " @ " + m.at : m.to, true),
          kv("Type / Status", [m.type === "P" ? "Private · " : "Bulletin · ", statusTag]),
          kv("Date (UTC)", fullDate(m.created), true),
          kv("Size", m.size + " bytes", true), kv("Origin", m.origin),
          kv("Msg-ID", m.msgid, true))),
      h("div", { class: "body", text: m.body })));
}

// Users and the user detail are a live dashboard: besides the feed events they poll
// every few seconds (connect time, state, bars). The timer dies with the view.
let liveTimer = null;
function live(fn, sec) {
  clearInterval(liveTimer);
  liveTimer = setInterval(() => { fn().catch(() => {}); }, sec * 1000);
}

function viewUser(call) {
  const card = h("section", { class: "card", style: "flex-shrink: 0" });   // the page scrolls, not the card
  main().className = "one";
  main().replaceChildren(card);
  const load = async () => {
    try { renderUser(card, await api("sessions/" + encodeURIComponent(call) + "/linkq")); }
    catch (e) {
      clearInterval(liveTimer);
      card.replaceChildren(
        h("div", { class: "card-head" }, h("div", { class: "crumb grow" },
          h("a", { href: "#/dashboard", text: "Dashboard" }), "\u203a", h("span", { class: "mono", text: call }))),
        h("div", { class: "empty", text: e.message }));
    }
  };
  load();
  live(load, 5);
  return { updateSessions: load };
}

function renderUser(card, d) {
  if (d.local) return renderLocalUser(card, d.session);
  const s = d.session, q = d.quality, r = d.result, w = d.window;
  const pct = (x) => x === null || x === undefined ? "-" : x.toFixed(1).replace(/\.0$/, "") + " %";
  const n = (x) => x === null || x === undefined ? "-" : String(x);

  const hero = h("div", { class: "hero" },
    h("div", { class: "grow" },
      h("div", { class: "call", text: s.call }),
      h("div", { class: "meta", text: s.origin + " \u00b7 connect time " + hhmm(s.since) +
                                      " (" + durationText(s.since) + ") \u00b7 " + s.state }),
      s.client ? h("div", { class: "meta client", text: clientText(s.client) }) : ""),
    h("div", { class: "verdict" }, barsEl(q, true),
      h("div", {},
        h("div", { class: "num" }, q && q.bars !== null ? [String(q.bars), h("small", { text: " / 5 bars" + (q.tentative ? " (tentative)" : "") })]
                                                        : h("small", { text: q ? "no frames yet" : "no data" })),
        h("div", { class: "why" }, q && q.worst ? ["worst direction: ", h("b", { text: q.worst.dir + " " + q.worst.loss + " %" }),
                                                   " \u00b7 T1 timeouts: " + q.t1] : ""))));

  // --- directions
  const worstDir = q && q.worst ? q.worst.dir : null;
  function dirBox(name, dir, desc, rows, formula) {
    if (!dir) return h("div", { class: "dir na" }, h("div", { class: "t" }, h("span", { text: name }), h("span", { class: "pct", text: "-" })),
                       h("div", { class: "d", text: desc }), h("div", { class: "f", text: "not available for this station" }));
    const cls = "dir" + (name === worstDir ? " worst" : "") + (dir.enough ? "" : " na");
    return h("div", { class: cls },
      h("div", { class: "t" }, h("span", {}, name + " ", h("span", { class: "badge" + (name === worstDir ? " warn" : ""), text: dir.label })),
        h("span", { class: "pct", text: dir.enough ? pct(dir.loss) : "-" })),
      h("div", { class: "d", text: desc }),
      h("div", { class: "f" }, ...rows.flatMap(([k, v]) => [h("span", { text: k }), h("b", { text: n(v) })])),
      h("div", { class: "formula", text: dir.enough ? formula : dir.frames
        ? dir.frames + " frames, " + dir.lost + " repeated: under " + w.min_frames + " the repeats count (5 - " + dir.lost + ")"
        : "no frames yet" }));
  }
  let dirs = h("div", { class: "empty", text: "No link quality data for this station yet." });
  if (r) {
    const o = r.outgoing, i = r.incoming, x = r.rx, wv = r.window;
    dirs = h("div", { class: "dirs" },
      dirBox("outgoing", o, "I-frames sent, how many had to be repeated",
        [["frames (i_new + i_retry)", o.frames], ["repeated (i_retry)", o.lost]],
        o.lost + " / " + o.frames + " = " + pct(o.loss)),
      dirBox("incoming", i, "I-frames received, how many we had to ask for again",
        [["frames (i_rx)", i.frames], ["REJ sent (rej_tx)", wv.rej_tx], ["repeats received (retry_rx)", wv.retry_rx]],
        "(" + wv.rej_tx + " + " + wv.retry_rx + ") / " + i.frames + " = " + pct(i.loss)),
      dirBox("rx quote", x, "chat events sent as UI frames (no ACK) and which the client asked for again (//RESEND, //LOST)",
        x ? [["events sent", x.frames], ["missed", x.lost], ["received", pct(r.rx_quote)]] : [],
        x ? "counts as outgoing if worse: " + pct(x.loss) + (o.loss !== null && x.loss <= o.loss ? " <= " + pct(o.loss) + " -> outgoing stays" : " -> used") : ""));
  }

  // --- bars from the worst direction
  // the step the worst loss lands on, before the T1 deduction (same as linkq.evaluate)
  let before = null;
  if (q && q.bars !== null && q.worst) {
    before = 0;
    for (let k = 0; k < w.steps.length; k++) if (q.worst.loss <= w.steps[k]) { before = 5 - k; break; }
  }
  const steps = h("div", { class: "steps" });
  const labels = [5, 4, 3, 2, 1];
  w.steps.forEach((lim, k) => steps.append(h("div", { class: "step" + (before === labels[k] ? " cur" : "") },
    h("div", { class: "b", text: String(labels[k]) }), h("div", { class: "l", text: "\u2264 " + lim + " %" }))));
  steps.append(h("div", { class: "step red" + (before === 0 ? " cur" : "") },
    h("div", { class: "b", text: "X" }), h("div", { class: "l", text: "> " + w.steps[w.steps.length - 1] + " %" })));
  let calc = "";
  if (q && q.bars !== null && !q.worst && r) {          // tentative: the repeats count
    const lost = Math.max(r.outgoing.frames ? r.outgoing.lost : 0, r.incoming.frames ? r.incoming.lost : 0);
    calc = h("div", { class: "calc" },
      "fewer than " + w.min_frames + " frames in every direction: 5 − repeats of the worse direction (" + lost + ")",
      " − T1 (" + q.t1 + ") = ", h("span", { class: "hl", text: q.bars + " bars (tentative)" }));
  } else if (before !== null && r) {
    const parts = [["outgoing", r.outgoing.loss], ["incoming", r.incoming.loss], ["rx quote", r.rx ? r.rx.loss : null]]
      .filter((p) => p[1] !== null).map((p) => p[0] + " " + pct(p[1]));
    calc = h("div", { class: "calc" },
      "worst loss = max(" + parts.join(", ") + ") = ", h("span", { class: "hl", text: pct(q.worst.loss) }),
      " \u2192 ", h("span", { class: "hl", text: before ? before + " bars" : "X (red bar)" }), h("br"),
      "T1 timeouts in window: ", h("span", { class: "hl", text: String(q.t1) }),
      " \u2192 max(0, " + before + " \u2212 " + q.t1 + ") = ", h("span", { class: "hl", text: q.bars + " bars" }));
  }

  // --- raw counters
  const C = d.counters, CW = d.counters_window;
  const kb = (x) => x >= 1000 ? (x / 1000).toFixed(1) + "k" : String(x);
  const rows = [
    ["i_new", "I-frames sent for the first time"], ["i_retry", "I-frames repeated (outgoing loss)"],
    ["i_rx", "I-frames received"], ["rej_tx", "REJ we sent - the station has to repeat (incoming loss)"],
    ["retry_rx", "repeated I-frames received (incoming loss)"], ["rej_rx", "REJ received - the station missed our frame"],
    ["t1_exp", "T1 timeouts - no answer at all (-1 bar each)"], ["rnr_rx", "RNR received (station busy)"],
    ["bytes_new", "payload bytes sent, net"], ["bytes_retry", "payload bytes sent again"],
    ["bytes_rx", "payload bytes received (v=2)"], ["tx_busy_ms", "ms the transmitter was busy (v=2)"]];
  const cur = [["srt", "smoothed round trip time, s"], ["t1v", "current T1 timer value, s"],
               ["unack", "frames waiting for ACK"], ["rc", "current retry count"], ["baud", "link speed (v=2)"],
               ["state", "AX.25 link state"], ["age", "link age, s"]];
  // where the counters come from: Direwolf fork (AGW 'Q') or TinyBox's own AX.25 link (KISS)
  const kiss = d.interface === "kiss";
  const src = kiss ? "TinyBox" : "Direwolf";
  let raw = h("div", { class: "empty", text: kiss
    ? "No link counters: the station has no AX.25 link to TinyBox."
    : "No Direwolf counters: the station has no radio link via Direwolf (or Direwolf has no TinyBox extension)." });
  if (C) {
    const fmt = (k, v) => k.startsWith("bytes") ? kb(v) : k === "srt" || k === "t1v" ? v.toFixed(2) : String(v);
    raw = h("table", { class: "raw" },
      h("thead", {}, h("tr", {}, h("th", { text: "Field" }), h("th", { class: "r", text: "Window" }),
                                 h("th", { class: "r", text: "Since link start" }), h("th", { text: "Meaning" }))),
      h("tbody", {},
        ...rows.map(([k, desc]) => h("tr", {}, h("td", { class: "mono", text: k }),
          h("td", { class: "r", text: CW ? fmt(k, CW[k]) : "-" }), h("td", { class: "r", text: fmt(k, C[k]) }),
          h("td", { class: "desc", text: desc }))),
        ...cur.map(([k, desc]) => h("tr", { class: "dim" }, h("td", { class: "mono", text: k }),
          h("td", { class: "r", text: "-" }), h("td", { class: "r", text: fmt(k, C[k]) }),
          h("td", { class: "desc", text: desc })))));
  }
  const pollNote = C ? (kiss ? "KISS \u00b7 own AX.25 link" : "AGW query 'Q' v=" + (C.v || "?")) +
                       " \u00b7 every " + w.poll_sec + " s" +
                       (d.poll_age !== null ? " \u00b7 last answer " + d.poll_age + " s ago" : "") : "";

  card.replaceChildren(
    h("div", { class: "card-head" },
      h("div", { class: "crumb grow" }, h("a", { href: "#/dashboard", text: "Dashboard" }), "\u203a",
        h("span", { class: "mono", text: s.call })),
      h("button", { class: "btn sm danger", type: "button", onclick: () => disconnect(s.call) }, "Disconnect")),
    h("div", { class: "detail" },
      hero,
      h("div", { class: "section" },
        h("h3", {}, "Directions ", h("span", { text: "window: last " + w.frames + " frames per direction, max. " +
                                              w.minutes + " min \u00b7 a direction counts from " + w.min_frames + " frames" })),
        dirs),
      h("div", { class: "section" },
        h("h3", {}, "Bars ", h("span", { text: "from the worst direction, minus one bar per T1 timeout in the window" })),
        steps, calc,
        ...(d.channel_load ? [h("div", { class: "legend", text: "Channel busy, last 10 min: " +
          pctTxt(d.channel_load.load_10min.total) + " (TinyBox " + pctTxt(d.channel_load.load_10min.own) +
          ", others " + pctTxt(d.channel_load.load_10min.other) + ") - not part of the bars; many T1 timeouts on a " +
          "busy channel point to collisions, on a quiet one to the radio path." })] : [])),
      h("div", { class: "section" },
        h("h3", {}, src + " counters ", h("span", { text: pollNote })),
        raw,
        h("div", { class: "legend", text: "Window = difference to the oldest sample in the window (what the bars are made of). " +
                                           "Since link start = raw counter from " + src + ". Grey rows are current values, not differences." }))));
}

// a station on the same PC over AXUDP: no radio path, so no link quality -
// connect type and time are enough
function renderLocalUser(card, s) {
  card.replaceChildren(
    h("div", { class: "card-head" },
      h("div", { class: "crumb grow" }, h("a", { href: "#/dashboard", text: "Dashboard" }), "\u203a",
        h("span", { class: "mono", text: s.call })),
      h("button", { class: "btn sm danger", type: "button", onclick: () => disconnect(s.call) }, "Disconnect")),
    h("div", { class: "detail" },
      h("div", { class: "hero" },
        h("div", { class: "grow" },
          h("div", { class: "call", text: s.call }),
          h("div", { class: "meta", text: s.origin + " \u00b7 connect time " + hhmm(s.since) +
                                          " (" + durationText(s.since) + ") \u00b7 " + s.state }),
          s.client ? h("div", { class: "meta client", text: clientText(s.client) }) : ""))));
}

function viewMonitor() {
  const mon = monitorCard(true);
  mon.card.style.minHeight = "100%";
  main().className = "one";
  main().replaceChildren(mon.card);
  return { monitorBody: mon.body };
}

// Stations (JLOG) and the connection log are dashboard cards (no menu entries of their
// own any more). They reload when a station connects or disconnects.
function jlogCard() {
  const tbody = h("tbody", {}, h("tr", {}, h("td", { colspan: 7, text: "Loading ..." })));
  const count = h("span", { class: "mono", style: "font-weight: 700" });
  async function update() {
    let rows;
    try { rows = await api("jlog"); }
    catch (e) { tbody.replaceChildren(h("tr", {}, h("td", { colspan: 7, text: e.message }))); return; }
    count.textContent = String(rows.length);
    tbody.replaceChildren(...(rows.length ? rows.map((r) => h("tr", {},
      h("td", { class: "mono", text: r.call }), h("td", { text: r.name || "" }),
      h("td", { class: "mono", text: r.loc || "" }), h("td", { class: "mono", text: r.home || "" }),
      h("td", { class: "mono", text: fullDate(r.first_seen) }),
      h("td", { class: "mono", text: fullDate(r.last_seen) }), h("td", { class: "mono subject", text: r.count })))
      : [h("tr", {}, h("td", { colspan: 7, text: "No stations logged yet." }))]));
  }
  const card = h("section", { class: "card", style: "flex-shrink: 0; max-height: 40vh" },
    h("div", { class: "card-head" }, h("h2", { class: "grow", text: "Stations (JLOG)" }), count),
    h("div", { class: "scroll" }, h("table", { class: "data" },
      h("thead", {}, h("tr", {}, ["Call", "Name", "Locator", "Home BBS", "First seen (UTC)", "Last seen (UTC)", "Connects"].map((t) => h("th", { text: t })))),
      tbody)));
  update();
  return { card, update };
}

// CR44: connection log - one row per connection, kept forever; export CSV/ADIF
function fmtDur(s) {
  s = Math.max(0, s || 0);
  return s >= 3600 ? `${Math.floor(s / 3600)}h${String(Math.floor(s % 3600 / 60)).padStart(2, "0")}m`
    : `${Math.floor(s / 60)}m${String(s % 60).padStart(2, "0")}`;
}
function fmtBytes(n) {
  return n === null || n === undefined ? "-" : n < 1000 ? String(n) : (n / 1000).toFixed(1) + " k";
}
function connlogCard() {
  const tbody = h("tbody", {}, h("tr", {}, h("td", { colspan: 8, text: "Loading ..." })));
  const filter = h("input", { type: "search", placeholder: "Filter call", class: "mono",
                              style: "width:9em", "aria-label": "Filter by call" });
  const link = (ext, label) => h("a", { class: "btn sm", text: label, href: "/api/connlog." + ext });
  const csv = link("csv", "CSV"), adi = link("adi", "ADIF");
  let rows = [];
  const show = () => {
    const f = filter.value.trim().toUpperCase();
    const base = f.split("-")[0];
    csv.href = "/api/connlog.csv" + (f ? "?call=" + encodeURIComponent(base) : "");
    adi.href = "/api/connlog.adi" + (f ? "?call=" + encodeURIComponent(base) : "");
    const list = rows.filter((r) => !f || r.call.startsWith(f));
    tbody.replaceChildren(...(list.length ? list.map((r) => h("tr", {},
      h("td", { class: "mono", text: fullDate(r.start) }),
      h("td", { class: "mono", text: fullDate(r.end) }),
      h("td", { class: "mono", text: fmtDur(r.secs) }),
      h("td", { class: "mono", text: r.call }),
      h("td", { text: r.via }),
      h("td", { class: "mono", text: fmtBytes(r.rx) + " / " + fmtBytes(r.tx) }),
      h("td", { class: "mono", title: "bytes sent on the air incl. repeats / received (Direwolf with TinyBox extension)",
                text: r.air_tx === null ? "-" : fmtBytes(r.air_tx) + " / " + fmtBytes(r.air_rx) }),
      h("td", { text: r.ended })))
      : [h("tr", {}, h("td", { colspan: 8, text: rows.length ? "No match." : "No connects logged yet." }))]));
  };
  filter.addEventListener("input", show);
  async function update() {
    try { rows = await api("connlog"); show(); }
    catch (e) { tbody.replaceChildren(h("tr", {}, h("td", { colspan: 8, text: e.message }))); }
  }
  const card = h("section", { class: "card", style: "flex-shrink: 0; max-height: 40vh" },
    h("div", { class: "card-head" }, h("h2", { class: "grow", text: "Connection log" }), filter, csv, adi),
    h("div", { class: "scroll" }, h("table", { class: "data" },
      h("thead", {}, h("tr", {}, ["Connect (UTC)", "Disconnect (UTC)", "Duration", "Call", "Via",
        "Bytes in / out", "On air out / in", "Ended"].map((t) => h("th", { text: t })))),
      tbody)));
  update();
  return { card, update };
}

function viewSettings() {
  const grid = h("div", { class: "settings-grid" });
  const file = h("span", { class: "mono" });
  main().className = "one";
  main().replaceChildren(
    h("section", { class: "card" }, h("div", { class: "card-body note" },
      "Read-only. Edit ", file, " and restart TinyBox to change settings.")),
    grid);
  api("config").then((cfg) => {
    file.textContent = cfg.file;
    delete cfg.file;
    grid.replaceChildren(...Object.entries(cfg).map(([section, values]) =>
      h("section", { class: "card" },
        h("div", { class: "card-head" }, h("h2", { class: "mono", text: "[" + section + "]" })),
        h("table", { class: "kvtable" }, h("tbody", {}, Object.entries(values).map(([k, v]) =>
          h("tr", {}, h("td", { text: k }), h("td", { text: v === null || v === "" ? "(empty)" : String(v) }))))))));
  }).catch((e) => toast(e.message, true));
  return {};
}

// ---- routing ------------------------------------------------------------------------

function route() {
  const parts = (location.hash || "#/dashboard").slice(2).split("/");
  const name = parts[0] || "dashboard";
  if (name !== "message") S.currentId = null;
  clearInterval(liveTimer);
  const navKey = name === "message" || name === "compose" ? "messages" : name === "user" ? "dashboard" : name;
  document.querySelectorAll(".side a[data-nav]").forEach((a) =>
    a.classList.toggle("active", a.dataset.nav === navKey));
  renderRubricNav();                              // Rubrik in der Seitenleiste markieren
  const views = { dashboard: viewDashboard, messages: viewMessages, compose: viewCompose,
                  monitor: viewMonitor, settings: viewSettings };   // users, jlog, connlog: on the dashboard
  if (name === "message" && /^\d+$/.test(parts[1] || "")) {
    if (S.view && S.view.showMessage) { S.view.showMessage(Number(parts[1])); return; }   // CR51
    S.view = viewMessage(Number(parts[1]));
  }
  else if (name === "user" && parts[1]) S.view = viewUser(decodeURIComponent(parts[1]));
  else S.view = (views[name] || viewDashboard)();
  main().scrollTop = 0;
}

// Shutdown / restart with warning: the stations get 60 s (button turns into "Cancel").
let shutdownAt = null, shutdownTimer = null, restartMode = false;

function setShutdown(left, restart) {
  shutdownAt = left === null || left === undefined ? null : Date.now() + left * 1000;
  if (restart !== undefined) restartMode = !!restart;
  tickShutdown();
  if (shutdownAt && !shutdownTimer) shutdownTimer = setInterval(tickShutdown, 1000);
}

function tickShutdown() {
  const bs = $("btn-shutdown"), br = $("btn-restart");
  if (shutdownAt === null) {
    clearInterval(shutdownTimer); shutdownTimer = null;
    bs.textContent = "Shutdown"; br.textContent = "Restart";
    bs.disabled = br.disabled = false;
    return;
  }
  const left = Math.max(0, Math.round((shutdownAt - Date.now()) / 1000));
  (restartMode ? br : bs).textContent = `Cancel ${restartMode ? "restart" : "shutdown"} (${left} s)`;
  (restartMode ? bs : br).disabled = true;
  if (left === 0 && Date.now() - shutdownAt > 2000) {
    clearInterval(shutdownTimer); shutdownTimer = null;
    stopped(restartMode);
  }
}

// After a restart the page waits until TinyBox answers again and reloads itself.
function stopped(restart) {
  $("stopped").hidden = false;
  if (!restart) return;
  $("stopped-title").textContent = "TinyBox restarts ...";
  $("stopped-text").textContent = "This page reloads as soon as TinyBox is back.";
  let tries = 0;
  const wait = setInterval(async () => {
    tries++;
    try {
      const r = await fetch("/api/status", { credentials: "same-origin", cache: "no-store" });
      if (r.ok || r.status === 401) { clearInterval(wait); location.reload(); }
    } catch (e) { /* not back yet */ }
    if (tries > 90) {
      clearInterval(wait);
      $("stopped-text").textContent = "TinyBox did not come back - check the TinyBox window.";
    }
  }, 2000);
}

async function shutdown(restart) {
  const word = restart ? "restart" : "shutdown";
  try {
    if (shutdownAt !== null) {
      if (!confirm(`Call off the ${word}? The stations are told.`)) return;
      await api("shutdown/cancel", {});
      setShutdown(null);
      toast(restart ? "Restart cancelled" : "Shutdown cancelled");
      return;
    }
    const users = S.status ? S.status.users : 0;
    const q = restart
      ? (users ? `Restart TinyBox in 60 seconds?\n${users} connected station(s) get a system ` +
                 "message now and are disconnected then. tinybox.conf is checked first."
               : "Restart TinyBox now? No station is connected. tinybox.conf is checked first.")
      : (users ? `Stop TinyBox in 60 seconds?\n${users} connected station(s) get a ` +
                 "system message now and are disconnected then."
               : "Stop TinyBox now? No station is connected.");
    if (!confirm(q)) return;
    const r = await api("shutdown", { delay: 60, restart: !!restart });
    if (r.delay) { setShutdown(r.delay, restart); toast(`${restart ? "Restart" : "Shutdown"} in ${r.delay} s - stations warned`); }
    else stopped(restart);
  } catch (e) { toast(e.message, true); }
}

async function init() {
  $("btn-shutdown").addEventListener("click", () => shutdown(false));
  $("btn-restart").addEventListener("click", () => shutdown(true));
  window.addEventListener("hashchange", route);
  let offen = true;                               // Rubriken standardmaessig aufgeklappt
  try { offen = localStorage.getItem("tinybox.rubrics") !== "0"; } catch (e) { /* private mode */ }
  setRubricsOpen(offen);
  $("nav-rubrics").addEventListener("click",
    () => setRubricsOpen($("nav-rubrics-list").hidden));
  try {
    S.csrf = (await api("session")).csrf;
    await refreshStatus();
    S.messages = await api("messages");
    S.sessions = await api("sessions");
    await refreshRubrics();
  } catch (e) { toast(e.message, true); }
  route();
  startFeed();
}

document.addEventListener("DOMContentLoaded", init);
