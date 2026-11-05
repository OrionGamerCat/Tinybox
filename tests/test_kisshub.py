"""kisshub: TNC dialog, KISS-TCP hub, priorities (KISS step K7).

FakePK232 plays the TNC over TCP in the states pk232py met on real devices:
command mode, autobaud after power-up, Converse, stopped by XOFF, Host Mode,
and KISS (from a previous hub run). The end-to-end test runs TinyBox ->
kisshub -> FakePK232 -> a station with its own AX.25 link.
"""

from __future__ import annotations

import asyncio
import dataclasses
import os
import tempfile
import time
import threading
import unittest
from pathlib import Path

from kisshub import config as hubconfig
from kisshub import profiles
from kisshub.hub import PRIO_CONTROL, PRIO_I, PRIO_UI, Hub, HubCfg, priority
from kisshub.tnc import BUNDLE_MAGIC, TUNNEL_MAGIC, Tnc, is_ui, pack_bundle, unpack_bundle
from prcore import termcolor
from kisshub.transport import TcpTransport
from prcore.ax25 import frame as ax
from prcore import kiss

ROOT = Path(__file__).resolve().parent.parent
EXAMPLE = (ROOT / "kisshub.conf.example").read_text(encoding="utf-8")
PK_HOST_OFF = bytes((0x01, 0x4F, ord("H"), ord("O"), ord("N"), 0x17))   # PK-232 Host Mode
EXPERT_ONLY = {"RAWHDLC", "HPOLL", "PPERSIST"}
BANNER = b"\r\nAEA PK-232M Data Controller\r\nRelease 13.SEP.95\r\ncmd:"


def load_conf(text: str, profile: str | None = None, dw: str | None = None):
    """Load a kisshub.conf text; DWDIR becomes a folder with direwolf.conf = dw."""
    with tempfile.TemporaryDirectory() as d:
        if dw is not None:
            (Path(d) / "direwolf.conf").write_text(dw, encoding="utf-8")
        p = Path(d) / "k.conf"
        p.write_text(text.replace("DWDIR", d), encoding="utf-8")
        return hubconfig.load(p, profile)


def example(profile: str | None = None, extra: str = "", dw: str | None = None):
    """kisshub.conf.example, plus own sections (e.g. [t] with base = pk232)."""
    return load_conf(EXAMPLE.replace("C:\\direwolf", "DWDIR") + "\n" + extra, profile,
                     dw if dw is not None else "")


def example_profile(name: str) -> profiles.Profile:
    return example(name).tnc.profile


def fast(p: profiles.Profile, factor: float = 0.1) -> profiles.Profile:
    """Same profile, timeouts scaled down for the tests."""
    def sc(steps):
        return tuple(dataclasses.replace(s, timeout=s.timeout * factor) for s in steps)
    return dataclasses.replace(p, wake=sc(p.wake), init=sc(p.init),
                               exit_lines=sc(p.exit_lines), settle_sec=0.05)


class FakePK232:
    """Just enough PK-232 behaviour on a TCP socket."""

    def __init__(self, state: str = "cmd") -> None:
        self.state = state          # autobaud | cmd | converse | xoff | host | kiss
        self.lines: list[str] = []
        self.transmitted: list[bytes] = []     # AX.25 frames sent "on the air"
        self.params: list[tuple[int, bytes]] = []
        self.on_air = None                     # callback(frame) for the e2e test
        self.writer: asyncio.StreamWriter | None = None
        self.connected = asyncio.Event()
        self.reject: set[str] = set()          # commands answered without a prompt
        self.expert = False
        self._line = bytearray()
        self._host = bytearray()
        self._dec = kiss.Decoder()

    async def handle(self, reader, writer) -> None:
        self.writer = writer
        self.connected.set()
        try:
            while data := await reader.read(4096):
                self.feed(data)
        except ConnectionError:
            pass
        finally:
            writer.close()

    def out(self, data: bytes) -> None:
        if self.writer is not None and not self.writer.is_closing():
            self.writer.write(data)

    def feed(self, data: bytes) -> None:
        if self.state == "kiss":
            if bytes((0xC0, 0xFF, 0xC0)) in data:              # leave KISS
                self.state = "cmd"
                return
            for port, cmd, frame in self._dec.feed(data):
                if cmd == kiss.CMD_DATA:
                    self.transmitted.append(frame)
                    if self.on_air:
                        self.on_air(frame)
                else:
                    self.params.append((cmd, frame))
            return
        if self.state == "host":
            self._host += data
            if PK_HOST_OFF in self._host:
                self.state, self._host = "cmd", bytearray()
            return
        for b in data:
            self._byte(b)

    def _byte(self, b: int) -> None:
        if self.state == "autobaud":
            if b == ord("*"):
                self.state = "cmd"
                self.out(BANNER)
            return
        if self.state == "xoff":
            self.out(bytes((b,)))                                # echo, nothing else
            if b == 0x11:
                self.state = "cmd"
            return
        if self.state == "converse":
            if b == 0x03:
                self.state = "cmd"
            return
        if b == 13:
            text = self._line.decode("ascii", "replace").strip("\x00\x03\x11* ")
            self._line.clear()
            self._command(text)
        elif 32 <= b < 127:
            self._line.append(b)
            self.out(bytes((b,)))                                # echo

    def _command(self, text: str) -> None:
        if not text:
            self.out(b"\r\ncmd:")
            return
        self.lines.append(text)
        if text in self.reject:
            self.out(b"\r\n?bad\r\n")
            return
        if text == "EXPERT ON":
            self.expert = True
        if text.split()[0] in EXPERT_ONLY and not self.expert:
            self.out(b"\r\n?EXPERT command\r\ncmd:")     # pk232py hw_logs, T175
            return
        if text == "RESTART":
            self.out(BANNER)
        elif text == "HOST ON" and "KISS ON" in self.lines:
            self.state = "kiss"
        elif text == "HOST ON":
            self.state = "host"
        elif text == "KISS ON":
            pass                     # the real PK-232 gives no cmd: here (17.10.2026)
        else:
            self.out(b"\r\ncmd:")

    def receive(self, frame: bytes) -> None:
        """A frame heard on the air: to the host as KISS."""
        self.out(kiss.encode(frame))


class HubTestBase(unittest.IsolatedAsyncioTestCase):
    profile = fast(example_profile("pk232"))

    async def start_hub(self, fake: FakePK232, **hubkw) -> Hub:
        self.fake = fake
        self.tnc_server = await asyncio.start_server(fake.handle, "127.0.0.1", 0)
        tport = self.tnc_server.sockets[0].getsockname()[1]
        params = {kiss.CMD_TXDELAY: 30, kiss.CMD_P: 63}

        def factory(on_frame):
            return Tnc(self.profile, TcpTransport("127.0.0.1", tport), on_frame,
                       reconnect_sec=0.2, params=params)

        hubkw.setdefault("status_port", -1)            # -1 = any free port (tests)
        cfg = HubCfg(port=0, air_baud=hubkw.pop("air_baud", 1_000_000),
                     txdelay_sec=hubkw.pop("txdelay_sec", 0.0), status_every_sec=0, **hubkw)
        self.hub = Hub(cfg, factory)
        await self.hub.start()
        return self.hub

    async def asyncTearDown(self):
        await self.hub.stop()
        self.tnc_server.close()
        await self.tnc_server.wait_closed()

    async def wait(self, cond, timeout: float = 5.0) -> None:
        loop = asyncio.get_running_loop()
        end = loop.time() + timeout
        while not cond():
            if loop.time() > end:
                raise AssertionError("timed out")
            await asyncio.sleep(0.01)

    async def client(self):
        reader, writer = await asyncio.open_connection("127.0.0.1", self.hub.port)
        got: list[bytes] = []
        dec = kiss.Decoder()

        async def pump():
            while data := await reader.read(4096):
                got.extend(f for _, c, f in dec.feed(data) if c == kiss.CMD_DATA)
        task = asyncio.create_task(pump())
        self.addAsyncCleanup(self._close, writer, task)
        await self.wait(lambda: len(self.hub.clients) >= 1)
        return writer, got

    @staticmethod
    async def _close(writer, task):
        writer.close()
        task.cancel()


