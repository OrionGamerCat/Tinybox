"""C3: offline mailbox - sync commands in the TinyBox, local store and sync in the client."""

from __future__ import annotations

import asyncio
import dataclasses
import random
import time
from unittest import mock
import tempfile
import unittest
from pathlib import Path

from tbclient.core import ClientCore
from tbclient.links import LineSplitter
from tbclient.mailstore import MailStore
from tbclient import VERSION, sync
from tbclient.sync import parse_header
from tinybox.adapters import agw as tb_agw
from prcore import lzhuf
from tinybox.session import Session, State
from tests.test_chat import chat_app
from tests.test_tbclient import FakeDirewolf, client_cfg, until
from tests.test_tinybox import FakeTransport, login, type_lines

LONG = "\n".join(f"Zeile {i}: Das Wetter im Weinviertel ist heute wieder schoen." for i in range(30))


class BinTransport(FakeTransport):
    """Like the AGW transport: text and raw bytes in one stream."""

    def __init__(self) -> None:
        super().__init__()
        self.raw = b""

    def write(self, text: str) -> None:
        self.raw += text.encode("utf-8")

    def write_bytes(self, data: bytes) -> None:
        self.raw += data


def client(app, call="OE3GAS", caps="CHAT,SYNC,Z", radio=False):
    t = BinTransport() if radio else FakeTransport()
    s = Session(call, app.service, app.cfg, t, origin="radio" if radio else "telnet")
    s.start()
    type_lines(s, f"//CLIENT TB1 caps={caps}")
    if radio:
        t.raw = b""
    else:
        t.take()
    return s, t


def mail(app, frm, to, subject, body="x", type="P"):
    return app.service.create(from_call=frm, to_call=to, type=type, subject=subject, body=body,
                              origin="telnet")


class ServerTests(unittest.TestCase):
    def setUp(self):
        self.app = chat_app()
        self.a = mail(self.app, "OE3TEC", "OE3GAS", "Hallo Gerhard", "Text 1\nZeile 2")
        self.b = mail(self.app, "OE3GAS", "OE3TEC", "Antwort")
        self.c = mail(self.app, "OE3TEC", "OE1ABC", "Fremd")                  # not mine
        self.d = mail(self.app, "OE3TEC", "ALL", "Bulletin 1", type="B")
        self.e = mail(self.app, "OE3TEC", "WX", "Wetter", LONG, type="B")

    def test_caps_and_lists(self):
        s, t = login(self.app, "OE3GAS")
        t.take()
        type_lines(s, "//MLIST")
        self.assertIn("//ERR", t.take())                  # not a client yet
        type_lines(s, f"//CLIENT TB1 v={VERSION} caps=CHAT,SYNC,Z")   # current client
        self.assertIn("//OK TB1 caps=CHAT,SYNC\r", t.take())   # Z only on radio
        type_lines(s, "//MLIST")
        rows = t.take().split("\r")[:-1]
        self.assertEqual(rows[-1], "//MEND 2 0")
        h = parse_header(rows[0][4:])                    # oldest first
        self.assertEqual((h["id"], h["type"], h["status"], h["from_call"], h["subject"]),
                         (self.a, "P", "N", "OE3TEC", "Hallo Gerhard"))
        self.assertGreater(h["created"], 1_700_000_000)
        type_lines(s, "//RUBRICS")
        self.assertEqual(t.take(), f"//RU ALL 1 {self.d}\r//RU WX 1 {self.e}\r//RUEND\r")
        type_lines(s, f"//BLIST ALL=0 WX={self.e}")
        out = t.take().split("\r")
        self.assertTrue(out[0].startswith(f"//M {self.d} B "))
        self.assertEqual(out[1], "//MEND 1 0")
        type_lines(s, "//BLIST ALL=x")
        self.assertEqual(t.take(), "//ERR blist\r")
        # page by page
        type_lines(s, "//MLIST max=1")
        out = t.take().split("\r")
        self.assertTrue(out[0].startswith(f"//M {self.a} "))
        self.assertEqual(out[1], "//MEND 1 1")
        type_lines(s, f"//MLIST after={self.a} max=1")
        out = t.take().split("\r")
        self.assertTrue(out[0].startswith(f"//M {self.b} "))
        self.assertEqual(out[1], "//MEND 1 0")
        type_lines(s, "//BLIST ALL=0 WX=0 max=1")
        self.assertTrue(t.take().endswith("//MEND 1 1\r"))

    def test_get_plain_and_foreign(self):
        s, t = client(self.app)
        type_lines(s, f"//GET {self.a} {self.c} 999")
        self.assertEqual(t.take(), f"//MSG {self.a} 2\rText 1\rZeile 2\r"
                                   f"//NOMSG {self.c}\r//NOMSG 999\r//GEND\r")
        self.assertEqual(self.app.service.store.get(self.a).status, "N")   # GET is not reading
        type_lines(s, "//GET " + " ".join(["1"] * 21))
        self.assertEqual(t.take(), "//ERR get\r//GEND\r")

    def test_get_compressed_on_radio(self):
        s, t = client(self.app, radio=True)
        type_lines(s, f"//GET {self.e} {self.a}")
        raw = t.raw
        head, _, rest = raw.partition(b"\r")
        _, msg_id, n = head.decode().split()
        self.assertEqual(int(msg_id), self.e)
        data, rest = rest[:int(n)], rest[int(n):]
        self.assertLess(len(data), len(LONG) / 2)
        self.assertEqual(lzhuf.decompress_b1(data).decode(), LONG)
        # short text: not worth compressing
        self.assertEqual(rest, f"//MSG {self.a} 2\rText 1\rZeile 2\r//GEND\r".encode())

    def test_part(self):
        s, t = client(self.app, radio=True)
        whole = b""
        while True:
            type_lines(s, f"//PART {self.e} {len(whole)} 50")
            head, _, rest = t.raw.partition(b"\r")
            t.raw = b""
            _, msg_id, kind, off, total, n = head.decode().split()
            self.assertEqual((int(msg_id), kind, int(off), len(rest)), (self.e, "Z", len(whole),
                                                                         int(n)))
            whole += rest
            if len(whole) >= int(total):
                break
        self.assertEqual(lzhuf.decompress_b1(whole).decode(), LONG)
        type_lines(s, f"//PART {self.c} 0 50")             # not mine
        self.assertEqual(t.raw, f"//NOMSG {self.c}\r".encode())
        s2, t2 = client(self.app)                          # telnet: no pieces
        type_lines(s2, f"//PART {self.e} 0 50")
        self.assertEqual(t2.take(), "//ERR part\r")

    def test_send_kill_read(self):
        s, t = client(self.app)
        type_lines(s, "//SEND P OE3TEC@OE3GAS-1 2 mid=abcdef123456", "Betreff hier",
                   "Erste Zeile", "")
        out = t.take()
        self.assertTrue(out.startswith("//SENT "), out)
        new = int(out.split()[1])
        m = self.app.service.store.get(new)
        self.assertEqual((m.from_call, m.to_call, m.subject, m.body), ("OE3GAS", "OE3TEC",
                                                                       "Betreff hier",
                                                                       "Erste Zeile\n"))
        # the same message again (answer was lost): old number, not stored twice
        type_lines(s, "//SEND P OE3TEC 2 mid=abcdef123456", "Betreff hier", "Erste Zeile", "")
        self.assertEqual(t.take(), f"//SENT {new}\r")
        # errors: the text lines are still taken away
        type_lines(s, "//SEND P NOCALL!! 1", "x", "y")
        self.assertIn("//ERR send invalid", t.take())
        self.assertEqual(s.state, State.COMMAND)
        type_lines(s, "//SEND B WX 0", "Bulletin vom Client")
        self.assertTrue(t.take().startswith("//SENT "))
        # read and kill
        type_lines(s, f"//READ {self.a}")
        self.assertEqual(t.take(), "//REND\r")
        self.assertEqual(self.app.service.store.get(self.a).status, "Y")
        type_lines(s, f"//KILL {self.a} {self.c} {self.d} 999")
        self.assertEqual(t.take(), f"//K {self.a} ok\r//K {self.c} not_found\r"
                                   f"//K {self.d} not_allowed\r//K 999 ok\r//KEND\r")
        self.assertIsNone(self.app.service.store.get(self.a))
        self.assertIsNotNone(self.app.service.store.get(self.c))

    def test_send_inside_board(self):
        s, t = client(self.app)
        type_lines(s, "C 1")
        t.take()
        type_lines(s, "//SEND P OE3TEC 1", "Aus dem Chat", "Text")
        self.assertTrue(t.take().startswith("//SENT "))
        self.assertEqual(s.state, State.CHAT)

    def test_no_sync_cap(self):
        s, t = client(self.app, caps="CHAT")
        type_lines(s, "//MLIST")
        self.assertEqual(t.take(), "//ERR MLIST needs SYNC\r")


