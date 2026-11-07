/* TinyBox client - web GUI.
 * Everything that comes from the air is untrusted: only textContent, never innerHTML.
 * Emojis never go over the air as Unicode (PLANUNG.md 12.6):
 *   stage 1  classic emoticons  :-) ;-) :-D :-( ... (table in emoji.json, CR28):
 *            typed ones turn into the emoji at once, emojis with an ASCII form
 *            always go on air as that form (readable at a terminal)
 *   stage 2  ~XY  (two base-36 characters, table in emoji.json), "~~" = a real tilde
 */
"use strict";

const $ = (id) => document.getElementById(id);
let S = null;                 // last snapshot from /api/state
let EMO = { emoticons: [], codes: {} };
let SYMNAMES = {};
let STK = {};                  // CR11: sticker name -> {file, title}
let STK_LIST = [];             // in the order of stickers.json ("73" would sort first in STK)
const STK_RE = /^\[STK\]([A-Z0-9]{1,4})$/;
let selected = null;          // message id with open reaction bar
let pickerMode = "input";     // input | react
const QUICK = ["👍", "❤️", "😂", "😮", "🙁", "📻"];

// ---------------------------------------------------------------- helpers
function el(tag, cls, text) {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text !== undefined && text !== null) e.textContent = text;
  return e;
}
const noVS = (s) => s.replace(/️/g, "");
function hhmm(unix) {
  const d = new Date(unix * 1000);
  return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

async function api(path, data) {
  const r = await fetch("/api/" + path, {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-TBClient": "1" },
    body: JSON.stringify(data || {}),
  });
  return r.ok;
}

// ---------------------------------------------------------------- emojis
let emoToWire = [];           // [emoji without VS, wire code, is emoticon], longest first
let wireRe = null;            // what arrives: codes and emoticons
let liveRe = null;            // what is being typed: an emoticon just completed
let EMOTICONS = [];           // {wire, aliases, emoji, also} (emoji.json v3, CR28)
const EMOTICON_EMOJI = {};    // every known form -> the emoji shown for it
const BOUNDARY = "\\s.,!?;:()\\[\\]\"'";   // what may stand next to an emoticon

function initEmoji() {
  // v3 entries, or the old [form, emoji] pairs of an older emoji.json
  EMOTICONS = (EMO.emoticons || []).map((e) => Array.isArray(e)
    ? { wire: e[0], aliases: [], emoji: e[1], also: [] } : e);
  const pairs = [], ascii = new Set();
  for (const e of EMOTICONS) {
    for (const form of [e.wire, ...(e.aliases || [])]) EMOTICON_EMOJI[form] = e.emoji;
    for (const x of [e.emoji, ...(e.also || [])]) {
      pairs.push([noVS(x), e.wire, true]);
      ascii.add(noVS(x));
    }
  }
  // an emoji with an ASCII form never goes as a code (the code still decodes)
  for (const [k, e] of Object.entries(EMO.codes)) if (!ascii.has(noVS(e))) pairs.push([noVS(e), "~" + k, false]);
  pairs.sort((a, b) => b[0].length - a[0].length);
  emoToWire = pairs;
  const forms = Object.keys(EMOTICON_EMOJI).sort((a, b) => b.length - a.length)
    .map((c) => c.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")).join("|");
  // emoticons only as separate words (also right after punctuation: "Hallo!:-)"),
  // so "QTH:Pinkafeld" and "http://" stay text
  wireRe = new RegExp("~~|~([0-9A-Za-z]{2})|(^|[" + BOUNDARY + "])(" + forms + ")(?=$|[" + BOUNDARY + "])", "g");
  liveRe = new RegExp("(^|[" + BOUNDARY + "])(" + forms + ")([\\s.,!?;:])$");
}

/* Just typed an emoticon and a space or punctuation after it: show the emoji
 * at once (CR28). Only the part before the cursor is looked at. */
function liveEmoticon(i) {
  if (!liveRe) return;
  const a = i.selectionStart;
  if (a == null || i.selectionEnd !== a) return;
  const m = i.value.slice(0, a).match(liveRe);
  if (!m) return;
  const emoji = EMOTICON_EMOJI[m[2]];
  if (!emoji) return;
  const start = a - m[2].length - m[3].length;
  i.value = i.value.slice(0, start) + emoji + i.value.slice(start + m[2].length);
  i.selectionStart = i.selectionEnd = start + emoji.length + m[3].length;
}

/* The emojis that have an ASCII form (cheapest and readable at a terminal). */
function asciiEmojis() {
  const out = [];
  for (const e of EMOTICONS) for (const x of [e.emoji, ...(e.also || [])]) if (!out.includes(x)) out.push(x);
  return out;
}

function wireToText(wire) {
  return wire.replace(wireRe, (m, code, pre, emo) => {
    if (m === "~~") return "~";
    if (code !== undefined) return EMO.codes[code.toUpperCase()] || "[?]";   // newer client sent it
    return pre + (EMOTICON_EMOJI[emo] || emo);
  });
}

/* Input text (may contain emojis) -> what goes over the air. Returns
 * {wire, bad} - bad = emojis that are not in the table (not sent). */
function textToWire(text) {
  let s = noVS(text).replace(/~/g, "~~");
  for (const [e, code, emoticon] of emoToWire) {
    if (!s.includes(e)) continue;
    s = s.split(e).join(emoticon ? "\u0001" + code + "\u0002" : code);
  }
  // emoticons need spaces around them (else the TinyBox side sees plain text)
  s = s.replace(/\s*\u0001/g, (m, off) => (off === 0 ? "" : " "))
       .replace(/\u0002\s*/g, (m, off, all) => (off + m.length >= all.length ? "" : " "));
  const bad = s.match(/\p{Extended_Pictographic}/gu);
  return { wire: s.trim(), bad: bad ? [...new Set(bad)] : [] };
}

/* What the picker offers, in groups (emoji.json "picker"). Codes in "hidden"
 * are still shown when they arrive, but not offered any more (CR2). */
function emojiGroups() {
  const ascii = asciiEmojis();
  const first = ascii.length ? [{ name: "Smileys (ASCII, cheapest)", items: ascii }] : [];
  if (Array.isArray(EMO.picker) && EMO.picker.length) {
    const seen = new Set(ascii.map(noVS));
    return [...first, ...EMO.picker.map((g) => ({ name: g.name, items: g.items.filter((e) => !seen.has(noVS(e))) }))
      .filter((g) => g.items.length)];
  }
  // old table without groups: everything in code order
  const hidden = new Set(EMO.hidden || []);
  const codes = Object.entries(EMO.codes).filter(([k]) => !hidden.has(k))
    .sort((a, b) => (a[0] < b[0] ? -1 : 1)).map(([, e]) => e);
  return [...first, { name: "", items: codes }];
}

// ---------------------------------------------------------------- rich text
/* Shown text -> DOM nodes, without innerHTML (text from the air is untrusted).
 *   `mono`   monospace, e.g. ASCII art (nothing else is formatted inside)
 *   _bold_   bold, only as a whole word: OE3GAS_1 or file_name stay text
 *   http(s)://... and www.... become links
 * The text goes over the air unchanged, the formatting happens only here. */
const URL_RE = /\b(?:https?:\/\/|www\.)[^\s<>"]+/gi;
const BOLD_RE = /(^|[\s(\["'])_([^\s_](?:[^_]*[^\s_])?)_(?=$|[\s.,!?;:)\]"'])/g;

function addBold(parent, text) {
  let last = 0;
  for (const m of text.matchAll(BOLD_RE)) {
    const start = m.index + m[1].length;
    parent.append(text.slice(last, start), el("b", "", m[2]));
    last = m.index + m[0].length;
  }
  parent.append(text.slice(last));
}

function addLinks(parent, text) {
  let last = 0;
  for (const m of text.matchAll(URL_RE)) {
    let url = m[0];
    const trail = url.match(/[.,!?;:)\]'"]+$/);       // "see www.oevsv.at." -> without the dot
    if (trail) url = url.slice(0, -trail[0].length);
    if (!url) continue;
    addBold(parent, text.slice(last, m.index));
    const a = el("a", "", url);
    a.href = /^https?:\/\//i.test(url) ? url : "http://" + url;
    a.target = "_blank"; a.rel = "noopener noreferrer";
    a.onclick = (ev) => ev.stopPropagation();       // no reaction bar when opening a link
    parent.append(a);
    last = m.index + url.length;
  }
  addBold(parent, text.slice(last));
}

function richText(parent, text) {
  const parts = text.split("`");
  // an odd number of backticks: the last one has no partner and stays a character
  const closed = parts.length % 2 === 1 ? parts.length : parts.length - 1;
  for (let i = 0; i < parts.length; i++) {
    if (i % 2 === 1 && i < closed) parent.append(el("code", "mono", parts[i]));
    else addLinks(parent, (i === closed && i > 0 ? "`" : "") + parts[i]);
  }
}

/* A message that is just one emoji is shown big (CR1). */
const segmenter = typeof Intl !== "undefined" && Intl.Segmenter ? new Intl.Segmenter() : null;
function isSingleEmoji(text) {
  const t = text.trim();
  if (!t || !/\p{Extended_Pictographic}/u.test(t)) return false;
  if (segmenter) return [...segmenter.segment(t)].length === 1;
  return [...noVS(t)].length === 1;
}

/* "@OE3GAS" or "@oe3gas-9" in a line from someone else -> highlight (CR15). */
function mentionsMe(text) {
  if (!S) return false;
  const base = baseCall(S.mycall).replace(/[^A-Z0-9]/g, "");
  return new RegExp(`(^|[^A-Za-z0-9])@${base}(-\\d{1,2})?(?![A-Za-z0-9])`, "i").test(text);
}

// ---------------------------------------------------------------- avatars
const PAL = [["#CECBF6", "#3C3489"], ["#9FE1CB", "#085041"], ["#F5C4B3", "#712B13"],
             ["#F4C0D1", "#72243E"], ["#B5D4F4", "#0C447C"], ["#C0DD97", "#27500A"],
             ["#FAC775", "#633806"], ["#D3D1C7", "#444441"]];

function baseCall(c) { return c.toUpperCase().split("-")[0].split("/")[0]; }
function fnv(s) {
  let h = 2166136261;
  for (const ch of s) { h ^= ch.charCodeAt(0); h = Math.imul(h, 16777619); }
  return h >>> 0;
}
function splitCall(c) {
  const m = baseCall(c).match(/^([A-Z0-9]*?\d)([A-Z]+)$/);
  return m ? [m[1], m[2]] : ["", baseCall(c)];
}

function symbolEl(sym) {
  if (!sym || sym.length !== 2) return null;
  const i = sym.charCodeAt(1) - 33;
  if (i < 0 || i > 93) return null;
  const e = el("span", "sym " + (sym[0] === "/" ? "t0" : "t1"));
  e.style.backgroundPosition = `${(i % 16) / 15 * 100}% ${Math.floor(i / 16) / 5 * 100}%`;
  e.title = SYMNAMES[sym] || sym;
  return e;
}

function avatar(call, sym, small) {
  const [bg, fg] = PAL[fnv(baseCall(call)) % PAL.length];
  const [p, s] = splitCall(call);
  const a = el("div", "av" + (small ? " sm" : ""));
  a.style.background = bg; a.style.color = fg;
  a.title = call;
  if (p) a.append(el("span", "p", p));
  a.append(el("span", "s", s));
  const se = symbolEl(sym);
  if (se) {
    a.classList.add("badged");
    const b = el("span", "badge"); b.append(se); a.append(b);
  }
  return a;
}
const symOf = (call) => (S && S.symbols[call]) || "";

// ---------------------------------------------------------------- rendering
function render() {
  if (!S) return;
  $("me-call").textContent = S.mycall;
  $("version").textContent = S.client_version;
  $("off-tb").textContent = S.tinybox;
  $("me-avatar").replaceChildren(avatar(S.mycall, S.my_symbol, true));
  renderTop();
  renderViewBtns();
  renderFreq();
  autoTerm();
  renderTerm();
  $("off-reason").textContent = endedText() || S.reason || "";
  $("offline").classList.toggle("hidden", S.state !== "offline");
  $("pick").classList.toggle("hidden", !(S.state === "online" && S.mode === "tinybox" && !S.board && S.boards.length));
  $("conn-info").textContent = `${S.mycall} → ${S.tinybox} via ${S.link}` +
    (S.state === "online" ? (S.mode === "terminal" ? ", terminal (no TinyBox)"
      : S.ui ? ", chat as UI frames (heard directly)" : ", chat as I-frames") : "") +
    (S.tinybox !== S.home ? `. Mailbox: ${S.home}` : "");
  const inBoard = !!S.board;
  if (!inBoard && quoteTo) setQuote(null);
  $("input").disabled = !inBoard; $("btn-send").disabled = !inBoard;
  if (!cryMode && !quoteTo) $("input").placeholder = inBoard ? `Message to ${S.board.name}` : "Join a board first";
  $("btn-cry").disabled = !inBoard;
  $("btn-stk").disabled = !inBoard || !Object.keys(STK).length;
  $("btn-img").disabled = !(inBoard && S.board.img);
  $("btn-img").title = inBoard && S.board.img ? `Send a picture (max. ${kbText(S.board.img)})`
    : inBoard ? "No pictures in this board" : "Picture";
  renderMail();
  renderProfile();
  renderSys();
  renderUpdate();
  checkFetch();
  for (const r of document.querySelectorAll('input[name="histmode"]')) r.checked = r.value === S.history_mode;
  renderMailbox();
  renderBoards();
  renderNav();
  renderPeople();
  $("board-head").classList.toggle("hidden", !S.board);
  if (S.board) {
    const b = S.boards.find((x) => x.n === S.board.n) || {};
    $("bh-name").textContent = S.board.name;
    $("bh-desc").textContent = `· ${b.desc || ""} · ` +
      (S.board.keep === "live" ? "live, nothing stored" : `history ${S.board.keep}`);
  }
  renderMessages();
}

/* Joining a board (CR24): the tapped board stays coloured until the TinyBox
   reports us in it (on radio this can take a while). */
let joining = null;           // {n, since}
const JOIN_WAIT_MS = 120000;

function joinBoard(n) {
  joining = { n, since: Date.now() };
  renderBoards(); renderNav();
  api("join", { board: n }).then((ok) => { if (!ok) { joining = null; renderBoards(); renderNav(); } });
}

function isJoining(b) {
  if (!joining) return false;
  if (S.state !== "online" || (S.board && S.board.n === joining.n)
      || Date.now() - joining.since > JOIN_WAIT_MS) {
    joining = null;
    return false;
  }
  return joining.n === b.n;
}

function renderBoards() {
  const nav = $("boards");
  nav.replaceChildren();
  if (S.state !== "online") return;
  for (const b of S.boards) {
    const active = S.board && S.board.n === b.n;
    const c = el("button", "chip" + (active ? " active" : isJoining(b) ? " joining" : ""), b.name);
    c.title = b.desc + (b.keep === "live" ? " (live)" : ` (history ${b.keep})`);
    c.append(el("span", "n", b.keep === "live" ? "live" : b.keep));
    c.onclick = () => { if (!active) joinBoard(b.n); };
    nav.append(c);
  }
  if (S.board) {                       // phone: leave the board right here (CR6)
    const lv = el("button", "chip leave", "Leave ✕");
    lv.title = `Leave ${S.board.name}`;
    lv.onclick = () => api("leave");
    nav.append(lv);
  }
}

let mailDismissed = 0;
try { mailDismissed = +localStorage.getItem("tbc-mail-dismissed") || 0; } catch (e) { /* none */ }

function renderMail() {
  const n = S.mail ? S.mail.count : 0;
  const show = n > 0 && S.mail.at > mailDismissed;
  $("mail-banner").classList.toggle("hidden", !show);
  if (show) {
    $("mb-count").textContent = `${n} new message${n === 1 ? "" : "s"}`;
    $("mb-text").textContent = `for ${S.mycall.split("-")[0]} at ${S.tinybox} · ${hhmm(S.mail.at)}`;
  }
  $("mb-sync").disabled = !!(S.sync && S.sync.running);
  const unread = S.mailbox ? S.mailbox.unread : 0;
  document.title = (unread ? `(${unread}) ` : "") + "TinyBox";
}

/* Newer client (CR18). Two cases:
 *  - the TinyBox knows a newer client (S.update) -> "please git pull", button to
 *    the feature bulletin in the rubric TBNEWS
 *  - the client program was updated, but this page is still the old one -> reload */
const PAGE_VERSION = (document.querySelector('meta[name="tbc-version"]') || {}).content || "";
let updDismissed = "";
let relDismissed = "";                     // PLANUNG 24: GitHub release, dismissed separately
try { updDismissed = localStorage.getItem("tbc-upd-dismissed") || ""; } catch (e) { /* none */ }
try { relDismissed = localStorage.getItem("tbc-rel-dismissed") || ""; } catch (e) { /* none */ }
let newsWanted = null;                     // {id, seen}: bulletin to open after the sync

function renderUpdate() {
  const stale = PAGE_VERSION && !PAGE_VERSION.startsWith("__") && S.client_version !== PAGE_VERSION;
  const u = S.update;
  const r = S.release;                     // PLANUNG 24: newer release on GitHub
  const tbShow = !!u && u.cur !== updDismissed;
  const relShow = !tbShow && !!r && r.latest !== relDismissed;
  const show = stale || tbShow || relShow;
  $("upd-banner").classList.toggle("hidden", !show);
  if (!show) return;
  const t = $("upd-text");
  if (stale) {
    t.replaceChildren("The client was updated to ", el("b", "", S.client_version),
                      " - reload the page to use it.");
  } else if (tbShow) {
    t.replaceChildren("New client version ", el("b", "", u.cur), ` available (you have ${S.client_version}). ` +
                      "Get it with git pull and restart the client.");
  } else {
    const link = el("a", "", "on GitHub");
    const url = String(r.url || "");
    link.href = url.startsWith("https://github.com/") ? url : "https://github.com/oe3gas/Tinybox/releases";
    link.target = "_blank";
    link.rel = "noopener noreferrer";
    t.replaceChildren("New TinyBox release ", el("b", "", r.latest), " ", link,
                      ` (you have ${r.current}). Get it with git pull and restart the client.`);
  }
  $("upd-reload").classList.toggle("hidden", !stale);
  $("upd-news").classList.toggle("hidden", stale || !tbShow || !u.news);
  $("upd-close").classList.toggle("hidden", stale);
  // feature bulletin asked for: open it as soon as the sync has fetched it
  const running = !!(S.sync && S.sync.running);
  if (newsWanted && running) newsWanted.seen = true;
  if (newsWanted && newsWanted.seen && !running) {
    const id = newsWanted.id;
    newsWanted = null;
    openFolder("b:TBNEWS");
    openMessage(id);
  }
}

// System message of the TinyBox (sysop shuts down): red banner with countdown.
let sysDismissed = 0;
function renderSys() {
  const m = S.sysmsg;
  const show = !!m && m.at !== sysDismissed &&
    !(m.left < 0 && Date.now() / 1000 - m.at > 60);        // "called off" for one minute
  $("sys-banner").classList.toggle("hidden", !show);
  if (!show) return;
  const cancelled = m.left < 0;
  const left = Math.max(0, m.left - Math.floor(Date.now() / 1000 - m.at));
  $("sys-banner").classList.toggle("info", cancelled);
  $("sys-text").textContent = cancelled ? "Shutdown called off - the TinyBox stays on."
    : `${S.tinybox} shuts down in ${left} s - please disconnect.`;
  $("sys-text").title = m.text;
  $("sys-disc").classList.toggle("hidden", cancelled || S.state === "offline");
}
setInterval(() => { if (S) renderSys(); }, 1000);

function renderNav() {
  const box = $("nav-boards");
  box.replaceChildren();
  if (S.state !== "online" || !S.boards.length) {
    box.append(el("p", "muted small pad", S.state === "online" ? "No boards" : "Not connected"));
    return;
  }
  for (const b of S.boards) {
    const active = S.board && S.board.n === b.n;
    const users = active ? S.members.length : b.users;
    const it = el("button", "nav-item" + (active && view === "chat" ? " active"
                                          : isJoining(b) ? " joining" : ""));
    const name = el("span", "", b.name + " ");
    if (b.keep === "live") name.append(el("span", "n", "live"));
    it.append(name, el("span", "n", String(users)));
    it.title = b.desc;
    it.onclick = () => { setView("chat"); if (!active) joinBoard(b.n); };
    box.append(it);
  }
}

function ago(sec) {
  if (sec < 60) return "just now";
  if (sec < 3600) return `${Math.floor(sec / 60)} min ago`;
  return `${Math.floor(sec / 3600)} h ago`;
}

/* Link quality (PLANUNG.md 14.4): 5 bars, grey = no result yet. */
const QTEXT = { 0: "bad link, more than half lost", 1: "poor link", 2: "weak link", 3: "fair link",
                4: "good link", 5: "very good link" };
function qualityBars(call) {
  if (!S.quality || !(call in S.quality)) return null;
  const n = S.quality[call];                    // 0..5, null = not enough data yet
  const known = n !== null && n !== undefined;
  const box = el("span", "qbars" + (known ? ` q${n}` : " qnone"));
  box.title = known ? `${QTEXT[n]} (${n}/5)` : "link quality: not enough data yet";
  // 0 = a single red bar
  for (let i = 1; i <= 5; i++) box.append(el("i", known && (i <= n || (n === 0 && i === 1)) ? "on" : ""));
  return box;
}

// own chat over AXUDP or the telnet test port: no radio path, no link quality
function localLink() { return S.chat_link === "axudp" || S.chat_link === "telnet"; }

function personRow(call, sym, note, member) {
  const li = el("li");
  const txt = el("div", "ptxt");
  txt.append(el("div", "c", call));
  if (note) txt.append(el("div", "x", note));
  li.append(avatar(call, sym, true), txt);
  const local = call === S.mycall && localLink();
  const q = local ? null : qualityBars(call);
  if (q) li.append(q);
  // CR33: tap = the numbers behind the bars - only where there are bars; a station
  // over local AXUDP has none (the TinyBox measures nothing for it)
  if (member && !local && ((S.quality && call in S.quality) || (S.linkq && S.linkq[call]))) {
    li.classList.add("tap");
    li.onclick = () => openLink(call);
  }
  return li;
}

/* --- link quality detail (CR33): what the TinyBox measured for one station ----- */
let linkCall = null;                     // station shown in #linkdlg, null = closed

function openLink(call) {
  linkCall = call;
  renderLink();
  $("linkdlg").classList.remove("hidden");
}
function closeLink() { linkCall = null; $("linkdlg").classList.add("hidden"); }

const QSTEPS_DEFAULT = [5, 10, 20, 35, 50];
function pct(lost, frames) { return frames ? Math.round(1000 * lost / frames) / 10 : null; }
function fmtPct(p) { return p === null || p === undefined ? "–" : p + " %"; }

function renderLink() {
  if (!linkCall || !S) return;
  const body = $("linkdlg-body");
  $("linkdlg-title").textContent = linkCall;
  body.replaceChildren();
  const q = S.linkq && S.linkq[linkCall];
  const bars = S.quality ? S.quality[linkCall] : undefined;
  const cfg = S.qcfg || {};
  const steps = cfg.steps && cfg.steps.length === 5 ? cfg.steps : QSTEPS_DEFAULT;
  const minFrames = cfg.min_frames || 20;

  // headline: big bars + verdict
  const head = el("div", "lq-head");
  const big = qualityBars(linkCall);
  if (big) { big.classList.add("big"); head.append(big); }
  const verdict = el("div", "lq-verdict");
  if (bars === null) verdict.append(el("div", "", "not enough frames yet"));
  else if (bars === undefined) verdict.append(el("div", "", "no link data"));
  else verdict.append(el("div", "lq-num", `${bars} / 5`), el("div", "muted small", QTEXT[bars]));
  head.append(verdict);
  body.append(head);

  if (!q) {
    body.append(el("p", "muted", S.ui
      ? "The TinyBox sends the numbers behind the bars every few minutes (when they change). Nothing received for this station yet."
      : "Details come only on radio connections to a TinyBox with member numbers (CR33)."));
    return;
  }
  // directions, as the TinyBox computes them (linkq.py): the worst one makes the bars
  const dirs = [
    { name: "outgoing", label: `TinyBox → ${linkCall}`, frames: q.out_frames, lost: q.out_retry,
      rows: [["frames", q.out_frames], ["repeated", q.out_retry]],
      formula: `${q.out_retry} / ${q.out_frames}` },
    { name: "incoming", label: `${linkCall} → TinyBox`, frames: q.in_frames, lost: q.rej_tx + q.retry_rx,
      rows: [["frames", q.in_frames], ["REJ sent", q.rej_tx], ["repeats received", q.retry_rx]],
      formula: `(${q.rej_tx} + ${q.retry_rx}) / ${q.in_frames}` },
  ];
  if (q.rx_sent) dirs.push({ name: "rx quote", label: "chat frames heard", frames: q.rx_sent, lost: q.rx_missed,
    rows: [["events sent", q.rx_sent], ["missed", q.rx_missed]], formula: `${q.rx_missed} / ${q.rx_sent}` });
  for (const d of dirs) { d.enough = d.frames >= minFrames; d.loss = d.enough ? pct(d.lost, d.frames) : null; }
  const known = dirs.filter((d) => d.loss !== null);
  const worst = known.length ? known.reduce((a, b) => (b.loss > a.loss ? b : a)) : null;

  const grid = el("div", "lq-dirs");
  for (const d of dirs) {
    const box = el("div", "lq-dir" + (d === worst ? " worst" : "") + (d.enough ? "" : " na"));
    const t = el("div", "t");
    t.append(el("span", "", d.name), el("span", "pct", d.enough ? fmtPct(d.loss) : "–"));
    box.append(t, el("div", "muted small", d.label));
    const f = el("div", "f");
    for (const [k, v] of d.rows) f.append(el("span", "", k), el("b", "", String(v)));
    box.append(f, el("div", "formula", d.enough ? `${d.formula} = ${fmtPct(d.loss)}`
                                                  : `needs ${minFrames} frames, has ${d.frames}`));
    grid.append(box);
  }
  body.append(el("h3", "", "Directions"), grid);
  body.append(el("p", "muted small",
    `Window: last ${cfg.frames || 50} frames per direction, max. ${cfg.minutes || 30} min. ` +
    `A direction counts from ${minFrames} frames.`));

  // the step ladder
  let before = null;
  if (worst) { before = 0; for (let k = 0; k < 5; k++) if (worst.loss <= steps[k]) { before = 5 - k; break; } }
  const ladder = el("div", "lq-steps");
  [5, 4, 3, 2, 1].forEach((n, k) => {
    const st = el("div", "lq-step" + (before === n ? " cur" : ""));
    st.append(el("div", "b", String(n)), el("div", "l", `≤ ${steps[k]} %`));
    ladder.append(st);
  });
  const red = el("div", "lq-step red" + (before === 0 ? " cur" : ""));
  red.append(el("div", "b", "X"), el("div", "l", `> ${steps[4]} %`));
  ladder.append(red);
  body.append(el("h3", "", "Bars"), ladder);
  if (worst) {
    const calc = el("div", "lq-calc");
    calc.append(`worst: ${worst.name} ${fmtPct(worst.loss)} → ${before ? before + " bars" : "X (red)"}`, el("br"),
                `T1 timeouts: ${q.t1} → max(0, ${before} − ${q.t1}) = ${Math.max(0, before - q.t1)} bars`);
    body.append(calc);
  }

  // counters
  const kb = (n) => n >= 1000 ? (n / 1000).toFixed(1) + " kB" : n + " B";
  const tbl = el("table", "lq-raw");
  const rows = [["REJ received", q.rej_rx, "the station missed our frame"],
                ["T1 timeouts", q.t1, "no answer at all, −1 bar each"],
                ["payload net / repeated", `${kb(q.bytes_new)} / ${kb(q.bytes_retry)}`, "sent to the station"],
                ["round trip (SRT)", q.srt ? q.srt.toFixed(1) + " s" : "–", "smoothed"]];
  for (const [k, v, d] of rows) {
    const tr = el("tr");
    tr.append(el("td", "", k), el("td", "v", String(v)), el("td", "muted small", d));
    tbl.append(tr);
  }
  body.append(el("h3", "", "Counters (window)"), tbl);
  body.append(el("p", "muted small", `Received ${ago(Math.floor(Date.now() / 1000) - q.at)}.`));
}

/* CR73: name · locator · distance from the profile, else the symbol name */
function profileNote(c) {
  const p = (S.profiles || {})[c];
  if (!p) return "";
  const km = p.km === undefined ? "" : `${p.km} km ${compass(p.deg)}`;
  return [p.name, p.loc, km].filter(Boolean).join(" · ");
}
function compass(deg) {
  return ["N", "NE", "E", "SE", "S", "SW", "W", "NW"][Math.round(((deg || 0) % 360) / 45) % 8];
}

function renderPeople() {
  const mem = $("members");
  mem.replaceChildren();
  if (S.board) {
    for (const c of S.members) {
      const name = SYMNAMES[symOf(c)];
      const mine = (S.profile && S.profile.name ? `you · ${S.profile.name}` : "you") +
                   (localLink() ? ` · ${S.chat_link}` : "");
      mem.append(personRow(c, symOf(c), c === S.mycall ? mine : (profileNote(c) || name || ""), true));
    }
  } else {
    mem.append(el("li", "muted small", "Not in a board"));
  }
  const heard = $("heard");
  heard.replaceChildren();
  for (const h of S.heard || []) heard.append(personRow(h.call, h.symbol, ago(h.ago)));
  $("heard-none").classList.toggle("hidden", (S.heard || []).length > 0);
}

/* Bar at the top of the chat (CR13): older stored lines on request. */
function histBar(ol) {
  const b = S.board;
  if (!b || b.hist === undefined || (!b.older && !b.loading)) return;
  const li = el("li", "histbar");
  if (b.loading) { li.append(el("span", "muted", "📜 loading history…")); ol.append(li); return; }
  li.append(el("span", "", `📜 ${b.older} older post${b.older === 1 ? "" : "s"}`));
  const ten = el("button", "sm", "load 10");
  ten.onclick = () => api("history", { n: 10 });
  const all = el("button", "sm", "load all");
  all.onclick = () => api("history", { n: 200 });
  li.append(ten, all);
  ol.append(li);
}

function renderMessages() {
  const box = $("chat");
  const atEnd = box.scrollTop + box.clientHeight >= box.scrollHeight - 30;
  const ol = $("messages");
  ol.replaceChildren();
  if (!S.board) return;
  if (S.board.motd) ol.append(el("li", "motd", "📌 " + S.board.motd));   // CR3
  histBar(ol);
  let prevCall = null, inHistory = false;
  for (const m of S.messages) {
    if (m.history && !inHistory) { ol.append(el("li", "divider", `history (${S.board.keep})`)); inHistory = true; }
    if (!m.history && inHistory) { ol.append(el("li", "divider", "now")); inHistory = false; }
    if (m.kind === "join" || m.kind === "leave") {
      ol.append(el("li", "sys", `${m.call} ${m.kind === "join" ? "joined" : "left"} · ${hhmm(m.time)}`));
      prevCall = null; continue;
    }
    if (m.kind === "system") { ol.append(el("li", "sys", wireToText(m.text))); prevCall = null; continue; }
    ol.append(bubble(m, prevCall === m.call));
    prevCall = m.call;
  }
  const up = S.images && S.images.upload;         // CR12: the picture on its way up
  const upBusy = up && up.state !== "done";
  const upLine = upBusy && up.line ? up.line.replace(/[\r\n]/g, " ").trim().slice(0, 200) : null;
  for (const text of S.pending) {
    // the chat line of the picture goes out right behind the bytes: while
    // the upload bubble (with the progress) is shown, do not show it twice
    if (upLine !== null && text === upLine) continue;
    ol.append(bubble({ id: "p", call: S.mycall, text, time: Date.now() / 1000, reactions: {}, pending: true },
                     prevCall === S.mycall));
    prevCall = S.mycall;
  }
  if (upBusy) ol.append(uploadBubble(up));
  for (const u of S.uploads || []) ol.append(uploadRow(u));      // CR30: the others' pictures
  if (atEnd) box.scrollTop = box.scrollHeight;
}

/* "Cry out" (CR17): a line "~!text" (max. 32 characters) is shown huge in a
 * comic "Bang!" burst. Over the air it is just the two characters "~!" in front. */
const CRY = "~!", CRY_MAX = 32;
const isCry = (wire) => wire.startsWith(CRY);
let BURST = "";
function burstPath() {
  if (BURST) return BURST;
  const pts = [], n = 18;
  for (let i = 0; i < 2 * n; i++) {
    const a = (Math.PI * i) / n - Math.PI / 2;
    const r = i % 2 ? 0.80 + 0.06 * ((i * 7) % 3) / 2 : 1;      // uneven spikes look hand drawn
    pts.push(`${(50 + 50 * r * Math.cos(a)).toFixed(1)}% ${(50 + 50 * r * Math.sin(a)).toFixed(1)}%`);
  }
  return (BURST = `polygon(${pts.join(",")})`);
}
function cryBubble(m, own) {
  const li = el("li", "msg cry" + (own ? " own" : ""));
  const col = el("div", "col");
  if (!own) col.append(el("div", "who", m.call));
  const bang = el("div", "bang" + (m.pending ? " pending" : ""));
  const outer = el("div", "burst outer"), inner = el("div", "burst inner");
  outer.style.clipPath = inner.style.clipPath = burstPath();
  const text = wireToText(m.text.slice(CRY.length));
  const t = el("div", "bang-text", text);
  // the longer the text (and its longest word), the smaller - but always big
  const longest = Math.max(...text.split(/\s+/).map((w) => [...w].length));
  t.style.fontSize = (text.length <= 12 && longest <= 9 ? 36 : longest <= 11 ? 28 : 23) + "px";
  bang.append(outer, inner, t);
  col.append(bang, el("div", "meta", m.pending ? "sending…" : hhmm(m.time)));
  if (own) li.append(col); else li.append(avatar(m.call, symOf(m.call)), col);
  return li;
}

// ---------------------------------------------------------------- comments (CR14, CR31)
/* Comment (CR14, CR31): over the air only the number of the event it answers,
 *   ~^4F I am QRV
 * = 5 bytes, unique within the last 256 events of the board - exactly the
 * window in which commenting is allowed. Lines from before CR31 carry call and
 * minute (~^OE3TEC 1402) and are still read that way. */
const QUOTE_RE = /^~\^([0-9A-Fa-f]{1,2})(?: |$)/;
const QUOTE_OLD_RE = /^~\^([A-Z0-9]{1,6}(?:-\d{1,2})?) (\d{4}) ?/;
/* -> {len, seq} (CR31) or {len, call, hhmm} (old lines), null without a quote */
function quoteOf(wire) {
  const m = (wire || "").match(QUOTE_RE);
  if (m) return { len: m[0].length, seq: parseInt(m[1], 16) };
  const o = (wire || "").match(QUOTE_OLD_RE);
  return o ? { len: o[0].length, call: o[1], hhmm: o[2] } : null;
}
const stripQuote = (wire) => { const q = quoteOf(wire); return q ? wire.slice(q.len) : (wire || ""); };
function quotePrefix() {
  return quoteTo ? `~^${(quoteTo.seq & 255).toString(16).toUpperCase()} ` : "";
}
let quoteTo = null;                      // message to quote with the next send
// A message from the history (loaded afterwards, or from before we joined) is
// read-only: no comment, no reaction – only what happens in the live chat.
const isHistory = (m) => !!m.history || m.seq < 0;
const srvMinute = (m) => {               // HHMM in UTC by the TinyBox clock
  const d = new Date(((m.srv_time || (m.time + (S.clock_off || 0)))) * 1000);
  return String(d.getUTCHours()).padStart(2, "0") + String(d.getUTCMinutes()).padStart(2, "0");
};
function quotedMessage(q, before) {
  let hit = null;
  for (const x of S.messages) {
    if (x === before) break;
    if (x.kind !== "line" && x.kind !== undefined) continue;
    if (q.seq !== undefined) {
      if (x.seq === q.seq) hit = x;        // CR31: unique, the newest one before us
      continue;
    }
    if (x.call !== q.call || !x.text) continue;      // old lines: call and minute
    const want = +q.hhmm.slice(0, 2) * 60 + +q.hhmm.slice(2);
    const t = srvMinute(x), mins = +t.slice(0, 2) * 60 + +t.slice(2);
    const diff = Math.min(Math.abs(mins - want), 1440 - Math.abs(mins - want));
    if (diff <= 1) hit = x;
  }
  return hit;
}
function excerpt(wire, n = 60) {
  const rest = stripQuote(wire);
  const sm = rest.match(STK_RE);
  if (sm && STK[sm[1]]) return "🏷️ " + STK[sm[1]].title;
  const ir = imageRef(rest);
  if (ir) return "🖼 image" + (ir.caption ? " · " + wireToText(ir.caption) : "");
  const t = wireToText(rest.replace(/^~!/, ""));
  return [...t].length > n ? [...t].slice(0, n).join("") + "…" : t;
}
function quoteBlock(ref, orig) {
  const q = el("div", "quote");
  let who;
  if (orig) who = `↩ ${orig.call} ${hhmmOf(orig)}`;
  else if (ref.seq !== undefined) who = `↩ message #${ref.seq.toString(16).toUpperCase()}`;
  else who = `↩ ${ref.call} ${utcToLocal(ref.hhmm)}`;
  q.append(el("div", "q-who", who));
  if (orig) {
    q.append(el("div", "q-text", excerpt(orig.text)));
    q.title = "Show the message";
    q.onclick = (ev) => {
      ev.stopPropagation();
      const li = document.querySelector(`li[data-mid="${CSS.escape(String(orig.id))}"]`);
      if (li) { li.scrollIntoView({ block: "center", behavior: "smooth" }); li.classList.add("flash");
                setTimeout(() => li.classList.remove("flash"), 1200); }
    };
  }
  return q;
}
const hhmmOf = (m) => hhmm(m.time);
function utcToLocal(h) {
  const d = new Date();
  d.setUTCHours(+h.slice(0, 2), +h.slice(2), 0, 0);
  return hhmm(d.getTime() / 1000 - (S.clock_off || 0));
}
function setQuote(m) {
  quoteTo = m;
  if (m && cryMode) setCry(false);
  const box = $("quote-bar");
  box.classList.toggle("hidden", !m);
  if (!cryMode) $("input").maxLength = 200 - (m ? quotePrefix().length : 0);
  if (m) {
    $("qb-text").replaceChildren("You are adding a comment on ", el("b", "", m.call + ": "),
                                 excerpt(m.text, 50));
    $("input").placeholder = `Your comment on ${m.call}'s message`;
    $("input").focus();
  } else if (S.board && !cryMode) {
    $("input").placeholder = `Message to ${S.board.name}`;
  }
  updateHint();
}

// ---------------------------------------------------------------- bubbles
function bubble(m, cont) {
  const own = m.call === S.mycall;
  if (isCry(m.text || "")) return cryBubble(m, own);
  const li = el("li", "msg" + (own ? " own" : "") + (cont ? " cont" : ""));
  li.dataset.mid = String(m.id);
  const col = el("div", "col");
  if (!own && !cont) col.append(el("div", "who", m.call));
  const qm = quoteOf(m.text);
  const body = qm ? m.text.slice(qm.len) : (m.text || "");
  const ir = imageRef(body);                      // CR12: a picture with a caption
  const text = wireToText(ir ? ir.caption : body);
  const orig = qm && !m.pending ? quotedMessage(qm, m) : null;
  const quotesMe = qm && !own && baseCall((orig && orig.call) || qm.call || "")
                   === baseCall(S.mycall);
  const b = el("div", "bubble" + (m.pending ? " pending" : "") + (m.history ? " history" : "")
               + (selected === m.id ? " selected" : "") + (isSingleEmoji(text) && !qm && !ir ? " jumbo" : "")
               + (ir ? " img" : "")
               + (!own && (mentionsMe(text) || quotesMe) ? " mention" : ""));
  if (qm) b.append(quoteBlock(qm, orig));
  const sm = body.match(STK_RE);
  if (ir) {
    b.append(imageBlock(ir, own));
    if (text) { const cap = el("div", "cap"); richText(cap, text); b.append(cap); }
  } else if (sm && STK[sm[1]]) {                 // CR11: sticker instead of text
    b.classList.add("stk");
    const img = el("img");
    img.src = "/stickers/" + STK[sm[1]].file;
    img.alt = img.title = STK[sm[1]].title;
    b.append(img);
  } else {
    richText(b, text);
  }
  // Comments and reactions only on messages that arrived while we were in the
  // board – nothing from the history, nothing after the fact.
  if (!m.pending && !isHistory(m)) {
    b.onclick = (ev) => { ev.stopPropagation(); openReactBar(m, b); };
  }
  col.append(b);
  const r = Object.entries(m.reactions || {});
  if (r.length) {
    const rs = el("div", "reacts");
    for (const [code, calls] of r) {
      const mine = calls.includes(S.mycall);
      const wait = mine && (S.pending_reacts || []).includes(`${m.seq}:${code}`);
      const pill = el("button", "react" + (mine ? " mine" : "") + (wait ? " pending" : ""),
                      `${wireToText(code)} ${calls.length}`);
      if (wait) pill.title = "sending…";
      if (!wait) pill.title = calls.join(", ");
      if (!mine) pill.onclick = () => api("react", { seq: m.seq, emoji: code });
      rs.append(pill);
    }
    col.append(rs);
  }
  col.append(el("div", "meta", m.pending ? "sending…" : hhmm(m.time)));
  if (own) li.append(col);
  else li.append(avatar(m.call, symOf(m.call)), col);
  return li;
}

// ---------------------------------------------------------------- reactions
// CR23: closing the full picker makes #chat taller, so the browser scrolls it by
// itself. That scroll event must not close the quick bar we are just opening.
let ignoreChatScrollUntil = 0;
function openReactBar(m, anchor) {
  if (pickerMode === "react") {                // never leave a picker aimed at another message
    closePicker();
    ignoreChatScrollUntil = performance.now() + 150;
  }
  selected = m.id;
  const bar = $("react-bar");
  bar.replaceChildren();
  if (isHistory(m)) return;                     // history: no comment, no reactions
  const q = el("button", "q-btn", "↩");
  q.title = "Comment / reply";
  q.onclick = (ev) => { ev.stopPropagation(); closeReactBar(); setQuote(m); };
  bar.append(q);
  for (const e of QUICK) {
    const btn = el("button", "", e);
    btn.onclick = () => { sendReaction(m, e); };
    bar.append(btn);
  }
  const more = el("button", "", "＋");
  more.onclick = (ev) => {
    // CR23: close the quick bar before the full picker opens (it used to float
    // over the picker). The target message travels with openPicker(target).
    ev.stopPropagation();
    const target = m;
    closeReactBar();
    pickerMode = "react";
    openPicker(target);
  };
  bar.append(more);
  bar.classList.remove("hidden");
  const r = anchor.getBoundingClientRect();
  bar.style.top = Math.max(8, r.top - 48) + "px";
  // CR24: keep the bar inside the chat column, not just inside the window
  // (in the 3-column view it used to reach into the right column).
  const c = $("chat").getBoundingClientRect();
  const minLeft = c.left + 8, maxLeft = c.right - bar.offsetWidth - 8;
  bar.style.left = Math.max(minLeft, Math.min(maxLeft, r.left)) + "px";
  anchor.classList.add("selected");
}
function closeReactBar() {
  selected = null;
  $("react-bar").classList.add("hidden");
  document.querySelectorAll(".bubble.selected").forEach((b) => b.classList.remove("selected"));
}
function sendReaction(m, emoji) {
  const { wire, bad } = textToWire(emoji);
  closeReactBar(); closePicker();
  if (!bad.length && wire) api("react", { seq: m.seq, emoji: wire });
}

// ---------------------------------------------------------------- emoji picker
let pickerTarget = null;
function openPicker(target) {
  pickerTarget = target || null;
  const grid = $("picker-grid");
  grid.replaceChildren();
  grid.classList.remove("stk-grid");
  for (const g of emojiGroups()) {
    if (g.name) grid.append(el("div", "picker-h", g.name));
    for (const e of g.items) {
      const b = el("button", "", e);
      b.onclick = () => {
        if (pickerMode === "react" && pickerTarget) { sendReaction(pickerTarget, e); return; }
        insertAtCursor(e);
      };
      grid.append(b);
    }
  }
  $("picker").classList.remove("hidden");
}
function closePicker() { $("picker").classList.add("hidden"); pickerMode = "input"; pickerTarget = null; }
/* CR11: sticker selection - a tap sends it at once, over the air only "[STK]CQ" */
function openStickers() {
  pickerMode = "sticker";
  const grid = $("picker-grid");
  grid.replaceChildren();
  for (const s of STK_LIST) {
    const b = el("button", "stk-btn");
    const img = el("img");
    img.src = "/stickers/" + s.file; img.alt = s.title;
    b.title = `${s.title}  ([STK]${s.name})`;
    b.append(img);
    b.onclick = async () => {
      closePicker();
      const wire = quotePrefix() + "[STK]" + s.name;
      if (quoteTo) setQuote(null);
      if (cryMode) setCry(false);
      await api("say", { text: wire });
    };
    grid.append(b);
  }
  grid.classList.add("stk-grid");
  $("picker").classList.remove("hidden");
}
function insertAtCursor(t) {
  const i = $("input");
  const a = i.selectionStart ?? i.value.length, z = i.selectionEnd ?? i.value.length;
  i.value = i.value.slice(0, a) + t + i.value.slice(z);
  i.focus();
  i.selectionStart = i.selectionEnd = a + t.length;
  updateHint();
}

// ---------------------------------------------------------------- composer
function updateHint() {
  const v = $("input").value;
  const hint = $("hint");
  if (!v.trim()) { hint.classList.add("hidden"); return; }
  const { wire, bad } = textToWire(v);
  hint.classList.remove("hidden");
  if (bad.length) {
    hint.className = "hint";
    hint.textContent = `Not sendable over radio: ${bad.join(" ")} – use the emoji button.`;
  } else {
    const air = cryMode ? CRY + wire : quotePrefix() + wire;
    hint.className = "hint info";
    hint.textContent = `${new TextEncoder().encode(air).length} bytes on air: ${air}` +
      (cryMode ? `  ·  ${[...$("input").value].length}/${CRY_MAX}` : "");
  }
}
let cryMode = false;
function setCry(on) {
  cryMode = on;
  if (on && quoteTo) { quoteTo = null; $("quote-bar").classList.add("hidden"); }
  const i = $("input");
  $("btn-cry").classList.toggle("active", on);
  i.maxLength = on ? CRY_MAX : 200;
  if (on && i.value.length > CRY_MAX) i.value = i.value.slice(0, CRY_MAX);
  i.placeholder = on ? `Cry out! (max. ${CRY_MAX} characters)` : (S && S.board ? `Message to ${S.board.name}` : "");
  i.focus(); updateHint();
}
async function send() {
  const i = $("input");
  const { wire: w0, bad } = textToWire(i.value);
  const wire = cryMode && w0 ? CRY + w0 : w0 ? quotePrefix() + w0 : w0;
  if (bad.length || !wire) { updateHint(); return; }
  if (wire.startsWith("/")) {
    $("hint").className = "hint"; $("hint").textContent = "Lines must not start with “/”.";
    return;
  }
  i.value = ""; closePicker();
  if (quoteTo) setQuote(null);
  if (cryMode) setCry(false); else updateHint();
  await api("say", { text: wire });
}

// ---------------------------------------------------------------- symbols
function renderSymbols() {
  const q = $("sym-search").value.trim().toLowerCase();
  const grid = $("sym-grid");
  grid.replaceChildren();
  const all = Object.entries(SYMNAMES).sort((a, b) =>
    (a[0][0] === b[0][0] ? (a[0][1] < b[0][1] ? -1 : 1) : (a[0][0] === "/" ? -1 : 1)));
  for (const [sym, name] of all) {
    if (q && !name.toLowerCase().includes(q) && sym !== q) continue;
    const b = el("button", S && S.my_symbol === sym ? "active" : "");
    const se = symbolEl(sym);
    if (!se) continue;
    b.append(se); b.title = `${sym}  ${name}`;
    b.onclick = async () => { await api("symbol", { symbol: sym }); };
    grid.append(b);
  }
}


// ---------------------------------------------------------------- blurhash
/* Blurred colour preview of an image in 16-22 characters (CR12). Our own
 * implementation of the public BlurHash algorithm (base83, DC + AC cosine
 * components). Encode in the browser before sending, decode to draw the
 * placeholder. The component counts (first character) also give the shape. */
const B83 = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz#$%*+,-.:;=?@[]^_{|}~";
const enc83 = (v, n) => { let s = ""; for (let i = 1; i <= n; i++) s += B83[Math.floor(v / 83 ** (n - i)) % 83]; return s; };
const dec83 = (s) => { let v = 0; for (const c of s) v = v * 83 + B83.indexOf(c); return v; };
const toLin = (v) => { v /= 255; return v <= 0.04045 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4; };
const toSRGB = (v) => { v = Math.max(0, Math.min(1, v)); return Math.round((v <= 0.0031308 ? v * 12.92 : 1.055 * v ** (1 / 2.4) - 0.055) * 255); };
const signPow = (v, e) => Math.sign(v) * Math.abs(v) ** e;

/* pixels: RGBA bytes of a w x h image; nx, ny: components (1..9). */
function blurhashEncode(pixels, w, h, nx, ny) {
  const f = [];
  for (let j = 0; j < ny; j++) for (let i = 0; i < nx; i++) {
    const norm = i === 0 && j === 0 ? 1 : 2;
    let r = 0, g = 0, b = 0;
    for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) {
      const basis = norm * Math.cos((Math.PI * i * x) / w) * Math.cos((Math.PI * j * y) / h);
      const o = 4 * (x + y * w);
      r += basis * toLin(pixels[o]); g += basis * toLin(pixels[o + 1]); b += basis * toLin(pixels[o + 2]);
    }
    f.push([r / (w * h), g / (w * h), b / (w * h)]);
  }
  const dc = f[0], ac = f.slice(1);
  let hash = enc83((nx - 1) + (ny - 1) * 9, 1);
  let maxVal = 1;
  if (ac.length) {
    const m = Math.max(...ac.map((c) => Math.max(...c.map(Math.abs))));
    const q = Math.floor(Math.max(0, Math.min(82, Math.floor(m * 166 - 0.5))));
    maxVal = (q + 1) / 166;
    hash += enc83(q, 1);
  } else hash += enc83(0, 1);
  hash += enc83((toSRGB(dc[0]) << 16) + (toSRGB(dc[1]) << 8) + toSRGB(dc[2]), 4);
  for (const c of ac) {
    const q = c.map((v) => Math.floor(Math.max(0, Math.min(18, Math.floor(signPow(v / maxVal, 0.5) * 9 + 9.5)))));
    hash += enc83(q[0] * 19 * 19 + q[1] * 19 + q[2], 2);
  }
  return hash;
}

/* {nx, ny} of a hash, or null if it is not a valid one. */
function blurhashShape(hash) {
  if (!hash || [...hash].some((c) => !B83.includes(c))) return null;
  const flag = dec83(hash[0]), nx = (flag % 9) + 1, ny = Math.floor(flag / 9) + 1;
  return hash.length === 4 + 2 * nx * ny ? { nx, ny } : null;
}
/* Length of a hash from its first character (0 = not a blurhash). */
function blurhashLen(first) {
  const i = first ? B83.indexOf(first) : -1;
  return i < 0 ? 0 : 4 + 2 * ((i % 9) + 1) * (Math.floor(i / 9) + 1);
}

/* -> RGBA bytes, w x h pixels. */
function blurhashDecode(hash, w, h, punch = 1) {
  const sh = blurhashShape(hash);
  if (!sh) return null;
  const maxVal = ((dec83(hash[1]) + 1) / 166) * punch;
  const colors = [];
  for (let i = 0; i < sh.nx * sh.ny; i++) {
    if (i === 0) {
      const v = dec83(hash.slice(2, 6));
      colors.push([toLin(v >> 16), toLin((v >> 8) & 255), toLin(v & 255)]);
    } else {
      const v = dec83(hash.slice(4 + i * 2, 6 + i * 2));
      colors.push([Math.floor(v / 361), Math.floor(v / 19) % 19, v % 19].map((q) => signPow((q - 9) / 9, 2) * maxVal));
    }
  }
  const out = new Uint8ClampedArray(w * h * 4);
  for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) {
    let r = 0, g = 0, b = 0;
    for (let j = 0; j < sh.ny; j++) for (let i = 0; i < sh.nx; i++) {
      const basis = Math.cos((Math.PI * x * i) / w) * Math.cos((Math.PI * y * j) / h);
      const c = colors[i + j * sh.nx];
      r += c[0] * basis; g += c[1] * basis; b += c[2] * basis;
    }
    const o = 4 * (x + y * w);
    out[o] = toSRGB(r); out[o + 1] = toSRGB(g); out[o + 2] = toSRGB(b); out[o + 3] = 255;
  }
  return out;
}

// ---------------------------------------------------------------- images (CR12)
/* Over the air only "~#<hash 6 hex><size 2 hex><blurhash>" (26-32 bytes, no
 * separators) and, after a space, the caption. The size is in steps of 64
 * bytes. The picture itself is fetched from the TinyBox on a tap (/api/image/get)
 * and then served by the client as /img/<hash>. */
const IMG_RE = /^~#([0-9a-f]{6})([0-9a-f]{2})/;
const IMG_SHRINK_MAX = 8192;            // fallback if the board says nothing
/* Three sizes to choose from (CR34): the target in bytes decides the time on
 * air, the long side in px keeps the picture sharp enough for that size.
 * "normal" is [images] target_bytes of the client (4 kB), "small" half of it,
 * "large" the board's limit; the choice is remembered in the browser.
 * The picture is shown in the chat at its own pixel size (CR36), so the
 * three sizes differ on the screen as well: 108 / 192 / 320 px. */
const IMG_SIZES = { small: { px: 108, of: 0.5 }, normal: { px: 192, of: 1 }, large: { px: 320, of: 0 } };
/* Width in px for the blurred placeholder - the pixels are not on the wire,
 * only the bytes, so guess the size step from them. */
function imgGuessPx(bytes) {
  const normal = imgTarget("normal"), small = imgTarget("small");
  return bytes <= (small + normal) / 2 ? IMG_SIZES.small.px
       : bytes <= (normal + imgTarget("large")) / 2 ? IMG_SIZES.normal.px : IMG_SIZES.large.px;
}
function imgTarget(size) {
  const limit = (S && S.board && S.board.img) || IMG_SHRINK_MAX;
  const normal = Math.min(limit, (S && S.img && S.img.target) || 4096);
  const f = IMG_SIZES[size] || IMG_SIZES.normal;
  return f.of ? Math.round(normal * f.of) : limit;
}

/* Parse the reference at the start of a (quote-free) wire text:
 * {hash, size, bh, caption} or null. */
function imageRef(wire) {
  const m = (wire || "").match(IMG_RE);
  if (!m) return null;
  const rest = wire.slice(m[0].length), n = blurhashLen(rest[0] || "");
  if (!n || rest.length < n) return null;
  const bh = rest.slice(0, n);
  if (!blurhashShape(bh)) return null;
  if (rest.length > n && rest[n] !== " ") return null;
  return { hash: m[1], size: parseInt(m[2], 16) * 64, bh, caption: rest.slice(n + 1) };
}

const kbText = (n) => `${(n / 1024).toFixed(1)} KB`;
function secText(s) {
  if (s < 50) return `~${Math.max(5, Math.round(s / 5) * 5)} s`;
  const m = Math.round(s / 60);
  return `~${Math.max(1, m)} min`;
}
/* Time over the air: net rate of the link (the picture goes in one go, the
 * AX.25 window paces it) plus the turnarounds: //IMGPUT - //IMGGO, the last
 * acknowledgement and //IMGOK when sending, request and answer when loading. */
function imgTime(size, sending) {
  const c = (S && S.img) || { rate: 100 };
  return size / c.rate + (sending ? 8 : 5);
}

/* Draw a blurhash into a canvas the shape of its components (3x2 = landscape). */
function blurCanvas(bh, cls, bytes) {
  const sh = blurhashShape(bh);
  const c = el("canvas", cls);
  if (bytes) {                            // CR36: placeholder about as big as the picture
    const px = imgGuessPx(bytes);
    c.style.width = (sh.nx >= sh.ny ? px : Math.round((px * sh.nx) / sh.ny)) + "px";
  }
  const w = 32, h = Math.max(4, Math.round((32 * sh.ny) / sh.nx));
  c.width = w; c.height = h;
  const px = blurhashDecode(bh, w, h);
  if (px) c.getContext("2d").putImageData(new ImageData(px, w, h), 0, 0);
  c.style.aspectRatio = `${sh.nx} / ${sh.ny}`;
  return c;
}

/* The image part of a bubble: the picture if it is here, else the blurred
 * placeholder with size, load time and the state of a running download. */
function imageBlock(ref, own) {
  const box = el("div", "imgbox");
  const I = S.images || { have: [], loading: {} };
  if (I.have.includes(ref.hash)) {
    const img = el("img");
    img.src = "/img/" + ref.hash; img.alt = "image";
    img.onclick = (ev) => { ev.stopPropagation(); window.open(img.src, "_blank", "noopener"); };
    box.append(img);
    return box;
  }
  box.append(blurCanvas(ref.bh, "blur", ref.size));
  const ov = el("div", "imgov");
  const ld = I.loading[ref.hash];
  if (ld && ld.error) {
    ov.append(el("div", "", `⚠ ${ld.error}`), el("div", "small", "tap to try again"));
    box.classList.add("err");
  } else if (ld) {
    const bar = el("div", "bar"), fill = el("div", "fill");
    const total = ld.total || ref.size;
    fill.style.width = Math.min(100, Math.round((100 * ld.done) / total)) + "%";
    bar.append(fill);
    ov.append(el("div", "", `${kbText(ld.done)} / ${kbText(total)}`), bar);
    box.classList.add("busy");
  } else {
    ov.append(el("div", "", `🖼 ${kbText(ref.size)} · ${secText(imgTime(ref.size, false))}`),
              el("div", "small", "tap to load"));
  }
  box.append(ov);
  if (!ld || ld.error) {
    box.onclick = (ev) => { ev.stopPropagation(); api("image/get", { hash: ref.hash }); };
  } else box.onclick = (ev) => ev.stopPropagation();
  return box;
}

/* CR30: another station is sending a picture. The TinyBox announces it once
 * ("^OE1ABC 50"); the bar shows what we hear of those frames on the channel.
 * A station we cannot hear directly (digipeater, too weak) gives no bytes -
 * then the bar runs over the expected time instead. */
function uploadRow(u) {
  const li = el("li", "sys uprow");
  const bar = el("div", "bar"), fill = el("div", "fill");
  const heard = u.got > 0;
  li.append(el("div", "uptxt", `🖼 ${u.call} uploading picture · ` +
    (heard ? `${kbText(u.got)} / ${kbText(u.size)}` : kbText(u.size))));
  if (heard) {
    fill.style.width = Math.min(100, Math.round((100 * u.got) / u.size)) + "%";
  } else {
    const secs = Math.max(5, imgTime(u.size, true));
    fill.style.animation = `upgrow ${secs}s linear ${-Math.max(0, Date.now() / 1000 - u.at)}s forwards`;
  }
  bar.append(fill);
  li.append(bar);
  return li;
}

/* The own upload under way (or failed): a bubble of its own until the chat
 * line with the reference comes back from the TinyBox. */
function uploadBubble(up) {
  const li = el("li", "msg own");
  const col = el("div", "col");
  const b = el("div", "bubble img pending");
  const ref = imageRef(stripQuote(up.line));
  const box = el("div", "imgbox");
  if (ref && (S.images.have || []).includes(ref.hash)) {
    const img = el("img"); img.src = "/img/" + ref.hash; img.alt = "image"; box.append(img);
  } else if (ref) box.append(blurCanvas(ref.bh, "blur", up.size || ref.size));
  const ov = el("div", "imgov");
  if (up.state === "error") {
    ov.append(el("div", "", `⚠ not sent: ${up.error}`));
    const row = el("div", "row");
    const again = el("button", "sm", "Try again");
    again.onclick = (ev) => { ev.stopPropagation(); api("image/retry"); };
    const x = el("button", "sm", "Discard");
    x.onclick = (ev) => { ev.stopPropagation(); api("image/dismiss"); };
    row.append(again, x);
    ov.append(row);
    box.classList.add("err");
  } else {
    const bar = el("div", "bar"), fill = el("div", "fill");
    fill.style.width = Math.min(100, Math.round((100 * up.sent) / up.size)) + "%";
    bar.append(fill);
    ov.append(el("div", "", up.state === "waiting" ? "waiting…" : `${kbText(up.sent)} / ${kbText(up.size)}`), bar);
    box.classList.add("busy");
  }
  box.append(ov);
  b.append(box);
  if (ref && ref.caption) { const cap = el("div", "cap"); richText(cap, wireToText(ref.caption)); b.append(cap); }
  col.append(b, el("div", "meta", up.state === "error" ? "failed" : "sending…"));
  li.append(col);
  return li;
}

/* Shrink a chosen file: WebP (JPEG where the browser cannot make WebP), long
 * side at most longPx, quality then size down until it fits maxBytes.
 * -> {blob, w, h, bh} or null. */
async function shrinkImage(file, maxBytes, longPx = 320) {
  let src;
  try { src = await createImageBitmap(file, { imageOrientation: "from-image" }); }
  catch (e) {
    src = await new Promise((ok, no) => {
      const im = new Image();
      im.onload = () => ok(im); im.onerror = no;
      im.src = URL.createObjectURL(file);
    });
  }
  const W = src.width || src.naturalWidth, H = src.height || src.naturalHeight;
  if (!W || !H) return null;
  const canvas = document.createElement("canvas");
  const toBlob = (type, q) => new Promise((ok) => canvas.toBlob(ok, type, q));
  let scale = Math.min(1, longPx / Math.max(W, H));
  let best = null;
  for (let round = 0; round < 8; round++) {
    const w = Math.max(8, Math.round(W * scale)), h = Math.max(8, Math.round(H * scale));
    canvas.width = w; canvas.height = h;
    canvas.getContext("2d").drawImage(src, 0, 0, w, h);
    let type = "image/webp";
    for (const q of [0.8, 0.65, 0.5, 0.4, 0.3, 0.2]) {
      let blob = await toBlob(type, q);
      if (!blob || blob.type !== type) { type = "image/jpeg"; blob = await toBlob(type, q); }
      if (!blob) return null;
      if (!best || blob.size < best.blob.size) best = { blob, w, h };
      if (blob.size <= maxBytes) { best = { blob, w, h }; round = 99; break; }
    }
    scale *= 0.75;
    if (w <= 64 && h <= 64) break;
  }
  if (!best || best.blob.size > maxBytes) return null;
  // the blurhash from a tiny copy; the component counts follow the shape
  const ratio = best.w / best.h;
  const [nx, ny] = ratio >= 1.25 ? [3, 2] : ratio <= 0.8 ? [2, 3] : [3, 3];
  const tw = 24, th = Math.max(4, Math.round(24 / ratio));
  canvas.width = tw; canvas.height = th;
  const ctx = canvas.getContext("2d");
  ctx.drawImage(src, 0, 0, tw, th);
  const bh = blurhashEncode(ctx.getImageData(0, 0, tw, th).data, tw, th, nx, ny);
  return { ...best, bh };
}

let imgPick = null;                      // {blob, bh} waiting for OK in the dialog
let imgFile = null;                      // the chosen file, shrunk again on a size change
let imgAspect = null;                    // width / height of the chosen file
let imgSize = "normal";
try { imgSize = localStorage.getItem("tb.imgsize") || "normal"; } catch (e) { /* no storage */ }
if (!IMG_SIZES[imgSize]) imgSize = "normal";

/* CR36: the three size buttons carry their numbers: pixels (from the shape
 * of the chosen file), bytes and the time to upload. */
function imgSizeButtons() {
  for (const b of document.querySelectorAll("#imgdlg-size button")) {
    const size = b.dataset.size, px = IMG_SIZES[size].px, bytes = imgTarget(size);
    b.classList.toggle("on", size === imgSize);
    let dims = `${px} px`;
    if (imgAspect) {
      const w = imgAspect >= 1 ? px : Math.round(px * imgAspect);
      const h = imgAspect >= 1 ? Math.round(px / imgAspect) : px;
      dims = `${w}×${h}`;
    }
    b.textContent = "";
    b.append(el("b", "", size), el("span", "", ` (${dims}), ~${kbText(bytes)}, ${secText(imgTime(bytes, true))}`));
  }
}
async function pickImageSize(size) {
  if (!IMG_SIZES[size] || size === imgSize) return;
  imgSize = size;
  try { localStorage.setItem("tb.imgsize", size); } catch (e) { /* no storage */ }
  imgSizeButtons();
  if (imgFile) await shrinkForDialog();
}
async function chooseImage(file) {
  if (!file || !S || !S.board || !S.board.img) return;
  imgFile = file; imgAspect = null;
  $("imgdlg-caption").value = $("input").value;
  $("imgdlg").classList.remove("hidden");
  imgSizeButtons();
  await shrinkForDialog();
}
async function shrinkForDialog() {
  const file = imgFile, limit = S.board.img || IMG_SHRINK_MAX;
  const target = imgTarget(imgSize), px = IMG_SIZES[imgSize].px;
  $("imgdlg-text").textContent = "Shrinking the picture…";
  $("imgdlg-ok").disabled = true;
  imgPick = null;
  let r = null;
  try { r = await shrinkImage(file, target, px); } catch (e) { r = null; }
  if (file !== imgFile) return;           // dialog closed or another file chosen meanwhile
  if (!r || r.blob.size > limit) {
    $("imgdlg-text").textContent = `Sorry, this picture cannot be made small enough (max. ${kbText(limit)}).`;
    return;
  }
  imgPick = r;
  if (!imgAspect) { imgAspect = r.w / r.h; imgSizeButtons(); }
  $("imgdlg-text").textContent = "";      // the numbers are in the buttons (CR36)
  $("imgdlg-ok").disabled = false;
}
function closeImageDialog() { $("imgdlg").classList.add("hidden"); imgPick = imgFile = imgAspect = null; $("imgfile").value = ""; }
async function sendImage() {
  if (!imgPick) return;
  const { wire, bad } = textToWire($("imgdlg-caption").value);
  if (bad.length) { $("imgdlg-text").textContent = `Not sendable over radio: ${bad.join(" ")}`; return; }
  const buf = new Uint8Array(await imgPick.blob.arrayBuffer());
  let bin = "";
  for (let i = 0; i < buf.length; i += 4096) bin += String.fromCharCode(...buf.subarray(i, i + 4096));
  const body = { data: btoa(bin), blurhash: imgPick.bh, caption: wire, quote: quotePrefix() };
  closeImageDialog();
  $("input").value = ""; updateHint();
  if (quoteTo) setQuote(null);
  const r = await postJson("image", body);
  if (!r.ok) { $("hint").className = "hint"; $("hint").textContent = "The picture was not accepted."; $("hint").classList.remove("hidden"); }
}

// ---------------------------------------------------------------- mailbox (C3)
/* Everything here is local in the client; only "Sync" goes on air.
 * Mail texts are untrusted as well: textContent only. */
let view = "chat";            // chat | mail | term (CR43); channel 0 = monitor (CR45)
let folder = "inbox";         // inbox | outbox | sent | b:<RUBRIC> | rubrics
let items = [];               // list of the current folder
let itemsFor = "";            // folder + mailbox version the list belongs to
let selId = null;             // shown message (id) or outbox entry ("o<oid>")
let level = "list";           // phone: folders | list | read | compose
let cur = null;               // message in the reader
let draft = null;             // {oid, type} while composing

try { view = localStorage.getItem("tbc-view") === "mail" ? "mail" : "chat"; } catch (e) { /* ok */ }

function setView(v) {
  view = v;
  try { localStorage.setItem("tbc-view", v); } catch (e) { /* ok */ }
  $("app").classList.toggle("view-mail", v === "mail");
  $("app").classList.toggle("view-term", v === "term");
  $("app").classList.toggle("view-stats", v === "stats");      // CR61
  $("statsview").classList.toggle("hidden", v !== "stats");
  if (v === "stats") AprsStatsView.show(); else AprsStatsView.hide();
  $("mailview").classList.toggle("hidden", v !== "mail");
  $("termview").classList.toggle("hidden", v !== "term");
  if (S) render();
  if (v === "term") { const o = $("term-out"); o.scrollTop = o.scrollHeight; $("term-input").focus(); }
}

function setLevel(l) {
  level = l;
  const mv = $("mailview");
  mv.classList.remove("lvl-folders", "lvl-list", "lvl-read", "lvl-compose");
  mv.classList.add("lvl-" + l);
}

function openFolder(f) {
  if (!f.startsWith("s:") && $("mv-search").value) $("mv-search").value = "";
  if (folder !== f) { folder = f; selId = null; cur = null; draft = null; items = []; itemsFor = ""; }
  setView("mail");
  setLevel("list");
  showReader();
  loadItems(true);
}

function folderName(f) {
  if (f.startsWith("s:")) return `Search "${f.slice(2)}"`;       // CR49
  if (f === "inbox") return "Inbox";
  if (f === "outbox") return "Outbox";
  if (f === "sent") return "Sent";
  if (f === "rubrics") return "Bulletin rubrics";
  return f === "b:TBNEWS" ? "TinyBox News" : "Bulletins " + f.slice(2);
}

function dateStr(unix) {
  if (!unix) return "";
  const d = new Date(unix * 1000), now = new Date();
  if (d.toDateString() === now.toDateString()) return hhmm(unix);
  return d.toLocaleDateString([], { day: "2-digit", month: "2-digit" }) + " " + hhmm(unix);
}
function longDate(unix) {
  return new Date(unix * 1000).toLocaleString([], { day: "2-digit", month: "2-digit", year: "numeric",
                                                     hour: "2-digit", minute: "2-digit" });
}

function folderEntries() {
  const M = S.mailbox || { rubrics: [] };
  const f = [["inbox", "✉ Inbox", M.unread, true], ["outbox", "⇪ Outbox", M.outbox, false],
             ["sent", "✓ Sent", 0, false]];
  const r = M.rubrics.filter((x) => x.sub || x.local)
    .map((x) => ["b:" + x.name, "▤ " + (x.name === "TBNEWS" ? "TinyBox News" : x.name), x.unread, true]);
  return { folders: f, rubrics: r };            // the rubric list: gear in the head (CR54)
}

function navButton(key, label, n, strong, target) {
  const active = view === "mail" && folder === key;
  const b = el("button", "nav-item" + (active ? " active" : ""));
  const m = /^([^\w\s])\s+(.*)$/.exec(label);  // CR54: the symbol in the colour of the section
  if (m) { const s = el("span", ""); s.append(el("span", "ic", m[1]), " " + m[2]); b.append(s); }
  else b.append(el("span", "", label));
  if (n) b.append(el("span", strong ? "cnt" : "n", String(n)));
  b.onclick = () => openFolder(key);
  target.append(b);
}

/* Section head "Mail" / "Bulletins" with its own sync button and, below it,
 * what that sync is doing (or why it failed). The sync after the login
 * (scope "login", CR40) covers both: Abort in both heads, the step under the
 * one it is working on. Abort is orderly: the exchange on the air is finished. */
function syncHead(target, title, scope, gear) {
  const sy = S.sync || {};
  const mine = sy.scope === scope || sy.scope === "login";
  const running = sy.running && mine;
  const active = sy.scope === "login" ? ((sy.step || "").startsWith("bulletin") ? "bulletins" : "mail")
                                      : sy.scope;
  const h = el("div", "nav-h sync-h");
  const b = el("button", "sync-btn" + (running ? " run" : ""),
               running ? (sy.aborting ? "Aborting…" : "✕ Abort") : "⟳ Sync");
  b.title = running ? "Stop after the exchange on the air - the next sync goes on from there"
    : scope === "mail" ? "Send the outbox and fetch the headers of new personal mail"
                       : "Fetch the headers of new bulletins of the subscribed rubrics";
  b.disabled = (sy.running && !mine) || (running && sy.aborting);   // one sync at a time
  b.onclick = (ev) => { ev.stopPropagation(); api(running ? "mail/abort" : "mail/sync", { scope }); };
  if (gear) {                                    // CR54: rubric list behind the gear
    const tools = el("span", "sec-tools");
    const g = el("button", "sec-gear" + (view === "mail" && folder === "rubrics" ? " on" : ""), "\u2699\uFE0E");
    g.title = "Bulletin rubrics: subscribe";
    g.setAttribute("aria-label", "Bulletin rubrics");
    g.onclick = (ev) => { ev.stopPropagation(); openFolder("rubrics"); };
    tools.append(b, g);
    h.append(el("span", "", title), tools);
  } else h.append(el("span", "", title), b);
  target.append(h);
  let txt = "", err = false;
  if (running && active === scope) txt = sy.step + "…";
  else if (!sy.running && sy.scope === scope && sy.error) { txt = "Sync failed: " + sy.error; err = true; }
  if (txt) {
    const st = el("div", "sync-st" + (err ? " err" : ""), txt);
    if (running) {
      const bar = el("div", "sync-bar"), fill = el("div");
      fill.style.cssText = "height:3px;background:var(--accent);" +
        `width:${sy.total ? Math.round(100 * sy.done / sy.total) : 8}%`;
      bar.append(fill); st.append(bar);
    }
    target.append(st);
  }
}

function buildMailNav(target) {
  const { folders, rubrics } = folderEntries();
  const sy = S.sync || {};
  target.replaceChildren();
  if (sy.notice) {                               // CR40: what is pending, how long; abort
    const n = el("div", "sync-st note", sy.notice);
    const x = el("button", "icon-btn", "✕");
    x.title = "Dismiss";
    x.onclick = (ev) => { ev.stopPropagation(); noticeDismissed = sy.notice; render(); };
    if (noticeDismissed !== sy.notice) { n.prepend(x); target.append(n); }
  }
  // CR54: each section framed in its own colour
  const mail = el("section", "navsec sec-mail"), bul = el("section", "navsec sec-bul");
  target.append(mail, bul);
  syncHead(mail, "Mail", "mail");
  for (const [k, l, n, strong] of folders) navButton(k, l, n, strong, mail);
  syncHead(bul, "Bulletins", "bulletins", true);
  for (const [k, l, n, strong] of rubrics) navButton(k, l, n, strong, bul);
  if (!rubrics.length) bul.append(el("p", "muted small pad", "No rubric subscribed"));
}
let noticeDismissed = "";

function lastSyncText(M) {
  const bul = folder.startsWith("b:") || folder === "rubrics";
  const t = bul ? M.last_bulletins : M.last_mail;
  let txt = t ? `Last sync ${dateStr(t)}` : "Never synced";
  if (!bul && M.outbox + M.todo) txt += ` · ${M.outbox + M.todo} change(s) waiting`;
  if (!bul && M.missing) txt += ` · ${M.missing} text(s) on click`;
  return txt;
}

function renderMailbox() {
  const M = S.mailbox;
  if (!M) return;
  // badge on the top bar button; the icon switches between the two views
  $("view-cnt").textContent = String(M.unread);
  $("view-cnt").classList.toggle("hidden", !M.unread || view === "mail");
  buildMailNav($("nav-mailbox"));
  buildMailNav($("mvf-list"));                   // phone: folder list in the mail view
  $("mv-last").textContent = lastSyncText(M);
  $("mb-info").textContent = `${M.inbox} message(s) in the inbox, ${M.sent} sent, ` +
    `${M.rubrics.filter((r) => r.sub).length} rubric(s) subscribed. ` +
    `Mail synced ${M.last_mail ? longDate(M.last_mail) : "never"}, ` +
    `bulletins ${M.last_bulletins ? longDate(M.last_bulletins) : "never"}.`;
  $("mv-title").textContent = folderName(folder);
  $("mv-new").classList.toggle("hidden", folder === "rubrics");
  if (view === "mail") loadItems(false);
}

async function loadItems(force) {
  if (!S || !S.mailbox) return;
  const key = folder + "/" + S.mailbox.version;
  if (!force && key === itemsFor) return;
  itemsFor = key;
  if (folder === "rubrics") { items = []; renderItems(); return; }
  try {
    const r = await fetch("/api/mail?folder=" + encodeURIComponent(folder), { cache: "no-store" });
    if (!r.ok) return;
    const data = await r.json();
    if (data.folder !== folder) return;
    items = data.items;
  } catch (e) { return; }
  renderItems();
}

function renderItems() {
  const ul = $("mv-items");
  ul.replaceChildren();
  const empty = $("mv-empty");
  if (folder === "rubrics") { renderRubrics(ul); empty.classList.add("hidden"); return; }
  for (const m of items) ul.append(folder === "outbox" ? outItem(m) : msgItem(m));
  empty.classList.toggle("hidden", items.length > 0);
  empty.textContent = folder.startsWith("s:")
    ? "Nothing found here. Texts not fetched yet are searched by their header only."
    : folder === "outbox" ? "Nothing waiting to be sent."
    : folder.startsWith("b:") ? "No bulletins here yet - they come with the next sync."
    : "No messages. Sync to fetch new mail.";
}

function msgItem(m) {
  const sent = folder === "sent";
  const li = el("li", "mv-item" + (m.seen ? "" : " unread") + (selId === m.id ? " sel" : ""));
  const who = sent ? m.to_call : m.from_call;
  const txt = el("div", "txt");
  const l1 = el("div", "l1");
  const c = el("span", "c", (sent ? "→ " : "") + who + (m.at_addr ? " @" + m.at_addr.split(".")[0] : ""));
  l1.append(c, el("span", "d", dateStr(m.created)));
  const l2 = el("div", "l2", m.subject);
  txt.append(l1, l2);
  if (m.snippet) txt.append(el("div", "snip", m.snippet));          // CR49: where it was found
  const tags = el("div", "l1");
  const left = el("span");
  left.append(el("span", "muted small", "#" + m.id + " "));
  if (!m.has_body) {                             // CR40: the text comes when clicked
    const t = el("span", "tag", "not loaded · " + kbText(m.size));
    t.title = "Click to fetch the text";
    left.append(t);
  }
  if (m.type === "P" && m.status === "Y" && sent) left.append(el("span", "tag", "read"));
  if (folder.startsWith("s:")) {
    left.append(el("span", "tag", m.type === "B" ? "bulletin " + m.to_call : "personal"));
  }
  tags.append(left);
  txt.append(tags);
  li.append(el("span", "dotu"), avatar(who, symOf(who), true), txt);
  li.onclick = () => openMessage(m.id);
  return li;
}

function outItem(o) {
  const li = el("li", "mv-item" + (selId === "o" + o.oid ? " sel" : ""));
  const txt = el("div", "txt");
  const l1 = el("div", "l1");
  l1.append(el("span", "c", "→ " + o.to_call), el("span", "d", dateStr(o.created)));
  txt.append(l1, el("div", "l2", o.subject || "(no subject)"));
  const l3 = el("div", "l1");
  const t = el("span");
  t.append(el("span", "tag", o.type === "B" ? "bulletin" : "personal"));
  if (o.error) t.append(" ", el("span", "tag err", "refused: " + o.error));
  l3.append(t);
  txt.append(l3);
  li.append(avatar(o.to_call.split("@")[0], "", true), txt);
  li.onclick = () => openCompose(o);
  return li;
}

function renderRubrics(ul) {
  const M = S.mailbox;
  const intro = el("li", "mv-item rub");
  intro.append(el("span", "muted small", "Subscribed rubrics are fetched with each sync. " +
                  "Numbers: in the TinyBox / here. The list of rubrics comes with the bulletin sync."));
  ul.append(intro);
  if (!M.rubrics.length) { ul.append(el("li", "mv-item rub muted small", "No rubrics known yet - sync the bulletins first.")); return; }
  for (const r of M.rubrics) {
    const li = el("li", "mv-item rub");
    const lab = el("label");
    const cb = el("input"); cb.type = "checkbox"; cb.checked = r.sub;
    cb.onchange = () => api("mail/subscribe", { rubric: r.name, on: cb.checked });
    const name = el("span", "", "");
    name.style.flex = "1";
    name.append(el("span", "c", r.name));
    if (r.desc) name.append(el("span", "muted small rub-desc", r.desc));
    lab.append(cb, name, el("span", "muted small", `${r.server} / ${r.local}`));
    li.append(lab);
    ul.append(li);
  }
}

async function postJson(path, data) {
  const r = await fetch("/api/" + path, {
    method: "POST", headers: { "Content-Type": "application/json", "X-TBClient": "1" },
    body: JSON.stringify(data || {}),
  });
  try { return { ok: r.ok, data: await r.json() }; } catch (e) { return { ok: false, data: {} }; }
}

/* CR40: a message without text -> fetch it now. No connection: say so, and the
 * request is forgotten. The reader shows the progress and opens the text when
 * it is here (checkFetch, on every state change). */
let fetchWanted = null;           // id whose text is on its way
async function openMessage(id) {
  selId = id; draft = null;
  const r = await postJson("mail/open", { id });
  if (!r.ok) return;
  cur = r.data;
  if (cur.body === null) await fetchText(id);
  setLevel("read");
  showReader();
  renderItems();
}

async function fetchText(id) {
  const f = await postJson("mail/fetch", { id });
  if (f.ok && f.data.ok) { fetchWanted = id; cur.fetchError = ""; }
  else { fetchWanted = null; cur.fetchError = (f.data && f.data.error) || "not possible"; }
}

let fetchSeen = false;            // the fetch was seen running
async function checkFetch() {
  if (fetchWanted === null || !cur || cur.id !== fetchWanted) return;
  const sy = S.sync || {};
  if (sy.running) { fetchSeen = true; showReader(); return; }
  const r = await postJson("mail/open", { id: fetchWanted });
  if (r.ok && r.data.body !== null) {
    cur = r.data; fetchWanted = null; fetchSeen = false;
    showReader(); renderItems();
  } else if (fetchSeen || sy.fetch_error) {
    cur.fetchError = sy.fetch_error || "aborted";
    fetchWanted = null; fetchSeen = false;
    showReader();
  }
}

function showReader() {
  const reading = !!cur && !draft;
  $("rd-msg").classList.toggle("hidden", !reading);
  $("cp").classList.toggle("hidden", !draft);
  $("rd-none").classList.toggle("hidden", reading || !!draft);
  $("rd-reply").classList.toggle("hidden", !reading);
  $("rd-delete").classList.toggle("hidden", !reading);
  if (!reading) return;
  const m = cur;
  $("rd-av").replaceChildren(avatar(m.from_call, symOf(m.from_call)));
  $("rd-subject").textContent = m.subject;
  const l1 = $("rd-line1");
  l1.replaceChildren(el("span", "c", m.from_call), " → ",
                     el("span", "c", m.to_call + (m.at_addr ? " @ " + m.at_addr : "")));
  $("rd-line2").textContent = `${longDate(m.created)} · #${m.id}` + (m.bid ? ` · BID ${m.bid}` : "") +
    (m.type === "B" ? " · bulletin" : "");
  const body = $("rd-body");
  body.replaceChildren();
  body.className = "rd-body" + (m.body === null ? " missing" : "");
  if (m.body === null) {
    const sy = S.sync || {};
    if (fetchWanted === m.id) {
      body.append(`Loading the text (${kbText(m.size)})` +
                  (sy.running && sy.fetch === m.id && sy.step.startsWith("text") ? ` - ${sy.step}` : "") + "… ");
      const a = el("button", "sm", sy.aborting ? "Aborting…" : "Abort");
      a.disabled = !!sy.aborting;
      a.onclick = () => api("mail/abort");
      body.append(a);
    } else {
      body.append(m.fetchError === "not connected" ? "Not connected - the text cannot be fetched now. "
                  : m.fetchError ? `Text not fetched (${m.fetchError}). ` : "The text is not here yet. ");
      const f = el("button", "sm", "Fetch text");
      f.onclick = async () => { await fetchText(m.id); showReader(); };
      body.append(f);
    }
  }
  else for (const [i, line] of m.body.split("\n").entries()) {
    if (i) body.append("\n");
    linkify(body, line);
  }
  $("rd-delete").title = m.type === "P" ? "Delete here and in the TinyBox (with the next sync)"
                                        : "Delete here only (bulletins belong to everyone)";
}

function linkify(parent, text) {
  let last = 0;
  for (const m of text.matchAll(URL_RE)) {
    let url = m[0];
    const trail = url.match(/[.,!?;:)\]'"]+$/);
    if (trail) url = url.slice(0, -trail[0].length);
    if (!url) continue;
    parent.append(text.slice(last, m.index));
    const a = el("a", "", url);
    a.href = /^https?:\/\//i.test(url) ? url : "http://" + url;
    a.target = "_blank"; a.rel = "noopener noreferrer";
    parent.append(a);
    last = m.index + url.length;
  }
  parent.append(text.slice(last));
}

// --- composing ---------------------------------------------------------------------
/* Bulletins (CR19): when the TinyBox has a rubric list, the rubric is picked from
   it and the text field only takes the optional area (@WW). Without a list (or
   before the first bulletin sync) the rubric is typed as before. */
function rubricList() {
  return (S.mailbox && S.mailbox.writable) || [];
}

function setType(t) {
  const wasPick = !!draft.pick;
  draft.type = t;
  const list = t === "B" ? rubricList() : [];
  draft.pick = list.length > 0;
  $("cp-p").classList.toggle("on", t === "P");
  $("cp-b").classList.toggle("on", t === "B");
  $("cp-to-l").textContent = t === "P" ? "To" : "Rubric";
  $("cp-rub").classList.toggle("hidden", !draft.pick);
  if (draft.pick && !wasPick) {
    const to = $("cp-to").value.trim().toUpperCase().replace(/\s+/g, "");
    const [rub, area] = to.split("@");
    const sel = $("cp-rub");
    sel.replaceChildren();
    for (const r of list) {
      const o = el("option", "", r.desc ? `${r.name} – ${r.desc}` : r.name);
      o.value = r.name;
      sel.append(o);
    }
    let value = list[0].name, keep = "";
    if (list.some((r) => r.name === rub)) { value = rub; keep = area || ""; }
    else if (to && to === draft.origTo) {               // outbox draft to a closed rubric
      const o = el("option", "", `${rub} – not open here`);
      o.value = rub; o.disabled = true;
      sel.append(o);
      value = rub; keep = area || "";
    }
    sel.value = value;
    $("cp-to").value = keep;
  } else if (!draft.pick && wasPick) {
    $("cp-to").value = "";
  }
  $("cp-to").placeholder = draft.pick ? "@ area, e.g. WW (optional)"
    : t === "P" ? "OE3ABC, OE3ABC@OE3XYZ or OE3ABC,OE3XYZ" : "ALL, WX ... or ALL@WW";
  composeInfo();
}

function composeTo() {
  // several recipients (CR27): comma, semicolon or blank between the calls -> "A,B"
  let to = $("cp-to").value.trim().toUpperCase()
    .replace(/\s*@\s*/g, "@").replace(/[\s,;]+/g, ",").replace(/^,|,$/g, "");
  if (draft.type === "B" && rubricList().length) {
    to = to.replace(/^@/, "");
    return $("cp-rub").value + (to ? "@" + to : "");
  }
  return to;
}

function openCompose(o) {
  o = o || {};
  draft = { oid: o.oid || null, type: o.type || "P",
            origTo: o.type === "B" ? (o.to_call || "").toUpperCase() : "" };
  selId = o.oid ? "o" + o.oid : null;
  cur = null;
  $("cp-to").value = o.to_call || "";
  $("cp-subj").value = o.subject || "";
  $("cp-body").value = o.body || "";
  $("cp-err").classList.toggle("hidden", !o.error);
  $("cp-err").textContent = o.error ? "The TinyBox refused it: " + o.error : "";
  $("cp-discard").textContent = o.oid ? "Delete from outbox" : "Discard";
  setType(draft.type);
  setView("mail");
  setLevel("compose");
  showReader();
  renderItems();
  setTimeout(() => $(o.to_call ? "cp-body" : "cp-to").focus(), 0);
}

function reply() {
  if (!cur) return;
  const subj = /^re:/i.test(cur.subject) ? cur.subject : "Re: " + cur.subject;
  const quote = (cur.body || "").split("\n").slice(0, 20).map((l) => "> " + l).join("\n");
  openCompose({ type: "P", to_call: cur.from_call.split("-")[0], subject: subj.slice(0, 60),
                body: `\n\n${cur.from_call} wrote:\n${quote}\n` });
  $("cp-body").setSelectionRange(0, 0);
}

function composeInfo() {
  const enc = new TextEncoder();
  const n = enc.encode($("cp-subj").value).length + enc.encode($("cp-body").value).length;
  const sec = Math.ceil(n * 10 / 1200 * 1.3);          // 1200 Bd, ~30 % protocol overhead
  $("cp-info").textContent = `${n} bytes · about ${sec < 60 ? sec + " s" : Math.ceil(sec / 60) + " min"} on air at 1200 Bd`;
}

async function saveCompose(ev) {
  ev.preventDefault();
  const to = composeTo();
  const err = $("cp-err");
  const ok = draft.type === "P" ? /^[A-Z0-9]{1,6}(-\d{1,2})?(,[A-Z0-9]{1,6}(-\d{1,2})?){0,9}(@[A-Z0-9#.-]{1,40})?$/.test(to)
                                : /^[A-Z0-9]{1,6}(@[A-Z0-9#.-]{1,40})?$/.test(to);
  if (!ok) {
    err.textContent = draft.type === "P" ? "Please enter calls, e.g. OE3ABC, OE3ABC@OE3XYZ or OE3ABC OE3XYZ (up to 10)."
                     : draft.pick ? "Please check the area, e.g. WW or AUT (or leave it empty)."
                                         : "Please enter a rubric, e.g. ALL or ALL@WW.";
    err.classList.remove("hidden");
    return;
  }
  if (!$("cp-subj").value.trim()) {
    err.textContent = "Please enter a subject."; err.classList.remove("hidden"); return;
  }
  const r = await postJson("mail/save", { oid: draft.oid, type: draft.type, to,
                                          subject: $("cp-subj").value, body: $("cp-body").value });
  if (!r.ok) { err.textContent = "Not saved: " + (r.data.error || "error"); err.classList.remove("hidden"); return; }
  draft = null; selId = null;
  openFolder("outbox");
}

async function discardCompose() {
  if (draft && draft.oid) await api("mail/discard", { oid: draft.oid });
  draft = null; selId = null;
  setLevel("list");
  showReader();
  renderItems();
}

async function deleteCurrent() {
  if (!cur) return;
  await api("mail/delete", { id: cur.id });
  cur = null; selId = null;
  setLevel("list");
  showReader();
  loadItems(true);
}

function initMail() {
  $("btn-view").onclick = () => setView(view === "mail" ? backView() : "mail");
  $("btn-chat").onclick = goChat;
  document.querySelectorAll(".mv-tochat").forEach((b) => { b.onclick = () => setView("chat"); });
  $("mv-back-folders").onclick = () => setLevel("folders");
  $("mv-back-list").onclick = () => { draft = null; setLevel("list"); showReader(); };
  // CR49: search in the mail and bulletins here (as you type, from 2 characters)
  let searchTimer = 0, beforeSearch = "inbox";
  $("mv-search").addEventListener("input", (e) => {
    clearTimeout(searchTimer);
    const q = e.target.value.trim();
    searchTimer = setTimeout(() => {
      if (q.length >= 2) {
        if (!folder.startsWith("s:")) beforeSearch = folder;
        openFolder("s:" + q);
      } else if (folder.startsWith("s:")) openFolder(beforeSearch);
    }, 250);
  });
  $("mv-new").onclick = () => openCompose({ type: folder.startsWith("b:") ? "B" : "P",
                                            to_call: folder.startsWith("b:") ? folder.slice(2) : "" });
  $("mb-sync").onclick = () => { api("mail/sync", { scope: "mail" }); openFolder("inbox"); };
  $("rd-reply").onclick = reply;
  $("rd-delete").onclick = deleteCurrent;
  $("cp-p").onclick = () => setType("P");
  $("cp-b").onclick = () => setType("B");
  $("cp-subj").oninput = composeInfo;
  $("cp-body").oninput = composeInfo;
  $("cp").onsubmit = saveCompose;
  $("cp-discard").onclick = discardCompose;
  setView(view);
  setLevel("list");
  showReader();
}

// ---------------------------------------------------------------- channels (CR45)
// Up to 5 connections, one window each, shown one at a time; channel 0 is the
// monitor. The top bar always shows the active channel; a chip blinks when
// something came in behind the scenes, red when a connection went away there.
let activeCh = 1;
try { activeCh = Math.max(0, Math.min(5, parseInt(localStorage.getItem("tbc-ch") || "1", 10) || 0)); } catch (e) { /* ok */ }
let pollCtl = null;           // aborts the waiting long poll when the channel changes
const seenAct = {}, seenEnd = {};
let manualTerm = false;       // the terminal of the TinyBox, opened by hand
let lastFocus = null;         // CR75: focus.seq last seen (null = not yet, no jump on load)

function chanOf(n) {
  const c = S && S.channels ? S.channels.find((x) => x.n === n) : null;
  return c || { n, target: "", state: "offline", reason: "", state_age: 0, ended: null,
                mode: "", view: "term", chat: false, act: 0, term_n: 0, outstanding: null, virtual: true };
}
const curCh = () => chanOf(activeCh);

/* CR54: Chat and Mailbox each have a button in the top bar; the one of the view
 * shown is filled. Mailbox pressed again goes back to where you came from. */
function renderViewBtns() {
  const back = backView();
  const backName = back === "term" ? (activeCh === 0 ? "Monitor" : "Terminal") : "Chat";
  const mt = view === "mail" ? "Back to " + backName : "Mailbox";
  $("btn-view").title = mt;
  $("btn-view").setAttribute("aria-label", mt);
  $("btn-view").classList.toggle("on", view === "mail");
  $("btn-chat").classList.toggle("on", view === "chat");
  $("nav-monitor").classList.toggle("active", view === "term" && activeCh === 0);
  $("nav-terminal").classList.toggle("active", view === "term" && activeCh !== 0);
  $("nav-stats").classList.toggle("active", view === "stats");
}

function goChat() {
  if (S && S.chat_ch && activeCh !== S.chat_ch) switchCh(S.chat_ch);
  manualTerm = false;
  if (activeCh !== 0 && curCh().chat) setView("chat");
  else if (S) render();
}

function baseView() {
  if (activeCh === 0) return "term";
  return curCh().chat ? "chat" : "term";
}
const backView = () => (manualTerm && curCh().chat ? "term" : baseView());

function switchCh(n) {
  if (n < 0 || n > (S ? S.max_ch : 5)) return;
  if (n === activeCh) {                            // CR58: already this channel, but maybe
    if (view !== backView()) setView(backView());  // the mailbox is shown: back to the channel
    if (S) render();
    return;
  }
  activeCh = n;
  manualTerm = false;
  try { localStorage.setItem("tbc-ch", String(n)); } catch (e) { /* ok */ }
  termShown = -1;                                  // the terminal shows another channel now
  monDirty = true;
  setView(baseView());
  if (pollCtl) pollCtl.abort();                    // fetch the lines of that channel now
  if (S) render();
}

function newChannel() {
  const used = new Set((S.channels || []).map((c) => c.n));
  const n = [1, 2, 3, 4, 5].find((x) => !used.has(x));
  if (n) { switchCh(n); setTimeout(() => $("to-call").focus(), 0); }
}

function renderStrip() {
  const strip = $("chstrip");
  const chans = S.channels || [];
  const items = [];
  const mon = el("button", "ch" + (activeCh === 0 ? " act" : ""));
  mon.append(el("span", "chn", "0"), el("span", "", "Monitor"));
  mon.title = "Monitor: everything heard (Alt+0)";
  mon.onclick = () => switchCh(0);
  items.push(mon);
  const list = chans.slice();
  if (activeCh && !chans.some((c) => c.n === activeCh)) list.push(chanOf(activeCh));   // the new one
  list.sort((a, b) => a.n - b.n);
  for (const c of list) {
    const act = c.n === activeCh;
    if (seenAct[c.n] === undefined || act) seenAct[c.n] = c.act;
    const endAt = c.ended && (c.ended.kind === "remote" || c.ended.kind === "failed") ? c.ended.at : 0;
    if (seenEnd[c.n] === undefined || act) seenEnd[c.n] = endAt;
    const disc = !act && endAt > seenEnd[c.n];
    const news = !act && !disc && c.act > seenAct[c.n];
    const b = el("button", "ch" + (act ? " act" : "") + (disc ? " blink-disc" : news ? " blink" : ""));
    const dot = el("span", "dot " + (c.ended && c.state === "offline" && c.ended.kind === "failed" ? "failed" : c.state));
    b.append(el("span", "chn", String(c.n)), dot, el("span", "", c.target || "new"));
    if (c.chat && c.state !== "offline") b.append(el("span", "chtag", "chat"));
    b.title = `Channel ${c.n} (Alt+${c.n})` + (c.target ? `: ${c.target}, ${c.state}` : "");
    b.onclick = () => switchCh(c.n);
    if (c.state === "offline" && !c.virtual && chans.length > 1) {
      const x = el("span", "chx", "✕");
      x.title = "Close channel " + c.n;
      x.onclick = (e) => {
        e.stopPropagation();
        api("channel/close", { ch: c.n }).then(() => { if (activeCh === c.n) switchCh(0); });
      };
      b.append(x);
    }
    items.push(b);
  }
  if (list.length < (S.max_ch || 5) && S.link !== "telnet" && (activeCh === 0 || !chanOf(activeCh).virtual)) {
    const plus = el("button", "ch chnew", "+ new");
    plus.title = "New connection in a free channel";
    plus.onclick = newChannel;
    items.push(plus);
  }
  strip.replaceChildren(...items);
  strip.classList.toggle("hidden", S.link === "telnet");
}

// ---------------------------------------------------------------- top bar (CR42)
// One line: own call, icon, the "Connect to" field (offline) or the other call,
// the status; on the right Disconnect, Mailbox/Chat and the menu.
let stateRecv = 0;            // performance.now() when the snapshot came in
let recentShown = "";
let lastEndAt = 0;
const CALL_OK = /^[A-Z0-9]{1,6}(-([0-9]|1[0-5]))?$/;
const MAX_VIA = 8;            // AX.25: at most 8 digipeaters

// CR71: "OE3XYZ-1 V OE3XTC-5,OE3ABC" -> {call, via} or {error}. Same rules as
// tbclient/target.py: V or VIA, commas and/or spaces, at most 8 digipeaters.
function parseTarget(text) {
  const w = String(text || "").trim().toUpperCase().split(/[\s,]+/).filter(Boolean);
  if (!w.length) return { error: "no call" };
  const call = w[0];
  let via = w.slice(1);
  if (!CALL_OK.test(call)) return { error: `${call}: not a call (e.g. OE3XYZ-8)` };
  if (S && call === S.mycall) return { error: "that is your own call" };
  if (via.length && (via[0] === "V" || via[0] === "VIA")) {
    via = via.slice(1);
    if (!via.length) return { error: "digipeater missing after VIA" };
  } else if (via.length) return { error: `after the call: V or VIA, not ${via[0]}` };
  if (via.length > MAX_VIA) return { error: `at most ${MAX_VIA} digipeaters` };
  for (const d of via) {
    if (!CALL_OK.test(d)) return { error: `${d}: not a digipeater call` };
    if (d === call || (S && d === S.mycall)) return { error: `${d} cannot be its own digipeater` };
  }
  if (new Set(via).size !== via.length) return { error: "a digipeater twice in the path" };
  return { call, via };
}
const targetLabel = (call, via) => call + (via && via.length ? " via " + via.join(",") : "");

// CR71: the field grows with the path; below it a preview (or what is wrong)
function targetPreview() {
  const inp = $("to-call"), hint = $("to-hint");
  const v = inp.value.trim();
  inp.style.width = `calc(${Math.max(9, v.length + 1)}ch + 20px)`;
  if (!v || !/[\s,]/.test(v)) { hint.classList.add("hidden"); return; }
  const p = parseTarget(v);
  hint.classList.toggle("bad", !!p.error);
  hint.textContent = p.error ? p.error
    : p.via.length ? `to ${p.call} · via ${p.via.join(" → ")}`
      + (p.via.length >= 3 ? " · many hops, slow" : "") : `to ${p.call}`;
  hint.classList.remove("hidden");
}

function setConnIcon(name, cls) {
  const ic = $("conn-ic");
  const src = "/conn/" + name + ".png";
  if (ic.getAttribute("src") !== src) ic.setAttribute("src", src);
  ic.className = "conn-ic" + (cls ? " " + cls : "");
}

// how the last connection of channel c ended, in words ("" = nothing to tell)
function endedText(c) {
  c = c || curCh();
  const e = c.ended;
  if (c.state !== "offline" || !e || e.kind === "user") return "";
  if (e.kind === "failed") {
    return c.reason && c.reason !== "disconnected" ? `connect failed: ${c.reason}`
      : `no answer from ${e.call}`;
  }
  return (c.reason && c.reason !== "disconnected" ? c.reason : `disconnected by ${e.call}`)
    + " · " + hhmm(e.at);
}

function topStatus() {
  const c = curCh();
  if (activeCh === 0) {
    const q = (S.channels || []).filter((x) => x.outstanding !== null && x.state === "online")
      .map((x) => `${x.n}: ${x.outstanding}`);
    return radioText() + ` · ${S.monitor_n} frames` + (q.length ? ` · waiting to send ${q.join(", ")}` : "");
  }
  if (c.state === "connecting") {
    const secs = Math.round(c.state_age + (performance.now() - stateRecv) / 1000);
    return `connecting · ${secs} s`;
  }
  if (c.state === "disconnecting") return "disconnecting…";
  if (c.state === "online") {
    if (c.mode === "terminal") return "connected · terminal";
    if (!c.chat || c.mode !== "tinybox") return "connected";
    return (S.board ? `${S.board.name} · ${S.members.length} here` : "connected")
      + (c.link === "axudp" ? " · AXUDP" : S.ui ? " · UI" : " · I-frames");
  }
  return endedText(c) || (radioUp() ? "offline" : radioText());
}

// CR46: the way to the radio - Direwolf (AGW) or kisshub with its TNC (KISS)
const radioUp = () => !S.radio || S.radio.up;
function radioText() {
  const r = S.radio || {};
  if (r.via === "telnet") return "telnet test port";
  if (r.via === "agw") return r.up ? "Direwolf" : "Direwolf not reachable";
  if (!r.up) return "kisshub not reachable";
  if (!r.tnc) return "kisshub";
  return `${r.tnc} ${r.tnc_state === "kiss" || !r.tnc_state ? "ready" : r.tnc_state} via KISS`;
}

function renderTop() {
  renderStrip();
  const c = curCh(), mon = activeCh === 0;
  const st = c.state, off = st === "offline" && !mon;
  const kind = off && c.ended ? c.ended.kind : "";
  $("me-call").textContent = S.mycall;
  $("to-form").classList.toggle("hidden", !off);
  $("tb-call").classList.toggle("hidden", off);
  $("tb-call").replaceChildren(mon ? "Monitor" : c.target || "");
  if (!mon && c.via && c.via.length) {           // CR71: the path, smaller
    $("tb-call").append(" ", el("span", "via", "via " + c.via.join(",")));
  }
  $("tb-call").classList.toggle("dim", st === "disconnecting" || mon);
  $("btn-disc").classList.toggle("hidden", mon || st === "offline" || st === "disconnecting");
  $("btn-disc").title = st === "connecting" ? "Stop connecting" : "Disconnect";
  const inp = $("to-call");
  const last = (c.target ? targetLabel(c.target, c.via) : "") || (S.recent || [])[0] || S.home;
  inp.placeholder = last;
  inp.readOnly = S.link === "telnet";          // the test port is always the own TinyBox
  inp.title = S.link === "telnet" ? "Telnet test port: always " + S.home
    : "Call of the station, digipeaters with V: OE3XYZ-8 V OE3ABC-5 (Enter = connect). Empty = "
      + last + ". Via is digipeating only - a node (NET/ROM, BPQ) is connected first, then C there.";
  const rec = (S.recent || []).join(",");
  if (rec !== recentShown) {
    recentShown = rec;
    $("to-recent").replaceChildren(...(S.recent || []).map((x) => { const o = el("option"); o.value = x; return o; }));
  }
  $("conn-ic").classList.toggle("hidden", mon);
  if (st === "connecting") setConnIcon("connecting", "wide pulse");
  else if (st === "online") setConnIcon("connected");
  else if (st === "disconnecting") setConnIcon("disconnected", "pulse");
  else setConnIcon(kind === "failed" ? "failed" : kind === "remote" ? "disconnected" : "connect");
  $("status-dot").className = "dot " + (!radioUp() ? "failed" : mon ? "online" : kind === "failed" ? "failed" : st);
  $("status-text").textContent = topStatus();
}
setInterval(() => { if (S && curCh().state === "connecting") $("status-text").textContent = topStatus(); }, 1000);

function connectTo(e) {
  e.preventDefault();
  const inp = $("to-call");
  const p = parseTarget(inp.value.trim() || inp.placeholder);
  if (p.error) {
    inp.classList.add("bad");
    inp.title = p.error;
    targetPreview();
    return;
  }
  const t = p.call;
  const busy = (S.channels || []).find((x) => x.target === t && x.state !== "offline");
  if (busy) { inp.classList.add("bad"); inp.title = `${t} is connected in channel ${busy.n}`; switchCh(busy.n); return; }
  inp.value = "";
  targetPreview();
  inp.blur();
  api("connect", { target: targetLabel(t, p.via), ch: activeCh || undefined });
}

// ---------------------------------------------------------------- terminal (CR43)
// Any station that is no TinyBox: lines in, lines out. On a TinyBox it can be
// opened by hand (Settings / navigation) - typed lines go to it as they are.
// Channel 0 shows the monitor here, read only.
let termShown = 0;            // number of the last line in the view (-1 = start over)
const termHist = [];
let termHistPos = 0;

function autoTerm() {
  if (view === "mail" || view === "stats") return;
  const want = backView();
  if (view !== want) setView(want);
}

// CR65: the statistics of one call, from the monitor; Back returns to the same place
let statsFromMon = null;
function openStationStats(call) {
  if (view === "term" && activeCh === 0) statsFromMon = $("term-out").scrollTop;
  AprsStatsView.openStation(call.replace(/\*$/, ""));
  setView("stats");
}

function showLens() {                           // CR55: the APRS lens only next to the monitor
  $("aprs-lens").hidden = !(activeCh === 0 && AprsView.lensOn());   // CR62: only in step 2
}

function renderTerm() {
  const out = $("term-out");
  const lines = S.ch === activeCh ? (S.term || []) : [];
  const c = curCh(), mon = activeCh === 0;
  $("term-title").textContent = mon ? "Monitor" : "Terminal";
  $("term-to").textContent = mon ? "everything heard on the channel"
    : c.state === "online" ? `${S.mycall} ↔ ${targetLabel(c.target, c.via)}`
      + (c.chat ? " (TinyBox: lines go to it as typed)" : "")
    : c.target ? `${c.target} - not connected` : "not connected - enter a call in the top bar";
  $("term-close").classList.toggle("hidden", !c.chat || mon);
  $("term-form").classList.toggle("hidden", mon);
  $("mon-tools").classList.toggle("hidden", !mon);
  $("ui-form").classList.toggle("hidden", !mon || !uiOpen);
  $("mon-ui").classList.toggle("on", uiOpen);
  showLens();
  $("term-input").disabled = c.state !== "online";
  if (S.ch !== activeCh) return;                   // lines of another channel: wait
  if (mon) { renderMonitor(); return; }
  if (termShown < 0 || S.term_n < termShown || (lines.length && lines[0][0] > termShown + 1)) {
    out.replaceChildren();                       // other channel, restart, or lines missed
    termShown = lines.length ? lines[0][0] - 1 : 0;
  }
  const atBottom = out.scrollTop + out.clientHeight >= out.scrollHeight - 40;
  for (const [n, kind, text] of lines) {
    if (n <= termShown) continue;
    out.append(el("span", kind, (kind === "tx" ? "> " : "") + text + "\n"));
  }
  termShown = Math.max(termShown, S.term_n || 0);
  while (out.childNodes.length > 600) out.firstChild.remove();
  if (atBottom) out.scrollTop = out.scrollHeight;
}

// ---------------------------------------------------------------- monitor (CR50)
// Channel 0: every frame heard, the calls in colours of their own (the same call
// always the same colour), a filter by text and by kind of TinyBox frame, Clear.
let monLines = [];            // [n, entry] as they came, max. 600
let monShown = 0;             // highest n taken into monLines
let monDirty = true;          // filter changed: draw everything again

function callColor(call) {
  let h = 2166136261;
  for (const ch of call) h = Math.imul(h ^ ch.charCodeAt(0), 16777619) >>> 0;
  return `hsl(${h % 360}, 70%, ${62 + (h >> 9) % 12}%)`;
}
function callSpan(call) {
  const s = el("span", "mc", call);
  s.style.color = callColor(call);
  return s;
}
function monText(e) {
  return (`${e.t} ${e.src} ${e.dst} ${(e.via || []).join(",")} <${e.typ}> ${e.kind} ${e.text}` +
          (e.aprs ? " aprs" + AprsView.searchText(e) : "")).toLowerCase();
}
function monMatch(e) {
  const q = $("mon-q").value.trim().toLowerCase();
  const k = $("mon-kind").value;
  if (k === "aprs" ? !e.aprs : k === "tb" ? !e.kind : k && e.kind !== k) return false;
  return !q || monText(e).includes(q);
}
function monLine(e) {
  const ap = AprsView.active(e);                // CR55/62: APRS as a card (Frame + Interpretation)
  const line = el("span", ap ? "" : "ml");
  line.append(el("span", "mt", e.t + " "), callSpan(e.src), " → ", ap ? AprsView.dest(e) : callSpan(e.dst));
  if (e.via && e.via.length) {
    line.append(" via ");
    e.via.forEach((v, i) => { if (i) line.append(","); line.append(callSpan(v.replace(/\*$/, ""))); if (v.endsWith("*")) line.append("*"); });
  }
  line.append(el("span", "mty", ` <${e.typ}>`));
  if (e.kind) line.append(el("span", "mk " + e.kind, e.kind));
  if (ap) return AprsView.card(e, line, "ml");
  if (e.text) line.append(": " + e.text);
  line.append("\n");
  return line;
}

function renderMonitor() {
  const out = $("term-out");
  const lines = S.term || [];
  if (lines.length && lines[0][0] > monShown + 1 && monShown) monDirty = true;   // missed some
  if (!lines.length || (lines.length && S.term_n < monShown)) {                    // cleared / restart
    if (monLines.length) monDirty = true;
    monLines = [];
    monShown = S.term_n || 0;
  }
  const fresh = lines.filter(([n]) => n > monShown).map(([n, , e]) => [n, e]);
  monLines = monLines.concat(fresh).slice(-600);
  monShown = Math.max(monShown, S.term_n || 0);
  const atBottom = out.scrollTop + out.clientHeight >= out.scrollHeight - 40;
  termShown = -1;                               // a terminal shown later starts over
  if (monDirty) {                               // filter changed, or just switched here
    out.replaceChildren(...monLines.filter(([, e]) => monMatch(e)).map(([, e]) => monLine(e)));
    monDirty = false;
  } else {
    for (const [, e] of fresh) if (monMatch(e)) out.append(monLine(e));
    while (out.childNodes.length > 600) out.firstChild.remove();
  }
  if (atBottom) out.scrollTop = out.scrollHeight;
}

// ---------------------------------------------------------------- UI frame (CR66)
// "Send UI" in the monitor bar: one unproto frame to any call, optional via,
// e.g. to test a modem (VARA FM KISS). The text stays for a quick repeat.
var uiOpen = false;   // var: renderTerm may run before this line
const UI_KEEP = "tbc.ui";     // last To / Via (this browser only)
function uiBytes() { return new TextEncoder().encode($("ui-text").value).length; }
function uiCount() {
  const n = uiBytes();
  $("ui-n").textContent = n + " B";
  $("ui-n").classList.toggle("bad", n > 1024);
}
function uiToggle() {
  uiOpen = !uiOpen;
  if (uiOpen) {
    try {
      const k = JSON.parse(localStorage.getItem(UI_KEEP) || "{}");
      if (k.dest) $("ui-dest").value = k.dest;
      if (k.via !== undefined) $("ui-via").value = k.via;
    } catch (e) { /* no storage: the defaults */ }
    $("ui-msg").textContent = "";
  }
  renderTerm();
  if (uiOpen) $("ui-text").focus();
}
async function uiSend(e) {
  e.preventDefault();
  const dest = $("ui-dest").value.trim().toUpperCase() || "CQ";
  const via = $("ui-via").value.trim().toUpperCase();
  const text = $("ui-text").value;
  const msg = $("ui-msg");
  msg.className = "small";
  if (!text) { msg.textContent = "no text"; msg.classList.add("bad"); return; }
  try { localStorage.setItem(UI_KEEP, JSON.stringify({ dest, via })); } catch (err) { /* fine */ }
  const r = await postJson("ui", { dest, via, text });
  if (r.ok) {
    msg.textContent = `sent ${new Date().toLocaleTimeString()} (${uiBytes()} B)`;
    msg.classList.add("good");
    $("ui-text").select();                        // Enter again = the same frame once more
  } else {
    msg.textContent = (r.data && r.data.error) || "not sent";
    msg.classList.add("bad");
  }
}

async function termSend(e) {
  e.preventDefault();
  const inp = $("term-input");
  const text = inp.value;
  if (!S || curCh().state !== "online" || !activeCh) return;
  if (text && termHist[termHist.length - 1] !== text) termHist.push(text);
  termHist.splice(0, Math.max(0, termHist.length - 50));
  termHistPos = termHist.length;
  inp.value = "";
  await api("term", { text, ch: activeCh });
}

function termKey(e) {
  if (e.key !== "ArrowUp" && e.key !== "ArrowDown") return;
  e.preventDefault();
  termHistPos = Math.max(0, Math.min(termHist.length, termHistPos + (e.key === "ArrowUp" ? -1 : 1)));
  e.target.value = termHist[termHistPos] || "";
}

// ---------------------------------------------------------------- connection log (CR44)
function durText(s) {
  s = Math.max(0, s || 0);
  return s >= 3600 ? `${Math.floor(s / 3600)}h${String(Math.floor(s % 3600 / 60)).padStart(2, "0")}m`
    : `${Math.floor(s / 60)}m${String(s % 60).padStart(2, "0")}`;
}
function byteText(n) { return n === null || n === undefined ? "-" : n < 1000 ? String(n) : (n / 1000).toFixed(1) + "k"; }
async function loadConnlog() {
  let rows = [];
  try { rows = await (await fetch("/api/connlog", { cache: "no-store" })).json(); } catch (e) { return; }
  const ENDED = { user: "", remote: "by station", failed: "no answer", cancelled: "cancelled" };
  $("clog").replaceChildren(...(rows.length ? rows.map((r) => {
    const tr = el("tr", r.ended === "failed" || r.ended === "cancelled" ? "failed" : "");
    const d = new Date(r.start);
    tr.append(el("td", "", d.toLocaleDateString([], { day: "2-digit", month: "2-digit" }) + " " + hhmm(d / 1000)),
      el("td", "", r.secs || r.rx !== null ? durText(r.secs) : "-"), el("td", "", r.call),
      el("td", "", r.rx === null ? "-" : byteText(r.rx) + " / " + byteText(r.tx)),
      el("td", "end", ENDED[r.ended] || ""));
    return tr;
  }) : [(() => { const tr = el("tr"); const td = el("td", "end", "No connections yet."); td.colSpan = 5; tr.append(td); return tr; })()]));
}

// own profile (CR73): banner as long as name or locator are missing, form, settings line
let profErrSeen = "";
function renderProfile() {
  $("prof-banner").classList.toggle("hidden", !S.profile_ask);
  const p = S.profile || {};
  $("prof-now").textContent = S.profile_set || p.loc
    ? [p.name || "no name", p.loc || "no locator", p.home ? `home BBS ${p.home}` : ""].filter(Boolean).join(" · ")
    : "not given yet";
  $("prof-note").textContent = S.profile_err ? `The TinyBox refused it (${PROF_FIELDS[S.profile_err] || S.profile_err}) - please correct it.`
    : S.profile_box ? "" : "Goes to the TinyBox with the next connection.";
  if (S.profile_err && S.profile_err !== profErrSeen) { profErrSeen = S.profile_err; openProfile(); }
  if (!S.profile_err) profErrSeen = "";
}
const PROF_FIELDS = { name: "name: up to 12 letters", loc: "locator: 4 or 6 characters, e.g. JN88EP",
                      home: "home BBS: a mailbox call, e.g. OE3XSR" };
function openProfile() {
  const p = (S && S.profile) || {};
  $("prof-name").value = p.name || "";
  $("prof-loc").value = p.loc || "";
  $("prof-home").value = p.home || "";
  $("prof-err").classList.toggle("hidden", !(S && S.profile_err));
  $("prof-err").textContent = S && S.profile_err ? `Check the ${PROF_FIELDS[S.profile_err]}.` : "";
  $("sheet").classList.add("hidden");
  $("profdlg").classList.remove("hidden");
  $(p.name ? "prof-loc" : "prof-name").focus();
}
async function saveProfile(e) {
  e.preventDefault();
  const r = await postJson("profile", { name: $("prof-name").value, loc: $("prof-loc").value,
                                        home: $("prof-home").value });
  if (!r.ok) {
    $("prof-err").textContent = `Check the ${PROF_FIELDS[r.data.error] || "input"}.`;
    $("prof-err").classList.remove("hidden");
    return;
  }
  $("profdlg").classList.add("hidden");
}

// frequency of this session (CR44): asked once per start of the client
let freqShown = false;
function renderFreq() {
  $("freq-now").textContent = S.freq ? S.freq + " MHz" : "not given";
  if (S.freq_ask && !freqShown) openFreq();
  if (!S.freq_ask) freqShown = false;
}
function openFreq() {
  freqShown = true;
  $("freq-in").value = S.freq || S.freq_last || "";
  $("freq-err").classList.add("hidden");
  $("freqdlg").classList.remove("hidden");
  $("freq-in").focus(); $("freq-in").select();
}
async function saveFreq(e) {
  e.preventDefault();
  const v = $("freq-in").value.trim().replace(",", ".");
  if (v && !(Number(v) >= 0.1)) { $("freq-err").classList.remove("hidden"); return; }
  if (!(await api("freq", { freq: v }))) { $("freq-err").classList.remove("hidden"); return; }
  $("freqdlg").classList.add("hidden");
}

function openTerm() {
  $("sheet").classList.add("hidden");
  if (!curCh().chat && S.chat_ch) switchCh(S.chat_ch);
  manualTerm = true;
  setView("term");
}

// ---------------------------------------------------------------- polling
async function poll() {
  let since = -1;
  for (;;) {
    try {
      pollCtl = new AbortController();
      const r = await fetch(`/api/state?since=${since}&ch=${activeCh}`,
                            { cache: "no-store", signal: pollCtl.signal });
      if (!r.ok) throw new Error(r.status);
      S = await r.json();
      if (S.focus) {                                     // CR75: a station connected to us
        if (lastFocus !== null && S.focus.seq !== lastFocus && S.focus.n) switchCh(S.focus.n);
        lastFocus = S.focus.seq;
      }
      if (S.ch !== activeCh) { since = -1; continue; }   // switched meanwhile
      stateRecv = performance.now();
      const endAt = Math.max(0, ...(S.channels || []).map((c) => (c.ended ? c.ended.at : 0)));   // CR44
      if (endAt !== lastEndAt) { lastEndAt = endAt; if (!$("sheet").classList.contains("hidden")) loadConnlog(); }
      since = S.version;
      render();
      if (!$("sheet").classList.contains("hidden")) renderSymbols();
      if (linkCall) renderLink();
    } catch (e) {
      if (e.name === "AbortError") { since = -1; continue; }   // channel switched (CR45)
      $("status-text").textContent = "client not reachable";
      $("status-dot").className = "dot";
      await new Promise((ok) => setTimeout(ok, 3000));
    }
  }
}

async function start() {
  try { EMO = await (await fetch("/emoji.json")).json(); } catch (e) { /* plain text then */ }
  try { SYMNAMES = await (await fetch("/aprs/names.json")).json(); } catch (e) { /* no names */ }
  try {
    STK_LIST = (await (await fetch("/stickers/stickers.json")).json()).stickers;
    for (const s of STK_LIST) STK[s.name] = s;
  } catch (e) { /* no stickers: shown as text */ }
  initEmoji();
  initMail();
  $("sys-disc").onclick = () => api("disconnect");
  $("pb-fill").onclick = openProfile;                         // CR73
  $("pb-later").onclick = () => api("profile/later");
  $("prof-edit").onclick = openProfile;
  $("prof-form").onsubmit = saveProfile;
  $("prof-cancel").onclick = () => $("profdlg").classList.add("hidden");
  $("profdlg").onclick = (e) => { if (e.target === $("profdlg")) $("profdlg").classList.add("hidden"); };
  $("upd-reload").onclick = () => location.reload();
  $("upd-close").onclick = () => {
    if (S && S.update && S.update.cur !== updDismissed) {      // the TinyBox's hint is shown
      updDismissed = S.update.cur;
      try { localStorage.setItem("tbc-upd-dismissed", updDismissed); } catch (e) { /* ok */ }
    } else if (S && S.release) {                                // the GitHub release is shown
      relDismissed = S.release.latest;
      try { localStorage.setItem("tbc-rel-dismissed", relDismissed); } catch (e) { /* ok */ }
    }
    render();
  };
  $("upd-news").onclick = async () => {
    if (!S || !S.update || !S.update.news) return;
    const id = S.update.news;
    openFolder("b:TBNEWS");
    const have = await postJson("mail/open", { id });
    if (have.ok && have.data.body !== null) { openMessage(id); return; }   // already here
    newsWanted = { id, seen: false };
    await api("mail/news");              // subscribe TBNEWS and fetch the bulletins
  };
  $("sys-close").onclick = () => { sysDismissed = S && S.sysmsg ? S.sysmsg.at : 0; renderSys(); };
  $("btn-connect").onclick = $("btn-connect2").onclick = () => api("connect", { ch: activeCh || undefined });
  $("btn-disconnect").onclick = () => api("disconnect");
  $("btn-disc").onclick = () => api("disconnect", { ch: activeCh });
  $("to-form").onsubmit = connectTo;
  $("to-call").oninput = (e) => { e.target.classList.remove("bad"); targetPreview(); };
  $("to-call").onblur = () => $("to-hint").classList.add("hidden");
  $("to-call").onfocus = targetPreview;
  $("term-form").onsubmit = termSend;
  $("term-input").addEventListener("keydown", termKey);
  $("term-close").onclick = () => { manualTerm = false; setView("chat"); };
  document.addEventListener("keydown", (e) => {               // CR45: Alt+0 ... Alt+5
    if (e.altKey && !e.ctrlKey && !e.metaKey && /^[0-5]$/.test(e.key)) {
      e.preventDefault();
      const n = Number(e.key);
      if (n === 0 || (S && (S.channels.some((c) => c.n === n) || S.channels.length < S.max_ch))) switchCh(n);
    }
  });
  $("btn-term").onclick = openTerm;
  const monRedraw = () => { monDirty = true; if (S && activeCh === 0) { renderMonitor(); $("term-out").scrollTop = $("term-out").scrollHeight; } };
  $("mon-ui").onclick = uiToggle;                              // CR66
  $("ui-form").addEventListener("submit", uiSend);
  $("ui-text").addEventListener("input", uiCount);
  $("mon-q").addEventListener("input", monRedraw);
  $("mon-kind").addEventListener("change", monRedraw);
  $("mon-clear").onclick = async () => { await api("monitor/clear"); monLines = []; AprsView.forget(); monRedraw(); };
  $("mon-aprs").replaceWith(AprsView.toggleButton("sm"));        // CR55
  AprsView.attachLens($("aprs-lens"));
  AprsView.setSymbolRenderer(symbolEl);                       // CR59: symbols in the lens
  AprsView.onChange(() => { showLens(); monRedraw(); });
  $("freq-form").onsubmit = saveFreq;
  $("freq-skip").onclick = async () => { await api("freq", { freq: "" }); $("freqdlg").classList.add("hidden"); };
  $("freq-change").onclick = () => { $("sheet").classList.add("hidden"); openFreq(); };
  $("nav-terminal").onclick = openTerm;
  $("bh-leave").onclick = () => api("leave");
  const openSheet = (focus) => {
    $("sheet").classList.remove("hidden"); renderSymbols(); loadConnlog();
    if (focus) $(focus).scrollIntoView({ block: "start" });
  };
  $("btn-menu").onclick = () => openSheet();
  $("nav-settings").onclick = () => openSheet();
  $("nav-monitor").onclick = () => switchCh(0);              // CR50: the monitor channel
  AprsStatsView.attach($("statsview"));                       // CR61: APRS statistics
  AprsStatsView.setSymbolRenderer(symbolEl);
  AprsStatsView.setOnCall((call) => {                         // "Show in monitor": filtered
    $("mon-q").value = call;
    monDirty = true;
    statsFromMon = null;
    if (activeCh === 0) setView("term"); else switchCh(0);
  });
  AprsStatsView.setOnExit(() => {                             // Back on the first page
    const from = statsFromMon;
    statsFromMon = null;
    setView(backView());
    if (from !== null && activeCh === 0) $("term-out").scrollTop = from;   // the same place
  });
  $("nav-stats").onclick = () => { statsFromMon = null; AprsStatsView.openOverview(); setView("stats"); };
  AprsView.setOnStation(openStationStats);                    // CR65: band and lens
  $("term-out").addEventListener("click", (ev) => {           // CR65: a call in the monitor
    const c = activeCh === 0 && ev.target.closest(".mc");
    if (!c) return;
    ev.stopPropagation();                                     // not the selection of the card
    openStationStats(c.textContent);
  }, true);
  $("status-text").onclick = () => $("app").classList.toggle("show-people");
  $("people-close").onclick = () => $("app").classList.remove("show-people");
  $("linkdlg-close").onclick = closeLink;
  $("linkdlg").onclick = (e) => { if (e.target === $("linkdlg")) closeLink(); };
  $("mb-close").onclick = () => {
    mailDismissed = S && S.mail ? S.mail.at : 0;
    try { localStorage.setItem("tbc-mail-dismissed", String(mailDismissed)); } catch (e) { /* ok */ }
    render();
  };
  $("btn-close").onclick = () => $("sheet").classList.add("hidden");
  $("sheet").onclick = (e) => { if (e.target === $("sheet")) $("sheet").classList.add("hidden"); };
  $("sym-search").oninput = renderSymbols;
  $("sym-none").onclick = () => api("symbol", { symbol: "" });
  for (const r of document.querySelectorAll('input[name="histmode"]')) {
    r.onchange = () => api("histmode", { mode: r.value });
  }
  $("btn-emoji").onclick = () => {
    if ($("picker").classList.contains("hidden")) { pickerMode = "input"; openPicker(); } else closePicker();
  };
  $("btn-send").onclick = send;
  $("btn-cry").onclick = () => setCry(!cryMode);
  $("btn-stk").onclick = () => {
    if (pickerMode === "sticker" && !$("picker").classList.contains("hidden")) closePicker();
    else openStickers();
  };
  $("qb-close").onclick = () => setQuote(null);
  $("btn-img").onclick = () => $("imgfile").click();
  $("imgfile").onchange = () => chooseImage($("imgfile").files[0]);
  $("imgdlg-ok").onclick = sendImage;
  $("imgdlg-cancel").onclick = closeImageDialog;
  for (const b of document.querySelectorAll("#imgdlg-size button")) b.onclick = () => pickImageSize(b.dataset.size);
  $("imgdlg").onclick = (e) => { if (e.target === $("imgdlg")) closeImageDialog(); };
  $("imgdlg-caption").addEventListener("keydown", (e) => { if (e.key === "Enter") { e.preventDefault(); sendImage(); } });
  $("input").addEventListener("keydown", (e) => { if (e.key === "Enter") { e.preventDefault(); send(); } });
  $("input").addEventListener("input", (e) => { if (e.inputType !== "deleteContentBackward") liveEmoticon(e.target); updateHint(); });
  document.addEventListener("click", (e) => {
    if (!$("react-bar").contains(e.target)) closeReactBar();
  });
  $("chat").addEventListener("scroll", () => {
    if (performance.now() > ignoreChatScrollUntil) closeReactBar();   // CR23
  });
  poll();
}
start();
