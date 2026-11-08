"""brocast adapter: report bulletins to brocastd, which sends them as pages.

TinyBox stays a small text BBS. This adapter only listens on the event bus
and calls brocastd's ingest API on the same PC (standard library only):

    bulletin created / edited   -> PUT    /pages/tinybox/<msg number>
    bulletin deleted / expired  -> DELETE /pages/tinybox/<msg number>
    at start and every sync_min -> PUT    /pages/tinybox   (full list)
    every 30 s / on a change    -> PUT    /busy  {"level", "why"}: 2 = forward over the
                                   radio, 1 = stations connected over the radio, 0 = free;
                                   brocastd steps back ([traffic] in brocastd.conf)

Private messages (type P) and the system rubric TBNEWS (client news) are
never reported: TinyBox users get TBNEWS by connecting or via the client,
pure brocast listeners do not need it. If brocastd is not running,
TinyBox logs one warning and goes on; the next full sync catches up.

The full sync also carries the sysop's rubric list ([rubrics], CR19) as
"rubrics": [{"name": "WX", "cat": "wx", "desc": "Weather and warnings"}, ...]
in the order of tinybox.conf, ALL always first. brocastd replaces its list of
this provider's rubrics with it and sends the station's rubric index page
(typ index) over the air, so listeners know new rubrics (with description)
before the first page arrives and drop rubrics the sysop removed. Without a
[rubrics] section (every rubric free) the list is empty: no index page.

Mapping bulletin -> page (agreed 02.10.2026):
    ti   subject (max 40 chars; longer: full subject as heading)
    cat  from the destination via [brocast] rubrics (unknown: own rubric)
    to   destination, src ["tinybox", author] (Liste src, ab Dictionary v3), exp = bulletin lifetime
         (at most [brocast] air_days)
    born creation time of the bulletin (ingest-only, not on air): brocastd's
         carousel ages the page from it ([station] aging)
    blk  body, paragraphs split at blank lines; cut at max_bytes with a
         hint "Vollständig in der Mailbox <call>: R <n>"

[brocast] air_days limits the time on air independent of the mailbox: older
bulletins are left out of the sync, so brocastd withdraws them, while TinyBox
keeps them until bulletin_expire_days.

Bulletins from the inbox may carry a ready page ("Brocast:" header, PLANUNG
6d, e.g. a weather page typ wx). Then that page is sent instead; TinyBox only
fills in ti, cat and exp if missing. If brocastd rejects it, the text page is
sent as a fallback.
"""

from __future__ import annotations

import asyncio
import calendar
import json
import logging
import time
from datetime import datetime
from typing import TYPE_CHECKING, Any

from ..config import NEWS_RUBRIC
from ..store import Message

if TYPE_CHECKING:
    from ..app import App

log = logging.getLogger(__name__)

PROVIDER = "tinybox"
TITLE_MAX = 40
TIMEOUT_SEC = 5
RETRY_SEC = 60                    # full sync interval while brocastd is not reachable
BUSY_SEC = 30                     # busy report to brocastd at least this often (it expires
BUSY_CHECK_SEC = 5                # after [traffic] hint_timeout_s there), checked this often
FOREVER_MIN = 365 * 1440          # bulletins never expire (bulletin_expire_days = 0)


# --- mapping ----------------------------------------------------------------

def _paragraphs(text: str) -> list[str]:
    paras, cur = [], []
    for line in text.replace("\r\n", "\n").split("\n"):
        if line.strip():
            cur.append(line.rstrip())
        elif cur:
            paras.append("\n".join(cur))
            cur = []
    if cur:
        paras.append("\n".join(cur))
    return paras


def _cut(text: str, max_bytes: int) -> tuple[str, bool]:
    raw = text.encode("utf-8")
    if len(raw) <= max_bytes:
        return text, False
    head = raw[:max_bytes].decode("utf-8", errors="ignore")
    for sep in ("\n\n", "\n", ". ", " "):            # nicest boundary in the back half
        pos = head.rfind(sep)
        if pos > len(head) // 2:
            return head[:pos + (1 if sep == ". " else 0)].rstrip(), True
    return head.rstrip(), True


