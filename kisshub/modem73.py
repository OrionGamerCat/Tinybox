"""modem73 (RFnexus, OFDM soundcard modem) as kisshub's "TNC" (profile modem73).

kisshub starts modem73.exe itself from the [modem73] section of kisshub.conf,
talks KISS-TCP to it like to any TNC and stops it again on Ctrl+C. modem73 is
a transparent KISS modem: every KISS data frame becomes one modem frame, so
SABM / I / RR go through unchanged (unlike VARA, no tunnel).

What is special - and why kisshub works the values out itself:
    - every frame costs a FIXED air time, whatever its length (a 17-byte RR as
      long as a full I frame): the frame time follows from modulation, code rate
      and frame size (aicodix COFDMTV, phy/common.hh in modem73)
    - a frame longer than the payload of one modem frame is CUT by modem73
      (fragmentation off) - the other side would get a damaged I frame, KISS has
      no checksum. PACLEN therefore comes from the payload, and the hub drops
      anything longer instead of handing it on
    - per key-up: PTT delay, then the lead (TX delay, with the signature lead
      tone at least 800 ms), then up to csma_burst frames 200 ms apart
    - after every received frame modem73 waits 1 s before it sends

The Windows build of modem73: tools/modem73 (README.md there).
"""

from __future__ import annotations

import asyncio
import logging
import math
import os
import re
import signal
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

log = logging.getLogger(__name__)

MODULATIONS = ("BPSK", "QPSK", "8PSK", "QAM16", "QAM64", "QAM256", "QAM1024", "QAM4096")
CODE_RATES = ("1/2", "2/3", "3/4", "5/6", "1/4", "1/2x2", "1/4x2")
FRAMES = ("short", "normal", "long")
PTT_TYPES = ("com", "vox", "rigctl", "none")
COM_LINES = ("rts", "dtr", "both", "-rts", "-dtr", "-both")
CSMA_BANDS = ("vhf", "hf")
CSMA_PRESETS = ("bench", "relaxed", "moderate", "busy")

SYMBOL_SEC = 41 / 300            # one OFDM symbol incl. guard (6560 samples at 48 kHz)
BURST_GAP_SEC = 0.2              # silence between frames of one key-up (BURST_GAP_MS)
RX_LOCKOUT_SEC = 1.0             # modem73 does not send for 1 s after a received frame
TONE_LEAD_MIN_MS = 800           # signature lead tone: ToneDCD MIN_LEAD_MS 650 + gap 150
HEADER_MAX = 31                  # AX.25: 2 addresses + 2 digis (28) + control (2) + PID
PACLEN_MAX = 256                 # TinyBox / client [ax25] paclen limit

# modulation -> (symbols, code order) of a short frame - phy/common.hh Common::setup
_SHORT = {"BPSK": (8, 11), "QPSK": (4, 11), "8PSK": (11, 13), "QAM16": (4, 12),
          "QAM64": (11, 14), "QAM256": (8, 14), "QAM1024": (13, 15), "QAM4096": (11, 15)}
# code rate -> data bits at code order 11 (doubling with every order)
_BITS = {"1/2": 1024, "2/3": 1368, "3/4": 1536, "5/6": 1704, "1/4": 512}


def frame_info(modulation: str, code_rate: str, frame: str) -> tuple[int, float]:
    """(KISS payload bytes, seconds on air) of ONE modem frame. The payload is the
    frame's data bytes minus modem73's 2-byte length prefix. ValueError for a
    combination modem73 does not have (e.g. QAM1024 long)."""
    if modulation not in _SHORT or code_rate not in CODE_RATES or frame not in FRAMES:
        raise ValueError(f"unknown mode {modulation} {code_rate} {frame}")
    symbols, order = _SHORT[modulation]
    if frame != "short":                       # normal: 4 -> 16 symbols, else double
        if symbols == 4:
            symbols, order = symbols * 4, order + 2
        else:
            symbols, order = symbols * 2, order + 1
    if frame == "long":
        symbols, order = symbols * 2, order + 1
    repeat2 = code_rate.endswith("x2")         # codeword sent twice (time diversity)
    if repeat2:
        if order > 15:
            raise ValueError(f"{modulation} {code_rate} {frame}: not available in modem73")
        symbols *= 2
    if not 11 <= order <= 16:
        raise ValueError(f"{modulation} {code_rate} {frame}: not available in modem73")
    bits = _BITS[code_rate.removesuffix("x2")] << (order - 11)
    return bits // 8 - 2, SYMBOL_SEC * (3 + symbols)


