"""TinyBox client: parsers, emoji-free wire format, and end to end against a
real TinyBox (telnet test port, and radio through a fake Direwolf)."""

from __future__ import annotations

import asyncio
import dataclasses
import json
import struct
import tempfile
import time
import unittest
from pathlib import Path

from tbclient import config as ccfg
from tbclient import proto, radio
from tbclient import channels as channels_mod
from tbclient import core as core_mod
from tbclient.core import ClientCore
from tbclient.web import WebServer
from prcore import agw as agwcodec
from tinybox.adapters import agw as tb_agw
from tinybox.adapters import telnet
from tests.test_chat import chat_app
from tests.test_tinybox import ROOT, FakeTransport, login, type_lines


def addr(call: str, last: bool) -> bytes:
    base, _, ssid = call.partition("-")
    return bytes(c << 1 for c in base.ljust(6).encode()) + bytes(
        [0x60 | (int(ssid or 0) << 1) | (1 if last else 0)])


def raw_frame(dest, src, control, info=b"", path=()):
    calls = [dest, src, *path]
    a = b"".join(addr(c, i == len(calls) - 1) for i, c in enumerate(calls))
    return a + bytes([control]) + ((bytes([0xF0]) + info) if control in (0x03, 0x00) else b"")


class RadioTests(unittest.TestCase):
    def test_decode_ui_and_path(self):
        f = radio.decode(raw_frame("TBCHAT-1", "OE3GAS-1", 0x03, b"#1 X: y"))
        self.assertTrue(f.is_ui and f.direct)
        self.assertEqual((f.dest, f.src, f.info), ("TBCHAT-1", "OE3GAS-1", b"#1 X: y"))
        f = radio.decode(raw_frame("APRS", "OE3TEC", 0x03, b"x", ["OE1XAR"]))
        self.assertFalse(f.direct)
        self.assertIsNone(radio.decode(b"\x00\x01"))

    def test_aprs_symbols(self):
        self.assertEqual(radio.aprs_symbol(b"!4833.07N/01606.22E-PHG2360"), "/-")
        self.assertEqual(radio.aprs_symbol(b"=4833.07N/01606.22E>mobil"), "/>")
        self.assertEqual(radio.aprs_symbol(b"@092345z4833.07N\\01606.22E#"), "\\#")
        self.assertEqual(radio.aprs_symbol(b"!/5L!!<*e7>7P["), "/>")       # compressed
        self.assertEqual(radio.aprs_symbol(b"`c51!f?>/]\"4V}="), "/>")     # Mic-E
        self.assertIsNone(radio.aprs_symbol(b">status text"))


class ProtoTests(unittest.TestCase):
    def test_events(self):
        e = proto.parse_event("#4F OE3GAS: Servus, Wetter passt :+1")
        self.assertEqual((e.seq, e.kind, e.call, e.text), (0x4F, "line", "OE3GAS",
                                                          "Servus, Wetter passt :+1"))
        e = proto.parse_event("#50 +OE3GAS /-")
        self.assertEqual((e.kind, e.call, e.symbol), ("join", "OE3GAS", "/-"))
        self.assertEqual(proto.parse_event("#51 -OE3GAS-9").kind, "leave")
        e = proto.parse_event("#52 OE3TEC *4F :+1")
        self.assertEqual((e.kind, e.ref, e.text), ("react", 0x4F, ":+1"))
        self.assertEqual(proto.parse_event("#53 !Board closes").kind, "system")
        self.assertIsNone(proto.parse_event("#zz nonsense"))
        self.assertIsNone(proto.parse_event("# 12 nothing"))

    def test_unwrap(self):
        u = proto.Unwrapper()
        u.reset(0xFE)
        self.assertEqual([u.unwrap(s) for s in (0xFF, 0x00, 0x01)], [255, 256, 257])
        self.assertEqual(u.unwrap(0xFF), 255)            # an old one, resent


class ConfigTests(unittest.TestCase):
    def test_example(self):
        cfg = ccfg.load(ROOT / "tbclient.conf.example")
        self.assertEqual((cfg.mycall, cfg.tinybox_call, cfg.link, cfg.web_port),
                         ("OE3GAS", "OE3GAS-1", "agw", 7744))
        self.assertEqual(cfg.data_dir, ROOT / "data" / "tbclient")
        self.assertEqual((cfg.hints, cfg.img_rate, cfg.img_rate_fixed), ([], 105, False))

    def load(self, text: str, dw: str | None = None) -> ccfg.Config:
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            if dw is not None:
                (Path(d) / "direwolf.conf").write_text(dw, encoding="utf-8")
                text = text.replace("DWDIR", d)
            p = Path(d) / "c.conf"
            p.write_text("[station]\nmycall = OE3GAS\n" + text, encoding="utf-8")
            return ccfg.load(p)

    def test_cr70_new_and_old_names(self):
        cfg = self.load("[radio]\ninterface = kiss\n[kiss]\nport = 8201\n")
        self.assertEqual((cfg.link, cfg.kiss_status_port, cfg.hints), ("kiss", 8202, []))
        cfg = self.load("[tinybox]\nlink = kiss\n[kiss]\nport = 8201\nair_baud = 350\n"
                        "[ax25]\nt1_min_sec = 20\nt1_max_sec = 60\n")
        self.assertEqual((cfg.link, cfg.kiss_air_baud), ("kiss", 350))
        self.assertEqual(cfg.kiss_fixed, frozenset({"air_baud", "t1_min_sec", "t1_max_sec"}))
        text = "\n".join(cfg.hints)
        self.assertIn("[tinybox] link is the old name - use [radio] interface", text)
        self.assertIn("air_baud = 350: overrides the kisshub value", text)
        self.assertEqual(cfg.img_rate, 31)                     # estimated from 350 Bd

    def test_cr70_agw_from_direwolf_conf(self):
        cfg = self.load("[agw]\ndirewolf_conf = DWDIR\n[direwolf]\nradio_port = 0\n",
                        "AGWPORT 8010\nMODEM 9600\n")
        self.assertEqual((cfg.agw_port, cfg.img_rate), (8010, 840))
        self.assertIn("old name", cfg.hints[0])
        self.assertIn("MODEM 9600", "\n".join(ccfg.radio_lines(cfg)))
        with self.assertRaises(ccfg.ConfigError):
            self.load("[agw]\ndirewolf_conf = /nowhere/x\n")


def client_cfg(tmp: str, **kw) -> ccfg.Config:
    return dataclasses.replace(ccfg.Config(), mycall="OE3GAS", tinybox_call="OE3GAS-1",
                               data_dir=Path(tmp), **kw)


async def until(cond, timeout=5.0):
    for _ in range(int(timeout / 0.02)):
        if cond():
            return
        await asyncio.sleep(0.02)
    raise AssertionError("condition not reached")


# --- a fake Direwolf: AGW server, the "air" connects the AGW clients -------------

H = agwcodec.HEADER


