// APRS statistics of the channel (CR61) - the page "APRS statistics" in the client.
// The numbers come from GET /api/aprs/stats?win=<seconds> (prcore/aprsstats.py);
// this file only draws them (the network graph: aprsgraph.js, CR79). CR65: a click on a call opens the station page of
// that call (GET /api/aprs/station?call=..&win=..); Back goes the way back.
"use strict";

const AprsStatsView = (() => {
  let root = null;
  let win = 3600;
  let timer = null;
  let data = null;
  let graph = null;                        // CR79: /api/aprs/graph of the same window
  let armed = false;                       // Reset needs a second click
  const sorts = {};                        // table id -> [column, descending]
  let onCall = () => {};                   // show a call / device in the monitor (filter)
  let onExit = () => {};                   // Back on the first page: where we came from
  let symbolRenderer = null;
  let stack = [{ kind: "overview" }];      // CR65: pages visited, last = shown
  try { win = Number(localStorage.getItem("tbc-aprs-win") || 3600); } catch (e) { /* ok */ }

  const CAT = { position: "Position", mice: "Mic-E position", weather: "Weather", telemetry: "Telemetry",
                tdef: "Telemetry definitions", object: "Object / item", status: "Status",
                message: "Message", other: "Other" };
  const SIN = { "too often": "Too often", "unchanged repeat": "Unchanged repeat", "long path": "Long path",
                "wrong clock": "Wrong clock", "malformed": "Malformed", "internet → radio": "Internet → radio" };

  function mk(tag, cls, text) {
    const e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text !== undefined && text !== null) e.textContent = text;
    return e;
  }
  function callBtn(call) {
    if (!call || call === "?") return mk("span", "st-mono", call || "?");
    const b = mk("button", "st-call", call);
    b.type = "button";
    b.title = "Statistics of " + call;
    b.addEventListener("click", () => openStation(call, true));
    return b;
  }
  function devBtn(dev) {                   // CR63: a device filters the monitor too
    if (!dev || dev === "(unknown)") return mk("span", "st-empty", dev || "–");
    const b = mk("button", "st-call st-dev", dev);
    b.type = "button";
    b.title = "Show frames of " + dev + " in the monitor";
    b.addEventListener("click", () => onCall(dev));
    return b;
  }
  function ago(t) {
    const s = Math.max(0, Math.round(data.now - t));
    return s < 90 ? s + " s" : s < 5400 ? Math.round(s / 60) + " min" : Math.round(s / 3600) + " h";
  }
  function hhmm(t) { return new Date(t * 1000).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }); }
  function interval(s) { return s === null || s === undefined ? "–" : s < 120 ? s + " s" : Math.round(s / 60) + " min"; }

  // ---- building blocks ---------------------------------------------------------------
  function card(title, sub, ...kids) {
    const c = mk("section", "st-card");
    const h = mk("h3", "st-h", title);
    if (sub) h.append(mk("span", "st-sub", " " + sub));
    c.append(h, ...kids);
    return c;
  }
  // cols: [label, key, render(row) -> node|string, numeric]
  function table(id, cols, rows, limit) {
    const [sk, desc] = sorts[id] || [null, true];
    if (sk !== null) {
      const col = cols.find((c) => c[1] === sk);
      rows = rows.slice().sort((a, b) => {
        const x = a[sk], y = b[sk];
        const r = col && col[3] ? (x ?? -1) - (y ?? -1) : String(x ?? "").localeCompare(String(y ?? ""));
        return desc ? -r : r;
      });
    }
    const t = mk("table", "st-table");
    const tr = mk("tr");
    for (const [label, key, , num] of cols) {
      const th = mk("th", num ? "num" : "");
      const b = mk("button", "st-sort", label + (sk === key ? (desc ? " ▾" : " ▴") : ""));
      b.type = "button";
      b.addEventListener("click", () => {
        sorts[id] = [key, sk === key ? !desc : true];
        draw();
      });
      th.append(b);
      tr.append(th);
    }
    t.append(mk("thead"));
    t.firstChild.append(tr);
    const tb = mk("tbody");
    for (const r of rows.slice(0, limit || 50)) {
      const row = mk("tr");
      for (const [, key, render, num] of cols) {
        const td = mk("td", num ? "num" : "");
        const v = render ? render(r) : r[key];
        td.append(v instanceof Node ? v : String(v ?? "–"));
        row.append(td);
      }
      tb.append(row);
    }
    if (!rows.length) {
      const row = mk("tr");
      const td = mk("td", "st-empty", "nothing yet");
      td.colSpan = cols.length;
      row.append(td);
      tb.append(row);
    }
    t.append(tb);
    const wrap = mk("div", "st-scroll");
    wrap.append(t);
    return wrap;
  }
  function bars(items) {                   // [label, value, note]
    const max = Math.max(1, ...items.map((i) => i[1]));
    const box = mk("div", "st-bars");
    for (const [label, v, note] of items) {
      const row = mk("div", "st-bar");
      const fill = mk("span", "st-fill");
      fill.style.width = (100 * v / max).toFixed(1) + "%";
      const track = mk("span", "st-track");
      track.append(fill);
      row.append(mk("span", "st-blabel", label), track, mk("span", "st-bval", note || String(v)));
      box.append(row);
    }
    return box;
  }
  function tile(label, value, note) {
    const t = mk("div", "st-tile");
    t.append(mk("div", "st-tlabel", label), mk("div", "st-tvalue", value));
    if (note) t.append(mk("div", "st-tnote", note));
    return t;
  }

  // ---- the page ----------------------------------------------------------------------
  function draw() {
    if (!root || !data) return;
    const d = data, T = d.totals;
    const body = root.querySelector(".st-body");
    body.replaceChildren();
    root.querySelector(".st-since").textContent = d.window
      ? `last ${d.window >= 86400 ? "24 h" : "hour"}`
      : `since ${new Date(d.since * 1000).toLocaleString([], { dateStyle: "short", timeStyle: "short" })}`;

    const tiles = mk("div", "st-tiles");
    tiles.append(
      tile("Frames", String(T.frames), T.per_min + " per minute"),
      tile("Stations", String(T.stations), T.heard + " received by your radio (see Heard)"),
      tile("Channel busy", T.busy_pct + " %", `≈ ${Math.round(T.air_sec / 60)} min on the air (estimate, 1200 Bd)`),
      tile("Internet → radio", String(T.inet), T.frames ? Math.round(100 * T.inet / T.frames) + " % of the frames" : ""));
    body.append(tiles);

    const tl = d.timeline;
    const tlb = mk("div", "st-timeline");
    const tmax = Math.max(1, ...tl.counts);
    tl.counts.forEach((c, i) => {
      const b = mk("span", "st-tbar");
      b.style.height = (100 * c / tmax).toFixed(1) + "%";
      b.title = `${hhmm(tl.first + i * tl.slot)}: ${c} frames`;
      tlb.append(b);
    });
    const tlfoot = mk("div", "st-tlfoot");
    tlfoot.append(mk("span", "", hhmm(tl.first)), mk("span", "", `one bar = ${tl.slot >= 3600 ? tl.slot / 3600 + " h" : tl.slot / 60 + " min"}`),
                  mk("span", "", hhmm(d.now)));
    body.append(card("Frames over time", "", tlb, tlfoot));
    if (graph && typeof AprsGraph !== "undefined") {   // CR79: network graph and device pie
      body.append(AprsGraph.card(graph, { cats: CAT, onStation: (c) => openStation(c, true) }));
    }

    const grid = mk("div", "st-grid");
    // CR63 order: Heard, iGates, Packet types, then the rest; Sins at the very end
    grid.append(
      card("Heard", "who your radio actually received", table("heard", [
        ["Station", "call", (r) => callBtn(r.call)], ["Frames", "n", null, true],
        ["Share", "pct", (r) => r.pct + " %", true], ["Last", "last", (r) => ago(r.last), true]], d.heard)),
      card("iGates", "internet → radio (third-party packets)", table("igates", [
        ["iGate", "call", (r) => callBtn(r.call)], ["Frames", "n", null, true],
        ["Stations", "stations", null, true], ["Share", "pct", (r) => r.pct + " %", true]], d.igates)),
      card("Packet types", "", bars(d.types.map((t) => [CAT[t.cat] || t.cat, t.n, `${t.pct} % (${t.n})`]))),
    );
    const snd = card("Senders", "third-party packets count for the station inside", table("senders", [
      ["Station", "call", (r) => callBtn(r.call)], ["Frames", "n", null, true],
      ["Every", "every", (r) => interval(r.every), true], ["km", "dist", null, true],
      ["Types", "cats"], ["Device", "dev", (r) => devBtn(r.dev)], ["Internet", "inet", null, true],
      ["Last", "last", (r) => ago(r.last), true]], d.senders, 100));
    snd.classList.add("st-wide");
    grid.append(snd);
    grid.append(
      card("Devices", "device list (tocalls / Mic-E) - click to see them in the monitor", table("devices", [
        ["Device", "dev", (r) => devBtn(r.dev)], ["Frames", "n", null, true],
        ["Stations", "stations", null, true]], d.devices)),
      card("Digipeaters", "every station that relayed (*)", table("digis", [
        ["Digipeater", "call", (r) => callBtn(r.call)], ["Frames", "n", null, true]], d.digis),
        mk("h4", "st-h4", "Ways (sender → … → you)"),
        table("chains", [["Chain", "chain"], ["Frames", "n", null, true]], d.chains),
        mk("h4", "st-h4", "Hops (relayed how often)"),
        bars(d.hops.map(([h, n]) => [h === 0 ? "direct" : h + " hop" + (h > 1 ? "s" : ""), n]))),
    );
    const R = d.range;
    if (R.have_home) {
      const far = mk("div", "st-far");
      const fl = (label, x) => {
        const p = mk("p", "");
        p.append(label + ": ");
        if (x) p.append(callBtn(x.call), ` ${x.km} km`); else p.append("–");
        return p;
      };
      far.append(fl("Farthest heard directly", R.farthest_direct), fl("Farthest over digipeaters", R.farthest_via));
      grid.append(card("Range", "from your locator", far, bars(R.buckets.map(([b, n]) => [b, n, n + " stations"]))));
    } else {
      grid.append(card("Range", "", mk("p", "st-empty", "Set your locator in tbclient.conf ([station] locator) to see distances.")));
    }
    grid.append(card("Countries", "by call prefix", table("countries", [
      ["Country", "country"], ["Frames", "n", null, true], ["Stations", "stations", null, true]], d.countries)));
    const sins = card("Sins", "what burdens the channel", table("sins", [
      ["Station", "call", (r) => callBtn(r.call)],
      ["Sin", "kind", (r) => mk("span", "st-sin", SIN[r.kind] || r.kind)],
      ["What", "text"],
      ["Frames", "count", null, true],
    ], d.sins, 60));
    sins.classList.add("st-wide");
    grid.append(sins);
    body.append(grid);
  }

  const page = () => stack[stack.length - 1];
  async function load() {
    const p = page();
    const url = p.kind === "station" ? `/api/aprs/station?call=${encodeURIComponent(p.call)}&win=${win}`
      : `/api/aprs/stats?win=${win}`;
    try {
      const gr = p.kind === "overview" ? fetch(`/api/aprs/graph?win=${win}`, { cache: "no-store" }) : null;
      const r = await fetch(url, { cache: "no-store" });
      if (!r.ok || page() !== p) return;
      data = await r.json();
      if (gr) {
        try { const g = await gr; graph = g.ok ? await g.json() : null; } catch (e) { graph = null; }
        if (page() !== p) return;
      }
      if (p.kind === "station") drawStation(); else draw();
    } catch (e) { /* next time */ }
  }
  function frame() {                       // title and buttons of the page shown
    const p = page();
    root.querySelector(".st-title b").textContent = p.kind === "station" ? "Station " + p.call : "APRS statistics";
    root.querySelector(".st-reset").classList.toggle("hidden", p.kind === "station");
    root.querySelector(".st-body").replaceChildren(mk("p", "st-empty", "Loading ..."));
    root.querySelector(".st-body").scrollTop = 0;
  }
  function openStation(call, push) {
    call = call.replace(/\*$/, "").toUpperCase();
    if (push) stack.push({ kind: "station", call }); else stack = [{ kind: "station", call }];
    frame();
    load();
  }
  function goBack() {
    if (stack.length > 1) { stack.pop(); frame(); load(); return; }
    onExit();
  }

  // ---- CR65: the station page ------------------------------------------------------
  const COMPASS = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE", "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"];
  const compass = (d) => COMPASS[Math.round((d % 360) / 22.5) % 16];
  function when(t) { return new Date(t * 1000).toLocaleString([], { dateStyle: "short", timeStyle: "short" }); }
  function chainEl(chain) {                // "A → B → C" with clickable calls
    const box = mk("span", "st-chainrow");
    chain.split(" → ").forEach((c, i) => {
      if (i) box.append(mk("span", "st-arrow", " → "));
      box.append(callBtn(c));
    });
    return box;
  }
  function linkBtn(href, text) {
    const a = mk("a", "st-linkbtn", text);
    a.href = href;
    a.target = "_blank";
    a.rel = "noopener noreferrer";
    return a;
  }
  function heatmap(grid) {
    const days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
    const max = Math.max(1, ...grid.flat());
    const box = mk("div", "st-heat");
    box.append(mk("span", ""));
    for (let h = 0; h < 24; h++) box.append(mk("span", "st-heat-h", h % 3 === 0 ? String(h) : ""));
    grid.forEach((row, d) => {
      box.append(mk("span", "st-heat-d", days[d]));
      row.forEach((n, h) => {
        const c = mk("span", "st-heat-c");
        if (n) c.style.background = `color-mix(in srgb, var(--accent) ${Math.round(15 + 85 * n / max)}%, transparent)`;
        c.title = `${days[d]} ${String(h).padStart(2, "0")}:00–${String(h).padStart(2, "0")}:59: ${n} frames`;
        box.append(c);
      });
    });
    return box;
  }
  function drawStation() {
    const d = data;
    const body = root.querySelector(".st-body");
    body.replaceChildren();
    root.querySelector(".st-since").textContent = d.window
      ? `last ${d.window >= 86400 ? "24 h" : "hour"}` : `since ${when(d.since)}`;

    // head: symbol, call, roles, device, distance, first/last heard, links
    const head = mk("section", "st-card st-head");
    const name = mk("div", "st-name");
    const icon = d.symbol && symbolRenderer ? symbolRenderer(d.symbol) : null;
    if (icon) { icon.classList.add("st-bigsym"); name.append(icon); }
    name.append(mk("span", "st-callbig", d.call));
    for (const r of d.roles || []) name.append(mk("span", "st-role", r));
    head.append(name);
    const facts = mk("div", "st-facts");
    const fact = (k, v) => { const p = mk("div", ""); p.append(mk("span", "st-k", k), mk("span", "", v)); facts.append(p); };
    fact("Device", d.device || "–");
    fact("Country", d.country);
    fact("Distance", !d.have_home ? "unknown (no locator)" : d.pos && d.pos.km !== undefined
      ? `${d.pos.km} km, ${d.pos.deg}° ${compass(d.pos.deg)}` : "no position");
    fact("First heard", d.first ? when(d.first) : "–");
    fact("Last heard", d.last ? when(d.last) : "–");
    head.append(facts);
    const acts = mk("div", "st-acts");
    const mon = mk("button", "sm", "Show in monitor");
    mon.type = "button";
    mon.addEventListener("click", () => onCall(d.call));
    acts.append(mon, linkBtn(`https://aprs.fi/#!call=a%2F${encodeURIComponent(d.call)}`, "aprs.fi ↗"));
    if (d.pos) {
      acts.append(linkBtn(`https://www.openstreetmap.org/?mlat=${d.pos.lat}&mlon=${d.pos.lon}#map=13/${d.pos.lat}/${d.pos.lon}`, "map ↗"),
        linkBtn(`https://aprs.fi/#!call=a%2F${encodeURIComponent(d.call)}&timerange=604800&tail=604800`, "track on aprs.fi ↗"));
    }
    head.append(acts);
    body.append(head);

    if (!d.frames) {
      body.append(mk("p", "st-empty", "No APRS frames from this station in the chosen window." +
        (d.relayed || d.gated ? " It appears below as digipeater or iGate." : "")));
    }
    const tiles = mk("div", "st-tiles");
    tiles.append(
      tile("Frames sent", String(d.frames), d.share.frames_pct + " % of the channel"),
      tile("Air time", d.share.air_pct + " %", `≈ ${d.share.air_sec} s on the air (estimate)`),
      tile("Relayed for others", String(d.relayed), "as digipeater"),
      tile("Internet → radio", String(d.gated), "as iGate"),
      tile("Received by your radio", String(d.heard_as), "frames that came from this station's transmitter"));
    body.append(tiles);

    if (d.frames) {
      const tl = d.timeline;
      const tlb = mk("div", "st-timeline");
      const tmax = Math.max(1, ...tl.counts);
      const unit = tl.slot >= 3600 ? (tl.slot / 3600 === 1 ? "h" : tl.slot / 3600 + " h") : tl.slot / 60 + " min";
      tl.counts.forEach((c, i) => {
        const b = mk("span", "st-tbar");
        b.style.height = (100 * c / tmax).toFixed(1) + "%";
        b.title = `${hhmm(tl.first + i * tl.slot)}: ${c} frames`;
        tlb.append(b);
      });
      const foot = mk("div", "st-tlfoot");
      foot.append(mk("span", "", hhmm(tl.first)), mk("span", "", `frames per ${unit}`), mk("span", "", hhmm(d.now)));
      body.append(card("Frames over time", "", tlb, foot));
    }

    const grid = mk("div", "st-grid");
    if (d.frames) {
      grid.append(card("Kinds of frames", "", bars(d.types.map((t) => [CAT[t.cat] || t.cat, t.n, `${t.pct} % (${t.n})`]))));
      if (d.beacon) {
        const b = d.beacon;
        const p = mk("p", "st-note", `Typically every ${interval(b.median)} (shortest ${interval(b.min)}, ` +
          `longest ${interval(b.max)}) - ${b.regular ? "a fixed timer" : "irregular: smart beaconing or by hand"}.`);
        grid.append(card("Beacon behaviour", "gaps between frames", p, bars(b.buckets.map(([l, n]) => [l, n]))));
      }
      const w = d.ways;
      const ways = card("How it reaches you", "",
        bars([["direct", w.direct, `${w.direct}`], ["over digipeaters / internet", w.via, `${w.via}`]]),
        mk("h4", "st-h4", "Ways"),
        table("st-ways", [["Way", "chain", (r) => chainEl(r.chain)], ["Frames", "n", null, true]], w.chains),
        mk("h4", "st-h4", "Relayed how often"),
        bars(w.hops.map(([h, n]) => [h === 0 ? "direct" : h + " hop" + (h > 1 ? "s" : ""), n])),
        mk("h4", "st-h4", "Hops asked for (path)"),
        bars(w.asked.map(([h, n]) => [h === 0 ? "none" : h + " hop" + (h > 1 ? "s" : ""), n])),
        mk("h4", "st-h4", "Your radio received it from"),
        table("st-heardby", [["Station", "call", (r) => callBtn(r.call)], ["Frames", "n", null, true]], w.heard));
      grid.append(ways);
      grid.append(card("Activity", "weekday × hour (local time), everything kept", heatmap(d.activity)));
      if (d.move) {
        const m = d.move;
        const p = mk("div", "st-far");
        p.append(mk("p", "", m.moving ? `Moving: about ${m.km} km covered, up to ${m.max_kmh} km/h.`
          : "Not moving (a fixed position)."));
        if (m.alt_min !== null) p.append(mk("p", "", `Altitude ${m.alt_min}${m.alt_max !== m.alt_min ? "–" + m.alt_max : ""} m`));
        if (d.pos) p.append(mk("p", "", `Last position ${when(d.pos.t)}`));
        grid.append(card("Movement", "", p));
      }
    }
    if (d.as_digi.length) {
      grid.append(card("As digipeater", "relayed these stations", table("st-digi", [
        ["Station", "call", (r) => callBtn(r.call)], ["Frames", "n", null, true]], d.as_digi)));
    }
    if (d.as_igate.length) {
      grid.append(card("As iGate", "put these internet stations on the air", table("st-igate", [
        ["Station", "call", (r) => callBtn(r.call)], ["Frames", "n", null, true]], d.as_igate)));
    }
    const sins = card("Sins", "of this station", d.sins.length ? table("st-sins", [
      ["Sin", "kind", (r) => mk("span", "st-sin", SIN[r.kind] || r.kind)], ["What", "text"],
      ["Frames", "count", null, true]], d.sins) : mk("p", "st-empty", "None - well done."));
    sins.classList.add("st-wide");
    grid.append(sins);
    body.append(grid);
  }

  function build(el) {
    root = el;
    const bar = mk("div", "st-bar-top");
    const back = mk("button", "icon-btn back", "‹");
    back.type = "button";
    back.setAttribute("aria-label", "Back");
    back.addEventListener("click", () => goBack());
    // CR64: the time window as three buttons, always visible
    const sel = mk("div", "st-seg");
    sel.setAttribute("role", "group");
    sel.setAttribute("aria-label", "Time window");
    const segs = [];
    for (const [v, t, tip] of [[3600, "Last hour", "the last 60 minutes"], [86400, "24 h", "the last 24 hours"],
                               [0, "All", "everything kept (max. 7 days, or since the last reset)"]]) {
      const b = mk("button", "", t);
      b.type = "button";
      b.title = tip;
      b.addEventListener("click", () => {
        win = v;
        try { localStorage.setItem("tbc-aprs-win", String(win)); } catch (e) { /* ok */ }
        segs.forEach(([x, bv]) => x.classList.toggle("on", bv === win));
        load();
      });
      b.classList.toggle("on", v === win);
      segs.push([b, v]);
      sel.append(b);
    }
    const reset = mk("button", "sm st-reset", "Reset");
    reset.type = "button";
    reset.addEventListener("click", async () => {
      if (!armed) {
        armed = true;
        reset.textContent = "Really reset?";
        setTimeout(() => { armed = false; reset.textContent = "Reset"; }, 4000);
        return;
      }
      armed = false;
      reset.textContent = "Reset";
      await fetch("/api/aprs/stats/reset", { method: "POST", body: "{}",
        headers: { "Content-Type": "application/json", "X-TBClient": "1" } });
      load();
    });
    const title = mk("div", "st-title");
    title.append(mk("b", "", "APRS statistics"), mk("span", "st-since muted", ""));
    bar.append(back, title, mk("span", "st-sp"), sel, reset);
    root.append(bar, mk("div", "st-body"));
  }

  return {
    setOnExit: (f) => { onExit = f; },
    setOnCall: (f) => { onCall = f; },
    setSymbolRenderer: (f) => { symbolRenderer = f; },
    openOverview: () => { stack = [{ kind: "overview" }]; if (root) frame(); },
    openStation: (call) => openStation(call, false),
    attach: (el) => build(el),
    show: () => { load(); clearInterval(timer); timer = setInterval(load, 15000); },
    hide: () => { clearInterval(timer); timer = null; },
  };
})();
