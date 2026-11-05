"""kisshub type modem73: mode table, its TNC section, hub timing and the
modem73 process (a fake modem73 in Python that speaks KISS-TCP)."""

from __future__ import annotations

import asyncio
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

from kisshub import config as hubconfig
from kisshub import modem73 as m73
from kisshub.hub import Hub, HubCfg
from prcore import kiss
from prcore.ax25 import frame as ax

ROOT = Path(__file__).resolve().parent.parent

HEAD = """[kisshub]
profile = modem73
[modem73]
type = modem73
transport = tcp
port = 8011
reconnect_sec = 10
settle_sec = 0.2
"""
BASE = HEAD + "callsign = OE3GAS\ncom_port = COM5\n"


class FrameInfoTests(unittest.TestCase):
    """Values computed with modem73's own phy/common.hh (2.4.8), 1.11.2026."""

    def test_table(self):
        for mode, payload, sec in ((("QAM16", "1/2", "short"), 254, 0.957),
                                   (("QPSK", "1/2", "short"), 126, 0.957),
                                   (("QPSK", "1/2", "normal"), 510, 2.597),
                                   (("8PSK", "1/2", "short"), 510, 1.913),
                                   (("QAM16", "1/2", "normal"), 1022, 2.597),
                                   (("QAM16", "3/4", "short"), 382, 0.957),
                                   (("QAM64", "5/6", "normal"), 3406, 3.417),
                                   (("BPSK", "1/2", "short"), 126, 1.503),
                                   (("QPSK", "1/2x2", "short"), 126, 1.503)):
            p, s = m73.frame_info(*mode)
            self.assertEqual(p, payload, mode)
            self.assertAlmostEqual(s, sec, places=2, msg=mode)

    def test_not_available(self):
        for mode in (("QAM1024", "1/2", "long"), ("QAM64", "1/2x2", "long"),
                     ("QAM17", "1/2", "short"), ("QPSK", "7/8", "short")):
            with self.assertRaises(ValueError, msg=mode):
                m73.frame_info(*mode)


