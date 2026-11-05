# KISS-Mode für TinyBox – Konzept

Stand: 14.10.2026 (3. Fassung) · Status: **entschieden, bereit für K1**

## 0. Entscheidungen (14.10.2026)

| # | Frage | Entscheidung |
|---|---|---|
| 1 | Welche TNCs? | PK-232, TNC2, Kenwood TH-D74/TH-D75, TM-D710 (Abschnitt 5); **Schwerpunkt PK-232 und Kenwood**, TNC2 nur der Vollständigkeit halber |
| 2 | Hub in der TinyBox oder eigener Prozess? | **eigener Prozess `kisshub`** (Variante B, Abschnitt 4) |
| 3 | Plattform | Windows (PC2) **und Raspberry Pi**; NanoPi nicht als Ziel |
| 4 | AX.25-Umfang | **gleich v2.2** (Modulo 128, SREJ, XID), mit Rückfall auf v2.0 |
| 5 | Digipeater/APRS von Direwolf | wird nicht genutzt → im KISS-Mode nichts zu ersetzen |
| 6 | Sprache des Layer-2-Automaten | **Python** (Abschnitt 7) |
| 7 | TNC2 | nur mit **reinem KISS-EPROM** (sofort in KISS, keine Init-Zeilen) |
| 8 | Erstes Gerät im Funktest | **PK-232** |
| 9 | Funktests | **nur VHF, 1200 Bd** (beim PK-232 der VHF-Port) |

## 1. Ziel

TinyBox soll wahlweise ohne Direwolf direkt an einem **KISS-tauglichen TNC**
laufen. Alles oberhalb der Verbindung – Sitzungen, Befehle, Chat,
TBCHAT-UI-Frames, Client-Abgleich, Forwarding, Verbindungsqualität – bleibt
unverändert. Umschaltung nur über die `tinybox.conf`:

```ini
[radio]
interface = agw          ; agw = wie bisher über Direwolf, kiss = KISS-Adapter
```

## 2. Der entscheidende Unterschied

| | AGW (heute) | KISS (neu) |
|---|---|---|
| Wer macht AX.25 Connected Mode? | Direwolf | **TinyBox selbst** |
| Was geht über die Schnittstelle? | fertige Verbindungen (`C`, `D`, `d`, `Y`) | rohe AX.25-Frames (SABM(E), UA, I, RR, REJ, SREJ, XID, DISC …) |
| Quittungen, Wiederholungen, Timer | Direwolf | TinyBox |
| Flusskontrolle | Abfrage `Y` alle 0,5 s | direkt bekannt (V(S) − V(A)) |
| Verbindungsqualität | nur mit Direwolf-Fork (`Q`) | **eingebaut**, ohne Fork |
| Rufzeichenfilter | Direwolf (`X`-Registrierung) | TinyBox |
| Kanalzugriff (CSMA, TXDELAY, P, SlotTime) | Direwolf | TNC (TinyBox setzt nur die Parameter) |

Ein KISS-TNC ist nur ein Modem mit HDLC-Rahmung. Den AX.25-Sicherungsschicht-
Automaten („Data Link State Machine“) bringt TinyBox selbst mit – das ist der
Kern und der größte Aufwand.

## 3. Architektur

```
 ┌──────────────────────────────────────────────────────────────────┐
 │ Session · Chat · Forward · Client-Sync · Sysop · Web (unverändert) │
 └───────────────┬──────────────────────────────────────────────────┘
                 │ Transport (write / write_bytes / close / abort_output)
                 │ + LinkAdapter (connect, send_ui, ask_quality …)
       ┌─────────┴──────────┐
 ┌─────▼──────┐   ┌─────────▼────────────────────────────────────┐
 │ AgwAdapter │   │ KissAdapter                                   │
 │ (heute)    │   │  Ax25Link (pro Verbindung, Layer-2-Automat)   │
 └─────┬──────┘   │  UI-Dienst (TBCHAT-n)                         │
       │          │  Frame-Router (Rufzeichen-/Pfadfilter)        │
       │          └─────────┬────────────────────────────────────┘
       │                    │ KISS (TCP oder seriell – je nach Hub-Variante)
       ▼                    ▼
   Direwolf          KISS-Hub ──▶ TNC (seriell / USB / Bluetooth-SPP)
                        └──────▶ brocastd (KISS-TCP, unverändert)
```

### 3.1 Gemeinsame Schnittstelle (`LinkAdapter`)

Heute greifen `forward.py`, `web.py`, `sysop.py` und der Chat direkt auf
`app.agw` zu. Diese Zugriffe werden zu einer kleinen Schnittstelle
zusammengefasst, die beide Adapter erfüllen:

| Element | Zweck | Heute genutzt von |
|---|---|---|
| `run()` | Hauptschleife inkl. Reconnect | `__main__` |
| `connected` (Event) | Schnittstelle oben? | Web, Sysop, Forward |
| `conns` | aktive Verbindungen | Web, Qualität |
| `connect(remote, attach, via, timeout)` | ausgehender Connect | Forward |
| `send_ui(dest, text)` | UI-Frame senden | Chat (TBCHAT-n) |
| `ask_quality(remote)` / `q_supported` | Verbindungsqualität | Chat, Web |
| `describe()` | Text für STATUS/Web („AGW 127.0.0.1:8000“ bzw. „KISS TM-D710 COM3“) | Sysop, Web |

`app.agw` wird zu `app.link` (mit Übergangs-Alias). Die Verbindungsobjekte
erfüllen weiter das bestehende `Transport`-Protokoll aus `session.py`.

### 3.2 Neue Module