class SplitterTests(unittest.TestCase):
    def test_binary_after_line(self):
        got = []
        sp = LineSplitter(None)
        sp.on_line = lambda line: (got.append(line),
                                   line.startswith("//ZMSG") and sp.expect(4, got.append))
        data = b"//ZMSG 1 4\r\n\r\x00\xffnext\r"       # binary starts with LF and CR
        for i in range(len(data)):                       # byte by byte, like small frames
            sp.feed(data[i:i + 1])
        self.assertEqual(got, ["//ZMSG 1 4", b"\n\r\x00\xff", "next"])


class StoreTests(unittest.TestCase):
    def test_folders_read_delete_outbox(self):
        with tempfile.TemporaryDirectory() as tmp:
            st = MailStore(Path(tmp) / "m.db", "OE3GAS-5")
            self.assertTrue(st.unused)
            self.assertEqual(st.summary()["inbox"], 0)
            hdr = dict(type="P", status="N", fwd="", size=3, at_addr="", bid="", created=1)
            self.assertTrue(st.upsert_header({**hdr, "id": 1, "from_call": "OE3TEC",
                                              "to_call": "OE3GAS", "subject": "a"}))
            st.upsert_header({**hdr, "id": 2, "from_call": "OE3GAS", "to_call": "OE3TEC",
                              "subject": "b", "status": "Y"})
            st.upsert_header({**hdr, "id": 3, "type": "B", "from_call": "OE3TEC",
                              "to_call": "ALL", "subject": "c"})
            self.assertEqual([m["id"] for m in st.folder("inbox")], [1])
            self.assertEqual([m["id"] for m in st.folder("sent")], [2])
            self.assertEqual([m["id"] for m in st.folder("b:ALL")], [3])
            self.assertEqual(st.missing_bodies(), [1, 2, 3])
            st.set_body(1, "hallo")
            self.assertFalse(st.upsert_header({**hdr, "id": 1, "from_call": "OE3TEC",
                                               "to_call": "OE3GAS", "subject": "a"}))
            self.assertEqual(st.summary()["unread"], 1)
            st.open(1)
            self.assertEqual((st.summary()["unread"], st.todo("read")), (0, [1]))
            st.delete(1)
            self.assertEqual((st.folder("inbox"), st.todo("kill")), ([], [1]))
            st.delete(3)                                   # bulletin: only here
            self.assertEqual(st.max_bulletin("ALL"), 3)
            oid = st.save_out(None, "P", "OE3TEC", "s", "b")
            self.assertEqual(st.save_out(oid, "P", "OE3TEC", "s2", "b2"), oid)
            self.assertEqual(st.outbox()[0]["subject"], "s2")
            st.subscribe("WX", True)
            self.assertEqual([r["name"] for r in st.summary()["rubrics"] if r["sub"]], ["WX"])
            st.close()


