"""Load and validate brocastd.conf (INI format)."""

from __future__ import annotations

import configparser
import ipaddress
import re
from dataclasses import dataclass, field
from pathlib import Path

from . import colorlog

# Callsign as used in an AX.25 address field: 3-6 chars, letters and digits,
# at least one digit and one letter, optional SSID 0-15.
AX25_CALL_RE = re.compile(
    r"^(?=[A-Z0-9]*[0-9])(?=[A-Z0-9]*[A-Z])[A-Z0-9]{1,6}(-([0-9]|1[0-5]))?$")
LOOPBACK_HOSTS = {"127.0.0.1", "::1", "localhost"}
MODES = ("station", "listener")


class ConfigError(Exception):
    """brocastd.conf is missing or invalid."""


def is_ax25_call(call: str) -> bool:
    return bool(AX25_CALL_RE.match(call))


INTERFACES = ("agw", "kiss")


@dataclass
class DirewolfCfg:
    interface: str = "agw"        # agw: Direwolf reports its transmit queue; kiss: computed
    host: str = "127.0.0.1"
    agw_port: int = 8000
    kiss_port: int = 8001
    channel: int = 0              # Direwolf radio channel (AGW port / KISS port nibble)
    reconnect_sec: int = 5

    @property
    def port(self) -> int:
        return self.agw_port if self.interface == "agw" else self.kiss_port

    def describe(self) -> str:
        return f"{self.interface.upper()} {self.host}:{self.port}"


@dataclass
class StationCfg:
    ingest_host: str = "127.0.0.1"
    ingest_port: int = 8090
    token: str = ""               # empty = no token required
    path: list[str] = field(default_factory=list)   # digipeaters, usually none
    airtime_percent: float = 15.0
    airtime_window_min: int = 10
    baud: int = 1200
    txdelay_ms: int = 300
    burst_frames: int = 4         # frames per transmission (PTT cycle); 0 = no limit
    burst_gap_s: float = 3.0      # pause after each transmission, channel free for others
    repeat_minutes: list[int] = field(default_factory=lambda: [0, 2, 5, 10])
    max_interval_min: int = 30
    # Alterung: (Alter der Revision in Stunden, Intervall in Minuten), aufsteigend.
    # Eine alte Seite muss nicht so oft wiederholt werden wie eine frische;
    # 0 Minuten = gar nicht mehr senden (bleibt im Bestand, neue Revision weckt sie).
    aging: list[tuple[int, int]] = field(
        default_factory=lambda: [(24, 120), (72, 360), (168, 1440)])
    withdraw_repeats: int = 3
    wire_format: int = 2          # 1 = eine Seite je Frame (alt), 2 = Fragmente (fragment.py)
    compress: bool = True         # Format 2: Blockliste mit Preset-Wörterbuch packen
    id_auto_start: int = 24       # ids 1..23 (1 byte) stay for manual pages
    max_subpages: int = 40
    dict_source: str = ""         # e.g. "Mailbox OE3GAS-1, Befehl DICT"; empty = no announcement
    dict_broadcast_hours: int = 24  # dictionary packed over the air every n hours; 0 = off


DEFAULT_BEACON = "{call}: brocast - Teletext-Seiten ueber Packet Radio (UI-Frames an BROCST). " \
                 "Empfang mit dem brocast-Listener."


@dataclass
class BeaconCfg:
    """[beacon] (08.11.2026): a plain-text UI frame now and then, so everyone
    listening with an ordinary terminal or monitor knows the system: brocast."""
    interval_min: int = 30        # 0 = no beacon
    text: str = DEFAULT_BEACON    # {call} {version} {pages} are filled in
    dest: str = "BEACON"          # AX.25 destination of the beacon (not BROCST: plain text)
    path: list[str] | None = None  # digipeaters; None = like [station] path


@dataclass
class ListenerCfg:
    web_host: str = "127.0.0.1"
    web_port: int = 7733
    allow_lan: bool = False            # GUI reachable from the LAN (no login!)
    lan_names: tuple[str, ...] = ()    # extra host names for the browser, e.g. pc2.fritz.box


