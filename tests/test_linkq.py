"""Link quality: parsing, window, bars, STAT command, AGW 'Q' (PLANUNG.md section 14)."""

from __future__ import annotations

import asyncio
import dataclasses
import unittest

from tinybox import linkq
from tinybox.adapters import agw
from tinybox.adapters.agw import Frame

from tests.test_agw import FakeDirewolf, MYCALL, stop
from tests.test_tinybox import make_app

LINE = ("v=1 state=3 i_new=21 i_retry=0 bytes_new=2189 bytes_retry=0 i_rx=13 retry_rx=0 "
        "rej_rx=0 rej_tx=0 t1_exp=0 rnr_rx=0 srt=1.38 t1v=2.76 rc=0 unack=4 age=2405")


def counters(**kw) -> dict:
    c = {k: 0 for k in linkq.FIELDS_INT} | {"srt": 1.0, "t1v": 2.0, "age": 0.0}
    c.update(kw)
    return c


class ParseTests(unittest.TestCase):
    def test_line_from_the_fork(self):
        c = linkq.parse(LINE)
        self.assertEqual((c["i_new"], c["i_rx"], c["unack"], c["srt"], c["age"]),
                         (21, 13, 4, 1.38, 2405.0))

    def test_no_link_or_garbage(self):
        self.assertIsNone(linkq.parse("v=1 none"))
        self.assertIsNone(linkq.parse("v=9 i_new=1"))
        self.assertEqual(linkq.parse("v=2 i_new=1 bytes_rx=50 tx_busy_ms=700 baud=1200")["baud"], 1200)
        self.assertIsNone(linkq.parse("v=1 i_new=x"))
        self.assertIsNone(linkq.parse(""))

    def test_unknown_keys_are_ignored(self):
        self.assertEqual(linkq.parse(LINE + " future=7")["i_new"], 21)


class EvaluateTests(unittest.TestCase):
    def test_few_frames_count_events(self):
        """07.11.2026: below 20 frames the events count, the result is tentative."""
        q = linkq.LinkQuality()
        q.add(counters(i_new=5, i_rx=4, age=60), now=1000)
        r = q.evaluate(now=1000)
        self.assertEqual((r.bars, r.tentative), (5, True))      # 5 clean frames: very good
        self.assertIsNone(r.out.loss)                           # no percentage yet
        for retry, bars in ((1, 4), (2, 3), (4, 1), (5, 0), (9, 0)):
            q = linkq.LinkQuality()
            q.add(counters(i_new=5, i_retry=retry, age=60), now=1000)
            self.assertEqual(q.evaluate(now=1000).bars, bars, retry)
        q = linkq.LinkQuality()                                 # T1 costs a bar here too
        q.add(counters(i_new=5, t1_exp=1, age=60), now=1000)
        self.assertEqual(q.evaluate(now=1000).bars, 4)

    def test_grey_without_frames(self):
        q = linkq.LinkQuality()
        q.add(counters(age=60), now=1000)
        r = q.evaluate(now=1000)
        self.assertIsNone(r.bars)
        self.assertEqual(linkq.bar_text(r.bars), "-----")

    def test_one_direction_is_enough(self):
        q = linkq.LinkQuality()
        q.add(counters(i_new=25, i_rx=3, age=60), now=1000)
        r = q.evaluate(now=1000)
        self.assertEqual((r.bars, r.tentative), (5, False))    # out has 25: not tentative
        self.assertEqual(r.out.loss, 0.0)
        self.assertIsNone(r.inn.loss)

    def test_bars_follow_the_worse_direction(self):
        q = linkq.LinkQuality()
        # out: 6 of 40 repeated = 15 % -> 3 bars; in: 1 of 40 = 2.5 % -> 5 bars
        q.add(counters(i_new=34, i_retry=6, i_rx=40, rej_tx=1, age=60), now=1000)
        r = q.evaluate(now=1000)
        self.assertAlmostEqual(r.out.loss, 15.0)
        self.assertAlmostEqual(r.inn.loss, 2.5)
        self.assertEqual(r.bars, 3)
        self.assertEqual(linkq.bar_text(3), "###..")
        self.assertEqual(linkq.bar_text(0), "X....")

    def test_t1_costs_one_bar_each(self):
        q = linkq.LinkQuality()
        q.add(counters(i_new=30, t1_exp=2, age=60), now=1000)
        self.assertEqual(q.evaluate(now=1000).bars, 3)
        q2 = linkq.LinkQuality()
        q2.add(counters(i_new=30, t1_exp=9, age=60), now=1000)
        self.assertEqual(q2.evaluate(now=1000).bars, 0)      # never below the red bar

    def test_thresholds(self):
        # 12.10.2026: 5 bars up to 5 %, 4 up to 10, 3 up to 20, 2 up to 35, 1 up to 50, then red (0)
        for retry, bars in ((0, 5), (5, 5), (6, 4), (10, 4), (15, 3), (20, 3), (30, 2), (40, 1), (51, 0)):
            q = linkq.LinkQuality()
            q.add(counters(i_new=100 - retry, i_retry=retry, age=60), now=1000)
            self.assertEqual(q.evaluate(now=1000).bars, bars, retry)

    def test_window_shows_now_not_the_past(self):
        """Bad start, then 60 clean frames: the window (50) no longer sees the losses."""
        q = linkq.LinkQuality()
        q.add(counters(i_new=20, i_retry=10, age=60), now=1000)
        self.assertEqual(q.evaluate(now=1000).bars, 2)         # 33 % lost
        q.add(counters(i_new=80, i_retry=10, age=120), now=1060)
        r = q.evaluate(now=1060)
        self.assertEqual((r.out.frames, r.out.lost, r.bars), (60, 0, 5))

    def test_window_max_30_minutes(self):
        q = linkq.LinkQuality()
        q.add(counters(i_new=20, i_retry=10, age=60), now=1000)
        q.add(counters(i_new=25, i_retry=10, age=60 + 1900), now=2900)   # 31 min later
        r = q.evaluate(now=2900)
        self.assertEqual(r.out.frames, 0)      # only 5 new frames, old sample is gone
        self.assertIsNone(r.bars)

    def test_long_link_without_baseline(self):
        """Link older than 30 min: the first sample is the baseline, no result yet."""
        q = linkq.LinkQuality()
        q.add(counters(i_new=500, i_retry=50, age=5000), now=1000)
        self.assertIsNone(q.evaluate(now=1000).bars)
        q.add(counters(i_new=530, i_retry=50, age=5030), now=1030)
        self.assertEqual(q.evaluate(now=1030).bars, 5)

    def test_link_restarted(self):
        q = linkq.LinkQuality()
        q.add(counters(i_new=90, i_retry=10, age=600), now=1000)
        q.add(counters(i_new=30, age=30), now=1030)            # counters fell: new link
        r = q.evaluate(now=1030)
        self.assertEqual((r.out.frames, r.bars), (30, 5))


