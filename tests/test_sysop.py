"""Sysop console tests."""

from __future__ import annotations

import asyncio
import unittest

from tinybox.adapters.sysop import MonitorFilter, SysopConsole
from tests.test_tinybox import FakeTransport, login, make_app


class ConsoleTests(unittest.TestCase):
    def setUp(self):
        self.app = make_app()
        self.app.stop_event = asyncio.Event()
        self.output = []
        self.filter = MonitorFilter(True)
        self.console = SysopConsole(self.app, self.filter, self.output.append)
        self.console.start()

    def run_cmd(self, *lines: str) -> str:
        self.output.clear()
        for line in lines:
            self.console.handle_line(line)
        return "".join(self.output)

    def test_banner_and_sysop_prompt(self):
        out = "".join(self.output)
        self.assertIn("sysop console", out)
        self.assertIn("TinyBox SYSOP", out)

    def test_help_has_console_part(self):
        out = self.run_cmd("H")
        self.assertIn("Send bulletin", out)
        self.assertIn("SHUTDOWN", out)

    def test_bye_does_not_close_console(self):
        out = self.run_cmd("B")
        self.assertIn("Use SHUTDOWN", out)
        self.assertFalse(self.console.session.closed)

    def test_send_bulletin_from_console(self):
        out = self.run_cmd("SB ALL", "Net", "Tonight 20:00", "/EX")
        self.assertIn("Msg 1 saved.", out)
        msg = self.app.store.get(1)
        self.assertEqual((msg.origin, msg.from_call), ("sysop", "OE3GAS"))

    def test_console_words_inside_message_body_are_text(self):
        self.run_cmd("S OE1ABC", "hi", "STATUS", "W", "/EX")
        self.assertEqual(self.app.store.get(1).body, "STATUS\nW")

    def test_who_and_disc(self):
        self.assertIn("No users connected.", self.run_cmd("W"))
        s, t = login(self.app, "OE1ABC-7")
        self.app.registry.add(s)
        self.assertIn("OE1ABC-7", self.run_cmd("W"))
        self.assertIn("OE5XYZ is not connected.", self.run_cmd("DISC OE5XYZ"))
        out = self.run_cmd("DISC OE1ABC")  # base call matches any SSID
        self.assertIn("OE1ABC-7 disconnected.", out)
        self.assertIn("Disconnected by sysop", t.take())
        self.assertTrue(t.closed)

    def test_monitor_toggle(self):
        self.assertIn("OFF", self.run_cmd("MON OFF"))
        self.assertFalse(self.filter.enabled)
        self.assertIn("ON", self.run_cmd("mon"))
        self.assertTrue(self.filter.enabled)

    def test_status(self):
        self.app.service.create(from_call="OE1ABC", to_call="OE3GAS", type="P",
                                subject="s", body="b", origin="radio")
        out = self.run_cmd("STATUS")
        self.assertIn("Direwolf:  not started", out)
        self.assertIn("1 private", out)
        self.assertIn("1 unread", out)

    def test_fwd_without_call_forwards_with_every_partner(self):
        """FWD alone calls all partners one after the other; FWD call only that one."""
        calls = []

        class Result:
            def summary(self):
                return "ok"

        class StubForward:
            cfg = type("C", (), {"partners": {"OE3GAS": None, "OE1XAB": None}})()
            busy = {"OE1XAB"}

            async def call(self, call):
                calls.append(call)
                return Result()

            def status_lines(self):
                return ["Forward: 2 partner(s)"]

            def _spawn(self, coro):
                asyncio.run(coro)

        self.app.forward = StubForward()
        out = self.run_cmd("FWD")
        self.assertEqual(calls, ["OE3GAS"])
        self.assertIn("Forward OE3GAS: ok", out)
        self.assertIn("Forward OE1XAB: already in a session.", out)
        calls.clear()
        self.run_cmd("FWD oe3gas")
        self.assertEqual(calls, ["OE3GAS"])
        self.assertIn("Forward: 2 partner(s)", self.run_cmd("FWQ"))

    def test_shutdown(self):
        self.assertIn("Shutting down", self.run_cmd("SHUTDOWN"))
        self.assertTrue(self.app.stop_event.is_set())


if __name__ == "__main__":
    unittest.main()