@dataclass
class Config:
    mode: str
    callsign: str
    data_dir: Path
    dictionary: Path
    log_level: str = "INFO"
    color: str = "auto"                  # [console] color: auto | yes | no
    log_file: Path | None = None         # this start's log file (set by setup_logging)
    log_dir: Path | None = None          # program log, one file per start; None = console only
    txlog_dir: Path | None = None        # Sendeprotokoll (station); None = aus
    db_flush_sec: int = 600              # flüchtige DB-Daten so oft schreiben (PLANUNG 11.9)
    direwolf: DirewolfCfg = field(default_factory=DirewolfCfg)
    station: StationCfg = field(default_factory=StationCfg)
    beacon: BeaconCfg = field(default_factory=BeaconCfg)
    listener: ListenerCfg = field(default_factory=ListenerCfg)
    sources: dict = field(default_factory=dict)   # CR70: woher baud / txdelay kommen
    hints: list = field(default_factory=list)     # CR70: alte Schlüssel in der Datei
    update_check: bool = True            # [update] check: GitHub 1x täglich (PLANUNG 24)

    @property
    def is_station(self) -> bool:
        return self.mode == "station"


def _ints(text: str, what: str) -> list[int]:
    try:
        return [int(x) for x in text.replace(" ", "").split(",") if x]
    except ValueError:
        raise ConfigError(f"{what}: Liste von Ganzzahlen erwartet") from None


def _aging(text: str, what: str) -> list[tuple[int, int]]:
    """"24:120, 168:0" -> [(24, 120), (168, 0)]; leer = keine Alterung."""
    steps: list[tuple[int, int]] = []
    for item in text.replace(" ", "").split(","):
        if not item:
            continue
        hours, _, minutes = item.partition(":")
        if not _:
            raise ConfigError(f"{what}: Stunden:Minuten erwartet, z. B. 24:120")
        try:
            steps.append((int(hours), int(minutes)))
        except ValueError:
            raise ConfigError(f"{what}: Stunden:Minuten erwartet, z. B. 24:120") from None
    steps.sort()
    for hours, minutes in steps:
        if hours <= 0 or minutes < 0:
            raise ConfigError(f"{what}: Stunden > 0 und Minuten >= 0 "
                              "(0 Minuten = nicht mehr senden)")
    return steps


def _float(text: str, what: str) -> float:
    try:
        return float(text)
    except ValueError:
        raise ConfigError(f"{what}: Zahl erwartet") from None


def release_module():
    """prcore/release.py of the TinyBox repo for the update check (PLANUNG 24);
    None when brocast runs without the repo around it."""
    import sys
    root = Path(__file__).resolve().parents[2]
    if (root / "prcore" / "release.py").is_file() and str(root) not in sys.path:
        sys.path.append(str(root))
    try:
        from prcore import release
    except ImportError:
        return None
    return release


def _direwolfconf():
    """prcore/direwolfconf.py of the TinyBox repo (brocast sits in its folder)."""
    import sys
    root = Path(__file__).resolve().parents[2]
    if (root / "prcore" / "direwolfconf.py").is_file() and str(root) not in sys.path:
        sys.path.append(str(root))
    from prcore import direwolfconf
    return direwolfconf


