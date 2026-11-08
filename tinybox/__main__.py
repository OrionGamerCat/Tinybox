"""Start TinyBox:  python -m tinybox [-c tinybox.conf]"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys

from prcore import termcolor

from . import VERSION, beacon, config, logsetup, notify, release, texts
from .adapters import agw, brocast, inbox, sysop, telnet, web
from .app import App

log = logging.getLogger("tinybox")

SHUTDOWN_GRACE_SEC = 10


def setup_logging(cfg: config.Config) -> tuple[logsetup.LogControl, sysop.MonitorFilter]:
    """Console, plus one log file per day if [logging] log_dir is set (CR32).
    Returns the LOG control and the console monitor filter (MON ON/OFF)."""
    return logsetup.setup(cfg, sysop.MonitorFilter)


async def housekeeping(app: App) -> None:
    # every minute: bulletins from the inbox may be valid for only 90 minutes
    while True:
        app.service.purge_expired()
        app.service.purge_bids()
        app.service.chat.purge()
        await asyncio.sleep(60)


async def close_sessions(app: App) -> None:
    """Say goodbye to connected users and give them time to receive it."""
    for s in app.registry:
        s.out(texts.SHUTDOWN)
        s.close()
    for _ in range(SHUTDOWN_GRACE_SEC * 10):
        if len(app.registry) == 0:
            return
        await asyncio.sleep(0.1)


async def run(cfg: config.Config, control: logsetup.LogControl,
              monitor_filter: sysop.MonitorFilter,
              config_path: str | None = None) -> bool:
    """Runs until SHUTDOWN/RESTART. Returns True for a restart."""
    # The start block answers the first question when debugging: which version
    # is running, what is switched on (CR32). It comes before everything else,
    # so a run always begins with it. Never tokens, only set/unset.
    head, *items = logsetup.start_block(cfg, VERSION, config_path, control.path,
                                        control.debug)
    log.info("%s", head, extra=termcolor.HEAD)
    termcolor.kv_block(log, items)
    for hint in cfg.hints or ():
        log.warning("config hint: %s", hint)
    app = App.create(cfg)
    app.stop_event = asyncio.Event()
    app.config_path = config_path
    app.log_control = control
    from . import clientnews
    app.service.client_news_id = clientnews.ensure_bulletin(app)

    servers = []
    if cfg.telnet.enabled:
        servers.append(await telnet.start(app))
    web_server = None
    if cfg.web.enabled:
        web_server = await web.start(app)
        # the login link contains the secret token: console only, never the log file
        termcolor.kv_print("[tinyb]", "Web GUI login", app.web_login_url,
                           cfg.console.color, url=True)
    if cfg.radio.interface == "kiss":              # own AX.25 layer 2 (PLANUNG.md 15)
        from .adapters import kiss
        app.agw = kiss.KissAdapter(app)
    else:
        app.agw = agw.AgwAdapter(app)
    notify.MailNotifier(app)
    app.beacon = beacon.Beacon(app)               # CR48: console BEACON works without [beacon]
    tasks = [asyncio.create_task(app.agw.run()),
             asyncio.create_task(housekeeping(app))]
    if cfg.axudp.enabled:                         # PLANUNG 25: second port next to the radio
        from .adapters import axudp
        app.axudp = axudp.AxudpAdapter(app)
        tasks.append(asyncio.create_task(app.axudp.run()))
    if cfg.beacon.enabled:
        app.beacon_task = asyncio.create_task(app.beacon.run())
    app.update = release.UpdateNotice(app)        # PLANUNG 24: new release on GitHub
    if cfg.update.check:
        tasks.append(asyncio.create_task(app.update.run()))
    if cfg.brocast.publish:
        tasks.append(await brocast.start(app))
    if cfg.inbox.enabled:
        tasks.append(await inbox.start(app))
    if cfg.forward.enabled:                 # optional: without it a standalone mailbox
        from .adapters import forward
        tasks.append(await forward.start(app))
    if cfg.mqtt.enabled:
        log.warning("[mqtt] enabled = yes, but MQTT follows in milestone M5 - ignored.")

    if cfg.console.enabled and sys.stdin is not None and sys.stdin.isatty():
        console = sysop.SysopConsole(app, monitor_filter)
        console.start()
        console.start_stdin()

    try:
        await app.stop_event.wait()
        await close_sessions(app)
    finally:
        if app.beacon_task is not None:            # CR82: RELOAD may start / stop it
            tasks.append(app.beacon_task)
        for task in tasks:
            task.cancel()
        for server in servers:
            server.close()
        if web_server is not None:
            web_server.close()
        await asyncio.gather(*tasks, return_exceptions=True)
        app.store.close()
        log.info("%s", logsetup.stop_line("RESTART" if app.restart else "SHUTDOWN"),
                 extra=termcolor.HEAD)
    return app.restart


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="tinybox", description="TinyBox mailbox")
    parser.add_argument("-c", "--config", default="tinybox.conf",
                        help="path to tinybox.conf (default: ./tinybox.conf)")
    parser.add_argument("--debugbundle", action="store_true",
                        help="write a debug bundle (log, version, config without "
                             "tokens) and exit - one file to hand over")
    args = parser.parse_args(argv)
    try:
        cfg = config.load(args.config)
    except config.ConfigError as exc:
        print(f"[tinyb] Config error: {exc}", file=sys.stderr)
        return 2
    control, monitor_filter = setup_logging(cfg)
    if args.debugbundle:
        return write_bundle_and_exit(cfg, control, args.config)
    restart = False
    try:
        restart = asyncio.run(run(cfg, control, monitor_filter, args.config))
    except KeyboardInterrupt:
        log.info("%s", logsetup.stop_line("Ctrl+C"))
    except Exception:
        log.exception("TinyBox stopped by an unexpected error")
        log.info("%s", logsetup.stop_line("crash"))
        raise
    if restart:
        return restart_process(argv)
    return 0


def write_bundle_and_exit(cfg: config.Config, control: logsetup.LogControl,
                          config_path: str) -> int:
    """--debugbundle without starting the mailbox: the store stays untouched."""
    app = App.create(cfg)
    app.config_path = config_path
    try:
        path = logsetup.write_bundle(app, control, VERSION)
    finally:
        app.store.close()
    print(f"[tinyb] debug bundle: {path}", flush=True)
    return 0


RESTART_EXIT = 3      # tinybox.bat / tinybox_dauerbetrieb.bat start again on this code


def restart_process(argv: list[str] | None) -> int:
    """RESTART: started from tinybox.bat (TINYBOX_LAUNCHER=1) the batch file starts
    TinyBox again on exit code 3 - in the same window, with new code and config.
    Otherwise the process replaces itself."""
    logging.shutdown()
    if os.environ.get("TINYBOX_LAUNCHER") == "1":
        return RESTART_EXIT
    args = sys.argv[1:] if argv is None else argv
    print("[tinyb] restarting ...", flush=True)
    os.execv(sys.executable, [sys.executable, "-m", "tinybox", *args])
    return RESTART_EXIT                   # not reached


if __name__ == "__main__":
    sys.exit(main())
