"""VARA command port 8300, read only (CR67, part A).

kisshub opens a second TCP connection to VARA's command port and only LISTENS:
it never sends a command. VARA reports there what it does (format as far as
known - VARA changelog, Pat-Vara, Mercury; parser tolerant, the rest is logged):

    SN 8.2                 signal/noise in dB; VARA HF since v4.7.2 also for every
                           KISS frame received -> given to that frame's station
    PTT ON / PTT OFF       transmitter keyed / released -> real airtime per burst,
                           waiting time from "frame handed to VARA" to PTT ON
    BUSY ON / BUSY OFF     channel busy (VARA's detector) -> busy share
    BITRATE (2) 600 BPS    speed level and bit rate (ARQ; maybe KISS)
    IAMALIVE               keepalive
    MISSING SOUNDCARD      USB audio gone - alarm (only a PC restart helps)
    VERSION ...            VARA version
    PENDING / CANCELPENDING   also in KISS mode: every ~2 s while sending, then CANCEL
    CONNECTED / DISCONNECTED  an ARQ connection - should not happen in KISS mode

Licence and encryption lines (REGISTERED, LINK ..., ENCRYPTION ...) are only
logged as text, never evaluated.

From PTT and the bytes kisshub handed to VARA, the monitor fits a straight
line  airtime = overhead + bytes * 8 / rate  - VARA's real cost per burst and
its rate, instead of the estimate from air_baud / txdelay_ms in the TNC section.

CAUTION (CR67 open question 2): with an older VARA, a program on the command
port together with KISS left the PTT keyed. Switch the monitor on the first
time with somebody at the radio. A PTT longer than ptt_alarm_sec raises an alarm.
"""

from __future__ import annotations

import asyncio
import logging
import re
import time
from collections import deque
from typing import Callable

log = logging.getLogger(__name__)

BURSTS_KEEP = 200
ALARMS_KEEP = 20
BUSY_WINDOW_SEC = 3600
SN_RE = re.compile(r"^SN\s+(-?\d+(?:[.,]\d+)?)")
BITRATE_RE = re.compile(r"^BITRATE\s+\((\d+)\)\s+(\d+)")
QUIET = ("REGISTERED", "LINK REGISTERED", "LINK UNREGISTERED", "ENCRYPTION",
         "ENCRYPTED LINK", "UNENCRYPTED LINK")


def fit_line(points: list[tuple[int, float]]) -> tuple[float, float] | None:
    """Least squares  seconds = a + b * bytes  -> (a = overhead s, b = s per byte).
    None while there are too few bursts or all have the same size."""
    if len(points) < 3:
        return None
    n = len(points)
    sx = sum(p[0] for p in points)
    sy = sum(p[1] for p in points)
    sxx = sum(p[0] * p[0] for p in points)
    sxy = sum(p[0] * p[1] for p in points)
    den = n * sxx - sx * sx
    if den == 0:
        return None
    b = (n * sxy - sx * sy) / den
    a = (sy - b * sx) / n
    return a, b