_CALL = re.compile(r"^[A-Za-z0-9/]{3,9}$")


@dataclass(frozen=True)
class Modem73Cfg:
    """[modem73] in kisshub.conf - see kisshub.conf.example."""
    callsign: str
    start: bool = True                 # no: modem73 runs on its own, values only
    exe: str = "modem73.exe"
    modulation: str = "QAM16"
    code_rate: str = "1/2"
    frame: str = "short"
    input_device: str = ""             # "" = system default (modem73 --list-audio)
    output_device: str = ""
    tx_level: int = 60                 # percent, 5..100
    ptt: str = "com"
    com_port: str = ""
    com_line: str = "rts"
    rigctl: str = "127.0.0.1:4532"
    ptt_delay_ms: int = 50             # PTT on -> audio starts
    tx_delay_ms: int = 300             # lead before the frame (250..2500)
    ptt_tail_ms: int = 50
    lead_tone: bool = True             # signature lead tone (needs >= 800 ms lead)
    csma_band: str = "vhf"
    csma_preset: str = ""              # "" = modem73's default for the band
    csma_burst: int = 4                # frames per key-up (1..4)
    control_port: int = 8073           # modem73's JSON control port (0 = off)
    extra_args: tuple[str, ...] = ()
    log_output: str = "info"           # modem73's own lines: info | debug | off
    # derived from the mode
    payload: int = field(init=False)
    frame_sec: float = field(init=False)

    def __post_init__(self) -> None:
        payload, sec = frame_info(self.modulation, self.code_rate, self.frame)
        object.__setattr__(self, "payload", payload)
        object.__setattr__(self, "frame_sec", sec)

    @property
    def lead_ms(self) -> int:
        """PTT on to the first frame: PTT delay + TX delay (with lead tone >= 800 ms)."""
        lead = max(self.tx_delay_ms, TONE_LEAD_MIN_MS) if self.lead_tone else self.tx_delay_ms
        return self.ptt_delay_ms + lead

    @property
    def mode(self) -> str:
        return f"{self.modulation} {self.code_rate} {self.frame}"

    def paclen(self) -> int:
        return min(PACLEN_MAX, self.payload - HEADER_MAX)

    def ax25(self) -> dict:
        """AX.25 recommendation for TinyBox and the client (CR70). T1 runs after the
        station's own estimated air time; it has to cover the answer: modem73's 1 s
        receive lockout, CSMA, the other side's lead and its RR - doubled for safety,
        plus half the window for the error of the estimate."""
        window = self.csma_burst
        answer = RX_LOCKOUT_SEC + 1.0 + self.lead_ms / 1000 + self.frame_sec
        t1_min = math.ceil(2 * answer + window * self.frame_sec / 2)
        return {"paclen": self.paclen(), "maxframe": window, "maxframe_ext": window,
                "t1_min_sec": float(t1_min), "t1_max_sec": float(max(60, 6 * t1_min)),
                "t2_sec": 0.5}

    def net_bps(self) -> int:
        """Payload bit rate of a full key-up (csma_burst frames of paclen)."""
        burst = self.csma_burst
        sec = self.lead_ms / 1000 + burst * self.frame_sec + (burst - 1) * BURST_GAP_SEC
        return round(burst * self.paclen() * 8 / sec)

    def describe(self) -> str:
        return (f"{self.mode}: {self.payload} B per frame, {self.frame_sec:.2f} s per frame, "
                f"lead {self.lead_ms} ms, burst {self.csma_burst}, ~{self.net_bps()} bit/s net")

    def args(self, port: int, bind: str) -> list[str]:
        """Command line for modem73 (headless). KISS port and bind address come from
        [tnc] port / host."""
        a = ["--headless", "-c", self.callsign.upper(), "-p", str(port), "--bind", bind,
             "--control-port", str(self.control_port),
             "--modem", "ofdm", "-m", self.modulation, "-r", self.code_rate, f"--{self.frame}",
             "--tx-level", str(self.tx_level),
             "--ptt-delay", str(self.ptt_delay_ms), "--tx-delay", str(self.tx_delay_ms),
             "--ptt-tail", str(self.ptt_tail_ms),
             "--csma-band", self.csma_band]
        if self.csma_preset:                   # the preset sets the burst too: burst after it
            a += ["--csma-preset", self.csma_preset]
        a += ["--csma-burst", str(self.csma_burst),
              "--lead-tone" if self.lead_tone else "--no-lead-tone", "--no-frag"]
        if self.input_device:
            a += ["--input-device", self.input_device]
        if self.output_device:
            a += ["--output-device", self.output_device]
        a += ["--ptt", self.ptt]
        if self.ptt == "com":
            a += ["--com-port", self.com_port, "--com-line", self.com_line]
        elif self.ptt == "rigctl":
            a += ["--rigctl", self.rigctl]
        return a + list(self.extra_args)