class TncDialogTests(HubTestBase):
    async def test_init_from_command_mode(self):
        await self.start_hub(FakePK232("cmd"))
        await asyncio.wait_for(self.hub.tnc.ready.wait(), 5)
        self.assertEqual(self.fake.lines, [s.note for s in example_profile("pk232").init])
        self.assertIn("VHF ON", self.fake.lines)
        self.assertEqual(self.fake.lines[0], "EXPERT ON")
        self.assertEqual(self.fake.lines[-2:], ["KISS ON", "HOST ON"])
        await self.wait(lambda: len(self.fake.params) == 2)
        self.assertEqual(self.fake.params, [(kiss.CMD_TXDELAY, bytes((30,))),
                                            (kiss.CMD_P, bytes((63,)))])

    async def test_wakes_from_every_state(self):
        for state in ("autobaud", "converse", "xoff", "host", "kiss"):
            with self.subTest(state=state):
                await self.start_hub(FakePK232(state))
                await asyncio.wait_for(self.hub.tnc.ready.wait(), 10)
                self.assertEqual(self.fake.lines[-1], "HOST ON")
                await self.asyncTearDown()

    async def test_failing_init_line_is_reported_and_retried(self):
        fake = FakePK232("cmd")
        fake.reject = {"PACKET"}
        with self.assertLogs("kisshub.tnc", "ERROR") as logs:
            await self.start_hub(fake)
            await self.wait(lambda: fake.lines.count("PACKET") >= 2, 10)
        self.assertIn("PACKET", "\n".join(logs.output))
        self.assertIn("?bad", "\n".join(logs.output))
        self.assertFalse(self.hub.tnc.ready.is_set())

    async def test_expert_command_refused_stops_the_init(self):
        """Without EXPERT ON the PK-232 says '?EXPERT command' and still prompts:
        that must stop the init, not end in a half set-up KISS."""
        self.profile = dataclasses.replace(
            self.profile, init=tuple(s for s in self.profile.init if s.note != "EXPERT ON"))
        fake = FakePK232("cmd")
        with self.assertLogs("kisshub.tnc", "ERROR") as logs:
            await self.start_hub(fake)
            await self.wait(lambda: any("EXPERT command" in o for o in logs.output), 10)
        self.assertIn("RAWHDLC ON", "\n".join(logs.output))
        self.assertNotIn("KISS ON", fake.lines)
        self.assertFalse(self.hub.tnc.ready.is_set())

    async def test_stop_leaves_kiss_and_switches_it_off(self):
        await self.start_hub(FakePK232("cmd"))
        await asyncio.wait_for(self.hub.tnc.ready.wait(), 5)
        await self.hub.tnc.stop()
        await self.wait(lambda: self.fake.state == "cmd" and "KISS OFF" in self.fake.lines)

    async def test_ctrl_c_still_leaves_kiss(self):
        """Ctrl+C cancels the hub's tasks before stop() runs: the TNC task must not
        close the port then, or stop() can no longer switch the TNC out of KISS."""
        await self.start_hub(FakePK232("cmd"))
        await asyncio.wait_for(self.hub.tnc.ready.wait(), 5)
        for t in self.hub._tasks:
            t.cancel()
        await asyncio.gather(*self.hub._tasks, return_exceptions=True)
        self.assertEqual(self.hub.tnc.state, "kiss")
        with self.assertLogs("kisshub.tnc", "INFO") as logs:
            await self.hub.stop()
        self.assertIn("leaving KISS mode", "\n".join(logs.output))
        await self.wait(lambda: self.fake.state == "cmd" and "KISS OFF" in self.fake.lines)

    async def test_tnc_lost_and_back(self):
        await self.start_hub(FakePK232("cmd"))
        await asyncio.wait_for(self.hub.tnc.ready.wait(), 5)
        self.fake.connected.clear()
        self.fake.writer.close()
        await self.wait(lambda: not self.hub.tnc.ready.is_set())
        await asyncio.wait_for(self.fake.connected.wait(), 5)
        await asyncio.wait_for(self.hub.tnc.ready.wait(), 10)   # woken from KISS again


class HubTests(HubTestBase):
    async def test_frames_to_all_clients_and_mirror(self):
        await self.start_hub(FakePK232("cmd"))
        await asyncio.wait_for(self.hub.tnc.ready.wait(), 5)
        w1, got1 = await self.client()
        w2, got2 = await self.client()
        await self.wait(lambda: len(self.hub.clients) == 2)
        heard = ax.ui_frame("APRS", "OE1ABC", b"!test").encode()
        self.fake.receive(heard)
        await self.wait(lambda: got1 == [heard] and got2 == [heard])
        mine = ax.ui_frame("TBCHAT-1", "OE3GAS-1", b"hi").encode()
        w1.write(kiss.encode(mine) + kiss.encode_param(kiss.CMD_TXDELAY, 1))
        await self.wait(lambda: self.fake.transmitted == [mine] and len(got2) == 2)
        self.assertEqual(got2[-1], mine)                          # client 2 "hears" it
        self.assertEqual(got1, [heard])                           # not echoed to sender
        self.assertNotIn((kiss.CMD_TXDELAY, b"\x01"), self.fake.params)

    async def test_garbage_address_dropped(self):
        """CR74: noise whose checksum passed in the TNC never reaches the clients."""
        await self.start_hub(FakePK232("cmd"))
        await asyncio.wait_for(self.hub.tnc.ready.wait(), 5)
        _, got = await self.client()
        good = ax.ui_frame("APRS", "OE1ABC", b"!test").encode()
        noise = bytes(b << 1 for b in b"^\x1bkDa\x7f") + b"\x70" + good[7:]   # source '^?kDa?-8'
        lower = good.replace(bytes(b << 1 for b in b"OE1ABC"), bytes(b << 1 for b in b"OE1aBC"))
        for f in (noise, lower, good):
            self.fake.receive(f)
        await self.wait(lambda: got == [good])
        self.assertEqual(self.hub.invalid, 2)
        self.assertEqual(self.hub.status_dict()["queue"]["invalid"], 2)
        self.assertIn("invalid 2", self.hub.status())

    async def test_acknowledgement_overtakes_ui_frames(self):
        # 1200 Bd, 0.3 s lead: only about one 100-byte frame at a time goes to the TNC
        await self.start_hub(FakePK232("cmd"), air_baud=1200, txdelay_sec=0.0,
                             max_lead_sec=0.3)
        await asyncio.wait_for(self.hub.tnc.ready.wait(), 5)
        pages = [ax.ui_frame("BROCST", "OE3GAS-2", bytes([i]) * 100).encode()
                 for i in range(5)]
        for p in pages:
            self.hub.enqueue(p)
        await self.wait(lambda: len(self.fake.transmitted) >= 1)
        rr = ax.s_frame("RR", "OE1ABC", "OE3GAS-1", 3).encode()
        self.hub.enqueue(rr)
        await self.wait(lambda: len(self.fake.transmitted) == 6, 15)
        self.assertLess(self.fake.transmitted.index(rr), 3)

    async def test_priority_classes(self):
        self.assertEqual(priority(ax.s_frame("RR", "A1A", "B1B", 1).encode()), PRIO_CONTROL)
        self.assertEqual(priority(ax.u_frame("UA", "A1A", "B1B", command=False).encode()),
                         PRIO_CONTROL)
        self.assertEqual(priority(ax.u_frame("SABME", "A1A", "B1B").encode()), PRIO_CONTROL)
        self.assertEqual(priority(ax.i_frame("A1A", "B1B", 0, 0, b"x").encode()), PRIO_I)
        self.assertEqual(priority(ax.i_frame("A1A", "B1B", 0, 0, b"x", modulo=128).encode()),
                         PRIO_I)
        self.assertEqual(priority(ax.ui_frame("A1A", "B1B", b"x").encode()), PRIO_UI)
        self.assertEqual(priority(b"\x00garbage"), PRIO_UI)
        self.hub = None

    async def asyncTearDown(self):
        if self.hub is not None:
            await super().asyncTearDown()


