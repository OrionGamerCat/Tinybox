"""tbclient.conf (INI). Missing values take the defaults below."""

from __future__ import annotations

import configparser
import re
from dataclasses import dataclass, field
from pathlib import Path

from prcore import release, termcolor
from prcore.ax25.link import parse_calls

CALL_RE = re.compile(r"^[A-Z0-9]{1,6}(-([0-9]|1[0-5]))?$")


class ConfigError(Exception):
    pass


MAX_CHANNELS_LIMIT = 10              # upper bound of [tinybox] max_channels


@dataclass
class Config:
    mycall: str = ""
    locator: str = ""                 # Maidenhead locator, ADIF MY_GRIDSQUARE (CR44)
    tinybox_call: str = "OE3GAS-1"
    link: str = "agw"                 # agw = Direwolf, kiss = kisshub (CR46), telnet = test port
    ui: str = "auto"                  # auto | yes | no  (chat events as UI frames)
    auto_connect: bool = False
    max_channels: int = 5             # connections at once (1 ... 10)
    telnet_host: str = "127.0.0.1"
    telnet_port: int = 6300
    # PLANUNG 25: the home TinyBox over AXUDP (same PC), everything else over the radio
    axudp_host: str = ""              # "" = off; the TinyBox's [axudp] address
    axudp_port: int = 10093
    axudp_listen: int = 10094         # own UDP port (the TinyBox lists it in its peers)
    # AX.25 over AXUDP (as [axudp] in tinybox.conf): no airtime by default; a slower way
    # (the testbed's simulated 1200 Bd channel, PLANUNG 27) needs a small window, long T1
    axudp_paclen: int = 256
    axudp_maxframe: int = 32          # window (modulo 128)
    axudp_t1_sec: float = 3.0         # T1 from this up to 4 times this (at least 10 s)
    axudp_n2: int = 10
    axudp_air_baud: int = 0           # > 0: the way has air time (half duplex, PLANUNG 27)
    axudp_txdelay_ms: int = 0
    agw_host: str = "127.0.0.1"
    agw_port: int = 8000
    radio_port: int = 0
    web_host: str = "0.0.0.0"
    web_port: int = 7744
    color: str = "auto"               # [console] color: auto | yes | no
    data_dir: Path = Path("data/tbclient")
    update_check: bool = True         # [update] check: GitHub once a day (PLANUNG 24)
    sync_chunk: int = 1024            # bytes per request of a mailbox sync (radio)
    sync_pause: float = 5.0           # seconds between two requests (radio)
    sync_short: int = 256             # personal mail up to this size comes with its text (CR40)
    sync_on_login: bool = True        # sync the headers after every login (CR40)
    img_rate: int = 100               # net bytes/s of the link, for the time estimate
    img_target: int = 4096            # the picture is shrunk to about this many bytes ("normal")
    # CR46: link = kiss - kisshub and the client's own AX.25 layer 2
    kiss_host: str = "127.0.0.1"
    kiss_port: int = 8101
    kiss_channel: int = 0
    kiss_status_port: int = 8102      # kisshub's status (which TNC), 0 = off
    kiss_air_baud: int = 1200
    kiss_txdelay_ms: int = 300
    ax25_version: str = "2.2"
    ax25_paclen: int = 256
    ax25_maxframe: int = 4
    ax25_maxframe_ext: int = 7
    ax25_srej: bool = True
    ax25_n2: int = 10
    ax25_t1_min: float = 3.0
    ax25_t1_max: float = 30.0
    ax25_t2: float = 1.5
    ax25_t3: float = 300.0
    ax25_v20_digis: frozenset = frozenset()   # digis that know only modulo 8: v2.0 over them
    ax25_v20_digi_paclen: int = 128           # longest I field over such a digi
    # CR70: one owner per value - over AGW direwolf.conf, over KISS kisshub
    direwolf_conf: str = ""           # resolved path, "" = not given
    img_rate_fixed: bool = False      # [images] bytes_per_sec set: no estimate
    kiss_fixed: frozenset = frozenset()   # LinkCfg fields set here (win over kisshub)
    sources: dict = field(default_factory=dict)
    hints: list = field(default_factory=list)


