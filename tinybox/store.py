"""SQLite storage. Only this module talks SQL (always with parameters)."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

SCHEMA_VERSION = 10  # 4: chat_lines; 5: forwarding fields, bids, fwd_queue; 6: fwd_partial
                     # 7: seq/cseq + sync_gone (delta sync of the client, CR26)
                     # 8: chat_images (small images in the chat, CR12)
                     # 9: profiles (name, locator, home BBS of a station, CR73)
                     # 10: chat_lines.seq (event number, so a quote finds its history line)

SCHEMA = """
CREATE TABLE IF NOT EXISTS messages (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,  -- numbers are never reused
    msgid     TEXT NOT NULL UNIQUE,               -- UUID, for MQTT de-duplication
    type      TEXT NOT NULL CHECK (type IN ('P', 'B')),
    status    TEXT NOT NULL DEFAULT 'N' CHECK (status IN ('N', 'Y')),
    to_call   TEXT NOT NULL,
    from_call TEXT NOT NULL,
    subject   TEXT NOT NULL,
    body      TEXT NOT NULL,
    size      INTEGER NOT NULL,
    origin    TEXT NOT NULL,                      -- radio, telnet, sysop, mqtt
    created   TEXT NOT NULL,                      -- ISO 8601 UTC
    read_at   TEXT,
    replace_key TEXT,                             -- inbox "Replace:": update instead of new
    expires   TEXT,                               -- inbox "Valid:": ISO 8601 UTC, then deleted
    brocast   TEXT,                               -- inbox "Brocast:": page as JSON (or NULL)
    -- schema 5: forwarding (all empty for purely local mail)
    at_addr   TEXT NOT NULL DEFAULT '',           -- @ address (P) or area (B), '' = local
    bid       TEXT,                               -- BID/MID, max 12 chars, unique
    bid_kind  TEXT NOT NULL DEFAULT '',           -- B real BID, M generated MID (W0RLI)
    rlines    TEXT NOT NULL DEFAULT '',           -- R: lines, newest first, one per line
    fwd       TEXT NOT NULL DEFAULT '',           -- '' local, $ to forward, F forwarded, H held
    note      TEXT NOT NULL DEFAULT ''            -- why a message is held
);
CREATE TABLE IF NOT EXISTS bids (                     -- every BID ever seen (duplicate check)
    bid        TEXT PRIMARY KEY,
    first_seen TEXT NOT NULL,
    origin     TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS fwd_queue (                -- filled by the forward module only
    msg_id  INTEGER NOT NULL,
    partner TEXT NOT NULL,
    state   TEXT NOT NULL,                            -- open, later, done, rejected
    changed TEXT NOT NULL,
    PRIMARY KEY (msg_id, partner)
);
CREATE TABLE IF NOT EXISTS fwd_partial (              -- B1 restart: half received messages
    partner TEXT NOT NULL,
    bid     TEXT NOT NULL,
    data    BLOB NOT NULL,                            -- compressed payload received so far
    tries   INTEGER NOT NULL DEFAULT 0,               -- restarts asked for
    created TEXT NOT NULL,
    PRIMARY KEY (partner, bid)
);
CREATE TABLE IF NOT EXISTS jlog (
    call       TEXT PRIMARY KEY,
    first_seen TEXT NOT NULL,
    last_seen  TEXT NOT NULL,
    count      INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS connlog (                 -- CR44: one row per connection, kept forever
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    call    TEXT NOT NULL,
    base    TEXT NOT NULL,                            -- call without SSID (QSO of a user)
    via     TEXT NOT NULL,
    t_on    TEXT NOT NULL,                            -- connect, UTC ISO
    t_off   TEXT NOT NULL,                            -- disconnect
    secs    INTEGER NOT NULL,
    rx      INTEGER,
    tx      INTEGER,
    air_tx  INTEGER,
    air_rx  INTEGER,
    ended   TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS connlog_base ON connlog (base, id);
CREATE TABLE IF NOT EXISTS users (
    call       TEXT PRIMARY KEY,
    last_login TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS profiles (                 -- CR73: one per call WITHOUT SSID
    base      TEXT PRIMARY KEY,
    name      TEXT NOT NULL DEFAULT '',
    locator   TEXT NOT NULL DEFAULT '',
    homebbs   TEXT NOT NULL DEFAULT '',
    changed   INTEGER NOT NULL DEFAULT 0,               -- unix time of the last change
    asked     TEXT                                      -- last time the terminal asked for it
);
CREATE TABLE IF NOT EXISTS chat_lines (               -- only boards with history
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    board   TEXT NOT NULL,
    call    TEXT NOT NULL,
    text    TEXT NOT NULL,
    created TEXT NOT NULL,                            -- ISO 8601 UTC
    seq     INTEGER                                   -- event number #n (0..255), NULL = before schema 10
);
CREATE INDEX IF NOT EXISTS chat_lines_board ON chat_lines (board, created);
CREATE TABLE IF NOT EXISTS chat_images (              -- small chat images (CR12), one per hash
    hash    TEXT PRIMARY KEY,                         -- 6 hex digits of SHA-256 (the client's id)
    data    BLOB NOT NULL,                            -- WebP or JPEG, never decoded here
    created TEXT NOT NULL                             -- ISO 8601 UTC (upload time)
);
CREATE TABLE IF NOT EXISTS sync_seq (                 -- change counter of the messages (CR26)
    k     INTEGER PRIMARY KEY CHECK (k = 1),
    v     INTEGER NOT NULL,
    floor INTEGER NOT NULL DEFAULT 0                  -- seq of the newest purged tombstone
);
CREATE TABLE IF NOT EXISTS sync_gone (                -- deleted messages: the client is told
    id        INTEGER PRIMARY KEY,
    seq       INTEGER NOT NULL,
    type      TEXT NOT NULL,
    to_call   TEXT NOT NULL,
    from_call TEXT NOT NULL
);
"""

# Schema 7: every message carries seq (last change of anything the client shows)
# and cseq (last change of the content: new or replaced). The triggers keep them
# and the tombstones up to date whatever code path changes a message, so the
# delta sync (clientsync.py //SYNC) never misses a deletion from the terminal,
# the sysop web, the forward module or the expiry.
TRIGGERS = """
CREATE TRIGGER IF NOT EXISTS sync_ins AFTER INSERT ON messages BEGIN
    UPDATE sync_seq SET v = v + 1 WHERE k = 1;
    UPDATE messages SET seq = (SELECT v FROM sync_seq WHERE k = 1),
                        cseq = (SELECT v FROM sync_seq WHERE k = 1) WHERE id = NEW.id;
    DELETE FROM sync_gone WHERE id = NEW.id;
END;
CREATE TRIGGER IF NOT EXISTS sync_upd AFTER UPDATE OF status, fwd, type, to_call, from_call,
    at_addr ON messages BEGIN
    UPDATE sync_seq SET v = v + 1 WHERE k = 1;
    UPDATE messages SET seq = (SELECT v FROM sync_seq WHERE k = 1) WHERE id = NEW.id;
END;
CREATE TRIGGER IF NOT EXISTS sync_cupd AFTER UPDATE OF body, subject, created ON messages BEGIN
    UPDATE sync_seq SET v = v + 1 WHERE k = 1;
    UPDATE messages SET seq = (SELECT v FROM sync_seq WHERE k = 1),
                        cseq = (SELECT v FROM sync_seq WHERE k = 1) WHERE id = NEW.id;
END;
CREATE TRIGGER IF NOT EXISTS sync_del AFTER DELETE ON messages BEGIN
    UPDATE sync_seq SET v = v + 1 WHERE k = 1;
    INSERT OR REPLACE INTO sync_gone (id, seq, type, to_call, from_call)
        VALUES (OLD.id, (SELECT v FROM sync_seq WHERE k = 1), OLD.type, OLD.to_call,
                OLD.from_call);
END;
"""


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass
class Message:
    id: int
    msgid: str
    type: str
    status: str
    to_call: str
    from_call: str
    subject: str
    body: str
    size: int
    origin: str
    created: str
    read_at: str | None
    replace_key: str | None = None
    expires: str | None = None
    brocast: str | None = None          # brocast page (JSON text) delivered with the bulletin
    at_addr: str = ""                   # @ address (P) or distribution area (B); '' = local
    bid: str | None = None              # BID/MID
    rlines: str = ""                    # R: lines, newest first, "\n"-separated
    fwd: str = ""                       # '' local, '$' to forward, 'F' forwarded, 'H' held
    note: str = ""                      # reason for 'H'
    bid_kind: str = ""                  # 'B' real BID, 'M' generated MID (personal mail)
    seq: int = 0                        # change counter: last change of anything (CR26)
    cseq: int = 0                       # change counter: last change of the content

    @property
    def rline_list(self) -> list[str]:
        return [x for x in self.rlines.split("\n") if x]


@dataclass
class ChatLine:
    board: str
    call: str
    text: str
    created: str
    seq: int | None = None              # event number #n, None = not known (old rows)


@dataclass
class JlogEntry:
    call: str
    first_seen: str
    last_seen: str
    count: int


class Store:
    def __init__(self, db_path: Path | str) -> None:
        if str(db_path) != ":memory:":
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(str(db_path))
        self._db.row_factory = sqlite3.Row
        self._db.execute("PRAGMA foreign_keys = ON")
        self._db.executescript(SCHEMA)
        # schema 1 -> 2: two columns for the inbox folder; 2 -> 3: brocast page;
        # 4 -> 5: forwarding fields (existing rows stay as they are, BIDs are
        # given by MessageService.assign_missing_bids)
        cols = {r["name"] for r in self._db.execute("PRAGMA table_info(messages)")}
        for col in ("replace_key", "expires", "brocast", "bid"):
            if col not in cols:
                self._db.execute(f"ALTER TABLE messages ADD COLUMN {col} TEXT")
        for col in ("at_addr", "rlines", "fwd", "note", "bid_kind"):
            if col not in cols:
                self._db.execute(f"ALTER TABLE messages ADD COLUMN {col} TEXT NOT NULL DEFAULT ''")
        self._db.execute("CREATE UNIQUE INDEX IF NOT EXISTS messages_bid ON messages (bid)")
        # 9 -> 10: event number of a chat line (a quote "~^5" finds it in the history)
        if "seq" not in {r["name"] for r in self._db.execute("PRAGMA table_info(chat_lines)")}:
            self._db.execute("ALTER TABLE chat_lines ADD COLUMN seq INTEGER")
        # 6 -> 7: change counter for the delta sync; old rows count as changed "at
        # their number", the counter starts above the highest number
        for col in ("seq", "cseq"):
            if col not in cols:
                self._db.execute(f"ALTER TABLE messages ADD COLUMN {col} INTEGER NOT NULL DEFAULT 0")
        self._db.execute("UPDATE messages SET seq = id, cseq = id WHERE seq = 0")
        self._db.execute("INSERT OR IGNORE INTO sync_seq (k, v) VALUES (1, "
                         "COALESCE((SELECT MAX(id) FROM messages), 0))")
        self._db.executescript(TRIGGERS)
        self._db.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
        self._db.commit()

    def close(self) -> None:
        self._db.close()

    # --- messages -------------------------------------------------------

    def add_message(self, *, msgid: str, type: str, to_call: str, from_call: str,
                    subject: str, body: str, origin: str, created: str,
                    replace_key: str | None = None, expires: str | None = None,
                    brocast: str | None = None, at_addr: str = "", bid: str | None = None,
                    rlines: str = "", fwd: str = "", note: str = "") -> int:
        size = len(body.encode("utf-8"))
        with self._db:
            cur = self._db.execute(
                "INSERT INTO messages (msgid, type, status, to_call, from_call, subject,"
                " body, size, origin, created, replace_key, expires, brocast,"
                " at_addr, bid, rlines, fwd, note)"
                " VALUES (?, ?, 'N', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (msgid, type, to_call, from_call, subject, body, size, origin, created,
                 replace_key, expires, brocast, at_addr, bid, rlines, fwd, note),
            )
        return int(cur.lastrowid)

    # --- forwarding fields ------------------------------------------------

    def set_forward_fields(self, msg_id: int, *, bid: str | None = None,
                           rlines: str | None = None, fwd: str | None = None,
                           note: str | None = None, bid_kind: str | None = None) -> None:
        sets, args = [], []
        for col, val in (("bid", bid), ("rlines", rlines), ("fwd", fwd), ("note", note),
                         ("bid_kind", bid_kind)):
            if val is not None:
                sets.append(f"{col} = ?")
                args.append(val)
        if sets:
            with self._db:
                self._db.execute(f"UPDATE messages SET {', '.join(sets)} WHERE id = ?",
                                 (*args, msg_id))

    # --- forward queue (used by the forward module only) -----------------

    def fwd_enqueue(self, msg_id: int, partner: str) -> None:
        with self._db:
            self._db.execute("INSERT OR IGNORE INTO fwd_queue (msg_id, partner, state, changed)"
                             " VALUES (?, ?, 'open', ?)", (msg_id, partner, utc_now()))

    def fwd_pending(self, partner: str) -> list[Message]:
        rows = self._db.execute(
            "SELECT m.* FROM fwd_queue q JOIN messages m ON m.id = q.msg_id"
            " WHERE q.partner = ? AND q.state IN ('open', 'later') AND m.fwd != 'H'"
            " ORDER BY m.id", (partner,)).fetchall()
        return [Message(**dict(r)) for r in rows]

    def fwd_set(self, msg_id: int, partner: str, state: str) -> None:
        with self._db:
            self._db.execute("UPDATE fwd_queue SET state = ?, changed = ?"
                             " WHERE msg_id = ? AND partner = ?",
                             (state, utc_now(), msg_id, partner))

    def fwd_states(self, msg_id: int) -> dict[str, str]:
        return {r["partner"]: r["state"] for r in self._db.execute(
            "SELECT partner, state FROM fwd_queue WHERE msg_id = ?", (msg_id,))}

    def fwd_remove(self, msg_ids: list[int]) -> None:
        with self._db:
            self._db.executemany("DELETE FROM fwd_queue WHERE msg_id = ?", [(i,) for i in msg_ids])

    def fwd_queue_list(self) -> list[tuple[str, int, str, str]]:
        """(partner, msg_id, state, changed) of everything not yet done."""
        return [(r["partner"], r["msg_id"], r["state"], r["changed"]) for r in self._db.execute(
            "SELECT * FROM fwd_queue WHERE state IN ('open', 'later') ORDER BY partner, msg_id")]

    # --- B1 restart data (forward module only) -----------------------------

    def partial_get(self, partner: str, bid: str) -> tuple[bytes, int] | None:
        row = self._db.execute("SELECT data, tries FROM fwd_partial WHERE partner = ? AND bid = ?",
                               (partner, bid)).fetchone()
        return (bytes(row["data"]), row["tries"]) if row else None

    def partial_put(self, partner: str, bid: str, data: bytes) -> None:
        with self._db:
            self._db.execute(
                "INSERT INTO fwd_partial (partner, bid, data, tries, created) VALUES (?, ?, ?, 0, ?)"
                " ON CONFLICT (partner, bid) DO UPDATE SET data = excluded.data",
                (partner, bid, data, utc_now()))

    def partial_tried(self, partner: str, bid: str) -> None:
        with self._db:
            self._db.execute("UPDATE fwd_partial SET tries = tries + 1 WHERE partner = ? AND bid = ?",
                             (partner, bid))

    def partial_drop(self, partner: str, bid: str) -> None:
        with self._db:
            self._db.execute("DELETE FROM fwd_partial WHERE partner = ? AND bid = ?", (partner, bid))

    def purge_partials(self, days: int = 2) -> int:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")
        with self._db:
            return self._db.execute("DELETE FROM fwd_partial WHERE created < ?", (cutoff,)).rowcount

    def fill_bid_kind(self) -> None:
        with self._db:
            self._db.execute("UPDATE messages SET bid_kind = CASE type WHEN 'B' THEN 'B' ELSE 'M'"
                             " END WHERE bid_kind = '' AND bid IS NOT NULL AND bid != ''")

    def ids_without_bid(self) -> list[int]:
        return [r["id"] for r in self._db.execute(
            "SELECT id FROM messages WHERE bid IS NULL OR bid = '' ORDER BY id")]

    def get_by_bid(self, bid: str) -> Message | None:
        row = self._db.execute("SELECT * FROM messages WHERE bid = ?", (bid,)).fetchone()
        return Message(**dict(row)) if row else None

    def bid_known(self, bid: str) -> bool:
        return (self._db.execute("SELECT 1 FROM bids WHERE bid = ?", (bid,)).fetchone()
                is not None or self.get_by_bid(bid) is not None)

    def bid_add(self, bid: str, origin: str) -> None:
        with self._db:
            self._db.execute("INSERT OR IGNORE INTO bids (bid, first_seen, origin)"
                             " VALUES (?, ?, ?)", (bid, utc_now(), origin))

    def purge_bids(self, days: int) -> int:
        """Forget BIDs older than `days` (BIDs of stored messages stay known anyway)."""
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")
        with self._db:
            return self._db.execute("DELETE FROM bids WHERE first_seen < ?", (cutoff,)).rowcount

    def get_by_replace_key(self, key: str) -> Message | None:
        row = self._db.execute("SELECT * FROM messages WHERE replace_key = ? AND type = 'B'"
                               " ORDER BY id DESC", (key,)).fetchone()
        return Message(**dict(row)) if row else None

    def replace_content(self, msg_id: int, *, to_call: str, from_call: str, subject: str,
                        body: str, created: str, expires: str | None,
                        brocast: str | None = None) -> None:
        """New content for the same message number; it counts as new (unread) again."""
        with self._db:
            self._db.execute(
                "UPDATE messages SET to_call = ?, from_call = ?, subject = ?, body = ?, size = ?,"
                " created = ?, expires = ?, brocast = ?, status = 'N', read_at = NULL"
                " WHERE id = ?",
                (to_call, from_call, subject, body, len(body.encode("utf-8")), created,
                 expires, brocast, msg_id))

    def set_expires(self, msg_id: int, expires: str | None) -> None:
        with self._db:
            self._db.execute("UPDATE messages SET expires = ? WHERE id = ?", (expires, msg_id))

    def delete_expired(self, now_iso: str) -> list[int]:
        """Bulletins whose own validity ("Valid:") is over."""
        rows = self._db.execute(
            "SELECT id FROM messages WHERE expires IS NOT NULL AND expires < ?", (now_iso,)
        ).fetchall()
        ids = [r["id"] for r in rows]
        with self._db:
            self._db.executemany("DELETE FROM messages WHERE id = ?", [(i,) for i in ids])
        return ids

    def get(self, msg_id: int) -> Message | None:
        row = self._db.execute("SELECT * FROM messages WHERE id = ?", (msg_id,)).fetchone()
        return Message(**dict(row)) if row else None

    def get_by_msgid(self, msgid: str) -> Message | None:
        row = self._db.execute("SELECT * FROM messages WHERE msgid = ?", (msgid,)).fetchone()
        return Message(**dict(row)) if row else None

    def list_messages(self) -> list[Message]:
        rows = self._db.execute("SELECT * FROM messages ORDER BY id DESC").fetchall()
        return [Message(**dict(r)) for r in rows]

    def mark_read(self, msg_id: int) -> None:
        with self._db:
            self._db.execute(
                "UPDATE messages SET status = 'Y', read_at = COALESCE(read_at, ?) WHERE id = ?",
                (utc_now(), msg_id),
            )

    def delete(self, msg_id: int) -> bool:
        with self._db:
            cur = self._db.execute("DELETE FROM messages WHERE id = ?", (msg_id,))
        return cur.rowcount > 0

    _EDITABLE = {"to_call", "from_call", "type", "status", "subject", "at_addr"}

    def update_field(self, msg_id: int, field: str, value: str) -> None:
        if field not in self._EDITABLE:  # column names cannot be parameters
            raise ValueError(f"field not editable: {field}")
        with self._db:
            self._db.execute(f"UPDATE messages SET {field} = ? WHERE id = ?", (value, msg_id))

    # --- delta sync of the client (CR26) ----------------------------------

    def sync_seq(self) -> int:
        """The change counter: everything up to here is known once a client has it."""
        return self._db.execute("SELECT v FROM sync_seq WHERE k = 1").fetchone()[0]

    def changed_since(self, seq: int) -> list[Message]:
        """Messages changed after `seq`, in the order of the changes."""
        rows = self._db.execute("SELECT * FROM messages WHERE seq > ? ORDER BY seq",
                                (seq,)).fetchall()
        return [Message(**dict(r)) for r in rows]

    def gone_since(self, seq: int) -> list[tuple[int, int, str, str, str]]:
        """(id, seq, type, to_call, from_call) of messages deleted after `seq`."""
        return [tuple(r) for r in self._db.execute(
            "SELECT id, seq, type, to_call, from_call FROM sync_gone WHERE seq > ? ORDER BY seq",
            (seq,))]

    def purge_gone(self, keep: int = 2000) -> None:
        """Tombstones are small; keep the newest `keep`. A client whose seq is
        below the newest purged one gets //ERR seq and starts over."""
        with self._db:
            row = self._db.execute("SELECT MAX(seq) FROM sync_gone WHERE id NOT IN "
                                   "(SELECT id FROM sync_gone ORDER BY seq DESC LIMIT ?)",
                                   (keep,)).fetchone()
            if row[0]:
                self._db.execute("UPDATE sync_seq SET floor = MAX(floor, ?) WHERE k = 1", (row[0],))
                self._db.execute("DELETE FROM sync_gone WHERE seq <= ?", (row[0],))

    def gone_floor(self) -> int:
        """Clients must know at least this seq, else deletions would be missed."""
        return self._db.execute("SELECT floor FROM sync_seq WHERE k = 1").fetchone()[0]

    def delete_bulletins_older_than(self, days: int, only: list[str] | None = None,
                                    exclude: list[str] | None = None) -> list[int]:
        """Bulletins older than days; only = just these rubrics, exclude = all but
        these (a rubric's own validity, CR40)."""
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")
        sql = ("SELECT id FROM messages WHERE type = 'B' AND created < ?"
               " AND (replace_key IS NULL OR replace_key NOT LIKE 'fixed:%')")
        args: list = [cutoff]
        for names, op in ((only, "IN"), (exclude, "NOT IN")):
            if names:                            # NOT IN (NULL) would match nothing
                sql += f" AND to_call {op} ({','.join('?' * len(names))})"
                args += names
            elif names is not None and op == "IN":
                return []
        rows = self._db.execute(sql, args).fetchall()
        ids = [r["id"] for r in rows]
        with self._db:
            self._db.executemany("DELETE FROM messages WHERE id = ?", [(i,) for i in ids])
        return ids

    # --- chat -----------------------------------------------------------

    def chat_add(self, board: str, call: str, text: str, created: str,
                 seq: int | None = None) -> None:
        with self._db:
            self._db.execute(
                "INSERT INTO chat_lines (board, call, text, created, seq) VALUES (?, ?, ?, ?, ?)",
                (board, call, text, created, seq))

    def chat_recent(self, board: str, since_iso: str, limit: int) -> list[ChatLine]:
        """The newest `limit` lines since `since_iso`, oldest first."""
        rows = self._db.execute(
            "SELECT board, call, text, created, seq FROM chat_lines"
            " WHERE board = ? AND created >= ? ORDER BY id DESC LIMIT ?",
            (board, since_iso, limit)).fetchall()
        return [ChatLine(**dict(r)) for r in reversed(rows)]

    def chat_stats(self, board: str, since_iso: str) -> tuple[int, str | None]:
        """Number of stored lines since `since_iso` and the time of the newest."""
        row = self._db.execute(
            "SELECT COUNT(*) AS n, MAX(created) AS last FROM chat_lines"
            " WHERE board = ? AND created >= ?", (board, since_iso)).fetchone()
        return row["n"], row["last"]

    def chat_page(self, board: str, since_iso: str, limit: int, after_iso: str | None = None,
                  before_iso: str | None = None) -> tuple[list[ChatLine], int]:
        """The newest `limit` lines since `since_iso` (and from `after_iso`, up to
        `before_iso` - both inclusive: lines of the same second are not lost, the
        client drops what it has already), oldest first, and how many stored lines
        are older than them."""
        where, args = "board = ? AND created >= ?", [board, since_iso]
        if after_iso:
            where += " AND created >= ?"
            args.append(after_iso)
        if before_iso:
            where += " AND created <= ?"
            args.append(before_iso)
        rows = self._db.execute(
            f"SELECT id, board, call, text, created, seq FROM chat_lines WHERE {where}"
            " ORDER BY id DESC LIMIT ?", (*args, limit)).fetchall()
        if rows:
            older = self._db.execute(
                "SELECT COUNT(*) FROM chat_lines WHERE board = ? AND created >= ? AND id < ?",
                (board, since_iso, rows[-1]["id"])).fetchone()[0]
        else:
            older = self._db.execute(
                "SELECT COUNT(*) FROM chat_lines WHERE board = ? AND created >= ?"
                + (" AND created <= ?" if before_iso else ""),
                (board, since_iso, *([before_iso] if before_iso else []))).fetchone()[0]
            if after_iso:        # nothing new since then: everything stored is "older"
                older = self.chat_stats(board, since_iso)[0]
        lines = [ChatLine(board=r["board"], call=r["call"], text=r["text"], created=r["created"],
                          seq=r["seq"]) for r in reversed(rows)]
        return lines, older

    def chat_purge(self, keep: dict[str, str]) -> int:
        """keep: board -> oldest allowed ISO time. Lines of other boards
        (removed from the config or switched to live) are deleted too."""
        with self._db:
            n = 0
            for board, cutoff in keep.items():
                n += self._db.execute("DELETE FROM chat_lines WHERE board = ? AND created < ?",
                                      (board, cutoff)).rowcount
            marks = ",".join("?" * len(keep))
            n += self._db.execute(f"DELETE FROM chat_lines WHERE board NOT IN ({marks})",
                                  list(keep)).rowcount
        return n

    # --- chat images (CR12) ---------------------------------------------

    def image_put(self, hash: str, data: bytes) -> None:
        with self._db:
            self._db.execute("INSERT OR IGNORE INTO chat_images (hash, data, created)"
                             " VALUES (?, ?, ?)", (hash, data, utc_now()))

    def image_get(self, hash: str) -> bytes | None:
        row = self._db.execute("SELECT data FROM chat_images WHERE hash = ?", (hash,)).fetchone()
        return bytes(row["data"]) if row else None

    def image_size(self, hash: str) -> int | None:
        row = self._db.execute("SELECT length(data) AS n FROM chat_images WHERE hash = ?",
                               (hash,)).fetchone()
        return row["n"] if row else None

    def image_purge(self, before_iso: str) -> int:
        """Delete images uploaded before `before_iso` that no stored chat line
        refers to any more (the line carries '~#<hash>')."""
        with self._db:
            return self._db.execute(
                "DELETE FROM chat_images WHERE created < ? AND NOT EXISTS"
                " (SELECT 1 FROM chat_lines WHERE instr(text, '~#' || chat_images.hash) > 0)",
                (before_iso,)).rowcount

    # --- JLOG / users ---------------------------------------------------

    def jlog_touch(self, call: str) -> None:
        now = utc_now()
        with self._db:
            self._db.execute(
                "INSERT INTO jlog (call, first_seen, last_seen, count) VALUES (?, ?, ?, 1)"
                " ON CONFLICT(call) DO UPDATE SET last_seen = excluded.last_seen,"
                " count = count + 1",
                (call, now, now),
            )

    # --- connection logbook (CR44) ---------------------------------------------

    def connlog_add(self, row: dict) -> None:
        with self._db:
            self._db.execute(
                "INSERT INTO connlog (call, base, via, t_on, t_off, secs, rx, tx, air_tx,"
                " air_rx, ended) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (row["call"], row["call"].split("-", 1)[0], row["via"], row["start"],
                 row["end"], row["secs"], row.get("rx"), row.get("tx"), row.get("air_tx"),
                 row.get("air_rx"), row["ended"]))

    def connlog_list(self, base: str | None = None, limit: int | None = None) -> list[dict]:
        """Newest first. base = only this station (call without SSID)."""
        sql = "SELECT * FROM connlog" + (" WHERE base = ?" if base else "") + " ORDER BY id DESC"
        args: list = [base] if base else []
        if limit:
            sql += " LIMIT ?"
            args.append(limit)
        return [{"call": r["call"], "via": r["via"], "start": r["t_on"], "end": r["t_off"],
                 "secs": r["secs"], "rx": r["rx"], "tx": r["tx"], "air_tx": r["air_tx"],
                 "air_rx": r["air_rx"], "ended": r["ended"]} for r in self._db.execute(sql, args)]

    def jlog_list(self, limit: int = 20) -> list[JlogEntry]:
        rows = self._db.execute(
            "SELECT * FROM jlog ORDER BY last_seen DESC LIMIT ?", (limit,)
        ).fetchall()
        return [JlogEntry(**dict(r)) for r in rows]

    # --- profiles (CR73) --------------------------------------------------------

    @staticmethod
    def _profile(r) -> dict:
        return {"name": r["name"], "loc": r["locator"], "home": r["homebbs"],
                "t": r["changed"], "asked": r["asked"]}

    def profile_get(self, base: str) -> dict | None:
        r = self._db.execute("SELECT * FROM profiles WHERE base = ?", (base,)).fetchone()
        return self._profile(r) if r else None

    def profiles_get(self, bases: list[str]) -> dict[str, dict]:
        if not bases:
            return {}
        rows = self._db.execute(
            f"SELECT * FROM profiles WHERE base IN ({','.join('?' * len(bases))})", bases)
        return {r["base"]: self._profile(r) for r in rows}

    def profile_set(self, base: str, name: str, loc: str, home: str, changed: int) -> None:
        with self._db:
            self._db.execute(
                "INSERT INTO profiles (base, name, locator, homebbs, changed) VALUES (?, ?, ?, ?, ?)"
                " ON CONFLICT(base) DO UPDATE SET name = excluded.name,"
                " locator = excluded.locator, homebbs = excluded.homebbs,"
                " changed = excluded.changed",
                (base, name, loc, home, changed))

    def profile_asked(self, base: str) -> None:
        with self._db:
            self._db.execute(
                "INSERT INTO profiles (base, asked) VALUES (?, ?)"
                " ON CONFLICT(base) DO UPDATE SET asked = excluded.asked", (base, utc_now()))

    def user_login(self, call: str) -> None:
        with self._db:
            self._db.execute(
                "INSERT INTO users (call, last_login) VALUES (?, ?)"
                " ON CONFLICT(call) DO UPDATE SET last_login = excluded.last_login",
                (call, utc_now()),
            )
