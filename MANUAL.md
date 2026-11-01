# TinyBox – Handbuch

Betrieb von TinyBox, TinyBox-Client, kisshub und den Hilfsprogrammen: welche Teile es gibt,
wie sie zusammenhängen, wie man sie konfiguriert und wie man die Funkstrecke misst.

Weitere Unterlagen: `README.md` (Start, Telnet-Test, Sysop-Konsole), `brocast/README.md`
(brocastd im Detail: Frames, Listener, Bilder, Wetter, Dictionary), `logging_manual.md`
(Log-Datei lesen), `tbclient/FEATURES.txt` (was der Client kann),
`docs/kiss-mode-konzept.md` (KISS-Mode, VARA, Messungen),
`docs/client-change-requests.md` (alle Änderungen), `PLANUNG.md` (Entscheidungen).

Stand: 22.10.2026 (kisshub 2026.10.22, tbclient 2026.10.18.7)

---

## 1. Die Teile

| Programm | Aufgabe | Start | Konfiguration |
|---|---|---|---|
| **TinyBox** | die Mailbox (BBS): Post, Bulletins, Chat, Forwarding, Web-GUI für den Sysop | `tinybox.bat` | `tinybox.conf` |
| **TinyBox-Client** (`tbclient`) | Programm für Benutzer: Chat, Post, Monitor, APRS – im Browser | `tbclient.bat` | `tbclient.conf` |
| **kisshub** | besitzt den KISS-TNC (PK-232, Kenwood TM-D710, TNC7multi, Direwolf-KISS, VARA FM) und teilt ihn per KISS-TCP; misst die Verbindungsqualität | `kisshub.bat -p <profil>` bzw. `python -m kisshub -c <datei> -p <profil>` | `kisshub.conf` (eine Datei für alle TNCs) |
| **Direwolf** | Soundkarten-Modem (AFSK 1200/9600) mit eigenem AX.25 (AGW) oder als reiner KISS-TNC | `direwolf.exe` | `direwolf.conf` (eigener Ordner, z. B. `E:\direwolf`) |
| **VARA FM** | Soundkarten-Modem von EA5HVK, hier als KISS-TNC (Port 8100) | `VARAFM.exe` | im Programm (Settings → VARA Setup) |
| **brocastd** | sendet/empfängt brocast-Seiten (UI-Frames); Einzelheiten in `brocast/README.md` | `brocast\brocastd.bat` | `brocast\brocastd.conf` |
| **dxfeed** | DX-Cluster → tägliches DX-Bulletin in die TinyBox | `dxfeed.bat` | `dxfeed.conf` |
| **fwdsim** | Testpartner für das Forwarding | `fwdsim.bat` | `fwdsim.conf` |
| **tbtest** | Testbed: 1–30 simulierte User über einen simulierten 1200-Bd-Funkkanal gegen eine eigene Test-TinyBox (`tbtest/README.md`) | `tbtest.bat` | `tbtest.conf` im Testbed-Verzeichnis |

**PCs im Testaufbau:** PC1 (`E:\Tinybox`, TS-790) – TinyBox. PC2 (`C:\Tinybox`, FT-818) –
Client. Auf jedem PC, der einen KISS-TNC nutzt, läuft ein eigener kisshub.

Die `*.conf` gehören nie ins Repo; im Repo liegen nur die `*.conf.example`.

### 1.1 Zwei Betriebsarten

```
AGW:   TinyBox / Client ──AGW 8000──► Direwolf (macht AX.25 selbst) ──► Funkgerät

KISS:  TinyBox / Client ──KISS 8101──► kisshub ──► TNC ──► Funkgerät
       (machen AX.25 selbst)                       ├─ PK-232 / TM-D710 (seriell)
                                                   ├─ Direwolf (KISS-TCP 8001)
                                                   └─ VARA FM  (KISS-TCP 8100, Tunnel)
```

| | AGW | KISS |
|---|---|---|
| Wer macht AX.25 (T1, T2, Fenster, Wiederholungen)? | Direwolf (`direwolf.conf`) | TinyBox / Client selbst |
| Wo stehen Funkrate, TXDELAY? | `direwolf.conf` | kisshub (Profil, `kisshub.conf`, bei VARA gemessen) |
| Verbindungsqualität | nur mit Direwolf-Fork (`Q`) | eingebaut, dazu kisshub-Auswertung (CR67) |
| Mehrere Programme am selben TNC | ja (AGW-Clients) | ja (alle über den kisshub) |

### 1.2 Ports (alle nur 127.0.0.1, außer Web-GUIs)

| Port | wer lauscht | wofür |
|---|---|---|
| 8000 | Direwolf | AGW (`AGWPORT`) |
| 8001 | Direwolf | KISS-TCP (`KISSPORT`) |
| 8100 | VARA FM | KISS-Interface |
| 8300 / 8301 | VARA FM | Befehls-/Datenport (kisshub liest 8300 nur mit) |
| 8101 | kisshub | KISS-TCP für TinyBox, Client, brocastd |
| 8102 | kisshub | Status (`GET /status`, JSON) – immer kisshub-Port + 1 |
| 6300 | TinyBox | Telnet-Testport |
| 10093 (UDP) | TinyBox | AXUDP-Port (`[axudp]`, PLANUNG 25) |
| 8080 | TinyBox | Sysop-Web-GUI |
| 7744 | Client | Web-GUI des Clients |
| 8090 | brocastd | Ingest (TinyBox meldet Bulletins) |

---

## 2. Konfiguration

> **Stand:** Der Aufbau aus CR70 ist umgesetzt (kisshub 2026.10.18.7, tbclient 2026.10.18.3,
> TinyBox, brocastd, dxfeed, fwdsim; `PLANUNG.md` 17.2). Die `*.conf.example` folgen ihm.
> Alte Schlüssel werden weiter gelesen – die Tabelle in 2.8 zeigt alt → neu.

### 2.1 Grundregel: jeder Wert hat genau einen Besitzer

| Wert | Besitzer | alle anderen |
|---|---|---|
| Funkrate, TXDELAY, Persistence, SlotTime | **AGW:** `direwolf.conf` – **KISS:** kisshub | lesen ihn von dort |
| AX.25-Werte (paclen, Fenster, T1, T2 …) | **AGW:** `direwolf.conf` (PACLEN, MAXFRAME, EMAXFRAME, FRACK, RETRY) – **KISS:** Profil des kisshub | `[ax25]` nur zum Überschreiben |
| kisshub-Adresse | `kisshub.conf [server] port` | nur `[kiss] port`; Host immer 127.0.0.1, Status = Port + 1 |
| Direwolf-Ports | `direwolf.conf` (AGWPORT, KISSPORT) | `[agw] direwolf_conf` zeigt auf die Datei |
| Station, Mailbox-Call, Inbox-Ordner | `tinybox.conf` | dxfeed, fwdsim lesen `tinybox.conf` mit |

