"""TNC profiles: read from kisshub.conf, one section per TNC (kisshub 2026.11.05).

Every value of a TNC is in its own section of kisshub.conf - the port, the wake and
init dialog, the radio values and the AX.25 recommendation. This module has no TNC
values of its own any more; it only knows how to read such a section:

    [pk232]                    ; the section name is the profile name (kisshub -p pk232)
    type = tnc                 ; tnc | vara | direwolf | modem73 - the code behind it
    base = ...                 ; optional: take all keys of another TNC section first
    wake = ...  init = ...  exit = ...      ; the terminal dialog, one step per line

What the four types do in code:
    tnc       a KISS TNC on a serial port or TCP, with or without a terminal dialog
    vara      VARA FM / HF KISS-TCP: connected mode tunnelled in KISS type 2 (tnc.py)
    direwolf  Direwolf's KISSPORT: radio values from its direwolf.conf
    modem73   modem73 OFDM modem: kisshub starts it (modem73.py), air time from its mode

Steps (wake, init, exit) - one step per line of the value:
    <send> [! <answer> <answer> ...] [@<seconds>]
    <send>     text; <CR> <LF> and <xx> (two hex digits) are bytes, ^C is Ctrl-C
               init and exit lines get a CR at the end, wake lines do not
    ! ...      answers that count as "the TNC answered" - default: the section's prompt
    !-         wait only, expect nothing (the line that enters KISS)
    @2.5       how long to wait - default: the section's step_timeout
The test history of the dialogs (which device, which firmware, which date) is in
docs/kiss-mode-konzept.md and in the comments of kisshub.conf.example.
"""

from __future__ import annotations

import configparser
import dataclasses
import re
from dataclasses import dataclass

KISS_EXIT = bytes((0xC0, 0xFF, 0xC0))      # KISS protocol: leave KISS (tnc.py, on stop)

TYPES = ("tnc", "vara", "direwolf", "modem73")
TUNNEL_MODES = ("no", "connected", "all")
GLOBAL_SECTIONS = ("kisshub", "server", "log", "console", "update")
# sections of the conf before 2026.11.05 - a file with them is refused with a hint
OLD_SECTIONS = ("tnc", "kiss", "ax25", "vara")
AX25_KEYS = ("paclen", "maxframe", "maxframe_ext", "n2", "t1_min_sec", "t1_max_sec",
             "t2_sec", "t3_sec")


class ProfileError(Exception):
    pass


@dataclass(frozen=True)
class Step:
    """Send `send`, then wait up to `timeout` s until one of `expect` arrives.
    Empty `expect`: just wait `timeout` (e.g. the line that enters KISS)."""
    send: bytes
    expect: tuple[bytes, ...] = ()
    timeout: float = 3.0
    note: str = ""


@dataclass(frozen=True)
class Profile:
    name: str
    type: str = "tnc"
    display: str = ""                  # name for status displays, e.g. "PK-232"
    notes: str = ""
    hint: str = ""                     # added to the error when the TNC does not answer
    start_note: str = ""               # one line at start; {air_baud} and {switch} filled in
    serial_baud: int = 9600
    dtr: bool = True
    rts: bool = True
    rtscts: bool = False               # RTS/CTS hardware flow control
    wake: tuple[Step, ...] = ()        # empty: the TNC is in KISS by itself
    init: tuple[Step, ...] = ()
    exit_kiss: bool = False            # C0 FF C0 when kisshub stops
    exit_lines: tuple[Step, ...] = ()  # sent after leaving KISS
    settle_sec: float = 1.0            # after the last init line, before KISS frames
    kiss_params: bool = True           # send TXDELAY/P/SlotTime (send_params)
    smack: bool = False                # send data frames with CRC (SMACK, TNC7multi)
    hbaud: tuple[int, ...] = ()        # air rates the TNC is set to with "HBAUD n" in init
    switch_positions: tuple[tuple[int, str], ...] = ()   # air rate -> position ON THE
                                       # DEVICE (TNC7multi rotary switch), not set by kisshub
    tunnel: str = "no"                 # VARA: no | connected | all
    bundle_ms: int = 0                 # VARA tunnel: collect frames into one type-2 frame
    bundle_max: int = 4000             # bytes per bundle (VARA takes up to 5000)

    @property
    def air_bauds(self) -> tuple[int, ...]:
        return tuple(b for b, _ in self.switch_positions)

    def switch(self, air_baud: int) -> str:
        return dict(self.switch_positions).get(air_baud, "a KISS position (Conf mode)")