class StatCommandTests(unittest.TestCase):
    def _session(self, call="OE1ABC"):
        from tinybox.session import Session
        from tests.test_tinybox import FakeTransport
        app = make_app()
        t = FakeTransport()
        s = Session(call, app.service, app.cfg, t, origin="radio")
        s.start()
        t.take()
        return app, s, t

    def test_own_link(self):
        app, s, t = self._session()
        q = linkq.LinkQuality()
        q.add(counters(i_new=37, i_retry=3, i_rx=40, rej_tx=1, bytes_new=2100, bytes_retry=64,
                       age=60, srt=1.4))
        app.service.links["OE1ABC"] = q
        s.handle_line("STAT")
        out = t.take()
        self.assertIn("last 50 frames", out)
        self.assertIn("OE1ABC     ####.", out)          # 8 % -> 4 bars
        self.assertIn("8%", out)
        self.assertIn("2.1k/64", out)
        self.assertIn("1.4s", out)

    def test_all_and_none(self):
        app, s, t = self._session()
        s.handle_line("STAT")
        self.assertIn("No link quality data", t.take())
        s.handle_line("STAT ALL")
        self.assertIn("No radio connections", t.take())
        q = linkq.LinkQuality()
        q.add(counters(i_new=5, age=10))
        app.service.links["OE3TEC"] = q
        s.handle_line("stat alle")
        self.assertIn("OE3TEC     ~~~~~", t.take())              # 5 clean frames: tentative
        s.handle_line("STAT x")
        self.assertIn("Usage: STAT", t.take())


class QDirewolf(FakeDirewolf):
    """FakeDirewolf that also answers 'Q' like the TinyBox fork (or not at all)."""

    def __init__(self, answer: bool = True) -> None:
        super().__init__()
        self.answer = answer
        self.q_asked = 0

    async def handle(self, reader, writer) -> None:
        self.writer = writer
        try:
            while True:
                f = await agw.read_frame(reader)
                self.frames.append(f)
                if f.kind == "Q":
                    self.q_asked += 1
                    if self.answer:
                        self.send(Frame("Q", call_from=f.call_from, call_to=f.call_to,
                                        data=LINE.replace("age=2405", "age=120").encode()))
                elif f.kind == "Y":
                    self.send(Frame("Y", call_from=f.call_from, call_to=f.call_to,
                                    data=b"\x00\x00\x00\x00"))
                elif f.kind == "R":
                    self.send(Frame("R", data=b"\x01\x00\x00\x00\x07\x00\x00\x00"))
                elif f.kind == "X":
                    self.send(Frame("X", call_from=f.call_from, data=b"\x01"))
                    self.registered.set()
                elif f.kind == "d":
                    self.send(Frame("d", call_from=f.call_to, call_to=f.call_from,
                                    data=b"*** DISCONNECTED\r"))
                    self.disconnected.set()
        except (asyncio.IncompleteReadError, ConnectionError):
            pass


