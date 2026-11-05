"""CR67: link quality in kisshub - passive AX.25 statistics and the VARA monitor."""

from __future__ import annotations

import asyncio
import json
import tempfile
import unittest
from pathlib import Path

from kisshub.linkstats import LinkStats, describe
from kisshub.varamon import VaraMonitor, fit_line
from prcore.ax25 import frame as ax

A, B = "OE3GAS", "OE3GAS-1"          # A = our client (tx), B = the TinyBox far away


def enc(f) -> bytes:
    return f.encode()


class LinkStatsTests(unittest.TestCase):
    def session(self, modulo: int = 128):
        """A connects to B, sends 3 I frames; frame 1 is lost and sent again after
        a REJ; B polls once; A disconnects."""
        closed = []
        st = LinkStats(airtime=lambda n: 0.01 * n, on_closed=closed.append)
        t = 100.0
        kind = "SABME" if modulo == 128 else "SABM"

        def tx(f, dt):
            nonlocal t
            t += dt
            st.frame(enc(f), t, tx=True)

        def rx(f, dt):
            nonlocal t
            t += dt
            st.frame(enc(f), t, tx=False)

        tx(ax.u_frame(kind, B, A, pf=True), 0)
        tx(ax.u_frame(kind, B, A, pf=True), 5)                         # a second try
        rx(ax.u_frame("UA", A, B, command=False, pf=True), 3)
        tx(ax.i_frame(B, A, 0, 0, b"L\r", modulo=modulo), 1)          # ns 0
        tx(ax.i_frame(B, A, 1, 0, b"R 1\r", modulo=modulo), 0.1)      # ns 1 (lost)
        tx(ax.i_frame(B, A, 2, 0, b"B\r", modulo=modulo), 0.1)        # ns 2
        rx(ax.s_frame("REJ", A, B, 1, modulo=modulo), 4)              # acks 0, wants 1
        tx(ax.i_frame(B, A, 1, 0, b"R 1\r", modulo=modulo), 2)        # again
        tx(ax.i_frame(B, A, 2, 0, b"B\r", modulo=modulo), 0.1)
        rx(ax.s_frame("RR", A, B, 3, command=True, pf=True, modulo=modulo), 3)   # a poll
        rx(ax.i_frame(A, B, 0, 3, b"Message 1 ...\r", modulo=modulo), 1)
        tx(ax.s_frame("RR", B, A, 1, modulo=modulo), 1.5)
        tx(ax.u_frame("DISC", B, A, pf=True), 2)
        rx(ax.u_frame("UA", A, B, command=False, pf=True), 3)
        return st, closed

    def test_session_numbers(self):
        for modulo in (128, 8):
            st, closed = self.session(modulo)
            self.assertEqual(len(closed), 1, modulo)
            rec = closed[0]
            self.assertEqual((rec["a"], rec["b"], rec["end"], rec["connect_tries"]),
                             (A, B, "disc", 2))
            self.assertEqual(rec["version"], "2.2" if modulo == 128 else "2.0")
            self.assertEqual(rec["connect_sec"], 8.0)
            a, b = rec["dir"][A], rec["dir"][B]
            self.assertEqual((a["i_frames"], a["retrans"], a["new_bytes"]), (5, 2, 8))
            self.assertEqual(a["retrans_pct"], 40.0)
            self.assertEqual((b["rej"], b["rr"], b["polls"]), (1, 1, 1))
            # ack: only frame 0 was acknowledged and sent once (Karn): 0.1+0.1+4 s
            self.assertEqual(a["ack_sec"]["n"], 1)
            self.assertAlmostEqual(a["ack_sec"]["avg"], 4.2)
            # B answered A after 3 s (UA), 4 s (REJ), 3 s (poll), 3 s (UA)
            self.assertEqual(b["answer_gap_sec"]["max"], 4.0)
            self.assertEqual(rec["local"], [A])
            self.assertIsNotNone(rec["goodput_Bps"])
            self.assertIn("retrans 2 (40.0%)", describe(rec))
            self.assertEqual(st.links, {})

    def test_refused_idle_and_join_in_the_middle(self):
        closed = []
        st = LinkStats(on_closed=closed.append)
        st.frame(enc(ax.u_frame("SABM", B, A, pf=True)), 1.0, tx=True)
        st.frame(enc(ax.u_frame("DM", A, B, command=False, pf=True)), 2.0, tx=False)
        self.assertEqual(closed[-1]["end"], "refused")
        # a link already running when kisshub started (mod 128 guessed from the frame)
        st.frame(enc(ax.i_frame(A, B, 5, 7, b"hello", modulo=128)), 10.0, tx=False)
        link = next(iter(st.links.values()))
        self.assertEqual((link.modulo, link.state), (128, "connected"))
        st.tick(10.0 + 2000)
        self.assertEqual(closed[-1]["end"], "idle")

    def test_sn_goes_to_the_received_frame(self):
        st = LinkStats(sn_window_sec=1.0)
        st.frame(enc(ax.ui_frame("CQ", "OE1ABC", b"x")), 5.0, tx=False)
        self.assertEqual(st.sn(7.5, 5.4), "OE1ABC")             # SN after the frame
        self.assertIsNone(st.sn(3.0, 20.0))                       # SN first ...
        st.frame(enc(ax.ui_frame("CQ", "OE3XHU", b"y")), 20.5, tx=False)   # ... frame next
        self.assertIsNone(st.sn(1.0, 40.0))                       # nothing near: unassigned
        s = st.status(41.0)["stations"]
        self.assertEqual((s["OE1ABC"]["sn_last"], s["OE3XHU"]["sn_last"]), (7.5, 3.0))
        self.assertEqual(st.status(41.0)["sizes"]["rx"], {"<=32": 2})

    def test_garbage_is_counted(self):
        st = LinkStats()
        st.frame(b"\x01\x02", 1.0, tx=False)
        self.assertEqual(st.undecodable, 1)


