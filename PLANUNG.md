# TinyBox – Planung

Kleine, eigenständige Packet-Radio-Mailbox für Direwolf.
Bedienersprache: **Englisch**. Speicherung komplett am PC.
Forwarding mit anderen Mailboxen als optionales Modul (Abschnitt 13). Vorbereitet für die Anbindung an MQTT-Broker.
Eigener TinyBox-Client mit Sonderfunktionen in Planung (Abschnitt 12).

Stand: 07.10.2026 (Rev. 4) · OE3GAS

**Überblick: zwei Projektteile neben dem Kern**

| Teil | Zweck | Stand | Details |
|---|---|---|---|
| Forwarding (F0–F7) | TinyBox tauscht Post und Bulletins mit anderen Mailboxen (LinBPQ, FBB, openBCM) | F1–F5 fertig: TinyBox empfängt und sendet (ASCII, FBB, B1 komprimiert), ruft Partner selbst an; mit LinBPQ (TCP) und TinyBox ↔ TinyBox über Funk getestet. Als Nächstes F6 (Anschluss ans Netz) | Abschnitt 13 und Konzept-Doc |
| TinyBox-Client (C0–C3) | Eigener Client mit Funktionen, die es nur mit der TinyBox gibt: Post-Hinweis, Chat per UI-Broadcast, Offline-Mailbox | C0–C3 umgesetzt: Grundgerüst, Handshake, Post-Hinweis, Chat mit UI-Broadcast, Web-GUI im Messenger-Stil (Handy und PC, 08.10.2026); Offline-Mailbox mit Abgleich (10.10.2026). Funktest von C3 offen | Abschnitt 12 |

**Änderungen gegenüber Rev. 3**

- Planung an den Code angeglichen (Stand Commit 329e67d).
- Forwarding ist jetzt im Umfang, als abschaltbares Modul (Abschnitt 13). Der Kern ist auf Schema 5: hierarchische Adressen, BID, R:-Zeilen.
- Chat-Boards (Befehl `C`) sind fertig und jetzt beschrieben (Abschnitt 2a).
- Client: Web-GUI im LAN/WAN erreichbar, ohne Anmeldung, mobile Oberfläche (Abschnitt 12.1).
- Befehlssatz, Ereignisse, Konfiguration, Datenhaltung, Projektstruktur und Meilensteine nachgezogen. Entwickelt wird auf PC2 in `C:\Tinybox`, PC1 (`E:\Tinybox`) holt per `git pull`.

**Änderungen gegenüber Rev. 2**

- Neuer Befehl `DICT` für die Zusammenarbeit mit brocast (Abschnitt 2). TinyBox bleibt bis auf Weiteres eine kleine Text-BBS ohne Dateiablage.

**Änderungen gegenüber Rev. 1**

- Der PK-232 MailDrop dient nur noch als Orientierung beim Entwurf der Befehle. Es gibt keine Abhängigkeit und keine Kompatibilitätsanforderung.
- Die Konfiguration steht in der Datei `tinybox.conf` (INI-Format), dort auch Mailbox-Call und SSID.
- Direwolf läuft immer auf demselben PC (AGW auf `127.0.0.1`).
- Python ist bestätigt.
- Neu: MQTT-Anbindung ist in der Architektur vorgesehen (Abschnitt 6).

---

## 1. Ziele & Abgrenzung

**Ziele**

- Anrufer verbinden sich per AX.25 (connected mode) mit dem Mailbox-Call aus `tinybox.conf`.
- Nachrichten lesen, schreiben, löschen und auflisten.
- SYSOP-Zugang lokal am PC (Konsole), ohne Funk.
- Persistente Speicherung am PC.
- Chat-Boards für eingeloggte Stationen (Abschnitt 2a).
- Optional: Austausch mit anderen Mailboxen (Forwarding, Abschnitt 13).
- Nachrichten können später auch über MQTT eingespielt und ausgegeben werden.
- Einfacher, gut lesbarer Code (Lernprojekt).

**Nicht im Umfang (v1)**

- BBS-Forwarding gehört nicht zum Kern. Es kommt als eigenes, abschaltbares Modul dazu (Abschnitt 13). Ohne Modul bleibt TinyBox eine Standalone-Mailbox.
- Keine Dateiablage / kein YAPP.
- MQTT: in v1 nur die Schnittstellen vorbereiten, die Umsetzung folgt in einem eigenen Meilenstein.

---

## 2. Befehlssatz

Orientiert sich am klassischen WORLI/MailDrop-Stil, den Packet-Nutzer kennen. Die Einzelheiten legt TinyBox selbst fest.

| Befehl | Funktion |
|---|---|
| `A` | Laufende Ausgabe abbrechen |
| `B` | Abmelden, Verbindung trennen |
| `C` / `C board` | Chat: Boards auflisten / Board betreten (Name oder Nummer), Abschnitt 2a |
| `H` / `?` | Hilfe |
| `J` | Zuletzt verbundene Stationen |
| `K n` | Nachricht n löschen (eigene oder an mich) |
| `KM` | Alle gelesenen Nachrichten an mich löschen |
| `L` | Nachrichten auflisten |
| `LB` / `LP` | Nur Bulletins / nur private Nachrichten |
| `L@ gebiet` | Nachrichten @ Gebiet oder Mailbox, z. B. `L@ WW` |
| `L> call` / `L< call` | Nachrichten an / von `call` |
| `LM` | Nur Nachrichten an mich |
| `R n` | Nachricht n lesen |
| `RM` | Alle ungelesenen Nachrichten an mich lesen |
| `S call` / `SP call` | Private Nachricht an `call` |
| `SP call @ mailbox` | Private Nachricht an einen User einer anderen Mailbox, z. B. `SP OE1ABC @ OE1XAB.#WIE.AUT.EU` (nur mit Forwarding) |
| `SB rubrik [@ gebiet]` | Bulletin, z. B. `SB ALL` oder `SB ALL @ WW`; optional am Ende `$BID`. Mit `[rubrics]` nur ALL und die angenommenen Rubriken (CR19) |
| `STAT` / `STAT ALL` | Verbindungsqualität: eigene Funkverbindung / alle (Abschnitt 14) |
| `V` | Version |
| `E n feld wert` | Nachrichtenkopf ändern (nur SYSOP), Felder TO, FROM, TYPE, STATUS, SUBJ, AT |
| `DICT` | brocast-Dictionary als Text ausgeben (für den Import im brocast-Listener) |

**`DICT` (Zusammenarbeit mit brocast):** TinyBox bleibt eine Textmailbox ohne Dateiablage. Das brocast-Dictionary ist reiner Text (YAML) und wird deshalb einfach ausgegeben: zwischen den Zeilen `#BROCAST-DICT BEGIN v<Version> lines=<n> sha256=<Prüfsumme>` und `#BROCAST-DICT END`, ohne Kommentar- und Leerzeilen, rein ASCII (Umlaute in Anführungszeichen als `\uXXXX`). Der Nutzer speichert den Mitschnitt seines Terminals und importiert ihn im brocast-Listener, der Zeilenzahl und SHA-256 prüft. Die Datei liest TinyBox direkt von der Platte (`[brocast] dict_file` in `tinybox.conf`), eine neue Version ist sofort verfügbar.

Eingabe einer Nachricht: zuerst wird der Betreff abgefragt, dann der Text. Ende mit **`/EX`** in eigener Zeile oder **CTRL-Z**.

**Rechte**

- **User**: liest Bulletins und die eigenen Privatnachrichten. Löscht nur Nachrichten, die an ihn gerichtet oder von ihm sind.
- **SYSOP** (lokal): darf alles lesen und löschen, dazu `E n`.
- `third_party = yes` (Standard): jeder darf an jeden schreiben. Mit `no` dürfen Remote-User nur an den Sysop schreiben.

**Typ/Status**: Typ `P` (privat) oder `B` (Bulletin); Status `N` (ungelesen) oder `Y` (gelesen). Ein dritter Buchstabe im Listing zeigt den Forward-Zustand: `$` wartet, `F` weitergeleitet, `H` gehalten (gehaltene Nachrichten sieht nur der Sysop).

## 2a. Chat-Boards (fertig, Commit 33c2259)

- Feste Boards, vom Sysop in `[chat_boards]` festgelegt: `NAME = Aufbewahrung Beschreibung`. Aufbewahrung `live` (nichts wird gespeichert) oder z. B. `12h` / `7d` (max. `365d`). Die Reihenfolge in der Datei ist die Nummer des Boards.
- `C` listet die Boards, `C board` betritt eines. Im Board ist jede Zeile Chattext, Befehle beginnen mit `/`: `/Q`, `/EX` oder CTRL-Z zurück in die Mailbox, `/W` wer ist da, `/L` alle Boards, `/J board` wechseln, `/H` Hilfe.
- Beim Betreten zeigt TinyBox nur, wie viele Zeilen gespeichert sind und von wann die letzte ist; `/H n` zeigt die letzten n (höchstens `history_lines` pro Abruf, Tabelle `chat_lines`). Clients holen die History mit `//HIST` (CR13, `docs/client-change-requests.md`). Zeilenlänge max. `max_line`.
- Der `ChatHub` (`chat.py`) verteilt die Zeilen und meldet `chat.joined`, `chat.left`, `chat.message` an den Event-Bus. Sysop-Konsole und Web-GUI zeigen den Chat an.
- Grenze: Jede Zeile geht per I-Frame einzeln an jeden Teilnehmer (1 Eingabe = n Ausgaben auf der Frequenz). Das soll der Client mit UI-Broadcast lösen (Abschnitt 12, C2).

---

## 3. Bedienoberfläche (English)

```
*** CONNECTED to OE3GAS-1
Welcome to TinyBox OE3GAS-1, hello OE1ABC.
You have 2 new message(s).
TinyBox (A,B,H,J,K,L,R,S,V,?) >
```

```
MSG# TS SIZE TO     FROM   DATE   SUBJECT
  12 PN  340 OE1ABC OE3GAS 260927 Sked 80m tonight
  11 BY  812 ALL    OE3XYZ 260926 Direwolf notes
```

```
> S OE3GAS
Subject: Test from the field
Enter message, end with /EX or ^Z:
...
/EX
Msg 13 saved.
```

Fehlermeldungen: `Unknown command. Type H for help.` · `No such message.` · `Not allowed.`
Alle Texte stehen zentral in `texts.py`.

**Lange Ausgaben: Abort statt Seiten (CR40, 15.10.2026; ersetzt die Seiten von CR29):** Eine Antwort auf einen Terminal-Befehl, die länger als 10 Zeilen ist, beginnt mit `*** 37 lines follow - send A to abort` und läuft dann **komplett** durch, ohne Rückfrage. `A` verwirft, was noch in der Warteschlange der Verbindung liegt (`abort_output()`); was Direwolf schon hat (höchstens `max_outstanding` Frames), geht noch hinaus. Über Telnet wirkt `A` nicht (dort wird sofort geschrieben). Nicht betroffen: Clients (`//CLIENT`), der Chat, `DICT` und Befehle, die den Zustand wechseln (`S`, `C`). Technik: `Session.out()` sammelt während eines Befehls, `_page_end()` stellt den Hinweis voran; `PAGE_LINES` in `session.py`.

---

## 4. Architektur

```
                        ┌──────────────────── TinyBox (Python, asyncio) ────────────────────┐
 Funk ─ Direwolf ─AGW──►│ AGW-Adapter ─┐                                                    │
       (127.0.0.1:8000) │              ├─► Session/Commands ─► MessageService ─► Store      │
 Telnet (Test) ────────►│ Telnet-Adapt.┘                          │   ▲         (SQLite)   │
                        │                                         ▼   │                    │
 Sysop-Konsole ────────►│ Sysop ────────────────────────────► Event-Bus                     │
                        │                                         │   ▲                    │
                        │                                         ▼   │                    │
 MQTT-Broker(s) ◄──────►│                                     MQTT-Adapter (später)          │
                        └───────────────────────────────────────────────────────────────────┘
```

**Kernidee für MQTT:** Keine Quelle schreibt direkt in die Datenbank. Funk, Telnet, Sysop und später MQTT gehen alle über den **MessageService**. Der prüft die Eingaben, speichert und meldet Ereignisse an einen internen **Event-Bus**. Der MQTT-Adapter muss sich dann nur am Bus anmelden. Am Kern ändert sich dafür nichts.

Interne Ereignisse (ab v1 vorhanden, auch ohne MQTT):

| Event | Auslöser |
|---|---|
| `message.created` | neue Nachricht gespeichert (egal aus welcher Quelle) |
| `message.read` | Nachricht gelesen |
| `message.deleted` | Nachricht gelöscht |
| `session.connected` / `session.disconnected` | Verbindung auf- oder abgebaut |
| `message.edited` | Nachricht geändert (`E n`, Eingang mit `Replace:`) |
| `message.expired` | Nachrichten abgelaufen und gelöscht (Aufräumroutine) |
| `chat.joined` / `chat.left` / `chat.message` | Chat-Boards (Abschnitt 2a) |

**Adapter heute (Rev. 4):** AGW (Funk), Telnet (Test), Sysop-Konsole, Sysop-Web-GUI, Eingangsordner (`inbox`), brocast und das Forward-Modul (nur bei `[forward] enabled = yes`). Der Chat läuft über den `ChatHub` neben dem MessageService. MQTT fehlt noch (M5).

### 4.1 Direwolf über das AGW-Protokoll

Direwolf übernimmt den AX.25-Connected-Mode (Layer 2). TinyBox verwendet folgende Frames:

| Kind | Richtung | Zweck |
|---|---|---|
| `X` | → DW | Mailbox-Call registrieren |
| `C` | ← DW | eingehende Verbindung |
| `D` | ↔ | Nutzdaten |
| `d` | ↔ | Trennen |
| `Y` | → DW | Anzahl ausstehender Frames (Flusskontrolle) |
| `R` | → DW | Version abfragen (Startprüfung) |

Da Direwolf immer mitläuft, prüft TinyBox beim Start die AGW-Verbindung. Geht sie verloren, verbindet TinyBox sich automatisch neu (Backoff). Die Sitzungen gehen dabei verloren, die Daten nicht.

### 4.2 Test ohne Funk

Telnet-Testport auf `127.0.0.1`. Er nutzt dieselbe Sitzungslogik, das Rufzeichen wird beim Login abgefragt.

---

## 5. Konfiguration: `tinybox.conf`

INI-Format (Python `configparser`, Standardbibliothek). Die vollständige, kommentierte Vorlage ist `tinybox.conf.example` im Repo. `tinybox.conf` selbst ist PC-spezifisch und liegt nicht im Repo.

| Abschnitt | Inhalt |
|---|---|
| `[station]` | Mailbox-Call, Sysop-Call, `sysop_via_radio`; neu `haddress` (z. B. `OE3XTC.#NOE.AUT.EU`) und `qth` für die R:-Zeilen |
| `[direwolf]` | AGW-Host und -Port, Funkkanal, Reconnect, `paclen`, `max_outstanding`; Verbindungsqualität `quality_*` (Abschnitt 14) |
| `[mailbox]` | Begrüßung, `third_party`, `max_users`, Größen, Idle-Timeout, `bulletin_expire_days` (0 = nie löschen) |
| `[telnet]` | Testport, nur Loopback |
| `[web]` | Sysop-Web-GUI, nur Loopback, Port 8080 |
| `[console]` | Sysop-Konsole und Monitor |
| `[storage]`, `[logging]` | Datenordner; Loglevel, optional Logordner |
| `[brocast]` | Datei für `DICT`, Bulletins an brocastd melden (Abschnitt 6b) |
| `[inbox]` | Eingangsordner für Skripte (Abschnitt 6c) |
| `[chat]`, `[chat_boards]` | Chat ein/aus, Verlauf, Zeilenlänge; die festen Boards (Abschnitt 2a) |
| `[forward]` | Modul ein/aus (Standard `no`), `bid_days`, Aliase, eingehender TCP-Port (Abschnitt 13) |
| `[partner.CALL]` | je Partner-Mailbox: Transport `agw`/`tcp`, Funk-Call, Digis, Login, Passwort, Routen, Gebiete, Protokoll, Timeout; Zeitplan `auto`, `interval_min`, `window`, `retry_min` |
| `[mqtt]` | vorbereitet, Standard `no` (M5) |

To: WX                        Pflicht: Bulletin-Ziel
Subject: Wetter 19:00         Pflicht: Betreff (max. 60)
From: OE3GAS                  optional, Standard: Sysop-Rufzeichen
Replace: geosphere-wetter     optional: gleichnamiges Bulletin aktualisieren (gleiche Nummer)
Valid: 6h                     optional: 90m / 6h / 2d, danach gelöscht

Text ...
```

- Nur `*.txt` (Skripte schreiben `*.tmp` und benennen dann um), Dateien jünger als 2 s werden noch nicht angefasst.
- Erfolgreich → `eingang\erledigt\<Zeitstempel>_<Name>`, abgelehnt → `eingang\fehler\` plus `.err` mit dem Grund.
- `Replace:` aktualisiert ein vorhandenes Bulletin mit gleicher Nummer, es gilt wieder als ungelesen (Ereignis `message.edited`, brocast: neue Revision derselben Seite).
- `Valid:` setzt ein eigenes Ablaufdatum; die Aufräumroutine läuft jetzt jede Minute und meldet `message.expired` (brocast zieht die Seite zurück).
- Datenbank: Schema 2 mit den Spalten `replace_key` und `expires`; ältere Datenbanken werden beim Start automatisch ergänzt.
- Kommt per `Replace:` exakt derselbe Inhalt noch einmal, verlängert TinyBox nur die Gültigkeit (kein „ungelesen“, keine neue brocast-Revision).

**Erste Lieferanten: GeoSphere-Skripte** (Windows-Aufgabenplanung, `geosphere_aufgaben_einrichten.bat`)

| Skript | Takt | Bulletin |
|---|---|---|
| `geosphere_station.py --tinybox` | stündlich xx:05 | an `WX`, `Replace: geosphere-wetter-11334`, `Valid: 2h`, mit `Brocast:` (Wetterseite `typ wx`, Abschnitt 6d) |
| `geosphere_station.py --region --tinybox` | stündlich xx:05 (**ersetzt die Zeile oben seit 13.10.2026**) | 24 Stationen Wein-/Waldviertel (`REGION` im Skript, 2 API-Abrufe): je Station ein Einzelbericht wie Schöngrabern (`Replace: geosphere-wetter-<ID>`, eigene `wx`-Seite = 1 Frame, grafisch im Listener) **und** der Gesamtüberblick „Wetter Wein- & Waldviertel“ (`Replace: geosphere-wetter-region`, Text ~1,9 kB nur in der Mailbox; `Brocast:` Tabellenseite `typ text`, Blöcke `table` mit `sc -1` und Spaltenbedeutung `n`, Abschnitt 6g; 3 Frames gepackt). Funkmenge je Karussell-Lauf: 24 + 3 Frames. **Nicht** `--einzel-ohne-brocast` (Variante B vom 13.10.2026, zurückgenommen 14.10.2026): die TinyBox sendet *jedes* Bulletin, ohne `Brocast:`-Seite ging der Mailbox-Text (≈ 600 B, 2–3 Frames) statt der `wx`-Seite (1 Frame) über Funk, und der Listener zeigte nur Text (Fehlerbild vom 14.10.). Der Schalter bleibt im Skript, taugt aber nur, wenn die Einzelbulletins gar nicht an brocast gehen sollen. |
| `geosphere_warnungen.py --tinybox` | alle 15 min | an `WARN` nur bei Änderung, gültig bis Warnungsende; bei vorzeitiger Aufhebung „Entwarnung“ (3 h) |
| `geosphere_prognose.py --locator JN88BN --tinybox` | alle 3 h um xx:35 (00:35, 03:35 …) | Prognose 48 h in 3-h-Schritten je Locator an `WX`, `Replace: geosphere-prognose-<LOC>`, `Valid: 4h`, mit `Brocast:` (Prognosetabelle, 2 Frames gepackt, im Listener als Meteogramm; Abschnitt 20) |

Bulletins an `WARN` werden in brocast zu Warnseiten (`[brocast] alert_destinations`, Rubrik Notfunk) und im Listener immer angezeigt und hervorgehoben.

### 6d. Kopfzeile `Brocast:` – eine Datei, zwei Zielsysteme

Ein Skript kann zum Text eine fertige brocast-Seite mitliefern. Die Mailbox speichert und zeigt nur den Text; der brocast-Adapter reicht statt der Textseite die mitgelieferte Seite weiter. So bleibt TinyBox die einzige Drehscheibe (Skript → TinyBox → brocast), und `Replace:`, `Valid:` und Löschen gelten für beide Darstellungen.

```
To: WX
Subject: Wetter Schoengrabern 18:00
Replace: geosphere-wetter-11334
Valid: 2h
Brocast: {"typ":"wx","dat":{"temp":21.3,"hum":31,"qff":1028.5},"blk":[{"k":"series","u":"Cel","sc":-1,"dt":7200,"v":[100,71,60]}]}

  Temperatur     21.3 °C
  ...
