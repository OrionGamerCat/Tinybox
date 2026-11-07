"""The two ways to reach the TinyBox.

AgwLink    radio, through Direwolf's AGW port: Direwolf does the AX.25
           connection; with 'k' (raw frames on) we also see every frame on
           the channel - that is how the UI frames to TBCHAT-<n> and APRS
           beacons (symbols) come in.
TelnetLink the TinyBox telnet test port on the same PC (no radio, no UI).

Both call back into the client core:
    on_state(state, reason)   state: offline | connecting | online | disconnecting
    on_line(text)             one line from the TinyBox
    on_frame(RawFrame)        a frame heard on the channel (AgwPort, shared by all)
"""

from __future__ import annotations

import asyncio
import logging
import struct
from typing import Callable

from prcore.termcolor import OK

from prcore import linkq
from prcore.agw import PID_NO_L3, Frame, read_frame, via_data

from . import radio
from .config import Config

log = logging.getLogger(__name__)

# Bytes per AGW "D" frame = bytes per I-frame on air. Direwolf makes one or
# more I-frames out of every "D" frame and never joins two, so this is what
# decides the frame size, not direwolf.conf (whose PACLEN only splits further).
# 256 = AX.25 and Direwolf default; 128 halved the data per frame and so
# doubled the frames (and the overhead) of every picture.
PACLEN = 256
IAC = 255


class LineSplitter:
    """Bytes -> lines (CR, LF or CR LF), UTF-8 with Latin-1 fallback."""

    def __init__(self, on_line: Callable[[str], None]) -> None:
        self.on_line = on_line
        self.buf = bytearray()
        self.last_cr = False
        self.need = 0                     # binary mode: bytes still expected
        self.bin = bytearray()
        self.on_bin: Callable[[bytes], None] | None = None
        self.on_progress: Callable[[int], None] | None = None

    def expect(self, n: int, on_bin: Callable[[bytes], None],
               on_progress: Callable[[int], None] | None = None) -> None:
        """The next n bytes are binary (compressed message text, an image), not
        lines. Called from on_line, so it applies right after the announcing
        line. on_progress(bytes so far) after every piece that comes in."""
        if n <= 0:
            on_bin(b"")
            return
        self.need, self.bin, self.on_bin, self.on_progress = n, bytearray(), on_bin, on_progress

    def feed(self, data: bytes) -> None:
        i = 0
        while i < len(data):
            if self.need:
                take = data[i:i + self.need]
                i += len(take)
                self.bin += take
                self.need -= len(take)
                if self.on_progress is not None:
                    self.on_progress(len(self.bin))
                if not self.need:
                    self.last_cr = False
                    cb, self.on_bin, self.on_progress = self.on_bin, None, None
                    cb(bytes(self.bin))
                continue
            b = data[i]
            i += 1
            if b in (10, 13):
                if b == 10 and self.last_cr:
                    self.last_cr = False
                    continue
                self.last_cr = b == 13
                raw = bytes(self.buf)
                self.buf.clear()
                try:
                    line = raw.decode("utf-8")
                except UnicodeDecodeError:
                    line = raw.decode("latin-1")
                self.on_line(line)
                continue
            self.last_cr = False
            if len(self.buf) < 4096:
                self.buf.append(b)


class BaseLink:
    paclen = PACLEN                 # bytes per frame handed over (progress estimate)

    def __init__(self, cfg: Config, on_state, on_line) -> None:
        self.cfg = cfg
        self.on_state = on_state          # both may be re-pointed (CR45: channel -> chat)
        self.on_line = on_line
        self.splitter = LineSplitter(self._line)
        self.online = False
        self.active = False               # anything but offline (connecting ... disconnecting)
        self.target = cfg.tinybox_call    # the station to connect to (set by the channel)
        self.via: list[str] = []          # CR71: digipeater path of the next connect
        self.rx_bytes = 0                 # CR44: payload of the current connection
        self.tx_bytes = 0

    def _line(self, line: str) -> None:
        self.on_line(line)

    def _set(self, state: str, reason: str = "") -> None:
        self.online = state == "online"
        self.active = state != "offline"
        self.on_state(state, reason)

    def _fresh(self) -> None:
        """A new connection: counters and line state start over."""
        self.rx_bytes = self.tx_bytes = 0
        self.splitter = LineSplitter(self._line)

    async def counters(self) -> dict | None:
        """CR78: AX.25 counters of this connection (names as prcore/linkq.py), None =
        not available (telnet, Direwolf without the TinyBox fork)."""
        return None

    def drop(self, reason: str) -> None:
        """Offline now, without waiting for the other side (a disconnect that
        never got an answer). A late answer is then ignored."""
        if self.active:
            self._set("offline", reason)


