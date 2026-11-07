"""Client logic: connection, handshake, chat state. The web GUI reads
snapshot() and calls the actions (connect, join, say, react ...)."""

from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from collections import deque

from prcore import aprs                  # APRS in plain language for the monitor (CR55)
from prcore.aprsstats import AprsStats    # CR61
from prcore import chatimg               # the image reference in a chat line (CR12)
from prcore.agw import PID_NO_L3, via_data
from prcore.ax25.frame import AX25Error, split_call
from prcore.ax25.frame import ui_frame as ax25_ui_frame

from . import VERSION, proto
from . import target as tgt
from .config import CALL_RE, Config
from .images import Images, ImageStore
from .channels import TERM_SNAPSHOT, Channel
from .kisslink import AxudpPort, KissLink, KissPort
from .links import AgwLink, AgwPort, TelnetLink
from .logbook import Logbook
from .mailstore import MailStore
from .peerchat import PeerChat
from .profiles import Profiles
from .radio import RawFrame, aprs_symbol, guess_mod128, monitor_entry
from .sync import Syncer

log = logging.getLogger(__name__)

PROTO = "TB1"
HANDSHAKE_FALLBACK_SEC = 6
LOGIN_SYNC_SEC = 1.5      # CR40: the sync after the login starts this much after //OK
DIRECT_VALID_SEC = 30 * 60
MAX_MESSAGES = 300
MAX_GAP = 32
RECENT_MAX = 10           # CR42: targets remembered for the "Connect to" field
MONITOR_MAX = 500         # CR45: frames kept for the monitor (channel 0)
OUTSTANDING_SEC = 3       # CR45: how often the send queues of the channels are asked
PEER_Q_SEC = 30           # CR78: how often the link counters of a TBClient channel are read
SYMBOL_RE = re.compile(r"^[/\\0-9A-Z][!-~]$")
UI_MAX_BYTES = 1024       # CR66: info field of a UI frame from the monitor
UI_MAX_VIA = 8            # AX.25 allows 8 digipeaters


def ui_request(dest: str, via: str, text: str) -> tuple[str, list[str], bytes]:
    """CR66: check what the monitor's UI form sent -> (dest, path, info).
    Raises ValueError with a short reason for the GUI."""
    def call(c: str) -> str:
        try:
            base, ssid = split_call(c)
        except AX25Error:
            raise ValueError(f"not a callsign: {c.strip() or '(empty)'}") from None
        return f"{base}-{ssid}" if ssid else base

    dest = call(dest or "CQ")
    path = [call(c) for c in re.split(r"[\s,]+", via or "") if c]
    if len(path) > UI_MAX_VIA:
        raise ValueError(f"at most {UI_MAX_VIA} digipeaters")
    info = (text or "").encode("utf-8")
    if not info:
        raise ValueError("no text")
    if len(info) > UI_MAX_BYTES:
        raise ValueError(f"text longer than {UI_MAX_BYTES} bytes")
    return dest, path, info


