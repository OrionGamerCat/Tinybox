"""Local sysop console in the TinyBox window.

All mailbox commands work here with sysop rights (L, R, K, E, S, SB ...),
plus console commands: W, MON, LOG, DISC, STATUS, SHUTDOWN, RESTART.
Input comes from a background thread reading the keyboard, so the
mailbox keeps running while the sysop types.
"""

from __future__ import annotations

import asyncio
import logging
import sys
import threading
import time
from typing import Callable

from .. import VERSION, commands, config, logsetup, texts
from ..app import App
from ..config import base_call, normalize_call
from ..session import Session, State

log = logging.getLogger(__name__)


class MonitorFilter(logging.Filter):
    """Hides 'tinybox.monitor' records on a handler unless enabled."""

    def __init__(self, enabled: bool) -> None:
        super().__init__()
        self.enabled = enabled

    def filter(self, record: logging.LogRecord) -> bool:
        return self.enabled or not record.name.startswith("tinybox.monitor")


def _stdout_write(text: str) -> None:
    sys.stdout.write(text)
    sys.stdout.flush()


class ConsoleTransport:
    def __init__(self, write_fn: Callable[[str], None]) -> None:
        self.write_fn = write_fn

    def write(self, text: str) -> None:
        self.write_fn(text.replace("\r", "\n"))

    def close(self) -> None:
        pass

    def abort_output(self) -> None:
        pass


