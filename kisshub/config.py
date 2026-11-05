"""kisshub.conf (INI) -> profile, transport and hub settings."""

from __future__ import annotations

import configparser
import dataclasses
from dataclasses import dataclass
from pathlib import Path

from prcore import direwolfconf, kiss, release, termcolor

from . import modem73 as m73
from .hub import HubCfg
from . import profiles as pr
from .profiles import AX25_KEYS as _AX25_NAMES, Profile, ProfileError, with_hbaud

# CR70: the AX.25 recommendation TinyBox and the client take - key -> (kind, min, max)
AX25_KEYS = {"paclen": (int, 16, 256), "maxframe": (int, 1, 7), "maxframe_ext": (int, 1, 127),
             "n2": (int, 1, 50), "t1_min_sec": (float, 0.1, 3600), "t1_max_sec": (float, 0.1, 3600),
             "t2_sec": (float, 0, 3600), "t3_sec": (float, 0, 3600)}
AX25_CORE = ("paclen", "maxframe", "maxframe_ext", "t1_min_sec", "t1_max_sec", "t2_sec")
assert set(AX25_KEYS) == set(_AX25_NAMES)


class ConfigError(Exception):
    pass


@dataclass(frozen=True)
class TncCfg:
    profile: Profile
    transport: str = "serial"         # serial | tcp
    device: str = ""
    serial_baud: int = 9600
    rtscts: bool = False              # RTS/CTS hardware flow control (serial only)
    host: str = "127.0.0.1"
    port: int = 0
    reconnect_sec: int = 10
    params: dict = dataclasses.field(default_factory=dict)   # KISS command -> value


@dataclass(frozen=True)
class Config:
    tnc: TncCfg
    hub: HubCfg
    log_level: str = "INFO"
    log_file: str = ""
    color: str = "auto"               # [console] color: auto | yes | no
    trace: bool = False               # [log] trace: every byte to/from the TNC in hex
    hints: tuple[str, ...] = ()       # shown at start
    direwolf: str = ""                # CR70: what was read from direwolf.conf
    update_check: bool = True         # [update] check: GitHub once a day (PLANUNG 24)
    data_dir: Path = Path("data")     # only the update check's cache (release state)
    modem73: m73.Modem73Cfg | None = None   # type modem73: kisshub starts it

# type modem73: every frame takes a fixed air time, whatever its length. The stations
# estimate air time as txdelay + bytes * 8 / air_baud - with txdelay = lead + frame time
# and this rate the bytes count for (almost) nothing, so one frame comes out right.
MODEM73_AIR_BAUD = 1_000_000

# keys a TNC section may have, per type (a typo is an error, not silently ignored)
COMMON_KEYS = ("type", "display", "notes", "hint", "start_note", "transport", "device",
               "serial_baud", "dtr", "rts", "rtscts", "host", "port", "reconnect_sec",
               "wake", "init", "exit", "prompt", "step_timeout", "exit_kiss", "settle_sec",
               "send_params", "smack", "hbaud", "switch_positions", "air_baud",
               "txdelay_ms", "max_lead_ms", "persist", "slottime_ms", *AX25_KEYS)
TYPE_KEYS = {"tnc": (),
             "vara": ("vara_tunnel", "vara_bundle_ms", "vara_bundle_max", "vara_monitor",
                      "vara_host", "vara_cmd_port", "vara_sn_window_ms"),
             "direwolf": ("direwolf_conf",),
             "modem73": m73.KEYS}
GLOBAL_KEYS = {"kisshub": ("profile",),
               "server": ("port", "listen", "status_port"),
               "log": ("level", "file", "trace", "status_every_sec", "links_file"),
               "console": ("color",),
               "update": ("check", "announce")}


def _read(path: Path) -> configparser.ConfigParser:
    if not path.is_file():
        raise ConfigError(f"config file not found: {path}")
    cp = configparser.ConfigParser(inline_comment_prefixes=("#", ";"))
    try:
        cp.read(path, encoding="utf-8")
    except configparser.Error as exc:
        raise ConfigError(f"{path.name}: {exc}") from None
    old = pr.old_format(cp)
    if old:
        raise ConfigError(
            f"{path.name} is in the old format ({', '.join(f'[{s}]' for s in old)}). Since "
            "kisshub 2026.11.05 every TNC has its own section with all its values, e.g. "
            "[pk232] or [tm-d710] - see kisshub.conf.example and MANUAL.md section 2.4")
    return cp


