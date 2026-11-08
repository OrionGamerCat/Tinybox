"""CR82: RELOAD - tinybox.conf again without disconnecting anybody."""

from __future__ import annotations

import asyncio
import tempfile
import unittest
from pathlib import Path

from tinybox import config, reload
from tinybox.app import App
from tinybox.adapters import sysop
from tests.test_tinybox import ROOT, login


def wheres(items) -> list[str]:
    return [c.where for c in items]


class ReloadTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "tinybox.conf"
        self.text = (ROOT / "tinybox.conf.example").read_text(encoding="utf-8")
        self.path.write_text(self.text, encoding="utf-8")
        self.app = App.create(config.load(self.path))
        self.app.config_path = str(self.path)

    def tearDown(self):
        self.app.store.close()
        self.tmp.cleanup()

    def edit(self, old: str, new: str) -> None:
        assert old in self.text, old
        self.text = self.text.replace(old, new, 1)
        self.path.write_text(self.text, encoding="utf-8")

    def test_no_changes(self):
        res = reload.reload(self.app)
        self.assertEqual(res.lines(), ["RELOAD: no changes in tinybox.conf."])

    def test_live_values_and_restart_values(self):
        mailbox = self.app.cfg.mailbox                    # held by sessions etc.
        self.edit("max_users            = 3", "max_users            = 5")
        self.edit("welcome_enabled      = yes", "welcome_enabled      = no")
        self.edit("qth          =  ", "qth          = Hinteralm  ")
        self.edit("port    = 6300", "port    = 6301")                 # [telnet]
        self.edit("mailbox_call = OE3GAS-1", "mailbox_call = OE3GAS-2")
        res = reload.reload(self.app)
        self.assertIs(self.app.cfg.mailbox, mailbox)      # changed in place
        self.assertEqual(mailbox.max_users, 5)
        self.assertEqual(self.app.registry.max_users, 5)
        self.assertFalse(mailbox.welcome_enabled)
        self.assertEqual(self.app.cfg.station.qth, "Hinteralm")
        self.assertIn("[mailbox] max_users", wheres(res.changed))
        self.assertIn("[station] qth", wheres(res.changed))
        # needs RESTART: listed, but nothing changed
        self.assertEqual(self.app.cfg.telnet.port, 6300)
        self.assertEqual(self.app.cfg.station.mailbox_call, "OE3GAS-1")
        self.assertIn("[telnet] port", wheres(res.ignored))
        self.assertIn("[station] mailbox_call", wheres(res.ignored))
        text = "\n".join(res.lines())
        self.assertIn("changed:", text)
        self.assertIn("needs RESTART (ignored):", text)
        self.assertRegex(text, r"\[mailbox\] max_users\s+3 -> 5")
        self.assertRegex(text, r"\[telnet\] port\s+6300 -> 6301")
        # a second RELOAD: the ignored value is still waiting for the RESTART
        res = reload.reload(self.app)
        self.assertEqual(wheres(res.changed), [])
        self.assertIn("[telnet] port", wheres(res.ignored))

    def test_bad_config_changes_nothing(self):
        self.edit("max_users            = 3", "max_users            = 5")
        self.edit("port    = 6300", "port    = 99999")
        with self.assertRaises(config.ConfigError):
            reload.reload(self.app)
        self.assertEqual(self.app.cfg.mailbox.max_users, 3)

    def test_secret_not_shown(self):
        self.edit("token      =  ", "token      = geheim123  ")
        res = reload.reload(self.app)
        text = "\n".join(res.lines())
        self.assertNotIn("geheim123", text)
        self.assertRegex(text, r"\[brocast\] token\s+\(changed\)")
        self.assertEqual(self.app.cfg.brocast.token, "geheim123")

    def test_brocast_publish_needs_restart(self):
        self.edit("publish    = yes", "publish    = no ")
        res = reload.reload(self.app)
        self.assertIn("[brocast] publish", wheres(res.ignored))
        self.assertTrue(self.app.cfg.brocast.publish)

    def test_boards(self):
        boards = self.app.cfg.chat.boards
        numbers = [b.name for b in boards]
        self.edit("DX    = 24h   DX spots and news", "DX    = 7d    DX spots and news\nNEU = 2d new one")
        self.edit("TECH  = 30d   Technical questions\n", "")
        res = reload.reload(self.app)
        self.assertIs(self.app.cfg.chat.boards, boards)
        self.assertEqual(self.app.cfg.chat.board("DX").keep_hours, 7 * 24)
        self.assertIsNotNone(self.app.cfg.chat.board("TECH"))   # removed: needs RESTART
        self.assertEqual([b.name for b in boards], numbers + ["NEU"])   # numbers stay
        self.assertIn("[chat_boards] DX keep", wheres(res.changed))
        self.assertIn("[chat_boards] NEU", wheres(res.changed))
        self.assertIn("[chat_boards] TECH", wheres(res.ignored))

    def test_board_order_needs_restart(self):
        self.edit("TREFF = 7d    General meeting point\nDX    = 24h   DX spots and news",
                  "DX    = 24h   DX spots and news\nTREFF = 7d    General meeting point")
        res = reload.reload(self.app)
        self.assertEqual(wheres(res.ignored), ["[chat_boards] order"])
        self.assertEqual(self.app.cfg.chat.boards[0].name, "TREFF")

    def test_motd_and_rubrics(self):
        self.edit("[chat_motd]", "[chat_motd]\nTREFF = Net Sunday 19:00")
        self.edit("\n[rubrics]\n", "\n[rubrics]\nDX = DX news\n")
        rubrics = self.app.cfg.rubrics
        res = reload.reload(self.app)
        self.assertEqual(self.app.cfg.chat.board("TREFF").motd, "Net Sunday 19:00")
        self.assertIs(self.app.cfg.rubrics, rubrics)
        self.assertIn("DX", [r.name for r in rubrics])
        self.assertIn("[chat_motd] TREFF", wheres(res.changed))
        self.assertIn("[rubrics] DX", wheres(res.changed))

    def test_logging_level(self):
        import logging
        from tinybox import logsetup
        control, _ = logsetup.setup(self.app.cfg, sysop.MonitorFilter)
        self.app.log_control = control
        try:
            self.edit("level     = INFO", "level     = WARNING")
            reload.reload(self.app)
            self.assertEqual(control.console_filter.level, logging.WARNING)
            self.assertEqual(logging.getLogger().level, logging.WARNING)
        finally:
            for h in list(logging.getLogger().handlers):
                logging.getLogger().removeHandler(h)
            logging.getLogger().setLevel(logging.WARNING)

    def test_beacon_started_and_stopped(self):
        from tinybox import beacon

        async def scenario():
            self.app.beacon = beacon.Beacon(self.app)
            self.edit("enabled      = no\ninterval_min", "enabled      = yes\ninterval_min")
            reload.reload(self.app)
            task = self.app.beacon_task
            self.assertIsNotNone(task)
            self.assertFalse(task.done())
            self.edit("enabled      = yes\ninterval_min", "enabled      = no\ninterval_min")
            reload.reload(self.app)
            await asyncio.sleep(0)
            self.assertTrue(task.cancelled())
            self.assertIsNone(self.app.beacon_task)

        asyncio.run(scenario())

    def test_users_stay_connected(self):
        s, t = login(self.app, "OE1ABC")
        self.edit("idle_timeout_min     = 10", "idle_timeout_min     = 20")
        reload.reload(self.app)
        self.assertFalse(s.closed)
        self.assertEqual(self.app.cfg.mailbox.idle_timeout_min, 20)

    def test_console_command(self):
        out = []
        console = sysop.SysopConsole(self.app, write_fn=out.append)
        self.edit("max_users            = 3", "max_users            = 4")
        console.cmd_reload("")
        text = "".join(out)
        self.assertIn("RELOAD tinybox.conf", text)
        self.assertIn("[mailbox] max_users", text)
        self.edit("port    = 6300", "port    = 0")
        out.clear()
        console.cmd_reload("")
        self.assertIn("nothing changed", "".join(out))


if __name__ == "__main__":
    unittest.main()
