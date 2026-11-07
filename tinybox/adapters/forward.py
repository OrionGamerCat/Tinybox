"""Forward module: exchange mail with partner mailboxes ([forward] enabled = yes).

Started by __main__ only when enabled; without it TinyBox is a standalone mailbox.

- listens to the event bus: new mail with fwd '$' goes into the queue of the
  partner(s) the router picks; deleted / expired mail leaves the queue
- answers partner connects: over AGW (the AGW adapter hands them over) and on
  the TCP forward port ([forward] listen_port, with callsign + password login)
- calls partners: FWD (all) or FWD <call> on the sysop console, or by itself (scheduler):
  when mail waits for a partner with auto = yes, every interval_min minutes if
  set, only inside the partner's window; after a failure, and for mail the
  partner wanted "later", it waits retry_min
- HOLD n / REL n (sysop): keep a message from forwarding / release it again
- at the start: bulletins held because of a new rubric (CR19) are released
  or deleted when the sysop has put the rubric into [rubrics]

Sessions receive (F3) and send (F4), see tinybox/fwd/.
"""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime
from typing import Any

from prcore import termcolor

from ..app import App
from ..config import LOOPBACK_HOSTS, PartnerCfg, normalize_call
from ..fwd.link import AgwLink, TcpLink
from ..fwd.router import Router
from ..fwd.session import ForwardSession, SessionResult

log = logging.getLogger("tinybox.forward")

LOGIN_TIMEOUT = 60
SCHED_SEC = 30          # scheduler round
SETTLE_SEC = 2          # after new mail: wait a moment, then call