async def start_q(app, dw):
    server = await asyncio.start_server(dw.handle, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    app.cfg.direwolf = dataclasses.replace(app.cfg.direwolf, agw_port=port, reconnect_sec=1,
                                           quality_poll_sec=1)
    adapter = agw.AgwAdapter(app)
    task = asyncio.create_task(adapter.run())
    await asyncio.wait_for(dw.registered.wait(), 5)
    return server, adapter, task


class AgwQualityTests(unittest.TestCase):
    def test_poll_and_stat_over_radio(self):
        async def scenario():
            app = make_app()
            dw = QDirewolf()
            server, adapter, task = await start_q(app, dw)
            dw.connect("OE1ABC-7")
            await asyncio.sleep(1.5)                      # one poll round
            dw.data("OE1ABC-7", "STAT\rB\r")
            await asyncio.wait_for(dw.disconnected.wait(), 5)
            await asyncio.sleep(0.1)
            links_after = dict(app.service.links)
            await stop(server, task, dw)
            return dw, adapter, links_after

        dw, adapter, links_after = asyncio.run(scenario())
        qs = [f for f in dw.frames if f.kind == "Q"]
        self.assertTrue(qs)
        self.assertEqual((qs[0].call_from, qs[0].call_to), (MYCALL, "OE1ABC-7"))
        self.assertTrue(adapter.q_supported)
        out = dw.output_for("OE1ABC-7")
        self.assertIn("OE1ABC-7   #####", out)
        self.assertEqual(links_after, {})               # gone with the connection

    def test_plain_direwolf_is_asked_once(self):
        async def scenario():
            app = make_app()
            dw = QDirewolf(answer=False)
            server, adapter, task = await start_q(app, dw)
            agw.Q_TIMEOUT, saved = 0.5, agw.Q_TIMEOUT
            try:
                dw.connect("OE1ABC-7")
                await asyncio.sleep(4)
            finally:
                agw.Q_TIMEOUT = saved
            await stop(server, task, dw)
            return dw, adapter

        dw, adapter = asyncio.run(scenario())
        self.assertEqual(dw.q_asked, 1)
        self.assertIs(adapter.q_supported, False)


if __name__ == "__main__":
    unittest.main()


# --- chat: receive quote, % event, lost link (PLANUNG.md 14.3-14.5) ----------------

def _radio_client(app, call, ui=True, num=False):
    from tinybox.session import Session
    from tests.test_tinybox import FakeTransport
    t = FakeTransport()
    s = Session(call, app.service, app.cfg, t, origin="radio")
    s.start()
    s.handle_line(f"//CLIENT TB1 v=2026.10.11 caps=CHAT{',UI' if ui else ''}{',NUM' if num else ''}")
    t.take()
    return s, t


class ChatQualityTests(unittest.TestCase):
    def setUp(self):
        from tests.test_chat import chat_app
        self.app = chat_app()
        self.ui: list[tuple[str, str]] = []
        self.app.service.chat.ui_send = lambda dest, text: self.ui.append((dest, text))
        self.a, self.ta = _radio_client(self.app, "OE3TEC")
        self.b, self.tb = _radio_client(self.app, "OE1ABC")
        self.a.handle_line("C 1")
        self.b.handle_line("C 1")
        self.hub = self.app.service.chat

    def test_receive_window_and_lost(self):
        self.assertIsNotNone(self.a.ui_rx)
        for i in range(30):
            self.b.handle_line(f"line {i}")
        seqs = [e[1] for e in self.a.ui_rx.events]
        self.a.handle_line(f"//RESEND {seqs[-3]:X}-{seqs[-2]:X}")     # 2 missed, sent again
        self.assertIn(f"OE1ABC: line 28", self.ta.take())
        self.a.handle_line(f"//LOST {seqs[0]:X}-{seqs[0]:X}")         # 1 missed, not resent
        self.assertEqual(self.ta.take(), "")
        r = linkq.result_for(self.app.service, "OE3TEC", self.a)
        self.assertEqual((r.rx.frames, r.rx.lost), (len(seqs), 3))
        self.assertAlmostEqual(r.rx_quote, 100 - 300 / len(seqs))
        self.assertEqual(r.bars, 4)                         # 3 of 31 = 9.7 % -> 4 bars

    def test_quality_event_on_change_only(self):
        for i in range(25):
            self.b.handle_line(f"x{i}")
        self.ui.clear()
        self.hub.quality_tick(self.app.service, now=1000)
        texts = [t for _, t in self.ui]
        self.assertEqual(len(texts), 1)
        self.assertRegex(texts[0], r"^#[0-9A-F]+ %1 5 2 5$")        # member numbers (CR33)
        self.assertTrue(self.ta.take().endswith("%OE3TEC 5 OE1ABC 5\r"))  # old client: I-frame
        self.hub.quality_tick(self.app.service, now=1030)           # nothing changed
        self.assertEqual(len(self.ui), 1)
        self.a.handle_line("//LOST 0-9")                              # OE3TEC missed 10
        self.hub.quality_tick(self.app.service, now=1040)           # within the minute
        self.assertEqual(len(self.ui), 1)
        self.hub.quality_tick(self.app.service, now=1070)
        self.assertEqual(len(self.ui), 2)
        self.assertIn("%1 1 2 5", self.ui[-1][1])
        # not in the stored history
        self.assertNotIn("%", " ".join(c.text for c in self.app.store.chat_recent(
            "TREFF", "2000-01-01T00:00:00Z", 100)))

    def test_lost_connection_event(self):
        self.ui.clear()
        self.b.end(lost=True)
        texts = [t.split(" ", 1)[1] for _, t in self.ui]       # UI frames to TBCHAT-1
        self.assertEqual(texts, ["-2", "!Connection to OE1ABC lost"])

    def test_qstat_line_for_num_clients(self):
        """CR33: the %Q line with the numbers behind the bars - no sequence number,
        only to NUM clients, at most every two minutes, only when changed."""
        c, tc = _radio_client(self.app, "OE3GAS", num=True)       # member 3
        c.handle_line("C 1")
        for i in range(25):
            self.b.handle_line(f"x{i}")
        self.ui.clear(); tc.take()
        self.hub.quality_tick(self.app.service, now=1000)
        texts = [t for _, t in self.ui]
        self.assertEqual(len(texts), 2)
        self.assertRegex(texts[0], r"^#[0-9A-F]+ %1 5 2 5 3 5$")
        # rx_sent counts every UI event the client should have heard (joins too)
        self.assertEqual(texts[1], "%Q 1 5 0 0 0 0 0 0 0 0 0 28 0 0;2 5 0 0 0 0 0 0 0 0 0 27 0 0;"
                                   "3 5 0 0 0 0 0 0 0 0 0 26 0 0")
        self.assertEqual(tc.take(), "")                   # UI client: no I-frame copy
        self.assertEqual(self.ta.take().count("%Q"), 0)   # old client: nothing
        self.hub.quality_tick(self.app.service, now=1030)
        self.assertEqual(len(self.ui), 2)                 # unchanged
        self.a.handle_line("//LOST 0-9")
        self.hub.quality_tick(self.app.service, now=1070)
        self.assertEqual(len(self.ui), 3)                 # % after a minute, %Q not yet
        self.hub.quality_tick(self.app.service, now=1130)
        self.assertEqual(len(self.ui), 4)
        self.assertRegex(self.ui[-1][1], r"^%Q 1 [12] 0 0 0 0 0 0 0 0 0 \d+ 10 0;")
        # the client side
        from tbclient import proto
        stats = proto.parse_qstat(self.ui[-1][1])
        self.assertEqual(stats[1]["rx_missed"], 10)

    def test_qstat_not_while_all_bars_unknown(self):
        """No %Q line while no member has bars yet ('?' = only interim counts)."""
        c, tc = _radio_client(self.app, "OE3GAS", num=True)
        c.handle_line("C 2")                              # alone in board 2, few frames
        self.ui.clear(); tc.take()
        self.hub.quality_tick(self.app.service, now=1000)
        self.assertFalse(any(t.startswith("%Q") for _, t in self.ui))
        self.assertNotIn("%Q", tc.take())

    def test_qstat_alone_as_iframe_only(self):
        """Only one station in the board: its %Q goes to it as I-frame, no UI frame."""
        c, tc = _radio_client(self.app, "OE3GAS", num=True)
        c.handle_line("C 2")
        for i in range(25):
            c.handle_line(f"x{i}")                        # own lines: rx_sent counts up
        self.ui.clear(); tc.take()
        self.hub.quality_tick(self.app.service, now=1000)
        self.assertFalse(any(t.startswith("%Q") for _, t in self.ui))
        self.assertRegex(tc.take(), r"%Q 1 5 ")

    def test_stat_shows_receive_quote(self):
        for i in range(25):
            self.b.handle_line(f"x{i}")
        self.ta.take()
        self.a.handle_line("/Q")
        self.a.handle_line("STAT ALL")
        out = self.ta.take()
        self.assertIn("RXq", out)
        self.assertRegex(out, r"OE1ABC +#####")


class ClientQualityTests(unittest.TestCase):
    def test_parse(self):
        from tbclient import proto
        ev = proto.parse_event("#54 %OE3TEC 4 OE1ABC ?")
        self.assertEqual((ev.kind, ev.bars), ("quality", {"OE3TEC": 4, "OE1ABC": None}))
        ev = proto.parse_event("#54 %2 4 3 ?")                     # member numbers (CR33)
        self.assertEqual((ev.kind, ev.bars), ("quality", {2: 4, 3: None}))
        self.assertIsNone(proto.parse_qstat("%Q 2 4 48 2"))
        self.assertEqual(proto.parse_qstat("%Q 2 4 48 2 50 3 1 1 0 41 1 48 2 14")[2]["bytes_new"],
                         4100)
        self.assertIsNone(proto.parse_event("#54 %OE3TEC 9"))
        self.assertIsNone(proto.parse_event("#54 %OE3TEC"))

    def test_core(self):
        import tempfile
        from tbclient import proto
        from tbclient.core import ClientCore
        from tests.test_tbclient import client_cfg

        async def scenario():
            with tempfile.TemporaryDirectory() as tmp:
                core = ClientCore(client_cfg(tmp, link="telnet"))
                sent: list[str] = []
                core.link.send_line = sent.append
                core.board = {"n": 1, "name": "TREFF", "keep": "7d"}
                core._event(proto.Event(1, "join", "OE3TEC"))
                core._event(proto.parse_event("#2 %OE3TEC 3 OE3GAS ?"))
                self.assertEqual(core.snapshot()["quality"], {"OE3TEC": 3, "OE3GAS": None})
                self.assertEqual([m["kind"] for m in core.messages], ["join"])
                core._event(proto.Event(50, "line", "OE3TEC", text="far ahead"))
                self.assertEqual(sent[-1], "//LOST 3-31")             # gap 47 > 32
                core._event(proto.Event(52, "line", "OE3TEC", text="x"))
                self.assertEqual(sent[-1], "//RESEND 33-33")
                core._event(proto.Event(53, "leave", "OE3TEC"))
                self.assertEqual(core.snapshot()["quality"], {"OE3GAS": None})
                # member numbers (CR33): join with number, % and %Q by number, leave by number
                core._event(proto.parse_event("#36 +2 OE3TEC /-"))
                core._event(proto.parse_event("#37 +3 OE1ABC"))
                core._event(proto.parse_event("#38 %2 4 3 ?"))
                self.assertEqual(core.snapshot()["quality"], {"OE3TEC": 4, "OE1ABC": None})
                core._qstat("%Q 2 3 48 2 50 3 1 1 0 41 1 48 2 14")
                snap = core.snapshot()
                self.assertEqual(snap["linkq"]["OE3TEC"]["out_frames"], 48)
                self.assertEqual(snap["quality"]["OE3TEC"], 3)
                core._event(proto.parse_event("#39 -2"))
                self.assertEqual(core.snapshot()["members"], ["OE1ABC"])
                self.assertEqual(core.snapshot()["linkq"], {})
                core._event(proto.parse_event("#3A +2 OE9XYZ"))       # number reused
                self.assertEqual(core.numbers, {3: "OE1ABC", 2: "OE9XYZ"})

        asyncio.run(scenario())


class LocalStationTests(unittest.TestCase):
    """A client on the same PC over AXUDP: no link quality at all."""

    def test_axudp_session_has_no_result(self):
        from types import SimpleNamespace
        q = SimpleNamespace(evaluate=lambda now, rx=None: "result")
        service = SimpleNamespace(links={"OE3GAS": q})
        radio = SimpleNamespace(origin="radio", ui_rx=None)
        local = SimpleNamespace(origin="axudp", ui_rx=None)
        self.assertIsNotNone(linkq.result_for(service, "OE3GAS", radio))
        self.assertIsNone(linkq.result_for(service, "OE3GAS", local))
        self.assertTrue(linkq.is_local(local))
        self.assertFalse(linkq.is_local(None))
