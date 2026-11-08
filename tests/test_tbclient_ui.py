"""CR66: one UI frame from the client's monitor (e.g. to test VARA FM over KISS)."""

from __future__ import annotations

import asyncio
import tempfile
import unittest

from tbclient.core import UI_MAX_BYTES, ui_request
from tests.test_tbclient import until
from tests.test_tbclient_kiss import FakeHub, kiss_client


class UiRequestTests(unittest.TestCase):
    def test_defaults_and_path(self):
        self.assertEqual(ui_request("", "", "hi"), ("CQ", [], b"hi"))
        self.assertEqual(ui_request("oe3gas-1", " oe3xbs-8, WIDE2-1 ", "x"),
                         ("OE3GAS-1", ["OE3XBS-8", "WIDE2-1"], b"x"))
        self.assertEqual(ui_request("TEST-0", "", "x")[0], "TEST")

    def test_refused(self):
        for dest, via, text in (("CQ", "", ""), ("TOOLONG7", "", "x"), ("CQ", "BAD-16", "x"),
                                ("CQ", ",".join(["D"] * 9), "x"),
                                ("CQ", "", "x" * (UI_MAX_BYTES + 1))):
            with self.assertRaises(ValueError):
                ui_request(dest, via, text)


class UiSendTests(unittest.TestCase):
    def test_ui_over_kiss_is_heard(self):
        async def scenario():
            hub = FakeHub()
            port = await hub.start()
            with tempfile.TemporaryDirectory() as ta, tempfile.TemporaryDirectory() as tb:
                a = kiss_client(ta, port, "OE3GAS")
                b = kiss_client(tb, port, "OE3TEC")
                tasks = [asyncio.create_task(a.run()), asyncio.create_task(b.run())]
                await asyncio.wait_for(a.port.agw_up.wait(), 5)
                await asyncio.wait_for(b.port.agw_up.wait(), 5)
                self.assertIsNone(a.send_ui("TEST", "OE3XBS-8", "VARA test 1"))
                await until(lambda: any(e.get("typ") == "UI" and "VARA test 1" in e.get("text", "")
                                        and e.get("dst") == "TEST" for _, e in b.monitor), 5)
                # the own frame is in the own monitor too
                self.assertTrue(any("VARA test 1" in e.get("text", "") for _, e in a.monitor))
                self.assertEqual(a.send_ui("CQ", "", ""), "no text")
                for t in tasks:
                    t.cancel()
            hub.close()
        asyncio.run(scenario())


if __name__ == "__main__":
    unittest.main()


class OwnUiTests(unittest.TestCase):
    """Direwolf reports our own UI frames as 'T' (monitor mode 'm') - the monitor shows them."""

    def test_t_frame_with_via(self):
        from tbclient.links import own_ui
        f = own_ui("OE3GAS-12", "CQ", b" 1:Fm OE3GAS-12 To CQ Via OE3XBS-8,WIDE2-1* "
                   b"<UI pid=F0 Len=14 >[19:17:25]\rBox wieder up!\r\0")
        self.assertEqual((f.src, f.dest, f.path, f.info),
                         ("OE3GAS-12", "CQ", ["OE3XBS-8", "WIDE2-1"], b"Box wieder up!"))
        self.assertTrue(f.is_ui)

    def test_dispatch(self):
        from tbclient.config import Config
        from tbclient.links import AgwPort
        got = []
        port = AgwPort(Config(), got.append)
        port._dispatch("T", "OE3GAS-12", "CQ", b" 1:Fm OE3GAS-12 To CQ <UI pid=F0 Len=2 >[1:2:3]\rhi\r\0")
        for kind in "IUS":                     # monitor text of received frames: ignored
            port._dispatch(kind, "OE1ABC", "OE3GAS-12", b" 1:Fm OE1ABC To OE3GAS-12 <I>[1:2:3]\rx\r\0")
        self.assertEqual([(f.src, f.info) for f in got], [("OE3GAS-12", b"hi")])