class EndToEndTests(unittest.TestCase):
    def test_sync_over_radio(self):
        async def scenario():
            dw = FakeDirewolf()
            port = await dw.start()
            app = chat_app()
            app.cfg.direwolf = dataclasses.replace(app.cfg.direwolf, agw_port=port,
                                                   reconnect_sec=1)
            adapter = tb_agw.AgwAdapter(app)
            app.agw = adapter
            t1 = asyncio.create_task(adapter.run())
            await asyncio.wait_for(adapter.connected.wait(), 5)
            a = mail(app, "OE3TEC", "OE3GAS", "Lang", LONG)
            mail(app, "OE3TEC", "OE3GAS", "Kurz", "kurz")
            rnd = random.Random(7)                         # hardly compressible: in pieces
            noise = "\n".join(" ".join(f"{rnd.randrange(16**8):08x}" for _ in range(8))
                              for _ in range(40))
            big = mail(app, "OE1ABC", "OE3GAS", "Gross", noise)
            for i in range(4):                             # more headers than one page
                mail(app, "OE3TEC", "OE3GAS", f"Nr {i}", f"Text {i}")
            mail(app, "OE3TEC", "WX", "Wetter", LONG, type="B")
            mail(app, "OE3TEC", "ALL", "Nicht abonniert", type="B")
            with tempfile.TemporaryDirectory() as tmp:
                core = ClientCore(client_cfg(tmp, agw_port=port, sync_chunk=256,
                                             sync_pause=0.05))
                box = core.mailbox
                t2 = asyncio.create_task(core.run())
                await asyncio.wait_for(core.link.agw_up.wait(), 5)
                box.subscribe("WX", True)
                box.save_out(None, "P", "OE3TEC", "Vom Client", "Hallo Tec\n73")
                # offline: the sync connects, does its work and disconnects again
                self.assertTrue(core.sync.start("mail"))
                self.assertFalse(core.sync.start("bulletins"))       # one at a time
                await until(lambda: not core.sync.running, 30)
                self.assertEqual(core.sync.status["error"], "")
                self.assertIn("*** client mode, caps: CHAT,HAVE,HSEQ,IMG,NUM,PROF,SHORT,SYNC,SYNC2,UI,Z", core.console)
                await until(lambda: core.state == "offline")
                inbox = box.folder("inbox")
                self.assertEqual([m["subject"] for m in inbox],
                                 ["Nr 3", "Nr 2", "Nr 1", "Nr 0", "Gross", "Kurz", "Lang"])
                # CR40: short texts came along, long ones only on demand
                self.assertEqual(box.message(inbox[5]["id"])["body"], "kurz")
                self.assertIsNone(box.message(a)["body"])
                self.assertIsNone(box.message(big)["body"])
                self.assertTrue(any("Press Abort" in x for x in core.console))
                # a click while not connected: said so and forgotten
                self.assertEqual(core.sync.fetch(big), "not connected")
                self.assertFalse(core.sync.running)
                self.assertEqual(box.folder("b:WX"), [])          # bulletins: own sync
                self.assertTrue(box.summary()["last_mail"])
                self.assertFalse(box.summary()["last_bulletins"])
                self.assertTrue(core.sync.start("bulletins"))
                await until(lambda: not core.sync.running, 30)
                self.assertEqual(core.sync.status["error"], "")
                self.assertEqual([m["subject"] for m in box.folder("b:WX")], ["Wetter"])
                wx = box.folder("b:WX")[0]["id"]
                self.assertIsNone(box.message(wx)["body"])        # bulletins: headers only
                self.assertEqual(box.folder("b:ALL"), [])
                # online: texts on click - the long one piece by piece, compressed
                await core.connect()
                await until(lambda: core.state == "online" and core.caps, 10)
                for msg_id in (big, a, wx):
                    self.assertEqual(core.sync.fetch(msg_id), "")
                    await until(lambda: not core.sync.running, 30)
                    self.assertEqual(core.sync.status["error"], "")
                self.assertEqual(box.message(a)["body"], LONG)
                self.assertEqual(box.message(big)["body"], noise)
                self.assertEqual(box.message(wx)["body"], LONG)
                self.assertTrue(any(x.startswith(f"> //PART {big} ") for x in core.console))
                self.assertGreater(core.sync.status["saved"], 100)        # compression
                core.disconnect()
                await until(lambda: core.state == "offline")
                sent = [m for m in app.service.store.list_messages() if m.subject == "Vom Client"]
                self.assertEqual(sent[0].body, "Hallo Tec\n73")
                self.assertEqual(box.folder("outbox"), [])
                self.assertEqual(box.folder("sent")[0]["id"], sent[0].id)
                names = {r["name"]: r for r in box.summary()["rubrics"]}
                self.assertEqual((names["ALL"]["server"], names["WX"]["local"]), (1, 1))
                # read and delete here, then sync: the TinyBox follows
                box.open(a)
                kurz = inbox[5]["id"]
                box.delete(kurz)
                core.sync.start()
                await until(lambda: not core.sync.running, 30)
                self.assertEqual(core.sync.status["error"], "")
                self.assertEqual(core.sync.status["total"], 0)       # nothing fetched again
                self.assertEqual(app.service.store.get(a).status, "Y")
                self.assertIsNone(app.service.store.get(kurz))
                self.assertEqual(box.todo("kill") + box.todo("read"), [])
                box.close()
                t2.cancel()
            t1.cancel()
            dw.server.close()
        asyncio.run(scenario())

    def test_pause_and_busy_channel(self):
        async def scenario():
            with tempfile.TemporaryDirectory() as tmp:
                core = ClientCore(client_cfg(tmp, sync_pause=0.2))
                sent = []
                core.link.send_line = lambda line: sent.append((line, time.monotonic()))
                core.state = "online"
                syncer = core.sync
                with mock.patch.object(sync, "BUSY_QUIET_SEC", 0.3):
                    await syncer._send("//MLIST")               # first request: at once
                    t0 = time.monotonic()
                    await syncer._send("//RUBRICS")              # pause
                    self.assertGreaterEqual(time.monotonic() - t0, 0.19)
                    core.channel_busy_at = time.monotonic() + 0.2   # others still talking
                    t0 = time.monotonic()
                    await syncer._send("//GET 1")
                    self.assertGreaterEqual(time.monotonic() - t0, 0.45)
                self.assertEqual([x[0] for x in sent], ["//MLIST", "//RUBRICS", "//GET 1"])
                core.mailbox.close()
        asyncio.run(scenario())

    def test_sync_fails_cleanly_without_direwolf(self):
        async def scenario():
            with tempfile.TemporaryDirectory() as tmp:
                core = ClientCore(client_cfg(tmp, agw_port=1))
                core.sync.start()
                await until(lambda: not core.sync.running, 10)
                self.assertIn("not connected", core.sync.status["error"])
                core.mailbox.close()
        asyncio.run(scenario())


if __name__ == "__main__":
    unittest.main()


