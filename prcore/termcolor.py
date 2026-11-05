"""Coloured console log output, shared by TinyBox, tbclient, kisshub and brocastd.

One look for all four windows:

    [tbcli] 17:36:45 Your call:              OE3XXX
    [tbcli] 17:36:47 [ERROR] Direwolf AGW 127.0.0.1:8000 not reachable (...)

- grey:   program tag, time, side notes in brackets
- cyan:   labels of label/value lines (``kv``), values bright white
- green:  "connected" lines (``extra=OK``)
- yellow: ``[WARN]`` (logging.WARNING), red: ``[ERROR]`` (ERROR and above)

The tags ``[WARN]``/``[ERROR]`` are always written, with or without colour.
Colour is only used on a real console: ``color = auto`` (the default) switches it
off when the output goes to a file or pipe, when NO_COLOR is set, or when the
Windows console cannot do ANSI. ``yes``/``no`` force it.

Only the console handler colours. Log files get the same plain text, because the
colour information travels in ``record`` attributes, never in the message.
"""

from __future__ import annotations

import logging
import os
import sys

RESET = "\033[0m"
GREY = "\033[90m"
CYAN = "\033[96m"
WHITE = "\033[97m"
BOLD = "\033[1m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BLUE_UL = "\033[94;4m"

LABEL_WIDTH = 23                      # "Your preferred TinyBox:" is the longest label

OK = {"tb_tone": "ok"}                # log.info("connected ...", extra=OK)
HEAD = {"tb_tone": "head"}            # start line: bright white


def _windows_vt(stream) -> bool:
    """Switch on ANSI processing of the Windows console (Windows 10 and later)."""
    try:
        import ctypes
        from ctypes import wintypes
        k32 = ctypes.windll.kernel32
        handle = k32.GetStdHandle(-12 if stream is sys.stderr else -11)
        mode = wintypes.DWORD()
        if not k32.GetConsoleMode(handle, ctypes.byref(mode)):
            return False
        if mode.value & 0x0004:                       # already on (Windows Terminal)
            return True
        return bool(k32.SetConsoleMode(handle, mode.value | 0x0004))
    except Exception:                                  # noqa: BLE001 - no colour then
        return False


def use_color(mode: str = "auto", stream=None) -> bool:
    """Decide once at start whether the console gets colour."""
    stream = stream or sys.stdout
    mode = (mode or "auto").strip().lower()
    if mode in ("no", "off", "false", "0"):
        return False
    if mode not in ("yes", "on", "true", "1"):        # auto
        if os.environ.get("NO_COLOR"):
            return False
        if os.environ.get("TERM") == "dumb":
            return False
        try:
            if not stream.isatty():
                return False
        except (AttributeError, ValueError):
            return False
    if os.name == "nt":
        return _windows_vt(stream)
    return True


def check_mode(value: str) -> str:
    """For the config loaders: auto / yes / no."""
    v = (value or "auto").strip().lower()
    if v in ("auto", ""):
        return "auto"
    if v in ("yes", "on", "true", "1"):
        return "yes"
    if v in ("no", "off", "false", "0"):
        return "no"
    raise ValueError(f"[console] color must be auto, yes or no, not {value!r}")


def kv_plain(label: str, value, note: str = "") -> str:
    """'Your call:              OE3XXX' - the text of a label/value line. An empty
    label gives a continuation line (value under the value above, no colon)."""
    text = f"{label + ':' if label else '':<{LABEL_WIDTH}} {value}"
    return text + f"  {note}" if note else text


LINE_WIDTH = 80                       # console lines: "[tag] HH:MM:SS " + label + value


def prefix_width(tag: str) -> int:
    """'[kisshb] 16:11:48 ' - tag, time and the blanks in front of the message."""
    return len(tag) + 10


def value_width(tag: str) -> int:
    return LINE_WIDTH - prefix_width(tag) - LABEL_WIDTH - 1


def wrap_items(tag: str, items: list, width: int | None = None) -> list:
    """Start block items (kv_block) broken to 80 columns: a long value goes on under
    itself (continuation lines with an empty label), a note that does not fit behind
    the last value line gets lines of its own under the value. A plain string line
    goes on indented by two. Links and single long words (paths) are never broken."""
    width = width or value_width(tag)
    plain = LINE_WIDTH - prefix_width(tag)
    out: list = []
    for item in items:
        if item is None:
            out.append(item)
        elif isinstance(item, str):
            out.extend(wrap_line(item, plain))
        elif len(item) > 3 and item[3]:
            out.append(item)                          # a link stays in one piece
        else:
            label, value = item[0], str(item[1])
            note = item[2] if len(item) > 2 else ""
            # a label longer than the label column pushes its value to the right
            first = width - max(0, len(label) + 1 - LABEL_WIDTH)
            lines = _wrap(value, first, width)
            room = (first if len(lines) == 1 else width) - len(lines[-1])
            tail = note if note and (not lines[-1] or len(note) + 2 <= room) else ""
            for n, text in enumerate(lines):
                out.append((label if n == 0 else "", text,
                            tail if n == len(lines) - 1 else ""))
            if note and not tail:
                out.extend(("", text) for text in _wrap(note, width, width))
    return out


def wrap_line(text: str, width: int) -> list[str]:
    """A plain line into lines of `width`, the continuation lines indented by two."""
    if len(text) <= width:
        return [text]
    return ["  " + x if n else x for n, x in enumerate(_wrap(text, width, width - 2))]


def _wrap(text: str, first: int, width: int) -> list[str]:
    """Words of text into lines: the first one `first` long, the others `width`."""
    import textwrap
    if not text:
        return [""]
    opts = dict(break_on_hyphens=False, break_long_words=False)
    lines = textwrap.wrap(text, max(first, 10), **opts)
    if len(lines) > 1 and first != width:
        lines = lines[:1] + textwrap.wrap(" ".join(lines[1:]), max(width, 10), **opts)
    return lines


def kv(log: logging.Logger, label: str, value, note: str = "", url: bool = False,
       level: int = logging.INFO) -> None:
    """A label/value line of a start block:  'Your call:              OE3XXX'."""
    log.log(level, "%s", kv_plain(label, value, note),
            extra={"tb_kv": (label + ":" if label else "", str(value), note), "tb_url": url})


def kv_block(log: logging.Logger, items) -> None:
    """A start block: (label, value[, note]) tuples, None = empty line,
    a plain string = a line as it is."""
    for item in items:
        if item is None:
            blank(log)
        elif isinstance(item, str):
            log.info("%s", item)
        else:
            kv(log, *item)


def blank(log: logging.Logger) -> None:
    """Empty line in a start block (only the program tag and the time)."""
    log.info("")


class ConsoleFormatter(logging.Formatter):
    """'[tag] HH:MM:SS [LEVEL] <context>message' - coloured if ``color``.

    ``context`` is the name of a record attribute put before the message (TinyBox:
    ``cctx``, the session number).
    """

    def __init__(self, tag: str, color: bool = False, context: str = "",
                 datefmt: str = "%H:%M:%S") -> None:
        super().__init__(datefmt=datefmt)
        self.tag = tag
        self.color = color
        self.context = context

    def _c(self, code: str, text: str) -> str:
        return f"{code}{text}{RESET}" if self.color and text else text

    def format(self, record: logging.LogRecord) -> str:
        head = f"{self.tag} {self.formatTime(record, self.datefmt)}"
        msg = record.getMessage()
        if record.exc_info and not record.exc_text:
            record.exc_text = self.formatException(record.exc_info)
        extra_text = ""
        if record.exc_text:
            extra_text += "\n" + record.exc_text
        if record.stack_info:
            extra_text += "\n" + self.formatStack(record.stack_info)
        ctx = getattr(record, self.context, "") if self.context else ""

        if record.levelno >= logging.ERROR:
            body = self._c(RED + BOLD, f"[ERROR] {ctx}{msg}{extra_text}")
        elif record.levelno >= logging.WARNING:
            body = self._c(YELLOW, "[WARN]") + f" {ctx}{msg}{extra_text}"
        else:
            body = ctx + self._body(record, msg) + extra_text
        if not msg and not extra_text and record.levelno < logging.WARNING:
            return self._c(GREY, head)
        return f"{self._c(GREY, head)} {body}"

    def _body(self, record: logging.LogRecord, msg: str) -> str:
        if not self.color:
            return msg
        kvt = getattr(record, "tb_kv", None)
        if kvt:
            label, value, note = kvt
            val = self._c(BLUE_UL if getattr(record, "tb_url", False) else WHITE + BOLD, value)
            text = f"{self._c(CYAN, f'{label:<{LABEL_WIDTH}}')} {val}"
            return text + (f"  {self._c(GREY, note)}" if note else "")
        tone = getattr(record, "tb_tone", "")
        if tone == "ok":
            return self._c(GREEN, msg)
        if tone == "head":
            return self._c(WHITE + BOLD, msg)
        if record.levelno < logging.INFO:
            return self._c(GREY, msg)
        return msg


def console_handler(tag: str, mode: str = "auto", context: str = "",
                    stream=None) -> logging.StreamHandler:
    """The console handler for one program, e.g. console_handler("[tbcli]", cfg.color)."""
    stream = stream or sys.stdout
    handler = logging.StreamHandler(stream)
    handler.setFormatter(ConsoleFormatter(tag, use_color(mode, stream), context))
    return handler


def kv_print(tag: str, label: str, value: str, mode: str = "auto", url: bool = False) -> None:
    """A label/value line printed past logging - never in a log file (TinyBox login link)."""
    import time
    record = logging.LogRecord("print", logging.INFO, "", 0, "%s",
                               (kv_plain(label, value),), None)
    record.created = time.time()
    record.tb_kv = (label + ":", value, "")
    record.tb_url = url
    print(ConsoleFormatter(tag, use_color(mode)).format(record), flush=True)