```

- **Inhalt:** ein JSON-Objekt in **einer** Zeile, genau im Format der brocast-Ingest-API (Namen statt Nummern, wie `PUT /pages/...`). Pflicht ist `typ`. Höchstens 8 kB.
- **Prüfung im Eingang:** nur, ob es gültiges JSON und ein Objekt mit `typ` ist; sonst landet die Datei in `fehler\`. Die inhaltliche Prüfung macht brocastd.
- **Speicherung:** neue Spalte `brocast` in `messages` (Schema 3, ältere Datenbanken werden beim Start ergänzt). `Replace:` ersetzt auch die Seite; „gleicher Inhalt“ heißt gleicher Text **und** gleiche Seite.
- **Adapter:** Hat ein Bulletin eine Seite, wird sie gesendet. TinyBox ergänzt nur, was fehlt: `ti` (Betreff), `cat` (Rubrik aus dem Ziel), `exp` (wie bei Textseiten). `to` und `src` setzt TinyBox hier nicht, das entscheidet das Skript.
- **Tabellen (13.10.2026):** `sc` gilt auch für `table`-Blöcke und skaliert alle Zahlenzellen (wie bei `series`); Text bleibt Text. Ein Block muss in einen Frame passen, der Splitter packt Blöcke nur ganz – lange Tabellen daher in kleine Blöcke teilen (Kopfzeile `hdr` nur im ersten).
- **Rückfall:** Lehnt brocastd die Seite ab (z. B. Feld nicht im Dictionary), sendet der Adapter stattdessen die Textseite und schreibt eine Warnung ins Log. Ohne `Brocast:` bleibt alles wie bisher.
- In der Mailbox ist die Kopfzeile unsichtbar (Funkamateure lesen Betreff und Text).

### 6e. brocast-Aussendungen verkleinert (entschieden und umgesetzt 14.10.2026)

**Befund** (gemessen an den 18 Seiten, die der Listener auf PC1 am 12.10. empfangen hat: 35 Frames, 6 326 Bytes): nur 55 % davon waren Nutztext.

| Verschwendung | Anteil | Beispiel |
|---|---|---|
| Umschlag in **jeder** Unterseite (Titel 36 B, `src` 18 B, `to`+`cat`, `t`/`exp`/`dv`/`rev`/`typ`/`id`) | 40 % (2 514 B) | Seite 46 „PR Revival“: 8 × ≈ 90 B Umschlag für 778 B Text |
| Halb gefüllte Frames (der Splitter packt nur ganze Blöcke) | Füllgrad 74 % | Frames mit 138, 136, 105 B |
| Text unkomprimiert | 35–50 % | 778 B → 452 B |
| Karussell-Inhalt: alte Seiten so oft wie neue | 46 % der Frames | 10 Client-News-Seiten = 16 von 35 Frames |

Der AX.25-Kopf selbst (17 B, ≈ 8 %) ist kein Hebel: größere Frames als 256 B sparen kaum Zeit, kosten aber bei einem Bitfehler die ganze Seite und schließen Hardware-TNCs aus.

**Entschieden** (Seiten müssen über ein Terminal *nicht* lesbar sein, 13.10.2026):

1. **Frame-Format 2** (`[station] wire_format = 2`, Standard, `brocast/brocast/fragment.py`): Fragment 1 trägt den Umschlag, die folgenden nur `id`, `rev`, `sub`; der Inhalt (Blockliste) geht als **ein** Blob über Funk und die Frames sind randvoll. Die Formatnummer steht im hohen Nibble des Header-Bytes – ältere Listener lassen die Frames liegen (keine halben Seiten) und melden „neueres Format“.
2. **Kompression mit Preset-Wörterbuch** (`compress = yes`, `brocast/zdict/brocast-zdict-1.bin`, 32 kB, erzeugt mit `tools/build_zdict.py`): raw deflate, Wörterbuch auf beiden Seiten vorhanden, Generation im Frame, SHA-256 beim Start geprüft. Passt es nicht, wird unkomprimiert gesendet. brotli, zstd und unishox brachten im Vergleich keinen Vorteil, der eine zusätzliche Abhängigkeit rechtfertigt (zlib ist Standardbibliothek und wird für das Dictionary über Funk schon benutzt).
3. **Alterung im Karussell** (`aging = 24:120`): eine Revision, die älter als 24 h ist, wird nur noch alle 120 min wiederholt; `168:0` lässt sie ruhen, bis der Lieferant sie ändert. (Griff bis 25.10.2026 wegen eines Fehlers nicht; Vorgabe jetzt feiner, siehe Abschnitt 23.)
4. Unvollständige Seiten werden **nur im Arbeitsspeicher** gesammelt (15 min, höchstens 64) – kein Datenbankschreiben je Frame (offener Punkt 9).

**Rechnung** (1200 Bd, TXDELAY 300 ms, 4 Frames je Aussendung, 3 s Pause; „Dauer“ = Kanalbelegung mit Pausen):

| Seite | Format 1 | Format 2 | Format 2 + gepackt |
|---|---|---|---|
| 46 „PR Revival“ (778 B Text) | 8 Frames, 1 428 B, 15 s | 5 Frames, 968 B, 11 s | **3 Frames, 573 B, 5 s** |
| 42 „Was ist KISS Mode?“ | 5 Frames, 923 B, 11 s | 4 Frames, 752 B | **2 Frames, 431 B, 4 s** |
| Wetter Region (24 Stationen, `table`) | 5 Frames, 920 B, 11 s | 4 Frames, 769 B | **3 Frames, 598 B, 5 s** |
| Karussell-Lauf (18 Seiten) | 38 Frames, 7 123 B, 68 s | 36 Frames, 6 269 B, 58 s | **27 Frames, 4 585 B, 42 s** |
| … zusätzlich mit `aging` (alte News ruhen) | – | – | **≈ 13 Frames, ≈ 2,2 kB, ≈ 20 s** |

Dauerzustand vorher 113 s Kanalzeit je Stunde (3,1 %), nachher rund 40 s, mit `aging` unter 20 s. Nachrechnen: `py -3 tools\payload_report.py` (eigene Datenbank oder `test\*.json`).

**Noch offen (eigener Schritt, Dictionary v3):** feste Texte ganz aus den Seiten nehmen – `src` („GeoSphere Austria, TAWES (CC BY 4.0)“ = 40 von 202 B der Wetterseite) als Enum, Serien-Namen aus dem Parameter ableiten, Stations-ID statt `pos`, Regionsüberblick als Zahlenmatrix mit Stationsnummern statt Klartext-Tabelle. Messung dazu: Wetterseite 202 → 110 B, Regionsüberblick 598 → 306 B.

### 6f. Rubriken zwischen TinyBox und brocast abgleichen (entschieden und umgesetzt 14.10.2026)

**Befund:** Die Rubriken lebten an drei Stellen, die nichts voneinander wussten: `[rubrics]` in `tinybox.conf` (CR19, Liste mit Beschreibung), die Zuordnung Bulletin-Ziel → Dictionary-Rubrik (`[brocast] rubrics` und `DEFAULT_RUBRICS`) und das Enum `cat` im Dictionary (13 Einträge). Eine neue Rubrik des Sysops (z. B. `FUCHS = Fuchsjagd`) ging als Freitext in jeder Seite mit; der Listener legte sie erst mit der ersten Seite an („FUCHS (eigene)“, ohne Beschreibung), ein Abo vorab war nicht möglich, Opt-out-Zeilen blieben nach dem Ende liegen.

**Entschieden** (Variante 1 + 2a; stationslokale Nummern für die eigenen Rubriken – 2b – vorerst nicht):

1. **TinyBox → brocastd (lokal):** Der volle Abgleich `PUT /api/v1/pages/tinybox` trägt neben `pages` die Liste `rubrics` – `[{"name": "WX", "cat": "wx", "desc": "Wetter und Warnungen"}, …]` – alle **angenommenen** Rubriken aus `[rubrics]` in Conf-Reihenfolge, `ALL` immer zuerst, `cat` nach derselben Zuordnung wie bei den Seiten. brocastd **ersetzt** damit die Liste dieses Lieferanten (Tabelle `rubrics`): was fehlt, ist entfernt. Ohne `[rubrics]` (alles frei) geht eine leere Liste, dann gibt es keine Indexseite. Fehlt das Feld ganz, bleibt die Liste unverändert. Kein Neustart von brocastd; nach dem RESTART der TinyBox kommt alles mit dem ersten Abgleich. `GET /api/v1/rubrics` zeigt den Stand.
2. **Station → Listener (über Funk): Rubriken-Indexseite.** brocastd sendet die Rubriken aller Lieferanten als eine Seite `typ index` (im Dictionary seit v1 vorgesehen, Lieferant `brocastd`, Schlüssel `rubrics`, Titel „Rubriken“, Gültigkeit 7 Tage) im Karussell: `dat {0: [[Rubrik, Beschreibung], …]}`, Rubrik so wie die Seiten sie tragen (Dictionary-Nummer oder eigener Text), Beschreibung höchstens 60 Zeichen. Rohe Nummern im `dat`, weil das Dictionary für `index` noch keinen Typ definiert (kommt mit v3 unter denselben Nummern). Drei Rubriken ≈ 90 B, ein Frame. Neue Revision nur, wenn sich die Liste ändert; sonst gilt die Karussell-Alterung.
3. **Listener:** Die Indexseite ist keine lesbare Seite (wie `dict`), sondern füllt die Tabelle `station_rubrics` je Station. Daraus: Rubrikenübersicht und Abo-Matrix zeigen angekündigte Rubriken **mit Beschreibung** schon vor der ersten Seite (Tooltip „angeboten von …“), auch leere; Opt-out vorab möglich. Empfangslog: „Rubrikenliste der Station – übernommen / unverändert“.
4. **Entfernen:** Rubrik aus `[rubrics]` streichen → RESTART → Abgleich ohne sie → neue Revision der Indexseite. Im Listener lebt eine eigene Rubrik, solange eine Station sie ankündigt **oder** Seiten dazu vorhanden sind; eine zurückgezogene Rubrik mit Restseiten ist als „zurückgezogen“ markiert, die Seiten laufen normal ab (wie CR19 bei Bulletins). Fällt beides weg, verschwindet sie samt Opt-out-Zeile (Aufräumlauf). Stationen ohne Indexseite: wie bisher, Rubrik kommt und geht mit den Seiten.

Tests: `brocast/tests/test_rubrics.py` (Station, Funkweg Format 2, Listener), `tests/test_brocast_adapter.py`.

### 6g. Regionsübersicht grafisch und Umschalter Grafisch/Text (entschieden und umgesetzt 14.10.2026)

**Anlass:** Die Wetterseiten der Einzelstationen kamen als reine Textseiten an (Fehler in der Aufgabenplanung, siehe Tabelle oben), und der Gesamtüberblick war nur eine nackte HTML-Tabelle.

**Entschieden:**

1. **Spaltenbedeutung im Tabellenblock.** Der erste `table`-Block des Überblicks trägt neben `hdr` (Spaltentexte) den Block-Key `n` (Bezeichnung, Typ *any*) als Liste der Spaltenbedeutungen: `["name", "temp", "wdir", "wspd", "gust", "r24h"]` – die Namen sind die `dat`-Felder des Wetter-Dictionarys, alles andere (`name`) ist eine Textspalte. Folgeblöcke ohne `hdr` erben `hdr` und `n` wie bisher. Kosten: ≈ 35 B vor der Kompression, einmal je Seite. Terminal/Rohansicht ignorieren `n`. Keine Dictionary-Änderung (bleibt v2); die Zahlenmatrix mit Stationsnummern (6e, Dictionary v3) ist davon unberührt und ersetzt später nur die Zeilen, nicht die Semantik.
2. **Gruppenzeilen.** Eine Tabellenzeile mit genau einer Textzelle (`["Weinviertel"]`, `["Waldviertel"]`) ist eine Gruppenüberschrift. Plain-Tabelle: Zeile über alle Spalten; Grafik: Abschnittsleiste. ≈ 25 B.
3. **Listener, Wetterraster** (`app.js` `wxGrid`, Vorschau `brocast/mockup/wx-region-vorschau.html`): oben vier Kacheln mit den Extremen der Tabelle (wärmste/kälteste Station mit Spanne, stärkste Böe mit km/h und Bft, meiste Regen mit „an n von 24 Stationen“), darunter je Station eine Zeile: Temperaturbalken relativ zu min…max der Region (Farbe nach Wert: blau unter 0 °C, warm darüber, Spanne im Spaltenkopf), Windpfeil (zeigt wohin der Wind weht) mit Richtung, m/s und km/h, Böe mit Bft-Chip (ab Bft 6 hervorgehoben), Regenbalken relativ zum Maximum. Alles aus den gesendeten Zahlen gerechnet, nichts Zusätzliches über Funk. Die Spaltentexte kommen aus `hdr`, nicht aus dem Listener.
4. **Umschalter Grafisch/Text.** Knopf in der Seitenleiste (neben „Rohansicht“), nur bei Seiten mit grafischer Ansicht (`typ wx` mit `dat` oder Tabelle mit `n`). „Text“ zeigt die Wetterseite als schlichte Wertekarten und die Tabelle als HTML-Tabelle; die Wahl merkt sich der Browser (`localStorage brocast.graphic`, Standard grafisch). In der Teletext-Ansicht gibt es die grafische Darstellung nicht (Abschnitt 6h), der Knopf wird dort ausgeblendet.
5. **Titel:** „Wetter Wein- & Waldviertel hh:mm“ (Seite und Bulletin-Betreff), statt „Wetter Region“.

### 6h. Ansichten im Listener: Fließtext und Teletext (entschieden und umgesetzt 14.10.2026, CR37)

**Entschieden** (drei Ansichten waren zwei zu viel):

1. **„Mit Trennlinien“ entfällt.** Es bleiben `flow` (Fließtext) und `teletext`; ein gemerktes `parts` fällt auf Fließtext zurück. Die Umschaltung steht bei jeder Seite, auch bei einteiligen.
2. **Teile-Knöpfe nur im Teletext.** Im Fließtext stehen alle Teile untereinander, es gibt nichts zu blättern; dort bleibt nur die Umschaltung „Ansicht“.
3. **Teletext als echter Teletext-Bildschirm:** schwarzer Grund, eigene Pixelschrift, 40 Zeichen je Zeile, Zeilenabstand 1,65 (das enge Original-Raster liest sich am Bildschirm schlecht). Kopfzeile Rubrik (rotes Feld) + Station/Seitennummer, darunter der Titel in Gelb; Farben nach Bedeutung (Überschrift gelb, Hinweis/Tabellenkopf cyan, Alarm rot, fehlender Teil magenta). Der Bildschirm ist **immer Text** – Wetterkacheln und Wetterraster (6g) erscheinen als Werteliste bzw. einfache Tabelle.
4. **Schrift:** `brocast/brocast/web/teletext.woff` (5,8 kB, 228 Zeichen), erzeugt von `brocast/tools/build_teletext_font.py` aus DejaVu Sans Mono **Bold**, bei 10 px schwarz-weiß gerastert (fett = 2 Pixel breite Striche = der grobe Eindruck), jedes Pixel wird ein Quadrat im Umriss. Raster 7 × 13 Pixel in einem em von 16 Pixeln: bei `font-size: 32px` ist ein Schriftpixel genau zwei Bildschirmpixel (Handy 24 px), darum nur geradzahlige Größen. Ausgeliefert vom Listener selbst (`/teletext.woff`, Content-Type `font/woff`), weil die CSP `default-src 'self'` gilt und der Listener offline läuft. Lizenz: DejaVu (Bitstream-Vera) erlaubt abgeleitete Schriften unter anderem Namen – hier „brocast Teletext“.

Nur Anzeige im Listener; über Funk ändert sich nichts. Vorschau: `brocast/mockup/teletext-vorschau.html`.

### 6i. Teletext-Kopf und Bildseiten (entschieden und umgesetzt 14.10.2026, CR38)

1. **Zeilenabstand** im Teletext-Bildschirm auf 1,125 (18 von 16 Schriftpixeln): zwischen zwei Zeilen genau eine Zeichenhöhe. Nur geradzahlige Zeilenabstände, sonst sitzt jede zweite Grundlinie auf einem halben Bildschirmpixel.
2. **Schriftzug** nach der ORF-Teletext-Titelseite über jeder Teletext-Seite: Feld aus hellen Quadraten mit schwarzen Fugen, Buchstaben ausgespart, darunter die rote Linie. `brocast/tools/build_logo.py` → `brocast/brocast/web/brocast-logo.svg` (Liberation Sans Bold, Raster 6 Einheiten je Zelle, 91 × 20 Zellen), vom Listener selbst ausgeliefert.
3. **Bildseiten (Bildkonverter).** Entschieden: **keine neue Blockart, kein Dictionary v3** – ein Bild ist Text aus Mosaikzeichen (Sextanten `U+1FB00…U+1FB3B`, 2 × 3 Felder je Zeichen) in `pre`-Blöcken, wie ASCII-Art, nur sechsmal feiner.
   - Gemessen an einer 40 × 16-Zeichen-Seite (80 × 48 Punkte): roh 2 096 B, **gepackt 514 B, 3–4 Frames**. Eine eigene 1-Byte-Kodierung (6 Bit je Zeichen) käme auf 370 B; die 40 % Mehrkosten sind der Preis dafür, dass die Seite reiner Text bleibt – kein neues Dictionary, kein Sonderweg im Codec, und ältere Listener zeigen wenigstens Kästchen statt Unsinn. Die Kompression macht das möglich: von den vier UTF-8-Bytes je Zeichen sind drei bei allen gleich.
   - Der Listener erkennt ein Bild daran, dass ein Block nur aus Mosaikzeichen besteht; aufeinanderfolgende Bildblöcke setzt er wieder zusammen (ein Bild wird in Blöcke zu drei Zeilen zerlegt, damit auch im Frame-Format 1 jeder Block in einen Frame passt).
   - Die Mosaikzeichen sind in der Pixelschrift **gezeichnet** (7 × 12 Punkte je Zelle, Zeilenhöhe 0,75 em), nicht aus der Quellschrift gerastert – nur so stoßen die Felder fugenlos aneinander.
   - Werkzeug: `py -3 -m brocast bild <datei>` – **nur im station-Betrieb** (liest `brocastd.conf`). Standard ist die Vorschau samt Byte- und Frame-Zahl; `--senden` gibt die Seite an das laufende brocastd (Lieferant `bild`), `--tinybox ORDNER` legt sie als Bulletin in den TinyBox-Eingang (Kopfzeile `Brocast:`). Pillow nur dafür nötig.

## 6. MQTT (vorbereitet, Umsetzung später)

**Richtungen**

- **Eingang:** Nachrichten vom Broker werden in TinyBox abgelegt, z. B. Bulletins aus einem anderen System.
- **Ausgang:** TinyBox veröffentlicht Ereignisse wie neue Nachrichten, Status oder Connects.

**Topic-Entwurf** (`<root>` = `topic_root`)

| Topic | Richtung | Inhalt |
|---|---|---|
| `<root>/in/message` | Broker → TB | neue Nachricht (JSON) |
| `<root>/out/message` | TB → Broker | `message.created` (JSON) |
| `<root>/out/event` | TB → Broker | Connect/Disconnect/Read/Delete |
| `<root>/status` | TB → Broker | `online`/`offline` (retained, Last Will) |

**Nachrichtenformat (JSON)**

```json
{ "msgid": "uuid", "type": "B", "to": "ALL", "from": "OE3GAS",
  "subject": "...", "body": "...", "created": "2026-09-27T20:00:00Z" }