class FakeDirewolf:
    def __init__(self) -> None:
        self.clients: list[dict] = []
        self.ui_sent: list[tuple[str, str]] = []
        self.chat_iframes: list[bytes] = []
        self.via_connects: list[tuple[str, list[str]]] = []      # CR71: AGW 'v'

    async def start(self) -> int:
        self.server = await asyncio.start_server(self._conn, "127.0.0.1", 0)
        return self.server.sockets[0].getsockname()[1]

    def _put(self, c, kind, cfrom="", cto="", data=b"", pid=0):
        c["w"].write(H.pack(0, kind.encode(), pid, cfrom.encode(), cto.encode(), len(data), 0)
                     + data)

    def _owner(self, call):
        return next((c for c in self.clients if call in c["calls"]), None)

    def _air(self, sender, frame: bytes):
        for c in self.clients:
            if c is not sender and c["mon"]:
                self._put(c, "K", data=b"\x00" + frame)

    async def _conn(self, r, w):
        me = {"w": w, "calls": set(), "mon": False}
        self.clients.append(me)
        try:
            while True:
                _p, kind, pid, cf, ct, n, _ = H.unpack(await r.readexactly(H.size))
                data = await r.readexactly(n) if n else b""
                kind, cf, ct = kind.decode(), agwcodec.decode_call(cf), agwcodec.decode_call(ct)
                if kind == "X":
                    me["calls"].add(cf)
                    self._put(me, "X", cf, data=b"\x01")
                elif kind == "k":
                    me["mon"] = True
                elif kind in ("C", "v"):
                    if kind == "v":                           # CR71: connect via digis
                        n = data[0] if data else 0
                        self.via_connects.append((ct, [agwcodec.decode_call(
                            data[1 + 10 * i:11 + 10 * i]) for i in range(n)]))
                    other = self._owner(ct)
                    if other is None:                         # nobody answers (CR42)
                        self._put(me, "d", ct, cf)
                        await w.drain()
                        continue
                    self._put(other, "C", cf, ct)                 # incoming connect
                    self._put(me, "C", ct, cf)                    # connected
                    self._air(me, raw_frame(ct, cf, 0x2F))        # SABM
                    self._air(other, raw_frame(cf, ct, 0x63))     # UA, heard directly
                elif kind == "D":
                    if data.startswith(b"#"):
                        self.chat_iframes.append(data)
                    self._put(self._owner(ct), "D", cf, ct, data, 0xF0)
                    self._air(me, raw_frame(ct, cf, 0x00, data))
                elif kind == "M":
                    self.ui_sent.append((ct, data.decode()))
                    self._air(me, raw_frame(ct, cf, 0x03, data))
                elif kind == "Y":
                    self._put(me, "Y", cf, ct, struct.pack("<I", 0))
                elif kind == "d":
                    other = self._owner(ct)
                    if other:
                        self._put(other, "d", cf, ct)
                    self._put(me, "d", ct, cf)
                await w.drain()
        except (asyncio.IncompleteReadError, ConnectionError):
            pass


class OwnReactionTests(unittest.TestCase):
    """CR8: an own reaction shows at once, the echo confirms it."""

    def test_react_shows_at_once(self):
        async def scenario():
            with tempfile.TemporaryDirectory() as tmp:
                core = ClientCore(client_cfg(tmp, link="telnet"))
                sent: list[str] = []
                core.link.send_line = sent.append
                core.board = {"n": 1, "name": "Chat", "keep": "live"}
                core._event(proto.Event(5, "line", "OE3TEC", text="hallo"))
                self.assertTrue(core.react(5, ":+1"))
                self.assertEqual(sent, ["/R 5 :+1"])
                snap = core.snapshot()
                self.assertEqual(snap["messages"][0]["reactions"], {":+1": ["OE3GAS"]})
                self.assertEqual(snap["pending_reacts"], ["5::+1"])
                # the echo from the TinyBox: no double entry, no longer pending
                core._event(proto.Event(6, "react", "OE3GAS", text=":+1", ref=5))
                snap = core.snapshot()
                self.assertEqual(snap["messages"][0]["reactions"], {":+1": ["OE3GAS"]})
                self.assertEqual(snap["pending_reacts"], [])
                # no echo within 2 minutes: taken back
                core.react(5, "~01")
                core.pending_reacts[(5, "~01")] -= 200
                snap = core.snapshot()
                self.assertEqual(snap["messages"][0]["reactions"], {":+1": ["OE3GAS"]})
                self.assertEqual(snap["pending_reacts"], [])
        asyncio.run(scenario())


class SymbolChangeTests(unittest.TestCase):
    """CR7: own change goes out as //SYM, a change of others updates the avatars."""

    def test_symbol_change(self):
        async def scenario():
            with tempfile.TemporaryDirectory() as tmp:
                core = ClientCore(client_cfg(tmp, link="telnet"))
                sent: list[str] = []
                core.link.send_line = sent.append
                core.state, core.caps = "online", {"CHAT"}
                core.board = {"n": 1, "name": "TREFF", "keep": "7d"}
                core._event(proto.Event(1, "join", "OE3TEC", symbol="/-"))
                self.assertEqual(core.snapshot()["symbols"]["OE3TEC"], "/-")
                core._event(proto.parse_event("#2 =OE3TEC /k"))
                self.assertEqual(core.snapshot()["symbols"]["OE3TEC"], "/k")
                self.assertEqual([m["kind"] for m in core.messages], ["join"])  # no chat line
                core._event(proto.parse_event("#3 =OE3TEC"))
                self.assertNotIn("OE3TEC", core.snapshot()["symbols"])
                self.assertTrue(core.set_symbol("/>"))
                self.assertEqual(sent[-1], "//SYM />")
                core.set_symbol("")
                self.assertEqual(sent[-1], "//SYM -")
        asyncio.run(scenario())


