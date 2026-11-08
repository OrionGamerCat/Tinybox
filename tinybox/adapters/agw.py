"""Direwolf adapter using the AGWPE TCP protocol.

Direwolf does the AX.25 connected-mode work (SABM/UA, I-frames, acks,
retries). TinyBox registers the mailbox callsign with an 'X' frame;
Direwolf then accepts connects to that call and passes them to us.

AGW frame = 36 byte header (little endian) + data:
    0  port (1)   1-3 reserved
    4  kind (1)   5 reserved   6 PID (1)   7 reserved
    8  call_from (10, NUL padded)
    18 call_to   (10, NUL padded)
    28 data_len (uint32)   32 user (uint32, unused)

Frames used:
    R  version        X  register call     C  connected
    D  connected data d  disconnect        Y  outstanding frames
    M  UI frame (sent by us: chat events to TBCHAT-<n> for TinyBox clients)
    Q  link quality counters - only the TinyBox Direwolf fork knows it
       (PLANUNG.md section 14); a normal Direwolf does not answer, then TinyBox
       stops asking until the next AGW connect.
"""

from __future__ import annotations

import asyncio
import logging
import struct
import time
from collections import deque

from prcore.agw import PID_NO_L3, AgwProtocolError, Frame, read_frame, via_data
from prcore.termcolor import OK

from .. import chatimg, framemon, linkq, logsetup, texts
from ..app import App
from ..config import is_valid_call, normalize_call
from ..session import MAX_LINE, Session

log = logging.getLogger(__name__)

CTRL_Z = 0x1A
DRAIN_TIMEOUT = 120  # s to wait for the last packets before disconnecting
Y_TIMEOUT = 5
Q_TIMEOUT = 5


def decode_line(raw: bytes) -> str:
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("latin-1")  # older terminals send Latin-1 umlauts


class AgwConnection:
    """One AX.25 connection. Acts as Transport for the Session."""

    def __init__(self, adapter: "AgwAdapter", remote: str) -> None:
        self.adapter = adapter
        self.remote = remote
        self.session: Session | None = None
        self.queue: deque[bytes] = deque()
        self.outstanding = 0
        self.closing = False
        self.gone = False
        self.last_activity = time.monotonic()
        self._wakeup = asyncio.Event()
        self._y_reply = asyncio.Event()
        self._rx = bytearray()
        self._last_cr = False
        self._after_z = False
        self.pump_task: asyncio.Task | None = None
        self.quality = linkq.LinkQuality(adapter.quality_cfg)
        self.rx_bytes = 0                 # CR44: payload of this connection, for the logbook
        self.tx_bytes = 0

    @property
    def log_ctx(self) -> str:
        """Session context for the log, as soon as a session is attached (CR32)."""
        return getattr(self.session, "log_ctx", None) or logsetup.NO_SESSION

    # --- Transport interface -------------------------------------------

    def write(self, text: str) -> None:
        self.write_bytes(text.encode("utf-8"))

    def write_bytes(self, data: bytes) -> None:
        """Raw bytes (text already encoded, or compressed forwarding data)."""
        if self.gone:
            return
        self.tx_bytes += len(data)
        n = self.adapter.cfg.direwolf.paclen
        self.queue.extend(data[i:i + n] for i in range(0, len(data), n))
        self._wakeup.set()

    def close(self) -> None:
        self.closing = True
        self._wakeup.set()

    def abort_output(self) -> None:
        dropped = len(self.queue)
        self.queue.clear()
        log.debug("%s: output aborted, %d packets dropped", self.remote, dropped)

    # --- input -----------------------------------------------------------

    def feed(self, data: bytes) -> None:
        self.last_activity = time.monotonic()
        self.rx_bytes += len(data)
        if self.session is not None and hasattr(self.session, "feed_bytes"):
            if not self.session.closed:         # forward link: bytes, it splits lines itself
                self.session.feed_bytes(data)
            return
        i = 0
        while i < len(data):
            if self.session is None or self.session.closed:
                return
            need = getattr(self.session, "raw_need", 0)
            if need > 0:                       # binary data announced by the line before
                take = data[i:i + need]        # (image upload, CR12): no line splitting
                i += len(take)
                self._last_cr = self._after_z = False
                self.session.feed_raw(bytes(take))
                continue
            b = data[i]
            i += 1
            if b in (10, 13):
                if b == 10 and self._last_cr:  # CR LF -> one line end
                    self._last_cr = False
                    continue
                self._last_cr = b == 13
                if self._after_z:              # the line end right after Ctrl-Z
                    self._after_z = False
                    continue
                self._line()
                continue
            self._last_cr = False
            self._after_z = False
            if b == CTRL_Z:
                self._rx.append(b)
                self._line()
                self._after_z = True           # Ctrl-Z already ended the line
            elif len(self._rx) < MAX_LINE:
                self._rx.append(b)

    def _line(self) -> None:
        line = decode_line(bytes(self._rx))
        self._rx.clear()
        self.session.handle_line(line)

    # --- output pump with flow control ------------------------------------

    def on_outstanding(self, count: int) -> None:
        self.outstanding = count
        self._y_reply.set()

    async def _query_outstanding(self) -> None:
        self._y_reply.clear()
        self.adapter.send(Frame("Y", self.adapter.radio_port,
                                call_from=self.adapter.mycall, call_to=self.remote))
        try:
            await asyncio.wait_for(self._y_reply.wait(), Y_TIMEOUT)
        except asyncio.TimeoutError:
            log.warning("%s: no 'Y' reply from Direwolf", self.remote)
            self.outstanding = 0

    async def pump(self) -> None:
        cfg = self.adapter.cfg.direwolf
        try:
            while not self.gone:
                if not self.queue:
                    if self.closing:
                        await self._drain_and_disconnect()
                        return
                    self._wakeup.clear()
                    await self._wakeup.wait()
                    continue
                while self.queue and self.outstanding < cfg.max_outstanding:
                    self.adapter.send(Frame("D", self.adapter.radio_port, PID_NO_L3,
                                            self.adapter.mycall, self.remote,
                                            self.queue.popleft()))
                    self.outstanding += 1
                if self.queue:  # window full: wait for acks
                    await asyncio.sleep(0.5)
                    await self._query_outstanding()
        except asyncio.CancelledError:
            pass

    async def _drain_and_disconnect(self) -> None:
        deadline = time.monotonic() + DRAIN_TIMEOUT
        await self._query_outstanding()
        while self.outstanding > 0 and time.monotonic() < deadline and not self.gone:
            await asyncio.sleep(1)
            await self._query_outstanding()
        if not self.gone:
            log.info("%s: disconnecting", self.remote)
            self.adapter.send(Frame("d", self.adapter.radio_port,
                                    call_from=self.adapter.mycall, call_to=self.remote))


