"""CR78: chat history between two TBClients - store, hash chain, the //HIST
comparison (same, a lost last line sent again, different -> both delete,
the delete button) and the link quality from the Direwolf fork's 'Q'."""

from __future__ import annotations

import asyncio
import dataclasses
import tempfile
import time
import unittest
from pathlib import Path

from tbclient import core as core_mod
from tbclient import peerchat
from tbclient.core import ClientCore
from tests.test_tbclient import FakeDirewolf, client_cfg, until


class StoreTests(unittest.TestCase):
    def test_chain_trim_clear(self):
        with tempfile.TemporaryDirectory() as d:
            s = peerchat.PeerChat(Path(d) / "p.db")
            gen = s.state("OE3TEC")["gen"]
            for i in range(peerchat.KEEP + 5):
                s.add("OE3TEC", "tx", f"line {i}")
            s.add("OE3TEC", "rx", "answer")
            st = s.state("OE3TEC")
            self.assertEqual((st["gen"], st["tx"][0], st["rx"][0]), (gen, peerchat.KEEP + 5, 1))
            h = "0"
            for i in range(peerchat.KEEP + 5):
                h = peerchat.chain(h, f"line {i}")
            self.assertEqual(st["tx"][1], h)                     # the chain over all lines
            self.assertIsNone(s.chain_at("OE3TEC", "tx", 5))     # trimmed
            self.assertEqual(s.chain_at("OE3TEC", "tx", peerchat.KEEP + 5), h)
            self.assertEqual(len(s.messages("OE3TEC")), peerchat.KEEP)
            self.assertTrue(s.clear("OE3TEC", "abcdef"))
            self.assertEqual(s.state("OE3TEC"), {"gen": "abcdef", "tx": (0, "0"), "rx": (0, "0")})
            self.assertFalse(s.clear("OE3TEC", "abcdef"))


