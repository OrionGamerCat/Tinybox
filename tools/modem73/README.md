# modem73 für Windows (headless)

[modem73](https://github.com/RFnexus/modem73) (RFnexus, Public Domain) ist ein OFDM-Soundkarten-Modem
mit KISS-TCP (8001) und JSON-Steuerport (8073). Hier liegt nur, was nötig ist, um das **aktuelle
Original** als `modem73.exe` für Windows zu bauen – ohne Terminal-Oberfläche, als KISS-Modem für
den kisshub. Der Quellcode von modem73 liegt nicht im Repo.

| Datei | Zweck |
|---|---|
| `modem73-win-oe3gas.patch` | Änderungen am Original (Unified Diff), damit es unter Windows kompiliert |
| `build-modem73-win.sh` | holt das Original, spielt den Patch ein, baut `modem73.exe` (statisch) |

## Was der Patch macht
- neue Datei `net_compat.hh`: Winsock statt BSD-Sockets (recv/send/accept/connect, Fehlercodes,
  nicht-blockierend, `WSAPoll`), `SO_EXCLUSIVEADDRUSE`, `%APPDATA%` statt `$HOME`;
  unter Linux bindet sie nur die POSIX-Header ein
- `serial_ptt.hh` wählt unter Windows die PTT über DTR/RTS aus
  [modem73-win](https://github.com/RFnexus/modem73-win) (`serial_ptt_win.hh`)
- in `kiss_tnc_impl.hh`, `control_port.hh`, `rigctl_ptt.hh` nur Include-Zeilen und
  `close()` → `sock_close()` für Sockets
- nicht enthalten: Terminal-UI, CM108-PTT, Hamlib (Einstellungen per Kommandozeile/`--config`)

## Bauen
Linux (Debian/Ubuntu): `sudo apt install g++-mingw-w64-x86-64-posix`, dann
`sh tools/modem73/build-modem73-win.sh` in einem Arbeitsordner.
Windows: MSYS2, Shell **MINGW64**, `pacman -S git patch mingw-w64-x86_64-gcc`, dann
`CC=gcc CXX=g++ sh build-modem73-win.sh`.

Neue Version des Originals: Skript erneut laufen lassen. Schlägt `patch` fehl, hat sich
upstream an den gepatchten Stellen etwas geändert – Patch nachziehen.

Getestet (1.11.2026, modem73 2.4.8): Build mit MinGW, Kurztest unter Wine (KISS-Frame
angenommen, CSMA, PTT, TX-Audio). Mit echter Soundkarte/Funkgerät noch offen.

## Betrieb mit dem kisshub

Der kisshub startet modem73 selbst: Profil `modem73`, Abschnitt `[modem73]` in der
`kisshub.conf`, Start `kisshub.bat -p modem73` – Beschreibung in MANUAL.md 3.5a. Die
Kommandozeile unten ist nur für einen Test von Hand.

## Start von Hand (Beispiel)
Direwolf vorher beenden (gleiche Soundkarte).
```
modem73.exe --list-audio
modem73.exe --headless -c OE3GAS -p 8011 --bind 127.0.0.1 ^
  -m QAM16 -r 1/2 --short --csma-band vhf ^
  --input-device "<Name>" --output-device "<Name>" ^
  --ptt com --com-port COM5 --com-line rts --tx-delay 300 --tx-level 60
```
Port 8011: 8001 ist der KISS-Port von Direwolf, 8101 der des kisshub. PACLEN + AX.25-Kopf
muss in die Nutzlast eines Rahmens passen (QAM16 1/2 short: 254 Byte), sonst schneidet
modem73 den Frame ab – mit dem Profil `modem73` achtet der kisshub darauf.
