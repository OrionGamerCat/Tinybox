"""kisshub - owns the KISS TNC and shares it over KISS-TCP (KISS step K7).

docs/kiss-mode-konzept.md section 4, PLANUNG.md section 15.

    TNC --serial/TCP-- kisshub --KISS-TCP 127.0.0.1:8001--+-- TinyBox
                                                          +-- brocastd

    profiles.py   how to wake each TNC and put it into KISS (PK-232, TM-D710, TNC7multi, ...)
    transport.py  serial port (pyserial, two threads) or TCP to the TNC
    tnc.py        wake + init dialog in terminal mode, then KISS framing
    hub.py        KISS-TCP server, clients, paced send queue with priorities
    console.py    commands in the kisshub window: LOG MARK/DEBUG/TRACE, TXDELAY, LINKS ...
    linkstats.py  passive AX.25 link quality per station pair (CR67) - any TNC
    varamon.py    VARA's command port, read only: PTT, BUSY, SN, alarms (CR67)
    modem73.py    modem73 (OFDM): mode table, [modem73], starts/stops the modem73 process
"""

VERSION = "2026.11.01.2"
