"""CR41: channel monitor, kisshub status query, TinyBox reading it."""

from __future__ import annotations

import asyncio
import json
import unittest

from tinybox import chanmon
from tinybox.adapters import kiss as kissadapter
from prcore.ax25 import frame as ax
from prcore import kiss, kissport

from tests.test_kisshub import FakePK232, HubTestBase, example_profile, fast


class ChannelMonitorTests(unittest.TestCase):
    def test_load_own_and_others(self):
        m = chanmon.ChannelMonitor("OE3GAS-1", 1200, 0.3)
        m.started = 0.0
        # 100-byte frame at 1200 Bd: 0.3 + 104*8/1200 = 0.993 s
        for t in range(10):
            m.record("OE3GAS-1", 100, now=100.0 + t, wall=1000.0 + t)
            m.record("OE1ABC", 100, now=100.5 + t, wall=1000.5 + t)
        load = m.load(60, now=120.0)
        self.assertAlmostEqual(load["own"], 10 * 0.99333 / 60, places=3)
        self.assertAlmostEqual(load["other"], load["own"], places=6)
        self.assertEqual(load["frames"], 20)
        heard = {h["call"]: h for h in m.heard_list()}
        self.assertTrue(heard["OE3GAS-1"]["own"])
        self.assertEqual(heard["OE1ABC"]["frames"], 10)

    def test_young_window_counts_from_start(self):
        m = chanmon.ChannelMonitor("OE3GAS-1", 1200, 0.0)
        m.started = 0.0
        m.record("OE1ABC", 146, now=5.0)                  # 150*8/1200 = 1 s
        self.assertAlmostEqual(m.load(600, now=10.0)["total"], 0.1)
        self.assertEqual(m.load(600, now=10.0)["span_sec"], 10)

    def test_per_minute_and_cap(self):
        m = chanmon.ChannelMonitor("OE3GAS-1", 300, 1.0)
        m.started = 0.0
        for i in range(100):                              # far more than a minute of air
            m.record("OE1ABC", 250, now=3600.0 + i * 0.1)
        pm = m.per_minute(60, now=3615.0)
        self.assertEqual(len(pm), 60)
        self.assertEqual(pm[-1]["frames"], 100)
        self.assertEqual(pm[-1]["other"], 1.0)            # capped at 100 %
        self.assertEqual(m.load(60, now=3615.0)["total"], 1.0)

    def test_old_frames_forgotten_and_heard_limit(self):
        m = chanmon.ChannelMonitor("OE3GAS-1", 1200, 0.3)
        m.record("OE1ABC", 50, now=0.0)
        m.record("OE1ABC", 50, now=chanmon.KEEP_SEC + 10)
        self.assertEqual(len(m.events), 1)
        for i in range(chanmon.MAX_HEARD + 5):
            m.record(f"OE{i % 10}X{i:02d}"[:6], 20, now=10.0, wall=float(i))
        self.assertLessEqual(len(m.heard), chanmon.MAX_HEARD)


