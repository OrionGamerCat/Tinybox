"""Web GUI tests: API and the security checks."""

from __future__ import annotations

import asyncio
import dataclasses
import json
import tempfile
import time
import unittest
from pathlib import Path

from tinybox.adapters import web
from tests.test_tinybox import login as radio_login, make_app
from tinybox import linkq


async def request(port, method, path, *, host=None, cookie=None, csrf=None,
                  body=None, origin=None, read_all=True):
    reader, writer = await asyncio.open_connection("127.0.0.1", port)
    data = json.dumps(body).encode() if body is not None else b""
    lines = [f"{method} {path} HTTP/1.1", f"Host: {host or f'127.0.0.1:{port}'}",
             f"Content-Length: {len(data)}"]
    if cookie:
        lines.append(f"Cookie: tb_session={cookie}")
    if csrf:
        lines.append(f"X-CSRF-Token: {csrf}")
    if origin:
        lines.append(f"Origin: {origin}")
    writer.write(("\r\n".join(lines) + "\r\n\r\n").encode() + data)
    await writer.drain()
    if not read_all:
        return reader, writer
    raw = await asyncio.wait_for(reader.read(), 5)
    writer.close()
    head, _, payload = raw.partition(b"\r\n\r\n")
    head_lines = head.decode("latin-1").split("\r\n")
    status = int(head_lines[0].split()[1])
    headers = {k.lower(): v.strip() for k, v in
               (l.split(":", 1) for l in head_lines[1:] if ":" in l)}
    return status, headers, payload


class WebTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.app = make_app()
        self.app.cfg.storage = dataclasses.replace(self.app.cfg.storage, data_dir=Path(self.tmp.name))
        self.app.cfg.web = dataclasses.replace(self.app.cfg.web, port=0)
        self.app.stop_event = asyncio.Event()

    def tearDown(self):
        self.tmp.cleanup()

    def run_async(self, coro_fn):
        async def wrapper():
            server = await web.start(self.app)
            try:
                return await coro_fn(server)
            finally:
                server.close()
                await server.server.wait_closed()
        return asyncio.run(wrapper())

    async def login(self, server):
        status, headers, _ = await request(server.port, "GET", f"/login?token={server.token}")
        self.assertEqual(status, 303)
        cookie = headers["set-cookie"].split(";")[0].split("=", 1)[1]
        self.assertIn("HttpOnly", headers["set-cookie"])
        self.assertIn("SameSite=Strict", headers["set-cookie"])
        _, _, payload = await request(server.port, "GET", "/api/session", cookie=cookie)
        return cookie, json.loads(payload)["csrf"]

    def test_token_is_persistent(self):
        t1 = self.run_async(lambda s: asyncio.sleep(0, s.token))
        t2 = self.run_async(lambda s: asyncio.sleep(0, s.token))
        self.assertEqual(t1, t2)
        self.assertGreaterEqual(len(t1), 32)

    def test_status_names_the_radio_interface(self):
        """Header: 'Direwolf connected via AGW' / 'via KISS' (PLANUNG.md 15)."""
        async def scenario(s):
            cookie, _ = await self.login(s)
            _, _, payload = await request(s.port, "GET", "/api/status", cookie=cookie)
            return json.loads(payload)

        st = self.run_async(scenario)
        self.assertEqual(st["interface"], "agw")
        app_js = (Path(__file__).resolve().parent.parent / "tinybox/web/app.js").read_text(
            encoding="utf-8")
        self.assertIn('" via " + st.interface.toUpperCase()', app_js)
        self.assertIn('kiss ? "KISS \\u00b7 own AX.25 link"', app_js)

    def test_security_checks(self):
        async def scenario(s):
            results = {}
            results["no_login"] = (await request(s.port, "GET", "/api/status"))[0]
            results["root_redirect"] = (await request(s.port, "GET", "/"))[0]
            results["bad_token"] = (await request(s.port, "GET", "/login?token=wrong"))[0]
            results["rebinding"] = (await request(s.port, "GET", "/api/status",
                                                  host=f"evil.example:{s.port}"))[0]
            cookie, csrf = await self.login(s)
            results["status"] = (await request(s.port, "GET", "/api/status", cookie=cookie))[0]
            results["post_no_csrf"] = (await request(s.port, "POST", "/api/messages", cookie=cookie,
                                                     body={"to": "ALL"}))[0]
            results["post_bad_origin"] = (await request(
                s.port, "POST", "/api/messages", cookie=cookie, csrf=csrf,
                origin="http://evil.example", body={"to": "ALL"}))[0]
            st, hdrs, _ = await request(s.port, "GET", "/app.js")
            results["static"] = st
            results["csp"] = hdrs.get("content-security-policy", "")
            results["xfo"] = hdrs.get("x-frame-options")
            return results

        r = self.run_async(scenario)
        self.assertEqual(r["no_login"], 401)
        self.assertEqual(r["root_redirect"], 303)
        self.assertEqual(r["bad_token"], 403)
        self.assertEqual(r["rebinding"], 421)
        self.assertEqual(r["status"], 200)
        self.assertEqual(r["post_no_csrf"], 403)
        self.assertEqual(r["post_bad_origin"], 403)
        self.assertEqual(r["static"], 200)
        self.assertIn("script-src 'self'", r["csp"])
        self.assertIn("frame-ancestors 'none'", r["csp"])
        self.assertEqual(r["xfo"], "DENY")

    def test_message_workflow(self):
        async def scenario(s):
            cookie, csrf = await self.login(s)
            post = lambda path, body: request(s.port, "POST", path, cookie=cookie, csrf=csrf,
                                              body=body, origin=f"http://127.0.0.1:{s.port}")
            get = lambda path: request(s.port, "GET", path, cookie=cookie)
            out = {}
            st, _, p = await post("/api/messages", {"type": "B", "to": "all", "subject": "Net",
                                                    "body": "<script>alert(1)</script>\r\nline 2"})
            out["create"] = (st, json.loads(p))
            out["bad_call"] = await post("/api/messages", {"type": "P", "to": "NOCALL",
                                                           "subject": "x", "body": "x"})
            st, _, p = await get("/api/messages")
            out["list"] = json.loads(p)
            st, _, p = await get("/api/messages/1")
            out["read"] = json.loads(p)
            st, _, p = await post("/api/messages/1/edit", {"field": "SUBJ", "value": "Net tonight"})
            out["edit"] = json.loads(p)
            out["kill"] = (await post("/api/messages/1/kill", {}))[0]
            out["gone"] = (await get("/api/messages/1"))[0]
            st, _, p = await get("/api/config")
            out["config"] = json.loads(p)
            out["shutdown"] = (await post("/api/shutdown", {}))[0]
            await asyncio.sleep(0.5)
            out["stopped"] = self.app.stop_event.is_set()
            return out

        o = self.run_async(scenario)
        self.assertEqual(o["create"], (200, {"id": 1}))
        self.assertEqual(o["bad_call"][0], 400)
        self.assertEqual(json.loads(o["bad_call"][2])["error"], "invalid_call")
        self.assertEqual(o["list"][0]["to"], "ALL")
        self.assertNotIn("body", o["list"][0])
        self.assertEqual(o["read"]["body"], "<script>alert(1)</script>\nline 2")
        self.assertEqual((o["read"]["origin"], o["read"]["from"]), ("sysop", "OE3GAS"))
        self.assertEqual(o["edit"]["subject"], "Net tonight")
        self.assertEqual(o["kill"], 200)
        self.assertEqual(o["gone"], 400)
        self.assertEqual(o["config"]["station"]["mailbox_call"], "OE3GAS-1")
        self.assertEqual(o["shutdown"], 200)
        self.assertTrue(o["stopped"])

    def test_message_with_at_address(self):
        """The compose form takes 'TEST @ WW' (and '$BID') like SB/SP at the terminal."""
        async def scenario(s):
            cookie, csrf = await self.login(s)
            post = lambda path, body: request(s.port, "POST", path, cookie=cookie, csrf=csrf,
                                              body=body, origin=f"http://127.0.0.1:{s.port}")
            get = lambda path: request(s.port, "GET", path, cookie=cookie)
            out = {}
            st, _, p = await post("/api/messages", {"type": "B", "to": "test @ ww $X1_OE3GAS",
                                                    "subject": "Fwd", "body": "x"})
            out["create"] = st
            st, _, p = await get("/api/messages/" + str(json.loads(p)["id"]))
            out["read"] = json.loads(p)
            st, _, p = await post("/api/messages", {"type": "B", "to": "TEST @ W#W",
                                                    "subject": "x", "body": "x"})
            out["bad"] = (st, json.loads(p)["error"])
            return out

        o = self.run_async(scenario)
        self.assertEqual(o["create"], 200)
        self.assertEqual((o["read"]["to"], o["read"]["at"], o["read"]["bid"]),
                         ("TEST", "WW", "X1_OE3GAS"))
        self.assertEqual(o["bad"], (400, "invalid_address"))

    def test_restart_rubrics_and_logins_survive(self):
        """Dashboard: Restart button (checks tinybox.conf), rubrics list; a login
        survives a restart of the web server."""
        from tinybox.config import Rubric
        self.app.cfg.rubrics = [Rubric("WX", "Weather"), Rubric("HUMOR", "", False)]
        self.app.service.create(from_call="OE3TEC", to_call="WX", type="B", subject="Rain",
                                body="x", origin="telnet")
        self.app.service.create(from_call="OE3GAS", to_call="SWAP", type="B", subject="Rig",
                                body="x", origin="sysop", sysop=True)   # the sysop is free
        box = {}

        async def first(s):
            box["cookie"], box["csrf"] = await self.login(s)
            st, _, p = await request(s.port, "GET", "/api/rubrics", cookie=box["cookie"])
            return json.loads(p)

        rows = self.run_async(first)
        by = {r["name"]: r for r in rows}
        self.assertEqual([r["name"] for r in rows], ["ALL", "WX", "HUMOR", "TBNEWS", "SWAP"])
        self.assertEqual((by["WX"]["status"], by["WX"]["count"], by["WX"]["description"]),
                         ("accepted", 1, "Weather"))
        self.assertEqual(by["HUMOR"]["status"], "refused")
        self.assertEqual(by["TBNEWS"]["status"], "system")
        self.assertEqual((by["SWAP"]["status"], by["SWAP"]["count"]), ("unlisted", 1))

        async def second(s):          # a new web server (= after a restart)
            post = lambda body: request(s.port, "POST", "/api/shutdown", cookie=box["cookie"],
                                        csrf=box["csrf"], body=body,
                                        origin=f"http://127.0.0.1:{s.port}")
            out = {"status": (await request(s.port, "GET", "/api/status",
                                            cookie=box["cookie"]))[0]}
            with tempfile.TemporaryDirectory() as tmp:
                bad = Path(tmp) / "tinybox.conf"
                bad.write_text("[station]\nmailbox_call = !!\n", encoding="utf-8")
                self.app.config_path = str(bad)
                st, _, p = await post({"delay": 0, "restart": True})
                out["bad"] = (st, json.loads(p).get("detail", json.loads(p).get("error")))
            out["not_stopped"] = not self.app.stop_event.is_set()
            self.app.config_path = str(Path(__file__).resolve().parent.parent / "tinybox.conf.example")
            out["ok"] = (await post({"delay": 0, "restart": True}))[0]
            await asyncio.sleep(0.5)
            out["restart"] = self.app.stop_event.is_set() and self.app.restart
            return out

        o = self.run_async(second)
        self.assertEqual(o["status"], 200)                  # still logged in
        self.assertEqual(o["bad"][0], 400)
        self.assertIn("not restarted", o["bad"][1])
        self.assertTrue(o["not_stopped"])
        self.assertEqual(o["ok"], 200)
        self.assertTrue(o["restart"])

    def test_feed_delivers_events(self):
        async def scenario(s):
            cookie, _ = await self.login(s)
            reader, writer = await request(s.port, "GET", "/api/feed", cookie=cookie, read_all=False)
            await asyncio.sleep(0.1)
            self.app.service.create(from_call="OE1ABC", to_call="ALL", type="B",
                                    subject="s", body="b", origin="radio")
            data = b""
            while b"message.created" not in data:
                data += await asyncio.wait_for(reader.read(4096), 5)
            writer.close()
            return data

        data = self.run_async(scenario)
        self.assertIn(b"text/event-stream", data)
        self.assertIn(b'"name": "message.created"', data)


    def test_sessions_with_link_quality(self):
        """Users list carries the bars, the detail endpoint the whole calculation."""
        sess, _ = radio_login(self.app, "OE3TEC-1")
        self.app.registry.add(sess)
        q = linkq.LinkQuality()
        base = {k: 0 for k in linkq.FIELDS_INT} | {"srt": 0.0, "t1v": 0.0, "age": 0.0}
        now = time.monotonic()                   # evaluate() measures the window from now
        q.add(base | {"state": 3}, now=now - 100.0)
        q.add(base | {"state": 3, "i_new": 48, "i_retry": 2, "i_rx": 50, "rej_tx": 3, "retry_rx": 1,
                      "bytes_new": 4100, "bytes_retry": 120, "srt": 1.38, "age": 100.0}, now=now)
        self.app.service.links["OE3TEC-1"] = q

        async def scenario(s):
            cookie, _ = await self.login(s)
            get = lambda path: request(s.port, "GET", path, cookie=cookie)
            _, _, p = await get("/api/sessions")
            st_detail, _, d = await get("/api/sessions/OE3TEC-1/linkq")
            st_missing, _, _ = await get("/api/sessions/OE9ZZZ/linkq")
            return json.loads(p), st_detail, json.loads(d), st_missing

        rows, st_detail, detail, st_missing = self.run_async(scenario)
        row = next(r for r in rows if r["call"] == "OE3TEC-1")
        self.assertEqual(row["quality"]["bars"], 4)                      # incoming 8 % -> 4 bars
        self.assertEqual(row["quality"]["worst"], {"dir": "incoming", "loss": 8.0})
        self.assertEqual(st_detail, 200)
        self.assertEqual(detail["result"]["outgoing"]["loss"], 4.0)
        self.assertEqual(detail["result"]["incoming"]["lost"], 4)
        self.assertEqual(detail["counters"]["i_rx"], 50)
        self.assertEqual(detail["counters_window"]["rej_tx"], 3)
        self.assertEqual(detail["window"]["steps"][0], 5.0)
        self.assertEqual(st_missing, 404)


if __name__ == "__main__":
    unittest.main()
