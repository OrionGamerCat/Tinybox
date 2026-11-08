"""SQLite storage for brocastd. Only this module talks SQL (always with parameters).

station side:  pages (one row per provider page) + frames (encoded subpages)
listener side: received (raw pages as heard; M2 adds read/unread etc.)

Schreiben (PLANUNG 11, Punkt 9 – eMMC am NanoPi):
- WAL-Journal und synchronous=NORMAL: ein Commit kostet kein fsync mehr.
- Echte Änderungen (Seiten, Einstellungen, Bedienung) werden sofort committet.
- Flüchtiges, das bei jedem Funk-Frame anfällt (rxlog, gehörte Stationen,
  Sendezeitplan, last_seen wiederholter Seiten), läuft über _volatile(): es ist
  sofort lesbar (dieselbe Verbindung), wird aber erst mit flush() – vom Daemon
  alle flush_sec Sekunden und beim Beenden – oder mit der nächsten echten
  Änderung geschrieben. Ein Stromausfall kostet höchstens diese Spanne.
"""

from __future__ import annotations

import sqlite3
import threading
from dataclasses import dataclass
from pathlib import Path

SCHEMA_VERSION = 4          # 2: pages.hdr (Frame-Format je Seite); 3: lpages.wire_*;
                            # 4: pages.rev_t (Alter der Revision fuer aging)

SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS pages (
    pid           INTEGER PRIMARY KEY AUTOINCREMENT,
    provider      TEXT NOT NULL,
    pkey          TEXT NOT NULL,
    id            INTEGER NOT NULL UNIQUE,     -- page number on air, never reused
    rev           INTEGER NOT NULL,
    t             INTEGER NOT NULL,            -- Unix time of last confirmation
    content       TEXT NOT NULL,               -- provider JSON (named fields)
    content_hash  TEXT NOT NULL,
    exp_min       INTEGER,                     -- effective validity in minutes
    pri           INTEGER NOT NULL DEFAULT 0,
    state         TEXT NOT NULL DEFAULT 'active' CHECK (state IN ('active', 'withdrawn')),
    withdraw_left INTEGER NOT NULL DEFAULT 0,
    tx_count      INTEGER NOT NULL DEFAULT 0,  -- sends of the current revision
    last_tx       INTEGER,
    next_tx       INTEGER NOT NULL,
    hdr           INTEGER NOT NULL DEFAULT 16, -- header byte of this page's frames
    rev_t         INTEGER NOT NULL DEFAULT 0,  -- Unix time the content was born (aging)
    UNIQUE (provider, pkey)
);
CREATE TABLE IF NOT EXISTS blocked (          -- vom Sysop aus der Sendung genommen (08.11.2026)
    provider      TEXT NOT NULL,
    pkey          TEXT NOT NULL,
    content_hash  TEXT NOT NULL,               -- gilt fuer diesen Inhalt; neuer Inhalt = wieder senden
    id            INTEGER,
    title         TEXT NOT NULL DEFAULT '',
    t             INTEGER NOT NULL,
    PRIMARY KEY (provider, pkey)
);
CREATE TABLE IF NOT EXISTS frames (
    pid  INTEGER NOT NULL REFERENCES pages(pid) ON DELETE CASCADE,
    n    INTEGER NOT NULL,                     -- subpage number, 1..m
    data BLOB NOT NULL,                        -- encoded CBOR page
    PRIMARY KEY (pid, n)
);
CREATE TABLE IF NOT EXISTS received (
    org         TEXT NOT NULL,
    id          INTEGER NOT NULL,
    sub         INTEGER NOT NULL DEFAULT 1,
    sub_total   INTEGER NOT NULL DEFAULT 1,
    rev         INTEGER NOT NULL,
    t           INTEGER NOT NULL,
    typ         INTEGER,
    data        BLOB NOT NULL,
    heard_from  TEXT NOT NULL,                 -- AX.25 source of the frame
    received_at INTEGER NOT NULL,
    PRIMARY KEY (org, id, sub)
);
CREATE TABLE IF NOT EXISTS lpages (               -- listener: one row per page
    org         TEXT NOT NULL,
    id          INTEGER NOT NULL,
    rev         INTEGER NOT NULL,
    t           INTEGER NOT NULL,
    typ         TEXT,
    ti          TEXT NOT NULL DEFAULT '',
    cats        TEXT NOT NULL DEFAULT '[]',      -- JSON: names / own texts
    cat_key     TEXT NOT NULL,                   -- primary rubric (for limits)
    pri         INTEGER NOT NULL DEFAULT 0,
    alert       INTEGER NOT NULL DEFAULT 0,
    exp_min     INTEGER,
    sub_total   INTEGER NOT NULL DEFAULT 1,
    wire_frames INTEGER NOT NULL DEFAULT 0,       -- Frames, die die Seite auf Funk brauchte
    wire_bytes  INTEGER NOT NULL DEFAULT 0,       -- Bytes auf Funk (Format 2: alle Fragmente)
    status      TEXT NOT NULL DEFAULT 'unread' CHECK (status IN ('unread', 'read')),
    updated     INTEGER NOT NULL DEFAULT 0,      -- new revision of a read page
    favorite    INTEGER NOT NULL DEFAULT 0,
    deleted_rev INTEGER,                         -- set: hidden until a newer rev
    first_seen  INTEGER NOT NULL,
    last_seen   INTEGER NOT NULL,
    search      TEXT NOT NULL DEFAULT '',
    PRIMARY KEY (org, id)
);
CREATE TABLE IF NOT EXISTS stations (
    call        TEXT PRIMARY KEY,
    first_heard INTEGER NOT NULL,
    last_heard  INTEGER NOT NULL,
    frames      INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS optout (              -- '*' = all
    station TEXT NOT NULL,
    cat     TEXT NOT NULL,
    PRIMARY KEY (station, cat)
);
CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS rubrics (              -- station: rubrics declared by providers
    provider TEXT NOT NULL,
    pos      INTEGER NOT NULL,                   -- order as the provider sent them
    name     TEXT NOT NULL,                      -- the provider's name (e.g. bulletin dest)
    cat      TEXT NOT NULL,                      -- rubric as pages carry it (dict name / own)
    descr    TEXT NOT NULL DEFAULT '',
    PRIMARY KEY (provider, pos)
);
CREATE TABLE IF NOT EXISTS station_rubrics (      -- listener: rubrics a station announced
    station TEXT NOT NULL,                       -- (its index page, typ index)
    pos     INTEGER NOT NULL,
    cat     TEXT NOT NULL,                       -- rubric key (dict name or x:own)
    name    TEXT NOT NULL,                       -- original spelling of an own rubric
    descr   TEXT NOT NULL DEFAULT '',
    rev     INTEGER NOT NULL DEFAULT 0,          -- revision of the index page
    seen    INTEGER NOT NULL DEFAULT 0,          -- last time the index page was heard
    PRIMARY KEY (station, pos)
);
CREATE TABLE IF NOT EXISTS rxlog (                -- every frame heard (and sent)
    n          INTEGER PRIMARY KEY AUTOINCREMENT,
    ts         INTEGER NOT NULL,
    heard_from TEXT NOT NULL,
    dest       TEXT NOT NULL DEFAULT '',
    org        TEXT,
    id         INTEGER,
    sub        INTEGER,
    sub_total  INTEGER,
    rev        INTEGER,
    ti         TEXT NOT NULL DEFAULT '',
    result     TEXT NOT NULL,
    bytes      INTEGER NOT NULL DEFAULT 0,
    own        INTEGER NOT NULL DEFAULT 0
);
"""
RXLOG_KEEP = 5000

LPAGE_FIELDS = ("org", "id", "rev", "t", "typ", "ti", "cats", "cat_key", "pri", "alert",
                "exp_min", "sub_total", "wire_frames", "wire_bytes", "status", "updated",
                "favorite", "deleted_rev", "first_seen", "last_seen", "search")


@dataclass
class PageRow:
    pid: int
    provider: str
    pkey: str
    id: int
    rev: int
    t: int
    content: str
    content_hash: str
    exp_min: int | None
    pri: int
    state: str
    withdraw_left: int
    tx_count: int
    last_tx: int | None
    next_tx: int
    hdr: int = 16               # Header-Byte der Frames (frame.header(); 16 = Format 1)
    rev_t: int = 0              # Geburt des Inhalts (Lieferant "born" oder neue Revision);
                                # davon haengt aging ab, nicht von t (= letzte Bestaetigung)


class Store:
    def __init__(self, path: Path | str):
        self.path = str(path)
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.path, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA foreign_keys = ON")
        if self.path != ":memory:":
            self.db.execute("PRAGMA journal_mode = WAL")
            self.db.execute("PRAGMA synchronous = NORMAL")
        self.lock = threading.Lock()
        with self.db:
            self.db.executescript(SCHEMA)
            self._migrate()
            self.db.execute("INSERT OR REPLACE INTO meta VALUES ('schema', ?)",
                            (str(SCHEMA_VERSION),))

    def _migrate(self) -> None:
        """Ältere Datenbanken nachziehen (neue Spalten; Daten bleiben erhalten)."""
        cols = {r["name"] for r in self.db.execute("PRAGMA table_info(pages)")}
        if "hdr" not in cols:                    # Schema 1 -> 2 (Frame-Format je Seite)
            self.db.execute("ALTER TABLE pages ADD COLUMN hdr INTEGER NOT NULL DEFAULT 16")
        if "rev_t" not in cols:                  # Schema 3 -> 4 (Alter der Revision)
            self.db.execute("ALTER TABLE pages ADD COLUMN rev_t INTEGER NOT NULL DEFAULT 0")
        # unbekanntes Alter (alte DB, frueher Bug: t wurde stuendlich erneuert): jetzt
        self.db.execute("UPDATE pages SET rev_t = t WHERE rev_t = 0")
        lcols = {r["name"] for r in self.db.execute("PRAGMA table_info(lpages)")}
        for name in ("wire_frames", "wire_bytes"):   # Schema 2 -> 3 (echte Funkgröße)
            if name not in lcols:
                self.db.execute(f"ALTER TABLE lpages ADD COLUMN {name} "
                                "INTEGER NOT NULL DEFAULT 0")

    def close(self) -> None:
        self.flush()
        self.db.close()

    # -- deferred writes ------------------------------------------------------

    def _volatile(self, sql: str, params: tuple = ()) -> int:
        """Run a write without commit (see module doc). Returns the rowcount."""
        with self.lock:
            return self.db.execute(sql, params).rowcount

    def pending(self) -> bool:
        """True if there are writes not yet on disk."""
        return self.db.in_transaction

    def flush(self) -> bool:
        """Commit deferred writes. Returns True if there was something to write."""
        with self.lock:
            if not self.db.in_transaction:
                return False
            self.db.commit()
            return True

    # -- ids ----------------------------------------------------------------

    def next_auto_id(self, start: int) -> int:
        """Next free page number >= start. Numbers are never handed out twice."""
        with self.lock, self.db:
            row = self.db.execute("SELECT value FROM meta WHERE key='next_id'").fetchone()
            nxt = max(int(row["value"]) if row else start, start)
            while self.db.execute("SELECT 1 FROM pages WHERE id=?", (nxt,)).fetchone():
                nxt += 1
            self.db.execute("INSERT OR REPLACE INTO meta VALUES ('next_id', ?)", (str(nxt + 1),))
            return nxt

    def id_in_use(self, page_id: int) -> bool:
        return self.db.execute("SELECT 1 FROM pages WHERE id=?", (page_id,)).fetchone() is not None

    # -- station pages ------------------------------------------------------

    def get_page(self, provider: str, pkey: str) -> PageRow | None:
        row = self.db.execute("SELECT * FROM pages WHERE provider=? AND pkey=?",
                              (provider, pkey)).fetchone()
        return PageRow(**dict(row)) if row else None

    def get_page_by_id(self, page_id: int) -> PageRow | None:
        row = self.db.execute("SELECT * FROM pages WHERE id=?", (page_id,)).fetchone()
        return PageRow(**dict(row)) if row else None

    # -- pages the sysop took off the air -------------------------------------

    def block(self, provider: str, pkey: str, content_hash: str, page_id: int, title: str,
              now: int) -> None:
        self.db.execute("INSERT OR REPLACE INTO blocked VALUES (?, ?, ?, ?, ?, ?)",
                        (provider, pkey, content_hash, page_id, title, now))

    def unblock(self, provider: str, pkey: str) -> bool:
        return self.db.execute("DELETE FROM blocked WHERE provider=? AND pkey=?",
                               (provider, pkey)).rowcount > 0

    def blocked_hash(self, provider: str, pkey: str) -> str | None:
        row = self.db.execute("SELECT content_hash FROM blocked WHERE provider=? AND pkey=?",
                              (provider, pkey)).fetchone()
        return row["content_hash"] if row else None

    def list_blocked(self) -> list[dict]:
        return [dict(r) for r in self.db.execute("SELECT * FROM blocked ORDER BY t DESC")]

    def get_page_by_pid(self, pid: int) -> PageRow | None:
        row = self.db.execute("SELECT * FROM pages WHERE pid=?", (pid,)).fetchone()
        return PageRow(**dict(row)) if row else None

    def list_pages(self, provider: str | None = None) -> list[PageRow]:
        if provider is None:
            rows = self.db.execute("SELECT * FROM pages ORDER BY id").fetchall()
        else:
            rows = self.db.execute("SELECT * FROM pages WHERE provider=? ORDER BY id",
                                   (provider,)).fetchall()
        return [PageRow(**dict(r)) for r in rows]

    def save_page(self, row: PageRow, frames: list[bytes]) -> int:
        """Insert (pid == 0) or update a page together with its frames."""
        fields = ("provider", "pkey", "id", "rev", "t", "content", "content_hash", "exp_min",
                  "pri", "state", "withdraw_left", "tx_count", "last_tx", "next_tx", "hdr",
                  "rev_t")
        values = tuple(getattr(row, f) for f in fields)
        with self.lock, self.db:
            if row.pid:
                self.db.execute(
                    f"UPDATE pages SET {', '.join(f + '=?' for f in fields)} WHERE pid=?",
                    values + (row.pid,))
                pid = row.pid
            else:
                cur = self.db.execute(
                    f"INSERT INTO pages ({', '.join(fields)}) "
                    f"VALUES ({', '.join('?' for _ in fields)})", values)
                pid = cur.lastrowid
            self.db.execute("DELETE FROM frames WHERE pid=?", (pid,))
            self.db.executemany("INSERT INTO frames VALUES (?, ?, ?)",
                                [(pid, n, data) for n, data in enumerate(frames, start=1)])
        return pid

    def frames(self, pid: int) -> list[bytes]:
        return [r["data"] for r in self.db.execute(
            "SELECT data FROM frames WHERE pid=? ORDER BY n", (pid,))]

    def mark_sent(self, pid: int, now: int, next_tx: int, withdraw_left: int | None = None) -> None:
        """Sendezeitplan: flüchtig, nach einem Stromausfall wird höchstens früher gesendet."""
        self._volatile("UPDATE pages SET tx_count=tx_count+1, last_tx=?, next_tx=? "
                       "WHERE pid=?", (now, next_tx, pid))
        if withdraw_left is not None:
            self._volatile("UPDATE pages SET withdraw_left=? WHERE pid=?",
                           (withdraw_left, pid))

    def send_now(self, pid: int, now: int) -> None:
        """Due at once, schedule starts again from the beginning."""
        with self.lock, self.db:
            self.db.execute("UPDATE pages SET next_tx=?, tx_count=0 WHERE pid=?", (now, pid))

    def delete_page(self, pid: int) -> None:
        with self.lock, self.db:
            self.db.execute("DELETE FROM pages WHERE pid=?", (pid,))

    def due_pages(self, now: int) -> list[PageRow]:
        rows = self.db.execute(
            "SELECT * FROM pages WHERE next_tx <= ? ORDER BY pri DESC, next_tx, id",
            (now,)).fetchall()
        return [PageRow(**dict(r)) for r in rows]

    def upcoming(self, limit: int = 8) -> list[PageRow]:
        """The carousel's next pages (resting ones last), for the web GUI."""
        rows = self.db.execute("SELECT * FROM pages ORDER BY next_tx, pri DESC, id LIMIT ?",
                               (limit,)).fetchall()
        return [PageRow(**dict(r)) for r in rows]

    def frame_count(self, pid: int) -> int:
        return self.db.execute("SELECT COUNT(*) AS n FROM frames WHERE pid=?", (pid,)).fetchone()["n"]

    def next_due(self) -> int | None:
        row = self.db.execute("SELECT MIN(next_tx) AS m FROM pages").fetchone()
        return row["m"]

    def expired_pages(self, now: int) -> list[PageRow]:
        rows = self.db.execute(
            "SELECT * FROM pages WHERE state='active' AND exp_min IS NOT NULL "
            "AND t + exp_min * 60 < ?", (now,)).fetchall()
        return [PageRow(**dict(r)) for r in rows]

    # -- received pages -----------------------------------------------------

    def save_received(self, org: str, page_id: int, sub: int, sub_total: int, rev: int,
                      t: int, typ: int | None, data: bytes, heard_from: str,
                      now: int) -> str:
        """Keep the newest revision per (org, id, sub).

        Returns "new" (this subpage/revision was not there), "newer" (same
        revision, confirmed with a newer t) or "same" (nothing changed)."""
        with self.lock:                        # Lesen ohne "with self.db": das würde
            row = self.db.execute(             # flüchtige Schreibvorgänge mitcommitten
                "SELECT rev, t FROM received WHERE org=? AND id=? AND sub=?",
                (org, page_id, sub)).fetchone()
            same = bool(row) and (row["rev"], row["t"]) >= (rev, t)
            if same:                           # nur wiederholt: flüchtig, kein Commit
                self.db.execute(
                    "UPDATE received SET received_at=? WHERE org=? AND id=? AND sub=?",
                    (now, org, page_id, sub))
                return "same"
            with self.db:
                self.db.execute(
                    "INSERT OR REPLACE INTO received VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (org, page_id, sub, sub_total, rev, t, typ, data, heard_from, now))
        return "newer" if row and row["rev"] == rev else "new"

    def received(self) -> list[sqlite3.Row]:
        return self.db.execute("SELECT * FROM received ORDER BY org, id, sub").fetchall()

    def subpages(self, org: str, page_id: int) -> list[sqlite3.Row]:
        return self.db.execute("SELECT * FROM received WHERE org=? AND id=? ORDER BY sub",
                               (org, page_id)).fetchall()

    def drop_older_subpages(self, org: str, page_id: int, rev: int) -> None:
        with self.lock, self.db:
            self.db.execute("DELETE FROM received WHERE org=? AND id=? AND rev<?",
                            (org, page_id, rev))

    # -- listener pages -----------------------------------------------------

    def lpage(self, org: str, page_id: int) -> dict | None:
        row = self.db.execute("SELECT * FROM lpages WHERE org=? AND id=?",
                              (org, page_id)).fetchone()
        return dict(row) if row else None

    def save_lpage(self, page: dict) -> None:
        with self.lock, self.db:
            self.db.execute(
                f"INSERT OR REPLACE INTO lpages ({', '.join(LPAGE_FIELDS)}) "
                f"VALUES ({', '.join('?' for _ in LPAGE_FIELDS)})",
                tuple(page.get(f) for f in LPAGE_FIELDS))

    def update_lpage(self, org: str, page_id: int, volatile: bool = False, **fields) -> bool:
        """volatile=True: nur Wiederholung einer bekannten Seite (last_seen …), kein Commit."""
        bad = set(fields) - set(LPAGE_FIELDS)
        if bad:
            raise ValueError(f"unbekannte Felder {bad}")
        sql = f"UPDATE lpages SET {', '.join(f + '=?' for f in fields)} WHERE org=? AND id=?"
        params = (*fields.values(), org, page_id)
        if volatile:
            return self._volatile(sql, params) > 0
        with self.lock, self.db:
            return self.db.execute(sql, params).rowcount > 0

    def delete_lpage(self, org: str, page_id: int) -> None:
        """Remove a page completely (row and all subpages)."""
        with self.lock, self.db:
            self.db.execute("DELETE FROM lpages WHERE org=? AND id=?", (org, page_id))
            self.db.execute("DELETE FROM received WHERE org=? AND id=?", (org, page_id))

    def lpages(self, where: str = "", params: tuple = (), order: str = "last_seen DESC",
               limit: int | None = None) -> list[dict]:
        """Visible pages. `where` is built by the caller from fixed SQL fragments only."""
        sql = "SELECT * FROM lpages WHERE deleted_rev IS NULL"
        if where:
            sql += f" AND ({where})"
        sql += f" ORDER BY {order}"
        if limit is not None:
            sql += f" LIMIT {int(limit)}"
        return [dict(r) for r in self.db.execute(sql, params).fetchall()]

    def lpages_hidden_before(self, ts: int) -> list[dict]:
        return [dict(r) for r in self.db.execute(
            "SELECT * FROM lpages WHERE deleted_rev IS NOT NULL AND last_seen < ?", (ts,))]

    # -- stations heard -----------------------------------------------------

    def heard(self, call: str, now: int) -> None:
        self._volatile(
            "INSERT INTO stations VALUES (?, ?, ?, 1) ON CONFLICT(call) DO UPDATE "
            "SET last_heard=excluded.last_heard, frames=frames+1", (call, now, now))

    def stations(self) -> list[dict]:
        return [dict(r) for r in self.db.execute("SELECT * FROM stations ORDER BY call")]

    # -- small internal values ----------------------------------------------

    def get_meta(self, key: str) -> str | None:
        row = self.db.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
        return row["value"] if row else None

    def set_meta(self, key: str, value: str, volatile: bool = False) -> None:
        sql, params = "INSERT OR REPLACE INTO meta VALUES (?, ?)", (key, value)
        if volatile:
            self._volatile(sql, params)
            return
        with self.lock, self.db:
            self.db.execute(sql, params)

    # -- receive log --------------------------------------------------------

    def add_rxlog(self, entry: dict) -> None:
        row = {"dest": "", "org": None, "id": None, "sub": None, "sub_total": None,
               "rev": None, "ti": "", "bytes": 0, "own": 0}
        row.update({k: v for k, v in entry.items() if v is not None})
        fields = ("ts", "heard_from", "dest", "org", "id", "sub", "sub_total", "rev", "ti",
                  "result", "bytes", "own")
        self._volatile(f"INSERT INTO rxlog ({', '.join(fields)}) "
                       f"VALUES ({', '.join('?' for _ in fields)})",
                       tuple(row[f] for f in fields))

    def rxlog(self, limit: int = 200, org: str | None = None, page_id: int | None = None,
              brocast_only: bool = False) -> list[dict]:
        sql, params = "SELECT * FROM rxlog WHERE 1=1", []
        if org:
            sql += " AND org=?"
            params.append(org)
        if page_id is not None:
            sql += " AND id=?"
            params.append(page_id)
        if brocast_only:
            sql += " AND result != 'foreign'"
        sql += " ORDER BY n DESC LIMIT ?"
        params.append(max(1, min(int(limit), RXLOG_KEEP)))
        return [dict(r) for r in self.db.execute(sql, params)]

    def prune_rxlog(self, keep: int = RXLOG_KEEP) -> None:
        self._volatile("DELETE FROM rxlog WHERE n <= (SELECT MAX(n) FROM rxlog) - ?", (keep,))

    # -- opt-out and settings -----------------------------------------------

    def optouts(self) -> list[tuple[str, str]]:
        return [(r["station"], r["cat"]) for r in
                self.db.execute("SELECT * FROM optout ORDER BY station, cat")]

    def set_optouts(self, pairs: list[tuple[str, str]]) -> None:
        with self.lock, self.db:
            self.db.execute("DELETE FROM optout")
            self.db.executemany("INSERT OR IGNORE INTO optout VALUES (?, ?)", pairs)

    # -- rubrics ------------------------------------------------------------

    def rubrics(self, provider: str | None = None) -> list[dict]:
        """Station: rubrics the providers declared, in provider / sent order."""
        if provider is None:
            rows = self.db.execute("SELECT * FROM rubrics ORDER BY provider, pos")
        else:
            rows = self.db.execute("SELECT * FROM rubrics WHERE provider=? ORDER BY pos",
                                   (provider,))
        return [dict(r) for r in rows]

    def set_rubrics(self, provider: str, items: list[dict]) -> None:
        with self.lock, self.db:
            self.db.execute("DELETE FROM rubrics WHERE provider=?", (provider,))
            self.db.executemany(
                "INSERT INTO rubrics (provider, pos, name, cat, descr) VALUES (?, ?, ?, ?, ?)",
                [(provider, pos, r["name"], r["cat"], r.get("desc", ""))
                 for pos, r in enumerate(items)])

    def station_rubrics(self, station: str | None = None) -> list[dict]:
        """Listener: rubrics the stations announced with their index pages."""
        if station is None:
            rows = self.db.execute("SELECT * FROM station_rubrics ORDER BY station, pos")
        else:
            rows = self.db.execute("SELECT * FROM station_rubrics WHERE station=? ORDER BY pos",
                                   (station,))
        return [dict(r) for r in rows]

    def set_station_rubrics(self, station: str, items: list[dict], rev: int, now: int) -> None:
        with self.lock, self.db:
            self.db.execute("DELETE FROM station_rubrics WHERE station=?", (station,))
            self.db.executemany(
                "INSERT INTO station_rubrics (station, pos, cat, name, descr, rev, seen) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                [(station, pos, r["cat"], r["name"], r["descr"], rev, now)
                 for pos, r in enumerate(items)])

    def touch_station_rubrics(self, station: str, now: int) -> None:
        self._volatile("UPDATE station_rubrics SET seen=? WHERE station=?", (now, station))

    def delete_optout(self, cat: str) -> None:
        with self.lock, self.db:
            self.db.execute("DELETE FROM optout WHERE cat=?", (cat,))

    def settings(self) -> dict[str, str]:
        return {r["key"]: r["value"] for r in self.db.execute("SELECT * FROM settings")}

    def set_setting(self, key: str, value: str) -> None:
        with self.lock, self.db:
            self.db.execute("INSERT OR REPLACE INTO settings VALUES (?, ?)", (key, value))