class FitTests(unittest.TestCase):
    def test_line(self):
        a, b = fit_line([(100, 1.5 + 100 * 0.001), (500, 1.5 + 0.5), (1000, 2.5)])
        self.assertAlmostEqual(a, 1.5)
        self.assertAlmostEqual(8 / b, 8000)
        self.assertIsNone(fit_line([(100, 1.0), (100, 1.2), (100, 1.1)]))


class VaraMonitorTests(unittest.IsolatedAsyncioTestCase):
    async def test_reads_and_never_writes(self):
        received = bytearray()
        conn = asyncio.Event()
        writers = []

        async def vara(reader, writer):
            writers.append(writer)
            conn.set()
            while data := await reader.read(100):
                received.extend(data)

        server = await asyncio.start_server(vara, "127.0.0.1", 0)
        port = server.sockets[0].getsockname()[1]
        loop = asyncio.get_running_loop()
        st = LinkStats()
        mon = VaraMonitor("127.0.0.1", port, clock=loop.time, on_sn=st.sn, reconnect_sec=0.1)
        task = asyncio.create_task(mon.run())
        await asyncio.wait_for(conn.wait(), 5)
        w = writers[0]
        mon.handed(300, loop.time())                     # kisshub gave VARA 300 bytes
        await asyncio.sleep(0.05)
        w.write(b"VERSION VARA FM 4.3.9\rBUSY ON\r")
        await asyncio.sleep(0.05)
        w.write(b"BUSY OFF\rPTT ON\r")
        await asyncio.sleep(0.1)
        w.write(b"PTT OFF\rIAMALIVE\rBITRATE (2) 600 BPS\rREGISTERED OE3GAS\rSOMETHING NEW 42\r")
        st.frame(ax.ui_frame("CQ", "OE3XHU", b"x").encode(), loop.time(), tx=False)
        w.write(b"SN 12.3\r")
        await asyncio.sleep(0.1)
        s = mon.status(loop.time())
        self.assertTrue(s["connected"])
        self.assertEqual(s["version"], "VARA FM 4.3.9")
        self.assertEqual(s["busy_count"], 1)
        self.assertEqual(s["bursts"], 1)
        burst = s["last_bursts"][0]
        self.assertEqual((burst["bytes"], burst["frames"]), (300, 1))
        self.assertGreater(burst["sec"], 0.05)
        self.assertGreater(burst["wait_sec"], 0.04)
        self.assertEqual(s["bitrate"], {"level": 2, "bps": 600})
        self.assertEqual(s["sn"]["last"]["call"], "OE3XHU")
        self.assertEqual(s["unknown_lines"], 1)
        self.assertEqual(bytes(received), b"")              # never sent anything
        mon.ptt, mon.ptt_on_t = True, loop.time() - 100     # a hanging PTT
        mon.tick(loop.time())
        self.assertIn("PTT", mon.status(loop.time())["alarms"][-1]["text"])
        w.write(b"MISSING SOUNDCARD\r")
        await asyncio.sleep(0.05)
        self.assertIn("soundcard", mon.alarms[-1]["text"])
        self.assertTrue(any("bursts" in x for x in mon.lines_text(loop.time())))
        task.cancel()
        w.close()
        server.close()