class DeltaSyncTests(unittest.TestCase):
    """CR26: //SYNC and //BSYNC - only what changed, in one exchange."""

    def setUp(self):
        self.app = chat_app()
        self.a = mail(self.app, "OE3TEC", "OE3GAS", "Hallo Gerhard", "Text 1\nZeile 2")
        self.b = mail(self.app, "OE3GAS", "OE3TEC", "Antwort", "eigener Text")
        self.c = mail(self.app, "OE3TEC", "OE1ABC", "Fremd")
        self.d = mail(self.app, "OE3TEC", "ALL", "Bulletin 1", "kurz", type="B")
        self.e = mail(self.app, "OE3TEC", "WX", "Wetter", LONG, type="B")

    def ask(self, s, t, line):
        type_lines(s, line)
        return t.take().split("\r")[:-1]

    def test_needs_cap(self):
        s, t = client(self.app, caps="CHAT,SYNC")
        self.assertEqual(self.ask(s, t, "//SYNC seq=0"), ["//ERR SYNC needs SYNC2"])
        s, t = client(self.app, caps="CHAT,SYNC,SYNC2")
        self.assertEqual(self.ask(s, t, "//SYNC"), ["//ERR sync"])
        self.assertEqual(self.ask(s, t, "//SYNC seq=x"), ["//ERR sync"])

    def test_sync_delta(self):
        s, t = client(self.app, caps="CHAT,SYNC,SYNC2")
        store = self.app.service.store
        # everything, with the text of the short mail from somebody else (not my own)
        out = self.ask(s, t, "//SYNC seq=0 want=100")
        self.assertTrue(out[0].startswith(f"//M {self.a} P N "))
        self.assertTrue(out[1].startswith(f"//M {self.b} P N "))
        self.assertEqual(out[2:], [f"//MSG {self.a} 2", "Text 1", "Zeile 2",
                                   f"//SYNCEND 0 seq={store.sync_seq()}"])
        seq = store.sync_seq()
        # nothing new: one short line
        self.assertEqual(self.ask(s, t, f"//SYNC seq={seq}"), [f"//SYNCEND 0 seq={seq}"])
        # read at the terminal, deleted at the terminal, new mail for somebody else
        self.app.service.read(self.a, "OE3GAS", False)
        self.app.service.delete(self.b, "OE3TEC", False)
        mail(self.app, "OE3TEC", "OE1ABC", "Fremd 2")
        out = self.ask(s, t, f"//SYNC seq={seq}")
        self.assertEqual(out[:2], [f"//S {self.a} Y -", f"//D {self.b}"])
        self.assertTrue(out[2].startswith("//SYNCEND 0 seq="))
        seq = store.sync_seq()
        # kill and read in the same request; nothing of it comes back
        f = mail(self.app, "OE3TEC", "OE3GAS", "Neu", "neu")
        out = self.ask(s, t, f"//SYNC seq={seq} k={f},{self.c},999 r={self.a}")
        self.assertEqual(out[:3], [f"//K {f} ok", f"//K {self.c} not_found", "//K 999 ok"])
        self.assertEqual(len(out), 4)
        self.assertIsNone(store.get(f))
        # the TinyBox is behind the client (database set up anew)
        self.assertEqual(self.ask(s, t, "//SYNC seq=99999"), ["//ERR seq"])

    def test_sync_paging(self):
        s, t = client(self.app, caps="CHAT,SYNC,SYNC2")
        for i in range(5):
            mail(self.app, "OE3TEC", "OE3GAS", f"Nr {i}", f"Text {i}")
        out = self.ask(s, t, "//SYNC seq=0 max=200")
        self.assertTrue(out[-1].startswith("//SYNCEND "))
        more, seq = out[-1].split()[1], int(out[-1].split("seq=")[1])
        self.assertGreater(int(more), 0)
        n = len(out) - 1
        out = self.ask(s, t, f"//SYNC seq={seq} max=10000")
        self.assertEqual(n + len(out) - 1, 7)                # all 7 headers, none twice
        self.assertTrue(out[-1].endswith(f"seq={self.app.service.store.sync_seq()}"))

    def test_bsync(self):
        s, t = client(self.app, caps="CHAT,SYNC,SYNC2")
        store = self.app.service.store
        out = self.ask(s, t, "//BSYNC seq=0 h=0 WX=0 want=10")
        self.assertEqual(out[:2], ["//RL ALL WX", "//RN ALL=1 WX=1"])
        self.assertTrue(out[2].startswith(f"//M {self.e} B "))     # ALL not subscribed
        self.assertEqual(len(out), 4)                               # long text: not pushed
        h = out[3].split("h=")[1]
        seq = store.sync_seq()
        # list unchanged: only the counts
        out = self.ask(s, t, f"//BSYNC seq={seq} h={h} WX={self.e}")
        self.assertEqual(out, ["//RN ALL=1 WX=1", f"//BSYNCEND 0 seq={seq} h={h}"])
        # subscribed ALL too: its bulletin with the text; a bulletin expired
        self.app.service.delete(self.e, "OE3TEC", True)
        out = self.ask(s, t, f"//BSYNC seq={seq} h={h} WX={self.e} ALL=0 want=100")
        self.assertEqual(out[0], "//RL ALL")                        # WX has no bulletin left
        self.assertEqual(out[1:3], ["//RN ALL=1", f"//D {self.e}"])
        self.assertTrue(out[3].startswith(f"//M {self.d} B "))
        self.assertEqual(out[4:6], [f"//MSG {self.d} 1", "kurz"])

    def bsync_rounds(self, s, t, after, seq=0, max_bytes=200, want=0):
        """Plays the client: asks on until more=0, `after` grows with every page
        as in the client. Returns the //M lines, the rounds and the new seq.
        Fails as soon as a request repeats - that is the loop from the bug."""
        h, seen, asked = "0", [], set()
        for rounds in range(1, 31):
            req = (f"//BSYNC seq={seq} h={h} "
                   + " ".join(f"{r}={n}" for r, n in sorted(after.items()))
                   + f" max={max_bytes} want={want}")
            self.assertNotIn(req, asked, "the TinyBox asks for the same page again")
            asked.add(req)
            out = self.ask(s, t, req)
            end = out[-1].split()
            self.assertEqual(end[0], "//BSYNCEND", out[-1])
            for line in out[:-1]:
                if line.startswith("//M "):
                    seen.append(line)
                    p = line.split()                       # //M id type status fwd size
                    after[p[7]] = max(after.get(p[7], 0), int(p[1]))     # from to ...
            for w in end[2:]:
                if w.startswith("seq="):
                    seq = int(w[4:])
                elif w.startswith("h="):
                    h = w[2:]
            if not int(end[1]):
                return seen, rounds, seq
        self.fail("the bulletin sync does not come to an end")

    def test_bsync_keeps_after_at_seq0(self):
        """seq=0 says nothing about the content: what the client has by after=
        stays there. Before the fix every bulletin counted as changed."""
        s, t = client(self.app, caps="CHAT,SYNC,SYNC2")
        out = self.ask(s, t, f"//BSYNC seq=0 h=0 ALL={self.d} WX={self.e}")
        self.assertEqual([x for x in out if x.startswith("//M ")], [])
        self.assertTrue(out[-1].startswith("//BSYNCEND 0 "))

    def test_bsync_paging_ends(self):
        """A backlog over several pages: after= moves on, nothing comes twice."""
        s, t = client(self.app, caps="CHAT,SYNC,SYNC2")
        new = [mail(self.app, "OE3TEC", "ALL", f"Bulletin Nr {i}", f"Text {i}", type="B")
               for i in range(8)]
        seen, rounds, seq = self.bsync_rounds(s, t, {"ALL": 0, "WX": 0})
        ids = [int(x.split()[1]) for x in seen]
        self.assertGreater(rounds, 1)                        # really paged
        self.assertEqual(len(ids), len(set(ids)))            # nothing twice
        self.assertEqual(set(ids), {self.d, self.e, *new})
        self.assertEqual(seq, self.app.service.store.sync_seq())

    def test_bsync_backlog_with_seq_not_twice(self):
        """Log 2026-10-13: the client knew seq, then 24 WX bulletins came in.
        Paged by after=, each bulletin came again as 'changed' (its cseq is
        above the client's seq) - 49 headers for 25 bulletins."""
        s, t = client(self.app, caps="CHAT,SYNC,SYNC2")
        store = self.app.service.store
        after = {"ALL": 0, "WX": 0}
        self.bsync_rounds(s, t, after)                       # client is up to date
        seq = store.sync_seq()
        new = [mail(self.app, "OE3TEC", "WX", f"Wetter Nr {i}", f"Text {i}", type="B")
               for i in range(8)]
        seen, rounds, seq = self.bsync_rounds(s, t, after, seq=seq)
        ids = [int(x.split()[1]) for x in seen]
        self.assertGreater(rounds, 1)                        # really paged
        self.assertEqual(ids, new)                           # each once, in order
        self.assertEqual(seq, store.sync_seq())

    def test_zsync_client_keeps_empty_text_lines(self):
        """Log 2026-10-13, session #4: a bulletin text ends in an empty line
        (clientnews: strip() + newline). The client dropped empty lines of a
        //ZSYNC block, counted one body line short and swallowed //BSYNCEND
        as text - the sync waited for its end for ever, and the next run asked
        the very same thing again."""
        syncer = sync.Syncer(object(), object())
        syncer.queue = asyncio.Queue()
        rows = ["//RN TBNEWS=1", "//M 77 B N OE3GAS-1 TBNEWS - - - 1791922433 Client",
                "//MSG 77 3", "zeile1", "zeile2", "", "//BSYNCEND 0 seq=147 h=dd0b"]
        plain = "".join(r + "\r" for r in rows).encode()
        syncer._zsync(lzhuf.compress_b1(plain))
        items = []
        while not syncer.queue.empty():
            items.append(syncer.queue.get_nowait())
        self.assertEqual(items[2], ("text", 77, "zeile1\nzeile2\n"))
        self.assertEqual(items[3], ("line", "//BSYNCEND 0 seq=147 h=dd0b"))
        self.assertIsNone(syncer._body)

    def test_bsync_replaced_paging_ends(self):
        """Bulletins the client has, with new content: they page by cseq, and
        seq= in the end line follows them."""
        s, t = client(self.app, caps="CHAT,SYNC,SYNC2")
        svc = self.app.service
        for i in range(8):
            svc.create(from_call="OE3TEC", to_call="ALL", type="B", subject=f"WX Lage {i}",
                       body=f"Text {i}", replace_key=f"wx{i}", origin="telnet")
        after = {"ALL": 0, "WX": 0}
        self.bsync_rounds(s, t, after)                       # client is up to date
        seen, _, seq = self.bsync_rounds(s, t, dict(after), seq=svc.store.sync_seq())
        self.assertEqual(seen, [])
        for i in range(8):                                   # same key: old number, new text
            svc.create(from_call="OE3TEC", to_call="ALL", type="B",
                       subject=f"WX Lage {i} neu", body=f"Text {i} neu",
                       replace_key=f"wx{i}", origin="telnet")
        seen, rounds, seq = self.bsync_rounds(s, t, after, seq=seq)
        ids = [int(x.split()[1]) for x in seen]
        self.assertGreater(rounds, 1)                        # really paged
        self.assertEqual(len(ids), len(set(ids)))            # nothing twice
        self.assertEqual(len(ids), 8)
        self.assertEqual(seq, svc.store.sync_seq())

    def test_sync_paging_ends(self):
        """The mail path pages by seq: every round moves seq= on."""
        s, t = client(self.app, caps="CHAT,SYNC,SYNC2")
        for i in range(8):
            mail(self.app, "OE3TEC", "OE3GAS", f"Nr {i}", f"Text {i}")
        seq, seen, asked = 0, [], set()
        for rounds in range(1, 31):
            req = f"//SYNC seq={seq} max=200 want=0"
            self.assertNotIn(req, asked, "the TinyBox asks for the same page again")
            asked.add(req)
            out = self.ask(s, t, req)
            end = out[-1].split()
            seen += [x for x in out[:-1] if x.startswith("//M ")]
            seq = int(end[2][4:])
            if not int(end[1]):
                break
        else:
            self.fail("the mail sync does not come to an end")
        ids = [int(x.split()[1]) for x in seen]
        self.assertGreater(rounds, 1)
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(len(ids), 10)                       # the two from setUp and 8 new
        self.assertEqual(seq, self.app.service.store.sync_seq())

    def test_no_loop_guard(self):
        """The client stops when a request repeats instead of staying on the air."""
        asked: set[str] = set()
        sync._no_loop(asked, "//SYNC seq=1 max=1024 want=754")
        sync._no_loop(asked, "//SYNC seq=2 max=1024 want=754")
        with self.assertRaises(sync.SyncError):
            sync._no_loop(asked, "//SYNC seq=1 max=1024 want=754")

    def test_zsync_on_radio(self):
        s, t = client(self.app, caps="CHAT,SYNC,SYNC2,Z", radio=True)
        for i in range(6):
            mail(self.app, "OE3TEC", "OE3GAS", f"Wetterbericht Weinviertel Nr {i}", f"Text {i}")
        type_lines(s, "//SYNC seq=0 want=300")
        head, _, rest = t.raw.partition(b"\r")
        self.assertTrue(head.startswith(b"//ZSYNC "))
        n = int(head.split()[1])
        self.assertEqual(len(rest), n)
        text = lzhuf.decompress_b1(rest).decode()
        self.assertGreater(len(text), 1.4 * n)                     # headers compress well
        lines = text.split("\r")
        self.assertEqual(sum(1 for x in lines if x.startswith("//M ")), 8)
        self.assertEqual(sum(1 for x in lines if x.startswith("//MSG ")), 7)   # not my own
        self.assertTrue(lines[-2].startswith("//SYNCEND 0 seq="))
        # a short answer stays plain text
        t.raw = b""
        type_lines(s, f"//SYNC seq={self.app.service.store.sync_seq()}")
        self.assertTrue(t.raw.startswith(b"//SYNCEND 0 seq="))

    def test_store_counter(self):
        store = self.app.service.store
        self.assertEqual([m.id for m in store.changed_since(0)][-1], self.e)
        seq = store.sync_seq()
        store.mark_read(self.a)
        self.assertEqual([(m.id, m.cseq > seq) for m in store.changed_since(seq)],
                         [(self.a, False)])
        store.replace_content(self.d, to_call="ALL", from_call="OE3TEC", subject="neu",
                              body="neu", created="2030-01-01T00:00:00Z", expires=None)
        self.assertTrue(all(m.cseq > seq for m in store.changed_since(seq) if m.id == self.d))
        store.delete(self.c)
        self.assertEqual([g[0] for g in store.gone_since(seq)], [self.c])
        for _ in range(3):
            store.delete(mail(self.app, "OE3TEC", "OE3GAS", "weg"))
        store.purge_gone(keep=2)
        self.assertEqual(len(store.gone_since(0)), 2)
        self.assertGreater(store.gone_floor(), seq)

    def test_client_end_to_end(self):
        """Client against the TinyBox over the fake radio: one exchange when nothing
        is new, deletions in the TinyBox arrive here, a new database starts over."""
        async def scenario():
            dw = FakeDirewolf()
            port = await dw.start()
            app = chat_app()
            app.cfg.direwolf = dataclasses.replace(app.cfg.direwolf, agw_port=port,
                                                   reconnect_sec=1)
            adapter = tb_agw.AgwAdapter(app)
            app.agw = adapter
            t1 = asyncio.create_task(adapter.run())
            await asyncio.wait_for(adapter.connected.wait(), 5)
            a = mail(app, "OE3TEC", "OE3GAS", "Eins", "Text eins")
            b = mail(app, "OE3TEC", "OE3GAS", "Zwei", "Text zwei")
            mail(app, "OE3TEC", "WX", "Wetter", "Sonne", type="B")
            with tempfile.TemporaryDirectory() as tmp:
                core = ClientCore(client_cfg(tmp, agw_port=port, sync_chunk=1024,
                                             sync_pause=0.05))
                box = core.mailbox
                t2 = asyncio.create_task(core.run())
                await asyncio.wait_for(core.link.agw_up.wait(), 5)
                box.subscribe("WX", True)
                box.save_out(None, "P", "OE3TEC", "Vom Client", "Hallo Tec")

                def requests():                    # the sync requests of the client
                    return [x[2:] for x in core.console
                            if x.startswith("> //") and not x.startswith(("> //CLIENT",
                                                                           "> //BOARDS"))]

                core.sync.start("mail")
                await until(lambda: not core.sync.running, 30)
                self.assertEqual(core.sync.status["error"], "")
                reqs = requests()
                self.assertTrue(any(r.startswith("//SYNC seq=0 ") for r in reqs))
                self.assertFalse(any(r.startswith(("//MLIST", "//GET")) for r in reqs))
                inbox = box.folder("inbox")
                self.assertEqual([m["subject"] for m in inbox], ["Zwei", "Eins"])
                self.assertEqual(box.message(a)["body"], "Text eins")     # pushed texts
                self.assertEqual(box.folder("sent")[0]["subject"], "Vom Client")
                sent_id = box.folder("sent")[0]["id"]
                self.assertEqual(box.message(sent_id)["body"], "Hallo Tec")  # kept, not fetched
                seq = app.service.store.sync_seq()
                self.assertEqual(box.get("seq.mail"), seq)
                # nothing new: exactly one request, nothing fetched
                core.console.clear()
                core.sync.start("mail")
                await until(lambda: not core.sync.running, 30)
                self.assertEqual(requests(), [f"//SYNC seq={seq} max=1024 want=754 short=256"])
                # read here, deleted here; deleted and read in the TinyBox
                box.open(a)
                box.delete(b)
                sent_id = box.folder("sent")[0]["id"]
                app.service.delete(sent_id, "OE3TEC", False)
                core.console.clear()
                core.sync.start("mail")
                await until(lambda: not core.sync.running, 30)
                self.assertEqual(core.sync.status["error"], "")
                self.assertEqual(len(requests()), 1)
                self.assertIn(f" k={b} r={a} ", requests()[0])
                self.assertEqual(app.service.store.get(a).status, "Y")
                self.assertIsNone(app.service.store.get(b))
                self.assertEqual(box.folder("sent"), [])                 # //D
                self.assertEqual(box.todo("kill") + box.todo("read"), [])
                # bulletins: list and header in one exchange (text on demand, CR40)
                core.console.clear()
                core.sync.start("bulletins")
                await until(lambda: not core.sync.running, 30)
                self.assertEqual(core.sync.status["error"], "")
                self.assertEqual(len(requests()), 1)
                self.assertEqual([m["subject"] for m in box.folder("b:WX")], ["Wetter"])
                self.assertIsNone(box.message(box.folder("b:WX")[0]["id"])["body"])
                self.assertIn(" want=0", requests()[0])
                names = {r["name"]: r for r in box.summary()["rubrics"]}
                self.assertEqual((names["WX"]["server"], names["WX"]["local"]), (1, 1))
                h = box.get("rubrics.h")
                core.console.clear()
                core.sync.start("bulletins")
                await until(lambda: not core.sync.running, 30)
                self.assertTrue(requests()[0].startswith(f"//BSYNC seq={box.get('seq.bulletins')} h={h} WX="))
                self.assertEqual(names["WX"]["desc"], "")
                # the TinyBox database is new: the client starts over by itself
                box.put("seq.mail", 99999)
                core.console.clear()
                core.sync.start("mail")
                await until(lambda: not core.sync.running, 30)
                self.assertEqual(core.sync.status["error"], "")
                self.assertEqual([r.split()[1] for r in requests()], ["seq=99999", "seq=0"])
                self.assertEqual([m["subject"] for m in box.folder("inbox")], ["Eins"])
                box.close()
                t2.cancel()
            t1.cancel()
            dw.server.close()
        asyncio.run(scenario())