**`direwolf_conf`** darf ein **Ordner** (`E:\direwolf` → dort `direwolf.conf`) oder eine
**Datei** sein. Gelesen werden: `AGWPORT`, `KISSPORT`, `MODEM`, `TXDELAY`, `PERSIST`,
`SLOTTIME`, `PACLEN`, `MAXFRAME`, `EMAXFRAME`, `FRACK`, `RETRY` (die letzten beiden nur zur
Anzeige). Steht Direwolf auf einem anderen PC oder fehlt der Eintrag, gelten die Standardwerte
bzw. `[ax25]`.

Jedes Programm zeigt beim Start, **woher** jeder Funkwert kommt (`kisshub`, `gemessen`,
`direwolf.conf`, `conf`).

### 2.2 `tinybox.conf` (Funk- und Verbindungsteil)

```ini
[radio]
interface = agw                ; agw | kiss

[agw]                          ; nur bei interface = agw
direwolf_conf = E:\direwolf    ; Ordner oder Datei; daraus: AGWPORT, PACLEN, EMAXFRAME/MAXFRAME
; host    = 127.0.0.1          ; Standard; nur wenn Direwolf auf einem anderen PC läuft
; port    = 8000               ; Standard: AGWPORT aus direwolf.conf, sonst 8000
channel   = 0                  ; Direwolf-Kanal (CHANNEL n in direwolf.conf)
reconnect_sec = 5
; Verbindungsqualität (nur mit Direwolf-Fork, AGW 'Q')
quality_poll_sec      = 30     ; 0 = aus
quality_window_frames = 50
quality_window_min    = 30
quality_min_frames    = 20
quality_steps         = 5, 10, 20, 35, 50

[kiss]                         ; nur bei interface = kiss
port = 8101                    ; kisshub; Status automatisch auf port + 1, Host immer 127.0.0.1

[ax25]                         ; OPTIONAL – nur eintragen, um etwas zu überschreiben
; paclen       =               ; agw: Standard PACLEN aus direwolf.conf (sonst 256)
;                              ; kiss: Standard aus dem kisshub-Profil
; maxframe     =               ; agw: = max_outstanding, Standard EMAXFRAME/MAXFRAME
; maxframe_ext =               ; nur kiss (Modulo 128)
; version      = 2.2           ; nur kiss: 2.2 (SABME/SREJ/XID, fällt selbst auf 2.0 zurück) | 2.0
; srej         = yes           ; nur kiss
; v20_digis    = OE3XTC-5      ; nur kiss: Digis, die nur v2.0 können (z. B. TM-D700) –
;                              ; Verbindungen über sie mit SABM/Modulo 8, alle anderen Digis = v2.2
; v20_digi_paclen = 128        ; nur kiss: längster I-Frame über einen solchen Digi
;                              ; (TM-D700: 256 nein, 128 ja)
; n2 / t1_min_sec / t1_max_sec / t2_sec / t3_sec   ; nur kiss, Standard aus dem kisshub-Profil
```

Alle übrigen Abschnitte (`[station]`, `[mailbox]`, `[telnet]`, `[web]`, `[logging]`, `[chat]`,
`[rubrics]`, `[forward]` …) bleiben wie in `tinybox.conf.example`.

### 2.3 `tbclient.conf`

```ini
[station]
mycall  = OE3GAS
locator = JN88bn

[tinybox]
call         = OE3GAS-1        ; die eigene TinyBox (Mailbox)
ui           = auto            ; auto | yes | no – Chat-Ereignisse als UI-Frames
auto_connect = no
telnet_host  = 127.0.0.1       ; nur für interface = telnet
telnet_port  = 6300

[radio]
interface = kiss               ; agw | kiss | telnet

[agw]                          ; nur bei interface = agw
direwolf_conf = C:\direwolf    ; daraus AGWPORT, MODEM + TXDELAY (Zeitschätzung für Bilder)
channel   = 0
; port    = 8000               ; Standard: AGWPORT aus direwolf.conf

[kiss]                         ; nur bei interface = kiss
port = 8101

[ax25]                         ; OPTIONAL, wie bei der TinyBox (nur kiss),
; v20_digis = OE3XTC-5         ; auch v20_digi_paclen – gilt für Connects über Digis (3.6)

[images]
target_bytes  = 4096
; bytes_per_sec =              ; Standard: aus der Funkrate geschätzt (kisshub bzw. direwolf.conf)
```

`[web]`, `[sync]`, `[storage]` wie in `tbclient.conf.example`.

### 2.4 `kisshub.conf` – der einzige Ort für TNC und Modem

**Eine Datei für alle TNCs** (seit kisshub 2026.10.18.8): welches Gerät läuft, entscheidet der
Start mit `-p`, nicht die Datei.

```
kisshub.bat -p pk232        kisshub.bat -p tm-d710
kisshub.bat -p vara-fm      kisshub.bat -p direwolf
```

Regeln:
- `-p` schlägt `[tnc] profile` (das ist nur der Standard ohne `-p`).
- **Allgemeine Abschnitte** (`[tnc]`, `[kiss]`, `[ax25]`, `[server]`, `[log]`, `[vara]`) gelten
  für **alle** Profile. Dort nur hinein, was wirklich für jedes Gerät stimmt.
- **`[<abschnitt>.<profil>]`** (z. B. `[tnc.pk232]`, `[kiss.pk232]`, `[tnc.vara-fm]`) gilt nur für
  dieses Profil und überschreibt den allgemeinen Abschnitt Schlüssel für Schlüssel.
- Gerätebezogenes gehört **immer** in den Profil-Abschnitt: `device`, `serial_baud`,
  `transport`, `port`, `host` und die `[kiss]`-Werte eines Hardware-TNC. Steht z. B.
  `send_params = yes` im allgemeinen `[kiss]`, bricht `-p vara-fm` mit einem Fehler ab; steht
  `air_baud = 1200` dort, überschreibt es die VARA-Messwerte.
- `{profile}` in Dateinamen (`[log] file`, `links_file`) wird zum Profilnamen – jedes Gerät hat
  sein eigenes Log.
- `kisshub -h` (oder `-?`) zeigt die Hilfe.

**Beispiel** (PC1 mit PK-232 an COM6 und TM-D710 an COM7):

```ini
[tnc]
profile       = pk232          ; Standard ohne -p
reconnect_sec = 10
exit_kiss_on_stop = yes        ; Strg+C: TNC verlässt KISS (Terminal/pk232py findet cmd:)
direwolf_conf = E:\direwolf    ; nur Profil direwolf

[server]
port = 8101                    ; Status automatisch auf 8102, Host immer 127.0.0.1

[log]
level = INFO                   ; DEBUG: jedes Byte des TNC-Dialogs
file  = kisshub-{profile}.log
links_file = kisshub-links-{profile}.jsonl
status_every_sec = 600

[vara]                         ; gilt nur bei vara-fm/vara-hf, sonst Hinweis und aus
monitor  = no
cmd_port = 8300

[tnc.pk232]
device      = COM6
serial_baud = 9600             ; TBAUD des PK-232

[kiss.pk232]
txdelay_ms  = 600              ; Profil-Standard 300

[tnc.tm-d710]                  ; TNC-Taste auf PACKET (3.3)
device      = COM7
serial_baud = 9600

[kiss.tm-d710]                 ; nur für 9600 Bd auf dem Datenband
air_baud    = 9600             ; 1200 (Standard) oder 9600 -> HBAUD
```