class HistoryOnRequestTests(unittest.TestCase):
    """CR13: the client asks for the history itself (missed lines by default)."""

    def make(self, tmp):
        core = ClientCore(client_cfg(tmp, link="telnet"))
        sent: list[str] = []
        core.link.send_line = sent.append
        core.state, core.caps = "online", {"CHAT"}
        return core, sent

    def test_join_modes(self):
        async def scenario():
            with tempfile.TemporaryDirectory() as tmp:
                core, sent = self.make(tmp)
                now = int(time.time())
                core._control(f"//IN 1 TREFF 7d 5 hist=7 last=1000 now={now}")
                self.assertEqual(sent[-1], "//HIST max=20")          # first visit: last 20
                self.assertTrue(core.board["loading"])
                core._control("//H 990 OE3TEC: alt")
                core._control("//H 1000 OE3TEC: neu")
                core._control("//H 1000 OE3TEC: neu")               # same line twice: once
                core._control("//HEND 2 5")
                hist = [m for m in core.messages if m.get("history")]
                self.assertEqual([m["text"] for m in hist], ["alt", "neu"])
                self.assertEqual((core.board["older"], core.board["loading"]), (5, False))
                # older ones on request: before the oldest one shown (inclusive)
                self.assertTrue(core.load_history(10))
                self.assertEqual(sent[-1], "//HIST max=10 before=990")
                core._control("//H 980 OE3TEC: noch aelter")
                core._control("//H 990 OE3TEC: auch 990")           # same second as "alt"
                core._control("//H 990 OE3TEC: alt")                # inclusive: already here
                core._control("//HEND 3 4")
                texts = [m["text"] for m in core.messages if m.get("history")]
                self.assertEqual(texts, ["noch aelter", "auch 990", "alt", "neu"])   # in order
                # leaving remembers the visit (TinyBox time); next time only what was missed
                core._clear_board()
                seen = core.settings["seen"]["TREFF"]
                self.assertLessEqual(abs(seen - now), 2)
                n = len(sent)
                core._control(f"//IN 1 TREFF 7d 9 hist=7 last=1000 now={now}")
                self.assertEqual(len(sent), n)                       # nothing new: no request
                core._control(f"//IN 1 TREFF 7d 9 hist=8 last={now + 60} now={now}")
                self.assertEqual(sent[-1], f"//HIST max=20 since={seen}")
                # other modes
                core.set_history_mode("none")
                n = len(sent)
                core._control(f"//IN 1 TREFF 7d 9 hist=8 last={now + 60} now={now}")
                self.assertEqual(len(sent), n)
                self.assertEqual(core.board["older"], 8)             # the bar offers them
                core.set_history_mode("10")
                core._control(f"//IN 1 TREFF 7d 9 hist=8 last={now + 60} now={now}")
                self.assertEqual(sent[-1], "//HIST max=10")
                self.assertFalse(core.set_history_mode("all"))
                self.assertEqual(core.snapshot()["history_mode"], "10")
                # an older TinyBox (no hist=) sends the history by itself: no request
                n = len(sent)
                core._control("//IN 2 DX 24h 3")
                self.assertEqual(len(sent), n)
                self.assertFalse(core.load_history(10))
        asyncio.run(scenario())


class EndToEndTests(unittest.TestCase):
    def test_radio_with_ui(self):
        async def scenario():
            dw = FakeDirewolf()
            port = await dw.start()
            app = chat_app()
            app.cfg.direwolf = dataclasses.replace(app.cfg.direwolf, agw_port=port,
                                                   reconnect_sec=1)
            adapter = tb_agw.AgwAdapter(app)
            app.agw = adapter
            from tinybox import notify
            notify.MailNotifier(app)
            t1 = asyncio.create_task(adapter.run())
            await asyncio.wait_for(adapter.connected.wait(), 5)
            term, tt = login(app, "OE3XYZ")
            type_lines(term, "C TREFF")
            with tempfile.TemporaryDirectory() as tmp:
                core = ClientCore(client_cfg(tmp, agw_port=port))
                core.set_symbol("/-")
                t2 = asyncio.create_task(core.run())
                await asyncio.wait_for(core.link.agw_up.wait(), 5)
                await core.connect()
                await until(lambda: core.boards, 10)
                self.assertEqual(core.caps, {"CHAT", "UI", "SYNC", "SYNC2", "SHORT", "Z", "IMG", "NUM", "HAVE", "PROF"})
                self.assertTrue(core.join(1))
                await until(lambda: core.board and "OE3GAS" in core.members)
                self.assertEqual(core.members, {"OE3XYZ": "", "OE3GAS": "/-"})
                type_lines(term, "Servus :+1")
                await until(lambda: any(m.get("text") == "Servus :+1" for m in core.messages))
                core.say("Hallo ~0A")
                await until(lambda: "OE3GAS: Hallo ~0A" in tt.buf)
                await until(lambda: not core.pending)
                seq = next(m["seq"] for m in core.messages if m.get("text") == "Servus :+1")
                core.react(seq, ":+1")
                await until(lambda: any(m.get("reactions") for m in core.messages))
                # every chat event came once as UI, never as I-frame to the client
                self.assertEqual(dw.chat_iframes, [])
                self.assertIn(("TBCHAT-1", "#2 OE3XYZ: Servus :+1"), dw.ui_sent)
                # C1: private mail -> UI frame to TBMAIL -> notice in the client
                self.assertEqual(core.mail["count"], 0)     # "No new messages." at login
                app.service.create(from_call="OE3XYZ", to_call="OE3GAS", type="P",
                                   subject="Test", body="x", origin="telnet")
                await until(lambda: core.mail and core.mail["count"] == 1)
                self.assertIn(("TBMAIL", "OE3GAS 1 new"), dw.ui_sent)
                snap = core.snapshot()
                self.assertTrue(snap["ui"])
                self.assertEqual(snap["mail"]["count"], 1)
                self.assertEqual(snap["symbols"]["OE3GAS"], "/-")
                core.leave()
                await until(lambda: core.board is None)
                core.disconnect()
                await until(lambda: core.state == "offline")
                t2.cancel()
            t1.cancel()
            dw.server.close()
        asyncio.run(scenario())

    def test_telnet_and_web_api(self):
        async def scenario():
            app = chat_app()
            server = await asyncio.start_server(
                lambda r, w: telnet.TelnetConnection(app, r, w).run(), "127.0.0.1", 0)
            port = server.sockets[0].getsockname()[1]
            term, tt = login(app, "OE3XYZ")
            type_lines(term, "C RUNDE")
            with tempfile.TemporaryDirectory() as tmp:
                cfg = client_cfg(tmp, link="telnet", telnet_port=port, web_host="127.0.0.1",
                                 web_port=0)
                core = ClientCore(cfg)
                web = await WebServer(core).start()
                wport = web.sockets[0].getsockname()[1]

                async def http(method, path, body=None, headers=True):
                    r, w = await asyncio.open_connection("127.0.0.1", wport)
                    data = json.dumps(body or {}).encode() if method == "POST" else b""
                    h = (f"{method} {path} HTTP/1.1\r\nHost: x\r\nConnection: close\r\n"
                         f"Content-Length: {len(data)}\r\n")
                    if headers and method == "POST":
                        h += "Content-Type: application/json\r\nX-TBClient: 1\r\n"
                    w.write(h.encode() + b"\r\n" + data)
                    raw = await r.read()
                    w.close()
                    head, _, payload = raw.partition(b"\r\n\r\n")
                    return int(head.split()[1]), payload

                self.assertEqual((await http("POST", "/api/connect", headers=False))[0], 403)
                self.assertEqual((await http("POST", "/api/connect"))[0], 200)
                await until(lambda: core.boards, 10)
                self.assertEqual(core.caps, {"CHAT", "SYNC", "SYNC2", "SHORT", "NUM", "HAVE", "PROF"})   # telnet: no UI, no Z
                await http("POST", "/api/join", {"board": 2})
                await until(lambda: core.board is not None)
                await http("POST", "/api/say", {"text": "per telnet ~01"})
                await until(lambda: "OE3GAS: per telnet ~01" in tt.buf)
                await until(lambda: any(m.get("text") == "per telnet ~01"
                                        for m in core.messages))
                status, body = await http("GET", "/api/state?since=-1")
                state = json.loads(body)
                self.assertEqual((status, state["board"]["name"]), (200, "RUNDE"))
                status, body = await http("GET", "/")
                self.assertIn(b"<title>TinyBox</title>", body)
                self.assertEqual((await http("GET", "/aprs/symbols-0.png"))[0], 200)
                self.assertEqual((await http("GET", "/../tbclient.conf"))[0], 404)
                core.disconnect()
                await until(lambda: core.state == "offline")
                web.close()
            server.close()
        asyncio.run(scenario())


