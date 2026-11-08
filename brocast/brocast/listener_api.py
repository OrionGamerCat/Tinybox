"""Listener JSON API on 127.0.0.1:7733 – the base for the web GUI (M3).

    GET    /api/v1/status
    GET    /                       web GUI (index.html, app.css, app.js)
    GET    /api/v1/categories[?station=CALL]
    GET    /api/v1/rubrics         all rubrics (for the subscription matrix)
    GET    /api/v1/rxlog[?limit=200&org=&id=&brocast=1]   receive log, newest first
    POST   /api/v1/dictionary/import  {"text": ...} or {"data_b64": ...}, "dry_run": bool
    POST   /api/v1/dictionary/install-received   install the dictionary received over the air
    POST   /api/v1/dictionary/broadcast          station: send the packed dictionary now
    GET    /api/v1/stations[?cat=KEY]
    GET    /api/v1/pages[?cat=&station=&unread=1&favorite=1&q=]
    GET    /api/v1/pages/{org}/{id}[?raw=1&peek=1]     (opening marks it read)
    POST   /api/v1/pages/{org}/{id}/read      {"read": true|false}
    POST   /api/v1/pages/{org}/{id}/favorite  {"favorite": true|false}
    DELETE /api/v1/pages/{org}/{id}
    GET    /api/v1/settings      PUT {"max_pages_total": 500, ...}
    GET    /api/v1/subscriptions PUT {"optout": [{"station": "*", "cat": "dx"}]}

Every write needs the header X-Brocast-Client: 1 (see webserver.py).
Page contents come from the air and are untrusted: the GUI must show them
as text only.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from . import dictimport
from .codec import BrocastError
from .listener import Listener, ListenerError, NotFound
from .station import NotFound as NotFoundStation
from .webserver import HttpError, JsonServer, Request

WEB_DIR = Path(__file__).resolve().parent / "web"
STATIC = {"/": WEB_DIR / "index.html", "/app.css": WEB_DIR / "app.css",
          "/app.js": WEB_DIR / "app.js",
          "/teletext.woff": WEB_DIR / "teletext.woff",      # Pixelschrift der Teletext-Ansicht
          "/brocast-logo.svg": WEB_DIR / "brocast-logo.svg"}


def _flag(req: Request, name: str) -> bool:
    return req.q(name, "") in ("1", "true", "yes")


class ListenerApi(JsonServer):
    name = "Listener-API"

    def __init__(self, listener: Listener, host: str, port: int,
                 status: Callable[[], dict[str, Any]] = dict,
                 dict_import: Callable[[Any, bool], dict[str, Any]] | None = None,
                 lan: bool = False, lan_names: tuple[str, ...] = ()):
        super().__init__(host, port, require_client_header=True, static=STATIC,
                         lan=lan, lan_names=lan_names)
        self.listener = listener
        self.status = status
        self.dict_import = dict_import
        self.dict_broadcast: Callable[[], dict[str, Any]] | None = None   # station only
        self.tx_status: Callable[[], dict[str, Any]] | None = None        # station only
        self.tx_action: Callable[[str, Any], dict[str, Any]] | None = None

    def route(self, req: Request) -> tuple[int, Any]:
        parts, method, body, li = req.parts, req.method, req.body, self.listener
        try:
            if parts == ["status"] and method == "GET":
                daemon = dict(self.status())
                if "pages" in daemon:                      # station: pages in the carousel
                    daemon["pages_station"] = daemon.pop("pages")
                return 200, {**daemon, **li.status()}
            if parts == ["tx"] and method == "GET":         # view "Sendung" (08.11.2026)
                return 200, self.tx_status() if self.tx_status else {"station": False}
            if len(parts) == 2 and parts[0] == "tx" and method == "POST" and self.tx_action:
                try:                                       # off {id} / restore {provider, key}
                    return 200, self.tx_action(parts[1], body)
                except NotFoundStation as exc:
                    raise HttpError(404, str(exc)) from None
                except BrocastError as exc:
                    return 400, {"ok": False, "message": str(exc), "error": str(exc)}
            if parts == ["categories"] and method == "GET":
                return 200, li.categories(station=req.q("station"))
            if parts == ["dictionary", "import"] and method == "POST" and self.dict_import:
                try:
                    return 200, self.dict_import(body, bool(isinstance(body, dict)
                                                            and body.get("dry_run")))
                except dictimport.ImportError_ as exc:
                    return 400, {"ok": False, "message": str(exc), "error": str(exc)}
            if parts == ["dictionary", "broadcast"] and method == "POST" and self.dict_broadcast:
                res = self.dict_broadcast()
                return (200 if res["ok"] else 400), {**res, "error": res["message"]}
            if parts == ["dictionary", "install-received"] and method == "POST":
                return 200, li.install_ready_dictionary()
            if parts == ["rxlog"] and method == "GET":
                try:
                    limit = int(req.q("limit", "200"))
                    page_id = int(req.q("id")) if req.q("id") else None
                except ValueError:
                    raise HttpError(400, "limit und id müssen Zahlen sein") from None
                return 200, li.rxlog(limit, (req.q("org") or "").upper() or None, page_id,
                                     brocast_only=_flag(req, "brocast"))
            if parts == ["rubrics"] and method == "GET":
                return 200, li.all_rubrics()
            if parts == ["stations"] and method == "GET":
                return 200, li.stations(cat=req.q("cat"))
            if parts == ["pages"] and method == "GET":
                return 200, li.list_pages(cat=req.q("cat"), station=req.q("station"),
                                          unread=_flag(req, "unread"),
                                          favorite=_flag(req, "favorite"), q=req.q("q"))
            if parts == ["settings"]:
                if method == "GET":
                    return 200, li.settings
                if method == "PUT":
                    return 200, li.set_settings(body)
            if parts == ["subscriptions"]:
                if method == "GET":
                    return 200, {"optout": li.optouts()}
                if method == "PUT":
                    if not isinstance(body, dict):
                        raise ListenerError("Objekt {\"optout\": [...]} erwartet")
                    return 200, {"optout": li.set_optouts(body.get("optout"))}
            if len(parts) in (3, 4) and parts[0] == "pages":
                org = parts[1].upper()
                try:
                    page_id = int(parts[2])
                except ValueError:
                    raise HttpError(404, "Seitennummer muss eine Zahl sein") from None
                if len(parts) == 3 and method == "GET":
                    return 200, li.page(org, page_id, raw=_flag(req, "raw"),
                                        mark_read=not _flag(req, "peek"))
                if len(parts) == 3 and method == "DELETE":
                    return 200, li.delete(org, page_id)
                if len(parts) == 4 and method == "POST" and isinstance(body, dict):
                    if parts[3] == "read":
                        return 200, li.set_read(org, page_id, body.get("read"))
                    if parts[3] == "favorite":
                        return 200, li.set_favorite(org, page_id, body.get("favorite"))
            if parts and parts[0] in ("pages", "settings", "subscriptions", "status", "tx",
                                      "categories", "stations", "rubrics", "rxlog",
                                      "dictionary"):
                raise HttpError(405, f"Methode {method} hier nicht erlaubt")
            raise HttpError(404, "unbekannter Pfad")
        except NotFound as exc:
            raise HttpError(404, str(exc)) from None
        except ListenerError as exc:
            raise HttpError(400, str(exc)) from None