# --- byte notation -------------------------------------------------------------------

_TOKEN = re.compile(r"<(CR|LF|[0-9A-Fa-f]{2})>|\^([@A-Za-z\[\\\]^_])")


def encode(text: str) -> bytes:
    """'^C<CR>' -> b'\\x03\\r', '<C0><FF><C0>' -> b'\\xc0\\xff\\xc0'."""
    out = bytearray()
    pos = 0
    for m in _TOKEN.finditer(text):
        out += text[pos:m.start()].encode("ascii")
        tok, ctl = m.groups()
        if tok == "CR":
            out += b"\r"
        elif tok == "LF":
            out += b"\n"
        elif tok:
            out.append(int(tok, 16))
        else:
            out.append(ord(ctl.upper()) & 0x1F)
        pos = m.end()
    out += text[pos:].encode("ascii")
    return bytes(out)


def parse_steps(value: str, *, cr: bool, prompt: str, timeout: float,
                what: str) -> tuple[Step, ...]:
    """One step per line: '<send> [! answers | !-] [@seconds]'."""
    steps = []
    for raw in value.splitlines():
        text = raw.strip()
        if not text:
            continue
        wait = timeout
        m = re.search(r"\s*@\s*([0-9.]+)\s*$", text)
        if m:
            try:
                wait = float(m.group(1))
            except ValueError:
                raise ProfileError(f"{what}: '{raw.strip()}' - @ needs seconds") from None
            text = text[:m.start()]
        send, bang, answers = text.partition("!")
        send = send.strip()
        if bang:
            words = answers.split()
            expect = () if words in ([], ["-"]) else tuple(w.encode("ascii") for w in words)
        else:
            if not prompt:
                raise ProfileError(f"{what}: '{raw.strip()}' waits for the prompt - "
                                   "set prompt = (e.g. cmd:) or write !- / ! <answer>")
            expect = (prompt.encode("ascii"),)
        if not send:
            raise ProfileError(f"{what}: '{raw.strip()}' - nothing to send")
        try:
            data = encode(send) + (b"\r" if cr else b"")
        except UnicodeEncodeError:
            raise ProfileError(f"{what}: '{send}' - ASCII only, other bytes as <xx>") from None
        steps.append(Step(data, expect, wait, send))
    return tuple(steps)


# --- sections ------------------------------------------------------------------------

def old_format(cp: configparser.ConfigParser) -> list[str]:
    """Sections that only the conf before 2026.11.05 had."""
    return [s for s in cp.sections() if s in OLD_SECTIONS or "." in s]


def names(cp: configparser.ConfigParser) -> list[str]:
    """The TNC sections = every section that is not a global one."""
    return [s for s in cp.sections() if s not in GLOBAL_SECTIONS]


def merged(cp: configparser.ConfigParser, name: str) -> dict[str, str]:
    """The keys of [name], with 'base = other' the keys of [other] underneath."""
    chain = []
    cur = name
    while cur:
        if cur in chain:
            raise ProfileError(f"[{name}] base: loop {' -> '.join(chain + [cur])}")
        if not cp.has_section(cur) or cur in GLOBAL_SECTIONS:
            where = f"[{chain[-1]}] base = {cur}" if chain else f"-p {cur}"
            raise ProfileError(f"{where}: no TNC section of that name")
        chain.append(cur)
        cur = cp.get(cur, "base", fallback="").strip().lower()
    keys: dict[str, str] = {}
    for sec in reversed(chain):
        for key, value in cp.items(sec, raw=True):
            if key not in cp.defaults():
                keys[key] = value
    keys.pop("base", None)
    return keys