def estimate_rate(air_baud: int) -> int:
    """Net bytes/s for the time estimate before the first measurement: about 70 %
    of the bit rate after flags, headers, TXDELAY and acknowledgements (1200 Bd
    with 256-byte frames: ~105, as measured before)."""
    return max(10, round(air_baud / 8 * 0.7))


def _strip(value: str) -> str:
    return value.split("#", 1)[0].split(";", 1)[0].strip()


def load(path: str | Path) -> Config:
    path = Path(path)
    if not path.exists():
        raise ConfigError(f"{path} not found - copy tbclient.conf.example to {path.name}")
    cp = configparser.ConfigParser(inline_comment_prefixes=("#", ";"))
    cp.read(path, encoding="utf-8")

    def get(section: str, key: str, default: str) -> str:
        return _strip(cp.get(section, key, fallback=default)) or default

    cfg = Config()
    cfg.mycall = get("station", "mycall", "").upper()
    cfg.locator = get("station", "locator", "").upper()
    cfg.tinybox_call = get("tinybox", "call", cfg.tinybox_call).upper()
    hints: list[str] = cfg.hints
    sources: dict[str, str] = cfg.sources

    def has(sec: str, key: str) -> bool:
        return cp.has_option(sec, key) and bool(_strip(cp.get(sec, key)))

    def pick(places: list[tuple[str, str]], default: str) -> str:
        """The new place first; an old one still works, with a hint."""
        for i, (sec, key) in enumerate(places):
            if has(sec, key):
                if i:
                    hints.append(f"[{sec}] {key} is the old name - use "
                                 f"[{places[0][0]}] {places[0][1]}")
                return get(sec, key, default)
        return default

    def old(sec: str, key: str, now: str, same_as: str | None = None) -> str | None:
        """A key whose value now comes from elsewhere: still read, as an override."""
        if not has(sec, key):
            return None
        v = get(sec, key, "")
        hints.append(f"[{sec}] {key} = {v}: " + (f"same as {now} - can be removed"
                                                 if same_as is not None and v == same_as
                                                 else f"overrides {now} - remove it to use that"))
        return v

    cfg.link = pick([("radio", "interface"), ("tinybox", "link")], cfg.link).lower()
    cfg.ui = get("tinybox", "ui", cfg.ui).lower()
    cfg.auto_connect = get("tinybox", "auto_connect", "no").lower() in ("yes", "true", "1", "on")
    try:
        cfg.max_channels = int(get("tinybox", "max_channels", str(cfg.max_channels)))
    except ValueError:
        raise ConfigError("[tinybox] max_channels must be a number 1 ... 10") from None
    if not 1 <= cfg.max_channels <= MAX_CHANNELS_LIMIT:
        raise ConfigError(f"[tinybox] max_channels must be 1 ... {MAX_CHANNELS_LIMIT}")
    cfg.telnet_host = get("tinybox", "telnet_host", cfg.telnet_host)
    cfg.telnet_port = int(get("tinybox", "telnet_port", str(cfg.telnet_port)))
    if has("tinybox", "axudp"):                                  # PLANUNG 25
        from prcore import axudp as udp
        try:
            cfg.axudp_host, cfg.axudp_port = udp.parse_addr(get("tinybox", "axudp", ""))
        except udp.AxudpError as exc:
            raise ConfigError(f"[tinybox] axudp: {exc}") from None
        cfg.axudp_listen = int(get("tinybox", "axudp_port", str(cfg.axudp_listen)))
        if not udp.is_loopback(cfg.axudp_host):
            raise ConfigError("[tinybox] axudp: only the TinyBox on this PC for now "
                              "(127.0.0.1)")
        if not 1 <= cfg.axudp_listen <= 65535:
            raise ConfigError("[tinybox] axudp_port must be 1 ... 65535")
        try:
            cfg.axudp_paclen = int(get("tinybox", "axudp_paclen", str(cfg.axudp_paclen)))
            cfg.axudp_maxframe = int(get("tinybox", "axudp_maxframe", str(cfg.axudp_maxframe)))
            cfg.axudp_t1_sec = float(get("tinybox", "axudp_t1_sec", str(cfg.axudp_t1_sec)))
            cfg.axudp_n2 = int(get("tinybox", "axudp_n2", str(cfg.axudp_n2)))
            cfg.axudp_air_baud = int(get("tinybox", "axudp_air_baud", "0"))
            cfg.axudp_txdelay_ms = int(get("tinybox", "axudp_txdelay_ms", "0"))
        except ValueError:
            raise ConfigError("[tinybox] axudp_paclen / _maxframe / _t1_sec / _n2 / "
                              "_air_baud / _txdelay_ms: numbers, please") from None
        if cfg.axudp_air_baud and not 300 <= cfg.axudp_air_baud <= 1_000_000:
            raise ConfigError("[tinybox] axudp_air_baud: 0 (no airtime) or 300 ... 1000000")
        if not 0 <= cfg.axudp_txdelay_ms <= 10000:
            raise ConfigError("[tinybox] axudp_txdelay_ms: 0 ... 10000")
        if not 32 <= cfg.axudp_paclen <= 256:
            raise ConfigError("[tinybox] axudp_paclen: 32 ... 256")
        if not 1 <= cfg.axudp_maxframe <= 127:
            raise ConfigError("[tinybox] axudp_maxframe: 1 ... 127")
        if not 0.2 <= cfg.axudp_t1_sec <= 60:
            raise ConfigError("[tinybox] axudp_t1_sec: 0.2 ... 60")
        if not 1 <= cfg.axudp_n2 <= 50:
            raise ConfigError("[tinybox] axudp_n2: 1 ... 50")

    # --- AGW: Direwolf, values from direwolf.conf -----------------------------------
    dw = None
    if has("agw", "direwolf_conf"):
        from prcore import direwolfconf
        dp = Path(get("agw", "direwolf_conf", "").strip('"'))
        if not dp.is_absolute() and not dp.exists():
            dp = path.parent / dp
        try:
            dw = direwolfconf.read(dp)
        except direwolfconf.DirewolfConfError as exc:
            raise ConfigError(f"[agw] direwolf_conf: {exc}") from None
        cfg.direwolf_conf = str(dw.path)
    cfg.agw_host = pick([("agw", "host"), ("direwolf", "agw_host")], cfg.agw_host)
    agw_default = str(dw.agw_port) if dw and dw.agw_port else str(cfg.agw_port)
    cfg.agw_port = int(pick([("agw", "port"), ("direwolf", "agw_port")], agw_default))
    cfg.radio_port = int(pick([("agw", "channel"), ("direwolf", "radio_port")],
                              str(cfg.radio_port)))
    sources["agw_port"] = ("tbclient.conf" if has("agw", "port") or has("direwolf", "agw_port")
                           else "direwolf.conf" if dw and dw.agw_port else "default")

    cfg.web_host = get("web", "host", cfg.web_host)
    cfg.web_port = int(get("web", "port", str(cfg.web_port)))
    try:
        cfg.color = termcolor.check_mode(get("console", "color", cfg.color))
    except ValueError as exc:
        raise ConfigError(str(exc)) from None
    data_dir = Path(get("storage", "data_dir", str(cfg.data_dir)))
    cfg.data_dir = data_dir if data_dir.is_absolute() else path.parent / data_dir

    cfg.sync_chunk = int(get("sync", "chunk_bytes", str(cfg.sync_chunk)))
    cfg.sync_pause = float(get("sync", "pause_sec", str(cfg.sync_pause)))
    if not 128 <= cfg.sync_chunk <= 8192:
        raise ConfigError("[sync] chunk_bytes must be 128 ... 8192")
    if not 0 <= cfg.sync_pause <= 120:
        raise ConfigError("[sync] pause_sec must be 0 ... 120")
    cfg.sync_short = int(get("sync", "short_bytes", str(cfg.sync_short)))
    if not 0 <= cfg.sync_short <= 8192:
        raise ConfigError("[sync] short_bytes must be 0 ... 8192")
    cfg.sync_on_login = get("sync", "on_login", "yes").lower() in ("yes", "true", "1", "on")
    try:
        cfg.update_check = release.load_cfg(cp).check          # PLANUNG 24
    except ValueError as exc:
        raise ConfigError(str(exc)) from None

    # --- KISS: kisshub, values from its status --------------------------------------
    cfg.kiss_port = int(get("kiss", "port", str(cfg.kiss_port)))
    fixed: set[str] = set()
    cfg.kiss_host = old("kiss", "host", "the fixed 127.0.0.1", "127.0.0.1") or cfg.kiss_host
    cfg.kiss_status_port = int(old("kiss", "status_port", "port + 1", str(cfg.kiss_port + 1))
                               or cfg.kiss_port + 1)
    cfg.kiss_channel = int(old("kiss", "channel", "the fixed 0", "0") or 0)
    v = old("kiss", "air_baud", "the kisshub value")
    if v is not None:
        cfg.kiss_air_baud = int(v)
        fixed.add("air_baud")
    v = old("kiss", "txdelay_ms", "the kisshub value")
    if v is not None:
        cfg.kiss_txdelay_ms = int(v)
        fixed.add("txdelay_sec")
    cfg.ax25_version = get("ax25", "version", cfg.ax25_version)
    for key, attr, kind, lc in (("paclen", "ax25_paclen", int, "paclen"),
                                ("maxframe", "ax25_maxframe", int, "maxframe"),
                                ("maxframe_ext", "ax25_maxframe_ext", int, "maxframe_ext"),
                                ("n2", "ax25_n2", int, "n2"),
                                ("t1_min_sec", "ax25_t1_min", float, "t1_min_sec"),
                                ("t1_max_sec", "ax25_t1_max", float, "t1_max_sec"),
                                ("t2_sec", "ax25_t2", float, "t2_sec"),
                                ("t3_sec", "ax25_t3", float, "t3_sec")):
        if has("ax25", key):
            setattr(cfg, attr, kind(get("ax25", key, "0")))
            fixed.add(lc)
    cfg.ax25_srej = get("ax25", "srej", "yes").lower() in ("yes", "true", "1", "on")
    cfg.ax25_v20_digis = parse_calls(get("ax25", "v20_digis", ""))
    cfg.ax25_v20_digi_paclen = int(get("ax25", "v20_digi_paclen", "128"))
    if not 16 <= cfg.ax25_v20_digi_paclen <= 256:
        raise ConfigError("[ax25] v20_digi_paclen must be 16 ... 256")
    cfg.kiss_fixed = frozenset(fixed)
    if cfg.ax25_version not in ("2.0", "2.2"):
        raise ConfigError("[ax25] version must be 2.0 or 2.2")
    if not 16 <= cfg.ax25_paclen <= 256:
        raise ConfigError("[ax25] paclen must be 16 ... 256")
    if not 1 <= cfg.ax25_maxframe <= 7 or not 1 <= cfg.ax25_maxframe_ext <= 127:
        raise ConfigError("[ax25] maxframe must be 1 ... 7, maxframe_ext 1 ... 127")
    if not 300 <= cfg.kiss_air_baud <= 115200:
        raise ConfigError("[kiss] air_baud must be 300 ... 115200")
    if not 0 < cfg.ax25_t1_min <= cfg.ax25_t1_max:
        raise ConfigError("[ax25] t1_min_sec must be above 0 and not above t1_max_sec")
    if cfg.link == "kiss":
        sources["kiss"] = "kisshub status" + (f", tbclient.conf: {', '.join(sorted(fixed))}"
                                              if fixed else "")

    # --- pictures: time estimate from the bit rate unless given ---------------------
    # piece_bytes / pause_sec of older versions are ignored: the picture goes to
    # the radio in one go, the AX.25 window paces it
    if has("images", "bytes_per_sec"):
        cfg.img_rate = int(get("images", "bytes_per_sec", str(cfg.img_rate)))
        cfg.img_rate_fixed = True
        sources["img_rate"] = "tbclient.conf"
    else:
        baud = (dw.channel(cfg.radio_port).baud if dw and cfg.link == "agw" else None) \
            or cfg.kiss_air_baud
        cfg.img_rate = estimate_rate(baud)
        sources["img_rate"] = (f"estimated from MODEM {baud} (direwolf.conf)"
                               if dw and cfg.link == "agw" and dw.channel(cfg.radio_port).baud
                               else f"estimated from {baud} Bd"
                               + (" - kisshub value follows" if cfg.link == "kiss" else ""))
    cfg.img_target = int(get("images", "target_bytes", str(cfg.img_target)))
    if not 10 <= cfg.img_rate <= 100000:
        raise ConfigError("[images] bytes_per_sec must be 10 ... 100000")
    if not 1024 <= cfg.img_target <= 16320:
        raise ConfigError("[images] target_bytes must be 1024 ... 16320")
    if dw:
        sources["direwolf.conf"] = dw.describe(cfg.radio_port)

    for name, call in (("[station] mycall", cfg.mycall), ("[tinybox] call", cfg.tinybox_call)):
        if not CALL_RE.match(call):
            raise ConfigError(f"{name}: invalid call {call!r}")
    if cfg.link not in ("agw", "kiss", "telnet"):
        raise ConfigError("[radio] interface must be agw, kiss or telnet")
    if cfg.ui not in ("auto", "yes", "no"):
        raise ConfigError("[tinybox] ui must be auto, yes or no")
    if cfg.axudp_host and cfg.link == "telnet":
        raise ConfigError("[tinybox] axudp needs [radio] interface = agw or kiss "
                          "(telnet already is the way to the own TinyBox)")
    return cfg