class MultiRecipientTests(unittest.TestCase):
    """CR27: personal mail to several recipients - one message each, text once."""

    def setUp(self):
        self.app = chat_app()

    def test_terminal(self):
        s, t = login(self.app, "OE3GAS")
        t.take()
        type_lines(s, "S OE3TEC,OE1ABC,OE3TEC", "Hallo", "Text", "/EX")
        out = t.take()
        self.assertIn("Msg 1, 2 saved.", out)                       # duplicate folded
        msgs = self.app.service.store.list_messages()
        self.assertEqual(sorted((m.to_call, m.body) for m in msgs),
                         [("OE1ABC", "To: OE3TEC, OE1ABC\nText"), ("OE3TEC", "To: OE3TEC, OE1ABC\nText")])
        self.assertNotEqual(msgs[0].bid, msgs[1].bid)                # own MID each
        type_lines(s, "S OE3TEC,XX")
        self.assertIn("invalid", t.take().lower())                   # nothing stored
        self.assertEqual(len(self.app.service.store.list_messages()), 2)
        type_lines(s, "SB ALL,WX")
        self.assertIn("one destination", t.take())
        type_lines(s, "S OE3TEC,OE1ABC $ABC123")
        self.assertIn("one destination", t.take())

    def test_client_send(self):
        s, t = client(self.app)
        type_lines(s, "//SEND P OE3TEC,OE1ABC 1 mid=abcdefgh12", "Betreff", "Zeile")
        self.assertEqual(t.take(), "//SENT 1 2\r")
        type_lines(s, "//SEND P OE3TEC,OE1ABC 1 mid=abcdefgh12", "Betreff", "Zeile")
        self.assertEqual(t.take(), "//SENT 1 2\r")                   # same mid: not twice
        self.assertEqual(self.app.service.store.get(2).body, "To: OE3TEC, OE1ABC\nZeile")
        type_lines(s, "//SEND P OE3TEC,XX 0 mid=abcdefgh13", "Betreff")
        self.assertTrue(t.take().startswith("//ERR send invalid_call"))
        self.assertEqual(len(self.app.service.store.list_messages()), 2)
        type_lines(s, "//SEND P OE3TEC 0 mid=abcdefgh14", "Einzeln")
        self.assertEqual(t.take(), "//SENT 3\r")
        self.assertEqual(self.app.service.store.get(3).msgid, "tbc-abcdefgh14")   # as before
        self.assertEqual(self.app.service.store.get(3).body, "")                  # no To: line

    def test_have_before_sending_again(self):
        """CR69: //HAVE answers for a mail that is already stored - before its text."""
        s, t = client(self.app, caps="CHAT,SYNC,HAVE")
        type_lines(s, "//HAVE abcdefgh20 OE3TEC")
        self.assertEqual(t.take(), "//HAVE abcdefgh20 -\r")           # not here: send it
        type_lines(s, "//SEND P OE3TEC 0 mid=abcdefgh20", "Einzeln")
        new = int(t.take().split()[1])
        type_lines(s, "//HAVE abcdefgh20 OE3TEC")
        self.assertEqual(t.take(), f"//HAVE abcdefgh20 {new}\r")
        type_lines(s, "//SEND P OE3TEC,OE1ABC 0 mid=abcdefgh21", "Zwei")
        ids = t.take().split()[1:]
        type_lines(s, "//HAVE abcdefgh21 OE3TEC,OE1ABC")
        self.assertEqual(t.take().split()[2:], ids)
        type_lines(s, "//HAVE abcdefgh21 OE3TEC,OE3XYZ")               # one not there
        self.assertEqual(t.take(), "//HAVE abcdefgh21 -\r")
        s2, t2 = client(self.app, call="OE1ABC", caps="CHAT,SYNC,HAVE")
        type_lines(s2, "//HAVE abcdefgh20 OE3TEC")                       # not his mail
        self.assertEqual(t2.take(), "//HAVE abcdefgh20 -\r")
        type_lines(s, "//HAVE bad OE3TEC")
        self.assertEqual(t.take(), "//ERR have usage\r")

    def test_client_store(self):
        with tempfile.TemporaryDirectory() as tmp:
            box = MailStore(Path(tmp) / "m.db", "OE3GAS")
            oid = box.save_out(None, "P", "OE3TEC,OE1ABC@OE3XYZ", "Hallo", "Text")
            item = box.outbox()[0]
            self.assertEqual(item["oid"], oid)
            calls, _, at = item["to_call"].partition("@")
            for msg_id, call in zip([7, 8], calls.split(",")):
                box.add_sent(msg_id, item, "OE3GAS", call, at)
            sent = box.folder("sent")
            self.assertEqual(sorted((m["id"], m["to_call"], m["at_addr"]) for m in sent),
                             [(7, "OE3TEC", "OE3XYZ"), (8, "OE1ABC", "OE3XYZ")])
            self.assertEqual(box.folder("outbox"), [])
            box.close()


