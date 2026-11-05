"""Logging for TinyBox: one file per day, fixed columns, session context (CR32).

A line is meant to be readable by eye and with grep:

    2026-10-13 19:42:08.233 I session  #7 OE3TEC  < LIST

    time with ms | level (D I W E) | component | #session call | message

One file per calendar day, ``tinybox-2026-10-13.log``, always opened in append
mode: a restart appends instead of starting a new file, so cause and effect stay
together. The day change is a date comparison before writing - no renaming,
because Windows cannot rename a file that is open.
"""

from __future__ import annotations

import contextlib
import contextvars
import itertools
import logging
import os
import platform
import re
import sys
import time
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path

from prcore import termcolor

PREFIX = "tinybox-"             # tinybox-2026-10-13.log
SUFFIX = ".log"
MAX_BYTES = 20 * 1024 * 1024    # per day; then tinybox-2026-10-13.2.log
SLOW_MS = 50                    # below this a duration is not worth a line
PAYLOAD_CHARS = 40              # of message/chat content without DEBUG

LEVEL_LETTER = {logging.DEBUG: "D", logging.INFO: "I",
                logging.WARNING: "W", logging.ERROR: "E", logging.CRITICAL: "E"}

# logger name -> component column. Also the names for "LOG DEBUG <component>".
COMPONENT = {
    "tinybox": "core",
    "tinybox.__main__": "core",
    "tinybox.config": "core",
    "tinybox.shutdown": "core",
    "tinybox.logsetup": "core",
    "tinybox.monitor": "session",
    "tinybox.monitor.agw": "agw",
    "tinybox.session": "session",
    "tinybox.service": "svc",
    "tinybox.commands": "cmd",
    "tinybox.chat": "chat",
    "tinybox.chatcmd": "chat",
    "tinybox.chatimg": "chat",
    "tinybox.clientsync": "sync",
    "tinybox.clientnews": "news",
    "tinybox.clientproto": "sync",
    "tinybox.notify": "notify",
    "tinybox.events": "bus",
    "tinybox.linkq": "linkq",
    "tinybox.store": "store",
    "tinybox.forward": "fwd",
    "tinybox.adapters.agw": "agw",
    "tinybox.adapters.kiss": "kiss",
    "tinybox.monitor.kiss": "kiss",
    "prcore.kiss": "kiss",
    "prcore.ax25.link": "kiss",
    "prcore.kissport": "kiss",
    "tinybox.adapters.axudp": "axudp",
    "prcore.axudp": "axudp",
    "tinybox.adapters.telnet": "telnet",
    "tinybox.adapters.web": "web",
    "tinybox.adapters.brocast": "brocast",
    "tinybox.adapters.inbox": "inbox",
    "tinybox.adapters.sysop": "sysop",
    "tinybox.adapters.forward": "fwd",
}
COMPONENTS = sorted(set(COMPONENT.values()))


def component_of(name: str) -> str:
    """Component column for a logger name, also for names not in the table."""
    comp = COMPONENT.get(name)
    if comp is not None:
        return comp
    for prefix, comp in (("tinybox.fwd", "fwd"), ("tinybox.forward", "fwd"),
                         ("tinybox.monitor", "session")):
        if name.startswith(prefix):
            return comp
    return name.rsplit(".", 1)[-1][:8] or "core"


# --- session context ------------------------------------------------------
#
# Every line of a connection carries "#7 OE3TEC", also the lines written by
# store, chat and sync: grep "#7" then gives the connection from connect to
# disconnect, even with several stations at the same time.

NO_SESSION = "#0 -"
_ctx: contextvars.ContextVar[str] = contextvars.ContextVar("tinybox_ctx", default=NO_SESSION)
_session_ids = itertools.count(1)


def next_session_id() -> int:
    return next(_session_ids)


def seed_session_ids(above: int) -> None:
    """Continue the numbering above a number already used today. A restart
    appends to the same file, so #7 has to mean one connection in that file -
    not one per run."""
    global _session_ids
    if above > 0:
        _session_ids = itertools.count(above + 1)


