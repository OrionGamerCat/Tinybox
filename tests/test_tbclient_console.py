"""tbclient window console (I / INFO)."""

from __future__ import annotations

import logging
import unittest

from tbclient.console import Console


class ConsoleTests(unittest.TestCase):
    def test_commands(self):
        out, calls = [], []
        con = Console(lambda: calls.append(1), out=out.append)
        for line in ("i", "INFO", "", "  "):
            con.handle_line(line)
        self.assertEqual(calls, [1, 1])
        con.handle_line("h")
        self.assertIn("I / INFO", out[-1])
        con.handle_line("bogus")
        self.assertIn("unknown command BOGUS", out[-1])

        def broken():
            raise RuntimeError("x")
        Console(broken, out=out.append).handle_line("I")
        self.assertEqual(out[-1], "error: x")

    def test_info_shows_radio_lines(self):
        from tbclient.__main__ import start_block

        class Cfg:                                   # just what start_block reads
            mycall, locator, tinybox_call, auto_connect = "OE3GAS", "JN88", "OE3XTC", True
        import tbclient.__main__ as m
        orig_lines, orig_note = m.config.radio_lines, m.config.link_note
        m.config.radio_lines = lambda cfg: ["radio values: test", "config hint: h"]
        m.config.link_note = lambda cfg: "(x)"
        self.addCleanup(setattr, m.config, "radio_lines", orig_lines)
        self.addCleanup(setattr, m.config, "link_note", orig_note)
        Cfg.link = "kiss"
        log = logging.getLogger("tbclient-test")
        with self.assertLogs(log, "INFO") as cm:
            start_block(log, Cfg(), details=True, head="info")
        text = "\n".join(cm.output)
        self.assertIn("TinyBox client info", text)
        self.assertIn("radio values: test", text)
        with self.assertLogs(log, "INFO") as cm:
            start_block(log, Cfg())
        self.assertNotIn("radio values: test", "\n".join(cm.output))   # only with -v


if __name__ == "__main__":
    unittest.main()
