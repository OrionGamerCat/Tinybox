"""KISS-TCP server in front of the TNC.

Clients (TinyBox, brocastd, a monitor) connect to the KISS-TCP port. Every
frame the TNC receives goes to all clients. Frames from clients go into ONE
send queue for the TNC:

    priority 0  U and S frames (UA, DM, RR, RNR, REJ, SREJ, SABM, DISC, XID ...)
    priority 1  I frames
    priority 2  UI frames (brocast pages, TBCHAT, beacons) and anything else

A KISS TNC takes every frame at once into its own buffer and sends them in
order - priorities would be useless if the hub passed frames on immediately.
So the hub only hands a frame to the TNC when the estimated air time already
queued in the TNC is below max_lead (default 1.5 s at the configured air
baud rate): an acknowledgement then waits at most that long, never behind a
whole brocast page.

Frames a client sends are also given to the OTHER clients when they go to the
TNC, as if heard on the air: brocastd sees what TinyBox sends and the other
way round (TinyBox's T1 pauses while the channel is busy).

KISS parameter frames from clients are ignored: the hub owns the TNC settings.

A frame that waited longer than stale_sec (TNC not ready, e.g. while it is
being initialised) is dropped: an old acknowledgement or I frame would only
confuse the stations' AX.25 state.

Status query (CR41): GET http://127.0.0.1:<status_port>/status gives the
state of the TNC, the queue with the waiting time in the hub, and the clients
as JSON. TinyBox polls it for its web GUI.
"""

from __future__ import annotations

import asyncio
import heapq
import itertools
import json
import logging
import time
from collections import deque
from dataclasses import dataclass, field

from prcore import kiss
from prcore.ax25.frame import addresses_valid
from prcore.termcolor import OK

from .linkstats import LinkStats, describe
from .tnc import Tnc
from .varamon import VaraMonitor

log = logging.getLogger(__name__)

PRIO_CONTROL, PRIO_I, PRIO_UI = 0, 1, 2


def priority(ax25: bytes) -> int:
    """Send priority of an AX.25 frame from its control field."""
    pos = 0
    while pos + 7 <= len(ax25):
        last = ax25[pos + 6] & 0x01
        pos += 7
        if last:
            break
    else:
        return PRIO_UI                                 # no proper address field
    if pos >= len(ax25) or pos < 14:
        return PRIO_UI
    c = ax25[pos]
    if c & 0x01 == 0:
        return PRIO_I
    if c & 0x03 == 0x01:
        return PRIO_CONTROL                            # S frame
    if c & 0xEF == 0x03:
        return PRIO_UI                                 # UI
    return PRIO_CONTROL                                # other U frames


PRIO_NAMES = {PRIO_CONTROL: "control", PRIO_I: "i", PRIO_UI: "ui"}
WAIT_KEEP_SEC = 600          # waiting times kept for the status (10 min)


def _src_call(ax25: bytes) -> str | None:
    """Source callsign of an AX.25 frame (second address), None for garbage."""
    if len(ax25) < 14:
        return None
    raw = ax25[7:14]
    try:
        base = bytes(b >> 1 for b in raw[:6]).decode("ascii").rstrip()
    except UnicodeDecodeError:
        return None
    if not base.isalnum():
        return None
    ssid = (raw[6] >> 1) & 0x0F
    return f"{base}-{ssid}" if ssid else base


@dataclass
class Client:
    name: str
    writer: asyncio.StreamWriter
    rx: int = 0           # frames from this client
    tx: int = 0           # frames to this client
    since: float = field(default_factory=time.time)
    air: float = 0.0      # estimated seconds on air of this client's frames
    calls: dict = field(default_factory=dict)   # source call -> frames


@dataclass(frozen=True)
class HubCfg:
    listen: str = "127.0.0.1"
    port: int = 8101
    air_baud: int = 1200
    txdelay_sec: float = 0.3
    max_lead_sec: float = 1.5
    status_every_sec: float = 600
    status_port: int = 8102          # 0 = no status query
    stale_sec: float = 30.0
    links_file: str = ""             # CR67: one JSON line per finished AX.25 link ("" = off)
    vara_monitor: bool = False       # CR67: listen on VARA's command port (read only)
    vara_host: str = "127.0.0.1"
    vara_cmd_port: int = 8300
    sn_window_sec: float = 1.5       # VARA's SN line and the received frame belong together
    # CR70: what TinyBox and the client take from the status query ("radio")
    profile: str = "generic"
    sources: dict = field(default_factory=dict)   # value -> where it came from
    ax25: dict = field(default_factory=dict)      # AX.25 recommendation ([ax25] keys)
    # profile modem73: fixed air time per frame (txdelay = lead + frame); a frame queued
    # behind another goes out in the same key-up and adds frame_sec (frame + 200 ms gap)
    frame_sec: float = 0.0           # 0 = air time by bytes (HDLC TNCs, VARA)
    max_frame: int = 0               # longest frame the modem takes (0 = no limit)


