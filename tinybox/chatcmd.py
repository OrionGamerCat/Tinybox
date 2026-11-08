"""User side of the chat: command C in the mailbox, and /commands inside a board.

Inside a board every line is chat text, except lines starting with "/":
    /Q  /EX  ^Z   back to the mailbox
    /W            who is in this board
    /L            list all boards
    /J board      change to another board
    /R n emoji    reaction to event #n (used by TinyBox clients)
    /H n          the last n stored lines (history on request, CR13)
    /H            help
    //...         client protocol (clientproto.py)

TinyBox clients (session.client set) get machine-readable lines instead
of the human headers - see clientproto.py. From such a session a bare
"C" or "C <board>" is not chat text but the mailbox command of a client
that has lost track of where it is: it is answered, not broadcast.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from prcore.profile import short as profile_short

from . import clientnews, clientproto, texts
from .config import ChatBoard

if TYPE_CHECKING:
    from .session import Session

CTRL_Z = "\x1a"
# "C" or "C <board>" from a client session: the mailbox command, sent into a
# board by a client that lost track of where it is (see resync_client).
CHAT_CMD_RE = re.compile(r"(?i)^C(?:\s+(\w{1,16}))?$")
# A chat line is text. Control characters mean binary data ended up here (e.g.
# the rest of an image upload after a line slipped into the byte stream, CR12):
# such a line is dropped, never sent on to everybody in the board.
CTRL_CHARS = ({chr(c) for c in range(0x20)} | {chr(0x7F)}) - {"\t", CTRL_Z}
C1_CHARS = {chr(c) for c in range(0x80, 0xA0)}


def looks_binary(text: str) -> bool:
    if any(c in CTRL_CHARS for c in text):
        return True
    return len(text) > 4 and sum(c in C1_CHARS for c in text) > len(text) // 5


def _time(iso: str) -> str:
    """2026-10-04T14:32:05Z -> 10-04 14:32"""
    return f"{iso[5:10]} {iso[11:16]}"


def list_boards(s: Session) -> None:
    hub = s.service.chat
    rows = [texts.CHAT_LIST_HEADER]
    for i, b in enumerate(hub.boards, 1):
        rows.append(texts.CHAT_LIST_ROW.format(n=i, board=b.name, keep=b.keep_label,
                                               users=len(hub.members(b.name)),
                                               desc=b.description))
    s.out(*rows, texts.CHAT_LIST_FOOT)


def cmd_chat(s: Session, arg: str) -> None:
    """Mailbox command C [board]: without a board, list the boards."""
    hub = s.service.chat
    if not hub.enabled:
        s.out(texts.CHAT_OFF)
        return
    if s.origin == "sysop":       # the chat is for users on radio/telnet only
        s.out(texts.CHAT_NOT_CONSOLE)
        return
    if not arg:
        list_boards(s)
        return
    board = hub.find(arg)
    if board is None:
        s.out(texts.CHAT_NO_BOARD.format(board=arg.upper()))
        return
    enter(s, board)


def _epoch(iso: str) -> int:
    return int(datetime.strptime(iso, "%Y-%m-%dT%H:%M:%SZ")
               .replace(tzinfo=timezone.utc).timestamp())


# clients from this version on ask for the history themselves (//HIST)
HIST_CLIENT = "2026.10.11.3"


def history_rows(lines, seq: bool = False) -> list[str]:
    """//H lines. seq (client cap HSEQ): with the event number of the line,
    "//H <unix> #<n hex> <call>: <text>" - so a client shows the text of a quote
    ("~^5 ...") whose line it has only from the history. Lines stored before
    schema 10 have no number and come without it."""
    return [f"//H {_epoch(c.created)} "
            + (f"#{c.seq:X} " if seq and c.seq is not None else "")
            + f"{c.call}: {c.text}" for c in lines]


def _board_lines(s: Session, board: ChatBoard) -> list[str]:
    """//IN (plus //WHO) for a client: which board it is in and what the board
    offers. The caller decides whether a join belongs with it."""
    hub = s.service.chat
    count, last = hub.history_info(board)
    hist = f" hist={count}" + (f" last={_epoch(last)}" if last else "")
    hist += f" now={int(datetime.now(timezone.utc).timestamp())}"   # the client's clock may be off
    if board.motd:                # CR3: only a check value, the text on request (//MOTD)
        hist += f" motd={board.motd_crc}"
    limit = hub.cfg.chat.image_limit(board)        # CR12: images allowed here?
    if "IMG" in s.client.caps and limit:
        hist += " img" if limit == 8192 else f" img={limit:x}"
    lines = [f"//IN {hub.number(board.name)} {board.name} {board.keep_label} "
             f"{hub.last_seq(board.name)}{hist}"]
    if clientnews.version_key(s.client.version) < clientnews.version_key(HIST_CLIENT):
        lines += history_rows(hub.history(board))       # older client: as before
    lines.append(hub.who_line(board.name, s))      # CR33: with member numbers (NUM)
    return lines


def _enter_client(s: Session, board: ChatBoard) -> None:
    from .session import State
    hub = s.service.chat
    if s.chat_board is not None:
        hub.leave(s)                  # the //WHO below is without us
    lines = _board_lines(s, board)
    s.state = State.CHAT
    s.out(*lines)
    hub.join(s, board)            # the join event follows the //WHO line


def resync_client(s: Session) -> bool:
    """The client is back on a session that never left the board: tell it where
    it is. Only //IN and //WHO go out, nothing to the other members - the
    station is still a member, so there is no leave and no join to announce.
    //WHO therefore has our own call in it (with the member number, CR33)."""
    if s.client is None or s.chat_board is None:
        return False
    hub = s.service.chat
    board = hub.cfg.chat.board(s.chat_board)
    if board is None:
        return False
    hub.rebind(s)                 # the new caps decide about the receive window
    s.out(*_board_lines(s, board))
    return True