class VaraMonitor:
    def __init__(self, host: str, port: int, *, clock: Callable[[], float],
                 on_sn: Callable[[float, float], str | None] | None = None,
                 reconnect_sec: float = 10, ptt_alarm_sec: float = 60,
                 alive_timeout_sec: float = 180) -> None:
        self.host, self.port = host, port
        self.clock = clock
        self.on_sn = on_sn or (lambda v, t: None)
        self.reconnect_sec = reconnect_sec
        self.ptt_alarm_sec = ptt_alarm_sec
        self.alive_timeout = alive_timeout_sec
        self.connected = False
        self.since: float | None = None            # wall clock of the connection
        self.version: str | None = None
        self.last_line_t: float | None = None
        self.last_alive_t: float | None = None
        self.lines = 0
        self.unknown = 0
        self.raw: deque[tuple[float, str]] = deque(maxlen=30)   # last lines (wall, text)
        # PTT / bursts
        self.ptt = False
        self.ptt_on_t = 0.0
        self.bursts: deque[dict] = deque(maxlen=BURSTS_KEEP)
        self._pending_bytes = 0                    # handed to VARA since the last PTT ON
        self._pending_frames = 0
        self._pending_t: float | None = None
        self._burst_bytes = 0
        self._burst_frames = 0
        self._burst_wait: float | None = None
        # BUSY
        self.busy = False
        self.busy_on_t = 0.0
        self.busy_count = 0
        self._busy_spans: deque[tuple[float, float]] = deque()   # (start, end), last hour
        # SN / BITRATE
        self.sn_count = 0
        self.sn_assigned = 0
        self.sn_last: tuple[float, float, str | None] | None = None   # (wall, dB, call)
        self.bitrate: tuple[int, int] | None = None              # (level, bps)
        self.arq_lines = 0
        self.pending_lines = 0                     # PENDING/CANCELPENDING (KISS traffic)
        # alarms
        self.alarms: deque[dict] = deque(maxlen=ALARMS_KEEP)
        self._ptt_alarmed = False
        self._alive_warned = False

    # --- connection ---------------------------------------------------------------------

    async def run(self) -> None:
        warned = False
        while True:
            try:
                reader, writer = await asyncio.open_connection(self.host, self.port)
            except OSError as exc:
                (log.debug if warned else log.warning)(
                    "VARA command port %s:%d not reachable (%s), retrying every %ss",
                    self.host, self.port, exc, self.reconnect_sec)
                warned = True
                await asyncio.sleep(self.reconnect_sec)
                continue
            warned = False
            self.connected, self.since = True, time.time()
            self.last_alive_t = self.clock()
            log.info("VARA monitor: listening on the command port %s:%d (sends nothing)",
                     self.host, self.port)
            buf = b""
            try:
                while data := await reader.read(4096):
                    buf += data
                    *done, buf = re.split(rb"[\r\n]", buf)
                    for raw in done:
                        if raw.strip():
                            self.handle(raw.decode("ascii", "replace").strip(), self.clock())
            except (ConnectionError, OSError) as exc:
                log.warning("VARA command port lost: %s", exc)
            finally:
                writer.close()
                self.connected = False
                if self.ptt:                             # do not keep a "PTT on" forever
                    self.ptt = False
            log.warning("VARA command port closed, reconnecting in %ss", self.reconnect_sec)
            await asyncio.sleep(self.reconnect_sec)

    # --- what kisshub hands to VARA ------------------------------------------------------

    def handed(self, nbytes: int, t: float) -> None:
        """kisshub gave VARA a frame of nbytes (KISS payload) at time t."""
        if self._pending_t is None:
            self._pending_t = t
        self._pending_bytes += nbytes
        self._pending_frames += 1

    # --- lines from VARA -------------------------------------------------------------------

    def handle(self, line: str, t: float) -> None:
        self.lines += 1
        self.last_line_t = t
        self.raw.append((time.time(), line))
        up = line.upper()
        if up == "PTT ON":
            self._ptt_on(t)
        elif up == "PTT OFF":
            self._ptt_off(t)
        elif up == "BUSY ON":
            if not self.busy:
                self.busy, self.busy_on_t = True, t
                self.busy_count += 1
        elif up == "BUSY OFF":
            if self.busy:
                self.busy = False
                self._busy_spans.append((self.busy_on_t, t))
        elif up == "IAMALIVE":
            self.last_alive_t = t
            self._alive_warned = False
        elif m := SN_RE.match(up):
            value = float(m.group(1).replace(",", "."))
            self.sn_count += 1
            call = self.on_sn(value, t)
            if call:
                self.sn_assigned += 1
            self.sn_last = (time.time(), value, call)
        elif m := BITRATE_RE.match(up):
            self.bitrate = (int(m.group(1)), int(m.group(2)))
        elif up.startswith("VERSION"):
            self.version = line.partition(" ")[2].strip() or line
            log.info("VARA version: %s", self.version)
        elif up.startswith("MISSING SOUNDCARD"):
            self._alarm("missing soundcard - VARA lost its USB audio (restart the PC)")
        elif up in ("PENDING", "CANCELPENDING"):
            # seen in KISS mode too (VARA FM 4.4.0, 18.10.2026): every ~2 s while the
            # station sends KISS traffic, CANCELPENDING when done - not an ARQ call
            self.pending_lines += 1
            log.debug("VARA: %s", line)
        elif up.startswith(("CONNECTED", "DISCONNECTED")):
            self.arq_lines += 1
            log.warning("VARA reports an ARQ connection in KISS mode: %s", line)
        elif up.startswith(QUIET):
            log.debug("VARA: %s", line)                  # licence/encryption: text only
        elif up.startswith(("BUFFER", "OK", "WRONG")):
            log.debug("VARA: %s", line)
        else:
            self.unknown += 1
            (log.info if self.unknown <= 50 else log.debug)("VARA (unknown line): %s", line)

    def _ptt_on(self, t: float) -> None:
        if self.ptt:
            return
        self.ptt, self.ptt_on_t = True, t
        self._ptt_alarmed = False
        self._burst_bytes, self._burst_frames = self._pending_bytes, self._pending_frames
        self._burst_wait = (t - self._pending_t) if self._pending_t is not None else None
        self._pending_bytes = self._pending_frames = 0
        self._pending_t = None

    def _ptt_off(self, t: float) -> None:
        if not self.ptt:
            return
        self.ptt = False
        self.bursts.append({"t": time.time(), "sec": round(t - self.ptt_on_t, 3),
                            "bytes": self._burst_bytes, "frames": self._burst_frames,
                            "wait_sec": round(self._burst_wait, 3)
                            if self._burst_wait is not None else None})

    def _alarm(self, text: str) -> None:
        self.alarms.append({"t": time.time(), "text": text})
        log.error("ALARM: %s", text)

    def tick(self, t: float) -> None:
        if self.ptt and not self._ptt_alarmed and t - self.ptt_on_t > self.ptt_alarm_sec:
            self._ptt_alarmed = True
            self._alarm(f"PTT keyed for more than {self.ptt_alarm_sec:.0f} s - check the radio")
        if self.connected and self.last_alive_t is not None and not self._alive_warned \
                and t - max(self.last_alive_t, self.last_line_t or 0) > self.alive_timeout:
            self._alive_warned = True
            self._alarm(f"nothing from VARA for {self.alive_timeout:.0f} s")
        while self._busy_spans and self._busy_spans[0][1] < t - BUSY_WINDOW_SEC:
            self._busy_spans.popleft()

    # --- evaluation ----------------------------------------------------------------------

    def busy_share(self, t: float, window: float) -> float:
        """Share of the last `window` seconds VARA reported the channel busy."""
        start = t - window
        busy = sum(max(0.0, min(e, t) - max(s, start)) for s, e in self._busy_spans)
        if self.busy:
            busy += t - max(self.busy_on_t, start)
        return round(min(1.0, busy / window), 3)

    def burst_fit(self) -> dict | None:
        """VARA's real cost per burst: overhead (s) and rate (bit/s) from PTT times."""
        pts = [(b["bytes"], b["sec"]) for b in self.bursts if b["bytes"] > 0]
        f = fit_line(pts)
        if f is None or f[1] <= 0:
            return None
        return {"overhead_sec": round(f[0], 2), "rate_bps": round(8 / f[1]), "bursts": len(pts)}

    def status(self, t: float) -> dict:
        b = list(self.bursts)
        secs = [x["sec"] for x in b]
        waits = [x["wait_sec"] for x in b if x["wait_sec"] is not None]
        return {
            "connected": self.connected, "since": self.since, "version": self.version,
            "lines": self.lines, "unknown_lines": self.unknown, "arq_lines": self.arq_lines,
            "pending_lines": self.pending_lines,
            "alive_age_sec": round(t - self.last_alive_t, 1) if self.last_alive_t else None,
            "ptt": self.ptt, "busy": self.busy, "busy_count": self.busy_count,
            "busy_share_10min": self.busy_share(t, 600),
            "busy_share_60min": self.busy_share(t, 3600),
            "bursts": len(b),
            "burst_sec": {"avg": round(sum(secs) / len(secs), 2), "min": min(secs),
                          "max": max(secs)} if secs else None,
            "wait_sec": {"avg": round(sum(waits) / len(waits), 2), "max": max(waits)}
            if waits else None,
            "fit": self.burst_fit(), "last_bursts": b[-10:],
            "sn": {"count": self.sn_count, "assigned": self.sn_assigned,
                   "last": {"t": self.sn_last[0], "db": self.sn_last[1], "call": self.sn_last[2]}
                   if self.sn_last else None},
            "bitrate": {"level": self.bitrate[0], "bps": self.bitrate[1]}
            if self.bitrate else None,
            "alarms": list(self.alarms),
            "last_lines": [{"t": w, "line": l} for w, l in list(self.raw)[-10:]],
        }

    def lines_text(self, t: float) -> list[str]:
        s = self.status(t)
        fit = s["fit"]
        bs, ws = s["burst_sec"], s["wait_sec"]
        sn = s["sn"]["last"]
        return [
            f"VARA command port {self.host}:{self.port}: "
            f"{'listening' if s['connected'] else 'not connected'}"
            + (f", version {s['version']}" if s["version"] else "")
            + (f", last IAMALIVE {s['alive_age_sec']} s ago" if s["alive_age_sec"] is not None else ""),
            f"  bursts {s['bursts']}" + (f": {bs['avg']} s avg ({bs['min']}..{bs['max']})" if bs else "")
            + (f", waiting before PTT {ws['avg']} s avg (max {ws['max']})" if ws else ""),
            "  measured: " + (f"overhead {fit['overhead_sec']} s per burst + {fit['rate_bps']} bit/s "
                              f"({fit['bursts']} bursts)" if fit else "not enough bursts yet"),
            f"  busy {'ON' if s['busy'] else 'off'}, {s['busy_count']} times, share "
            f"{round(100 * s['busy_share_10min'])}% (10 min) / {round(100 * s['busy_share_60min'])}% (60 min)",
            f"  SN lines {s['sn']['count']} ({s['sn']['assigned']} given to a station)"
            + (f", last {sn['db']} dB {sn['call'] or ''}" if sn else "")
            + (f"; bitrate level {s['bitrate']['level']} {s['bitrate']['bps']} bps" if s["bitrate"] else ""),
        ] + [f"  ALARM {time.strftime('%H:%M:%S', time.localtime(a['t']))} {a['text']}"
             for a in s["alarms"][-3:]]