class ForwardModule:
    def __init__(self, app: App) -> None:
        self.app = app
        self.cfg = app.cfg.forward
        self.router = Router(self.cfg, app.cfg.station.address)
        self.wake = asyncio.Event()
        self.last_call: dict[str, float] = {}             # monotonic time of the last call
        self.failed_at: dict[str, float] = {}             # monotonic time of the last failure
        self._loop: asyncio.AbstractEventLoop | None = None
        self.busy: set[str] = set()                       # partners in a session now
        self.last: dict[str, SessionResult] = {}          # last result per partner
        self.server: asyncio.AbstractServer | None = None
        self.listen_port = 0
        self.tasks: set[asyncio.Task] = set()
        for name in ("message.created", "message.deleted", "message.expired"):
            app.bus.subscribe(name, self.on_event)

    # --- queue -----------------------------------------------------------------

    def on_event(self, name: str, data: dict[str, Any]) -> None:
        store = self.app.store
        if name == "message.created":
            msg = data["message"]
            if msg is None or msg.fwd != "$":
                return
            targets = self.router.targets(msg)
            if not targets and msg.type == "B":
                # a bulletin nobody else needs (e.g. all partners already had it):
                # it is simply ours now, nothing to forward - not held
                self.app.service.set_fwd_state(msg.id, "", "")
                return
            if not targets:
                log.warning("msg %d (%s) @ %s: no partner - held", msg.id, msg.bid, msg.at_addr)
                self.app.service.set_fwd_state(msg.id, "H", "no route to " + msg.at_addr)
                return
            for partner in targets:
                store.fwd_enqueue(msg.id, partner)
            log.info("msg %d (%s) queued for %s", msg.id, msg.bid, ", ".join(targets))
            self._wake()
        elif name == "message.deleted":
            store.fwd_remove([data["message"].id])
        elif name == "message.expired":
            store.fwd_remove(list(data.get("ids", [])))

    def _wake(self) -> None:
        """Wake the scheduler - also when the event came from another thread."""
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            if self._loop is not None:
                self._loop.call_soon_threadsafe(self.wake.set)
            return
        self.wake.set()

    # --- sysop: hold / release ---------------------------------------------------------

    def hold(self, msg_id: int) -> str:
        msg = self.app.store.get(msg_id)
        if msg is None:
            raise KeyError(msg_id)
        self.app.service.set_fwd_state(msg_id, "H", "held by sysop")
        return "H"

    def release(self, msg_id: int) -> str:
        """Back into the queue if it has to leave, else simply local. Returns the new state."""
        store, st = self.app.store, self.app.cfg.station
        msg = store.get(msg_id)
        if msg is None:
            raise KeyError(msg_id)
        from .. import addressing
        if not msg.at_addr or addressing.is_local(msg.at_addr, st.mailbox_call):
            self.app.service.set_fwd_state(msg_id, "", "")
            return ""
        targets = self.router.targets(msg)
        if not targets:
            if msg.type == "B":
                self.app.service.set_fwd_state(msg_id, "", "")
                return ""
            self.app.service.set_fwd_state(msg_id, "H", "no route to " + msg.at_addr)
            return "H"
        for partner in targets:
            store.fwd_enqueue(msg_id, partner)
            store.fwd_set(msg_id, partner, "open")
        self.app.service.set_fwd_state(msg_id, "$", "")
        self._wake()
        return "$"

    def resolve_rubrics(self) -> tuple[int, int]:
        """Bulletins held for a new rubric (CR19): accepted now -> released,
        refused now -> deleted, still unknown -> stay held. Returns (released, deleted)."""
        svc = self.app.service
        released = deleted = 0
        for msg in svc.new_rubric_waiting():
            state = svc.rubric_state(msg.to_call)
            if state == "accepted":
                self.release(msg.id)
                released += 1
            elif state in ("refused", "system"):
                svc.delete(msg.id, self.app.cfg.station.sysop_call, sysop=True)
                deleted += 1
        if released or deleted:
            log.info("new rubrics decided by the sysop: %d bulletin(s) released, %d deleted",
                     released, deleted)
        return released, deleted

    # --- partners ----------------------------------------------------------------

    def partner_for_radio(self, remote: str) -> PartnerCfg | None:
        p = self.cfg.partner_by_radio_call(remote)
        return p if p is not None and p.transport == "agw" else None

    def _spawn(self, coro) -> asyncio.Task:
        task = asyncio.create_task(coro)
        self.tasks.add(task)
        task.add_done_callback(self.tasks.discard)
        return task

    async def _run(self, partner: PartnerCfg, link, master: bool, transport: str) -> SessionResult:
        self.busy.add(partner.call)
        try:
            s = ForwardSession(self.app.cfg.station.bbs_call, partner, link, master=master,
                               transport=transport, service=self.app.service)
            result = await s.run()
        finally:
            self.busy.discard(partner.call)
        self.last[partner.call] = result
        self.last_call[partner.call] = time.monotonic()
        if result.ok:
            self.failed_at.pop(partner.call, None)
        else:
            self.failed_at[partner.call] = time.monotonic()
        return result

    # --- incoming ------------------------------------------------------------------

    def attach_agw(self, conn, remote: str) -> None:
        """Called by the AGW adapter for a connect from a partner's radio call."""
        partner = self.partner_for_radio(remote)
        if partner is None or partner.call in self.busy:
            log.warning("%s: forward connect refused (%s)", remote,
                        "busy" if partner else "no partner")
            conn.close()
            return
        link = AgwLink(conn, f"ax25:{remote}")
        conn.session = link
        self._spawn(self._run(partner, link, master=False, transport="agw"))

    async def _tcp_in(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        peer = writer.get_extra_info("peername")
        link = TcpLink(reader, writer, f"tcp:{peer}")
        try:
            link.write_lines("Callsign:")
            call = normalize_call((await link.readline(LOGIN_TIMEOUT)) or "")
            link.write_lines("Password:")
            password = ((await link.readline(LOGIN_TIMEOUT)) or "").strip()
        except asyncio.TimeoutError:
            await link.close()
            return
        partner = self.cfg.partner(call)
        open_port = self.cfg.listen_host in LOOPBACK_HOSTS
        ok = (partner is not None and partner.transport == "tcp"
              and (password == partner.password if partner.password else open_port)
              and partner.call not in self.busy)
        if not ok:
            log.warning("TCP forward login refused: %r from %s", call, peer)
            link.write_lines("Login failed.")
            await link.close()
            return
        log.info("TCP forward login %s from %s", partner.call, peer)
        await self._run(partner, link, master=False, transport="tcp")

    # --- outgoing ------------------------------------------------------------------

    async def call(self, call: str) -> SessionResult:
        """Connect to a partner now (sysop command FWD)."""
        partner = self.cfg.partner(call)
        if partner is None:
            raise KeyError(f"{call} is not a forward partner")
        if partner.call in self.busy:
            raise ConnectionError(f"already in a session with {partner.call}")
        if partner.transport == "tcp":
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(partner.host, partner.port), partner.timeout)
            link = TcpLink(reader, writer, f"tcp:{partner.call}")
            if partner.login:
                link.write_lines(*partner.login)
            return await self._run(partner, link, master=True, transport="tcp")
        agw = self.app.agw
        if agw is None:
            raise ConnectionError("AGW adapter not running")
        holder: dict[str, AgwLink] = {}

        def attach(conn) -> None:
            holder["link"] = conn.session = AgwLink(conn, f"ax25:{partner.radio_call}")

        await agw.connect(partner.radio_call, attach, partner.via, timeout=partner.timeout)
        return await self._run(partner, holder["link"], master=True, transport="agw")

    # --- lifecycle -----------------------------------------------------------------

    async def start_server(self) -> None:
        if self.cfg.listen_port:
            self.server = await asyncio.start_server(self._tcp_in, self.cfg.listen_host,
                                                     self.cfg.listen_port)
            self.listen_port = self.server.sockets[0].getsockname()[1]
            termcolor.kv(log, "Forward port", f"{self.cfg.listen_host}:{self.listen_port}")

    # --- scheduler ---------------------------------------------------------------------

    def due(self, p: PartnerCfg, now: float, minute_of_day: int) -> bool:
        """Should we call this partner now?"""
        if not p.auto or p.call in self.busy or not p.in_window(minute_of_day):
            return False
        failed = self.failed_at.get(p.call)
        if failed is not None and now - failed < p.retry_min * 60:
            return False
        last = self.last_call.get(p.call)
        pending = self.app.store.fwd_pending(p.call)
        if pending:
            states = {self.app.store.fwd_states(m.id).get(p.call) for m in pending}
            if "open" in states:
                return True
            # only mail the partner wanted "later": try again after retry_min
            if last is None or now - last >= p.retry_min * 60:
                return True
        return bool(p.interval_min) and (last is None or now - last >= p.interval_min * 60)

    async def _call_logged(self, call: str) -> None:
        try:
            await self.call(call)
        except Exception as exc:              # unreachable partner etc.: retry later
            log.warning("forward call %s failed: %s", call, exc or type(exc).__name__)
            if call not in self.busy:          # not just "partner is calling us right now"
                self.failed_at[call] = time.monotonic()

    def tick(self) -> list[str]:
        """One scheduler round: start sessions with every partner that is due."""
        now, local = time.monotonic(), datetime.now()
        started = []
        for p in self.cfg.partners.values():
            if self.due(p, now, local.hour * 60 + local.minute):
                self.busy.add(p.call)          # reserve now; _run takes it over
                self._spawn(self._start(p.call))
                started.append(p.call)
        return started

    async def _start(self, call: str) -> None:
        self.busy.discard(call)
        await self._call_logged(call)

    async def run(self) -> None:
        """Scheduler: looks every SCHED_SEC seconds, and soon after new mail was queued."""
        self._loop = asyncio.get_running_loop()
        try:
            while True:
                try:
                    await asyncio.wait_for(self.wake.wait(), SCHED_SEC)
                    await asyncio.sleep(SETTLE_SEC)        # collect a few messages first
                except asyncio.TimeoutError:
                    pass
                self.wake.clear()
                self.tick()
        finally:
            if self.server is not None:
                self.server.close()
            for task in list(self.tasks):
                task.cancel()

    def status_lines(self) -> list[str]:
        queue = self.app.store.fwd_queue_list()
        out = [f"Forward: {self.app.cfg.station.address}, {len(self.cfg.partners)} partner(s), "
               f"{len(queue)} message(s) queued"
               + (f", TCP port {self.cfg.listen_host}:{self.listen_port}" if self.server else "")]
        for p in self.cfg.partners.values():
            n = sum(1 for q in queue if q[0] == p.call)
            last = self.last.get(p.call)
            state = "in session" if p.call in self.busy else (last.summary() if last else "-")
            mode = ("auto" + (f"/{p.interval_min}m" if p.interval_min else "")
                    + (" window" if p.window else "")) if p.auto else "manual"
            out.append(f"  {p.call:<7} {p.transport:<3} {p.protocol:<5} {mode:<12} "
                       f"queued {n:>3}  {state}")
        return out


async def start(app: App) -> asyncio.Task:
    module = ForwardModule(app)
    app.forward = module
    module.resolve_rubrics()
    await module.start_server()
    log.info("forward module on: %s, partners %s", app.cfg.station.address,
             ", ".join(module.cfg.partners) or "none")
    return asyncio.create_task(module.run())
