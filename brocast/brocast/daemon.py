"""brocastd – start:  py -3 -m brocast.daemon [-c brocastd.conf]

listener: receive brocast frames from Direwolf (AGW or KISS) and store them.
station:  listener + ingest API + carousel (sends via the same link).
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import signal
import sys
import time
from pathlib import Path
from typing import Any, Callable

import yaml

from . import colorlog, config, dictimport, dicttransfer, fragment, zdict
from .agw import AgwLink
from .carousel import Carousel
from .codec import BrocastError, Codec
from .dictionary import Dictionary
from .frame import (FORMAT_FRAGMENT, describe_other, parse as parse_frame,
                    unknown_format)
from .ingest import IngestServer
from .kiss import KissLink
from .listener import Listener
from .listener_api import ListenerApi
from .station import Station
from .store import Store
from .txlog import TxLog

VERSION = "0.3 (M3)"
HOUSEKEEPING_SEC = 60
DICT_DATA = ("brocastd", "dictionary-data")   # carousel page with the packed dictionary
DICT_REPEAT_MIN = 15                           # second round for listeners that missed a part
log = logging.getLogger("brocastd")


class Daemon:
    def __init__(self, cfg: config.Config, clock: Callable[[], float] = time.time,
                 db_path: str | Path | None = None):
        self.cfg, self.clock = cfg, clock
        self.codec = Codec(Dictionary.load(cfg.dictionary))
        self.store = Store(db_path or cfg.data_dir / "brocastd.db")
        dw = cfg.direwolf
        self.link: AgwLink | KissLink
        if dw.interface == "agw":
            self.link = AgwLink(dw.host, dw.agw_port, self.on_frame, dw.reconnect_sec)
        else:
            self.link = KissLink(dw.host, dw.kiss_port, self.on_frame, dw.reconnect_sec)
        self.release: dict[str, Any] | None = None   # newest TinyBox release (PLANUNG 24)
        self.rx_pages = 0
        self.rx_errors = 0
        self.rx_fragments = 0
        self.zd = zdict.load()
        self.assembler = fragment.Assembler(self.zd, clock=clock)
        self.listener = Listener(self.store, self.codec, clock,
                                 baud=cfg.station.baud, txdelay_ms=cfg.station.txdelay_ms)
        self.web = ListenerApi(self.listener, cfg.listener.web_host, cfg.listener.web_port,
                               self.status, dict_import=self.import_dictionary,
                               lan=cfg.listener.allow_lan, lan_names=cfg.listener.lan_names)
        self.listener.install_dictionary = self.install_received
        self.web.dict_broadcast = self.broadcast_dictionary_now
        self.web.tx_status = self.tx_status                 # view "Sendung" (station)
        self.carousel: Carousel | None = None
        self.station: Station | None = None
        self.ingest: IngestServer | None = None
        self.txlog: TxLog | None = None
        if cfg.is_station:
            if cfg.txlog_dir is not None:
                self.txlog = TxLog(cfg.txlog_dir, cfg.callsign)
            queue_len = None
            if isinstance(self.link, AgwLink):
                link = self.link
                async def queue_len() -> int | None:
                    return await link.queue_len(dw.channel)
            self.carousel = Carousel(self.store, self._send, cfg.station, cfg.callsign, clock,
                                     txlog=self.txlog, queue_len=queue_len)
            self.carousel.schedules[DICT_DATA] = self._dict_gap
            self.station = Station(cfg, self.codec, self.store, clock, self.carousel.wake,
                                   zd=self.zd)
            self.ingest = IngestServer(self.station, cfg.station.ingest_host,
                                       cfg.station.ingest_port, cfg.station.token, self.status)

    async def _send(self, data: bytes) -> bool:
        ok = await self.link.send(data, self.cfg.direwolf.channel)
        if ok:
            # Direwolf does not echo our own frames: show them in our own listener
            self._receive(data, own=True)
        return ok

    # -- receive path (always active) ---------------------------------------

    def on_frame(self, channel: int, data: bytes) -> None:
        if channel == self.cfg.direwolf.channel:
            self._receive(data, own=False)

    def _receive(self, data: bytes, own: bool) -> None:
        now = round(self.clock(), 3)                 # with milliseconds for the receive log
        parsed = parse_frame(data)
        if parsed is None:                           # not a brocast frame: log it briefly
            src, dest, kind = describe_other(data)
            fmt = unknown_format(data)
            if fmt is None:
                self.store.add_rxlog({"ts": now, "heard_from": src, "dest": dest,
                                      "ti": f"{kind}-Frame", "result": "foreign",
                                      "bytes": len(data)})
                return
            log.warning("%s sendet brocast-Frames im Format %s – diese Software kennt es "
                        "nicht (brocastd aktualisieren: git pull)", src, fmt)
            self.store.add_rxlog({"ts": now, "heard_from": src, "dest": dest,
                                  "ti": f"Format {fmt}", "result": "newer_format",
                                  "bytes": len(data)})
            return
        frame, fmt, flags, raw = parsed
        if not own and self.cfg.is_station and frame.src == self.cfg.callsign:
            return                                   # our own frame, digipeated back
        entry = {"ts": now, "heard_from": frame.src, "dest": frame.dest, "bytes": len(data),
                 "own": int(own)}
        frames_used = 1
        if fmt == FORMAT_FRAGMENT:
            fed = self.assembler.feed(frame.src, raw, flags, len(data))
            if fed.status != "page":
                if not own:
                    self.rx_fragments += 1
                    if fed.status in ("zdict", "bad"):
                        self.rx_errors += 1
                        log.warning("Fragment von %s (Seite %s): %s", frame.src,
                                    fed.id, fed.note)
                sub, total = fed.sub or (1, 1)
                self.store.add_rxlog({**entry, "id": fed.id, "rev": fed.rev, "sub": sub,
                                      "sub_total": total, "ti": fed.note[:80],
                                      "result": fed.status})
                return
            assert fed.page is not None
            raw, frames_used = fed.page, fed.fragments
            if not own:
                self.rx_fragments += 1
            entry["bytes"] = fed.bytes_on_air or len(data)
        try:
            page = self.codec.decode(raw, ax25_src=frame.src, defaults=False)
        except BrocastError as exc:
            self.rx_errors += 1
            log.warning("Seite von %s nicht dekodierbar: %s", frame.src, exc)
            self.store.add_rxlog({**entry, "result": "error", "ti": str(exc)[:80]})
            return
        wire = (frames_used, entry["bytes"]) if fmt == FORMAT_FRAGMENT else None
        result = self.listener.on_page(page, raw, frame.src, wire=wire)
        sub, total = page.get("sub") or [frames_used, frames_used]
        self.store.add_rxlog({**entry, "org": page.get("org") or frame.src, "id": page["id"],
                              "sub": sub, "sub_total": total, "rev": page.get("rev", 0),
                              "ti": page.get("ti", ""), "result": result})
        if not own:
            self.rx_pages += 1
        if result in ("new", "updated", "subpage", "withdrawn") and not own:
            log.info("empfangen: %s Seite %s rev %s (%s/%s%s) %s [%s]",
                     page.get("org") or frame.src, page["id"], page.get("rev", 0),
                     sub, total, " Fragmente" if fmt == FORMAT_FRAGMENT and total > 1 else "",
                     page.get("ti", ""), result)

    # -- dictionary ---------------------------------------------------------

    def announce_dictionary(self) -> None:
        """Station: keep a small typ-dict page in the carousel (version, hash, source,
        and how often the dictionary itself is sent over the air).
        Idempotent; called regularly so the page never expires."""
        st = self.cfg.station
        if not (self.station and (st.dict_source or st.dict_broadcast_hours > 0)):
            return
        d = self.codec.d
        dat: dict[Any, Any] = {"version": d.version, "hash": d.hash4.hex()}
        if st.dict_source:
            dat["source"] = st.dict_source
        topic = d.types.get("dict")
        if st.dict_broadcast_hours > 0 and topic and "zint" in topic.by_name:
            dat["zint"] = st.dict_broadcast_hours      # number 5, fixed (bootstrap), from v2 on
        try:
            self.station.put("brocastd", "dictionary", {
                "typ": "dict", "ti": f"Dictionary v{d.version}", "dat": dat})
        except BrocastError as exc:
            log.warning("Dictionary-Ankündigung nicht möglich: %s", exc)

    def _dict_gap(self, sends_done: int) -> int:
        """Dictionary data: once more after 15 min, then every dict_broadcast_hours."""
        return DICT_REPEAT_MIN if sends_done == 1 else self.cfg.station.dict_broadcast_hours * 60

    def broadcast_dictionary(self) -> None:
        """Station: keep the packed dictionary in the carousel (spec "Dictionary über
        Funk"). Idempotent; a new dictionary gives a new revision, sent at once."""
        if not self.station:
            return
        provider, key = DICT_DATA
        if self.cfg.station.dict_broadcast_hours <= 0:
            row = self.store.get_page(provider, key)
            if row and row.state == "active":
                self.station.delete(provider, key)
            return
        d = self.codec.d
        try:
            res = self.station.put_frames(
                provider, key, lambda pid, rev, t: dicttransfer.build_frames(d, pid, rev, t),
                content_hash=f"v{d.version}-{d.hash4.hex()}",
                description={"typ": "dict", "ti": f"Dictionary v{d.version} (Daten)",  # log only
                             "version": d.version, "hash": d.hash4.hex()})
        except (BrocastError, dicttransfer.TransferError) as exc:
            log.warning("Dictionary-Aussendung nicht möglich: %s", exc)
            return
        if res:
            log.info("Dictionary v%s über Funk: %s Teile, ca. %s s Sendezeit, alle %s h",
                     d.version, res["subpages"], res["airtime_s"],
                     self.cfg.station.dict_broadcast_hours)

    def broadcast_dictionary_now(self) -> dict[str, Any]:
        """Station, GUI button: send the packed dictionary at once (e.g. for a test).
        Afterwards the normal schedule applies again (15 min, then every n hours)."""
        if not (self.station and self.carousel):
            return {"ok": False, "message": "Nur im Modus station möglich."}
        if self.cfg.station.dict_broadcast_hours <= 0:
            return {"ok": False, "message": "Aussendung ist aus (dict_broadcast_hours = 0)."}
        self.broadcast_dictionary()
        row = self.store.get_page(*DICT_DATA)
        if row is None or row.state != "active":
            return {"ok": False, "message": "Dictionary-Seite nicht vorhanden (siehe Log)."}
        self.store.send_now(row.pid, int(self.clock()))
        self.carousel.wake()
        n = len(self.store.frames(row.pid))
        log.info("Dictionary v%s: Aussendung von Hand angestoßen (%s Teile)", self.codec.d.version, n)
        return {"ok": True, "message": f"Dictionary v{self.codec.d.version} wird jetzt gesendet "
                                       f"({n} Teile). Wiederholung in 15 min."}

    def import_dictionary(self, body: Any, dry_run: bool) -> dict[str, Any]:
        """Listener GUI: install a dictionary fetched as text (e.g. TinyBox DICT)."""
        text = dictimport.text_from_request(body)
        result = dictimport.run(text, self.codec.d, self.cfg.dictionary, dry_run=dry_run)
        if result.installed:
            new = Dictionary.load(self.cfg.dictionary)
            self.codec.d = new
            self.listener.d = new
            log.info("Dictionary Version %s installiert und geladen", new.version)
            self.announce_dictionary()
            self.broadcast_dictionary()
        return result.as_dict()

    def install_received(self, new: Dictionary, station: str) -> None:
        """A dictionary received over the air (already checked: complete, hash,
        newer, only additions). Written as YAML; the old file stays as backup."""
        text = (f"# brocast Dictionary v{new.version}, über Funk empfangen von {station}\n"
                + yaml.safe_dump(new.raw, allow_unicode=True, sort_keys=False))
        if Dictionary(yaml.safe_load(text)).hash4 != new.hash4:      # never write a changed one
            raise dicttransfer.TransferError("YAML-Darstellung weicht ab – nicht installiert")
        dictimport.install(text, self.cfg.dictionary, self.codec.d.version)
        loaded = Dictionary.load(self.cfg.dictionary)
        self.codec.d = loaded
        self.listener.d = loaded
        log.info("Dictionary Version %s (über Funk von %s) installiert und geladen",
                 loaded.version, station)
        self.announce_dictionary()
        self.broadcast_dictionary()

    async def _housekeeping(self) -> None:
        while True:
            self.announce_dictionary()
            self.broadcast_dictionary()
            removed = self.listener.housekeeping()
            self.store.prune_rxlog()
            if removed:
                log.info("Listener: %s Seiten entfernt (abgelaufen/Grenzen)", removed)
            await asyncio.sleep(HOUSEKEEPING_SEC)

    async def _flush_loop(self) -> None:
        """Flüchtige Daten (rxlog, Stationen, Sendezeitplan) gebündelt schreiben."""
        while True:
            await asyncio.sleep(self.cfg.db_flush_sec)
            if self.store.flush():
                log.debug("Datenbank: flüchtige Daten geschrieben")

    def on_release(self, result) -> None:
        """From prcore.release.watch(): shown on the listener's status page."""
        new = result.as_dict()
        if result.newer and (self.release or {}).get("latest") != result.latest:
            log.warning("Update: neuer TinyBox-Release %s auf GitHub (läuft: %s): %s",
                        result.latest, result.current, result.url)
        self.release = new

    # -- status -------------------------------------------------------------

    def tx_status(self) -> dict[str, Any]:
        """What the station sends right now (web GUI, view "Sendung")."""
        if not self.carousel:
            return {"station": False}
        return {"station": True, "connected": self.link.connected.is_set(),
                "interface": self.cfg.direwolf.describe(),
                "pages": len(self.store.list_pages()), **self.carousel.tx_state()}

    def status(self) -> dict[str, Any]:
        now = self.clock()
        info: dict[str, Any] = {
            "version": VERSION, "mode": self.cfg.mode, "callsign": self.cfg.callsign,
            "kiss_connected": self.link.connected.is_set(),      # name kept for the web UI
            "interface": self.cfg.direwolf.describe(),
            "rx_frames": self.link.rx_frames, "tx_frames": self.link.tx_frames,
            "rx_pages": self.rx_pages, "rx_errors": self.rx_errors,
            "dictionary": {"version": self.codec.d.version, "hash": self.codec.d.hash4.hex()},
            "release": self.release,
            "wire": {"format": self.cfg.station.wire_format if self.cfg.is_station else None,
                     "compress": self.cfg.station.compress and self.zd.ok,
                     "zdict": self.zd.describe(),
                     "assembled": self.assembler.assembled,
                     "incomplete": self.assembler.dropped,
                     "waiting": self.assembler.waiting()},
        }
        if self.carousel:
            b = self.carousel.budget
            info["pages"] = len(self.store.list_pages())
            info["due"] = len(self.store.due_pages(int(now)))
            info["airtime_used_s"] = round(b.spent(now), 1)
            info["airtime_limit_s"] = round(b.limit, 1)
        return info

    # -- run ----------------------------------------------------------------

    async def run(self) -> None:
        cfg = self.cfg
        st = cfg.station
        log.info("brocastd start - Version %s", VERSION, extra=colorlog.HEAD)
        items: list = [("Modus", cfg.mode), ("Rufzeichen", cfg.callsign or "-"), None,
                       ("Verbindung über", cfg.direwolf.describe()),
                       ("Funk", f"{st.baud} Bd ({cfg.sources.get('baud', '-')}), "
                                f"TXDELAY {st.txdelay_ms} ms ({cfg.sources.get('txdelay_ms', '-')})"),
                       None, ("Preset-Wörterbuch", self.zd.describe())]
        if cfg.is_station:
            items.append(("Frame-Format", str(st.wire_format) + (
                ", Blockliste gepackt" if st.wire_format == FORMAT_FRAGMENT
                and st.compress and self.zd.ok else "")))
            items.append(("Alterung", ", ".join(f"ab {h} h alle {m} min" if m else f"ab {h} h Pause"
                                                for h, m in st.aging) or "aus"))
        items += [None, ("Log-Datei", cfg.log_file or "- (nur Konsole)")]
        if cfg.is_station and cfg.txlog_dir is not None:
            items.append(("Sendeprotokoll", cfg.txlog_dir))
        items.append(None)
        colorlog.kv_block(log, items)
        for hint in cfg.hints:
            log.warning("Konfig-Hinweis: %s", hint)
        if self.cfg.is_station and self.cfg.direwolf.interface == "kiss" \
                and self.cfg.station.burst_frames > 0:
            log.info("KISS: Sendepausen werden berechnet; bei belegtem Kanal können Blöcke "
                     "in Direwolf zusammenwachsen (README, „Verbindung zu Direwolf“)")
        await self.web.start()
        colorlog.kv(log, "Listener-Oberfläche", f"http://{self.web.host}:{self.web.port}/", url=True)
        tasks = [asyncio.create_task(self.link.run(), name="direwolf"),
                 asyncio.create_task(self._housekeeping(), name="housekeeping"),
                 asyncio.create_task(self._flush_loop(), name="db-flush")]
        if self.ingest and self.carousel:
            await self.ingest.start()
            tasks.append(asyncio.create_task(self.carousel.run(), name="carousel"))
        rel = config.release_module() if cfg.update_check else None
        if rel is not None:                      # PLANUNG 24: Hinweis, nie eine Installation
            self.release = {"current": rel.RELEASE, "latest": None, "newer": False}
            tasks.append(asyncio.create_task(rel.watch(
                self.on_release, cache=cfg.data_dir / "release.json", program="brocastd"),
                name="update"))
        try:
            await asyncio.gather(*tasks)
        finally:
            for t in tasks:
                t.cancel()
            if self.ingest:
                await self.ingest.close()
            await self.web.close()
            self.store.close()


TAG = "[brocst]"


def setup_logging(cfg: config.Config) -> None:
    """Console, plus a log file per start (brocastd_log_<date>_<time>.log) if log_dir is set."""
    root = logging.getLogger()
    root.setLevel(cfg.log_level)
    console = colorlog.console_handler(TAG, cfg.color)
    root.addHandler(console)
    if cfg.log_dir is not None:
        cfg.log_dir.mkdir(parents=True, exist_ok=True)
        name = f"brocastd_log_{time.strftime('%Y-%m-%d_%H-%M-%S')}.log"
        fh = logging.FileHandler(cfg.log_dir / name, encoding="utf-8")
        fh.setFormatter(logging.Formatter("%(asctime)s %(levelname)-7s %(name)s: %(message)s",
                                          "%Y-%m-%d %H:%M:%S"))
        root.addHandler(fh)
        cfg.log_file = cfg.log_dir / name               # shown in the start block


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="brocastd")
    ap.add_argument("-c", "--config", default="brocastd.conf")
    args = ap.parse_args(argv)
    try:
        cfg = config.load(args.config)
    except config.ConfigError as exc:
        print(f"{TAG} [ERROR] Konfigurationsfehler: {exc}", file=sys.stderr)
        return 2
    setup_logging(cfg)

    async def run() -> None:
        # systemd stoppt mit SIGTERM: sauber beenden, damit Daemon.run() im finally
        # die flüchtigen Datenbank-Daten noch schreibt (PLANUNG 11, Punkt 9)
        task = asyncio.current_task()
        try:
            asyncio.get_running_loop().add_signal_handler(signal.SIGTERM, task.cancel)
        except (NotImplementedError, AttributeError, RuntimeError):
            pass                                 # Windows: kein SIGTERM vom Dienst
        # create the daemon inside the running loop (asyncio.Event on Python 3.9)
        await Daemon(cfg).run()

    try:
        asyncio.run(run())
    except (KeyboardInterrupt, asyncio.CancelledError):
        log.info("beendet")
    return 0


if __name__ == "__main__":
    sys.exit(main())