class ForeignBbs:
    """CR43: an AGW client that plays a BBS which is no TinyBox."""

    def __init__(self, call: str, port: int) -> None:
        self.call, self.port, self.got = call, port, []

    async def run(self) -> None:
        r, w = await asyncio.open_connection("127.0.0.1", self.port)
        self.w = w
        w.write(H.pack(0, b"X", 0, self.call.encode(), b"", 0, 0))
        try:
            while True:
                _p, kind, _pid, cf, ct, n, _ = H.unpack(await r.readexactly(H.size))
                data = await r.readexactly(n) if n else b""
                kind, peer = kind.decode(), agwcodec.decode_call(cf)
                if kind == "C":
                    self._say(peer, b"[BPQ-6.0.24.1] OE3XBS-8\r#Stations heard\r//nonsense\r"
                                    b"OE3XBS:OE3XBS-8} BBS CHAT NODES\r")
                elif kind == "D":
                    self.got.append(data)
                    if data.strip() == b"N":
                        self._say(peer, b"Nodes: OE1XAR OE3XNR\r")
        except (asyncio.IncompleteReadError, ConnectionError):
            pass

    def _say(self, peer: str, data: bytes) -> None:
        self.w.write(H.pack(0, b"D", 0xF0, self.call.encode(), peer.encode(), len(data), 0) + data)


