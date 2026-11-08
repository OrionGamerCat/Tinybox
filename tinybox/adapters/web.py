"""Sysop web GUI - a small HTTP server on 127.0.0.1 (standard library only).

Security model (the browser is the risky part, not the network):
  * listens on loopback only (checked in config)
  * Host header must be 127.0.0.1/localhost/[::1] with our port
    -> blocks DNS rebinding
  * login with a secret token (data/web.token), then an HttpOnly,
    SameSite=Strict session cookie
  * every POST needs the session's CSRF token in the X-CSRF-Token header
    and, if the browser sends one, a matching Origin
  * strict Content-Security-Policy (no inline script), no framing,
    no caching; the frontend only uses textContent (no innerHTML)
    because message texts come from the air and are untrusted
"""

from __future__ import annotations

import asyncio
import hmac
import json
import logging
import secrets
import threading
import time
from collections import deque
from dataclasses import asdict
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from prcore import aprs, termcolor

from .. import VERSION, config, connlog, framemon, linkq, logsetup
from ..app import App
from ..config import base_call, normalize_call
from ..service import ServiceError
from ..session import State

log = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).resolve().parent.parent / "web"
STATIC_FILES = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/app.css": ("app.css", "text/css; charset=utf-8"),
    "/app.js": ("app.js", "text/javascript; charset=utf-8"),
    "/logo.svg": ("logo.svg", "image/svg+xml"),
    "/aprsview.js": ("aprsview.js", "text/javascript; charset=utf-8"),     # CR55 (also the client's)
    "/aprsview.css": ("aprsview.css", "text/css; charset=utf-8"),
}
MAX_HEADER = 16 * 1024
MAX_BODY = 128 * 1024
MAX_WEB_SESSIONS = 20      # remembered logins (data/web.sessions)
SSE_PING_SEC = 15
BACKLOG_LINES = 600

SECURITY_HEADERS = {
    "Content-Security-Policy": ("default-src 'self'; script-src 'self'; style-src 'self'; "
                                "img-src 'self' data:; connect-src 'self'; "
                                "frame-ancestors 'none'; base-uri 'none'; form-action 'self'"),
    "X-Frame-Options": "DENY",
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "Cache-Control": "no-store",
    "Cross-Origin-Opener-Policy": "same-origin",
    "Cross-Origin-Resource-Policy": "same-origin",
}

STATUS_TEXT = {200: "OK", 303: "See Other", 400: "Bad Request", 401: "Unauthorized",
               403: "Forbidden", 404: "Not Found", 405: "Method Not Allowed",
               413: "Payload Too Large", 421: "Misdirected Request",
               500: "Internal Server Error"}

STATE_LABEL = {State.COMMAND: "idle", State.SEND_SUBJECT: "writing a message",
               State.SEND_BODY: "writing a message", State.CLOSED: "closing",
               State.CHAT: "chat"}


class HttpError(Exception):
    def __init__(self, status: int, message: str = "") -> None:
        super().__init__(message or STATUS_TEXT.get(status, ""))
        self.status = status


# --- live feed: log lines + events for the browser --------------------------

class Hub:
    """Fan-out of monitor lines and events to all open browser tabs."""

    def __init__(self) -> None:
        self.backlog: deque[dict] = deque(maxlen=BACKLOG_LINES)
        self.subscribers: set[asyncio.Queue] = set()

    def push(self, item: dict) -> None:
        if item.get("type") != "event":
            self.backlog.append(item)
        for q in list(self.subscribers):
            if q.qsize() < 1000:  # a stuck tab must not eat memory
                q.put_nowait(item)


