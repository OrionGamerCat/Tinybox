"""Carousel: decides which page goes on air when.

  * a new revision goes out at once, then with growing gaps
    (repeat_minutes, then every max_interval_min); an old revision is
    repeated less often (aging: Alter -> Intervall, 0 = Pause)
  * all subpages of a page are sent in one slot, split into transmissions of
    at most burst_frames frames with burst_gap_s of free channel in between.
    Direwolf keys up once for everything in its queue, so the split has to
    happen here. With AGW, the next block waits until Direwolf's transmit
    queue is empty (queue_len), then airtime of the last frame + gap. With
    KISS there is no such feedback: the end is computed, assuming Direwolf
    could transmit at once.
  * higher priority first; expired pages are dropped, not sent
  * withdrawn pages are sent withdraw_repeats times, then removed
  * an airtime budget (percent of a sliding window) keeps the channel free
    for the BBS; emergency pages (pri 3) may exceed it
  * what is on the air right now, what waits and what went out last is kept
    for the web GUI (tx_state(), view "Sendung", 08.11.2026) - updated with
    every frame handed to Direwolf, like the Sendeprotokoll
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections import deque
from typing import Awaitable, Callable

from .config import StationCfg
from .frame import airtime_s, build as build_frame, tx_airtime_s
from .store import PageRow, Store
from .txlog import TxLog, title_of

log = logging.getLogger(__name__)

EMERGENCY = 3
MAX_SLEEP = 30.0
RESTING = 2 ** 31 - 1   # next_tx einer ruhenden Seite (aging-Intervall 0)
RECENT = 12             # pages kept in "zuletzt gesendet"
QUEUE_POLL_S = 0.5      # AGW: how often to ask Direwolf for its transmit queue
TX_MARGIN_S = 0.5       # AGW: TXTAIL + audio buffer after the queue became empty
QUEUE_STALE_S = 120.0   # AGW: queue empty and last block older -> long over, no pause
BUSY_WARN_S = 60.0


class AirtimeBudget:
    def __init__(self, percent: float, window_s: float):
        self.limit = window_s * percent / 100
        self.window = window_s
        self.used: deque[tuple[float, float]] = deque()

    def _trim(self, now: float) -> None:
        while self.used and self.used[0][0] < now - self.window:
            self.used.popleft()

    def spent(self, now: float) -> float:
        self._trim(now)
        return sum(a for _, a in self.used)

    def allows(self, now: float, needed: float) -> bool:
        spent = self.spent(now)
        # a single slot larger than the whole budget may go when nothing else ran
        return spent + needed <= self.limit or (spent == 0 and needed > self.limit)

    def add(self, now: float, airtime: float) -> None:
        self.used.append((now, airtime))

    def free_at(self, now: float, needed: float) -> float:
        """Earliest time at which `needed` seconds fit into the budget."""
        self._trim(now)
        spent = self.spent(now)
        for ts, amount in self.used:
            if spent + needed <= self.limit:
                break
            spent -= amount
            now = ts + self.window
        return now


class Carousel:
    def __init__(self, store: Store, send: Callable[[bytes], Awaitable[bool]],
                 cfg: StationCfg, callsign: str, clock: Callable[[], float] = time.time,
                 txlog: TxLog | None = None,
                 mono: Callable[[], float] = time.monotonic,
                 sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
                 queue_len: Callable[[], Awaitable[int | None]] | None = None):
        self.store, self.send, self.cfg, self.callsign = store, send, cfg, callsign
        self.clock = clock
        self.mono, self.sleep = mono, sleep
        self.queue_len = queue_len          # AGW only; None = KISS, pauses computed
        # current transmission: frames handed to Direwolf, computed end on air
        self._burst_count = 0
        self._burst_end = 0.0
        self._last_air = 0.0                # airtime of the last frame handed over
        self._handed_at = 0.0
        self.budget = AirtimeBudget(cfg.airtime_percent, cfg.airtime_window_min * 60)
        self._wake = asyncio.Event()
        self.sent_pages = 0
        # own schedules for single pages: (provider, key) -> gap_min(sends_done)
        self.schedules: dict[tuple[str, str], Callable[[int], int]] = {}
        self.txlog: TxLog | None = txlog
        # for the web GUI: the page on the air, the last ones, why it waits
        self.current: dict | None = None
        self.recent: deque[dict] = deque(maxlen=RECENT)
        self.blocked: dict | None = None      # {"reason": "budget"|"link", "until", "page"}
        self.last_queue: int | None = None    # AGW: frames Direwolf still holds (last look)
        self.day = ""
        self.day_pages = self.day_frames = 0
        # [beacon]: a plain-text UI frame every interval_s (build() -> the frame)
        self.beacon_build: Callable[[], bytes] | None = None
        self.beacon_interval_s = 0.0
        self.beacon_next = 0.0
        self.beacon_text = ""

    def wake(self) -> None:
        self._wake.set()

    def gap_min(self, sends_done: int, age_s: float = 0.0) -> int:
        """Minuten bis zur nächsten Aussendung. 0 = ruhen (nicht mehr senden).

        Zuerst die Staffel repeat_minutes (neue Revision), dann
        max_interval_min – und je nach Alter der Revision der größere
        Abstand aus aging (eine Woche alte Seite muss nicht alle 30 min
        wiederholt werden)."""
        gaps = self.cfg.repeat_minutes[1:]
        if sends_done - 1 < len(gaps):
            return gaps[sends_done - 1]
        gap = self.cfg.max_interval_min
        for hours, minutes in self.cfg.aging:          # aufsteigend sortiert
            if age_s >= hours * 3600:
                gap = minutes
        return gap

    async def _pace(self, frame_len: int) -> None:
        """Before handing one frame to Direwolf: start a new transmission (and
        wait for the gap) when the current one is full or already over."""
        limit = self.cfg.burst_frames
        if limit <= 0:
            return
        t = self.mono()
        if self._burst_count and (self._burst_count >= limit or t >= self._burst_end):
            await self._gap()
            self._burst_count = 0
        if self._burst_count == 0:
            # Direwolf keys up now (assumed: channel free): TXDELAY once per transmission
            self._burst_end = self.mono() + self.cfg.txdelay_ms / 1000
        self._last_air = airtime_s(frame_len, self.cfg.baud, 0)
        self._burst_end += self._last_air
        self._handed_at = self.mono()
        self._burst_count += 1

    async def _gap(self) -> None:
        """Wait until the previous transmission is over, then burst_gap_s."""
        gap = self.cfg.burst_gap_s
        if self.queue_len is not None:
            seen = await self._queue_empty()
            if seen is not None:
                empty_at, at_first_look = seen
                if at_first_look and empty_at - self._handed_at > QUEUE_STALE_S:
                    return                               # long over
                # last frame left the queue at empty_at at the latest: still on air
                wait = empty_at + self._last_air + TX_MARGIN_S + gap - self.mono()
                if wait > 0:
                    log.debug("Sendepause %.1f s (Direwolf-Queue leer)", wait)
                    await self.sleep(wait)
                return
        wait = self._burst_end + gap - self.mono()
        if wait > 0:
            log.debug("Sendepause %.1f s (berechnet)", wait)
            await self.sleep(wait)

    async def _queue_empty(self) -> tuple[float, bool] | None:
        """Poll Direwolf until its transmit queue is empty.
        -> (time it was seen empty, empty at the first look) or None if unknown."""
        assert self.queue_len is not None
        first, since = True, self.mono()
        while True:
            n = await self.queue_len()
            self.last_queue = n
            if n is None:
                return None
            if n == 0:
                return self.mono(), first
            first = False
            if self.mono() - since > BUSY_WARN_S:
                log.warning("Direwolf hält seit über %.0f s %s Frames zurück – Kanal belegt?",
                            BUSY_WARN_S, n)
                since = self.mono()
            await self.sleep(QUEUE_POLL_S)

    async def run(self) -> None:
        while True:
            delay = await self.step()
            self._wake.clear()
            try:
                await asyncio.wait_for(self._wake.wait(), timeout=delay)
            except asyncio.TimeoutError:
                pass

    def set_beacon(self, build: Callable[[], bytes], interval_min: int, text: str) -> None:
        self.beacon_build, self.beacon_interval_s, self.beacon_text = build, interval_min * 60.0, text
        self.beacon_next = self.clock()                 # the first one right at the start

    async def _beacon(self, now: float) -> bool:
        """[beacon] due: one UI frame in plain text, between two pages (never in
        the middle of one). Counts towards the airtime, but is never held back
        by the budget - it is the station's identification. False = link down."""
        if self.beacon_build is None or self.beacon_interval_s <= 0 or now < self.beacon_next:
            return True
        frame = self.beacon_build()
        await self._pace(len(frame))
        if not await self.send(frame):
            self._burst_count = 0
            return False
        air = airtime_s(len(frame), self.cfg.baud, self.cfg.txdelay_ms)
        self.budget.add(now, air)
        self._count_frame()
        self.beacon_next = now + self.beacon_interval_s
        if self.txlog:
            self.txlog.record(self.clock(), "BEACON", 0, 0, 1, 1, "beacon", len(frame),
                              airtime_s(len(frame), self.cfg.baud, 0), "brocastd", "beacon",
                              self.beacon_text)
        self.recent.appendleft({"t": self.clock(), "id": None, "title": self.beacon_text,
                                "typ": "beacon", "pri": 0, "sent": 1, "total": 1,
                                "air": round(air, 1), "result": "ok"})
        log.info("Bake gesendet (%s Bytes)", len(frame))
        return True

    async def step(self) -> float:
        """Send what is due. Returns seconds until the next useful step."""
        now = self.clock()
        if not await self._beacon(now):
            log.debug("Direwolf nicht verbunden, Bake verschoben")
            return 5.0
        for row in self.store.expired_pages(int(now)):
            log.info("Seite %s (%s/%s) abgelaufen, entfernt", row.id, row.provider, row.pkey)
            self.store.delete_page(row.pid)

        for row in self.store.due_pages(int(now)):
            frames = [build_frame(self.callsign, data, self.cfg.path, row.hdr)
                      for data in self.store.frames(row.pid)]
            needed = tx_airtime_s([len(f) for f in frames], self.cfg.baud,
                                  self.cfg.txdelay_ms, self.cfg.burst_frames)
            if row.pri < EMERGENCY and not self.budget.allows(now, needed):
                wait = self.budget.free_at(now, needed) - now
                log.debug("Airtime-Budget erschöpft, warte %.0f s", wait)
                self.blocked = {"reason": "budget", "until": now + wait, "page": row.id,
                                "waiting": len(self.store.due_pages(int(now)))}
                return min(max(wait, 1.0), MAX_SLEEP)
            typ, title = title_of(row.content)
            dest = "BROCST" + ("," + ",".join(self.cfg.path) if self.cfg.path else "")
            airs = [airtime_s(len(f), self.cfg.baud, 0) for f in frames]
            self.current = {"id": row.id, "rev": row.rev, "typ": typ, "title": title,
                            "provider": row.provider, "pkey": row.pkey, "pri": row.pri,
                            "withdrawn": row.state == "withdrawn", "dest": dest,
                            "total": len(frames), "sent": 0, "bytes": sum(len(f) for f in frames),
                            "air": round(needed, 1), "air_done": 0.0, "started": self.clock(),
                            "handed": None, "bursts": self._bursts(len(frames))}
            for n, f in enumerate(frames, start=1):
                await self._pace(len(f))
                if not await self.send(f):
                    self._burst_count = 0
                    log.debug("Direwolf nicht verbunden, Senden verschoben")
                    self._done("paused")
                    self.blocked = {"reason": "link", "until": self.clock() + 5, "page": row.id}
                    return 5.0
                self.blocked = None
                cur = self.current
                if cur is not None:
                    cur["sent"], cur["handed"] = n, self.clock()
                    cur["air_done"] = round(cur["air_done"] + airs[n - 1], 1)
                self._count_frame()
                if self.txlog:
                    self.txlog.record(self.clock(), dest, row.id, row.rev, n, len(frames), typ,
                                      len(f), airtime_s(len(f), self.cfg.baud, 0),
                                      row.provider, row.pkey, title,
                                      withdrawn=row.state == "withdrawn")
            self.budget.add(now, needed)
            self.sent_pages += 1
            self.day_pages += 1
            self._done("withdrawn" if row.state == "withdrawn" else "ok")
            self._after_send(row, int(now))
            bursts = self._bursts(len(frames))
            log.info("gesendet: Seite %s rev %s (%s Frames in %s Aussendung%s, %.1f s)%s",
                     row.id, row.rev, len(frames), bursts, "en" if bursts > 1 else "", needed,
                     " [zurückgezogen]" if row.state == "withdrawn" else "")

        nxt = self.store.next_due()
        if self.beacon_build is not None and self.beacon_interval_s > 0:
            nxt = self.beacon_next if nxt is None else min(nxt, self.beacon_next)
        if nxt is None:
            return MAX_SLEEP
        return min(max(nxt - self.clock(), 0.5), MAX_SLEEP)

    def _bursts(self, frames: int) -> int:
        limit = self.cfg.burst_frames
        return -(-frames // limit) if limit > 0 else 1

    def _count_frame(self) -> None:
        day = time.strftime("%Y-%m-%d", time.localtime(self.clock()))
        if day != self.day:
            self.day, self.day_pages, self.day_frames = day, 0, 0
        self.day_frames += 1

    def _done(self, result: str) -> None:
        """The page in self.current is through (ok / withdrawn) or broken off (paused)."""
        cur = self.current
        if cur is None:
            return
        self.recent.appendleft({"t": cur["handed"] or cur["started"], "id": cur["id"],
                                "title": cur["title"], "typ": cur["typ"], "pri": cur["pri"],
                                "sent": cur["sent"], "total": cur["total"], "air": cur["air"],
                                "result": result})
        self.current = None

    def tx_state(self) -> dict:
        """For the web GUI (view "Sendung"): on the air, waiting, last sent, budget."""
        now = self.clock()
        cur = dict(self.current) if self.current else None
        if cur is not None:
            # still on the air: what is not handed over yet, plus (AGW) what Direwolf holds
            left = max(cur["air"] - cur["air_done"], 0.0)
            if self.queue_len is not None and self.last_queue:
                left += self.last_queue * (cur["air_done"] / max(cur["sent"], 1))
            cur["left_s"] = round(left, 1)
        blocked = self.blocked
        if blocked and blocked.get("until", 0) < now - 30:
            blocked = None                                  # long gone
        nxt = []
        for row in self.store.upcoming(8):
            typ, title = title_of(row.content)
            n = self.store.frame_count(row.pid)
            nxt.append({"id": row.id, "title": title, "typ": typ, "pri": row.pri,
                        "provider": row.provider, "key": row.pkey,
                        "parts": n, "next_tx": None if row.next_tx >= RESTING else row.next_tx,
                        "resting": row.next_tx >= RESTING, "withdrawn": row.state == "withdrawn",
                        "withdraw_left": row.withdraw_left,
                        "withdraw_of": self.cfg.withdraw_repeats,
                        "new": row.tx_count == 0})
        b = self.budget
        if self.day != time.strftime("%Y-%m-%d", time.localtime(now)):
            self.day, self.day_pages, self.day_frames = "", 0, 0
        return {"now": now, "current": cur, "blocked": blocked, "next": nxt,
                "recent": list(self.recent), "queue": self.last_queue,
                "agw": self.queue_len is not None,
                "budget": {"used_s": round(b.spent(now), 1), "limit_s": round(b.limit, 1),
                           "percent": self.cfg.airtime_percent,
                           "window_min": self.cfg.airtime_window_min},
                "gap_s": self.cfg.burst_gap_s, "burst_frames": self.cfg.burst_frames,
                "beacon": None if self.beacon_build is None or self.beacon_interval_s <= 0 else
                {"interval_min": round(self.beacon_interval_s / 60), "next": self.beacon_next,
                 "text": self.beacon_text},
                "today": {"pages": self.day_pages, "frames": self.day_frames}}

    def _after_send(self, row: PageRow, now: int) -> None:
        sends_done = row.tx_count + 1
        if row.state == "withdrawn":
            left = row.withdraw_left - 1
            if left <= 0:
                self.store.delete_page(row.pid)
                return
            # withdrawals are repeated quickly, at the first regular gap
            gap = self.cfg.repeat_minutes[1] if len(self.cfg.repeat_minutes) > 1 else 1
            self.store.mark_sent(row.pid, now, now + 60 * max(gap, 1), left)
            return
        own = self.schedules.get((row.provider, row.pkey))
        if own is not None:                            # eigener Takt (Dictionary-Daten)
            minutes = own(sends_done)
        else:
            minutes = self.gap_min(sends_done, max(now - (row.rev_t or row.t), 0))
        if minutes <= 0:                               # ruht, bis eine neue Revision kommt
            self.store.mark_sent(row.pid, now, RESTING)
            log.info("Seite %s ruht (Revision älter als %s h)", row.id,
                     self.cfg.aging[-1][0] if self.cfg.aging else "?")
            return
        self.store.mark_sent(row.pid, now, now + 60 * minutes)