class EndToEndTests(HubTestBase):
    async def test_tinybox_over_kisshub_and_pk232(self):
        """TinyBox (KissAdapter) -> kisshub -> PK-232 -> air -> a station."""
        from tinybox.adapters import kiss as kissadapter
        from prcore.ax25.link import Ax25Link
        from tests.test_kiss_adapter import kiss_app, station_cfg

        fake = FakePK232("kiss")                       # left in KISS by a previous run
        await self.start_hub(fake)
        await asyncio.wait_for(self.hub.tnc.ready.wait(), 10)
        loop = asyncio.get_running_loop()
        st = Ax25Link("OE1ABC", "OE3GAS-1", cfg=station_cfg("2.0"), now=loop.time())
        rx = bytearray()
        events = []

        def pump():
            for f in st.pop_output():
                fake.receive(f.encode())
            for e in st.pop_events():
                events.append(e)
                if e[0] == "data":
                    rx.extend(e[1])

        def on_air(raw):
            dest, *_ = ax.peek(raw)
            if dest == "OE1ABC":
                st.receive(ax.Frame.decode(raw, st.modulo), loop.time())
                pump()
        fake.on_air = on_air

        async def ticks():
            while True:
                await asyncio.sleep(0.02)
                d = st.next_deadline()
                if d is not None and d <= loop.time():
                    st.tick(loop.time())
                    pump()
        ticker = asyncio.create_task(ticks())

        app = kiss_app(self.hub.port, "2.2")
        adapter = kissadapter.KissAdapter(app)
        app.agw = adapter
        task = asyncio.create_task(adapter.run())
        try:
            await asyncio.wait_for(adapter.connected.wait(), 5)
            st.connect(loop.time())
            pump()
            await self.wait(lambda: b"hello" in rx, 10)
            st.send(b"S OE3GAS\rVia PK-232\rKISS works\r/EX\rB\r", loop.time())
            pump()
            await self.wait(lambda: any(e[0] == "disconnected" for e in events), 20)
        finally:
            task.cancel()
            ticker.cancel()
            await asyncio.gather(task, ticker, return_exceptions=True)
        self.assertIn(b"Msg 1 saved.", bytes(rx))
        self.assertEqual(app.store.get(1).body, "KISS works")
        kinds = [ax.Frame.decode(f).kind for f in fake.transmitted[:1]]
        self.assertEqual(kinds, ["UA"])                # v2.0 station called with SABM


class FakeTMD710(FakePK232):
    """Kenwood TM-D710 TNC in PACKET mode: HBAUD, KISS ON, RESTART (Gerhard,
    22.10.2026). 'aprs': TNC key in APRS position - the TNC gives no cmd:."""

    def __init__(self, state: str = "cmd") -> None:
        super().__init__(state)
        self.kiss_on = False
        self.hbaud = 9600

    def _byte(self, b: int) -> None:
        if self.state == "aprs":
            return
        super()._byte(b)

    def _command(self, text: str) -> None:
        if not text:
            self.out(b"\r\ncmd:")
            return
        self.lines.append(text)
        word, _, arg = text.partition(" ")
        if word == "HBAUD":
            self.out(f"\r\nHBAUD was {self.hbaud}\r\ncmd:".encode())
            self.hbaud = int(arg)
        elif text == "KISS ON":
            self.out(b"\r\nKISS was OFF\r\ncmd:")
            self.kiss_on = True
        elif text == "KISS OFF":
            self.out(b"\r\nKISS was ON\r\ncmd:")
            self.kiss_on = False
        elif text == "RESTART":
            if self.kiss_on:
                self.state = "kiss"
            else:
                self.out(b"\r\nTM-D710 TNC\r\ncmd:")
        else:
            self.out(b"\r\n?EH\r\ncmd:")


class TmD710Tests(HubTestBase):
    profile = fast(example_profile("tm-d710"))

    async def test_init_hbaud_kiss_restart(self):
        await self.start_hub(FakeTMD710("cmd"))
        await asyncio.wait_for(self.hub.tnc.ready.wait(), 5)
        self.assertEqual(self.fake.lines, ["HBAUD 1200", "KISS ON", "RESTART"])
        self.assertEqual((self.fake.state, self.fake.hbaud), ("kiss", 1200))
        await self.wait(lambda: len(self.fake.params) == 2)

    async def test_wakes_from_kiss_and_converse(self):
        for state in ("kiss", "converse", "xoff"):
            with self.subTest(state=state):
                await self.start_hub(FakeTMD710(state))
                await asyncio.wait_for(self.hub.tnc.ready.wait(), 10)
                self.assertEqual(self.fake.lines[-1], "RESTART")
                await self.asyncTearDown()

    async def test_aprs_mode_gives_the_hint(self):
        with self.assertLogs("kisshub.tnc", "ERROR") as logs:
            await self.start_hub(FakeTMD710("aprs"))
            await self.wait(lambda: any("PACKET" in o for o in logs.output), 10)
        self.assertFalse(self.hub.tnc.ready.is_set())

    async def test_stop_leaves_kiss_and_switches_it_off(self):
        await self.start_hub(FakeTMD710("cmd"))
        await asyncio.wait_for(self.hub.tnc.ready.wait(), 5)
        await self.hub.tnc.stop()
        await self.wait(lambda: self.fake.state == "cmd" and not self.fake.kiss_on)