class HubLogHandler(logging.Handler):
    """Copies TinyBox log records into the hub (thread-safe)."""

    def __init__(self, hub: Hub, loop: asyncio.AbstractEventLoop) -> None:
        super().__init__(logging.INFO)
        self.hub = hub
        self.loop = loop

    def emit(self, record: logging.LogRecord) -> None:
        if not record.name.startswith("tinybox") or record.name.startswith("tinybox.adapters.web"):
            return
        try:
            t = self.formatter_time(record)
            if record.name == "tinybox.frames":                     # CR52: channel frames
                item = {"type": "frame", "t": t, **getattr(record, "frame", {})}
            elif record.name == "tinybox.monitor" and isinstance(record.args, tuple) \
                    and len(record.args) == 2 and record.msg in ("%s > %s", "%s < %s"):
                item = {"type": "mon", "t": t, "call": str(record.args[0]),
                        "dir": record.msg[3], "text": str(record.args[1])}
            elif record.name == "tinybox.monitor" and isinstance(record.args, tuple) \
                    and len(record.args) == 1 and record.msg in ("> %s", "< %s"):
                # CR52: session text; the station is in the session context "#7 OE3TEC"
                ctx = logsetup.context().split()
                item = {"type": "mon", "t": t, "call": ctx[1] if len(ctx) > 1 else "?",
                        "dir": record.msg[0], "text": str(record.args[0])}
            else:
                item = {"type": "log", "t": t, "level": record.levelname,
                        "text": record.getMessage()}
                if getattr(record, "ui_hex", None) is not None and isinstance(record.args, tuple):
                    # a UI frame TinyBox sent: payload for the HEX view (AGW mode has no frames)
                    item.update(dst=str(record.args[0]), hex=record.ui_hex)
            if threading.current_thread() is threading.main_thread():
                self.hub.push(item)
            else:
                self.loop.call_soon_threadsafe(self.hub.push, item)
        except Exception:
            self.handleError(record)

    @staticmethod
    def formatter_time(record: logging.LogRecord) -> str:
        import time                                  # HH:MM:SS.mmm - milliseconds for the monitor
        return (time.strftime("%H:%M:%S", time.localtime(record.created))
                + f".{int(record.msecs):03d}")


# --- the server ----------------------------------------------------------------