class SysopConsole:
    def __init__(self, app: App, monitor_filter: MonitorFilter | None = None,
                 write_fn: Callable[[str], None] | None = None) -> None:
        self.app = app
        self.filter = monitor_filter or MonitorFilter(app.cfg.console.monitor)
        self.transport = ConsoleTransport(write_fn or _stdout_write)
        self.session = Session(app.cfg.station.sysop_call, app.service, app.cfg,
                               self.transport, origin="sysop", sysop=True, monitor=False)

    def out(self, *lines: str) -> None:
        self.session.out(*lines)

    def start(self) -> None:
        self.out(texts.CONSOLE_BANNER)
        self.session.start()

    # --- keyboard thread ----------------------------------------------------

    def start_stdin(self) -> None:
        loop = asyncio.get_running_loop()
        interactive = sys.stdin is not None and sys.stdin.isatty()

        def reader() -> None:
            while True:
                line = sys.stdin.readline()
                if line == "":
                    if not interactive:
                        return  # input redirected and finished
                    line = "\x1a"  # Windows: CTRL-Z + Enter = end of message
                    time.sleep(0.2)  # guard against a busy loop on a dead console
                loop.call_soon_threadsafe(self.handle_line, line.rstrip("\r\n"))

        threading.Thread(target=reader, name="sysop-console", daemon=True).start()

    # --- input --------------------------------------------------------------

    def handle_line(self, line: str) -> None:
        if self.session.state == State.COMMAND:
            word, _, arg = line.strip().partition(" ")
            handler = self.COMMANDS.get(word.upper())
            if handler is not None:
                handler(self, arg.strip())
                if not (self.app.stop_event and self.app.stop_event.is_set()):
                    self.session.prompt()
                return
        self.session.handle_line(line)

    # --- console commands -----------------------------------------------------

    def cmd_help(self, arg: str) -> None:
        commands.cmd_help(self.session, "")
        self.out(*texts.HELP_CONSOLE)

    def cmd_info(self, arg: str) -> None:
        """INFO: the start block again (version, calls, radio values, adapters, log,
        config). Only INFO - I [call] stays the mailbox profile command."""
        from prcore import termcolor
        control = self.app.log_control
        head, *items = logsetup.start_block(
            self.app.cfg, VERSION, self.app.config_path,
            control.path if control else None, control.debug if control else set())
        tlog = logging.getLogger("tinybox")
        tlog.info("%s", head.replace(" start -----", " info -----"), extra=termcolor.HEAD)
        termcolor.kv_block(tlog, items)

    def cmd_bye(self, arg: str) -> None:
        self.out(texts.CONSOLE_NO_BYE)

    def cmd_who(self, arg: str) -> None:
        sessions = list(self.app.registry)
        if not sessions:
            self.out(texts.WHO_EMPTY)
            return
        self.out(texts.WHO_HEADER, *[
            texts.WHO_ROW.format(call=s.call, via=s.origin,
                                 since=s.started[:16].replace("T", " "),
                                 state=(f"chat {s.chat_board}" if s.chat_board
                                        else s.state.name.lower().replace("_", " ")))
            for s in sessions])

    def cmd_monitor(self, arg: str) -> None:
        arg = arg.upper()
        if arg in ("ON", "OFF"):
            self.filter.enabled = arg == "ON"
        elif arg == "":
            self.filter.enabled = not self.filter.enabled
        self.out(texts.MON_STATE.format(state="ON" if self.filter.enabled else "OFF"))

    def cmd_log(self, arg: str) -> None:
        """LOG, LOG DEBUG agw, LOG OFF [agw], LOG MARK text, LOG BUNDLE (CR32)."""
        control = self.app.log_control
        if control is None:
            self.out(texts.LOG_NO_FILE)
            return
        word, _, rest = arg.partition(" ")
        word, rest = word.upper(), rest.strip()
        if word in ("DEBUG", "OFF") and not rest and word == "OFF":
            control.clear_debug()
        elif word in ("DEBUG", "OFF"):
            known = control.set_debug(rest.replace(";", ",").split(","), word == "DEBUG")
            if not known:
                self.out(texts.LOG_UNKNOWN.format(
                    comps=" ".join(logsetup.COMPONENTS) + " all"))
                return
        elif word == "MARK":
            if not rest:
                self.out(texts.USAGE_LOG)
                return
            self.out(texts.LOG_MARKED if control.mark(rest) else texts.LOG_NO_FILE)
            return
        elif word == "BUNDLE":
            try:
                path = logsetup.write_bundle(self.app, control, VERSION)
            except OSError as exc:
                self.out(texts.LOG_BUNDLE_FAILED.format(error=exc))
                return
            self.out(texts.LOG_BUNDLE_DONE.format(path=path))
            return
        elif word:
            self.out(texts.USAGE_LOG)
            return
        path = control.path
        values = dict(level=control.level,
                      debug=",".join(sorted(control.debug)) or "-",
                      file=path or "none ([logging] log_dir is empty)",
                      size=f"{control.size() / 1024:.0f} kB" if path else "-")
        self.out(*[line.format(**values) for line in texts.LOG_LINES])

    def cmd_disc(self, arg: str) -> None:
        if not arg:
            self.out(texts.USAGE_DISC)
            return
        call = normalize_call(arg)
        sessions = list(self.app.registry)
        targets = [s for s in sessions if s.call == call] or \
                  [s for s in sessions if "-" not in call and base_call(s.call) == call]
        if not targets:
            self.out(texts.DISC_NONE.format(call=call))
            return
        for s in targets:
            s.out(texts.DISC_BY_SYSOP)
            s.close()
            log.info("%s disconnected by sysop", s.call)
            self.out(texts.DISC_DONE.format(call=s.call))

    def cmd_status(self, arg: str) -> None:
        cfg = self.app.cfg
        msgs = self.app.store.list_messages()
        agw = self.app.agw
        where = (agw.describe() if agw is not None and cfg.radio.interface == "kiss"
                 else f"{cfg.direwolf.agw_host}:{cfg.direwolf.agw_port}")
        if agw is None:
            agw_state = "not started"
        elif agw.connected.is_set():
            agw_state = f"connected ({where})"
        else:
            agw_state = f"NOT connected ({where})"
        if agw is not None and hasattr(agw, "radio_state"):       # KISS mode (CR41)
            r = agw.radio_state()
            if r["tnc_state"]:
                agw_state += f", TNC {r['tnc']} {r['tnc_state']}"
                if r["tnc_error"] and r["tnc_state"] != "kiss":
                    agw_state += f" ({r['tnc_error']})"
            elif r["hub"] == "unreachable":
                agw_state += ", kisshub status not available"
        values = dict(
            version=VERSION, mailbox=cfg.station.mailbox_call, sysop=cfg.station.sysop_call,
            since=self.app.started[:16].replace("T", " ") + " UTC", agw=agw_state,
            users=len(self.app.registry), max_users=cfg.mailbox.max_users,
            msgs=len(msgs), private=sum(m.type == "P" for m in msgs),
            bulletins=sum(m.type == "B" for m in msgs),
            unread=sum(m.type == "P" and m.status == "N" for m in msgs),
            data_dir=cfg.storage.data_dir,
        )
        self.out(*[line.format(**values) for line in texts.STATUS_LINES])
        if self.app.axudp is not None:                  # PLANUNG 25
            st = self.app.axudp.state()
            drop = ", ".join(f"{k} {v}" for k, v in st["dropped"].items() if v)
            self.out(texts.STATUS_AXUDP.format(
                listen=st["listen"], up="up" if st["up"] else "DOWN",
                peers=",".join(st["peers"]) or "-", links=",".join(st["links"]) or "-",
                rx=st["rx"], tx=st["tx"], dropped=f", dropped: {drop}" if drop else ""))
        notice = getattr(self.app, "update", None)
        if notice is not None and notice.result is not None and notice.result.newer:
            r = notice.result
            self.out(texts.UPDATE_NEWER.format(tag=r.latest, cur=r.current, url=r.url))
        left = self.app.shutdown.seconds_left() if self.app.shutdown else None
        if left is not None:
            self.out(texts.SHUTDOWN_PENDING.format(sec=left))

    def cmd_web(self, arg: str) -> None:
        # shown on the console only - it contains the secret token
        self.out(f"Web GUI login: {self.app.web_login_url}" if self.app.web_login_url
                 else "Web GUI is disabled ([web] enabled = no).")

    def cmd_fwd(self, arg: str) -> None:
        """FWD: forward status; FWD call: connect to that partner now."""
        fwd = self.app.forward
        if fwd is None:
            self.out(texts.FWD_OFF)
            return
        if not arg:
            self.out(*fwd.status_lines())
            return
        call = normalize_call(arg.split()[0])

        async def go() -> None:
            try:
                r = await fwd.call(call)
                self.out(texts.FWD_DONE.format(call=call, result=r.summary()))
            except Exception as exc:          # tell the sysop, keep the console alive
                self.out(texts.FWD_FAILED.format(call=call, error=exc or type(exc).__name__))
            self.session.prompt()

        self.out(texts.FWD_START.format(call=call))
        fwd._spawn(go())

    def cmd_fwq(self, arg: str) -> None:
        """FWQ: messages waiting for forwarding."""
        if self.app.forward is None:
            self.out(texts.FWD_OFF)
            return
        rows = self.app.store.fwd_queue_list()
        if not rows:
            self.out(texts.FWQ_EMPTY)
            return
        self.out(texts.FWQ_HEADER, *[texts.FWQ_ROW.format(partner=p, id=i, state=s,
                                                          changed=c[:16].replace("T", " "))
                                     for p, i, s, c in rows])

    def _hold_rel(self, arg: str, release: bool) -> None:
        fwd = self.app.forward
        if fwd is None:
            self.out(texts.FWD_OFF)
            return
        nums = arg.split()
        if not nums or not all(x.isdigit() for x in nums):
            self.out(texts.USAGE_HOLD)
            return
        for x in nums:
            msg_id = int(x)
            try:
                if release:
                    state = fwd.release(msg_id)
                    msg = self.app.store.get(msg_id)
                    self.out(texts.RELEASED[state].format(id=msg_id, at=msg.at_addr if msg else ""))
                else:
                    fwd.hold(msg_id)
                    self.out(texts.HELD.format(id=msg_id))
            except KeyError:
                self.out(texts.NO_SUCH_MSG.format(id=msg_id))

    def cmd_hold(self, arg: str) -> None:
        """HOLD n: keep a message from forwarding."""
        self._hold_rel(arg, release=False)

    def cmd_rel(self, arg: str) -> None:
        """REL n: release a held message."""
        self._hold_rel(arg, release=True)

    def cmd_shutdown(self, arg: str) -> None:
        """SHUTDOWN [seconds] warns all stations first; NOW at once; CANCEL."""
        arg = arg.strip().upper()
        timer = self.app.shutdown
        if arg == "CANCEL":
            self.out(texts.SHUTDOWN_CANCEL_DONE if timer.cancel() else texts.SHUTDOWN_NONE)
            return
        if arg and arg != "NOW" and not arg.isdigit():
            self.out(texts.USAGE_SHUTDOWN)
            return
        users = len(self.app.registry)
        # nobody connected and no time given: no reason to wait
        if arg == "NOW" or arg == "0" or (not arg and users == 0):
            self.out(texts.SHUTTING_DOWN)
            if self.app.stop_event is not None:
                self.app.stop_event.set()
            return
        sec = timer.schedule(int(arg) if arg else 60, self.app.cfg.station.sysop_call)
        self.out(texts.SHUTDOWN_SCHEDULED.format(sec=sec, n=users))

    def cmd_restart(self, arg: str) -> None:
        """RESTART [seconds|NOW|CANCEL]: like SHUTDOWN, then TinyBox starts again.
        tinybox.conf is checked first - with an error nothing happens."""
        arg = arg.strip().upper()
        timer = self.app.shutdown
        if arg == "CANCEL":
            self.out(texts.SHUTDOWN_CANCEL_DONE if timer.cancel() else texts.SHUTDOWN_NONE)
            return
        if arg and arg != "NOW" and not arg.isdigit():
            self.out(texts.USAGE_RESTART)
            return
        if self.app.config_path:
            try:
                config.load(self.app.config_path)
            except config.ConfigError as exc:
                self.out(texts.RESTART_BAD_CONFIG.format(error=exc))
                return
            self.out(texts.RESTART_CONFIG_OK)
        users = len(self.app.registry)
        if arg == "NOW" or arg == "0" or (not arg and users == 0):
            self.out(texts.RESTARTING)
            self.app.restart = True
            if self.app.stop_event is not None:
                self.app.stop_event.set()
            return
        sec = timer.schedule(int(arg) if arg else 60, self.app.cfg.station.sysop_call,
                             restart=True)
        self.out(texts.RESTART_SCHEDULED.format(sec=sec, n=users))

    def cmd_beacon(self, arg: str) -> None:
        """BEACON: send the beacon now and show it (CR48)."""
        from ..beacon import Beacon, beacon_text
        b = getattr(self.app, "beacon", None) or Beacon(self.app)
        self.app.beacon = b
        text = b.send_now()
        cfg = self.app.cfg.beacon
        if text:
            self.out(texts.BEACON_SENT.format(dest=cfg.dest, text=text))
        elif not beacon_text(self.app.cfg, self.app.service):
            self.out(texts.BEACON_EMPTY)
        else:
            self.out(texts.BEACON_NO_RADIO)
        self.out(texts.BEACON_STATE.format(
            state=f"every {cfg.interval_min} min" if cfg.enabled else "off ([beacon] enabled = no)",
            n=b.sent))

    def cmd_update(self, arg: str) -> None:
        """UPDATE: ask GitHub now for a new release (PLANUNG 24).
        UPDATE NEWS: send the TBNEWS bulletin of that release now (again)."""
        notice = getattr(self.app, "update", None)
        if notice is None:
            from ..release import UpdateNotice
            notice = self.app.update = UpdateNotice(self.app)
        if arg.upper() == "NEWS":
            r = notice.result
            if r is None or not r.newer:
                self.out(texts.UPDATE_NO_NEWS.format(cur=VERSION))
                return
            msg_id = notice.announce(r, force=True)
            self.out(texts.UPDATE_NEWS_SENT.format(n=msg_id, tag=r.latest))
            return
        self.out(texts.UPDATE_ASKING)

        async def ask() -> None:
            r = await notice.check_now()
            if r is None:
                self.out(texts.UPDATE_UNKNOWN)
            elif r.newer:
                self.out(texts.UPDATE_NEWER.format(tag=r.latest, cur=r.current, url=r.url))
                self.out(texts.UPDATE_ANNOUNCED if notice.announced() == r.latest
                         else texts.UPDATE_NOT_ANNOUNCED)
            else:
                self.out(texts.UPDATE_CURRENT.format(cur=r.current))
            self.session.prompt()

        asyncio.get_running_loop().create_task(ask())

    COMMANDS: dict[str, Callable[["SysopConsole", str], None]] = {
        "H": cmd_help, "?": cmd_help, "HELP": cmd_help,
        "B": cmd_bye, "BYE": cmd_bye,
        "W": cmd_who, "WHO": cmd_who,
        "INFO": cmd_info,
        "MON": cmd_monitor,
        "LOG": cmd_log,
        "DISC": cmd_disc,
        "STATUS": cmd_status,
        "BEACON": cmd_beacon,
        "UPDATE": cmd_update,
        "WEB": cmd_web,
        "FWD": cmd_fwd,
        "FWQ": cmd_fwq,
        "HOLD": cmd_hold,
        "REL": cmd_rel,
        "SHUTDOWN": cmd_shutdown,
        "RESTART": cmd_restart,
    }