def context() -> str:
    return _ctx.get()


@contextlib.contextmanager
def session_context(ctx: str):
    """Mark everything logged inside as belonging to this connection. A task
    started in here inherits the context, so later lines keep the number."""
    token = _ctx.set(ctx)
    try:
        yield
    finally:
        _ctx.reset(token)


_active: "LogControl | None" = None      # set by setup(), for debug_on()


def debug_on(comp: str) -> bool:
    """True while this component is switched to DEBUG (config or LOG DEBUG)."""
    if _active is None:
        return False
    debug = _active.debug
    return "all" in debug or comp in debug


def short(text: str, full: bool = False, chars: int = PAYLOAD_CHARS) -> str:
    """Content of mail and chat for the log: length plus the first characters.
    The file ends up in chats - other people's mail should not ride along."""
    if full:
        return repr(text)
    text = text.replace("\r", " ").replace("\n", " ")
    if len(text) <= chars:
        return f"{len(text)}c {text!r}"
    return f"{len(text)}c {text[:chars]!r}..."


def ms(t0: float) -> str:
    """Duration since a time.monotonic() mark, as '(312ms)' - that is where
    the time went. Over radio almost every bug is a timing problem."""
    return f"({int((time.monotonic() - t0) * 1000)}ms)"


def ms_if_slow(t0: float, limit: int = SLOW_MS) -> str:
    took = int((time.monotonic() - t0) * 1000)
    return f"({took}ms)" if took >= limit else ""


# --- counters (for the closing line) --------------------------------------


@dataclass
class Counters:
    sessions: int = 0
    frames_in: int = 0
    frames_out: int = 0
    bulletins_fwd: int = 0
    warnings: int = 0
    errors: int = 0
    started: float = field(default_factory=time.monotonic)

    def uptime(self) -> str:
        sec = int(time.monotonic() - self.started)
        if sec < 60:
            return f"{sec}s"
        if sec < 3600:
            return f"{sec // 60}m{sec % 60:02d}s"
        return f"{sec // 3600}h{sec % 3600 // 60:02d}m"

    def summary(self) -> str:
        return (f"{self.uptime()}, {self.sessions} sessions, "
                f"{self.frames_in}/{self.frames_out} frames in/out, "
                f"{self.bulletins_fwd} fwd, {self.warnings} warnings, {self.errors} errors")


counters = Counters()


# --- filters and formatter ------------------------------------------------


def annotate(record: logging.LogRecord) -> None:
    """The extra columns. The session context has to be read here, while the
    record is being handled - afterwards the connection may already be gone."""
    record.comp = component_of(record.name)
    record.ctx = getattr(record, "ctx", None) or _ctx.get()
    record.lvl = LEVEL_LETTER.get(record.levelno, "I")
    record.cctx = "" if record.ctx == NO_SESSION else record.ctx + "  "


class ContextFilter(logging.Filter):
    """Adds component, session context and the level letter to every record,
    and counts warnings and errors for the closing line."""

    def filter(self, record: logging.LogRecord) -> bool:
        annotate(record)
        # This filter sits on every handler, a record counts once (not per handler).
        if not getattr(record, "tb_counted", False):
            record.tb_counted = True
            if record.levelno >= logging.ERROR:
                counters.errors += 1
            elif record.levelno == logging.WARNING:
                counters.warnings += 1
        return True


class LevelFilter(logging.Filter):
    """The level, plus DEBUG for single components (LOG DEBUG agw).

    DEBUG everywhere drowns the file in monitor traffic, so it is switchable
    per component instead of all or nothing."""

    def __init__(self, level: str) -> None:
        super().__init__()
        self.level = logging.getLevelName(level) if isinstance(level, str) else level
        self.debug: set[str] = set()

    def filter(self, record: logging.LogRecord) -> bool:
        if record.levelno >= self.level:
            return True
        if record.levelno >= logging.DEBUG and self.debug:
            return "all" in self.debug or component_of(record.name) in self.debug
        return False


