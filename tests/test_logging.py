"""Logging for debugging: daily file, columns, session context, LOG (CR32)."""

from __future__ import annotations

import asyncio
import dataclasses
import logging
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

from prcore import termcolor
from tinybox import config, logsetup
from tinybox.adapters.sysop import MonitorFilter, SysopConsole
from tests.test_tinybox import ROOT, login, make_app


def read(path: Path) -> list[str]:
    """The log file without the three legend lines."""
    return [line for line in path.read_text(encoding="utf-8").splitlines()
            if not line.startswith("#")]


class DailyFileTests(unittest.TestCase):
    """One file per day, append mode - a restart must not start a new file."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.addCleanup(self.tmp.cleanup)

    def handler(self, **kw) -> logsetup.DailyFileHandler:
        h = logsetup.DailyFileHandler(self.dir, **kw)
        h.setFormatter(logsetup.Formatter())
        h.addFilter(logsetup.ContextFilter())
        self.addCleanup(h.close)
        return h

    def record(self, msg: str, name: str = "tinybox.adapters.agw",
               level: int = logging.INFO) -> logging.LogRecord:
        return logging.LogRecord(name, level, __file__, 1, msg, (), None)

    def test_file_is_named_after_the_day(self):
        h = self.handler()
        self.assertEqual(h.path.name, f"tinybox-{date.today():%Y-%m-%d}.log")

    def test_legend_is_the_header_of_a_new_file(self):
        h = self.handler()
        head = h.path.read_text(encoding="utf-8").splitlines()[:3]
        self.assertEqual(len(head), 3)
        self.assertTrue(all(line.startswith("#") for line in head))
        self.assertIn("component", head[0])
        self.assertIn("MARK:", head[2])

    def test_restart_appends_instead_of_starting_a_new_file(self):
        first = self.handler()
        first.handle(self.record("before the restart"))
        first.close()
        second = self.handler()                       # same day, new process
        second.handle(self.record("after the restart"))
        self.assertEqual(second.path, first.path)
        lines = read(first.path)
        self.assertEqual(len(lines), 2)
        self.assertIn("before the restart", lines[0])
        self.assertIn("after the restart", lines[1])
        self.assertEqual(len(list(self.dir.glob("tinybox-*.log"))), 1)

    def test_day_change_opens_the_next_file(self):
        h = self.handler()
        yesterday = date.today() - timedelta(days=1)
        h._day = yesterday                            # as if it had run overnight
        h.handle(self.record("after midnight"))
        self.assertEqual(h.path.name, f"tinybox-{date.today():%Y-%m-%d}.log")
        self.assertIn("after midnight", read(h.path)[0])

    def test_size_brake_continues_in_part_two(self):
        h = self.handler(max_bytes=400)
        for i in range(20):
            h.handle(self.record(f"line {i} " + "x" * 60))
        self.assertTrue((self.dir / f"tinybox-{date.today():%Y-%m-%d}.2.log").exists())

    def test_keep_days_deletes_older_files(self):
        old = self.dir / f"tinybox-{date.today() - timedelta(days=20):%Y-%m-%d}.log"
        recent = self.dir / f"tinybox-{date.today() - timedelta(days=3):%Y-%m-%d}.log"
        other = self.dir / "notes.txt"
        for path in (old, recent, other):
            path.write_text("x", encoding="utf-8")
        self.handler(keep_days=14)
        self.assertFalse(old.exists())
        self.assertTrue(recent.exists())
        self.assertTrue(other.exists(), "only our own log files are deleted")

    def test_keep_days_zero_keeps_everything(self):
        old = self.dir / f"tinybox-{date.today() - timedelta(days=400):%Y-%m-%d}.log"
        old.write_text("x", encoding="utf-8")
        self.handler(keep_days=0)
        self.assertTrue(old.exists())


class SessionNumberAcrossRestartTests(unittest.TestCase):
    """A restart appends, so #7 must mean one connection in the whole file."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.addCleanup(self.tmp.cleanup)
        self.addCleanup(logsetup.seed_session_ids, 0)

    def write(self, *lines: str) -> logsetup.DailyFileHandler:
        h = logsetup.DailyFileHandler(self.dir)
        h.setFormatter(logsetup.Formatter())
        h.addFilter(logsetup.ContextFilter())
        self.addCleanup(h.close)
        for ctx, msg in enumerate(lines, start=1):
            record = logging.LogRecord("tinybox.monitor", logging.INFO,
                                       __file__, 1, msg, (), None)
            record.ctx = ctx if isinstance(ctx, str) else f"#{ctx} OE3TEC"
            h.handle(record)
        return h

    def test_highest_session_id_is_found(self):
        h = self.write("< L", "< B", "< H")
        self.assertEqual(h.highest_session_id(), 3)

    def test_empty_file_starts_at_zero(self):
        h = logsetup.DailyFileHandler(self.dir)
        self.addCleanup(h.close)
        self.assertEqual(h.highest_session_id(), 0)

    def test_numbering_goes_on_after_the_seed(self):
        logsetup.seed_session_ids(12)
        self.assertEqual(logsetup.next_session_id(), 13)
        self.assertEqual(logsetup.next_session_id(), 14)

    def test_seed_zero_does_not_reset_the_counter(self):
        logsetup.seed_session_ids(50)
        first = logsetup.next_session_id()
        logsetup.seed_session_ids(0)
        self.assertEqual(logsetup.next_session_id(), first + 1)

    def test_a_number_in_a_message_is_not_mistaken_for_a_session(self):
        h = self.write("< L")
        record = logging.LogRecord("tinybox", logging.INFO, __file__, 1,
                                   "msg #4711 created", (), None)
        h.handle(record)
        self.assertEqual(h.highest_session_id(), 1)


