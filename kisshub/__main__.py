"""python -m kisshub [-c kisshub.conf]

Commands can be typed into the window while it runs (H for help): LOG MARK,
LOG DEBUG, LOG TRACE, TXDELAY ... - see console.py.

Ctrl+C ends kisshub cleanly: the TNC is switched back out of KISS first
(if the profile says so), so a terminal program or pk232py finds it at cmd:.
"""

from __future__ import annotations

import argparse
import asyncio
import dataclasses
import logging
import textwrap
import sys
from pathlib import Path

from prcore import release, termcolor

from . import VERSION
from .config import ConfigError, load, make_transport, profile_list, radio_lines
from .console import Console, LogControl
from .hub import Hub
from .tnc import Tnc


TAG = "[kisshb]"


def setup_logging(level: str, file: str, color: str = "auto") -> None:
    handlers: list[logging.Handler] = [termcolor.console_handler(TAG, color)]
    if file:
        fh = logging.FileHandler(file, encoding="utf-8")
        fh.setFormatter(termcolor.ConsoleFormatter(TAG, datefmt="%Y-%m-%d %H:%M:%S"))
        handlers.append(fh)
    logging.basicConfig(level=getattr(logging, level, logging.INFO), handlers=handlers)


async def main(cfg, config_path: str = "kisshub.conf") -> None:
    t = cfg.tnc

    def tnc_factory(on_frame):
        return Tnc(t.profile, make_transport(t), on_frame,
                   reconnect_sec=t.reconnect_sec, params=t.params)

    hub = Hub(cfg.hub, tnc_factory)
    hub.tnc.trace = cfg.trace
    modem = supervisor = None
    log = logging.getLogger("kisshub")
    watcher = None
    try:
        if cfg.modem73 is not None and cfg.modem73.start:
            from .modem73 import Modem73Process
            modem = Modem73Process(cfg.modem73, t.port, t.host, restart_sec=t.reconnect_sec)
            hub.modem73 = modem
            try:
                await modem.start()
            except RuntimeError as exc:
                log.error("%s", exc)
                return
            if await modem.wait_port():
                log.info("modem73 ready on %s:%d", t.host, t.port, extra=termcolor.OK)
            else:
                log.warning("modem73: KISS port %s:%d not open after 30 s - see its lines "
                            "above (audio device, COM port?); kisshub keeps trying",
                            t.host, t.port)
            supervisor = asyncio.create_task(modem.supervise())
        if sys.stdin is not None and sys.stdin.isatty():
            def info() -> None:              # console I: the start block with today's values
                termcolor.kv_block(log, start_items(
                    config_path, dataclasses.replace(cfg, hub=hub.cfg)))
            Console(hub, LogControl(cfg.log_level, cfg.log_file), info=info).start_stdin()
        if cfg.update_check:                 # PLANUNG 24: a log line, nothing else
            watcher = asyncio.create_task(release.watch(
                release_logger(), cache=cfg.data_dir / "kisshub-release.json",
                program="kisshub"))
        await hub.run()
    finally:
        if watcher is not None:
            watcher.cancel()
        try:
            await asyncio.shield(hub.stop())
        finally:
            if modem is not None:
                await asyncio.shield(modem.stop())     # PTT released, COM port closed
            if supervisor is not None:
                supervisor.cancel()


def release_logger():
    """Callback for prcore.release.watch(): one warning per new release."""
    log = logging.getLogger("kisshub")
    seen: set[str] = set()

    def on_result(result) -> None:
        if result.newer and result.latest not in seen:
            seen.add(result.latest)
            log.warning("update: %s", result.hint())
    return on_result


def log_lines(config_path: str, cfg) -> list[tuple]:
    """Where this run is logged - shown at every start, so a test run is never
    lost because the log went nowhere (or somewhere unexpected)."""
    trace = ", trace on" if cfg.trace else ""
    lines = [("Config", Path(config_path).resolve())]
    if cfg.log_file:
        lines.append(("Log file", Path(cfg.log_file).resolve(), f"(level {cfg.log_level}{trace})"))
    else:
        lines.append(("Log file", "NO log file - console only",
                      f"(level {cfg.log_level}{trace}; set [log] file = kisshub.log to keep it)"))
    if cfg.hub.links_file:
        lines.append(("Links file", Path(cfg.hub.links_file).resolve(),
                      "(one JSON line per finished AX.25 link)"))
    else:
        lines.append(("Links file", "off", "(finished AX.25 links are not written, "
                                           "[log] links_file)"))
    return lines


# console line: "[kisshb] 16:11:48 " + label (LABEL_WIDTH + 1) + value - 80 columns
LINE_WIDTH = 80
PREFIX_WIDTH = len(TAG) + 10
VALUE_WIDTH = LINE_WIDTH - PREFIX_WIDTH - termcolor.LABEL_WIDTH - 1


