# TinyBox

**Eine kleine Packet-Radio-Mailbox (BBS) mit eigenem Client – damit Packet Radio wieder Spaß macht.**

TinyBox ist eine schlanke BBS für AX.25 Packet Radio, geschrieben in Python. Sie
läuft auf einem normalen Windows-PC neben [Direwolf](https://github.com/wb2osz/direwolf)
oder an einem KISS-TNC und bietet Post, Bulletins, Chat-Boards, Forwarding und eine
Sysop-Weboberfläche. Dazu gibt es den **TinyBox-Client** (`tbclient`): ein
Packet-Radio-Programm im Browser mit Chat, Mailbox (auch offline), Monitor und
Terminal – der Client funktioniert auch ganz ohne eigene TinyBox.

*English: TinyBox is a small AX.25 packet radio BBS (mail, bulletins, chat boards,
FBB-style forwarding, sysop web GUI) for Direwolf (AGW) or KISS TNCs, plus a
browser-based client. Documentation is in German; questions in English are welcome.*

## Was ist drin?

| Teil | Wofür |
|---|---|
| **TinyBox** | die Mailbox: Post, Bulletins, Chat (`C`), Forwarding (FBB/B1, mit LinBPQ getestet), Sysop-Konsole und Web-GUI |
| **TinyBox-Client** (`tbclient`) | für Benutzer: Chat, Mailbox mit Offline-Abgleich, bis 5 Verbindungen, Monitor, Terminal, Verbindungslogbuch (CSV/ADIF) – im Browser, auch am Handy |
| **kisshub** | teilt einen KISS-TNC (PK-232, TM-D710, Direwolf-KISS, VARA FM) zwischen mehreren Programmen und misst die Verbindungsqualität |
| **brocast** | kompaktes Seitenprotokoll (Wetter, Warnungen, Bilder) als UI-Frames |
| **dxfeed** | täglich eine DX-Zusammenfassung als Bulletin statt Live-Spots |

## Schnellstart

TinyBox läuft unter **Windows** und **Linux** (z. B. Debian, Ubuntu, Raspberry Pi OS).

1. **Python 3.10 oder neuer** installieren.
   - Windows: https://www.python.org, beim Installieren „Add python.exe to PATH“ anhaken.
   - Linux: meist schon da, prüfen mit `python3 --version`; sonst
     `sudo apt install python3`.
2. **TinyBox holen:** unter [Releases](https://github.com/oe3gas/Tinybox/releases)
   das ZIP der neuesten Version laden und entpacken – oder
   `git clone https://github.com/oe3gas/Tinybox.git`
3. **Konfiguration anlegen:** `tinybox.conf.example` nach `tinybox.conf` kopieren
   (für den Client: `tbclient.conf.example` nach `tbclient.conf`) und überall `OE3GAS` (das
   Rufzeichen des Autors) durch das eigene ersetzen. Die `.example`-Dateien erklären jeden Wert.
   Unter Linux: `cp tinybox.conf.example tinybox.conf` (bzw. `tbclient`).
4. **Starten:**
   - Windows: `tinybox.bat` bzw. `tbclient.bat` doppelklicken.
   - Linux: im TinyBox-Ordner im Terminal
     ```
     python3 -m tinybox -c tinybox.conf      # die Mailbox
     python3 -m tbclient -c tbclient.conf    # der Client
     ```
   Die Web-GUI des Clients: http://127.0.0.1:7744/
   Im Fenster des Clients zeigt `I` (oder `INFO`) den Startblock noch einmal, `H` die Hilfe.
5. **Ohne Funk ausprobieren:** per Telnet auf `127.0.0.1`, Port `6300` – unter
   Windows mit PuTTY, unter Linux mit `telnet 127.0.0.1 6300` (siehe unten).

Für TinyBox und den Client sind keine Zusatzpakete nötig. Nur kisshub (serieller
TNC: `pip install pyserial`) und brocast (`pip install -r brocast/requirements.txt`)
brauchen welche. Unter Debian/Ubuntu/Raspberry Pi OS gibt es sie auch als Pakete:
`sudo apt install python3-serial python3-cbor2 python3-yaml`.

**Linux-Hinweise**
- Die `.bat`-Dateien sind nur für Windows. Für Linux gibt es die Gegenstücke
  `tinybox.sh`, `tbclient.sh`, `kisshub.sh` und `brocast/brocastd.sh` – im Terminal
  starten, z. B. `./tbclient.sh`. Die Log-Ausgabe (Konsole) erscheint dort genauso
  wie im Windows-Fenster, beendet wird mit Strg+C. Alles andere startet man wie oben
  mit `python3 -m <programm> -c <programm>.conf` (`dxfeed` genauso, fwdsim mit
  `python3 -m fwdsim`, das Testbed mit `python3 -m tbtest`).
- Pfade in den Beispielen wie `C:\Tinybox` oder `data\` sind unter Linux einfach
  `~/Tinybox` bzw. `data/`.
- Direwolf: `sudo apt install direwolf`, Konfiguration wie unten bei „Mit Direwolf“.
- Serieller TNC (PK-232, TM-D710 über kisshub): in `kisshub.conf` bei `device`
  z. B. `/dev/ttyUSB0` eintragen und den eigenen Benutzer einmal in die Gruppe
  `dialout` aufnehmen: `sudo usermod -aG dialout $USER` (danach neu anmelden).
- `RESTART` in der Sysop-Konsole funktioniert auch unter Linux: TinyBox startet
  sich im selben Terminal selbst neu.
- VARA FM gibt es nur für Windows. Unter Linux die Betriebsarten mit Direwolf oder
  einem Hardware-TNC nutzen.
- dxfeed: Statt der Windows-Aufgabenplanung (`dxfeed_aufgabe_einrichten.bat`)
  übernehmen unter Linux `deploy/systemd/dxfeed.service` und `dxfeed-digest.timer`
  den Tagesablauf.
- Dauerbetrieb als Dienst: Fertige systemd-Units liegen in `deploy/systemd/`,
  die Installation beschreibt [`PRODUCTION.md`](PRODUCTION.md).

**Weiterlesen:** [`MANUAL.md`](MANUAL.md) – Handbuch mit allen Teilen, Konfiguration,
Betrieb mit Direwolf, KISS-TNC und VARA FM, Fehlersuche ·
[`tbclient/FEATURES.txt`](tbclient/FEATURES.txt) – was der Client kann ·
[`logging_manual.md`](logging_manual.md) – Log lesen ·
[`PLANUNG.md`](PLANUNG.md) – Entscheidungen und Ausblick ·
[`CHANGELOG.md`](CHANGELOG.md) – Versionen.

## Mitmachen und Kontakt

Rückmeldungen, Fehlerberichte und Ideen gerne als
[Issue](https://github.com/oe3gas/Tinybox/issues). Wer eine TinyBox in die Luft
bringt: Bescheid sagen, dann connecten wir uns!

73 de **OE3GAS** (Gerhard) und **OE3TEC** (Tobias)

## Lizenz

GNU General Public License v3.0 – siehe [`LICENSE`](LICENSE).

---

# Betrieb im Detail

## Voraussetzung

Python 3.10 oder neuer (https://www.python.org). Für M1 sind keine Zusatzpakete nötig.

## Starten

Windows: Doppelklick auf `tinybox.bat`, oder in der Eingabeaufforderung:

```
cd /d C:\Tinybox          (dein TinyBox-Ordner)
py -3 -m tinybox -c tinybox.conf
```

Linux:

```
cd ~/Tinybox              (dein TinyBox-Ordner)
python3 -m tinybox -c tinybox.conf
```

Beenden mit `SHUTDOWN` (verbundene Stationen werden 60 s vorher gewarnt) oder sofort mit `SHUTDOWN NOW` bzw. Ctrl+C. Die Daten liegen unter `data\` (Linux: `data/`).

## Log-Datei

In `tinybox.conf` unter `[logging]` einen vorhandenen Ordner bei `log_dir`
eintragen (z. B. `logs`). Leer = keine Log-Datei.

Dort entsteht **eine Datei pro Tag**, `tinybox-<Datum>.log`; ein Neustart hängt
an dieselbe Datei an, Dateien älter als `keep_days` (Standard 14) werden gelöscht.
Eine Zeile ist ein Ereignis, in festen Spalten:

```
2026-10-13 20:08:29.944 I session  #1 OE3TEC    < L
Zeit mit ms             |  Level  |  Komponente  |  #Session Call  |  Meldung
```

`<` ist Eingabe der Station, `>` Ausgabe der TinyBox, `<<` und `>>` sind
AGW-Frames; eine Zahl in Klammern ist eine Dauer. Die Session-Nummer steht in
jeder Zeile dieser Verbindung – `grep "#1"` liefert sie vollständig. Jeder Lauf
beginnt mit einem Block aus `-----`-Zeilen, der Version, Commit und die aktiven
Adapter nennt, und endet mit einer Schlusszeile samt Zählern. Die ersten drei
Zeilen jeder Datei sind eine Legende.

In der Sysop-Konsole:

| Befehl | Wirkung |
|---|---|
| `LOG` | Level, eingeschaltete Debug-Komponenten, Dateipfad und -größe |
| `LOG DEBUG agw` | zusätzliches DEBUG nur für eine Komponente, ohne Neustart |
| `LOG OFF [agw]` | zurück auf den normalen Level (ohne Namen: alle) |
| `LOG MARK Text` | Markenzeile ins Log – Marke setzen, Fehler auslösen, „ab der Marke“ |
| `LOG BUNDLE` | eine Datei mit Log, Version und Konfiguration (ohne Token) zum Weitergeben |

Dasselbe Paket ohne laufende TinyBox: `py -3 -m tinybox --debugbundle`.

**Vollständige Anleitung: `logging_manual.md`** – Einschalten, Zeilen lesen,
welche Komponente für welches Problem, Suchrezepte für Windows und der
Arbeitsablauf, um einen Fehler mit Claude zu debuggen.

## Ohne Funk testen (Telnet-Testport)

Windows mit PuTTY: Host `127.0.0.1`, Port `6300`, Connection type **Telnet**.
Linux: `telnet 127.0.0.1 6300` (falls nötig `sudo apt install telnet`).
Als Rufzeichen z. B. `OE1ABC` eingeben. Mit dem Sysop-Call aus `tinybox.conf` hast du Sysop-Rechte.

## Mit Direwolf

In `direwolf.conf`:

```
MYCALL OE3GAS          # Direwolf selbst; die Mailbox nutzt OE3GAS-1
AGWPORT 8000
```

Erst Direwolf starten, dann TinyBox. Die Reihenfolge ist nicht kritisch:
TinyBox versucht es alle `reconnect_sec` Sekunden erneut und verbindet sich
auch nach einem Direwolf-Neustart selbst wieder.

Im Log sollte stehen:

```
connected to Direwolf AGW 127.0.0.1:8000
Direwolf AGW version 1.x
mailbox call OE3GAS-1 registered with Direwolf
```

Danach von einer zweiten Station (oder einem zweiten Direwolf/TNC) `C OE3GAS-1` connecten.

## Sysop-Weboberfläche

Beim Start zeigt das TinyBox-Fenster den Login-Link:

```
  Web GUI login:  http://127.0.0.1:8080/login?token=...
```

Link im Browser öffnen (am besten als Lesezeichen speichern). Der Token liegt in
`data\web.token` und bleibt über Neustarts gleich. Neuer Token: Datei löschen und
TinyBox neu starten. Konsolenbefehl `WEB` zeigt den Link erneut.

Die Oberfläche ist nur am eigenen PC erreichbar (127.0.0.1). Einstellungen unter `[web]`.

## Sysop-Konsole

Im TinyBox-Fenster tippen. Es gelten alle Mailbox-Befehle mit Sysop-Rechten
(`L`, `R n`, `K n`, `E n ...`, `S call`, `SB ALL` ...), dazu:

| Befehl | Funktion |
|---|---|
| `INFO` | Startblock noch einmal: Version, Rufzeichen, Funkwerte, Adapter, Log, Config (nur `INFO` – `I` bleibt der Profil-Befehl der Mailbox) |
| `W` | Wer ist verbunden |
| `MON [ON\|OFF]` | Laufende Sitzungen mitlesen (ohne Argument: umschalten) |
| `DISC call` | Benutzer trennen (ohne SSID: alle SSIDs dieses Calls) |
| `STATUS` | Direwolf-Verbindung, Benutzer, Nachrichten |
| `WEB` | Login-Link der Weboberfläche anzeigen |
| `SHUTDOWN [s]` | TinyBox in s Sekunden beenden (Standard 60). Alle verbundenen Stationen bekommen sofort eine Systemnachricht, Erinnerung bei 30 und 10 s; wer sich in der Zeit anmeldet, wird beim Login gewarnt. Ist niemand verbunden, sofort |
| `SHUTDOWN NOW` | Sofort beenden (Benutzer werden verabschiedet) |
| `SHUTDOWN CANCEL` | Angekündigten Shutdown absagen, die Stationen werden informiert |
| `RESTART [s]` | TinyBox neu starten, z. B. nach einer Änderung in `tinybox.conf` oder einem `git pull`. Prüft zuerst `tinybox.conf` – bei einem Fehler wird nicht neu gestartet. Warnung an die Stationen wie bei `SHUTDOWN` (Standard 60 s, `NOW`, `CANCEL`). Mit `tinybox.bat` / `tinybox_dauerbetrieb.bat` startet TinyBox im selben Fenster sofort wieder |
| `RELOAD` | `tinybox.conf` neu einlesen, **ohne** jemanden zu trennen (CR82). Übernimmt nur, was im laufenden Betrieb geht (Mailbox-Werte, Bake, Log-Level, Rubriken, neue/geänderte Chat-Boards und MOTD, brocast, Forward-Partner …) und listet danach die geänderten Werte und die ignorierten, die einen `RESTART` brauchen (Rufzeichen, Funk/AGW/KISS, Ports, Adapter ein/aus, gelöschte Boards). Bei einem Fehler in der Datei wird nichts geändert. In der Sysop-Web-GUI: Knopf **Reload** |

Nachricht beenden mit `/EX`. Log-Meldungen und Monitor erscheinen
zwischen den Eingaben – das ist normal.

## Chat

Eingeloggte Benutzer (Funk, Telnet) wechseln mit `C` in den Chat: `C` zeigt die
Boards, `C TREFF` oder `C 1` betritt eines. Dort ist jede Zeile Chat-Text,
Befehle beginnen mit `/`: `/Q` (oder `/EX`, `^Z`) zurück zur Mailbox, `/W` wer ist
da, `/L` Boards, `/J board` wechseln, `/H` Hilfe.

Die Boards legt der Sysop in `tinybox.conf` unter `[chat_boards]` fest
(`NAME = Aufbewahrung Beschreibung`):

```
[chat_boards]
TREFF = 7d    General meeting point
DX    = 24h   DX spots and news
RUNDE = live  Live round, nothing is stored
```

`live` = nichts wird gespeichert, nur wer gerade im Board ist, liest mit.
`12h`/`7d` = Verlauf so lange aufbewahren. Beim Betreten zeigt TinyBox nur,
wie viele Zeilen gespeichert sind; lesen mit `/H n` (höchstens `history_lines`
Zeilen pro Abruf, `[chat]`). Der Client holt die History selbst (nur verpasste
Zeilen oder auf Knopfdruck). Ältere Zeilen löscht TinyBox automatisch. Im Chat gilt kein Idle-Timeout (Mitlesen ist erlaubt), zurück in
der Mailbox wieder `idle_timeout_min`. Änderungen an den Boards wirken nach einem Neustart. Konsole (`W`)
und Weboberfläche zeigen, wer in welchem Board ist; mitchatten nur über die Mailbox.

## DX-Zusammenfassung (dxfeed)

Sammelt die Spots eines DX-Clusters und legt alle 3 Stunden eine
Zusammenfassung der letzten 24 Stunden als zwei Bulletins an **DX** in den
Eingangsordner (gleitend, sie ersetzen sich): „DX-Zusammenfassung“ (Stationen, nach Relevanz A/B/C aus Club
Log Most Wanted und Spotterzahl) und „DX-Bandaktivitaet“. Nur lokal, keine
Live-Spots über Funk. Beide tragen eine brocast-Seite `dxsum` (Dictionary v4),
die der Listener als Band/Mode-Raster bzw. Heatmap zeigt (`PLANUNG.md`, Abschnitt 16).

1. `dxfeed.conf.example` nach `dxfeed.conf` kopieren, unter `[cluster]` das
   Rufzeichen bei `login` eintragen. Hat `tinybox.conf` einen Abschnitt
   `[rubrics]`, dort `DX = DX news` als angenommene Rubrik eintragen.
2. `start_alles.bat` startet den Sammler mit (Fenster `[dxfeed]`), einzeln:
   `dxfeed_dauerbetrieb.bat`. Die Ländertabelle `cty.dat` holt er selbst.
3. Einmal `dxfeed_aufgabe_einrichten.bat` ausführen: Aufgabe 05:00 in der
   Aufgabenplanung (Ordner *TinyBox*).

Dazu alle 10 Minuten `dxfeed live`: „DX jetzt“ (letzte 2 Stunden), „Bänder jetzt“
(letzte Stunde nach Kontinent) und „Neu auf dem Band“ (seltenes DX), jeweils als eigenes,
sich selbst ersetzendes Bulletin, das nach 1½–2 Stunden ausläuft (`[live]` in `dxfeed.conf`).
`dxfeed_aufgabe_einrichten.bat` legt beide Aufgaben an (bei schon eingerichteter Aufgabe einfach
nochmals ausführen).

Prüfen: `dxfeed status` (auch Most-Wanted-Liste und DXCC-Liste), `dxfeed live` (zeigt alles
nur an), `dxfeed show`,
`dxfeed digest` (zeigt beide Bulletins nur an). Most-Wanted-Liste sofort holen:
`dxfeed mw-update`. Meldungen in `logs\dxfeed.log`.

## Tests

Windows: Doppelklick auf `runtests.bat`. Linux:
`python3 -m unittest discover -s tests -t .`

## Stand

- M1 (lokale Mailbox + Telnet): fertig
- M2 (Direwolf über AGW): fertig, Funktest erfolgreich
- M3 (Sysop-Konsole, Monitor): fertig
- M3b (Sysop-Weboberfläche): fertig
- M3c–M3f (DICT, brocast-Anbindung, Eingangsordner, Kopfzeile Brocast:): fertig
- Chat-Boards (Befehl C): fertig
- Forwarding (optionales Modul): F1–F5 fertig (Empfangen, Senden, B1 komprimiert, Zeitplan, HOLD/REL), mit LinBPQ getestet; als Nächstes F6 (Anschluss ans Netz)
- M4 (Limits, Rate-Limit, Dauerbetrieb): offen
- DX-Zusammenfassung (dxfeed): umgesetzt – Sammler, Tages-Digest an DX um 05:00
- TinyBox-Client (C0–C3): umgesetzt – Post-Hinweis, Chat per UI-Broadcast, Offline-Mailbox mit Abgleich (`tbclient.bat`)

Details und Meilensteine: `PLANUNG.md` (Rev. 4).