class HubStatusTests(HubTestBase):
    profile = fast(example_profile("pk232"))

    async def get_status(self) -> dict:
        return await kissport.fetch_hub_status("127.0.0.1", self.hub.status_port)

    async def test_status_query(self):
        await self.start_hub(FakePK232("cmd"))
        await asyncio.wait_for(self.hub.tnc.ready.wait(), 5)
        w, _got = await self.client()
        w.write(kiss.encode(ax.ui_frame("TBCHAT-1", "OE3GAS-1", b"hi").encode()))
        w.write(kiss.encode(ax.s_frame("RR", "OE1ABC", "OE3GAS-1", 1).encode()))
        await self.wait(lambda: len(self.fake.transmitted) == 2)
        st = await self.get_status()
        t = st["tnc"]
        self.assertEqual((t["name"], t["profile"], t["state"], t["inits"]), ("PK-232", "pk232", "kiss", 1))
        self.assertEqual(t["init_log"][-1]["send"], "HOST ON")
        self.assertTrue(any(x["send"] == "EXPERT ON" and x["ok"] for x in t["init_log"]))
        q = st["queue"]
        self.assertEqual((q["wait_10min"]["control"]["frames"], q["wait_10min"]["ui"]["frames"]), (1, 1))
        self.assertEqual(q["queued"], {"control": 0, "i": 0, "ui": 0})
        self.assertEqual(st["clients"][0]["calls"], ["OE3GAS-1"])
        self.assertEqual(st["clients"][0]["rx"], 2)

    async def test_failed_init_visible(self):
        fake = FakePK232("cmd")
        fake.reject = {"PACKET"}
        with self.assertLogs("kisshub.tnc", "ERROR"):
            await self.start_hub(fake)
            await self.wait(lambda: self.hub.tnc.last_error is not None, 10)
        st = await self.get_status()
        self.assertNotEqual(st["tnc"]["state"], "kiss")
        self.assertIn("PACKET", st["tnc"]["last_error"])
        self.assertFalse(st["tnc"]["init_log"][-1]["ok"])

    async def test_stale_frames_dropped(self):
        await self.start_hub(FakePK232("cmd"), stale_sec=0.0)
        await asyncio.wait_for(self.hub.tnc.ready.wait(), 5)
        self.hub.tnc.ready.clear()                       # TNC "not ready": frames wait
        self.hub.enqueue(ax.ui_frame("X1X", "OE3GAS-1", b"old").encode())
        await asyncio.sleep(0.05)
        self.hub.tnc.ready.set()
        await self.wait(lambda: self.hub.dropped == 1)
        self.assertEqual(self.fake.transmitted, [])

    async def test_unknown_path_404(self):
        await self.start_hub(FakePK232("cmd"))
        r, w = await asyncio.open_connection("127.0.0.1", self.hub.status_port)
        w.write(b"GET /nothing HTTP/1.0\r\n\r\n")
        self.assertIn(b"404", await r.read(1000))
        w.close()


class TinyBoxReadsHubTests(HubTestBase):
    profile = fast(example_profile("pk232"))

    async def test_adapter_shows_tnc_and_channel(self):
        from tests.test_kiss_adapter import kiss_app
        await self.start_hub(FakePK232("kiss"))
        await asyncio.wait_for(self.hub.tnc.ready.wait(), 10)
        app = kiss_app(self.hub.port)
        app.cfg.kiss = __import__("dataclasses").replace(app.cfg.kiss,
                                                         status_port=self.hub.status_port)
        adapter = kissadapter.KissAdapter(app)
        app.agw = adapter
        task = asyncio.create_task(adapter.run())
        try:
            await asyncio.wait_for(adapter.connected.wait(), 5)
            await self.wait(lambda: adapter.hub_status is not None, 5)
            r = adapter.radio_state()
            self.assertEqual((r["tnc"], r["tnc_state"], r["ready"], r["hub"]),
                             ("PK-232", "kiss", True, "ok"))
            heard = ax.ui_frame("APRS", "OE1ABC", b"x" * 40).encode()
            self.fake.receive(heard)
            adapter.send_ui("TBCHAT-1", "hello")
            await self.wait(lambda: len(adapter.channel.heard) == 2)
            snap = adapter.channel_snapshot()
            self.assertGreater(snap["load_1min"]["own"], 0)
            self.assertGreater(snap["load_1min"]["other"], 0)
            self.assertEqual(snap["hub"]["tnc"]["state"], "kiss")
            json.dumps(snap)                                       # web API must serialise it
            # STATUS in the sysop console names the TNC
            from tinybox.adapters import sysop
            out: list[str] = []
            con = sysop.SysopConsole.__new__(sysop.SysopConsole)
            con.app, con.out = app, lambda *lines: out.extend(lines)
            con.cmd_status("")
            self.assertIn("TNC PK-232 kiss", "\n".join(out))
        finally:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)

    async def test_no_hub_status(self):
        from tests.test_kiss_adapter import kiss_app
        await self.start_hub(FakePK232("kiss"))
        app = kiss_app(self.hub.port)
        app.cfg.kiss = __import__("dataclasses").replace(app.cfg.kiss, status_port=1)
        adapter = kissadapter.KissAdapter(app)
        app.agw = adapter
        task = asyncio.create_task(adapter.run())
        try:
            await asyncio.wait_for(adapter.connected.wait(), 5)
            await self.wait(lambda: adapter.hub_error is not None, 5)
            r = adapter.radio_state()
            self.assertEqual((r["hub"], r["tnc_state"], r["ready"]), ("unreachable", None, True))
        finally:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)


if __name__ == "__main__":
    unittest.main()
