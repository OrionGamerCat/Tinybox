"""Pictures between two TBClients (CR78) - the CR12 way, without a TinyBox.

The sender keeps the picture; over the air goes only the reference, as a
chat line like in a TinyBox board (prcore/chatimg.py):

    ~#<hash 6 hex><size 2 hex><blurhash>[ caption]

It lands in the chat history of both sides. The other side shows the blurred
placeholder and fetches the bytes on a tap - straight from the sender:

    //IMG <hash> [<offset>]           -> //I <hash> <offset> <total> + the bytes
                                      or //NOIMG <hash>

A client gives a picture only to the station it sent it to (the reference
is in its sent history with that station). The bytes go to Direwolf in one go, the AX.25 window paces them; nothing
else is sent in between (the line and the bytes are handed over together).
A download broken off by the link starts again from the beginning when
tapped (the offset is in the protocol for later). Both need the cap IMG; pictures
are files in data/tbclient/images/ like those from the TinyBox.
"""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING

from prcore import chatimg

if TYPE_CHECKING:
    from .peer import Peer

log = logging.getLogger(__name__)

PEER_IMG_MAX = 8192        # bytes, like the default image_max of a TinyBox board
IDLE_SEC = 120             # a download without a byte for this long gives up


class PeerImages:
    def __init__(self, peer: "Peer") -> None:
        self.peer = peer
        self._want: str | None = None                  # the download under way
        self._last = 0.0                               # time of its last byte

    @property
    def core(self):
        return self.peer.ch.core

    @property
    def loading(self) -> dict:
        return self.core.images.loading              # shared with the TinyBox chat (GUI)

    @property
    def store(self):
        return self.core.images.store

    @property
    def ok(self) -> bool:
        return "IMG" in self.peer.caps and self.peer.ch.state == "online" \
            and self.peer.ch.link.kind != "telnet"

    # --- sending a picture ------------------------------------------------------------

    def send(self, data: bytes, blurhash: str, caption: str = "") -> str | None:
        if not self.ok or not data or len(data) > PEER_IMG_MAX or chatimg.image_type(data) is None:
            return None
        if not blurhash or chatimg.blurhash_len(blurhash[:1]) != len(blurhash) \
                or any(c not in chatimg.B83 for c in blurhash):
            return None
        h = chatimg.image_hash(data)
        self.store.put(h, data)
        line = f"~#{h}{chatimg.size_code(len(data))}{blurhash}"
        caption = caption.replace("\r", " ").replace("\n", " ").strip()[:150]
        if caption:
            line += " " + caption
        self.peer.ch.send_raw(line)                   # chat line + history, like typed
        return h

    # --- fetching one -----------------------------------------------------------------

    def fetch(self, h: str) -> bool:
        if not chatimg.HASH_RE.match(h) or self.store.has(h) or not self.ok:
            return False
        ld = self.loading.get(h)
        if ld and not ld.get("error") and self._want == h \
                and time.monotonic() - self._last < IDLE_SEC:
            return True                               # on its way
        if self._want and self._want != h and time.monotonic() - self._last < IDLE_SEC:
            return False                              # one at a time
        self._want, self._last = h, time.monotonic()
        self.loading[h] = {"done": 0, "total": 0, "error": ""}
        self.peer._send(f"//IMG {h}")
        self.core._touch()
        return True

    def link_lost(self) -> None:
        if self._want:
            self._fail(self._want, "connection lost - tap to try again")

    def _fail(self, h: str, why: str) -> None:
        self.loading[h] = {**self.loading.get(h, {}), "error": why}
        if self._want == h:
            self._want = None
        self.core._touch()

    # --- lines from the other side ----------------------------------------------------

    def take(self, word: str, rest: str) -> bool:
        p = rest.split()
        if word == "IMG" and p:
            self._serve(p[0], int(p[1]) if len(p) > 1 and p[1].isdigit() else 0)
            return True
        if word == "I" and len(p) == 3 and p[1].isdigit() and p[2].isdigit():
            self._incoming(p[0], int(p[1]), int(p[2]))
            return True
        if word == "NOIMG" and p:
            self._fail(p[0], "not available any more")
            return True
        return False

    def _sent_to_them(self, h: str) -> bool:
        pc = self.core.peerchat
        if pc is None:
            return False
        return any(m["dir"] == "tx" and m["text"].startswith("~#" + h)
                   for m in pc.messages(self.peer.call))

    def _serve(self, h: str, off: int) -> None:
        data = self.store.get(h) if chatimg.HASH_RE.match(h) else None
        if data is None or not self._sent_to_them(h) or off > len(data):
            self.peer._send(f"//NOIMG {h}")
            return
        # the line and the bytes in one go - nothing can come in between
        self.peer._send(f"//I {h} {off} {len(data)}")
        self.peer.ch.link.send_bytes(data[off:])
        log.info("image %s to %s (%d bytes from %d)", h, self.peer.call, len(data), off)

    def _incoming(self, h: str, off: int, total: int) -> None:
        n = max(0, total - off)
        ld = self.loading.setdefault(h, {"done": off, "total": total, "error": ""})
        ld["total"] = total

        def progress(got: int) -> None:
            self._last = time.monotonic()
            ld["done"] = off + got
            self.core._touch()

        def done(data: bytes) -> None:
            whole = data
            if self._want == h:
                self._want = None
            if chatimg.image_hash(whole) != h or chatimg.image_type(whole) is None:
                self._fail(h, "damaged, tap to try again")
                return
            self.store.put(h, whole)
            self.loading.pop(h, None)
            log.info("image %s from %s (%d bytes)", h, self.peer.call, len(whole))
            self.core._touch()

        if off:                                       # we always ask from 0
            log.warning("image %s from %s: offset %d not asked for", h, self.peer.call, off)
        self.peer.ch.link.splitter.expect(n, done, progress)
