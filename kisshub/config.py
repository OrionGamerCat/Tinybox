"""kisshub.conf (INI) -> profile, transport and hub settings."""

from __future__ import annotations

import configparser
import dataclasses
from dataclasses import dataclass
from pathlib import Path

from prcore import direwolfconf, kiss, release, termcolor

from . import modem73 as m73
from .hub import HubCfg
from .profiles import (PROFILES, TNC7_SWITCH, TUNNEL_MODES, Profile, ax25_recommendation,
                       with_hbaud, with_init_lines)

# CR70: [ax25] in kisshub.conf may override the recommendation of the profile
AX25_KEYS = {"paclen": (int, 16, 256), "maxframe": (int, 1, 7), "maxframe_ext": (int, 1, 127),
             "n2": (int, 1, 50), "t1_min_sec": (float, 0.1, 3600), "t1_max_sec": (float, 0.1, 3600),
             "t2_sec": (float, 0, 3600), "t3_sec": (float, 0, 3600)}


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
    hints: tuple[str, ...] = ()       # CR70: old keys still in the file, shown at start
    direwolf: str = ""                # CR70: what was read from direwolf.conf
    update_check: bool = True         # [update] check: GitHub once a day (PLANUNG 24)
    data_dir: Path = Path("data")     # only the update check's cache (release state)
    modem73: m73.Modem73Cfg | None = None   # profile modem73: [modem73], kisshub starts it

# profile modem73: every frame takes a fixed air time, whatever its length. The stations
# estimate air time as txdelay + bytes * 8 / air_baud - with txdelay = lead + frame time
# and this rate the bytes count for (almost) nothing, so one frame comes out right.
MODEM73_AIR_BAUD = 1_000_000


SECTIONS = ("tnc", "kiss", "ax25", "server", "log", "vara", "console", "update")