class FakeSerial:
    """pyserial stand-in for the RTS/CTS writer: CTS follows a script of
    (start, end) low phases in seconds from creation."""
    def __init__(self, cts_low_sec: float = 0.0, low=(), fail_write: bool = False):
        self.t0 = time.monotonic()
        self.low = list(low) + ([(0.0, cts_low_sec)] if cts_low_sec else [])
        self.written = []
        self.flushes = 0
        self.fail_write = fail_write

    @property
    def cts(self) -> bool:
        t = time.monotonic() - self.t0
        return not any(a <= t < b for a, b in self.low)

    def write(self, data):
        if self.fail_write:
            raise OSError("device unplugged")
        assert self.cts, "written while CTS low"
        self.written.append(bytes(data))

    def flush(self):
        self.flushes += 1


class RtsCtsWriterTests(unittest.TestCase):
    def transport(self, ser):
        from kisshub.transport import SerialTransport
        t = SerialTransport("COM7", 9600, rtscts=True)
        t._ser = ser
        return t

    def run_writer(self, ser, data):
        t = self.transport(ser)
        t.write(data)
        th = threading.Thread(target=t._writer, daemon=True)
        th.start()
        deadline = time.monotonic() + 3
        while sum(map(len, ser.written)) < len(data) and time.monotonic() < deadline:
            time.sleep(0.01)
        t._stop.set()
        th.join(1)
        return t

    def test_small_pieces_each_flushed_and_waits_for_cts(self):
        ser = FakeSerial(cts_low_sec=0.2)
        t = self.run_writer(ser, bytes(200))
        self.assertEqual([len(c) for c in ser.written], [32] * 6 + [8])
        self.assertEqual(ser.flushes, 7)               # every piece out before the next check
        f = t.flow_status()
        self.assertEqual((f["flow"], f["cts_waits"], f["tx_bytes"]), ("rtscts", 1, 200))
        self.assertGreaterEqual(f["cts_wait_s"], 0.1)

    def test_stop_while_cts_low(self):
        t = self.transport(FakeSerial(cts_low_sec=60))
        t._stop.set()
        self.assertFalse(t._wait_cts())

    def test_monitor_counts_every_low_phase(self):
        ser = FakeSerial(low=[(0.05, 0.10), (0.20, 0.35)])
        t = self.transport(ser)
        th = threading.Thread(target=t._cts_monitor, daemon=True)
        with self.assertLogs("kisshub.transport", "DEBUG") as logs:
            th.start()
            time.sleep(0.5)
            t._stop.set()
            th.join(1)
        f = t.flow_status()
        self.assertEqual(f["cts_drops"], 2)
        self.assertAlmostEqual(f["cts_low_s"], 0.2, delta=0.06)
        self.assertAlmostEqual(f["cts_low_max_ms"], 150, delta=40)
        self.assertEqual(sum("CTS low" in o for o in logs.output), 2)
        self.assertEqual(sum("CTS high again" in o for o in logs.output), 2)

    def test_monitor_sees_cts_never_drop(self):
        t = self.transport(FakeSerial())
        th = threading.Thread(target=t._cts_monitor, daemon=True)
        th.start()
        time.sleep(0.1)
        t._stop.set()
        th.join(1)
        self.assertEqual((t.cts_drops, t.cts_low_s), (0, 0.0))

    def test_write_error_reopens_the_port(self):
        async def go():
            t = self.transport(FakeSerial(fail_write=True))
            t._loop, t._rx = asyncio.get_running_loop(), asyncio.Queue()
            t.write(b"\xc0\x00abc\xc0")
            th = threading.Thread(target=t._writer, daemon=True)
            with self.assertLogs("kisshub.transport", "WARNING"):
                th.start()
                with self.assertRaises(ConnectionError):
                    await asyncio.wait_for(t.read(), 2)
            t._stop.set()
            th.join(1)
            self.assertFalse(th.is_alive())
        asyncio.run(go())

    @unittest.skipUnless(hasattr(os, "openpty"), "termios only on Linux/macOS")
    def test_driver_rtscts_reads_termios(self):
        import termios
        from kisshub.transport import driver_rtscts
        master, slave = os.openpty()
        try:
            class Port:
                def fileno(self):
                    return slave
            attrs = termios.tcgetattr(slave)
            attrs[2] |= termios.CRTSCTS
            termios.tcsetattr(slave, termios.TCSANOW, attrs)
            self.assertIs(driver_rtscts(Port()), True)
            attrs[2] &= ~termios.CRTSCTS
            termios.tcsetattr(slave, termios.TCSANOW, attrs)
            self.assertIs(driver_rtscts(Port()), False)
        finally:
            os.close(master)
            os.close(slave)
        self.assertIsNone(driver_rtscts(object()))


