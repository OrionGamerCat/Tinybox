"""Start the TinyBox client:  python -m tbclient [-c tbclient.conf]"""

from __future__ import annotations

import argparse
import asyncio
import logging
import socket
import sys

from prcore import release, termcolor

from . import VERSION, config
from .console import Console
from .core import ClientCore
from .web import WebServer

TAG = "[tbcli]"


def main() -> int:
    ap = argparse.ArgumentParser(prog="tbclient", description="TinyBox client")
    ap.add_argument("-c", "--config", default="tbclient.conf")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()
    try:
        cfg = config.load(args.config)
        color = cfg.color
    except (config.ConfigError, ValueError) as exc:
        cfg, color = None, "auto"
        error = exc
    root = logging.getLogger()
    root.setLevel(logging.DEBUG if args.verbose else logging.INFO)
    root.addHandler(termcolor.console_handler(TAG, color))
    log = logging.getLogger("tbclient")
    if cfg is None:
        log.error("Config error: %s", error)
        return 1
    start_block(log, cfg)

    async def run() -> None:
        core = ClientCore(cfg)
        await WebServer(core).start()
        web_line(log, cfg)
        if sys.stdin is not None and sys.stdin.isatty():
            def info() -> None:                 # console I: start block with all details
                start_block(log, cfg, details=True, head="info")
                web_line(log, cfg)
            Console(info).start_stdin()
        tasks = []
        if cfg.update_check:                    # PLANUNG 24: hint only, never an install
            tasks.append(asyncio.create_task(release.watch(
                core.on_release, cache=cfg.data_dir / "release.json", program="tbclient")))
        try:
            await core.run()
        finally:
            for t in tasks:
                t.cancel()

    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        pass
    except OSError as exc:
        log.error("%s", exc)
        return 1
    return 0


def start_block(log: logging.Logger, cfg: config.Config, details: bool = False,
                head: str = "start") -> None:
    """What the user wants to see at start: who am I, where to, over what.
    details: the radio lines as INFO too (console I), else only with -v."""
    log.info("TinyBox client %s - version %s (release %s)", head, VERSION, release.RELEASE,
             extra=termcolor.HEAD)
    termcolor.kv(log, "Your call", cfg.mycall)
    termcolor.kv(log, "Your locator", cfg.locator or "(not set)")
    termcolor.blank(log)
    termcolor.kv(log, "Your preferred TinyBox", cfg.tinybox_call)
    termcolor.kv(log, "Autoconnect to", cfg.tinybox_call if cfg.auto_connect else "off")
    termcolor.blank(log)
    termcolor.kv(log, "Connection via", cfg.link, config.link_note(cfg))
    termcolor.blank(log)
    for line in config.radio_lines(cfg):     # details only with -v, hints always
        if line.startswith("config hint: "):
            log.warning("%s", line)
        else:
            log.log(logging.INFO if details else logging.DEBUG, "%s", line)


def web_line(log: logging.Logger, cfg: config.Config) -> None:
    if cfg.web_host in ("0.0.0.0", "::"):
        termcolor.kv(log, "Web GUI on HTTP", f"http://{socket.gethostname()}:{cfg.web_port}/",
                     f"(on this PC: http://127.0.0.1:{cfg.web_port}/)", url=True)
    else:
        termcolor.kv(log, "Web GUI on HTTP", f"http://{cfg.web_host}:{cfg.web_port}/", url=True)


if __name__ == "__main__":
    sys.exit(main())