class ShortTextTests(unittest.TestCase):
    """CR40: short= - only short personal mail comes with its text."""

    def setUp(self):
        self.app = chat_app()
        self.a = mail(self.app, "OE3TEC", "OE3GAS", "Kurz", "kurz")
        self.b = mail(self.app, "OE3TEC", "OE3GAS", "Lang", "x" * 300)

    def test_cap_granted(self):
        s, t = client(self.app, caps="CHAT,SYNC,SYNC2,SHORT")
        self.assertIn("SHORT", s.client.caps)

    def test_only_short_texts(self):
        s, t = client(self.app, caps="CHAT,SYNC,SYNC2,SHORT")
        type_lines(s, "//SYNC seq=0 want=1000 short=256")
        out = t.take().split("\r")[:-1]
        self.assertIn(f"//MSG {self.a} 1", out)
        self.assertNotIn(f"//MSG {self.b} 1", out)
        self.assertTrue(any(x.startswith(f"//M {self.b} ") for x in out))
        type_lines(s, "//SYNC seq=0 want=1000 short=0")
        out = t.take().split("\r")[:-1]
        self.assertFalse([x for x in out if x.startswith("//MSG")])
        type_lines(s, "//SYNC seq=0 want=1000 short=x")
        self.assertEqual(t.take().split("\r")[:-1], ["//ERR sync"])