**Alle Schlüssel:**

| Abschnitt | Schlüssel | Bedeutung |
|---|---|---|
| `[tnc]` | `profile` | Standardprofil ohne `-p`: `pk232`, `tm-d710`, `tnc7multi`, `th-d74`, `th-d75`, `tnc2-kiss`, `generic`, `vara-fm`, `vara-hf`, `direwolf`, `modem73` |
| | `transport` | `serial` \| `tcp` – Standard je Profil (tcp bei vara-*/direwolf) |
| | `device`, `serial_baud` | nur seriell, z. B. `COM6` / `9600`, Raspberry Pi `/dev/ttyUSB0` |
| | `host`, `port` | nur tcp; Standard 127.0.0.1, vara 8100, direwolf = KISSPORT |
| | `reconnect_sec` | Wartezeit bis zum nächsten Versuch (Standard 10) |
| | `exit_kiss_on_stop` | beim Beenden KISS verlassen (Standard je Profil) |
| | `init_lines` | ersetzt den Init-Dialog: `A \| B \| … \| KISS ON`, die letzte Zeile schaltet in KISS |
| | `direwolf_conf` | nur Profil `direwolf`: Ordner oder Datei |
| | `smack` | KISS mit CRC-16 (SMACK): Standard `yes` bei `tnc7multi`, sonst `no` (3.3a) |
| | `vara_tunnel`, `vara_bundle_ms`, `vara_bundle_max` | nur VARA (3.5) |
| `[kiss]` | `air_baud`, `txdelay_ms`, `max_lead_ms` | Funkwerte – nur zum Überschreiben, Standard aus dem Profil |
| | `persist`, `slottime_ms`, `send_params` | nur Hardware-TNC (KISS-Parameter); bei VARA/Direwolf muss `send_params` no bleiben |
| `[ax25]` | `paclen`, `maxframe`, `maxframe_ext`, `n2`, `t1_min_sec`, `t1_max_sec`, `t2_sec`, `t3_sec` | Empfehlung an TinyBox und Client überschreiben |
| `[server]` | `port` | KISS-TCP für TinyBox, Client, brocastd (Standard 8101) |
| `[log]` | `level`, `file`, `trace`, `status_every_sec`, `links_file` | Logging, Links-Datei (Kapitel 4) |
| `[vara]` | `monitor`, `host`, `cmd_port`, `sn_window_ms` | VARA-Befehlsport mitlesen (Kapitel 4) |

**Profile und ihre Standardwerte:**

| Profil | Weg | air_baud | txdelay_ms | send_params | max_lead_ms | AX.25-Empfehlung |
|---|---|---|---|---|---|---|
| `pk232` | seriell, Init-Dialog | 1200 | 300 | yes | 1500 | 1200-Bd-Werte |
| `tm-d710` | seriell, Init-Dialog (`HBAUD <air_baud>`, `KISS ON`, `RESTART`) | 1200 oder 9600 | 300 | yes | 1500 | 1200- bzw. 9600-Bd-Werte |
| `tnc7multi` | seriell/USB, schon in KISS (Drehschalter), SMACK | 1200 oder 9600 (Schalter 1k2/9k6) | 150 | yes (P 64, SlotTime 50) | 1500 | 1200- bzw. 9600-Bd-Werte |
| `th-d74`, `th-d75`, `tnc2-kiss`, `generic` | seriell/tcp, schon in KISS (kein Dialog) | 1200 | 300 | yes | 1500 | 1200-Bd-Werte |
| `direwolf` | tcp, KISSPORT | aus MODEM | aus TXDELAY | no | 1500 | 1200-Bd-Werte |
| `vara-fm`, `vara-hf` | tcp 8100, Tunnel | 350 | 2700 | **no** | 12000 | 256 B, Fenster 4, T1 18–90 s, T2 0,3 s |
| `modem73` | tcp 8011, startet modem73 aus `[modem73]` (3.5a) | aus dem Modus (fest je Rahmen) | Vorlauf + Rahmenzeit | **no** | Burst | aus dem Modus: QAM16 1/2 short 223 B, Fenster 4, T1 10–60 s, T2 0,5 s |

*1200-Bd-Werte:* paclen 256, Fenster 4 (Modulo 8) / 7 (Modulo 128), T1 3–30 s, T2 1,5 s.
*9600-Bd-Werte* (Startwerte, am Funk noch zu prüfen): paclen 256, Fenster 7 / 7, T1 1,5–15 s, T2 0,5 s.
Beim Profil `direwolf` kommen paclen und Fenster aus PACLEN/MAXFRAME/EMAXFRAME.
Die VARA-Werte sind am 18.10.2026 gemessen (Konzept 8d). `th-d74`, `th-d75` und `tnc2-kiss`
sind noch nicht am Gerät getestet.

**So kommen die Werte bei TinyBox und Client an:** Beide fragen den kisshub-Status
(`http://127.0.0.1:<port + 1>/status`, Block `radio`) alle 30 s ab und übernehmen Funkrate,
TXDELAY und die AX.25-Empfehlung für jede **neue** Verbindung. Im Log steht dann
`radio values from kisshub (profile vara-fm): air_baud 350, txdelay 2700 ms, …`. Was in der
eigenen `[ax25]` steht (oder als alter Schlüssel in `[kiss]`), bleibt und gewinnt.

### 2.5 `brocastd.conf`

```ini
[radio]
interface = agw                ; agw | kiss

[agw]
direwolf_conf = E:\direwolf    ; AGWPORT, MODEM, TXDELAY
channel = 0

[kiss]
port = 8101                    ; kisshub (oder Direwolf-KISSPORT direkt, z. B. 8001)

[station]
; baud / txdelay_ms            ; entfallen: aus direwolf.conf bzw. kisshub
airtime_percent = 15           ; Rest wie in brocastd.conf.example
```

Die Systemrubrik **TBNEWS** (Client-News) geht nie über brocast – auch nicht, wenn sie in
`[brocast] destinations` der TinyBox steht (entschieden 20.10.2026, `PLANUNG.md` 19). Was
brocastd sendet und wie Listener, Bilder, Wetterseite und Dictionary funktionieren, steht in
`brocast/README.md`.

### 2.6 `dxfeed.conf`