class HubLinksFileTests(unittest.TestCase):
    def test_finished_link_is_one_json_line(self):
        from kisshub.hub import Hub, HubCfg

        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "links.jsonl"
            hub = Hub(HubCfg(port=0, links_file=str(path), status_port=0),
                      lambda on_frame: _NoTnc())
            hub.stats.frame(ax.u_frame("SABM", B, A, pf=True).encode(), 1.0, tx=True)
            hub.stats.frame(ax.u_frame("UA", A, B, command=False, pf=True).encode(), 2.0,
                            tx=False)
            hub.stats.close_all()
            rec = json.loads(path.read_text(encoding="utf-8").strip())
            self.assertEqual((rec["tnc"], rec["a"], rec["end"], rec["air_baud"]),
                             ("generic", A, "kisshub stopped", 1200))


class StartLinesTests(unittest.TestCase):
    def test_log_and_links_file_are_named(self):
        from kisshub.__main__ import log_lines
        from kisshub import config as hubconfig
        from prcore import termcolor
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "k.conf"
            tnc = ("[kisshub]\nprofile = generic\n[generic]\ntype = tnc\ntransport = tcp\n"
                   "port = 8001\nreconnect_sec = 10\nsettle_sec = 1\nsend_params = no\n"
                   "exit_kiss = no\nair_baud = 1200\ntxdelay_ms = 300\nmax_lead_ms = 1500\n"
                   "paclen = 256\nmaxframe = 4\nmaxframe_ext = 7\nt1_min_sec = 3\n"
                   "t1_max_sec = 30\nt2_sec = 1.5\n")
            p.write_text(tnc + "[log]\nlinks_file =\n", encoding="utf-8")
            text = "\n".join(termcolor.kv_plain(*x) for x in log_lines(str(p), hubconfig.load(p)))
            self.assertIn("NO log file", text)
            self.assertRegex(text, r"Links file: +off")
            p.write_text(tnc + "[log]\nfile = kisshub-dw.log\nlinks_file = links-dw.jsonl\n",
                         encoding="utf-8")
            text = "\n".join(termcolor.kv_plain(*x) for x in log_lines(str(p), hubconfig.load(p)))
            self.assertIn("kisshub-dw.log  (level INFO)", text)
            self.assertIn("links-dw.jsonl", text)


class _NoTnc:
    """Enough of a Tnc for a Hub that is never started."""
    from kisshub import profiles as _p
    profile = _p.Profile(name="generic")
    ready = asyncio.Event

    @staticmethod
    def status() -> dict:
        return {"tunnel_tx": 0, "bundles_tx": 0}


if __name__ == "__main__":
    unittest.main()
