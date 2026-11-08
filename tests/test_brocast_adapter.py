"""brocast adapter: bulletins -> brocastd ingest API (fake brocastd, no radio)."""

from __future__ import annotations

import asyncio
import json
import unittest

from tinybox.adapters import brocast
from tinybox.config import DEFAULT_RUBRICS, BrocastCfg, Rubric
from tinybox.store import Message
from tests.test_tinybox import make_app


def msg(**kw) -> Message:
    base = dict(id=12, msgid="x", type="B", status="N", to_call="DX", from_call="OE3XYZ",
                subject="3B8 Mauritius", body="Zeile 1\nZeile 2\n\nAbsatz 2", size=10,
                origin="radio", created="2026-10-02T18:30:00Z", read_at=None)
    base.update(kw)
    return Message(**base)


class MappingTests(unittest.TestCase):
    def setUp(self):
        self.app = make_app()
        self.app.cfg.brocast = BrocastCfg(publish=True)

    def test_basic_mapping(self):
        page = brocast.to_page(msg(), self.app)
        self.assertEqual(page["typ"], "text")
        self.assertEqual(page["ti"], "3B8 Mauritius")
        self.assertEqual(page["cat"], ["dx"])
        self.assertEqual(page["to"], "DX")
        self.assertEqual(page["src"], ["tinybox", "OE3XYZ"])
        self.assertEqual(page["exp"], 30 * 1440)
        self.assertEqual(page["blk"], [{"k": "para", "x": "Zeile 1\nZeile 2"},
                                       {"k": "para", "x": "Absatz 2"}])

    def test_long_subject(self):
        subject = "Sehr langer Betreff ueber die DXpedition nach Clipperton 2026"
        page = brocast.to_page(msg(subject=subject), self.app)
        self.assertEqual(len(page["ti"]), 40)
        self.assertTrue(page["ti"].endswith("…"))
        self.assertEqual(page["blk"][0], {"k": "heading", "x": subject})

    def test_rubrics(self):
        for dest, cat in (("ALL", "all"), ("WX", "wx"), ("KEPS", "keps"), ("FUCHS", "FUCHS")):
            with self.subTest(dest=dest):
                self.assertEqual(brocast.to_page(msg(to_call=dest), self.app)["cat"], [cat])
        self.app.cfg.brocast.rubrics = {**DEFAULT_RUBRICS, "FUCHS": "Fuchsjagd"}
        self.assertEqual(brocast.to_page(msg(to_call="FUCHS"), self.app)["cat"], ["Fuchsjagd"])

    def test_long_body_is_cut_with_hint(self):
        body = "\n\n".join(f"Absatz {i}: " + "x" * 300 for i in range(30))
        page = brocast.to_page(msg(body=body), self.app)
        text = "\n\n".join(b["x"] for b in page["blk"] if b["k"] == "para")
        self.assertLessEqual(len(text.encode()), 4096)
        self.assertEqual(page["blk"][-1]["k"], "note")
        self.assertIn("Mailbox OE3GAS-1: R 12", page["blk"][-1]["x"])

    def test_never_expires(self):
        self.app.cfg.mailbox.bulletin_expire_days = 0
        self.assertEqual(brocast.to_page(msg(), self.app)["exp"], brocast.FOREVER_MIN)

    def test_wanted(self):
        self.assertTrue(brocast.wanted(msg(), self.app))
        self.assertFalse(brocast.wanted(msg(type="P", to_call="OE1ABC"), self.app))
        self.app.cfg.brocast.destinations = ["WX"]
        self.assertFalse(brocast.wanted(msg(), self.app))
        self.assertTrue(brocast.wanted(msg(to_call="WX"), self.app))

    def test_tbnews_never_on_brocast(self):
        news = msg(to_call="TBNEWS", origin="sysop", subject="Client 2026.10.18")
        self.assertFalse(brocast.wanted(news, self.app))
        self.app.cfg.brocast.destinations = ["TBNEWS"]          # not even when listed
        self.assertFalse(brocast.wanted(news, self.app))

    def test_rubric_list_for_brocastd(self):
        self.assertEqual(brocast.rubric_list(self.app), [])          # no [rubrics]: free
        self.app.cfg.rubrics = [Rubric("WX", "Weather and warnings"), Rubric("FUCHS", "Fuchsjagd"),
                                Rubric("HUMOR", "not wanted", False)]
        self.assertEqual(brocast.rubric_list(self.app), [
            {"name": "ALL", "cat": "all", "desc": ""},                # ALL always, first
            {"name": "WX", "cat": "wx", "desc": "Weather and warnings"},
            {"name": "FUCHS", "cat": "FUCHS", "desc": "Fuchsjagd"},   # own rubric: as text
        ])
        self.app.cfg.rubrics.insert(0, Rubric("ALL", "To everybody"))
        self.assertEqual(brocast.rubric_list(self.app)[0]["desc"], "To everybody")