def load_section(cp, base: Path) -> Modem73Cfg:
    """[modem73] -> Modem73Cfg. ValueError with '<key>: ...' for a bad value."""
    sec = "modem73"

    def s(key: str, default: str = "") -> str:
        return cp.get(sec, key, fallback=default).strip()

    def i(key: str, default: int, lo: int, hi: int) -> int:
        try:
            v = cp.getint(sec, key, fallback=default)
        except ValueError:
            raise ValueError(f"{key}: a number") from None
        if not lo <= v <= hi:
            raise ValueError(f"{key}: {lo}..{hi}")
        return v

    def b(key: str, default: bool) -> bool:
        try:
            return cp.getboolean(sec, key, fallback=default)
        except ValueError:
            raise ValueError(f"{key}: yes or no") from None

    def choice(key: str, default: str, options: tuple[str, ...], upper=False) -> str:
        v = s(key, default)
        v = v.upper() if upper else v.lower()
        if v not in options:
            raise ValueError(f"{key} = {v}: use {' | '.join(options)}")
        return v

    call = s("callsign")
    if call.upper() == "N0CALL":
        raise ValueError("callsign: N0CALL is modem73's placeholder - put YOUR callsign here")
    if not _CALL.match(call):
        raise ValueError("callsign: your callsign without SSID, e.g. OE3GAS (modem73 puts "
                         "it into every OFDM frame; letters, digits, / - at most 9)")
    exe = s("exe", "modem73.exe")
    if exe and (os.sep in exe or "/" in exe) and not Path(exe).is_absolute():
        exe = str((base / exe).resolve())     # relative to kisshub.conf
    ptt = choice("ptt", "com", PTT_TYPES)
    com_port = s("com_port")
    if ptt == "com" and not com_port:
        raise ValueError("com_port: the COM port that keys the radio, e.g. COM5 "
                         "(or ptt = vox / rigctl / none)")
    log_output = choice("log_output", "info", ("info", "debug", "off"))
    try:
        cfg = Modem73Cfg(
            callsign=call.upper(), start=b("start", True), exe=exe,
            modulation=choice("modulation", "QAM16", MODULATIONS, upper=True),
            code_rate=choice("code_rate", "1/2", CODE_RATES),
            frame=choice("frame", "short", FRAMES),
            input_device=s("input_device"), output_device=s("output_device"),
            tx_level=i("tx_level", 60, 5, 100),
            ptt=ptt, com_port=com_port, com_line=choice("com_line", "rts", COM_LINES),
            rigctl=s("rigctl", "127.0.0.1:4532"),
            ptt_delay_ms=i("ptt_delay_ms", 50, 0, 2000),
            tx_delay_ms=i("tx_delay_ms", 300, 250, 2500),
            ptt_tail_ms=i("ptt_tail_ms", 50, 0, 2000),
            lead_tone=b("lead_tone", True),
            csma_band=choice("csma_band", "vhf", CSMA_BANDS),
            csma_preset=choice("csma_preset", "", ("",) + CSMA_PRESETS),
            csma_burst=i("csma_burst", 4, 1, 4),
            control_port=i("control_port", 8073, 0, 65535),
            extra_args=tuple(s("extra_args").split()),
            log_output=log_output)
    except ValueError as exc:
        if "not available" in str(exc):
            raise ValueError(f"modulation / code_rate / frame: {exc}") from None
        raise
    if cfg.payload - HEADER_MAX < 32:
        raise ValueError(f"{cfg.mode}: only {cfg.payload} bytes per frame - too small for "
                         "AX.25 frames, take a larger frame or code rate")
    return cfg