class HubConfigTests(unittest.TestCase):
    """kisshub 2026.11.05: one section per TNC, every value from the conf."""

    def test_example_default_profile(self):
        cfg = hubconfig.load(ROOT / "kisshub.conf.example")
        self.assertEqual((cfg.tnc.profile.name, cfg.tnc.device, cfg.hub.port),
                         ("pk232", "COM3", 8101))
        self.assertEqual(cfg.tnc.params[kiss.CMD_TXDELAY], 30)

    def test_example_every_tnc_loads(self):
        names = [n for n, _, _ in hubconfig.profile_list(ROOT / "kisshub.conf.example")]
        self.assertEqual(names, ["pk232", "tm-d710", "tm-d710-9k6", "tnc7multi",
                                 "tnc7multi-9k6", "th-d74", "th-d75", "tnc2-kiss", "generic",
                                 "vara-fm", "vara-hf", "direwolf", "modem73"])
        for name in names:
            if name == "modem73":               # N0CALL in the example - its own test
                continue
            with self.subTest(name):
                self.assertEqual(example(name).tnc.profile.name, name)

    def test_pk232_dialog_from_conf(self):
        p = example_profile("pk232")
        self.assertEqual(p.wake[0], profiles.Step(
            b"*", (b"cmd:", b"AEA", b"PK-232", b"Copyright"), 2.0, "*"))
        self.assertEqual(p.wake[4].send, b"\xc0\xff\xc0\x00\x00")
        self.assertEqual(p.wake[4].expect, ())
        self.assertEqual(p.wake[6].send, bytes((1, 1, 0x4F, 71, 71, 0x17)) + PK_HOST_OFF)
        self.assertEqual(p.init[0], profiles.Step(b"EXPERT ON\r", (b"cmd:",), 3.0, "EXPERT ON"))
        self.assertEqual(p.init[-1], profiles.Step(b"HOST ON\r", (), 1.5, "HOST ON"))
        self.assertEqual([s.send for s in p.exit_lines], [b"KISS OFF\r"])
        self.assertEqual((p.exit_kiss, p.dtr, p.rts, p.rtscts), (True, True, True, False))

    def test_example_tm_d710(self):
        cfg = example("tm-d710")
        self.assertEqual((cfg.tnc.profile.name, cfg.tnc.device, cfg.tnc.serial_baud),
                         ("tm-d710", "COM7", 9600))
        self.assertEqual([s.note for s in cfg.tnc.profile.init], ["HBAUD 1200", "KISS ON", "RESTART"])
        self.assertEqual(cfg.hub.ax25["t1_min_sec"], 3.0)
        self.assertEqual(cfg.hub.sources["air_baud"], "kisshub.conf [tm-d710]")

    def test_tm_d710_9600_via_base(self):
        cfg = example("tm-d710-9k6")
        init = cfg.tnc.profile.init
        self.assertEqual([s.note for s in init], ["HBAUD 9600", "KISS ON", "RESTART"])
        self.assertEqual((init[0].send, init[0].expect), (b"HBAUD 9600\r", (b"cmd:",)))
        self.assertEqual((cfg.hub.ax25["maxframe"], cfg.hub.ax25["t1_min_sec"]), (7, 1.5))
        self.assertEqual((cfg.tnc.device, cfg.tnc.rtscts), ("COM7", True))   # from base

    def test_tm_d710_hbaud_invalid(self):
        with self.assertRaises(hubconfig.ConfigError) as cm:
            example("t", "[t]\nbase = tm-d710\nair_baud = 4800\n")
        self.assertIn("1200 or 9600", str(cm.exception))

    def test_pk232_hbaud_stays_fixed(self):
        cfg = example("t", "[t]\nbase = pk232\nair_baud = 9600\n")
        self.assertIn("HBAUD 1200", [s.note for s in cfg.tnc.profile.init])

    def test_rtscts_from_the_section(self):
        self.assertTrue(example("tm-d710").tnc.rtscts)
        self.assertFalse(example("pk232").tnc.rtscts)
        self.assertTrue(example("t", "[t]\nbase = pk232\nrtscts = yes\n").tnc.rtscts)
        t = hubconfig.make_transport(example("tm-d710").tnc)
        self.assertEqual((t.rtscts, t.describe()), (True, "COM7 9600 Bd RTS/CTS"))

    def test_own_profile_name_and_dialog(self):
        cfg = example("my-tnc", "[my-tnc]\nbase = generic\ntransport = tcp\nport = 4001\n"
                                "prompt = cmd:\nstep_timeout = 2\n"
                                "init =\n    A ONE\n    B TWO  ! OK  @5\n    KISS ON  !-\n")
        p = cfg.tnc.profile
        self.assertEqual((p.name, cfg.tnc.port, p.notes), ("my-tnc", 4001, "already in KISS"))
        self.assertEqual([(s.send, s.expect, s.timeout) for s in p.init],
                         [(b"A ONE\r", (b"cmd:",), 2.0), (b"B TWO\r", (b"OK",), 5.0),
                          (b"KISS ON\r", (), 2.0)])
        self.assertEqual(cfg.log_file, "kisshub-my-tnc.log")

    def test_notation(self):
        self.assertEqual(profiles.encode("^C<CR>x<c0><LF>^q"), b"\x03\rx\xc0\n\x11")
        st = profiles.parse_steps("  <CR>  @1.5\n\n  *  ! a b\n", cr=False, prompt="cmd:",
                                  timeout=3.0, what="w")
        self.assertEqual(st, (profiles.Step(b"\r", (b"cmd:",), 1.5, "<CR>"),
                              profiles.Step(b"*", (b"a", b"b"), 3.0, "*")))
        with self.assertRaises(profiles.ProfileError):           # no prompt to wait for
            profiles.parse_steps("X", cr=True, prompt="", timeout=1, what="w")
        with self.assertRaises(profiles.ProfileError):
            profiles.parse_steps("  ! cmd:", cr=True, prompt="cmd:", timeout=1, what="w")

    def test_old_format_refused(self):
        for text in ("[tnc]\nprofile=pk232\ndevice=COM1\n",
                     "[pk232]\ntype=tnc\n[kiss.pk232]\ntxdelay_ms=400\n",
                     "[ax25]\npaclen=128\n"):
            with self.assertRaises(hubconfig.ConfigError, msg=text) as cm:
                load_conf(text, "pk232")
            self.assertIn("old format", str(cm.exception))

    def test_missing_keys_named_together(self):
        with self.assertRaises(hubconfig.ConfigError) as cm:
            load_conf("[x]\ntype = tnc\ntransport = serial\n", "x")
        msg = str(cm.exception)
        for key in ("device", "serial_baud", "air_baud", "txdelay_ms", "paclen", "t2_sec",
                    "send_params", "exit_kiss", "settle_sec"):
            self.assertIn(key, msg)
        # step_timeout only when there is a dialog
        with self.assertRaises(hubconfig.ConfigError) as cm:
            example("t", "[t]\nbase = th-d74\nstep_timeout =\ninit =\n    KISS ON !-\n")
        self.assertIn("step_timeout", str(cm.exception))

    def test_invalid(self):
        for text, profile in (
                ("", "pk9999"),                                        # no such section
                ("[t]\nbase = pk232\nwindow = 3\n", "t"),              # unknown key
                ("[t]\nbase = pk232\nvara_tunnel = all\n", "t"),       # VARA key on a TNC
                ("[t]\nbase = pk232\ntype = radio\n", "t"),            # unknown type
                ("[t]\nbase = pk232\npersist = 300\n", "t"),
                ("[t]\nbase = pk232\ntransport = tcp\n", "t"),         # no port
                ("[t]\nbase = u\n[u]\nbase = t\n", "t"),                # base loop
                ("[t]\nbase = nix\n", "t"),
                ("[kisshub]\nprofil = pk232\n", None)):                 # [kisshub] typo
            with self.assertRaises(hubconfig.ConfigError, msg=text):
                example(profile, text)

    def test_no_profile_given(self):
        text = EXAMPLE.replace("profile = pk232", "")
        with self.assertRaises(hubconfig.ConfigError) as cm:
            load_conf(text)
        self.assertIn("-p NAME", str(cm.exception))

    def test_list(self):
        import contextlib
        import io
        from kisshub.__main__ import run
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(run(["-c", str(ROOT / "kisshub.conf.example"), "-l"]), 0)
        self.assertIn("vara-hf", out.getvalue())
        self.assertIn("direwolf", out.getvalue())


class FakeVara:
    """VARA's KISS-TCP port as found on 17.10.2026: type 0 takes UI frames only
    ("Wrong KISS frame" for the rest), type 2 takes any bytes."""

    def __init__(self) -> None:
        self.type0: list[bytes] = []
        self.type2: list[bytes] = []
        self.wrong = 0
        self.writer: asyncio.StreamWriter | None = None
        self._dec = kiss.Decoder()

    async def handle(self, reader, writer) -> None:
        self.writer = writer
        try:
            while data := await reader.read(4096):
                for port, cmd, frame in self._dec.feed(data):
                    if cmd == 0 and port == 0:
                        if is_ui(frame):
                            self.type0.append(frame)
                        else:
                            self.wrong += 1
                    elif cmd == 2 and port == 0:
                        self.type2.append(frame)
        except (ConnectionError, OSError):
            pass
        finally:
            writer.close()

    def out(self, kind: int, data: bytes) -> None:
        self.writer.write(kiss.encode(data, 0, kind))