class ClientCore:
    def __init__(self, cfg: Config) -> None:
        self.cfg = cfg
        self.settings_path = cfg.data_dir / "settings.json"
        self.settings = self._load_settings()
        self.release_info: dict | None = None     # newer release on GitHub (PLANUNG 24)
        # CR42: free target. home = the TinyBox of tbclient.conf, the mailbox belongs to it
        self.home = cfg.tinybox_call
        # CR45: up to 5 channels over one AGW port (telnet: one channel). chan is
        # the chat channel - the one TinyBox in client mode; without one it is
        # the placeholder channel 0, always offline.
        self.port = (AgwPort(cfg, self._on_frame, self._incoming) if cfg.link == "agw"
                     else KissPort(cfg, self._on_frame, self._incoming) if cfg.link == "kiss"
                     else None)
        # PLANUNG 25: the home TinyBox over AXUDP, the radio for everything else
        self.udp = AxudpPort(cfg, lambda remote: self._incoming(remote, udp=True)) \
            if cfg.axudp_host and self.port is not None else None
        self.channels: dict[int, Channel] = {}
        self.nochat = Channel(self, 0, self._new_link())
        last = self.settings.get("target", "")
        first = self.open_channel(1)
        first.target = last if CALL_RE.match(last or "") and last != cfg.mycall else self.home
        self.chan: Channel = first
        self.monitor: deque[tuple[int, str]] = deque(maxlen=MONITOR_MAX)   # (n, line)
        self.monitor_n = 0
        self._mod128: set[frozenset] = set()      # pairs that talk modulo 128 (monitor)
        self.aprs_memory = aprs.TelemetryMemory()  # CR55: telemetry definitions per station
        self.aprs_home = aprs.locator_to_latlon(cfg.locator) if cfg.locator else None
        self.aprs_stats = AprsStats(cfg.data_dir / "aprsstats.db", self.aprs_home)   # CR61
        # CR44: connection logbook
        self.logbook = Logbook(cfg.data_dir / "connlog.db")
        try:                                      # CR78: chat history with other TBClients
            self.peerchat: PeerChat | None = PeerChat(cfg.data_dir / "peerchat.db")
        except Exception:
            log.exception("peerchat.db: no chat history with other clients")
            self.peerchat = None
        # the frequency is asked once per run of the client (the last one is offered)
        self.freq = ""
        self.freq_asked = False
        self.caps: set[str] = set()
        self.handshake_done = False
        self.boards: list[dict] = []
        self._boards_tmp: list[dict] | None = None
        self.board: dict | None = None
        self.members: dict[str, str] = {}         # call -> symbol sent with the join
        self.numbers: dict[int, str] = {}         # member number -> call (CR33)
        self.quality: dict[str, int | None] = {}  # call -> bars 0..5 (None = no result yet)
        self.linkq: dict[str, dict] = {}          # call -> numbers behind the bars (%Q, CR33)
        self.qcfg: dict = {}                      # how the TinyBox makes bars (q= in //OK)
        self.messages: list[dict] = []
        self.pending: list[dict] = []
        self.pending_reacts: dict[tuple[int, str], float] = {}   # own reactions not echoed yet
        self.console: deque[str] = deque(maxlen=200)
        self.uploads: dict[str, dict] = {}        # call -> {size, at}: picture on its way (CR30)
        self.heard: dict[str, str] = {}           # call -> APRS symbol from a beacon
        self.heard_at: dict[str, float] = {}      # call -> last frame heard (any kind)
        self.mail: dict | None = None             # {"count": n, "at": unix} - C1 notice
        self.sysmsg: dict | None = None           # system message (shutdown) from the TinyBox
        # CR75: a station connected to us - the GUI switches to its terminal
        self.focus = {"n": 0, "seq": 0}
        self.direct_at: dict[str, float] = {}     # call -> last frame heard directly
        self.channel_busy_at = 0.0                # last frame not between us and the TinyBox
        self.unwrap = proto.Unwrapper()
        self.seen: set[int] = set()
        self._hist_buf: list[tuple[int, str, str]] | None = None   # //H lines of a //HIST
        self._hist_older = False                  # the running //HIST asks for older lines
        self._hist_lo = self._hist_hi = 0         # orders history lines of the same second
        self._hist_keys: set[tuple] = set()       # (time, call, text) already shown
        self.clock_off = 0                        # TinyBox time - own time (from //IN now=)
        self.version = 0
        self._changed = asyncio.Event()
        self._hs_task: asyncio.Task | None = None
        # UI frames are sent at once, I-frames wait in a queue: the UI frame of
        # our own join can overtake the //IN line. Keep such events until //IN.
        self._joining: int | None = None
        self._early: list[proto.Event] = []
        # lines held back while image bytes go out as one raw block (CR12)
        self._hold: list[str] | None = None
        # offline mailbox (C3)
        self.mailbox = MailStore(cfg.data_dir / "mailbox.db", cfg.mycall)
        self.sync = Syncer(self, self.mailbox)
        # small images in the chat (CR12)
        self.images = Images(self, ImageStore(cfg.data_dir / "images"))
        self.images.store.purge()
        # name, locator, home BBS - own and of the others (CR73)
        self.profiles = Profiles(self)

    # --- settings --------------------------------------------------------

    def _load_settings(self) -> dict:
        try:
            return json.loads(self.settings_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}

    @property
    def tset(self) -> dict:
        """Settings that belong to the TinyBox of the connection (last board,
        seen, MOTD): the home TinyBox keeps them at the top level as before."""
        if self.target == self.home:
            return self.settings
        return self.settings.setdefault("targets", {}).setdefault(self.target, {})

    def _save_settings(self) -> None:
        self.settings_path.parent.mkdir(parents=True, exist_ok=True)
        self.settings_path.write_text(json.dumps(self.settings, indent=1), encoding="utf-8")

    # --- newer client version (CR18) ---------------------------------------------

    @staticmethod
    def version_key(v: str) -> tuple[int, ...]:
        return tuple(int(p) for p in re.findall(r"\d+", v or ""))

    def _update_info(self, ok_line: str) -> None:
        """//OK ... cur=<newest version> news=<feature bulletin>: remember it, so
        the hint stays after disconnecting. A TinyBox without cur= means: up to date."""
        cur = re.search(r"\bcur=(\S+)", ok_line)
        news = re.search(r"\bnews=(\d+)", ok_line)
        info = None
        if cur and self.version_key(cur.group(1)) > self.version_key(VERSION):
            info = {"cur": cur.group(1), "news": int(news.group(1)) if news else None}
            self.console.append(f"*** newer client available: {info['cur']} (this is {VERSION})")
        if info != self.settings.get("update"):
            if info:
                self.settings["update"] = info
            else:
                self.settings.pop("update", None)
            self._save_settings()

    # --- new release on GitHub (PLANUNG 24) ----------------------------------------

    def on_release(self, result) -> None:
        """From prcore.release.watch(): remember the newest release; the banner
        shows it only when it is newer than the RELEASE of this installation."""
        info = result.as_dict() if result.newer else None
        if info != self.release_info:
            self.release_info = info
            if info:
                self.console.append(f"*** new TinyBox release {result.latest} on GitHub "
                                    f"(this is {result.current}): {result.url}")
            self._touch()

    @property
    def update(self) -> dict | None:
        info = self.settings.get("update")
        if info and self.version_key(info.get("cur", "")) > self.version_key(VERSION):
            return info
        return None                      # meanwhile updated

    def open_news(self) -> bool:
        """'Read about new features': fetch the rubric TBNEWS and the bulletin."""
        self.mailbox.subscribe("TBNEWS", True)
        if not self.sync.running:
            self.sync.start("bulletins")
        return True

    @property
    def my_symbol(self) -> str:
        return self.settings.get("symbol", "")

    def set_symbol(self, symbol: str) -> bool:
        if symbol and not SYMBOL_RE.match(symbol):
            return False
        self.settings["symbol"] = symbol
        self._save_settings()
        if self.state == "online" and self.caps:     # the board sees it at once (CR7)
            self._send(f"//SYM {symbol or '-'}")
        self._touch()
        return True

    # --- change notification (long poll) -------------------------------------

    def _touch(self) -> None:
        self.version += 1
        self._changed.set()
        self._changed = asyncio.Event()

    async def wait_change(self, since: int, timeout: float) -> None:
        if since != self.version:
            return
        ev = self._changed
        try:
            await asyncio.wait_for(ev.wait(), timeout)
        except asyncio.TimeoutError:
            pass

    # --- actions from the GUI -------------------------------------------------

    # --- channels (CR45) -------------------------------------------------------

    def _new_link(self):
        if isinstance(self.port, KissPort):
            return KissLink(self.port, self.cfg, None, None)
        if self.port is not None:
            return AgwLink(self.port, self.cfg, None, None)
        return TelnetLink(self.cfg, None, None)

    def _udp_link(self):
        return KissLink(self.udp, self.cfg, None, None)

    def uses_axudp(self, target: str, via: list[str] | None = None) -> bool:
        """PLANUNG 25: the home TinyBox, directly, while AXUDP is configured."""
        return self.udp is not None and target == self.home and not via

    def relink(self, ch: Channel, target: str, via: list[str] | None = None) -> None:
        """Before a connect: the channel's link fits the way to target."""
        want = self.uses_axudp(target, via)
        if want != (ch.link.kind == "axudp"):
            ch.set_link(self._udp_link() if want else self._new_link())

    def _incoming(self, remote: str, udp: bool = False):
        """CR46: somebody connected to us - the first free channel takes it as a
        terminal. None = no channel free (or that station is already connected)."""
        if any(c.target == remote and c.state != "offline" for c in self.channels.values()):
            return None
        n = self.free_channel()
        if n is None:
            return None
        ch = self.open_channel(n)
        if ch.state != "offline":
            return None
        if udp != (ch.link.kind == "axudp"):         # PLANUNG 25: over the port it came in
            ch.set_link(self._udp_link() if udp else self._new_link())
        ch.target = ch.link.target = remote
        ch.via, ch.link.via = [], []          # their path is in their frames, not ours
        ch.incoming, ch.view, ch.auto, ch._user_disc = True, "term", False, False
        self.console.append(f"[{n}] *** {remote} connected to us")
        return ch.link

    def focus_channel(self, n: int) -> None:
        """CR75: the GUI shows channel n (its terminal) at once - for an incoming
        connect of a station that is no TinyBox."""
        self.focus = {"n": n, "seq": self.focus["seq"] + 1}
        self._touch()

    def open_channel(self, n: int) -> Channel:
        ch = self.channels.get(n)
        if ch is None:
            ch = self.channels[n] = Channel(self, n, self._new_link())
        return ch

    def drop_channel(self, ch: Channel) -> None:
        """A channel goes away (closed, or the sync's own connection is over)."""
        if ch.state != "offline" or self.channels.get(ch.n) is not ch:
            return
        if len(self.channels) == 1:
            ch.auto = False                       # the last one stays as channel 1
            return
        del self.channels[ch.n]
        if self.chan is ch:
            self.chan = self.nochat

    def close_channel(self, n: int) -> bool:
        ch = self.channels.get(n)
        if ch is None or ch.state != "offline" or len(self.channels) == 1:
            return False
        self.drop_channel(ch)
        self._touch()
        return True

    def can_attach(self, ch: Channel) -> bool:
        """Only one TinyBox in client mode at a time (CR45)."""
        return self.chan is ch or self.chan.state == "offline" or self.chan.mode != "tinybox"

    def attach(self, ch: Channel, welcome: str | None = None, handshake: bool = False) -> None:
        """ch talks to a TinyBox: it becomes the chat channel."""
        if self.chan is not ch and self.chan.mode != "tinybox":
            self.chan = ch
        elif self.chan is not ch:
            self.chan = ch                        # the old chat channel is offline
        ch.mode, ch.view = "tinybox", "chat"
        self.handshake_done = False
        self.caps = set()
        if self.target != self.settings.get("target"):
            self.settings["target"] = self.target
            self._save_settings()
        if welcome is not None:
            self._on_line(welcome)                # schedules the handshake
        elif handshake:
            self._handshake()
        else:                                     # telnet: Welcome follows, else after 6 s
            self._hs_task = asyncio.ensure_future(self._handshake_fallback())
        self._touch()

    def detach(self) -> None:
        """The chat channel is no TinyBox after all (or went away)."""
        self._clear_chat()
        self.chan = self.nochat

    def known_tinybox(self, call: str) -> bool:
        return call == self.home or call in self.settings.get("tinyboxes", [])

    # the chat engine reads these from the chat channel
    @property
    def link(self):
        return self.chan.link

    @property
    def state(self) -> str:
        return self.chan.state

    @state.setter
    def state(self, value: str) -> None:          # tests and the chat engine (offline)
        self.chan.state = value

    @property
    def reason(self) -> str:
        return self.chan.reason

    @property
    def target(self) -> str:
        return self.chan.target or self.settings.get("target") or self.home

    @property
    def mode(self) -> str:
        return self.chan.mode

    @property
    def at_home(self) -> bool:
        """The chat channel is (or would be) the TinyBox the mailbox belongs to."""
        return self.target == self.home

    @property
    def recent(self) -> list[str]:
        r = [c for c in self.settings.get("recent", []) if isinstance(c, str) and tgt.valid(c)]
        return r or [self.home]

    def free_channel(self) -> int | None:
        """The first offline channel, else the first unused number."""
        for n in sorted(self.channels):
            if self.channels[n].state == "offline":
                return n
        return next((n for n in range(1, self.cfg.max_channels + 1) if n not in self.channels), None)

    async def connect(self, target: str | None = None, ch: int | None = None,
                      auto: bool = False) -> bool:
        """Connect to target in channel ch (CR45; None = the first free one).
        target None = the last station of that channel. The same station only
        once at a time. Telnet: one channel, always the own TinyBox."""
        if self.cfg.link == "telnet":
            ch, target = 1, self.home
        if ch is None:
            ch = self.free_channel()
        if ch is None or not 1 <= ch <= self.cfg.max_channels:
            return False
        chan = self.channels.get(ch)
        if chan is not None and chan.state != "offline":
            return False
        text = str(target if target is not None else
                   (chan.label if chan and chan.target else self.recent[0]))
        try:                                     # CR71: 'OE3XYZ-1 V OE3XTC-5,...'
            t, via = tgt.parse(text, self.cfg.mycall)
        except tgt.TargetError as exc:
            log.info("connect %r refused: %s", text, exc)
            return False
        if self.cfg.link == "telnet":
            via = []
        if any(c.target == t and c.state != "offline" for c in self.channels.values()):
            return False
        chan = self.open_channel(ch)
        chan.auto = auto and chan.state == "offline" and not chan.term_n
        if chan.target != t:
            chan.view = "term"                   # its window starts as a terminal
        shown = tgt.label(t, via)
        recent = [shown] + [c for c in self.settings.get("recent", [])
                            if isinstance(c, str) and c != shown]
        self.settings["recent"] = recent[:RECENT_MAX]
        self._save_settings()
        await chan.connect(t, via)
        return True

    def disconnect(self, ch: int | None = None) -> None:
        """Disconnect channel ch (None = the chat channel)."""
        chan = self.chan if ch is None else self.channels.get(ch)
        if chan is not None:
            chan.disconnect()

    def peer_clear(self, ch: int) -> bool:
        """CR78: the button "Delete history" in the TBClient view."""
        chan = self.channels.get(ch)
        if chan is None or chan.peer is None or self.peerchat is None:
            return False
        chan.peer.clear_history()
        return True

    async def _poll_peer_quality(self) -> None:
        """CR78: link counters of the channels with a TBClient (no lines on the air)."""
        while True:
            await asyncio.sleep(PEER_Q_SEC)
            changed = False
            for c in list(self.channels.values()):
                if c.peer is not None and c.state == "online":
                    try:
                        c.peer.add_counters(await c.link.counters(), time.monotonic())
                        changed = True
                    except Exception:
                        log.exception("link counters of channel %s", c.n)
            if changed:
                self._touch()

    def peer_heard(self, ch: int) -> bool:
        """CR78: ask the TBClient in channel ch whom it hears."""
        chan = self.channels.get(ch)
        return chan is not None and chan.ask_heard()

    def send_raw(self, text: str, ch: int | None = None) -> bool:
        chan = self.chan if ch is None else self.channels.get(ch)
        return chan.send_raw(text) if chan is not None else False

    def send_ui(self, dest: str, via: str, text: str) -> str | None:
        """CR66: one UI frame (unproto) from the monitor, e.g. to test a modem.
        Returns None when it went to the TNC, otherwise the reason."""
        try:
            dest, path, info = ui_request(dest, via, text)
        except ValueError as exc:
            return str(exc)
        if isinstance(self.port, KissPort):
            if not self.port.agw_up.is_set():
                return "kisshub not reachable"
            self.port.transmit(ax25_ui_frame(dest, self.cfg.mycall, info, path=path), None)
        elif isinstance(self.port, AgwPort):
            if not self.port.agw_up.is_set():
                return "Direwolf not reachable"
            if path:
                self.port.send("V", self.cfg.mycall, dest, via_data(path) + info, PID_NO_L3)
            else:
                self.port.send("M", self.cfg.mycall, dest, info, PID_NO_L3)
        else:
            return "no radio (telnet test link)"
        log.info("UI %s>%s%s: %d bytes", self.cfg.mycall, dest,
                 "," + ",".join(path) if path else "", len(info))
        return None

    async def _poll_outstanding(self) -> None:
        """CR45: frames waiting in Direwolf per channel - all channels share the
        frequency, a picture on one slows the others down (shown in the monitor)."""
        while True:
            await asyncio.sleep(OUTSTANDING_SEC)
            for c in list(self.channels.values()):
                if c.state == "online" and c.link.kind != "telnet" and c.n:
                    try:
                        c.outstanding = await c.link.outstanding()
                    except Exception:
                        c.outstanding = None

    def join(self, n: int) -> bool:
        if not self.handshake_done or not any(b["n"] == n for b in self.boards):
            return False
        self._send(f"/J {n}" if self.board else f"C {n}")
        self._joining, self._early = n, []
        return True

    # --- history on request (CR13) ---------------------------------------------

    HIST_MODES = ("missed", "none", "10", "20")
    HIST_MISSED_MAX = 20

    @property
    def history_mode(self) -> str:
        m = self.settings.get("history", "missed")
        return m if m in self.HIST_MODES else "missed"

    def set_history_mode(self, mode: str) -> bool:
        if mode not in self.HIST_MODES:
            return False
        self.settings["history"] = mode
        self._save_settings()
        self._touch()
        return True

    def _history_on_join(self, in_line: str) -> None:
        """//IN ... hist=<n> last=<unix> now=<unix>: ask for the history the way the
        user wants it. A TinyBox without hist= sends the history by itself."""
        args = dict(re.findall(r"\b(hist|last|now)=(\d+)", in_line))
        if "hist" not in args:
            return
        if "now" in args:
            self.clock_off = int(args["now"]) - int(time.time())
        count, last = int(args["hist"]), int(args.get("last", 0))
        self.board.update(hist=count, hist_last=last, older=count, loading=False)
        mode = self.history_mode
        if not count or mode == "none":
            return
        if mode == "missed":
            since = self.tset.get("seen", {}).get(self.board["name"])
            if since and last <= since:
                return                                    # nothing new since the last visit
            self._ask_history(self.HIST_MISSED_MAX, since=since)
        else:
            self._ask_history(int(mode))

    @staticmethod
    def _img_limit(in_line: str) -> int:
        """//IN ... img | img=<hex>: images allowed here, max bytes (0 = none, CR12)."""
        m = re.search(r"(?:^| )img(?:=([0-9a-fA-F]{1,5}))?(?= |$)", in_line)
        if not m:
            return 0
        return int(m.group(1), 16) if m.group(1) else 8192

    def _motd_on_join(self, in_line: str) -> None:
        """//IN ... motd=<crc> (CR3): the text is fetched only when it is new."""
        m = re.search(r"\bmotd=([0-9a-f]{4})\b", in_line)
        name = self.board["name"]
        if not m:
            self.board["motd"] = ""
            return
        known = self.tset.get("motd", {}).get(name)
        if known and known.get("crc") == m.group(1):
            self.board["motd"] = known.get("text", "")
        else:
            self.board["motd"] = ""
            self._send("//MOTD")

    def _add_history(self, lines: list[tuple[int, str, str]], older: bool) -> None:
        """History lines (oldest first) into the chat. Ordered by time, always before
        the live events (ids >= 0); within the same second an older page goes in
        front of what is shown, a newer one behind it."""
        new = []
        for x in lines:                          # inclusive limits: drop what is here
            if x not in self._hist_keys:
                self._hist_keys.add(x)
                new.append(x)
        lines = new
        if older:
            self._hist_lo -= len(lines)
            k0 = self._hist_lo
        else:
            k0 = self._hist_hi
            self._hist_hi += len(lines)
        for i, (t, call, text) in enumerate(lines):
            self._add({"id": -(2 ** 50) + t * 1000 + k0 + i, "seq": -1, "kind": "line",
                       "call": call, "text": text, "time": t - self.clock_off,
                       "history": True, "srv_time": t, "reactions": {}})

    def _ask_history(self, n: int, since: int | None = None, before: int | None = None) -> None:
        self.board["loading"] = True
        self._hist_buf, self._hist_older = [], before is not None
        self._send(f"//HIST max={n}" + (f" since={since}" if since else "")
                   + (f" before={before}" if before else ""))

    def load_history(self, n: int) -> bool:
        """Button "load 10 / load all": older lines than the ones shown."""
        b = self.board
        if not b or "hist" not in b or b.get("loading") or not b.get("older"):
            return False
        loaded = [m["srv_time"] for m in self.messages if "srv_time" in m]
        # inclusive on the TinyBox side; lines we already have are dropped (_hist_keys)
        before = min(loaded) if loaded else (b.get("hist_last") or None)
        self._ask_history(max(1, min(n, 200)), before=before)
        self._touch()
        return True

    def leave(self) -> None:
        if self.board:
            self._send("/Q")

    def say(self, text: str) -> bool:
        text = text.replace("\r", " ").replace("\n", " ").strip()
        if not self.board or not text or text.startswith("/"):
            return False
        self._send(text[:200])
        self.pending.append({"text": text[:200], "at": time.time()})
        self._touch()
        return True

    def react(self, seq: int, emoji: str) -> bool:
        if not self.board or not re.match(r"^[!-~]{1,8}$", emoji) or not 0 <= seq < 256:
            return False
        self._send(f"/R {seq:X} {emoji}")
        # show it at once (CR8); the echo from the TinyBox confirms it
        for m in reversed(self.messages):
            if m.get("seq") == seq and m["kind"] == "line":
                calls = m["reactions"].setdefault(emoji, [])
                if self.cfg.mycall not in calls:
                    calls.append(self.cfg.mycall)
                    self.pending_reacts[(seq, emoji)] = time.time()
                break
        self._touch()
        return True

    def _send(self, line: str) -> None:
        if self._hold is not None:          # an image is going out: wait (CR12)
            self._hold.append(line)
            self.console.append("| " + line)
            return
        self.console.append("> " + line)
        self.link.send_line(line)

    def hold_lines(self, on: bool) -> None:
        """While the bytes of an image go to the TinyBox, nothing else may go on
        the link: a line in between would be counted as image data there, the
        picture would be damaged and its last bytes would land in the chat.
        Held lines (typed text, reactions, //RESEND ...) go out afterwards."""
        if on:
            if self._hold is None:
                self._hold = []
            return
        held, self._hold = self._hold or [], None
        for line in held:
            self._send(line)

    # --- link callbacks ---------------------------------------------------------

    def _on_state(self, state: str, reason: str) -> None:
        """Link state of the chat channel (kept for the tests and old callers)."""
        self.chan._on_state(state, reason)

    def _chat_state(self, state: str, prev: str, reason: str) -> None:
        """The chat channel changed its state (called by the channel)."""
        if state == "offline":
            self._clear_chat()
            if self.chan.mode == "tinybox":
                self.chan.mode = ""
        self.console.append(f"*** {state}" + (f" ({reason})" if reason else ""))

    def _clear_chat(self) -> None:
        self.handshake_done = False
        self.caps = set()
        self._clear_board()
        self.pending.clear()
        self.sync.link_lost()
        self.images.link_lost()
        self.profiles.link_lost()
        if self._hold is not None:           # held lines are gone with the link
            self._hold = []
        self.sysmsg = None                   # a shutdown warning is over now
        if self._hs_task:
            self._hs_task.cancel()

    def set_freq(self, freq: str) -> bool:
        """Frequency (MHz) for this run of the client; '' = none. Goes into
        every logbook row from now on and into the ADIF export."""
        freq = freq.strip().replace(",", ".")
        if freq:
            try:
                f = float(freq)
            except ValueError:
                return False
            if not 0.1 <= f <= 300000:
                return False
            whole, _, dec = f"{f:.6f}".rstrip("0").partition(".")
            freq = f"{whole}.{dec.ljust(3, '0')}"          # 144.8 -> 144.800
            self.settings["freq"] = freq
            self._save_settings()
        self.freq, self.freq_asked = freq, True
        self._touch()
        return True

    async def _handshake_fallback(self) -> None:
        """Telnet test port: no "Welcome to TinyBox" seen - the handshake anyway."""
        await asyncio.sleep(HANDSHAKE_FALLBACK_SEC)
        if self.state == "online" and not self.handshake_done:
            self._handshake()

    def _want_ui(self) -> bool:
        if self.link.kind in ("telnet", "axudp") or self.cfg.ui == "no":
            return False
        if self.cfg.ui == "yes":
            return True
        return time.time() - self.direct_at.get(self.target, 0) < DIRECT_VALID_SEC

    def _handshake(self) -> None:
        if self.handshake_done:
            return
        self.handshake_done = True          # sent; //OK confirms the caps
        self.chan.mode = "tinybox"
        caps = "CHAT,UI" if self._want_ui() else "CHAT"
        caps += ",SYNC,SYNC2,SHORT,NUM,HAVE,PROF" + (",Z,IMG" if self.link.kind != "telnet" else "")
        sym = f" sym={self.my_symbol}" if self.my_symbol else ""
        self._send(f"//CLIENT {PROTO} v={VERSION} caps={caps}{sym}")

    def _on_line(self, line: str) -> None:
        if self.sync.take(line):                 # mailbox sync answers and texts
            return
        if self.images.take(line):               # image transfer answers and bytes
            self.console.append(line.rstrip())
            return
        line = line.rstrip()
        if not line:
            return
        if line.startswith("//"):
            self._control(line)
        elif line.startswith("#") and (ev := proto.parse_event(line)) is not None:
            self._event(ev)
        elif line.startswith("%Q ") and self.board:
            self._qstat(line)
        else:
            self.console.append(line)
            self.chan.term_line("rx", line)        # the manual terminal of the TinyBox
            m = re.match(r"^You have (\d+) new message", line)
            if m or line.startswith("No new messages"):
                self._set_mail(int(m.group(1)) if m else 0)
            if not self.handshake_done and line.startswith("Welcome to TinyBox"):
                asyncio.get_event_loop().call_later(1.0, self._handshake)
        self._touch()

    def _on_frame(self, f: RawFrame) -> None:
        pair = frozenset((f.src, f.dest))        # CR45: channel 0, everything heard
        u = f.control & 0xEF if f.control & 0x03 == 0x03 else None
        if u == 0x6F:                            # SABME: this pair uses modulo 128
            self._mod128.add(pair)
        elif u in (0x2F, 0x43, 0x0F):            # SABM, DISC, DM: modulo 8 again
            self._mod128.discard(pair)
        else:                                    # CR50: our own SABME is not always heard
            guess = guess_mod128(f)
            if guess is True:
                self._mod128.add(pair)
            elif guess is False:
                self._mod128.discard(pair)
        self.monitor_n += 1
        entry = monitor_entry(f, pair in self._mod128,
                              frozenset([self.home, *self.settings.get("tinyboxes", [])]),
                              self.aprs_memory, self.aprs_home)
        now = time.time()                        # HH:MM:SS.mmm - milliseconds for the monitor
        entry["t"] = time.strftime("%H:%M:%S", time.localtime(now)) + f".{int(now * 1000) % 1000:03d}"
        self.monitor.append((self.monitor_n, entry))
        if "aprs" in entry:                      # CR61: APRS statistics
            try:
                self.aprs_stats.add(f.src, f.path, f.repeated, f.info,
                                    7 * (2 + len(f.path)) + len(f.rest), entry["aprs"])
            except Exception:                    # statistics must never break the radio
                log.exception("APRS statistics")
        tb = self.target
        if f.direct:
            self.direct_at[f.src] = time.time()
            if len(self.direct_at) > 200:
                del self.direct_at[min(self.direct_at, key=self.direct_at.get)]
        if {f.src, f.dest} != {self.cfg.mycall, tb}:
            self.channel_busy_at = time.monotonic()     # others use the frequency
        # CR30: a picture someone else is sending - count what we hear of it,
        # so the progress bar shows the real state and not an estimate
        u = self.uploads.get(f.src)
        if u is not None and f.is_i and f.dest == tb and f.info:
            u["got"] = min(u["size"], u["got"] + len(f.info))
            self._touch()
        if f.src != self.cfg.mycall and not f.src.startswith("TBCHAT"):
            self.heard_at[f.src] = time.time()
            if len(self.heard_at) > 200:          # forget the oldest
                del self.heard_at[min(self.heard_at, key=self.heard_at.get)]
        if not f.is_ui:
            return
        sym = aprs_symbol(f.info)
        if sym:
            self.heard[f.src] = sym
            self._touch()
        if f.src == self.home and f.dest == "TBMAIL":       # the mailbox is the home's
            self._mail_notice(f.info.decode("utf-8", "replace"))
            return
        if f.src != tb or "UI" not in self.caps:
            return
        text = f.info.decode("utf-8", "replace")
        if text.startswith("%Q "):                   # statistics line, no sequence number
            if self.board and f.dest == f"TBCHAT-{self.board['n']}":
                self._qstat(text)
            return
        ev = proto.parse_event(text)
        if ev is None:
            return
        if self._joining is not None and f.dest == f"TBCHAT-{self._joining}":
            self._early = (self._early + [ev])[-20:]
        elif self.board and f.dest == f"TBCHAT-{self.board['n']}":
            self._event(ev)
            self._touch()

    # --- protocol lines -------------------------------------------------------------

    def _control(self, line: str) -> None:
        cmd, _, rest = line[2:].partition(" ")
        if cmd == "OK":
            m = re.search(r"caps=(\S*)", rest)
            self.caps = set(filter(None, (m.group(1) if m else "").split(",")))
            self.console.append(f"*** client mode, caps: {','.join(sorted(self.caps)) or '-'}")
            known = self.settings.setdefault("tinyboxes", [])
            if self.target != self.home and self.target not in known:
                known.append(self.target)          # CR43: next time no terminal guess
                del known[:-20]
                self._save_settings()
            q = re.search(r"q=(\d+)/(\d+)/(\d+)/([\d.,]+)", rest)      # CR33
            if q:
                self.qcfg = {"frames": int(q.group(1)), "minutes": int(q.group(2)),
                             "min_frames": int(q.group(3)),
                             "steps": [float(x) for x in q.group(4).split(",") if x]}
            self._update_info(rest)
            self._send("//BOARDS")
            self.profiles.on_ok(rest)                # CR73: profile only if it differs
            if self.cfg.sync_on_login and "SYNC" in self.caps and self.at_home \
                    and not self.sync.running:
                # CR40: headers of mail and subscribed rubrics after every login,
                # a moment later so the board list comes first
                asyncio.get_event_loop().call_later(LOGIN_SYNC_SEC, self._login_sync)
        elif cmd == "B":
            parts = rest.split(" ", 4)
            if len(parts) >= 4 and parts[0].isdigit():
                if self._boards_tmp is None:
                    self._boards_tmp = []
                self._boards_tmp.append({"n": int(parts[0]), "name": parts[1], "keep": parts[2],
                                         "users": int(parts[3]) if parts[3].isdigit() else 0,
                                         "desc": parts[4] if len(parts) > 4 else ""})
        elif cmd == "BEND":
            self.boards = self._boards_tmp or []
            self._boards_tmp = None
            last = self.tset.get("board")
            if self.board is None and any(b["n"] == last for b in self.boards) \
                    and not self.sync.own_connect:   # a sync-only connection stays out
                self.join(last)                  # back into the last board
        elif cmd == "IN":
            parts = rest.split()
            if len(parts) >= 4:
                self._clear_board()
                self.board = {"n": int(parts[0]), "name": parts[1], "keep": parts[2],
                              "img": self._img_limit(rest)}
                self._history_on_join(rest)
                self._motd_on_join(rest)
                last = None if parts[3] == "-" else int(parts[3], 16)
                self.unwrap.reset(last)
                early = self._early if self._joining == self.board["n"] else []
                self._joining, self._early = None, []
                if early:     # after the //H and //WHO lines, which come next
                    asyncio.get_event_loop().call_soon(self._replay_early, early, last)
                if self.tset.get("board") != self.board["n"]:
                    self.tset["board"] = self.board["n"]
                    self._save_settings()
        elif cmd == "H":
            m = re.match(r"^(\d+) ([A-Z0-9-]+): ?(.*)$", rest)
            if m and self.board:
                line = (int(m.group(1)), m.group(2), m.group(3))
                if self._hist_buf is not None:
                    self._hist_buf.append(line)          # answer to //HIST: until //HEND
                else:
                    self._add_history([line], older=False)   # older TinyBox: right away
        elif cmd == "HEND":
            p = rest.split()
            if self.board and len(p) == 2 and p[1].isdigit():
                self._add_history(self._hist_buf or [], older=self._hist_older)
                self._hist_buf = None
                self.board["older"] = int(p[1])
                self.board["loading"] = False
        elif cmd == "MOTD":
            crc, _, text = rest.partition(" ")
            if self.board:
                motds = self.tset.setdefault("motd", {})
                if crc == "-":
                    motds.pop(self.board["name"], None)
                else:
                    motds[self.board["name"]] = {"crc": crc, "text": text}
                self._save_settings()
                self.board["motd"] = text if crc != "-" else ""
                self._touch()
        elif cmd == "WHO":                 # 'n call[=sym] ...' (NUM) or 'call[=sym] ...'
            num = 0
            for item in rest.split():
                if item.isdigit():
                    num = int(item)
                    continue
                call, _, sym = item.partition("=")
                self.members[call] = sym
                if num:
                    self._set_number(num, call)
                    num = 0
            self.profiles.want(self.members)         # CR73: names and locators
        elif cmd == "PROF":
            self.profiles.on_line(rest)
        elif cmd == "WI":
            self.profiles.on_whois(rest)
        elif cmd == "WIEND":
            self.profiles.on_whois_end()
        elif cmd == "OUT":
            self._clear_board()
            self.tset.pop("board", None)
            self._save_settings()
        elif cmd == "SYS":
            # //SYS <seconds left> <text>  (-1 = shutdown called off)
            left, _, text = rest.partition(" ")
            if re.match(r"^-?\d+$", left):
                self.sysmsg = {"text": text, "left": int(left), "at": int(time.time())}
                self.console.append("*** " + text)
        elif cmd == "ERR":
            self.console.append(line)
        # //CLIENT etc. echoed by a terminal: ignore

    def _mail_notice(self, text: str) -> None:
        """UI frame to TBMAIL: '<call> <n> new' (sent by the TinyBox, C1)."""
        m = re.match(r"^([A-Z0-9]{1,6})(?:-\d{1,2})? (\d+) new$", text.strip())
        if m and m.group(1) == self.cfg.mycall.split("-")[0]:
            self._set_mail(int(m.group(2)))
            self.console.append(f"*** mail notice: {m.group(2)} new")

    def send_outbox(self) -> str:
        """CR47: a mail just put into the outbox goes out at once - over the
        connection to the own TinyBox, or the sync connects to it by itself.
        Returns "" (on its way) or why it waits in the outbox."""
        if not self.mailbox.outbox():
            return ""
        if self.sync.running:
            self.sync.send_again = True           # after the running sync
            return ""
        if self.state != "offline" and not self.at_home:
            return f"connected to {self.target} - goes out with the next sync at {self.home}"
        if self.state != "offline" and self.state != "online":
            self.sync.send_again = True
            return "the connection is changing - goes out with the next sync"
        if self.state == "online" and "SYNC" not in self.caps:
            return "not ready yet - goes out with the next sync"
        if not self.sync.start("send"):
            return "busy (picture or no free channel) - goes out with the next sync"
        return ""

    def _login_sync(self) -> None:
        if self.state == "online" and "SYNC" in self.caps and self.at_home \
                and not self.sync.running:
            self.sync.start("login")

    def after_sync(self) -> None:
        """Everything is fetched now: the notice of new mail is done."""
        if self.mail and self.mail["count"] and not self.sync.status["error"]:
            self.mail = {"count": 0, "at": self.mail["at"]}

    def _set_mail(self, count: int) -> None:
        old = self.mail["count"] if self.mail else 0
        self.mail = {"count": count, "at": int(time.time()) if count != old else
                     (self.mail or {}).get("at", int(time.time()))}
        self._touch()

    def _replay_early(self, events: list[proto.Event], last: int | None) -> None:
        for ev in events:
            if last is None or 0 < (ev.seq - last) % 256 < 128:
                self._event(ev)
        self._touch()

    def _clear_board(self) -> None:
        if self.board:                       # everything up to now was seen (CR13)
            seen = self.tset.setdefault("seen", {})
            seen[self.board["name"]] = int(time.time()) + self.clock_off
            self._save_settings()
        self._hist_keys = set()
        self._hist_buf, self._hist_lo, self._hist_hi = None, 0, 0
        self.board = None
        self.members = {}
        self.numbers = {}
        self.quality = {}
        self.linkq = {}
        self.messages = []
        self.uploads = {}
        self.seen = set()
        self.unwrap = proto.Unwrapper()
        self.pending_reacts = {}

    def _event(self, ev: proto.Event) -> None:
        if not self.board:
            return
        before = self.unwrap.last
        pos = self.unwrap.unwrap(ev.seq)
        if pos in self.seen:
            return                                   # UI + I-frame, or a resend
        self.seen.add(pos)
        if before is not None and pos > before + 1:
            first, last = (before + 1) % 256, (pos - 1) % 256
            if pos - before - 1 <= MAX_GAP:
                self._send(f"//RESEND {first:X}-{last:X}")
            else:                 # too many to fetch: only tell, for the receive quote
                self._send(f"//LOST {first:X}-{last:X}")
        now = int(time.time())
        if ev.kind == "line":
            self._add({"id": pos, "seq": ev.seq, "kind": "line", "call": ev.call,
                       "text": ev.text, "time": now, "reactions": {}})
            if chatimg.parse_ref(ev.text):          # the picture is here: no "uploading"
                self.uploads.pop(ev.call, None)
            if ev.call == self.cfg.mycall:
                for p in self.pending:
                    if p["text"] == ev.text:
                        self.pending.remove(p)
                        break
        elif ev.kind == "join":
            self.members[ev.call] = ev.symbol
            self.profiles.want([ev.call])
            if ev.num:
                self._set_number(ev.num, ev.call)
            self._add({"id": pos, "seq": ev.seq, "kind": "join", "call": ev.call, "time": now})
        elif ev.kind == "symbol":                    # nothing to show, only the avatars
            call = ev.call or self.numbers.get(ev.num, "")
            if call in self.members:
                self.members[call] = ev.symbol
        elif ev.kind == "leave":
            call = ev.call or self.numbers.pop(ev.num, "")
            if not call:
                return                               # number unknown: nothing to remove
            self.numbers = {n: c for n, c in self.numbers.items() if c != call}
            self.members.pop(call, None)
            self.quality.pop(call, None)
            self.linkq.pop(call, None)
            self._add({"id": pos, "seq": ev.seq, "kind": "leave", "call": call, "time": now})
        elif ev.kind == "react":
            for m in reversed(self.messages):
                if m.get("seq") == ev.ref and m["kind"] == "line":
                    calls = m["reactions"].setdefault(ev.text, [])
                    if ev.call not in calls:
                        calls.append(ev.call)
                    break
            if ev.call == self.cfg.mycall:
                self.pending_reacts.pop((ev.ref, ev.text), None)
        elif ev.kind == "upload":                    # CR30: a picture is going up
            if ev.call != self.cfg.mycall:
                self.uploads[ev.call] = {"size": ev.ref, "at": now, "got": 0}
        elif ev.kind == "quality":                   # bars next to the avatars (14.4)
            self.quality = {}
            for who, b in (ev.bars or {}).items():
                call = self.numbers.get(who, "") if isinstance(who, int) else who
                if call:
                    self.quality[call] = b
        elif ev.kind == "system":
            self._add({"id": pos, "seq": ev.seq, "kind": "system", "text": ev.text,
                       "time": now})

    def _set_number(self, num: int, call: str) -> None:
        """Member numbers are reused: a new holder pushes the old one out."""
        self.numbers = {n: c for n, c in self.numbers.items() if c != call and n != num}
        self.numbers[num] = call

    def _qstat(self, line: str) -> None:
        """%Q: the numbers behind the bars of every member with data (CR33)."""
        stats = proto.parse_qstat(line)
        if stats is None:
            return
        self.linkq = {}
        for num, rec in stats.items():
            call = self.numbers.get(num)
            if call:
                rec = dict(rec, call=call, at=int(time.time()))
                self.linkq[call] = rec
                self.quality[call] = rec["bars"]       # the bars come with it
        self._touch()

    def _add(self, msg: dict) -> None:
        self.chan.act_n += 1                     # CR45: the chip blinks in the background
        self.messages.append(msg)
        self.messages.sort(key=lambda m: m["id"])
        del self.messages[:-MAX_MESSAGES]

    # --- for the GUI -------------------------------------------------------------------

    def _expire_reacts(self, now: float) -> None:
        """Own reactions that never came back within 2 min are taken back."""
        for (seq, emoji), at in list(self.pending_reacts.items()):
            if now - at < 120:
                continue
            del self.pending_reacts[(seq, emoji)]
            for m in reversed(self.messages):
                if m.get("seq") == seq and m["kind"] == "line":
                    calls = m["reactions"].get(emoji, [])
                    if self.cfg.mycall in calls:
                        calls.remove(self.cfg.mycall)
                    if not calls:
                        m["reactions"].pop(emoji, None)
                    break

    def symbol_of(self, call: str) -> str:
        if call == self.cfg.mycall and self.my_symbol:
            return self.my_symbol
        return self.members.get(call) or self.heard.get(call, "")

    def snapshot(self, ch: int | None = None) -> dict:
        """ch = the channel shown in the GUI: its terminal lines come along
        (0 = the monitor). The top level describes the chat channel."""
        calls = {self.cfg.mycall, *self.members}
        calls.update(m["call"] for m in self.messages if m.get("call"))
        now = time.time()
        self.pending = [p for p in self.pending if now - p["at"] < 120]
        rate = max(1, self.cfg.img_rate)         # an upload that never finished: forget it
        self.uploads = {c: u for c, u in self.uploads.items()
                        if now - u["at"] < 2 * u["size"] / rate + 60}
        self._expire_reacts(now)
        return {
            "version": self.version, "client_version": VERSION,
            "mycall": self.cfg.mycall, "tinybox": self.target,
            "home": self.home, "recent": self.recent,                  # CR42
            "link": self.cfg.link, "state": self.state, "reason": self.reason,
            "state_age": round(now - self.chan.state_at, 1), "ended": self.chan.ended,
            "mode": self.mode,                                          # CR43
            "freq": self.freq, "freq_ask": not self.freq_asked,         # CR44
            "freq_last": self.settings.get("freq", ""),
            # CR45: the channels, the chat channel (0 = none) and the shown one
            "channels": [c.summary(now) for _, c in sorted(self.channels.items())],
            "chat_ch": self.chan.n, "max_ch": self.cfg.max_channels, "monitor_n": self.monitor_n,
            "focus": self.focus,                                        # CR75
            "radio": self.radio_state(),                                # CR46
            "axudp": self.udp.radio_state() if self.udp is not None else None,   # PLANUNG 25
            "ch": ch,
            "term": self._term_of(ch), "term_n": self._term_n_of(ch),
            "peerchat": self._peerchat_of(ch),                          # CR78
            "client": self.handshake_done and bool(self.caps or self.boards),
            "ui": "UI" in self.caps,
            "boards": self.boards, "board": self.board,
            "members": sorted(self.members),
            "quality": self.quality,
            # PLANUNG 25: the chat runs over AXUDP (or the telnet test port) - no radio
            # path, so no link quality for the own station: only the connection type
            "chat_link": self.link.kind,
            "linkq": self.linkq, "qcfg": self.qcfg,      # CR33: detail view per station
            "mail": self.mail,
            "sysmsg": self.sysmsg,
            "heard": [{"call": c, "symbol": self.heard.get(c, ""), "ago": int(now - t)}
                      for c, t in sorted(self.heard_at.items(), key=lambda kv: -kv[1])[:30]
                      if c not in self.members and c != self.target],
            "symbols": {c: self.symbol_of(c) for c in calls if self.symbol_of(c)},
            "my_symbol": self.my_symbol,
            "messages": self.messages, "pending": [p["text"] for p in self.pending],
            "clock_off": self.clock_off,     # TinyBox time - own time (quotes, CR14)
            "pending_reacts": [f"{seq}:{e}" for seq, e in self.pending_reacts],
            "mailbox": self.mailbox.summary(),
            "sync": self.sync.status,
            "update": self.update,
            "release": self.release_info,                               # PLANUNG 24
            "history_mode": self.history_mode,
            # CR30: pictures other stations are sending right now
            "uploads": [{"call": c, "size": u["size"], "at": u["at"], "got": u["got"]}
                        for c, u in self.uploads.items()],
            "images": self.images.status(self._image_refs()),
            "img": {"rate": self.cfg.img_rate, "target": self.cfg.img_target},
            **self.profiles.snapshot(calls),                            # CR73
        }

    def _image_refs(self) -> set[str]:
        """Hashes of the images referred to in the chat shown right now."""
        refs = set()
        for m in self.messages:
            if m.get("kind") == "line" and "~#" in (m.get("text") or ""):
                r = chatimg.parse_ref(m["text"])
                if r:
                    refs.add(r[0])
        if self.images.upload:
            refs.add(self.images.upload["hash"])
        return refs

    # --- images (CR12) ---------------------------------------------------------------

    def send_image(self, data: bytes, blurhash: str, caption: str, quote: str) -> str | None:
        """From the GUI: the shrunk picture, its blurhash, the caption (wire
        text) and the quote prefix. Starts the upload; the chat line follows."""
        if not self.board or not self.board.get("img") or "IMG" not in self.caps:
            return None
        if len(data) > self.board["img"]:
            return None
        if quote and not re.match(r"^~\^(?:[0-9A-Fa-f]{1,2}|[A-Z0-9-]{1,9} \d{4}) $", quote):
            return None
        caption = caption.replace("\r", " ").replace("\n", " ").strip()
        if caption.startswith("/"):
            caption = " " + caption
        return self.images.send(data, blurhash, caption[:150], quote)

    def fetch_image(self, hash: str) -> bool:
        if self.state != "online" or "IMG" not in self.caps:
            return False
        return self.images.fetch(hash)

    def clear_monitor(self) -> None:
        """CR50: the Clear button of the monitor (the counter goes on)."""
        self.monitor.clear()
        self._touch()

    def radio_state(self) -> dict:
        """The way to the radio: Direwolf (AGW), kisshub (KISS, with the TNC) or telnet."""
        if isinstance(self.port, KissPort):
            return self.port.radio_state()
        if self.port is not None:
            return {"via": "agw", "up": self.port.agw_up.is_set()}
        return {"via": "telnet", "up": True}

    def _term_of(self, ch: int | None) -> list:
        if ch == 0:
            return [(n, "mon", e) for n, e in list(self.monitor)[-TERM_SNAPSHOT:]]
        c = self.channels.get(ch) if ch is not None else self.chan
        return list(c.term)[-TERM_SNAPSHOT:] if c is not None else []

    def _peerchat_of(self, ch: int | None) -> dict | None:
        """The stored chat with the TBClient of the channel shown (CR78)."""
        c = self.channels.get(ch) if ch else None
        if c is None or c.peer is None or self.peerchat is None or not c.peer.hist:
            return None
        return {"v": self.peerchat.version, "msgs": self.peerchat.messages(c.peer.call)}

    def _term_n_of(self, ch: int | None) -> int:
        if ch == 0:
            return self.monitor_n
        c = self.channels.get(ch) if ch is not None else self.chan
        return c.term_n if c is not None else 0

    async def run(self) -> None:
        if self.cfg.auto_connect:            # always to the own TinyBox, channel 1
            asyncio.get_event_loop().call_later(
                2, lambda: asyncio.ensure_future(self.connect(self.home, ch=1)))
        if self.port is None:
            await asyncio.Event().wait()     # telnet: nothing to keep open between sessions
            return
        poller = asyncio.ensure_future(self._poll_outstanding())
        qpoll = asyncio.ensure_future(self._poll_peer_quality())
        udp = asyncio.ensure_future(self.udp.run()) if self.udp is not None else None
        try:
            await self.port.run()
        finally:
            poller.cancel()
            qpoll.cancel()
            if udp is not None:
                udp.cancel()