class AgwPort:
    """The TCP link to Direwolf's AGW port, shared by all connections (CR45: up
    to 5 at once). Registers mycall, switches the raw monitor on and hands every
    frame to the AgwLink of that station; raw frames go to on_frame."""

    def __init__(self, cfg: Config, on_frame, on_incoming=None) -> None:
        self.cfg = cfg
        self.on_frame = on_frame
        self.on_incoming = on_incoming            # remote -> AgwLink of a free channel, or None
        self._writer: asyncio.StreamWriter | None = None
        self.agw_up = asyncio.Event()
        self.links: dict[str, "AgwLink"] = {}      # remote call -> its connection
        # CR78: Direwolf answers 'Q' (TinyBox fork)? None = not known yet
        self.q_supported: bool | None = None

    def send(self, kind: str, call_from: str = "", call_to: str = "",
             data: bytes = b"", pid: int = 0) -> None:
        w = self._writer
        if w is not None and not w.is_closing():
            w.write(Frame(kind, self.cfg.radio_port, pid, call_from, call_to, data).pack())

    async def run(self) -> None:
        """Keep the TCP link to Direwolf open (reconnects by itself)."""
        warned = False
        while True:
            try:
                reader, writer = await asyncio.open_connection(self.cfg.agw_host,
                                                               self.cfg.agw_port)
            except OSError as exc:
                if not warned:
                    log.error("Direwolf AGW %s:%s not reachable (%s)",
                                self.cfg.agw_host, self.cfg.agw_port, exc)
                warned = True
                await asyncio.sleep(5)
                continue
            warned = False
            self._writer = writer
            log.info("connected to Direwolf AGW %s:%s", self.cfg.agw_host, self.cfg.agw_port,
                     extra=OK)
            self.send("R")
            self.send("X", self.cfg.mycall)
            self.send("k")
            self.q_supported = None                 # maybe another Direwolf now
            self.agw_up.set()
            try:
                while True:
                    f = await read_frame(reader)
                    try:
                        self._dispatch(f.kind, f.call_from, f.call_to, f.data)
                    except Exception:
                        log.exception("error handling AGW frame")
            except (asyncio.IncompleteReadError, ConnectionError, OSError) as exc:
                log.error("AGW connection lost: %s", exc or type(exc).__name__)
            finally:
                self.agw_up.clear()
                self._writer = None
                writer.close()
                for link in list(self.links.values()):
                    link.connecting = False
                    link.drop("Direwolf connection lost")
            await asyncio.sleep(5)

    def _dispatch(self, kind: str, cfrom: str, cto: str, data: bytes) -> None:
        if kind == "K" and len(data) > 1:
            frame = radio.decode(data[1:])
            if frame is not None:
                self.on_frame(frame)
            return
        if kind == "X":
            if data[:1] != b"\x01":
                log.error("Direwolf refused to register %s", self.cfg.mycall)
            return
        remote = cto if cfrom == self.cfg.mycall else cfrom
        link = self.links.get(remote) or self.links.get(cfrom) or self.links.get(cto)
        if link is None and kind == "C" and self.on_incoming is not None:
            # somebody connected to us (CR46): a free channel, or the link goes down again
            link = self.on_incoming(remote)
            if link is None:
                self.send("d", self.cfg.mycall, remote)
                return
            self.links[remote] = link
            link._fresh()
        if link is not None:
            link.on_agw(kind, data)