class PeerHistoryTests(unittest.TestCase):
    def setUp(self):
        self._old = core_mod.HANDSHAKE_FALLBACK_SEC
        core_mod.HANDSHAKE_FALLBACK_SEC = 0.3

    def tearDown(self):
        core_mod.HANDSHAKE_FALLBACK_SEC = self._old

    def test_history_both_sides(self):
        async def scenario():
            dw = FakeDirewolf()
            port = await dw.start()
            with tempfile.TemporaryDirectory() as ta, tempfile.TemporaryDirectory() as tb:
                a = ClientCore(client_cfg(ta, agw_port=port))
                b = ClientCore(dataclasses.replace(client_cfg(tb, agw_port=port), mycall="OE3TEC"))
                tasks = [asyncio.create_task(a.run()), asyncio.create_task(b.run())]
                await asyncio.wait_for(a.port.agw_up.wait(), 5)
                await asyncio.wait_for(b.port.agw_up.wait(), 5)
                await until(lambda: len([c for c in dw.clients if c["calls"]]) == 2)

                async def connect():
                    self.assertTrue(await b.connect("OE3GAS", ch=1))
                    await until(lambda: a.channels[1].peer is not None
                                and b.channels[1].peer is not None)
                    await asyncio.sleep(0.2)                   # the //HIST lines

                async def disconnect():
                    b.disconnect(1)
                    await until(lambda: a.channels[1].state == "offline"
                                and b.channels[1].state == "offline")

                sa, sb = a.peerchat, b.peerchat
                await connect()
                g = sa.state("OE3TEC")["gen"]
                self.assertEqual(sb.state("OE3GAS")["gen"], g)   # the first connect agrees
                self.assertTrue(b.send_raw("Servus", ch=1))
                await until(lambda: sa.state("OE3TEC")["rx"][0] == 1)
                self.assertTrue(a.send_raw("Hallo Tobias", ch=1))
                await until(lambda: sb.state("OE3GAS")["rx"][0] == 1)
                self.assertEqual(sa.state("OE3TEC")["tx"], sb.state("OE3GAS")["rx"])
                snap = a.snapshot(1)["peerchat"]
                self.assertEqual([m["text"] for m in snap["msgs"]], ["Servus", "Hallo Tobias"])
                await disconnect()
                # a line of b never arrived at a (lost at the disconnect): sent again
                sb.add("OE3GAS", "tx", "das kam nicht an")
                await connect()
                await until(lambda: sa.state("OE3TEC")["rx"][0] == 2)
                self.assertEqual(sa.state("OE3TEC")["rx"], sb.state("OE3GAS")["tx"])
                self.assertEqual(sa.state("OE3TEC")["gen"], g)  # nothing deleted
                await disconnect()
                # different on both sides: both delete
                sa.add("OE3TEC", "rx", "nur hier")
                await connect()
                await until(lambda: sb.count("OE3GAS") == 0 and sa.count("OE3TEC") == 0)
                self.assertEqual(sa.state("OE3TEC")["gen"], sb.state("OE3GAS")["gen"])
                self.assertIn("chat history removed", sa.messages("OE3TEC")[-1]["text"])
                # the button while connected: the other side deletes at once
                self.assertTrue(a.send_raw("neu", ch=1))
                await until(lambda: sb.count("OE3GAS") == 1)
                self.assertTrue(b.peer_clear(1))
                await until(lambda: sa.count("OE3TEC") == 0)
                self.assertEqual(sa.messages("OE3TEC")[-1]["text"], "chat history removed by OE3TEC")
                self.assertEqual(sa.state("OE3TEC")["gen"], sb.state("OE3GAS")["gen"])
                await disconnect()
                # deleted while not connected: different generations -> both delete
                self.assertTrue(await b.connect("OE3GAS", ch=1))
                await until(lambda: a.channels[1].peer is not None)
                await asyncio.sleep(0.2)
                self.assertTrue(a.send_raw("vorher", ch=1))
                await until(lambda: sb.count("OE3GAS") == 1)
                await disconnect()
                sb.clear("OE3GAS", peerchat.new_gen())
                await connect()
                await until(lambda: sa.count("OE3TEC") == 0)
                for t in tasks:
                    t.cancel()
            dw.server.close()
        asyncio.run(scenario())

    def test_link_quality_from_q(self):
        async def scenario():
            dw = FakeDirewolf()
            dw.q_line = (b"v=2 state=3 i_new=40 i_retry=2 bytes_new=4000 bytes_retry=200 i_rx=30 "
                         b"retry_rx=1 rej_rx=0 rej_tx=0 t1_exp=0 rnr_rx=0 srt=1.5 t1v=4.0 rc=0 "
                         b"unack=0 age=100 bytes_rx=3000 tx_busy_ms=20000 baud=1200")
            port = await dw.start()
            with tempfile.TemporaryDirectory() as ta, tempfile.TemporaryDirectory() as tb:
                a = ClientCore(client_cfg(ta, agw_port=port))
                b = ClientCore(dataclasses.replace(client_cfg(tb, agw_port=port), mycall="OE3TEC"))
                tasks = [asyncio.create_task(a.run()), asyncio.create_task(b.run())]
                await asyncio.wait_for(a.port.agw_up.wait(), 5)
                await asyncio.wait_for(b.port.agw_up.wait(), 5)
                await until(lambda: len([c for c in dw.clients if c["calls"]]) == 2)
                self.assertTrue(await b.connect("OE3GAS", ch=1))
                await until(lambda: b.channels[1].peer is not None)
                cb = b.channels[1]
                cb.peer.add_counters(await cb.link.counters(), time.monotonic())
                q = cb.summary(0)["peer"]["q"]
                self.assertEqual((q["out"]["frames"], q["out"]["lost"], q["out"]["bars"]), (42, 2, 5))
                self.assertEqual((q["in"]["frames"], q["in"]["bars"]), (30, 5))
                self.assertEqual(q["rate"], 200)                 # 4000 B in 20 s
                dw.q_line = None                                 # Direwolf without the fork
                ca = a.channels[1]
                self.assertIsNone(await ca.link.counters())
                ca.peer.add_counters(None, time.monotonic())
                self.assertTrue(ca.summary(0)["peer"]["q"]["none"])
                for t in tasks:
                    t.cancel()
            dw.server.close()
        asyncio.run(scenario())