def radio_lines(cfg: Config) -> list[str]:
    """CR70: where the radio values come from - shown at start."""
    src = cfg.sources
    if cfg.link == "kiss":
        lines = [f"radio values: {src.get('kiss')}; until the first status air_baud "
                 f"{cfg.kiss_air_baud}, txdelay {cfg.kiss_txdelay_ms} ms, paclen "
                 f"{cfg.ax25_paclen}, window {cfg.ax25_maxframe}/{cfg.ax25_maxframe_ext}, "
                 f"T1 {cfg.ax25_t1_min}-{cfg.ax25_t1_max} s, T2 {cfg.ax25_t2} s "
                 f"(kisshub status 127.0.0.1:{cfg.kiss_status_port})"]
    elif cfg.link == "agw":
        lines = [f"AGW {cfg.agw_host}:{cfg.agw_port} ({src.get('agw_port')}), "
                 f"channel {cfg.radio_port}"]
    else:
        lines = []
    if cfg.link != "telnet":
        lines.append(f"picture estimate {cfg.img_rate} B/s ({src.get('img_rate')})")
    if src.get("direwolf.conf"):
        lines.append(f"direwolf.conf {src['direwolf.conf']}")
    if cfg.axudp_host:
        lines.append(f"home TinyBox {cfg.tinybox_call} over AXUDP {cfg.axudp_host}:"
                     f"{cfg.axudp_port} (own UDP port {cfg.axudp_listen}), the rest over radio")
    return lines + [f"config hint: {h}" for h in cfg.hints]


def link_note(cfg: Config) -> str:
    """The bracket after 'Connection via:' in the start block."""
    if cfg.link == "agw":
        return f"(Direwolf {cfg.agw_host}:{cfg.agw_port}, channel {cfg.radio_port})"
    if cfg.link == "kiss":
        return f"(kisshub {cfg.kiss_host}:{cfg.kiss_port})"
    return f"(TinyBox {cfg.telnet_host}:{cfg.telnet_port}, test only)"
