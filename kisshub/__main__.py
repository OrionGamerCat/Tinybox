"""python -m kisshub [-c kisshub.conf]

Commands can be typed into the window while it runs (H for help): LOG MARK,
LOG DEBUG, LOG TRACE, TXDELAY ... - see console.py.

Ctrl+C ends kisshub cleanly: the TNC is switched back out of KISS first
(if the profile says so), so a terminal program or pk232py finds it at cmd:.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path

from prcore import release, termcolor

from . import VERSION
from .config import ConfigError, load, make_transport, radio_lines
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


async def main(cfg) -> None:
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
            Console(hub, LogControl(cfg.log_level, cfg.log_file)).start_stdin()
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


def start_items(config_path: str, cfg) -> list:
    """The start block (termcolor.kv_block): what runs, where, with which values."""
    h = cfg.hub
    p = cfg.tnc.profile
    if h.status_port:
        status = (("Status query", f"http://127.0.0.1:{h.status_port}/status", "", True)
                  if h.status_port > 0 else ("Status query", "on (free port)"))
    else:
        status = ("Status query", "off",
                  "([server] status_port = 0 - TinyBox and client keep their own values)")
    return [("TNC profile", p.name, f"({p.notes})"),
            ("TNC port", make_transport(cfg.tnc).describe()),
            ("KISS-TCP for programs", f"{h.listen}:{h.port}"),
            status,
            None,
            *radio_lines(cfg),
            None,
            *log_lines(config_path, cfg),
            None]


HELP = """\
kisshub owns the KISS TNC or modem and shares it over KISS-TCP with TinyBox,
the client and brocastd (all on this PC, 127.0.0.1). It also holds the radio
values (bit rate, TXDELAY, AX.25 recommendation) - TinyBox and the client take
them from its status query on port + 1.
"""

EPILOG = """\
profiles:
  pk232      AEA PK-232 / PK-232MBX, serial ([tnc] device), 1200 Bd
  tm-d710    Kenwood TM-D710 (TNC key -> packet mode first), serial
  tnc7multi  TNC7multi (IfD), rotary switch 1k2/9k6, USB 115200, SMACK
  th-d74     Kenwood TH-D74, KISS on in the menu, serial / Bluetooth
  th-d75     Kenwood TH-D75, KISS on in the menu, serial / Bluetooth
  tnc2-kiss  TNC2 with a pure KISS EPROM, serial
  generic    any TNC already in KISS (serial or tcp)
  vara-fm    VARA FM, KISS-TCP 8100, connected mode tunnelled (both stations!)
  vara-hf    VARA HF, the same
  direwolf   Direwolf's KISSPORT, values from [tnc] direwolf_conf
  modem73    modem73 OFDM modem (KISS-TCP 8011), kisshub starts it from [modem73]

one kisshub.conf for all TNCs:
  -p PROFILE overrides [tnc] profile. A section [<section>.<profile>]
  (e.g. [kiss.pk232], [tnc.vara-fm]) overrides the plain section for that
  profile only. {profile} in [log] file / links_file becomes the profile
  name, e.g. file = kisshub-{profile}.log. [vara] monitor is ignored with
  other profiles than vara-fm / vara-hf.

examples:
  kisshub.bat -p pk232
  kisshub.bat -p vara-fm
  kisshub.bat -p direwolf
  kisshub.bat -p modem73
  python -m kisshub -c kisshub-test.conf -p generic

While it runs, type H in the window for the console commands (S status,
L links, V VARA, LOG MARK text, TXDELAY ms ...). Ctrl+C stops it cleanly.
More: MANUAL.md section 2.4 and 3, kisshub.conf.example.
"""


def parser() -> argparse.ArgumentParser:
    from .profiles import PROFILES
    ap = argparse.ArgumentParser(prog="kisshub", description=HELP, epilog=EPILOG,
                                 add_help=False,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("-h", "-?", "--help", action="help",
                    help="show this help and exit")
    ap.add_argument("-c", "--config", default="kisshub.conf", metavar="FILE",
                    help="configuration file (default: kisshub.conf)")
    ap.add_argument("-p", "--profile", choices=sorted(PROFILES), metavar="PROFILE",
                    help="TNC profile, overrides [tnc] profile (see below)")
    ap.add_argument("-V", "--version", action="version", version=f"kisshub {VERSION}")
    return ap


def run(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
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
        asyncio.run(main(cfg))
    except KeyboardInterrupt:
        log.info("stopped")
    return 0


if __name__ == "__main__":
    sys.exit(run())