```
tinybox/
  adapters/kiss.py   KissAdapter + KissConnection (Gegenstück zu agw.py)
  ax25/
    frame.py         AX.25-Codec: I, S (RR/RNR/REJ/SREJ), U (SABM/SABME/UA/DM/DISC/FRMR/UI/XID/TEST)
    link.py          Ax25Link: Layer-2-Automat für EINE Verbindung (rein, ohne I/O)
    timers.py        T1 (mit SRT-Schätzung), T2, T3
    xid.py           XID-Aushandlung (v2.2-Parameter)
    kissio.py        KISS-Rahmung, Parameterbefehle, seriell + TCP
kisshub/             nur bei Hub-Variante B (Abschnitt 4)
```

Basis: `brocast/brocast/kiss.py` (KISS-Codec, TCP-Link) und
`brocast/brocast/ax25.py` (Adressen, UI-Frames) sind getestet und werden
übernommen und erweitert.

### 3.3 Frame-Router

Direwolf filtert heute über die `X`-Registrierung. Im KISS-Mode sieht die
TinyBox **jeden** Frame auf der Frequenz und entscheidet selbst:

| Frame | Ziel | Aktion |
|---|---|---|
| beliebig | nicht Mailbox-Call, keine laufende Verbindung | ignorieren (nur Monitor) |
| Pfad mit Digis, noch nicht alle H-Bits gesetzt | – | ignorieren (Frame noch unterwegs) |
| SABM / SABME | Mailbox-Call | neue `Ax25Link` → `_on_connect()` wie heute |
| I / S / U | Mailbox-Call, bekannte Verbindung | an deren `Ax25Link` |
| I / S / DISC | Mailbox-Call, unbekannt | DM zurück |
| UI an TBCHAT-n / Mailbox-Call | – | an Chat-/Client-Logik |

Rückweg bei Connects über Digis: Pfad umgedreht, H-Bits gelöscht.

### 3.4 Layer-2-Automat (`Ax25Link`) – AX.25 v2.2

Umsetzung nach der Zustandsbeschreibung (SDL) der AX.25-2.2-Spezifikation
(Rev. 2017). Direwolfs `ax25_link.c` setzt dieselbe SDL um und dient als
Referenz zum Verständnis und für Interop-Tests.

- Zustände: *Disconnected*, *Awaiting Connection*, *Awaiting v2.2 Connection*,
  *Connected*, *Timer Recovery*, *Awaiting Release*.
- **v2.2:** SABME → Modulo 128, Fenster k bis 127 (praktisch 7–32), **SREJ**
  (nur Fehlendes wird wiederholt), **XID** für PACLEN (N1), Fenster (k),
  T1/N2 und Halb-/Vollduplex.
- **Rückfall auf v2.0 ist Pflicht, nicht Option:** Die eingebauten TNCs der
  PK-232, TNC2 und der Kenwood-Geräte sprechen nur v2.0. Ablauf:
  - Gegenstation sendet SABME → v2.2.
  - Gegenstation sendet SABM → v2.0 (Modulo 8, REJ statt SREJ).
  - TinyBox ruft aus (Forwarding): erst SABME; kommt DM oder FRMR → SABM.
  - Merken pro Rufzeichen, was die Gegenstation kann (spart beim nächsten
    Mal den Fehlversuch).
- Empfangsseitig RNR, wenn die Session nicht nachkommt.
- Timer: **T1** dynamisch aus der Umlaufzeit (SRT), Startwert pro
  Digipeater-Hop erhöht; **T2** sammelt Quittungen (ein RR für mehrere
  I-Frames); **T3** Leerlauf-Polling; **N2** max. Wiederholungen.
- Callbacks wie heute die AGW-Ereignisse: `on_connected` (= `C`),
  `on_data` (= `D`), `on_disconnected(reason)` (= `d`, „RETRYOUT“ →
  `lost=True`).
- Der Automat hat **kein eigenes I/O und keine eigene Uhr**: Er bekommt
  Frames und Zeitpunkte, er gibt Frames und Timer-Wünsche zurück. Dadurch
  ist er ohne Funk und Netzwerk testbar (Simulator mit Paketverlust) – und
  ließe sich später isoliert in eine andere Sprache übertragen (Abschnitt 7).

**Erkenntnisse aus dem Simulator (K2, 14.10.2026):**

- **T1 und eigene Sendezeit:** Ein KISS-TNC meldet nicht, wann ein Frame wirklich
  gesendet ist. Bei 1200 Bd brauchen vier 128-Byte-Frames über 5 s. Der Automat
  schätzt deshalb seine eigene Sendezeit (`air_baud`, `txdelay`) und startet T1
  erst ab dem geschätzten Ende des ganzen Blocks.
- **T1 pausiert bei belegtem Kanal:** Jeder gehörte Frame schiebt T1 um seine
  Sendezeit hinaus (halbduplex – solange jemand sendet, kann die Quittung nicht
  kommen). Für Frames der eigenen Verbindung macht das der Automat selbst, für
  fremde Frames auf der Frequenz meldet es der KISS-Adapter (`channel_busy`).
- **T2 startet bei jedem I-Frame neu:** Quittiert wird erst, wenn der Block der
  Gegenstation vorbei ist – ein RR für das ganze Fenster.
- **Timer Recovery:** Solange die Antwort (F=1) auf die eigene Abfrage aussteht,
  werden keine neuen I-Frames gesendet; sonst gehen sie doppelt raus.
- **REJ (v2.0) gegen SREJ (v2.2), K3:** 4000 Byte, je 20 Läufe, Standardwerte
  (k = 4 bzw. 7, 1200 Bd, TXDELAY 300 ms):

  | Verlust | v2.0 neue Bytes | v2.0 Nutzrate | v2.2 neue Bytes | v2.2 Nutzrate |
  |---|---|---|---|---|
  | 5 % | 83 % | 465 bit/s | 90 % | 564 bit/s |
  | 10 % | 72 % | 379 bit/s | 80 % | 458 bit/s |
  | 20 % | 53 % | 159 bit/s | 61 % | 223 bit/s |
  | 30 % | 39 % | 67 bit/s | 44 % | 88 bit/s |

  v2.2 ist damit rund 20–40 % schneller. Ab etwa 40 % Verlust brechen
  Verbindungen in beiden Versionen nach N2 Abfragen ordentlich ab (`retryout`)
  – dort muss Abfrage *und* Antwort durchkommen.
