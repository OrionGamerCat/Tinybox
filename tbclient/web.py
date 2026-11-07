"""Web GUI of the client: static files + a small JSON API (standard library only).

Reachable in the LAN/WAN without login (decided, see PLANUNG.md 11/5).
What stays protected:
  * writes need Content-Type application/json and the header X-TBClient: 1.
    A foreign web page cannot send that without a CORS preflight, which we
    never answer -> no sending under your call from a malicious page.
  * strict Content-Security-Policy, the page only uses textContent
    (chat texts come from the air and are untrusted).

API:
  GET  /api/state?since=<version>   snapshot; waits up to 25 s for a change
  GET  /api/state?since=<version>&ch=<n>   ch = channel shown (its terminal lines; 0 = monitor)
  POST /api/connect {"target": "CALL", "ch": n} (both optional, CR42/CR45)
  POST /api/disconnect {"ch": n} | /api/leave | /api/channel/close {"ch": n}
  POST /api/term   {"text": "...", "ch": n}   a raw line from the terminal view (CR43)
  POST /api/peer/heard {"ch": n}             CR78: ask the TBClient there whom it hears
  POST /api/peer/clear {"ch": n}             CR78: delete the chat history with it (both sides)
  POST /api/ui     {"dest": "CQ", "via": "OE3XBS-8,WIDE2-1", "text": "..."}   one UI frame
                   from the monitor (CR66) -> {"ok": true} or {"ok": false, "error": "..."}
  POST /api/join   {"board": n}
  POST /api/say    {"text": "..."}
  POST /api/react  {"seq": n, "emoji": ":+1"}
  POST /api/symbol {"symbol": "/-"}  ("" = none)
  POST /api/history  {"n": 10}   older history lines of the board (CR13)
  POST /api/histmode {"mode": "missed"|"none"|"10"|"20"}   history when joining

Mailbox (C3), all local - only "sync" goes on air:
  GET  /api/mail?folder=inbox|sent|outbox|b:<RUBRIC>   message list (no texts)
  POST /api/mail/open     {"id": n}          -> the message with text (marks it read)
  POST /api/mail/delete   {"id": n}
  POST /api/mail/save     {"oid": n|null, "type": "P"|"B", "to": "...", "subject": "...",
                           "body": "..."}   -> {"oid": n}  (into the outbox)
  POST /api/mail/discard  {"oid": n}
  POST /api/mail/subscribe {"rubric": "ALL", "on": true}
  POST /api/mail/sync {"scope": "mail"|"bulletins"|"login"}
  POST /api/mail/abort    orderly abort of the running sync or text fetch (CR40;
                          /api/mail/cancel is the old name)
  POST /api/mail/fetch {"id": n}   fetch this text now (CR40) -> {"ok": true} or
                          {"ok": false, "error": "not connected"} (forgotten, not queued)
  POST /api/mail/news   subscribe TBNEWS + fetch bulletins ("Read about new features")

Images in the chat (CR12):
  POST /api/image      {"data": <base64 WebP/JPEG>, "blurhash": "...", "caption": "...",
                        "quote": "~^CALL HHMM " | ""}  -> {"ok": true, "hash": "a1b2c3"}
                       upload, then the chat line goes out
  POST /api/image/get  {"hash": "a1b2c3"}     fetch an image someone posted
  POST /api/image/retry                       send a failed upload again
  POST /api/image/dismiss                     take the finished/failed upload off the GUI
  GET  /img/<hash>                            the image file (WebP or JPEG)
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import re
import time
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from tinybox import connlog                # CSV and ADIF of the connection log (CR44)

from . import VERSION
from .core import ClientCore

log = logging.getLogger(__name__)

STATIC = Path(__file__).resolve().parent / "web"
SHARED = Path(__file__).resolve().parent.parent / "tinybox" / "web"   # CR55: one copy for both GUIs
TYPES = {".html": "text/html; charset=utf-8", ".css": "text/css; charset=utf-8",
         ".js": "text/javascript; charset=utf-8", ".json": "application/json",
         ".png": "image/png", ".svg": "image/svg+xml", ".webp": "image/webp"}
FILES = {"/": "index.html", "/app.css": "app.css", "/app.js": "app.js",
         "/emoji.json": "emoji.json", "/aprs/symbols-0.png": "aprs/aprs-symbols-24-0@2x.png",
         "/aprs/symbols-1.png": "aprs/aprs-symbols-24-1@2x.png",
         "/aprs/names.json": "aprs/names.json", "/manifest.json": "manifest.json",
         "/logo.svg": "logo.svg", "/aprsstats.js": "aprsstats.js", "/aprsgraph.js": "aprsgraph.js",
         "/aprsview.js": str(SHARED / "aprsview.js"), "/aprsview.css": str(SHARED / "aprsview.css")}
# CR42: the icons of the connection in the top bar
FILES.update({f"/conn/{p.name}": f"conn/{p.name}" for p in (STATIC / "conn").glob("*.png")})
# CR11: the sticker set (fixed files in the client, never sent over the air)
FILES.update({f"/stickers/{p.name}": f"stickers/{p.name}"
              for p in (STATIC / "stickers").glob("*") if p.suffix in (".webp", ".json")})
HEADERS = {
    "Content-Security-Policy": ("default-src 'self'; script-src 'self'; style-src 'self'; "
                                "img-src 'self' data:; connect-src 'self'; "
                                "frame-ancestors 'none'; base-uri 'none'; form-action 'none'"),
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "X-Frame-Options": "DENY",
}
REASONS = {200: "OK", 400: "Bad Request", 403: "Forbidden", 404: "Not Found",
           405: "Method Not Allowed", 413: "Payload Too Large", 415: "Unsupported Media Type"}
CALL_AT_RE = re.compile(r"^[A-Z0-9]{1,6}(-\d{1,2})?(,[A-Z0-9]{1,6}(-\d{1,2})?){0,9}"
                        r"(@[A-Z0-9#.-]{1,40})?$")      # CR27: up to 10 recipients
RUBRIC_RE = re.compile(r"^[A-Z0-9]{1,6}$")
MAX_BODY = 131072        # a message for the outbox can be long
POLL_SEC = 25


class WebServer:
    def __init__(self, core: ClientCore) -> None:
        self.core = core

    async def start(self) -> asyncio.base_events.Server:
        cfg = self.core.cfg
        server = await asyncio.start_server(self._client, cfg.web_host, cfg.web_port)
        log.debug("web server on %s:%s", cfg.web_host, cfg.web_port)
        return server

    async def _client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        try:
            while True:
                keep = await self._request(reader, writer)
                if not keep:
                    break
        except (asyncio.IncompleteReadError, ConnectionError, asyncio.LimitOverrunError,
                ValueError):
            pass
        except Exception:
            log.exception("web request failed")
        finally:
            writer.close()

    async def _request(self, reader, writer) -> bool:
        head = await reader.readuntil(b"\r\n\r\n")
        if len(head) > 16384:
            return False
        lines = head.decode("latin-1").split("\r\n")
        method, target, _ = (lines[0].split(" ") + ["", ""])[:3]
        headers = {}
        for h in lines[1:]:
            k, sep, v = h.partition(":")
            if sep:
                headers[k.strip().lower()] = v.strip()
        length = int(headers.get("content-length", "0") or 0)
        if length > MAX_BODY:
            await self._send(writer, 413, {"error": "too large"})
            return False
        body = await reader.readexactly(length) if length else b""
        url = urlsplit(target)
        res = await self._route(method, url.path, parse_qs(url.query), headers, body)
        status, payload, ctype = res[:3]
        await self._send(writer, status, payload, ctype, res[3] if len(res) > 3 else None)
        return headers.get("connection", "").lower() != "close"

    async def _route(self, method, path, query, headers, body):
        core = self.core
        if path.startswith("/api/"):
            if method == "GET" and path == "/api/state":
                since = int((query.get("since") or ["-1"])[0] or -1)
                ch = (query.get("ch") or [""])[0]            # CR45: the channel shown
                await core.wait_change(since, POLL_SEC)
                return 200, core.snapshot(int(ch) if ch.isdigit() else None), None
            if method == "GET" and path == "/api/aprs/station":     # CR65: one call
                win = (query.get("win") or ["0"])[0]
                call = (query.get("call") or [""])[0]
                if not call:
                    return 400, {"error": "call"}, None
                return 200, core.aprs_stats.station(call, int(win) if win.isdigit() else 0), None
            if method == "GET" and path == "/api/aprs/graph":       # CR79: network graph
                win = (query.get("win") or ["0"])[0]
                return 200, core.aprs_stats.graph(int(win) if win.isdigit() else 0,
                                                  me=core.cfg.mycall), None
            if method == "GET" and path == "/api/aprs/stats":       # CR61
                win = (query.get("win") or ["0"])[0]
                return 200, core.aprs_stats.report(int(win) if win.isdigit() else 0), None
            if method == "GET" and path == "/api/connlog":          # CR44
                return 200, core.logbook.rows(200), None
            if method == "GET" and path in ("/api/connlog.csv", "/api/connlog.adi"):
                return self._connlog_file(path)
            if method == "GET" and path == "/api/mail":
                folder = (query.get("folder") or ["inbox"])[0]
                if folder not in ("inbox", "sent", "outbox") and not folder.startswith(("b:", "s:")):
                    return 400, {"error": "folder"}, None
                return 200, {"folder": folder, "items": core.mailbox.folder(folder)}, None
            if method != "POST":
                return 405, {"error": "method"}, None
            if headers.get("x-tbclient") != "1":
                return 403, {"error": "X-TBClient header missing"}, None
            if not headers.get("content-type", "").startswith("application/json"):
                return 415, {"error": "json only"}, None
            try:
                data = json.loads(body or b"{}")
                if not isinstance(data, dict):
                    raise ValueError
            except ValueError:
                return 400, {"error": "bad json"}, None
            ok = True
            if path == "/api/connect":           # {"target": "OE3XBS-8", "ch": 2} (CR42/45)
                t, ch = data.get("target"), data.get("ch")
                ok = await core.connect(None if t is None else str(t),
                                        ch if isinstance(ch, int) else None)
            elif path == "/api/disconnect":      # {"ch": 2}; none = the chat channel
                ch = data.get("ch")
                core.disconnect(ch if isinstance(ch, int) else None)
            elif path == "/api/aprs/stats/reset":  # CR61
                core.aprs_stats.reset()
            elif path == "/api/monitor/clear":    # CR50
                core.clear_monitor()
            elif path == "/api/ui":               # CR66: one UI frame from the monitor
                err = core.send_ui(str(data.get("dest", "")), str(data.get("via", "")),
                                   str(data.get("text", "")))
                return (200, {"ok": True}, None) if err is None \
                    else (400, {"ok": False, "error": err}, None)
            elif path == "/api/channel/close":   # CR45: an offline channel goes away
                ch = data.get("ch")
                ok = core.close_channel(ch if isinstance(ch, int) else 0)
            elif path == "/api/leave":
                core.leave()
            elif path == "/api/join":
                ok = core.join(int(data.get("board", 0)))
            elif path == "/api/freq":              # CR44: frequency of this session (MHz)
                ok = core.set_freq(str(data.get("freq", "")))
            elif path == "/api/term":              # CR43: a raw line from the terminal
                ch = data.get("ch")
                ok = core.send_raw(str(data.get("text", "")), ch if isinstance(ch, int) else None)
            elif path == "/api/peer/clear":        # CR78: {"ch": n} - delete the chat history
                ch = data.get("ch")
                ok = core.peer_clear(ch if isinstance(ch, int) else 0)
            elif path == "/api/peer/heard":        # CR78: {"ch": n} - whom it hears
                ch = data.get("ch")
                ok = core.peer_heard(ch if isinstance(ch, int) else 0)
            elif path == "/api/say":
                ok = core.say(str(data.get("text", "")))
            elif path == "/api/react":
                ok = core.react(int(data.get("seq", -1)), str(data.get("emoji", "")))
            elif path == "/api/symbol":
                ok = core.set_symbol(str(data.get("symbol", "")))
            elif path == "/api/profile":           # CR73: {"name", "loc", "home"}
                err = core.profiles.set(str(data.get("name", "")), str(data.get("loc", "")),
                                        str(data.get("home", "")))
                return (200, {"ok": True}, None) if not err \
                    else (400, {"ok": False, "error": err}, None)
            elif path == "/api/profile/later":     # CR73: "Later" on the invitation
                core.profiles.later()
            elif path == "/api/history":
                ok = core.load_history(int(data.get("n", 10)))
            elif path == "/api/histmode":
                ok = core.set_history_mode(str(data.get("mode", "")))
            elif path == "/api/image":
                try:
                    raw = base64.b64decode(str(data.get("data", "")), validate=True)
                except (ValueError, TypeError):
                    return 400, {"error": "bad data"}, None
                h = core.send_image(raw, str(data.get("blurhash", "")),
                                    str(data.get("caption", "")), str(data.get("quote", "")))
                return (200, {"ok": True, "hash": h}, None) if h else (400, {"ok": False}, None)
            elif path == "/api/image/get":
                ok = core.fetch_image(str(data.get("hash", "")))
            elif path == "/api/image/retry":
                ok = core.images.retry()
            elif path == "/api/image/dismiss":
                core.images.dismiss_upload()
            elif path.startswith("/api/mail/"):
                return self._mail(path[10:], data)
            else:
                return 404, {"error": "unknown"}, None
            return (200 if ok else 400), {"ok": ok}, None
        if method != "GET":
            return 405, {"error": "method"}, None
        if path.startswith("/img/"):                 # CR12: a fetched or sent image
            data = core.images.store.get(path[5:])
            if data is None:
                return 404, {"error": "not found"}, None
            return 200, data, "image/webp" if data[:4] == b"RIFF" else "image/jpeg"
        name = FILES.get(path)
        if name is None or not (STATIC / name).is_file():
            return 404, {"error": "not found"}, None
        data = (STATIC / name).read_bytes()
        if name == "index.html":                 # the page knows its version (CR18)
            data = data.replace(b"__TBC_VERSION__", VERSION.encode())
        return 200, data, TYPES.get(Path(name).suffix, "application/octet-stream")

    def _connlog_file(self, path: str):
        """The whole connection log as CSV (all, failed connects too) or ADIF
        (connections only, oldest first - as logbook programs expect it)."""
        cfg = self.core.cfg
        name = f"tbclient-connlog-{cfg.mycall}-{time.strftime('%Y%m%d')}{path[-4:]}"
        disp = {"Content-Disposition": f'attachment; filename="{name}"'}
        if path.endswith(".csv"):
            data = connlog.to_csv(self.core.logbook.rows()).encode("utf-8")
            return 200, data, "text/csv; charset=utf-8", disp
        rows = list(reversed(self.core.logbook.rows(connected_only=True)))
        data = connlog.to_adif(rows, cfg.mycall, "TBClient", VERSION, locator=cfg.locator,
                               operator=cfg.mycall).encode("utf-8")
        return 200, data, "text/plain; charset=us-ascii", disp

    def _mail(self, action: str, data: dict):
        core, box = self.core, self.core.mailbox
        try:
            if action == "open":
                m = box.open(int(data.get("id", 0)))
                core._touch()
                return (200, m, None) if m else (404, {"error": "not found"}, None)
            if action == "delete":
                ok = box.delete(int(data.get("id", 0)))
            elif action == "save":
                kind = str(data.get("type", "P")).upper()
                to = str(data.get("to", "")).strip().upper().replace(" ", "")
                subject = " ".join(str(data.get("subject", "")).split())[:60]
                body = str(data.get("body", "")).replace("\r\n", "\n")
                if kind not in ("P", "B") or not CALL_AT_RE.match(to):
                    return 400, {"error": "address"}, None
                oid = box.save_out(int(data.get("oid") or 0) or None, kind, to, subject, body)
                waits = core.send_outbox()          # CR47: out at once
                if waits:
                    core.sync._notice(f"The mail waits in the outbox: {waits}.")
                core._touch()
                return 200, {"ok": True, "oid": oid, "waits": waits}, None
            elif action == "discard":
                ok = box.discard_out(int(data.get("oid", 0)))
            elif action == "subscribe":
                rubric = str(data.get("rubric", "")).upper()
                if not RUBRIC_RE.match(rubric):
                    return 400, {"error": "rubric"}, None
                box.subscribe(rubric, bool(data.get("on")))
                ok = True
            elif action == "sync":
                ok = core.sync.start(str(data.get("scope", "mail")))
            elif action == "news":
                ok = core.open_news()
            elif action in ("abort", "cancel"):
                core.sync.abort()
                ok = True
            elif action == "fetch":
                err = core.sync.fetch(int(data.get("id", 0)))
                core._touch()
                return (200, {"ok": True}, None) if not err else (200, {"ok": False, "error": err}, None)
            else:
                return 404, {"error": "unknown"}, None
        except (TypeError, ValueError):
            return 400, {"error": "bad value"}, None
        core._touch()
        return (200 if ok else 400), {"ok": ok}, None

    async def _send(self, writer, status, payload, ctype=None, extra=None) -> None:
        if isinstance(payload, (bytes, bytearray)):
            data = bytes(payload)
        else:
            data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            ctype = "application/json; charset=utf-8"
        head = [f"HTTP/1.1 {status} {REASONS.get(status, '')}",
                f"Content-Type: {ctype}", f"Content-Length: {len(data)}",
                "Cache-Control: no-store"] + [f"{k}: {v}" for k, v in HEADERS.items()] \
            + [f"{k}: {v}" for k, v in (extra or {}).items()]
        writer.write(("\r\n".join(head) + "\r\n\r\n").encode("latin-1") + data)
        await writer.drain()
