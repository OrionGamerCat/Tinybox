"""kisshub console: commands typed into the kisshub window while it runs.

    H / ?                 help
    S / STATUS            TNC, queue and clients in one line
    LOG                   log level, file, debug and trace
    LOG MARK text         a marker line in the log (before a test)
    LOG DEBUG             debug messages on (TNC dialog, KISS-TCP clients)
    LOG TRACE [ON|OFF]    every byte to and from the TNC in hex, frames with calls
    LOG OFF               debug and trace off
    PARAMS                the KISS parameters
    L / LINKS             AX.25 links: retransmissions, REJ, polls, ack times, answer
                          gaps, goodput (CR67) - running and the last finished ones
    V / VARA              what VARA reports on its command port (bursts, busy, SN)
    STATIONS              stations heard (frames, SN)
    TXDELAY ms            change at once, without leaving KISS (also PERSIST n,
    PERSIST n             SLOTTIME ms, TXTAIL ms); kept until kisshub stops -
    SLOTTIME ms           put the value into kisshub.conf to keep it
    TXTAIL ms

Ctrl+C ends kisshub (the TNC is switched back out of KISS first).
Same idea as the TinyBox sysop console (LOG MARK / LOG DEBUG, CR32).
"""

from __future__ import annotations

import asyncio
import dataclasses
import logging
import sys
import threading
import time
from pathlib import Path

from prcore import kiss

from .tnc import PARAM_NAMES

log = logging.getLogger("kisshub")

HELP = """kisshub console:
  S / STATUS           TNC, queue and clients
  LOG                  log level, file, debug, trace
  LOG MARK text        marker line in the log (before a test)
  LOG DEBUG            debug messages on
  LOG TRACE [ON|OFF]   every byte to/from the TNC in hex
  LOG OFF              debug and trace off
  PARAMS               KISS parameters
  L / LINKS            AX.25 link quality (running + last finished)
  V / VARA             VARA command port: bursts, waiting, busy, SN
  STATIONS             stations heard, with SN
  TXDELAY ms | PERSIST n | SLOTTIME ms | TXTAIL ms
                       change at once (stays until kisshub stops;
                       put it into kisshub.conf to keep it)
  Ctrl+C               stop kisshub (TNC leaves KISS)"""

# console word -> (KISS command, unit: 10 ms or a plain number)
PARAMS = {"TXDELAY": (kiss.CMD_TXDELAY, 10), "PERSIST": (kiss.CMD_P, 1),
          "SLOTTIME": (kiss.CMD_SLOTTIME, 10), "TXTAIL": (kiss.CMD_TXTAIL, 10)}


class LogControl:
    """Debug on/off and LOG MARK for the kisshub logger (and the log file)."""

    def __init__(self, level: str, file: str) -> None:
        self.level = level
        self.file = file
        self.debug = False

    def set_debug(self, on: bool) -> None:
        self.debug = on
        logging.getLogger("kisshub").setLevel(logging.DEBUG if on else logging.NOTSET)

    def mark(self, text: str) -> None:
        # WARNING level: the mark is in the log whatever [log] level says
        log.warning("===== MARK: %s =====", text)

    def size(self) -> str:
        try:
            return f"{Path(self.file).stat().st_size / 1024:.0f} kB"
        except OSError:
            return "-"