- **XID-Bitwerte:** nach Direwolfs `xid.c` übernommen; im Interop-Test gegen
  Direwolf (K4) zu bestätigen.
- **Fenster bei v2.2:** Standard `maxframe_ext = 7`. Größere Fenster lohnen erst
  bei 9600 Bd – bei 1200 Bd belegen 7 Frames den Kanal schon rund 9 s.

**Fehler aus dem PK-232-Funktest (14.10.2026):** Eine Sitzung schreibt ihre
Antwort in Stücken (Kopfzeile `//PART …`, dann die Daten). T1 startete nach dem
ersten, kurzen Frame und wurde nicht verlängert, als der Rest des Blocks folgte –
jede längere Antwort löste eine T1-Abfrage aus, obwohl nichts verloren war
(18 T1-Abläufe bei 0 % Verlust, Balken auf 0). Behoben: Kommen Frames zu einem
laufenden Block hinzu, läuft T1 ab dessen neuem geschätztem Ende. Der Mitschnitt
zeigte zugleich, dass die Sendezeit-Schätzung stimmt (Quittung 1,9 s nach dem
geschätzten Blockende).

### 3.5 Flusskontrolle

`KissConnection.pump()` wartet auf das Ereignis „Fenster frei“ des Automaten
statt alle 0,5 s per `Y` zu fragen. `_drain_and_disconnect()` wartet, bis
alles quittiert ist, und sendet dann DISC.

### 3.6 Verbindungsqualität ohne Fork

Der Automat führt dieselben Zähler wie der Direwolf-Fork (`i_new`,
`i_retry`, `bytes_new`, `bytes_retry`, `i_rx`, `retry_rx`, `rej_rx`,
`rej_tx`, `t1_exp`, `rnr_rx`, `srt`, `t1v`, `unack`, `bytes_rx`,
`tx_busy_ms`, `baud`), zusätzlich `srej_rx`/`srej_tx`. `ask_quality()`
liefert sie direkt im Format von `linkq.parse()`. Balken, `%Q` und `stat`
funktionieren unverändert, `q_supported` ist immer `True`.
`tx_busy_ms` wird aus Funk-Baudrate (conf) und gesendeten Bytes geschätzt –
ein KISS-TNC meldet keine Sendezeit.

## 4. KISS-Hub: in der TinyBox oder eigener Prozess?

**Das Problem:** Ein serieller Port (COM3, `/dev/ttyUSB0`, Bluetooth-SPP)
kann nur von **einem** Programm geöffnet werden. Am TNC wollen aber TinyBox
**und** brocastd hängen. Einer muss den Port besitzen und für den anderen
verteilen.

### Variante A – Hub in der TinyBox

```
TNC ──seriell── TinyBox [Hub + Layer 2] ──KISS-TCP :8001── brocastd
```

Die TinyBox öffnet den TNC selbst und bietet brocastd einen KISS-TCP-Port an.

### Variante B – eigener Hub-Prozess `kisshub`

```
TNC ──seriell── kisshub ──KISS-TCP :8001──┬── TinyBox [Layer 2]
                                          └── brocastd
```

Ein kleines, eigenständiges Programm (geschätzt 300–400 Zeilen) besitzt den
TNC, initialisiert ihn und verteilt die Frames an alle KISS-TCP-Teilnehmer.
TinyBox und brocastd sind beide nur KISS-TCP-Clients.

### Gegenüberstellung

| Kriterium | A: Hub in TinyBox | B: eigener `kisshub` |
|---|---|---|
| Prozesse / Start | einer weniger, einfacher zu starten | ein Prozess mehr (Startskript, Dienst auf dem Raspi) |
| TinyBox-Neustart (`git pull`, Update, Absturz) | **TNC weg für alle** – brocastd sendet nicht, der TNC wird bei jedem Start neu initialisiert (PK-232/D710: `KISS ON` + `RESTART`) | TNC bleibt offen, brocastd sendet weiter, TinyBox verbindet sich einfach neu |
| Fehlerisolierung | ein Fehler in Chat/Forward/Web kann den Funkzugang mitreißen | Hub ist klein und ändert sich selten → sehr stabil |
| Code in der TinyBox | seriell **und** TCP, TNC-Init, Server | **nur KISS-TCP** – derselbe Code wie gegen Direwolfs KISS-Port |
| Test ohne Hardware | eigene Testumgebung für den seriellen Teil | TinyBox gegen Direwolf-KISS-Port = exakt wie gegen den Hub |
| TNC-Eigenheiten (Init, Exit, Port-Wahl, Bluetooth-Abbrüche) | in der TinyBox | gekapselt im Hub, TinyBox weiß nichts davon |
| Latenz | direkt | + einmal localhost-TCP (< 1 ms, bei 1200 Bd belanglos) |
| Priorität (Quittungen vor brocast-Seiten) | einfach, alles in einem Prozess | Hub muss das Steuerbyte lesen und sortieren – einfach, AX.25-Control ist ein Byte |
| Weitere Abnehmer (Monitor, Paket-Dekoder, APRS-Tool) | über den TCP-Port | über den TCP-Port |
| Wiederverwendung | nur mit TinyBox | jedes KISS-Programm (auch ohne TinyBox) |
| Konfiguration | alles in `tinybox.conf` | eigene `kisshub.conf` (TNC-Typ, Port, Parameter) |

**Entschieden: Variante B** (14.10.2026). Ausschlaggebend sind drei Punkte:

1. TinyBox wird laufend weiterentwickelt und oft neu gestartet. Mit A hängt
   jedes Mal der Funkzugang samt brocastd mit, und die Kenwood-/PK-232-TNCs
   müssen jedes Mal neu in KISS geschaltet werden.
2. Die TinyBox kennt nur **eine** Art TNC: KISS über TCP. Ob dahinter der
   Hub mit PK-232 oder Direwolfs KISS-Port steckt, ist ihr gleich. Das
   halbiert den Testaufwand.
3. Alles Gerätespezifische (Init-Sequenzen, Bluetooth-Abbrüche beim TH-D74/75,
   USB-Wackler) bleibt in einem kleinen Programm, das selten angefasst wird.

Der Preis ist ein zusätzlicher Prozess – auf PC2 eine Zeile in
`start_alles.bat`, auf dem Raspi ein systemd-Dienst.

### Exkurs: Linux-Kernel-AX.25 (`kissattach`)

Auf dem Raspi gäbe es noch den AX.25-Stack im Linux-Kernel. Er scheidet aus:
nicht unter Windows, kein vollständiges v2.2, keine Qualitätszähler, und die
TinyBox müsste zwei völlig verschiedene Wege pflegen.

### Aufgaben des Hubs (Variante B)

- TNC öffnen (seriell / USB / Bluetooth-SPP), bei Verlust selbst neu öffnen
  und neu initialisieren.
- Geräteprofil anwenden: Init-Sequenz, KISS-Parameter, Exit beim Beenden.
- Jeden empfangenen Frame an alle TCP-Teilnehmer verteilen.
- Sendewarteschlange mit Priorität: U/S-Frames (UA, DM, RR, RNR, REJ, SREJ)
  vor I-Frames vor UI-Frames. Eine Quittung wartet nie hinter einer langen
  brocast-Seite.
- Eigene gesendete Frames an die **anderen** Teilnehmer spiegeln (wie ein
  Monitor) – brocastd und der Monitor sehen dann auch, was die TinyBox sendet.
- Status für Sysop/Web: TNC verbunden?, Frames rx/tx, Warteschlange.

## 5. Die vorgesehenen TNCs

| Gerät | Anschluss | In KISS schalten | KISS verlassen | Besonderheiten |
|---|---|---|---|---|
| **PK-232 / PK-232MBX** (AEA/Timewave) | RS-232 | Terminal: `KISS ON`, dann `RESTART` | `C0 FF C0` | zwei Funkports (HF/VHF): Port vor dem Umschalten wählen, im Test prüfen; Firmware-Stand prüfen |
| **TNC2** (bzw. Nachbauten) – nur der Vollständigkeit halber | RS-232 | **reines KISS-EPROM vorausgesetzt**: TNC ist nach dem Einschalten sofort in KISS, keine Init-Zeilen | – | andere EPROMs (TAPR mit `KISS ON`, TheFirmware/Hostmode) werden nicht unterstützt |
| **Kenwood TM-D710** | COM-Buchse am Bedienteil (PG-5G), 9600 Bd (bei Gerhard COM7) | TNC-Taste bis PACKET (nicht APRS), dann Terminal: `HBAUD 1200` + `KISS ON` + `RESTART` – von Gerhard am Gerät geprüft (22.10.2026) | `C0 FF C0`, dann `KISS OFF` | 1200/9600 Bd; Datenband A/B im Menü; kleiner Puffer → PACLEN/Fenster vorsichtig |
| **TNC7multi** (IfD Güttner) – ergänzt 29.10.2026 | USB (FTDI, virtueller COM, 115200 Bd) oder RS232 mit Nullmodemkabel (38400 Bd) | Drehschalter **1k2** bzw. **9k6** = KISS/SMACK ab dem Einschalten, keine Init-Zeilen | nur durch Neustart (Schalter) | SMACK (KISS mit CRC-16), kisshub sendet mit CRC; Modulationsspannung nur im Conf-Modus |
| **Kenwood TH-D74** | USB (virtueller COM) oder Bluetooth-SPP | im Gerätemenü KISS-Mode einschalten (keine Init-Zeilen) | Menü | 1200/9600 Bd; Datenband im Menü; Bluetooth-Abbrüche → Hub muss neu verbinden |
| **Kenwood TH-D75** | USB oder Bluetooth-SPP | wie TH-D74, Menü | Menü | Firmware-Stand prüfen (KISS-Verhalten über USB) |

Alle fünf sprechen **nur AX.25 v2.0** – v2.2 bringt nur etwas, wenn auf der
Gegenseite ebenfalls ein v2.2-fähiges System läuft (Direwolf, ein zweiter
TinyBox-KISS-Mode, ggf. LinBPQ). Gegen Terminalbenutzer mit diesen TNCs
greift immer der v2.0-Rückfall.

Die Tabelle beruht auf den Handbüchern bzw. bekannten Abläufen; Details
(Port-Wahl beim PK-232, Puffergrößen der Kenwood-TNCs, Verhalten von
TXDELAY-Befehlen im Kenwood-KISS) werden im Funktest je Gerät bestätigt und
dann als **Geräteprofil** im Hub abgelegt. (Seit kisshub 2026.11.05 steht jedes
Geräteprofil vollständig als eigener Abschnitt in der `kisshub.conf`, z. B. `[pk232]` –
MANUAL.md 2.4. Der Entwurf unten ist der Stand vom 14.10.2026.)

```ini
; kisshub.conf (Variante B)
[tnc]
profile = pk232              ; pk232 | tm-d710 | th-d74 | th-d75 | tnc2-kiss | generic
device = COM3                ; Raspi: /dev/ttyUSB0, Bluetooth: /dev/rfcomm0
serial_baud = 9600
channel = 0
air_baud = 1200
txdelay_ms = 300
persist = 63
slottime_ms = 100
exit_kiss_on_stop = no

[server]
listen = 127.0.0.1
port = 8001
```