class Formatter(logging.Formatter):
    """The fixed columns of the log file."""

    def format(self, record: logging.LogRecord) -> str:
        if not hasattr(record, "lvl"):    # handler without the ContextFilter
            annotate(record)
        stamp = datetime.fromtimestamp(record.created).strftime("%Y-%m-%d %H:%M:%S")
        line = (f"{stamp}.{int(record.msecs):03d} {record.lvl} "
                f"{record.comp:<8} {record.ctx:<12} {record.getMessage()}")
        if record.exc_info:
            line += "\n" + self.formatException(record.exc_info)
        return line


# the session number in the context column of a written line
CTX_IN_LINE = re.compile(r"\d{4}-\d\d-\d\d \d\d:\d\d:\d\d\.\d{3} \w \S+\s+#(\d+) ")

LEGEND = (
    "# TinyBox log - time with ms | level D I W E | component | #session call | message",
    "#   '<' from the station, '>' to the station, '<<' '>>' AGW frames,"
    " (312ms) is a duration",
    "#   '-----' is a start or a stop, 'MARK:' a mark set by the sysop."
    " grep '#7' for one connection.",
)


# --- the daily file -------------------------------------------------------


class DailyFileHandler(logging.Handler):
    """One file per calendar day, append mode, no renaming.

    Not TimedRotatingFileHandler: that renames the file it is writing to, and
    on Windows a file that is open cannot be renamed - in continuous operation
    over midnight that fails exactly where the log would have to say so."""

    def __init__(self, log_dir: Path, keep_days: int = 14,
                 max_bytes: int = MAX_BYTES) -> None:
        super().__init__()
        self.log_dir = Path(log_dir)
        self.keep_days = keep_days
        self.max_bytes = max_bytes
        self._day: date | None = None
        self._part = 1
        self._stream = None
        self.path: Path | None = None
        self._open(date.today())
        self.purge()

    # --- file handling ---

    def _path_for(self, day: date, part: int) -> Path:
        tail = "" if part <= 1 else f".{part}"
        return self.log_dir / f"{PREFIX}{day:%Y-%m-%d}{tail}{SUFFIX}"

    def _open(self, day: date) -> None:
        self._close()
        self._day, self._part = day, 1
        while (path := self._path_for(day, self._part)).exists() \
                and path.stat().st_size >= self.max_bytes:
            self._part += 1                       # today is full already: next part
        self.path = path
        fresh = not path.exists() or path.stat().st_size == 0
        self._stream = open(path, "a", encoding="utf-8", errors="replace")
        if fresh:
            for line in LEGEND:
                self._stream.write(line + "\n")
            self._stream.flush()

    def _close(self) -> None:
        if self._stream is not None:
            with contextlib.suppress(Exception):
                self._stream.close()
        self._stream = None

    def _roll_if_needed(self) -> None:
        today = date.today()
        if today != self._day:                    # the day changed: new file
            self._open(today)
            self.purge()
            return
        if self._stream is not None and self._stream.tell() >= self.max_bytes:
            self._part += 1                       # emergency brake: .2, .3, ...
            self._close()
            self.path = self._path_for(self._day, self._part)
            self._stream = open(self.path, "a", encoding="utf-8", errors="replace")
            for line in LEGEND:
                self._stream.write(line + "\n")

    def purge(self) -> int:
        """Delete log files older than keep_days. Logs never go into the repo,
        so the folder may as well tidy itself up."""
        if self.keep_days <= 0:
            return 0
        oldest = date.today() - timedelta(days=self.keep_days)
        gone = 0
        for path in self.log_dir.glob(f"{PREFIX}*{SUFFIX}"):
            found = re.match(rf"{PREFIX}(\d{{4}})-(\d{{2}})-(\d{{2}})", path.name)
            if not found:
                continue
            try:
                day = date(*(int(p) for p in found.groups()))
            except ValueError:
                continue
            if day < oldest:
                with contextlib.suppress(OSError):
                    path.unlink()
                    gone += 1
        return gone

    # --- logging.Handler ---

    def emit(self, record: logging.LogRecord) -> None:
        try:
            self._roll_if_needed()
            if self._stream is None:
                return
            self._stream.write(self.format(record) + "\n")
            self._stream.flush()                  # after a crash the last line counts
        except Exception:                         # a broken log must not stop TinyBox
            self.handleError(record)

    def close(self) -> None:
        self._close()
        super().close()

    # --- for LOG MARK and LOG BUNDLE ---

    def write_raw(self, text: str) -> None:
        self._roll_if_needed()
        if self._stream is not None:
            self._stream.write(text + "\n")
            self._stream.flush()

    def size(self) -> int:
        try:
            return self.path.stat().st_size if self.path else 0
        except OSError:
            return 0

    def tail(self, lines: int) -> list[str]:
        if self.path is None or not self.path.exists():
            return []
        with open(self.path, encoding="utf-8", errors="replace") as fh:
            return [line.rstrip("\n") for line in fh.readlines()[-lines:]]

    def highest_session_id(self, lines: int = 2000) -> int:
        """The largest session number already in today's file, so the numbering
        goes on after a restart instead of starting at #1 again."""
        found = 0
        for line in self.tail(lines):
            match = CTX_IN_LINE.match(line)
            if match:
                found = max(found, int(match.group(1)))
        return found


