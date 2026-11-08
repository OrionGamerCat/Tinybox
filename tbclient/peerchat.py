"""Chat history between two TBClients (CR78): data/tbclient/peerchat.db.

One history per other station (full call with SSID). It is two streams, one
per direction - AX.25 keeps the order within a direction, but lines of both
sides may cross, so a single list could differ while nothing is missing.

Every stream is a hash chain: h(n) = sha1(h(n-1) + LF + text)[:8], h(0) = "0".
The number n and h(n) of the last line say exactly what a side has. A history
also has a generation (random); deleting gives a new one. Both sides compare
at the connect (peer.py):

    same generation, same numbers and hashes      -> nothing to do
    same generation, the other has a prefix of a  -> the missing tail goes out
    stream of mine (a line lost at a disconnect)     again (//HM)
    anything else                                 -> both delete

Kept: the last KEEP lines per direction (and the notes "chat history removed").
"""

from __future__ import annotations

import hashlib
import secrets
import sqlite3
import time
from pathlib import Path

KEEP = 100                      # lines per direction and station


def chain(prev: str, text: str) -> str:
    return hashlib.sha1(f"{prev}\n{text}".encode("utf-8")).hexdigest()[:8]


def new_gen() -> str:
    return secrets.token_hex(3)


class PeerChat:
    def __init__(self, path: str | Path) -> None:
        self.db = sqlite3.connect(str(path))
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS peers (
                peer TEXT PRIMARY KEY, gen TEXT NOT NULL,
                tx_n INTEGER NOT NULL DEFAULT 0, tx_h TEXT NOT NULL DEFAULT '0',
                rx_n INTEGER NOT NULL DEFAULT 0, rx_h TEXT NOT NULL DEFAULT '0');
            CREATE TABLE IF NOT EXISTS msgs (
                id INTEGER PRIMARY KEY AUTOINCREMENT, peer TEXT NOT NULL,
                dir TEXT NOT NULL,              -- tx | rx | note
                n INTEGER NOT NULL, text TEXT NOT NULL, t INTEGER NOT NULL,
                h TEXT NOT NULL);
            CREATE INDEX IF NOT EXISTS msgs_peer ON msgs (peer, dir, n);
        """)
        try:                                     # ok = acknowledged by AX.25 (tick, 08.11.2026)
            self.db.execute("ALTER TABLE msgs ADD COLUMN ok INTEGER NOT NULL DEFAULT 0")
        except sqlite3.OperationalError:
            pass                                 # there already
        self.db.commit()
        self.version = 0                         # changes with every write (GUI)

    # --- state -----------------------------------------------------------------------

    def state(self, peer: str) -> dict:
        row = self.db.execute("SELECT gen, tx_n, tx_h, rx_n, rx_h FROM peers WHERE peer = ?",
                              (peer,)).fetchone()
        if row is None:
            row = (new_gen(), 0, "0", 0, "0")
            self.db.execute("INSERT INTO peers (peer, gen) VALUES (?, ?)", (peer, row[0]))
            self.db.commit()
        return {"gen": row[0], "tx": (row[1], row[2]), "rx": (row[3], row[4])}

    def hist_line(self, peer: str) -> str:
        s = self.state(peer)
        return (f"//HIST g={s['gen']} m={s['tx'][0]}:{s['tx'][1]} "
                f"y={s['rx'][0]}:{s['rx'][1]}")

    def count(self, peer: str) -> int:
        return self.db.execute("SELECT COUNT(*) FROM msgs WHERE peer = ? AND dir != 'note'",
                               (peer,)).fetchone()[0]

    # --- writing ---------------------------------------------------------------------

    def add(self, peer: str, direction: str, text: str, t: int | None = None) -> int:
        """A line of the chat (tx = ours, rx = theirs). Returns its number."""
        s = self.state(peer)
        n, prev = s[direction]
        n += 1
        h = chain(prev, text)
        self.db.execute(f"UPDATE peers SET {direction}_n = ?, {direction}_h = ? WHERE peer = ?",
                        (n, h, peer))
        self.db.execute("INSERT INTO msgs (peer, dir, n, text, t, h) VALUES (?, ?, ?, ?, ?, ?)",
                        (peer, direction, n, text, int(t or time.time()), h))
        self.db.execute("DELETE FROM msgs WHERE peer = ? AND dir = ? AND n <= ?",
                        (peer, direction, n - KEEP))
        self.db.commit()
        self.version += 1
        return n

    def note(self, peer: str, text: str) -> None:
        self.db.execute("INSERT INTO msgs (peer, dir, n, text, t, h) VALUES (?, 'note', 0, ?, ?, '')",
                        (peer, text, int(time.time())))
        self.db.execute("DELETE FROM msgs WHERE peer = ? AND dir = 'note' AND id NOT IN "
                        "(SELECT id FROM msgs WHERE peer = ? AND dir = 'note' "
                        "ORDER BY id DESC LIMIT 5)", (peer, peer))
        self.db.commit()
        self.version += 1

    def clear(self, peer: str, gen: str) -> bool:
        """Delete the history; gen = the generation from now on. True = there was one."""
        had = self.count(peer) > 0
        self.state(peer)
        self.db.execute("DELETE FROM msgs WHERE peer = ?", (peer,))
        self.db.execute("UPDATE peers SET gen = ?, tx_n = 0, tx_h = '0', rx_n = 0, rx_h = '0' "
                        "WHERE peer = ?", (gen, peer))
        self.db.commit()
        self.version += 1
        return had

    # --- reading ---------------------------------------------------------------------

    def chain_at(self, peer: str, direction: str, n: int) -> str | None:
        """h(n) of a stream, None if line n is not (or no more) here."""
        if n == 0:
            return "0"
        row = self.db.execute("SELECT h FROM msgs WHERE peer = ? AND dir = ? AND n = ?",
                              (peer, direction, n)).fetchone()
        return row[0] if row else None

    def since(self, peer: str, direction: str, n: int, upto: int) -> list[tuple[int, int, str]]:
        """(n, t, text) of the lines n+1 .. upto."""
        return self.db.execute("SELECT n, t, text FROM msgs WHERE peer = ? AND dir = ? "
                               "AND n > ? AND n <= ? ORDER BY n", (peer, direction, n, upto)).fetchall()

    def delivered(self, peer: str, numbers: list[int]) -> None:
        """These sent lines are acknowledged (AX.25: nothing left to send)."""
        if not numbers:
            return
        self.db.executemany("UPDATE msgs SET ok = 1 WHERE peer = ? AND dir = 'tx' AND n = ?",
                            [(peer, n) for n in numbers])
        self.db.commit()
        self.version += 1

    def messages(self, peer: str, limit: int = KEEP) -> list[dict]:
        rows = self.db.execute("SELECT id, dir, n, text, t, ok FROM msgs WHERE peer = ? "
                               "ORDER BY t DESC, id DESC LIMIT ?", (peer, limit)).fetchall()
        return [{"id": i, "dir": d, "n": n, "text": x, "t": t, "ok": bool(ok)}
                for i, d, n, x, t, ok in reversed(rows)]