class FreeConnectTests(unittest.TestCase):
    """CR42 (Connect to any station), CR43 (terminal for a station that is no
    TinyBox), CR44 (logbook) and CR45 (channels)."""

    def setUp(self):
        self._old = core_mod.HANDSHAKE_FALLBACK_SEC
        core_mod.HANDSHAKE_FALLBACK_SEC = 0.3

    def tearDown(self):
        core_mod.HANDSHAKE_FALLBACK_SEC = self._old

    def test_foreign_bbs_terminal_and_states(self):
        async def scenario():
            dw = FakeDirewolf()
            port = await dw.start()
            bbs = ForeignBbs("OE3XBS-8", port)
            tb = asyncio.create_task(bbs.run())
            with tempfile.TemporaryDirectory() as tmp:
                core = ClientCore(client_cfg(tmp, agw_port=port))
                t = asyncio.create_task(core.run())
                await asyncio.wait_for(core.port.agw_up.wait(), 5)
                await until(lambda: any(c["calls"] == {"OE3XBS-8"} for c in dw.clients))
                # CR44: the frequency of the session is asked once
                self.assertTrue(core.snapshot()["freq_ask"])
                self.assertFalse(core.set_freq("abc"))
                self.assertTrue(core.set_freq("144,8"))
                self.assertEqual((core.freq, core.snapshot()["freq_ask"]), ("144.800", False))
                # bad targets are refused
                self.assertFalse(await core.connect("OE3XBS-99"))
                self.assertFalse(await core.connect("oe3gas"))           # own call
                self.assertFalse(await core.connect("OE3XYZ", ch=6))     # max. 5 channels
                # nobody answers: failed
                self.assertTrue(await core.connect("oe3nix-1", ch=1))
                ch1 = core.channels[1]
                await until(lambda: ch1.state == "offline" and ch1.ended)
                self.assertEqual((ch1.ended["kind"], ch1.target), ("failed", "OE3NIX-1"))
                # the foreign BBS: terminal, never a //CLIENT line
                self.assertTrue(await core.connect("OE3XBS-8", ch=1))
                await until(lambda: ch1.mode == "terminal")
                self.assertEqual(core.state, "offline")        # no chat channel
                self.assertEqual(core.chan.n, 0)
                self.assertFalse(any(b"//CLIENT" in d for d in bbs.got))
                texts = [x for _, k, x in ch1.term if k == "rx"]
                self.assertIn("#Stations heard", texts)          # not taken as a chat event
                self.assertIn("//nonsense", texts)               # nor as a control line
                self.assertTrue(core.send_raw("N", ch=1))
                await until(lambda: any(x == "Nodes: OE1XAR OE3XNR" for _, _, x in ch1.term))
                self.assertIn(b"N\r", bbs.got)
                self.assertFalse(await core.connect("OE3XBS-8", ch=2))   # the same station twice
                snap = core.snapshot(1)
                self.assertEqual(snap["home"], "OE3GAS-1")
                self.assertEqual(snap["channels"][0]["mode"], "terminal")
                self.assertIn("Nodes: OE1XAR OE3XNR", [x for _, _, x in snap["term"]])
                self.assertEqual(snap["recent"][:2], ["OE3XBS-8", "OE3NIX-1"])
                self.assertTrue(core.snapshot(0)["term"])        # the monitor heard frames
                # disconnect: "disconnecting" until Direwolf says it is down
                states = []
                orig = ch1._on_state
                ch1.link.on_state = lambda st, r: (states.append(st), orig(st, r))
                core.disconnect(1)
                await until(lambda: ch1.state == "offline")
                self.assertEqual(states, ["disconnecting", "offline"])
                self.assertEqual(ch1.ended["kind"], "user")
                # CR44: the logbook - the failed connect and the connection with bytes
                rows = core.logbook.rows()
                self.assertEqual([(r["call"], r["ended"]) for r in rows],
                                 [("OE3XBS-8", "user"), ("OE3NIX-1", "failed")])
                self.assertEqual(rows[0]["tx"], 2)                    # "N" CR
                self.assertGreater(rows[0]["rx"], 60)
                self.assertIsNone(rows[1]["rx"])
                self.assertEqual(len(core.logbook.rows(connected_only=True)), 1)
                self.assertEqual(rows[0]["freq"], "144.800")
                # the list survives a restart of the client, the frequency is asked again
                core2 = ClientCore(client_cfg(tmp, agw_port=port))
                self.assertEqual(core2.recent[:2], ["OE3XBS-8", "OE3NIX-1"])
                snap2 = core2.snapshot()
                self.assertEqual((snap2["freq_ask"], snap2["freq_last"]), (True, "144.800"))
                t.cancel()
            tb.cancel()
            dw.server.close()
        asyncio.run(scenario())

    def test_channels_tinybox_and_terminal(self):
        """CR45: TinyBox chat in one channel, a BBS terminal in another, a
        second TinyBox only as terminal; channels close only when offline."""
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
            bbs = ForeignBbs("OE3XBS-8", port)
            tb = asyncio.create_task(bbs.run())
            with tempfile.TemporaryDirectory() as tmp:
                core = ClientCore(client_cfg(tmp, agw_port=port, sync_on_login=False))
                t2 = asyncio.create_task(core.run())
                await asyncio.wait_for(core.port.agw_up.wait(), 5)
                await until(lambda: any(c["calls"] == {"OE3XBS-8"} for c in dw.clients))
                self.assertTrue(await core.connect("OE3XBS-8"))        # first free: 1
                self.assertTrue(await core.connect("OE3GAS-1"))        # next free: 2
                await until(lambda: core.boards, 10)
                self.assertEqual((core.chan.n, core.chan.mode), (2, "tinybox"))
                await until(lambda: core.channels[1].mode == "terminal")
                self.assertTrue(core.join(1))
                await until(lambda: core.board is not None)
                # both at once: a line in the BBS channel, the chat goes on
                self.assertTrue(core.send_raw("N", ch=1))
                await until(lambda: any(x == "Nodes: OE1XAR OE3XNR"
                                        for _, _, x in core.channels[1].term))
                core.say("parallel")
                await until(lambda: any(m.get("text") == "parallel" for m in core.messages))
                snap = core.snapshot(2)
                self.assertEqual([c["n"] for c in snap["channels"]], [1, 2])
                self.assertEqual(snap["chat_ch"], 2)
                self.assertTrue(snap["channels"][1]["chat"])
                self.assertGreater(snap["channels"][0]["act"], 0)
                self.assertFalse(core.close_channel(1))                 # still connected
                # the BBS goes; its channel stays with its lines until closed
                core.disconnect(1)
                await until(lambda: core.channels[1].state == "offline")
                self.assertEqual(core.state, "online")                 # chat untouched
                self.assertTrue(core.close_channel(1))
                self.assertEqual(list(core.channels), [2])
                core.disconnect()                                       # the chat channel
                await until(lambda: core.state == "offline")
                self.assertIsNone(core.board)
                t2.cancel()
            tb.cancel()
            t1.cancel()
            dw.server.close()
        asyncio.run(scenario())

    def test_incoming_connect_over_agw(self):
        """CR46: another station connects to us - a free channel takes it."""
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
                await until(lambda: any(c.incoming and c.state == "online"
                                        for c in a.channels.values()))
                ca = a.channels[1]
                self.assertEqual((ca.target, ca.mode), ("OE3TEC", "terminal"))
                self.assertEqual(a.snapshot()["focus"], {"n": 1, "seq": 1})   # CR75
                self.assertTrue(b.send_raw("Servus", ch=1))
                await until(lambda: any(x == "Servus" for _, k, x in ca.term if k == "rx"))
                b.disconnect(1)
                await until(lambda: ca.state == "offline")
                self.assertEqual(ca.ended["kind"], "remote")
                # CR75: a TinyBox connecting to us - no jump to its terminal
                a.settings["tinyboxes"] = ["OE3TEC"]
                self.assertTrue(await b.connect("OE3GAS", ch=1))
                await until(lambda: any(c.incoming and c.state == "online"
                                        for c in a.channels.values()))
                self.assertEqual(a.focus["seq"], 1)
                b.disconnect(1)
                await until(lambda: all(c.state == "offline" for c in a.channels.values()))
                for t in tasks:
                    t.cancel()
            dw.server.close()
        asyncio.run(scenario())

    def test_only_one_tinybox_in_client_mode(self):
        with tempfile.TemporaryDirectory() as tmp:
            core = ClientCore(client_cfg(tmp))
            a, b = core.open_channel(1), core.open_channel(2)
            a.state, a.mode = "online", "tinybox"
            core.chan = a
            self.assertFalse(core.can_attach(b))
            a.state = "offline"
            self.assertTrue(core.can_attach(b))

    def test_settings_per_target(self):
        with tempfile.TemporaryDirectory() as tmp:
            core = ClientCore(client_cfg(tmp))
            core.chan.target = "OE3GAS-1"
            core.tset["board"] = 2
            core.chan.target = "OE3XYZ-1"
            self.assertIsNone(core.tset.get("board"))         # another TinyBox, other boards
            core.tset["board"] = 5
            core.chan.target = "OE3GAS-1"
            self.assertEqual(core.tset["board"], 2)
            self.assertEqual(core.settings["targets"]["OE3XYZ-1"]["board"], 5)

    def test_disconnect_without_answer(self):
        async def scenario():
            with tempfile.TemporaryDirectory() as tmp:
                core = ClientCore(client_cfg(tmp))
                old = channels_mod.DISC_TIMEOUT_SEC
                channels_mod.DISC_TIMEOUT_SEC = 0.2
                try:
                    core.port.agw_up.set()
                    ch = core.channels[1]
                    ch.target = ch.link.target = "OE3GAS-1"
                    ch.link._set("online")
                    core.disconnect(1)                   # nobody answers ('d' never comes)
                    self.assertEqual(ch.state, "disconnecting")
                    await until(lambda: ch.state == "offline", 2)
                    self.assertEqual(ch.reason, "no answer to the disconnect")
                finally:
                    channels_mod.DISC_TIMEOUT_SEC = old
        asyncio.run(scenario())

    def test_monitor_lines(self):
        f = radio.decode(raw_frame("APRS", "OE3XYZ-9", 0x03, b"!4833.07N/01606.22E-x", ["OE1XAR"]))
        self.assertEqual(radio.describe(f), "fm OE3XYZ-9 to APRS via OE1XAR <UI>: "
                                            "!4833.07N/01606.22E-x")
        self.assertEqual(radio.frame_type(0x3F), "SABM+")
        self.assertEqual(radio.frame_type(0x41), "RR 2")
        self.assertEqual(radio.frame_type(0x46), "I 3,2")
        # modulo 128 (after SABME): two control bytes, then the PID
        f = radio.decode(raw_frame("OE3GAS", "OE1ABC", 0x02) + bytes([0x0A, 0xF0]) + b"Hallo")
        self.assertEqual(radio.describe(f, mod128=True), "fm OE1ABC to OE3GAS <I 1,5>: Hallo")
        # CR50: modulo 128 recognised without the SABME (our own is not always heard)
        self.assertTrue(radio.guess_mod128(f))
        f8 = radio.decode(raw_frame("OE3GAS", "OE1ABC", 0x00, b"Hallo"))
        self.assertFalse(radio.guess_mod128(f8))
        rr128 = radio.decode(raw_frame("OE3GAS", "OE1ABC", 0x01) + bytes([0x0B]))
        self.assertTrue(radio.guess_mod128(rr128))
        e = radio.monitor_entry(f, True)
        self.assertEqual((e["src"], e["dst"], e["typ"], e["text"], e["kind"]),
                         ("OE1ABC", "OE3GAS", "I 1,5", "Hallo", ""))
        ui = radio.decode(raw_frame("TBCHAT-1", "OE3GAS-1", 0x03, b"%Q 1 5 23"))
        self.assertEqual(radio.monitor_entry(ui)["kind"], "quality")
        ui = radio.decode(raw_frame("TBMAIL", "OE3GAS-1", 0x03, b"OE3TEC 2 new"))
        self.assertEqual(radio.monitor_entry(ui)["kind"], "mail")
        ui = radio.decode(raw_frame("BEACON", "OE3GAS-1", 0x03, b"TinyBox"))
        self.assertEqual(radio.monitor_entry(ui, tinyboxes=frozenset({"OE3GAS-1"}))["kind"],
                         "beacon")
        pr = radio.decode(raw_frame("OE3GAS", "OE3GAS-1", 0x00, b"//IN 1 TREFF"))
        self.assertEqual(radio.monitor_entry(pr)["kind"], "proto")