# --- control (LOG command) ------------------------------------------------


class LogControl:
    """What the LOG console command works on."""

    def __init__(self, level: str, file_filter: LevelFilter | None,
                 handler: DailyFileHandler | None, console_filter: LevelFilter) -> None:
        self.level = level
        self.file_filter = file_filter
        self.handler = handler
        self.console_filter = console_filter

    @property
    def debug(self) -> set[str]:
        return self.file_filter.debug if self.file_filter else self.console_filter.debug

    def _sync_root_level(self) -> None:
        """The root level decides whether a DEBUG record is built at all. Without
        a single component on DEBUG it stays at the configured level, so a
        log.debug() in the frame path costs nothing."""
        level = logging.DEBUG if self.debug else logging.getLevelName(self.level)
        logging.getLogger().setLevel(level)

    def set_debug(self, comps: list[str], on: bool) -> list[str]:
        """Switch DEBUG for components at runtime, without a restart."""
        known = []
        for comp in comps:
            comp = comp.strip().lower()
            if not comp or (comp not in COMPONENTS and comp != "all"):
                continue
            known.append(comp)
            for flt in (self.file_filter, self.console_filter):
                if flt is None:
                    continue
                if on:
                    flt.debug.add(comp)
                else:
                    flt.debug.discard(comp)
        self._sync_root_level()
        return known

    def clear_debug(self) -> None:
        for flt in (self.file_filter, self.console_filter):
            if flt is not None:
                flt.debug.clear()
        self._sync_root_level()

    def mark(self, text: str) -> bool:
        """A marker line. Set a mark, trigger the bug, then say 'from the mark
        on' - that saves the most time when debugging."""
        if self.handler is None:
            return False
        stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.000")
        self.handler.write_raw(f"{stamp} I core     {NO_SESSION:<12} "
                               f"===== MARK: {text} =====")
        return True

    @property
    def path(self) -> Path | None:
        return self.handler.path if self.handler else None

    def size(self) -> int:
        return self.handler.size() if self.handler else 0


# --- start block and closing line -----------------------------------------


def git_commit(root: Path) -> str:
    """The checked out commit, read from .git - no git call, no dependency."""
    try:
        head = (root / ".git" / "HEAD").read_text(encoding="ascii").strip()
        if head.startswith("ref:"):
            ref = head.partition(" ")[2].strip()
            path = root / ".git" / ref
            if path.exists():
                return path.read_text(encoding="ascii").strip()[:7]
            packed = (root / ".git" / "packed-refs").read_text(encoding="ascii")
            for line in packed.splitlines():
                if line.endswith(" " + ref):
                    return line.split(" ", 1)[0][:7]
            return "-"
        return head[:7]
    except (OSError, ValueError, UnicodeDecodeError):
        return "-"


