"""Frame monitor for the web GUI (CR52 KISS mode, CR83 AGW mode).

In KISS mode TinyBox does AX.25 itself, so it knows every frame it hears on the
channel and every frame it sends. In AGW mode Direwolf hands out the frames it
hears raw ('k' / 'K'), and the TinyBox fork of Direwolf also the ones it sends
('O', CR83) - a standard Direwolf shows the own frames to nobody.
Each frame becomes one monitor entry in parts (time, calls, type, text, kind;
I and UI frames also len = payload bytes and hex = the payload as hex; every
frame raw = all its bytes as hex and ctl = offset of the control field, for
the frame inspector of the HEX view):
the web GUI colours the calls and filters, like the client's monitor (CR50).

The entries go to the logger "tinybox.frames". It does not propagate: the
frames do not end up in the log file or on the console, only the web GUI
attaches a handler. Without a handler nothing is built at all.
"""

from __future__ import annotations

import logging

from prcore import aprs
from prcore.ax25 import frame as ax
from prcore.ax25.frame import AX25Error

flog = logging.getLogger("tinybox.frames")
flog.propagate = False
flog.setLevel(logging.INFO)

U_NAMES = {0x2F: "SABM", 0x6F: "SABME", 0x43: "DISC", 0x0F: "DM", 0x63: "UA", 0x87: "FRMR",
           0x03: "UI", 0xAF: "XID", 0xE3: "TEST"}
S_NAMES = {0x01: "RR", 0x05: "RNR", 0x09: "REJ", 0x0D: "SREJ"}
PID_NO_L3 = 0xF0

# CR55: APRS in plain language - telemetry definitions heard so far and the
# own position (from the locator; the web GUI sets it)
aprs_memory = aprs.TelemetryMemory()
home: tuple[float, float] | None = None


def frame_type(control: int, ext: int | None = None) -> str:
    """'I 3,2', 'RR 4', 'SABM', 'UI'; '+' marks the poll/final bit. ext = the
    second control byte of an I or S frame with modulo 128."""
    if control & 0x03 == 0x03:
        return U_NAMES.get(control & 0xEF, f"U{control:02X}") + ("+" if control & 0x10 else "")
    if ext is not None:
        pf, nr = ("+" if ext & 0x01 else ""), ext >> 1
        if control & 0x01 == 0:
            return f"I {control >> 1},{nr}{pf}"
        return f"{S_NAMES.get(control & 0x0F, 'S?')} {nr}{pf}"
    pf = "+" if control & 0x10 else ""
    if control & 0x01 == 0:
        return f"I {(control >> 1) & 7},{(control >> 5) & 7}{pf}"
    return f"{S_NAMES.get(control & 0x0F, 'S?')} {(control >> 5) & 7}{pf}"


def guess_mod128(rest: bytes) -> bool:
    """Modulo 128 for a pair we have no link with: an I frame has the PID right
    after one control byte (mod 8) or after two (mod 128); an S frame is one
    byte long (mod 8) or two (mod 128)."""
    control = rest[0]
    if control & 0x03 == 0x03:
        return False
    if control & 0x01 == 0:
        return len(rest) >= 3 and rest[1] != PID_NO_L3 and rest[2] == PID_NO_L3
    return len(rest) == 2


def text_of(info: bytes) -> str:
    raw = info.decode("utf-8", "replace").replace("\r", " ").replace("\n", " ")
    return "".join(c if c.isprintable() else "." for c in raw)[:200].rstrip()


def entry(data: bytes, *, tx: bool, mycall: str, mod128: bool | None = None) -> dict | None:
    """One monitor entry from a raw AX.25 frame (without KISS framing).
    kind = what a TinyBox sends besides normal text ("" for anything else):
        chat     UI to TBCHAT-n: chat events
        quality  %Q lines (link quality numbers)
        mail     UI to TBMAIL: new private mail
        beacon   any other UI frame of this TinyBox (CR48)
        proto    I frame with client protocol lines (//IN, //SYNC ...)"""
    try:
        dest, src, path, repeated = ax.peek(data)
    except AX25Error:
        return None
    off = 7 * (2 + len(path))
    rest = data[off:]
    if not rest:
        return None
    control = rest[0]
    if mod128 is None:
        mod128 = guess_mod128(rest)
    ext = rest[1] if mod128 and control & 0x03 != 0x03 and len(rest) >= 2 else None
    if control & 0x03 == 0x03:                         # U: UI carries PID + info
        info = rest[2:] if (control & 0xEF) == 0x03 else b""
    elif control & 0x01 == 0:                          # I: control (1 or 2) + PID
        info = rest[3:] if ext is not None else rest[2:]
    else:
        info = b""
    text = text_of(info) if info else ""
    kind = ""
    typ = frame_type(control, ext)
    if typ.startswith("UI"):
        if dest.startswith("TBCHAT"):
            kind = "quality" if text.startswith("%Q ") else "chat"
        elif dest == "TBMAIL":
            kind = "mail"
        elif src == mycall:
            kind = "beacon"
    elif typ.startswith("I ") and text:
        if text.lstrip().startswith("//"):
            kind = "proto"
        elif text.startswith("%Q "):
            kind = "quality"
    e = {"src": src, "dst": dest,
         "via": [c + ("*" if h else "") for c, h in zip(path, repeated)],
         "typ": typ, "text": text, "kind": kind, "tx": tx,
         "raw": data.hex(), "ctl": off}             # whole frame for the inspector; control at ctl
    if control & 0x01 == 0 or (control & 0xEF) == 0x03:       # I and UI carry a payload
        e["len"] = len(info)                           # PacLen, shown as [n]
        e["hex"] = info.hex()                          # for the HEX view of the monitor
    if typ.startswith("UI") and kind in ("", "beacon") and rest[1:2] == bytes([PID_NO_L3]):
        try:
            a = aprs.decode(dest, src, path, repeated, info, memory=aprs_memory, home=home)
        except Exception:                              # the monitor must never break the radio
            a = None
        if a is not None:
            e["aprs"] = a
    return e


def emit(data: bytes, *, tx: bool, mycall: str, mod128: bool | None = None) -> None:
    """Hand one frame to the web GUI's monitor - if a web GUI listens."""
    if not flog.handlers:
        return
    try:
        e = entry(data, tx=tx, mycall=mycall, mod128=mod128)
    except Exception:                                  # the monitor must never break the radio
        return
    if e is not None:
        flog.info("frame", extra={"frame": e})
