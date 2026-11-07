"""Chat boards: fixed rooms set by the sysop in tinybox.conf ([chat_boards]).

A board is either "live" (lines go only to stations in the board right now)
or keeps a history for n hours/days (shown when a station joins).
The ChatHub knows who is in which board and delivers the lines; the
sessions themselves only call join/leave/say/react.

Every chat event gets a sequence number per board (hex 0-FF, wraps) and a
readable text form for TinyBox clients (PLANUNG.md 12.4):

    #4F OE3GAS: Servus             line
    #50 +2 OE3GAS /-               joined as member number 2 (with APRS symbol,
                                   if the client sent one)
    #51 -2                         member 2 left
    #53 =2 /k                      member 2 has a new APRS symbol ("=2" = none)
    #52 OE3TEC *4F :+1             reaction to event 4F
    #54 %2 4 3 ?                   link quality bars 0-5 per member number, ? = no
                                   result yet (PLANUNG.md 14.4), clients only
    #55 !Connection to OE1ABC lost system text (after "-2" when the link broke)

Member numbers (CR33): every station in a board gets the lowest free number
1..n when it joins, //WHO lists "n call[=sym]". Clients without the NUM cap
get the old form with calls instead ("+OE3GAS /-", "-OE3GAS", "%OE3GAS 4"):
the UI frame carries the new form, old clients get the old line as I-frame.

    %Q 2 4 48 2 50 3 1 1 0 41 1 48 2 14;3 ...   link statistics of all members
                                   with data (CR33, 14.6): no sequence number,
                                   never resent, NUM clients only

Terminal users get the usual human text. Clients get the event line: if at
least one client in the board hears the mailbox directly (UI mode), the line
goes out ONCE as UI frame to TBCHAT-<board number>; clients without UI get
it as I-frame. The last 256 events per board are kept in memory for //RESEND.
"""

from __future__ import annotations

import logging
import re
from collections import deque
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Callable

from prcore.chatimg import terminal_text

from . import chatimg, linkq, texts
from .config import ChatBoard, Config
from .events import EventBus
from .store import ChatLine, Store, utc_now

if TYPE_CHECKING:
    from .session import Session

log = logging.getLogger(__name__)

SEQ_MOD = 256
MAX_UI_BOARD = 15          # TBCHAT-1 .. TBCHAT-15 (SSID)
UI_DEST = "TBCHAT"
REACTION_RE = re.compile(r"^[!-~]{1,8}$")    # an emoji code: :+1, <3, ~0A ...
# CR31: a comment refers to the event it answers - "~^4F text"
QUOTE_RE = re.compile(r"^~\^([0-9A-F]{1,2})(?: |$)")
QUOTE_OLD_RE = re.compile(r"^~\^([A-Z0-9]{1,6}(?:-\d{1,2})?) (\d{4}) ?")
QUOTE_EXCERPT = 40


def _iso_hours_ago(hours: int) -> str:
    t = datetime.now(timezone.utc) - timedelta(hours=hours)
    return t.strftime("%Y-%m-%dT%H:%M:%SZ")