def lifetime_min(days: int) -> int:
    """Validity sent to brocastd. Kept constant (not "time left") so that the
    hourly sync does not create a new page revision every time; when the
    bulletin really expires, TinyBox withdraws the page (message.expired)."""
    return FOREVER_MIN if days <= 0 else days * 1440


TIME_FMT = "%Y-%m-%dT%H:%M:%SZ"


def born(msg: Message) -> int | None:
    """Creation time of the bulletin as Unix seconds (UTC), None if unknown."""
    try:
        return calendar.timegm(time.strptime(msg.created, TIME_FMT))
    except (TypeError, ValueError):
        return None


def on_air(msg: Message, app: App, now: float | None = None) -> bool:
    """False once the bulletin is older than [brocast] air_days."""
    days = app.cfg.brocast.air_days
    t = born(msg)
    if days <= 0 or t is None:
        return True
    return (time.time() if now is None else now) - t < days * 86400


def _valid_min(msg: Message) -> int | None:
    """Bulletins from the inbox with "Valid:": the same validity for the page.
    expires - created is constant per content, so syncs stay idempotent."""
    if not msg.expires:
        return None
    try:
        span = (datetime.strptime(msg.expires, TIME_FMT)
                - datetime.strptime(msg.created, TIME_FMT))
    except ValueError:
        return None
    return max(int(span.total_seconds() // 60), 1)


def text_page(msg: Message, app: App) -> dict[str, Any]:
    """The bulletin text as a text page (typ text, or alert for WARN)."""
    cfg = app.cfg.brocast
    subject = msg.subject.strip() or "(no subject)"
    blocks: list[dict[str, Any]] = []
    title = subject
    if len(subject) > TITLE_MAX:
        title = subject[:TITLE_MAX - 1].rstrip() + "…"
        blocks.append({"k": "heading", "x": subject})
    body, cut = _cut(msg.body, cfg.max_bytes)
    blocks += [{"k": "para", "x": p} for p in _paragraphs(body)]
    if cut:
        blocks.append({"k": "note", "st": "info",
                       "x": f"Gekürzt. Vollständig in der Mailbox "
                            f"{app.cfg.station.mailbox_call}: R {msg.id}"})
    if not blocks:
        blocks.append({"k": "para", "x": "(leer)"})
    page = {
        # bulletins to an alert destination (WARN) become warning pages: the
        # listener always shows them, highlighted, even if the rubric is deselected
        "typ": "alert" if msg.to_call in cfg.alert_destinations else "text",
        "ti": title,
        "cat": [cfg.rubrics.get(msg.to_call, msg.to_call)],
        "to": msg.to_call,
        "src": ["tinybox", msg.from_call],
        "exp": _exp(msg, app),
        "blk": blocks,
    }
    _set_born(page, msg)
    return page


def _set_born(page: dict[str, Any], msg: Message) -> None:
    t = born(msg)
    if t is not None:
        page.setdefault("born", t)


def _exp(msg: Message, app: App) -> int:
    exp = _valid_min(msg) or lifetime_min(app.cfg.mailbox.bulletin_expire_days)
    air = app.cfg.brocast.air_days
    return min(exp, air * 1440) if air > 0 else exp


def delivered_page(msg: Message, app: App) -> dict[str, Any] | None:
    """The page that came with the bulletin ("Brocast:"), completed, or None."""
    if not msg.brocast:
        return None
    try:
        page = json.loads(msg.brocast)
    except ValueError:
        return None
    if not isinstance(page, dict):
        return None
    cfg = app.cfg.brocast
    subject = msg.subject.strip() or "(no subject)"
    page.setdefault("ti", subject if len(subject) <= TITLE_MAX
                    else subject[:TITLE_MAX - 1].rstrip() + "…")
    page.setdefault("cat", [cfg.rubrics.get(msg.to_call, msg.to_call)])
    page.setdefault("exp", _exp(msg, app))
    _set_born(page, msg)
    return page


def to_page(msg: Message, app: App) -> dict[str, Any]:
    """What goes to brocastd: the delivered page if there is one, else the text."""
    return delivered_page(msg, app) or text_page(msg, app)


def rubric_list(app: App) -> list[dict[str, str]]:
    """The sysop's rubrics for brocastd: accepted entries of [rubrics] in their
    order, ALL always first. cat = the same mapping the pages use."""
    cfg = app.cfg.brocast
    accepted = [r for r in app.cfg.rubrics if r.accepted]
    if not accepted:
        return []                       # no [rubrics]: every rubric is free, no list
    out: list[dict[str, str]] = []
    names = ["ALL"] + [r.name for r in accepted if r.name != "ALL"]
    descs = {r.name: r.description for r in accepted}
    for name in names:
        out.append({"name": name, "cat": cfg.rubrics.get(name, name),
                    "desc": descs.get(name, "")})
    return out


def wanted(msg: Message, app: App) -> bool:
    dests = app.cfg.brocast.destinations
    if msg.origin == "forward" and not app.cfg.forward.publish_to_brocast:
        return False                    # bulletins from other mailboxes stay off the air
    if msg.fwd == "H":
        return False                    # held for the sysop (e.g. new rubric, CR19)
    if msg.to_call == NEWS_RUBRIC:
        return False                    # client news: for TinyBox users only, not on brocast
    if not on_air(msg, app):
        return False                    # older than air_days: off the air, still in the mailbox
    return msg.type == "B" and (not dests or msg.to_call in dests)


# --- adapter ----------------------------------------------------------------

class BrocastPublisher:
    def __init__(self, app: App) -> None:
        self.app = app
        self.cfg = app.cfg.brocast
        # (method, key, body, fallback): fallback = text page if body is a delivered page
        self.queue: asyncio.Queue[tuple[str, str, Any, Any]] = asyncio.Queue()
        self.loop = asyncio.get_running_loop()
        self.online = True              # for "warn once" logging
        self.sent = 0
        for name in ("message.created", "message.edited", "message.deleted",
                     "message.expired"):
            app.bus.subscribe(name, self.on_event)

    # events arrive synchronously from the MessageService
    def on_event(self, name: str, data: dict) -> None:
        if name == "message.expired":
            for msg_id in data.get("ids", []):
                self._enqueue("DELETE", str(msg_id), None)
            return
        msg: Message = data["message"]
        if name == "message.deleted":
            if msg.type == "B":
                self._enqueue("DELETE", str(msg.id), None)
        elif wanted(msg, self.app):                     # created or edited bulletin
            page = delivered_page(msg, self.app)
            if page is None:
                self._enqueue("PUT", str(msg.id), text_page(msg, self.app))
            else:
                self._enqueue("PUT", str(msg.id), page, text_page(msg, self.app))
        elif name == "message.edited":                  # now private or other destination
            self._enqueue("DELETE", str(msg.id), None)

    def _enqueue(self, method: str, key: str, body: Any, fallback: Any = None) -> None:
        self.loop.call_soon_threadsafe(self.queue.put_nowait, (method, key, body, fallback))

    def bulletins(self) -> list[Message]:
        return [m for m in self.app.store.list_messages() if wanted(m, self.app)]

    def full_list(self) -> dict[str, Any]:
        return {str(m.id): to_page(m, self.app) for m in self.bulletins()}

    # --- busy report: brocast steps back for the real traffic (08.11.2026) ---------

    def busy_level(self) -> tuple[int, str]:
        """2 = forward over the radio, 1 = stations connected over the radio
        (KISS/AGW, not AXUDP/telnet), 0 = free."""
        fwd = self.app.forward
        if fwd is not None and getattr(fwd, "radio_busy", None):
            return 2, "Forward " + ", ".join(sorted(fwd.radio_busy))
        calls = sorted({s.call for s in self.app.registry
                        if getattr(s, "origin", "") == "radio" and not s.closed})
        if calls:
            more = f" +{len(calls) - 3}" if len(calls) > 3 else ""
            return 1, "verbunden: " + ", ".join(calls[:3]) + more
        return 0, ""

    async def busy_loop(self) -> None:
        last: tuple[int, str] | None = None
        sent_at = 0.0
        while True:
            now = time.monotonic()
            level = self.busy_level()
            if level != last or now - sent_at >= BUSY_SEC:
                status, _ = await self.request("PUT", "/busy", {"level": level[0], "why": level[1]},
                                               quiet=True)
                if status == 200:
                    if level != last:
                        log.debug("brocast: busy %s %s", *level)
                    last, sent_at = level, now
            await asyncio.sleep(BUSY_CHECK_SEC)

    async def run(self) -> None:
        worker = asyncio.create_task(self._worker())
        busy = asyncio.create_task(self.busy_loop())
        try:
            while True:
                await self.sync()
                # brocastd missing: try again every minute, so nothing waits up to an hour
                await asyncio.sleep(self.cfg.sync_min * 60 if self.online else RETRY_SEC)
        finally:
            worker.cancel()
            busy.cancel()

    async def sync(self) -> None:
        msgs = {str(m.id): m for m in self.bulletins()}
        pages = {key: to_page(m, self.app) for key, m in msgs.items()}
        rubrics = rubric_list(self.app)
        status, res = await self.request("PUT", f"/pages/{PROVIDER}",
                                         {"pages": pages, "rubrics": rubrics})
        if status == 200:
            log.info("brocast: %s bulletins in sync, %s withdrawn, %s rubrics", len(pages),
                     len(res.get("withdrawn", [])), len(rubrics))
            for key, err in (res.get("errors") or {}).items():
                msg = msgs.get(key)
                if msg is not None and delivered_page(msg, self.app) is not None:
                    log.warning("brocast: page of bulletin %s not accepted (%s) - "
                                "sending the text instead", key, err)
                    self._enqueue("PUT", key, text_page(msg, self.app))
                else:
                    log.warning("brocast: bulletin %s not accepted: %s", key, err)

    async def _worker(self) -> None:
        while True:
            method, key, body, fallback = await self.queue.get()
            status, res = await self.request(method, f"/pages/{PROVIDER}/{key}", body)
            if status == 400 and fallback is not None:
                log.warning("brocast: page of bulletin %s not accepted (%s) - "
                            "sending the text instead", key, res.get("error", ""))
                status, res = await self.request(method, f"/pages/{PROVIDER}/{key}", fallback)
            if status == 200:
                log.info("brocast: bulletin %s %s (page %s, %s subpages)", key,
                         "withdrawn" if method == "DELETE" else "published",
                         res.get("id"), res.get("subpages"))
            elif status == 404 and method == "DELETE":
                pass                                # was never published: fine
            elif status:
                log.warning("brocast: bulletin %s: HTTP %s %s", key, status, res.get("error", ""))

    async def request(self, method: str, path: str, body: Any = None,
                      quiet: bool = False) -> tuple[int, dict]:
        """One HTTP/1.1 request to brocastd. Returns (0, {}) if not reachable.
        quiet: the busy report - no log lines, does not count as reachable."""
        data = b"" if body is None else json.dumps(body, ensure_ascii=False).encode("utf-8")
        head = [f"{method} {self.cfg.ingest_path}{path} HTTP/1.1",
                f"Host: {self.cfg.ingest_host}:{self.cfg.ingest_port}",
                f"Content-Length: {len(data)}", "Connection: close"]
        if body is not None:
            head.append("Content-Type: application/json")
        if self.cfg.token:
            head.append(f"X-Brocast-Token: {self.cfg.token}")
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(self.cfg.ingest_host, self.cfg.ingest_port), TIMEOUT_SEC)
            writer.write(("\r\n".join(head) + "\r\n\r\n").encode("ascii") + data)
            await writer.drain()
            raw = await asyncio.wait_for(reader.read(), TIMEOUT_SEC)
            writer.close()
        except (OSError, asyncio.TimeoutError) as exc:
            if quiet:
                return 0, {}
            if self.online:
                log.warning("brocast: brocastd not reachable (%s) - bulletins will be "
                            "synced later", exc)
            self.online = False
            return 0, {}
        if not quiet:
            if not self.online:
                log.info("brocast: brocastd reachable again")
            self.online = True
            self.sent += 1
        try:
            status = int(raw.split(b" ", 2)[1])
            payload = json.loads(raw.split(b"\r\n\r\n", 1)[1] or b"{}")
        except (IndexError, ValueError):
            return 0, {}
        return status, payload if isinstance(payload, dict) else {"result": payload}


async def start(app: App) -> asyncio.Task:
    publisher = BrocastPublisher(app)
    app.brocast = publisher
    log.info("brocast: bulletins are reported to brocastd at http://%s:%s%s",
             app.cfg.brocast.ingest_host, app.cfg.brocast.ingest_port,
             app.cfg.brocast.ingest_path)
    return asyncio.create_task(publisher.run(), name="brocast")