class LoginSyncAbortTests(unittest.TestCase):
    """CR40: headers after every login, orderly abort with what is left,
    a text clicked meanwhile goes between two exchanges."""

    def test_login_abort_and_fetch(self):
        async def scenario():
            dw = FakeDirewolf()
            port = await dw.start()
            app = chat_app()
            app.cfg.direwolf = dataclasses.replace(app.cfg.direwolf, agw_port=port,
                                                   reconnect_sec=1)
            adapter = tb_agw.AgwAdapter(app)
            app.agw = adapter
            t1 = asyncio.create_task(adapter.run())
            await asyncio.wait_for(adapter.connected.wait(), 5)
            first = mail(app, "OE3TEC", "OE3GAS", "Erste", LONG)
            for i in range(30):
                mail(app, "OE3TEC", "OE3GAS", f"Nummer {i}", "x" * 400)
            for i in range(5):
                mail(app, "OE3TEC", "WX", f"Wetter {i}", "Sonne", type="B")
            with tempfile.TemporaryDirectory() as tmp:
                core = ClientCore(client_cfg(tmp, agw_port=port, sync_chunk=256,
                                             sync_pause=0.3))
                box = core.mailbox
                box.subscribe("WX", True)
                t2 = asyncio.create_task(core.run())
                await asyncio.wait_for(core.link.agw_up.wait(), 5)
                await core.connect()
                # the login starts the sync by itself
                await until(lambda: core.sync.running and core.sync.status["scope"] == "login", 10)
                await until(lambda: "Press Abort" in core.sync.status["notice"], 20)
                self.assertTrue(core.sync.status["notice"].startswith("Mail: "))
                self.assertIn("mail header(s)", core.sync.status["notice"])
                # a click meanwhile: served between two exchanges
                await until(lambda: box.message(first) is not None, 20)
                self.assertEqual(core.sync.fetch(first), "")
                await until(lambda: box.message(first)["body"] is not None, 30)
                self.assertTrue(core.sync.running)
                # orderly abort: the exchange on the air is finished, then stop
                core.sync.abort()
                self.assertTrue(core.sync.status["aborting"])
                await until(lambda: not core.sync.running, 30)
                st = core.sync.status
                self.assertEqual((st["step"], st["error"]), ("aborted", ""))
                self.assertIn("Sync aborted. Still pending:", st["notice"])
                self.assertIn("approx.", st["notice"])
                self.assertTrue(any(x.startswith("*** Sync aborted.") for x in core.console))
                n = len(box.folder("inbox"))
                self.assertLess(n, 31)
                self.assertFalse(box.folder("b:WX"))
                self.assertEqual(core.state, "online")               # the link stays
                # the next sync goes on from there and fetches no long text
                self.assertTrue(core.sync.start("login"))
                await until(lambda: not core.sync.running, 60)
                self.assertEqual(core.sync.status["error"], "")
                self.assertEqual(len(box.folder("inbox")), 31)
                self.assertEqual(len(box.folder("b:WX")), 5)
                self.assertEqual(sum(m["has_body"] for m in box.folder("inbox")), 1)
                self.assertTrue(box.summary()["last_bulletins"])
                core.disconnect()
                await until(lambda: core.state == "offline")
                box.close()
                t2.cancel()
            t1.cancel()
            dw.server.close()
        asyncio.run(scenario())