```ini
; tinybox.conf
[radio]
interface = kiss

[kiss]
host = 127.0.0.1             ; kisshub oder Direwolf-KISS-Port
port = 8001
air_baud = 1200

[ax25]
version = 2.2                ; 2.2 = SABME versuchen, Rückfall 2.0
paclen = 128
maxframe = 4                 ; v2.0 (Modulo 8)
maxframe_ext = 7             ; v2.2 (Modulo 128); bei 1200 Bd reichen 7
t1_min_sec = 3
t1_max_sec = 30
t2_sec = 1.5
t3_sec = 300
n2 = 10
```

## 6. Plattform

- **Windows (PC2)** und **Raspberry Pi**. Seriell über `pyserial`, auf dem
  Raspi auch `/dev/rfcomm0` für Bluetooth-SPP der TH-D74/75.
- Rechenlast: Bei 1200 Bd kommen höchstens rund 5 Frames pro Sekunde über
  den Kanal, bei 9600 Bd rund 40. Ein Python-Automat braucht pro Frame
  Mikrosekunden – die CPU-Last bleibt auf dem Raspi im Promille-Bereich.
  Auch ein NanoPi wäre dafür **nicht** zu schwach; dessen Engpass war der
  eMMC-Verschleiß (PLANUNG.md, offener Punkt 9), nicht die Rechenleistung.

## 7. Sprache: Python oder C?

Frage: Sollte der Layer-2-Automat aus Gründen der Performance und
Verlässlichkeit in C geschrieben werden?

**Entschieden: Python** (14.10.2026), mit sauber abgekapseltem Automaten.

| Kriterium | C | Python |
|---|---|---|
| Performance | weit mehr als nötig | ausreichend mit großem Abstand: Timer im Sekundenbereich, asyncio-Jitter im Millisekundenbereich, ≤ 40 Frames/s |
| Speichersicherheit | Frames kommen **ungeprüft aus der Luft** (fremde Eingabe) – jeder Längen-/Indexfehler kann zu Pufferüberlauf, Absturz oder schlimmer führen | Längen-/Indexfehler werden zur Ausnahme, die pro Frame abgefangen wird (wie heute im AGW-Adapter) |
| Verlässlichkeit | hängt an der Korrektheit des Automaten, nicht an der Sprache | dto. – erreicht durch Spezifikation + Simulator-Tests |
| Testbarkeit | eigenes Testgerüst, Anbindung an pytest über Bindings | direkt im bestehenden pytest-Bestand, Simulator mit Paketverlust in wenigen Zeilen |
| Einbindung | Build für Windows **und** Raspi (ARM), Python-Bindings (ctypes/cffi), Compiler auf beiden PCs | keine – `git pull` genügt wie bisher |
| Pflege / Lernen | zweite Sprache im Projekt | eine Sprache für alles |
| Fehlersuche | Debugger, Speicherfehler schwer zu finden | Log + Traceback, wie im übrigen Code |

Wo C wirklich angebracht wäre: im Betriebssystemkern, auf einem
Mikrocontroller (z. B. ein eigener TNC) oder bei Baudraten weit jenseits
dessen, was im Amateurfunk-Packet üblich ist. Nichts davon trifft hier zu.

**Sicherheitsnetz:** Der Automat ist rein (Abschnitt 3.4: keine Uhr, kein
I/O). Sollte sich je herausstellen, dass er schneller sein muss, lässt er
sich als Ganzes übertragen – dann eher nach **Rust** als nach C, weil Rust
die Speichersicherheit behält. Der Python-Simulator prüft dann beide
Fassungen gegen dieselben Testfälle.

## 8. Umsetzung in Schritten

| # | Inhalt | Prüfung |
|---|---|---|
| K1 ✅ | AX.25-Codec (alle Frame-Typen, Modulo 8 und 128), KISS-I/O – `tinybox/ax25/frame.py`, `kissio.py` (14.10.2026) | 31 Unit-Tests inkl. von Hand gerechneter Bytes und 5000 Zufalls-/Müll-Frames; UI-Frames byte-gleich mit brocast; Mitschnitte von Direwolf folgen bei K2 |
| K2 ✅ | `Ax25Link` v2.0 (SABM → Sitzung → DISC, auch ausgehend), REJ, RR/RNR, T1/T2/T3, N2 – `tinybox/ax25/link.py`, Simulator `tests/ax25sim.py` (14.10.2026) | 23 Tests; Stresstest 100 Zufallskanäle 5–40 % Verlust, k 1–7: alle Daten vollständig und in Reihenfolge |
| K3 ✅ | v2.2: SABME, Modulo 128, SREJ, XID (mit Wiederholung), Rückfall-Logik – `tinybox/ax25/xid.py`, `link.py` (14.10.2026) | 20 neue Tests; Stresstest 150 Zufallskanäle, Versionen gemischt, 5–40 % Verlust: alle Daten vollständig |
| K4 ✅ | `KissAdapter` (`tinybox/adapters/kiss.py`) als zweiter Adapter neben AGW, Router, UI für TBCHAT, ausgehende Connects inkl. via, Qualität aus dem eigenen Link (14.10.2026) | 16 Tests Ende-zu-Ende mit echter Gegenstation (v2.0/v2.2, 20 % Verlust); alle AGW-Tests unverändert grün |
| K5 ✅ | ausgehende Connects inkl. via (Forwarding), Merken der Gegenstations-Version | Forward gegen LinBPQ und Direwolf – Tests laut Gerhard erfolgreich (14.10.2026) |
| K6 ⏸ | Qualitätszähler aus dem Automaten | Balken wie mit Fork – ruht (15.10.2026), Funktest steht aus |
| K7 ✅ | `kisshub` (eigener Prozess): Geräteprofile, Weck-/Init-Dialog, KISS-TCP-Server, Sendewarteschlange mit Prioritäten, Spiegeln an andere Clients (14.10.2026) | 13 Tests mit simuliertem PK-232 (alle Ausgangszustände), Ende-zu-Ende TinyBox → kisshub → PK-232 → Station |
| K8 ⏸ | Geräteprofil + Funktest **PK-232** (erstes Gerät) | Erster Funktest erfolgreich (14.10.2026, Gerät A, Firmware Release 13.SEP.95); Dauerlauf und Raspi ruhen (15.10.2026) |
| K9 | Geräteprofile + Funktest TM-D710, TH-D74, TH-D75 | **TM-D710:** Profil `tm-d710` auf die am Gerät geprüften Befehle umgestellt (kisshub 2026.10.22, 4 Tests mit simuliertem D710), Funktest steht aus; TH-D74/D75 ruhen, Zugriff steht aus |
| K10 ⏸ | TNC2 mit KISS-EPROM (Profil `generic`/`tnc2-kiss`) | Kurztest – ruht, Zugriff auf das Gerät steht aus |