```ini
[tinybox]
conf = tinybox.conf            ; daraus der Inbox-Ordner ([inbox] dir)

[digest]
; inbox =                      ; nur noch zum Überschreiben
```

`[cluster]`, `[data]`, Rest von `[digest]`, `[log]` wie in `dxfeed.conf.example`.

### 2.7 `fwdsim.conf`

```ini
[tinybox]
conf = tinybox.conf            ; daraus mailbox_call, haddress, Telnet-Port, DB-Pfad
forward_host = 127.0.0.1       ; Testdaten bleiben hier
forward_port = 0
forward_password =
telnet_user  = OE3XTC

[agw]
direwolf_conf = E:\direwolf    ; paclen, max_outstanding, Port
channel = 0
via     =
```

`[fwdsim]`, `[hop]`, `[remote]` wie in `fwdsim.conf.example`.

### 2.8 Alt → neu

Alte Schlüssel werden weiter gelesen. Steht einer noch in der Datei, gilt er als bewusste
Überschreibung; beim Start erscheint ein Hinweis (z. B. `[kiss] air_baud = 1200 überschreibt
den kisshub-Wert 350 – kann entfernt werden`).

| alt | neu |
|---|---|
| tinybox `[direwolf] agw_host / agw_port / agw_radio_port` | `[agw] host / port / channel` |
| tinybox `[direwolf] paclen / max_outstanding` | aus `direwolf.conf`, sonst `[ax25] paclen / maxframe` |
| tinybox `[direwolf] quality_*` | `[agw] quality_*` |
| tinybox / tbclient `[kiss] air_baud / txdelay_ms` | kisshub (Profil bzw. kisshub `[kiss]`) |
| tinybox / tbclient `[kiss] host / status_port / channel` | fest 127.0.0.1 / `port + 1` / 0 |
| tbclient `[tinybox] link` | `[radio] interface` |
| tbclient `[direwolf] agw_host / agw_port / radio_port` | `[agw] host / port / channel` |
| kisshub `[server] listen / status_port` | fest 127.0.0.1 / `port + 1` |
| kisshub: je TNC eine eigene conf | eine `kisshub.conf`, Start mit `-p <profil>` |
| kisshub `[tnc] device / transport / serial_baud` (gerätebezogen) | `[tnc.<profil>]` |
| kisshub `[kiss] txdelay_ms / persist / send_params …` eines Hardware-TNC | `[kiss.<profil>]` |
| brocastd `[direwolf] interface / agw_port / kiss_port / channel` | `[radio] interface`, `[agw]`, `[kiss]` |
| brocastd `[station] baud / txdelay_ms` | aus `direwolf.conf` bzw. kisshub |
| tbclient `[images] bytes_per_sec` | geschätzt aus der Funkrate (70 %), danach gemessen |
| fwdsim `[agw] radio_port / port / paclen / max_outstanding` | `[agw] channel`, Rest aus `direwolf.conf` |
| dxfeed `[digest] inbox` | aus `tinybox.conf` |
| fwdsim `[tinybox] call / haddress / ax25_call / telnet_* / db` | aus `tinybox.conf` |

### 2.9 `[update]` – Hinweis auf einen neuen Release (alle vier Programme)

Einmal am Tag fragt jedes Programm bei GitHub nach dem neuesten Release von
`oe3gas/Tinybox` und vergleicht ihn mit der eigenen Release-Version (`prcore/release.py`,
`RELEASE`). Es ist nur ein Hinweis: heruntergeladen oder installiert wird nichts, das Update
bleibt `git pull` (Abschnitt „Laufend“ in `GIT-ANLEITUNG.md`). Ohne Internet passiert nichts,
auch keine Fehlermeldung.

```ini
[update]
check    = yes   # alle vier Programme; no = nie fragen
announce = yes   # nur tinybox.conf: EIN Bulletin pro neuem Release in TBNEWS
```

| Programm | Hinweis |
|---|---|
| TinyBox | Warnzeile im Log, `STATUS` an der Konsole, Link unter der Version in der Sysop-Web-GUI; mit `announce = yes` ein Bulletin in TBNEWS |
| TBClient | Banner in der Web-GUI (wegklickbar) und Zeile im Konsolenfenster |
| brocastd | Warnzeile im Log, Zeile „TinyBox-Release“ auf der Statusseite des Listeners |
| kisshub | Warnzeile im Log |

**Das Bulletin** (TinyBox): genau eines pro Release, auch nach Neustarts oder wenn der Sysop
es löscht (gemerkt in `data/release.json`). Ein neuerer Release ersetzt das Bulletin des
älteren. TBNEWS geht nie über Forwarding und nie über brocast – keine Kopien im Netz, keine
Dauerbeschallung. Mit `announce = no` gibt es nur den Hinweis; Konsolenbefehle:

- `UPDATE` – jetzt bei GitHub nachfragen (statt auf den Tagestakt zu warten)
- `UPDATE NEWS` – das Bulletin zum neuen Release jetzt senden

---

## 3. Betriebsrezepte

### 3.1 Packet 1200 Bd über Direwolf (AGW) – der Standardbetrieb

1. Direwolf starten (Fenster zeigt „Ready to accept AGW client application … on port 8000“).
2. `tinybox.conf`: `[radio] interface = agw`, `[agw] direwolf_conf = E:\direwolf`.
3. `tbclient.conf` auf dem anderen PC: `[radio] interface = agw`, `[agw] direwolf_conf = C:\direwolf`.
4. TinyBox, dann Client starten.

AX.25-Einstellungen (PACLEN, MAXFRAME, EMAXFRAME, FRACK, RETRY, TXDELAY) stehen hier nur in
der `direwolf.conf`.

### 3.2 KISS mit Hardware-TNC: PK-232

1. `kisshub.conf`: `[tnc.pk232] device = COM6` (Beispiel 2.4).
2. `kisshub.bat -p pk232` → „TNC answers …“, die Init-Zeilen, „TNC in KISS mode – ready“.
3. TinyBox/Client: `[radio] interface = kiss`, `[kiss] port = 8101`.
4. Ende mit Strg+C im kisshub-Fenster: der PK-232 verlässt KISS (`KISS OFF`, pk232py findet
   ihn wieder).

Der Init-Dialog (am Gerät geprüft, 14./17.10.2026): `EXPERT ON` zuerst (sonst `?EXPERT
command`), `VHF ON`, `HBAUD 1200`, `AWLEN 8`, `PARITY 0`, …, `KISS ON`, `HOST ON`. Der kisshub
weckt den PK-232 aus jedem Zustand (Autobaud, Converse, XOFF, Host Mode, KISS).

### 3.3 KISS mit Hardware-TNC: Kenwood TM-D710

1. Am Funkgerät die **TNC-Taste** drücken, bis **PACKET** im Display steht. Im APRS-Modus
   antwortet der TNC nicht. Datenband (A/B) im Menü des Funkgeräts prüfen.