class FakeBrocastd:
    """Records requests like brocastd's ingest API would receive them."""

    def __init__(self):
        self.requests: list[tuple[str, str, object]] = []
        self.busy: list[dict] = []          # PUT /busy reports, kept apart from the pages
        self.event = asyncio.Event()
        self.reject_typ: str | None = None    # pages of this typ get HTTP 400 / an error

    async def start(self) -> int:
        self.server = await asyncio.start_server(self._client, "127.0.0.1", 0)
        return self.server.sockets[0].getsockname()[1]

    async def _client(self, reader, writer):
        head = await reader.readuntil(b"\r\n\r\n")
        lines = head.decode().split("\r\n")
        method, path, _ = lines[0].split(" ")
        length = next((int(l.split(":")[1]) for l in lines if l.lower().startswith("content-length")), 0)
        body = json.loads(await reader.readexactly(length)) if length else None
        if path.endswith("/busy"):
            self.busy.append(body)
        else:
            self.requests.append((method, path, body))
            self.event.set()
        status, payload = b"200 OK", {"id": 24, "subpages": 1, "withdrawn": [], "errors": {}}
        if self.reject_typ and isinstance(body, dict):
            if body.get("typ") == self.reject_typ:
                status, payload = b"400 Bad Request", {"error": "dat: Feld unbekannt"}
            for key, page in (body.get("pages") or {}).items():
                if page.get("typ") == self.reject_typ:
                    payload["errors"][key] = "dat: Feld unbekannt"
        data = json.dumps(payload).encode()
        writer.write(b"HTTP/1.1 " + status + b"\r\nContent-Length: " + str(len(data)).encode()
                     + b"\r\nConnection: close\r\n\r\n" + data)
        await writer.drain()
        writer.close()

    async def wait(self, n: int, timeout: float = 2.0) -> None:
        for _ in range(int(timeout / 0.02)):
            if len(self.requests) >= n:
                return
            await asyncio.sleep(0.02)

    async def close(self):
        self.server.close()


class PublisherTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.fake = FakeBrocastd()
        port = await self.fake.start()
        self.app = make_app()
        self.app.cfg.brocast = BrocastCfg(publish=True, ingest_port=port)
        self.svc = self.app.service
        self.svc.create(from_call="OE1ABC", to_call="ALL", type="B", subject="schon da",
                        body="alt", origin="telnet")
        self.task = await brocast.start(self.app)
        await self.fake.wait(1)

    async def asyncTearDown(self):
        self.task.cancel()
        await asyncio.gather(self.task, return_exceptions=True)
        await self.fake.close()

    def last(self):
        return self.fake.requests[-1]

    async def test_sync_at_start(self):
        method, path, body = self.fake.requests[0]
        self.assertEqual((method, path), ("PUT", "/api/v1/pages/tinybox"))
        self.assertEqual(list(body["pages"]), ["1"])
        self.assertEqual(body["pages"]["1"]["cat"], ["all"])
        self.assertEqual(body["rubrics"], [])                     # no [rubrics] configured

    async def test_sync_carries_the_rubric_list(self):
        self.app.cfg.rubrics = [Rubric("WX", "Weather")]
        await self.app.brocast.sync()
        body = self.last()[2]
        self.assertEqual([r["name"] for r in body["rubrics"]], ["ALL", "WX"])

    async def test_bulletin_lifecycle(self):
        msg_id = self.svc.create(from_call="OE3XYZ", to_call="DX", type="B", subject="3B8",
                                 body="QRV ab 5.10.", origin="radio")
        await self.fake.wait(2)
        method, path, body = self.last()
        self.assertEqual((method, path), ("PUT", f"/api/v1/pages/tinybox/{msg_id}"))
        self.assertEqual((body["ti"], body["cat"], body["src"]), ("3B8", ["dx"], ["tinybox", "OE3XYZ"]))
        self.svc.delete(msg_id, "OE3XYZ", sysop=False)
        await self.fake.wait(3)
        self.assertEqual(self.last()[:2], ("DELETE", f"/api/v1/pages/tinybox/{msg_id}"))

    async def test_private_mail_never_published(self):
        self.svc.create(from_call="OE3XYZ", to_call="OE1ABC", type="P", subject="privat",
                        body="geheim", origin="radio")
        await asyncio.sleep(0.2)
        self.assertEqual(len(self.fake.requests), 1)            # only the start sync

    async def test_edit_to_private_withdraws(self):
        msg_id = self.svc.create(from_call="OE3XYZ", to_call="DX", type="B", subject="x",
                                 body="y", origin="radio")
        await self.fake.wait(2)
        self.svc.edit(msg_id, "TYPE", "P", "OE3GAS", sysop=True)
        await self.fake.wait(3)
        self.assertEqual(self.last()[:2], ("DELETE", f"/api/v1/pages/tinybox/{msg_id}"))

    async def test_expired_bulletins_withdrawn(self):
        self.app.bus.publish("message.expired", ids=[1])
        await self.fake.wait(2)
        self.assertEqual(self.last()[:2], ("DELETE", "/api/v1/pages/tinybox/1"))