def _secret(value: str) -> str:
    return "set" if value else "unset"


def start_block(cfg, version: str, config_path: str | None,
                log_path: Path | None, debug: set[str]) -> list:
    """The first lines of every run: which version, what is switched on.
    Never tokens or the login URL - only set/unset.

    Items for termcolor.kv_block: (label, value[, note]), None = empty line,
    a string = a line as it is (the head line)."""
    root = Path(__file__).resolve().parent.parent
    adapters = " ".join(f"{name}={'on' if on else 'off'}" for name, on in (
        ("telnet", cfg.telnet.enabled), ("axudp", cfg.axudp.enabled), ("web", cfg.web.enabled),
        ("brocast", cfg.brocast.publish), ("inbox", cfg.inbox.enabled),
        ("forward", cfg.forward.enabled), ("mqtt", cfg.mqtt.enabled),
        ("console", cfg.console.enabled)))
    if cfg.radio.interface == "kiss":
        via = ("kiss", f"(kisshub {cfg.kiss.host}:{cfg.kiss.port}, channel {cfg.kiss.channel}, "
                       f"own AX.25 {cfg.ax25.version})")
    else:
        via = ("agw", f"(Direwolf {cfg.direwolf.agw_host}:{cfg.direwolf.agw_port}, "
                      f"port {cfg.direwolf.agw_radio_port})")
    return [f"----- TinyBox {version} ({git_commit(root)}) start -----",
            *termcolor.wrap_items("[tinyb]", _start_items(cfg, adapters, via, config_path,
                                                          log_path, debug))]


def _start_items(cfg, adapters: str, via: tuple, config_path, log_path, debug) -> list:
    return [
        ("Mailbox call", cfg.station.mailbox_call),
        ("BBS call", cfg.station.bbs_call),
        ("Sysop", cfg.station.sysop_call),
        ("Max users", cfg.mailbox.max_users),
        None,
        ("Connection via", *via),
        *radio_lines(cfg),
        None,
        ("Adapters", adapters),
        ("brocast token", _secret(cfg.brocast.token)),
        ("Logging", f"level {cfg.logging.level}, debug {','.join(sorted(debug)) or '-'}, "
                    f"keep_days {cfg.logging.keep_days}"),
        ("Log file", log_path or "- (console only)"),
        ("Config", config_path or "-"),
        ("Data", cfg.storage.data_dir),
        ("Python", f"{platform.python_version()} {sys.platform}, {platform.platform()}, "
                   f"pid {os.getpid()}"),
        None,
    ]


def radio_lines(cfg) -> list[tuple]:
    """CR70: where the radio values come from (start block items)."""
    src = cfg.sources or {}
    if cfg.radio.interface == "kiss":
        a = cfg.ax25
        lines = [("Radio values",
                  f"air_baud {cfg.kiss.air_baud}, txdelay {cfg.kiss.txdelay_ms} ms, "
                  f"paclen {a.paclen}, window {a.maxframe}/{a.maxframe_ext}, "
                  f"T1 {a.t1_min_sec}-{a.t1_max_sec} s, T2 {a.t2_sec} s",
                  f"({src.get('kiss', '-')}; until the first status of kisshub "
                  f"127.0.0.1:{cfg.kiss.status_port})")]
    else:
        d = cfg.direwolf
        lines = [("AGW values",
                  f"port {d.agw_port} ({src.get('agw_port', '-')}), "
                  f"paclen {d.paclen} ({src.get('agw_paclen', '-')}), "
                  f"window {d.max_outstanding} ({src.get('agw_window', '-')})")]
    if src.get("direwolf.conf"):
        lines.append(("direwolf.conf", src["direwolf.conf"]))
    return lines


def stop_line(reason: str) -> str:
    return f"----- stop: {reason}, {counters.summary()} -----"


