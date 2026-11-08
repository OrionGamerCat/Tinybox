"""CR78: chat history between two TBClients - store, hash chain, the //HIST
comparison (same, a lost last line sent again, different -> both delete,
the delete button) and the link quality from the Direwolf fork's 'Q'."""

from __future__ import annotations

import asyncio
import hashlib
import dataclasses
import tempfile
import time
import unittest
from pathlib import Path

from prcore import chatimg
from tbclient import core as core_mod
from tbclient import peerfile
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

    def test_picture_between_clients(self):
        """CR78: the reference goes as a chat line, the bytes on a tap straight
        from the sender - only to the station it was sent to."""
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
                self.assertTrue(await b.connect("OE3GAS", ch=1))
                await until(lambda: a.channels[1].peer is not None and b.channels[1].peer is not None)
                await asyncio.sleep(0.2)
                webp = b"RIFF\x20\x00\x00\x00WEBPVP8 " + bytes(range(256)) * 5
                h = b.peer_image(1, webp, "BEHV6nWB2yk8pyo0", "vom Berg")
                self.assertTrue(h)
                line = f"~#{h}{chatimg.size_code(len(webp))}BEHV6nWB2yk8pyo0 vom Berg"
                await until(lambda: a.peerchat.messages("OE3TEC")[-1:]
                            and a.peerchat.messages("OE3TEC")[-1]["text"] == line)
                self.assertFalse(a.images.store.has(h))
                self.assertTrue(a.peer_image_get(1, h))
                await until(lambda: a.images.store.has(h))
                self.assertEqual(a.images.store.get(h), webp)
                self.assertIn(h, a.snapshot(1)["images"]["have"])
                # the bytes did not end up as chat lines
                self.assertFalse(any("RIFF" in m["text"] for m in a.peerchat.messages("OE3TEC")))
                # a picture never sent to them: refused
                other = b"RIFF\x20\x00\x00\x00WEBPVP8 " + bytes(range(200))
                oh = chatimg.image_hash(other)
                b.images.store.put(oh, other)
                self.assertTrue(a.peer_image_get(1, oh))
                await until(lambda: a.images.loading.get(oh, {}).get("error"))
                self.assertFalse(a.images.store.has(oh))
                for t in tasks:
                    t.cancel()
            dw.server.close()
        asyncio.run(scenario())

    def test_file_between_clients(self):
        """CR78: a file - offered as a chat line, fetched on a tap, LZHUF on the
        air (raw if that is not smaller); the clocks are compared at the start."""
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
                self.assertTrue(await b.connect("OE3GAS", ch=1))
                await until(lambda: a.channels[1].peer is not None and b.channels[1].peer is not None)
                await asyncio.sleep(0.2)
                self.assertLessEqual(abs(a.channels[1].peer.clock_off), 2)       # same PC clock
                self.assertEqual(a.channels[1].summary(0)["peer"]["clock"], a.channels[1].peer.clock_off)
                text = ("Antennenbau: Dipol fuer 2 m, Laenge 98 cm\n" * 200).encode()
                rnd = b"".join(hashlib.sha256(i.to_bytes(2, "big")).digest() for i in range(100))
                for name, data in (("../dipol notes.txt", text), ("bin.dat", rnd)):
                    self.assertTrue(b.peer_file(1, name, data))
                    h = chatimg.image_hash(data)
                    await until(lambda: any(m["text"].startswith(f"~%{h} ")
                                            for m in a.peerchat.messages("OE3TEC")))
                    ref = peerfile.parse_ref(a.peerchat.messages("OE3TEC")[-1]["text"])
                    self.assertEqual(ref[0], h)
                    self.assertEqual(ref[1], len(data))
                    self.assertFalse("/" in ref[3])
                    self.assertTrue(a.peer_file_get(1, h))
                    await until(lambda: a.files.has(h))
                    self.assertEqual(a.files.get(h), data)
                    self.assertIn(h, a.snapshot(1)["peerchat"]["files"]["have"])
                self.assertEqual(ref[2], len(rnd))                  # not packable: raw
                self.assertEqual(peerfile.parse_ref(f"~%{chatimg.image_hash(text)} 1 1 x")[3], "x")
                # a file never offered to them: refused
                b.files.put("abcdef", b"geheim")
                self.assertTrue(a.peer_file_get(1, "abcdef"))
                await until(lambda: a.file_loading.get("abcdef", {}).get("error"))
                for t in tasks:
                    t.cancel()
            dw.server.close()
        asyncio.run(scenario())

    def test_ping_speed_chess_tick(self):
        """CR78 stage 8: ping, speed test both ways, chess turns, the delivery tick."""
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
                self.assertTrue(await b.connect("OE3GAS", ch=1))
                await until(lambda: a.channels[1].peer is not None and b.channels[1].peer is not None)
                await asyncio.sleep(0.2)
                pa, pb = a.channels[1].peer, b.channels[1].peer
                # ping
                self.assertTrue(b.peer_fun(1, "ping"))
                await until(lambda: pb.fun.pings)
                # speed test: both directions measured, the bytes are no chat lines
                self.assertTrue(b.peer_fun(1, "speed"))
                await until(lambda: pb.fun.st["state"] == "done")
                self.assertGreater(pb.fun.st["out"], 0)
                self.assertGreater(pb.fun.st["in"], 0)
                self.assertEqual(a.peerchat.count("OE3TEC"), 0)
                # CR80: the last results stay per station, also for the next connect
                last = pb.fun.summary()["last"]
                self.assertEqual(last["ping"][0], pb.fun.pings[-1])
                self.assertEqual(last["st"][:2], [pb.fun.st["out"], pb.fun.st["in"]])
                self.assertIn("OE3GAS", b.settings["fun_last"])
                # chess: b plays white, turns are checked
                self.assertTrue(b.peer_fun(1, "chess-new", "w"))
                await until(lambda: pa.fun.game is not None)
                self.assertEqual(pa.fun.game["white"], "them")
                self.assertFalse(a.peer_fun(1, "chess-move", "e7e5"))       # not a's turn
                self.assertTrue(b.peer_fun(1, "chess-move", "e2e4"))
                await until(lambda: pa.fun.game["moves"] == ["e2e4"])
                self.assertFalse(b.peer_fun(1, "chess-move", "d2d4"))       # twice in a row
                self.assertTrue(a.peer_fun(1, "chess-move", "e7e5"))
                await until(lambda: pb.fun.game["moves"] == ["e2e4", "e7e5"])
                self.assertTrue(a.peer_fun(1, "chess-resign"))
                await until(lambda: pb.fun.game["result"] == "they resigned")
                self.assertIn("chess", b.settings)                          # kept for later
                # delivery tick
                self.assertTrue(b.send_raw("kommt an?", ch=1))
                await until(lambda: a.peerchat.count("OE3TEC") >= 1)
                self.assertFalse(b.peerchat.messages("OE3GAS")[-1]["ok"])
                pb.outstanding(0)
                self.assertTrue([m for m in b.peerchat.messages("OE3GAS") if m["dir"] == "tx"][-1]["ok"])
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