2. `kisshub.conf`: `[tnc.tm-d710] device = COM7`, `serial_baud = 9600` (Beispiel 2.4).
   `serial_baud` ist nur die Verbindung PC ↔ Funkgerät, nicht die Funkrate.
   **Funkrate** 1200 oder 9600 Bd: `[kiss.tm-d710] air_baud = 9600` (ohne Eintrag 1200).
   Andere Werte lehnt der kisshub beim Start ab. Bei 9600 auch die Gegenstation auf 9600
   und ein für 9600 geeignetes Datenband (meist 70 cm) wählen; `txdelay_ms` ggf. kürzer.
3. `kisshub.bat -p tm-d710`. Der kisshub schickt `HBAUD <air_baud>`, `KISS ON`, `RESTART`
   (mit 1200 von OE3GAS am Gerät geprüft, 22.10.2026; 9600 noch nicht am Funk getestet) und
   wartet 2 s, bis der TNC in KISS hochgefahren ist. Mit `air_baud` stimmen auch die
   Sendezeit-Schätzung, die Statusabfrage (TinyBox, Client, brocastd) und die AX.25-Empfehlung.
4. TinyBox/Client: `[radio] interface = kiss`, `[kiss] port = 8101`.
5. Ende mit Strg+C: `C0 FF C0` und `KISS OFF` – ein Terminal findet wieder `cmd:`.

Antwortet der TNC nicht, nennt die Fehlermeldung im Log die TNC-Taste. Für den ersten Lauf
`[log] level = DEBUG`: dann steht jedes Byte des Dialogs im Log.

**Flusssteuerung:** Beim TM-D710 ist **RTS/CTS** eingeschaltet (`[tnc] rtscts`, Standard
`yes` bei diesem Profil). Ist der kleine TNC-Puffer des Funkgeräts voll, nimmt es CTS weg und
der kisshub wartet, bis CTS wieder kommt – das Funkgerät bremst selbst. Das Kabel muss RTS
und CTS durchführen. Der kisshub verlässt sich dabei nicht allein auf den Treiber: Er schreibt
in 32-Byte-Stücken, schiebt jedes Stück ganz aus der Schnittstelle und prüft CTS vor dem
nächsten. So läuft höchstens ein Stück (plus der FIFO des USB-Adapters) über, wenn Treiber
oder Adapter CTS nicht rechtzeitig beachten. Ausschalten mit `[tnc.tm-d710] rtscts = no`.
`max_lead_ms` bleibt zusätzlich aktiv (Vorrang für Quittungen).

Ob das Funkgerät überhaupt bremst, zeigt der **CTS-Monitor**: Er fragt CTS alle 2 ms ab, mit
`[log] level = DEBUG` steht jeder Wechsel im Log (`CTS low …` / `CTS high again after … ms`),
die Statuszeile zeigt `CTS low 3x (0.4 s, max 210 ms), writer waits 1 (0.1 s)`. Bleibt `CTS low`
bei einer langen Übertragung auf `0x`, bremst das Gerät nicht über CTS (so der TM-D700 im
KISS-Modus, 26.10.2026). Steht CTS länger als 5 s auf tief, kommt eine Warnung. Unter Linux
meldet der Start zusätzlich, ob der Treiber die Flusssteuerung wirklich eingeschaltet hat
(`driver flow control (termios CRTSCTS) on`). Bricht ein Schreibvorgang ab (Adapter gezogen),
öffnet der kisshub die Schnittstelle neu, statt still nichts mehr zu senden.

**Stand:** Profil und Dialog mit simuliertem TNC getestet, Funktest steht aus (Konzept K9).
Gehen trotz RTS/CTS lange Frames verloren, `[ax25.tm-d710] paclen = 128` versuchen.

Als **KISS-TNC** sendet der D710 nur, was TinyBox oder Client liefern – AX.25 v2.2 geht daher
durch ihn. Die v2.0-Grenze betrifft den D710 nur als **Digipeater** (3.6).

### 3.3a KISS mit Hardware-TNC: TNC7multi (IfD)

Alle Werte aus dem Handbuch V1.04 (Firmware TOS 1.04).

1. **Drehschalter** auf **1k2** (KISS, 1200 Bd AFSK) oder **9k6** (KISS, 9600 Bd FSK). Mehr ist
   nicht zu tun: Der TNC ist ab dem Einschalten in KISS, es gibt keinen Init-Dialog. Stellung
   **1** ist ab Werk Flexnet, **Conf** das Einstellmenü – beides geht mit dem kisshub nicht.
   Jedes Drehen startet den TNC neu.
2. **Anschluss:** am besten **USB** (FTDI-Treiber, virtueller COM-Port, Standard **115200 Bd**,
   Strom kommt über USB). Alternativ RS232 mit **Nullmodemkabel** (Standard **38400 Bd**).
   `kisshub.conf`: `[tnc.tnc7multi] device = COM8`, bei RS232 `serial_baud = 38400`.
   Die Datenrate muss zu der im TNC eingestellten passen (Conf-Befehle `u` / `v`).
3. **Funkrate:** `[kiss.tnc7multi] air_baud = 9600` nur, wenn der Schalter auf 9k6 steht – der
   kisshub kann die Rate nicht einstellen, nur Sendezeit-Schätzung und AX.25-Empfehlung folgen.
   Andere Raten (4k8 bis 115k2) nur mit dem Zusatzmodem und einer im Conf-Modus angelegten
   KISS-Schalterstellung (`f1`, `r`, `s`); der Start zeigt dann einen Hinweis.
4. `kisshub.bat -p tnc7multi`. Der kisshub schickt nur die KISS-Parameter – Standard sind die
   Werte des TNC: **TXDELAY 150 ms, Persistence 64, SlotTime 50 ms**, Duplex aus. TXtail und
   SetHardware braucht der TNC nicht.
5. **SMACK** (KISS mit CRC-16): Der kisshub sendet Datenframes mit Prüfsumme, der TNC schaltet
   daraufhin selbst auf SMACK und sendet ebenfalls mit Prüfsumme. Frames mit falscher
   Prüfsumme verwirft der kisshub (Warnung im Log, Zähler `crc_errors` in Status und
   Statuszeile: `SMACK on (CRC ok 120, bad 0)`). Zurück zu reinem KISS geht nur mit einem
   Neustart des TNC (Schalter drehen oder Strom aus) – CRC-Frames liest der kisshub daher
   immer, auch mit `[tnc.tnc7multi] smack = no`.
6. Ende mit Strg+C: nichts wird an den TNC geschickt, er bleibt in KISS.