class AgwLink(BaseLink):
    """One AX.25 connection through the shared AgwPort."""
    kind = "agw"

    def __init__(self, port: AgwPort, cfg: Config, on_state, on_line) -> None:
        super().__init__(cfg, on_state, on_line)
        self.port = port
        self.agw_up = port.agw_up
        self.connecting = False
        self._outstanding = 0
        self._y_reply = asyncio.Event()
        self._q: dict | None = None
        self._q_reply = asyncio.Event()

    def _set(self, state: str, reason: str = "") -> None:
        if state == "offline" and self.port.links.get(self.target) is self:
            del self.port.links[self.target]        # free for the next connection
        super()._set(state, reason)

    def on_agw(self, kind: str, data: bytes) -> None:
        if kind == "C":
            self.connecting = False
            self._set("online")
        elif kind == "D":
            self.rx_bytes += len(data)
            self.splitter.feed(data)
        elif kind == "Y" and len(data) >= 4:
            self._outstanding = struct.unpack("<I", data[:4])[0]
            self._y_reply.set()
        elif kind == "Q":                         # CR78: TinyBox Direwolf fork
            self.port.q_supported = True
            self._q = linkq.parse(data.decode("ascii", "replace"))
            self._q_reply.set()
        elif kind == "d":
            self.connecting = False
            if self.active:
                self._set("offline", "disconnected")

    async def connect(self) -> None:
        if not self.agw_up.is_set():
            self._set("offline", "Direwolf not reachable")
            return
        other = self.port.links.get(self.target)
        if other is not None and other is not self:
            self._set("offline", f"already connected to {self.target}")
            return
        self.port.links[self.target] = self
        self.connecting = True
        self._fresh()
        self._set("connecting")
        if self.via:                      # CR71: AGW 'v' = connect via digipeaters
            self.port.send("v", self.cfg.mycall, self.target, via_data(self.via), PID_NO_L3)
        else:
            self.port.send("C", self.cfg.mycall, self.target, pid=PID_NO_L3)

    def send_line(self, text: str) -> None:
        self.send_bytes((text + "\r").encode("utf-8"))

    def send_bytes(self, data: bytes) -> None:
        """Raw bytes (a line, or image data after //IMGGO)."""
        self.tx_bytes += len(data)
        for i in range(0, len(data), PACLEN):
            self.port.send("D", self.cfg.mycall, self.target, data[i:i + PACLEN], PID_NO_L3)

    async def outstanding(self) -> int:
        """Frames of our connection still waiting in Direwolf (AGW 'Y')."""
        self._y_reply.clear()
        self.port.send("Y", self.cfg.mycall, self.target)
        try:
            await asyncio.wait_for(self._y_reply.wait(), 5)
        except asyncio.TimeoutError:
            return 0
        return self._outstanding

    async def counters(self) -> dict | None:
        """AGW 'Q' - only the TinyBox fork of Direwolf answers (direwolf-tinybox)."""
        if self.port.q_supported is False or not self.online:
            return None
        self._q_reply.clear()
        self.port.send("Q", self.cfg.mycall, self.target)
        try:
            await asyncio.wait_for(self._q_reply.wait(), 3)
        except asyncio.TimeoutError:
            if self.port.q_supported is None:
                self.port.q_supported = False
                log.info("Direwolf does not answer 'Q' (no TinyBox fork): no link quality")
            return None
        return self._q

    def disconnect(self) -> None:
        """Direwolf answers with 'd' once the link is down (DISC/UA, or after
        its retries); until then the state is "disconnecting"."""
        if self.active and self.agw_up.is_set():
            self._set("disconnecting")
            self.port.send("d", self.cfg.mycall, self.target)
        elif self.active:
            self.connecting = False
            self._set("offline", "Direwolf not reachable")


class TelnetLink(BaseLink):
    kind = "telnet"

    def __init__(self, *a) -> None:
        super().__init__(*a)
        self._writer: asyncio.StreamWriter | None = None
        self._task: asyncio.Task | None = None
        self._sent: list[str] = []       # our own lines come back as telnet echo

    async def run(self) -> None:
        await asyncio.Event().wait()      # nothing to keep open between sessions

    def _line(self, line: str) -> None:
        # the server echoes what we typed (after a prompt on the same line)
        if self._sent and self._sent[0] and line.rstrip().endswith(self._sent[0].rstrip()):
            self._sent.pop(0)
            return
        self.on_line(line)

    async def connect(self) -> None:
        self._fresh()
        self._set("connecting")
        try:
            reader, writer = await asyncio.open_connection(self.cfg.telnet_host,
                                                           self.cfg.telnet_port)
        except OSError as exc:
            self._set("offline", f"telnet: {exc}")
            return
        self._writer = writer
        writer.write((self.cfg.mycall + "\r\n").encode())       # answers the call prompt
        self._sent = [self.cfg.mycall]
        self._set("online")
        self._task = asyncio.create_task(self._read(reader))

    async def _read(self, reader: asyncio.StreamReader) -> None:
        try:
            while True:
                data = await reader.read(1024)
                if not data:
                    break
                self.rx_bytes += len(data)
                self.splitter.feed(_strip_iac(data))
        except (ConnectionError, OSError):
            pass
        self._writer = None
        self._set("offline", "disconnected")

    def send_line(self, text: str) -> None:
        if self._writer is not None:
            self._sent.append(text)
            del self._sent[:-20]
            data = (text + "\r\n").encode("utf-8")
            self.tx_bytes += len(data)
            self._writer.write(data)

    def send_bytes(self, data: bytes) -> None:      # never used: no IMG cap on telnet
        if self._writer is not None:
            self._writer.write(data)

    async def outstanding(self) -> int:
        return 0

    def disconnect(self) -> None:
        if self._writer is not None:
            self._set("disconnecting")
            self._writer.close()          # the reader then reports "offline"


def _strip_iac(data: bytes) -> bytes:
    out = bytearray()
    i = 0
    while i < len(data):
        b = data[i]
        if b == IAC and i + 1 < len(data):
            cmd = data[i + 1]
            i += 3 if cmd in (251, 252, 253, 254) else 2
            continue
        out.append(b)
        i += 1
    return bytes(out)
