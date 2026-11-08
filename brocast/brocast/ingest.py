"""Ingest API: content providers (TinyBox first) describe pages as JSON.

    PUT    /api/v1/pages/{provider}/{key}   create or update (idempotent)
    DELETE /api/v1/pages/{provider}/{key}   withdraw
    PUT    /api/v1/pages/{provider}         full sync {"pages": {key: page},
                                            "rubrics": [{name, cat, desc}]} (optional:
                                            the provider's rubric list -> index page)
    GET    /api/v1/rubrics                  rubrics the providers declared
    GET    /api/v1/pages/{provider}/{key}   status of one page
    GET    /api/v1/pages[?provider=x]       list
    POST   /api/v1/validate                 dry run
    GET    /api/v1/dictionary               allowed names
    GET    /api/v1/status                   station status

Security: see webserver.py (loopback, Host check, JSON only, optional token).
"""

from __future__ import annotations

from typing import Any, Callable

from .codec import BrocastError
from .splitter import TooLargeError
from .station import NotFound, Station
from .webserver import PREFIX, HttpError, JsonServer, Request

__all__ = ["IngestServer", "PREFIX"]


class IngestServer(JsonServer):
    name = "Ingest-API"

    def __init__(self, station: Station, host: str, port: int, token: str = "",
                 status: Callable[[], dict[str, Any]] = dict):
        super().__init__(host, port, token)
        self.station = station
        self.status = status

    def route(self, req: Request) -> tuple[int, Any]:
        parts, method, body, st = req.parts, req.method, req.body, self.station
        try:
            if parts == ["status"] and method == "GET":
                return 200, self.status()
            if parts == ["dictionary"] and method == "GET":
                return 200, self._dictionary()
            if parts == ["validate"] and method == "POST":
                return 200, st.validate(body)
            if parts == ["pages"] and method == "GET":
                return 200, st.list(req.q("provider"))
            if len(parts) == 2 and parts[0] == "pages" and method == "PUT":
                if not isinstance(body, dict):
                    raise BrocastError("Objekt {\"pages\": {...}} erwartet")
                return 200, st.sync(parts[1], body.get("pages"), body.get("rubrics"))
            if parts == ["rubrics"] and method == "GET":
                return 200, st.rubrics()
            if len(parts) == 3 and parts[0] == "pages":
                provider, key = parts[1], parts[2]
                if method == "PUT":
                    return 200, st.put(provider, key, body)
                if method == "DELETE":
                    st.store.unblock(provider, key)    # gone at the source: no need to hold it off
                    return 200, st.delete(provider, key)
                if method == "GET":
                    return 200, st.get(provider, key)
            if parts and parts[0] in ("pages", "status", "dictionary", "validate", "rubrics"):
                raise HttpError(405, f"Methode {method} hier nicht erlaubt")
            raise HttpError(404, "unbekannter Pfad")
        except NotFound as exc:
            raise HttpError(404, str(exc)) from None
        except TooLargeError as exc:
            raise HttpError(413, str(exc)) from None
        except BrocastError as exc:
            raise HttpError(400, str(exc)) from None

    def _dictionary(self) -> dict[str, Any]:
        d = self.station.codec.d
        return {
            "dictionary": d.name, "version": d.version, "hash": d.hash4.hex(),
            "envelope": [e.name for e in d.envelope.by_num.values()],
            "blocks": [e.name for e in d.blocks.by_num.values()],
            "enums": {name: [e.name for e in t.by_num.values() if not e.spec.get("reserved")]
                      for name, t in d.enums.items()},
            "types": {name: {e.name: {k: v for k, v in e.spec.items() if k != "name"}
                             for e in t.by_num.values()} for name, t in d.types.items()},
        }
