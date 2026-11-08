"""Sendung (web GUI): the carousel's state - on the air, waiting, last sent, budget."""

from __future__ import annotations

import unittest

from brocast.carousel import Carousel
from tests.test_daemon import BULLETIN, Clock, make_station


class TxStateTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.clock = Clock()
        self.seen: list[dict | None] = []
        self.up = True

        async def send(data: bytes) -> bool:
            self.seen.append(dict(self.car.current) if self.car.current else None)
            return self.up

        async def sleep(s: float) -> None:
            pass

        self.st, self.store = make_station(self.clock)
        self.car = Carousel(self.store, send, self.st.cfg.station, "OE3GAS-5", self.clock,
                            mono=lambda: 0.0, sleep=sleep)

    async def test_current_recent_next(self):
        self.st.put("tinybox", "1", BULLETIN)
        tx = self.car.tx_state()
        self.assertIsNone(tx["current"])
        self.assertEqual(len(tx["next"]), 1)
        self.assertTrue(tx["next"][0]["new"])
        await self.car.step()
        cur = self.seen[0]                        # while the first frame is handed over
        self.assertEqual((cur["sent"], cur["title"]), (0, BULLETIN.get("ti", "")))
        tx = self.car.tx_state()
        self.assertIsNone(tx["current"])          # through
        r = tx["recent"][0]
        self.assertEqual((r["result"], r["sent"], r["total"]), ("ok", r["total"], r["total"]))
        self.assertEqual(tx["today"]["pages"], 1)
        self.assertGreaterEqual(tx["today"]["frames"], 1)
        self.assertGreater(tx["budget"]["used_s"], 0)
        self.assertFalse(tx["next"][0]["new"])
        self.assertGreater(tx["next"][0]["next_tx"], tx["now"])

    async def test_link_down_is_paused(self):
        self.up = False
        self.st.put("tinybox", "1", BULLETIN)
        await self.car.step()
        tx = self.car.tx_state()
        self.assertEqual(tx["recent"][0]["result"], "paused")
        self.assertEqual(tx["blocked"]["reason"], "link")
        self.up = True
        self.clock.t += 6
        await self.car.step()
        self.assertIsNone(self.car.tx_state()["blocked"])

    async def test_budget_full(self):
        self.st.cfg.station.airtime_percent = 0.0001
        self.car = Carousel(self.store, self.car.send, self.st.cfg.station, "OE3GAS-5",
                            self.clock, mono=lambda: 0.0, sleep=self.car.sleep)
        self.car.budget.add(self.clock(), 999)
        self.st.put("tinybox", "1", BULLETIN)
        await self.car.step()
        tx = self.car.tx_state()
        self.assertEqual(tx["blocked"]["reason"], "budget")
        self.assertEqual(tx["blocked"]["waiting"], 1)


class TakeOffAirTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.clock = Clock()

        async def send(data: bytes) -> bool:
            return True

        async def sleep(s: float) -> None:
            pass

        self.st, self.store = make_station(self.clock)
        self.car = Carousel(self.store, send, self.st.cfg.station, "OE3GAS-5", self.clock,
                            mono=lambda: 0.0, sleep=sleep)

    async def test_off_air_stays_off_until_new_content(self):
        self.st.sync("tinybox", {"26": BULLETIN})
        page_id = self.store.get_page("tinybox", "26").id
        self.st.take_off_air(page_id)
        self.assertEqual(self.store.get_page("tinybox", "26").state, "withdrawn")
        for _ in range(10):                      # the withdrawal goes out, then the page is gone
            await self.car.step()
            self.clock.t += 600
        self.assertIsNone(self.store.get_page("tinybox", "26"))
        res = self.st.sync("tinybox", {"26": BULLETIN})       # TinyBox still has it
        self.assertTrue(res["pages"]["26"]["blocked"])
        self.assertIsNone(self.store.get_page("tinybox", "26"))
        self.assertEqual(len(self.car.tx_state()["next"]), 0)
        changed = {**BULLETIN, "ti": "geändert"}
        self.st.sync("tinybox", {"26": changed})               # new content: back on the air
        self.assertEqual(self.store.get_page("tinybox", "26").state, "active")
        self.assertEqual(self.store.list_blocked(), [])

    async def test_restore_and_guard(self):
        self.st.put("tinybox", "27", BULLETIN)
        pid = self.store.get_page("tinybox", "27").id
        self.st.take_off_air(pid)
        self.assertEqual(len(self.store.list_blocked()), 1)
        self.assertTrue(self.st.restore("tinybox", "27")["restored"])
        self.st.put("tinybox", "27", BULLETIN)
        self.assertEqual(self.store.get_page("tinybox", "27").state, "active")
        from brocast.station import NotFound
        with self.assertRaises(NotFound):
            self.st.take_off_air(9999)


class BeaconTests(unittest.IsolatedAsyncioTestCase):
    async def test_beacon_every_interval_plain_text(self):
        from brocast.ax25 import UIFrame
        from brocast.frame import parse as parse_frame
        clock = Clock()
        sent: list[bytes] = []

        async def send(data: bytes) -> bool:
            sent.append(data)
            return True

        async def sleep(s: float) -> None:
            pass

        st, store = make_station(clock)
        car = Carousel(store, send, st.cfg.station, "OE3GAS-5", clock, mono=lambda: 0.0, sleep=sleep)
        text = "OE3GAS-5: brocast - Teletext ueber Packet Radio"
        car.set_beacon(lambda: UIFrame(dest="BEACON", src="OE3GAS-5", info=text.encode()).encode(),
                       30, text)
        await car.step()                                   # the first one at the start
        self.assertEqual(len(sent), 1)
        f = UIFrame.decode(sent[0])
        self.assertEqual((f.dest, f.info.decode()), ("BEACON", text))
        self.assertIsNone(parse_frame(sent[0]))            # no brocast frame: listeners ignore it
        clock.t += 29 * 60
        await car.step()
        self.assertEqual(len(sent), 1)
        clock.t += 61
        await car.step()
        self.assertEqual(len(sent), 2)
        tx = car.tx_state()
        self.assertEqual(tx["recent"][0]["typ"], "beacon")
        self.assertEqual(tx["beacon"]["interval_min"], 30)
        self.assertGreater(tx["budget"]["used_s"], 0)


class BeaconConfigTests(unittest.TestCase):
    def test_config(self):
        import tempfile
        from pathlib import Path
        from brocast import config
        base = "[brocastd]\nmode = station\ncallsign = OE3GAS-5\n[radio]\ninterface = kiss\n"
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "b.conf"
            p.write_text(base, encoding="utf-8")
            c = config.load(p)
            self.assertEqual((c.beacon.interval_min, c.beacon.dest), (30, "BEACON"))
            p.write_text(base + "[beacon]\ninterval_min = 60\ntext = {call} hier brocast, {pages} Seiten\n"
                         "dest = ID\n", encoding="utf-8")
            c = config.load(p)
            self.assertEqual((c.beacon.interval_min, c.beacon.dest), (60, "ID"))
            p.write_text(base + "[beacon]\ntext = {call} brocast\n       zweite Zeile\n", encoding="utf-8")
            self.assertEqual(config.load(p).beacon.text, "{call} brocast\nzweite Zeile")
            for bad in ("interval_min = 2\n", "text = {foo}\n", "text = " + "x" * 300 + "\n"):
                p.write_text(base + "[beacon]\n" + bad, encoding="utf-8")
                with self.assertRaises(config.ConfigError):
                    config.load(p)