class ConfigTests(unittest.TestCase):
    def load(self, text: str, profile: str | None = None, exe: bool = True):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "k.conf"
            p.write_text(text, encoding="utf-8")
            if exe:
                (Path(d) / "modem73.exe").write_bytes(b"MZ")
            return hubconfig.load(p, profile)

    def test_exe(self):
        cfg = self.load(BASE)
        self.assertTrue(cfg.modem73.exe.endswith("modem73.exe"))
        self.assertTrue(Path(cfg.modem73.exe).is_absolute())
        # Gerhard 1.11.2026: "./modem73.exe; path ..." - no blank before the ";"
        cfg = self.load(BASE + "exe = ./modem73.exe; path to modem73.exe\n")
        self.assertEqual(Path(cfg.modem73.exe).name, "modem73.exe")
        with self.assertRaises(hubconfig.ConfigError) as cm:
            self.load(BASE, exe=False)
        self.assertIn("not found", str(cm.exception))
        cfg = self.load(BASE + "start = no\n", exe=False)      # elsewhere: no check
        self.assertEqual(cfg.modem73.exe, "modem73.exe")

    def test_defaults(self):
        cfg = self.load(BASE)
        m, h = cfg.modem73, cfg.hub
        self.assertEqual((cfg.tnc.transport, cfg.tnc.host, cfg.tnc.port), ("tcp", "127.0.0.1", 8011))
        self.assertEqual((m.mode, m.payload, m.lead_ms), ("QAM16 1/2 short", 254, 850))
        self.assertEqual(h.max_frame, 254)
        self.assertEqual(round(h.txdelay_sec * 1000), 850 + 957)
        self.assertAlmostEqual(h.frame_sec, 0.957 + 0.2, places=2)
        self.assertEqual(h.ax25["paclen"], 223)
        self.assertEqual((h.ax25["maxframe"], h.ax25["maxframe_ext"]), (4, 4))
        self.assertEqual(h.ax25["t1_min_sec"], 10.0)
        self.assertEqual(cfg.tnc.params, {})              # no KISS parameters to modem73
        self.assertIn("modem73 QAM16 1/2 short", h.sources["ax25"])

    def test_args(self):
        cfg = self.load(BASE + "input_device = USB Audio\nlead_tone = no\n"
                               "csma_preset = moderate\nextra_args = --postamble -v\n")
        a = cfg.modem73.args(8011, "127.0.0.1")
        self.assertEqual(a[:7], ["--headless", "-c", "OE3GAS", "-p", "8011", "--bind", "127.0.0.1"])
        self.assertIn("--short", a)
        self.assertIn("--no-lead-tone", a)
        self.assertIn("--no-frag", a)
        self.assertEqual(a[a.index("--input-device") + 1], "USB Audio")
        self.assertLess(a.index("--csma-preset"), a.index("--csma-burst"))   # burst wins
        self.assertEqual(a[a.index("--com-port") + 1:a.index("--com-port") + 4],
                         ["COM5", "--com-line", "rts"])
        self.assertEqual(a[-2:], ["--postamble", "-v"])
        self.assertEqual(cfg.modem73.lead_ms, 50 + 300)     # without lead tone

    def test_example(self):
        text = (ROOT / "kisshub.conf.example").read_text(encoding="utf-8")
        with self.assertRaises(hubconfig.ConfigError) as cm:
            self.load(text, "modem73")                      # N0CALL in the example
        self.assertIn("callsign", str(cm.exception))
        cfg = self.load(text.replace("callsign      = N0CALL", "callsign      = OE3GAS"),
                        "modem73")
        self.assertEqual(cfg.modem73.mode, "QAM16 1/2 short")
        self.assertEqual(self.load(text).tnc.profile.name, "pk232")   # others unchanged
        self.assertEqual(self.load(text).hints, ())

    def test_paclen_override(self):
        cfg = self.load(BASE + "paclen = 200\n")
        self.assertEqual(cfg.hub.ax25["paclen"], 200)
        with self.assertRaises(hubconfig.ConfigError) as cm:
            self.load(BASE + "paclen = 240\n")
        self.assertIn("at most 223", str(cm.exception))

    def test_invalid(self):
        for text, word in (
                (BASE + "air_baud = 9600\n", "air_baud"),
                (BASE.replace("transport = tcp", "transport = serial\ndevice = COM3\n"
                              "serial_baud = 9600"), "transport"),
                (BASE + "host = 192.168.1.5\n", "host"),
                (BASE + "modulation = QAM1024\nframe = long\n", "not available"),
                (BASE + "modulation = BPSK\ncode_rate = 1/4\n", "too small"),
                (BASE + "csma_burst = 5\n", "csma_burst"),
                (BASE + "send_params = yes\n", "send_params"),
                (HEAD + "callsign = OE3GAS\n", "com_port"),
                (HEAD + "callsign = OE3GAS-7\nptt = none\n", "callsign"),
                (HEAD + "ptt = none\n", "callsign")):
            with self.assertRaises(hubconfig.ConfigError, msg=text) as cm:
                self.load(text)
            self.assertIn(word, str(cm.exception), text)

    def test_host_elsewhere_with_start_no(self):
        cfg = self.load(HEAD + "host = 192.168.1.5\ncallsign = OE3GAS\nstart = no\nptt = none\n")
        self.assertFalse(cfg.modem73.start)
        self.assertEqual(cfg.tnc.host, "192.168.1.5")


class FakeTnc:
    """Records what the hub hands on."""
    def __init__(self, on_frame) -> None:
        self.sent: list[bytes] = []
        self.ready = asyncio.Event()
        self.ready.set()
        self.profile = None

    def send_ax25(self, frame: bytes, port: int = 0) -> bool:
        self.sent.append(frame)
        return True

    async def run(self) -> None:
        await asyncio.Event().wait()

    async def stop(self) -> None:
        pass

    def status(self) -> dict:
        return {}


def ui(n: int) -> bytes:
    return ax.ui_frame("OE3TEC", "OE3GAS", b"x" * n).encode()