class Modem73Process:
    """Starts modem73, passes its output into the kisshub log, restarts it when it
    ends by itself, and stops it with kisshub."""

    def __init__(self, cfg: Modem73Cfg, port: int, bind: str, restart_sec: float = 10) -> None:
        self.cfg = cfg
        self.port = port
        self.bind = bind
        self.restart_sec = restart_sec
        self.proc: asyncio.subprocess.Process | None = None
        self.starts = 0
        self.last_exit: int | None = None
        self._stopping = False
        self._pump: asyncio.Task | None = None

    def command(self) -> list[str]:
        return [self.cfg.exe, *self.cfg.args(self.port, self.bind)]

    async def start(self) -> None:
        cmd = self.command()
        log.info("modem73: starting %s", subprocess.list2cmdline(cmd))
        # own process group: Ctrl+C in the kisshub window reaches kisshub only, kisshub
        # then stops modem73 itself (PTT released, port closed) - without it modem73
        # would stop by itself first and the supervisor would start it again
        if sys.platform == "win32":
            kw = {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}
        else:
            kw = {"start_new_session": True}
        try:
            self.proc = await asyncio.create_subprocess_exec(
                *cmd, stdin=asyncio.subprocess.DEVNULL, stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT, **kw)
        except OSError as exc:
            raise RuntimeError(f"modem73 could not be started ({self.cfg.exe}): {exc} - "
                               "[modem73] exe, build: tools/modem73/README.md") from None
        self.starts += 1
        self._pump = asyncio.create_task(self._read(self.proc))

    async def _read(self, proc) -> None:
        """modem73's lines into the log: its start block at INFO (devices, mode,
        port - worth seeing) until kisshub connects, after that only warnings at
        once - the lines it prints for every frame (TX:, mode block, CSMA) at DEBUG."""
        level = {"info": logging.INFO, "debug": logging.DEBUG}.get(self.cfg.log_output)
        started = False
        while line := await proc.stdout.readline():
            text = line.decode("utf-8", "replace").rstrip()
            if not text or level is None or text.startswith("ALSA lib"):
                continue
            low = text.lower()
            if "(!)" in text or "error" in low or "warning" in low or "failed" in low:
                log.warning("modem73: %s", text)
            elif started or text.startswith(("TX:", "RX:", "CSMA:", "control:")):
                log.debug("modem73: %s", text)
            else:
                log.log(level, "modem73: %s", text)
            if text.startswith("Client connected"):     # kisshub is in: start block over
                started = True

    async def wait_port(self, timeout: float = 30) -> bool:
        """True as soon as modem73's KISS port takes a connection."""
        loop = asyncio.get_running_loop()
        end = loop.time() + timeout
        while loop.time() < end:
            if self.proc is not None and self.proc.returncode is not None:
                return False
            try:
                _, w = await asyncio.open_connection(self.bind, self.port)
                w.close()
                return True
            except OSError:
                await asyncio.sleep(0.5)
        return False

    async def supervise(self) -> None:
        """Runs beside the hub: start again when modem73 ends by itself."""
        while True:
            if self.proc is None:
                await self.start()
            rc = await self.proc.wait()
            if self._pump is not None:
                await asyncio.gather(self._pump, return_exceptions=True)
            self.last_exit = rc
            if self._stopping:
                return
            log.warning("modem73 ended (exit code %s) - start again in %d s", rc,
                        self.restart_sec)
            self.proc = None
            await asyncio.sleep(self.restart_sec)

    async def stop(self) -> None:
        self._stopping = True
        p = self.proc
        if p is None or p.returncode is not None:
            log.info("modem73 stopped (it had ended by itself)" if p is not None else
                     "modem73 not running")
            return
        try:
            if sys.platform == "win32":
                p.send_signal(signal.CTRL_BREAK_EVENT)
            else:
                p.terminate()
            await asyncio.wait_for(p.wait(), 3)
        except (asyncio.TimeoutError, ProcessLookupError, OSError):
            try:
                p.kill()
                await asyncio.wait_for(p.wait(), 3)
            except (asyncio.TimeoutError, ProcessLookupError, OSError):
                pass
        log.info("modem73 stopped")

    def status(self) -> dict:
        p = self.proc
        return {"running": p is not None and p.returncode is None,
                "pid": p.pid if p is not None else None, "starts": self.starts,
                "last_exit": self.last_exit, "mode": self.cfg.mode,
                "payload": self.cfg.payload, "frame_ms": round(self.cfg.frame_sec * 1000),
                "lead_ms": self.cfg.lead_ms, "burst": self.cfg.csma_burst}