class DeliveredPageTests(unittest.IsolatedAsyncioTestCase):
    """Bulletins with a ready page ("Brocast:" in the inbox)."""

    asyncSetUp, asyncTearDown = PublisherTests.asyncSetUp, PublisherTests.asyncTearDown
    last = PublisherTests.last

    def create_wx(self) -> int:
        return self.svc.create(from_call="OE3GAS", to_call="WX", type="B", subject="Wetter 18:00",
                               body="Temperatur 21,3 °C", origin="inbox", sysop=True,
                               brocast='{"typ":"wx","dat":{"temp":21.3}}')

    async def test_page_is_sent(self):
        msg_id = self.create_wx()
        await self.fake.wait(2)
        method, path, body = self.last()
        self.assertEqual((method, path), ("PUT", f"/api/v1/pages/tinybox/{msg_id}"))
        self.assertEqual((body["typ"], body["dat"], body["ti"]), ("wx", {"temp": 21.3}, "Wetter 18:00"))

    async def test_rejected_page_falls_back_to_text(self):
        self.fake.reject_typ = "wx"
        msg_id = self.create_wx()
        await self.fake.wait(3)
        self.assertEqual(self.fake.requests[1][2]["typ"], "wx")          # tried first
        method, path, body = self.fake.requests[2]
        self.assertEqual((method, path, body["typ"]), ("PUT", f"/api/v1/pages/tinybox/{msg_id}", "text"))
        self.assertEqual(body["blk"], [{"k": "para", "x": "Temperatur 21,3 °C"}])

    async def test_rejected_page_in_full_sync_falls_back_to_text(self):
        msg_id = self.create_wx()
        await self.fake.wait(2)
        self.fake.reject_typ = "wx"
        await self.app.brocast.sync()
        await self.fake.wait(4)
        method, path, body = self.last()
        self.assertEqual((method, path, body["typ"]), ("PUT", f"/api/v1/pages/tinybox/{msg_id}", "text"))


async def wait_offline(app, timeout: float = 10.0) -> None:
    """A refused connect to localhost takes ~2 s on Windows (SYN retries), not ms."""
    for _ in range(int(timeout / 0.05)):
        if not app.brocast.online:
            return
        await asyncio.sleep(0.05)


class CatchUpTests(unittest.IsolatedAsyncioTestCase):
    async def test_bulletins_arrive_when_brocastd_starts_later(self):
        brocast.RETRY_SEC, saved = 0.2, brocast.RETRY_SEC
        fake = FakeBrocastd()
        port = await fake.start()
        await fake.close()                           # brocastd not running yet
        app = make_app()
        app.cfg.brocast = BrocastCfg(publish=True, ingest_port=port)
        task = await brocast.start(app)
        try:
            app.service.create(from_call="OE3XYZ", to_call="WX", type="B", subject="x",
                               body="y", origin="inbox")
            await wait_offline(app)
            self.assertFalse(app.brocast.online)
            fake.server = await asyncio.start_server(fake._client, "127.0.0.1", port)
            await fake.wait(1, timeout=10)           # next retry syncs everything
            method, path, body = fake.requests[0]
            self.assertEqual((method, path), ("PUT", "/api/v1/pages/tinybox"))
            self.assertEqual(len(body["pages"]), 1)
        finally:
            brocast.RETRY_SEC = saved
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
            await fake.close()


class UnreachableTests(unittest.IsolatedAsyncioTestCase):
    async def test_brocastd_down_does_not_break_mailbox(self):
        app = make_app()
        app.cfg.brocast = BrocastCfg(publish=True, ingest_port=1)     # nothing listens
        task = await brocast.start(app)
        try:
            msg_id = app.service.create(from_call="OE3XYZ", to_call="DX", type="B",
                                        subject="x", body="y", origin="radio")
            self.assertIsNotNone(app.store.get(msg_id))
            await wait_offline(app)
            self.assertFalse(app.brocast.online)
        finally:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)