if __name__ == "__main__":
    unittest.main()


class EmoticonTests(unittest.TestCase):
    """CR28: emoticons <-> emojis in app.js, run with node (skipped without it)."""

    def run_js(self, cases):
        import shutil
        import subprocess
        node = shutil.which("node")
        if not node:
            self.skipTest("node not installed")
        root = Path(__file__).resolve().parent.parent
        out = subprocess.run([node, str(root / "tests" / "fixtures" / "emoticons.js"),
                              str(root / "tbclient" / "web" / "app.js"),
                              str(root / "tbclient" / "web" / "emoji.json"), json.dumps(cases)],
                             capture_output=True, text=True, encoding="utf-8", check=True)
        return json.loads(out.stdout)

    def test_both_directions(self):
        r = self.run_js([["in", "das funktioniert ;-)"], ["in", "Hallo!:-) und :) oder :-D"],
                         ["in", "QTH:Pinkafeld http://x.at/ :/"], ["in", "sehr nett!~0B"],
                         ["in", "xD ~~ ~0C"],
                         ["out", "sehr nett!\U0001F642"], ["out", "\U0001F60A \U0001F604 \U0001F60E \U0001F914 \U0001F622"],
                         ["out", "Hallo \U0001F44D"],
                         ["live", "Hallo ;-) "], ["live", "nett!:-),"], ["live", "QTH:P "], ["live", "http://"],
                         ["groups", ""]])
        self.assertEqual(r["in:das funktioniert ;-)"], "das funktioniert \U0001F609")       # nose
        self.assertEqual(r["in:Hallo!:-) und :) oder :-D"], "Hallo!\U0001F642 und \U0001F642 oder \U0001F604")
        self.assertEqual(r["in:QTH:Pinkafeld http://x.at/ :/"], "QTH:Pinkafeld http://x.at/ \U0001F615")
        self.assertEqual(r["in:sehr nett!~0B"], "sehr nett!\U0001F642")                     # old client
        self.assertEqual(r["in:xD ~~ ~0C"], "\U0001F602 ~ \U0001F914")
        self.assertEqual(r["out:sehr nett!\U0001F642"], "sehr nett! :-)")                    # space added
        self.assertEqual(r["out:\U0001F60A \U0001F604 \U0001F60E \U0001F914 \U0001F622"], ":-) :-D 8-) ~0C :'(")
        self.assertEqual(r["out:Hallo \U0001F44D"], "Hallo :+1")
        self.assertEqual(r["live:Hallo ;-) "], "Hallo \U0001F609 |9")                       # cursor after
        self.assertEqual(r["live:nett!:-),"], "nett!\U0001F642,|8")
        self.assertEqual(r["live:QTH:P "], "QTH:P |6")                                       # not a word
        self.assertEqual(r["live:http://"], "http://|7")
        self.assertTrue(r["groups"][0].startswith("Smileys (ASCII, cheapest)=\U0001F642"))
        self.assertNotIn("\U0001F642", r["groups"][1])                                       # not twice


class ImageTests(unittest.TestCase):
    """CR12: a picture goes up in one block, the chat line carries only the
    reference, a tap fetches it back."""

    def test_upload_and_fetch_over_radio(self):
        async def scenario():
            from prcore import chatimg
            dw = FakeDirewolf()
            port = await dw.start()
            app = chat_app()
            app.cfg.direwolf = dataclasses.replace(app.cfg.direwolf, agw_port=port,
                                                   reconnect_sec=1)
            adapter = tb_agw.AgwAdapter(app)
            app.agw = adapter
            t1 = asyncio.create_task(adapter.run())
            await asyncio.wait_for(adapter.connected.wait(), 5)
            term, tt = login(app, "OE3XYZ")
            type_lines(term, "C TREFF")
            webp = b"RIFF\x20\x00\x00\x00WEBPVP8 " + bytes(range(256)) * 5     # 1292 bytes
            with tempfile.TemporaryDirectory() as tmp:
                core = ClientCore(client_cfg(tmp, agw_port=port))
                t2 = asyncio.create_task(core.run())
                await asyncio.wait_for(core.link.agw_up.wait(), 5)
                await core.connect()
                await until(lambda: core.boards, 10)
                self.assertIn("IMG", core.caps)
                self.assertIsNone(core.send_image(webp, "BEHV6nWB2yk8pyo0", "", ""))  # no board
                core.join(1)
                await until(lambda: core.board and core.board.get("img") == 8192)
                h = core.send_image(webp, "BEHV6nWB2yk8pyo0", "vom Berg :-)", "")
                self.assertEqual(h, chatimg.image_hash(webp))
                await until(lambda: core.images.upload["state"] == "done", 15)
                line = f"~#{h}{chatimg.size_code(len(webp))}BEHV6nWB2yk8pyo0 vom Berg :-)"
                await until(lambda: any(m.get("text") == line for m in core.messages), 10)
                self.assertIn("OE3GAS: [Image 1.3 KB - TinyBox client only] vom Berg :-)", tt.buf)
                self.assertEqual(app.store.image_get(h), webp)
                snap = core.snapshot()
                self.assertEqual(snap["images"]["have"], [h])
                self.assertEqual(snap["board"]["img"], 8192)
                # forget the local copy, fetch it from the TinyBox
                core.images.store.path(h).unlink()
                self.assertTrue(core.fetch_image(h))
                await until(lambda: core.images.store.has(h), 15)
                self.assertEqual(core.images.store.get(h), webp)
                self.assertEqual(core.snapshot()["images"]["loading"], {})
                # an image the TinyBox does not have
                self.assertTrue(core.fetch_image("000000"))
                await until(lambda: core.images.loading.get("000000", {}).get("error"), 10)
                core.disconnect()
                await until(lambda: core.state == "offline")
                t2.cancel()
            t1.cancel()
            dw.server.close()
        asyncio.run(scenario())