class VaraTunnelTests(HubTestBase):
    profile = example_profile("vara-fm")

    async def test_connected_frames_go_through_type_2(self):
        vara = FakeVara()
        await self.start_hub(vara)
        await asyncio.wait_for(self.hub.tnc.ready.wait(), 5)
        w, got = await self.client()
        sabme = ax.u_frame("SABME", "OE3GAS-1", "OE3GAS", pf=True).encode()
        ui = ax.ui_frame("TEST", "OE3GAS", b"hello vara").encode()
        w.write(kiss.encode(sabme) + kiss.encode(ui))
        await self.wait(lambda: vara.type2 and vara.type0)
        self.assertEqual(vara.type2, [TUNNEL_MAGIC + sabme])     # unchanged inside
        self.assertEqual(vara.type0, [ui])                       # UI stays readable
        self.assertEqual(vara.wrong, 0)
        self.assertFalse(self.hub.tnc.set_param(kiss.CMD_P, 63))   # console: not to VARA
        # the other station's answer comes back through type 2 -> a normal frame
        ua = ax.u_frame("UA", "OE3GAS", "OE3GAS-1", command=False, pf=True).encode()
        vara.out(2, TUNNEL_MAGIC + ua)
        await self.wait(lambda: got == [ua])
        # VARA hands our own frame back: dropped; type-2 data of others: ignored
        vara.out(2, TUNNEL_MAGIC + sabme)
        vara.out(2, b"HE0\rsomebody's VarAC data")
        heard = ax.ui_frame("CQ", "OE1ABC", b"vara ui").encode()
        vara.out(0, heard)
        await self.wait(lambda: len(got) == 2)
        self.assertEqual(got, [ua, heard])
        st = self.hub.tnc.status()
        self.assertEqual((st["tunnel"], st["tunnel_tx"], st["tunnel_rx"], st["echoes"],
                          st["foreign"]), ("connected", 1, 1, 1, 1))

    async def test_bundling(self):
        vara = FakeVara()
        self.profile = dataclasses.replace(example_profile("vara-fm"), bundle_ms=100, bundle_max=250)
        await self.start_hub(vara, max_lead_sec=60)
        await asyncio.wait_for(self.hub.tnc.ready.wait(), 5)
        w, got = await self.client()
        frames = [ax.i_frame("OE3GAS-1", "OE3GAS", n, 0, bytes([65 + n]) * 60,
                             modulo=128).encode() for n in range(4)]
        ui = ax.ui_frame("TEST", "OE3GAS", b"stays type 0").encode()
        for f in frames:
            self.hub.enqueue(f)
        self.hub.enqueue(ui)
        await self.wait(lambda: len(vara.type2) == 2 and vara.type0)
        # 4 x (2 + 77) bytes: three fit into 250, the fourth goes alone
        self.assertEqual(unpack_bundle(vara.type2[0]), frames[:3])
        self.assertEqual(vara.type2[1], TUNNEL_MAGIC + frames[3])
        self.assertEqual(vara.type0, [ui])
        st = self.hub.tnc.status()
        self.assertEqual((st["bundles_tx"], st["bundled_tx"], st["tunnel_tx"]), (1, 3, 4))
        # the other station's bundle is unpacked into single frames for the clients
        answers = [ax.s_frame("RR", "OE3GAS", "OE3GAS-1", n, modulo=128).encode()
                   for n in (1, 2)]
        vara.out(2, pack_bundle(answers))
        vara.out(2, BUNDLE_MAGIC + b"\x00\x40broken")
        await self.wait(lambda: len(got) >= 2)
        await asyncio.sleep(0.05)
        self.assertEqual(got[-2:], answers)
        st = self.hub.tnc.status()
        self.assertEqual((st["bundles_rx"], st["bundled_rx"], st["foreign"]), (1, 2, 1))

    async def test_all_and_no(self):
        vara = FakeVara()
        self.profile = dataclasses.replace(example_profile("vara-fm"), tunnel="all")
        await self.start_hub(vara)
        await asyncio.wait_for(self.hub.tnc.ready.wait(), 5)
        ui = ax.ui_frame("TEST", "OE3GAS", b"x").encode()
        self.hub.enqueue(ui)
        await self.wait(lambda: vara.type2)
        self.assertEqual((vara.type2, vara.type0), ([TUNNEL_MAGIC + ui], []))
        self.assertFalse(is_ui(ax.u_frame("SABM", "A1A", "B1B").encode()))
        self.assertTrue(is_ui(ax.ui_frame("A1A", "B1B", b"", path=["C1C", "D1D"]).encode()))



class StartBlockTests(unittest.TestCase):
    """The start block (and console I) fits into 80 columns."""

    def test_lines_fit_80_columns(self):
        from kisshub.__main__ import PREFIX_WIDTH, start_items
        for name in ("tnc7multi", "vara-fm", "pk232", "direwolf"):
            with self.subTest(name):
                items = start_items("k.conf", example(name))
                for x in items:
                    if x is None or isinstance(x, str) or (len(x) > 3 and x[3]):
                        continue
                    line = termcolor.kv_plain(*x[:3])
                    if " " in str(x[1]) or not x[0]:         # paths stay in one piece
                        self.assertLessEqual(PREFIX_WIDTH + len(line), 80, line)

    def test_wrap(self):
        from kisshub.__main__ import wrap_items
        items = wrap_items([("Label", "one two three four five six", "(a note)")], width=12)
        self.assertEqual(items, [("Label", "one two", ""), ("", "three four", ""),
                                 ("", "five six", ""), ("", "(a note)")])
        self.assertEqual(wrap_items([("L", "short", "(n)")], width=20), [("L", "short", "(n)")])
        link = ("Status query", "http://127.0.0.1:8102/status", "", True)
        self.assertEqual(wrap_items([link, None, "plain"], width=5), [link, None, "plain"])
        self.assertEqual(termcolor.kv_plain("", "x"), " " * termcolor.LABEL_WIDTH + " x")


