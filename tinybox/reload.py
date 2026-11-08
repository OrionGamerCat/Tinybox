"""RELOAD (CR82): read tinybox.conf again without disconnecting anybody.

Only values that can change while TinyBox runs are taken over; everything
else (calls, radio, ports, adapters switched on or off) stays as it is and is
listed as "needs RESTART". The running configuration objects are changed in
place, so every part of TinyBox that holds a reference to them sees the new
values at once.

Rules, section by section (attribute names of config.Config):

  station   haddress, qth, freq, locator, sysop_via_radio      - rest: RESTART
  mailbox   everything (max_users also in the session registry)
  logging   level, debug, keep_days                            - rest: RESTART
  brocast   everything but publish
  inbox     poll_sec                                           - rest: RESTART
  beacon    everything (enabled starts / stops the beacon)
  update    announce                                           - check: RESTART
  client    everything
  chat      history_lines, max_line, image_max                 - enabled: RESTART
  boards    new boards (at the end) and changed ones; removed boards and a
            new order need a RESTART (the clients know the boards by number)
  rubrics   everything
  forward   bid_days, aliases, publish_to_brocast and the partners (new,
            changed, removed); enabled, listen_host, listen_port: RESTART
  all other sections (agw, radio, kiss, ax25, telnet, axudp, web, console,
  storage, mqtt): RESTART
"""

from __future__ import annotations

import asyncio
import dataclasses
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from prcore import aprs

from . import config

log = logging.getLogger(__name__)

ALL = "*"

# attribute of Config -> the fields taken over at runtime (ALL = every field)
LIVE: dict[str, Any] = {
    "station": {"haddress", "qth", "freq", "locator", "sysop_via_radio"},
    "mailbox": ALL,
    "logging": {"level", "debug", "keep_days"},
    "brocast": ALL,                 # but publish, see NOT_LIVE
    "inbox": {"poll_sec"},
    "beacon": ALL,
    "update": {"announce"},
    "client": ALL,
    "chat": {"history_lines", "max_line", "image_max"},
    "forward": {"bid_days", "aliases", "publish_to_brocast"},
}
NOT_LIVE = {("brocast", "publish")}

# attribute of Config -> section name in tinybox.conf
SECTION = {"direwolf": "agw"}
# (attribute, field) -> key name in tinybox.conf where it differs
KEY = {
    ("direwolf", "agw_host"): "host", ("direwolf", "agw_port"): "port",
    ("direwolf", "agw_radio_port"): "channel", ("inbox", "directory"): "dir",
    ("brocast", "ingest_host"): "ingest_url (host)",
    ("brocast", "ingest_port"): "ingest_url (port)",
    ("brocast", "ingest_path"): "ingest_url (path)",
}
# Config fields that are no section of their own (bookkeeping of load())
SKIP = {"path", "sources", "hints", "kiss_fixed"}
SECRET_WORDS = ("token", "password", "secret", "login")


@dataclass
class Change:
    where: str            # "[beacon] interval_min"
    old: str
    new: str

    def line(self, width: int = 32) -> str:
        if self.old == "":                    # a secret: only that it changed
            return f"  {self.where:<{width}} {self.new}"
        return f"  {self.where:<{width}} {self.old} -> {self.new}"


@dataclass
class Result:
    changed: list[Change] = field(default_factory=list)
    ignored: list[Change] = field(default_factory=list)
    hints: list[str] = field(default_factory=list)

    def lines(self) -> list[str]:
        if not self.changed and not self.ignored:
            out = ["RELOAD: no changes in tinybox.conf."]
        else:
            width = max(len(c.where) for c in self.changed + self.ignored)
            width = min(max(width, 20), 40)
            out = ["RELOAD tinybox.conf"]
            out.append("changed:" if self.changed else "changed: nothing")
            out += [c.line(width) for c in self.changed]
            if self.ignored:
                out.append("needs RESTART (ignored):")
                out += [c.line(width) for c in self.ignored]
        out += [f"hint: {h}" for h in self.hints]
        return out


# --- formatting --------------------------------------------------------------------

def fmt(value: Any) -> str:
    if value is None:
        return "-"
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, (list, tuple, frozenset, set)):
        items = sorted(value) if isinstance(value, (frozenset, set)) else value
        return ", ".join(fmt(x) for x in items) if items else "(empty)"
    if isinstance(value, dict):
        return ", ".join(f"{k}:{fmt(v)}" for k, v in value.items()) if value else "(empty)"
    if dataclasses.is_dataclass(value):
        return ", ".join(f"{f.name}={fmt(getattr(value, f.name))}"
                         for f in dataclasses.fields(value))
    text = str(value)
    return text if text != "" else "(empty)"


