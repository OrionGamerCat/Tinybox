"""Who is on the other end (CR76) and what two TBClients do together (CR78).

CR76 - right after an outgoing connect the client sends one line to whatever
station it reached:

    //TB? CLIENT v=<version> caps=PROF,HEARD

    TinyBox     -> //TB BOX v=<release> call=<mailbox>   (session unchanged)
    TBClient    -> //TB CLIENT v=<version> caps=PROF,HEARD
    any other   -> nothing, or "unknown command" - the channel is a terminal

A TinyBox then gets the //CLIENT handshake if no other TinyBox is in client
mode (CR45: one at a time), else the channel stays a terminal. An older
TinyBox without //TB? is still found by its "Welcome to TinyBox" line.

CR78 - two TBClients ("peers") are both terminals, with a few extras on top.
Their lines start with // and never show up as text in the terminal:

    //PROF loc=.. home=.. name=..   own profile, sent once after the //TB lines
                                    (if both know PROF and it is not empty)
    //HEARD?                        "who do you hear?" (button in the terminal)
    //HEARD <call>=<min> ...        answer: up to 10 stations, minutes ago
                                    ("//HEARD -" = nobody)

The other side's version is compared with the own one: a newer client over
there is mentioned in the terminal.

Chat history (peerchat.py) - both sides know HIST:

    //HIST g=<gen> m=<n>:<hash> y=<n>:<hash>   right after the start: generation,
                                    my sent stream (m) and my received stream (y)
    //HM <n> <unix> <text>          a line of mine the other side is missing (lost
                                    at the last disconnect), sent again
    //HIST CLR g=<gen>              the histories differ: both delete, new generation
    //HIST DEL g=<gen>              the other one deleted its history (button):
                                    delete too, note "chat history removed"

Each side checks only its own sent stream against what the other reports (the
sender has the whole chain); a different generation means: both delete.

Link quality: no lines on the air. Each side has the counters of its own link
(Direwolf fork 'Q' over AGW, the own AX.25 over KISS/AXUDP) - they give both
directions (prcore/linkq.py), polled every 30 s by the core.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from prcore import aprs, linkq
from prcore import profile as pf

from .peerchat import new_gen

from . import VERSION

if TYPE_CHECKING:
    from .channels import Channel

PEER_CAPS = ("PROF", "HEARD", "HIST")
HEARD_MAX = 10              # stations in one //HEARD line
RESEND_MAX = 10             # lines sent again at most (//HM); more missing = both delete


def probe_line() -> str:
    return f"//TB? CLIENT v={VERSION} caps={','.join(PEER_CAPS)}"


def answer_line() -> str:
    return f"//TB CLIENT v={VERSION} caps={','.join(PEER_CAPS)}"


def _args(text: str) -> dict[str, str]:
    out = {}
    for part in text.split():
        key, eq, value = part.partition("=")
        if eq:
            out[key.lower()] = value
    return out


def version_key(v: str) -> tuple:
    return tuple(int(x) if x.isdigit() else 0 for x in v.split("."))


class Peer:
    """The TBClient on the other end of one channel."""

    def __init__(self, ch: "Channel", args: str) -> None:
        a = _args(args)
        self.ch = ch
        self.version = a.get("v", "")[:20]
        self.caps = {c.strip().upper() for c in a.get("caps", "").split(",") if c.strip()}
        self.prof: dict | None = None
        self.heard: list[tuple[str, int]] | None = None   # (call, minutes ago)
        self.heard_at = 0
        self.asked = False
        self.quality = linkq.LinkQuality()
        self.q_at = 0                       # last counters (time), 0 = none yet
        self.q_none = False                 # the link gives no counters (Direwolf without fork)
        self._snap: tuple[int, str] | None = None   # own sent stream when //HIST went out

    @property
    def newer(self) -> bool:
        return version_key(self.version) > version_key(VERSION)

    def start(self) -> None:
        """Both sides know each other: tell it, send the own profile."""
        ch = self.ch
        ch.term_line("sys", f"*** {ch.target}: TBClient {self.version or '?'}")
        ch.core.console.append(f"[{ch.n}] *** {ch.target}: TBClient {self.version}")
        if self.newer:
            ch.term_line("sys", f"*** {ch.target} runs a newer tbclient ({self.version}, "
                                f"here {VERSION})")
        mine = ch.core.profiles.mine
        if "PROF" in self.caps and ch.core.settings.get("profile") is not None \
                and not pf.empty(mine):
            self._send(f"//PROF {pf.encode(mine, with_time=False)}")
        if self.hist:
            self._snap = self.store.state(self.call)["tx"]
            self._send(self.store.hist_line(self.call))

    # --- chat history (peerchat.py) --------------------------------------------------

    @property
    def hist(self) -> bool:
        return "HIST" in self.caps and self.ch.core.peerchat is not None

    @property
    def store(self):
        return self.ch.core.peerchat

    @property
    def call(self) -> str:
        return self.ch.target.upper()

    def text(self, direction: str, text: str) -> None:
        """A chat line typed here (tx) or from the other side (rx)."""
        text = text.rstrip()
        if self.hist and text:
            self.store.add(self.call, direction, text)

    def clear_history(self) -> None:
        """The button: delete here, the other side deletes too (now or at the next connect)."""
        gen = new_gen()
        self.store.clear(self.call, gen)
        self.store.note(self.call, "chat history removed")
        if self.ch.state == "online" and self.hist:
            self._send(f"//HIST DEL g={gen}")
        self.ch.core._touch()

    def _on_hist(self, rest: str) -> None:
        word, _, more = rest.partition(" ")
        a = _args(rest)
        gen = a.get("g", "")
        if not self.hist or not gen:
            return
        if word.upper() in ("CLR", "DEL"):
            self.store.clear(self.call, gen)
            self.store.note(self.call, "chat history removed" + (
                f" by {self.ch.target}" if word.upper() == "DEL" else " (not the same on both sides)"))
            return
        mine = self.store.state(self.call)
        if gen != mine["gen"]:                   # deleted on one side, or never the same
            had = self.store.clear(self.call, max(gen, mine["gen"]))
            if had:
                self.store.note(self.call, "chat history removed (not the same on both sides)")
            return
        try:                                     # y = what they received of mine
            yn, yh = a.get("y", "0:0").split(":", 1)
            yn = int(yn)
        except ValueError:
            return
        snap_n = (self._snap or mine["tx"])[0]
        here = self.store.chain_at(self.call, "tx", yn)
        if yn >= snap_n:
            ok = here == yh                      # the same (or they got lines sent since)
            missing = []
        else:
            ok = here == yh and snap_n - yn <= RESEND_MAX
            missing = self.store.since(self.call, "tx", yn, snap_n) if ok else []
            ok = ok and len(missing) == snap_n - yn
        if not ok:
            gen = new_gen()
            self.store.clear(self.call, gen)
            self.store.note(self.call, "chat history removed (not the same on both sides)")
            self._send(f"//HIST CLR g={gen}")
            return
        for n, t, text in missing:               # lost at the last disconnect: again
            self._send(f"//HM {n} {t} {text}")

    def _on_hm(self, rest: str) -> None:
        """//HM <n> <unix> <text>: a line of theirs that did not arrive last time."""
        parts = rest.split(" ", 2)
        if not self.hist or len(parts) < 3 or not parts[0].isdigit() or not parts[1].isdigit():
            return
        if int(parts[0]) == self.store.state(self.call)["rx"][0] + 1:
            self.store.add(self.call, "rx", parts[2].rstrip(), int(parts[1]))
            self.ch.term_line("sys", f"*** delivered again: {parts[2]}")

    # --- link quality (no lines on the air) -----------------------------------------

    def add_counters(self, counters: dict | None, now: float) -> None:
        if counters is None:
            self.q_none = self.q_at == 0
            return
        self.q_none = False
        self.q_at = now
        self.quality.add(counters, now)

    def quality_summary(self, now: float) -> dict | None:
        if self.q_at == 0:
            return {"none": self.q_none}
        r = self.quality.evaluate(now)
        if r is None:
            return {"none": False}
        last = self.quality.last or {}
        busy = last.get("tx_busy_ms", 0)
        steps = self.quality.cfg.steps

        def side(d):
            return {"frames": d.frames, "lost": d.lost, "loss": d.loss, "bars": d.bars(steps),
                    "tent": d.frames > 0 and not d.enough}   # few frames: repeats count
        return {"bars": r.bars, "tentative": r.tentative, "out": side(r.out), "in": side(r.inn),
                "t1": r.t1, "rej_rx": r.rej_rx, "rej_tx": r.rej_tx, "srt": r.srt,
                "rate": round(last.get("bytes_new", 0) * 1000 / busy) if busy else None,
                "age": round(now - self.q_at)}

    def _send(self, line: str) -> None:
        self.ch.core.console.append(f"[{self.ch.n}]> {line}")
        self.ch.link.send_line(line)

    def take(self, line: str) -> bool:
        """A // line from the peer: True = handled (not shown as text)."""
        word, _, rest = line[2:].partition(" ")
        word = word.upper()
        if word == "PROF":
            self._on_prof(rest)
        elif word == "HEARD?":
            self._send(self._heard_line())
        elif word == "HEARD":
            self._on_heard(rest)
        elif word == "HIST":
            self._on_hist(rest)
        elif word == "HM":
            self._on_hm(rest)
        else:
            return False
        self.ch.core._touch()
        return True

    # --- profile ---------------------------------------------------------------------

    def _on_prof(self, text: str) -> None:
        p = pf.decode(text)
        try:
            checked = pf.check(p["name"], p["loc"], p["home"])
        except pf.ProfileError:
            return
        self.prof = checked
        cache = self.ch.core.settings.setdefault("profiles", {})   # as //WI (CR73)
        cache[self.ch.target.upper().split("-", 1)[0]] = {"at": int(time.time()), **checked}
        self.ch.core._save_settings()
        row = self.profile_row()
        text = ", ".join(x for x in (row.get("name"), row.get("loc"),
                                      f"{row['km']} km {_dir(row['deg'])}" if "km" in row else "",
                                      f"home BBS {row['home']}" if row.get("home") else "") if x)
        self.ch.term_line("sys", f"*** {self.ch.target}: {text}")

    def profile_row(self) -> dict:
        if not self.prof:
            return {}
        row = dict(self.prof)
        mine = self.ch.core.profiles.mine
        here = aprs.locator_to_latlon(mine["loc"] or self.ch.core.cfg.locator or "")
        there = aprs.locator_to_latlon(row["loc"]) if row.get("loc") else None
        if here and there:
            km, deg = aprs.distance_bearing(here, there)
            row["km"], row["deg"] = round(km), round(deg)
        return row

    # --- heard list ------------------------------------------------------------------

    def ask_heard(self) -> bool:
        if "HEARD" not in self.caps or self.ch.state != "online":
            return False
        self.asked = True
        self._send("//HEARD?")
        self.ch.term_line("sys", f"*** asking {self.ch.target} who it hears ...")
        self.ch.core._touch()
        return True

    def _heard_line(self) -> str:
        now = time.time()
        core = self.ch.core
        skip = {self.ch.target, core.cfg.mycall}
        calls = sorted(((c, t) for c, t in core.heard_at.items() if c not in skip),
                       key=lambda ct: -ct[1])[:HEARD_MAX]
        if not calls:
            return "//HEARD -"
        return "//HEARD " + " ".join(f"{c}={int((now - t) // 60)}" for c, t in calls)

    def _on_heard(self, text: str) -> None:
        heard = []
        for part in text.split():
            call, eq, mins = part.partition("=")
            if eq and mins.isdigit():
                heard.append((call.upper()[:9], int(mins)))
        self.heard, self.heard_at = heard, int(time.time())
        if heard:
            self.ch.term_line("sys", f"*** {self.ch.target} hears: " + ", ".join(
                f"{c} ({m} min)" if m else f"{c} (now)" for c, m in heard))
        else:
            self.ch.term_line("sys", f"*** {self.ch.target} has heard nobody yet")

    # --- for the GUI ------------------------------------------------------------------

    def summary(self, now: float) -> dict:
        return {"v": self.version, "newer": self.newer, "caps": sorted(self.caps),
                "prof": self.profile_row(), "heard": self.heard, "heard_at": self.heard_at,
                "hist": self.hist, "q": self.quality_summary(now)}


def _dir(deg: float) -> str:
    return ["N", "NE", "E", "SE", "S", "SW", "W", "NW"][round((deg % 360) / 45) % 8]
