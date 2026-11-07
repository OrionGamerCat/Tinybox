"""Mailbox commands. Each command gets the session and its argument string."""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING, Callable

from prcore.profile import CALL_RE as BASE_CALL_RE, ProfileError

from . import addressing, chatcmd, dictfile, linkq, profiles, texts
from .service import ServiceError
from .store import Message

if TYPE_CHECKING:
    from .session import Session

CMD_RE = re.compile(r"^\s*([A-Za-z?]+)\s*(.*?)\s*$")
# S/SP/SB arguments:  call [@ address] [$BID]   ("call@address" works too)
SEND_RE = re.compile(r"^(?P<to>[^\s@$]+)\s*(?:@\s*(?P<at>[^\s$]+))?\s*(?:\$(?P<bid>\S+))?$")
log = logging.getLogger(__name__)


def _yymmdd(iso: str) -> str:
    return iso[2:4] + iso[5:7] + iso[8:10]


def _numbers(arg: str) -> list[int] | None:
    parts = arg.replace(",", " ").split()
    if not parts or not all(p.isdigit() for p in parts):
        return None
    return [int(p) for p in parts]


def _list(s: Session, msgs: list[Message]) -> None:
    if not msgs:
        s.out(texts.NO_MESSAGES)
        return
    rows = [texts.LIST_HEADER]
    for m in msgs:
        rows.append(texts.LIST_ROW.format(
            id=m.id, type=m.type, status=m.status, fwd=m.fwd or " ", size=m.size,
            to=m.to_call, at=addressing.addr_call(m.at_addr), frm=m.from_call,
            date=_yymmdd(m.created), time=m.created[11:16], subject=m.subject[:30]))
    s.out(*rows)


def _show(s: Session, m: Message) -> None:
    head = [line.format(id=m.id, type=m.type, status=m.status, fwd=m.fwd, bid=m.bid or "-",
                        frm=m.from_call, to=m.to_call,
                        at=f" @ {m.at_addr}" if m.at_addr else "",
                        date=m.created.replace("T", " "),
                        subject=m.subject) for line in texts.READ_HEADER]
    if m.fwd == "H" and m.note:
        head.insert(-1, texts.HELD_NOTE.format(note=m.note))
    rl = m.rline_list
    s.out(*head, *rl, *([""] if rl else []), *m.body.split("\n"),
          texts.READ_END.format(id=m.id))


# --- commands ---------------------------------------------------------------

def cmd_abort(s: Session, arg: str) -> None:
    s.transport.abort_output()
    s.out(texts.ABORTED)


def cmd_bye(s: Session, arg: str) -> None:
    s.out(texts.BYE)
    s.close()


def cmd_help(s: Session, arg: str) -> None:
    s.out(*texts.HELP, *(texts.HELP_SYSOP if s.sysop else []))


def cmd_jlog(s: Session, arg: str) -> None:
    entries = s.service.store.jlog_list()
    if not entries:
        s.out(texts.JLOG_EMPTY)
        return
    s.out(texts.JLOG_HEADER, *[
        texts.JLOG_ROW.format(call=e.call, last=e.last_seen[:16].replace("T", " "),
                              count=e.count) for e in entries])


QSO_DEFAULT, QSO_MAX = 10, 100


def cmd_qso(s: Session, arg: str) -> None:
    """CR44: the connection log. Everybody sees his own connects (all SSIDs of
    his call); the sysop also QSO ALL and QSO <call>."""
    from .connlog import base_call, duration, kb
    words = arg.upper().split()
    base, n, which = base_call(s.call), QSO_DEFAULT, ""
    if words and not words[0].isdigit():
        if not s.sysop:
            s.out(texts.USAGE_QSO)
            return
        which = words[0]
        base = None if which in ("ALL", "ALLE") else base_call(which)
        words = words[1:]
    if words:
        if not words[0].isdigit() or len(words) > 1:
            s.out(texts.USAGE_QSO)
            return
        n = max(1, min(QSO_MAX, int(words[0])))
    rows = s.service.store.connlog_list(base, n + 1)
    if not rows:
        s.out(texts.QSO_EMPTY)
        return
    more = len(rows) > n and n < QSO_MAX
    lines = [texts.QSO_ROW.format(start=r["start"][:16].replace("T", " "),
                                  dur=duration(r["secs"]), call=r["call"], via=r["via"],
                                  rx=kb(r["rx"]), tx=kb(r["tx"]),
                                  ended=" lost" if r["ended"] == "lost" else "")
             for r in rows[:n]]
    nxt = f"{which} {min(QSO_MAX, n * 2)}".strip()
    s.out(texts.QSO_HEADER, *lines, *([texts.QSO_MORE.format(next=nxt)] if more else []))


def cmd_find(s: Session, arg: str) -> None:
    """CR49: F text - messages (personal ones of your own, bulletins) that contain text
    in the subject, the text, a call or the @address."""
    text = arg.strip()
    if len(text) < s.service.SEARCH_MIN:
        s.out(texts.USAGE_FIND)
        return
    msgs = s.service.search(s.call, s.sysop, text)
    if not msgs:
        s.out(texts.FIND_NONE.format(text=text))
        return
    s.out(texts.FIND_COUNT.format(n=len(msgs), text=text))
    _list(s, msgs)


