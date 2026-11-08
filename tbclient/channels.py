"""Channels of the client (CR45): up to max_channels (tbclient.conf, 1 ... 10) connections at once, one window each,
shown one at a time. A channel owns one link and its life: state, how it ended,
the terminal lines, the logbook row. At most one channel talks to a TinyBox in
client mode - the chat channel (ClientCore.chan); every other channel is a
terminal (CR43). A channel 0 does not exist: the monitor lives in the core."""

from __future__ import annotations

import asyncio
import logging
import time
from collections import deque
from typing import TYPE_CHECKING

from . import peer as peer_mod
from .target import label as target_label

if TYPE_CHECKING:
    from .core import ClientCore

log = logging.getLogger(__name__)

TERM_MAX = 500            # CR43: lines kept per channel for the terminal view
TERM_SNAPSHOT = 300       # ... and sent to the GUI
DISC_TIMEOUT_SEC = 90     # CR42: "disconnecting" without an answer: offline anyway


def utc_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


class Channel:
    def __init__(self, core: "ClientCore", n: int, link) -> None:
        self.core = core
        self.n = n                  # 1..5; 0 = the placeholder "no chat channel"
        self.link = link
        link.on_state = self._on_state
        link.on_line = self._on_line
        self.target = ""
        self.via: list[str] = []                  # CR71: digipeater path of the connection
        self.state = "offline"
        self.state_at = time.time()
        self.reason = ""
        self.ended: dict | None = None            # how the last connection ended (CR42)
        # "tinybox" (client protocol, the chat channel) | "terminal" | "" = not known yet
        self.mode = ""
        self.view = "term"                        # "chat" once it was the chat channel
        self.term: deque[tuple[int, str, str]] = deque(maxlen=TERM_MAX)  # (n, rx|tx|sys, text)
        self.term_n = 0
        self.act_n = 0                            # activity: the GUI blinks the chip on change
        self.auto = False                         # opened by the mail sync: gone when offline
        self.incoming = False                     # the other station connected to us (CR46)
        self.outstanding: int | None = None       # frames waiting in Direwolf (AGW 'Y')
        self._user_disc = False
        self._disc_timer: asyncio.TimerHandle | None = None
        self._detect_task: asyncio.Task | None = None
        self.probed = False                       # CR76: //TB? sent on this connection
        self.peer: peer_mod.Peer | None = None    # CR78: the other side is a TBClient
        self._t0 = 0.0
        self._start = ""

    # --- actions -----------------------------------------------------------------

    @property
    def label(self) -> str:
        """'OE3XYZ-1' or 'OE3XYZ-1 via OE3XTC-5' (CR71)."""
        return target_label(self.target, self.via)

    def set_link(self, link) -> None:
        """PLANUNG 25: another way for the next connection (AXUDP or radio)."""
        self.link = link
        link.on_state = self._on_state
        link.on_line = self._on_line

    async def connect(self, target: str, via: list[str] | None = None) -> None:
        self.core.relink(self, target, via)
        self.target = target
        self.via = list(via or [])
        self.link.target = target
        self.link.via = list(self.via)
        self._user_disc = False
        self.incoming = False
        await self.link.connect()

    def disconnect(self) -> None:
        if self.state in ("offline", "disconnecting"):
            return
        self._user_disc = True
        self.link.disconnect()

    def send_raw(self, text: str) -> bool:
        """A line typed in the terminal: goes out as it is (an empty line too)."""
        if self.state != "online":
            return False
        text = text.replace("\r", " ").replace("\n", " ")[:250]
        self.term_line("tx", text)
        if self.peer is not None and not text.startswith("//"):
            self.peer.text("tx", text)                  # CR78: the chat history
        if self.core.chan is self:
            self.core._send(text)             # an image upload may hold lines back
        else:
            self.core.console.append(f"[{self.n}]> {text}")
            self.link.send_line(text)
        self.core._touch()
        return True

    def term_line(self, kind: str, text: str) -> None:
        self.term_n += 1
        self.term.append((self.term_n, kind, text))
        if kind == "rx":
            self.act_n += 1

    # --- link callbacks ---------------------------------------------------------------

    def _on_state(self, state: str, reason: str) -> None:
        prev = self.state
        self.state, self.reason = state, reason
        self.state_at = time.time()
        if self._disc_timer is not None:
            self._disc_timer.cancel()
            self._disc_timer = None
        if state == "connecting":
            self.ended = None
            self.mode = ""
            self.probed, self.peer = False, None
            self._mark()
        if state == "online" and prev != "online":
            self._mark()                           # the connection counts from here
            if self.link.kind == "telnet":         # the test port is always the own TinyBox
                self.core.attach(self)
            elif self.incoming:                     # they called us: a terminal (CR46)
                self.probed, self.peer = False, None
                self.ended = None
                self._terminal()
                self.act_n += 1                     # the chip blinks
                self.core.focus_channel(self.n)      # CR75: the GUI shows it at once
            else:
                self._probe()                       # CR76: who is there?
                self._detect_task = asyncio.ensure_future(self._detect())
        if state == "disconnecting":
            self._disc_timer = asyncio.get_event_loop().call_later(
                DISC_TIMEOUT_SEC, self.link.drop, "no answer to the disconnect")
        if state == "offline":
            # CR42: how it ended - by us, never came up, or by the other side
            kind = "user" if self._user_disc else "failed" if prev == "connecting" else "remote"
            self.ended = {"kind": kind, "at": int(time.time()), "call": self.target}
            self._user_disc = False
            self.outstanding = None
            if self._detect_task:
                self._detect_task.cancel()
            if prev != "offline":
                self._log(prev, kind)
        who = self.label if state == "connecting" else self.target   # CR71: path once
        self.term_line("sys", f"*** {state} {who}" + (f" ({reason})" if reason else ""))
        if self.core.chan is self:
            self.core._chat_state(state, prev, reason)
        else:
            self.core.console.append(f"[{self.n}] *** {state} {who}"
                                     + (f" ({reason})" if reason else ""))
        if state == "offline" and self.auto:     # the sync's own connection: away again
            self.core.drop_channel(self)
        self.core._touch()

    def _on_line(self, line: str) -> None:
        if self.core.chan is self and self.mode == "tinybox":
            self.core._on_line(line)               # the chat engine
            return
        line = line.rstrip()
        if self.probed and not self.incoming and not line.startswith("//") \
                and (i := line.find(" //TB ")) >= 0:
            # an older TinyBox: the answer right behind the prompt "... > "
            self.term_line("rx", line[:i])
            line = line[i + 1:]
        if line.startswith("//") and self._tb_line(line):
            self.core._touch()
            return
        if self.mode == "" and line.startswith("Welcome to TinyBox"):
            if self.core.can_attach(self):
                self.core.attach(self, line)    # the chat engine puts it into the terminal
                return
            self.mode = "terminal"              # only one TinyBox in client mode (CR45)
        # CR43: not (yet) a TinyBox in client mode: every line goes to the terminal
        self.term_line("rx", line)
        if self.peer is not None:
            self.peer.text("rx", line)                  # CR78: the chat history
        if line:
            self.core.console.append(f"[{self.n}] {line}")
        self.core._touch()

    async def _detect(self) -> None:
        """No "Welcome to TinyBox" seen: a TinyBox we know gets the handshake
        anyway (the line may have been missed); any other station is not
        bothered with //CLIENT - the channel is a terminal (CR43)."""
        from . import core as core_mod          # tests change the delay there
        await asyncio.sleep(core_mod.HANDSHAKE_FALLBACK_SEC)
        if self.state != "online" or self.mode:
            return
        if self.core.known_tinybox(self.target) and self.core.can_attach(self):
            self.core.attach(self, handshake=True)
        else:
            self.to_terminal()

    # --- CR76: who is there / CR78: TBClient to TBClient ------------------------------

    def _probe(self) -> None:
        line = peer_mod.probe_line()
        self.probed = True
        self.term_line("tx", line)
        self.core.console.append(f"[{self.n}]> {line}")
        self.link.send_line(line)

    def _tb_line(self, line: str) -> bool:
        """A // line on a channel that is no TinyBox in client mode (yet).
        True = handled, not shown as text."""
        word, _, rest = line[2:].partition(" ")
        word = word.upper()
        if word == "TB?" and self.incoming:          # a TBClient called us
            self.link.send_line(peer_mod.answer_line())
            self.core.console.append(f"[{self.n}]> {peer_mod.answer_line()}")
            kind, _, args = rest.partition(" ")
            if kind.upper() == "CLIENT" and self.peer is None:
                self._terminal()
                self.peer = peer_mod.Peer(self, args)
                self.peer.start()
            return True
        if word == "TB" and self.probed and not self.incoming:
            kind, _, args = rest.partition(" ")
            kind = kind.upper()
            if kind == "BOX" and self.mode in ("", "terminal"):
                self._found_box()
                return True
            if kind == "CLIENT" and self.peer is None:
                if self._detect_task:
                    self._detect_task.cancel()
                self._terminal()
                self.peer = peer_mod.Peer(self, args)
                self.peer.start()
                return True
            return False
        if self.peer is not None:
            return self.peer.take(line)
        return False

    def _found_box(self) -> None:
        """//TB BOX: a TinyBox. Client mode if no other TinyBox has it (CR45)."""
        if self._detect_task:
            self._detect_task.cancel()
        if self.core.can_attach(self):
            self.term_line("sys", f"*** {self.target}: TinyBox")
            self.core.attach(self, handshake=True)
        else:
            self._terminal()
            self.term_line("sys", f"*** {self.target}: TinyBox - terminal, the chat "
                                  f"channel is busy with another one")
            self.core.console.append(f"[{self.n}] *** {self.target}: TinyBox, terminal")

    def _terminal(self) -> None:
        """This channel is a terminal. Was it the chat channel of an earlier
        connection (same channel number, the TinyBox went away), it is none any
        more - else the GUI shows the chat without an input (CR78 fix)."""
        self.mode, self.view = "terminal", "term"
        if self.core.chan is self:
            self.core.detach()

    def ask_heard(self) -> bool:
        return self.peer is not None and self.peer.ask_heard()

    def to_terminal(self) -> None:
        self.mode = "terminal"
        self.core.console.append(f"[{self.n}] *** {self.target}: terminal")
        if self.core.chan is self:
            self.core.detach()
        self.core._touch()

    # --- logbook (CR44) ------------------------------------------------------------------

    def _mark(self) -> None:
        self._t0 = time.monotonic()
        self._start = utc_iso()

    def _log(self, prev: str, kind: str) -> None:
        """One row per connection; one that never came up as "failed" (duration 0)."""
        failed = prev == "connecting"
        try:
            self.core.logbook.add({
                "call": self.target, "via": self.link.kind, "start": self._start or utc_iso(),
                "end": utc_iso(), "secs": 0 if failed else int(time.monotonic() - self._t0),
                "rx": None if failed else self.link.rx_bytes,
                "tx": None if failed else self.link.tx_bytes,
                "ended": ("cancelled" if kind == "user" else "failed") if failed else kind,
                "freq": self.core.freq})
        except Exception:                    # the logbook must never break the client
            log.exception("connection log: row not written")

    # --- for the GUI ------------------------------------------------------------------

    def summary(self, now: float) -> dict:
        return {"n": self.n, "target": self.target, "via": self.via, "label": self.label,
                "link": self.link.kind,                       # PLANUNG 25: axudp | agw | kiss ...
                "state": self.state, "reason": self.reason,
                "state_age": round(now - self.state_at, 1), "ended": self.ended,
                "mode": self.mode, "view": self.view, "chat": self.core.chan is self,
                "act": self.act_n, "term_n": self.term_n, "outstanding": self.outstanding,
                "peer": self.peer.summary(time.monotonic()) if self.peer is not None else None}
