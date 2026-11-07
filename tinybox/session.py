"""One user session, independent of the transport (AGW, telnet, ...).

The adapter feeds complete input lines into Session.handle_line() and
gives the session a Transport to write to and to close the connection.
"""

from __future__ import annotations

import logging
import time
from enum import Enum
from typing import Protocol

from prcore.profile import ProfileError

from . import logsetup, profiles, texts
from .config import Config
from .service import MessageService, ServiceError
from .store import utc_now

log = logging.getLogger("tinybox.monitor")

MAX_LINE = 1024
CTRL_Z = "\x1a"


class Transport(Protocol):
    def write(self, text: str) -> None:
        """Send text. Lines are separated by CR ('\\r')."""

    def close(self) -> None:
        """Disconnect after pending output is sent."""

    def abort_output(self) -> None:
        """Drop output that is still queued (command A)."""


class State(Enum):
    COMMAND = 1
    SEND_SUBJECT = 2
    SEND_BODY = 3
    CLOSED = 4
    CHAT = 5
    COLLECT = 6     # client protocol: n raw lines for a callback (//SEND)
    PROFILE = 7     # CR73: questions for name, locator, home BBS after the login


PAGE_LINES = 10     # terminal output longer than this starts with the abort hint (CR40)


class Session:
    def __init__(self, call: str, service: MessageService, cfg: Config,
                 transport: Transport, origin: str, sysop: bool = False,
                 monitor: bool = True) -> None:
        self.call = call
        self.service = service
        self.cfg = cfg
        self.transport = transport
        self.origin = origin
        self.sysop = sysop
        self.monitor = monitor  # log traffic to logger "tinybox.monitor"
        # Every log line of this connection carries "#7 OE3TEC" (CR32), also the
        # lines written by store, chat and sync: grep "#7" gives the whole session.
        self.log_id = logsetup.next_session_id()
        self.log_ctx = f"#{self.log_id} {call}"
        self._t0 = time.monotonic()
        logsetup.counters.sessions += 1
        self.started = utc_now()
        self._closed_by_us = False      # CR44: B command or timeout -> "bye"
        self._logged = False
        self.state = State.COMMAND
        self.chat_board: str | None = None  # set by ChatHub while in a board
        self.client = None  # clientproto.ClientInfo after //CLIENT (TinyBox client)
        self.ui_rx = None   # linkq.RxWindow while a UI client is in a chat board
        # message being composed
        self._to = ""
        self._type = "P"
        self._at = ""
        self._bid: str | None = None
        self._subject = ""
        self._body: list[str] = []
        self._body_bytes = 0
        # client protocol: lines to collect (see collect())
        self._collect_n = 0
        self._collect_lines: list[str] = []
        self._collect_done = None
        self._collect_back = State.COMMAND
        # terminal output of the running command (CR29/CR40: abort hint if long)
        self._page_collect = False
        self._page_buf: list[str] = []
        # client protocol: raw bytes to collect (image upload, CR12 - see collect_raw())
        self.raw_need = 0
        self.raw_since = 0.0        # when the last raw byte came in (timeout)
        self._raw_chunk = None
        self._raw_done = None
        self._raw_cancel = None
        # CR73: profile questions after the login (fields still to ask, answers)
        self._ask_fields: list[str] = []
        self._ask_answers: dict[str, str] = {}

    # --- output ---------------------------------------------------------

    def out(self, *lines: str) -> None:
        if self._page_collect:                   # a terminal command: paged at its end
            self._page_buf.extend(lines)
            return
        text = "\r".join(lines) + "\r"
        if self.monitor:
            with logsetup.session_context(self.log_ctx):
                for line in lines:
                    log.info("> %s", line)
        self.transport.write(text)

    # --- terminal paging (CR29) ------------------------------------------

    def flush_output(self) -> None:
        """Write what a command has produced so far, without paging (for a
        command that then writes to the transport itself, e.g. DICT)."""
        buf, self._page_buf = self._page_buf, []
        self._page_collect = False
        if buf:
            self.out(*buf)

    def _page_end(self) -> None:
        """End of a terminal command. Output longer than PAGE_LINES starts with
        a hint that A aborts it, then goes out in full (CR40, replaces the pages
        of CR29). A drops what is still queued for the radio (transport
        abort_output); what Direwolf already has (max_outstanding) still goes."""
        buf, self._page_buf = self._page_buf, []
        self._page_collect = False
        if len(buf) > PAGE_LINES and self.state == State.COMMAND:
            buf = [texts.LONG_OUTPUT.format(n=len(buf)), *buf]
        if buf:
            self.out(*buf)

    def prompt(self) -> None:
        if self.client is not None:     # a client program needs no prompt
            return
        self.transport.write(texts.PROMPT_SYSOP if self.sysop else texts.PROMPT)

    def prompt_again(self) -> None:
        """After a message in between (system message): the prompt once more,
        but not while the user types a message or chats."""
        if self.state == State.COMMAND:
            self.prompt()

    def error(self, exc: ServiceError, msg_id: int | str = "") -> None:
        if exc.code == "not_found":
            self.out(texts.NO_SUCH_MSG.format(id=msg_id))
        elif exc.code == "not_allowed" and "third party" in str(exc):
            self.out(texts.THIRD_PARTY_OFF.format(sysop=self.cfg.station.sysop_call))
        elif exc.code == "not_allowed":
            self.out(texts.NOT_ALLOWED)
        elif exc.code == "invalid_call":
            self.out(texts.INVALID_CALL.format(call=str(exc)))
        elif exc.code == "too_large":
            self.out(texts.TOO_LARGE.format(max=self.cfg.mailbox.max_msg_bytes))
        elif exc.code == "invalid_address":
            self.out(texts.INVALID_ADDRESS.format(addr=str(exc)))
        elif exc.code == "duplicate":
            self.out(texts.DUPLICATE_BID.format(bid=str(exc)))
        elif exc.code == "no_forward":
            self.out(texts.NO_FORWARD.format(addr=str(exc)))
        elif exc.code == "bad_rubric":
            self.out(texts.BAD_RUBRIC.format(rubric=str(exc),
                                             rubrics=" ".join(self.service.writable_rubrics())))
        else:
            self.out(texts.INVALID_VALUE.format(value=str(exc)))

    # --- lifecycle ------------------------------------------------------

    @property
    def idle_exempt(self) -> bool:
        """In a chat board, reading along without typing is allowed."""
        return self.state == State.CHAT

    @property
    def closed(self) -> bool:
        return self.state == State.CLOSED

    def start(self) -> None:
        self.service.login(self.call, self.origin)
        mailbox = self.cfg.station.mailbox_call
        lines = [texts.HELLO.format(mailbox=mailbox, call=self.call)]
        if self.cfg.mailbox.welcome_enabled and self.cfg.mailbox.welcome_text:
            lines.append(self.cfg.mailbox.welcome_text)
        n = len(self.service.unread_for(self.call))
        lines.append(texts.NEW_MSGS.format(n=n) if n else texts.NO_NEW_MSGS)
        chat = self.service.chat
        if chat.enabled and chat.total_members():
            lines.append(texts.CHAT_ACTIVE.format(n=chat.total_members()))
        left = self.service.shutdown_left() if self.service.shutdown_left else None
        if left is not None:             # shutdown pending: warn new stations too
            lines.append(texts.SHUTDOWN_WARNING.format(
                mailbox=mailbox, sysop=self.cfg.station.sysop_call,
                left="1 second" if left == 1 else f"{left} seconds"))
        ask = self._profile_due()
        if ask:
            lines.append(texts.PROFILE_INTRO)
        self.out(*lines)
        if ask:
            self.service.store.profile_asked(profiles.base_call(self.call))
            self._ask_fields, self._ask_answers = ask, {}
            self._ask_next()
        else:
            self.prompt()

    # --- profile questions after the login (CR73) --------------------------

    def _profile_due(self) -> list[str]:
        """Fields to ask a terminal user for. Not on the sysop console; a
        client announces itself with //CLIENT and has its own form (that line
        ends the questions, see _handle_line)."""
        if not self.cfg.mailbox.ask_profile or self.origin == "sysop" or self.client is not None:
            return []
        return profiles.ask_due(self.service.store, self.call)

    def _ask_next(self) -> None:
        if not self._ask_fields:
            self._ask_end()
            return
        self.state = State.PROFILE
        question = texts.PROFILE_ASK[self._ask_fields[0]]
        if self.monitor:                     # without CR: the answer goes on the same line
            log.info("> %s", question.rstrip())
        self.transport.write(question)

    def _ask_end(self, quiet: bool = False) -> None:
        """Store what was answered, back to the commands."""
        answers, self._ask_fields, self._ask_answers = self._ask_answers, [], {}
        if answers:
            profiles.save(self.service.store, self.call, answers)
        self.state = State.COMMAND
        if not quiet:
            self.out(texts.PROFILE_THANKS if answers else texts.PROFILE_LATER)

    def _on_profile(self, line: str) -> None:
        if CTRL_Z in line or line.strip().upper() == "/AB":
            self._ask_end()
            return
        field = self._ask_fields[0]
        try:
            value = profiles.check_field(field, line)
        except ProfileError:
            self.out(texts.PROFILE_BAD[field])
            self._ask_next()                 # the same question again
            return
        if value:
            self._ask_answers[field] = value
        self._ask_fields.pop(0)
        self._ask_next()

    def close(self) -> None:
        """Log off from the mailbox side (command B, timeout)."""
        if self.state != State.CLOSED:
            self.flush_output()              # "73, bye" before the link goes down
            self._closed_by_us = True
            self.state = State.CLOSED
            self.transport.close()

    def end(self, lost: bool = False) -> None:
        """Called by the adapter when the connection is gone (lost: retries used up)."""
        with logsetup.session_context(self.log_ctx):
            if self.state in (State.SEND_SUBJECT, State.SEND_BODY):
                log.info("disconnected while sending, message discarded")
            if self.state == State.PROFILE and self._ask_answers:
                self._ask_end(quiet=True)        # what was answered so far is kept
            self.state = State.CLOSED
            self.service.chat.leave(self, reason=texts.CHAT_REASON_LOST if lost
                                    else texts.CHAT_REASON_DISC, lost=lost)
            self.service.logout(self.call, self.origin)
            logging.getLogger("tinybox.session").info(
                "session end via %s after %s%s", self.origin, logsetup.ms(self._t0),
                " - connection lost" if lost else "")
            self._log_connection(lost)

    def _log_connection(self, lost: bool) -> None:
        """CR44: one row in the connection logbook - station, way, times, bytes.
        The local sysop console is no connection."""
        if self._logged or self.origin == "sysop":
            return
        self._logged = True
        t = self.transport
        q = getattr(getattr(t, "quality", None), "last", None) or {}
        air_tx = (q.get("bytes_new", 0) + q.get("bytes_retry", 0)) if q else None
        try:
            self.service.store.connlog_add({
                "call": self.call, "via": self.origin, "start": self.started, "end": utc_now(),
                "secs": int(time.monotonic() - self._t0),
                "rx": getattr(t, "rx_bytes", None), "tx": getattr(t, "tx_bytes", None),
                "air_tx": air_tx, "air_rx": q.get("bytes_rx") if q.get("bytes_rx") else None,
                "ended": "bye" if self._closed_by_us else "lost" if lost else "disc"})
        except Exception:                 # the logbook must never break a disconnect
            logging.getLogger("tinybox.session").exception("connection log: row not written")

    # --- input ----------------------------------------------------------

    def handle_line(self, line: str) -> None:
        if self.closed:
            return
        line = line[:MAX_LINE]
        with logsetup.session_context(self.log_ctx):
            self._handle_line(line)

    def _handle_line(self, line: str) -> None:
        if self.monitor:
            # The text of a mail only as length plus the first characters: the
            # log is put into chats, other people's post must not ride along.
            # With LOG DEBUG session it is written in full (CR32).
            if self.state in (State.SEND_SUBJECT, State.SEND_BODY):
                log.info("< %s", logsetup.short(line, full=logsetup.debug_on("session")))
            else:
                log.info("< %s", line)
        started = time.monotonic()
        try:
            if self.state == State.PROFILE and line.strip().upper().startswith("//TB?"):
                # CR76: a TBClient asks what it reached - answer, the question stays
                from . import clientproto  # local import avoids a cycle
                clientproto.tb_probe(self)
                self._ask_next()
                return
            if self.state == State.PROFILE and line.lstrip().startswith("//"):
                # a TinyBox client announces itself (//CLIENT) while the terminal
                # questions are up: they are over, the client has its own form
                self._ask_end(quiet=True)
            if self.state == State.PROFILE:
                self._on_profile(line)
            elif self.state == State.COLLECT:
                self._on_collect(line)
            elif self.state == State.COMMAND:
                from . import commands  # local import avoids a cycle
                self._page_collect = self.client is None
                try:
                    commands.dispatch(self, line)
                finally:
                    self._page_end()
            elif self.state == State.SEND_SUBJECT:
                self._on_subject(line)
            elif self.state == State.SEND_BODY:
                self._on_body_line(line)
            elif self.state == State.CHAT:
                from . import chatcmd  # local import avoids a cycle
                chatcmd.handle(self, line)
        except Exception:
            # A bug or a storage error must not kill the connection (or, over
            # AGW, the whole radio link). The traceback goes to the log together
            # with the line that caused it - that is what makes it reproducible.
            logging.getLogger("tinybox").exception(
                "internal error handling %r (state %s)", line, self.state.name)
            if self.state != State.CLOSED:
                self.service.chat.leave(self)
                self._page_collect, self._page_buf = False, []
                self.state = State.COMMAND
                self.out(texts.INTERNAL_ERROR)
        else:
            slow = logsetup.ms_if_slow(started)
            if slow:
                logging.getLogger("tinybox.commands").debug("%r took %s", line, slow)
        if self.state == State.COMMAND:
            self.prompt()

    # --- client protocol: take the next n lines as they are --------------

    def collect(self, n: int, done) -> None:
        """The next n input lines go unchanged to done(lines) - also inside a
        chat board, where the session returns to afterwards."""
        self._collect_back = self.state
        self._collect_n, self._collect_lines, self._collect_done = n, [], done
        self.state = State.COLLECT

    def _on_collect(self, line: str) -> None:
        self._collect_lines.append(line)
        if len(self._collect_lines) < self._collect_n:
            return
        self.state = self._collect_back
        done, lines = self._collect_done, self._collect_lines
        self._collect_done, self._collect_lines = None, []
        done(lines)

    # --- client protocol: the next n bytes as they are (binary) ----------

    def collect_raw(self, n: int, chunk, done, cancel=None) -> None:
        """The next n input bytes are binary data, not lines: every piece goes
        to chunk(bytes) as it arrives (so nothing is lost when the link breaks),
        done() is called after the last one. cancel() is called when the data
        stops coming (raw_timeout). The adapter looks at raw_need before it
        splits lines (AGW only)."""
        if n <= 0:
            done()
            return
        self.raw_need, self._raw_chunk, self._raw_done = n, chunk, done
        self._raw_cancel = cancel
        self.raw_since = time.monotonic()

    def _raw_end(self):
        self.raw_need = 0
        done, cancel = self._raw_done, self._raw_cancel
        self._raw_chunk = self._raw_done = self._raw_cancel = None
        return done, cancel

    def feed_raw(self, data: bytes) -> None:
        """At most raw_need bytes from the adapter."""
        self.raw_need -= len(data)
        self.raw_since = time.monotonic()
        try:
            self._raw_chunk(data)
            if self.raw_need <= 0:
                done, _ = self._raw_end()
                done()
        except Exception:
            self._raw_end()
            with logsetup.session_context(self.log_ctx):
                logging.getLogger("tinybox").exception(
                    "internal error handling %d raw bytes", len(data))
            if self.state != State.CLOSED:
                self.out(texts.INTERNAL_ERROR)

    def raw_timeout(self, limit: float, now: float | None = None) -> bool:
        """True if binary data was announced but stopped coming: back to lines.
        What came so far is kept, the client goes on where it stopped."""
        if self.raw_need <= 0:
            return False
        now = time.monotonic() if now is None else now
        if now - self.raw_since < limit:
            return False
        missing = self.raw_need
        _, cancel = self._raw_end()
        with logsetup.session_context(self.log_ctx):
            logging.getLogger("tinybox").info(
                "%d bytes of binary data never arrived, back to lines", missing)
        if cancel is not None and self.state != State.CLOSED:
            cancel()
        return True

    # --- composing a message -------------------------------------------

    def begin_send(self, to_call: str | list[str], type: str, at_addr: str = "",
                   bid: str | None = None) -> None:
        # CR27: a list = one message per recipient, same text
        self._to = [to_call] if isinstance(to_call, str) else list(to_call)
        self._type = type
        self._at, self._bid = at_addr, bid
        self._subject, self._body, self._body_bytes = "", [], 0
        self.state = State.SEND_SUBJECT
        # written without CR so the user types on the same line -> log it here,
        # out() would append a line break
        if self.monitor:
            log.info("%s > %s", self.call, texts.SUBJECT_PROMPT.rstrip())
        self.transport.write(texts.SUBJECT_PROMPT)

    def _on_subject(self, line: str) -> None:
        if CTRL_Z in line or line.strip().upper() == "/AB":
            self.out(texts.CANCELLED)
            self.state = State.COMMAND
            return
        self._subject = line.strip()
        self.out(texts.BODY_PROMPT)
        self.state = State.SEND_BODY

    def _on_body_line(self, line: str) -> None:
        finished = False
        if CTRL_Z in line:
            line = line.split(CTRL_Z, 1)[0]
            finished = True
        elif line.strip().upper() == "/EX":
            line, finished = "", True
        elif line.strip().upper() == "/AB":
            self.out(texts.CANCELLED)
            self.state = State.COMMAND
            return

        if line or not finished:
            self._body.append(line)
            self._body_bytes += len(line.encode("utf-8")) + 1
            if self._body_bytes > self.cfg.mailbox.max_msg_bytes:
                self.out(texts.TOO_LARGE.format(max=self.cfg.mailbox.max_msg_bytes))
                self.state = State.COMMAND
                return

        if finished:
            self.state = State.COMMAND
            ids = []
            body = self.service.multi_to_line(self._to) + "\n".join(self._body)
            try:
                for to in self._to:
                    ids.append(self.service.create(
                        from_call=self.call, to_call=to, type=self._type,
                        subject=self._subject, body=body,
                        origin=self.origin, sysop=self.sysop,
                        at_addr=self._at, bid=self._bid,
                    ))
            except ServiceError as exc:
                self.error(exc)
                if not ids:
                    return
            self.out(texts.SAVED.format(id=", ".join(map(str, ids))))


class SessionRegistry:
    """Keeps track of active sessions across all adapters (max_users)."""

    def __init__(self, max_users: int) -> None:
        self.max_users = max_users
        self._sessions: list[Session] = []

    def add(self, session: Session) -> bool:
        if len(self._sessions) >= self.max_users:
            return False
        self._sessions.append(session)
        return True

    def remove(self, session: Session) -> None:
        if session in self._sessions:
            self._sessions.remove(session)

    def __len__(self) -> int:
        return len(self._sessions)

    def __iter__(self):
        return iter(list(self._sessions))