class ImageJsTests(unittest.TestCase):
    """CR12: blurhash and the reference parser in app.js (node, skipped without it)."""

    def test_blurhash_and_reference(self):
        import shutil
        import subprocess
        node = shutil.which("node")
        if not node:
            self.skipTest("node not installed")
        root = Path(__file__).resolve().parent.parent
        out = subprocess.run([node, str(root / "tests" / "fixtures" / "images.js"),
                              str(root / "tbclient" / "web" / "app.js")],
                             capture_output=True, text=True, encoding="utf-8", check=True)
        r = json.loads(out.stdout)
        from prcore import chatimg
        self.assertEqual(len(r["bh"]), 16)                       # 3x2 components
        self.assertEqual(r["shape"], {"nx": 3, "ny": 2})
        self.assertEqual((r["len33"], r["len43"]), (22, 28))
        self.assertEqual(chatimg.blurhash_len(r["bh"][0]), 16)   # the TinyBox agrees
        left, right, bottom = r["left"], r["right"], r["bottom"]
        self.assertGreater(left[0], left[2] + 100)               # red on the left
        self.assertGreater(right[2], right[0] + 100)             # blue on the right
        self.assertLess(bottom[0], left[0] - 30)                 # darker at the bottom
        self.assertEqual(r["ref"], {"hash": "a1b2c3", "size": 5120, "bh": r["bh"],
                                    "caption": "vom Berg"})
        self.assertEqual(r["ref_nocap"]["caption"], "")
        self.assertEqual(r["ref_bad"], [None, None, None])
        # the same line parsed by the TinyBox
        line = "~#a1b2c350" + r["bh"] + " vom Berg"
        self.assertEqual(chatimg.parse_ref(line)[:3], ("a1b2c3", 5120, r["bh"]))
        self.assertEqual(chatimg.terminal_text(line),
                         "[Image 5.0 KB - TinyBox client only] vom Berg")


class ImageHoldTests(unittest.TestCase):
    """The bug of 12.10.2026: a line sent while the image bytes were going out
    landed in the byte stream, so the TinyBox counted it as image data and read
    the last real bytes as a chat line. Since 13.10.2026 the bytes go to
    Direwolf in one go, the chat line right behind them; from //IMGPUT until
    then nothing else may go on the link, afterwards Direwolf keeps the order."""

    def test_lines_wait_until_the_bytes_are_handed_over(self):
        async def scenario():
            from prcore import chatimg
            with tempfile.TemporaryDirectory() as tmp:
                core = ClientCore(client_cfg(tmp))
                sent: list = []
                core.link.send_line = lambda t: sent.append(t)
                core.link.send_bytes = lambda b: sent.append(b)

                async def outstanding():
                    return 0
                core.link.outstanding = outstanding
                core.state = "online"
                core.caps = {"IMG"}
                core.board = {"n": 1, "name": "Treff", "keep": "7d", "img": 8192}
                webp = b"RIFF\x20\x00\x00\x00WEBPVP8 " + bytes(range(256)) * 5
                h = core.send_image(webp, "BEHV6nWB2yk8pyo0", "vom Berg", "")
                await until(lambda: sent and sent[0] == f"//IMGPUT {h} {len(webp)}")
                # between //IMGPUT and //IMGGO: typed text and the gap detection
                # must wait - the TinyBox would take them as image data
                self.assertTrue(core.say("mitten drin"))
                core._send("//RESEND 1-2")
                self.assertEqual(core._hold, ["mitten drin", "//RESEND 1-2"])
                self.assertEqual(len(sent), 1)
                core._on_line(f"//IMGGO {h} 0")
                await until(lambda: len(sent) >= 4)
                # the bytes in one go, then the held lines (typed first) and the
                # chat line with the reference - all behind the bytes
                line = f"~#{h}{chatimg.size_code(len(webp))}BEHV6nWB2yk8pyo0 vom Berg"
                self.assertEqual(sent[1:], [webp, "mitten drin", "//RESEND 1-2", line])
                self.assertIsNone(core._hold)
                self.assertEqual(core.images.upload["state"], "sending")
                core._on_line(f"//IMGOK {h}")
                await until(lambda: core.images.upload["state"] == "done")
                self.assertEqual(core.images.upload["sent"], len(webp))
        asyncio.run(scenario())

    def test_known_picture_sends_only_the_chat_line(self):
        """Bug of 13.10.2026: the TinyBox answered //IMGPUT with //IMGOK at once
        (it had the picture), the client took that as done and never sent the
        chat line - the picture did not show up again."""
        async def scenario():
            from prcore import chatimg
            with tempfile.TemporaryDirectory() as tmp:
                core = ClientCore(client_cfg(tmp))
                sent: list = []
                core.link.send_line = lambda t: sent.append(t)
                core.link.send_bytes = lambda b: sent.append(b)
                core.state = "online"
                core.caps = {"IMG"}
                core.board = {"n": 1, "name": "Treff", "keep": "7d", "img": 8192}
                webp = b"RIFF\x20\x00\x00\x00WEBPVP8 " + bytes(range(256)) * 5
                h = core.send_image(webp, "BEHV6nWB2yk8pyo0", "nochmal", "")
                await until(lambda: len(sent) == 1)
                core._on_line(f"//IMGOK {h}")
                await until(lambda: core.images.upload["state"] == "done")
                line = f"~#{h}{chatimg.size_code(len(webp))}BEHV6nWB2yk8pyo0 nochmal"
                self.assertEqual(sent, [f"//IMGPUT {h} {len(webp)}", line])
                self.assertTrue(core.images.upload["known"])
                self.assertIsNone(core._hold)
        asyncio.run(scenario())

    def test_upload_resumes_at_the_offset(self):
        async def scenario():
            with tempfile.TemporaryDirectory() as tmp:
                core = ClientCore(client_cfg(tmp))
                sent: list = []
                core.link.send_line = lambda t: sent.append(t)
                core.link.send_bytes = lambda b: sent.append(b)
                core.state = "online"
                core.caps = {"IMG"}
                core.board = {"n": 1, "name": "Treff", "keep": "7d", "img": 8192}
                webp = b"RIFF\x20\x00\x00\x00WEBPVP8 " + bytes(range(256)) * 5
                h = core.send_image(webp, "BEHV6nWB2yk8pyo0", "", "")
                await until(lambda: len(sent) == 1)
                core._on_line(f"//IMGGO {h} 1000")                # the TinyBox has 1000 bytes
                await until(lambda: len(sent) >= 3)
                self.assertEqual(sent[1], webp[1000:])
                core._on_line("//ERR img bad_hash")
                await until(lambda: core.images.upload["state"] == "error")
                self.assertEqual(core.images.upload["error"], "damaged on the way, try again")
        asyncio.run(scenario())