def wrap_items(items: list, width: int = VALUE_WIDTH) -> list:
    """Start block items broken to 80 columns: a long value goes on under itself
    (continuation lines with an empty label), a note that does not fit behind the
    last value line gets lines of its own under the value. Links are never broken."""
    out: list = []
    for item in items:
        if item is None or isinstance(item, str) or (len(item) > 3 and item[3]):
            out.append(item)                          # empty line, plain line, link
            continue
        label, value = item[0], str(item[1])
        note = item[2] if len(item) > 2 else ""
        # a label longer than the label column pushes its value to the right
        first = width - max(0, len(label) + 1 - termcolor.LABEL_WIDTH)
        lines = _wrap(value, first, width)
        room = (first if len(lines) == 1 else width) - len(lines[-1])
        tail = note if note and (not lines[-1] or len(note) + 2 <= room) else ""
        for n, text in enumerate(lines):
            last = n == len(lines) - 1
            out.append((label if n == 0 else "", text, tail if last else ""))
        if note and not tail:
            out.extend(("", text) for text in _wrap(note, width, width))
    return out


def _wrap(text: str, first: int, width: int) -> list[str]:
    """Words of text into lines: the first one `first` long, the others `width`."""
    if not text:
        return [""]
    lines = textwrap.wrap(text, max(first, 10), break_on_hyphens=False,
                          break_long_words=False)
    if len(lines) > 1 and first != width:
        lines = lines[:1] + textwrap.wrap(" ".join(lines[1:]), width,
                                          break_on_hyphens=False, break_long_words=False)
    return lines


def start_items(config_path: str, cfg) -> list:
    """The start block (termcolor.kv_block): what runs, where, with which values -
    at start and with the console command I."""
    h = cfg.hub
    p = cfg.tnc.profile
    if h.status_port:
        status = (("Status query", f"http://127.0.0.1:{h.status_port}/status", "", True)
                  if h.status_port > 0 else ("Status query", "on (free port)"))
    else:
        status = ("Status query", "off",
                  "([server] status_port = 0 - TinyBox and client keep their own values)")
    return wrap_items([("TNC profile", p.name, f"({p.notes})"),
                       ("TNC port", make_transport(cfg.tnc).describe()),
                       ("KISS-TCP for programs", f"{h.listen}:{h.port}"),
                       status,
                       None,
                       *radio_lines(cfg),
                       None,
                       *log_lines(config_path, cfg),
                       None])


HELP = """\
kisshub owns the KISS TNC or modem and shares it over KISS-TCP with TinyBox,
the client and brocastd (all on this PC, 127.0.0.1). It also holds the radio
values (bit rate, TXDELAY, AX.25 recommendation) - TinyBox and the client take
them from its status query on port + 1.
"""

EPILOG = """\
profiles = the TNC sections of kisshub.conf (kisshub 2026.11.05):
  Every TNC has its own section with ALL its values - port, wake / init dialog,
  radio values, AX.25 recommendation. The section name is the profile name:
  [pk232] -> kisshub.bat -p pk232. type = tnc | vara | direwolf | modem73 picks
  the code behind it; base = <other section> takes the keys of another TNC first
  (e.g. [tm-d710-9k6] with base = tm-d710 and only the 9600 Bd values).
  Global sections: [kisshub] profile (default without -p), [server], [log],
  [console], [update]. {profile} in [log] file / links_file = the profile name.
  kisshub -l lists the TNC sections of the conf.

examples:
  kisshub.bat -p pk232
  kisshub.bat -p vara-fm
  kisshub.bat -l
  python -m kisshub -c kisshub-test.conf -p generic

While it runs, type H in the window for the console commands (S status,
L links, V VARA, LOG MARK text, TXDELAY ms ...). Ctrl+C stops it cleanly.
More: MANUAL.md section 2.4 and 3, kisshub.conf.example.
"""


def parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="kisshub", description=HELP, epilog=EPILOG,
                                 add_help=False,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("-h", "-?", "--help", action="help",
                    help="show this help and exit")
    ap.add_argument("-c", "--config", default="kisshub.conf", metavar="FILE",
                    help="configuration file (default: kisshub.conf)")
    ap.add_argument("-p", "--profile", metavar="PROFILE",
                    help="TNC section of the conf to use, overrides [kisshub] profile")
    ap.add_argument("-l", "--list", action="store_true",
                    help="list the TNC sections (profiles) of the conf and exit")
    ap.add_argument("-V", "--version", action="version", version=f"kisshub {VERSION}")
    return ap


def run(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    if args.list:
        try:
            rows = profile_list(args.config)
        except ConfigError as exc:
            print(f"{TAG} [ERROR] {exc}", file=sys.stderr)
            return 2
        width = max((len(r[0]) for r in rows), default=4)
        for name, ptype, notes in rows:
            print(f"  {name:<{width}}  {ptype:<8}  {notes}")
        return 0
    try:
        cfg = load(args.config, args.profile)
    except ConfigError as exc:
        print(f"{TAG} [ERROR] {exc}", file=sys.stderr)
        return 2
    setup_logging(cfg.log_level, cfg.log_file, cfg.color)
    log = logging.getLogger("kisshub")
    log.info("kisshub start - version %s (release %s)", VERSION, release.RELEASE,
             extra=termcolor.HEAD)
    termcolor.kv_block(log, start_items(args.config, cfg))
    for hint in cfg.hints:
        log.warning("config hint: %s", hint)
    try:
        asyncio.run(main(cfg, args.config))
    except KeyboardInterrupt:
        log.info("stopped")
    return 0


if __name__ == "__main__":
    sys.exit(run())