class WebServer:
    def __init__(self, app: App) -> None:
        self.app = app
        self.cfg = app.cfg
        self.token = self._load_token()
        self.sessions: dict[str, str] = self._load_sessions()  # session id -> csrf token
        self.hub = Hub()
        self.port = self.cfg.web.port
        self.allowed_hosts: set[str] = set()
        self.server: asyncio.AbstractServer | None = None
        self._log_handler: HubLogHandler | None = None

    # token survives restarts, so a bookmarked login link keeps working
    def _load_token(self) -> str:
        path = self.cfg.storage.data_dir / "web.token"
        try:
            token = path.read_text(encoding="ascii").strip()
            if len(token) >= 32:
                return token
        except OSError:
            pass
        token = secrets.token_urlsafe(32)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(token + "\n", encoding="ascii")
        return token

    # logins survive a RESTART too (else the open page would need the login link again)
    def _sessions_path(self):
        return self.cfg.storage.data_dir / "web.sessions"

    def _load_sessions(self) -> dict[str, str]:
        try:
            data = json.loads(self._sessions_path().read_text(encoding="ascii"))
            if isinstance(data, dict):
                return {str(k): str(v) for k, v in list(data.items())[-MAX_WEB_SESSIONS:]}
        except (OSError, ValueError):
            pass
        return {}

    def _save_sessions(self) -> None:
        try:
            path = self._sessions_path()
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(dict(list(self.sessions.items())[-MAX_WEB_SESSIONS:])),
                            encoding="ascii")
        except OSError as exc:
            log.warning("web sessions not saved: %s", exc)

    async def start(self) -> None:
        self.server = await asyncio.start_server(self._handle, self.cfg.web.host,
                                                 self.cfg.web.port, limit=MAX_HEADER)
        self.port = self.server.sockets[0].getsockname()[1]
        self.allowed_hosts = {f"127.0.0.1:{self.port}", f"localhost:{self.port}",
                              f"[::1]:{self.port}"}
        loop = asyncio.get_running_loop()
        self._log_handler = HubLogHandler(self.hub, loop)
        logging.getLogger().addHandler(self._log_handler)
        framemon.flog.addHandler(self._log_handler)          # CR52 (does not propagate)
        if self.cfg.station.locator:                          # CR55: distance in the APRS line
            framemon.home = aprs.locator_to_latlon(self.cfg.station.locator)
        self.app.bus.subscribe("*", lambda name, data: self.hub.push(
            {"type": "event", "name": name}))
        self.app.web_login_url = f"http://127.0.0.1:{self.port}/login?token={self.token}"
        termcolor.kv(log, "Web GUI", f"http://127.0.0.1:{self.port}/", url=True)

    def close(self) -> None:
        if self._log_handler:
            logging.getLogger().removeHandler(self._log_handler)
            framemon.flog.removeHandler(self._log_handler)
        if self.server:
            self.server.close()

    # --- HTTP plumbing ---------------------------------------------------------

    async def _handle(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        try:
            try:
                head = await asyncio.wait_for(reader.readuntil(b"\r\n\r\n"), 10)
            except (asyncio.IncompleteReadError, asyncio.LimitOverrunError,
                    asyncio.TimeoutError, ConnectionError):
                return
            try:
                method, path, query, headers = self._parse_head(head)
                length = int(headers.get("content-length", "0") or "0")
                if length < 0 or length > MAX_BODY:
                    raise HttpError(413)
                body = await asyncio.wait_for(reader.readexactly(length), 10) if length else b""
                self._check_host(headers)
                await self._route(writer, method, path, query, headers, body)
            except HttpError as exc:
                self._json(writer, exc.status, {"error": str(exc)})
            except ServiceError as exc:
                self._json(writer, 400, {"error": exc.code, "detail": str(exc)})
            except (asyncio.IncompleteReadError, asyncio.TimeoutError):
                return
            except Exception:
                log.exception("web request failed")
                self._json(writer, 500, {"error": "internal error"})
            await writer.drain()
        except (ConnectionError, OSError):
            pass
        finally:
            try:
                writer.close()
            except (ConnectionError, OSError):
                pass

    @staticmethod
    def _parse_head(head: bytes):
        lines = head.decode("latin-1").split("\r\n")
        try:
            method, target, _version = lines[0].split(" ", 2)
        except ValueError:
            raise HttpError(400) from None
        headers = {}
        for line in lines[1:]:
            if ":" in line:
                k, v = line.split(":", 1)
                headers[k.strip().lower()] = v.strip()
        parts = urlsplit(target)
        return method.upper(), parts.path, parse_qs(parts.query), headers

    def _check_host(self, headers: dict) -> None:
        if headers.get("host", "").lower() not in self.allowed_hosts:
            raise HttpError(421, "wrong host")

    def _send(self, writer, status: int, body: bytes, ctype: str,
              extra: dict | None = None) -> None:
        hdrs = {"Content-Type": ctype, "Content-Length": str(len(body)),
                "Connection": "close", **SECURITY_HEADERS, **(extra or {})}
        head = f"HTTP/1.1 {status} {STATUS_TEXT.get(status, '')}\r\n" + \
               "".join(f"{k}: {v}\r\n" for k, v in hdrs.items()) + "\r\n"
        writer.write(head.encode("latin-1") + body)

    def _json(self, writer, status: int, data) -> None:
        self._send(writer, status, json.dumps(data).encode("utf-8"),
                   "application/json; charset=utf-8")

    def _redirect(self, writer, location: str, extra: dict | None = None) -> None:
        self._send(writer, 303, b"", "text/plain", {"Location": location, **(extra or {})})

    # --- auth --------------------------------------------------------------------

    @staticmethod
    def _cookie(headers: dict) -> str | None:
        for part in headers.get("cookie", "").split(";"):
            name, _, value = part.strip().partition("=")
            if name == "tb_session":
                return value
        return None

    def _session_csrf(self, headers: dict) -> str | None:
        sid = self._cookie(headers)
        return self.sessions.get(sid) if sid else None

    def _require_auth(self, headers: dict) -> str:
        csrf = self._session_csrf(headers)
        if csrf is None:
            raise HttpError(401, "login required")
        return csrf

    def _require_post_ok(self, headers: dict) -> None:
        csrf = self._require_auth(headers)
        sent = headers.get("x-csrf-token", "")
        if not hmac.compare_digest(sent.encode(), csrf.encode()):
            raise HttpError(403, "bad csrf token")
        origin = headers.get("origin")
        if origin and origin.lower().removeprefix("http://") not in self.allowed_hosts:
            raise HttpError(403, "bad origin")

    async def _login(self, writer, token: str) -> None:
        if not hmac.compare_digest(token.encode(), self.token.encode()):
            log.warning("web login with wrong token")
            await asyncio.sleep(1)  # slow down guessing
            raise HttpError(403, "wrong token")
        sid = secrets.token_urlsafe(32)
        self.sessions[sid] = secrets.token_urlsafe(24)
        self._save_sessions()
        log.info("web login")
        self._redirect(writer, "/", {"Set-Cookie":
            f"tb_session={sid}; HttpOnly; SameSite=Strict; Path=/"})

    # --- routing -------------------------------------------------------------------

    async def _route(self, writer, method, path, query, headers, body) -> None:
        if path == "/login":
            if method == "GET" and "token" in query:
                return await self._login(writer, query["token"][0])
            if method == "POST":
                form = parse_qs(body.decode("utf-8", "replace"))
                return await self._login(writer, form.get("token", [""])[0])
            return self._send(writer, 200, (STATIC_DIR / "login.html").read_bytes(),
                              "text/html; charset=utf-8")

        if path in STATIC_FILES:
            if method != "GET":
                raise HttpError(405)
            if path == "/" and self._session_csrf(headers) is None:
                return self._redirect(writer, "/login")
            name, ctype = STATIC_FILES[path]
            return self._send(writer, 200, (STATIC_DIR / name).read_bytes(), ctype)

        if not path.startswith("/api/"):
            raise HttpError(404)

        csrf = self._require_auth(headers)
        if method == "POST":
            self._require_post_ok(headers)
        elif method != "GET":
            raise HttpError(405)

        parts = [p for p in path[len("/api/"):].split("/") if p]
        data = json.loads(body or b"{}") if method == "POST" else {}
        if not isinstance(data, dict):
            raise HttpError(400, "json object expected")

        if method == "GET" and parts == ["session"]:
            return self._json(writer, 200, {"csrf": csrf})
        if method == "GET" and parts == ["feed"]:
            return await self._feed(writer)
        if method == "GET" and parts == ["messages"] and query.get("q"):     # CR49 search
            sysop = self.app.cfg.station.sysop_call
            found = self.app.service.search(sysop, True, query["q"][0][:100])
            return self._json(writer, 200, [self._msg(m) for m in found])
        if method == "GET" and parts in (["connlog.csv"], ["connlog.adi"]):   # CR44 export
            return self._connlog_file(writer, parts[0], query)
        result = self._api(method, parts, data)
        self._json(writer, 200, result)

    def _api(self, method: str, parts: list[str], data: dict):
        app, svc = self.app, self.app.service
        sysop = app.cfg.station.sysop_call
        if method == "GET":
            if parts == ["status"]:
                return self._status()
            if parts == ["messages"]:
                return [self._msg(m) for m in svc.list_for(sysop, sysop=True)]
            if len(parts) == 2 and parts[0] == "messages":
                return self._msg(svc.read(self._int(parts[1]), sysop, sysop=True), body=True)
            if parts == ["sessions"]:
                return self._sessions()
            if len(parts) == 3 and parts[0] == "sessions" and parts[2] == "linkq":
                return self._linkq(parts[1])
            if parts == ["jlog"]:
                rows = [asdict(e) for e in app.store.jlog_list(100)]
                known = app.store.profiles_get(sorted({r["call"].split("-", 1)[0] for r in rows}))
                for r in rows:                   # CR73: name, locator, home BBS
                    p = known.get(r["call"].split("-", 1)[0]) or {}
                    r.update(name=p.get("name", ""), loc=p.get("loc", ""), home=p.get("home", ""))
                return rows
            if parts == ["connlog"]:
                return app.store.connlog_list(limit=1000)
            if parts == ["config"]:
                return self._config()
            if parts == ["rubrics"]:
                return self._rubrics()
            if parts == ["channel"]:
                return self._channel()
        else:
            if parts == ["messages"]:
                to_call, at_addr, bid = self._split_to(str(data.get("to", "")))
                msg_id = svc.create(from_call=sysop, to_call=to_call, at_addr=at_addr, bid=bid,
                                    type=str(data.get("type", "P")),
                                    subject=str(data.get("subject", "")),
                                    body=str(data.get("body", "")).replace("\r\n", "\n"),
                                    origin="sysop", sysop=True)
                return {"id": msg_id}
            if len(parts) == 3 and parts[0] == "messages" and parts[2] == "kill":
                svc.delete(self._int(parts[1]), sysop, sysop=True)
                return {"ok": True}
            if len(parts) == 3 and parts[0] == "messages" and parts[2] == "edit":
                m = svc.edit(self._int(parts[1]), str(data.get("field", "")),
                             str(data.get("value", "")), sysop, sysop=True)
                return self._msg(m, body=True)
            if len(parts) == 3 and parts[0] == "sessions" and parts[2] == "disconnect":
                return {"disconnected": self._disconnect(parts[1])}
            if parts == ["shutdown"]:
                delay = data.get("delay", 0)
                restart = data.get("restart") is True
                if not isinstance(delay, int) or delay < 0:
                    raise HttpError(400, "delay: seconds")
                what = "restart" if restart else "shutdown"
                if restart and app.config_path:      # never restart into a broken config
                    try:
                        config.load(app.config_path)
                    except config.ConfigError as exc:
                        raise HttpError(400, f"tinybox.conf has an error, not restarted: {exc}")
                if delay and len(app.registry):        # warn the stations first
                    log.info("%s in %d s requested from web GUI", what, delay)
                    return {"ok": True, "delay": app.shutdown.schedule(delay, sysop,
                                                                       restart=restart)}
                log.info("%s requested from web GUI", what)
                app.restart = restart
                if app.stop_event is not None:
                    asyncio.get_running_loop().call_later(0.3, app.stop_event.set)
                return {"ok": True, "delay": 0}
            if parts == ["reload"]:                              # CR82: no disconnect
                from .. import reload
                try:
                    res = reload.reload(app)
                except config.ConfigError as exc:
                    raise HttpError(400, f"tinybox.conf has an error, nothing changed: {exc}")
                log.info("reload requested from web GUI")
                return {"ok": True, "lines": res.lines(),
                        "changed": len(res.changed), "ignored": len(res.ignored)}
            if parts == ["monitor", "clear"]:                    # CR52: Clear for all tabs
                self.hub.backlog.clear()
                return {"ok": True}
            if parts == ["shutdown", "cancel"]:
                return {"ok": app.shutdown.cancel()}
        raise HttpError(404)

    def _connlog_file(self, writer, name: str, query: dict) -> None:
        """The whole connection log (CR44) as CSV or ADIF; ?call=OE3TEC = one station."""
        call = "".join(c for c in (query.get("call") or [""])[0].upper()
                       if c.isascii() and (c.isalnum() or c == "-"))[:9]   # goes into a header
        rows = self.app.store.connlog_list(base_call(call) if call else None)
        st = self.app.cfg.station
        stamp = time.strftime("%Y%m%d")
        if name.endswith(".csv"):
            body, ctype = connlog.to_csv(rows), "text/csv; charset=utf-8"
        else:
            rows = list(reversed(rows))                  # logbooks: oldest first
            body = connlog.to_adif(rows, st.mailbox_call, "TinyBox", VERSION, freq=st.freq,
                                   locator=st.locator, operator=st.sysop_call)
            ctype = "text/plain; charset=us-ascii"
        fname = f"tinybox-connlog-{stamp}{('-' + call) if call else ''}{name[7:]}"
        self._send(writer, 200, body.encode("utf-8"), ctype,
                   {"Content-Disposition": f'attachment; filename="{fname}"'})

    @staticmethod
    def _int(value: str) -> int:
        if not value.isdigit():
            raise HttpError(400, "number expected")
        return int(value)

    @staticmethod
    def _split_to(to: str) -> tuple[str, str, str | None]:
        """'TEST @ WW $BID' as at the terminal (SP/SB call @ address $BID):
        returns (recipient, @ address, BID); the service checks all three."""
        rest, _, bid = to.partition("$")
        call, _, at_addr = rest.partition("@")
        return call.strip(), at_addr.strip(), bid.strip() or None

    @staticmethod
    def _msg(m, body: bool = False) -> dict:
        d = {"id": m.id, "msgid": m.msgid, "type": m.type, "status": m.status,
             "to": m.to_call, "from": m.from_call, "subject": m.subject, "size": m.size,
             "origin": m.origin, "created": m.created,
             "at": m.at_addr, "bid": m.bid, "bid_kind": m.bid_kind, "fwd": m.fwd}
        if body:
            d["body"] = m.body
            d["rlines"] = m.rline_list
            d["note"] = m.note
        return d

    def _rubrics(self) -> list[dict]:
        """Rubrics for the dashboard: from [rubrics] (in that order), then the ones
        that only exist because bulletins are addressed to them."""
        from ..clientnews import RUBRIC as NEWS
        stats: dict[str, dict] = {}
        for m in self.app.store.list_messages():
            if m.type != "B":
                continue
            st = stats.setdefault(m.to_call, {"count": 0, "unread": 0, "newest": ""})
            st["count"] += 1
            st["unread"] += m.status == "N"
            st["newest"] = max(st["newest"], m.created)
        rows, seen = [], set()

        def row(name, desc, status):
            seen.add(name)
            st = stats.get(name, {"count": 0, "unread": 0, "newest": ""})
            rows.append({"name": name, "description": desc, "status": status,
                         "expire_days": self.app.service.rubric_expire_days(name), **st})

        conf = {r.name: r for r in self.app.cfg.rubrics}
        if "ALL" not in conf:
            row("ALL", "To everybody", "accepted")
        for r in self.app.cfg.rubrics:
            row(r.name, r.description, "accepted" if r.accepted or r.name == "ALL" else "refused")
        if NEWS not in seen:
            row(NEWS, "TinyBox News (client features)", "system")
        for name in sorted(stats):
            if name not in seen:
                row(name, "", "unlisted")
        return rows

    def _status(self) -> dict:
        cfg, msgs = self.app.cfg, self.app.store.list_messages()
        agw = self.app.agw
        return {
            "version": VERSION, "mailbox": cfg.station.mailbox_call,
            "update": self.app.update.status() if self.app.update is not None else None,
            "sysop": cfg.station.sysop_call, "started": self.app.started,
            "agw": "connected" if agw is not None and agw.connected.is_set()
                   else ("disconnected" if agw is not None else "not started"),
            "interface": cfg.radio.interface,
            "axudp": self.app.axudp.state() if self.app.axudp is not None else None,
            # KISS mode (CR41): kisshub and the TNC behind it
            "radio": agw.radio_state() if agw is not None and hasattr(agw, "radio_state") else None,
            "users": len(self.app.registry), "max_users": cfg.mailbox.max_users,
            "messages": len(msgs), "private": sum(m.type == "P" for m in msgs),
            "bulletins": sum(m.type == "B" for m in msgs),
            "unread": sum(m.status == "N" for m in msgs),
            "max_msg_bytes": cfg.mailbox.max_msg_bytes,
            "web": f"127.0.0.1:{self.port}",
            "shutdown_in": self.app.shutdown.seconds_left() if self.app.shutdown else None,
            "restart_pending": bool(self.app.shutdown and self.app.shutdown.pending
                                    and self.app.shutdown.restart),
            "forward": (None if self.app.forward is None else
                        {"queued": len(self.app.store.fwd_queue_list()),
                         "held": sum(m.fwd == "H" for m in msgs),
                         "lines": self.app.forward.status_lines()}),
        }

    def _session_json(self, s) -> dict:
        client = s.client
        return {"call": s.call, "origin": s.origin, "since": s.started,
                "state": (f"chat {s.chat_board}" if s.chat_board
                          else STATE_LABEL.get(s.state, s.state.name.lower())),
                "client": ({"proto": client.proto, "version": client.version, "ui": client.ui}
                           if client is not None else None)}

    @staticmethod
    def _direction(d, label: str) -> dict | None:
        if d is None:
            return None
        return {"label": label, "frames": d.frames, "lost": d.lost, "enough": d.enough,
                "loss": None if d.loss is None else round(d.loss, 1)}

    def _quality(self, s) -> dict | None:
        """Link quality summary for the user list: bars and the direction that set them."""
        r = linkq.result_for(self.app.service, s.call, s)
        if r is None:
            return None
        dirs = [("outgoing", r.out), ("incoming", r.inn), ("rx quote", r.rx)]
        known = [(n, d.loss) for n, d in dirs if d is not None and d.loss is not None]
        worst = max(known, key=lambda x: x[1]) if known else None
        return {"bars": r.bars, "t1": r.t1, "tentative": r.tentative,   # under min_frames
                "lost": {"outgoing": r.out.lost, "incoming": r.inn.lost},
                "worst": None if worst is None else {"dir": worst[0], "loss": round(worst[1], 1)},
                "frames": {"outgoing": r.out.frames, "incoming": r.inn.frames},
                "min_frames": self.app.cfg.direwolf.quality_min_frames}

    def _sessions(self) -> list[dict]:
        return [self._session_json(s) | {"quality": self._quality(s)} for s in self.app.registry]

    def _linkq(self, call: str) -> dict:
        """Everything behind the bars of one station (detail view)."""
        call = normalize_call(call)
        sessions = [s for s in self.app.registry if s.call == call]
        if not sessions:
            raise HttpError(404, f"{call} is not connected")
        s = sessions[0]
        if linkq.is_local(s):                          # AXUDP: connect type and time only
            return {"session": self._session_json(s), "local": True}
        dw = self.app.cfg.direwolf
        r = linkq.result_for(self.app.service, call, s)
        q = self.app.service.links.get(call)
        out = {"session": self._session_json(s), "quality": self._quality(s),
               "window": {"frames": dw.quality_window_frames, "minutes": dw.quality_window_min,
                          "min_frames": dw.quality_min_frames, "steps": list(dw.quality_steps),
                          "poll_sec": dw.quality_poll_sec},
               "result": None, "counters": None, "counters_window": None, "poll_age": None,
               "interface": self.app.cfg.radio.interface,
               "channel_load": self._channel_load()}
        if r is not None:
            out["result"] = {"bars": r.bars, "t1": r.t1,
                             "outgoing": self._direction(r.out, "TinyBox -> " + call),
                             "incoming": self._direction(r.inn, call + " -> TinyBox"),
                             "rx": self._direction(r.rx, "chat UI frames"),
                             "rx_quote": None if r.rx_quote is None else round(r.rx_quote, 1),
                             "window": {"i_retry": r.i_retry, "rej_rx": r.rej_rx, "rej_tx": r.rej_tx,
                                        "retry_rx": r.retry_rx, "t1_exp": r.t1,
                                        "bytes_new": r.bytes_new, "bytes_retry": r.bytes_retry},
                             "srt": r.srt}
        if q is not None and q.last is not None:
            out["counters"] = dict(q.last)
            if q.samples:
                out["poll_age"] = round(time.monotonic() - q.samples[-1][0])
                oldest = q.samples[0][1]
                out["counters_window"] = {k: q.last[k] - oldest.get(k, 0) for k in linkq.FIELDS_INT}
        return out

    def _channel(self) -> dict:
        """CR41: channel monitor and kisshub status (KISS mode only)."""
        agw = self.app.agw
        if agw is None or not hasattr(agw, "channel_snapshot"):
            raise HttpError(404, "channel monitor only in the KISS mode")
        return agw.channel_snapshot()

    def _channel_load(self) -> dict | None:
        agw = self.app.agw
        if agw is None or not hasattr(agw, "channel"):
            return None
        return {"load_10min": agw.channel.load(600), "load_1min": agw.channel.load(60)}

    def _disconnect(self, call: str) -> list[str]:
        call = normalize_call(call)
        sessions = list(self.app.registry)
        targets = [s for s in sessions if s.call == call] or \
                  [s for s in sessions if "-" not in call and base_call(s.call) == call]
        from .. import texts
        for s in targets:
            s.out(texts.DISC_BY_SYSOP)
            s.close()
            log.info("%s disconnected by sysop (web)", s.call)
        return [s.call for s in targets]

    def _config(self) -> dict:
        """Read-only view of tinybox.conf values (no secrets)."""
        cfg = self.app.cfg
        out = {}
        for section in ("station", "direwolf", "mailbox", "telnet", "web", "console",
                        "storage", "logging", "mqtt", "beacon"):
            values = {k: (str(v) if isinstance(v, Path) else v)
                      for k, v in asdict(getattr(cfg, section)).items()}
            out[section] = values
        out["file"] = str(cfg.path)
        return out

    # --- server-sent events ------------------------------------------------------

    async def _feed(self, writer) -> None:
        head = ("HTTP/1.1 200 OK\r\nContent-Type: text/event-stream; charset=utf-8\r\n"
                "Connection: keep-alive\r\n" +
                "".join(f"{k}: {v}\r\n" for k, v in SECURITY_HEADERS.items()) + "\r\n")
        writer.write(head.encode("latin-1"))
        q: asyncio.Queue = asyncio.Queue()
        for item in self.hub.backlog:
            q.put_nowait(item)
        self.hub.subscribers.add(q)
        try:
            while True:
                try:
                    item = await asyncio.wait_for(q.get(), SSE_PING_SEC)
                    writer.write(f"data: {json.dumps(item)}\n\n".encode("utf-8"))
                except asyncio.TimeoutError:
                    writer.write(b": ping\n\n")
                await writer.drain()
        except (ConnectionError, OSError, asyncio.CancelledError):
            pass
        finally:
            self.hub.subscribers.discard(q)


async def start(app: App) -> WebServer:
    server = WebServer(app)
    await server.start()
    return server