def profile_list(path: str | Path) -> list[tuple[str, str, str]]:
    """kisshub -l: (name, type, notes) of every TNC section."""
    cp = _read(Path(path))
    out = []
    for name in pr.names(cp):
        try:
            keys = pr.merged(cp, name)
        except ProfileError as exc:
            out.append((name, "?", str(exc)))
            continue
        out.append((name, keys.get("type", "?").strip(), keys.get("notes", "").strip()))
    return out


def load(path: str | Path, profile_name: str | None = None) -> Config:
    """One section per TNC: -p NAME (or [kisshub] profile) picks the section [NAME],
    every value of that TNC comes from there - nothing from the code. Global sections:
    [kisshub], [server], [log], [console], [update]. {profile} in [log] file names
    becomes the profile name."""
    path = Path(path)
    cp = _read(path)
    for sec, allowed in GLOBAL_KEYS.items():
        if cp.has_section(sec):
            for key in cp.options(sec):
                if key not in allowed and key not in cp.defaults():
                    raise ConfigError(f"[{sec}] {key}: unknown - use {', '.join(allowed)}")

    def gget(sec, key, default, kind=str):
        try:
            if kind is int:
                return cp.getint(sec, key, fallback=default)
            if kind is bool:
                return cp.getboolean(sec, key, fallback=default)
            return cp.get(sec, key, fallback=default).strip()
        except ValueError as exc:
            raise ConfigError(f"[{sec}] {key}: {exc}") from None

    tncs = pr.names(cp)
    if not tncs:
        raise ConfigError(f"{path.name}: no TNC section - copy the ones you need from "
                          "kisshub.conf.example")
    name = (profile_name or gget("kisshub", "profile", "")).strip().lower()
    if not name:
        raise ConfigError(f"no profile: start with -p NAME or set [kisshub] profile - "
                          f"TNC sections: {', '.join(tncs)}")
    if name not in tncs:
        where = "-p" if profile_name else "[kisshub] profile"
        raise ConfigError(f"{where} {name}: no section [{name}] - TNC sections in "
                          f"{path.name}: {', '.join(tncs)}")
    try:
        keys = pr.merged(cp, name)
    except ProfileError as exc:
        raise ConfigError(str(exc)) from None
    # the merged keys (with base) as the section the rest reads from
    cp.remove_section(name)
    cp.add_section(name)
    for key, value in keys.items():
        cp.set(name, key, value)
    sec = name
    ptype = keys.get("type", "").strip().lower()
    if ptype not in pr.TYPES:
        raise ConfigError(f"[{name}] type = {ptype or '(missing)'}: use "
                          f"{' | '.join(pr.TYPES)}")
    allowed = set(COMMON_KEYS) | set(TYPE_KEYS[ptype])
    for key in keys:
        if key not in allowed and key not in cp.defaults():
            others = [t for t, k in TYPE_KEYS.items() if key in k]
            raise ConfigError(f"[{name}] {key}: "
                              + (f"only with type = {others[0]}" if others else "unknown key"))
    _check_required(name, ptype, keys)

    def get(key, default, kind=str):
        if default is None and not cp.has_option(sec, key):
            raise ConfigError(f"[{name}] {key}: missing")
        try:
            if kind is int:
                return cp.getint(sec, key, fallback=default)
            if kind is bool:
                return cp.getboolean(sec, key, fallback=default)
            if kind is float:
                return cp.getfloat(sec, key, fallback=default)
            return cp.get(sec, key, fallback=default).strip()
        except ValueError as exc:
            raise ConfigError(f"[{name}] {key}: {exc}") from None

    def named(value: str) -> str:
        return value.replace("{profile}", name)

    try:
        profile = pr.build(name, get)
    except ProfileError as exc:
        raise ConfigError(str(exc)) from None

    hints: list[str] = []
    dw = None
    if ptype == "direwolf":
        try:
            dw = direwolfconf.read(get("direwolf_conf", None))
        except direwolfconf.DirewolfConfError as exc:
            raise ConfigError(f"[{name}] direwolf_conf: {exc}") from None
    dch = dw.channel(0) if dw else None

    transport = get("transport", None).lower()
    if transport not in ("serial", "tcp"):
        raise ConfigError(f"[{name}] transport: use serial or tcp")
    device = get("device", "")
    if transport == "serial" and not device:
        raise ConfigError(f"[{name}] device: the serial port, e.g. COM3 or /dev/ttyUSB0")
    if ptype in ("vara", "direwolf", "modem73") and transport != "tcp":
        raise ConfigError(f"[{name}] transport: tcp with type = {ptype}")
    tport = dw.kiss_port if dw and dw.kiss_port else get("port", 0, int)
    if transport == "tcp" and not 1 <= tport <= 65535:
        raise ConfigError(f"[{name}] port: the TCP port of the TNC")
    host = get("host", "127.0.0.1")

    mcfg = None
    if ptype == "modem73":
        try:
            mcfg = m73.load_section(cp, path.resolve().parent, sec)
        except ValueError as exc:
            raise ConfigError(f"[{name}] {exc}") from None
        if mcfg.start and host not in ("127.0.0.1", "localhost"):
            raise ConfigError(f"[{name}] host = {host}: kisshub starts modem73 on this PC - "
                              "127.0.0.1, or start = no for a modem73 elsewhere")
        for key in ("air_baud", "txdelay_ms"):
            if cp.has_option(sec, key):
                raise ConfigError(f"[{name}] {key}: not with type = modem73 - the air time "
                                  "follows from modulation / code_rate / frame / tx_delay_ms")

    # CR70: radio values from the TNC section - for type direwolf direwolf.conf wins
    # (Direwolf really runs with it), the section has the values it does not set
    here = f"kisshub.conf [{name}]"
    sources: dict[str, str] = {}

    def radio(key: str, dw_value: int | None) -> int:
        if dw_value is not None:
            sources[key] = "direwolf.conf"
            return dw_value
        sources[key] = here
        return get(key, None, int)

    if mcfg is not None:
        air_baud = MODEM73_AIR_BAUD
        txdelay_ms = mcfg.lead_ms + round(mcfg.frame_sec * 1000)
        sources["air_baud"] = sources["txdelay_ms"] = f"modem73 {mcfg.mode}"
        if cp.has_option(sec, "max_lead_ms"):
            max_lead_ms = get("max_lead_ms", None, int)
            sources["max_lead_ms"] = here
        else:
            max_lead_ms = mcfg.lead_ms + mcfg.csma_burst * round(
                (mcfg.frame_sec + m73.BURST_GAP_SEC) * 1000)
            sources["max_lead_ms"] = f"modem73 burst {mcfg.csma_burst}"
    else:
        air_baud = radio("air_baud", dch.baud if dch else None)
        txdelay_ms = radio("txdelay_ms", dch.txdelay_ms if dch else None)
        max_lead_ms = radio("max_lead_ms", None)
    if profile.hbaud:                        # TM-D710: air_baud goes to the TNC (HBAUD)
        try:
            profile = with_hbaud(profile, air_baud)
        except ValueError as exc:
            raise ConfigError(f"[{name}] air_baud = {air_baud}: {exc}") from None
    if profile.air_bauds and air_baud not in profile.air_bauds:
        # TNC7multi: the rate is set on the device (switch / Conf mode r, s), kisshub
        # cannot check it - only the extra modem has other rates
        hints.append(f"[{name}] air_baud = {air_baud}: the {profile.display} modem has "
                     f"{' / '.join(map(str, profile.air_bauds))} Bd - other rates only with "
                     "the extra modem and a KISS switch position set up in Conf mode")

    # AX.25 recommendation for TinyBox and the client
    ax25: dict = mcfg.ax25() if mcfg is not None else {}
    from_dw = {}
    if dw:                                   # Direwolf's own AX.25 values win
        from_dw = {k: v for k, v in (("paclen", dw.paclen), ("maxframe", dw.maxframe),
                                     ("maxframe_ext", dw.emaxframe)) if v}
    for key in AX25_KEYS:
        if key in from_dw:
            ax25[key] = from_dw[key]
            continue
        if not cp.has_option(sec, key):
            continue
        kind, lo, hi = AX25_KEYS[key]
        value = get(key, None, kind)
        if not lo <= value <= hi:
            raise ConfigError(f"[{name}] {key}: {lo}..{hi}")
        if key == "paclen" and mcfg is not None and value > mcfg.paclen():
            raise ConfigError(f"[{name}] paclen = {value}: at most {mcfg.paclen()} with "
                              f"modem73 {mcfg.mode} ({mcfg.payload} bytes per frame "
                              f"minus {m73.HEADER_MAX} for the AX.25 header)")
        ax25[key] = value
    missing = [k for k in AX25_CORE if k not in ax25]
    if missing:
        raise ConfigError(f"[{name}] missing: {', '.join(missing)} (AX.25 recommendation)")
    ax25 = {k: ax25[k] for k in AX25_KEYS if k in ax25}
    parts = [f"modem73 {mcfg.mode}"] if mcfg else []
    if from_dw:
        parts.append("direwolf.conf")
    if any(cp.has_option(sec, k) and k not in from_dw for k in AX25_KEYS) or not parts:
        parts.append(here)
    sources["ax25"] = " + ".join(parts)

    params = {}
    if profile.kiss_params:
        params = {kiss.CMD_TXDELAY: kiss.ms_to_units(txdelay_ms),
                  kiss.CMD_P: get("persist", None, int),
                  kiss.CMD_SLOTTIME: kiss.ms_to_units(get("slottime_ms", None, int)),
                  kiss.CMD_FULLDUPLEX: 0}
        if not 0 <= params[kiss.CMD_P] <= 255:
            raise ConfigError(f"[{name}] persist: 0..255")

    tnc = TncCfg(profile=profile, transport=transport, device=device,
                 serial_baud=profile.serial_baud, rtscts=profile.rtscts,
                 host=host, port=tport,
                 reconnect_sec=get("reconnect_sec", None, int), params=params)
    port = gget("server", "port", 8101, int)
    # CR70: host fixed 127.0.0.1, status on port + 1; the old keys still work
    for key, default in (("listen", "127.0.0.1"), ("status_port", str(port + 1))):
        if cp.has_option("server", key):
            hints.append(f"[server] {key} = {gget('server', key, '')}: "
                         + ("same as the default - can be removed"
                            if gget("server", key, "") == default
                            else f"overrides the default {default}"))
    vara = ptype == "vara"
    hub = HubCfg(listen=gget("server", "listen", "127.0.0.1"),
                 port=port,
                 air_baud=air_baud,
                 txdelay_sec=txdelay_ms / 1000,
                 max_lead_sec=max_lead_ms / 1000,
                 frame_sec=(mcfg.frame_sec + m73.BURST_GAP_SEC) if mcfg else 0.0,
                 max_frame=mcfg.payload if mcfg else 0,
                 status_every_sec=gget("log", "status_every_sec", 600, int),
                 status_port=gget("server", "status_port", port + 1, int),
                 profile=profile.name, sources=sources, ax25=ax25,
                 links_file=named(gget("log", "links_file", "kisshub-links.jsonl")),
                 vara_monitor=get("vara_monitor", False, bool) if vara else False,
                 vara_host=get("vara_host", host) if vara else host,
                 vara_cmd_port=get("vara_cmd_port", 8300, int) if vara else 8300,
                 sn_window_sec=(get("vara_sn_window_ms", 1500, int) if vara else 1500) / 1000)
    if not 1 <= hub.port <= 65535:
        raise ConfigError("[server] port: 1..65535")
    if not 0 <= hub.status_port <= 65535:
        raise ConfigError("[server] status_port: 0 (off) or 1..65535")
    if not 1 <= hub.vara_cmd_port <= 65535:
        raise ConfigError(f"[{name}] vara_cmd_port: 1..65535")
    if hub.air_baud < 300:
        raise ConfigError(f"[{name}] air_baud: at least 300")
    if not 0 <= txdelay_ms <= 10000:
        raise ConfigError(f"[{name}] txdelay_ms: 0..10000")
    return Config(tnc=tnc, hub=hub, log_level=gget("log", "level", "INFO").upper(),
                  log_file=named(gget("log", "file", "")),
                  trace=gget("log", "trace", False, bool),
                  hints=tuple(hints), direwolf=dw.describe() if dw else "",
                  color=_color(gget("console", "color", "auto")),
                  update_check=_update(cp).check, data_dir=path.resolve().parent / "data",
                  modem73=mcfg)