class FormatTests(unittest.TestCase):
    """Fixed columns: time with ms | level | component | #session call | message."""

    def line(self, msg: str, name: str = "tinybox.adapters.agw",
             level: int = logging.WARNING, ctx: str | None = None) -> str:
        record = logging.LogRecord(name, level, __file__, 1, msg, (), None)
        if ctx:
            record.ctx = ctx
        logsetup.ContextFilter().filter(record)
        return logsetup.Formatter().format(record)

    def test_columns(self):
        line = self.line("retry 3/10", ctx="#7 OE3TEC")
        self.assertRegex(line, r"^\d{4}-\d\d-\d\d \d\d:\d\d:\d\d\.\d{3} W agw "
                               r"\s*#7 OE3TEC\s+retry 3/10$")

    def test_level_letters(self):
        for level, letter in ((logging.DEBUG, "D"), (logging.INFO, "I"),
                              (logging.WARNING, "W"), (logging.ERROR, "E"),
                              (logging.CRITICAL, "E")):
            self.assertIn(f" {letter} ", self.line("x", level=level))

    def test_component_of_known_and_unknown_loggers(self):
        self.assertEqual(logsetup.component_of("tinybox.adapters.agw"), "agw")
        self.assertEqual(logsetup.component_of("tinybox.monitor"), "session")
        self.assertEqual(logsetup.component_of("tinybox.monitor.agw"), "agw")
        self.assertEqual(logsetup.component_of("tinybox.fwd.session"), "fwd")
        self.assertEqual(logsetup.component_of("tinybox"), "core")
        self.assertEqual(logsetup.component_of("aiohttp.access"), "access")

    def test_without_a_session_the_context_is_zero(self):
        self.assertIn(logsetup.NO_SESSION, self.line("starting"))

    def test_errors_and_warnings_are_counted_once_per_record(self):
        before = (logsetup.counters.errors, logsetup.counters.warnings)
        record = logging.LogRecord("tinybox", logging.ERROR, __file__, 1, "x", (), None)
        flt = logsetup.ContextFilter()
        flt.filter(record)
        flt.filter(record)                            # a second handler sees it again
        self.assertEqual(logsetup.counters.errors, before[0] + 1)
        self.assertEqual(logsetup.counters.warnings, before[1])