if __name__ == "__main__":
    unittest.main()


class AirDaysTests(unittest.TestCase):
    """born (Bulletin-Datum für das Alter im Karussell) und air_days (Funkdauer)."""

    def setUp(self):
        self.app = make_app()
        self.app.cfg.brocast = BrocastCfg(publish=True)

    def test_born_is_the_creation_time(self):
        page = brocast.to_page(msg(created="2026-10-05T12:00:00Z"), self.app)
        self.assertEqual(page["born"], 1791201600)     # 2026-10-05 12:00 UTC

    def test_no_born_for_unknown_date(self):
        self.assertNotIn("born", brocast.to_page(msg(created="kaputt"), self.app))

    def test_delivered_page_gets_born(self):
        page = brocast.to_page(msg(brocast=json.dumps({"typ": "wx", "dat": {}})), self.app)
        self.assertIn("born", page)

    def test_air_days_off_by_default(self):
        self.assertTrue(brocast.on_air(msg(), self.app, now=1791201600 + 400 * 86400))

    def test_air_days_limits_the_time_on_air(self):
        self.app.cfg.brocast.air_days = 7
        born = 1791201600
        m = msg(created="2026-10-05T12:00:00Z")
        self.assertTrue(brocast.on_air(m, self.app, now=born + 6 * 86400))
        self.assertFalse(brocast.on_air(m, self.app, now=born + 8 * 86400))

    def test_old_bulletin_is_not_wanted(self):
        self.app.cfg.brocast.air_days = 1
        self.assertFalse(brocast.wanted(msg(created="2020-01-01T00:00:00Z"), self.app))

    def test_exp_at_most_air_days(self):
        self.app.cfg.brocast.air_days = 7
        self.assertEqual(brocast.to_page(msg(), self.app)["exp"], 7 * 1440)
        self.app.cfg.brocast.air_days = 60          # Mailbox-Frist (30 Tage) ist kürzer
        self.assertEqual(brocast.to_page(msg(), self.app)["exp"], 30 * 1440)


class _Sess:
    def __init__(self, call, origin, closed=False):
        self.call, self.origin, self.closed = call, origin, closed


class _Fwd:
    def __init__(self):
        self.radio_busy: set[str] = set()


class BusyTests(unittest.IsolatedAsyncioTestCase):
    """brocast steps back for real traffic: the TinyBox reports 0/1/2 (08.11.2026)."""

    def setUp(self):
        self.app = make_app()

    def publisher(self, port=1):
        self.app.cfg.brocast = BrocastCfg(publish=True, ingest_port=port)
        return brocast.BrocastPublisher(self.app)

    async def test_free(self):
        self.assertEqual(self.publisher().busy_level(), (0, ""))

    async def test_radio_session_is_level_1(self):
        self.app.registry.add(_Sess("OE1ABC", "radio"))
        self.app.registry.add(_Sess("OE3TEL", "telnet"))
        self.app.registry.add(_Sess("OE9OLD", "radio", closed=True))
        self.assertEqual(self.publisher().busy_level(), (1, "verbunden: OE1ABC"))

    async def test_radio_forward_is_level_2(self):
        self.app.registry.add(_Sess("OE1ABC", "radio"))
        self.app.forward = _Fwd()
        self.app.forward.radio_busy.add("OE5XBL")
        self.assertEqual(self.publisher().busy_level(), (2, "Forward OE5XBL"))

    async def until(self, cond, timeout=2.0):
        for _ in range(int(timeout / 0.02)):
            if cond():
                return
            await asyncio.sleep(0.02)

    async def test_loop_reports_changes(self):
        fake = FakeBrocastd()
        port = await fake.start()
        pub = self.publisher(port)
        old = brocast.BUSY_CHECK_SEC
        brocast.BUSY_CHECK_SEC = 0.02
        task = asyncio.create_task(pub.busy_loop())
        try:
            await self.until(lambda: len(fake.busy) >= 1)
            self.app.registry.add(_Sess("OE1ABC", "radio"))
            await self.until(lambda: len(fake.busy) >= 2)
            await asyncio.sleep(0.1)
        finally:
            task.cancel()
            brocast.BUSY_CHECK_SEC = old
            await asyncio.gather(task, return_exceptions=True)
            await fake.close()
        self.assertEqual([b["level"] for b in fake.busy], [0, 1])
        self.assertEqual(fake.busy[1]["why"], "verbunden: OE1ABC")
        self.assertEqual(len(fake.busy), 2)                    # unchanged level: no repeat before 30 s
