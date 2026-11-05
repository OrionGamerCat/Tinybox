"""The way to the TNC: a serial port or a TCP connection.

Both give the same small interface to tnc.py:
    await open()    raises OSError / serial errors when the TNC is not there
    write(data)     never blocks the event loop
    await read()    next chunk of bytes; raises ConnectionError when the link is gone
    close()

SerialTransport uses pyserial with one reader and one writer thread: at
9600 Bd a 300-byte write takes 0.3 s, which must not stall the asyncio loop.
Port settings as pk232py found them working on the PK-232 (P54.2): 8N1,
no XON/XOFF, no RTS/CTS, DTR and RTS asserted.

RTS/CTS (rtscts = yes in the TNC section, e.g. [tm-d710], 25.10.2026; reworked 26.10.2026):
the radio holds CTS low while its buffer is full. The port driver is asked to
stop on CTS (rtscts=True), but that alone is not enough - write() returns as
soon as the bytes are in the operating system's buffer (kilobytes), and some
USB adapters (PL2303 types, clones) keep sending their FIFO after CTS went low.
So kisshub does its own flow control as well: small pieces (CHUNK bytes), each
one pushed out of the port (flush) before CTS is checked again. At most one
piece plus the adapter's FIFO can overrun the radio instead of everything
queued in the driver.

A monitor thread samples CTS every CTS_POLL_SEC and counts every time the
radio takes it away (cts_drops, cts_low_s, cts_low_max_ms), with each change
in the DEBUG log - so the log shows whether the radio paces at all (the
TM-D700 never drops CTS in KISS mode, 26.10.2026). cts_waits / cts_wait_s
count only the times the writer itself had to wait.

A write that fails (unplugged adapter and the like) ends the port like a
failed read: read() raises ConnectionError and tnc.py reconnects - before,
the writer thread just ended and kisshub went silent on the air.

TcpTransport is for a TNC behind a network serial server (ser2net and the
like) and for the tests.
"""

from __future__ import annotations

import asyncio
import logging
import queue
import threading
import time

log = logging.getLogger(__name__)

CHUNK = 32                 # bytes per write with RTS/CTS: at 9600 Bd ~33 ms on the wire
CTS_WARN_SEC = 5.0         # CTS low this long: one warning (radio busy, cable, menu)
CTS_POLL_SEC = 0.002       # CTS monitor: sample interval


def driver_rtscts(ser) -> bool | None:
    """Linux/macOS: is hardware flow control really switched on in the driver
    (termios CRTSCTS, what 'stty -a' shows as crtscts)? None where unknown."""
    try:
        import termios
        return bool(termios.tcgetattr(ser.fileno())[2] & termios.CRTSCTS)
    except Exception:
        return None