class EstimateTests(unittest.TestCase):
    def test_human_secs(self):
        self.assertEqual(sync.human_secs(3), "a few seconds")
        self.assertEqual(sync.human_secs(42), "approx. 40 s")
        self.assertEqual(sync.human_secs(100), "approx. 1 min 40 s")
        self.assertEqual(sync.human_secs(120), "approx. 2 min")
        self.assertEqual(sync.human_secs(3600), "approx. 60 min")

    def test_estimate_default_and_measured(self):
        with tempfile.TemporaryDirectory() as tmp:
            core = ClientCore(client_cfg(tmp, sync_chunk=1024, sync_pause=5))
            sy = core.sync
            self.assertTrue(sy.radio)
            # 1000 bytes, 1 exchange: 1000/100 + (5 + 3) = 18 s
            self.assertAlmostEqual(sy.estimate(1000), 18.0)
            sy._air_bytes, sy._air_secs = 2000, 10.0                 # measured 200 B/s
            self.assertAlmostEqual(sy.estimate(1000), 5.0 + 5)
            self.assertEqual(sy.estimate(0), 0.0)
            core.mailbox.close()


class SendAtOnceTests(unittest.TestCase):
    """CR47: a mail put into the outbox goes out at once."""

    def test_outbox_goes_out_at_once(self):
        async def scenario():
            dw = FakeDirewolf()
            port = await dw.start()
            app = chat_app()
            app.cfg.direwolf = dataclasses.replace(app.cfg.direwolf, agw_port=port,
                                                   reconnect_sec=1)
            adapter = tb_agw.AgwAdapter(app)
            app.agw = adapter
            t1 = asyncio.create_task(adapter.run())
            await asyncio.wait_for(adapter.connected.wait(), 5)
            with tempfile.TemporaryDirectory() as tmp:
                core = ClientCore(client_cfg(tmp, agw_port=port, sync_pause=0.05,
                                             sync_on_login=False))
                box = core.mailbox
                t2 = asyncio.create_task(core.run())
                await asyncio.wait_for(core.port.agw_up.wait(), 5)
                self.assertEqual(core.send_outbox(), "")           # nothing waits: nothing to do
                self.assertFalse(core.sync.running)
                # offline: the sync connects by itself, sends, disconnects again
                box.save_out(None, "P", "OE3TEC", "Sofort", "gleich raus")
                self.assertEqual(core.send_outbox(), "")
                await asyncio.sleep(0)
                self.assertEqual(core.sync.status["scope"], "send")
                await until(lambda: not core.sync.running, 20)
                self.assertEqual(core.sync.status["error"], "")
                await until(lambda: core.state == "offline", 10)
                self.assertEqual(box.folder("outbox"), [])
                self.assertEqual([m.body for m in app.service.store.list_messages()
                                  if m.subject == "Sofort"], ["gleich raus"])
                self.assertEqual(box.folder("inbox"), [])          # "send" fetches nothing
                self.assertEqual(list(core.channels), [1])         # its channel is gone again
                # CR69: tried before, but the //SENT never came: the client asks
                # first and does not send the text again
                box.save_out(None, "P", "OE3TEC", "Schon da", "nur einmal")
                item = box.folder("outbox")[0]
                app.service.create(from_call="OE3GAS", to_call="OE3TEC", type="P",
                                   subject="Schon da", body="nur einmal", origin="radio",
                                   msgid=f"tbc-{item['mid']}")
                box.put(f"out_try.{item['mid']}", 1)
                from tinybox import clientsync
                sends, orig = [], clientsync._send
                clientsync._send = lambda s_, p_: (sends.append(p_), orig(s_, p_))
                self.assertEqual(core.send_outbox(), "")
                await until(lambda: not core.sync.running, 20)
                clientsync._send = orig
                self.assertEqual(sends, [])                         # the text never went out
                self.assertEqual(box.folder("outbox"), [])
                self.assertEqual(len([m for m in app.service.store.list_messages()
                                      if m.subject == "Schon da"]), 1)
                self.assertIsNone(box.get(f"out_try.{item['mid']}"))
                await until(lambda: core.state == "offline", 10)
                # connected to the own TinyBox: over that connection
                await core.connect("OE3GAS-1")
                await until(lambda: core.state == "online" and core.caps, 10)
                box.save_out(None, "P", "OE3TEC", "Online", "auch gleich")
                self.assertEqual(core.send_outbox(), "")
                await until(lambda: not core.sync.running and not box.folder("outbox"), 20)
                self.assertEqual(core.state, "online")              # the link stays
                # written while a sync runs: goes out right after it
                self.assertTrue(core.sync.start("bulletins"))
                box.save_out(None, "P", "OE3TEC", "Danach", "nach dem Sync")
                self.assertEqual(core.send_outbox(), "")
                self.assertTrue(core.sync.send_again)
                await until(lambda: not box.folder("outbox"), 20)
                self.assertTrue(any(m.subject == "Danach" for m in app.service.store.list_messages()))
                core.disconnect()
                await until(lambda: core.state == "offline")
                t2.cancel()
            t1.cancel()
            dw.server.close()
        asyncio.run(scenario())

    def test_other_tinybox_waits(self):
        with tempfile.TemporaryDirectory() as tmp:
            core = ClientCore(client_cfg(tmp))
            core.mailbox.save_out(None, "P", "OE3TEC", "x", "y")
            core.chan.target, core.chan.state, core.chan.mode = "OE1XAB-1", "online", "tinybox"
            self.assertIn("OE1XAB-1", core.send_outbox())
            self.assertFalse(core.sync.running)