class SessionContextTests(unittest.TestCase):
    """Every line of a connection carries #n call - also store, chat, sync."""

    def test_context_manager_sets_and_resets(self):
        self.assertEqual(logsetup.context(), logsetup.NO_SESSION)
        with logsetup.session_context("#3 OE3TEC"):
            self.assertEqual(logsetup.context(), "#3 OE3TEC")
        self.assertEqual(logsetup.context(), logsetup.NO_SESSION)

    def test_session_numbers_count_up(self):
        app = make_app()
        first, _ = login(app, "OE3TEC")
        second, _ = login(app, "OE1ABC")
        self.assertEqual(first.log_ctx, f"#{first.log_id} OE3TEC")
        self.assertEqual(second.log_id, first.log_id + 1)
        app.store.close()

    def test_two_sessions_of_the_same_call_differ(self):
        app = make_app()
        radio, _ = login(app, "OE3TEC")
        telnet, _ = login(app, "OE3TEC")
        self.assertNotEqual(radio.log_ctx, telnet.log_ctx)
        app.store.close()

    def test_traffic_lines_carry_the_session(self):
        """The context has to be resolved while the line is being logged."""
        app = make_app()
        app.cfg.logging.monitor = True
        session, _ = login(app, "OE3TEC")
        seen: list[tuple[str, str]] = []

        class Capture(logging.Handler):
            def emit(self, record):
                logsetup.annotate(record)
                seen.append((record.ctx, record.getMessage()))

        monitor = logging.getLogger("tinybox.monitor")
        handler, before = Capture(), monitor.level
        monitor.addHandler(handler)
        monitor.setLevel(logging.INFO)
        try:
            session.handle_line("L")
        finally:
            monitor.removeHandler(handler)
            monitor.setLevel(before)
        self.assertTrue([msg for _, msg in seen if msg.startswith("< ")])
        self.assertTrue([msg for _, msg in seen if msg.startswith("> ")])
        for ctx, msg in seen:
            self.assertEqual(ctx, session.log_ctx, msg)
        app.store.close()

    def test_mail_text_is_shortened_but_a_command_is_not(self):
        app = make_app()
        app.cfg.logging.monitor = True
        session, _ = login(app, "OE3TEC")
        with self.assertLogs("tinybox.monitor", level="INFO") as caught:
            session.handle_line("S OE1ABC")
            session.handle_line("Subject here")
        lines = [r.getMessage() for r in caught.records if r.getMessage().startswith("< ")]
        self.assertIn("< S OE1ABC", lines)            # the command stays readable
        self.assertIn("< 12c 'Subject here'", lines)  # the content is only indicated
        app.store.close()

    def test_short_keeps_length_and_start(self):
        self.assertEqual(logsetup.short("hello"), "5c 'hello'")
        long = logsetup.short("y" * 100)
        self.assertTrue(long.startswith("100c 'yyy"))
        self.assertTrue(long.endswith("..."))
        self.assertIn("y" * 100, logsetup.short("y" * 100, full=True))


class SetupTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = logging.getLogger()
        self.saved = list(self.root.handlers), self.root.level

        def restore():
            self.root.handlers = self.saved[0]
            self.root.setLevel(self.saved[1])
            logsetup._active = None
        self.addCleanup(restore)

    def make_cfg(self, **logging_kw):
        cfg = config.load(ROOT / "tinybox.conf.example")
        data = Path(self.tmp.name) / "data"
        logs = Path(self.tmp.name) / "logs"
        logs.mkdir(parents=True, exist_ok=True)
        cfg.storage = dataclasses.replace(cfg.storage, data_dir=data)
        cfg.logging = dataclasses.replace(cfg.logging, log_dir=logs, **logging_kw)
        return cfg

    def test_level_and_per_component_debug(self):
        cfg = self.make_cfg(level="INFO", debug=["agw"])
        control, _ = logsetup.setup(cfg, MonitorFilter)
        logging.getLogger("tinybox.adapters.agw").debug("frame seen")
        logging.getLogger("tinybox.chat").debug("not interesting")
        logging.getLogger("tinybox.chat").info("board entered")
        lines = read(control.path)
        self.assertTrue(any("frame seen" in line for line in lines))
        self.assertFalse(any("not interesting" in line for line in lines),
                         "DEBUG only for the components that were switched on")
        self.assertTrue(any("board entered" in line for line in lines))

    def test_debug_on_reports_the_switched_components(self):
        cfg = self.make_cfg(level="INFO", debug=["agw"])
        logsetup.setup(cfg, MonitorFilter)
        self.assertTrue(logsetup.debug_on("agw"))
        self.assertFalse(logsetup.debug_on("chat"))

    def test_no_log_dir_means_console_only(self):
        cfg = self.make_cfg()
        cfg.logging = dataclasses.replace(cfg.logging, log_dir=None)
        control, _ = logsetup.setup(cfg, MonitorFilter)
        self.assertIsNone(control.path)
        self.assertEqual(control.size(), 0)

    def test_monitor_no_keeps_traffic_out_of_the_file(self):
        cfg = self.make_cfg(monitor=False)
        control, _ = logsetup.setup(cfg, MonitorFilter)
        logging.getLogger("tinybox.monitor").info("< L")
        logging.getLogger("tinybox").info("plain line")
        lines = read(control.path)
        self.assertFalse(any("< L" in line for line in lines))
        self.assertTrue(any("plain line" in line for line in lines))

    def test_start_block_names_version_adapters_and_no_token(self):
        cfg = self.make_cfg()
        cfg.brocast.token = "s3cret"
        block = logsetup.start_block(cfg, "1.2.3", "tinybox.conf", None, {"agw"})
        text = "\n".join(x if isinstance(x, str) else termcolor.kv_plain(*x)
                         for x in block if x is not None)
        self.assertIn("----- TinyBox 1.2.3", text)
        self.assertIn("Adapters:", text)
        self.assertIn("telnet=on", text)
        self.assertRegex(text, r"brocast token: +set")
        self.assertNotIn("s3cret", text)
        self.assertIn("debug agw", text)

    def test_stop_line_has_reason_and_counters(self):
        line = logsetup.stop_line("RESTART")
        self.assertIn("----- stop: RESTART", line)
        self.assertIn("sessions", line)
        self.assertIn("errors", line)


class SecretTests(unittest.TestCase):
    def test_tokens_and_passwords_are_removed(self):
        text = ("[brocast]\ntoken = abc123\npassword=hunter2\n"
                "[station]\nmailbox_call = OE3GAS-1\n")
        out = logsetup.strip_secrets(text)
        self.assertNotIn("abc123", out)
        self.assertNotIn("hunter2", out)
        self.assertIn("token = <removed>", out)
        self.assertIn("mailbox_call = OE3GAS-1", out)