class SerialTransport:
    def __init__(self, device: str, baud: int, dtr: bool = True, rts: bool = True,
                 rtscts: bool = False) -> None:
        self.device, self.baud, self.dtr, self.rts = device, baud, dtr, rts
        self.rtscts = rtscts
        self.cts_waits = 0                 # times the writer waited for CTS
        self.cts_wait_s = 0.0              # total time CTS held the writer back
        self.cts_drops = 0                 # monitor: times the radio took CTS away
        self.cts_low_s = 0.0               # monitor: total time CTS was low
        self.cts_low_max_s = 0.0           # monitor: longest single CTS low
        self.tx_bytes = 0                  # bytes written to the port
        self.crtscts: bool | None = None   # Linux: driver flow control really on (termios)
        self._loop: asyncio.AbstractEventLoop | None = None
        self._ser = None
        self._rx: asyncio.Queue | None = None
        self._tx: queue.Queue = queue.Queue()
        self._stop = threading.Event()
        self._threads: list[threading.Thread] = []

    def describe(self) -> str:
        return f"{self.device} {self.baud} Bd" + (" RTS/CTS" if self.rtscts else "")

    def flow_status(self) -> dict:
        cts = None
        if self._ser is not None and self.rtscts:
            try:
                cts = bool(self._ser.cts)
            except Exception:
                pass
        return {"flow": "rtscts" if self.rtscts else "none", "cts": cts,
                "cts_drops": self.cts_drops, "cts_low_s": round(self.cts_low_s, 2),
                "cts_low_max_ms": round(self.cts_low_max_s * 1000),
                "cts_waits": self.cts_waits, "cts_wait_s": round(self.cts_wait_s, 1),
                "crtscts": self.crtscts, "tx_bytes": self.tx_bytes}

    async def open(self) -> None:
        import serial                                  # pyserial, only needed here

        def _open():
            # no write_timeout: a timed-out write may have sent part of a piece, and
            # the rest sent later would join two frames into one. The writer is a
            # daemon thread, so a write blocked by CTS cannot hang Ctrl+C.
            ser = serial.Serial(port=None, baudrate=self.baud, bytesize=8, parity="N",
                                stopbits=1, timeout=0.1, xonxoff=False,
                                rtscts=self.rtscts, dsrdtr=False, write_timeout=None)
            ser.port = self.device
            ser.dtr = self.dtr                           # before open: no glitch
            if not self.rtscts:                          # with RTS/CTS the driver drives RTS
                ser.rts = self.rts
            ser.open()
            ser.reset_input_buffer()
            if self.rtscts and not ser.cts:
                log.warning("%s: CTS is low - the radio does not take data yet "
                            "(TNC busy, cable without RTS/CTS lines, or radio off?)",
                            self.device)
            return ser

        self._ser = await asyncio.get_running_loop().run_in_executor(None, _open)
        loop = asyncio.get_running_loop()
        self._loop = loop
        self._rx = asyncio.Queue()
        self._stop.clear()
        self._tx = queue.Queue()
        if self.rtscts:
            self.crtscts = driver_rtscts(self._ser)
            if self.crtscts is not None:
                (log.info if self.crtscts else log.warning)(
                    "%s: driver flow control (termios CRTSCTS) %s", self.device,
                    "on" if self.crtscts else "OFF - the driver ignores CTS, only "
                    "kisshub's own check paces the radio")
        self._threads = [
            threading.Thread(target=self._reader, args=(loop,), daemon=True,
                             name="kisshub-rx"),
            threading.Thread(target=self._writer, daemon=True, name="kisshub-tx"),
        ]
        if self.rtscts:
            self._threads.append(threading.Thread(target=self._cts_monitor, daemon=True,
                                                  name="kisshub-cts"))
        for t in self._threads:
            t.start()

    def _reader(self, loop: asyncio.AbstractEventLoop) -> None:
        try:
            while not self._stop.is_set():
                data = self._ser.read(self._ser.in_waiting or 1)
                if data:
                    loop.call_soon_threadsafe(self._rx.put_nowait, data)
        except Exception as exc:                       # unplugged USB adapter and the like
            if not self._stop.is_set():
                log.warning("serial read failed: %s", exc)
        loop.call_soon_threadsafe(self._rx.put_nowait, None)

    def _writer(self) -> None:
        while not self._stop.is_set():
            try:
                data = self._tx.get(timeout=0.2)
            except queue.Empty:
                continue
            try:
                if self.rtscts:
                    for i in range(0, len(data), CHUNK):
                        if not self._wait_cts():
                            return
                        piece = data[i:i + CHUNK]
                        self._ser.write(piece)
                        self._ser.flush()            # out of the port before the next check
                        self.tx_bytes += len(piece)
                else:
                    self._ser.write(data)
                    self._ser.flush()
                    self.tx_bytes += len(data)
            except Exception as exc:
                if self._stop.is_set():
                    return
                log.warning("serial write failed: %s - reopening the port", exc)
                self._port_lost()
                return

    def _port_lost(self) -> None:
        """Writer or monitor gave up: let read() raise, tnc.py reconnects."""
        if self._loop is not None and self._rx is not None:
            try:
                self._loop.call_soon_threadsafe(self._rx.put_nowait, None)
            except RuntimeError:                       # loop already closed
                pass

    def _wait_cts(self) -> bool:
        """RTS/CTS: wait while the radio holds CTS low. False when stopping."""
        if self._ser.cts:
            return True
        start = time.monotonic()
        self.cts_waits += 1
        while not self._ser.cts:
            if self._stop.is_set():
                return False
            time.sleep(0.005)
        self.cts_wait_s += time.monotonic() - start
        return True

    def _cts_monitor(self) -> None:
        """Sample CTS and count every low phase - independent of the writer."""
        ser = self._ser
        try:
            high = bool(ser.cts)
            low_since = None if high else time.monotonic()
            if not high:
                self.cts_drops += 1
            warned = False
            while not self._stop.is_set():
                time.sleep(CTS_POLL_SEC)
                now = time.monotonic()
                cts = bool(ser.cts)
                if cts == high:
                    if not cts and not warned and now - low_since >= CTS_WARN_SEC:
                        log.warning("%s: CTS low for %.0f s - the radio holds data back",
                                    self.device, now - low_since)
                        warned = True
                    continue
                high = cts
                if not cts:
                    low_since = now
                    self.cts_drops += 1
                    log.debug("%s: CTS low (radio buffer full), %d bytes written so far",
                              self.device, self.tx_bytes)
                else:
                    low = now - low_since
                    self.cts_low_s += low
                    self.cts_low_max_s = max(self.cts_low_max_s, low)
                    (log.info if warned else log.debug)(
                        "%s: CTS high again after %.0f ms", self.device, low * 1000)
                    warned = False
        except Exception as exc:                       # port closed under us
            if not self._stop.is_set():
                log.debug("CTS monitor ended: %s", exc)

    def write(self, data: bytes) -> None:
        self._tx.put(data)

    async def drain(self, timeout: float = 5.0) -> None:
        """Wait until everything written has left the port (used before close)."""
        end = asyncio.get_running_loop().time() + timeout
        while not self._tx.empty() and asyncio.get_running_loop().time() < end:
            await asyncio.sleep(0.05)
        await asyncio.sleep(0.2)

    async def read(self) -> bytes:
        data = await self._rx.get()
        if data is None:
            raise ConnectionError(f"serial port {self.device} lost")
        return data

    def close(self) -> None:
        self._stop.set()
        if self._ser is not None:
            try:
                self._ser.cancel_write()                # a write blocked by CTS
            except Exception:
                pass
            try:
                self._ser.close()
            except Exception:
                pass
            self._ser = None


class TcpTransport:
    def __init__(self, host: str, port: int) -> None:
        self.host, self.port = host, port
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None

    def describe(self) -> str:
        return f"tcp {self.host}:{self.port}"

    async def open(self) -> None:
        self._reader, self._writer = await asyncio.open_connection(self.host, self.port)

    def write(self, data: bytes) -> None:
        if self._writer is not None and not self._writer.is_closing():
            self._writer.write(data)

    async def drain(self, timeout: float = 5.0) -> None:
        if self._writer is not None:
            try:
                await asyncio.wait_for(self._writer.drain(), timeout)
            except (asyncio.TimeoutError, ConnectionError):
                pass

    async def read(self) -> bytes:
        data = await self._reader.read(4096)
        if not data:
            raise ConnectionError(f"TNC connection {self.host}:{self.port} closed")
        return data

    def close(self) -> None:
        if self._writer is not None:
            self._writer.close()
            self._writer = None