def _load_radio(cp, base: Path, hints: list, get, getint):
    """CR70: [radio] interface, [agw] direwolf_conf/channel/port, [kiss] port.
    The old [direwolf] section (and the even older lone [kiss]) still work."""
    dw = DirewolfCfg()
    dwconf = None
    if cp.has_option("agw", "direwolf_conf") and get("agw", "direwolf_conf"):
        mod = _direwolfconf()
        p = Path(get("agw", "direwolf_conf").strip('"'))
        if not p.is_absolute() and not p.exists():
            p = base / p
        try:
            dwconf = mod.read(p)
        except mod.DirewolfConfError as exc:
            raise ConfigError(f"[agw] direwolf_conf: {exc}") from None
    if cp.has_option("radio", "interface"):
        interface = get("radio", "interface", "agw").lower()
    elif cp.has_option("direwolf", "interface"):
        interface = get("direwolf", "interface", "agw").lower()
        hints.append("[direwolf] interface ist der alte Name - [radio] interface verwenden")
    elif cp.has_section("kiss") and not cp.has_section("direwolf"):
        interface = "kiss"                     # ganz alte brocastd.conf: KISS wie bisher
    else:
        interface = "agw"

    def pick(places, fallback: int) -> int:
        for i, (sec, key) in enumerate(places):
            if cp.has_option(sec, key):
                if i:
                    hints.append(f"[{sec}] {key} ist der alte Name - "
                                 f"[{places[0][0]}] {places[0][1]} verwenden")
                return getint(sec, key, fallback)
        return fallback

    agw_default = dwconf.agw_port if dwconf and dwconf.agw_port else dw.agw_port
    kiss_port = pick([("kiss", "port"), ("direwolf", "kiss_port")], 8101 if cp.has_section("radio")
                     else dw.kiss_port)
    channel = (pick([("agw", "channel"), ("direwolf", "channel")], dw.channel)
               if interface == "agw" else pick([("kiss", "channel"), ("direwolf", "channel")], 0))
    host = dw.host
    for sec in ("agw", "direwolf", "kiss"):
        if cp.has_option(sec, "host"):
            host = get(sec, "host", dw.host)
            break
    dw = DirewolfCfg(interface=interface, host=host,
                     agw_port=pick([("agw", "port"), ("direwolf", "agw_port")], agw_default),
                     kiss_port=kiss_port, channel=channel,
                     reconnect_sec=pick([("agw", "reconnect_sec"), ("direwolf", "reconnect_sec"),
                                         ("kiss", "reconnect_sec")], dw.reconnect_sec))
    if dw.interface not in INTERFACES:
        raise ConfigError(f"[radio] interface muss agw oder kiss sein, nicht {dw.interface!r}")
    if not 0 <= dw.channel <= 15:
        raise ConfigError("[agw] channel muss 0..15 sein")
    return dw, dwconf


def kisshub_radio(port: int, timeout: float = 1.5) -> dict | None:
    """kisshub's "radio" block (status on port + 1), None if not reachable."""
    import json
    import urllib.request
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port + 1}/status",
                                    timeout=timeout) as r:
            data = json.loads(r.read().decode("utf-8"))
    except (OSError, ValueError):
        return None
    radio = data.get("radio") if isinstance(data, dict) else None
    return radio if isinstance(radio, dict) else None


def _radio_values(cp, dw: DirewolfCfg, dwconf, cfg: "Config", getint) -> tuple[int, int]:
    """CR70: baud / txdelay - [station] only as an override; otherwise over AGW
    from direwolf.conf, over KISS from kisshub's status."""
    baud, txdelay, src = 1200, 300, "Standard"
    if dw.interface == "agw" and dwconf:
        ch = dwconf.channel(dw.channel)
        baud, txdelay = ch.baud or baud, ch.txdelay_ms if ch.txdelay_ms is not None else txdelay
        src = "direwolf.conf"
    elif dw.interface == "kiss":
        radio = kisshub_radio(dw.kiss_port)
        if radio:
            baud = int(radio.get("air_baud") or baud)
            txdelay = int(radio.get("txdelay_ms") if radio.get("txdelay_ms") is not None
                          else txdelay)
            src = "kisshub"
        else:
            src = f"Standard (kisshub-Status 127.0.0.1:{dw.kiss_port + 1} nicht erreichbar)"
    cfg.sources["baud"] = cfg.sources["txdelay_ms"] = src
    for key in ("baud", "txdelay_ms"):
        if cp.has_option("station", key):
            v = getint("station", key, 0)
            now = baud if key == "baud" else txdelay
            cfg.hints.append(f"[station] {key} = {v}: "
                             + (f"gleich wie {src} - kann entfernt werden" if v == now
                                else f"überschreibt {src} ({now})"))
            cfg.sources[key] = "brocastd.conf"
            if key == "baud":
                baud = v
            else:
                txdelay = v
    if baud < 300:
        raise ConfigError("Funkrate (baud) mindestens 300")
    return baud, txdelay