def _check_required(name: str, ptype: str, keys: dict) -> None:
    """All missing keys of a TNC section at once (direwolf / modem73 values that can
    come from elsewhere are checked later)."""
    need = ["transport", "settle_sec", "reconnect_sec"]
    transport = keys.get("transport", "").strip().lower()
    if transport == "serial":
        need += ["device", "serial_baud"]
    elif transport == "tcp":
        need.append("port")
    if any(keys.get(k, "").strip() for k in ("wake", "init", "exit")):
        need.append("step_timeout")
    if ptype in ("tnc", "vara", "direwolf"):
        need += ["air_baud", "txdelay_ms", "max_lead_ms", *AX25_CORE]
    if ptype == "tnc":
        need += ["send_params", "exit_kiss"]
        if keys.get("send_params", "").strip().lower() in ("yes", "true", "on", "1"):
            need += ["persist", "slottime_ms"]
    if ptype == "vara":
        need.append("vara_tunnel")
    if ptype == "direwolf":
        need.append("direwolf_conf")
    missing = [k for k in need if not keys.get(k, "").strip()]
    if missing:
        raise ConfigError(f"[{name}] missing: {', '.join(missing)}")


def _update(cp: configparser.ConfigParser) -> release.UpdateCfg:
    try:
        return release.load_cfg(cp)               # PLANUNG 24
    except ValueError as exc:
        raise ConfigError(str(exc)) from None