def cmd_kill(s: Session, arg: str) -> None:
    ids = _numbers(arg)
    if ids is None:
        s.out(texts.USAGE_K)
        return
    for msg_id in ids:
        try:
            s.service.delete(msg_id, s.call, s.sysop)
            s.out(texts.KILLED.format(id=msg_id))
        except ServiceError as exc:
            s.error(exc, msg_id)


def cmd_kill_mine(s: Session, arg: str) -> None:
    ids = s.service.kill_mine(s.call)
    if not ids:
        s.out(texts.KILLED_NONE)
    for msg_id in ids:
        s.out(texts.KILLED.format(id=msg_id))


def cmd_list(s: Session, arg: str) -> None:
    """L, L@ area, L> call, L< call"""
    msgs = s.service.list_for(s.call, s.sysop)
    arg = arg.strip().upper()
    if arg[:1] in ("@", ">", "<"):
        op, value = arg[0], arg[1:].strip()
        if not value:
            s.out(texts.UNKNOWN_CMD)
            return
        if op == "@":
            msgs = [m for m in msgs if value in addressing.parts(m.at_addr)
                    or addressing.addr_call(m.at_addr) == addressing.base_call(value)]
        elif op == ">":
            msgs = [m for m in msgs if m.to_call == value]
        else:
            msgs = [m for m in msgs if m.from_call == value]
    _list(s, msgs)


def cmd_list_bulletins(s: Session, arg: str) -> None:
    _list(s, [m for m in s.service.list_for(s.call, s.sysop) if m.type == "B"])


def cmd_list_private(s: Session, arg: str) -> None:
    _list(s, [m for m in s.service.list_for(s.call, s.sysop) if m.type == "P"])


def cmd_list_mine(s: Session, arg: str) -> None:
    _list(s, s.service.list_for(s.call, s.sysop, mine=True))


def cmd_read(s: Session, arg: str) -> None:
    ids = _numbers(arg)
    if ids is None:
        s.out(texts.USAGE_R)
        return
    for msg_id in ids:
        try:
            _show(s, s.service.read(msg_id, s.call, s.sysop))
        except ServiceError as exc:
            s.error(exc, msg_id)


def cmd_read_mine(s: Session, arg: str) -> None:
    msgs = s.service.unread_for(s.call)
    if not msgs:
        s.out(texts.NO_NEW_MSGS)
    for m in reversed(msgs):  # oldest first
        _show(s, s.service.read(m.id, s.call, s.sysop))


def _send(s: Session, arg: str, type: str) -> None:
    m = SEND_RE.match(arg.strip())
    if not arg or m is None:
        s.out(texts.USAGE_S)
        return
    try:
        to_calls = s.service.check_send_list(s.call, m.group("to"), type, s.sysop,
                                             m.group("bid"))
        at_addr, bid = s.service.check_address(type, m.group("at") or "", m.group("bid"),
                                               s.origin)
    except ServiceError as exc:
        s.error(exc)
        return
    s.begin_send(to_calls, type, at_addr, bid)


def cmd_send(s: Session, arg: str) -> None:
    _send(s, arg, "P")


def cmd_send_bulletin(s: Session, arg: str) -> None:
    _send(s, arg, "B")


def cmd_version(s: Session, arg: str) -> None:
    mode = (texts.VERSION_FWD.format(address=s.cfg.station.address)
            if s.cfg.forward.enabled else texts.VERSION_LOCAL)
    s.out(texts.VERSION_TEXT.format(mode=mode))


def cmd_dict(s: Session, arg: str) -> None:
    """Send the brocast dictionary as framed ASCII text (see dictfile.py)."""
    path = s.cfg.brocast.dict_file if s.cfg.brocast else None
    if path is None:
        s.out(texts.DICT_NONE)
        return
    try:
        d = dictfile.prepare(path)
    except dictfile.DictError as exc:
        log.warning("DICT: %s", exc)
        s.out(texts.DICT_NONE)
        return
    log.info("%s: DICT v%s (%s lines) sent", s.call, d.version, len(d.lines))
    s.out(texts.DICT_INTRO.format(version=d.version, lines=len(d.lines)))
    s.flush_output()                  # the dictionary is machine-read: no abort hint (CR40)
    # write directly: 200+ lines would flood the monitor log otherwise
    s.transport.write("\r".join(d.framed()) + "\r")
    s.out(texts.DICT_DONE)


def _stat_row(call: str, r: "linkq.Result") -> str:
    pct = lambda d: "-" if d is None or d.loss is None else f"{d.loss:.0f}%"   # noqa: E731
    rxq = r.rx_quote
    return texts.STAT_ROW.format(
        call=call, bars=linkq.bar_text(r.bars, r.tentative), out=pct(r.out), inn=pct(r.inn),
        retry=r.i_retry, rej_rx=r.rej_rx, rej_tx=r.rej_tx, t1=r.t1,
        net=f"{linkq.kbytes(r.bytes_new)}/{linkq.kbytes(r.bytes_retry)}",
        rxq="-" if rxq is None else f"{rxq:.0f}%",
        srt=f"{r.srt:.1f}s" if r.srt else "-")