**Nur im Conf-Modus einstellbar** (Schalter auf Conf, Terminal 9600 Bd 8N1, z. B. PuTTY): vor
allem die **Modulationsspannung** (`n`, 10…220 = 100…2200 mVss, Standard 1000 mVss) – laut
Handbuch „unbedingt notwendig für einen einwandfreien Betrieb“. Beispiel für die 1k2-Stellung
mit 400 mVss: `@1200`, `n40`, `!1200`. Dazu RX-Mute-Delay (`m`, bei echten Datentransceivern
0) und PTT-Watchdog (`g`, Standard 20 s). Das Handbuch empfiehlt, auch für 1200 Bd den
9k6-Eingang des Funkgeräts zu benutzen.

**Stand:** Profil, SMACK und Konfiguration mit simuliertem TNC getestet (kisshub 2026.10.29),
Funktest steht aus.

### 3.4 KISS mit Direwolf als Modem (für Messungen und den Vergleich mit VARA)

Gleicher AX.25-Automat wie bei VARA, nur das Modem ist anders – dafür gedacht, Modems zu
vergleichen.

1. Direwolf läuft, KISSPORT 8001 offen. **VARA geschlossen** (gleiche Soundkarte!).
2. `kisshub.conf`: `[tnc] direwolf_conf = E:\direwolf`; Start `kisshub.bat -p direwolf`. Port
   (KISSPORT), Funkrate (MODEM), TXDELAY, PACLEN und Fenster kommen aus der `direwolf.conf`;
   die Startzeilen des kisshub zeigen sie.
3. TinyBox/Client auf `interface = kiss`, Port 8101.

### 3.5 KISS mit VARA FM

**VARA einrichten** (beide PCs): Settings → VARA Setup → **KISS interface** anhaken, KISS-Port
**8100**; Soundkarte und PTT einstellen; FM System NARROW (Mikrofon/Lautsprecher) bzw. WIDE
(9600er-Datenport). VARA neu starten, `netstat -an | findstr 8100` muss LISTENING zeigen.

**Wichtig zu VARA am KISS-Port** (gemessen 17./18.10.2026):
- VARA nimmt als normalen KISS-Frame (Typ 0) **nur UI-Frames**; SABM/SABME und alles für
  Verbindungen lehnt es mit „Wrong KISS frame“ ab. Der kisshub tunnelt diese Frames deshalb in
  VARAs Typ 2 („Generic Data“). **Beide Stationen brauchen den kisshub** mit Profil `vara-fm`.
- **Keine KISS-Parameter an VARA** (KISS-Kommando 1/2 = VARA-Rahmentyp 1/2 – würde gesendet).
  Das Profil verhindert es; `send_params = yes` wird abgewiesen.
- VARA FM und Direwolf **nie gleichzeitig** an derselben Soundkarte.

**kisshub** (beide PCs): Start `kisshub.bat -p vara-fm`. Das Profil bringt alles mit
(transport tcp, Port 8100, air_baud 350, txdelay 2700 ms, max_lead 12000 ms, AX.25-Empfehlung).
In der gemeinsamen `kisshub.conf` (2.4) ist nichts nötig; wer will, ergänzt:

```ini
[vara.vara-fm]
monitor = yes                  ; beim ersten Mal jemand ans Funkgerät (PTT-Hänger möglich)

[tnc.vara-fm]
; host = 192.168.1.20          ; nur wenn VARA auf einem anderen PC läuft
; vara_tunnel = connected      ; Standard; all = auch UI-Frames durch den Tunnel
```

Erwartet beim Start: `vara-fm`, `radio: air_baud 350 (profile vara-fm), txdelay 2700 ms …`,
„VARA tunnel connected …“, „VARA monitor: listening …“. Das Log heißt `kisshub-vara-fm.log`.

**TinyBox / Client:** nur `[radio] interface = kiss` und `[kiss] port = 8101` – **kein**
`[ax25]` nötig. Die Werte (paclen 256, Fenster 4/4, T1 18–90 s, T2 0,3 s, Funkrate,
TXDELAY) kommen vom kisshub; im Log erscheint `radio values from kisshub …`. Stehen noch
alte Einträge (`[kiss] air_baud`, `[ax25] t1_min_sec` …) in der conf, gelten sie weiter und
der Start meldet `config hint: …` – entfernen, damit der kisshub bestimmt.

**Pegel:** Im VARA-Fenster S/N und Konstellation beobachten. Vier enge Punktwolken, S/N
25–30 dB auf kurzer Strecke. Ein deutlich niedrigerer Wert in einer Richtung heißt meist:
TX-Pegel des sendenden Geräts zu niedrig (Lauf 1: TS-790, 15 % Frameverlust).

**Was zu erwarten ist** (18.10.2026, kurze Strecke, VHF): VARA FM Narrow über KISS ist
verlustfrei, aber rund halb so schnell wie Direwolf 1200 Bd (22 gegen 40 B/s): VARA sendet
KISS-Verkehr mit ~300–500 bit/s und 2–4 s Aufwand je Burst.

### 3.5a KISS mit modem73 (OFDM, PLANUNG 15)

modem73 (RFnexus, Public Domain) ist ein OFDM-Soundkarten-Modem mit 2400 Hz Bandbreite und
transparentem KISS-TCP: SABM, I, RR gehen unverändert durch – kein Tunnel wie bei VARA. Der
kisshub **startet modem73 selbst** aus dem Abschnitt `[modem73]` der `kisshub.conf` und beendet
es mit Strg+C wieder.

**Vorher:**
- `modem73.exe` bauen bzw. holen: `tools/modem73/README.md`. Pfad in `[modem73] exe`.
- **Direwolf beenden** – modem73 braucht die Soundkarte für sich.
- **Beide Stationen** brauchen modem73 + kisshub; 1200-Bd-Stationen und Digis hören es nicht.
  Eigene Frequenz verwenden.
- Soundkartennamen: `modem73.exe --list-audio`.

**kisshub.conf** (beide PCs, je mit eigenem Rufzeichen und Geräten):

```ini
[modem73]
callsign      = OE3GAS          ; ohne SSID - steht in jedem OFDM-Rahmen
exe           = C:\modem73\modem73.exe
modulation    = QAM16
code_rate     = 1/2
frame         = short           ; 254 B je Rahmen in 0,96 s
input_device  = <Name aus --list-audio>
output_device = <Name aus --list-audio>
tx_level      = 60
ptt           = com
com_port      = COM5            ; der Port, der bisher bei Direwolf die PTT schaltet
com_line      = rts
tx_delay_ms   = 300
csma_band     = vhf
csma_burst    = 4
```

Start: `kisshub.bat -p modem73`. Die Startzeilen zeigen modem73 mit Modus, Nutzlast und
Rahmenzeit, die festen Sendezeiten und die AX.25-Empfehlung; danach die Startzeilen von
modem73 selbst (Soundkarte, PTT, Port 8011) und `modem73 ready on 127.0.0.1:8011`. Endet
modem73 von selbst, startet der kisshub es nach `reconnect_sec` neu. Log: `kisshub-modem73.log`.