class Console:
    def __init__(self, hub, control: LogControl, out=print) -> None:
        self.hub = hub
        self.control = control
        self.out = out

    @property
    def tnc(self):
        return self.hub.tnc

    def start_stdin(self) -> None:
        loop = asyncio.get_running_loop()

        def reader() -> None:
            while True:
                line = sys.stdin.readline()
                if line == "":
                    time.sleep(0.2)                  # closed/dead console: do not spin
                    continue
                loop.call_soon_threadsafe(self.handle_line, line.rstrip("\r\n"))

        threading.Thread(target=reader, name="kisshub-console", daemon=True).start()
        self.out("kisshub console: H for help")

    def handle_line(self, line: str) -> None:
        word, _, arg = line.strip().partition(" ")
        word, arg = word.upper(), arg.strip()
        if not word:
            return
        try:
            if word in ("H", "?", "HELP"):
                self.out(HELP)
            elif word in ("S", "STATUS"):
                self.out(self.hub.status())
            elif word == "LOG":
                self.cmd_log(arg)
            elif word == "PARAMS":
                self.cmd_params()
            elif word in ("L", "LINKS"):
                self.out("\n".join(self.hub.stats.lines(self.hub.now())))
            elif word in ("V", "VARA"):
                v = self.hub.vara
                self.out("\n".join(v.lines_text(self.hub.now())) if v is not None
                         else "VARA monitor off (vara_monitor = yes in the VARA section of kisshub.conf)")
            elif word == "STATIONS":
                self.cmd_stations()
            elif word in PARAMS:
                self.cmd_set(word, arg)
            else:
                self.out(f"unknown command {word} - H for help")
        except Exception as exc:                     # a typo must never stop the hub
            log.exception("console command failed")
            self.out(f"error: {exc}")

    def cmd_stations(self) -> None:
        st = self.hub.stats.status(self.hub.now())["stations"]
        if not st:
            self.out("no stations heard yet")
            return
        for call, h in st.items():
            sn = h["sn_db"]
            self.out(f"{call:<10} {h['frames']:>5} frames {h['bytes']:>7} B  last "
                     f"{time.strftime('%H:%M:%S', time.localtime(h['last']))}"
                     + (f"  SN {sn['avg']} dB ({sn['min']}..{sn['max']}, n={sn['n']})" if sn else ""))

    def cmd_log(self, arg: str) -> None:
        sub, _, rest = arg.partition(" ")
        sub, rest = sub.upper(), rest.strip()
        if sub == "MARK":
            if not rest:
                self.out("Usage: LOG MARK text")
                return
            self.control.mark(rest)
            return
        if sub == "DEBUG":
            self.control.set_debug(True)
            log.info("log: debug on")
        elif sub == "TRACE":
            on = rest.upper() != "OFF"
            self.tnc.trace = on
            log.info("log: trace %s", "on" if on else "off")
        elif sub == "OFF":
            self.control.set_debug(False)
            self.tnc.trace = False
            log.info("log: debug and trace off")
        elif sub:
            self.out("Usage: LOG | LOG MARK text | LOG DEBUG | LOG TRACE [ON|OFF] | LOG OFF")
            return
        self.out(f"log level {self.control.level}, debug {'on' if self.control.debug else 'off'}, "
                 f"trace {'on' if self.tnc.trace else 'off'}, file "
                 f"{self.control.file or 'none ([log] file is empty)'}"
                 + (f" ({self.control.size()})" if self.control.file else ""))

    def cmd_params(self) -> None:
        parts = []
        for name, (cmd, unit) in PARAMS.items():
            value = self.tnc.params.get(cmd)
            if value is not None:
                parts.append(f"{name} {value * unit}{' ms' if unit == 10 else ''}")
        self.out("KISS parameters: " + (", ".join(parts) or "none sent (send_params = no)"))

    def cmd_set(self, name: str, arg: str) -> None:
        cmd, unit = PARAMS[name]
        try:
            given = int(arg)
        except ValueError:
            self.out(f"Usage: {name} {'ms' if unit == 10 else 'n'}")
            return
        value = round(given / unit)
        if not 0 <= value <= 255:
            self.out(f"{name}: 0..{255 * unit}")
            return
        sent = self.tnc.set_param(cmd, value)
        if cmd == kiss.CMD_TXDELAY:                  # the hub paces with it too
            self.hub.cfg = dataclasses.replace(
                self.hub.cfg, txdelay_sec=value / 100,
                sources={**self.hub.cfg.sources, "txdelay_ms": "console"})
        shown = f"{value * unit}{' ms' if unit == 10 else ''}"
        log.info("%s %s %s", PARAM_NAMES.get(cmd, name), shown,
                 "sent to the TNC" if sent
                 else "not sent - this modem takes no KISS parameters (hub timing only)"
                 if not self.tnc.profile.kiss_params
                 else "set, goes to the TNC with the next init")
        if cmd == kiss.CMD_TXDELAY:
            self.out("TinyBox and client take it from the status query (CR70); "
                     "for the next start put it into txdelay_ms in the TNC section of kisshub.conf")