class RadioValuesTests(unittest.TestCase):
    """CR70: kisshub owns the radio values and tells where each one came from."""

    def test_vara_values(self):
        cfg = example("vara-fm")
        self.assertEqual((cfg.tnc.transport, cfg.tnc.port), ("tcp", 8100))
        h = cfg.hub
        self.assertEqual((h.air_baud, h.txdelay_sec, h.max_lead_sec), (350, 2.7, 12.0))
        self.assertEqual(h.sources["air_baud"], "kisshub.conf [vara-fm]")
        self.assertEqual((h.ax25["paclen"], h.ax25["maxframe"], h.ax25["t1_min_sec"]),
                         (256, 4, 18.0))
        self.assertEqual((h.status_port, cfg.hints), (8102, ()))
        text = "\n".join(termcolor.kv_plain(*x) for x in hubconfig.radio_lines(cfg))
        self.assertIn("Radio values as defined in conf-file:", text)
        self.assertRegex(text, r"  air_baud: +350 Bd\n")       # from the section: bare
        self.assertNotIn("kisshub.conf [vara-fm]", text)
        # a value from elsewhere names where it came from
        moved = dataclasses.replace(h, sources={**h.sources, "txdelay_ms": "console"})
        text = "\n".join(termcolor.kv_plain(*x) for x in
                         hubconfig.radio_lines(dataclasses.replace(cfg, hub=moved)))
        self.assertRegex(text, r"  txdelay: +2700 ms  \(console\)")

    def test_overrides_and_old_keys(self):
        cfg = example("t", "[t]\nbase = vara-fm\nair_baud = 600\nt1_min_sec = 25\n"
                           "port = 8100\n").hub
        self.assertEqual((cfg.air_baud, cfg.ax25["t1_min_sec"]), (600, 25.0))
        text = EXAMPLE.replace("port   = 8101", "port = 8201\nstatus_port = 8202")
        cfg = load_conf(text, "vara-fm")
        self.assertEqual(cfg.hub.status_port, 8202)
        self.assertIn("can be removed", cfg.hints[0])
        self.assertEqual(load_conf(EXAMPLE.replace("port   = 8101", "port = 8201"),
                                   "vara-fm").hub.status_port, 8202)

    def test_direwolf_conf_wins(self):
        dw = "MODEM 9600\nTXDELAY 15\nKISSPORT 8011\nPACLEN 200\nEMAXFRAME 6\n"
        cfg = example("direwolf", dw=dw)
        self.assertEqual((cfg.tnc.transport, cfg.tnc.port, cfg.tnc.params), ("tcp", 8011, {}))
        h = cfg.hub
        self.assertEqual((h.air_baud, round(h.txdelay_sec * 1000)), (9600, 150))
        self.assertEqual(h.sources["txdelay_ms"], "direwolf.conf")
        self.assertEqual((h.ax25["paclen"], h.ax25["maxframe"], h.ax25["maxframe_ext"]),
                         (200, 4, 6))                      # MAXFRAME not set: the section's
        self.assertIn("MODEM 9600", "\n".join(termcolor.kv_plain(*x)
                                              for x in hubconfig.radio_lines(cfg)))
        # nothing in direwolf.conf: the section's values
        cfg = example("direwolf", dw="")
        self.assertEqual((cfg.tnc.port, cfg.hub.air_baud, cfg.hub.sources["air_baud"]),
                         (8001, 1200, "kisshub.conf [direwolf]"))
        with self.assertRaises(hubconfig.ConfigError):
            example("t", "[t]\nbase = direwolf\ndirewolf_conf = /nowhere/x\n")

    def test_status_has_radio_block(self):
        cfg = example("vara-fm")
        from tests.test_kisshub_quality import _NoTnc
        hub = Hub(dataclasses.replace(cfg.hub, port=0, status_port=0, links_file=""),
                  lambda on_frame: _NoTnc())
        r = hub.radio_dict()
        self.assertEqual((r["air_baud"], r["txdelay_ms"], r["profile"]), (350, 2700, "vara-fm"))
        self.assertEqual(r["ax25"]["t2_sec"], 0.3)
        self.assertEqual(r["source"]["max_lead_ms"], "kisshub.conf [vara-fm]")


class OneConfTests(unittest.TestCase):
    """One kisshub.conf for all TNCs: -p picks the section, {profile} in file names."""

    def test_profiles_one_file(self):
        extra = EXAMPLE.replace("links_file = kisshub-links-{profile}.jsonl",
                                "links_file = links-{profile}.jsonl")
        pk = load_conf(extra)
        self.assertEqual((pk.tnc.profile.name, pk.tnc.transport, pk.tnc.device),
                         ("pk232", "serial", "COM3"))
        self.assertEqual((pk.log_file, pk.hub.links_file),
                         ("kisshub-pk232.log", "links-pk232.jsonl"))
        self.assertFalse(pk.hub.vara_monitor)
        va = load_conf(extra.replace("vara_monitor  = no", "vara_monitor = yes")
                       .replace("host          = 127.0.0.1  ; VARA", "host = 127.0.0.2  ; VARA"),
                       "vara-fm")
        self.assertEqual((va.tnc.transport, va.tnc.host, va.tnc.port), ("tcp", "127.0.0.2", 8100))
        self.assertEqual((va.hub.vara_monitor, va.hub.vara_host), (True, "127.0.0.2"))
        self.assertEqual(va.log_file, "kisshub-vara-fm.log")
        hf = load_conf(extra, "vara-hf")                    # base = vara-fm
        self.assertEqual((hf.tnc.profile.display, hf.hub.air_baud), ("VARA HF", 350))

    def test_help(self):
        import contextlib
        import io
        from kisshub.__main__ import parser
        for opt in ("-h", "-?"):
            out = io.StringIO()
            with contextlib.redirect_stdout(out), self.assertRaises(SystemExit):
                parser().parse_args([opt])
            self.assertIn("the TNC sections of kisshub.conf", out.getvalue())
        self.assertEqual(parser().parse_args(["-p", "anything"]).profile, "anything")


class VaraConfigTests(unittest.TestCase):
    def test_config(self):
        cfg = example("vara-fm")
        self.assertEqual((cfg.tnc.profile.tunnel, cfg.tnc.params), ("connected", {}))
        self.assertEqual(example("t", "[t]\nbase = vara-fm\nvara_tunnel = all\n")
                         .tnc.profile.tunnel, "all")
        # KISS parameters would be VARA frames of type 1/2 on the air
        for bad in ("send_params = yes", "vara_tunnel = maybe", "smack = yes",
                    "transport = serial\ndevice = COM1\nserial_baud = 9600"):
            with self.assertRaises(hubconfig.ConfigError, msg=bad):
                example("t", f"[t]\nbase = vara-fm\n{bad}\n")


if __name__ == "__main__":
    unittest.main()


class ConsoleTests(HubTestBase):
    async def test_console_mark_debug_trace_and_live_txdelay(self):
        import logging as _logging
        from kisshub.console import Console, LogControl
        await self.start_hub(FakePK232("cmd"))
        await asyncio.wait_for(self.hub.tnc.ready.wait(), 5)
        await self.wait(lambda: len(self.fake.params) == 2)
        lines: list[str] = []
        ctl = LogControl("INFO", "")
        con = Console(self.hub, ctl, out=lambda *a: lines.append(" ".join(map(str, a))))
        with self.assertLogs("kisshub", "INFO") as logs:
            con.handle_line("log mark test 1")
            con.handle_line("LOG TRACE")
            con.handle_line("TXDELAY 600")
        text = "\n".join(logs.output)
        self.assertIn("MARK: test 1", text)
        self.assertIn(">> TNC param TXDELAY=60", text)
        await self.wait(lambda: len(self.fake.params) == 3)
        self.assertEqual(self.fake.params[-1], (kiss.CMD_TXDELAY, bytes((60,))))
        self.assertEqual(self.hub.tnc.state, "kiss")            # never left KISS
        self.assertAlmostEqual(self.hub.cfg.txdelay_sec, 0.6)
        con.handle_line("LOG DEBUG")
        self.assertEqual(_logging.getLogger("kisshub").level, _logging.DEBUG)
        con.handle_line("LOG OFF")
        self.assertFalse(self.hub.tnc.trace)
        self.assertEqual(_logging.getLogger("kisshub").level, _logging.NOTSET)
        con.handle_line("PARAMS")
        self.assertIn("TXDELAY 600 ms", lines[-1])
        con.handle_line("bogus")
        self.assertIn("unknown command", lines[-1])
        calls = []
        Console(self.hub, ctl, out=lines.append, info=lambda: calls.append(1)).handle_line("i")
        con.handle_line("INFO")
        self.assertEqual((calls, lines[-1]), ([1], "no start block available"))


# --- TNC7multi (KISS/SMACK, handbook V1.04) -------------------------------------------

