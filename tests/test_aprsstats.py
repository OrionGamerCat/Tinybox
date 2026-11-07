"""CR61: APRS statistics of the channel."""

import tempfile
import unittest
from pathlib import Path

from prcore import aprs
from prcore.aprsstats import AprsStats, country

T0 = 1_792_000_000.0


def feed(st, t, src, path, used, info, dest="APMI06"):
    rep = [bool(x) for x in used]
    a = aprs.decode(dest, src, path, rep, info, now=t)
    st.add(src, path, rep, info, 7 * (2 + len(path)) + 2 + len(info), a, now=t)


class StatsTests(unittest.TestCase):
    def setUp(self):
        self.st = AprsStats(None, aprs.locator_to_latlon("JN88EP"))
        self.st.since = T0 - 1

    def test_counts(self):
        for i in range(5):                        # a stationary car every 60 s
            feed(self.st, T0 + 60 * i, "OE1IAH-8", ["OE6XTR", "OE3XWJ-10", "WIDE2"], [1, 1, 1],
                 b"!4807.19N/01656.63Ev209/000/A=000891Arnold car 578", dest="APDR10")
        feed(self.st, T0 + 10, "OM0ODX", ["OE3XWJ-10", "WIDE2"], [1, 1],
             b"}OM5KV-15>APNL51,TCPIP,OM0ODX*:!4746.48N/01805.55E`Radiosonde")
        feed(self.st, T0 + 20, "OE3XKN-10", ["WIDE1", "WIDE3-3"], [0, 0], b"!/6,fxRISM} st", dest="APOT2A")
        r = self.st.report(0, now=T0 + 400)
        self.assertEqual(r["totals"]["frames"], 7)
        self.assertEqual(r["totals"]["inet"], 1)
        heard = {h["call"]: h["n"] for h in r["heard"]}
        self.assertEqual(heard, {"OE3XWJ-10": 6, "OE3XKN-10": 1})
        senders = {s["call"] for s in r["senders"]}
        self.assertIn("OM5KV-15", senders)                     # the station inside, not the iGate
        self.assertEqual(r["igates"][0]["call"], "OM0ODX")
        self.assertEqual(r["digis"][0], {"call": "OE3XWJ-10", "n": 6})
        self.assertIn({"chain": "OE6XTR → OE3XWJ-10", "n": 5}, r["chains"])
        kinds = {(s["call"], s["kind"]) for s in r["sins"]}
        self.assertIn(("OE1IAH-8", "too often"), kinds)
        self.assertIn(("OE3XKN-10", "long path"), kinds)
        self.assertIn(("OM0ODX", "internet → radio"), kinds)  # 1 of 7 frames = 14 %
        self.assertEqual(r["range"]["farthest_direct"]["call"], "OE3XKN-10")

    def test_station_page(self):
        for i in range(5):
            feed(self.st, T0 + 300 * i, "OE1IAH-8", ["OE6XTR", "OE3XWJ-10", "WIDE2"], [1, 1, 1],
                 b"!4807.19N/01656.63Ev209/000/A=000891Arnold car 578", dest="APDR10")
        feed(self.st, T0 + 10, "OM0ODX", ["OE3XWJ-10", "WIDE2"], [1, 1],
             b"}OM5KV-15>APNL51,TCPIP,OM0ODX*:!4746.48N/01805.55E`Radiosonde")
        s = self.st.station("oe1iah-8", 0, now=T0 + 1500)
        self.assertEqual(s["frames"], 5)
        self.assertEqual(s["types"][0]["cat"], "position")
        self.assertEqual(s["beacon"]["median"], 300)
        self.assertEqual(s["ways"]["chains"][0]["chain"], "OE1IAH-8 → OE6XTR → OE3XWJ-10")
        self.assertEqual(s["roles"][0], "fixed station")
        self.assertEqual(sum(map(sum, s["activity"])), 5)
        self.assertIn("km", s["pos"])
        digi = self.st.station("OE3XWJ-10", 0, now=T0 + 1500)
        self.assertEqual(digi["frames"], 0)
        self.assertEqual(digi["relayed"], 6)
        self.assertIn("digipeater", digi["roles"])
        gate = self.st.station("OM0ODX", 0, now=T0 + 1500)
        self.assertEqual(gate["as_igate"], [{"call": "OM5KV-15", "n": 1}])

    def test_window_and_reset(self):
        feed(self.st, T0, "OE3CRA-2", [], [], b">old")
        feed(self.st, T0 + 7200, "OE3CRA-2", [], [], b">new")
        self.assertEqual(self.st.report(3600, now=T0 + 7300)["totals"]["frames"], 1)
        self.assertEqual(self.st.report(0, now=T0 + 7300)["totals"]["frames"], 2)
        self.st.reset()
        self.assertEqual(self.st.report(0)["totals"]["frames"], 0)

    def test_kept_over_a_restart(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "aprsstats.db"
            st = AprsStats(p)
            feed(st, __import__("time").time(), "OE3CRA-2", [], [], b">hello")
            st.close()
            st2 = AprsStats(p)
            self.assertEqual(st2.report(0)["totals"]["frames"], 1)
            st2.close()

    def test_file_is_tidied_while_running(self):
        import sqlite3
        import time as _t
        from prcore import aprsstats
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "aprsstats.db"
            st = AprsStats(p)
            now = _t.time()
            feed(st, now - aprsstats.KEEP_SEC - 10, "OE3OLD", [], [], b">old")
            feed(st, now + aprsstats.PRUNE_SEC + 1, "OE3NEW", [], [], b">new")    # an hour later
            st.close()
            n = sqlite3.connect(str(p)).execute("SELECT count(*) FROM rec").fetchone()[0]
            self.assertEqual(n, 1)

    def test_graph(self):                        # CR79: the network graph
        for i in range(3):
            feed(self.st, T0 + 60 * i, "OE1IAH-8", ["OE6XTR", "OE3XWJ-10", "WIDE2"], [1, 1, 1],
                 b"!4807.19N/01656.63Ev209/000/A=000891Arnold car 578", dest="APDR10")
        feed(self.st, T0 + 10, "OM0ODX", ["OE3XWJ-10", "WIDE2"], [1, 1],
             b"}OM5KV-15>APNL51,TCPIP,OM0ODX*:!4746.48N/01805.55E`Radiosonde")
        feed(self.st, T0 + 20, "OE3XKN-10", ["WIDE1", "WIDE3-3"], [0, 0], b"!/6,fxRISM} st", dest="APOT2A")
        g = self.st.graph(0, now=T0 + 400, me="OE3GAS-10")
        kinds = {n["call"]: n["kind"] for n in g["nodes"]}
        self.assertEqual(kinds["OE3GAS-10"], "me")
        self.assertEqual(kinds["OE3XWJ-10"], "digi")
        self.assertEqual(kinds["OM0ODX"], "igate")
        self.assertEqual(kinds["OM5KV-15"], "station")
        ways = {tuple(w["chain"]): w for w in g["ways"]}
        self.assertEqual(ways[("OE1IAH-8", "OE6XTR", "OE3XWJ-10", "OE3GAS-10")]["n"], 3)
        self.assertTrue(ways[("OM5KV-15", "OM0ODX", "OE3XWJ-10", "OE3GAS-10")]["inet"])
        self.assertIn(("OE3XKN-10", "OE3GAS-10"), ways)              # heard directly
        me = next(n for n in g["nodes"] if n["call"] == "OE3GAS-10")
        self.assertIsNotNone(me["lat"])                               # our locator

    def test_country(self):
        self.assertEqual(country("OE3GAS-1"), "Austria")
        self.assertEqual(country("OK1KZE-1"), "Czechia")
        self.assertEqual(country("SR6NPK"), "Poland")
        self.assertEqual(country("9A1DD-9"), "Croatia")
        self.assertEqual(country("DB0RDH"), "Germany")
        self.assertEqual(country("HG2PPA-2"), "Hungary")


if __name__ == "__main__":
    unittest.main()