def _history(s: Session, n: int) -> None:
    """/H n: the last n stored lines of the board (terminal users)."""
    hub = s.service.chat
    board = hub.cfg.chat.board(s.chat_board or "")
    if board is None:
        return
    lines, _ = hub.history_page(board, n)
    if not lines:
        s.out(texts.CHAT_HISTORY_NONE.format(keep=board.keep_label))
        return
    s.out(texts.CHAT_HISTORY.format(keep=board.keep_label),
          *[texts.CHAT_HISTORY_ROW.format(time=_time(c.created), call=c.call,
                                          text=hub.readable(board.name, c.text, live=False))
            for c in lines],
          texts.CHAT_HISTORY_END)


def enter(s: Session, board: ChatBoard) -> None:
    from .session import State  # local import avoids a cycle
    hub = s.service.chat
    if s.client is not None:
        _enter_client(s, board)
        return
    lines = [texts.CHAT_HEADER.format(board=board.name, desc=board.description,
                                      keep=board.keep_label)]
    if board.motd:
        lines.append(texts.CHAT_MOTD.format(text=board.motd))
    if board.live:
        lines.append(texts.CHAT_LIVE_NOTE)
    else:
        count, last = hub.history_info(board)
        if count:                  # no history unasked (CR13), only how much there is
            lines.append(texts.CHAT_HISTORY_STORED.format(
                n=count, last=f"{last[:10]} {last[11:16]}"))
            lines.append(texts.CHAT_HISTORY_ASK)
        else:
            lines.append(texts.CHAT_HISTORY_NONE.format(keep=board.keep_label))
    hub.join(s, board)
    lines.append(_who_line(s))
    lines.append(texts.CHAT_HINT)
    s.state = State.CHAT
    s.out(*lines)


def _who_line(s: Session) -> str:
    """'In this board: OE3ABC (Hans, JN88), OE3XYZ' - with name and locator
    of the profile, where the station gave one (CR73)."""
    from .addressing import base_call
    others = [m.call for m in s.service.chat.members(s.chat_board or "") if m is not s]
    if not others:
        return texts.CHAT_ALONE
    known = s.service.store.profiles_get(sorted({base_call(c) for c in others}))
    calls = []
    for c in others:
        extra = profile_short(known.get(base_call(c)))
        calls.append(f"{c} ({extra})" if extra else c)
    return texts.CHAT_WHO.format(calls=", ".join(calls))


def _quit(s: Session) -> None:
    from .session import State
    board = s.chat_board
    s.service.chat.leave(s)
    s.state = State.COMMAND
    s.out(f"//OUT {board}" if s.client else texts.CHAT_BACK.format(board=board))


def handle(s: Session, line: str) -> None:
    """One input line while in a board."""
    hub = s.service.chat
    if looks_binary(line):
        import logging
        logging.getLogger(__name__).warning(
            "%s: chat line with control characters dropped (%d bytes)", s.call,
            len(line.encode("utf-8", "replace")))
        return
    if s.chat_board is None or hub.cfg.chat.board(s.chat_board) is None:
        _quit(s)
        return
    if CTRL_Z in line:
        text = line.split(CTRL_Z, 1)[0].strip()
        if text and not looks_binary(text):
            hub.say(s, text[:hub.cfg.chat.max_line])
        _quit(s)
        return
    text = line.strip()
    if not text:
        return
    if text.startswith("//"):
        clientproto.handle(s, text)
        return
    if s.client is not None and (m := CHAT_CMD_RE.match(text)):
        # A client does not mean "C <n>" as chat text: an older one that has
        # restarted on a link that stayed up does not know it is still in a
        # board and sends the mailbox command into it. Do what it meant - and
        # above all do not put it in front of everybody in the board.
        board = hub.find(m.group(1)) if m.group(1) else None
        if board is not None and board.name != s.chat_board:
            enter(s, board)
        else:
            resync_client(s)
        return
    if text.startswith("/"):
        cmd, _, arg = text[1:].partition(" ")
        cmd = cmd.upper()
        if cmd in ("Q", "QUIT", "EX", "B"):
            _quit(s)
        elif cmd in ("W", "WHO"):
            s.out(_who_line(s))
        elif cmd in ("L", "LIST"):
            list_boards(s)
        elif cmd in ("J", "JOIN"):
            board = hub.find(arg) if arg.strip() else None
            if board is None:
                s.out(texts.CHAT_NO_BOARD.format(board=arg.strip().upper() or "?"))
            elif board.name == s.chat_board:
                s.out(texts.CHAT_ALREADY.format(board=board.name))
            else:
                enter(s, board)
        elif cmd in ("R", "REACT"):
            ref, _, emoji = arg.strip().partition(" ")
            ok = False
            try:
                ok = hub.react(s, int(ref, 16), emoji.strip())
            except ValueError:
                pass
            if not ok:
                s.out("//ERR react" if s.client else texts.CHAT_UNKNOWN)
        elif cmd in ("H", "HELP", "?") and arg.strip().isdigit():
            _history(s, int(arg.strip()))
        elif cmd in ("H", "HELP", "?"):
            s.out(*texts.CHAT_HELP)
        else:
            s.out(texts.CHAT_UNKNOWN)
        return
    if len(text) > hub.cfg.chat.max_line:
        text = text[:hub.cfg.chat.max_line]
        s.out(texts.CHAT_CUT.format(max=hub.cfg.chat.max_line))
    if s.client is not None:          # CR12: an image reference must name an upload
        reason = hub.images.check_line(s, text)
        if reason:
            s.out(f"//ERR img {reason}")
            return
    hub.say(s, text)