def cmd_stat(s: Session, arg: str) -> None:
    """Link quality (PLANUNG.md 14.4): STAT = own link, STAT ALL = all stations
    with data (radio links via Direwolf, TinyBox clients in UI mode)."""
    which = arg.strip().upper()
    if which not in ("", "ALL", "ALLE"):
        s.out(texts.STAT_USAGE)
        return
    hub = s.service.chat
    in_chat = {m.call: m for b in hub.boards for m in hub.members(b.name)}
    if which:
        calls = sorted(set(s.service.links) | {c for c, m in in_chat.items() if m.ui_rx})
    else:
        calls = [s.call]
    rows = [(c, linkq.result_for(s.service, c, s if c == s.call else in_chat.get(c)))
            for c in calls]
    rows = [(c, r) for c, r in rows if r is not None]
    if not rows:
        s.out(texts.STAT_NOBODY if which else texts.STAT_NONE)
        return
    dw = s.cfg.direwolf
    s.out(texts.STAT_TITLE.format(frames=dw.quality_window_frames, minutes=dw.quality_window_min),
          texts.STAT_HEADER, *[_stat_row(c, r) for c, r in rows], *texts.STAT_LEGEND)


def cmd_edit(s: Session, arg: str) -> None:
    if not s.sysop:
        s.out(texts.NOT_ALLOWED)
        return
    parts = arg.split(None, 2)
    if len(parts) != 3 or not parts[0].isdigit():
        s.out(texts.USAGE_E)
        return
    msg_id = int(parts[0])
    try:
        s.service.edit(msg_id, parts[1], parts[2], s.call, s.sysop)
        s.out(texts.EDITED.format(id=msg_id))
    except ServiceError as exc:
        s.error(exc, msg_id)


# --- profile (CR73) ------------------------------------------------------------

def _show_profile(s: Session, call: str) -> None:
    p = profiles.get(s.service.store, call)
    base = addressing.base_call(call)
    if p is None:
        s.out(texts.PROFILE_NONE.format(call=base))
        return
    s.out(texts.PROFILE_SHOW.format(call=base, name=p["name"] or "-", loc=p["loc"] or "-",
                                    home=p["home"] or "-"))


def _set_profile(s: Session, field: str, arg: str) -> None:
    """N / NL / NH: without an argument the own profile, '-' clears the field."""
    if not arg:
        _show_profile(s, s.call)
        return
    try:
        value = "" if arg.strip() == "-" else profiles.check_field(field, arg)
    except ProfileError:
        s.out(texts.PROFILE_BAD[field])
        return
    profiles.save(s.service.store, s.call, {field: value})
    _show_profile(s, s.call)


def cmd_name(s: Session, arg: str) -> None:
    _set_profile(s, "name", arg)


def cmd_locator(s: Session, arg: str) -> None:
    _set_profile(s, "loc", arg)


def cmd_home(s: Session, arg: str) -> None:
    _set_profile(s, "home", arg)


def cmd_info(s: Session, arg: str) -> None:
    """I [call]: the profile of a station - everybody may see every profile."""
    words = arg.split()
    if len(words) > 1:
        s.out(texts.USAGE_I)
        return
    call = words[0].upper() if words else s.call
    if not BASE_CALL_RE.match(addressing.base_call(call)):
        s.out(texts.INVALID_CALL.format(call=call))
        return
    _show_profile(s, call)


COMMANDS: dict[str, Callable[[Session, str], None]] = {
    "A": cmd_abort,
    "B": cmd_bye,
    "BYE": cmd_bye,
    "C": chatcmd.cmd_chat,
    "CHAT": chatcmd.cmd_chat,
    "DICT": cmd_dict,
    "E": cmd_edit,
    "F": cmd_find,
    "FIND": cmd_find,
    "H": cmd_help,
    "?": cmd_help,
    "HELP": cmd_help,
    "I": cmd_info,
    "J": cmd_jlog,
    "K": cmd_kill,
    "KM": cmd_kill_mine,
    "L": cmd_list,
    "LB": cmd_list_bulletins,
    "LM": cmd_list_mine,
    "LP": cmd_list_private,
    "N": cmd_name,
    "NH": cmd_home,
    "NL": cmd_locator,
    "R": cmd_read,
    "RM": cmd_read_mine,
    "S": cmd_send,
    "SP": cmd_send,
    "SB": cmd_send_bulletin,
    "QSO": cmd_qso,
    "STAT": cmd_stat,
    "V": cmd_version,
}


def dispatch(s: Session, line: str) -> None:
    if not line.strip():
        return
    if line.lstrip().startswith("//"):      # TinyBox client protocol
        from . import clientproto
        clientproto.handle(s, line)
        return
    m = CMD_RE.match(line)
    if not m:
        s.out(texts.UNKNOWN_CMD)
        return
    handler = COMMANDS.get(m.group(1).upper())
    if handler is None:
        s.out(texts.UNKNOWN_CMD)
        return
    handler(s, m.group(2))