**Testtrick für K1–K6 ohne Hardware-TNC:** Direwolf auf PC2 mit KISS-TCP-Port
als „dummer TNC“, die Gegenstation auf PC1 mit Direwolf/AGW und
Terminalprogramm. So wird der eigene Automat gegen Direwolfs v2.2-
Implementierung getestet, bevor ein Hardware-TNC dazukommt. Bei Variante B
ändert sich für die TinyBox beim Wechsel zum Hub nichts.

## 8a. Funktest K4 auf PC2: TinyBox gegen Direwolfs KISS-Port

Direwolf dient hier nur als Modem („dummer TNC“); AX.25 macht die TinyBox selbst.

1. **PC2:** `git pull` in `C:\Tinybox`.
2. **PC2, `tinybox.conf`** (nicht im Repo) ergänzen:
   ```ini
   [radio]
   interface = kiss
   [kiss]
   port = 8001          ; KISSPORT in direwolf.conf (Standard 8001)
   air_baud = 1200
   ```
   `[ax25]` kann fehlen – dann gelten `paclen`/`max_outstanding` aus `[direwolf]`
   und Version 2.2.
3. Direwolf wie gewohnt starten, dann die TinyBox. In der Konsole muss stehen:
   `KISS mode: own AX.25 layer 2 (version 2.2), KISS 127.0.0.1:8001` und
   `connected to KISS 127.0.0.1:8001`.
4. In der Sysop-Konsole `LOG DEBUG kiss` – dann zeigt das Log jeden Frame
   (`<<` empfangen, `>>` gesendet) im Monitor-Format.
5. **PC1:** mit dem Terminalprogramm über Direwolf/AGW `OE3GAS-1` connecten und
   eine normale Sitzung fahren: `L`, `R n`, `S`, `B`. Danach Chat mit dem
   TinyBox-Client.
6. Prüfen: `STATUS` zeigt `connected (KISS 127.0.0.1:8001)`; die Balken der
   Verbindungsqualität erscheinen **ohne** Direwolf-Fork.
7. Besonders beobachten:
   - Ruft Direwolf auf PC1 mit SABME (v2.2), folgt ein XID-Austausch. Meldet
     Direwolf dabei einen Fehler oder FRMR, stimmen die XID-Bitwerte nicht
     (Abschnitt 3.4) – Log-Ausschnitt schicken.
   - Ruft Direwolf mit SABM, läuft v2.0 – das ist in Ordnung.
8. Zurück zu AGW: `interface = agw` (oder `[radio]` löschen), TinyBox neu starten.

## 8a2. Kanal- und kisshub-Werte in der Web-GUI (CR41, 15.10.2026)