```

**Schon ab v1 im Datenmodell berücksichtigt**

- `origin` pro Nachricht: `radio`, `telnet`, `sysop` oder `mqtt`
- `msgid` (UUID) pro Nachricht, damit Duplikate erkannt werden (MQTT QoS 1 kann doppelt zustellen)
- Event-Bus und MessageService wie in Abschnitt 4

**Technik:** Bibliothek `paho-mqtt` (oder `aiomqtt` für asyncio). Das ist die einzige externe Abhängigkeit, und sie wird erst mit dem MQTT-Meilenstein nötig. Die Struktur erlaubt später mehrere Broker (je einen `[mqtt.xyz]`-Abschnitt).

**Sicherheit und Recht**

- TLS, Anmeldung am Broker, eigener Topic-Bereich (ACL am Broker).
- Eingehende Daten gelten als nicht vertrauenswürdig: Schema prüfen, Größe begrenzen, Rufzeichen prüfen, Rate-Limit.
- Was über MQTT hereinkommt, kann über Funk ausgelesen werden. Deshalb nur Absender mit gültigem Amateurfunk-Rufzeichen annehmen und eine Absender-Allowlist in der Konfiguration führen. Die Verantwortung liegt beim Sysop (AFV/AFG beachten: Inhalte, Drittverkehr).

---

## 7. Datenhaltung

`data_dir` (Standard `data\` neben der `tinybox.conf`)

- `tinybox.db` (SQLite, Schema 5, ältere Datenbanken werden beim Start migriert)
  - `messages(id, msgid, type, status, to_call, from_call, subject, body, size, origin, created, read_at, replace_key, expires, brocast, at_addr, bid, bid_kind, rlines, fwd, note)`
    - Schema 5 (Forwarding): `at_addr` (@-Adresse bzw. Verteilgebiet, leer = lokal), `bid` (max. 12 Zeichen, eindeutig), `bid_kind` (B echte BID, M erzeugte MID), `rlines` (R:-Zeilen, getrennt vom Text), `fwd` (leer, `$`, `F`, `H`), `note` (Grund fürs Halten)
  - `bids(bid, first_seen, origin)` – jede je gesehene BID, Aufbewahrung `bid_days`
  - `fwd_queue(msg_id, partner, state, changed)` – nur vom Forward-Modul befüllt; Zustände open, later, done, rejected
  - `chat_lines(id, board, call, text, created)` – nur Boards mit Verlauf
  - `jlog(call, first_seen, last_seen, count)`
  - `users(call, last_login)`
- Log-Datei optional: `[logging] log_dir` (Ordner muss existieren und beschreibbar sein),
  **eine Datei pro Tag** `tinybox-<JJJJ-MM-TT>.log`, reiner Text, feste Spalten mit
  Session-Nummer; ein Neustart hängt an, `keep_days` räumt Ältere weg. DEBUG je
  Komponente über `[logging] debug` bzw. im Betrieb mit `LOG DEBUG <komp>`.
  Entwurf und Leseregeln: CR32 in `docs/client-change-requests.md`

Nachrichtennummern laufen fortlaufend und werden nie wiederverwendet. Für ein Backup genügt es, den Ordner zu kopieren.

---

## 8. Projektstruktur

```
C:\Tinybox\                PC2 (Entwicklung); PC1: E:\Tinybox, per git pull
  PLANUNG.md  README.md  GIT-ANLEITUNG.md
  tinybox.conf              PC-spezifisch, nicht im Repo (Vorlage tinybox.conf.example)
  tinybox.bat  tinybox_dauerbetrieb.bat  start_alles.bat  runtests.bat
  tinybox\
    __main__.py             Start, Konfiguration laden, Adapter starten
    app.py                  verbindet die Bausteine
    config.py               tinybox.conf lesen und prüfen
    events.py               Event-Bus
    service.py              MessageService (Regeln, Rechte, BID-Prüfung)
    store.py                SQLite, Schema 5 mit Migration
    addressing.py           hierarchische Adressen, BID, R:-Zeilen
    session.py              Sitzungs-Zustandsautomat
    commands.py             Befehle
    chat.py  chatcmd.py     Chat-Boards (ChatHub, Befehl C, /-Kommandos, TBCHAT-Ereignisse)
    clientproto.py          Client-Protokoll TB1 (//CLIENT, //BOARDS, //RESEND)
    dictfile.py             Befehl DICT
    texts.py                englische Ausgabetexte
    logsetup.py             Logging: Tagesdatei, Spalten, Session-Kontext, LOG (CR32)
    adapters\
      agw.py                Direwolf/AGW (annehmen und anrufen)
      telnet.py             Testport
      sysop.py              lokale Konsole
      web.py                Sysop-Web-GUI (Dateien in tinybox\web\)
      inbox.py              Eingangsordner
      brocast.py            Bulletins an brocastd
      forward.py            Forward-Modul (nur bei [forward] enabled)
      mqtt.py               (später, M5)
    fwd\                    Forwarding: protocol, link (AGW/TCP), router, session
    web\                    HTML/CSS/JS der Sysop-Web-GUI
  tbclient\                 TinyBox-Client (Abschnitt 12): Start tbclient.bat, Vorlage tbclient.conf.example
    core.py  proto.py       Client-Logik, Ereignis-Parser
    links.py  radio.py      AGW (Funk, mit Rohframes) bzw. Telnet; AX.25/APRS-Symbole
    web.py  web\            Web-GUI (Messenger-Chat), emoji.json, aprs\ (Symbole OH7LZB)
  fwdsim\                   Forward-Testpartner, eigenständig (Abschnitt 13)
  brocast\                  brocast (eigenes Projekt, siehe brocast\README.md)
  geosphere_*.py            Wetter- und Warnungs-Skripte für den Eingangsordner
  dxfeed\                  DX-Cluster-Sammler und Tages-Digest (Abschnitt 16), dxfeed.conf.example
  tests\
  docs\                     W0RLI-Spezifikation, Fachartikel
  data\  logs\  eingang\     Betriebsdaten, nicht im Repo
```

Sitzungszustände: `COMMAND` → `SEND_SUBJECT` → `SEND_BODY` → `COMMAND`. Wird die Verbindung während `SEND_BODY` getrennt, wird die Nachricht verworfen.

---

## 9. Sicherheit & Betrieb

- Zeilenlänge und Nachrichtengröße begrenzen, Rate-Limit pro Call.
- Rufzeichen validieren (SSID 0–15), in Großbuchstaben speichern.
- SQL nur mit Parametern.
- Idle-Timeout.
- Telnet nur auf `127.0.0.1`.
- Kein Schreibzugriff außerhalb von `data_dir`.

---

## 10. Meilensteine

| # | Inhalt | Ergebnis |
|---|---|---|
| M1 ✅ | config, store, service, events, Befehle, Telnet (inkl. `E n`) | Mailbox lokal bedienbar – erledigt 27.09.2026, 15 Tests grün |
| M2 ✅ | AGW-Adapter mit Direwolf | Fertig, Funktest mit echtem Direwolf erfolgreich (27.09.2026) |
| M3 ✅ | Sysop-Konsole (W, MON, DISC, STATUS, SHUTDOWN), Monitor | Fertig 28.09.2026, 29 Tests grün. Seit 10.10.2026: `SHUTDOWN [s]` warnt alle Stationen vorher (Standard 60 s, `NOW`, `CANCEL`), auch der Knopf in der Web-GUI; Client-Sitzungen bekommen `//SYS <s> <Text>` und zeigen einen roten Hinweis |
| M3b ✅ | Sysop-Web-GUI (nur 127.0.0.1, Token, Host-Check, POST+Token für Änderungen), Light Theme mit kräftig dunkler Schrift | Fertig 28.09.2026 nach freigegebenem Mockup, 36 Tests grün |
| M3c ✅ | Befehl `DICT` (brocast-Dictionary als Text), `[brocast] dict_file` | Fertig 01.10.2026, 43 Tests grün |
| M3d ✅ | brocast-Adapter: Bulletins an brocastd melden (Abschnitt 6b) | Fertig 02.10.2026, 55 Tests grün |
| M3e ✅ | Eingangsordner für Skripte mit `Replace:` und `Valid:` (Abschnitt 6c) | Fertig 02.10.2026, 65 Tests grün |
| M3f ✅ | Kopfzeile `Brocast:` im Eingang, Seite statt Text an brocastd (Abschnitt 6d) | Fertig 03.10.2026 |
| M3g ✅ | Chat-Boards mit Aufbewahrung, Befehl `C`, /-Kommandos, Anzeige in Konsole und Web (Abschnitt 2a) | Fertig 04.10.2026 |
| M3h ✅ | brocast: Frame-Format 2 (Umschlag einmal, Inhalt gepackt), Preset-Wörterbuch, Karussell-Alterung (Abschnitt 6e) | Fertig 14.10.2026, 27 neue Tests grün; rund 45 % weniger Bytes, 42 % weniger Kanalzeit |
| M4 | Limits, Timeouts, Logging, Tests | Dauerbetrieb |
| P1 ✅ | **Major Fix** brocastd: kein Datenbank-Schreiben pro Funk-Frame, Sendeprotokoll abschaltbar (offener Punkt 9) | Umgesetzt 28.10.2026 (Abschnitt 26), Voraussetzung für Dauerbetrieb auf dem NanoPi (eMMC) |
| M5 | MQTT-Adapter (Ein-/Ausgang) | Anbindung an Broker |
| M6 (opt.) | Beacon (UI-Frame) | Mailbox kündigt sich an |
| F0–F7 | Forwarding-Modul (Abschnitt 13) | F1–F5 fertig (06.–08.10.2026), mit LinBPQ getestet, über Funk TinyBox ↔ TinyBox 07.11.2026; F0 teilweise. Als Nächstes F6 |
| C0–C3 | TinyBox-Client (Abschnitt 12) | Grundgerüst, Post-Hinweis, Chat-Broadcast (08.10.2026), Offline-Mailbox (10.10.2026). Funktest C3 offen |
| K1–K10 | KISS-Mode: eigener AX.25-Automat (v2.2) + `kisshub` (Abschnitt 15) | K1–K5 ✅, K7 ✅; Funktest PK-232 erfolgreich (14.10.2026, Gerät A, FW 13.SEP.95). K6, K8–K10 ruhen (15.10.2026): Tests und Zugriff auf weitere TNCs stehen aus |

---

## 11. Offene Punkte

1. ~~`third_party`~~ → entschieden: `yes` (Standard).
2. ~~Bulletins nach X Tagen automatisch löschen~~ → umgesetzt: `bulletin_expire_days = 30` (0 = nie).
3. MQTT: Welcher Broker (lokaler Mosquitto oder extern)? Wofür konkret, also woher kommen die Nachrichten und wer liest die Ausgänge?
4. MQTT-Eingang: Nur Bulletins oder auch Privatnachrichten an einzelne Calls?
5. Client-Web-GUI im WAN ohne Anmeldung (Abschnitt 12.1): Wer die Adresse kennt, kann unter dem Rufzeichen des Client-Betreibers senden (Chat, Post). Zu klären, wie das abgesichert wird, z. B. nur über VPN/HAMNET erreichbar oder ein einfaches Zugangstoken.
6. ✅ Direwolf: Wie viele Programme gleichzeitig am AGW-Port (`MAX_NET_CLIENTS`)? Relevant für PC2 mit TinyBox, brocastd und ggf. Client.
   Geklärt 28.10.2026: Das Original erlaubt fest **3** AGW-Clients und je `KISSPORT` 3 KISS-TCP-Clients (einkompiliert).
   Ein vierter Client hängt still: TCP-Connect gelingt, aber Direwolf antwortet nicht. Der Fork `oe3gas/direwolf-tinybox`
   (Zweig `tinybox`, Commit 28df0cc) erlaubt je **10** und meldet im Log, wenn alle Plätze belegt sind (Details in
   seiner `TINYBOX.md`). Am NanoPi mit dem Direwolf aus dem Paket bleibt es bei 3: TinyBox + brocastd = 2, ein Platz frei.
7. Forwarding über Funk ohne Aufsicht ist vermutlich eine Relaisfunkstelle mit Clubrufzeichen: mit Fernmeldebüro oder ÖVSV klären (F0). Bis dahin Forwarding nur über TCP/HAMNET.
8. Forwarding: OE-Hub-Partner finden, eigene Region für `haddress` mit dem Hub-Sysop abstimmen (F0/F6).
9. ✅ **MAJOR FIX (vor Dauerbetrieb auf dem NanoPi, eMMC 8 GB)** – umgesetzt 28.10.2026, siehe Abschnitt 26. Befund: brocastd schreibt bei **jedem Funk-Frame** mehrfach in die SQLite-Datenbank, jeweils als eigener Commit ohne PRAGMAs (Rollback-Journal, `synchronous=FULL`, also mehrere fsync pro Commit). Das ist verschwenderisch und verschleißt den eMMC. Gefunden am 07.10.2026 bei der Produktionsversion (`PRODUCTION.md`).
   - Jeder gesendete Frame wird über `_send` → `_receive(own=True)` (`brocast/brocast/daemon.py:79-84`) als eigener Empfang verbucht. Das sind die Commits `heard()` (`store.py:326`), `save_received`, `update_lpage` (`listener.py:191-258`) und `add_rxlog` (`store.py:347`). Pro Seite kommt noch `mark_sent` dazu (`carousel.py:225`).
   - Jeder empfangene Frame, auch fremde wie APRS, schreibt `add_rxlog` (`daemon.py:95-100`). Brocast-Frames schreiben zusätzlich `heard()` und die lpage-Commits.
   - Das Sendeprotokoll schreibt eine Zeile pro Frame (`txlog.py:46-59`). Es lässt sich nicht abschalten: Ein leeres `txlog_dir` wird zu `logs` (`config.py:138`), deshalb ist die Prüfung `is not None` in `daemon.py:65` toter Code.

   Vorschlag:
   - Pro Verbindung `PRAGMA journal_mode=WAL` und `synchronous=NORMAL`.
   - Flüchtige Daten nur im RAM halten: rxlog, „stations heard“, das Echo eigener Frames und `last_seen`, wenn eine Seite nur wiederholt wird. Höchstens gebündelt speichern, z. B. alle 10 min und beim Beenden.
   - Den Sendezeitplan (`mark_sent`) im RAM führen und nur gebündelt oder beim Beenden speichern.
   - Leeres `txlog_dir` = Sendeprotokoll aus.
   - Ziel: Die Datenbank wird nur bei echten Änderungen geschrieben, also bei neuen oder geänderten Seiten, Einstellungen und Bedienung.
   - Danach dieselben PRAGMAs für die TinyBox-Datenbank prüfen, die nur bei Login, Nachrichten und Chat schreibt (niedrige Priorität).

   Bis zum Fix bleibt die brocastd-Datenbank auf dem eMMC. Das Sendeprotokoll legt die Produktionsversion in den RAM (`/run/tinybox`).

   Offen bleibt nur der letzte Vorschlag: PRAGMAs für die TinyBox-Datenbank (niedrige Priorität).

---

## 12. TinyBox-Client (Konzept, Stand 07.10.2026)

Eigener Client mit Zusatzfunktionen, die es nur mit der TinyBox gibt. Getrennt von brocast.

**Grundsatz:** Der Client ist ein Zusatz, keine Voraussetzung. Alles Wesentliche funktioniert weiterhin mit jedem Terminalprogramm, über Digi und über Node.

### 12.1 Technik

- Python-Dienst mit **Web-GUI**, gleiche Bauart wie der brocastd-Listener.
- Die Web-GUI ist im **LAN und WAN** erreichbar (vor allem für den Chat am Handy), **ohne Anmeldung**, mit **mobiler Oberfläche**. Absicherung: offener Punkt 5. Die Sysop-Web-GUI der TinyBox bleibt davon unberührt auf 127.0.0.1.
- Anbindung an Direwolf über **AGW**, nicht KISS. Direwolf erledigt die AX.25-Verbindung (`C`/`D`/`d`). Der Client sendet UI-Frames (`M`/`V`) und liest alle Frames roh mit (`k`).
- Zu prüfen: Wie viele Anwendungen Direwolf gleichzeitig am AGW-Port zulässt (`MAX_NET_CLIENTS`), relevant für PC2 mit TinyBox + brocastd.

### 12.2 Handshake (umgesetzt für CHAT und UI)

- **Kennung zuerst (CR76, 07.11.2026):** Gleich nach jedem ausgehenden Connect (nicht Telnet)
  sendet der Client an jede Station `//TB? CLIENT v=<Version> caps=PROF,HEARD`. Eine TinyBox
  antwortet `//TB BOX v=<RELEASE> call=<Mailbox>` und ändert sonst nichts (Prompts und
  Profilfragen bleiben); ein anderer TBClient antwortet `//TB CLIENT v=… caps=…` (CR78);
  fremde BBSen/Nodes ignorieren die Zeile oder melden „unknown command“. Erst auf `//TB BOX`
  folgt `//CLIENT` – nur, wenn kein anderer Kanal schon eine TinyBox im Client-Modus hat
  (CR45 bleibt: eine TinyBox mit vollen Funktionen). Ältere TinyBoxen ohne `//TB?` erkennt der
  Client weiter am Welcome-Text. Eine TinyBox ruft nie selbst einen Client an.
- Der Client sendet nach dem Login `//CLIENT TB1 caps=CHAT,UI,SYNC,Z sym=/-` (`SYNC` und `Z` für die Offline-Mailbox, 12.8).
- Die TinyBox antwortet `//OK TB1 caps=…` mit dem gemeinsamen Funktionsumfang.
- Die TinyBox merkt sich je Sitzung, ob ein Client angemeldet ist.
- **UI-Modus nur bei direkter Verbindung:**
  - Hat die Sitzung einen Digi-Pfad (`via`), bleibt sie immer im I-Frame-Modus.
  - Der Client meldet sich nur für den UI-Modus an, wenn er die TinyBox selbst hört. Damit sind Node-Verbindungen abgedeckt.

### 12.2a „C 1“ landete im Chat (Fehler, behoben 14.10.2026)

**Befund:** Nach einem Client-Neustart erschienen `C 1`, `C 2` … als Chat-Zeilen im
Board – für alle sichtbar, und der Client selbst sah nichts davon. Die Kette:

1. Der Client wird beendet, **Direwolf hält den AX.25-Link**. Die TinyBox bekommt kein
   `d` und räumt die Sitzung nicht ab: sie steht weiter in `State.CHAT`.
2. Der neue Client verbindet. Direwolf meldet den bestehenden Link, die TinyBox verwirft
   das in `agw.py:_on_connect()` als `duplicate connect ignored` – **keine neue Sitzung,
   kein „Welcome to TinyBox“**.
3. Ohne Welcome greift im Client nach 6 s `_handshake_fallback()`: `//CLIENT` geht raus.
   `//`-Zeilen gelten auch im Board, also laufen `//OK`, `//BOARDS`, `//B …`, `//BEND`
   ganz normal durch.
4. Bei `//BEND` springt der Auto-Rejoin an. `self.board` ist im frischen Prozess `None`,
   also sendet `join()` den **Mailbox**-Befehl `C <n>` statt `/J <n>`.
5. Im Board ist jede Zeile ohne „/“ Chat-Text → `C 1` geht an alle. Der Client bleibt
   ohne Board, verwirft wegen `if not self.board` alle `#`-Ereignisse und sieht die
   eigene Zeile nicht – also klickt der Benutzer noch einmal.

**Korrektur (Server, keine Client-Änderung nötig):**

- `//CLIENT` auf einer Sitzung, die noch in einem Board steht, wird nach dem `//OK` mit
  `//IN` + `//WHO` beantwortet (`chatcmd.resync_client()`). Der Client weiß damit sofort,
  wo er ist, holt sich mit `last seq` den Anschluss und sendet gar kein `C <n>` mehr.
- **Ohne leave/join**: die Station hat das Board nie verlassen. Es gibt kein `-n`/`+n` an
  die anderen Mitglieder, nichts geht zusätzlich in die Luft, die Teilnehmernummer bleibt.
  `//WHO` enthält deshalb das eigene Rufzeichen mit. Angepasst wird nur das
  Empfangsfenster (`ChatHub.rebind()`), weil der neue Client andere Caps haben kann.
- Im Normalfall (frische Verbindung, `chat_board` leer) ändert sich **kein einziges Byte**.
- Zusätzlich fängt `chatcmd.handle()` eine Zeile `C` / `C <n>` **von einer Client-Sitzung**
  ab: gleiches Board → `//IN`, anderes Board → regulärer Wechsel. Damit können auch ältere
  Clients den Kanal nicht mehr mit `C 1` belegen. Für Terminal-Benutzer bleibt `C 1` im
  Board normaler Chat-Text.

**Tests:** `test_restart_in_board_gets_in_without_anybody_hearing_it` (Sequenzzähler
unverändert, Terminal und UI hören nichts), `test_mailbox_command_from_a_client_is_not_chat`.

---

### 12.3 Funktionen v1 (Reihenfolge = Umsetzungsreihenfolge)

| # | Funktion | Kern |
|---|---|---|
| C0 | Grundgerüst + Handshake | AGW-Anbindung, Verbinden, UI mitlesen, `//CLIENT` |
| C1 | Post-Benachrichtigung | Die TinyBox sendet ein UI-Frame „neue Post für <Call>“. Der Client zeigt einen Hinweis an, ohne verbunden zu sein. **Umgesetzt:** UI an `TBMAIL`, Text `OE3ABC 2 new` (Rufzeichen ohne SSID, Zahl ungelesener Privatnachrichten). Nur lokale Post (nicht zum Weiterleiten oder angehalten), höchstens ein Frame pro Rufzeichen und Minute; mehr Post in dieser Minute wird am Ende einmal mit neuer Zahl gemeldet. Abschaltbar: `[client] mail_notify = no`. Der Client wertet zusätzlich die Login-Zeile „You have n new message(s)“ aus. |
| C2 | Chat mit UI-Broadcast | Beitrag als I-Frame an die TinyBox, die ihn einmal als UI an `TBCHAT-x` sendet (x = Nummer des Boards in `[chat_boards]`, 1–15 = SSID). Client-Sitzungen im UI-Modus bekommen die Zeile nicht zusätzlich per I-Frame. Ab Board 16 gehen die Ereignisse per I-Frame. **Umgesetzt.** |
| C3 | Offline-Mailbox mit Delta-Sync | Neue Nachrichten/Bulletins komprimiert in einem Durchgang holen, offline lesen und schreiben, gesammelt senden, nach Abbruch fortsetzen. **Umgesetzt (10.10.2026)**, Protokoll in 12.8 |

### 12.4 Chat-Frame (entschieden 08.10.2026: lesbarer Text)

```
Ziel:   TBCHAT-x        Quelle: <TinyBox-Call>     PID: 0xF0
Info:   lesbarer Text, Folgenummer hexadezimal (1–2 Zeichen)
```

| Typ | Info-Feld | Beispiel |
|---|---|---|
| Beitrag | `#<nr> <Call>: <Text>` | `#4F OE3GAS: Servus, Wetter passt :+1` |
| Betreten | `#<nr> +<Tn> <Call> [<APRS-Symbol>]` | `#50 +2 OE3GAS /-` – Tn = Teilnehmernummer im Board (CR33; alte Clients: `+OE3GAS /-`) |
| Verlassen | `#<nr> -<Tn>` | `#51 -2` (alte Clients: `-OE3GAS`) |
| Symbol | `#<nr> =<Tn> [<APRS-Symbol>]` | `#53 =2 /k` (alte Clients: `=OE3GAS /k`) |
| Qualität | `#<nr> %<Tn> <Balken> …` | `#54 %1 5 2 4 3 ?` (alte Clients: `%OE3GAS 5 …`) |
| Statistik | `%Q <Tn> <14 Werte>;…` | ohne Folgenummer, nur NUM-Clients, siehe 14.6 |
| Reaktion | `#<nr> <Call> *<Bezug-nr> <Emoji>` | `#52 OE3TEC *4F :+1` |
| System | `#<nr> !<Text>` | `#53 !Board schließt um 22:00` |
| Bild-Upload läuft | `#<nr> ^<Call> <Größe>` | `#54 ^OE1ABC 50` – einmal beim Start, Fortschrittsbalken im Client (CR30) |
| Kommentar | `#<nr> <Call>: ~^<Bezug-nr> <Text>` | `#55 OE3GAS: ~^4E Ich bin QRV` – Bezug auf Ereignis 4E (CR31) |
| Beitrag mit Bild | `#<nr> <Call>: ~#<Hash 6 hex><Größe 2 hex><BlurHash> [Text]` | `#54 OE3GAS: ~#a1b2c350BjElSA\|nsR,x$0n~ Blick vom Berg` (CR12, 12.10) |

- Keine Steuerbytes: Mithörer mit Terminalprogramm oder Direwolf lesen den Chat ohne Client mit.
- Keine Version im Frame; Client und TinyBox tauschen sie beim `//CLIENT`-Handshake aus (12.2).
- Emojis und Avatare: siehe 12.6.

- Der Client erkennt Lücken an der Folgenummer und fordert über seine Sitzung nach (`//RESEND <Board> <von>-<bis>`). Die Antwort kommt nur an ihn, per I-Frame.
- Teilnehmer mit Terminalprogramm sowie Verbindungen über Digi oder Node bekommen die Zeilen wie bisher einzeln per I-Frame.
- Voraussetzung erfüllt: Der Chat-Code ist seit Commit 33c2259 im Repo (Abschnitt 2a).
- Gelöst: Die TinyBox hält je Board die letzten 256 Ereignisse im Speicher, `//RESEND` (höchstens 64 auf einmal) bedient sich dort – auch bei Live-Boards.

**Umgesetztes Client-Protokoll (TB1)** – Steuerzeilen per I-Frame, nur für Client-Sitzungen (ohne Prompt):

| Richtung | Zeile | Bedeutung |
|---|---|---|
| C → T | `//CLIENT TB1 caps=CHAT,UI sym=/-` | Anmeldung; UI nur bei Funk-Sitzung, `sym` nur wenn im Client gewählt |
| T → C | `//OK TB1 caps=…` | gemeinsamer Funktionsumfang |
| C → T | `//BOARDS` | → `//B <n> <Board> <keep> <User> <Beschreibung>` … `//BEND` |
| C → T | `C <n>` bzw. `/J <n>` | Board betreten bzw. wechseln |
| T → C | `//IN <n> <Board> <keep> <letzte Nr.>` | Board betreten |
| T → C | `//H <Unixzeit> <Call>: <Text>` | Verlaufszeile |
| T → C | `//WHO <Call>[=<Symbol>] …` | wer schon da ist; mit Cap `NUM`: `//WHO <Tn> <Call>[=<Symbol>] …` (CR33) |
| C → T | `/R <Nr.> <Emoji-Code>` | Reaktion (geht auch vom Terminal) |
| C → T | `//RESEND <a>-<b>` | fehlende Ereignisse nachfordern |
| C → T / T → C | `/Q` / `//OUT <Board>` | Board verlassen |

- **Reihenfolge:** Ein UI-Frame geht sofort hinaus, I-Frames warten in der Sendewarteschlange. Das UI-Frame des eigenen Betretens kann deshalb vor `//IN` ankommen; der Client hält solche Ereignisse bis `//IN` zurück.
- **APRS-Symbol eines Teilnehmers:** Symbol aus der Betreten-Meldung (seine eigene Wahl) vor gehörter APRS-Bake. Ohne gewähltes Symbol sendet der Client keins (0 Byte), dann zählt die Bake.

### 12.5 Bezug zum Forwarding

- Client und Forward-Modul sind getrennt. Ein Client ist ein User und meldet sich mit `//CLIENT` an, eine Partner-Mailbox mit ihrer SID. Die Partnerliste (`[partner.CALL]`) entscheidet, wer Forward-Sitzungen bekommt.
- Wiederverwendbar aus F2: ausgehender AGW-Connect (`AgwAdapter.connect`) und die Link-Abstraktion (`tinybox/fwd/link.py`).
- C3 (Delta-Sync) braucht eindeutige Kennungen je Nachricht. Dafür eignen sich `msgid` bzw. die BID aus Schema 5.

### 12.6 Chat-Oberfläche im Messenger-Stil (Stand 08.10.2026)

Der Chat im Client sieht aus wie ein heutiger Messenger: Avatare, Sprechblasen, Emojis. **Grundsatz: Alles Optische entsteht lokal im Client, über Funk geht nur das Nötigste.** Bei 1200 Bd zählt vor allem die Zahl der Frames (jeder UI-Frame hat ≥ 16 Byte Kopf plus TXDelay), erst danach die Bytes.

**Was über Funk geht – und was nicht**

| Element | Über Funk | Umsetzung |
|---|---|---|
| Avatar | nein | Lokal aus dem Rufzeichen erzeugt (siehe unten) |
| Autor | ja, als Text | Im TBCHAT-Frame sendet die TinyBox, also muss der Autor in die Nutzdaten |
| Zeitstempel | nein | Empfangszeit; beim Verlauf aus der BBS liefert die TinyBox die Zeit (connected) |
| Sprechblasen links/rechts | nein | Eigene Beiträge rechts, fremde links |
| „Tippt gerade …“, Gelesen-Häkchen | **bewusst nicht** | Wären je ein Frame pro Teilnehmer |
| Sticker | nur ein Kurzname | `[STK]CQ`, die Bilder liegen im Client (CR11) |
| Bilder | nur ein Verweis, 26–32 Byte | `~#<Hash><Größe><BlurHash>`; das Bild (max. 8 KB) geht einmal zur TinyBox, wer es sehen will, holt es per I-Frame (CR12, 12.10) |
| Folgenummer | ja, 1–2 Zeichen | Lückenerkennung, `//RESEND`, Bezug für Reaktionen |

**Nutzdaten als lesbarer Text** (Frame-Schema in 12.4): Terminal-User und Mithörer verstehen den Chat weiterhin. CBOR würde nur 3–5 Byte pro Frame sparen, Kompression bringt unter ~80 Byte nichts.

```
UI an TBCHAT-1:   #4F OE3GAS: Servus, Wetter passt :+1 ~1K
```

**Emojis – nie als Unicode über Funk** (👍 = 4 Byte, mit Hautton 8, Familien-Sequenzen bis 18 Byte):

- **Stufe 1, klassische Emoticons (2–4 Byte):** `:-)` `;-)` `:-D` `:-(` `:-P` `:-O` `<3` `:+1` `:-1` … (16 Stück, mit und ohne Nase; Tabelle in `emoji.json`). Der Client zeigt 🙂 😉 😄 🙁 😛 😮 ❤️ 👍 👎 … Terminal-User verstehen sie ohne Client. Seit CR28 (12.10.2026): Getippte Emoticons werden sofort zum Emoji, und jedes Emoji mit ASCII-Form geht als Emoticon mit Nase über Funk (😊 😀 → `:-)`, 😎 → `8-)`), nie als `~XY`.
- **Stufe 2, Code-Tabelle (3 Byte):** Escape-Zeichen + 2 Zeichen Base36, z. B. `~1K` = 📻; 1296 Plätze; `~~` = echte Tilde. Die Tabelle wird wie das brocast-Dictionary versioniert mit dem Client ausgeliefert. Grundstock funkerspezifisch (📻 📡 🔋 ⚡ ☕ 🍺 🌧 ☀️ 👋 …).
- Der Emoji-Picker bietet **nur** Emojis aus Stufe 1 und 2 an; jedes Emoji kostet damit höchstens 3 Byte. Ein eingefügtes unbekanntes Emoji wird nicht gesendet, der Client zeigt einen Hinweis.
- **Reaktionen** (👍 auf einen Beitrag, ab v1): eigener Typ mit Folgenummer + Emoji-Code, ca. 5 Byte Nutzdaten.

**Avatar – aus dem Rufzeichen, 0 Byte über Funk**

- Kreis mit **Präfix klein oben, Suffix groß darunter** (z. B. `OE3` / `GAS`). Im lokalen Chat haben fast alle dasselbe Präfix, unterscheidbar macht das Suffix.
- **Füllfarbe** aus einem Hash (FNV-1a) des Rufzeichens **ohne SSID und ohne /-Zusatz**, feste Palette mit 8 Farben, Schrift in der dunklen Stufe derselben Farbe. Jeder Client zeigt für jedes Rufzeichen dasselbe Bild. Kein Farbring.
- **APRS-Symbol als Plakette links oben** (frei wählbar): Über Funk geht wie bei APRS nur der 2-Zeichen-Code (z. B. `/-` Haus, `/>` Auto, `/y` Yagi, `/#` Digi). Herkunft in dieser Reihenfolge: eigene Wahl im Client → APRS-Bake, die der Client von diesem Rufzeichen gehört hat (0 Byte) → Code aus der Betreten-Meldung (2 Byte).
- Mit Plakette rückt das Präfix ca. 5 px nach rechts, **ohne Plakette steht es mittig**.
- Die SSID wird dadurch nützlich: OE3GAS (Haus) und OE3GAS-9 (Auto) haben dieselbe Farbe, aber verschiedene Symbole.
- Grafiken: aprs.fi-Symbolsatz von OH7LZB (github.com/hessu/aprs-symbols, PNG-Sprites 24/48/64/128 px), lokal im Client; Quellenhinweis auf der „Über“-Seite. Namen für die Auswahlliste aus dessen Symbol-Index (JSON).

**Entschieden (08.10.2026):** Escape-Zeichen für Stufe 2 ist `~`. Reaktionen kommen schon in v1.

### 12.6a Oberfläche am PC und Mailbox-Ansicht (entschieden 08.10.2026)

- **Eine Oberfläche, die nach Fensterbreite umschaltet:** ab ca. 1000 px drei Spalten, 700–1000 px zwei, darunter die Handy-Ansicht.
- **Links Navigation:** Chat-Boards mit Teilnehmerzahl, Post (Eingang, Ausgang, Gesendet), Bulletins nach Rubrik mit Zähler, Monitor, Einstellungen.
- **Chat am PC:** Mitte wie am Handy. Rechts die Teilnehmer im Board und die Stationen, deren APRS-Baken gehört wurden (mit „vor n min“).
- **Mailbox am PC:** Liste in der Mitte, Lesebereich rechts (Kopf mit Avatar, Von/An/Datum/Nummer, BID bei Bulletins; Text in Festbreitenschrift). Am Handy nacheinander: Ordner → Liste → Nachricht.
- **Offline (C3):** Knopf „Abgleichen“ mit Zeitpunkt des letzten Abgleichs; Gelesenes liegt lokal. Neue Nachrichten kommen in den **Ausgang** und gehen beim nächsten Abgleich hinaus, bis dahin bearbeitbar oder verwerfbar.
- **Abgleich:** Post immer vollständig; Bulletins nur aus abonnierten Rubriken (sonst dauert der Abgleich bei 1200 Bd zu lange).
- **Löschen:** eigene Post wird beim nächsten Abgleich auch in der TinyBox gelöscht; Bulletins nur lokal (sie gehören allen).

### 12.7 Später

Strukturierter Modus (CBOR statt Menütext), Formulare, kleine Dateien, Sysop-Fernverwaltung mit Challenge-Response (keine Verschlüsselung), zeitgesteuertes Abholen. Anzeige der Verbindungsqualität: jetzt eigener Abschnitt 14.

### 12.8 Offline-Mailbox: Abgleich (umgesetzt 10.10.2026)

**Zwei Abgleiche, getrennt gestartet** (geändert 10.10.2026): je ein Knopf „Sync“ in der linken Spalte bei „Mail“ und bei „Bulletins“; immer nur einer läuft. Neben dem Ordnertitel steht „Last sync“ des jeweiligen Abgleichs. Ist der Client nicht verbunden, verbindet er sich selbst, tritt keinem Board bei und trennt danach wieder.

*Mail:*
1. Ausgang senden (`//SEND`)
2. hier gelöschte eigene Post in der TinyBox löschen (`//KILL`)
3. hier gelesene Post melden, damit sie in der TinyBox den Status Y bekommt (`//READ`)
4. Köpfe der eigenen Post holen – immer alle, seitenweise (`//MLIST after= max=`)
5. fehlende Texte der Post holen

*Bulletins:*
1. Rubrikenliste holen (`//RUBRICS`)
2. Köpfe neuer Bulletins aus den abonnierten Rubriken holen (`//BLIST … max=`, je Rubrik ab der höchsten schon bekannten Nummer)
3. fehlende Texte der Bulletins holen

**Kanalschonend (nur über Funk):** Jede Anfrage holt nur etwa `chunk_bytes` (Standard 1024): kurze Texte gemeinsam, lange Texte stückweise (`//PART`), Köpfe seitenweise. Zwischen zwei Anfragen pausiert der Client `pause_sec` (Standard 5 s). Hört er in der Pause andere Stationen, wartet er, bis der Kanal 3 s frei ist (höchstens 30 s zusätzlich). Einstellbar in `tbclient.conf`, Abschnitt `[sync]`. Texte kommen ältere zuerst.

Alles wird sofort lokal gespeichert (`data/tbclient/mailbox.db`, SQLite). Bricht die Verbindung ab, setzt der nächste Abgleich dort fort: Vorhandene Texte werden nicht noch einmal geholt, bereits empfangene Stücke eines langen Texts behält der Client, solange er läuft. Ein zweiter Abgleich ohne Neues überträgt nur die Köpfe der eigenen Post.

**Kompression:** Über Funk (Cap `Z`) kommen Texte über 64 Byte LZHUF-komprimiert, im selben Format wie FBB-B1 (CRC-16 + Länge + Daten, `tinybox/fwd/lzhuf.py`). Die TinyBox schickt einen Text nur komprimiert, wenn er dadurch kleiner wird. Über Telnet gibt es kein `Z`.

**Protokoll** (Cap `SYNC`, jede Antwort endet mit einer End-Zeile):

| Richtung | Zeile | Bedeutung |
|---|---|---|
| C → T | `//MLIST [after=<Nr.>] [max=<n>]` | eigene Post (an mich oder von mir), älteste zuerst → `//M <Kopf>` … `//MEND <n> <noch übrig>` |
| C → T | `//RUBRICS` | → `//RU <Rubrik> <Anzahl> <höchste Nr.>` … `//RUEND`; mit `[rubrics]` (CR19) zusätzlich `//RU <Rubrik> : <Beschreibung>` und `//RU + ALL WX …` (wohin User schreiben dürfen, Reihenfolge des Sysops) |
| C → T | `//BLIST <Rubrik>=<ab Nr.> … [max=<n>]` | Bulletins dieser Rubriken mit höherer Nummer → `//M …` … `//MEND <n> <noch übrig>` |
| C → T | `//PART <Nr.> <ab Byte> <max. Bytes>` | Stück eines langen Texts (nur mit `Z`) → `//P <Nr.> <Z\|T> <ab> <gesamt> <n>` + n Bytes (Z = Stück der LZHUF-Daten, T = Stück des UTF-8-Texts) |
| C → T | `//GET <Nr.> …` (max. 20) | `//MSG <Nr.> <Zeilen>` + Zeilen, oder `//ZMSG <Nr.> <Bytes>` + Binärdaten, oder `//NOMSG <Nr.>`; Ende `//GEND`. Liest nicht (Status bleibt N) |
| C → T | `//SEND <P\|B> <An>[,<An>…][@<Adresse>] <Zeilen> mid=<Kennung>` + Betreff + Zeilen | → `//SENT <Nr.> [<Nr.> …]` oder `//ERR send <Grund>`; mehrere Empfänger (CR27): je eine Nachricht, Text einmal über Funk, höchstens 10 |
| C → T | `//KILL <Nr.> …` | → `//K <Nr.> ok\|<Grund>` … `//KEND`; nur Privatpost |
| C → T | `//READ <Nr.> …` | Status Y wie beim Lesen am Terminal → `//REND` |

Kopf: `<Nr.> <P|B> <N|Y> <Fwd|-> <Größe> <Von> <An> <@Adresse|-> <BID|-> <Unixzeit> <Betreff>`

- **Doppelt senden verhindert:** Jede Nachricht im Ausgang hat eine eindeutige Kennung (`mid=`). Geht `//SENT` verloren und der Client sendet sie noch einmal, antwortet die TinyBox mit der alten Nummer (`msgid = tbc-<Kennung>`).
- `//SEND` geht auch in einem Chat-Board; die Sitzung bleibt danach im Board.
- Was in der TinyBox gelöscht wurde (z. B. am Terminal mit `K`), blieb im Client als Archiv erhalten (bis 12.10.2026; mit dem Delta-Abgleich 12.9 verschwindet es auch im Client). Ein Text, den die TinyBox nicht mehr hat (`//NOMSG`), wird im Client entfernt.
- Gesendete Nachrichten legt der Client sofort im Ordner „Sent“ ab, ohne sie noch einmal zu holen.

**Oberfläche:** Ordner Inbox, Outbox, Sent; Bulletins je abonnierter Rubrik; „Rubrics…“ zum Abonnieren (Zahlen: in der TinyBox / im Client). Am Handy über ✉ oben: Ordner → Liste → Nachricht. Antworten zitiert die ersten 20 Zeilen. Beim Schreiben zeigt der Client Bytes und ungefähre Sendezeit bei 1200 Bd.

### 12.9 Delta-Abgleich: so wenig wie möglich in die Luft (entschieden und umgesetzt 12.10.2026, CR26)

**Befund:** Über Funk kostet jeder Wechsel Anfrage/Antwort mehr als die Bytes (TXDelay, Frame-Overhead, ACK, dazu `pause_sec` und Warten auf den freien Kanal). Der Abgleich nach 12.8 holte bei jedem Mail-Sync **alle** Köpfe der eigenen Post von vorn (30 Mails ≈ 2,7 kB in drei Seiten, auch wenn nichts neu ist) und bei jedem Bulletin-Sync die ganze Rubrikenliste samt Beschreibungen. Eine neue kurze Mail brauchte vier Wechsel.

**Grundsatz:** Erst die Zahl der Wechsel senken, dann die Bytes je Wechsel. Lesbar bleibt alles (Textzeilen, am Terminal nachvollziehbar); ein Binärprotokoll bringt gegenüber LZHUF über dem Text kaum mehr und kostet die Debugbarkeit.

**Stufe 1 – Delta statt Vollabgleich.** Die TinyBox führt einen Änderungszähler: jede Nachricht trägt `seq` (letzte Änderung: angelegt, Status N→Y, Forward-Flag, Inhalt) und `cseq` (letzte Inhaltsänderung: angelegt oder ersetzt). Gelöschte Nachrichten bleiben als Tombstone (`sync_gone`: Nr., `seq`, Typ, An, Von) erhalten, damit der Client erfährt, was weg ist. Die Spalten pflegen SQLite-Trigger – jeder Löschweg (Terminal `K`, Sysop-Web, Ablauf, Forward) ist damit abgedeckt. Der Client merkt sich die zuletzt gesehene `seq` je Abgleich. Ein Request für die Schritte 2–4 des Mail-Abgleichs:

```
//SYNC seq=<n> [k=<Nr.>,…] [r=<Nr.>,…] [max=<Bytes>] [want=<Bytes>]
→ //K <Nr.> ok|<Grund>        nur mit k= (Löschungen bestätigt)
  //M <Kopf>                  neu oder Inhalt geändert seit n (ganzer Kopf)
  //S <Nr.> <N|Y> <Fwd|->     nur Status/Flag geändert seit n (~12 Byte statt ~90)
  //D <Nr.> <Nr.> …           seit n gelöscht (oder nicht mehr sichtbar)
  //MSG/<//ZMSG> …            Texte neuer Nachrichten, älteste zuerst, bis want= Bytes (Stufe 2)
  //SYNCEND <noch übrig> seq=<m>
```

- „Nichts Neues“ = ein Wechsel, ~25 Byte hin, ~20 Byte zurück.
- `//READ` braucht keine eigene Antwort mehr (r= im selben Request); `//KILL` nur noch die winzigen `//K`-Zeilen.
- In der TinyBox gelöschte Post verschwindet jetzt auch im Client (`//D`) – bisher blieb sie als Archiv stehen. Lokal gelöschte, noch nicht bestätigte Post (todo kill) wird nicht zurückgeholt.
- `seq=0` = Vollabgleich (neuer Client). Kennt die TinyBox die `seq` des Clients nicht (DB neu aufgesetzt, Zähler kleiner), antwortet sie `//ERR seq`; der Client fängt bei 0 an.
- Mehr Köpfe als `max=` erlaubt: `<noch übrig>` > 0 und `seq=<m>` ist die höchste gelieferte `seq`, der Client fragt mit ihr weiter (Seiten wie bisher, nur bei Bedarf).

Bulletins analog, aber je Rubrik „was habe ich“ statt `seq` für Neues (Abonnements ändern sich unabhängig vom Zähler):

```
//BSYNC seq=<n> h=<Hash> ALL=120 WX=33 [max=] [want=]
→ //RU …                      nur wenn sich die Rubrikenliste geändert hat (Hash über Namen, Beschreibungen, Schreibrechte)
  //RN ALL=12 WX=3 …          Anzahl je Rubrik (eine Zeile, für „in der TinyBox / hier“)
  //M <Kopf>                  Bulletins der genannten Rubriken mit höherer Nr. oder seit n ersetztem Inhalt
  //D <Nr.> …                 in diesen Rubriken seit n gelöscht (abgelaufen, Sysop)
  //MSG/<//ZMSG> …            Texte bis want=
  //BSYNCEND <noch übrig> seq=<m> h=<Hash>
```

**Stufe 2 – kleine Texte gleich mit.** Der häufigste Fall ist „1–2 neue kurze Mails“; dafür hängt die TinyBox die Texte der neuen Nachrichten (älteste zuerst) an die Antwort, bis `want=` Bytes erreicht sind. Den Rest holt der Client wie bisher mit `//GET`/`//PART`. Ergebnis: der typische Abgleich ist **ein einziger Wechsel**. `want` = `chunk_bytes` minus Platz für die Köpfe.

**Stufe 3 – Bytes je Wechsel.** Mit Cap `Z` (Funk) und einer Antwort über 200 Byte schickt die TinyBox den ganzen Block zwischen Anfang und Endzeile als eine LZHUF-Einheit: `//ZSYNC <Bytes>` + Daten (darin alles Text, auch die Texte als `//MSG`). Köpfe wiederholen sich stark (Rufzeichen, Datum, `P N -`), Erfahrungswert 35–50 % Ersparnis. Darunter lohnt der LZHUF-Overhead nicht. Das Kopfformat bleibt unverändert (lesbar, ein Codepfad). Offen für später: `//SEND` mit komprimiertem Text (`//ZSEND`), lohnt erst ab ~300 Byte.

**Erwartung (30 Mails im Postfach):**

| Fall | vorher (12.8) | nachher |
|---|---|---|
| nichts Neues | 3 Wechsel, ~2,7 kB | 1 Wechsel, ~45 Byte |
| 1 neue Mail (400 Byte) | 4 Wechsel, ~3,2 kB | 1 Wechsel, ~330 Byte (Z) |
| 2 gelesen, 1 gelöscht gemeldet | +2 Wechsel | im selben Request |
| Bulletin-Sync, nichts Neues | 1 Wechsel, 200–500 Byte | 1 Wechsel, ~60 Byte |

**Kompatibilität:** neue Cap `SYNC2`. Alte Clients bekommen `SYNC` wie bisher (`//MLIST`, `//RUBRICS`, `//BLIST`, `//KILL`, `//READ` bleiben); ein neuer Client ohne `SYNC2` von der TinyBox fällt auf den alten Ablauf zurück. Schema der TinyBox-DB: Version 7 (`seq`, `cseq`, `sync_gone`, Trigger); bestehende Nachrichten bekommen `seq = cseq = Nr.`, der Zähler startet bei der höchsten Nr.

---

### 12.9a Bulletin-Abgleich lief im Kreis (Fehler, behoben 13.10.2026)

**Befund (Direwolf-Mitschnitt):** Nach dem ersten `//BSYNC` fragte der Client elfmal
hintereinander dasselbe (`//BSYNC seq=0 h=dd0b ALL=28 TBNEWS=39 WX=12 max=1024`), die
TinyBox antwortete jedes Mal mit demselben 977-Byte-ZSYNC-Block. Zwei Ursachen in
`_bsync` (`tinybox/clientsync.py`), die sich ergänzten:

1. Die Auswahl lautete `m.id > after[Rubrik] or m.cseq > seq`. Jede Nachricht hat
   `cseq ≥ 1`, bei `seq=0` war `cseq > 0` also **immer** wahr – die `after=`-Angaben des
   Clients waren wirkungslos, die TinyBox hielt alle Bulletins für neu.
2. Bei `<noch übrig> > 0` gab die TinyBox `seq=<n>` unverändert zurück. Es gab keinen
   Fortschrittsmarker: die nächste Seite war wieder die erste.

**Korrektur:** Die Treffer zerfallen in zwei Gruppen mit je eigenem Marker. Zuerst der
*Rückstand* (`id > after=`, nach Nr. sortiert) – er schrumpft, weil das `after=` des
Clients mit jeder Seite wächst. Dahinter die *geänderten* (`cseq > seq`, nach `cseq`
sortiert, und nur wenn `seq > 0`, denn bei `seq=0` weiß der Client nichts über den
Zähler und sein `after=` ist die Wahrheit). Endet eine Seite in den geänderten, ist
`seq=<m>` deren letzte `cseq`, sonst bleibt `seq` stehen. So rückt **jede** Seite genau
einen der beiden Marker vor, und der Austausch endet immer.

**Mail-Pfad geprüft:** `_sync` war in Ordnung – er zieht aus `changed_since(seq)`
(strikt `seq > n`), sortiert nach `seq` und liefert bei mehr Seiten `seq=<letzte Zeile>`.
Ein Test über mehrere Seiten belegt das (`test_sync_paging_ends`).

**Zusätzlich im Client:** `_delta_mail` und `_delta_bulletins` merken sich die gestellten
Anfragen. Kommt dieselbe ein zweites Mal, bricht der Abgleich mit einer Fehlermeldung ab,
statt weiter zu senden – ein Protokollfehler soll nie wieder den Kanal belegen.

**Nebenbefund:** Direwolfs `ERROR!!! Unknown APRS Data Type Indicator "#"` stammt von den
UI-Frames des Chatboards (`OE3GAS-1>TBCHAT-1:#0 …`). Direwolf versucht sie als APRS zu
lesen; rein kosmetisch, kein Handlungsbedarf.

---

### 12.9b Köpfe zuerst, Texte auf Abruf (entschieden und umgesetzt 15.10.2026, CR40)

- **Abgleich nach jeder Anmeldung** (Scope `login` = Mail + abonnierte Rubriken), `[sync] on_login` (Vorgabe yes). Auch der Knopf „Sync“ holt nur noch Köpfe.
- **Texte:** persönliche Mails bis `[sync] short_bytes` (Vorgabe 256 = 1 Frame ≈ 2 s bei 1200 Bd) kommen gleich mit – neue Cap `SHORT`, `//SYNC … want=<n> short=<n>`; die TinyBox hängt dann nur Texte bis `short` an. TinyBox ohne `SHORT`: `want=0`, kurze Texte mit einem `//GET`. Bulletins: `//BSYNC … want=0`, nie Texte. Alles andere holt der Client beim Anklicken (`POST /api/mail/fetch`, `//GET` bzw. `//PART`); ohne Verbindung „not connected“, die Anforderung wird verworfen. Ein Klick während eines Abgleichs geht zwischen zwei Wechseln hinaus.
- **Geordneter Abort** (`POST /api/mail/abort`): die Antwort auf die laufende Anfrage wird noch empfangen und gespeichert, dann geht keine Anfrage mehr hinaus (`seq` bleibt stimmig, der nächste Abgleich macht dort weiter). Kommt sie nicht binnen 30 s, harter Abbruch. Die Verbindung bleibt.
- **Meldung** zu Beginn (nach der ersten Antwort, dann ist der Umfang bekannt: `//SYNCEND <more>`, `//RN`) und beim Abort: was noch offen ist und wie lange es etwa dauert. Rate gemessen (Bytes vom Absenden bis zum letzten Byte der Antwort), vorher `[images] bytes_per_sec`; je Wechsel dazu `pause_sec`.
- **Frist je Rubrik** (TinyBox): `[rubrics] NAME = Beschreibung | Tage`, 0 = nie löschen, ohne Angabe gilt `[mailbox] bulletin_expire_days`. Damit ist auch die Zahl der Köpfe begrenzt, die ein neuer Client holt – kein Limit nötig.

### 12.10 Kleine Bilder im Chat (entschieden und umgesetzt 12.10.2026, CR12)

Über Funk geht so wenig wie möglich – jedes Feld wurde einzeln auf Bytes geprüft:

| Was | Über Funk | Bytes |
|---|---|---|
| Verweis in der Chat-Zeile | `~#` + Hash (6 Hex von SHA-256) + Größe (2 Hex, 64-Byte-Schritte) + BlurHash – ohne Trennzeichen | 26–32 |
| Bildmaße | **nicht.** Die Form steckt im BlurHash: sein erstes Zeichen nennt die Komponenten (3×2 = quer, 2×3 = hoch, 3×3 = quadratisch), daraus formt der Client den Platzhalter; die Pixel kommen mit dem Bild | 0 |
| BlurHash | 16 Zeichen (3×2, 2×3) bzw. 22 (3×3), statt der üblichen 28 (4×3) | 16–22 |
| Bildunterschrift | optional, nach einem Leerzeichen, Emojis wie im Chat | – |
| Upload | `//IMGPUT <hash> <bytes>` → `//IMGGO <hash> <have>` → die Bytes **am Stück** → `//IMGOK` – kein Stückeln, kein Ack (AX.25 ist gesichert) | ≈ 55 |
| Download | `//IMG <hash> [<offset>]` → `//I <hash> <offset> <total>` + Bytes am Stück | ≈ 35 |
| Beim Betreten | `//IN … img` (bzw. `img=<hex>` bei anderem Limit) nur in Boards mit Bildern | 4 |

- **Bild selbst:** der Browser macht WebP (JPEG als Rückfall), längste Seite höchstens 320 px, dann Qualität und notfalls Auflösung weiter runter, bis es unter das Limit passt (`[chat] image_max`, Standard 8 KB). Kein fester Rahmen, Form und Seitenverhältnis bleiben. TinyBox dekodiert nichts: Größe, Hash und Dateikennung (WebP/JPEG) werden geprüft, ein Exemplar je Hash.
- **Vor dem Senden** zeigt ein Dialog Pixelgröße, Bytes, Upload- und Ladedauer (aus `[images] bytes_per_sec` des Clients) und die Größenwahl klein/normal/groß – OK oder Abbruch. Der Client gibt die Bytes am Stück an Direwolf, das AX.25-Fenster taktet sie (12.10a; bis 13.10. stückweise mit Pause, `piece_bytes`/`pause_sec`).
- **Empfänger** sehen den BlurHash-Platzhalter mit „5.0 KB · ~1 min · tap to load“ und holen das Bild erst beim Antippen, mit Fortschrittsbalken; ein abgebrochener Download setzt beim Offset fort, ein abgebrochener Upload ebenso (`//IMGGO <have>`). Geladene Bilder liegen als Dateien im Client (`data/tbclient/images/`).
- **Terminal-Teilnehmer** lesen `[Image 5.0 KB - TinyBox client only]`, auch im Verlauf und als Reaktionsziel.
- **Nicht** in Live-Boards; pro Board abschaltbar mit `noimg` nach der Aufbewahrung (`TECH = 30d noimg …`); `image_max = 0` schaltet Bilder ganz ab (dann gibt es die Fähigkeit `IMG` nicht). Bilder nur über Funk (AGW), wie die Z-Kompression.
- **Aufbewahrung:** ein Bild wird gelöscht, wenn keine gespeicherte Chat-Zeile es mehr nennt (Aufbewahrung des Boards), nie in der ersten Stunde nach dem Upload. Ein halb hochgeladenes Bild bleibt eine Stunde im Speicher.
- **Der Rohblock darf nicht unterbrochen werden** (Fehler beim ersten Funktest, 12.10.2026): Die TinyBox nimmt nach `//IMGPUT` alles als Bilddaten. Rutscht eine Zeile dazwischen (getippter Text, Reaktion, vor allem das automatische `//RESEND`), zählt sie als Bilddaten mit, der Zähler ist zu früh bei null und die letzten echten Bildbytes landen als Chat-Zeile im Board. Darum hält der Client von `//IMGPUT` bis zur Übergabe der Bytes an Direwolf jede andere Zeile zurück (`ClientCore.hold_lines`) und sendet sie danach – Direwolf hält die Reihenfolge, was nach den Bytes übergeben wird, kommt nach den Bytes an. Zusätzlich: Zeitlimit für den Rohmodus in der TinyBox (120 s ohne Byte → `//ERR img timeout <bytes>`, Empfangenes bleibt für die Fortsetzung) und Chat-Zeilen mit Steuerzeichen werden verworfen, damit Binärmüll nie an alle geht.
- Mail-Anhänge: später extra (dann prüfen, was LinBPQ/FBB heute statt 7PLUS können).

### 12.10a Bildübertragung beschleunigt (entschieden und umgesetzt 13.10.2026, CR34)

**Befund:** Ein 8-kB-Bild brauchte rund 3 Minuten (≈ 45 B/s netto). Nicht Direwolf war der Engpass – dessen Vorgaben sind PACLEN 256, MAXFRAME 4 (v2.0), EMAXFRAME 32 (v2.2) –, sondern unser Code:

- Der Client schnitt jeden AGW-`D`-Frame fest auf 128 Byte (`links.py`). Direwolf macht aus jedem `D`-Frame eigene I-Frames und fasst nie zwei zusammen; PACLEN in der `direwolf.conf` teilt nur weiter. Also gingen 128er Frames, doppelt so viele wie nötig, jeder mit ≈ 20 Byte Kopf.
- Die TinyBox machte dasselbe (`paclen = 128`) und gab mit `max_outstanding = 4` nur 512 Byte je Sendung frei (Download).
- Der Upload schickte 256 Byte, schlief 2 s und wartete, bis das Stück bestätigt war (AGW `Y`): das Fenster war nie gefüllt, jede Sendung ein eigener Durchlauf mit TXDelay, ACK-Wechsel und Pause.

**Rechnung (1200 Bd, TXDelay 300 ms):** 256 B in 2 Frames + ACK + Pause ≈ 5,7 s → 45 B/s. Mit 6 Frames à 256 B je Sendung: ≈ 12 s Sendung + ≈ 0,7 s ACK → ≈ 115 B/s; 8 kB in ≈ 70 s, 4 kB in ≈ 35 s.

**Entschieden:**
- Client: `PACLEN = 256`; die Bytes gehen **am Stück** an Direwolf, die Chat-Zeile mit dem Verweis gleich dahinter (ein Wechsel gespart; die TinyBox liest sie nach dem letzten Bildbyte und prüft erst dann den Verweis). Fortschritt aus AGW `Y` (was Direwolf noch nicht bestätigt hat); solange die Zahl fällt, lebt die Übertragung, das 120-s-Limit läuft erst bei Stillstand. `piece_bytes`/`pause_sec` entfallen, alte Einträge in `tbclient.conf` werden ignoriert.
- TinyBox: `paclen = 256`, `max_outstanding = 6` (Beispiel-Konfiguration; auf PC2 in `tinybox.conf` nachziehen).
- **`direwolf.conf` auf beiden PCs** (PC-spezifisch, nicht im Repo): `PACLEN 256`, `MAXFRAME 4`, **`EMAXFRAME 6`**. Beide Enden sind Direwolf und handeln per XID AX.25 v2.2 aus, es gilt also EMAXFRAME – mit der Vorgabe 32 ginge ein 8-kB-Bild als **eine** Sendung von ≈ 60 s raus. 6 Frames ≈ 1,5 kB ≈ 12 s je Sendung, dann ACK und eine Lücke für andere (DCD, PERSIST, SLOTTIME) – schnell genug und kanalfreundlich. Bei gestörtem Link (`i_retry` im Q-Status hoch) eher PACLEN 200; v2.2/SREJ wiederholt nur den verlorenen Frame.
- Bildgröße: Ziel statt Limit. Der Dialog bietet **klein / normal / groß** (½ · `[images] target_bytes` (4 kB) · Board-Limit) mit 192 / 256 / 320 px längster Seite; vorher landete fast jedes Foto knapp unter 8 kB. Die Wahl merkt sich der Browser.
- Feintuning später, wirkt nur je Sendung: `TXDELAY 20–25`, `TXTAIL 5`, `DWAIT 0`. Der große Hebel bliebe 9600 Bd (flache Datenbuchse an beiden Geräten) – eigenes Projekt.

Messen: TinyBox-Log (`[logging] log_dir`) – Zeit von `//IMGPUT` (Monitor) bis `uploaded image … bytes`; Client-Dialog zeigt die Schätzung mit `bytes_per_sec` (Standard jetzt 100), nach den ersten Messungen anpassen.

## 13. Forwarding-Modul (optional)

Ausführliches Konzept mit Protokollen, Routing, Testfällen und Quellen: Claude-Doc „Tinybox als Packet-Radio-BBS: Forwarding-Konzept“ (https://claude.ai/code/artifact/ed861fd0-7519-4796-8f4b-8de6ab3fbd2a). Hier nur der Überblick.

**Grundsatz:** Das Nachrichtenmodell (Adresse, BID, R:-Zeilen) gehört zum Kern, der Austausch ist ein abschaltbares Modul (`[forward] enabled`). Ohne Modul bleibt TinyBox eine Standalone-Mailbox, `@`-Adressen gibt es dann nur für Bulletins.

**Zielbild in drei Stufen:** Standalone → Empfänger (Leaf an einem Hub, Standardroute WW) → Forwarder (mehrere Partner).

- **Protokolle:** SID-Austausch, FBB-ASCII-Batch (`FB`, `F>`, `FS +-=`, `FF`/`FQ`) als Hauptprotokoll, MBL/RLI-ASCII nach der W0RLI-Spezifikation (12.10.1998, `docs/w0rli/`) als Rückfall, später FBB B1 (LZHUF). TinyBox kündigt `FH$` an, ohne `M`.
- **Transport:** AX.25 über Direwolf/AGW (annehmen und anrufen, auch über Digis) und transparentes TCP (z. B. LinBPQ FBBPORT). Eingehender TCP-Port mit `Callsign:`/`Password:`-Login, standardmäßig aus.
- **Routing (BPQ-Modell):** Persönliche Post an den Partner mit dem besten Treffer von rechts, Bulletins an alle Partner mit passendem Verteilgebiet (erstes Element des @-Feldes). Nie zurück an einen Partner aus den R:-Zeilen. Ohne Treffer Status `H`.
- **Duplikate:** Tabelle `bids` mit Aufbewahrung `bid_days`. Umgang mit bekannter BID/MID je nach SID der Gegenseite (Entscheidung 06.10.2026, siehe Konzept-Doc).
- **brocast:** Fremd-Bulletins gehen nur ins Karussell, wenn `[forward] publish_to_brocast = yes` (Standard `no`).
- **Sysop:** `FWD` (Partner anzeigen), `FWD call` (Forward anstoßen), `FWQ` (Warteschlange), `HOLD n` / `REL n` (Nachricht halten / freigeben). Die Web-GUI zeigt im Kopf „Forward: n queued · n held“, mit den Partnern als Tooltip.

**Stand der Meilensteine**

| # | Inhalt | Stand |
|---|---|---|
| F0 | Vorbereitung: PLANUNG Rev. 4, LinBPQ als Testpartner, Mitschnitte echter Sitzungen, Hub-Suche, Rechtsfrage, Test-Tool fwdsim | teilweise: fwdsim fertig, PLANUNG Rev. 4 erledigt (07.10.2026). Offen: LinBPQ, Mitschnitte, Hub, Rechtsfrage |
| F1 ✅ | Kern: Schema 5, `addressing.py`, `SP/SB … @ … $BID`, `LB`/`LP`/`L@`/`L>`/`L<`, Lesekopf mit BID und R:-Zeilen, `E n AT`, Halten bei Schleife oder zu alter Nachricht | Fertig 06.10.2026 |
| F2 ✅ | Modul-Gerüst: `tinybox/fwd/`, `adapters/forward.py`, `[partner.CALL]`, AGW- und TCP-Verbindungen in beide Richtungen, SID-Aushandlung, Warteschlange, `FWD`/`FWQ` | Fertig 06.10.2026, 144 Tests grün. Angebotenes wird noch zurückgestellt (`=` bzw. Trennen), damit nichts verloren geht |
| F3 ✅ | Empfänger: ASCII- und FBB-Empfang, R:-Zeilen, Loop-Erkennung, BID/MID-Regel, Partner-Whitelist, Grenzen, `publish_to_brocast` | Fertig 07.10.2026, 168 Tests grün |
| F4 ✅ | Forwarder: Senden, Reverse Forward, Routing-Feinschliff, Scheduler, Prompt-Skip je Partner, `HOLD`/`REL`, Web-Anzeige | Fertig 07.10.2026, 191 Tests grün |
| F5 ✅ | B1 komprimiert (LZHUF, Resume) | Fertig 08.10.2026, 204 Tests; B1 mit LinBPQ in beide Richtungen bestätigt |
| F6 | Anschluss ans Netz: Leaf an einem OE-Hub über TCP/HAMNET, Probebetrieb | **als Nächstes** (Hub-Partner nötig) |
| F7 (opt.) | Mehrere Partner, White Pages, MQTT und Forwarding gemeinsam, Doku für Partner-Sysops | offen |

**F3 im Detail (07.10.2026)**

- Neues Modul `tinybox/fwd/receive.py`: entscheidet je Angebot (`+`/`-` bzw. `OK`/`NO`) und speichert über den MessageService (Origin `forward`, eigene R:-Zeile oben, Schleife oder zu alt → `H`).
- Abgelehnt werden: Typ T (NTS) und unbekannte Typen, ungültige Calls oder Adressen, zu große Nachrichten (Größe aus dem Vorschlag), dieselbe BID zweimal im Block, bekannte BIDs. Ausnahme nach W0RLI: Eine bekannte MID persönlicher Post von einer ASCII-Gegenseite ohne `M` wird angenommen und für den Sysop gehalten.
- Gespeichert wird erst nach vollständigem Empfang (Ctrl-Z oder `/EX`); ein Abbruch mitten in der Nachricht hinterlässt nichts. `'/EX'` im Text wird wieder zu `/EX`.
- Ruft TinyBox selbst an, holt sie die Post des Partners in derselben Sitzung ab (FBB: eigenes `FF`, ASCII: `F>`).
- Ein empfangenes Bulletin, das kein weiterer Partner braucht, ist einfach lokal (nicht gehalten).
- Korrektur in AGW-Adapter und TCP-Link: Das CR nach Ctrl-Z erzeugt keine leere Zeile mehr (sonst wurde die leere Zeile als Betreff der nächsten Nachricht gelesen).
- Grenzen je Sitzung: höchstens 500 Nachrichten, Text höchstens doppelte `max_msg_bytes` plus 8 kB, sonst Trennen.

**F4 im Detail (07.10.2026)**

- Neues Modul `tinybox/fwd/send.py`: Warteschlange je Partner, FBB-Vorschläge (`FB`, max. 5 je Block, max. 10 kB), W0RLI-S-Befehle (`$BID` nur bei echten BIDs), Nachricht mit Betreff (max. 79 Zeichen), R:-Zeilen, Leerzeile, Text, Ctrl-Z; eine Textzeile `/EX` geht als `'/EX'`.
- Antworten: `+`/`Y`/`H` → `done`, `-`/`N`/`R`/`E` → `rejected` (Partner hat sie schon), `=`/`L` → `later`. Ist für eine Nachricht kein Partner mehr offen, bekommt sie `F`.
- Beide Richtungen in einer Sitzung: FBB abwechselnd blockweise; ASCII: der Anrufer sendet seine S-Befehle und holt dann mit `F>` ab, der Angerufene bedient `F>` mit seinen S-Befehlen.
- Routing: Bulletins für ein fremdes Gebiet (z. B. `@FRA.EU`) gehen gerichtet wie persönliche Post zum besten Partner, `WW` und die eigenen Gebiete werden geflutet.
- Zeitplan je Partner: `auto` (ruft an, wenn Post wartet; Standard bei TCP `yes`, bei Funk `no` wegen offener Punkt 7), `interval_min` (zusätzlich regelmäßig abholen), `window` (z. B. `22:00-06:00`), `retry_min` (Pause nach Fehler und für „later“). Der Planer schaut alle 30 s und 2 s nach neuer Post.
- Prompt-Falle (T20): TinyBox wartet nach dem Connect zuerst auf die SID, Knoten-Texte davor mit `>` stören nicht. Eine eigene Skip-Option je Partner war deshalb nicht nötig.
- Korrektur in fwdsim: auch dort erzeugte das CR nach Ctrl-Z eine leere Zeile (Betreff der zweiten Nachricht ging verloren).

**Gegentest mit LinBPQ 6.0.25.41 (08.10.2026)** – LinBPQ in WSL auf PC2, Test-TinyBox `test\bpq\`, Mitschnitte in `tests/fixtures/`

- ASCII nach W0RLI funktioniert in beide Richtungen (TinyBox sendet, TinyBox holt mit `F>` ab).
- LinBPQ sendet `F` in der SID nur mit „Allow Binary“ und überträgt dann **immer komprimiert**, auch wenn die Gegenseite kein `B` ankündigt. Unkomprimiertes FBB gibt es mit LinBPQ also nicht: Partner-Einstellung `protocol = b1` oder `ascii`.
- Eine Nachricht mit kaputter @-Adresse wird jetzt angenommen und gehalten statt abgelehnt (ein `-` hieße für den Absender „schon da“).
- **B1 (nach F5):** TinyBox ↔ LinBPQ komprimiert in beide Richtungen, sowohl wenn TinyBox anruft (FBBPORT 8011) als auch wenn LinBPQ anruft (Login am Forward-Port 6411). Titel und Text mit Umlauten kommen unverändert an. Damit sind die Tore von F3 und F4 über TCP erreicht; über Funk siehe den Funktest vom 07.11.2026.

**Funktest TinyBox ↔ TinyBox (07.11.2026)** – PC1 (OE3XHU, `OE3XHU.#NOE.AUT.EU`, Direwolf + TS-790) und die Box auf der Hinteralm (OE3GAS-1, `OE3GAS.#NOE.AUT.EU`, Direwolf + IC-9700), 2 m, 1200 Bd, AGW, `protocol = b1`, beide Seiten `auto = no` (Sitzungen von Hand mit `FWD`)

- ✅ A: persönliche Nachricht PC1 → Hinteralm (Sitzung ca. 7 s, Verbindungsaufbau 1,5–2,5 s)
- ✅ B: Nachricht Hinteralm → PC1, Reverse Forward in der Sitzung von PC1
- ✅ C: Bulletin `@WW`; ✅ D: zweiter Durchgang bietet nichts an, nichts geht zurück (Split Horizon)
- ✅ E: Umlaute und große Nachricht (ca. 3 kB) unverändert
- ✅ G: Hinteralm ruft PC1 an (`25_OE3GAS` empfangen, 18 s)
- Offen: F – Abbruch mitten in einer B1-Übertragung und Fortsetzen (`!offset`) über Funk
- Beobachtung: PC1 lief vorher als OE3GAS-1 und kennt deshalb die BIDs `1_OE3GAS`–`24_OE3GAS` aus der eigenen Zeit. Angebote der Hinteralm mit diesen BIDs wurden korrekt als bekannt abgelehnt; die Hinteralm markiert sie dann als weitergeleitet (`F`), sie kommen also nie an. Kein Fehler, aber Merkposten: Wer das Mailbox-Rufzeichen wechselt, behält die alten BIDs bis `bid_days`.
- Dabei behoben: Web-GUI „New message“ nimmt `@ Adresse` und `$BID`; Lesen zeigt „To“ mit @-Adresse.

**F5 im Detail (08.10.2026)**

- `tinybox/fwd/lzhuf.py`: LZHUF in Python (FBB-Variante: 2-kB-Fenster, 60 Byte Vorschau), byte-identisch mit LinBPQs `lzhuf32.c` – geprüft gegen Testvektoren aus dem kompilierten C-Original (`tests/fixtures/lzhuf_vectors.json`). B1 = CRC-16 + Länge + Daten.
- `tinybox/fwd/b1.py`: Rahmen wie LinBPQ (SOH-Kopf mit Titel und Offset, STX-Blöcke à 250 Byte, EOT mit Prüfsumme); Text innen mit CR LF, R:-Zeilen vor dem Text.
- Link: ein Bytestrom, aus dem zeilenweise oder roh gelesen wird – kein Datenverlust beim Umschalten. AGW reicht Forward-Verbindungen die Rohbytes durch.
- Restart (B1): bricht eine Übertragung ab, hebt TinyBox das Empfangene auf (Tabelle `fwd_partial`, Schema 6, 2 Tage) und antwortet beim nächsten Angebot `!offset`; als Sender setzt TinyBox an diesem Offset fort. Nach 10 Versuchen wieder von vorn.
- SID mit `protocol = b1`: `[TINYBOX-…-B1FH$]`. B0 (Gegenseite nur `B`) ist eingebaut, aber ungetestet.
- Getestet: LZHUF gegen LinBPQ-C-Code, Rahmen, und Sitzungen TinyBox ↔ TinyBox in beide Richtungen inklusive Abbruch und Restart. fwdsim kann kein B1.

**Test-Tool fwdsim** (`fwdsim\`, Start mit `fwdsim.bat`, Bedienung in `fwdsim/README.md`): spielt die Partner OE3GAS (`#OOE`, Endstation und Hop) und DL0XTC (`#BAY`, nur über OE3GAS erreichbar, sendet nie auf Funk). TinyBox läuft im Test als OE3XTC (`#NOE`). Testfälle T01–T28 über TCP oder Direwolf, mit Fehlerinjektion. Gegen einen fwdsim-Stellvertreter laufen alle automatischen Fälle grün. Gegen die echte TinyBox (TCP) laufen seit F4 alle 24 automatischen Fälle grün (T01–T16, T18–T20, T24–T28); T21 (Neustart) ist als Unit-Test abgedeckt. Manuell offen: T17, T22, T23. Noch offen: fwdsim nimmt TCP-Anrufe ohne Login an.

---

## 14. Verbindungsqualität (Konzept, entschieden 10.10.2026)

Ziel: Qualität jeder Verbindung live messen und den Usern zeigen. Keine Langzeitstatistik, die Werte werden nach der Abfrage nicht mehr gebraucht.

### 14.1 Direwolf-Fork

Direwolf führt die AX.25-Protokollschicht selbst; über AGW sieht TinyBox keine Retries. Darum ein eigener Fork von `wb2osz/direwolf` (GPL v2), nur für die TinyBox, keine Weitergabe. Läuft auf Windows 11 (Bau mit MSYS2/MinGW + CMake).

**Grundsatz: der Fork zählt nur, er ändert kein Protokollverhalten.** Kleiner Patch, wenige Dateien, damit neue Direwolf-Versionen leicht nachzuziehen sind.

Geprüft am Quelltext (Stand `eda1383`, Mai 2026), alles in `src/ax25_link.c`, Zustandsblock `ax25_dlsm_t` pro Verbindung:

| Zähler | Wo einhängen | Bemerkung |
|---|---|---|
| `i_new` | `i_frame_pop_off_queue()` | neues I-Frame gesendet |
| `i_retry` | `invoke_retransmission()` und SREJ-Antwort (`ax25_i_frame` bei Zeile ~4230/4265) | I-Frame wiederholt |
| `bytes_new`, `bytes_retry` | dieselben Stellen | Nutzbytes netto / wiederholt |
| `rej_rx` | gibt es schon: `count_recv_frame_type[frame_type_S_REJ]` | Gegenstation hat einen unserer Frames verpasst |
| `rej_tx` | beim Senden von REJ/SREJ (`i_frame_continued()`, Zeile ~2996, bzw. `send_srej_frames()`) | wir haben einen Frame verpasst |
| `retry_rx` | `i_frame_continued()`, Zweig `ns != S->vr`, wenn N(S) schon empfangen war (liegt hinter V(R)) | Gegenstation wiederholt |
| `i_rx` | gibt es schon: `count_recv_frame_type[frame_type_I]` | empfangene I-Frames |
| `t1_exp` | `t1_expiry()` | T1 abgelaufen |
| `srt` | gibt es schon: `S->srt` | geglättete Round-Trip-Zeit (nur Anzeige) |

Abfrage über eine **AGW-Erweiterung**: neuer Frame-Typ `Q` (in Direwolf bisher unbenutzt), Ablauf wie das vorhandene `Y` (Anfrage → dlq → `ax25_link.c` → Antwort an den Client). Antwort: eine Textzeile mit allen Zählern seit Verbindungsaufbau. Normale AGW-Clients schicken nie `Q`, es bricht also nichts.

**Umgesetzt (11.10.2026):** Repo `oe3gas/direwolf-tinybox`, Zweig `tinybox` (`master` = unverändertes Original), lokal `C:\direwolf-tinybox`. Format und alle Schlüssel in `TINYBOX.md` dort, z. B. `v=1 state=3 i_new=21 i_retry=0 … srt=1.38 unack=4 age=2405`; ohne Verbindung `v=1 none`. Jeder AGW-Client darf fragen (nur lesend); Diagnose-Werkzeug `tinybox-tools\agw_q.py`. Windows-Programm per MinGW gebaut, unter Windows 11 mit echtem Funk getestet.

Der **Abbruchgrund** braucht keinen Fork: Direwolf meldet ihn schon im AGW-Frame `d` als Text (`*** DISCONNECTED RETRYOUT With …` statt `*** DISCONNECTED From Station …`). TinyBox wertet das heute noch nicht aus.

**Der Patch im Fork** (Stand `bfed142`, 2 Commits auf `master` = `eda1383`, Direwolf 1.8.2; 340 Zeilen in 9 Dateien, jede Stelle mit `TinyBox` kommentiert, Überblick `git diff master tinybox`):

| Datei | Änderung |
|---|---|
| `src/ax25_link.c` | `struct tb_stats_s` im Zustandsblock `ax25_dlsm_t` (Feld `tb`); Zähler an den Stellen aus der Tabelle oben: `i_new` beim Senden aus der Warteschlange, `i_retry` bei Wiederholung nach REJ/SREJ/T1, `rej_tx` beim Senden von REJ/SREJ, `retry_rx` wenn N(S) hinter V(R) liegt, `t1_exp` in `t1_expiry()`, `rnr_rx`; neue Funktion `dl_link_stats_request()` baut die Antwortzeile (`v=1 …`, ohne Verbindung `v=1 none`) – darf jeder AGW-Client abfragen, nicht nur der Besitzer der Verbindung |
| `src/ax25_link.h` | Prototyp `dl_link_stats_request` |
| `src/dlq.c`, `src/dlq.h` | neuer Warteschlangen-Typ `DLQ_LINK_STATS` mit Einreihfunktion, wie `DLQ_OUTSTANDING_FRAMES_REQUEST` für `Y` |
| `src/recv.c` | Verteiler: `DLQ_LINK_STATS` → `dl_link_stats_request` |
| `src/server.c` | `case 'Q'` beim Empfang vom AGW-Client (reiht ein), `server_link_stats_reply()` schickt Frame `Q` mit der Textzeile zurück; Beschriftung für das Debug-Log |
| `src/server.h` | Prototyp `server_link_stats_reply` |
| `TINYBOX.md` | Format, Schlüssel, Bau, Tests |
| `tinybox-tools/agw_q.py` | Diagnose: fragt `Q` für eine Verbindung ab und zeigt die Zeile |

Nichts davon ändert Protokollverhalten; ohne `Q`-Anfrage läuft der Fork wie das Original. (`TINYBOX.md` im Fork sagt noch „Funktest unter Windows 11 steht aus“ – der ist seit 11.10.2026 erledigt, Satz dort nachziehen.)

**Verteilung des Windows-Programms (`direwolf.exe`):** Das Tinybox-Repo enthält den Fork nicht, ein `git pull` dort bringt also keine neue `direwolf.exe`. Der Fork ist ein eigenes Repo mit Quelltext; die `.exe` ist ein Bauergebnis und liegt in keinem Repo. Gebraucht wird sie nur dort, wo die TinyBox läuft (PC2) – der Client braucht keinen Fork, seine Balken kommen von der TinyBox. Vorgehen:
1. Auf PC2 `git pull` in `C:\direwolf-tinybox` (Zweig `tinybox`), dann mit MSYS2/MinGW + CMake bauen und die `.exe` in den Direwolf-Ordner kopieren, Direwolf neu starten.
2. Soll die `.exe` ohne Bauen auf einen zweiten Rechner: als **GitHub-Release** im Fork-Repo anhängen (Tag = Direwolf-Version + Datum, z. B. `1.8.2-tb1`); privates Repo, Download mit `gh release download` oder im Browser nach Login. Entschieden 12.10.2026: kein Binary ins Tinybox-Repo (ein paar MB je Stand, wächst für immer), keine automatische Verteilung – ein Rechner, seltene Änderungen.

### 14.2 Messung in der TinyBox

TinyBox fragt die Zähler per `Q` ab und rechnet selbst; Bewertung, Fenster und Formatierung liegen in der TinyBox, nicht im Fork.

Pro Richtung eine Verlustquote:

| Richtung | Terminal-User (I-Frames) | Client im UI-Modus |
|---|---|---|
| TinyBox → Station | `i_retry` / (`i_new` + `i_retry`); `rej_rx` nur Anzeige | Empfangsquote der TBCHAT-Frames (14.3) |
| Station → TinyBox | (`rej_tx` + `retry_rx`) / empfangene I-Frames | wie links |

- **Fenster:** die letzten **50 Frames pro Richtung, höchstens aber die letzten 30 Minuten** – was zuerst greift (TinyBox bildet Differenzen zwischen den Abfragen). Zeigt den aktuellen Zustand, nicht den Durchschnitt seit Verbindungsaufbau. Die Zeitgrenze kam nach dem ersten Funktest dazu: in 40 Minuten BBS-/Chat-Betrieb fielen nur 21 bzw. 13 Frames an, 50 Frames hätten also weit über eine Stunde zurückgereicht.
- **Mindestmenge:** nach Prozent wird eine Richtung erst ab **20 Frames** bewertet.
  **Geändert 07.11.2026 (OE3GAS):** Darunter (1–19 Frames) zählen die Ereignisse statt der
  Prozente – 5 saubere Frames sind schon ein sehr guter Link, eine einzelne Wiederholung unter
  5 Frames wären aber 20 % und 3 Balken: 0 Wiederholungen/REJ → 5 Balken, jede kostet einen
  Balken, ab 5 → roter Balken; T1 kostet wie immer einen Balken. Das Ergebnis heißt
  **vorläufig** (`Result.tentative`, solange keine bewertete Richtung 20 Frames hat) und wird
  blasser gezeigt (TinyBox-Web, Client, `STAT` mit `~~~~~` statt `#####`). Ohne Frames graue
  Balken. Gilt für TinyBox und Client (`prcore/linkq.py`).
- **Die schlechtere Richtung bestimmt die Balken.**
- **Schwellen** (geändert 12.10.2026, in `tinybox.conf` einstellbar):

| Verlust | Balken |
|---|---|
| ≤ 5 % | 5 |
| ≤ 10 % | 4 |
| ≤ 20 % | 3 |
| ≤ 35 % | 2 |
| ≤ 50 % | 1 |
| darüber | 1 roter Balken (Code `0`, Terminal `X....`) |
| zu wenig Daten | 5 ausgegraute Balken |

- Jeder T1-Ablauf im Fenster kostet zusätzlich einen Balken (minimal der rote Balken).
- `bytes_new`/`bytes_retry` fließen nicht in die Balken ein, nur in `stat`.

### 14.3 Empfangsquote der Clients (ohne zusätzliche Frames)

Die Folgenummern gibt es schon (`chat.py`, hex 0–FF pro Board). Der Client fordert Lücken mit `//RESEND von-bis` nach (`tbclient/core.py`, bis Lücke 32). TinyBox kennt also gesendete und nachgeforderte Ereignisse und berechnet die Quote selbst – der Client meldet nichts zusätzlich (sonst wieder 1 Frame pro Teilnehmer).

- Neu: `//LOST <n>` vom Client, wenn eine Lücke größer als 32 ist (heute fordert er dann nichts an, TinyBox erführe davon nichts).
- Fehlende letzte Frames merkt der Client erst beim nächsten Ereignis; die Quote hinkt in ruhigen Boards etwas nach. Akzeptiert.
- Maßnahmen bei schlechter Quote (z. B. priorisieren) später.

### 14.4 Ausgabe

**Live-Ansicht im Client:** Balken neben dem Avatar in der Teilnehmerliste. Alle sehen die Qualität aller. Neuer Ereignistyp im TBCHAT-Schema (12.4), z. B.

```
#53 %OE3TEC 4 OE1ABC 2 OE3XYZ ?
```

- `?` = noch kein Ergebnis (graue Balken).
- Bekommt eine Folgenummer wie alle Ereignisse (Lückenerkennung, RESEND).
- Nur bei Änderung der Balken, alle Stationen gebündelt, höchstens 1× pro Minute und Board.
- Nicht in der Chat-History (`chat_lines`) speichern; Terminal-User bekommen ihn nicht.

**Abbruch:** nur als Chat-Ereignis „Verbindung zu OE3XYZ verloren“ statt „hat das Board verlassen“ (aus dem AGW-`d`-Text, 14.1). Fließt nicht in die Balken ein.

**Befehl `stat`** (Mailbox und Chat): `stat` = eigene Verbindung, `stat alle` = alle Verbindungen. Reiner Text, z. B.

```
Call     Bal  Hin   Rück  Retry  REJrx REJtx T1  Netto/Wdh   RX-Quote
OE3TEC   4    3%    1%    3%     1     0     0   2.1k/64     -
OE1ABC   2    14%   4%    -      -     2     1   -           86%
```

### 14.5 Stand der Umsetzung (11.10.2026)

| Schritt | Inhalt | Stand |
|---|---|---|
| 1 | `Q`-Abfrage im AGW-Adapter, Fenster, Balken (`tinybox/linkq.py`) | ✅ |
| 2 | Empfangsquote aus `//RESEND`, `//LOST` im Client | ✅ |
| 3 | Ereignis `%` im TBCHAT, Balken neben dem Avatar im Client | ✅ |
| 4 | Befehl `STAT` / `STAT ALL` | ✅ |
| 5 | Chat-Ereignis „Verbindung verloren“ aus `RETRYOUT` | ✅ |
| 6 | Web-GUI: Balken in der Userliste, Detailansicht je User (13.10.2026) | ✅ |
| 7 | Teilnehmernummern, `%Q`-Statusframe, Detailansicht im Client (CR33, 13.10.2026) | ✅ |

- TinyBox fragt alle `quality_poll_sec` Sekunden (Standard 30) alle Funkverbindungen ab. Antwortet Direwolf nicht (normaler Direwolf ohne Erweiterung), fragt TinyBox bis zum nächsten AGW-Connect nicht mehr und schreibt das einmal ins Log.
- Einstellungen in `[direwolf]`: `quality_poll_sec`, `quality_window_frames` (50), `quality_window_min` (30), `quality_min_frames` (20), `quality_steps` (5, 10, 20, 35, 50).
- `STAT` nutzt den letzten Messwert (höchstens `quality_poll_sec` alt). Ausgabe englisch wie die übrige Bedienung; Balken als Text: `#####` = bestens, `#....` = schlecht, `-----` = noch kein Ergebnis.
- Getestet: Unit-Tests (`tests/test_linkq.py`) und Ende-zu-Ende mit zwei Direwolf-Instanzen (Fork) über Audio-Schleife: TinyBox findet die Erweiterung, `STAT` zeigt die Werte der laufenden Verbindung.
- **Empfangsquote (2):** TinyBox merkt sich pro UI-Client im Board die per UI gesendeten Ereignisse (`linkq.RxWindow`, gleiches Fenster 50/30 min) und markiert die per `//RESEND a-b` nachgeforderten. Neu `//LOST a-b`: der Client meldet Lücken über 32, ohne Nachsenden. Die Quote zählt als Richtung „Out“ (die schlechtere von I-Frames und UI), in `STAT` als Spalte `RXq`. Auch ohne Fork-Direwolf gibt es so Balken für UI-Clients.
- **Ereignis `%` (3):** nach jeder Abfragerunde pro Board `#nn %CALL b CALL b …` (b = 1–5, `?` = noch kein Ergebnis), alle Stationen mit Daten, nur bei Änderung, höchstens 1× pro Minute, nur an Clients, nicht in der History. Der Client zeigt die Balken in der Teilnehmerliste rechts (grün 4–5, gelb 3, rot 1–2, grau = `?`).
- **Abbruch (5):** meldet Direwolf `*** DISCONNECTED RETRYOUT`, gehen ans Board `-CALL` und danach die Systemzeile `!Connection to CALL lost` (auch ältere Clients zeigen sie an); Terminals lesen „left … (connection lost)“.
- Abfrage nach jeder Chat-Zeile: nicht umgesetzt, der 30-s-Takt reicht (die Balken dürfen sich ohnehin nur 1× pro Minute ändern).
- Client-Version 2026.10.11.4 (CR18: ältere Clients bekommen den Hinweis auf die neue Version).

### 14.6 Teilnehmernummern und Statusframe `%Q` (CR33, 13.10.2026)

- **Teilnehmernummern:** kleinste freie Nummer 1…n je Board beim Betreten, frei nach dem Verlassen. Cap `NUM` im Handshake; dann `//WHO <Tn> <Call>[=<Sym>]`, Ereignisse `+<Tn> <Call> [<Sym>]`, `-<Tn>`, `=<Tn> [<Sym>]`, `%<Tn> <Balken> …`. Spart je Station ≈ 7 Byte im `%`-Ereignis und macht den `%Q`-Frame möglich. `//OK` nennt `q=<Fenster-Frames>/<Minuten>/<Mindest-Frames>/<Schwellen>`.
- **Alte Clients (ohne `NUM`)** bekommen unverändert die Rufzeichenform: UI-Frame in Nummernform, dazu die alte Zeile als I-Frame mit derselben Folgenummer; `//RESEND` ebenso.
- **`%Q`-Zeile:** `%Q <Tn> <Balken|?> <out Frames> <out Wdh> <in Frames> <REJ tx> <Wdh rx> <REJ rx> <T1> <Netto/100> <Wdh/100> <RX gesendet> <RX verpasst> <SRT·10>;…` für alle Teilnehmer mit Daten (Fensterwerte aus `linkq.Result`). Ohne Folgenummer: wird nie nachgefordert, zählt nicht für die Empfangsquote, steht nicht in der History. Nur bei Änderung, höchstens alle 2 Minuten je Board (`QSTAT_MIN_SEC`), nach dem `%`-Ereignis derselben Abfragerunde. Einmal als UI-Frame an TBCHAT-n, per I-Frame an NUM-Clients ohne UI. Seit 07.11.2026: keine `%Q`-Zeile, solange alle Balken `?` sind (nur Zwischenstände); ist nur eine Station im Board, bekommt sie `%Q` per I-Frame, ohne UI-Rundspruch. Leere Boards und Boards ohne Client bekommen weiterhin nichts.
- **Payload:** 5 Stationen ≈ 165 Byte ≈ 1,5 s bei 1200 Bd inkl. TXDelay; im 2-Minuten-Takt < 1,5 % Kanal. Binär (≈ 85 Byte) verworfen: nur ≈ 0,3 s Gewinn, im Monitor unlesbar, Binärfilter (CR12).
- **Client:** Teilnehmer antippen → Detailansicht (Richtungen, Schwellenleiter, Zähler) nach denselben Regeln wie `linkq.py`; Balkenzahl kommt mit, die Leiter rechnet der Client aus `q=`.
- **Web-GUI (6, 13.10.2026):** Ansicht „Users“ zeigt pro Station die 5 Balken (grau = noch zu wenig Frames, ein roter Balken = über 50 % Verlust) mit der Richtung, die die Balken bestimmt hat („outgoing“ = TinyBox → Station, „incoming“ = Station → TinyBox, „rx quote“ = UI-Frames eines Clients), dazu Connect-Zeit (hh:mm UTC), Zustand und den TBClient+ samt Version. Klick auf die Zeile öffnet `#/user/CALL`: Richtungen mit Frames, Verlustzählern und Formel, Schwellenleiste mit Rechnung (inkl. T1-Abzug) und alle Direwolf-Zähler (Fenster-Differenz und Rohwert). API: `GET /api/sessions` liefert zusätzlich `client` und `quality`, neu `GET /api/sessions/CALL/linkq`. Beide Ansichten sind live: Feed-Ereignisse (neu `link.quality` nach jeder Abfragerunde) plus Abfrage alle 5 s.

## 15. KISS-Mode (Konzept, entschieden 14.10.2026)

Vollständiges Konzept: `docs/kiss-mode-konzept.md`.

- TinyBox kann wahlweise statt Direwolf/AGW an einem **KISS-TNC** laufen (`[radio] interface = agw | kiss`). Oberhalb der Verbindung ändert sich nichts.
- Den **AX.25-Connected-Mode** übernimmt dann die TinyBox selbst: eigener, reiner Layer-2-Automat (ohne Uhr und I/O, im Simulator testbar), **gleich v2.2** (SABME, Modulo 128, SREJ, XID) mit Pflicht-Rückfall auf v2.0.
- **Sprache: Python.** C verworfen: keine Performance-Not (≤ 40 Frames/s bei 9600 Bd), Frames aus der Luft sind fremde Eingabe → Speichersicherheit wichtiger; falls je nötig, später Übertragung des Automaten nach Rust.
- **Eigener Prozess `kisshub`** besitzt den TNC (seriell/USB/Bluetooth), initialisiert ihn per Geräteprofil und verteilt die Frames per KISS-TCP (`127.0.0.1:8001`) an TinyBox und brocastd. TinyBox spricht nur KISS-TCP – gegen den Hub genauso wie gegen Direwolfs KISS-Port. TinyBox-Neustarts trennen brocastd nicht mehr vom Funk.
- Verbindungsqualität kommt im KISS-Mode direkt aus dem Automaten, **ohne Direwolf-Fork**.
- **TNCs:** Schwerpunkt **PK-232** und **Kenwood TM-D710, TH-D74, TH-D75**; TNC2 nur der Vollständigkeit halber und nur mit **reinem KISS-EPROM**. **Erstes Gerät im Funktest: PK-232.** Getestet wird nur auf **VHF mit 1200 Bd**.
- **Plattform:** Windows (PC2) und Raspberry Pi; NanoPi nicht als Ziel.
- Digipeater/APRS von Direwolf wird nicht genutzt – im KISS-Mode nichts zu ersetzen.
- **Umgesetzt (K4):** `[radio] interface = kiss` schaltet auf `tinybox/adapters/kiss.py` um; `[kiss]` und `[ax25]` in `tinybox.conf.example`. Ohne `[radio]` bleibt alles bei AGW. Eine verlorene KISS-TCP-Verbindung beendet die AX.25-Verbindungen nicht; Stationen, die SABME mit DM ablehnen, werden bis zum Neustart als v2.0 gemerkt.
- **Umgesetzt (K7):** `kisshub` (`python -m kisshub -c kisshub.conf`, `kisshub.bat`) besitzt den TNC, Standard-Port **8101** (8001 bleibt Direwolf). PK-232-Profil mit Weckkette und Schnittstellen-Einstellungen aus pk232py (8N1, ohne Flusskontrolle, DTR/RTS high) und Init nach TRM 4.7.1 + `VHF ON`/`HBAUD 1200`; beim Beenden `C0 FF C0` + `KISS OFF`. Sendewarteschlange: Steuer-Frames vor I-Frames vor UI, höchstens 1,5 s Sendezeit im TNC.
- **Umgesetzt (CR41, 15.10.2026):** Kanalmonitor in der TinyBox (Auslastung, Heard), Status-Abfrage von kisshub (`127.0.0.1:8102/status`), Web-GUI-Karte *Channel* und Kopfzeile mit TNC-Zustand.

**TM-D710 mit 9600 Bd (entschieden und umgesetzt 25.10.2026):** `[kiss] air_baud` (bzw.
`[kiss.tm-d710]`) ist beim TM-D710 nicht mehr nur die Schätzung, sondern geht als
`HBAUD <air_baud>` an den TNC; erlaubt 1200 (Standard) und 9600 (Profilfeld `hbaud`).
Bei 9600 eigene AX.25-Empfehlung (Fenster 7, T1 1,5–15 s, T2 0,5 s) als Startwert.
`init_lines` hat weiter Vorrang. PK-232 bleibt fest auf 1200. Funktest mit 9600 steht aus.

**TNC7multi (entschieden und umgesetzt 29.10.2026, kisshub 2026.10.29):** Gerhard hat einen
TNC7multi (IfD Güttner). Neues Profil `tnc7multi`, alle Werte aus dem Handbuch V1.04: KISS ist
eine Drehschalter-Stellung (1k2/9k6), daher kein Weck- und Init-Dialog und kein Verlassen von
KISS beim Beenden; seriell 115200 Bd (USB) bzw. 38400 Bd (RS232), keine Flusssteuerung;
KISS-Parameter mit den TNC-Standardwerten (TXDELAY 150 ms, P 64, SlotTime 50 ms, Duplex 0).
**SMACK** (KISS mit CRC-16/ARC, low byte zuerst) neu in `prcore/kiss.py`: Bei `[tnc] smack = yes`
(Standard nur bei `tnc7multi`) gehen Datenframes mit CRC raus, der TNC zieht von selbst nach;
empfangene CRC-Frames werden immer geprüft (auch bei `smack = no`, der TNC bleibt bis zum
Neustart in SMACK), falsche CRC → Frame verworfen, Zähler `crc_errors`. `air_baud` ist hier nur
die Schätzung (Rate kommt vom Schalter); 1200/9600 ohne Hinweis, andere Raten mit Hinweis
(Zusatzmodem). Funktest steht aus.

**TM-D710 mit RTS/CTS (entschieden und umgesetzt 25.10.2026):** Zwischen kisshub und D710 gilt
Hardware-Flusssteuerung RTS/CTS (`[tnc] rtscts`, Profil-Standard `yes`, andere Profile `no`).
Das Funkgerät steuert damit selbst, wann es Daten nimmt; `max_lead_ms` bleibt als
Vorlauf-Grenze für die Prioritäten. Geschrieben wird in 64-Byte-Stücken mit CTS-Prüfung
davor, damit ein Stopp nie in einem blockierten Schreibvorgang hängt.

**RTS/CTS wirksam machen (entschieden und umgesetzt 26.10.2026, kisshub 2026.10.26):** Funktest
OE3GAS (TM-D710) ↔ OE3TEC (TM-D700) mit 9600 Bd: Bei 57600 Bd seriell verschmolzen Frames von
OE3TEC (Anfang von I7 + Ende von I10 als *ein* Frame mit gültiger FCS) – Bytes gingen zwischen
PC und TNC verloren, die Statuszeile zeigte trotzdem `CTS waits 0`. Befund im Code: `write()`
kehrt zurück, sobald die Daten im Puffer des Betriebssystems liegen; die CTS-Prüfung vor jedem
64-Byte-Stück lief also durch, bevor ein Byte auf der Leitung war, und zählte nur Zufälle. Die
Flusssteuerung hing ganz am Treiber und am USB-Adapter (PL2303). Ein Schreibfehler (auch der
2-s-`write_timeout`) beendete den Schreib-Thread still. Entscheidung, Gerhard: RTS/CTS ist die
Kontrolle, die der TNC bietet, und muss vom kisshub selbst ausgewertet werden:
- 32-Byte-Stücke, jedes mit `flush()` aus der Schnittstelle, dann CTS prüfen; kein
  `write_timeout` mehr (ein abgebrochenes Stück könnte zwei Frames verbinden), Strg+C über
  `cancel_write()` und Daemon-Threads.
- CTS-Monitor-Thread (2 ms): zählt jede Tief-Phase (`cts_drops`, `cts_low_s`,
  `cts_low_max_ms`), jeder Wechsel im DEBUG-Log, Warnung nach 5 s; Status und Statuszeile.
- Linux: Startmeldung, ob der Treiber `CRTSCTS` wirklich gesetzt hat.
- Schreibfehler → Port neu öffnen wie bei einem Lesefehler.
Befund TM-D700 (OE3TEC, GTKTerm): CTS arbeitet nur im Befehlsmodus, **im KISS-Modus ist CTS
immer frei** – dort hilft RTS/CTS nicht; laut Handbuch verlangt der D700 außerdem 9600 Bd
seriell (Menü 1–9–5 nicht ändern). Ein Profil `tm-d700` (Taktung durch den kisshub, gemessene
effektive Rate statt 9600, Puffergröße messen) folgt nach Absprache mit OE3TEC.

**modem73 als Modem (entschieden und umgesetzt 1.11.2026, kisshub 2026.11.01):** modem73
(RFnexus, OFDM, 2400 Hz, Public Domain) als Alternative zu den KISS-TNCs auf 2 m/70 cm FM.
Bewertung: transparentes KISS-TCP (kein Tunnel), Steuerport 8073 mit SNR/BER je Rahmen; aber
feste Rahmenzeit je Frame, Abschneiden zu langer Frames, 1 s Sendesperre nach Empfang, nur
Punkt-zu-Punkt zwischen modem73-Stationen. Windows: eigener Build des aktuellen Originals mit
dünner Winsock-Schicht statt des veralteten `modem73-win` (`tools/modem73`, Gerhard: kein Pi
nur für ein KISS-Modem). Entscheidung, Gerhard: eigene conf statt langer Kommandozeile, und
zwar im kisshub (Variante b):
- Profil `modem73`, Abschnitt `[modem73]` in der `kisshub.conf`; der kisshub startet modem73
  (headless, eigene Prozessgruppe), wartet auf den KISS-Port (8011), leitet die Ausgabe ins
  eigene Log, startet es nach einem Absturz neu und beendet es mit Strg+C.
- Aus Modulation/Coderate/Rahmengröße berechnet (`kisshub/modem73.py`, Formel aus
  `phy/common.hh`): Nutzlast und Rahmenzeit; daraus TXDELAY = Vorlauf + Rahmenzeit,
  `air_baud` 1 000 000 (die Bytes zählen für die Stationen fast nichts), Burst-Folgerahmen
  + Rahmenzeit + 200 ms, PACLEN = Nutzlast − 31, Fenster = `csma_burst`, T1 aus Antwortzeit.
- Frames über der Nutzlast verwirft der Hub (`oversize`), statt sie abschneiden zu lassen.
- Offen: Qualitätswerte vom Steuerport (SNR, BER, Pegel je Rahmen, PTT-Zeiten) wie
  `varamon` in linkstats und Web-GUI; Bündeln mehrerer AX.25-Frames je OFDM-Rahmen;
  Funktest OE3GAS ↔ OE3TEC. Bedienung: MANUAL 3.5a.

## 16. DX-Cluster-Feed `dxfeed` (entschieden 15.10.2026)

- **Keine Live-Spots über Funk**, keine Dauerbeschallung: Der Spot-Strom wird gesammelt und **einmal täglich verdichtet**.
- **Eigener Prozess** `python -m dxfeed collect` (Telnet zum DX-Cluster, DXSpider/CC-Cluster), unabhängig von der TinyBox; ein Cluster-Ausfall stört die Mailbox nicht. Neuverbindung mit wachsender Pause, Knotenliste reihum. Standardknoten `dxc.hamserve.uk:7300` (kein Favorit bei OE3GAS, in `dxfeed.conf` änderbar).
- Spots in eigener SQLite-DB `data/dxfeed.db` (7 Tage), dazu die Verbindungszeiten: Der Digest sagt, wenn er nicht den ganzen Tag abdeckt.
- **Ländertabelle** AD1C `cty.dat` (country-files.com), wird automatisch geholt und alle 14 Tage erneuert. WAE-Einträge (`*`) werden übersprungen, z. B. IT9 → Italien.
- **Tages-Digest um 05:00 Lokalzeit** über die letzten 24 Stunden, als Bulletin an **DX** in den Eingangsordner (`Replace: dxfeed-JJJJMMTT`, `Valid: 7d`). **Nur lokal** (keine @-Adresse), da es (noch) keine Forward-Partner gibt.
- **Relevanz:** nur Spotter in EU, 160 m – 70 cm, häufige DXCC-Gebiete ausgeschlossen (Liste in `dxfeed.conf`; auf 2 m und 70 cm zählen alle Gebiete, `all_dxcc_bands`, ergänzt 16.10.2026), eine Zeile pro DX-Call (Gebiet, Bänder, Modes, erster/letzter Spot, Anzahl verschiedener Spotter). Calls mit nur einem Spotter werden nur gezählt (oft Tippfehler). Dazu Bandaktivität aller EU-Spots mit Spitzenstunde.
- Höchstens 3000 Bytes Text (geht per brocast über Funk), ASCII, Zeilen unter 80 Spalten.
- **Sicherheit:** Cluster-Daten sind fremde Eingabe aus dem Internet: Steuerzeichen und Telnet-Befehle werden entfernt, Kommentare auf druckbares ASCII und 40 Zeichen gekürzt, Rufzeichen geprüft, überlange Zeilen verworfen. Einzige Außenverbindungen: Telnet zum Cluster (Klartext, nur das Rufzeichen) und HTTPS für `cty.dat` (Zertifikatsprüfung an, `ssl_verify`).
- **Betrieb PC2:** `start_alles.bat` startet den Sammler (`START_DXFEED=1`, nur wenn `dxfeed.conf` existiert); `dxfeed_aufgabe_einrichten.bat` legt die 05:00-Aufgabe an. NanoPi: `dxfeed.service`, `dxfeed-digest.timer` (aktiv, sobald `dxfeed.conf` existiert).
- **Später (offen):** BBS-Befehl `DX` (letzte gefilterte Spots auf Abruf), persönliche Watchlist (Mail nur bei Treffer, opt-in).

### 16a. Relevanz und brocast-Seite (entschieden 23.10.2026)

- **Relevanz statt Spotterzahl:** EA6, CU, CE, KP4 usw. sind kein echtes DX; ein seltenes Gebiet mit wenigen Spottern zählt mehr als ein häufiges mit vielen (5 Spotter für Bouvet > 10 für LU).
- **Score = Seltenheit × log₂(1 + Spotter)**. Seltenheit 1 … 10 aus dem **Club Log Most Wanted**-Rang: `1 + 9·((341 − Rang)/340)²`. Stufen **A** (ab `relevance_a` = 25, sofort hinschauen), **B** (ab `relevance_b` = 12, interessant), **C** (Alltag). Schwellen sind Startwerte, nach ein paar Tagen echter Daten nachjustieren.
- Most-Wanted-Liste als JSON (`mostwanted.php?api=1`), Datei `data/mostwanted.json`, alle 7 Tage erneuert (`dxfeed.bat mw-update` von Hand). Fehlt sie, gilt für alle Gebiete Rang 170 (nur Spotterzahl zählt), der Digest läuft weiter.
- **Mailbox-Text:** alle Calls ab `min_spotters`, alphabetisch, mit Spalten R (Stufe) und MW (Rang); bei Platzmangel fallen die am wenigsten relevanten zuerst weg. Bandaktivität jetzt je Mode-Gruppe (CW, SSB, FT8, Andere), die anderen Modes mit Namen und Anzahl.
- **brocast-Seite:** abgelöst durch 16b (Dictionary v4). Die erste Fassung (Tabellenblöcke mit Spaltennamen und Gebietsnamen als Text) brauchte für 8 Stationen A+B 735 B in 3 Frames.
- Die Most-Wanted-Liste nennt Club-Log-Präfixe (1A0, IS0, KL7 …), cty.dat die AD1C-Präfixe (1A, IS, KL …). Die Zuordnung läuft über die DXCC-Liste des Dictionarys (16b, Feld `cl`).

### 16b. DX-Zusammenfassung im Dictionary v4 (entschieden und umgesetzt 23.10.2026)

- **Seitentyp `13 dxsum`** mit eigenem Namensraum `types.dxsum` (12 bleibt frei: war im Entwurf Pull). Der Namensraum ersetzt Spaltennamen und -köpfe auf der Luft.
- **Neue Listen in `enums`**, für alle Seitentypen nutzbar: `band` (160 m … 70 cm, auch als Bitnummer), `mode` (CW, SSB, FT8, FT4, RTTY …), `dxtier` (A/B/C) und **`dxcc`: alle 402 DXCC-Gebiete, Nummer = ADIF-Code** (340 aktiv, gelöschte mit `del: true`). Je Eintrag AD1C-Präfix als Name, englischer Name, Kontinent, CQ-/ITU-Zone, `cl` = Club-Log-Präfix, wo er abweicht. Erzeugt mit `brocast/tools/build_dxcc.py` aus Club Log cty.xml, AD1C cty.plist und k0swe/dxcc-json (Apache 2.0).
- **Neuer Feldtyp `rows`** (Zeilen mit Spaltenbeschreibung `cols`): Spalten mit `enum`/`enums` (Nummer, unbekannt als Text bis `free_text`), `bits` (Bitmaske über eine Liste), `counts` ([Nummer, Anzahl, …]).
- **Neue Blockart `11 data`:** `v` wie `dat` im Namensraum des Seitentyps. Nötig, weil der Umschlag mit `dat` im Format 2 in den ersten Frame passen muss, die Blockliste dagegen gepackt und fragmentiert wird.
- **Zwei Bulletins, zwei Seiten:** „DX-Zusammenfassung“ (Stationen, Seite `st`) und „DX-Bandaktivitaet“ (Seite `act`, `Replace: dxfeed-act-JJJJMMTT`). In der Mailbox ebenso getrennt.
- **Größe (Beispiel 23.10.2026):** Stationen A+B (8) **247 B in 1 Frame**, Bandaktivität (14 Bänder) **239 B in 1 Frame**; alle 25 Stationen 540 B in 3 Frames. Vorher (16a): 735 B in 3 Frames für Stationen und Bandaktivität zusammen.
- **Preis:** Das Dictionary wächst durch die Gebietsnamen auf rund 42 kB Text (`DICT`: 629 Zeilen) bzw. 11 kB gepackt über Funk (56 Frames statt rund 15). Bei `dict_broadcast_hours = 24` etwa 1,5–2 min Sendezeit pro Tag.
- dxfeed liest die DXCC-Liste direkt aus `brocast/brocast-core.yaml` (`[data] dictionary`, braucht PyYAML). Fehlt sie, geht das Gebiet als Text und der Most-Wanted-Rang wird über den AD1C-Präfix gesucht. `dxfeed status` zeigt cty.dat-Gebiete ohne DXCC-Nummer.
- Listener: zeichnet Raster, Heatmap und Listen aus `p.data`; Gebiets- und Mode-Namen liefert der Listener aus dem Dictionary (`texts`, `bits`).
- **Korrekturen 24.10.2026 (erster echter Lauf):**
  - Club Log liefert die Most-Wanted-Liste als **Rang → ADIF-Nummer** (`{"1":"344",…}`), nicht als Präfix: bis dahin bekam kein Gebiet einen Rang (alle „–“, Seltenheit = Mittelwert). Zuordnung jetzt über die DXCC-Liste des Dictionarys; die alten Formen werden weiter gelesen.
  - **Mindestens 10 Stationen** auf der brocast-Seite (`brocast_min_rows`): Stufen aus `brocast_tiers`, nach Relevanz mit Stufe C aufgefüllt, höchstens `brocast_max_rows`. 10 Stationen ≈ 300 B in 2 Frames.
  - Mode „?“ = weder im Kommentar noch aus dem Bandplan erkennbar. Bandplan ergänzt: Digital-Segmente als `DIGI`, Phonie bis 4000/7300 kHz (Region 2), FM-Bereiche; gespeicherte Spots ohne Mode werden beim Digest neu eingeordnet.
  - Bandaktivität trägt dieselbe Abdeckung (`cov`) wie die Stationsseite; der Listener zeigt den Zeitraum in UTC wie die Tabelle.
  - **Bandaktivität über dieselben relevanten Spots wie die Stationsliste** (entschieden 24.10.2026): Spotter in EU, ohne ausgeschlossene häufige Gebiete. Die Summe der Tabelle = Zahl der relevanten Spots im Kopf der DX-Zusammenfassung. Vorher zählten alle EU-Spots (auch Europa, USA …), die Zahlen passten nicht zusammen.

### 16c. DX live: Bezug zum Jetzt (entschieden und umgesetzt 25.10.2026)

Anlass: Die 24-Stunden-Übersicht ist für „wer war aktiv“ ideal, um 10:30 aber schon 5 Stunden alt.
Ergänzung in eigenen Bulletins, ohne Dauerbeschallung: jede Art ersetzt sich selbst (`Replace:`),
läuft per `Valid:` von selbst aus und wird nur bei Bedarf gesendet.

- **Neuer Befehl `dxfeed live`**, alle 10 Minuten (PC: Aufgabe `TinyBox\DX-Live`; Feeder-Pi:
  `dxfeed-live.timer`). Entscheidet selbst, was fällig ist; Zustand in `data/dxfeed-live.json`,
  nur bei Änderung geschrieben (SD-Karte). `dxfeed live` ohne `--tinybox` zeigt alles nur an.
- **DX jetzt** (`Replace: dxfeed-jetzt`, Valid 2 h): Stufen A/B der letzten 2 Stunden, höchstens 8,
  mit letzter Frequenz und Uhrzeit. Prüfung alle 30 min, gesendet nur wenn sich Stationen oder
  Bänder ändern (oder die letzte Seite 90 min alt ist).
- **Bänder jetzt** (`Replace: dxfeed-baender`, Valid 90 min, stündlich): Spots der letzten Stunde
  je Band und **Kontinent der DX-Station** – hier **alle Gebiete** (CE, LU … zeigen den Pfad nach
  Südamerika), Spotter in EU. Ohne Spots in der Stunde: nichts.
- **Neu auf dem Band** (`Replace: dxfeed-neu-<Call>`, Valid 2 h): Most-Wanted-Rang ≤ 100, mindestens
  3 EU-Spotter in 60 min, in den 24 Stunden davor nicht gespottet. Je Call einmal am Tag, höchstens
  3 pro Stunde. Statt „Stufe A“: mit 3 Spottern erreicht selbst Rang 1 rechnerisch nur Stufe B.
- **24-Stunden-Übersicht gleitend** alle 3 Stunden (02:00, 05:00, 08:00 …) statt einmal um 05:00;
  feste Replace-Schlüssel `dxfeed-24h` / `dxfeed-24h-act`, es gibt also immer genau eine.
- **Dictionary v5** (nur Ergänzungen): `dxsum.kind` (Liste `dxkind`: day, now, new, paths),
  `dxsum.path` (Band × AF AN AS EU NA OC SA), Spalte `qrg` am Ende der Stationszeilen. Spalten von
  `rows` dürfen nur hinten angehängt werden (Prüfung in `dictimport`).
- **Listener:** Alter groß („Stand vor 12 min“, rot wenn veraltet), Neu-Hinweis mit Call, Gebiet,
  QRG und Mode in großer Schrift, Pfad-Matrix als Heatmap mit Zahlen, QRG-Spalte bei „jetzt“.
- **Größe:** DX jetzt mit 8 Stationen 1–2 Frames, Bänder jetzt und Neu je 1 Frame.
- Einstellungen: `[live]` in `dxfeed.conf` (Vorlage `dxfeed.conf.example`).
- Offen: Ausbreitungsdaten (SFI, A/K) als eigenes Bulletin – später (Gerhard, 25.10.2026).

## 17. Refactoring (entschieden 17.10.2026)

Gezielt in Schritten, kein Großumbau. Sicherheitsnetz sind die bestehenden Tests (TinyBox und brocast).

1. ✅ **`production/` aus dem Repo** (17.10.2026): Builds bleiben lokal (`.gitignore`), freigegebene Versionen werden mit Git-Tag `prod-<hash>` markiert. Der bisherige Build `f16d5a3` liegt im Tag `prod-f16d5a3` (Details in PRODUCTION.md).
2. ✅ **Gemeinsames Paket `prcore`** für die Funk-Grundlagen (umgesetzt 17.10.2026, siehe 17.1; Funktest steht aus).
3. **Config-Laden** auf eine gemeinsame, tabellengesteuerte Grundlage (heute vier eigene Lader, `tinybox/config.py: load` rund 200 Zeilen).
4. **Lange Funktionen** (z. B. `aprs._mice`, `aprsstats.report`, tbclient `core._control`, `web._route`) nur aufteilen, wenn dort ohnehin CRs anstehen.

NanoPi-Produktionsschiene (`PRODUCTION.md`, `build_production.sh`, `deploy/`, von OE3TEC) bleibt vorerst unberührt (17.10.2026).

### 17.1 Gemeinsames Paket `prcore` (Plan, 17.10.2026)

**Ausgangslage (Bestand 17.10.2026):**
- tbclient und kisshub importieren schon heute TinyBox-Interna (`tinybox.ax25`, `aprs`, `aprsstats`, `chatimg`, `fwd.lzhuf`). `tinybox/` ist damit stillschweigend auch die Bibliothek für Client und Hub. Ziel CR46 – Client als eigenständiges PR-Programm ohne TinyBox – passt dazu nicht.
- Der **AGW-Kopf** (`HEADER = struct.Struct(...)`, Pack/Unpack, Rufzeichen dekodieren) ist viermal geschrieben: `tinybox/adapters/agw.py`, `tbclient/links.py`, `fwdsim/agw.py`, `brocast/brocast/agw.py`.
- Der **KISS-Port** (Timer-Schleife der Links, Sendezeit, „Kanal belegt“ an die anderen Links, Frame → Link verteilen, kisshub-Status abfragen) steckt zweimal fast gleich in `tinybox/adapters/kiss.py` (`KissAdapter`) und `tbclient/kisslink.py` (`KissPort`); `_timer_loop`, `_airtime`, `now`, `fetch_hub_status` sind praktisch Kopien. Jede Änderung (VARA FM, Qualitätswerte) muss heute doppelt gemacht werden.
- brocast hat für UI-Frames eigene kleine Kopien von AX.25-Adressen, KISS und AGW (zusammen rund 360 Zeilen).

**Inhalt von `prcore/`** (neues Paket im Repo-Wurzelverzeichnis, neben `tinybox/`, `tbclient/`, `kisshub/`):

| Neu | Bisher |
|---|---|
| `prcore/ax25/frame.py`, `link.py`, `xid.py` | `tinybox/ax25/` |
| `prcore/kiss.py` | `tinybox/ax25/kissio.py` |
| `prcore/agw.py` – nur der AGW-Kopf und seine Hilfsfunktionen | je eine Kopie in tinybox, tbclient, fwdsim |
| `prcore/kissport.py` – gemeinsamer KISS-Port als Basisklasse | `KissAdapter` (tinybox) und `KissPort` (tbclient) |
| `prcore/aprs.py` + `aprs_data.json`, `prcore/aprsstats.py` | `tinybox/` |
| `prcore/chatimg.py` – nur die reinen Funktionen (Hash, Größe, Referenz parsen, Terminaltext); die Klasse `ChatImages` (braucht die BBS-Session) bleibt in tinybox | `tinybox/chatimg.py` |
| `prcore/lzhuf.py` | `tinybox/fwd/lzhuf.py` |

Regel: `prcore` importiert nie aus `tinybox`, `tbclient`, `kisshub` oder `brocast` – nur umgekehrt.

**Reihenfolge** (jeder Teilschritt ein eigener Commit, Tests vorher und nachher grün):
- ✅ **2a – Verschieben** der fertigen Module (ax25, kiss, aprs, aprsstats, lzhuf, chatimg-Funktionen). Rein mechanisch, kein Verhalten ändert sich; Importe in tinybox, tbclient, kisshub, fwdsim und den Tests werden angepasst, keine Umleitungs-Module in `tinybox/`.
- ✅ **2b – AGW-Kopf** vereinheitlichen (tinybox, tbclient, fwdsim).
- ✅ **2c – KISS-Port** zusammenführen: Basisklasse in `prcore/kissport.py`, `KissAdapter` und `KissPort` behalten nur ihr Eigenes (BBS-Sitzungen bzw. Client-Kanäle). Einziger Teilschritt mit echtem Verhaltensrisiko → danach **Funktest** auf PC1 mit PK-232 (und VARA FM, sobald es läuft), TinyBox und Client im KISS-Mode.
- **2d – brocast:** entschieden 17.10.2026 – bleibt eigenständig mit seinen eigenen UI-Kopien.

**Stand 17.10.2026:** 2a–2c umgesetzt (Commits „Refactoring 2a/2b/2c“), 628 Tests grün, tbclient 2026.10.17.6.
- `prcore/agw.py`: AGW-Kopf (`Frame`, `read_frame`, `decode_call`, `via_data`); `AgwProtocolError` ist jetzt ein `ConnectionError`.
- `prcore/kissport.py`: `KissPort` mit Haken (`on_heard`, `on_transmit`, `received`, `accept_incoming`, `on_link_event`) sowie `fetch_hub_status`/`poll_hub`. TinyBox: `_BoxPort` als Bestandteil von `KissAdapter` (der weiter vom AGW-Adapter erbt); Client: `KissPort` erbt direkt.
- Nebenbei behoben (Client): Ein Connect ohne freien Kanal wurde mit UA angenommen und dann vergessen; jetzt bekommt die Station DM, wie beschrieben. Die TinyBox lehnt nie ab, für sie unverändert.
- Eingehende Rufzeichen werden im KISS-Port jetzt auf beiden Seiten gleich normalisiert (Großschrift, ohne „-0“); bisher nur im Client.
- Offen: **Funktest** auf PC1 mit PK-232 (KISS-Mode) – TinyBox und Client je: eingehender und ausgehender Connect, Mail/Chat, Trennen; Client zusätzlich Connect bei belegten Kanälen (DM).
- Ältere Abschnitte und `docs/` nennen noch die alten Pfade (`tinybox/ax25`, `tinybox/aprs.py` …); das ist Geschichte und bleibt so.

**Nebenwirkungen:**
- tbclient: Version einmal für 2a–2c erhöht (2026.10.17.6) mit News-Datei – ein Bulletin statt drei.
- `build_production.sh`: `prcore` muss in `INCLUDE`, sonst startet die TinyBox im NanoPi-Build nicht. Nur diese eine Zeile, sonst bleibt die NanoPi-Schiene unberührt.
- Gestartet wird alles weiter aus dem Repo-Wurzelordner (`python -m tinybox`, `-m tbclient`, `-m kisshub`), dort ist `prcore` ohne weiteres importierbar.

**Entscheidungen (17.10.2026):** brocast bleibt eigenständig; Name `prcore`; im NanoPi-Build nur `prcore` in `INCLUDE`.

✅ Offen aus Schritt 1: `kisshub/` ist in `build_production.sh` weder in `INCLUDE` noch in `EXCLUDE`. Laut Abschnitt 15 ist der NanoPi kein Ziel für den KISS-Mode → bei Gelegenheit in `EXCLUDE` eintragen. Erledigt 28.10.2026 (Abschnitt 26).

---

### 17.2 Konfiguration ohne Doppelungen (CR70, umgesetzt 18.10.2026)

**Befund:** Funkrate und TXDELAY standen bis zu fünfmal (kisshub, tinybox, tbclient, brocastd,
direwolf.conf), die kisshub-Adresse dreimal, AX.25-Werte doppelt (TinyBox `[ax25]` mit Rückfall
auf `[direwolf]`, Client „dieselben Werte wie die TinyBox“), Direwolf/AGW unter vier Namen
(`agw_radio_port`, `radio_port`, `channel`), die Schnittstellenwahl unter drei Namen
(`[radio] interface`, `[tinybox] link`, `[direwolf] interface`). Beim VARA-Test führte das zu
Fehlern (vergessene Werte, T1 zu kurz).

**Entscheidung (18.10.2026):** Jeder Wert hat genau einen Besitzer.
- **AGW:** `direwolf.conf` ist die Quelle. Neuer Eintrag `[agw] direwolf_conf` (Ordner oder Datei);
  gelesen werden AGWPORT, KISSPORT, MODEM, TXDELAY, PERSIST, SLOTTIME, PACLEN, MAXFRAME, EMAXFRAME,
  FRACK, RETRY. Über AGW lassen sich die Werte nicht abfragen: Direwolf beantwortet `g` (Port
  Capabilities) mit festen Fantasiewerten (Quellcode `server.c`).
- **KISS:** der kisshub ist die Quelle. `/status` bekommt einen Block `radio` (air_baud, txdelay_ms,
  Herkunft, AX.25-Empfehlung des Profils); TinyBox, Client, brocastd übernehmen ihn. Neues Profil
  `direwolf` (liest direwolf.conf), VARA-Profile mit den gemessenen Werten als Standard.
- Einheitliche Abschnitte `[radio] interface`, `[agw]`, `[kiss] port` in allen Programmen;
  `host` fest 127.0.0.1, Status-Port = Port + 1. `[ax25]` nur noch zum Überschreiben.
- dxfeed und fwdsim lesen `tinybox.conf` mit (`[tinybox] conf`).
- Alte Schlüssel werden weiter gelesen (gelten als Überschreibung, Hinweis beim Start).

Zielaufbau und Tabelle alt → neu: `MANUAL.md` Abschnitt 2.

**Schritte:** 1. kisshub liefert `radio`, TinyBox/Client übernehmen es, `direwolf_conf` lesen –
2. einheitliche Abschnittsnamen – 3. kisshub-Profil `direwolf`, brocastd – 4. dxfeed, fwdsim.
**Stand 18.10.2026: alle vier Schritte umgesetzt** (kisshub 2026.10.18.7, tbclient 2026.10.18.3).
Die kisshub-Werte gelten für jede neue Verbindung ab dem ersten Status (alle 30 s); eine
Verbindung, die schon läuft, behält ihre Werte.
Passt zu Schritt 3 oben (gemeinsamer Config-Lader).

## 18. Quellenangabe über das Dictionary (brocast v3, entschieden 19.10.2026)

Anlass: Die Wetterseite trug bei jeder Aussendung den Text „GeoSphere Austria, TAWES
(CC BY 4.0)“ – 39 B von rund 120 B je Frame. Der Lizenzhinweis muss bleiben, muss aber
nicht jedes Mal als Text über die Luft.

- Neue Liste `src` im Dictionary **Version 3**: `0 geosphere` (voller Lizenztext),
  `1 tinybox`. Umschlag-Key 21 `src` ist ab v3 `enums` mit `free_text: 60` – wie `cat`:
  Listen-Eintrag (1 B) oder freier Text (z. B. Rufzeichen des Autors).
- `geosphere_station.py` sendet `src: ["geosphere"]`, der TinyBox-Adapter `["tinybox", <Rufzeichen>]`.
- Ersparnis Wetterseite: **122 → 85 B** (−37 B, rund 0,25 s bei 1200 Bd).
- Listener mit v2 zeigen bis zur Dictionary-Übernahme (kommt über Funk) „0“ als Quelle.
- Die Zahlenmatrix mit Stationsnummern (Abschnitt 6e, dort „v3“ genannt) kommt damit
  in eine spätere Version (v4).

## 19. Content-Lieferanten: Sofortmaßnahmen (entschieden 20.10.2026)

Anlass: Prüfung der Lieferanten dxfeed, GeoSphere (Wetter, Warnungen) und TBNEWS.

- **TBNEWS nie über brocast.** Wer die TinyBox nutzt, bekommt die Client-News per
  Connect oder über den Client; reine brocast-Listener brauchen sie nicht. Der
  brocast-Adapter meldet die Systemrubrik TBNEWS nicht mehr (auch nicht, wenn sie in
  `[brocast] destinations` steht); die nächste Vollsynchronisation zieht schon
  gesendete TBNEWS-Seiten bei brocastd zurück.
- **TLS-Prüfung bei GeoSphere ein.** Die Daten gehen über Funk weiter, Warnungen als
  Warnseite, die jeder Listener anzeigt – die Quelle muss echt sein (Integrität, nicht
  Vertraulichkeit). Fehlende Stammzertifikate unter Windows: Paket `truststore`
  (nutzt die Windows-Zertifikatsprüfung), sonst `certifi`, sonst der Systemspeicher.
  `geosphere_aufgaben_einrichten.bat` installiert `truststore` bei Bedarf.
- Weitere Punkte der Prüfung (gemeinsames Paket für Lieferanten, einheitliche
  Konfiguration, dxfeed als Tabellenseite, DX-News als zweiter Inhalt) folgen gesondert.

## 20. Wetterprognose für einen Locator (Weg 1 entschieden und umgesetzt 24.10.2026, Weg 2 = CR72)

Anlass: Neben den Messwerten (TAWES, Abschnitt 6d/6g) soll es eine **Prognose** geben,
besonders für den Wind. Die Stations-API von GeoSphere liefert nur Messwerte; die
Prognose kommt aus dem Wettermodell `nwp-v1-1h-2500m` (C-LAEF, 2,5-km-Gitter,
Stundenwerte, 61 h, neuer Lauf alle 3 h, CC BY 4.0), abgefragt über
`/v1/timeseries/forecast/nwp-v1-1h-2500m?lat_lon=<lat>,<lon>`.

**Ort = Maidenhead-Locator.** Funkamateure kennen ihren Locator; die API nimmt nur
Koordinaten. Das Skript rechnet den Locator in den Mittelpunkt um, die API liefert die
Gitterzelle an diesem Punkt (ihre Koordinaten stehen in der Antwort und gehen als `pos`
mit). 6-stellig (ca. 6 × 5 km ≈ 3 × 2 Modellzellen) passt zur Auflösung, 8-stellig geht
auch, 4-stellig (150 × 110 km) wird abgelehnt, ebenso ein Locator außerhalb des
Modellgebiets (≈ 43–51,8° N, 5,5–22° O).

**Weg 1 – feste Locators, zeitgesteuert (umgesetzt):** `geosphere_prognose.py --locator
JN88BN[,…] --tinybox`, Aufgabenplanung alle 3 h um 00:35, 03:35 … (`geosphere_aufgaben_einrichten.bat`,
Variable `LOCATOR`; NanoPi: `geosphere-prognose.timer`). Ein API-Abruf für alle Locators.
Je Locator ein Bulletin an `WX`, `Replace: geosphere-prognose-<LOC>`, `Valid: 4h`.

- **Werte je Schritt** (Standard 48 h in 3-h-Schritten, `--stunden` bis 54, `--schritt` 1/2/3/6):
  Temperatur am Beginn, mittlerer Wind (Vektormittel aus `u10m`/`v10m`), stärkste Böe im
  Schritt (`ugust`/`vgust` sind das Maximum der jeweils letzten Stunde), Niederschlag im
  Schritt (Differenz der Summenreihe `rr_acc`, nie negativ), Bewölkung in Achteln (`tcc`).
  Die Zeilen stehen auf dem lokalen 3-h-Raster (über die Zeitumstellung hinweg lesbar), der
  erste Schritt beginnt mit der aktuellen Stunde.
- **Text** (Mailbox, Terminal): Tabelle ≤ 60 Zeichen breit, Wind und Böen in km/h mit Bft,
  darunter Temperaturspanne, stärkste Böe mit Zeit, Regensumme und Beginn.
- **brocast-Seite** `typ wx` ohne `dat`, mit `area` = Locator, `pos` = Gitterzelle und einer
  Tabelle mit Spaltenbedeutung `n = ["hour", "sky", "temp", "wdir", "wspd", "gust", "rr"]`
  (wie die Regionsübersicht, 6g): Uhrzeit als Text, Achtel ×10, sonst `sc -1`; je Tag eine
  Gruppenzeile („Sa 24.10.“). Keine Dictionary-Änderung. 48 h / 3 h = 17 Zeilen,
  **gepackt 2 Frames** (≈ 340 B).
- **Listener:** Erste Spalte `hour` → **Prognosegrafik (Meteogramm)** statt Stationsraster:
  oben Kacheln (Temperaturspanne mit Zeiten, stärkste Böe in km/h mit Bft und Zeit,
  Niederschlagssumme mit Beginn), darunter je Zeitschritt eine Spalte: Tag/Uhrzeit,
  Wolkensymbol (Sonne/Mond nach Sonnenauf- und -untergang am Ort, Tropfen bei Regen),
  Temperaturkurve, Regenbalken, Windpfeil mit Richtung und km/h, Böen mit Bft (ab Bft 6
  hervorgehoben); Nachtschritte hinterlegt, Tageswechsel als Linie. Text und Teletext zeigen
  die schlichte Tabelle. Alles aus den gesendeten Zahlen, nichts zusätzlich über Funk.
- **Quelle:** vorerst als Text `GeoSphere Austria, NWP (CC BY 4.0)` (35 B), denn der
  Listen-Eintrag `geosphere` nennt TAWES. **Offen:** eigener `src`-Eintrag in der nächsten
  Dictionary-Version (spart ≈ 33 B je Aussendung).
- Tests: `tests/test_geosphere_prognose.py` mit einer echten API-Antwort (`tests/fixtures/
  geosphere_nwp_jn88bn.json`, über das Ende der Sommerzeit am 25.10.2026).

**Weg 2 – Prognose auf Anfrage eines Users (geplant, CR72):** Ein User fordert über die
TinyBox die Prognose für **seinen** Locator an und bekommt sie zurück. Details siehe
`docs/client-change-requests.md`, CR72.

## 21. Benutzerprofil: Name, Locator, Home-BBS (entschieden und umgesetzt 24.10.2026, CR73)

Anlass: Andere PR-BBS (FBB, BPQ, BayCom/OpenBCM) fragen neue Benutzer nach Name, QTH und
Home-BBS. Die TinyBox soll das auch, und der Client soll dieselben Daten nutzen.

**Entscheidungen (OE3GAS, 24.10.2026)**

- **Wo:** verbindlich in der TinyBox (Tabelle `profiles`, ein Eintrag je Rufzeichen ohne SSID),
  der Client hält eine Kopie. Eingabe im Client (Formular) oder im Terminal.
- **Was:** Name, Locator (4 oder 6 Stellen, der User wählt die Genauigkeit) und Home-BBS.
- **Wer sieht es:** alle – Chat, Terminal (`I call`), andere Clients, Sysop-Web-GUI.
- **Konflikt:** die neuere Änderung gilt (Zeitstempel `t`), egal ob aus Client oder Terminal.

**Ablauf**

- *Terminal:* nach dem Login Fragen nur nach den fehlenden Feldern (Enter überspringt, `/AB`
  bricht ab), höchstens alle 30 Tage; danach Befehle `N`, `NL`, `NH`. Schalter
  `[mailbox] ask_profile`. Eine `//`-Zeile beendet die Fragen (Client).
- *Client:* `//CLIENT … caps=…,PROF` → `//OK … prof=<crc>|-`. Gleiche Prüfsumme: nichts über
  Funk. Sonst `//PROF …` (senden) bzw. `//PROF ?` (holen, neuere Fassung gewinnt).
  Einladungsbalken, solange Name oder Locator fehlen („Later“ = eine Woche).
- *Andere Stationen:* `//WHOIS` für die Board-Teilnehmer, im Client eine Woche gemerkt;
  Anzeige mit Entfernung und Richtung vom eigenen Locator.

**Bytes über Funk:** je Login ≈ 10 B (`prof=xxxx`); das Profil selbst (≈ 50 B) nur bei einer
Änderung; je fremder Station einmal pro Woche ≈ 50 B. Der Prompt bleibt unverändert.

**Später:** Home-BBS für die Zustellung persönlicher Post nutzen (White Pages / Forwarding);
CR72 (Prognose auf Anfrage) nimmt den Locator aus dem Profil.

## 22. Feeder-Pi: Content-Lieferanten auf einem Raspberry Pi (entschieden und umgesetzt 24.10.2026)

Anlass: dxfeed und die GeoSphere-Jobs sollen nicht mehr auf dem TinyBox-PC laufen, sondern
auf einem Raspberry Pi 1 (512 MB, SD-Karte 4 GB). Anleitung: `feederpi/README.md`.

- **Leistung:** reicht deutlich. Beide Lieferanten brauchen nur die Standardbibliothek
  (dxfeed zusätzlich PyYAML für die DXCC-Liste), der Sammler ein paar Prozent CPU, die Jobs
  laufen Sekunden. Schwachstellen sind SD-Karte, fehlende Uhr und Netzteil, nicht die CPU.
- **OS:** Raspberry Pi OS Lite (32-bit), Debian 13 „trixie“ (einzige aktuelle Ausgabe für ARMv6).
- **Gleiche Programme, nur andere Starter:** `dxfeed/` und `geosphere_*.py` unverändert;
  systemd-Units und Timer in `feederpi/systemd/` mit denselben Zeiten wie die Windows-Aufgaben
  (Wetter `--region` xx:05, Warnungen 15 min, Prognose 3 h xx:35, DX 05:00). Locator(s) in
  `/etc/default/feederpi`. Unabhängig von der NanoPi-Schiene (`deploy/`, OE3TEC): eigener
  Ordner `feederpi/`, in `build_production.sh` unter `EXCLUDE`.
- **Übergabe = Eingangsordner.** Die Jobs schreiben am Pi in `/run/tinybox/ausgang` (RAM,
  `.tmp` → `.txt` wie bisher). Die brocast-Seite steckt in der Kopfzeile `Brocast:`; die
  Ingest-API von brocastd bleibt auf 127.0.0.1.
- **Der PC holt ab (Pull), der Pi liefert nicht:** `pi_abholung.py` alle 5 min aus der
  Aufgabenplanung (`pi_abholung_einrichten.bat`), schreibt `NAME.abholung.tmp` und benennt in
  `NAME.txt` um. Vorteile: PC bietet keine Freigabe an; ist der PC aus, warten die Dateien
  (gleichnamige ersetzen sich). Eine Abholung = zwei SSH-Verbindungen (`bundle` als tar, `ack`).
- **Sicherheit:** eigener Benutzer `abholer` mit eigenem Schlüssel (`~/.ssh/tinybox_feederpi`),
  erzwungenes Kommando `abholung.sh` (nur `list`, `bundle`, `ack`) in `authorized_keys` und
  sshd, kein Passwort, keine Shell, kein Forwarding. Host-Schlüssel beim ersten Kontakt gemerkt.
  PC prüft Namen (`*.txt`, keine Pfade/Links) und Größe (512 KB). Jobs als `tinybox` mit
  `ProtectSystem=strict`. `unattended-upgrades`. SSH-Passwörter aus, sobald der Admin einen
  Schlüssel hat.
- **Zeit:** NTP (`at.pool.ntp.org`) mit `systemd-time-wait-sync`; Kalender-Timer starten erst
  mit synchroner Uhr (kein Pi 1 hat eine RTC).
- **SD-Karte:** Ausgang und Journal im RAM, keine Auslagerungsdatei, Bytecode einmalig. Auf
  der Karte nur Spot-Datenbank (≈ 1 Schreibvorgang/min), cty.dat, Most Wanted, Warnungszustand.
- **Einrichten:** Imager → `pi_sd_vorbereiten.bat` (schreibt `feederpi\` auf die Boot-Partition:
  Programme, Dictionary, `dxfeed.conf` des PCs, Locator, PC-Schlüssel) →
  `sudo sh /boot/firmware/feederpi/install.sh` → `pi_abholung_einrichten.bat` (schaltet auf
  Wunsch die PC-Aufgaben ab und benennt `dxfeed.conf` in `dxfeed.conf.vor-feederpi` um, damit
  `start_alles.bat` den Sammler nicht mehr startet). Updates per `scp` + `install.sh`.
- **Grenzen:** bis zu 5 min Verzögerung; nach Pi-Neustart sind wartende Dateien weg.
- **Späte Abholung (27.10.2026):** Ist der PC länger weg, staut sich nichts – je Thema eine
  Datei, der nächste Lauf überschreibt sie (nur `dxfeed_neu_<call>` sammeln sich, je wenige KB).
  Weil die TinyBox `Valid:` ab dem Einlesen zählt, zieht `pi_abholung.py` das Alter der Datei
  (Zeitstempel am Pi) von `Valid:` ab; ist die Gültigkeit schon vorbei, wird die Datei nicht
  zugestellt, aber quittiert. Ausfall: einmal `FEHLER`, nach `--warnen-nach` (60 min) einmal
  `WARNUNG`, danach „wieder in Ordnung (letzte Abholung vor …)“ in `logs\pi_abholung.log`.
  Zustand in `data\pi_abholung.state` (JSON, letzte erfolgreiche Abholung).
- **Einschätzung (24.10.2026): TinyBox selbst auf einem zweiten Pi 1** – nur mit Hardware-TNC
  (KISS) denkbar und ohne Reserve; mit Direwolf am selben Pi zu knapp. Eine SSD bringt dort
  nichts (Datenbank wenige MB, kein USB-Boot, USB 2.0 teilt sich den Bus mit dem LAN). Ziel für
  die TinyBox bleibt der NanoPi (`PRODUCTION.md`) bzw. ein Pi ab Modell 3.

## 23. Karussell: Alter der Revision, Funkdauer getrennt von der Mailbox (entschieden und umgesetzt 25.10.2026)

**Befund:** Bulletins vom 5.10. liefen am 25.10. noch alle 30 min. Ursache war ein Fehler:
`aging` rechnete mit `pages.t`, und `t` ist der Zeitpunkt der *letzten Bestätigung* – der
stündliche Sync der TinyBox setzte das Alter jedes Mal auf 0. Die Stufe `24:120` griff nie.
(Dasselbe gilt für den Ablauf `exp`; dort ist es aber gewollt: eine Seite läuft ab, wenn der
Lieferant sie nicht mehr bestätigt.)

**Umgesetzt:**

1. **Alter der Revision** (brocastd, Schema 4): neue Spalte `pages.rev_t`, gesetzt nur bei einer
   neuen Revision. `aging` rechnet damit, `t` bleibt für Ablauf und Frame-Kopf. Alte
   Datenbanken bekommen `rev_t = t` (Alter ab dem Update, bis der Lieferant `born` schickt).
2. **Feinere Staffel als Vorgabe:** `aging = 24:120, 72:360, 168:1440` – ab 24 h alle 2 h, ab
   3 Tagen alle 6 h, ab 7 Tagen einmal am Tag. Nicht ganz still, weil es kein Pull gibt:
   ein Listener, der später einschaltet, bekommt die Seite so noch. Eine Seite: Tag 1 ≈ 48,
   Tag 2–3 12, Tag 4–7 4, danach 1 Aussendung pro Tag.
3. **`born` im Ingest:** Lieferanten dürfen das Entstehungsdatum mitschicken (Unix-Sekunden,
   nur für brocastd, nie auf Funk, nicht Teil des Inhalts-Hashes – nachgeliefert gibt es
   keine neue Revision, nur das Alter wird korrigiert). TinyBox schickt das Erstelldatum des
   Bulletins. Ein geändertes Bulletin bekommt die Staffel `repeat_minutes` neu, altert danach
   aber ab dem ursprünglichen Datum.
4. **Funkdauer unabhängig von der Mailbox:** `[brocast] air_days` in `tinybox.conf` (Vorgabe
   0 = so lange wie in der Mailbox). Ältere Bulletins fehlen im Sync, brocastd zieht sie
   zurück (Listener entfernen sie); in der Mailbox bleiben sie bis `bulletin_expire_days`
   bzw. zur Frist der Rubrik. `exp` der Seite ist höchstens `air_days`.

**Hinweis Betrieb:** eine eigene `brocastd.conf` mit `aging = 24:120` behält diese Einstellung
– für die neue Staffel dort anpassen oder die Zeile löschen.

## 24. Update-Hinweis bei neuem Release (entschieden und umgesetzt 25.10.2026)

**Ziel:** Wer TinyBox, Client, brocastd oder kisshub betreibt, erfährt von einem neuen
GitHub-Release, ohne selbst nachzusehen.

**Entscheidungen (25.10.2026):**
- **Eine Version für alles** (Variante A): `RELEASE` in `prcore/release.py`, Tag `vX.Y.Z`.
  TinyBox übernimmt sie als eigene Version; Client, kisshub, dxfeed behalten ihre
  Datums-Builds. Variante B (eigene Tags je Modul, `tbclient-v…`) erst, wenn die Module
  wirklich getrennt releast werden.
- **Nur Hinweis, keine Installation.** Ein Auto-Updater wäre ein Weg auf jede Station für
  den, der das Konto oder einen Release übernimmt. Update bleibt `git pull`.
- **Ein Bulletin pro Release** in TBNEWS (wie die Client-News), keine Dauerbeschallung.
  Die meisten PR-Nutzer haben Internet; das Bulletin ist für die Nutzer der TinyBox.
  TBNEWS geht nie über Forwarding und nie über brocast – jede TinyBox informiert nur die
  eigenen Nutzer, es kursieren keine Kopien. Ohne eigenen BID-Mechanismus.

**Umsetzung:**
- `prcore/release.py`: `GET https://api.github.com/repos/oe3gas/Tinybox/releases/latest`
  (ohne Entwürfe und Pre-Releases), höchstens einmal pro Tag, Cache-Datei mit ETag
  (`304 Not Modified` zählt nicht gegen das GitHub-Limit von 60/h ohne Token), Timeout 5 s,
  TLS wie üblich geprüft, Fehler/offline still (nur DEBUG). `watch()` als asyncio-Task, erste
  Prüfung 30 s nach dem Start. `ascii_notes()` macht aus dem Release-Text einige ASCII-Zeilen.
- TinyBox (`tinybox/release.py`): Hinweis im Log, bei `STATUS`, in der Web-GUI; Bulletin
  einmal je Tag-Name (gemerkt in `data/release.json` – Neustart oder gelöschtes Bulletin
  bringen es nicht wieder), ein neuerer Release ersetzt das ältere Bulletin.
  `[update] announce = no`: nur Hinweis. Konsole `UPDATE` (jetzt fragen), `UPDATE NEWS`
  (Bulletin von Hand).
- Client 2026.10.25: Banner (nach dem Hinweis der eigenen TinyBox auf einen neueren Client,
  getrennt wegklickbar). brocastd: Zeile auf der Statusseite. kisshub 2026.10.25: Logzeile.
- `[update] check` in allen vier `*.conf.example`; Handbuch 2.9, Release-Ablauf in
  `GIT-ANLEITUNG.md`. Tests: `tests/test_release.py`.

## 25. AXUDP: zweiter Port neben dem Funk (entschieden 25.10.2026, Schritte 1–3 umgesetzt)

**Anlass:** Auf PC1 gibt es nur ein Funkgerät (9600 Bd). TinyBox und Client sollen dort
gemeinsam laufen, und der Client soll vollwertig mitfunken. Über AGW erreicht der Client die
eigene TinyBox nicht: Direwolf sendet das SABM in die Luft und hört sich selbst nicht. Der
Telnet-Testport ist nur ein Kanal ohne Bilder, `Z`, Monitor und UI. Mittelfristig braucht die
TinyBox ohnehin einen Netzweg zu anderen Knoten (Internet, HAMNET).

**Entscheidung (OE3GAS, 25.10.2026):** Die TinyBox bekommt neben dem Funk-Port (`agw` oder
`kiss`, unverändert) einen **AXUDP-Port**. Darauf läuft das eigene AX.25 (`prcore/ax25/link.py`,
wie im KISS-Modus); Session, Chat, Sync und Forwarding darüber wie beim Funk. Der Client
verbindet die Heim-TinyBox über AXUDP, alle anderen Ziele über Funk (AGW an denselben
Direwolf bzw. KISS). Direwolf darf im AGW-Betrieb bleiben (Fork, Qualitätsbalken).

```
                 ┌── Port 1: Funk (agw → Direwolf | kiss → kisshub)  ── 9600 Bd
TinyBox OE3GAS-1 ┤
                 └── Port 2: AXUDP 127.0.0.1:10093 ◄──┐
                                                      │  UDP, eigenes AX.25
tbclient OE3GAS ── Kanal zur Heim-Box ────────────────┘
                └─ alle anderen Kanäle ── Funk
```

**AXUDP (wie BPQ32/LinBPQ "AXIP UDP", XNet, JNOS):** ein UDP-Paket = ein AX.25-Frame
(Adressen, Control, PID, Info, ohne HDLC-Flags) + **FCS** 2 Byte, CRC-16/X.25 (wie HDLC),
niederwertiges Byte zuerst. Falsche FCS → verworfen. Gegenstellen fest in einer Tabelle
Rufzeichen → IP:Port (wie `MAP` bei BPQ); Rufzeichen mit SSID vor Rufzeichen ohne SSID.
Üblicher Port 10093. Direwolf kann kein AXUDP – nicht nötig.

**Sicherheit:** AXUDP hat weder Anmeldung noch Verschlüsselung, das Rufzeichen im Frame ist
nur eine Behauptung.
- Zuerst nur `127.0.0.1`.
- Angenommen wird nur von eingetragenen Gegenstellen: Absender-IP muss zu einer Gegenstelle
  passen **und** das Absender-Rufzeichen des Frames zu dieser Gegenstelle gehören.
  Alles andere wird still verworfen (kein DM, nur gezählt).
- Übers Internet später nur durch WireGuard oder über HAMNET.
- Sysop-Rechte über AXUDP nur von Loopback (wie Telnet), für fremde Gegenstellen nie.

**Schritte:**
1. ✅ `prcore/axudp.py`: FCS, Kodieren/Dekodieren, Gegenstellen (`parse_peers`),
   `AxudpEndpoint` mit derselben Schnittstelle wie `KissTcpClient` (`run`, `send`,
   `connected`, `describe`, Zähler), Ziel aus der Zieladresse des Frames.
   Tests `tests/test_axudp.py`.
2. ✅ TinyBox mit zwei Ports (26.10.2026): `[axudp]` in `tinybox.conf` (`enabled`,
   `listen`, `port`, `peers`; optional `paclen`, `maxframe_ext`, `t1_sec`, `n2`), vorerst
   nur Loopback. `KissPort` bekommt den Transport von außen (`transport=`, Standard
   KISS-TCP) und `half_duplex=False` für AXUDP (keine Sendezeit, Frames pausieren die
   anderen Links nicht). `tinybox/adapters/axudp.py`: `AxudpAdapter` = `KissAdapter` mit
   AXUDP-Port, `app.axudp` neben `app.agw`. Monitor, Bake, brocast, Qualität und
   UI-Chat bleiben am Funk-Port (`owns_ui`); der AXUDP-Adapter ändert `chat.ui_send` nicht.
   Session-Herkunft `axudp` (auch in `ORIGINS` der Nachrichten); `Z` und `IMG` wie über
   Funk, `UI` nicht. AX.25-Werte: v2.2, Fenster 32, PACLEN 256, T1 3 s, T2 0,05 s.
   Dieselbe Station nur einmal (Funk **oder** AXUDP, sonst *busy*). Sysop nur für das
   Sysop-Rufzeichen von einer Loopback-Gegenstelle. Konsole `STATUS`: Zeile `AXUDP:`;
   Web-GUI `/api/status`: `axudp`. Log-Komponente `axudp`. Forwarding über AXUDP noch
   nicht (Schritt 4). Tests `tests/test_axudp_adapter.py`.
3. ✅ Client (26.10.2026, Version 2026.10.26.2): `[tinybox] axudp = 127.0.0.1:10093`,
   `axudp_port = 10094` (eigener UDP-Port), vorerst nur Loopback, nicht mit
   `interface = telnet`. `AxudpPort` (`tbclient/kisslink.py`) = der KISS-Port des Clients
   mit AXUDP-Transport, einzige Gegenstelle die Heim-TinyBox; Frames nicht im Monitor
   (nicht auf der Luft). Weiche `ClientCore.relink()` vor jedem Connect: Heim-TinyBox ohne
   Digi → AXUDP-Link, sonst Funk-Link; `Channel.set_link()` tauscht den Link des Kanals.
   Eingehende Connects über AXUDP bekommen einen AXUDP-Link. Handshake ohne `UI`, mit
   `Z` und `IMG`; Mail-Sync ohne Funkpausen (`Syncer.radio` falsch wie bei Telnet).
   Snapshot: `axudp` (Port offen?) und `link` je Kanal; Kanal-Chip „AXUDP“; Logbuch
   `via axudp`. Offen: brocast hört der Client über seinen Funk-Monitor – meldet Direwolf
   über AGW dem Client die Frames, die die TinyBox sendet? (Funktest auf PC1.)
   Tests `tests/test_tbclient_axudp.py`.
4. Forwarding: `transport = axudp` in `[partner.*]` (z. B. LinBPQ über HAMNET).

Ergänzung 29.10.2026 (PLANUNG 27.2): `[axudp] air_baud` / `txdelay_ms` (TinyBox) und
`[tinybox] axudp_*` (Client) für einen AXUDP-Weg mit Sendezeit, z. B. den simulierten
1200-Bd-Kanal des Testbeds.

**Offen:** UI-Frames an Ziele ohne Gegenstelle (Bake, CQ) über AXUDP – vorerst nicht
gesendet (gezählt als `no_route`). Gegenstellen per Hostname (DynDNS) und dynamisch gelernte
Adressen erst mit Schritt 4.

## 26. NanoPi-Deployment für OE3TEC (umgesetzt 28.10.2026)

**Ziel:** ein aktueller, installierbarer Produktionsbuild für den NanoPi, mit dem OE3TEC
weiterarbeiten kann. Der letzte Build `prod-f16d5a3` war älter als `prcore` (17.10.2026).

**brocastd schreibt nur noch bei echten Änderungen** (offener Punkt 9, P1):
- Pro Verbindung `PRAGMA journal_mode=WAL` und `synchronous=NORMAL` (`store.py`).
- Flüchtiges läuft über `Store._volatile()` ohne Commit und ist trotzdem sofort lesbar
  (dieselbe Verbindung, Web-GUI unverändert): rxlog und `prune_rxlog`, gehörte Stationen
  (`heard`), Sendezeitplan (`mark_sent`), `received_at` und `last_seen`/`t` bei reiner
  Wiederholung einer Seite, `seen` der Rubrikenliste, `dict_seen.last`.
- Geschrieben wird mit `Store.flush()` alle `db_flush_sec` Sekunden (neu in `[brocastd]`,
  Standard 600), beim Beenden (`close()`) und mit jeder echten Änderung, die ohnehin committet.
  Ein Stromausfall kostet höchstens diese Spanne: Empfangslog und Stationsliste fehlen dann,
  und Seiten werden womöglich etwas früher wieder gesendet.
- Wichtig für später: ein `with self.db:` committet beim Verlassen auch dann, wenn darin nichts
  geschrieben wurde. Lesen daher nie in so einem Block, sonst gehen die flüchtigen Daten mit.
- Leeres `txlog_dir` = Sendeprotokoll aus (bisher wurde daraus `logs`).
- SIGTERM beendet brocastd sauber (die systemd-Unit nutzt ohnehin SIGINT).
- Tests: `brocast/tests/test_dbwrites.py` prüft mit einer zweiten Verbindung, was wirklich
  auf der Platte steht.

**Build und Installation:**
- `deploy/install.sh` kopierte `prcore/`, `brocast/zdict/` und `tbclient/` (Version + News)
  nicht nach `/opt/tinybox`, obwohl sie im Build lagen. Ohne `prcore` startet die TinyBox
  nicht, ohne `zdict` sendet brocastd unkomprimiert, ohne News gibt es kein TBNEWS. Behoben.
- `build_production.sh`: `LICENSE` (GPLv3) wird mitgeliefert; `kisshub/`,
  `kisshub.conf.example` und die Linux-Starter `*.sh` stehen unter `EXCLUDE`. Der Build läuft
  ohne „not classified“-Warnung.
- Probe-Installation in einem Linux-Container (systemd nur nachgebildet): TinyBox und
  brocastd starten als Benutzer `tinybox` aus `/opt/tinybox`, Datenbank im WAL-Modus,
  GeoSphere-Skripte und `dxfeed` laufen an. Nicht getestet: echte NanoPi-Hardware, systemd,
  Direwolf am NanoPi – das ist der nächste Schritt für OE3TEC.

**Noch offen für den NanoPi:**
- Offener Punkt 6: Wie viele AGW-Clients lässt Direwolf am NanoPi zu? TinyBox und brocastd
  hängen beide am AGW-Port.
- PRAGMAs für die TinyBox-Datenbank (Punkt 9, letzter Vorschlag, niedrige Priorität).

---

## 27. Testbed `tbtest` (entschieden und umgesetzt 29.10.2026)

**Anlass:** Mit AXUDP (Abschnitt 25) erreicht man die TinyBox ohne Funk. Damit lässt sich ein
Testtool bauen, das mehrere User gleichzeitig mit der Box arbeiten lässt – lokal, ohne
rechtliche Fragen, reproduzierbar.

**Entscheidungen (OE3GAS, 29.10.2026):**
1. Client-User laufen als **echter Client-Kern** (`tbclient.core.ClientCore`) im
   tbtest-Prozess, ohne Web-GUI, je User ein Kern mit eigenem Datenordner und eigenem
   AXUDP-Port (Variante A; nicht 10 tbclient-Prozesse, kein eigener Mini-Client).
2. **Fiktive OE- und DL-Rufzeichen** (`OE1TBA`, `DL1TBB` … `DL5TBJ`, Box `OE3TBX-1`, Sysop
   `OE3TBS` = keiner der User). Nur Loopback, nichts auf Funk.
3. **Eigenes Testbed-Verzeichnis**, das Gerhard anlegt (`E:\tinybox-testbed`, Standard =
   `tinybox-testbed` neben dem Repo, sonst `-D` oder `TBTEST_DIR`). Der Code liegt im Repo
   (`tbtest/`, `tbtest.bat`), Daten, Konfiguration und Berichte nur im Testbed-Verzeichnis.
4. **Ziel ist nur die eigene Test-Box**, nie die echte TinyBox: tbtest startet
   `python -m tinybox -c <testbed>/tinybox.conf` als eigenen Prozess mit eigener DB und
   eigenen Ports (AXUDP 10193, Web 8180, Telnet 6400).
5. **Voller Funktionsumfang** der TinyBox inkl. Chat über den Client: `conn`, `send`, `bull`,
   `read`, `kill`, `info` (übrige Terminal-Befehle), `chat`, `img`. Die Funkstrecke (Verlust,
   1200/9600 Bd) wird jetzt **nicht** untersucht.

**Aufbau:**
- `tbtest init` schreibt `tbtest.conf` (Rufzeichen, Ports; darf geändert werden) und erzeugt
  daraus `tinybox.conf`: `interface = kiss` an die **Funk-Attrappe** (KISS-TCP-Server in
  tbtest, Port 10190, schluckt und zählt jeden Frame), `[axudp]` mit allen Usern als
  Gegenstellen, `max_users = 20`, Rubrik `TBTEST`, Boards TREFF/TECH/RUNDE, brocast, Inbox,
  Update-Abfrage und Bake aus. Auch die Clients bekommen die Attrappe als Funk-Port – kein
  Frame der Testumgebung kann einen echten Sender erreichen.
- Terminal-User: `prcore.kissport.KissPort` mit `AxudpEndpoint`, liest wie ein Mensch (Prompt,
  Fragen ohne Zeilenende), beantwortet beim ersten Login die Profilfragen (CR73).
- Ende-zu-Ende-Prüfung (`tbtest/ledger.py`): jede Nachricht trägt `TBTEST <schlüssel>
  <prüfsumme>`, Chat-Zeilen `tbt <schlüssel>`, Bilder ihren Hash. Schlussrunde: jeder User liest
  am Ende alles Ungelesene. Chat: wer beim Senden im Board war (2 s Spielraum), muss die Zeile
  bekommen; Clients müssen ihre eigene Zeile zurückbekommen.
- Bericht `runs/<zeit>/report.txt` + `result.json`: Zeiten je Funktion (min/Ø/p95/max), je
  User, Ende-zu-Ende-Bilanz, Frames auf der Attrappe (Connected-Mode muss 0 sein), Fehlerzeilen
  der Test-Box. Exit-Code 0/1/2. Stirbt die Box, endet der Lauf sofort.
- Tests `tests/test_tbtest.py` (inkl. eines kurzen echten Laufs mit freien Ports).

### 27.2 Teil 2: simulierter Funkkanal, bis 30 User, eigener Client (29.10.2026)

**Entscheidungen (OE3GAS, 29.10.2026):**
1. Die Simulation von **Kanalbelegung und Übertragungsqualität** sitzt **im AXUDP-Weg**, KISS
   spielt keine Rolle: ein UDP-Relais in tbtest (`tbtest/channel.py`, Port 10192) zwischen Box
   und Usern. Die Box hat alle User als Gegenstellen mit der Adresse des Relais.
2. Qualität: **Profile + Zufall** – good / medium / poor (1 / 8 / 25 % Frame-Verlust für
   256 Byte, je Richtung, kürzere Frames seltener) und ein Anteil „hidden“, mit dem Seed
   verteilt; je Rufzeichen in `tbtest.conf` `[quality]` festlegbar.
3. **Bis 30 User** (fiktive OE/DL-Rufzeichen, die ersten zehn wie bisher). `max_users` der
   Test-Box 50.
4. **Gerhards eigener Client** hängt ebenfalls per AXUDP am Kanal:
   `tbclient-testbed.conf` (von `tbtest init`), Rufzeichen OE3GAS (nicht Sysop),
   Web-GUI 7745, eigener Datenordner `guest/`. `tbtest run -t 0` läuft bis Strg+C.

**Kanalmodell:** eine gemeinsame Halbduplex-Frequenz, ein TNC pro Station: Sendewarteschlange,
Carrier Sense + p-Persistence (63 / 100 ms), ein Tastendruck = TXDELAY + bis zu 7 Frames,
Sendezeit nach Bitrate (+3 % Bitstuffing). Ein Frame geht beim Empfänger verloren bei
Überlappung mit einem Sender, den er hört, wenn er selbst sendet, oder durch Rauschen
(Profil). Versteckte User hören die anderen User nicht (und umgekehrt); die Box hört alle,
alle hören die Box. Jeder, der den Sender hört, bekommt eine Kopie des Frames (Mithören).
Bericht: Belegung des Kanals in %, je Station Frames, Bytes, Sendezeit, Wiederholungen
(gleiches I-Frame nochmals), Verluste durch Rauschen / Kollision, Wartezeit in der
Warteschlange.

**AXUDP mit Sendezeit (TinyBox und Client):** Ohne Wissen um die Sendezeit läuft T1 schon,
während die Frames noch in der Warteschlange des Kanals stehen – Wiederholungssturm. Deshalb
neu: `[axudp] air_baud` / `txdelay_ms` in `tinybox.conf` und `[tinybox] axudp_air_baud` /
`axudp_txdelay_ms` / `axudp_paclen` / `axudp_maxframe` / `axudp_t1_sec` / `axudp_n2` in
`tbclient.conf` (Client 2026.10.29). Mit `air_baud` > 0 ist der AXUDP-Port halbduplex wie ein
KISS-Port: T1 startet nach der geschätzten eigenen Sendezeit, gehörte Frames (die Kopien des
Kanals) halten T1 an, T2 1,5 s. Damit eine Station auch Frames anderer Stationen „hört“,
nimmt der AXUDP-Endpunkt in diesem Modus Frames von der Adresse einer Gegenstelle an, die
nicht an ihn gehen (nur für die Kanalbelegung, zählt `heard`); ein Frame an das eigene
Rufzeichen von einem Fremden wird weiter verworfen. Standard bleibt 0 = ohne Sendezeit, wie
bisher. Testbed: PACLEN 256, Fenster 4, T1 6–24 s, N2 10, 1200 Bd, TXDELAY 300 ms.

**Befund beim ersten Lauf (10 User, 1200 Bd):** Ein SABME, das wegen belegtem Kanal in der
Warteschlange des TNC hängt, wird nach Ablauf von T1 ein zweites Mal eingereiht; kommt es
nach dem UA an, setzt die Box die Verbindung zurück („link re-established – data in flight
may be lost“), Begrüßung und Prompt sind weg, beide Seiten warten. Abhilfe im Testbed: der
Terminal-User drückt nach längerer Stille Enter (wie ein Mensch). Für die TinyBox ist offen,
ob sie nach einem Reset den Prompt von sich aus noch einmal schicken soll.

Weitere Punkte: `--air 0` schaltet den Kanal ab (schneller Funktionstest), Standardwerte je
nach Kanal (Pausen 30–180 s, Chat 60–180 s, Timeouts 300 s, Nachrichten bis 3 KB); erstes
Strg+C beendet die Aktionen und macht Schlussrunde + Bericht, zweites bricht ab; ein
Terminal-User trennt nach einer fehlgeschlagenen Aktion und beginnt neu.

**Werte je Bitrate (OE3GAS, 29.10.2026):** `tbtest.conf` hat je Bitrate einen Abschnitt
`[air.0]`, `[air.1200]`, `[air.9600]` (weitere möglich); ein Lauf nimmt alle Werte aus dem
Abschnitt seiner Bitrate (`--air`, sonst `[radio] air_baud`): Kanal (TXDELAY, persist,
slottime), AX.25 über AXUDP (PACLEN, Fenster, T1, N2) und Verhalten der User (Pausen,
Chat-Aufenthalt, Timeout, größte Nachricht/Bild, Dauer). 1200: 300 ms, 63/100 ms, Fenster 4,
T1 6 s, Pausen 30–180 s; 9600: 150 ms, 63/50 ms, Fenster 7, T1 3 s, Pausen 10–60 s. Der eigene
Client bekommt je Bitrate eine Konfiguration `tbclient-testbed-<baud>.conf`.

**Offen:** Forwarding (zusammen mit fwdsim). Über AXUDP gehen Chat-Ereignisse als I-Frames an
jeden Teilnehmer statt als UI-Frame – auf dem simulierten Kanal teurer als auf einer echten
Frequenz.

## Quellen

- Forwarding-Konzept (Claude-Doc): https://claude.ai/code/artifact/ed861fd0-7519-4796-8f4b-8de6ab3fbd2a
- W0RLI-BBS-Spezifikation vom 12.10.1998: `docs/w0rli/w0rli-bbs-spec-12oct1998.pdf`
- AEA PK-232MBX Operating Manual, Kap. 5 (nur Orientierung): https://www.dl0bn.de/dc7xj/Anleitungen/AEA%20PK-232MBX_Manual.pdf
- Direwolf-Dokumentation (AGW-Interface): https://github.com/wb2osz/direwolf/tree/master/doc
- DXSpider-Wiki, Verbinden mit einem Knoten: https://wiki.dxcluster.org/wiki/How_to_connect
- AD1C Country Files (cty.dat): https://www.country-files.com
- Raspberry Pi OS (Downloads, unterstützte Modelle): https://www.raspberrypi.com/software/operating-systems/
