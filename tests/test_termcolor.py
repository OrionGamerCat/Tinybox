"""prcore/termcolor.py: console format, [WARN]/[ERROR] tags, colours only when asked."""

import io
import logging
import unittest

from prcore import termcolor


class TermcolorTests(unittest.TestCase):
    def run_log(self, color: bool, fn) -> str:
        buf = io.StringIO()
        handler = logging.StreamHandler(buf)
        handler.setFormatter(termcolor.ConsoleFormatter("[test]", color))
        log = logging.getLogger("termcolor-test")
        log.handlers = [handler]
        log.propagate = False
        log.setLevel(logging.DEBUG)
        fn(log)
        return buf.getvalue()

    def test_plain_tags_and_alignment(self):
        out = self.run_log(False, lambda log: (
            termcolor.kv(log, "Your call", "OE3XXX"),
            termcolor.kv(log, "Your preferred TinyBox", "OE3GAS-1"),
            termcolor.blank(log),
            log.warning("careful"),
            log.error("Direwolf not reachable"),
            log.info("connected", extra=termcolor.OK)))
        lines = [line[len("[test] 00:00:00 "):] for line in out.splitlines()]
        self.assertEqual(lines[0], "Your call:              OE3XXX")
        self.assertEqual(lines[1], "Your preferred TinyBox: OE3GAS-1")
        self.assertRegex(out.splitlines()[2], r"^\[test\] \d\d:\d\d:\d\d$")
        self.assertEqual(lines[3], "[WARN] careful")
        self.assertEqual(lines[4], "[ERROR] Direwolf not reachable")
        self.assertEqual(lines[5], "connected")
        self.assertNotIn("\033", out)

    def test_colour_codes(self):
        out = self.run_log(True, lambda log: (
            log.error("bad"), log.info("ok", extra=termcolor.OK),
            termcolor.kv(log, "Web GUI on HTTP", "http://x/", url=True)))
        self.assertIn(termcolor.RED, out)
        self.assertIn(termcolor.GREEN + "ok", out)
        self.assertIn(termcolor.BLUE_UL + "http://x/", out)
        self.assertIn("[ERROR] bad", out)

    def test_use_color(self):
        self.assertFalse(termcolor.use_color("no"))
        self.assertFalse(termcolor.use_color("auto", io.StringIO()))   # not a console
        self.assertEqual(termcolor.check_mode("Yes"), "yes")
        with self.assertRaises(ValueError):
            termcolor.check_mode("bunt")


if __name__ == "__main__":
    unittest.main()


class WrapTests(unittest.TestCase):
    """Start blocks of TinyBox, client and kisshub: 80 columns."""

    def test_wrap_items_and_line(self):
        from prcore import termcolor as tc
        self.assertEqual(tc.value_width("[tinyb]"), 80 - 17 - tc.LABEL_WIDTH - 1)
        items = tc.wrap_items("[tinyb]", [("Adapters", "a=on " * 12), None,
                                          ("Data", "C:\\a\\very\\long\\path\\" * 3)])
        for x in items:
            if x and x[0] != "Data":
                self.assertLessEqual(17 + len(tc.kv_plain(*x)), 80)
        self.assertEqual(items[-1][1], "C:\\a\\very\\long\\path\\" * 3)     # not broken
        lines = tc.wrap_line("word " * 30, 40)
        self.assertTrue(all(len(x) <= 40 for x in lines))
        self.assertTrue(lines[1].startswith("  "))
        self.assertEqual(tc.wrap_line("short", 40), ["short"])