def _secret(name: str) -> bool:
    return any(w in name.lower() for w in SECRET_WORDS)


def _change(where: str, key: str, old: Any, new: Any) -> Change:
    """Passwords, tokens and login lines never in clear text."""
    if _secret(key):
        return Change(where, "", "(changed)")
    return Change(where, fmt(old), fmt(new))


def _where(attr: str, key: str) -> str:
    return f"[{SECTION.get(attr, attr)}] {KEY.get((attr, key), key)}"


# --- compare -----------------------------------------------------------------------

def _is_live(attr: str, key: str) -> bool:
    live = LIVE.get(attr)
    if live is None or (attr, key) in NOT_LIVE:
        return False
    return live == ALL or key in live


def _section(attr: str, old: Any, new: Any, res: Result, todo: list) -> None:
    """One dataclass section, field by field."""
    for f in dataclasses.fields(old):
        key = f.name
        if attr == "chat" and key == "boards":
            continue                                   # _boards()
        if attr == "forward" and key == "partners":
            continue                                   # _partners()
        a, b = getattr(old, key), getattr(new, key)
        if a == b:
            continue
        ch = _change(_where(attr, key), key, a, b)
        if _is_live(attr, key):
            res.changed.append(ch)
            todo.append((old, key, b))
        else:
            res.ignored.append(ch)


BOARD_FIELDS = ("keep_hours", "description", "noimg", "motd")


def _keep(hours: int) -> str:
    return config.ChatBoard("X", hours).keep_label


def _boards(old: list, new: list, res: Result, todo: list) -> None:
    """Chat boards: the clients know them by number (TBCHAT-n), so only new
    boards at the end and changes of existing ones go live."""
    old_by = {b.name: b for b in old}
    new_by = {b.name: b for b in new}
    for b in new:
        o = old_by.get(b.name)
        if o is None:
            continue
        for key in BOARD_FIELDS:
            a, n = getattr(o, key), getattr(b, key)
            if a == n:
                continue
            if key == "motd":
                where, a_s, n_s = f"[chat_motd] {b.name}", fmt(a), fmt(n)
            else:
                where = f"[chat_boards] {b.name} {key.replace('_hours', '')}"
                a_s, n_s = (_keep(a), _keep(n)) if key == "keep_hours" else (fmt(a), fmt(n))
            res.changed.append(Change(where, a_s, n_s))
            todo.append((o, key, n))
    added = [b for b in new if b.name not in old_by]
    for b in added:
        res.changed.append(Change(f"[chat_boards] {b.name}", "-",
                                  f"new ({b.keep_label})"))
        todo.append(("append", old, b))
    for b in old:
        if b.name not in new_by:
            res.ignored.append(Change(f"[chat_boards] {b.name}", b.keep_label, "removed"))
    common_old = [b.name for b in old if b.name in new_by]
    common_new = [b.name for b in new if b.name in old_by]
    if common_old != common_new:
        res.ignored.append(Change("[chat_boards] order", ", ".join(common_old),
                                  ", ".join(common_new)))


def _rubrics(old: list, new: list, res: Result, todo: list) -> None:
    old_by = {r.name: r for r in old}
    new_by = {r.name: r for r in new}
    for r in new:
        o = old_by.get(r.name)
        if o is None:
            res.changed.append(Change(f"[rubrics] {r.name}", "-", "new"))
        elif o != r:
            for f in dataclasses.fields(r):
                a, b = getattr(o, f.name), getattr(r, f.name)
                if a != b:
                    res.changed.append(Change(f"[rubrics] {r.name} {f.name}", fmt(a), fmt(b)))
    for r in old:
        if r.name not in new_by:
            res.changed.append(Change(f"[rubrics] {r.name}", "-", "removed"))
    if [dataclasses.astuple(r) for r in old] != [dataclasses.astuple(r) for r in new]:
        todo.append(("replace_list", old, new))