class Hub:
    def __init__(self, cfg: HubCfg, tnc_factory) -> None:
        """tnc_factory(on_frame) -> Tnc (lets tests plug in their own transport)."""
        self.cfg = cfg
        self.tnc: Tnc = tnc_factory(self._from_tnc)
        self.clients: dict[asyncio.StreamWriter, Client] = {}
        self._queue: list[tuple[int, int, bytes, int, Client | None, float]] = []
        self._waits: deque[tuple[float, int, float]] = deque()   # (time, prio, waited s)
        self.started = time.time()
        self._status_server: asyncio.base_events.Server | None = None
        self._seq = itertools.count()
        self._kick = asyncio.Event()
        self._busy_until = 0.0                          # estimated end of the TNC's backlog
        self._server: asyncio.base_events.Server | None = None
        self._tasks: list[asyncio.Task] = []
        self.dropped = 0
        self.invalid = 0                                # CR74: frames with a garbage address field
        self.oversize = 0                               # modem73: longer than one modem frame
        self._names = itertools.count(1)
        # CR67: link quality from the frames passing the hub, VARA's own reports
        self.stats = LinkStats(airtime=self.airtime, on_closed=self._link_closed,
                               sn_window_sec=cfg.sn_window_sec)
        self.vara: VaraMonitor | None = None
        self.modem73 = None                             # Modem73Process, set by __main__
        if cfg.vara_monitor:
            self.vara = VaraMonitor(cfg.vara_host, cfg.vara_cmd_port, clock=self.now,
                                    on_sn=self.stats.sn)

    @property
    def port(self) -> int:
        return self._server.sockets[0].getsockname()[1] if self._server else self.cfg.port

    @staticmethod
    def now() -> float:
        return asyncio.get_running_loop().time()

    def airtime(self, nbytes: int) -> float:
        return self.cfg.txdelay_sec + (nbytes + 4) * 8 / self.cfg.air_baud

    # --- life cycle ------------------------------------------------------------------

    async def start(self) -> None:
        self._server = await asyncio.start_server(self._client, self.cfg.listen, self.cfg.port)
        log.debug("KISS-TCP server on %s:%d", self.cfg.listen, self.port)
        if self.cfg.status_port:
            self._status_server = await asyncio.start_server(
                self._status_client, "127.0.0.1",
                self.cfg.status_port if self.cfg.status_port > 0 else 0)
            log.debug("status query on http://127.0.0.1:%d/status", self.status_port)
        self._tasks = [asyncio.create_task(self.tnc.run()),
                       asyncio.create_task(self._sender()),
                       asyncio.create_task(self._status()),
                       asyncio.create_task(self._tick())]
        if self.vara is not None:
            self._tasks.append(asyncio.create_task(self.vara.run()))

    async def run(self) -> None:
        await self.start()
        await asyncio.gather(*self._tasks)

    @property
    def status_port(self) -> int:
        srv = self._status_server
        return srv.sockets[0].getsockname()[1] if srv else 0

    async def stop(self) -> None:
        if self._status_server is not None:
            self._status_server.close()
        if self._server is not None:
            self._server.close()
        for w in list(self.clients):
            w.close()
        self.stats.close_all()                          # open links into the links file
        try:
            await self.tnc.stop()
        finally:
            for t in self._tasks:
                t.cancel()
            await asyncio.gather(*self._tasks, return_exceptions=True)

    # --- clients -------------------------------------------------------------------------

    async def _client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        peer = writer.get_extra_info("peername")
        c = Client(f"client{next(self._names)} {peer[0]}:{peer[1]}" if peer else "client",
                   writer)
        self.clients[writer] = c
        log.info("%s connected (%d clients)", c.name, len(self.clients), extra=OK)
        dec = kiss.Decoder()
        try:
            while data := await reader.read(4096):
                for port, cmd, frame in dec.feed(data):
                    if cmd != kiss.CMD_DATA:
                        log.debug("%s: KISS command 0x%02X ignored", c.name, cmd)
                        continue
                    c.rx += 1
                    src = _src_call(frame)
                    if src and (src in c.calls or len(c.calls) < 20):
                        c.calls[src] = c.calls.get(src, 0) + 1
                    self.enqueue(frame, port, c)
        except (ConnectionError, OSError):
            pass
        finally:
            self.clients.pop(writer, None)
            writer.close()
            log.info("%s disconnected (%d clients)", c.name, len(self.clients))

    def _to_clients(self, port: int, frame: bytes, skip: Client | None = None) -> None:
        raw = kiss.encode(frame, port)
        for c in list(self.clients.values()):
            if c is skip or c.writer.is_closing():
                continue
            c.writer.write(raw)
            c.tx += 1

    # --- from the TNC ---------------------------------------------------------------------

    def _from_tnc(self, port: int, frame: bytes) -> None:
        if not addresses_valid(frame):
            # CR74: the TNC's checksum passed by chance (noise, open squelch at
            # 9600 Bd) - '^?kDa?-8' must not reach the heard lists of the stations
            self.invalid += 1
            log.info("invalid frame from the TNC dropped (%d bytes): %s", len(frame),
                     frame[:32].hex(" "))
            return
        self._to_clients(port, frame)
        now = self.now()
        self.stats.frame(frame, now, tx=False)           # CR67
        if self._busy_until > now:                       # it could not send meanwhile
            self._busy_until += self.airtime(len(frame))

    # --- to the TNC -------------------------------------------------------------------------

    def enqueue(self, frame: bytes, port: int = 0, origin: Client | None = None) -> None:
        heapq.heappush(self._queue, (priority(frame), next(self._seq), frame, port, origin,
                                     self.now()))
        self._kick.set()

    async def _sender(self) -> None:
        while True:
            if not self._queue or not self.tnc.ready.is_set():
                if not self._queue:
                    self._kick.clear()
                    await self._kick.wait()
                else:
                    await self.tnc.ready.wait()
                continue
            wait = self._busy_until - self.now() - self.cfg.max_lead_sec
            if wait > 0:                                  # TNC still has enough to send
                self._kick.clear()
                try:
                    await asyncio.wait_for(self._kick.wait(), wait)
                except asyncio.TimeoutError:
                    pass
                continue
            prio, _, frame, port, origin, queued = heapq.heappop(self._queue)
            now = self.now()
            if self.cfg.max_frame and len(frame) > self.cfg.max_frame:
                # modem73 would cut it - the other side would get a damaged frame
                self.oversize += 1
                self.dropped += 1
                log.warning("frame of %d bytes dropped: the modem takes at most %d per "
                            "frame - PACLEN of the station too large (%s)", len(frame),
                            self.cfg.max_frame, origin.name if origin else "?")
                continue
            if now - queued > self.cfg.stale_sec or not self.tnc.send_ax25(frame, port):
                self.dropped += 1
                continue
            self._waits.append((now, prio, now - queued))
            self.stats.frame(frame, now, tx=True)        # CR67: on the air (soon)
            if self.vara is not None:
                self.vara.handed(len(frame), now)
            while self._waits and self._waits[0][0] < now - WAIT_KEEP_SEC:
                self._waits.popleft()
            air = self.airtime(len(frame))
            if origin is not None:
                origin.air += air
            if self._busy_until <= now:
                self._busy_until = now + air
            elif self.cfg.frame_sec:                      # same key-up (modem73 burst)
                self._busy_until += self.cfg.frame_sec
            else:
                self._busy_until += air - self.cfg.txdelay_sec
            self._to_clients(port, frame, skip=origin)    # the others "hear" it

    # --- link quality (CR67) ------------------------------------------------------------------

    async def _tick(self) -> None:
        while True:
            await asyncio.sleep(5)
            now = self.now()
            self.stats.tick(now)
            if self.vara is not None:
                self.vara.tick(now)

    def _link_closed(self, rec: dict) -> None:
        """A link ended: log it, and one JSON line into the links file - the same
        line for PK-232 (HDLC) and VARA, so runs can be compared side by side."""
        log.info("link ended: %s", describe(rec))
        if not self.cfg.links_file:
            return
        from . import VERSION
        p = self.tnc.profile
        line = {"ended": time.time(), "kisshub": VERSION, "tnc": p.name, "tunnel": p.tunnel,
                "air_baud": self.cfg.air_baud, "txdelay_ms": round(self.cfg.txdelay_sec * 1000),
                "vara_fit": self.vara.burst_fit() if self.vara is not None else None,
                # tunnel counters since kisshub started (bundles: did it bundle at all?)
                "tunnel_counters": {k: v for k, v in self.tnc.status().items()
                                    if k in ("tunnel_tx", "tunnel_rx", "bundles_tx",
                                             "bundles_rx", "bundled_tx", "bundled_rx",
                                             "foreign", "echoes")},
                **rec}
        try:
            with open(self.cfg.links_file, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(line, ensure_ascii=False) + "\n")
        except OSError as exc:
            log.warning("links file %s: %s", self.cfg.links_file, exc)

    # --- status ------------------------------------------------------------------------------

    def status_dict(self) -> dict:
        """Everything for the status query (CR41)."""
        now = self.now()
        waits: dict = {}
        for prio, name in PRIO_NAMES.items():
            ws = [w for t, p, w in self._waits if p == prio and t >= now - WAIT_KEEP_SEC]
            waits[name] = {"frames": len(ws),
                           "avg_ms": round(sum(ws) / len(ws) * 1000) if ws else None,
                           "max_ms": round(max(ws) * 1000) if ws else None}
        queued: dict = {name: 0 for name in PRIO_NAMES.values()}
        for item in self._queue:
            queued[PRIO_NAMES[item[0]]] += 1
        from . import VERSION
        return {
            "version": VERSION, "started": self.started, "now": time.time(),
            "kiss_port": self.port, "air_baud": self.cfg.air_baud,
            "radio": self.radio_dict(),                              # CR70
            "tnc": self.tnc.status(),
            "quality": self.stats.status(now),                       # CR67 B + C
            "vara": self.vara.status(now) if self.vara is not None else None,   # CR67 A
            "modem73": self.modem73.status() if self.modem73 is not None else None,
            "queue": {"queued": queued, "wait_10min": waits, "dropped": self.dropped,
                      "invalid": self.invalid, "oversize": self.oversize,
                      "backlog_ms": max(0, round((self._busy_until - now) * 1000)),
                      "max_lead_ms": round(self.cfg.max_lead_sec * 1000)},
            "clients": [{"name": c.name, "since": c.since, "rx": c.rx, "tx": c.tx,
                         "air_sec": round(c.air, 1),
                         "calls": sorted(c.calls, key=c.calls.get, reverse=True)[:5]}
                        for c in self.clients.values()],
        }

    def radio_dict(self) -> dict:
        """CR70: the radio values the stations use instead of their own copies."""
        c = self.cfg
        return {"profile": c.profile, "air_baud": c.air_baud,
                "txdelay_ms": round(c.txdelay_sec * 1000),
                "max_lead_ms": round(c.max_lead_sec * 1000),
                "ax25": dict(c.ax25), "source": dict(c.sources)}

    async def _status_client(self, reader: asyncio.StreamReader,
                             writer: asyncio.StreamWriter) -> None:
        """Tiny HTTP: GET /status -> JSON. Loopback only, nothing can be changed."""
        try:
            head = await asyncio.wait_for(reader.readuntil(b"\r\n\r\n"), 5)
            line = head.split(b"\r\n", 1)[0].split()
            if len(line) >= 2 and line[0] == b"GET" and line[1] in (b"/status", b"/"):
                body = json.dumps(self.status_dict()).encode()
                writer.write(b"HTTP/1.0 200 OK\r\nContent-Type: application/json\r\n"
                             b"Cache-Control: no-store\r\nContent-Length: "
                             + str(len(body)).encode() + b"\r\n\r\n" + body)
            else:
                writer.write(b"HTTP/1.0 404 Not Found\r\nContent-Length: 0\r\n\r\n")
            await writer.drain()
        except (asyncio.TimeoutError, asyncio.IncompleteReadError, asyncio.LimitOverrunError,
                ConnectionError):
            pass
        finally:
            writer.close()

    def status(self) -> str:
        names = ", ".join(f"{c.name} rx {c.rx} tx {c.tx}" for c in self.clients.values())
        return (f"TNC {self.tnc.describe()} {self.tnc.state}: rx {self.tnc.rx_frames} "
                f"tx {self.tnc.tx_frames}, queued {len(self._queue)}, dropped "
                f"{self.dropped}, invalid {self.invalid}{self._smack_text()}{self._cts_text()}; "
                f"clients: {names or 'none'}")

    def _smack_text(self) -> str:
        t = self.tnc
        if not getattr(t, "profile", None) or not (t.profile.smack or t.smack_rx or t.crc_errors):
            return ""
        return (f", SMACK {'on' if t.smack_seen else 'waiting for the TNC'}"
                f" (CRC ok {t.smack_rx}, bad {t.crc_errors})")

    def _cts_text(self) -> str:
        fs = getattr(self.tnc.transport, "flow_status", None)
        if fs is None or not getattr(self.tnc.transport, "rtscts", False):
            return ""
        f = fs()
        return (f", CTS low {f['cts_drops']}x ({f['cts_low_s']} s, max {f['cts_low_max_ms']} ms)"
                f", writer waits {f['cts_waits']} ({f['cts_wait_s']} s)")

    async def _status(self) -> None:
        if self.cfg.status_every_sec <= 0:
            return
        while True:
            await asyncio.sleep(self.cfg.status_every_sec)
            log.info("status: %s", self.status())
