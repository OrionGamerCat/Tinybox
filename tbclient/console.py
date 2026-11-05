"""tbclient console: commands typed into the tbclient window while it runs.

    H / ? / HELP   help
    I / INFO       the start block again: call, TinyBox, connection, radio values,
                   web GUI

Only for the window - what is typed in the web GUI terminal still goes to the
TinyBox. Same idea as the kisshub console (I / INFO).
"""

from __future__ import annotations

import asyncio
import sys
import threading
import time
from typing import Callable

HELP = """tbclient console:
  I / INFO             start block: call, TinyBox, connection, radio values, web GUI
  H / ?                this help
  Ctrl+C               stop the client"""


class Console:
    def __init__(self, info: Callable[[], None], out=print) -> None:
        self.info = info
        self.out = out

    def start_stdin(self) -> None:
        loop = asyncio.get_running_loop()

        def reader() -> None:
            while True:
                line = sys.stdin.readline()
                if line == "":
                    time.sleep(0.2)                  # closed/dead console: do not spin
                    continue
                loop.call_soon_threadsafe(self.handle_line, line.rstrip("\r\n"))

        threading.Thread(target=reader, name="tbclient-console", daemon=True).start()
        self.out("tbclient console: H for help")

    def handle_line(self, line: str) -> None:
        word = line.strip().partition(" ")[0].upper()
        if not word:
            return
        try:
            if word in ("H", "?", "HELP"):
                self.out(HELP)
            elif word in ("I", "INFO"):
                self.info()
            else:
                self.out(f"unknown command {word} - H for help (the web GUI terminal "
                         "talks to the TinyBox)")
        except Exception as exc:                     # a typo must never stop the client
            self.out(f"error: {exc}")