class LogCommandTests(unittest.TestCase):
    """LOG, LOG DEBUG, LOG OFF, LOG MARK, LOG BUNDLE on the sysop console."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.logs = Path(self.tmp.name) / "logs"
        self.logs.mkdir()
        self.app = make_app()
        self.app.cfg.logging = dataclasses.replace(
            self.app.cfg.logging, log_dir=self.logs, level="INFO", debug=[])
        self.app.stop_event = asyncio.Event()
        self.handler = logsetup.DailyFileHandler(self.logs)
        self.handler.setFormatter(logsetup.Formatter())
        self.handler.addFilter(logsetup.ContextFilter())
        self.addCleanup(self.handler.close)
        self.control = logsetup.LogControl(
            "INFO", logsetup.LevelFilter("INFO"), self.handler,
            logsetup.LevelFilter("INFO"))
        self.app.log_control = self.control
        self.output: list[str] = []
        self.console = SysopConsole(self.app, MonitorFilter(True), self.output.append)
        self.console.start()
        self.addCleanup(self.app.store.close)

    def run_cmd(self, line: str) -> str:
        self.output.clear()
        self.console.handle_line(line)
        return "".join(self.output)

    def test_status_shows_level_and_file(self):
        out = self.run_cmd("LOG")
        self.assertIn("Level INFO", out)
        self.assertIn("extra DEBUG: -", out)
        self.assertIn(self.handler.path.name, out)

    def test_debug_on_and_off(self):
        self.run_cmd("LOG DEBUG agw")
        self.assertEqual(self.control.debug, {"agw"})
        self.assertIn("extra DEBUG: agw", self.run_cmd("LOG"))
        self.run_cmd("LOG OFF agw")
        self.assertEqual(self.control.debug, set())

    def test_root_level_follows_the_debug_switch(self):
        """Without a component on DEBUG a log.debug() must not even build a record."""
        root = logging.getLogger()
        before = root.level
        self.addCleanup(root.setLevel, before)
        self.run_cmd("LOG DEBUG agw")
        self.assertEqual(root.level, logging.DEBUG)
        self.run_cmd("LOG OFF")
        self.assertEqual(root.level, logging.INFO)

    def test_debug_several_components_and_off_without_a_name(self):
        self.run_cmd("LOG DEBUG agw,fwd")
        self.assertEqual(self.control.debug, {"agw", "fwd"})
        self.run_cmd("LOG OFF")
        self.assertEqual(self.control.debug, set())

    def test_unknown_component_is_refused_with_the_list(self):
        out = self.run_cmd("LOG DEBUG direwolf")
        self.assertIn("Unknown component", out)
        self.assertIn("agw", out)
        self.assertEqual(self.control.debug, set())

    def test_info_shows_the_start_block_again(self):
        self.app.config_path = "tinybox.conf"
        with self.assertLogs("tinybox", "INFO") as cm:
            self.run_cmd("INFO")
        text = "\n".join(cm.output)
        self.assertIn("info -----", text)
        self.assertIn("Mailbox call", text)
        self.assertIn("Config:", text)
        # I stays the mailbox profile command, it does not give the start block
        with self.assertNoLogs("tinybox", "INFO"):
            self.run_cmd("I")

    def test_mark_is_written_into_the_log(self):
        out = self.run_cmd("LOG MARK CR32 nachstellen")
        self.assertIn("Mark written", out)
        self.assertIn("===== MARK: CR32 nachstellen =====",
                      self.handler.path.read_text(encoding="utf-8"))

    def test_mark_without_text_shows_the_usage(self):
        self.assertIn("Usage: LOG", self.run_cmd("LOG MARK"))

    def test_nonsense_shows_the_usage(self):
        self.assertIn("Usage: LOG", self.run_cmd("LOG FOO"))

    def test_bundle_has_log_version_and_config_without_tokens(self):
        self.app.config_path = str(ROOT / "tinybox.conf.example")
        self.handler.handle(logging.LogRecord(
            "tinybox", logging.INFO, __file__, 1, "something to find", (), None))
        out = self.run_cmd("LOG BUNDLE")
        self.assertIn("Debug bundle written", out)
        bundles = list(self.logs.glob("tinybox_debug_*.txt"))
        self.assertEqual(len(bundles), 1)
        text = bundles[0].read_text(encoding="utf-8")
        self.assertIn("--- start block", text)
        self.assertIn("--- tinybox.conf (tokens removed)", text)
        self.assertIn("something to find", text)
        self.assertNotIn("token = s3cret", text)

    def test_log_is_in_the_console_help(self):
        out = self.run_cmd("H")
        self.assertIn("LOG MARK", out)

    def test_without_a_log_file_log_says_so(self):
        self.app.log_control = logsetup.LogControl(
            "INFO", None, None, logsetup.LevelFilter("INFO"))
        self.assertIn("log_dir", self.run_cmd("LOG"))


class ConfigTests(unittest.TestCase):
    def test_unknown_debug_component_is_a_config_error(self):
        with self.assertRaises(config.ConfigError) as caught:
            config._debug_components("agw, direwolf")
        self.assertIn("direwolf", str(caught.exception))
        self.assertIn("agw", str(caught.exception))

    def test_debug_components_are_parsed_and_lowercased(self):
        self.assertEqual(config._debug_components("AGW; fwd , "), ["agw", "fwd"])
        self.assertEqual(config._debug_components(""), [])
        self.assertEqual(config._debug_components("all"), ["all"])


class DurationTests(unittest.TestCase):
    def test_ms_has_the_shape_the_legend_promises(self):
        self.assertRegex(logsetup.ms(0.0), r"^\(\d+ms\)$")

    def test_only_slow_steps_get_a_duration(self):
        import time
        self.assertEqual(logsetup.ms_if_slow(time.monotonic()), "")
        self.assertRegex(logsetup.ms_if_slow(time.monotonic() - 1.0), r"^\(\d+ms\)$")


if __name__ == "__main__":
    unittest.main()