class HubTimingTests(unittest.IsolatedAsyncioTestCase):
    async def test_oversize_dropped_and_burst_time(self):
        cfg = HubCfg(port=0, status_port=0, air_baud=1_000_000, txdelay_sec=1.8,
                     max_lead_sec=10, frame_sec=1.16, max_frame=254, status_every_sec=0)
        hub = Hub(cfg, FakeTnc)
        await hub.start()
        try:
            hub.enqueue(ui(300))                   # 316 bytes: longer than one modem frame
            hub.enqueue(ui(100))
            hub.enqueue(ui(10))
            for _ in range(50):
                if len(hub.tnc.sent) == 2:
                    break
                await asyncio.sleep(0.01)
            self.assertEqual([len(f) for f in hub.tnc.sent], [116, 26])
            self.assertEqual((hub.oversize, hub.dropped), (1, 1))
            # first frame: lead + frame, the second in the same key-up: + frame_sec
            backlog = hub._busy_until - hub.now()
            self.assertAlmostEqual(backlog, 1.8 + 1.16, delta=0.2)
            self.assertEqual(hub.status_dict()["queue"]["oversize"], 1)
        finally:
            await hub.stop()


FAKE = textwrap.dedent('''
    import socket, sys, threading
    a = sys.argv[1:]
    port = int(a[a.index("-p") + 1]); bind = a[a.index("--bind") + 1]
    print("Callsign: " + a[a.index("-c") + 1], flush=True)
    print("(!) COM PTT: test warning", flush=True)
    s = socket.socket(); s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind((bind, port)); s.listen(4)
    print("KISS TNC listening on %s:%d" % (bind, port), flush=True)
    def client(c):
        while True:
            d = c.recv(4096)
            if not d:
                return
            print("TX: %d bytes" % (len(d) - 3), flush=True)
            c.sendall(d)                          # "heard": echo back
    while True:
        c, _ = s.accept()
        threading.Thread(target=client, args=(c,), daemon=True).start()
''')


class ProcessTests(unittest.IsolatedAsyncioTestCase):
    async def test_start_wait_stop(self):
        with tempfile.TemporaryDirectory() as d:
            script = Path(d) / "fake_modem73.py"
            script.write_text(FAKE, encoding="utf-8")
            s = socket_free_port()
            cfg = m73.Modem73Cfg(callsign="OE3GAS", ptt="none")
            proc = m73.Modem73Process(cfg, s, "127.0.0.1", restart_sec=0.2)
            proc.command = lambda: [sys.executable, "-u", str(script),
                                    *cfg.args(s, "127.0.0.1")]
            with self.assertLogs("kisshub.modem73", "INFO") as logs:
                await proc.start()
                self.assertTrue(await proc.wait_port(10))
                r, w = await asyncio.open_connection("127.0.0.1", s)
                w.write(kiss.encode(b"\x01\x02\x03"))
                await w.drain()
                self.assertEqual(await asyncio.wait_for(r.readexactly(6), 5),
                                 kiss.encode(b"\x01\x02\x03"))
                w.close()
                sup = asyncio.create_task(proc.supervise())
                self.assertTrue(proc.status()["running"])
                await proc.stop()
                await asyncio.wait_for(sup, 5)        # no restart after stop()
            text = "\n".join(logs.output)
            self.assertIn("modem73: Callsign: OE3GAS", text)
            self.assertIn("WARNING:kisshub.modem73:modem73: (!) COM PTT", text)
            self.assertFalse(proc.status()["running"])
            self.assertEqual(proc.starts, 1)

    async def test_restart_when_it_ends(self):
        cfg = m73.Modem73Cfg(callsign="OE3GAS", ptt="none")
        proc = m73.Modem73Process(cfg, 1, "127.0.0.1", restart_sec=0.1)
        proc.command = lambda: [sys.executable, "-c", "print('bye')"]
        with self.assertLogs("kisshub.modem73", "INFO"):
            sup = asyncio.create_task(proc.supervise())
            for _ in range(100):
                if proc.starts >= 2:
                    break
                await asyncio.sleep(0.05)
            await proc.stop()
            sup.cancel()
        self.assertGreaterEqual(proc.starts, 2)

    async def test_missing_exe(self):
        cfg = m73.Modem73Cfg(callsign="OE3GAS", ptt="none", exe="/nonexistent/modem73.exe")
        with self.assertRaises(RuntimeError) as cm:
            await m73.Modem73Process(cfg, 8011, "127.0.0.1").start()
        self.assertIn("tools/modem73", str(cm.exception))


def socket_free_port() -> int:
    import socket
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


if __name__ == "__main__":
    unittest.main()