class ChatHub:
    def __init__(self, store: Store, bus: EventBus, cfg: Config) -> None:
        self.store = store
        self.bus = bus
        self.cfg = cfg
        self._members: dict[str, list[Session]] = {}
        self._seq: dict[str, int] = {}                       # last number per board
        self._recent: dict[str, deque[tuple[int, str, str]]] = {}  # (seq, line, old form)
        self._numbers: dict[str, dict[str, int]] = {}         # board -> call -> member no.
        # set by the AGW adapter: ui_send(dest_call, text) sends one UI frame
        self.ui_send: Callable[[str, str], None] | None = None
        self._q_text: dict[str, str] = {}       # board -> last % event (link quality)
        self._q_at: dict[str, float] = {}       # board -> when it was sent
        self._qs_text: dict[str, str] = {}      # board -> last %Q line (statistics)
        self._qs_at: dict[str, float] = {}
        self.images = chatimg.ChatImages(store, cfg)     # small images (CR12)

    # --- boards ---------------------------------------------------------

    @property
    def enabled(self) -> bool:
        return self.cfg.chat.enabled and bool(self.cfg.chat.boards)

    @property
    def boards(self) -> list[ChatBoard]:
        return self.cfg.chat.boards

    def find(self, arg: str) -> ChatBoard | None:
        """Board by name, or by its number in the board list (1, 2, ...)."""
        arg = arg.strip()
        if arg.isdigit():
            n = int(arg)
            return self.boards[n - 1] if 1 <= n <= len(self.boards) else None
        return self.cfg.chat.board(arg)

    def number(self, board: str) -> int:
        """1-based number of a board (0 if unknown)."""
        for i, b in enumerate(self.boards, 1):
            if b.name == board:
                return i
        return 0

    def members(self, board: str) -> list[Session]:
        return [s for s in self._members.get(board, []) if not s.closed]

    def member_no(self, board: str, call: str) -> int:
        """Member number of a station in a board (0 = not a member)."""
        return self._numbers.get(board, {}).get(call, 0)

    def _assign_no(self, board: str, call: str) -> int:
        nums = self._numbers.setdefault(board, {})
        n = 1
        while n in nums.values():
            n += 1
        nums[call] = n
        return n

    @staticmethod
    def _num_client(s: Session) -> bool:
        return bool(s.client) and "NUM" in s.client.caps

    def who_line(self, board: str, for_session: Session) -> str:
        """//WHO for a joining client: 'n call[=sym] ...' (NUM) or 'call[=sym] ...'."""
        items = []
        for m in self.members(board):
            sym = m.client.symbol if m.client else ""
            item = m.call + (f"={sym}" if sym else "")
            if self._num_client(for_session):
                item = f"{self.member_no(board, m.call)} {item}"
            items.append(item)
        return "//WHO " + " ".join(items) if items else "//WHO"

    def total_members(self) -> int:
        return sum(len(self.members(b.name)) for b in self.boards)

    def history(self, board: ChatBoard) -> list[ChatLine]:
        """The last history_lines lines (old clients get them when joining)."""
        if board.live or self.cfg.chat.history_lines == 0:
            return []
        return self.store.chat_recent(board.name, _iso_hours_ago(board.keep_hours),
                                      self.cfg.chat.history_lines)

    # History on request (CR13): joining only tells how much is stored.

    def history_info(self, board: ChatBoard) -> tuple[int, str | None]:
        """(number of stored lines, time of the newest) - (0, None) for live boards."""
        if board.live or self.cfg.chat.history_lines == 0:
            return 0, None
        return self.store.chat_stats(board.name, _iso_hours_ago(board.keep_hours))

    def history_page(self, board: ChatBoard, n: int, after_iso: str | None = None,
                     before_iso: str | None = None) -> tuple[list[ChatLine], int]:
        """Up to n lines (at most history_lines per request), and how many older
        lines are left."""
        n = max(0, min(n, self.cfg.chat.history_lines))
        if board.live or n == 0:
            return [], 0
        return self.store.chat_page(board.name, _iso_hours_ago(board.keep_hours), n,
                                    after_iso, before_iso)

    def last_seq(self, board: str) -> str:
        n = self._seq.get(board)
        return "-" if n is None else f"{n:X}"

    # --- membership -----------------------------------------------------

    def _rx_window(self, session: Session) -> linkq.RxWindow | None:
        return (linkq.RxWindow(linkq.cfg_from(self.cfg.direwolf))
                if session.client and session.client.ui and not linkq.is_local(session) else None)

    def rebind(self, session: Session) -> None:
        """A client announced itself again on a session that is still in a board
        (a restart on a link that stayed up): only the receive window follows the
        new caps. No leave/join - the station never left, so nobody else hears a
        thing and nothing goes over the air for the others."""
        session.ui_rx = self._rx_window(session)

    def join(self, session: Session, board: ChatBoard) -> None:
        self.leave(session, quiet=False)
        self._members.setdefault(board.name, []).append(session)
        session.chat_board = board.name
        session.ui_rx = self._rx_window(session)
        sym = session.client.symbol if session.client else ""
        n = self._assign_no(board.name, session.call)
        tail = f" {sym}" if sym else ""
        self._deliver(board.name, f"+{n} {session.call}{tail}",
                      texts.CHAT_JOINED.format(call=session.call, board=board.name),
                      sender=session, legacy=f"+{session.call}{tail}")
        self.bus.publish("chat.joined", board=board.name, call=session.call)
        log.info("%s joined chat %s", session.call, board.name)

    def leave(self, session: Session, quiet: bool = False, reason: str = "",
              lost: bool = False) -> None:
        """lost: the radio link broke (Direwolf: retries used up) - clients also
        get a system line, so everybody sees why the station is gone."""
        board = session.chat_board
        if board is None:
            return
        session.chat_board = None
        session.ui_rx = None
        members = self._members.get(board, [])
        if session in members:
            members.remove(session)
        n = self._numbers.get(board, {}).pop(session.call, 0)
        if not quiet:
            self._deliver(board, f"-{n}",
                          texts.CHAT_LEFT.format(call=session.call, board=board,
                                                 reason=reason), sender=session,
                          legacy=f"-{session.call}")
            if lost:
                self._deliver(board, "!" + texts.CHAT_LOST_SYS.format(call=session.call), None,
                              sender=session)
        self.bus.publish("chat.left", board=board, call=session.call)
        log.info("%s left chat %s%s", session.call, board, reason)

    # --- talking --------------------------------------------------------

    def readable(self, board: str, text: str, live: bool = True) -> str:
        """A chat line as a terminal user should read it: the image reference
        becomes "[Image ...]" (CR12), the comment reference the quoted line
        (CR31). live=False (history): the event numbers mean nothing any more."""
        m = QUOTE_RE.match(text)
        if m:
            rest = text[m.end():]
            ref = int(m.group(1), 16)
            quoted = self._line_of(board, ref) if live else ""
            if quoted:
                call, _, what = quoted.partition(": ")
                what = terminal_text(what, short=True)
                if len(what) > QUOTE_EXCERPT:
                    what = what[:QUOTE_EXCERPT] + "\u2026"
                text = texts.CHAT_QUOTE.format(call=call, text=what) + rest
            else:
                text = texts.CHAT_QUOTE_GONE.format(ref=m.group(1)) + rest
        return terminal_text(text)

    def say(self, session: Session, text: str) -> None:
        board = self.cfg.chat.board(session.chat_board or "")
        if board is None:
            return
        now = utc_now()
        if not board.live:
            self.store.chat_add(board.name, session.call, text, now)
        # terminals read "[Image ...]" and the quoted line instead of the bare
        # references (CR12, CR31)
        self._deliver(board.name, f"{session.call}: {text}",
                      texts.CHAT_LINE.format(call=session.call,
                                             text=self.readable(board.name, text)),
                      sender=session)
        self.bus.publish("chat.message", board=board.name, call=session.call,
                         text=text, created=now)

    def react(self, session: Session, ref: int, emoji: str) -> bool:
        """Reaction (emoji code) to event number ref of the session's board."""
        board = session.chat_board
        if board is None or not REACTION_RE.match(emoji) or not 0 <= ref < SEQ_MOD:
            return False
        target = self.readable(board, self._line_of(board, ref))
        human = texts.CHAT_REACT.format(call=session.call, emoji=emoji,
                                        target=target[:40] if target else f"#{ref:X}")
        self._deliver(board, f"{session.call} *{ref:X} {emoji}", human, sender=session)
        return True

    def upload_started(self, session: Session, size_code: str, size: int) -> None:
        """CR30: a picture is going up - everybody in the board should know why
        the channel is busy. One event, no running progress over the air."""
        board = session.chat_board
        if board is None:
            return
        self._deliver(board, f"^{session.call} {size_code}",
                      texts.CHAT_UPLOAD.format(call=session.call, size=f"{size / 1024:.1f} KB"),
                      sender=session)

    def symbol_changed(self, session: Session) -> None:
        """The client chose another APRS symbol: tell the board at once (CR7),
        so every avatar of this station changes. Only for clients (2-3 bytes)."""
        board = session.chat_board
        if board is None or session.client is None:
            return
        sym = session.client.symbol
        tail = f" {sym}" if sym else ""
        self._deliver(board, f"={self.member_no(board, session.call)}{tail}", None,
                      sender=session, legacy=f"={session.call}{tail}")

    def replay(self, board: str, first: int, last: int, legacy: bool = False) -> list[str]:
        """Events first..last (inclusive, may wrap) still in memory; legacy = the
        form for clients without member numbers."""
        count = (last - first) % SEQ_MOD + 1
        wanted = {(first + i) % SEQ_MOD for i in range(min(count, 64))}
        return [(old if legacy else line) for seq, line, old in self._recent.get(board, ())
                if seq in wanted]

    # --- delivery -------------------------------------------------------

    def _line_of(self, board: str, ref: int) -> str:
        for seq, line, _old in self._recent.get(board, ()):
            if seq == ref:
                text = line.split(" ", 1)[1] if " " in line else ""
                return text if ":" in text.split(" ", 1)[0] else ""
        return ""

    def _next_event(self, board: str, payload: str, legacy: str | None = None) -> tuple[str, str]:
        seq = (self._seq.get(board, -1) + 1) % SEQ_MOD
        self._seq[board] = seq
        line = f"#{seq:X} {payload}"
        old = f"#{seq:X} {legacy}" if legacy is not None else line
        self._recent.setdefault(board, deque(maxlen=SEQ_MOD)).append((seq, line, old))
        return line, old

    def _deliver(self, board: str, payload: str, human: str | None, sender: Session,
                 legacy: str | None = None) -> None:
        """human None: an event only for clients (terminals get nothing).
        legacy: the same event with calls instead of member numbers, for clients
        without the NUM cap - they get it as I-frame even in UI mode (the UI
        frame carries the new form, which they cannot read)."""
        line, old = self._next_event(board, payload, legacy)
        members = self.members(board)
        ui_clients = [s for s in members if s.client and s.client.ui]
        n = self.number(board)
        sent_ui = False
        if ui_clients and self.ui_send is not None and 1 <= n <= MAX_UI_BOARD:
            self.ui_send(f"{UI_DEST}-{n}", line)
            sent_ui = True
            seq = self._seq[board]
            for s in ui_clients:                # receive quote: they should hear it
                if s.ui_rx is not None:
                    s.ui_rx.sent(seq)
        for s in members:
            if s.client:
                mine = line if self._num_client(s) else old
                if not (sent_ui and s.client.ui and mine == line):
                    s.out(mine)            # clients get every event, also their own
            elif s is not sender and human is not None:   # a terminal shows what was typed
                s.out(human)

    def _send_raw(self, board: str, text: str, ui: bool = True) -> None:
        """A line outside the event sequence (no number, never resent) to the NUM
        clients of a board: once as UI frame, I-frame to the others.
        ui False: I-frames only."""
        members = [s for s in self.members(board) if self._num_client(s)]
        n = self.number(board)
        sent_ui = False
        if ui and any(s.client.ui for s in members) and self.ui_send is not None \
                and 1 <= n <= MAX_UI_BOARD:
            self.ui_send(f"{UI_DEST}-{n}", text)
            sent_ui = True
        for s in members:
            if not (sent_ui and s.client.ui):
                s.out(text)

    # --- link quality (PLANUNG.md 14.4) -----------------------------------

    QUALITY_MIN_SEC = 60        # at most one % event per board and minute
    QSTAT_MIN_SEC = 120         # at most one %Q line per board and two minutes (CR33)

    def quality_tick(self, service, now: float | None = None) -> None:
        """Called after each round of Direwolf queries: per board one % event with
        the bars of all stations that have link data - only if something changed.
        Then the %Q line with the numbers behind the bars (CR33), same rule but
        at most every two minutes, only to clients with member numbers."""
        import time
        now = time.monotonic() if now is None else now
        for b in self.boards:
            members = self.members(b.name)
            if not members or not any(s.client for s in members):
                continue
            items, legacy, stats, rated = [], [], [], False
            for s in members:
                if linkq.is_local(s):                    # AXUDP: no bars for a local station
                    continue
                r = linkq.result_for(service, s.call, s)
                n = self.member_no(b.name, s.call)
                if r is not None or s.call in service.links:
                    items.append(f"{n} {linkq.bar_code(r)}")
                    legacy.append(f"{s.call} {linkq.bar_code(r)}")
                if r is not None:
                    stats.append(self._qstat_item(n, r))
                    rated = rated or r.bars is not None
            if not items:
                continue
            text = "%" + " ".join(items)
            if text != self._q_text.get(b.name) \
                    and now - self._q_at.get(b.name, -1e9) >= self.QUALITY_MIN_SEC:
                self._q_text[b.name], self._q_at[b.name] = text, now
                self._deliver(b.name, text, None, sender=members[0],
                              legacy="%" + " ".join(legacy))
            if not stats or not any(self._num_client(s) for s in members):
                continue
            if not rated:                    # all bars still '?': only interim counts
                continue
            qs = "%Q " + ";".join(stats)
            if qs != self._qs_text.get(b.name) \
                    and now - self._qs_at.get(b.name, -1e9) >= self.QSTAT_MIN_SEC:
                self._qs_text[b.name], self._qs_at[b.name] = qs, now
                # alone in the board: only its own link - as I-frame to it, no UI broadcast
                self._send_raw(b.name, qs, ui=len(members) > 1)

    @staticmethod
    def _qstat_item(n: int, r: "linkq.Result") -> str:
        """One member in the %Q line (14.6): n bars out_frames out_retry in_frames
        rej_tx retry_rx rej_rx t1 bytes_new/100 bytes_retry/100 rx_sent rx_missed srt*10
        - window values, the client shows them like the sysop GUI."""
        rx = r.rx
        return " ".join(str(x) for x in (
            n, linkq.bar_code(r), r.out.frames, r.i_retry, r.inn.frames, r.rej_tx,
            r.retry_rx, r.rej_rx, r.t1, r.bytes_new // 100, r.bytes_retry // 100,
            rx.frames if rx else 0, rx.lost if rx else 0, round(r.srt * 10)))

    def quality_config(self) -> str:
        """For //OK of NUM clients: q=<window frames>/<minutes>/<min frames>/<steps>."""
        dw = self.cfg.direwolf
        steps = ",".join(f"{x:g}" for x in dw.quality_steps)
        return f"q={dw.quality_window_frames}/{dw.quality_window_min}/{dw.quality_min_frames}/{steps}"

    # --- housekeeping ---------------------------------------------------

    def purge(self) -> int:
        """Delete lines older than their board's keep time, and lines of
        boards that are gone or live now."""
        keep = {b.name: _iso_hours_ago(b.keep_hours) for b in self.boards if not b.live}
        n = self.store.chat_purge(keep)
        if n:
            log.info("chat: %s old line(s) deleted", n)
        m = self.images.purge()
        if m:
            log.info("chat: %s image(s) without a line deleted", m)
        return n