class FakeTNC7:
    """TNC7multi with the rotary switch on 1k2: in KISS from power-on, no terminal.
    Handbook 4.1: switches to SMACK on the first CRC frame from the PC and from then
    on sends CRC frames itself; frames with a bad CRC are not sent."""

    def __init__(self, smack: bool = False) -> None:
        self.smack = smack                     # True: still in SMACK from an earlier run
        self.transmitted: list[bytes] = []
        self.params: list[tuple[int, bytes]] = []
        self.raw = bytearray()
        self.bad_crc = 0
        self.writer = None
        self._dec = kiss.Decoder()

    async def handle(self, reader, writer) -> None:
        self.writer = writer
        try:
            while data := await reader.read(4096):
                self.raw += data
                for port, cmd, frame in self._dec.feed(data):
                    if cmd == kiss.CMD_DATA and port >= 8:
                        ok = kiss.smack_check(port, frame)
                        if ok is None:
                            self.bad_crc += 1
                        else:
                            self.smack = True
                            self.transmitted.append(ok)
                    elif cmd == kiss.CMD_DATA:
                        self.transmitted.append(frame)
                    elif cmd != kiss.CMD_RETURN:
                        self.params.append((cmd, frame))
        except ConnectionError:
            pass
        finally:
            writer.close()

    def receive(self, ax25: bytes, corrupt: bool = False) -> None:
        f = kiss.encode_smack(ax25) if self.smack else kiss.encode(ax25)
        if corrupt:
            f = f[:-3] + bytes((f[-3] ^ 0x01,)) + f[-2:]
        self.writer.write(f)


class SmackTests(unittest.TestCase):
    def test_crc16_arc(self):
        self.assertEqual(kiss.crc16(b"123456789"), 0xBB3D)

    def test_roundtrip_with_escapes(self):
        data = bytes(range(256)) + b"\xc0\xdb\xc0"
        for port in (0, 3, 7):
            f = kiss.encode_smack(data, port)
            self.assertEqual(f[1], 0x80 | port << 4)
            ((p, cmd, body),) = kiss.Decoder().feed(f)
            self.assertEqual((p, cmd), (8 + port, 0))
            self.assertEqual(kiss.smack_check(p, body), data)

    def test_bad_crc(self):
        ((p, _, body),) = kiss.Decoder().feed(kiss.encode_smack(b"hello"))
        self.assertIsNone(kiss.smack_check(p, body[:-1] + bytes((body[-1] ^ 0xFF,))))
        self.assertIsNone(kiss.smack_check(p, b"x"))


class Tnc7Tests(HubTestBase):
    profile = fast(example_profile("tnc7multi"))

    async def test_no_dialog_params_and_smack(self):
        await self.start_hub(FakeTNC7())
        await asyncio.wait_for(self.hub.tnc.ready.wait(), 5)
        await self.wait(lambda: len(self.fake.params) == 2)      # TXDELAY, P - no text sent
        self.assertNotIn(b"\r", bytes(self.fake.raw))
        w, got = await self.client()
        mine = ax.ui_frame("TEST", "OE3GAS", b"via TNC7").encode()
        w.write(kiss.encode(mine))
        await self.wait(lambda: self.fake.transmitted == [mine])
        self.assertTrue(self.fake.smack)                          # TNC followed
        self.assertEqual(self.fake.bad_crc, 0)
        heard = ax.ui_frame("CQ", "OE1ABC", b"with crc").encode()
        self.fake.receive(heard)
        await self.wait(lambda: got == [heard])
        st = self.hub.tnc.status()
        self.assertEqual((st["smack"], st["smack_seen"], st["smack_rx"], st["crc_errors"]),
                         (True, True, 1, 0))
        self.assertIn("SMACK on (CRC ok 1, bad 0)", self.hub.status())

    async def test_bad_crc_dropped(self):
        await self.start_hub(FakeTNC7(smack=True))
        await asyncio.wait_for(self.hub.tnc.ready.wait(), 5)
        _, got = await self.client()
        bad = ax.ui_frame("CQ", "OE1ABC", b"broken").encode()
        good = ax.ui_frame("CQ", "OE1ABC", b"fine").encode()
        with self.assertLogs("kisshub.tnc", "WARNING"):
            self.fake.receive(bad, corrupt=True)
            self.fake.receive(good)
            await self.wait(lambda: got == [good])
        self.assertEqual(self.hub.tnc.crc_errors, 1)

    async def test_smack_off_still_reads_crc_frames(self):
        """kisshub restarted with smack = no: the TNC stays in SMACK until it
        restarts - its CRC frames must still come through."""
        self.profile = dataclasses.replace(self.profile, smack=False)
        await self.start_hub(FakeTNC7(smack=True))
        await asyncio.wait_for(self.hub.tnc.ready.wait(), 5)
        w, got = await self.client()
        heard = ax.ui_frame("CQ", "OE1ABC", b"old smack").encode()
        self.fake.receive(heard)
        await self.wait(lambda: got == [heard])
        mine = ax.ui_frame("TEST", "OE3GAS", b"plain").encode()
        w.write(kiss.encode(mine))
        await self.wait(lambda: self.fake.transmitted == [mine])
        self.assertNotIn(0x80, bytes(self.fake.raw[:2]))

    async def test_stop_sends_nothing(self):
        await self.start_hub(FakeTNC7())
        await asyncio.wait_for(self.hub.tnc.ready.wait(), 5)
        await self.wait(lambda: len(self.fake.params) == 2)
        before = bytes(self.fake.raw)
        await self.hub.tnc.stop()
        await asyncio.sleep(0.1)
        self.assertEqual(bytes(self.fake.raw), before)            # no C0 FF C0


class Tnc7ConfigTests(unittest.TestCase):
    def test_values_from_the_section(self):
        cfg = example("tnc7multi")
        t = cfg.tnc
        self.assertEqual((t.serial_baud, t.rtscts, t.profile.smack, t.profile.exit_kiss),
                         (115200, False, True, False))
        self.assertEqual((t.profile.wake, t.profile.init), ((), ()))
        self.assertEqual(t.params, {kiss.CMD_TXDELAY: 15, kiss.CMD_P: 64,
                                    kiss.CMD_SLOTTIME: 5, kiss.CMD_FULLDUPLEX: 0})
        lines = dict((x[0], x[1]) for x in hubconfig.radio_lines(cfg))
        self.assertIn("rotary switch on 1k2", lines["TNC7multi"])
        self.assertIn("SMACK", lines)
        self.assertEqual(cfg.hints, ())

    def test_9600_and_rs232(self):
        cfg = example("t", "[t]\nbase = tnc7multi-9k6\nserial_baud = 38400\nsmack = no\n")
        self.assertEqual((cfg.tnc.serial_baud, cfg.tnc.profile.smack), (38400, False))
        lines = dict((x[0], x[1]) for x in hubconfig.radio_lines(cfg))
        self.assertIn("9k6", lines["TNC7multi"])
        self.assertNotIn("SMACK", lines)
        self.assertEqual(cfg.hub.ax25["maxframe"], 7)

    def test_other_rate_gives_a_hint(self):
        cfg = example("t", "[t]\nbase = tnc7multi\nair_baud = 19200\n")
        self.assertIn("extra modem", cfg.hints[0])
