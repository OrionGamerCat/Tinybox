"""CR83: frame monitor in AGW mode - received frames ('k'/'K') and, with the
TinyBox Direwolf fork, own sent frames ('O')."""

from __future__ import annotations

import asyncio
import logging
import unittest

from prcore.ax25 import frame as ax
from tinybox import framemon
from tinybox.adapters.agw import Frame
from tinybox.adapters.web import HubLogHandler

from tests.test_agw import MYCALL, start, stop
from tests.test_tinybox import make_app


def raw_ui(src: str, dest: str, text: str) -> bytes:
    """A UI frame as Direwolf hands it out raw: addresses, control, PID, info."""
    return ax.ui_frame(dest, src, text.encode()).encode()


def raw_rr(src: str, dest: str, nr: int) -> bytes:
    return ax.s_frame("RR", dest, src, nr, command=True, pf=True).encode()


class Catch(logging.Handler):
    def __init__(self):
        super().__init__()
        self.frames = []

    def emit(self, record):
        self.frames.append(record.frame)


class AgwMonitorTests(unittest.TestCase):
    def setUp(self):
        self.catch = Catch()
        framemon.flog.addHandler(self.catch)

    def tearDown(self):
        framemon.flog.removeHandler(self.catch)

    def run_with(self, frames_from_dw, own_ack: bool):
        async def scenario():
            app = make_app()
            dw, server, adapter, task = await start(app)
            await asyncio.sleep(0.1)
            if own_ack:
                dw.send(Frame("O"))                      # the fork's answer to 'O'
            for f in frames_from_dw:
                dw.send(f)
            await asyncio.sleep(0.2)
            await stop(server, task, dw)
            return dw, adapter

        return asyncio.run(scenario())

    def test_monitor_asked_once_per_connect(self):
        dw, adapter = self.run_with([], own_ack=False)
        kinds = [f.kind for f in dw.frames]
        self.assertEqual(kinds.count("k"), 1)            # a toggle in Direwolf: only once
        self.assertEqual(kinds.count("O"), 1)
        self.assertFalse(adapter.own_frames)

    def test_received_frames(self):
        ui = raw_ui("OE3GAS-12", "CQ", "test")
        rr = raw_rr("OE3TEC", MYCALL, 3)
        dw, adapter = self.run_with([
            Frame("K", 0, call_from="OE3GAS-12", call_to="CQ", data=b"\x00" + ui),
            Frame("K", 0, call_from="OE3TEC", call_to=MYCALL, data=b"\x00" + rr),
            Frame("K", 1, call_from="OE3XYZ", call_to="CQ", data=b"\x10" + ui),  # other channel
        ], own_ack=False)
        got = [(e["src"], e["dst"], e["typ"].split()[0], e["tx"]) for e in self.catch.frames]
        self.assertEqual(got, [("OE3GAS-12", "CQ", "UI", False), ("OE3TEC", MYCALL, "RR", False)])
        self.assertEqual(self.catch.frames[0]["text"], "test")

    def test_own_frames_with_fork(self):
        rr = raw_rr(MYCALL, "OE3TEC", 5)
        dw, adapter = self.run_with([
            Frame("O", 0, call_from=MYCALL, call_to="OE3TEC", data=b"\x00" + rr),
        ], own_ack=True)
        self.assertTrue(adapter.own_frames)
        self.assertEqual(len(self.catch.frames), 1)
        e = self.catch.frames[0]
        self.assertEqual((e["src"], e["dst"], e["tx"]), (MYCALL, "OE3TEC", True))
        self.assertTrue(e["typ"].startswith("RR"))

    def test_counters_not_counted(self):
        from tinybox import logsetup
        before = logsetup.counters.frames_in
        ui = raw_ui("OE3GAS-12", "CQ", "test")
        self.run_with([Frame("K", 0, data=b"\x00" + ui)] * 3, own_ack=False)
        self.assertEqual(logsetup.counters.frames_in, before + 2)     # only R and X answers

    def test_ui_log_line_hidden_with_own_frames(self):
        class Hub:
            def __init__(self):
                self.items = []

            def push(self, item):
                self.items.append(item)

        hub = Hub()
        handler = HubLogHandler(hub, None)
        logger = logging.getLogger("tinybox.monitor.agw")
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        try:
            logger.info("UI %s > %s", "BEACON", "hi", extra={"ui_hex": "6869", "framed": False})
            logger.info("UI %s > %s", "BEACON", "hi", extra={"ui_hex": "6869", "framed": True})
        finally:
            logger.removeHandler(handler)
        self.assertEqual(len(hub.items), 1)


if __name__ == "__main__":
    unittest.main()