class CommentReferenceTests(unittest.TestCase):
    """CR31: a comment refers to the event number, not to call + minute."""

    def test_reference_is_unique(self):
        import shutil
        import subprocess
        node = shutil.which("node")
        if not node:
            self.skipTest("node not installed")
        root = Path(__file__).resolve().parent.parent
        out = subprocess.run([node, str(root / "tests" / "fixtures" / "comments.js"),
                              str(root / "tbclient" / "web" / "app.js")],
                             capture_output=True, text=True, encoding="utf-8", check=True)
        r = json.loads(out.stdout)
        self.assertEqual(r["parse_new"], {"len": 5, "seq": 0x4F})      # 5 bytes on air
        self.assertEqual(r["parse_old"], {"len": 14, "call": "OE3TEC", "hhmm": "1402"})
        self.assertIsNone(r["parse_none"])
        self.assertEqual(r["strip"], "ja genau")
        self.assertEqual(r["prefix"], "~^4F ")
        self.assertEqual(r["prefix_none"], "")
        # two messages of the same station in the same minute: the number hits
        # the first one, the old call+minute form took the last (the bug)
        self.assertEqual(r["hit"], "erste frage")
        self.assertEqual(r["hit_second"], "zweite frage")
        self.assertEqual(r["old_hit"], "zweite frage")


class UploadNoticeTests(unittest.TestCase):
    """CR30: the others see that a picture is going up, with real progress from
    the frames heard on the channel."""

    def test_event_and_progress(self):
        from tbclient import proto
        from prcore import chatimg
        ev = proto.parse_event("#5A ^OE1ABC 50")
        self.assertEqual((ev.kind, ev.call, ev.ref), ("upload", "OE1ABC", 5120))
        self.assertIsNone(proto.parse_event("#5B ^OE1ABC zz"))
        with tempfile.TemporaryDirectory() as tmp:
            core = ClientCore(client_cfg(tmp))
            core.board = {"n": 1, "name": "TREFF", "keep": "7d", "img": 8192}
            core.unwrap.reset(0x59)
            core._event(ev)
            self.assertEqual(core.uploads["OE1ABC"]["size"], 5120)
            self.assertEqual(core.uploads["OE1ABC"]["got"], 0)
            # I-frames of that station to the TinyBox: counted, capped at the size
            f = radio.decode(raw_frame("OE3GAS-1", "OE1ABC", 0x00, b"x" * 200))
            core._on_frame(f)
            core._on_frame(f)
            self.assertEqual(core.uploads["OE1ABC"]["got"], 400)
            for _ in range(40):
                core._on_frame(f)
            self.assertEqual(core.uploads["OE1ABC"]["got"], 5120)       # never more
            # frames of someone else, or not to the TinyBox: not counted
            core.uploads["OE1ABC"]["got"] = 0
            core._on_frame(radio.decode(raw_frame("OE3GAS-1", "OE3XYZ", 0x00, b"y" * 50)))
            core._on_frame(radio.decode(raw_frame("OE3XYZ", "OE1ABC", 0x00, b"y" * 50)))
            core._on_frame(radio.decode(raw_frame("OE3GAS-1", "OE1ABC", 0x01)))     # RR
            self.assertEqual(core.uploads["OE1ABC"]["got"], 0)
            self.assertEqual(core.snapshot()["uploads"],
                             [{"call": "OE1ABC", "size": 5120, "at": core.uploads["OE1ABC"]["at"],
                               "got": 0}])
            # the picture arrives: the notice is gone
            line = f"~#a1b2c3{chatimg.size_code(5120)}BEHV6nWB2yk8pyo0"
            core._event(proto.Event(0x5B, "line", "OE1ABC", text=line))
            self.assertNotIn("OE1ABC", core.uploads)


class TargetParseTests(unittest.TestCase):
    """CR71: the connect field with digipeaters."""

    def test_parse(self):
        from tbclient.target import TargetError, label, parse
        self.assertEqual(parse("oe3xyz-1"), ("OE3XYZ-1", []))
        self.assertEqual(parse("OE3XYZ-1 v oe3xtc-5"), ("OE3XYZ-1", ["OE3XTC-5"]))
        self.assertEqual(parse(" OE3XYZ-1  VIA A1,B2  C3 "), ("OE3XYZ-1", ["A1", "B2", "C3"]))
        self.assertEqual(parse("OE3XYZ-1 V A1,,B2"), ("OE3XYZ-1", ["A1", "B2"]))
        self.assertEqual(label("OE3XYZ-1", ["A1", "B2"]), "OE3XYZ-1 via A1,B2")
        self.assertEqual(parse(label("OE3XYZ-1", ["A1"])), ("OE3XYZ-1", ["A1"]))
        for bad in ("", "OE3XYZ-16", "OE3XYZ-1 OE3XTC-5", "OE3XYZ-1 V", "OE3XYZ-1 V OE3XYZ-1",
                    "A V B,B", "A V " + ",".join(f"D{i}" for i in range(9)), "A V TOOLONG7"):
            with self.subTest(bad=bad), self.assertRaises(TargetError):
                parse(bad)
        with self.assertRaises(TargetError):
            parse("OE3XYZ V OE3GAS", mycall="OE3GAS")


class ConnectViaAgwTests(unittest.TestCase):
    """CR71: over Direwolf the connect with a path goes out as AGW 'v'."""

    def test_agw_v_frame(self):
        async def scenario():
            dw = FakeDirewolf()
            port = await dw.start()
            bbs = ForeignBbs("OE3XBS-8", port)
            tb = asyncio.create_task(bbs.run())
            with tempfile.TemporaryDirectory() as tmp:
                core = ClientCore(client_cfg(tmp, agw_port=port))
                t = asyncio.create_task(core.run())
                await asyncio.wait_for(core.port.agw_up.wait(), 5)
                await until(lambda: any(c["calls"] == {"OE3XBS-8"} for c in dw.clients))
                self.assertTrue(await core.connect("OE3XBS-8 V OE3XTC-5,OE3ABC", ch=1))
                await until(lambda: core.channels[1].state == "online")
                self.assertEqual(dw.via_connects, [("OE3XBS-8", ["OE3XTC-5", "OE3ABC"])])
                ch1 = core.channels[1]
                self.assertIn("*** connecting OE3XBS-8 via OE3XTC-5,OE3ABC",
                              [x for _, k, x in ch1.term if k == "sys"])
                core.disconnect(1)
                await until(lambda: ch1.state == "offline")
                # without a path: AGW 'C' as before
                self.assertTrue(await core.connect("OE3XBS-8", ch=1))
                await until(lambda: ch1.state == "online")
                self.assertEqual(len(dw.via_connects), 1)
                self.assertEqual(ch1.via, [])
                self.assertEqual(core.recent[:2], ["OE3XBS-8", "OE3XBS-8 via OE3XTC-5,OE3ABC"])
                core.disconnect(1)
                await until(lambda: ch1.state == "offline")
                t.cancel()
            tb.cancel()
            dw.server.close()
        asyncio.run(scenario())