def _color(value: str) -> str:
    try:
        return termcolor.check_mode(value)
    except ValueError as exc:
        raise ConfigError(str(exc)) from None


def radio_lines(cfg: Config) -> list[tuple]:
    """CR70: where each radio value came from - start block items."""
    h = cfg.hub
    src = h.sources
    lines = [("Radio values", f"air_baud {h.air_baud} ({src.get('air_baud')}), "
                              f"txdelay {round(h.txdelay_sec * 1000)} ms ({src.get('txdelay_ms')}), "
                              f"max_lead {round(h.max_lead_sec * 1000)} ms ({src.get('max_lead_ms')})"),
             ("AX.25 recommendation", ", ".join(f"{k} {v}" for k, v in h.ax25.items()),
              f"({src.get('ax25')}; for TinyBox and client)")]
    if cfg.direwolf:
        lines.insert(0, ("direwolf.conf", cfg.direwolf))
    m = cfg.modem73
    if m is not None:
        lines[0] = ("Radio values", f"fixed per frame: {round(h.txdelay_sec * 1000)} ms "
                                    f"(lead {m.lead_ms} + frame {round(m.frame_sec * 1000)}), "
                                    f"max_lead {round(h.max_lead_sec * 1000)} ms "
                                    f"({src.get('max_lead_ms')})")
        lines.insert(0, ("modem73", m.describe(),
                         f"({'started by kisshub: ' + m.exe if m.start else 'start = no'})"))
    p = cfg.tnc.profile
    if p.start_note:
        lines.insert(0, (p.display or p.name, p.start_note.format(
            air_baud=h.air_baud, switch=p.switch(h.air_baud))))
    if p.smack:
        lines.append(("SMACK", "on: data frames with CRC-16, the TNC follows by itself "
                               f"([{p.name}] smack = no for plain KISS)"))
    return lines


def make_transport(t: TncCfg):
    from .transport import SerialTransport, TcpTransport
    if t.transport == "tcp":
        return TcpTransport(t.host, t.port)
    return SerialTransport(t.device, t.serial_baud, t.profile.dtr, t.profile.rts, t.rtscts)
