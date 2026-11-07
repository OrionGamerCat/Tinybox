"""KISS link of the client (CR46): kisshub instead of Direwolf - the client runs
its own AX.25 layer 2 (prcore/ax25, v2.2 with fallback to v2.0).
With a KISS TNC behind kisshub the client is a complete packet radio program
of its own: no Direwolf, no TinyBox needed.

    TNC --serial-- kisshub --KISS-TCP 127.0.0.1:8101-- KissPort --+-- KissLink channel 1
                                                                  +-- KissLink channel 2 ...

KissPort  the shared KISS port (prcore/kissport.py: KISS-TCP, router, timers of
          all links, DM for strangers) plus the monitor and the channels
KissLink  one AX.25 connection, the same interface as AgwLink for the channels

Incoming connects (somebody connects to us) open a free channel as a terminal;
with no free channel the station gets DM.
"""

from __future__ import annotations

import logging

from prcore.ax25.frame import Frame
from prcore.ax25.link import Ax25Link, LinkCfg
from prcore.kissport import KissPort as SharedKissPort
from prcore.kissport import describe_changes, norm_call, poll_hub

from . import radio
from .config import Config, estimate_rate
from .links import BaseLink

log = logging.getLogger(__name__)

HUB_POLL_SEC = 30

# why a link went down -> the reason the channel shows ("disconnected" = normal,
# while connecting the GUI makes "no answer from ..." of it)
REASONS = {"local": "disconnected", "remote": "disconnected", "timeout": "disconnected",
           "refused": "refused (DM)", "dm": "refused (DM)",
           "retryout": "link lost (no answer)", "protocol": "protocol error"}


def link_cfg(cfg: Config) -> LinkCfg:
    return LinkCfg(paclen=cfg.ax25_paclen, maxframe=cfg.ax25_maxframe,
                   maxframe_ext=cfg.ax25_maxframe_ext, srej=cfg.ax25_srej, n2=cfg.ax25_n2,
                   version=cfg.ax25_version, t1_min_sec=cfg.ax25_t1_min,
                   t1_max_sec=cfg.ax25_t1_max, t2_sec=cfg.ax25_t2, t3_sec=cfg.ax25_t3,
                   v20_digis=cfg.ax25_v20_digis,
                   v20_digi_paclen=cfg.ax25_v20_digi_paclen,
                   air_baud=cfg.kiss_air_baud, txdelay_sec=cfg.kiss_txdelay_ms / 1000,
                   max_rx_info=max(512, cfg.ax25_paclen))


def axudp_link_cfg(cfg: Config) -> LinkCfg:
    """PLANUNG 25: AX.25 to the home TinyBox over AXUDP - no airtime. Window, PACLEN,
    T1 and N2 as in tbclient.conf ([tinybox] axudp_*; same rule as the TinyBox's
    [axudp]: T1 from t1_sec up to 4 times that, at least 10 s)."""
    t1 = cfg.axudp_t1_sec
    slow = cfg.axudp_air_baud > 0                 # a way with air time (half duplex)
    return LinkCfg(paclen=cfg.axudp_paclen, maxframe=min(7, cfg.axudp_maxframe),
                   maxframe_ext=cfg.axudp_maxframe, n2=cfg.axudp_n2, version="2.2",
                   srt_init_sec=t1 / 2, t1_min_sec=t1, t1_max_sec=max(t1 * 4, 10.0),
                   t2_sec=1.5 if slow else 0.05, t3_sec=300.0,
                   air_baud=cfg.axudp_air_baud or 10_000_000,
                   txdelay_sec=cfg.axudp_txdelay_ms / 1000,
                   srej=cfg.ax25_srej, max_rx_info=max(512, cfg.axudp_paclen))


class KissPort(SharedKissPort):
    link_kind = "kiss"                            # KissLink.kind of its channels
    down_text = "kisshub not reachable"

    def __init__(self, cfg: Config, on_frame, on_incoming=None, *,
                 lcfg: LinkCfg | None = None, transport=None,
                 half_duplex: bool | None = None) -> None:
        super().__init__(cfg.mycall, cfg.kiss_host, cfg.kiss_port, lcfg or link_cfg(cfg),
                         channel=cfg.kiss_channel, reconnect_sec=5, transport=transport,
                         half_duplex=transport is None if half_duplex is None else half_duplex)
        self.cfg = cfg
        self.on_frame = on_frame                  # monitor: radio.RawFrame
        self.on_incoming = on_incoming            # remote -> KissLink of a free channel, or None
        self.agw_up = self.connected              # same name as AgwPort: "the radio is there"
        self.chans: dict[str, KissLink] = {}      # remote -> the channel of that connection
        self.hub: dict | None = None              # kisshub's /status: the TNC behind it

    async def run(self) -> None:
        log.info("KISS %s:%d, own AX.25 layer 2 (version %s), %s",
                 self.cfg.kiss_host, self.cfg.kiss_port, self.link_cfg.version, self.mycall)
        await super().run(poll_hub(self.cfg.kiss_host, self.cfg.kiss_status_port,
                                   HUB_POLL_SEC, self._on_hub_status))

    # --- hooks of the shared port --------------------------------------------------

    def on_heard(self, data: bytes, peeked: tuple | None, target: Ax25Link | None) -> None:
        rf = radio.decode(data)
        if rf is not None:
            self.on_frame(rf)

    def on_transmit(self, f: Frame, raw: bytes) -> None:
        rf = radio.decode(raw)
        if rf is not None:
            self.on_frame(rf)                     # the own frames belong into the monitor

    def accept_incoming(self, link: Ax25Link) -> bool:
        """Somebody connects to us: a free channel takes it, otherwise DM."""
        if self.on_incoming is None:
            return False
        k = self.on_incoming(link.remote)
        if k is None:
            return False
        k.ax = link
        self.chans[link.remote] = k
        return True

    def on_link_event(self, link: Ax25Link, name: str, arg) -> None:
        k = self.chans.get(link.remote)
        if k is not None and k.ax is link:
            k.on_event(name, arg)

    # --- kisshub status -------------------------------------------------------------

    def _on_hub_status(self, status: dict | None, exc: Exception | None) -> None:
        """Which TNC, and is it in KISS? (kisshub GET /status, loopback only)."""
        if status is None:
            self.hub = None
            return
        changed = self.apply_hub_status(status, self.cfg.kiss_fixed)   # CR70
        if changed:
            log.info("radio values from kisshub: %s", describe_changes(changed))
            if "air_baud" in changed and not self.cfg.img_rate_fixed:
                self.cfg.img_rate = estimate_rate(self.link_cfg.air_baud)
        tnc = status.get("tnc") or {}
        self.hub = {"tnc": tnc.get("name"), "state": tnc.get("state"),
                    "error": tnc.get("last_error")}

    def radio_state(self) -> dict:
        h = self.hub or {}
        return {"via": "kiss", "up": self.kiss.connected.is_set(), "tnc": h.get("tnc"),
                "tnc_state": h.get("state"), "error": h.get("error")}