Siehe `docs/client-change-requests.md` CR41. Kurz: Die TinyBox misst die Kanalauslastung selbst aus
dem KISS-Strom (kisshub reicht alle gehörten Frames und die Aussendungen von brocastd weiter);
kisshub meldet über `GET http://127.0.0.1:8102/status`, ob der TNC im KISS-Mode ist, wie lange
Frames im Hub warten und wer am Hub hängt. Die Kopfzeile zeigt im KISS-Mode den TNC
(„PK-232 ready via KISS"), das Dashboard die Karte **Channel**. Die Kanalauslastung fließt nicht in
die Balken ein.

## 8b. Funktest K8: PK-232 über kisshub (VHF, 1200 Bd)

Die Init-Zeilen des PK-232 stammen aus TRM 4.7.1 (über pk232py) plus `VHF ON` und
`HBAUD 1200`, mit `EXPERT ON` an erster Stelle, gefolgt von `VHF ON` und `HBAUD 1200` (Einschalt-Standard, zur Sicherheit gesendet), ohne `RESTART` – Reihenfolge von Gerhard am Gerät geprüft (14.10.2026) (RAWHDLC, HPOLL, PPERSIST sind
Experten-Befehle; ohne ihn antwortet der PK-232 `?EXPERT command`). Eine Antwort mit
`?` bricht den Init ab, statt den TNC halb eingerichtet in KISS zu schalten; mit KISS auf der Luft sind sie noch nicht erprobt. kisshub
protokolliert jede Zeile mit der Antwort des TNC – damit lässt sich jede
Abweichung sofort zuordnen.

1. **PC2:** `git pull`, dann einmal `py -3 -m pip install pyserial`.
2. `kisshub.conf.example` nach `kisshub.conf` kopieren (bleibt außerhalb des
   Repos) und `device` auf den COM-Port des PK-232 setzen, `serial_baud` auf
   seine Terminal-Baudrate (pk232py: 9600).
3. **pk232py beenden** – der COM-Port gehört dann kisshub allein.
4. `kisshub.bat` starten. Erwartet:
   `TNC answers (...)`, eine `init ...`-Zeile je Befehl, zuletzt
   `TNC in KISS mode - ready`.
   - Zeile mit `?bad` / `?What?` (Warnung) oder `TNC init failed`: Log schicken.
     Mit `[log] level = DEBUG` steht jedes Byte des Dialogs drin.
   - Zeile kann man ohne Code-Änderung ersetzen: `init =` im Abschnitt `[pk232]` der conf.
5. **`tinybox.conf`:** `[radio] interface = kiss`, `[kiss] port = 8101`
   (8101 = kisshub, 8001 = Direwolf), TinyBox neu starten. kisshub meldet
   `client1 ... connected`, die Web-GUI zeigt `via KISS`.
6. Funk: VHF-Ausgang des PK-232 an das FM-Gerät, gleiche Frequenz wie die
   Gegenstation. Von PC1 (Direwolf + Terminal) `OE3GAS-1` connecten und eine
   Sitzung fahren (`L`, `R n`, `S`, `B`), dann Chat mit dem Client.
7. brocastd (optional): in `brocastd.conf` `interface = kiss`, `kiss_port = 8101` –
   dann teilen sich TinyBox und brocastd den PK-232 über kisshub.
8. Ende: **Strg+C im kisshub-Fenster** – kisshub holt den PK-232 aus KISS
   (`C0 FF C0`) und schaltet `KISS OFF`; danach findet pk232py ihn wieder bei `cmd:`.

## 8c. Experiment: VARA FM als KISS-TNC (17./18.10.2026)

**Befund (Funktest 17.10.2026, VARA FM, KISS-Port 8100):** VARA ist kein transparenter KISS-TNC.
UI-Frames (Typ 0) nimmt es an und sendet sie; SABM/SABME (und damit Connected Mode) lehnt es mit
„Wrong KISS frame“ ab. Laut VARA-Changelog (v4.7.6/v4.7.9) ist das Byte nach `C0` bei VARA der
**Rahmentyp**, nicht das KISS-Kommando:

| Bytes | VARA |
|---|---|
| `C0 00 … C0` | AX.25-Frame (6-Zeichen-Rufzeichen) – VARA zerlegt den Kopf, nur UI |
| `C0 01 … C0` | AX.25-Frame mit 7-Zeichen-Rufzeichen (VARA Chat/VarAC) |
| `C0 02 … C0` | „Generic Data“, beliebige Bytes, bis 5000 Byte |

Folge: KISS-Parameter (TXDELAY = Kommando 1, P = Kommando 2) wären bei VARA **Datenrahmen auf der
Luft**. Das Profil `vara-fm`/`vara-hf` sendet keine Parameter; `[kiss] send_params = yes` wird mit
Fehler abgewiesen, die Konsole (`TXDELAY …`) ändert dann nur den Sendetakt des Hubs.

**Tunnel (kisshub):** Profil `vara-fm`, `vara_tunnel = connected` (im Abschnitt `[vara-fm]`): UI-Frames gehen
wie bisher als Typ 0 (lesbar für jede VARA-KISS-Anwendung), alle anderen Frames als Typ 2 mit dem
Kennzeichen `AX` vor dem unveränderten AX.25-Frame. Der kisshub der Gegenseite packt Typ-2-Rahmen
mit `AX` wieder aus und gibt sie als normale KISS-Frames an TinyBox/Client – die merken nichts.
`vara_tunnel = all` schickt auch UI-Frames durch den Tunnel. Typ-2-Daten anderer Programme ohne
`AX` werden gezählt und verworfen (`foreign`). Gibt VARA eigene Frames zurück, verwirft kisshub
sie (`echoes`, Vergleich mit den Frames der letzten 30 s). Zähler in `/status` unter `tnc`:
`tunnel`, `tunnel_tx`, `tunnel_rx`, `foreign`, `echoes`.

**Beide Stationen** brauchen kisshub mit Tunnel. Offen (Funktest): Gibt VARA Typ-2-Rahmen
unverändert und mit Typ 2 zurück? Wie lange dauert ein Typ-2-Burst je Größe (für `air_baud`,
`txdelay_ms`, T1)? Wie verhalten sich zwei Verbindungen gleichzeitig?

Quellen: VARA-Changelog (Help → ChangeLog, zitiert in groups.io VARA-MODEM #7213), Mitschnitt
VARA Chat (groups.io VARA-MODEM #6336).

## 8d. Messung: VARA FM gegen Direwolf (1200 Bd) über KISS (18.10.2026)

**Aufbau:** PC1 TinyBox (TS-790), PC2 Client (FT-818), kurze Strecke, VHF. Beide Läufe mit
demselben AX.25-Automaten (TinyBox/Client über kisshub), gemessen von der passiven
AX.25-Auswertung im kisshub (CR67) auf beiden PCs. Nur das Modem ist verschieden: VARA FM 4.4.0
(Narrow, KISS-Port 8100, Tunnel) bzw. Direwolf als KISS-TNC (Port 8001, 1200 Bd AFSK).

**Läufe mit VARA FM** (Szenario: Connect, Chatboard laden, Bulletin ~3000 Zeichen senden, Bye):

| | Lauf 1 | Lauf 2 | Lauf 3 |
|---|---|---|---|
| AX.25 | 128 B, Fenster 1, T2 1,5 s, T1 10 s | wie 1 | **256 B, Fenster 4, T2 0,3 s, T1 18 s** |
| Besonderheit | TX-Pegel TS-790 zu niedrig | Pegel korrigiert | dazu VARA-Monitor |
| Verluste TinyBox → Client | 9 von 61 (15 %) | 0 | 0 |
| Wiederholungen | 2 | 0 | 0 |
| Polls Client / TinyBox | 5 / 6 | 2 / 2 | 3 / 2 |
| Dauer der Verbindung | 790 s | 386 s | **208 s** |
| Rate über die Verbindung | 6,4 B/s | 11,4 B/s | **21,2 B/s** |

**VARA-Monitor (Lauf 3):** Aufwand je Burst 2,2 s (PC2) bzw. 3,2 s (PC1), Rate im Burst nur
**370 bzw. 280 bit/s** – VARA wählt die Stufe nach der KISS-Framegröße, Frames um 256 Byte gehen
in der langsamsten Stufe. VARA **bündelt** schnell aufeinander folgende KISS-Frames (2,4–3 Frames je
Burst). S/N wird jedem empfangenen Frame zugeordnet (VARA FM meldet `SN` auch im KISS-Betrieb, Bezug
2500 Hz): 29,1 dB vom FT-818, 13,2 dB vom TS-790. `PENDING`/`CANCELPENDING` kommen auch im
KISS-Betrieb (ca. alle 2 s während der eigenen Sendephasen) – keine ARQ-Meldung.

**Vergleich mit gleichen AX.25-Werten (Lauf 3 = VARA, Lauf 4 = Direwolf):**

| | VARA FM | Direwolf 1200 Bd |
|---|---|---|
| Verbindungsaufbau | 6,5 s | 1,3 s |
| Rate über die Verbindung | 21,2 B/s | **39,7 B/s** |
| Ein Hin und Her (Antwortabstand der Gegenseite) | 5,5–6,1 s | **2,2–3,2 s** |
| Quittung eines vollen Fensters (4 × 256 B) | 28,2 s | **7,9 s** |
| Verlorene Frames (je Richtung) | **0 / 0** | 2 von 44 / 2 von 39 |
| Wiederholungen / SREJ | **0 / 0** | 2 / 1 |

**Bewertung:** Auf einer kurzen, starken Strecke ist 1200-Bd-AFSK über KISS rund **doppelt so
schnell** wie VARA FM über KISS. Grund ist nicht die Funkstrecke, sondern wie VARA KISS-Verkehr
sendet: 2–3 s Aufwand je Burst und die langsamste Stufe für kleine Frames. VARA war dafür
**verlustfrei**, auch auf der schwächeren Richtung (~13 dB). Der Vorteil von VARA ist bei
schwachen Signalen zu erwarten (eigener Test mit reduzierter Leistung offen).

**Folgerungen:**
- Für VARA in TinyBox/Client und kisshub `[kiss] air_baud = 350`, `txdelay_ms = 2700` (gemessen),
  sonst startet T1 zu früh (unnötige Polls); T1-Untergrenze ≥ 18 s; T2 0,3 s; Fenster 4, 256 B.
- kisshub `max_lead_ms = 12000` bei VARA, damit ein ganzes Fenster auf einmal an VARA geht.
- **Bündelung im Tunnel** (kisshub 2026.10.18.5, `vara_bundle_ms`): mehrere AX.25-Frames
  als **ein** Typ-2-Rahmen (`AB` + je 2 Byte Länge + Frame, bis `vara_bundle_max` Byte) – VARA soll
  so größere Rahmen sehen und eine schnellere Stufe wählen. Einzelne Frames weiter als `AX` +
  Frame. Beide Stationen brauchen die neue Version.

**Lauf 5 (18.10.2026, 17:22, beide kisshub 2026.10.18.5, Bündelung 300 ms, `air_baud = 350`,
`txdelay_ms = 2700`, sonst wie Lauf 3):**

| | Lauf 3 | Lauf 5 |
|---|---|---|
| Verluste / Wiederholungen | 0 / 0 | 0 / 0 |
| Polls Client / TinyBox | 3 / 2 | **0 / 0** |
| Quittung eines Client-Fensters | 28,2 s | **20,4 s** |
| Rate über die Verbindung | 21,2 B/s | 22,1 B/s |
| VARA Client sendet: Aufwand / Rate / Frames je Burst | 2,2 s / 370 bit/s / 3,2 | 3,2 s / 487 bit/s / 2,6 |
| VARA TinyBox sendet: Aufwand / Rate / Frames je Burst | 3,2 s / 280 bit/s / 2,4 | 4,5 s / 476 bit/s / 3,0 |

Die gemessenen Zeitwerte beseitigen die unnötigen Polls vollständig. Mit Bündelung sendet VARA im
Burst schneller (~480 statt 280–370 bit/s), der Aufwand je Burst steigt aber ebenso – unterm Strich
**kein messbarer Gewinn** bei diesem Hin-und-Her-Verkehr (Lauf 5 ohne Bündelung auf der
Client-Seite – erster Versuch, PC2 noch alte Version – lag bei 509 bit/s ebenso hoch). VARA FM über
KISS bleibt auf dieser Strecke bei rund der Hälfte von Direwolf 1200 Bd (39,7 B/s). Der nächste Hebel
ist VARA FM **Wide** über den 9600er-Datenport.

## 9. Risiken

- **Layer-2-Automat ist der Hauptaufwand**, v2.2 mit SREJ und XID deutlich
  mehr als v2.0. Fehler zeigen sich als hängende oder abbrechende
  Verbindungen. Gegenmittel: reiner Automat, Simulator mit Paketverlust,
  Interop gegen Direwolf, LinBPQ und die echten TNCs.
- **v2.2-Nutzen begrenzt:** Mit den vorgesehenen TNCs auf beiden Seiten
  läuft immer v2.0. v2.2 wirkt nur gegen moderne Gegenstellen.
- **Kenwood-TNCs:** kleine Puffer, Bluetooth-Abbrüche – Werte je Gerät im
  Funktest ermitteln.
- **Neue Abhängigkeit:** `pyserial` – auch für Raspi/Produktion einplanen.

## 10. Offene Fragen

1. ~~PK-232: welche Firmware-Version?~~ → getestet mit Gerät A, Firmware Release 13.SEP.95 (13. Sep. 1995).
2. Raspi: welches Modell und welche Anbindung je TNC (USB-Seriell-Adapter, Bluetooth)?