# --- LOG BUNDLE -----------------------------------------------------------

SECRET_KEY = re.compile(r"^\s*([\w.-]*(token|password|secret|key)[\w.-]*)\s*=", re.I)


def strip_secrets(text: str) -> str:
    out = []
    for line in text.splitlines():
        found = SECRET_KEY.match(line)
        out.append(f"{found.group(1)} = <removed>" if found else line)
    return "\n".join(out)


def write_bundle(app, control: LogControl, version: str, lines: int = 400) -> Path:
    """One file that can be put into a chat unchanged: start block, the last
    lines of the log, version, tinybox.conf without tokens, data folder."""
    cfg = app.cfg
    target_dir = cfg.logging.log_dir or cfg.storage.data_dir
    path = Path(target_dir) / f"tinybox_debug_{datetime.now():%Y-%m-%d_%H-%M-%S}.txt"
    out: list[str] = [f"TinyBox debug bundle {datetime.now():%Y-%m-%d %H:%M:%S}", ""]
    out.append("--- start block -------------------------------------------------")
    out += [x if isinstance(x, str) else termcolor.kv_plain(*x) if x else ""
            for x in start_block(cfg, version, app.config_path, control.path, control.debug)]
    out.append("")
    out.append("--- state -------------------------------------------------------")
    out.append(f"up {counters.summary()}")
    out.append(f"sessions now: {len(app.registry)}")
    out.append("")
    out.append("--- tinybox.conf (tokens removed) -------------------------------")
    if app.config_path and Path(app.config_path).exists():
        out.append(strip_secrets(Path(app.config_path).read_text(
            encoding="utf-8", errors="replace")))
    else:
        out.append("(not found)")
    out.append("")
    out.append("--- data folder -------------------------------------------------")
    try:
        for item in sorted(Path(cfg.storage.data_dir).iterdir()):
            size = item.stat().st_size if item.is_file() else 0
            out.append(f"{item.name:<40} {size:>12}")
    except OSError as exc:
        out.append(f"(not readable: {exc})")
    out.append("")
    out.append(f"--- log, last {lines} lines -------------------------------------")
    out += control.handler.tail(lines) if control.handler else ["(no log file)"]
    path.write_text("\n".join(out) + "\n", encoding="utf-8")
    return path


# --- setting it all up ----------------------------------------------------


def setup(cfg, monitor_filter_factory) -> tuple[LogControl, object]:
    """Console plus, with [logging] log_dir, the daily file.

    Returns the LogControl (for the LOG command) and the console monitor
    filter (switched with MON ON/OFF).
    """
    cfg.storage.data_dir.mkdir(parents=True, exist_ok=True)
    root = logging.getLogger()
    for old in list(root.handlers):               # a restart in the same process
        root.removeHandler(old)
    debug = set(cfg.logging.debug)
    console_filter = monitor_filter_factory(cfg.console.monitor)
    console_level = LevelFilter(cfg.logging.level)
    console_level.debug = set(debug)
    console = termcolor.console_handler("[tinyb]", cfg.console.color, context="cctx")
    console.addFilter(ContextFilter())            # also for records without the root path
    console.addFilter(console_level)
    console.addFilter(console_filter)
    root.addHandler(console)

    handler = None
    file_filter = None
    if cfg.logging.log_dir is not None:
        handler = DailyFileHandler(cfg.logging.log_dir, cfg.logging.keep_days)
        handler.setFormatter(Formatter())
        file_filter = LevelFilter(cfg.logging.level)
        file_filter.debug = set(debug)
        handler.addFilter(ContextFilter())
        handler.addFilter(file_filter)
        handler.addFilter(monitor_filter_factory(cfg.logging.monitor))
        root.addHandler(handler)
        seed_session_ids(handler.highest_session_id())

    global _active
    _active = LogControl(cfg.logging.level, file_filter, handler, console_level)
    _active._sync_root_level()     # DEBUG records are built only if asked for
    return _active, console_filter