**Was der kisshub aus dem Modus ableitet** – nichts davon von Hand eintragen:
- Jeder Rahmen kostet seine volle Zeit, egal wie lang er ist (ein RR so viel wie ein I-Frame).
  Sendezeit je Rahmen = Vorlauf (PTT-Verzögerung + TX-Delay, mit Vorlaufton mindestens
  800 ms) + Rahmenzeit; weitere Rahmen derselben Tastung + Rahmenzeit + 200 ms.
- **PACLEN** = Nutzlast − 31 Byte AX.25-Kopf (QAM16 1/2 short: 223). Ein längerer Frame würde
  von modem73 abgeschnitten; der kisshub verwirft ihn mit Warnung (`oversize` im Status).
- Fenster = `csma_burst`, T1 ab 10 s (QAM16 1/2 short), T2 0,5 s.
- `[kiss] air_baud` / `txdelay_ms` werden abgewiesen; `[ax25]` darf PACLEN nur verkleinern.

**TinyBox / Client:** wie immer bei KISS nur `[radio] interface = kiss`, `[kiss] port = 8101`,
`[ax25] version = 2.2` – die Werte kommen vom kisshub.

**Modi** (Nutzlast je Rahmen / Rahmenzeit, aus modem73 2.4.8 berechnet):

| Modus | Nutzlast | Zeit | Hinweis |
|---|---|---|---|
| QPSK 1/2 short | 126 B | 0,96 s | robust, PACLEN 95 |
| QAM16 1/2 short | 254 B | 0,96 s | Standard für FM, PACLEN 223 |
| QAM16 3/4 short | 382 B | 0,96 s | gutes Signal; PACLEN bleibt 256 (Grenze der Stationen) |
| QPSK 1/2 normal | 510 B | 2,60 s | modem73-Standard – für AX.25 ungünstig (RR 2,6 s) |

`lead_tone = no` spart je Tastung rund 0,5 s, andere modem73-Stationen erkennen den belegten
Kanal dann aber erst am Signal selbst.

### 3.6 Connect über Digipeater (Client, CR71)

Im Client ins Connect-Feld die klassische TNC-Syntax: `OE3XYZ-1 V OE3XTC-5` (mehrere Digis mit
Komma oder Leerzeichen, höchstens 8). Unter dem Feld zeigt eine Vorschau den Pfad. Die Liste der
letzten Ziele merkt sich den ganzen Pfad. Via ist nur Digipeating – einen Node connectet man
selbst und verbindet dort mit `C` weiter.

**v2.0-Digis** (nur bei `interface = kiss`): Ältere Hardware-Digis wie der TM-D700 OE3XTC-5
kennen nur AX.25 v2.0. Über sie scheitern SABME/Modulo 128 und 256-Byte-Frames. Deshalb in
`tinybox.conf` **und** `tbclient.conf`:

```ini
[ax25]
v20_digis       = OE3XTC-5     ; Verbindungen über diese Digis: SABM, Modulo 8
v20_digi_paclen = 128          ; längster I-Frame über sie
```

Alle anderen Digis gelten als v2.2 (aktuelle Digis laufen meist über Software-TNC), wie bei
Direwolf (`V20`). Bei AGW entscheidet Direwolf selbst.

---

### 3.7 Benutzerprofil: Name, Locator, Home-BBS (CR73)

Die TinyBox kennt zu jedem Rufzeichen (alle SSIDs zusammen) Name, Locator und Home-BBS.
Alle Benutzer sehen diese Angaben.

- **Terminal:** Nach dem Login fragt die TinyBox nach den fehlenden Angaben. Enter
  überspringt eine Frage, `/AB` alle. Ist das Profil unvollständig, fragt sie höchstens
  alle 30 Tage wieder. Ändern mit `N name`, `NL JN88EP`, `NH OE3XSR` (`-` löscht ein Feld),
  ansehen mit `N` (eigenes) oder `I call`. Im Chat zeigt `/W` Name und Locator.
  Abschalten der Fragen: `[mailbox] ask_profile = no` in `tinybox.conf`.
- **Client:** Fehlen Name oder Locator, erscheint über dem Chat ein Balken
  „Introduce yourself“ – *Fill in* öffnet das Formular, *Later* fragt in einer Woche wieder.
  Jederzeit unter Settings > *My profile*. Vorschlag für den Locator ist `[station] locator`
  aus `tbclient.conf`. Das Profil geht nur über Funk, wenn es sich geändert hat; eine
  Änderung im Terminal kommt beim nächsten Connect in den Client (die neuere gilt).
- **Sysop-Web-GUI:** Stationen (JLOG) zeigen Name, Locator und Home-BBS.

### 3.8 AXUDP: Client und TinyBox am selben PC (PLANUNG 25)

Ein Funkgerät, TinyBox und Client am selben PC: Die TinyBox bekommt neben dem Funk einen
AXUDP-Port. Der Client erreicht die eigene Box darüber, alle anderen Stationen über Funk.

```ini
[axudp]                        ; tinybox.conf
enabled = yes
listen  = 127.0.0.1
port    = 10093
peers   = OE3GAS 127.0.0.1:10094   ; Rufzeichen des Clients und sein UDP-Port
```

- Über AXUDP läuft das eigene AX.25 der TinyBox (auch wenn der Funk über Direwolf/AGW
  geht): Fenster 32, PACLEN 256, T1 3 s – keine Sendezeit. Login, Chat, Mail-Sync, Bilder
  und Kompression wie über Funk; UI-Frames (Chat-Ereignisse, Bake) nur über Funk.
- Angenommen wird nur, was von der IP einer Gegenstelle **und** mit deren Rufzeichen kommt;
  alles andere wird still verworfen. Vorerst nur Loopback. Sysop-Rechte nur für das
  Sysop-Rufzeichen von Loopback (wie Telnet).
- Dieselbe Station nur einmal: über Funk **oder** AXUDP.
- `STATUS` (Konsole) zeigt eine Zeile `AXUDP:` mit Gegenstellen, Verbindungen, Zählern und
  verworfenen Paketen. Log-Komponente `axudp` (`[logging] debug = axudp`).
- **Client** (ab 2026.10.26.2): in `tbclient.conf`

  ```ini
  [tinybox]
  call       = OE3GAS-1
  axudp      = 127.0.0.1:10093   ; die TinyBox ([axudp] port)
  axudp_port = 10094             ; eigener UDP-Port = Eintrag in den peers der TinyBox
  ```

  Ein Connect zur Heim-TinyBox (ohne Digi) läuft dann über AXUDP, jeder andere über Funk
  (`[radio] interface = agw` an denselben Direwolf oder `kiss`). Über AXUDP: voller
  Client-Modus mit Bildern und Kompression, Mail-Sync ohne Funkpausen, Chat ohne UI-Frames;
  der Kanal-Chip zeigt „AXUDP“, das Logbuch `via axudp`. Mit Digi-Pfad geht auch die
  Heim-TinyBox über Funk. Mit `interface = telnet` ist `axudp` nicht erlaubt.