def _partners(old: dict, new: dict, res: Result, todo: list) -> None:
    for call, p in new.items():
        o = old.get(call)
        if o is None:
            res.changed.append(Change(f"[partner.{call}]", "-", "new"))
            continue
        for f in dataclasses.fields(p):
            a, b = getattr(o, f.name), getattr(p, f.name)
            if a != b:
                res.changed.append(_change(f"[partner.{call}] {f.name}", f.name, a, b))
    for call in old:
        if call not in new:
            res.changed.append(Change(f"[partner.{call}]", "-", "removed"))
    if old != new:
        todo.append(("replace_dict", old, new))


def compare(cur: config.Config, new: config.Config) -> tuple[Result, list]:
    """What changed between the running and the new configuration, and the
    steps to take the live part over (nothing is changed here)."""
    res, todo = Result(), []
    for f in dataclasses.fields(cur):
        attr = f.name
        if attr in SKIP:
            continue
        a, b = getattr(cur, attr), getattr(new, attr)
        if attr == "rubrics":
            _rubrics(a, b, res, todo)
        elif dataclasses.is_dataclass(a) and dataclasses.is_dataclass(b):
            _section(attr, a, b, res, todo)
            if attr == "chat":
                _boards(a.boards, b.boards, res, todo)
            elif attr == "forward":
                _partners(a.partners, b.partners, res, todo)
        elif a != b:                                  # e.g. brocast None -> set
            res.ignored.append(Change(f"[{SECTION.get(attr, attr)}]", fmt(a), fmt(b)))
    res.hints = [h for h in (new.hints or []) if h not in (cur.hints or [])]
    return res, todo


# --- apply -------------------------------------------------------------------------

def _apply(todo: list) -> None:
    for step in todo:
        if step[0] == "append":
            step[1].append(step[2])
        elif step[0] == "replace_list":
            step[1][:] = step[2]
        elif step[0] == "replace_dict":
            step[1].clear()
            step[1].update(step[2])
        else:
            obj, key, value = step
            object.__setattr__(obj, key, value)


def _after(app, res: Result) -> None:
    """Parts that copied a value when they started."""
    cfg = app.cfg
    touched = {c.where.split("]")[0] + "]" for c in res.changed}
    app.registry.max_users = cfg.mailbox.max_users
    if "[logging]" in touched and app.log_control is not None:
        _logging(app.log_control, cfg.logging)
    if "[station]" in touched:                 # CR55: distance in the APRS monitor line
        from . import framemon
        try:
            framemon.home = (aprs.locator_to_latlon(cfg.station.locator)
                             if cfg.station.locator else None)
        except Exception:                      # a bad locator: no distance, as at the start
            framemon.home = None
    fwd = getattr(app, "forward", None)
    if fwd is not None:
        if "[station]" in touched or "[forward]" in touched:
            from .fwd.router import Router
            fwd.router = Router(fwd.cfg, cfg.station.address)
        if any(t.startswith("[partner.") for t in touched):
            fwd._wake()
        if "[rubrics]" in touched:
            released, deleted = fwd.resolve_rubrics()
            if released or deleted:
                res.changed.append(Change(
                    "[rubrics] held bulletins", "",
                    f"{released} released, {deleted} deleted"))
    if "[beacon]" in touched:
        _beacon(app, any(c.where.startswith("[beacon] interval_min") for c in res.changed))


def _logging(control, lc) -> None:
    import logging as _l
    control.level = lc.level
    for flt in (control.file_filter, control.console_filter):
        if flt is not None:
            flt.level = _l.getLevelName(lc.level)
            flt.debug = set(lc.debug)
    if control.handler is not None:
        control.handler.keep_days = lc.keep_days
    control._sync_root_level()


def _beacon(app, new_interval: bool) -> None:
    """[beacon] enabled starts or stops the beacon task. A new interval_min starts
    it again (else the old interval runs out first); text, path etc. the running
    beacon reads each time."""
    task = getattr(app, "beacon_task", None)
    running = task is not None and not task.done()
    if running and (not app.cfg.beacon.enabled or new_interval):
        task.cancel()
        app.beacon_task, running = None, False
    if app.cfg.beacon.enabled and not running and getattr(app, "beacon", None) is not None:
        app.beacon_task = asyncio.get_running_loop().create_task(app.beacon.run())


def reload(app) -> Result:
    """Read app.config_path again and take over what may change at runtime.
    Raises config.ConfigError (then nothing is changed)."""
    if not app.config_path:
        raise config.ConfigError("no tinybox.conf known (started without -c?)")
    new = config.load(app.config_path)
    res, todo = compare(app.cfg, new)
    _apply(todo)
    _after(app, res)
    for line in res.lines():
        log.info("%s", line)
    return res