def build(name: str, get) -> Profile:
    """Profile from a TNC section. get(key, default, kind) reads it (config.py); a
    default of None means: the key must be there."""
    ptype = get("type", None).lower()
    if ptype not in TYPES:
        raise ProfileError(f"[{name}] type = {ptype}: use {' | '.join(TYPES)}")
    wake_text = get("wake", "")
    init_text = get("init", "")
    exit_text = get("exit", "")
    dialog = wake_text.strip() or init_text.strip() or exit_text.strip()
    prompt = get("prompt", "")
    timeout = get("step_timeout", None if dialog else 3.0, float)

    def steps(key: str, text: str, cr: bool) -> tuple[Step, ...]:
        return parse_steps(text, cr=cr, prompt=prompt, timeout=timeout, what=f"[{name}] {key}")

    tunnel = get("vara_tunnel", None if ptype == "vara" else "no").lower()
    if tunnel not in TUNNEL_MODES:
        raise ProfileError(f"[{name}] vara_tunnel: use {', '.join(TUNNEL_MODES)}")
    if tunnel != "no" and ptype != "vara":
        raise ProfileError(f"[{name}] vara_tunnel: only with type = vara")
    bundle_ms = get("vara_bundle_ms", 0, int)
    bundle_max = get("vara_bundle_max", 4000, int)
    if not 0 <= bundle_ms <= 2000:
        raise ProfileError(f"[{name}] vara_bundle_ms: 0 (off) .. 2000")
    if not 100 <= bundle_max <= 5000:
        raise ProfileError(f"[{name}] vara_bundle_max: 100 .. 5000 (VARA's limit)")
    if bundle_ms and tunnel == "no":
        raise ProfileError(f"[{name}] vara_bundle_ms: only with the VARA tunnel (vara_tunnel)")
    smack = get("smack", False, bool)
    if smack and ptype == "vara":
        raise ProfileError(f"[{name}] smack: not with VARA (it reads the type byte itself)")
    send_params = get("send_params", None if ptype == "tnc" else False, bool)
    if send_params and ptype != "tnc":
        raise ProfileError(f"[{name}] send_params: must be no with type = {ptype} - "
                           + ("VARA reads KISS commands 1 and 2 as its frame types and "
                              "would send them on the air" if ptype == "vara" else
                              "the modem keeps these values itself"))
    return Profile(
        name=name, type=ptype,
        display=get("display", name), notes=get("notes", ""), hint=get("hint", ""),
        start_note=get("start_note", ""),
        serial_baud=get("serial_baud", 9600, int),
        dtr=get("dtr", True, bool), rts=get("rts", True, bool),
        rtscts=get("rtscts", False, bool),
        wake=steps("wake", wake_text, False),
        init=steps("init", init_text, True),
        exit_kiss=get("exit_kiss", None if ptype == "tnc" else False, bool),
        exit_lines=steps("exit", exit_text, True),
        settle_sec=get("settle_sec", None, float),
        kiss_params=send_params, smack=smack,
        hbaud=_bauds(get("hbaud", ""), f"[{name}] hbaud"),
        switch_positions=_positions(get("switch_positions", ""), name),
        tunnel=tunnel, bundle_ms=bundle_ms, bundle_max=bundle_max)


def _bauds(text: str, what: str) -> tuple[int, ...]:
    try:
        return tuple(int(x) for x in text.replace(",", " ").split())
    except ValueError:
        raise ProfileError(f"{what}: bit rates, e.g. 1200 9600") from None


def _positions(text: str, name: str) -> tuple[tuple[int, str], ...]:
    out = []
    for item in text.replace(",", " ").split():
        baud, colon, pos = item.partition(":")
        if not colon or not baud.isdigit() or not pos:
            raise ProfileError(f"[{name}] switch_positions: rate:position, e.g. 1200:1k2 9600:9k6")
        out.append((int(baud), pos))
    return tuple(out)


def with_hbaud(p: Profile, baud: int) -> Profile:
    """air_baud for a TNC with a switchable modem (hbaud = ..., TM-D710): the init line
    "HBAUD ..." becomes "HBAUD <baud>". Raises ValueError for a rate the TNC does
    not have or an init without an HBAUD line."""
    if baud not in p.hbaud:
        raise ValueError(f"{p.display or p.name} knows {' or '.join(map(str, p.hbaud))} Bd")
    if not any(s.note.upper().startswith("HBAUD ") for s in p.init):
        raise ValueError(f"hbaud is set, but init has no HBAUD line for {p.name}")
    steps = tuple(dataclasses.replace(s, send=f"HBAUD {baud}".encode("ascii") + b"\r",
                                      note=f"HBAUD {baud}")
                  if s.note.upper().startswith("HBAUD ") else s for s in p.init)
    return dataclasses.replace(p, init=steps)