class AxudpPort(KissPort):
    """PLANUNG 25: the home TinyBox over AXUDP - the client's own AX.25 over UDP
    on loopback, next to the radio port. Only the home TinyBox is a peer; its
    frames do not go to the monitor (they are not on the air)."""
    link_kind = "axudp"
    down_text = "AXUDP port not open"

    def __init__(self, cfg: Config, on_incoming=None) -> None:
        from prcore import axudp as udp
        peers = {cfg.tinybox_call: udp.Peer(cfg.tinybox_call, cfg.axudp_host, cfg.axudp_port)}
        listen = "::1" if ":" in cfg.axudp_host else "127.0.0.1"
        super().__init__(cfg, lambda rf: None, on_incoming, lcfg=axudp_link_cfg(cfg),
                         transport=lambda on_frame: udp.AxudpEndpoint(
                             listen, cfg.axudp_listen, peers, on_frame,
                             hear=cfg.mycall if cfg.axudp_air_baud else None),
                         half_duplex=cfg.axudp_air_baud > 0)

    async def run(self) -> None:
        log.info("AXUDP 127.0.0.1:%d -> home TinyBox %s at %s:%d", self.cfg.axudp_listen,
                 self.cfg.tinybox_call, self.cfg.axudp_host, self.cfg.axudp_port)
        await SharedKissPort.run(self)

    def on_heard(self, data: bytes, peeked: tuple | None, target: Ax25Link | None) -> None:
        pass

    def on_transmit(self, f: Frame, raw: bytes) -> None:
        pass

    def radio_state(self) -> dict:
        ep = self.kiss
        return {"via": "axudp", "up": ep.connected.is_set(),
                "addr": f"{self.cfg.axudp_host}:{self.cfg.axudp_port}",
                "dropped": sum(ep.dropped.values())}


class KissLink(BaseLink):
    """One AX.25 connection over the KissPort (or the AxudpPort), for one channel."""
    kind = "kiss"

    def __init__(self, port: KissPort, cfg: Config, on_state, on_line) -> None:
        super().__init__(cfg, on_state, on_line)
        self.port = port
        self.kind = port.link_kind
        self.agw_up = port.agw_up
        self.ax: Ax25Link | None = None

    def _forget(self) -> None:
        ax = self.ax
        if ax is not None:
            if self.port.chans.get(ax.remote) is self:
                del self.port.chans[ax.remote]
            if self.port.links.get(ax.remote) is ax:
                del self.port.links[ax.remote]
        self.ax = None

    def on_event(self, name: str, arg) -> None:
        if name == "connected":                   # (the port keeps its v2.0 memory)
            if arg == "incoming":
                self._fresh()
            self._set("online")
        elif name == "data":
            self.rx_bytes += len(arg)
            self.splitter.feed(arg)
        elif name == "disconnected":
            self._forget()
            if self.active:
                self._set("offline", REASONS.get(arg, str(arg)))

    async def connect(self) -> None:
        if not self.agw_up.is_set():
            self._set("offline", self.port.down_text)
            return
        remote = norm_call(self.target)
        if remote in self.port.links or remote in self.port.chans:
            self._set("offline", f"already connected to {self.target}")
            return
        self._fresh()
        self.ax = self.port.open_link(remote, self.via)     # CR71: digipeater path
        self.port.chans[remote] = self
        self._set("connecting")
        self.ax.connect(self.port.now())
        self.port.service(self.ax)

    def send_line(self, text: str) -> None:
        self.send_bytes((text + "\r").encode("utf-8"))

    def send_bytes(self, data: bytes) -> None:
        if self.ax is None:
            return
        self.tx_bytes += len(data)
        self.ax.send(data, self.port.now())
        self.port.service(self.ax)

    async def counters(self) -> dict | None:
        """CR78: our own AX.25 counts - same names as the Direwolf fork's 'Q'."""
        return self.ax.counters(self.port.now()) if self.ax is not None and self.online else None

    async def outstanding(self) -> int:
        """Frames not yet acknowledged or not yet sent."""
        return (len(self.ax.queue) + self.ax.unacked) if self.ax else 0

    def disconnect(self) -> None:
        if not self.active or self.ax is None:
            return
        if self.online:
            self._set("disconnecting")
        self.ax.disconnect(self.port.now())       # connecting: gone at once ("local")
        self.port.service(self.ax)

    def drop(self, reason: str) -> None:
        self._forget()
        super().drop(reason)
