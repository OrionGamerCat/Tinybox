"""TNC profiles: how to reach the command prompt and switch into KISS.

A profile is data, not code: a list of wake steps (tried in order until one
gets an answer) and a list of init steps (each one must get its answer).
kisshub.conf can replace the init lines without touching code.

PK-232 / PK-232MBX - taken from pk232py (oe3gas/pk232py), measured on three
devices there (firmware 30.DEC.88, 01.AUG.91, 13.SEP.95):
    - serial 8N1, no XON/XOFF and no RTS/CTS on the port, DTR and RTS HIGH
      (P54.2: with DTR/RTS low the TNC did not answer, PuTTY with them high did)
    - wake chain (serial_manager.py, P43/P54): '*' (autobaud after power-up),
      CR, Ctrl-C + CR (COMMAND character, leaves Converse), XON + CR (a stray
      XOFF stops the TNC's own output), host mode exit (recovery frame +
      HOST OFF frame), and here also the KISS exit C0 FF C0 - after a hub run
      the TNC may still be in KISS
    - KISS init after TRM section 4.7.1 (pk232py comm/kiss.py), plus VHF ON and
      HBAUD 1200 (modes/packet_vhf.py): the 1200 Bd Bell 202 modem.
      EXPERT ON first (Gerhard, 14.10.2026): some of the commands are expert
      commands - without it the PK-232 answers "?EXPERT command" and ignores them.
      Order checked by Gerhard on the device; RESTART after AWLEN/PARITY (TRM) is
      not needed
      Tested on the air 14.10.2026 with device A, firmware Release 13.SEP.95
      (VHF, 1200 Bd). Other devices / firmware not yet.

Kenwood TM-D710: the TNC must be in packet mode (TNC key on the panel until
PACKET shows - in APRS mode the TNC gives no cmd:), then in terminal mode
"HBAUD 1200" + "KISS ON" + "RESTART" (tested by Gerhard in a terminal,
22.10.2026, COM7 at 9600 Bd). [kiss] air_baud = 9600 sends "HBAUD 9600" instead
(25.10.2026, not yet tried on the air). RTS/CTS on by default: the radio holds
CTS low while its small TNC buffer is full ([tnc] rtscts = no switches it off). Leaving: C0 FF C0, then KISS OFF.
TH-D74 / TH-D75: KISS is switched on in
the radio's menu - nothing to send. TNC2 with a pure KISS EPROM: nothing to send.
TH-D74/D75/TNC2 lines are from the manuals and still to be tried (K9/K10).

TNC7multi (IfD Guettner, TOS 1.04 - all from the handbook V1.04, 29.10.2026):
    - KISS/SMACK is a firmware mode chosen with the ROTARY SWITCH, there is no
      terminal dialog: position "1k2" = KISS 1200 Bd AFSK, "9k6" = KISS 9600 Bd
      FSK (handbook 4.1); positions 1-7 can be set up in Conf mode (f1 = KISS),
      position 1 is Flexnet out of the box. Each turn of the switch restarts the TNC.
      So: no wake, no init, and no leaving KISS - C0 FF C0 means nothing to it
      (back to the Conf menu only with the switch on "Conf").
    - PC side: USB (FTDI virtual COM port, default 115200 Bd, "u" in Conf mode)
      or RS232 (null modem cable, default 38400 Bd, "v"), 8N1. Config item c=2:
      USB if USB is active, else RS232. No flow control named for KISS.
    - SMACK: KISS with CRC-16. The TNC switches to SMACK by itself on the first
      CRC frame from the PC (kiss.encode_smack); back to plain KISS only by a
      restart. kisshub sends with CRC ([tnc] smack = yes, default for this
      profile) and drops received frames with a bad CRC.
    - KISS parameters the PC may set (handbook 4.1): TXDELAY (default 15 = 150 ms),
      Persistence (64), SlotTime (5 = 50 ms), Duplex (0); TXtail and SetHardware
      are not needed. Not settable over KISS (Conf mode only): modulation level
      (n, default 1000 mVss - "must be right for clean operation"), RX mute delay
      (m), PTT watchdog (g, 20 s).
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass

CR = b"\r"
CMD_PROMPT = b"cmd:"
KISS_EXIT = bytes((0xC0, 0xFF, 0xC0))

# PK-232 Host Mode frames (pk232py comm/constants.py)
PK_HOST_OFF = bytes((0x01, 0x4F, ord("H"), ord("O"), ord("N"), 0x17))
PK_RECOVERY = bytes((0x01, 0x01, 0x4F, ord("G"), ord("G"), 0x17))
CTRL_C = b"\x03"
XON = b"\x11"


@dataclass(frozen=True)
class Step:
    """Send `send`, then wait up to `timeout` s until one of `expect` arrives.
    Empty `expect`: just wait `timeout` (e.g. the line that enters KISS)."""
    send: bytes
    expect: tuple[bytes, ...] = (CMD_PROMPT,)
    timeout: float = 3.0
    note: str = ""


def line(text: str, timeout: float = 3.0, expect: tuple[bytes, ...] = (CMD_PROMPT,)) -> Step:
    return Step(text.encode("ascii") + CR, expect, timeout, text)


@dataclass(frozen=True)
class Profile:
    name: str
    serial_baud: int = 9600
    dtr: bool = True
    rts: bool = True
    rtscts: bool = False               # RTS/CTS hardware flow control ([tnc] rtscts)
    wake: tuple[Step, ...] = ()        # empty: the TNC is in KISS by itself
    init: tuple[Step, ...] = ()
    exit_kiss: bool = True             # C0 FF C0 when kisshub stops
    exit_lines: tuple[Step, ...] = ()  # sent after leaving KISS
    settle_sec: float = 1.0            # after the last init line, before KISS frames
    notes: str = ""
    hint: str = ""                     # added to the error when the TNC does not answer
    display: str = ""                  # name for status displays, e.g. "PK-232"
    kiss_params: bool = True           # send TXDELAY/P/SlotTime ([kiss] send_params default)
    tunnel: str = "no"                 # VARA: no | connected | all (see VARA_FM)
    bundle_ms: int = 0                 # VARA tunnel: collect frames this long into one
                                       # type-2 frame (0 = off) - see VARA_FM
    bundle_max: int = 4000             # bytes per bundle (VARA takes up to 5000)
    # CR70: the radio values belong to kisshub - TinyBox and the client read them
    # from the status query ("radio" block); kisshub.conf [kiss] may override them
    air_baud: int = 1200               # bit rate on the air (air time estimate)
    txdelay_ms: int = 300              # key-up to data
    max_lead_ms: int = 1500            # at most this much air time queued in the TNC
    tcp_port: int = 0                  # default [tnc] port with transport = tcp
    ax25: tuple[tuple[str, float | int | str], ...] = ()   # AX.25 recommendation
                                       # (tinybox.conf [ax25] key names); () = AX25_1200
    reads_direwolf_conf: bool = False  # profile direwolf: values from direwolf.conf
    hbaud: tuple[int, ...] = ()        # air rates the TNC can be set to with "HBAUD n";
                                       # [kiss] air_baud picks one and replaces the
                                       # HBAUD line of the init. () = rate fixed
    smack: bool = False                # send data frames with CRC (SMACK, TNC7multi)
    persist: int = 63                  # [kiss] persist default (KISS P, 0..255)
    slottime_ms: int = 100             # [kiss] slottime_ms default
    air_bauds: tuple[int, ...] = ()    # air rates set ON THE DEVICE (switch), not by
                                       # kisshub; another [kiss] air_baud only gives a hint
    start_note: str = ""               # one line at start; {air_baud} and {switch} filled in


# CR70: AX.25 recommendation for the stations, the same key names as [ax25] in
# tinybox.conf / tbclient.conf. 1200 Bd: the values TinyBox used so far.
AX25_1200 = (("paclen", 256), ("maxframe", 4), ("maxframe_ext", 7),
             ("t1_min_sec", 3.0), ("t1_max_sec", 30.0), ("t2_sec", 1.5))
# VARA FM Narrow over KISS, measured 18.10.2026 (docs/kiss-mode-konzept.md 8d):
# about 350 bit/s net with 2.7 s from PTT to data - a window of 4 x 256 bytes
# takes ~9 s, so T1 must not start below 18 s; T2 short, VARA is lossless
# 9600 Bd (TM-D710 on the data band, 25.10.2026): eight times the 1200 Bd rate,
# so a full window of 4-7 frames is on the air in ~1-2 s - T1 may start lower,
# T2 shorter. A starting point, still to be checked on the air.
AX25_9600 = (("paclen", 256), ("maxframe", 7), ("maxframe_ext", 7),
             ("t1_min_sec", 1.5), ("t1_max_sec", 15.0), ("t2_sec", 0.5))
AX25_VARA = (("paclen", 256), ("maxframe", 4), ("maxframe_ext", 4),
             ("t1_min_sec", 18.0), ("t1_max_sec", 90.0), ("t2_sec", 0.3))


PK232 = Profile(
    name="pk232", display="PK-232",
    serial_baud=9600,
    wake=(
        Step(b"*", (CMD_PROMPT, b"AEA", b"PK-232", b"Copyright"), 2.0, "autobaud '*'"),
        Step(CR, (CMD_PROMPT,), 1.5, "CR"),
        Step(CTRL_C + CR, (CMD_PROMPT,), 2.0, "Ctrl-C (Converse)"),
        Step(XON + CR, (CMD_PROMPT,), 2.0, "XON (stopped by XOFF)"),
        Step(KISS_EXIT + b"\x00" * 2, (), 2.0, "leave KISS"),
        Step(CR, (CMD_PROMPT,), 2.0, "CR after leaving KISS"),
        Step(PK_RECOVERY + PK_HOST_OFF, (), 1.0, "leave Host Mode"),
        Step(CR, (CMD_PROMPT,), 2.0, "CR after leaving Host Mode"),
    ),
    init=(
        # order and content checked on the device by Gerhard (14.10.2026):
        # EXPERT ON first (RAWHDLC, HPOLL, PPERSIST need it); VHF ON and HBAUD 1200
        # are the power-on defaults, sent anyway to be sure; RESTART not needed
        line("EXPERT ON"),
        line("VHF ON"),
        line("HBAUD 1200"),
        line("AWLEN 8"),
        line("PARITY 0"),
        line("CONMODE TRANS"),
        line("TRACE OFF"),
        line("HID OFF"),
        line("BEACON EVERY 0"),
        line("PACKET"),
        line("RAWHDLC ON"),
        line("HPOLL OFF"),
        line("PPERSIST ON"),
        # KISS ON gives no cmd: of its own on the device (17.10.2026): until then
        # every answer was one step late, so KISS ON only matched the cmd: of
        # PPERSIST; after a wake via 'CR after leaving KISS' the answers were in
        # step and the init failed at KISS ON. So: just its echo.
        line("KISS ON", timeout=1.0, expect=()),
        line("HOST ON", timeout=1.5, expect=()),       # from here on: KISS, no prompt
    ),
    exit_kiss=True,
    exit_lines=(line("KISS OFF"),),                    # leave it as pk232py expects it
    notes="PK-232/PK-232MBX, VHF port 1200 Bd",
)

TM_D710 = Profile(
    name="tm-d710", display="TM-D710",
    serial_baud=9600,                  # COM port of the radio (Gerhard: COM7, 9600 Bd)
    wake=(Step(CR, (CMD_PROMPT,), 2.0, "CR"),
          Step(KISS_EXIT + CR, (CMD_PROMPT,), 3.0, "leave KISS"),
          Step(CTRL_C + CR, (CMD_PROMPT,), 2.0, "Ctrl-C (Converse)"),
          Step(XON + CR, (CMD_PROMPT,), 2.0, "XON (stopped by XOFF)")),
    init=(
        # tested by Gerhard in a terminal on the device (22.10.2026):
        # HBAUD 1200 / KISS ON / RESTART. KISS ON is taken with or without a
        # cmd: (the PK-232 gave none, 17.10.2026); RESTART reboots the TNC into
        # KISS - no prompt any more, settle_sec gives it time to come up
        line("HBAUD 1200"),
        line("KISS ON", timeout=1.0, expect=()),
        line("RESTART", timeout=2.0, expect=()),
    ),
    exit_kiss=True,
    exit_lines=(line("KISS OFF"),),    # a terminal finds cmd: again, also after RESTART
    settle_sec=2.0,
    rtscts=True,                       # the radio paces kisshub over CTS (25.10.2026)
    hbaud=(1200, 9600),                # [kiss] air_baud = 9600 -> "HBAUD 9600"
    hint="TM-D710: press the TNC key until PACKET shows (not APRS), PC port = COM "
         "speed of the radio menu (9600)",
    notes="Kenwood TM-D710: TNC key -> packet mode first, 1200 or 9600 Bd on the data band",
)

TH_D74 = Profile(name="th-d74", display="TH-D74", serial_baud=9600, exit_kiss=False,
                 notes="Kenwood TH-D74: KISS on in the menu")
TH_D75 = Profile(name="th-d75", display="TH-D75", serial_baud=9600, exit_kiss=False,
                 notes="Kenwood TH-D75: KISS on in the menu")
TNC2_KISS = Profile(name="tnc2-kiss", display="TNC2", serial_baud=9600, exit_kiss=False,
                    notes="TNC2 with pure KISS EPROM")
TNC7MULTI = Profile(
    name="tnc7multi", display="TNC7multi",
    serial_baud=115200,                # USB default (u); RS232: 38400 (v) - handbook 5
    exit_kiss=False,                   # KISS is the switch position, not a command
    settle_sec=0.3,
    smack=True,                        # KISS with CRC, the TNC follows by itself
    txdelay_ms=150, persist=64, slottime_ms=50,     # the TNC's own defaults (4.1)
    air_bauds=(1200, 9600),            # built-in modem; other rates need the extra modem
    start_note="rotary switch on {switch} (KISS {air_baud} Bd); PC port USB 115200 / "
               "RS232 38400 Bd unless changed in Conf mode",
    notes="TNC7multi (IfD), KISS/SMACK - rotary switch 1k2 or 9k6",
)
TNC7_SWITCH = {1200: "1k2", 9600: "9k6"}

GENERIC = Profile(name="generic", display="KISS TNC", exit_kiss=False, notes="already in KISS")


# VARA FM / VARA HF (EA5HVK): KISS-TCP on port 8100 ("KISS interface" in VARA Setup).
# Not a transparent TNC: VARA takes the AX.25 header apart and accepts UI frames
# only - SABM/SABME/I/RR are refused with "Wrong KISS frame" (tested 17.10.2026).
# Frame type 2 ("Generic Data", C0 02 ... C0, up to 5000 bytes) carries any bytes,
# so kisshub tunnels the other frames in it (TUNNEL_MAGIC + the AX.25 frame) and
# unpacks them on the other side; TinyBox and the client do not notice. Both
# stations need kisshub with the tunnel. VARA does its own channel access (DCD,
# persistence 0.3): no KISS parameters are sent.
#   tunnel = connected   UI frames as normal type 0 (readable for any VARA KISS
#                        user), everything else through type 2
#   tunnel = all         every frame through type 2
# Bundling (vara_bundle_ms > 0, experiment 18.10.2026): VARA picks its speed
# level by the size of the KISS frame and sends small frames in the slowest
# level. kisshub collects the tunnelled frames that arrive within bundle_ms and
# sends them as ONE type-2 frame: BUNDLE_MAGIC + (2-byte length + AX.25 frame)...
# A single frame still goes as TUNNEL_MAGIC + frame. Needs kisshub 2026.10.18.5
# or newer on both stations.
VARA_FM = Profile(name="vara-fm", display="VARA FM", exit_kiss=False, kiss_params=False,
                  tunnel="connected", settle_sec=0.2, tcp_port=8100,
                  air_baud=350, txdelay_ms=2700, max_lead_ms=12000, ax25=AX25_VARA,
                  notes="VARA FM KISS-TCP (port 8100), connected mode tunnelled in type 2")
VARA_HF = dataclasses.replace(VARA_FM, name="vara-hf", display="VARA HF",
                              notes="VARA HF KISS-TCP (port 8100), connected mode tunnelled in type 2")

# Direwolf's KISS port (CR70): a modem without a TNC dialog. kisshub reads
# MODEM / TXDELAY / KISSPORT from direwolf.conf ([tnc] direwolf_conf) and does
# not send KISS parameters - Direwolf keeps those from its own file.
DIREWOLF = Profile(name="direwolf", display="Direwolf", exit_kiss=False, kiss_params=False,
                   settle_sec=0.2, tcp_port=8001, reads_direwolf_conf=True,
                   notes="Direwolf KISS-TCP (KISSPORT), values from direwolf.conf")

# modem73 (RFnexus, OFDM soundcard modem, kisshub/modem73.py): transparent KISS-TCP, so
# no tunnel. kisshub starts it from [modem73] in kisshub.conf; air time, PACLEN and the
# AX.25 recommendation follow from the mode there (config.py), not from these fields.
# Port 8011: 8001 is Direwolf's KISS port, 8101 kisshub's own.
MODEM73 = Profile(name="modem73", display="modem73", exit_kiss=False, kiss_params=False,
                  settle_sec=0.2, tcp_port=8011,
                  notes="modem73 KISS-TCP (port 8011), started by kisshub from [modem73]")

PROFILES = {p.name: p for p in (PK232, TM_D710, TNC7MULTI, TH_D74, TH_D75, TNC2_KISS, GENERIC,
                                VARA_FM, VARA_HF, DIREWOLF, MODEM73)}


def ax25_recommendation(p: Profile, air_baud: int = 1200) -> dict:
    if p.ax25:
        return dict(p.ax25)
    return dict(AX25_9600 if air_baud >= 9600 else AX25_1200)


def with_hbaud(p: Profile, baud: int) -> Profile:
    """[kiss] air_baud for a TNC with a switchable modem (TM-D710): the init line
    "HBAUD ..." becomes "HBAUD <baud>". Raises ValueError for a rate the TNC
    does not have."""
    if baud not in p.hbaud:
        raise ValueError(f"{p.display or p.name} knows {' or '.join(map(str, p.hbaud))} Bd")
    steps = tuple(line(f"HBAUD {baud}", s.timeout, s.expect)
                  if s.note.upper().startswith("HBAUD ") else s for s in p.init)
    return dataclasses.replace(p, init=steps)
TUNNEL_MODES = ("no", "connected", "all")


def with_init_lines(p: Profile, lines: list[str]) -> Profile:
    """kisshub.conf 'init_lines': replace the init. The last line enters KISS and
    gets no prompt back."""
    steps = [line(t) for t in lines[:-1]]
    if lines:
        steps.append(line(lines[-1], timeout=1.5, expect=()))
    return dataclasses.replace(p, init=tuple(steps))