def load(path: str | Path) -> Config:
    path = Path(path)
    if not path.is_file():
        raise ConfigError(f"Konfigurationsdatei fehlt: {path}")
    cp = configparser.ConfigParser(inline_comment_prefixes=(";", "#"))
    cp.read(path, encoding="utf-8")
    base = path.resolve().parent

    def get(section: str, key: str, fallback: str = "") -> str:
        return cp.get(section, key, fallback=fallback).strip()

    def getint(section: str, key: str, fallback: int) -> int:
        try:
            return cp.getint(section, key, fallback=fallback)
        except ValueError:
            raise ConfigError(f"[{section}] {key}: Ganzzahl erwartet") from None

    def getbool(section: str, key: str, fallback: bool) -> bool:
        try:
            return cp.getboolean(section, key, fallback=fallback)
        except ValueError:
            raise ConfigError(f"[{section}] {key}: yes oder no erwartet") from None

    mode = get("brocastd", "mode", "listener").lower()
    if mode not in MODES:
        raise ConfigError(f"[brocastd] mode muss station oder listener sein, nicht {mode!r}")
    callsign = get("brocastd", "callsign").upper()
    if mode == "station" and not is_ax25_call(callsign):
        raise ConfigError(f"[brocastd] callsign {callsign!r} ist kein gültiges AX.25-Rufzeichen")

    cfg = Config(
        mode=mode,
        callsign=callsign,
        data_dir=base / get("brocastd", "data_dir", "data"),
        dictionary=base / get("brocastd", "dictionary", "brocast-core.yaml"),
        log_level=get("brocastd", "log_level", "INFO").upper(),
    )
    try:
        cfg.color = colorlog.check_mode(get("console", "color", "auto"))
    except ValueError as exc:
        raise ConfigError(str(exc)) from None
    log_dir = get("logging", "log_dir", "logs")
    cfg.log_dir = (base / log_dir) if log_dir else None
    try:
        cfg.update_check = cp.getboolean("update", "check", fallback=True)
    except ValueError as exc:
        raise ConfigError(f"[update] check: {exc}") from None
    txlog_dir = get("logging", "txlog_dir", "logs")     # leer = Sendeprotokoll aus
    cfg.txlog_dir = (base / txlog_dir) if txlog_dir else None
    cfg.db_flush_sec = getint("brocastd", "db_flush_sec", cfg.db_flush_sec)
    if cfg.db_flush_sec < 1:
        raise ConfigError("[brocastd] db_flush_sec: mindestens 1")
    dw, dwconf = _load_radio(cp, base, cfg.hints, get, getint)
    cfg.direwolf = dw

    st = StationCfg()
    if cp.has_section("station"):
        path_text = get("station", "path")
        st = StationCfg(
            ingest_host=get("station", "ingest_host", st.ingest_host),
            ingest_port=getint("station", "ingest_port", st.ingest_port),
            token=get("station", "token"),
            path=[p.strip().upper() for p in path_text.split(",") if p.strip()],
            airtime_percent=float(get("station", "airtime_percent", str(st.airtime_percent))),
            airtime_window_min=getint("station", "airtime_window_min", st.airtime_window_min),
            burst_frames=getint("station", "burst_frames", st.burst_frames),
            burst_gap_s=_float(get("station", "burst_gap_s", str(st.burst_gap_s)),
                               "[station] burst_gap_s"),
            repeat_minutes=_ints(get("station", "repeat_minutes", "0,2,5,10"),
                                 "[station] repeat_minutes"),
            max_interval_min=getint("station", "max_interval_min", st.max_interval_min),
            aging=_aging(get("station", "aging", "24:120, 72:360, 168:1440"), "[station] aging"),
            withdraw_repeats=getint("station", "withdraw_repeats", st.withdraw_repeats),
            wire_format=getint("station", "wire_format", st.wire_format),
            compress=getbool("station", "compress", st.compress),
            id_auto_start=getint("station", "id_auto_start", st.id_auto_start),
            max_subpages=getint("station", "max_subpages", st.max_subpages),
            dict_source=get("station", "dict_source")[:80],
            dict_broadcast_hours=getint("station", "dict_broadcast_hours",
                                        st.dict_broadcast_hours),
        )
    st.baud, st.txdelay_ms = _radio_values(cp, dw, dwconf, cfg, getint)
    if st.ingest_host not in LOOPBACK_HOSTS:
        raise ConfigError("[station] ingest_host muss 127.0.0.1 oder localhost sein")
    for digi in st.path:
        if not is_ax25_call(digi):
            raise ConfigError(f"[station] path: {digi!r} ist kein AX.25-Rufzeichen")
    if len(st.path) > 8:
        raise ConfigError("[station] path: höchstens 8 Digipeater")
    if not 0 < st.airtime_percent <= 100:
        raise ConfigError("[station] airtime_percent muss zwischen 0 und 100 liegen")
    if not 0 <= st.burst_frames <= 64:
        raise ConfigError("[station] burst_frames muss 0..64 sein (0 = keine Aufteilung)")
    if not 0 <= st.burst_gap_s <= 60:
        raise ConfigError("[station] burst_gap_s muss 0..60 Sekunden sein")
    if not st.repeat_minutes:
        raise ConfigError("[station] repeat_minutes darf nicht leer sein")
    if not 0 <= st.dict_broadcast_hours <= 24 * 30:
        raise ConfigError("[station] dict_broadcast_hours muss 0..720 sein")
    if st.wire_format not in (1, 2):
        raise ConfigError("[station] wire_format muss 1 (eine Seite je Frame) "
                          "oder 2 (Fragmente, Standard) sein")
    cfg.station = st

    bc = BeaconCfg()
    if cp.has_section("beacon"):
        ptext = get("beacon", "path", "-")
        bc = BeaconCfg(interval_min=getint("beacon", "interval_min", bc.interval_min),
                       text=get("beacon", "text", bc.text) or bc.text,
                       dest=get("beacon", "dest", bc.dest).upper() or bc.dest,
                       path=None if ptext == "-" else
                       [p.strip().upper() for p in ptext.split(",") if p.strip()])
    if not 0 <= bc.interval_min <= 24 * 60:
        raise ConfigError("[beacon] interval_min muss 0..1440 sein (0 = keine Bake)")
    if bc.interval_min and 0 < bc.interval_min < 5:
        raise ConfigError("[beacon] interval_min: mindestens 5 Minuten (Kanal frei halten)")
    if not re.fullmatch(r"[A-Z0-9]{1,6}(-(1[0-5]|[0-9]))?", bc.dest):
        raise ConfigError(f"[beacon] dest: {bc.dest!r} ist kein AX.25-Ziel")
    for digi in bc.path or []:
        if not is_ax25_call(digi):
            raise ConfigError(f"[beacon] path: {digi!r} ist kein AX.25-Rufzeichen")
    try:
        sample = bc.text.format(call=cfg.callsign or "OE0XXX-0", version="0.0", pages=0)
    except (KeyError, IndexError, ValueError) as exc:
        raise ConfigError(f"[beacon] text: Platzhalter {exc} unbekannt "
                          "(erlaubt: {call} {version} {pages})") from None
    if len(sample.encode("utf-8")) > 250:
        raise ConfigError("[beacon] text: höchstens 250 Bytes (ein UI-Frame)")
    if not sample.isascii():
        cfg.hints.append("[beacon] text enthält Umlaute/Sonderzeichen - manche Terminals zeigen "
                         "sie falsch an (ASCII empfohlen)")
    cfg.beacon = bc

    try:
        allow_lan = cp.getboolean("listener", "allow_lan", fallback=False)
    except ValueError:
        raise ConfigError("[listener] allow_lan: yes oder no erwartet") from None
    cfg.listener = ListenerCfg(
        web_host=get("listener", "web_host", "127.0.0.1"),
        web_port=getint("listener", "web_port", 7733),
        allow_lan=allow_lan,
        lan_names=tuple(n.strip() for n in get("listener", "lan_names").split(",") if n.strip()),
    )
    if cfg.listener.web_host not in LOOPBACK_HOSTS:
        if not allow_lan:
            raise ConfigError("[listener] web_host muss 127.0.0.1 oder localhost sein "
                              "(für Zugriff aus dem LAN: allow_lan = yes)")
        try:
            ipaddress.ip_address(cfg.listener.web_host)
        except ValueError:
            raise ConfigError("[listener] web_host: IP-Adresse erwartet, "
                              "z. B. 0.0.0.0 (alle Netzwerkkarten)") from None
    return cfg
