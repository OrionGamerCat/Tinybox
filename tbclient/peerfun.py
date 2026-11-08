"""TBClient to TBClient, the extras (CR78 stage 8): ping, speed test, chess.

Ping        //PING <token>  ->  //PONG <token>        round trip, last 5 kept
Speed test  //ST <n> go + n bytes  ->  //STR <n> <ms>  then  //ST <n> back + n bytes
            The receiver measures from the //ST line to the last byte (the first
            frame is in flight already: a little optimistic, the same both ways).
            One button runs both directions; ST_BYTES each way.
Chess       //CHESS NEW <w|b>      the sender plays white (w) or black (b)
            //CHESS M <uci>        a move, e2e4 / e7e8q (promotion)
            //CHESS RESIGN
            The rules are checked in the web GUI (both sides run the same code);
            here only whose turn it is. The game is kept in the settings per
            station, so it goes on after a restart or the next connect.

All three: only lines starting with //, nothing in the chat history except
the chess notes ("new game", "resigned").
"""

from __future__ import annotations

import os
import re
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .peer import Peer

ST_BYTES = 2048
ST_MAX = 8192
UCI_RE = re.compile(r"^[a-h][1-8][a-h][1-8][qrbn]?$")


class PeerFun:
    def __init__(self, peer: "Peer") -> None:
        self.peer = peer
        self.pings: list[float] = []
        self._ping: tuple[str, float] | None = None
        self.st: dict | None = None            # speed test: {"state", "out", "in", "at"}

    @property
    def ch(self):
        return self.peer.ch

    @property
    def core(self):
        return self.peer.ch.core

    # --- ping -----------------------------------------------------------------------

    def ping(self) -> bool:
        if self.ch.state != "online" or "FUN" not in self.peer.caps:
            return False
        token = os.urandom(3).hex()
        self._ping = (token, time.monotonic())
        self.peer._send(f"//PING {token}")
        self.core._touch()
        return True

    def _pong(self, token: str) -> None:
        if self._ping and self._ping[0] == token:
            self.pings = (self.pings + [round(time.monotonic() - self._ping[1], 3)])[-5:]
            self._ping = None
            self.core._touch()

    # --- speed test -----------------------------------------------------------------

    def speedtest(self) -> bool:
        if self.ch.state != "online" or "FUN" not in self.peer.caps:
            return False
        if self.st and self.st["state"] == "running" and time.time() - self.st["at"] < 600:
            return False
        self.st = {"state": "running", "out": None, "in": None, "at": time.time(), "n": ST_BYTES}
        self._send_block(ST_BYTES, "go")
        self.core._touch()
        return True

    def _send_block(self, n: int, how: str) -> None:
        self.peer._send(f"//ST {n} {how}")                 # line and bytes together
        self.ch.link.send_bytes(os.urandom(n))

    def _block(self, n: int, how: str) -> None:
        t0 = time.monotonic()

        def done(_data: bytes) -> None:
            ms = max(1, int((time.monotonic() - t0) * 1000))
            if how == "go":                   # their test: tell them, send ours back
                self.peer._send(f"//STR {n} {ms}")
                self._send_block(n, "back")
            elif self.st:                     # the way back of our own test
                self.st["in"] = round(n * 1000 / ms)
                self._finish()
            self.core._touch()
        self.ch.link.splitter.expect(n, done)

    def _result(self, n: int, ms: int) -> None:
        if self.st and self.st["state"] == "running":
            self.st["out"] = round(n * 1000 / max(1, ms))
            self._finish()

    def _finish(self) -> None:
        if self.st and self.st["out"] is not None and self.st["in"] is not None:
            self.st["state"] = "done"
            self.ch.term_line("sys", f"*** speed test: to {self.ch.target} {self.st['out']} B/s, "
                                     f"from {self.ch.target} {self.st['in']} B/s")

    # --- chess ----------------------------------------------------------------------

    @property
    def game(self) -> dict | None:
        return self.core.settings.get("chess", {}).get(self.peer.call)

    def _save(self, game: dict | None) -> None:
        games = self.core.settings.setdefault("chess", {})
        if game is None:
            games.pop(self.peer.call, None)
        else:
            games[self.peer.call] = game
        self.core._save_settings()
        self.core._touch()

    def _mine_white(self) -> bool:
        g = self.game
        return bool(g) and g["white"] == "me"

    def _my_turn(self) -> bool:
        g = self.game
        return bool(g) and not g.get("result") and \
            (len(g["moves"]) % 2 == 0) == (g["white"] == "me")

    def _note(self, text: str) -> None:
        if self.core.peerchat is not None:
            self.core.peerchat.note(self.peer.call, text)

    def chess(self, act: str, arg: str = "") -> bool:
        if self.ch.state != "online" or "FUN" not in self.peer.caps:
            return False
        if act == "new":
            white = arg != "b"
            self._save({"white": "me" if white else "them", "moves": [], "result": "",
                        "at": int(time.time())})
            self.peer._send(f"//CHESS NEW {'w' if white else 'b'}")
            self._note(f"♟ new chess game - you play {'white' if white else 'black'}")
            return True
        g = self.game
        if g is None:
            return False
        if act == "move" and UCI_RE.match(arg) and self._my_turn():
            g["moves"].append(arg)
            self._save(g)
            self.peer._send(f"//CHESS M {arg}")
            return True
        if act == "resign" and not g.get("result"):
            g["result"] = "you resigned"
            self._save(g)
            self.peer._send("//CHESS RESIGN")
            self._note("♟ you resigned")
            return True
        if act == "end" and arg in ("mate", "stalemate"):     # the GUI saw it on the board
            g["result"] = arg
            self._save(g)
            return True
        if act == "close":
            self._save(None)
            return True
        return False

    def _on_chess(self, rest: str) -> None:
        p = rest.split()
        if not p:
            return
        word = p[0].upper()
        if word == "NEW" and len(p) > 1 and p[1] in ("w", "b"):
            they_white = p[1] == "w"
            self._save({"white": "them" if they_white else "me", "moves": [], "result": "",
                        "at": int(time.time())})
            self._note(f"♟ {self.ch.target} started a chess game - you play "
                       f"{'black' if they_white else 'white'}")
        elif word == "M" and len(p) > 1 and UCI_RE.match(p[1]):
            g = self.game
            if g and not g.get("result") and not self._my_turn():
                g["moves"].append(p[1])
                self._save(g)
        elif word == "RESIGN":
            g = self.game
            if g and not g.get("result"):
                g["result"] = "they resigned"
                self._save(g)
                self._note(f"♟ {self.ch.target} resigned - you win")

    # --- lines ----------------------------------------------------------------------

    def take(self, word: str, rest: str) -> bool:
        p = rest.split()
        if word == "PING" and p:
            self.peer._send(f"//PONG {p[0][:12]}")
        elif word == "PONG" and p:
            self._pong(p[0])
        elif word == "ST" and len(p) == 2 and p[0].isdigit() and p[1] in ("go", "back") \
                and 0 < int(p[0]) <= ST_MAX:
            self._block(int(p[0]), p[1])
        elif word == "STR" and len(p) == 2 and p[0].isdigit() and p[1].isdigit():
            self._result(int(p[0]), int(p[1]))
        elif word == "CHESS":
            self._on_chess(rest)
        else:
            return False
        return True

    def summary(self) -> dict:
        g = self.game
        return {"pings": self.pings, "pinging": self._ping is not None, "st": self.st,
                "chess": None if g is None else {**g, "my_turn": self._my_turn()}}