- **Langsamer Weg** (z. B. der simulierte 1200-Bd-Kanal des Testbeds, PLANUNG 27.2): die
  AX.25-Werte über AXUDP lassen sich einstellen, mit `air_baud` rechnet das AX.25 mit
  Sendezeit (Halbduplex, T1 erst nach dem eigenen Senden, gehörte Frames halten T1 an,
  T2 1,5 s). Ohne diese Einträge bleibt alles wie oben.

  ```ini
  [axudp]                          ; tinybox.conf
  paclen = 256
  maxframe_ext = 4
  t1_sec = 6
  air_baud = 1200
  txdelay_ms = 300

  [tinybox]                        ; tbclient.conf (ab 2026.10.29)
  axudp_paclen = 256
  axudp_maxframe = 4
  axudp_t1_sec = 6
  axudp_air_baud = 1200
  axudp_txdelay_ms = 300
  ```

## 4. Verbindungsqualität messen (kisshub, CR67)

Der kisshub wertet jede AX.25-Verbindung, die durch ihn läuft, passiv aus – für jeden TNC gleich,
so lassen sich Modems vergleichen.

**Konsole des kisshub:**

| Befehl | zeigt |
|---|---|
| `L` / `LINKS` | laufende und letzte Verbindungen: Wiederholungen, REJ/SREJ, Polls, Quittungszeit, Antwortabstand, Rate, S/N |
| `V` / `VARA` | VARA-Befehlsport: Bursts (Dauer, Wartezeit), gemessener Aufwand + Rate, BUSY-Anteil, S/N |
| `STATIONS` | gehörte Stationen mit Frames und S/N |
| `LOG MARK text` | Marke ins Log (vor jedem Testschritt) |
| `LOG TRACE` | jedes Byte zum/vom TNC |
| `S` | Kurzstatus TNC, Warteschlange, Clients |

**Links-Datei** (`[log] links_file`): je beendeter Verbindung eine JSON-Zeile mit TNC-Profil,
Einstellungen, VARA-Messwerten, Tunnel-Zählern und allen Kennzahlen. Für einen Vergleich je Lauf
einen eigenen Dateinamen setzen, auf **beiden** PCs.

**Kennzahlen lesen:**

| Kennzahl | bedeutet | Hinweis auf |
|---|---|---|
| Wiederholungen (`retrans`) | I-Frame nochmals gesendet | Verluste auf dem Weg zur Gegenstelle |
| Polls | S-Frame mit P=1 ≈ T1 abgelaufen | T1 zu kurz oder Frame verloren |
| Quittungszeit (`ack`) | I-Frame bis zur Quittung | Laufzeit über das Modem (+ T2 der Gegenstelle) |
| Antwortabstand (`answers after`) | Frame der Gegenstelle nach dem eigenen | ein „Hin und Her“ |
| Vergleich gesendet ↔ angekommen | Frames bei A gesendet, bei B empfangen | Verluste je Richtung (beide Logs nötig) |
| S/N (VARA) | dem empfangenen Frame zugeordnet, Bezug 2500 Hz | Pegel/Hub, Reserve |

Statusabfrage für Programme: `GET http://127.0.0.1:8102/status` (Blöcke `tnc`, `radio`,
`queue`, `quality`, `vara`). `radio` enthält Profil, `air_baud`, `txdelay_ms`, `max_lead_ms`,
die AX.25-Empfehlung (`ax25`) und je Wert die Herkunft (`source`).

---

## 5. Fehlersuche

| Meldung / Beobachtung | Ursache | Abhilfe |
|---|---|---|
| kisshub-Startzeile zeigt alte Version oder `generic` statt `vara-fm` | kein `git pull` bzw. falsches Profil | `git pull`, Profil in der kisshub-conf |
| VARA: „Wrong KISS frame“ | Verbindungs-Frames als Typ 0 an VARA | Profil `vara-fm` (Tunnel) auf **beiden** Seiten |
| kisshub: „type-2 data that is not ours … ignored“ | Gegenseite sendet Bündel/Format, das diese Version nicht kennt | gleiche kisshub-Version auf beiden PCs |
| VARA: „Soundcard … missing in action“ | Audio-Gerät nicht gefunden | Settings → Soundcard neu wählen, VARA neu starten |
| Viele Polls, Quittungen über T1 | T1 zu kurz für das Modem | Log: fehlt `radio values from kisshub`? kisshub ≥ 2026.10.18.7 und alte `[kiss]`/`[ax25]`-Werte entfernen |
| Start meldet `config hint: … overrides …` | alter Schlüssel in der conf überschreibt den Besitzer | Schlüssel entfernen (Tabelle 2.8), außer die Überschreibung ist gewollt |
| `[agw] direwolf_conf: direwolf.conf not readable` | Pfad falsch | Ordner oder Datei angeben, z. B. `E:\direwolf` |
| `[kiss] txdelay_ms … must be between 0 and 2550` | alte TinyBox | `git pull` (Grenze jetzt 10 000 ms) |
| Mail bleibt im Postausgang trotz Aussendung | alter Client (vor 2026.10.18) | `git pull`; CR68/CR69 |
| `not reachable … 8100` | VARA nicht gestartet oder KISS-Interface aus | VARA starten, Häkchen „KISS interface“ |
| PTT bleibt gedrückt | bekannter VARA-Fehler mit KISS + Befehlsport | kisshub mit Strg+C beenden, `[vara] monitor = no` |
| kisshub: `no answer from the TNC … TM-D710: press the TNC key …` | TNC im APRS-Modus, falscher COM-Port oder falsche Baudrate | TNC-Taste bis PACKET, `[tnc.tm-d710] device`, COM-Geschwindigkeit im Menü |
| kisshub: `[tnc] device: the serial port …` | serielles Profil gestartet, aber kein `device` für dieses Profil | `[tnc.<profil>] device = COMx` |
| kisshub: `[kiss] send_params: must be no with profile vara-fm` | `send_params = yes` im allgemeinen `[kiss]` | nach `[kiss.pk232]` verschieben (2.4) |
| VARA zu schnell/zu langsame Timer, obwohl Profil vara-fm | `air_baud`/`txdelay_ms` im allgemeinen `[kiss]` überschreibt die Messwerte | nach `[kiss.<hardware-profil>]` verschieben |
| Connect über OE3XTC-5 kommt nicht zustande oder hängt bei langen Texten | Digi kann nur v2.0 bzw. verwirft 256-Byte-Frames | `[ax25] v20_digis` und `v20_digi_paclen = 128` (3.6) |
| GeoSphere: Zertifikatsfehler (`CERTIFICATE_VERIFY_FAILED`) | Stammzertifikate fehlen unter Windows (TLS-Prüfung seit 20.10.2026 ein) | `geosphere_aufgaben_einrichten.bat` erneut oder `py -3 -m pip install truststore` |