def load(path: str | Path, profile_name: str | None = None) -> Config:
    """profile_name (command line -p) wins over [tnc] profile. One kisshub.conf
    can serve several TNCs: [<section>.<profile>] (e.g. [kiss.pk232], [log.vara-fm])
    overrides the plain section for that profile, and {profile} in file names
    becomes the profile name."""
    path = Path(path)
    if not path.is_file():
        raise ConfigError(f"config file not found: {path}")
    cp = configparser.ConfigParser(inline_comment_prefixes=("#", ";"))
    cp.read(path, encoding="utf-8")

    def get(sec, key, default, kind=str):
        try:
            if kind is int:
                return cp.getint(sec, key, fallback=default)
            if kind is bool:
                return cp.getboolean(sec, key, fallback=default)
            return cp.get(sec, key, fallback=default).strip()
        except ValueError as exc:
            raise ConfigError(f"[{sec}] {key}: {exc}") from None

    name = (profile_name or get("tnc", "profile", "generic")).strip().lower()
    if name not in PROFILES:
        where = "-p" if profile_name else "[tnc] profile"
        raise ConfigError(f"{where}: '{name}' - use one of {', '.join(PROFILES)}")
    profile = PROFILES[name]
    for sec in SECTIONS:                     # [kiss.pk232] etc. over [kiss]
        own = f"{sec}.{name}"
        if cp.has_section(own):
            if not cp.has_section(sec):
                cp.add_section(sec)
            for key, value in cp.items(own, raw=True):
                if key not in cp.defaults():
                    cp.set(sec, key, value)
    for sec in cp.sections():
        base, dot, other = sec.partition(".")
        if dot and (base not in SECTIONS or other not in PROFILES):
            raise ConfigError(f"[{sec}]: unknown - use [<section>.<profile>], sections "
                              f"{', '.join(SECTIONS)}, profiles {', '.join(PROFILES)}")

    def named(value: str) -> str:
        return value.replace("{profile}", name)
    lines = [x.strip() for x in get("tnc", "init_lines", "").split("|") if x.strip()]
    if lines:
        profile = with_init_lines(profile, lines)
    exit_kiss = get("tnc", "exit_kiss_on_stop", profile.exit_kiss, bool)
    tunnel = get("tnc", "vara_tunnel", profile.tunnel).lower()
    if tunnel not in TUNNEL_MODES:
        raise ConfigError(f"[tnc] vara_tunnel: use {', '.join(TUNNEL_MODES)}")
    bundle_ms = get("tnc", "vara_bundle_ms", profile.bundle_ms, int)
    bundle_max = get("tnc", "vara_bundle_max", profile.bundle_max, int)
    if not 0 <= bundle_ms <= 2000:
        raise ConfigError("[tnc] vara_bundle_ms: 0 (off) .. 2000")
    if not 100 <= bundle_max <= 5000:
        raise ConfigError("[tnc] vara_bundle_max: 100 .. 5000 (VARA's limit)")
    if bundle_ms and tunnel == "no":
        raise ConfigError("[tnc] vara_bundle_ms: only with the VARA tunnel (vara_tunnel)")
    smack = get("tnc", "smack", profile.smack, bool)
    if smack and profile.tunnel != "no":
        raise ConfigError("[tnc] smack: not with VARA (it reads the type byte itself)")
    profile = dataclasses.replace(profile, exit_kiss=exit_kiss, tunnel=tunnel,
                                  bundle_ms=bundle_ms, bundle_max=bundle_max, smack=smack)

    hints: list[str] = []
    dw = None
    if profile.reads_direwolf_conf:
        dpath = get("tnc", "direwolf_conf", "")
        if not dpath:
            raise ConfigError("[tnc] direwolf_conf: the Direwolf folder or its direwolf.conf "
                              "(profile direwolf)")
        try:
            dw = direwolfconf.read(dpath)
        except direwolfconf.DirewolfConfError as exc:
            raise ConfigError(f"[tnc] direwolf_conf: {exc}") from None
    dch = dw.channel(0) if dw else None

    transport = get("tnc", "transport", "tcp" if profile.tcp_port else "serial").lower()
    if transport not in ("serial", "tcp"):
        raise ConfigError("[tnc] transport: use serial or tcp")
    device = get("tnc", "device", "")
    if transport == "serial" and not device:
        raise ConfigError("[tnc] device: the serial port, e.g. COM3 or /dev/ttyUSB0")
    tport_default = (dw.kiss_port if dw and dw.kiss_port else profile.tcp_port)
    tport = get("tnc", "port", tport_default, int)
    if transport == "tcp" and not 1 <= tport <= 65535:
        raise ConfigError("[tnc] port: the TCP port of the TNC")

    mcfg = None
    if profile.name == "modem73":
        try:
            mcfg = m73.load_section(cp, path.resolve().parent)
        except ValueError as exc:
            raise ConfigError(f"[modem73] {exc}") from None
        if transport != "tcp":
            raise ConfigError("[tnc] transport: tcp with profile modem73")
        host = get("tnc", "host", "127.0.0.1")
        if mcfg.start and host not in ("127.0.0.1", "localhost"):
            raise ConfigError(f"[tnc] host = {host}: kisshub starts modem73 on this PC - "
                              "127.0.0.1, or [modem73] start = no for a modem73 elsewhere")
        for key in ("air_baud", "txdelay_ms"):
            if cp.has_option("kiss", key):
                raise ConfigError(f"[kiss] {key}: not with profile modem73 - the air time "
                                  "follows from [modem73] modulation / code_rate / frame / "
                                  "tx_delay_ms")

    send_params = get("kiss", "send_params", profile.kiss_params, bool)
    if send_params and not profile.kiss_params:
        raise ConfigError(f"[kiss] send_params: must be no with profile {profile.name} - "
                          "VARA reads KISS commands 1 and 2 as its frame types and would "
                          "send them on the air")
    # CR70: radio values - profile, then direwolf.conf, then kisshub.conf [kiss]
    sources: dict[str, str] = {}

    def radio(key: str, profile_value: int, dw_value: int | None) -> int:
        if cp.has_option("kiss", key):
            sources[key] = "kisshub.conf"
            return get("kiss", key, profile_value, int)
        if dw_value is not None:
            sources[key] = "direwolf.conf"
            return dw_value
        sources[key] = f"profile {profile.name}"
        return profile_value

    if mcfg is not None:
        air_baud = MODEM73_AIR_BAUD
        txdelay_ms = mcfg.lead_ms + round(mcfg.frame_sec * 1000)
        sources["air_baud"] = sources["txdelay_ms"] = f"modem73 {mcfg.mode}"
        burst_ms = mcfg.lead_ms + mcfg.csma_burst * round(
            (mcfg.frame_sec + m73.BURST_GAP_SEC) * 1000)
        max_lead_ms = radio("max_lead_ms", burst_ms, None)
        if sources["max_lead_ms"].startswith("profile"):
            sources["max_lead_ms"] = f"modem73 burst {mcfg.csma_burst}"
    else:
        air_baud = radio("air_baud", profile.air_baud, dch.baud if dch else None)
        txdelay_ms = radio("txdelay_ms", profile.txdelay_ms, dch.txdelay_ms if dch else None)
        max_lead_ms = radio("max_lead_ms", profile.max_lead_ms, None)
    if profile.hbaud and not lines:          # TM-D710: air_baud goes to the TNC (HBAUD)
        try:
            profile = with_hbaud(profile, air_baud)
        except ValueError as exc:
            raise ConfigError(f"[kiss] air_baud = {air_baud}: {exc}") from None
    if profile.air_bauds and air_baud not in profile.air_bauds:
        # TNC7multi: the rate is set on the device (switch / Conf mode r, s), kisshub
        # cannot check it - only the extra modem has other rates
        hints.append(f"[kiss] air_baud = {air_baud}: the {profile.display} modem has "
                     f"{' / '.join(map(str, profile.air_bauds))} Bd - other rates only with "
                     "the extra modem and a KISS switch position set up in Conf mode")
    ax25 = mcfg.ax25() if mcfg is not None else ax25_recommendation(profile, air_baud)
    if dw:                                   # Direwolf's own AX.25 values as the hint
        if dw.paclen:
            ax25["paclen"] = dw.paclen
        if dw.maxframe:
            ax25["maxframe"] = dw.maxframe
        if dw.emaxframe:
            ax25["maxframe_ext"] = dw.emaxframe
    sources["ax25"] = ("direwolf.conf" if dw else f"modem73 {mcfg.mode}" if mcfg
                       else f"profile {profile.name}")
    if cp.has_section("ax25"):
        for key in cp.options("ax25"):
            if key not in AX25_KEYS:
                raise ConfigError(f"[ax25] {key}: unknown - use {', '.join(AX25_KEYS)}")
            kind, lo, hi = AX25_KEYS[key]
            value = get("ax25", key, 0, int) if kind is int else _float(cp, key)
            if not lo <= value <= hi:
                raise ConfigError(f"[ax25] {key}: {lo}..{hi}")
            if key == "paclen" and mcfg is not None and value > mcfg.paclen():
                raise ConfigError(f"[ax25] paclen = {value}: at most {mcfg.paclen()} with "
                                  f"modem73 {mcfg.mode} ({mcfg.payload} bytes per frame "
                                  f"minus {m73.HEADER_MAX} for the AX.25 header)")
            ax25[key] = value
        if cp.options("ax25"):
            sources["ax25"] += " + kisshub.conf [ax25]"
    params = {}
    if send_params:
        params = {kiss.CMD_TXDELAY: kiss.ms_to_units(txdelay_ms),
                  kiss.CMD_P: get("kiss", "persist", profile.persist, int),
                  kiss.CMD_SLOTTIME: kiss.ms_to_units(get("kiss", "slottime_ms",
                                                          profile.slottime_ms, int)),
                  kiss.CMD_FULLDUPLEX: 0}
        if not 0 <= params[kiss.CMD_P] <= 255:
            raise ConfigError("[kiss] persist: 0..255")

    tnc = TncCfg(profile=profile, transport=transport, device=device,
                 serial_baud=get("tnc", "serial_baud", profile.serial_baud, int),
                 rtscts=get("tnc", "rtscts", profile.rtscts, bool),
                 host=get("tnc", "host", "127.0.0.1"), port=tport,
                 reconnect_sec=get("tnc", "reconnect_sec", 10, int), params=params)
    port = get("server", "port", 8101, int)
    # CR70: host fixed 127.0.0.1, status on port + 1; the old keys still work
    for key, default in (("listen", "127.0.0.1"), ("status_port", str(port + 1))):
        if cp.has_option("server", key):
            hints.append(f"[server] {key} = {get('server', key, '')}: "
                         + ("same as the default - can be removed"
                            if get("server", key, "") == default
                            else f"overrides the default {default}"))
    hub = HubCfg(listen=get("server", "listen", "127.0.0.1"),
                 port=port,
                 air_baud=air_baud,
                 txdelay_sec=txdelay_ms / 1000,
                 max_lead_sec=max_lead_ms / 1000,
                 frame_sec=(mcfg.frame_sec + m73.BURST_GAP_SEC) if mcfg else 0.0,
                 max_frame=mcfg.payload if mcfg else 0,
                 status_every_sec=get("log", "status_every_sec", 600, int),
                 status_port=get("server", "status_port", port + 1, int),
                 profile=profile.name, sources=sources, ax25=ax25,
                 links_file=named(get("log", "links_file", "kisshub-links.jsonl")),
                 vara_monitor=get("vara", "monitor", False, bool),
                 vara_host=get("vara", "host", get("tnc", "host", "127.0.0.1")),
                 vara_cmd_port=get("vara", "cmd_port", 8300, int),
                 sn_window_sec=get("vara", "sn_window_ms", 1500, int) / 1000)
    if not 1 <= hub.port <= 65535:
        raise ConfigError("[server] port: 1..65535")
    if not 0 <= hub.status_port <= 65535:
        raise ConfigError("[server] status_port: 0 (off) or 1..65535")
    if hub.vara_monitor and not profile.name.startswith("vara"):
        # one kisshub.conf for all TNCs: the VARA monitor simply stays off
        hints.append(f"[vara] monitor = yes: ignored with profile {profile.name} "
                     "(only vara-fm / vara-hf)")
        hub = dataclasses.replace(hub, vara_monitor=False)
    if not 1 <= hub.vara_cmd_port <= 65535:
        raise ConfigError("[vara] cmd_port: 1..65535")
    if hub.air_baud < 300:
        raise ConfigError("[kiss] air_baud: at least 300")
    if not 0 <= txdelay_ms <= 10000:
        raise ConfigError("[kiss] txdelay_ms: 0..10000")
    return Config(tnc=tnc, hub=hub, log_level=get("log", "level", "INFO").upper(),
                  log_file=named(get("log", "file", "")), trace=get("log", "trace", False, bool),
                  hints=tuple(hints), direwolf=dw.describe() if dw else "",
                  color=_color(get("console", "color", "auto")),
                  update_check=_update(cp).check, data_dir=Path(path).resolve().parent / "data",
                  modem73=mcfg)


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


def _float(cp: configparser.ConfigParser, key: str) -> float:
    try:
        return cp.getfloat("ax25", key)
    except ValueError as exc:
        raise ConfigError(f"[ax25] {key}: {exc}") from None


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
            air_baud=h.air_baud,
            switch=TNC7_SWITCH.get(h.air_baud, "a KISS position (Conf mode)"))))
    if p.smack:
        lines.append(("SMACK", "on: data frames with CRC-16, the TNC follows by itself "
                               "([tnc] smack = no for plain KISS)"))
    return lines


def make_transport(t: TncCfg):
    from .transport import SerialTransport, TcpTransport
    if t.transport == "tcp":
        return TcpTransport(t.host, t.port)
    return SerialTransport(t.device, t.serial_baud, t.profile.dtr, t.profile.rts, t.rtscts)