class AgwAdapter:
    conn_class = AgwConnection      # the KISS adapter plugs in its own connection type
    origin = "radio"                # Session.origin of incoming connects (AXUDP: "axudp")
    owns_ui = True                  # this adapter sends the chat's UI frames (the radio)

    def __init__(self, app: App) -> None:
        self.app = app
        self.cfg = app.cfg
        self.mycall = app.cfg.station.mailbox_call
        self.radio_port = app.cfg.direwolf.agw_radio_port
        self.conns: dict[str, AgwConnection] = {}
        self._pending: dict[str, asyncio.Future] = {}   # outgoing connects (forward)
        self._writer: asyncio.StreamWriter | None = None
        self.connected = asyncio.Event()  # AGW link up (used by tests)
        if self.owns_ui:
            app.service.chat.ui_send = self.send_ui
        self.quality_cfg = linkq.cfg_from(self.cfg.direwolf)
        self.q_supported: bool | None = None    # None = not known yet (per AGW connect)
        self._q_reply = asyncio.Event()
        # CR83: own sent frames from the Direwolf fork ('O'), per AGW connect
        self.own_frames = False

    def describe(self) -> str:
        """For STATUS and the web GUI."""
        dw = self.cfg.direwolf
        return f"AGW {dw.agw_host}:{dw.agw_port}"

    def send(self, frame: Frame) -> None:
        if self._writer is not None and not self._writer.is_closing():
            self._writer.write(frame.pack())
            logsetup.counters.frames_out += 1
            log.debug(">> %s len=%d to %s", frame.kind, len(frame.data),
                      frame.call_to or "-")

    def send_ui(self, dest: str, text: str, path: list[str] | None = None) -> None:
        """One UI frame (unproto) from the mailbox call, e.g. to TBCHAT-1; with
        path through digipeaters (AGW 'V': count, 10 bytes per call, data)."""
        if path:
            data = via_data([normalize_call(c) for c in path])
            self.send(Frame("V", self.radio_port, PID_NO_L3, self.mycall, dest,
                            data + text.encode("utf-8")))
        else:
            self.send(Frame("M", self.radio_port, PID_NO_L3, self.mycall, dest,
                            text.encode("utf-8")))
        # HEX view; with the fork's own frames (CR83) the frame itself is in the
        # monitor, the line then only goes into the log file
        logging.getLogger("tinybox.monitor.agw").info("UI %s > %s", dest, text,
                                                      extra={"ui_hex": text.encode("utf-8").hex(),
                                                             "framed": self.own_frames})

    # --- main loop --------------------------------------------------------

    async def run(self) -> None:
        dw = self.cfg.direwolf
        warned = False
        while True:
            try:
                reader, writer = await asyncio.open_connection(dw.agw_host, dw.agw_port)
            except OSError as exc:
                # warn once, then retry quietly until Direwolf is back
                (log.debug if warned else log.error)(
                    "Direwolf AGW %s:%d not reachable (%s), retrying every %ds",
                    dw.agw_host, dw.agw_port, exc, dw.reconnect_sec)
                warned = True
                await asyncio.sleep(dw.reconnect_sec)
                continue
            warned = False
            log.info("connected to Direwolf AGW %s:%d", dw.agw_host, dw.agw_port, extra=OK)
            self._writer = writer
            watchdog = asyncio.create_task(self._idle_watchdog())
            self.q_supported = None
            self.own_frames = False
            quality = asyncio.create_task(self._quality_poll())
            try:
                self.send(Frame("R"))
                self.send(Frame("X", self.radio_port, call_from=self.mycall))
                self._monitor_on()
                self.connected.set()
                while True:
                    frame = await read_frame(reader)
                    try:
                        self._dispatch(frame)
                    except Exception:  # one bad frame must not take the radio link down
                        log.exception("error handling AGW frame '%s' from %s",
                                      frame.kind, frame.call_from)
            except (asyncio.IncompleteReadError, ConnectionError, AgwProtocolError) as exc:
                log.error("AGW connection lost: %s", exc or type(exc).__name__)
            except Exception:
                log.exception("AGW adapter error, reconnecting")
            finally:
                self.connected.clear()
                watchdog.cancel()
                quality.cancel()
                self._drop_all()
                self._writer = None
                writer.close()
            await asyncio.sleep(dw.reconnect_sec)

    # --- incoming frames ----------------------------------------------------

    def _remote_of(self, f: Frame) -> str:
        # Direwolf: call_from = remote station, call_to = our call.
        return f.call_to if f.call_from == self.mycall else f.call_from

    def _dispatch(self, f: Frame) -> None:
        """Count and tag the frame, then handle it. The '<<' / '>>' lines are the
        layer below the session text: they show whether a line is missing on the
        frame level or above it (CR32)."""
        if f.kind in ("K", "O"):                 # CR83: monitor copies, not traffic
            self._monitor_frame(f)
            return
        logsetup.counters.frames_in += 1
        conn = self.conns.get(normalize_call(self._remote_of(f)))
        with logsetup.session_context(getattr(conn, "log_ctx", None) or logsetup.NO_SESSION):
            log.debug("<< %s len=%d from %s", f.kind, len(f.data), f.call_from or "-")
            self._handle_frame(f)

    def _handle_frame(self, f: Frame) -> None:
        if f.kind == "R":
            if len(f.data) >= 8:
                major, _, minor, _ = struct.unpack("<hhhh", f.data[:8])
                log.info("Direwolf AGW version %d.%d", major, minor)
        elif f.kind == "X":
            if f.data[:1] == b"\x01":
                log.info("mailbox call %s registered with Direwolf", self.mycall)
            else:
                log.error("Direwolf refused to register %s - already in use?", self.mycall)
        elif f.kind == "C":
            remote = normalize_call(self._remote_of(f))
            fut = self._pending.pop(remote, None)
            if fut is not None and not fut.done():
                self._on_outgoing_connected(remote, fut)
            else:
                self._on_connect(remote)
        elif f.kind == "D":
            conn = self.conns.get(self._remote_of(f))
            if conn:
                conn.feed(f.data)
        elif f.kind == "d":
            remote = normalize_call(self._remote_of(f))
            fut = self._pending.pop(remote, None)
            if fut is not None and not fut.done():
                fut.set_exception(ConnectionError(f"connect to {remote} failed"))
            # Direwolf: "*** DISCONNECTED RETRYOUT With ..." = retries used up
            self._on_disconnect(remote, lost=b"RETRYOUT" in f.data.upper())
        elif f.kind == "Y":
            conn = self.conns.get(self._remote_of(f))
            if conn and len(f.data) >= 4:
                conn.on_outstanding(struct.unpack("<I", f.data[:4])[0])
        elif f.kind == "Q":
            self._q_reply.set()
            if not self.q_supported:
                self.q_supported = True
                log.info("Direwolf with TinyBox extension: link quality available")
            conn = self.conns.get(normalize_call(self._remote_of(f)))
            counters = linkq.parse(f.data.decode("ascii", "replace"))
            if conn and counters:
                conn.quality.add(counters)
        else:
            log.debug("AGW frame '%s' ignored", f.kind)

    # --- frame monitor (CR83) ------------------------------------------------

    def _monitor_on(self) -> None:
        """CR83: frames for the web GUI's monitor, once per AGW connect (both are
        toggles in Direwolf, a new AGW connection starts with them off).
        'k' = every received frame raw ('K'), standard Direwolf.
        'O' = every frame Direwolf sends raw ('O') - only the TinyBox fork, it
        answers with an empty 'O'. A Direwolf without it prints "Unexpected
        Command" once and the monitor shows the received frames only."""
        self.send(Frame("k"))
        self.send(Frame("O"))

    def _monitor_frame(self, f: Frame) -> None:
        if f.kind == "O" and not f.data:
            if not self.own_frames:
                self.own_frames = True
                log.info("Direwolf with TinyBox extension: own frames in the monitor")
            return
        # data: one byte port/TNC (channel << 4), then the frame without FCS
        if len(f.data) < 16 or f.port != self.radio_port:
            return
        framemon.emit(f.data[1:], tx=f.kind == "O", mycall=self.mycall)

    def _on_connect(self, remote: str) -> None:
        remote = normalize_call(remote)
        if remote in self.conns:
            log.warning("%s: duplicate connect ignored", remote)
            return
        conn = self.conn_class(self, remote)
        self.conns[remote] = conn
        self.app.service.links[remote] = conn.quality
        conn.pump_task = asyncio.create_task(conn.pump())
        if not is_valid_call(remote):
            log.warning("connect from invalid call %r refused", remote)
            conn.write(texts.INVALID_CALL.format(call=remote) + "\r")
            conn.close()
            return
        other = self._connected_elsewhere(remote)
        if other:
            log.warning("%s: already connected via %s, connect refused", remote, other)
            conn.write(texts.BUSY + "\r")
            conn.close()
            return
        fwd = self.app.forward
        if fwd is not None and self.origin == "radio" and \
                fwd.partner_for_radio(remote) is not None:
            fwd.attach_agw(conn, remote)           # a partner mailbox: forward session
            return
        sysop = self._sysop_allowed(remote)
        session = Session(remote, self.app.service, self.cfg, conn, origin=self.origin,
                          sysop=sysop)
        if not self.app.registry.add(session):
            log.info("%s: busy (max_users reached)", remote)
            conn.write(texts.BUSY + "\r")
            conn.close()
            return
        conn.session = session
        with logsetup.session_context(session.log_ctx):
            log.info("%s connect, %s%s", self.origin, self.port_label(),
                     " (sysop)" if sysop else "")
            session.start()

    def port_label(self) -> str:
        return f"agw port {self.radio_port}"

    def _sysop_allowed(self, remote: str) -> bool:
        return self.cfg.station.sysop_via_radio and self.app.service.is_sysop_call(remote)

    def _connected_elsewhere(self, remote: str) -> str | None:
        """PLANUNG 25: one station once - over the radio or AXUDP, not both
        (service.links and the chat are keyed by the call)."""
        for other in (self.app.agw, getattr(self.app, "axudp", None)):
            if other is not None and other is not self and remote in other.conns:
                return other.origin
        return None

    # --- outgoing connects (forward module) ------------------------------------

    async def connect(self, remote: str, attach, via: list[str] | None = None,
                      timeout: float = 120) -> AgwConnection:
        """Connect to another station (a partner mailbox). attach(conn) is called the
        moment the link is up and must set conn.session to a line sink - before the
        first data frame is handled. Raises ConnectionError / asyncio.TimeoutError."""
        remote = normalize_call(remote)
        if not self.connected.is_set():
            raise ConnectionError("Direwolf AGW is not connected")
        if remote in self.conns or remote in self._pending:
            raise ConnectionError(f"already connected to {remote}")
        fut: asyncio.Future = asyncio.get_running_loop().create_future()
        fut.attach = attach  # type: ignore[attr-defined]
        self._pending[remote] = fut
        port = self.radio_port
        if via:
            data = via_data([normalize_call(v) for v in via])
            self.send(Frame("v", port, PID_NO_L3, self.mycall, remote, data))
        else:
            self.send(Frame("C", port, PID_NO_L3, self.mycall, remote))
        log.info("connecting to %s%s", remote, f" via {','.join(via)}" if via else "")
        started = time.monotonic()
        try:
            conn = await asyncio.wait_for(fut, timeout)
            log.info("link to %s up %s", remote, logsetup.ms(started))
            return conn
        except (asyncio.TimeoutError, ConnectionError) as exc:
            log.warning("connect to %s failed after %s: %s", remote,
                        logsetup.ms(started), exc or type(exc).__name__)
            raise
        finally:
            self._pending.pop(remote, None)

    def _on_outgoing_connected(self, remote: str, fut: asyncio.Future) -> None:
        conn = self.conn_class(self, remote)
        self.conns[remote] = conn
        self.app.service.links[remote] = conn.quality
        conn.pump_task = asyncio.create_task(conn.pump())
        fut.attach(conn)             # sink in place before the next frame arrives
        log.info("connected to %s", remote)
        fut.set_result(conn)

    def _on_disconnect(self, remote: str, lost: bool = False) -> None:
        conn = self.conns.pop(remote, None)
        if conn is None:
            return
        with logsetup.session_context(conn.log_ctx):
            self._disconnect(remote, conn, lost)

    def _disconnect(self, remote: str, conn: AgwConnection, lost: bool) -> None:
        self.app.service.links.pop(remote, None)
        conn.gone = True
        conn._wakeup.set()
        if conn.pump_task:
            conn.pump_task.cancel()
        if conn.session is not None:
            if isinstance(conn.session, Session):
                conn.session.end(lost=lost)
            else:
                conn.session.end()                  # forward link
            self.app.registry.remove(conn.session)
        log.info("%s disconnect %s%s", self.origin, remote,
                 " (connection lost)" if lost else "")

    def _drop_all(self) -> None:
        for remote in list(self.conns):
            self._on_disconnect(remote)

    # --- link quality (AGW 'Q', TinyBox Direwolf fork) ---------------------------

    def ask_quality(self, remote: str) -> None:
        """Ask Direwolf for the counters of one link (answer arrives as 'Q' frame)."""
        if self.q_supported is not False:
            self.send(Frame("Q", self.radio_port, call_from=self.mycall, call_to=remote))

    async def _quality_poll(self) -> None:
        """Every quality_poll_sec: ask Direwolf about all links, then let the chat
        boards tell their clients about changed bars (event %)."""
        every = self.cfg.direwolf.quality_poll_sec
        if every <= 0:
            return
        while True:
            await asyncio.sleep(every)
            if self.conns and self.q_supported is not False:
                self._q_reply.clear()
                for remote in list(self.conns):
                    self.ask_quality(remote)
                try:
                    await asyncio.wait_for(self._q_reply.wait(), Q_TIMEOUT)
                    await asyncio.sleep(0.5)             # the other answers
                except asyncio.TimeoutError:
                    if self.q_supported is None:
                        self.q_supported = False
                        log.info("Direwolf does not answer 'Q' (no TinyBox extension): "
                                 "link quality only from TinyBox clients until the next "
                                 "AGW connect")
            try:
                self.app.service.chat.quality_tick(self.app.service)
            except Exception:
                log.exception("link quality: chat update failed")
            self.app.bus.publish("link.quality")      # web GUI: refresh the bars

    async def _idle_watchdog(self) -> None:
        limit = self.cfg.mailbox.idle_timeout_min * 60
        while True:
            await asyncio.sleep(10)
            now = time.monotonic()
            for conn in list(self.conns.values()):
                # binary data announced but no longer coming: back to lines (CR12)
                if conn.session is not None and hasattr(conn.session, "raw_timeout"):
                    conn.session.raw_timeout(chatimg.RAW_TIMEOUT, now)
                if (conn.session and not conn.session.closed
                        and not conn.session.idle_exempt  # reading along in a chat
                        and now - conn.last_activity > limit):
                    log.info("%s: idle timeout", conn.remote)
                    conn.write(texts.IDLE_TIMEOUT + "\r")
                    conn.session.close()
