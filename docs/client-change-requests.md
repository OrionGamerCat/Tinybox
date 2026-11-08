# TinyBox-Client – Change Requests

Gesammelt beim ersten Test PC1 ↔ PC2 (OE3GAS, OE3TEC) am 09.10.2026, ergänzt laufend.
Stand: 07.11.2026 (CR79 Stufe 1 umgesetzt)

## Übersicht

| CR | Inhalt | Status |
|---|---|---|
| 1 | Einzelnes Emoji als Nachricht groß anzeigen (≥ 2×) | ✅ (c376e16) |
| 2 | Emojis: 🤮 💩 ❓ ❗ und Pfeile dazu, 🗼 raus, Auswahl nach Gruppen sortiert | ✅ siehe unten |
| 3 | MOTD pro Board | ✅ siehe unten |
| 4 | Schrift: `_fett_` und Monospace für ASCII-Art | ✅ `_fett_`, `` `mono` `` (c376e16) |
| 5 | URLs erkennen und klickbar | ✅ (c376e16) |
| 6 | „Leave board“ im Chat statt in den Settings | ✅ (c376e16) |
| 7 | Bug: APRS-Symbol-Änderung wirkt erst nach Board-Wechsel – soll sofort wirken (Avatar-Update aller bleibt) | ✅ siehe unten |
| 8 | Eigene Reaktion sofort anzeigen | ✅ blass bis Echo, nach 2 min ohne Echo zurück (c376e16) |
| 9 | Zeilenumbruch mit Shift+Enter | offen – braucht Zeilenumbruch-Kodierung über Funk (Protokoll ist zeilenbasiert) |
| 10 | Mehrzeilige Texte einfügen | offen – wie CR9 |
| 11 | Sticker und Animationen | Sticker ✅ (Animationen offen) – siehe unten |
| 12 | Kleine Bilder im Chat (Verkleinern im Browser, BlurHash-Vorschau, Laden beim Antippen) | ✅ siehe unten |
| 13 | History wählbar beim Einchecken („last n lines?“, Enter = keine) | ✅ siehe unten |
| 14 | Zitatfunktion (Nachricht antippen → Zitieren, gekürzt über der Antwort) | ✅ siehe unten |
| 15 | @CALL hebt Nachricht beim Empfänger farbig hervor | ✅ (c376e16) |
| 16 | Anstupsen: Klick auf Call in Teilnehmerliste → kurze persönliche Nachricht als Pop-up mit Klingelton | offen – über Funk für Mithörer lesbar |
| 17 | „Cry out“: max. 32 Zeichen, sehr große Schrift in einer „Bang!“-Blase | ✅ siehe unten |
| 18 | Versionskontrolle: Client prüft, ob er aktuell ist; User wird informiert und aufgefordert, die neue Version zu holen | ✅ siehe unten |
| 19 | Rubriken sind Sysop-Sache: feste Rubrikenliste, User schreiben Bulletins nur an ALL und diese Rubriken (Auswahl im Composer), Forwarding nimmt nur diese Rubriken an | ✅ siehe unten |
| 20 | Verbindungsqualität: 1–5 Balken neben jeder Station im Board, Meldung bei Verbindungsabbruch, Befehl `STAT` | ✅ siehe unten |
| 21 | Bulletins zwischen Rubriken verschieben und kopieren | Entschieden: nur Sysop, nur Sysop-Konsole und Sysop-Weboberfläche – noch nicht umgesetzt |
| 22 | Sysop-Konsole: Befehl RESTART (Neustart, z. B. nach Änderung in tinybox.conf) | ✅ siehe unten |
| 23 | BUG – Emoji-Picker: Schnellauswahl-Leiste verdeckt die Gesamtauswahl | ✅ siehe unten |
| 24 | BUG – Schnellauswahl-Leiste ragt in der PC-Ansicht rechts aus der Chat-Spalte | ✅ siehe unten |
| 25 | Board antippen: Button einfärben, bis man im Board angekommen ist | ✅ siehe unten |
| 26 | Delta-Abgleich: Mail-/Bulletin-Sync mit minimaler Payload (ein Wechsel, nur Änderungen, kleine Texte gleich mit, Z für Köpfe) | ✅ siehe unten |
| 27 | Persönliche Post an mehrere Empfänger (`OE3TEC,OE1ABC`): Text einmal über Funk, TinyBox legt je Empfänger eine eigene Nachricht an | ✅ siehe unten |
| 28 | Emoticons ↔ Emojis: `;-)` beim Tippen sofort als Emoji, Terminal-Eingabe `;-)` im Client als Emoji, Emojis mit ASCII-Form gehen als `:-)` statt `~0B` über Funk | ✅ siehe unten |
| 29 | Terminal: Ausgaben über 10 Zeilen seitenweise mit „continue/abort“ (`L` und jeder andere Befehl), damit nicht hunderte Titel über die Luft laufen | ✅ – seit CR40 ersetzt durch Hinweis + Abort |
| 30 | Bild-Upload eines Teilnehmers sichtbar machen: „OE1ABC uploading picture“ mit Fortschrittsbalken | ✅ siehe unten |
| 31 | Kommentarbezug eindeutig machen (bisher Rufzeichen + Minute, mehrdeutig) | ✅ siehe unten |
| 32 | Logfile zum Debuggen mit Claude: eine Datei pro Tag, feste Spalten, Session-Nummer, Startblock, `LOG`-Befehl | ✅ siehe unten |
| 33 | Teilnehmernummern und Verbindungsdetails im Client (Detailansicht je Station) | ✅ siehe unten |
| 34 | Bildübertragung schneller (256-Byte-Frames, Bild am Stück an Direwolf) | ✅ siehe unten |
| 35 | Bug: Bekanntes Bild ließ sich nicht erneut in den Chat stellen – Upload brach stumm ab | ✅ siehe unten |
| 36 | Bildgröße im Chat sichtbar (klein bleibt klein), Größenwahl mit Zahlen in den Knöpfen | ✅ siehe unten |
| 37 | brocast-Listener: Ansicht „Mit Trennlinien“ raus, Teile-Knöpfe nur im Teletext, Teletext in echter Teletext-Optik (Pixelschrift, großer Zeilenabstand) | ✅ siehe unten |
| 38 | Teletext: Zeilenabstand auf Zeichenhöhe, brocast-Schriftzug nach der Teletext-Titelseite über jeder Seite; Bildkonverter (Bilder als Mosaik-Bulletins, nur station) | ✅ siehe unten |
| 39 | TinyBox-Web-GUI: „Rubrics“ aufklappbar in der Seitenleiste, Klick zeigt die Bulletins dieser Rubrik | ✅ siehe unten |
| 40 | Sync beim Anmelden: alle Köpfe (eigene Mails + abonnierte Rubriken), persönliche Mails ≤ 256 Byte gleich mit, sonst Text erst beim Anklicken; geordneter Abort mit Restanzeige und Zeitschätzung; Terminal: Abort statt 10-Zeilen-Seiten (CR29); Frist je Rubrik | ✅ siehe unten |
| 41 | KISS-Mode: Kanal- und kisshub-Werte in der Sysop-Web-GUI (Kanalauslastung, gehörte Stationen, TNC-Zustand, Wartezeit im Hub) für das Qualitäts-Monitoring | ✅ siehe unten |
| 42 | Freier Connect: „Connect to:“ in der Titelleiste statt fest verdrahtetem OE3GAS-1, Verlauf der letzten Ziele, Titelleiste einzeilig mit Zustands-Icons (connecting mit Zähler, connected, disconnecting, no answer / disconnected by) | ✅ siehe unten |
| 43 | Terminalmodus: Gegenstelle ist keine TinyBox → Terminal statt Chat, kein `//CLIENT`; bei einer TinyBox per Menü | ✅ siehe unten |
| 44 | Verbindungslogbuch in TinyBox und Client: Gegenstation, Connect, Disconnect, Dauer, Bytes; unbegrenzt, Export CSV und ADIF; jeder User sieht seine Connects (`QSO`) | ✅ siehe unten |
| 45 | Multi-Connect im Client: bis 5 Verbindungen, umschaltbar (Kanäle), Monitor-Kanal | ✅ siehe unten |
| 46 | Client über kisshub (`link = kiss`) mit eigenem AX.25 – vollwertiges PR-Programm ohne Direwolf und ohne TinyBox; eingehende Connects | ✅ siehe unten |
| 47 | Mail in der Outbox sofort aussenden, nicht erst beim nächsten Sync | ✅ siehe unten |
| 48 | TinyBox-Bake: Text und Intervall in `[beacon]`, neue Post als „Mail for:“-Liste in der Bake | ✅ siehe unten |
| 49 | Suche in Mails und Bulletins: Client (Suchfeld), TinyBox (Befehl `F`), Sysop-Weboberfläche | ✅ siehe unten |
| 50 | Monitor: alter Monitor aus den Settings raus, ohne „fm“, Rufzeichen farbig, Filter nach Text und nach TinyBox-Sonderframes, Clear | ✅ siehe unten |
| 53 | TinyBox-Web-GUI: Monitor auf schwarzem Hintergrund (wie im Client) | ✅ siehe unten |
| 73 | Benutzerprofil: Name, Locator, Home-BBS in TinyBox und Client (Terminal-Fragen, Formular im Client, `//PROF`, `//WHOIS`) | ✅ siehe unten (Funktest offen) |
| 79 | APRS-Statistik: Netzgraph (Bubbles, Knoten, Wege) mit Filter nach Paketart, Geräte-Torte | ✅ Stufe 1 siehe unten (Stufe 2 offen) |

## CR2 – Emojis (erledigt 11.10.2026)

- Neu in `emoji.json` (Version 2, angehängt): 🤮 `~1Q`, 💩 `~1R`, ❓ `~1S`, ❗ `~1T`, Pfeile ⬆️ ➡️ ⬇️ ⬅️ ↗️ ↘️ ↙️ ↖️ (`~1U` … `~21`).
- 🗼 (`~10`, der rote Turm) wird nicht mehr angeboten: Eintrag in `"hidden"`. Kommt der Code an, wird er weiter angezeigt – Codes ändern nie ihre Bedeutung.
- Die Auswahl ist nach Gruppen sortiert (`"picker"` in `emoji.json`): Gesichter, Hände & Herz, Zeichen & Pfeile, Funk & Technik, Wetter & Natur, Unterwegs, Essen & Feiern, Tiere & Sonstiges.

## CR7 – APRS-Symbol sofort (erledigt 11.10.2026)

- Ursache: Das Symbol ging nur beim Betreten eines Boards mit (`+CALL sym`); eine Änderung meldete der Client zwar der TinyBox, aber niemand gab sie an das Board weiter.
- Neu: Der Client sendet `//SYM <symbol>` (`-` = keins). Ist er in einem Board, bekommen alle Clients dort sofort das Ereignis `=CALL <symbol>` (bzw. `=CALL`), per UI-Frame ca. 12 Byte Nutzdaten. Alle Avatare dieser Station wechseln das Symbol. Terminal-Teilnehmer bekommen nichts.
- Außerhalb eines Boards wird das Symbol nur gemerkt und beim nächsten Betreten mitgeschickt. Gleiches Symbol noch einmal: kein Ereignis.
- Client-Version 2026.10.11.2. Tests in `tests/test_clientproto.py` und `tests/test_tbclient.py`; Praxistest mit TinyBox und zwei Clients.

## CR11 – Sticker und Animationen

### Grundsatz

- **Über Funk geht nur ein kurzer Code** (wie bei den Emojis, ca. 3 Byte), nie das Bild.
- **Die Bilder liegen fest im Client** und werden versioniert wie `emoji.json`. Ein neues Paket kommt mit einem neuen Client (Git); später ist auch die Verteilung über das brocast-Dictionary denkbar.
- **Start mit einer festen Auswahl**, dann schauen, wie sie genutzt wird.
- Offen: Format des Codes im Chattext (z. B. eigenes Escape-Zeichen) und wie Terminal-Teilnehmer ihn sehen.

### Quellen (Recherche 10.10.2026)

- Fertige, frei nutzbare **Funk-Sticker gibt es praktisch nicht**. Radioddity „Ramoji“ (6 animierte GIFs: CQCQ, QRL, Morse, Roger, Over, 73) ist „free to use“, aber © Radioddity ohne Lizenz – Weitergabe nur nach Rückfrage.
- Allgemeine Emojis mit offener Lizenz: **Noto Emoji Animation** (CC BY 4.0; Lottie/WebP/GIF), OpenMoji (CC BY-SA 4.0), Microsoft Fluent Emoji (MIT, statisch), Twemoji (CC BY 4.0). Quelle im Client-„About“ nennen.
- Erste Idee: Funk-Sticker selbst als SVG zeichnen. Ersetzt durch das von Gerhard gelieferte Set (siehe unten). Allgemeine Animationen weiter von Noto.

### Sticker-Set (initiales Set, 20 Stück, 11.10.2026)

Von Gerhard geliefert, einzeln freigestellt. Dateien: `tbclient/web/stickers/` (WebP mit Transparenz, je ca. 20–37 KB, zusammen ca. 0,5 MB). Übersicht: `docs/sticker-set.png`. Die gezeichneten SVG-Entwürfe vom 10.10. sind damit ersetzt (in der Git-Historie noch vorhanden).

| Nr. | Datei | Motiv |
|---|---|---|
| 1 | `01-cq.webp` | „CQ CQ CQ“, Mikrofon und Transceiver |
| 2 | `02-73.webp` | „73!“, OM mit Daumen hoch |
| 3 | `03-88.webp` | „88 ❤“, zwei Funker formen ein Herz |
| 4 | `04-qsl.webp` | „QSL? / QSL ✓“ mit QSL-Karten |
| 5 | `05-59plus20.webp` | „5/9+20“, jubelnder OM, Signalbalken |
| 6 | `06-qrm.webp` | „QRM!“, genervter OM |
| 7 | `07-qrt.webp` | „QRT – gute Nacht“, Shack bei Nacht, Katze |
| 8 | `08-qrz.webp` | „QRZ?“, OM mit Kopfhörer im Dunkeln |
| 9 | `09-widerstand.webp` | „Widerstand“, muskulöser Widerstand mit Sonnenbrille |
| 10 | `10-pileup.webp` | „PILEUP“, schreiende Menge |
| 11 | `11-magic-smoke.webp` | „Magic Smoke“, rauchendes Gerät |
| 12 | `12-swr-1-1.webp` | „SWR 1:1“, zufriedenes Messgerät |
| 13 | `13-swr-unendlich.webp` | „SWR ∞“, verzweifelter OM |
| 14 | `14-dummy-load.webp` | „Dummy Load“, cooler Kühlkörper |
| 15 | `15-band-offen.webp` | „Band offen!“, Erdkugel mit Verbindungen |
| 16 | `16-band-tot.webp` | „Band tot“, toter Planet |
| 17 | `17-bin-dxen.webp` | „Bin DXen“, Funken am Strand |
| 18 | `18-kaffee.webp` | „Kaffee im Shack“, Tasse „DX FUEL“ |
| 19 | `19-dipole.webp` | „All you need is a Dipole!“ |
| 20 | `20-antennenbau.webp` | „Bin am Antennenbauen“ |

- **Entschieden (11.10.2026):** Jeder Sticker hat einen **Kurznamen mit höchstens 4 Zeichen** (Buchstaben/Ziffern, Varianten mit Ziffer: CQ1, CQ2, SWR1, SWR2). Terminal-Teilnehmer sehen **`[STK]CQ`**.
- Vorschlag zur Umsetzung: über Funk geht genau dieser Text `[STK]CQ` als ganzer Beitrag (7–9 Byte). Damit braucht es keine Umsetzung für Terminal-Teilnehmer, und sie können selbst Sticker senden, indem sie `[STK]CQ` tippen.
- Kurznamen (von Gerhard bestätigt 11.10.2026): 01 CQ, 02 73, 03 88, 04 QSL, 05 S9P, 06 QRM, 07 QRT, 08 QRZ, 09 OHM, 10 PILE, 11 SMOK, 12 SWR1, 13 SWR2, 14 DUMY, 15 OPEN, 16 DEAD, 17 DX, 18 COFE, 19 DIPO, 20 ANT. Liste: `tbclient/web/stickers/stickers.json` – Namen ändern nie ihre Bedeutung, neue nur anhängen.

### Umsetzung Sticker (✅ 11.10.2026)

- **Über Funk** genau `[STK]CQ` als ganzer Beitrag (7–9 Byte), auch mit Zitat davor (`~^OE3TEC 1402 [STK]73`). Terminal-Teilnehmer sehen `[STK]CQ` und können Sticker so auch selbst senden.
- **Client:** Knopf 🏷️ neben dem Emoji-Knopf öffnet die Sticker-Auswahl, Antippen sendet sofort. Anzeige ohne Sprechblase, ca. 128 px; Reaktionen und Zitieren gehen wie bei Text. Unbekannter Name (neuerer Client) → der Text `[STK]XYZ`.
- Client-Version 2026.10.11.9.

### Animationen (Vorschlag, 10 Stück – noch nicht entschieden)

| Nr. | Animation | Herkunft |
|---|---|---|
| 1 | Antenne strahlt Wellen ab (CQ) | selbst |
| 2 | Morsetaste klopft | selbst |
| 3 | S-Meter-Zeiger schnellt auf 9+ | selbst |
| 4 | Signal hüpft an der Ionosphäre (Skip) | selbst |
| 5 | Blitz schlägt in die Antenne | selbst |
| 6 | Satellit zieht vorbei (Pass) | selbst |
| 7 | 🎉 Konfetti (Erstverbindung, neues DXCC) | Noto |
| 8 | 😂 Lachen | Noto |
| 9 | 🔥 Feuer | Noto |
| 10 | 👋 Winken (Gruß, 73) | Noto |

- Offen: Auswahl bestätigen; Verfügbarkeit 7–10 in der Noto-Liste prüfen; Technik für eigene Animationen (animiertes SVG/CSS vs. Lottie).

## CR12 – Kleine Bilder im Chat (Konzept 11.10.2026, ✅ 12.10.2026)

### Entscheidungen (Gerhard, 11.10.2026)

1. **Nur Chat.** Binär-Anhänge in Mails werden später extra betrachtet (dann prüfen, was LinBPQ/FBB heute statt 7PLUS können, z. B. Winlink B2F-Anhänge bei LinBPQ, `#BIN#` bei FBB).
2. **Maximalgröße** mit Standardwert (Vorschlag 8 KB), vom Sysop einstellbar. Der User sieht **vor dem Hochladen**, wie lange Upload und Download dauern, und entscheidet selbst.
3. **Vorschau = BlurHash** (unscharfe Farbvorschau, ca. 20–30 Zeichen).
4. **Upload-Dialog ohne Vorschau:** Bild wählen → Hinweis „Das Bild wird auf kleine Größe reduziert: ca. 5,1 KB, Upload ca. 1 min, Laden für andere ca. 1 min (1200 Bd)“ → **OK** oder **Abbruch**.
5. **Aufbewahrung wie die History des Boards.** Auch beim Laden der History kommt nur der Verweis mit BlurHash; das Bild holt man mit Antippen. Unter dem BlurHash steht die Ladezeit – über Funk geht dafür nur die Größe, die Zeit rechnet der Client selbst aus.

### Grundsätze

- **Kompression = Bildformat, nicht LZHUF.** WebP (bzw. JPEG als Rückfall) ist schon komprimiert, LZHUF bringt darauf nichts. Gespart wird mit Auflösung (z. B. 320 px an der langen Seite) und Qualität. Der Browser macht das selbst (`canvas.toBlob("image/webp", q)`): er verkleinert und senkt die Qualität schrittweise, bis das Bild unter die Maximalgröße passt.
- **Kein 7PLUS** zwischen Client und TinyBox: AX.25 connected ist 8-Bit-transparent und gesichert (CRC + Wiederholung). Übertragen wird binär in Stücken mit Offset wie beim Mail-Abgleich (`//PART`), ein abgebrochener Transfer setzt fort.
- **Über Funk im Chat nur der Verweis**, nie das Bild. Wer es sehen will, holt es per I-Frame bei der TinyBox.
- **TinyBox dekodiert keine Bilder:** sie speichert einen Blob unter seinem Hash, prüft nur Größe und Dateikennung (WebP/JPEG). Gleiches Bild = ein Exemplar.

### Ablauf (Vorschlag, Details bei der Umsetzung)

- **Chat-Beitrag** mit Bild: Escape `~#` + Kennung + Größe + Seitenverhältnis + BlurHash, z. B.
  `~#3fa9c2d1 5120 4x3 LEHV6nWB2yk8pyo0adR*.7kCMdnj` (ca. 45 Byte). Optional danach Text als Bildunterschrift.
- **Hochladen:** Client sendet `//IMGPUT <hash> <größe>` und die Daten in Stücken (z. B. 256 Byte, mit Pausen, damit Chat-Zeilen dazwischen durchkommen); TinyBox antwortet `//IMGOK` bzw. `//ERR img too_large`. Erst dann geht der Chat-Beitrag hinaus.
- **Laden:** Antippen → `//IMG <hash> <offset> <länge>` → Antwort wie `//P` (binär). Der Client merkt sich geladene Bilder.
- **Anzeige:** BlurHash im richtigen Seitenverhältnis mit „🖼 5,1 KB · ca. 1 min · antippen zum Laden“, nach dem Laden das Bild in der Bubble. Die Ladezeit schätzt der Client aus Größe und Link (Baudrate bzw. gemessene Rate beim Abgleich).
- **Terminal-Teilnehmer** sehen z. B. `[Bild 5,1 KB – nur im TinyBox-Client]`.
- **Aufbewahrung:** Ein Bild wird gelöscht, wenn keine Chat-Zeile in der History es mehr verwendet.

### Weitere Entscheidungen (Gerhard, 11.10.2026)

- **Live-Boards** (`live`, z. B. RUNDE): **keine Bilder.**
- **Maximalgröße:** Standard 8 KB, in `tinybox.conf` `[chat]` `image_max = 8k`.
- **Abschaltbar durch den Sysop** pro Board in der `tinybox.conf` (Vorschlag: Zusatz in `[chat_boards]`, z. B. `TECH = 30d  Technical questions  noimg`, oder eigener Schlüssel – bei der Umsetzung festlegen). Der Client zeigt den Bild-Knopf nur in Boards, die Bilder erlauben (kommt mit der Board-Liste).
- **Ladefortschritt** im Chat anzeigen: beim Hochladen in der eigenen Bubble, beim Laden über dem BlurHash (Balken + „2,3 / 5,1 KB“). Möglich, weil in Stücken übertragen wird.

### Umsetzung (✅ 12.10.2026) – Payload nochmals durchgesehen (Gerhard, 12.10.2026)

Vor dem Codieren wurde jedes Feld, das über die Luft geht, auf Bytes geprüft. Abweichungen vom Ablauf-Vorschlag oben:

- **Verweis:** `~#` + Hash **6 Hex** + Größe **2 Hex in 64-Byte-Schritten** + BlurHash, **ohne Trennzeichen** (Hash und Größe sind fix lang, der BlurHash beschreibt seine Länge selbst) → **26–32 Byte** statt ~48. Beispiel: `~#a1b2c350BjElSA|nsR,x$0n~ Blick vom Berg`.
- **Bildmaße gehen nicht über Funk.** Kein fester Rahmen: Form und Seitenverhältnis bleiben, der Client formt den Platzhalter aus den BlurHash-Komponenten (3×2 quer, 2×3 hoch, 3×3 quadratisch), die Pixel kommen mit dem Bild. Der Browser verkleinert auf höchstens 320 px lange Seite und senkt dann Qualität/Auflösung, bis es unter das Limit passt.
- **BlurHash 16–22 Zeichen** (3×2 / 2×3 / 3×3) statt 28.
- **Kein Stückeln, kein Ack:** AX.25 ist gesichert. Upload `//IMGPUT <hash> <bytes>` → `//IMGGO <hash> <have>` → Bytes am Stück → `//IMGOK`; Download `//IMG <hash> [<offset>]` → `//I <hash> <offset> <total>` + Bytes am Stück. Overhead je ≈ 35–55 Byte statt 8–18 %. Der Client gibt die Bytes stückweise mit Pause an Direwolf (`tbclient.conf [images]`) und wartet, bis das Stück davor gesendet ist (AGW `Y`) – kostet keine Luft. Fortschritt: beim Hochladen aus den übergebenen Stücken, beim Laden aus den eintreffenden Bytes.
- **Erlaubnis** kommt beim Betreten (`//IN … img`, 4 Byte), nicht in der Board-Liste (`//B` ließe sich nicht erweitern, ohne alte Clients zu brechen). Abschalten pro Board: `noimg` direkt nach der Aufbewahrung (`TECH = 30d noimg Technical questions`).
- Terminal-Teilnehmer lesen `[Image 5.0 KB - TinyBox client only]` (auch `/H`-Verlauf und Reaktionsziel). Bilder nur über Funk (AGW) wie Cap Z; Cap `IMG`.
- Dateien: `tinybox/chatimg.py` (Protokoll, Referenz, Prüfung, Purge), `tbclient/images.py` (Transfer, Ablage `data/tbclient/images/`), BlurHash-Encoder/-Decoder in `app.js`. Protokoll ausführlich in `PLANUNG.md` 12.10.

### Fehler beim ersten Funktest und Behebung (✅ 12.10.2026, Client 2026.10.12.9)

Beim ersten Bild über Funk kamen die letzten Bytes nicht an: der Upload meldete „damaged on the way", und der Rest des Bildes stand als Zeichenmüll im Chat (und ging als Chat-Beitrag an alle).

**Ursache:** Der Client gibt die Bildbytes absichtlich in Häppchen mit Pausen an Direwolf. In diesen Pausen konnte jede andere Zeile dazwischenrutschen – getippter Text, eine Reaktion, vor allem das automatische `//RESEND`/`//LOST` der Lückenerkennung. Die TinyBox nimmt nach `//IMGPUT` aber **alles** als Bilddaten, zählte die Zeile mit, war zu früh „fertig" – und las die letzten echten Bildbytes als Chat-Zeile. Der Hash stimmte folglich nicht.

**Behoben in drei Schritten:**
- **Client:** Sendesperre von `//IMGPUT` bis zum letzten Byte (`ClientCore.hold_lines`). Zurückgehaltene Zeilen gehen danach in der getippten Reihenfolge hinaus; bricht die Verbindung ab, werden sie verworfen. Ein laufender Mailbox-Abgleich blockiert den Upload weiterhin (und umgekehrt), nach 10 Minuten Wartezeit mit Fehlermeldung statt Senden.
- **TinyBox:** Zeitlimit für den Rohmodus (`chatimg.RAW_TIMEOUT`, 120 s ohne Byte, geprüft im Idle-Watchdog des AGW-Adapters). Die Sitzung liest wieder Zeilen, meldet `//ERR img timeout <bytes>`, und das bereits Empfangene bleibt erhalten – das nächste `//IMGPUT` setzt dort fort.
- **TinyBox:** Chat-Zeilen mit Steuerzeichen (C0 außer Tab/Ctrl-Z, oder über 20 % C1-Zeichen) werden verworfen und nur geloggt. So geht im Fehlerfall nie wieder Binärmüll über Funk an alle Teilnehmer.
- **Client:** Nach einem fehlgeschlagenen Upload gibt es „Try again" (das verkleinerte Bild liegt noch im Client) neben „Discard".

## CR13 – History nur auf Wunsch (erledigt 11.10.2026)

- **Aufbewahrung** wie bisher pro Board in `tinybox.conf` `[chat_boards]` (Beispiel: TREFF 7d, DX 24h, TECH 30d, RUNDE live). `history_lines` (Standard 20) ist jetzt die **Höchstzahl pro Abruf**.
- **Vorher:** Beim Betreten kamen ungefragt die letzten 20 Zeilen (~800 Byte, 6–10 s Kanal bei 1200 Bd), auch wenn man sie schon kannte.
- **Terminal:** Beim Betreten nur noch
  `*** 37 lines stored. Last from 2026-10-09 12:33 UTC` und `*** /H n to read`. `/H n` zeigt die letzten n Zeilen, `/H` allein bleibt die Hilfe.
- **Client:** `//IN … hist=<Anzahl> last=<Zeit> now=<Zeit der TinyBox>`; die History holt er mit `//HIST max=<n> [since=<Zeit>] [before=<Zeit>]`, Antwort `//H …` + `//HEND <n> <ältere>` – nur an ihn, per I-Frame.
  - Einstellung **„Chat history“**: *Only what I missed (max. 20)* (Standard), *None*, *Last 10*, *Last 20*. „Verpasst“ = seit dem letzten Verlassen des Boards; die Zeit wird mit der Uhr der TinyBox gerechnet (`now=`), falsch gehende PC-Uhren stören nicht.
  - **Leiste oben im Chat:** „📜 37 older posts · load 10 · load all“ (all = höchstens `history_lines` pro Klick, die Leiste zeigt den Rest).
  - Zeitgrenzen sind inklusiv, doppelte Zeilen verwirft der Client – keine Zeile geht verloren, die Reihenfolge stimmt auch bei Zeilen aus derselben Sekunde.
- **Ältere Clients** (vor 2026.10.11.3) bekommen die History wie bisher beim Betreten.
- Client-Version 2026.10.11.3. Tests in `tests/test_chat.py`, `tests/test_clientproto.py`, `tests/test_tbclient.py`; Praxistest mit 25 Zeilen (Client und Terminal).

## CR17 – „Cry out“ (erledigt 11.10.2026)

- Ein Beitrag mit höchstens **32 Zeichen** wird in **sehr großer Schrift** (Großbuchstaben, Comic-Stil) in einer gelb-roten **„Bang!“-Blase** angezeigt, leicht schräg.
- **Über Funk:** nur zwei Zeichen `~!` vor dem Text, z. B. `~!PILEUP!` (9 Byte). `~!` ist frei, weil eine echte Tilde als `~~` gesendet wird. Terminal-Teilnehmer sehen `~!PILEUP!`.
- **Eingabe:** Knopf 💥 neben dem Emoji-Knopf schaltet den Cry-out-Modus ein (Feld auf 32 Zeichen begrenzt, Zähler im Hinweis), nach dem Senden wieder aus.
- **Schriftgröße** passt sich an: kurze Texte 36 px, längere 28 bzw. 23 px; Wörter werden nicht mitten drin getrennt.
- Status: von Gerhard freigegeben und eingebaut; getestet mit TinyBox + zwei Clients (PC- und Handy-Ansicht).

## CR18 – Versionskontrolle (erledigt 11.10.2026)

Entscheidungen: Version automatisch aus dem Repo, Feature-Beschreibung als festes Bulletin, Versionsnummer = Datum.

- **Version = Datum:** `tbclient/__init__.py` `VERSION = "2026.10.11"`. **Regel: bei jeder Änderung am Client erhöhen** (gleicher Tag noch einmal: `2026.10.11.2`).
- **Handshake:** Client sendet `//CLIENT TB1 v=2026.10.11 caps=…`. Die TinyBox liest die aktuelle Version selbst aus `tbclient/__init__.py` (gleiches Repo: nach `git pull` sofort aktuell, auch ohne Neustart). Ist der Client älter (oder ohne `v=`), antwortet sie `//OK TB1 caps=… cur=2026.10.11 news=<Nr.>`.
- **News-Bulletins (inkrementell, ab 11.10.2026 abends):** Pro Client-Version eine kurze Datei `tbclient/news/<Version>.txt` (ASCII, ohne Emojis, nur Stichworte – geht über Funk). Die TinyBox legt jede beim Start als eigenes Bulletin „Client <Version>“ an die Rubrik **TBNEWS**; die Clients holen nur die neuen. Es bleiben die letzten 10 Versionen, ältere Dateien kann man löschen. Ändert sich ein Text, bekommt das Bulletin eine neue Nummer. `tbclient/FEATURES.txt` ist nur noch die Übersicht im Repo und wird nicht gesendet (das frühere große Feature-Bulletin wird beim Start gelöscht). **Bei jeder neuen Client-Version eine News-Datei anlegen.**
- **Hinweis im Client:** gelbes Banner „New client version … available (you have …). Get it with git pull and restart the client.“ mit Knopf **„Read about new features“**: abonniert TBNEWS, gleicht die Bulletins ab und öffnet das Feature-Bulletin. Wegklicken gilt bis zur nächsten Version; der Hinweis bleibt auch nach Trennen/Neustart des Clients.
- **Seite veraltet:** Wurde der Client aktualisiert, die Seite im Browser ist aber noch alt, zeigt sie „The client was updated … – reload the page“ mit Knopf „Reload page“.
- **Unbekannte Emoji-Codes** (von einem neueren Client) erscheinen als `[?]` statt als Rohcode.
- Tests: `tests/test_clientnews.py`; Praxistest mit TinyBox, aktuellem und altem Client (PC und Handy).

## CR19 – Rubriken sind Sysop-Sache (erledigt 11.10.2026)

### Umsetzung (11.10.2026)

- **Ohne `[rubrics]`** (kein Eintrag) bleibt alles wie bisher: jede Rubrik ist frei. Nur **TBNEWS** ist immer gesperrt.
- **User** (Terminal, Client): Bulletins nur an ALL und angenommene Rubriken. Terminal: `SB FUCHS` → `Rubric FUCHS is not open for bulletins here. Rubrics: ALL WX …` (vor der Texteingabe). Client: `//ERR send bad_rubric FUCHS`.
- **Skripte (Eingangsordner) und MQTT:** nur Rubriken aus der Liste, sonst landet die Datei mit `.err` („Rubrik nicht in [rubrics] der tinybox.conf“) zurück. **Sysop** (Konsole, Sysop-Web) ist frei.
- **Forwarding** (`tinybox/fwd/receive.py`):
  - angenommen → `+`; abgelehnt oder TBNEWS → `-`.
  - **unbekannt, erstes Angebot** → `+`. **Abweichung vom Vorschlag:** das Bulletin wird nicht verworfen, sondern **gehalten (H) gespeichert** (User sehen es nicht, brocast auch nicht), dazu geht die **Mail an den Sysop** („New rubric FUCHS offered by OE3GAS“, mit Kopf, Text und Anleitung). So ist das erste Bulletin nach dem Annehmen auch in der Rubrik.
  - **unbekannt, Sysop hat noch nicht entschieden** → FBB/B1: `=` (später), Partner bietet es wieder an. **ASCII (W0RLI)** kennt kein „später“ → angenommen und gehalten, ohne weitere Mail.
  - Woran „noch nicht entschieden“ erkannt wird: es gibt ein gehaltenes Bulletin dieser Rubrik mit dem Vermerk „new rubric …“. Löscht der Sysop es ohne Entscheidung, beginnt es beim nächsten Angebot von vorn (neue Mail).
- **Nach dem Eintrag in `[rubrics]` und RESTART:** angenommen → gehaltene Bulletins werden freigegeben (wie `REL`), abgelehnt → gelöscht; zurückgestellte kommen beim nächsten Forward-Lauf bzw. werden abgelehnt.
- **Client** (Version 2026.10.11.5): `//RUBRICS` liefert zusätzlich die angenommenen Rubriken ohne Bulletins (`//RU WX 0 0`), die Beschreibungen (`//RU WX : Weather and warnings`) und die Liste zum Schreiben (`//RU + ALL WX CONTEST`, Reihenfolge wie in `[rubrics]`). Alte Clients überlesen diese Zeilen. Composer: beim Typ *Bulletin* Auswahlliste „WX – Weather and warnings“, daneben das Feld für das Verteilgebiet (`@WW`, optional). Ohne Liste (alte TinyBox, noch kein Bulletin-Abgleich) bleibt das freie Feld. Die Rubrikenliste zum Abonnieren zeigt die Beschreibungen.
- Tests: `tests/test_rubrics.py` (Regeln, Terminal, `//RUBRICS`, Forwarding inkl. fwdsim-Lauf FBB).
- **Hinweis zur eigenen `tinybox.conf`:** `BROCAST` hat 7 Zeichen und wird ignoriert (Warnung im Log) – Rubriknamen höchstens 6 Zeichen, z. B. `BROCST`.

### Ursprüngliche Erfassung

**Heute:** Es gibt keine Rubrikenliste. Eine Rubrik entsteht mit dem ersten Bulletin an sie (Empfängerfeld, 1–6 Zeichen) – von Usern, per Forwarding, Skript oder Sysop – und verschwindet mit dem letzten. Tippfehler erzeugen eigene Rubriken, Beschreibungen gibt es nicht.

**Gewünscht (Gerhard):**
- Rubriken legt **nur der Sysop** fest.
- **Forwarding:** Bulletins von Partner-Mailboxen kommen **nur in den freigegebenen Rubriken** in die Box, alles andere nicht automatisch.
- **User** schreiben Bulletins **nur an ALL und die freigegebenen Rubriken**.
- **Bulletin-Composer im Client:** Auswahl der Rubrik (statt freiem Feld).

**Entscheidungen (11.10.2026):**
- Skripte (Eingangsordner, z. B. GeoSphere) und MQTT schreiben nur an Rubriken aus der Liste; der Sysop ist frei.
- **Neue Rubriken aus dem Forwarding** werden nicht angelegt, sondern kommen als **Mail an den Sysop**; er entscheidet und trägt sie in `tinybox.conf` ein – als angenommen oder als abgelehnt.
- Die Liste gilt vorerst **nur für den Rubriknamen**, nicht für das Verteilgebiet (`@WW`, `@OE` …) – Forwarding über Funk gibt es in OE/DL derzeit kaum.

**Syntax in `tinybox.conf` (Vorschlag):**

```
[rubrics]
# Bulletin rubrics, set by the sysop. One line per rubric:
#   NAME = description      accepted: users may write, forwarding is taken
#   NAME = - [note]         refused: forwarding is declined, no sysop mail
# NAME: 1-6 letters/digits. ALL is always accepted. Order = order in the client.
ALL    = To everybody
WX     = Weather and warnings
AMSAT  = Amateur radio satellites
KEPLER = Satellite orbit data
CONTEST= Contests, results
FLOHMA = Buy, sell, swap
HUMOR  = -  not wanted here
```

**Ablauf beim Forwarding:**
- Rubrik **angenommen** → Bulletin wird angenommen (FBB „+“) und gespeichert.
- Rubrik **abgelehnt** → Vorschlag wird abgelehnt (FBB „-“), der Partner bietet ihn nicht mehr an.
- Rubrik **unbekannt** → das **erste** Bulletin wird angenommen, aber **nicht als Bulletin** gespeichert, sondern als **persönliche Mail an den Sysop**: „Neue Rubrik XYZ, angeboten von PARTNER“ mit Betreff und Text des Bulletins und dem Hinweis, wie man sie in `[rubrics]` annimmt oder ablehnt. Weitere Bulletins derselben Rubrik werden zurückgestellt (FBB „=“ = später), bis der Sysop entschieden hat – so geht nichts verloren und es kommt nur eine Mail pro Rubrik.
- Nach dem Eintrag in `tinybox.conf` (und Neustart) gilt die Entscheidung; zurückgestellte Bulletins kommen beim nächsten Forward-Lauf herein bzw. werden abgelehnt.

**Weitere Umsetzung:**
- **Terminal:** Bulletin an eine nicht angenommene Rubrik → Fehlermeldung mit der Liste der erlaubten Rubriken.
- **Client:** `//RUBRICS` liefert auch die angenommenen Rubriken ohne Bulletins und ihre Beschreibung (z. B. `//RU WX 0 0 Weather and warnings`). Der Composer zeigt beim Typ *Bulletin* eine Auswahlliste („ALL – To everybody“, „WX – Weather …“); die Rubrikenliste zum Abonnieren zeigt die Beschreibungen.
- **Bestehende Bulletins** in nicht angenommenen Rubriken bleiben bis zum Ablauf.
- **TBNEWS** („TinyBox News“, Feature-Bulletin aus CR18) ist eine System-Rubrik: immer vorhanden, muss nicht in `[rubrics]` stehen, User können dort nicht schreiben, Forwarding nimmt sie nicht an.

**Übliche PR-Rubriken (Recherche 11.10.2026)** – neben ALL und DX. Englische Bezeichnungen aus US-/internationalen Boxen (FBB, BPQ) sind belegt; die deutschsprachigen Namen stammen aus der Praxis der DL/OE-Boxen (OpenBCM/FBB) und sind nicht online belegt, bitte gegen die Rubriken der Partnerboxen prüfen:

| Rubrik | Inhalt | Herkunft |
|---|---|---|
| AMSAT | Amateurfunk-Satelliten, AMSAT-Nachrichten | international (belegt) |
| KEPS / KEPLER | Bahndaten (Keplerelemente) der Satelliten | international / DL |
| PACKET | Packet Radio, Netz, Software | international (belegt) |
| SWOP / SALE / FLOHMA | Verkauf, Tausch, Suche („Flohmarkt“) | US (belegt) / DL |
| QST | Nachrichten an alle Funkamateure, Verbände (ARRL) | US (belegt) |
| ARES / NOTFUNK | Notfunk | US (belegt) / OE |
| WX / WETTER | Wetter und Wetterwarnungen | international / DL |
| PROPAG | Ausbreitung, Sonnenaktivität | international |
| CONTEST | Contest-Ankündigungen und -Ergebnisse | international |
| DXNEWS | DX-Meldungen, DXpeditionen (oft neben DX) | DL |
| APRS | APRS | international |
| ATV | Amateurfunk-Fernsehen | DL |
| TECHNIK / ANTENNE | Technik, Selbstbau, Antennen | DL |
| LINUX | Linux im Amateurfunk | DL |
| HUMOR | Witze, Funkerhumor | DL |
| QSL | QSL-Karten, -Büro | DL |
| RUNDSP | Rundsprüche (DARC/ÖVSV) | DL/OE |
| (Verband/Region) | z. B. Landesverband, Ortsstelle | OE |

Quellen: [Introduction to Packet Radio (ZL1RAH)](https://www.qsl.net/zl1rah/about_packet.htm) (ALL, QST, ARES, USERS, SWOP, AMSAT, PACKET, Verteilgebiete), [Packet Radio FAQ](https://papperlan.duckdns.org/textfiles.com/internet/FAQ/faq-pktr.txt) (ARRL-, AMSAT- und Ausbreitungs-Bulletins), [FBB (Wikipedia)](https://en.wikipedia.org/wiki/FBB_(software)).

## CR20 – Verbindungsqualität (erledigt 11.10.2026)

Konzept und Entscheidungen: PLANUNG.md Abschnitt 14. Commits 6b379e8 (Abfrage, Balken, `STAT`) und 1f3312c (Client, Empfangsquote, Abbruch).

- Eigener Direwolf-Fork `oe3gas/direwolf-tinybox` (Zweig `tinybox`) zählt pro Verbindung Wiederholungen, REJ, T1-Abläufe usw.; TinyBox fragt sie alle 30 s über die neue AGW-Abfrage `Q` ab.
- Bewertung: letzte 50 Frames pro Richtung, höchstens 30 Minuten; die schlechtere Richtung gibt die Balken, jeder T1-Ablauf kostet einen Balken; unter 20 Frames grau.
- Für Clients im UI-Modus zählt zusätzlich die Empfangsquote der TBCHAT-Frames (aus `//RESEND` und neuem `//LOST`) – damit gibt es Balken auch ohne Fork-Direwolf.
- Client: Balken rechts in der Teilnehmerliste (grün 4–5, gelb 3, rot 1–2, grau = noch keine Daten), über das Chat-Ereignis `%`; bei Abbruch die Zeile „Connection to … lost“.
- Terminal: `STAT` (eigene Verbindung) und `STAT ALL` (alle) als Text.
- Client-Version 2026.10.11.4.

## CR21 – Bulletins verschieben und kopieren (Vorschlag 11.10.2026, noch nicht umgesetzt)

**Heute:** Der Sysop kann mit `E <Nr> TO <Rubrik>` (Terminal) bzw. „edit“ in der Sysop-Weboberfläche den Empfänger eines Bulletins ändern – das ist ein Verschieben, aber: die Nummer bleibt gleich, deshalb merken die Clients nichts davon (ihr Abgleich holt nur Nummern, die größer sind als die höchste bekannte der Rubrik). Kopieren gibt es nicht.

**Vorschlag:**
- **Wer:** nur der Sysop (Rubriken sind Sysop-Sache, CR19). Ziel muss eine angenommene Rubrik aus `[rubrics]` sein.
- **Terminal (Sysop):**
  - `MOVE <Nr>[,<Nr>…] <Rubrik>` – verschiebt, z. B. `MOVE 12,15 WX`
  - `COPY <Nr>[,<Nr>…] <Rubrik>` – legt eine Kopie in der Ziel-Rubrik an
- **Sysop-Weboberfläche der TinyBox:** in der Nachrichtenliste Mehrfachauswahl + Knöpfe „Move to…“ / „Copy to…“ mit Auswahlliste der Rubriken.
- **Client:** dieselben Knöpfe im Bulletin-Leser, aber nur, wenn die TinyBox der Sitzung Sysop-Rechte gibt (lokal, `sysop_via_radio = no` bleibt).
- **Verschieben:** Das Bulletin behält Text, Absender, Datum und BID und bekommt die neue Rubrik. Damit die Clients es mitbekommen, führt die TinyBox ein kleines Verschiebe-Protokoll (alte Nr. → neue Rubrik, Zeit). Beim nächsten Bulletin-Abgleich bekommt der Client eine Zeile `//MV <Nr> <Rubrik>` und hängt sein lokales Exemplar um – **der Text wird nicht noch einmal übertragen** (kanalschonend). Clients, die die neue Rubrik nicht abonniert haben, entfernen es.
- **Kopieren:** neues Bulletin mit neuer Nummer und eigener BID in der Ziel-Rubrik, Text/Absender/Datum wie das Original, Vermerk „copied from <Rubrik> #<Nr>“ in der ersten Zeile. Wer die Ziel-Rubrik abonniert hat, bekommt es beim nächsten Abgleich wie ein neues Bulletin.
- **Forwarding:** Verschieben und Kopieren wirken **nur lokal**; nichts wird erneut an Partner-Mailboxen geschickt (die Kopie bekommt keinen Forward-Status).
- **Protokoll:** jede Aktion im Log („sysop moved #12 ALL -> WX“).

**Entscheidungen (11.10.2026):**
1. Nur der Sysop, nicht der Autor.
2. Wo: **nur in der Sysop-Konsole (Terminal am TinyBox-PC) und in der Sysop-Weboberfläche** – **keine Sysop-Rechte über Funk und keine im Client** (Entscheidung Gerhard, 11.10.2026).
3. Eine Kopie übernimmt die Ablaufzeit des Originals.

**Sysop-Rechte im Client – verworfen (11.10.2026):** Es gibt keine Sysop-Rechte über Funk und keine im Client. Der folgende Vorschlag bleibt nur zur Dokumentation stehen:
- **Lokal (Client auf dem TinyBox-PC, `link = telnet`):** schon heute bekommt eine Telnet-Sitzung mit dem Sysop-Rufzeichen Sysop-Rechte (der Testport hört nur auf 127.0.0.1). Die TinyBox meldet das im Handshake (`//OK … sysop=1`), der Client zeigt dann die Sysop-Knöpfe.
- **Über Funk:** Rufzeichen sind nicht authentisch (`sysop_via_radio = no`). Neu: Anmeldung mit **Challenge-Response** wie Winlink „Secure Login“: Die TinyBox schickt eine Zufallszahl, der Client antwortet mit einem daraus und einem geheimen Sysop-Passwort berechneten Code (HMAC). Das Passwort geht nie über Funk, ein mitgehörter Code nützt beim nächsten Mal nichts. Der Inhalt bleibt Klartext – es wird nur angemeldet, nichts verschlüsselt.
  - `tinybox.conf`: `sysop_via_radio = auth`, `sysop_secret = …`; `tbclient.conf` bzw. Client-Einstellung: dasselbe Passwort, nur lokal gespeichert.
  - Befehle: `//SYSOP` → `//CHAL <zufall>` → `//SYSOP <code>` → `//OK sysop=1` bzw. `//ERR sysop`.
- **Sysop-Weboberfläche der TinyBox** (Port 8080, mit Login-Link) bleibt der Weg für die Verwaltung am TinyBox-PC.

## CR22 – RESTART in der Sysop-Konsole (erledigt 11.10.2026)

- `RESTART [s]` startet die TinyBox neu, z. B. nach einer Änderung in `tinybox.conf` oder nach einem `git pull`. Ablauf wie `SHUTDOWN`: verbundene Stationen werden gewarnt („OE3GAS-1 restarts in 60 seconds and is back shortly …“, Erinnerung bei 30 und 10 s), Standard 60 s, `RESTART NOW` sofort, `RESTART CANCEL` sagt ab. Ist niemand verbunden, sofort.
- **Vorher wird `tinybox.conf` geprüft.** Hat sie einen Fehler, startet die TinyBox **nicht** neu und zeigt den Fehler – sie läuft mit der alten Konfiguration weiter.
- **Neustart im selben Fenster:** `tinybox.bat` und `tinybox_dauerbetrieb.bat` starten die TinyBox sofort wieder (Exit-Code 3); ohne Batch-Datei (Linux, systemd) ersetzt sich der Prozess selbst. Neue Konfiguration und neuer Code werden dabei geladen.
- Tests in `tests/test_shutdown.py`; README und PRODUCTION ergänzt.
- Hinweis: Die neuen Batch-Dateien wirken erst, wenn TinyBox einmal mit ihnen gestartet wurde.

## CR23 – BUG Emoji-Picker: Schnellauswahl-Leiste verdeckt die Gesamtauswahl (gemeldet und ✅ 11.10.2026)

**Fehler:** Wenn man die Emoji-Gesamtauswahl öffnet (über den ➕-Button in der Reaktions-/Schnellauswahl-Leiste mit 👍 ❤️ 😂 😮 😞 📻 ➕), bleibt diese Leiste als schwebendes Overlay über dem großen Emoji-Panel stehen und verdeckt Einträge (z. B. die Zeile „RADIO & TECH“).

**Erwartet:** Sobald die Gesamtauswahl geöffnet wird, wird die Schnellauswahl-Leiste ausgeblendet/geschlossen.

**Fix (b5714a8):** In `openReactBar()` schließt der ➕-Button zuerst die Leiste und öffnet dann die Gesamtauswahl für die gemerkte Nachricht. Wird eine andere Nachricht angetippt, während die Gesamtauswahl im Reaktionsmodus offen ist, schließt sie sich.

**Test auf PC1 (11.10.2026), PC- und mobile Ansicht:**
- a) Nachricht antippen → Leiste erscheint: ok
- b) ➕ → Leiste weg, Gesamtauswahl frei („RADIO & TECH“ sichtbar): ok
- c) Emoji aus der Gesamtauswahl → Reaktion an der angetippten Nachricht, Gesamtauswahl zu: ok
- d) ➕ bei Nachricht A offen, dann B antippen: **Fehler** – die Gesamtauswahl schließt sich, die Leiste für B erscheint aber nicht (erst beim zweiten Antippen). Die Reaktion landet dann richtig bei B.
- e) Emoji-Button im Eingabefeld fügt Emojis weiter in den Text ein: ok

**Ursache von d:** Schließt sich die Gesamtauswahl, wird `#chat` höher und der Browser verschiebt die Scroll-Position von selbst. Das `scroll`-Ereignis von `#chat` ruft `closeReactBar()` auf und schließt die gerade geöffnete Leiste sofort wieder.

**Nachbesserung (08a5993):** `openReactBar()` merkt sich beim Schließen der Gesamtauswahl einen Zeitpunkt (`ignoreChatScrollUntil`, 150 ms). Scroll-Ereignisse von `#chat` innerhalb dieser Zeit schließen die Leiste nicht. Echtes Scrollen durch den User schließt sie weiterhin.

**Nachtest auf PC1 (11.10.2026, 22:02):** d in PC- und mobiler Ansicht ok – die Leiste für die zweite Nachricht bleibt stehen, die Reaktion landet dort. Echtes Scrollen schließt die Leiste weiterhin.

## CR24 – BUG Schnellauswahl-Leiste ragt in der PC-Ansicht rechts aus der Chat-Spalte (gemeldet und ✅ 11.10.2026)

**Fehler:** In der PC-Ansicht (3 Spalten) ragt die Schnellauswahl-Leiste bei eigenen (rechtsbündigen) Nachrichten über den rechten Rand der Chat-Spalte hinaus in die rechte Spalte („IN THIS BOARD“).

**Ursache:** `openReactBar()` begrenzt die Position auf `window.innerWidth`, nicht auf die Breite der Chat-Spalte.

**Erwartet:** Die Leiste bleibt innerhalb der Chat-Spalte.

**Fix (4c080ac):** `openReactBar()` begrenzt die Position der Leiste jetzt auf die Chat-Spalte (`#chat`), links und rechts mit 8 px Abstand. Ist die Leiste breiter als die Spalte, beginnt sie am linken Rand der Spalte.

**Test auf PC1 (11.10.2026):** PC-Ansicht ok – die Leiste endet innerhalb der Chat-Spalte (8 px vor dem Rand). Mobile Ansicht unverändert.

## CR25 – Board antippen: Bestätigung (✅ 11.10.2026)

- Das angetippte Board (Chip oben bzw. Eintrag in der linken Spalte) wird **orange und pulsiert leicht**, bis die TinyBox meldet, dass man im Board ist; dann wird es wie gewohnt blau (aktiv).
- Kommt keine Bestätigung (z. B. Verbindung weg), endet die Markierung nach spätestens 2 Minuten. Bei „Bewegung reduzieren“ im System pulsiert nichts.
- Client-Version 2026.10.11.6. Nur Oberfläche (`app.js`, `app.css`).

## CR3 – MOTD pro Board (✅ 11.10.2026)

- Der **Sysop** setzt sie in `tinybox.conf`, eigener Abschnitt `[chat_motd]`, eine Zeile pro Board, höchstens 120 Zeichen (kein `#` oder `;` im Text – die beginnen einen Kommentar). Ändern: Datei bearbeiten, `RESTART`.
  ```
  [chat_motd]
  TREFF = Willkommen! Runde jeden Sonntag 19:00 auf dieser QRG.
  ```
- **Terminal:** beim Betreten eine Zeile `*** <Text>` unter der Board-Überschrift.
- **Client:** über Funk geht beim Betreten nur eine Prüfsumme (`//IN … motd=ab12`, 10 Byte). Den Text holt der Client nur, wenn er neu ist (`//MOTD` → `//MOTD ab12 <Text>`) und merkt ihn sich. Anzeige oben im Chat als gelbe Notiz mit 📌.
- Client-Version 2026.10.11.7. Tests in `tests/test_motd.py`.

## CR14 – Zitieren (✅ 11.10.2026, Variante B)

- **Bedienung:** Beitrag antippen → in der Leiste ganz links **↩** → über dem Eingabefeld steht „You are adding a comment on **OE3TEC:** Wer ist heute…“ (✕ = kein Kommentar), das Eingabefeld zeigt „Your comment on OE3TEC's message“ → Text schreiben, senden.
- **Nur im laufenden Chat** (Fix 12.10.2026): Kommentieren und Reagieren geht nur bei Beiträgen, die eingetroffen sind, während man im Board ist. Beiträge aus der History (gestrichelter Rand) sind nur lesbar – kein ↩, keine Reaktionen, kein nachträgliches Kommentieren.
- **Über Funk nur ein Verweis** vor dem Text: `~^OE3TEC 1402 Ich bin QRV` – Rufzeichen und Minute (UTC, Uhr der TinyBox) des zitierten Beitrags, ca. 13 Byte.
- **Anzeige:** Der Client sucht den Beitrag im eigenen Chat (±1 Minute, bei mehreren der letzte) und zeigt über der Antwort einen Zitatblock „↩ OE3TEC 14:02“ mit Auszug; Antippen springt zum Original. Ohne Original (später gekommen, History nicht geladen) nur „↩ OE3TEC 14:02“.
- Wer zitiert wird, sieht die Antwort hervorgehoben wie bei @CALL (CR15).
- **Terminal-Teilnehmer** sehen `~^OE3TEC 1402 Ich bin QRV`.
- Kein Zitat im Cry-out-Modus. Client-Version 2026.10.11.8, nur Client (`app.js`, `app.css`, `index.html`); Fix History/Kommentarleiste: 2026.10.12.

## CR26 – Delta-Abgleich mit minimaler Payload (✅ 12.10.2026)

**Problem:** Der Mail-Sync holte immer alle Köpfe der eigenen Post von vorn (30 Mails ≈ 2,7 kB in 3 Wechseln, auch ohne Neues), der Bulletin-Sync jedes Mal die ganze Rubrikenliste. Eine neue kurze Mail = 4 Wechsel. Über Funk zählt jeder Wechsel (TXDelay, ACK, Pause) mehr als die Bytes.

**Lösung** (Konzept und Protokoll: PLANUNG.md 12.9):
- **TinyBox:** Änderungszähler `seq`/`cseq` je Nachricht und Tombstones gelöschter Nachrichten (SQLite-Trigger, Schema 7). Neue Befehle `//SYNC` (Löschen + Gelesen + Delta der Köpfe + kleine Texte in **einem** Wechsel) und `//BSYNC` (Rubrikenliste nur bei Änderung per Hash, neue/gelöschte Bulletins, kleine Texte). Cap `SYNC2`. Mit `Z` über Funk kommt die Antwort ab 200 Byte als ein LZHUF-Block (`//ZSYNC`). Alte Befehle bleiben für alte Clients.
- **Client:** nutzt `SYNC2`, wenn die TinyBox es anbietet, sonst alter Ablauf. Merkt sich `seq` je Abgleich; in der TinyBox gelöschte Post verschwindet jetzt auch hier (`//D`). Vollabgleich bei `//ERR seq` (TinyBox-DB neu).
- **Ergebnis:** „nichts Neues“ = 1 Wechsel, ~45 Byte statt ~2,7 kB; 1 neue Mail = 1 Wechsel statt 4.
- Client-Version 2026.10.12.3. Tests: `tests/test_mailsync.py` (`DeltaSyncTests`).

## CR27 – Persönliche Post an mehrere Empfänger (✅ 12.10.2026)

**Entscheidung:** nur Variante „mehrere Rufzeichen in einer Mail". Eine Verteilerliste (eine Nachricht, viele Leser, Lesestatus je Leser) gibt es nicht – dafür sind die Rubriken da (Bulletins).

**Verhalten:**
- Empfängerfeld mit Komma: `OE3TEC,OE1ABC[@ADRESSE]`. Terminal `SP OE3TEC,OE1ABC`, Client-Composer (Feld „To"), `//SEND P OE3TEC,OE1ABC <n> mid=…`. Eine `@`-Adresse gilt für alle; braucht ein Empfänger eine andere, zwei Mails schreiben. Höchstens 10 Empfänger, doppelte werden zusammengefasst, jeder wie bisher geprüft (`check_send`).
- Die TinyBox legt **je Empfänger eine eigene Nachricht** an: gleicher Text und Betreff, eigene Nummer, eigener Status, eigene MID (fürs Forwarding, jede Kopie geht ihren eigenen Weg). Ist einer der Empfänger ungültig, wird gar nichts gespeichert (`//ERR send …` bzw. Fehlertext am Terminal) – keine halben Sendungen.
- Über Funk geht der Text **einmal**: der Client schickt eine `//SEND`-Zeile mit der Empfängerliste; Antwort `//SENT <Nr.> <Nr.> …` (eine Zeile, alle Nummern). `mid=` bleibt eine Kennung für die ganze Sendung: kommt sie noch einmal, antwortet die TinyBox mit den vorhandenen Nummern (Zuordnung Kennung → Nummern über `msgid = tbc-<Kennung>-<Empfänger>`).
- Terminal-Antwort: `Message 12, 13 saved` (wie bisher, nur mit allen Nummern).
- Client: im Ordner „Sent" erscheint je Empfänger ein Eintrag (jede Kopie hat ihre Nummer, kann einzeln gelöscht werden); der Ausgang zeigt die Sendung bis zum `//SENT` als einen Eintrag. Der Delta-Abgleich braucht nichts Neues.
- Alte Clients: schicken nie ein Komma, nichts ändert sich.

**Umgesetzt 12.10.2026:** `MessageService.check_send_list()` (Liste prüfen, Doppelte falten, max. 10; Bulletins und `$BID` nur ein Ziel), Terminal `S OE3TEC,OE1ABC` → `Msg 12, 13 saved.`, `//SEND` → `//SENT 12 13` (msgid `tbc-<mid>-<Call>`, ein Empfänger wie bisher `tbc-<mid>`), Client legt je Nummer einen „Sent"-Eintrag an, Composer nimmt `OE3ABC,OE3XYZ[@…]`. Jede Kopie beginnt mit der Zeile `To: OE3TEC, OE1ABC`, damit jeder Leser sieht, wer sie noch bekommen hat (Ergänzung 12.10.2026 abends; auch im Sent-Ordner des Clients). Client-Version 2026.10.12.4, To-Zeile 2026.10.12.5. Tests: `test_mailsync.py` (`MultiRecipientTests`).


**Korrektur 15.10.2026:** Die Eingabeprüfung im Composer ließ nur ein Rufzeichen zu – Listen
wurden mit „Please enter a call“ abgelehnt, Leerzeichen einfach entfernt. Jetzt trennen
Leerzeichen, Komma oder Strichpunkt (bis 10 Empfänger, z. B. `OE3TEC OE3NDC`); der Client
schickt sie als `OE3TEC,OE3NDC`. Client 2026.10.15.7.
## CR28 – Emoticons und Emojis in beide Richtungen (✅ 12.10.2026)

**Beobachtet (Funktest 12.10.2026):** Vom Terminal kam `das funktioniert ;-)` – der Client zeigte `;-)` als Text, weil nur die nasenlosen Formen (`;)`) bekannt sind. Vom Client ging `sehr nett!~0B` – 🙂 aus dem Picker hat keine Emoticon-Form, also der Code; dazu klebte er am `!`. Am Terminal liest sich das als `~0B`.

**Heute:** Stufe 1 (PLANUNG 12.4) kennt neun Emoticons ohne Nase (`:)` `:(` `;)` `:D` `:P` `:O` `<3` `:+1` `:-1`), umgewandelt erst beim Senden bzw. beim Anzeigen, nur als eigenes Wort (Leerzeichen davor).

**Gewünscht:**
1. **Eingabe im Client:** Ein Emoticon wird **sofort beim Tippen** zum Emoji (sobald Leerzeichen, Satzzeichen oder Enter folgt), wie in Messengern. Die Tabelle kennt die Formen mit und ohne Nase: `:-)` `:)` `;-)` `;)` `:-D` `:D` `:-(` `:(` `:-P` `:P` `:-O` `:O` `:-/` `:-|` `<3` `:+1` `:-1` … Der Picker bleibt für den Rest.
2. **Senden:** Jedes Emoji, das eine Emoticon-Form hat, geht **als Emoticon** über Funk, nie als `~XY` – auch Varianten, die nur im Aussehen abweichen (🙂 😊 😀 → `:-)`, 😄 😃 😁 → `:-D`, 😉 → `;-)`, 🙁 😢 → `:-(`). Gesendet wird die Form **mit Nase** (`:-)`, wie am Terminal üblich; 1 Byte mehr, dafür für Terminal-User eindeutig). Fehlt vor dem Emoticon ein Leerzeichen (`nett!:-)`), fügt der Client es ein. `~XY` nur noch für Emojis ohne ASCII-Form.
3. **Anzeige im Client:** Emoticons aus jeder Quelle (Terminal, alter Client, History `//H`) werden zum **kanonischen Emoji** der Tabelle (`:-)` und `:)` → 🙂; `:-D` → 😄 …), auch direkt nach Satzzeichen (`Hallo!:-)`), nicht aber mitten im Wort (`QTH:Pinkafeld`, `http://`).
4. **Terminal:** nichts zu tun – die TinyBox reicht Text durch; wer `;-)` tippt, erscheint im Client als 😉. Reaktionen (`~XY` als Reaktionscode) bleiben, wie sie sind.

**Umgesetzt 12.10.2026 (nur Client):** `emoji.json` Version 3 – 16 Emoticons `{wire, aliases, emoji, also}`: `:-)` `;-)` `:-D` `:-(` `:'(` `:-P` `:-O` `:-/` `:-|` `:-*` `8-)` `>:-(` `xD` `<3` `:+1` `:-1`, jeweils mit nasenloser Form; 😊 😀 ☺️ gehen als `:-)`, 😃 😁 😆 als `:-D`, 😎 als `8-)`, 😢 als `:'(`, 😡 als `>:-(`, 😂 als `xD` (die alten Codes `~0A` `~0D` `~14` `~15` werden weiter verstanden). `app.js`: Live-Ersetzung beim Tippen (`liveEmoticon`, nach Leerzeichen oder Satzzeichen, Cursor bleibt), Erkennung auch nach Satzzeichen (`Hallo!:-)`), nicht im Wort (`QTH:Pinkafeld`, `http://`); Picker mit neuer erster Gruppe „Smileys (ASCII, cheapest)“, die anderen Gruppen ohne diese Doppelten. Client-Version 2026.10.12.4. Tests: `test_tbclient.py` (`EmoticonTests`, laufen mit node, sonst übersprungen).

## CR29 – Terminal: lange Ausgaben seitenweise (✅ 12.10.2026)

**Problem:** `L` listet alle Nachrichten; mit wachsender Box laufen irgendwann hunderte Titel ungefragt über Funk. Gleiches gilt für `LB`, `H`, `J` und lange Texte bei `R`.

**Lösung (nur TinyBox, `session.py`):** Jede Antwort auf einen Terminal-Befehl, die länger als 10 Zeilen ist, kommt in Seiten zu 10 Zeilen mit der Zeile `--More (10/37)-- Enter = continue, A = abort: `. Enter (oder jede andere Eingabe) holt die nächste Seite, `A` / `Q` / `/AB` verwirft den Rest (`*** rest skipped`). Gilt für alle Terminal-Befehle; nicht für Clients, den Chat, `DICT` und Befehle, die in einen anderen Zustand wechseln (`S`, `C`). Nach `B` kommt das „73, bye“ noch vor dem Trennen. `PAGE_LINES = 10` in `session.py`, Texte in `texts.py`. Tests: `test_tinybox.py` (`PagingTests`), `test_agw.py` angepasst. Als TBNEWS-Feature in Client-News 2026.10.12.8 (nur Textänderung, der Client selbst ist unverändert).

## CR30 – Bild-Upload sichtbar machen (✅ 12.10.2026)

**Problem:** Lädt jemand ein Bild hoch, ist der Kanal ein bis zwei Minuten belegt, ohne dass die anderen wissen warum.

**Entscheidung:** Ein einziges Ereignis beim Start, kein laufender Fortschritt über Funk.

- Die TinyBox sendet, sobald sie den Upload mit `//IMGGO` freigibt, das Chat-Ereignis `^<Call> <Größe>` (Größe wie in der Bildreferenz: 2 Hex in 64-Byte-Schritten), z. B. `#5A ^OE1ABC 50` – rund 14 Byte, einmal pro Bild. Nicht in der History gespeichert (wie das Qualitäts-Ereignis `%`).
- **Client:** Zeile im Chat „OE1ABC uploading picture · 2.1 / 5.0 KB“ mit Fortschrittsbalken. Der Fortschritt ist **echt gemessen**: der Client hört den Kanal ohnehin mit und zählt die Nutzbytes der I-Frames, die von dieser Station zur TinyBox gehen – null zusätzliche Payload. Wer die Station nicht direkt hört (Digi, zu schwach), zählt nichts; dort läuft der Balken über die geschätzte Dauer. Wiederholte Frames würden doppelt zählen, darum ist bei 100 % Schluss. Mit der eintreffenden Bildzeile verschwindet die Anzeige; bleibt sie aus (abgebrochener Upload), blendet der Client sie nach der doppelten geschätzten Dauer aus.
- **Terminal-Teilnehmer** lesen `*** OE1ABC is sending a picture (5.0 KB)` – auch dort weiß damit jeder, warum die Frequenz belegt ist.
- Der Uploader selbst sieht weiterhin nur seine eigene Bubble mit „sending …“.

## CR31 – Kommentarbezug eindeutig (✅ 12.10.2026)

**Problem (Funktest 12.10.2026):** Der Kommentar bezog sich über Rufzeichen + Minute (`~^OE3TEC 1402`) auf einen Beitrag. Hat dieselbe Station in derselben Minute mehrmals geschrieben, nahm der Client den letzten – inhaltlich falsch.

**Entscheidung:** Bezug über die **Folgenummer des Ereignisses**, die es ohnehin in jedem Frame gibt und die die Reaktionen schon so nutzen (`#52 OE3TEC *4F :+1`). Ein eigener Hash wäre größer und bräuchte neue Vergabe- und Abgleichlogik auf beiden Seiten.

- **Über Funk:** `~^4F Ich bin QRV` statt `~^OE3TEC 1402 Ich bin QRV` – **5 statt 14 Byte**, eindeutig über die letzten 256 Ereignisse des Boards (genau das Fenster, in dem Kommentieren erlaubt ist).
- **Client:** sendet nur noch das neue Format, liest beide (alte Zeilen stehen in der History). Kennt er den Bezug nicht (später eingecheckt), zeigt er „↩ message #4F“ – **kein Nachfordern über Funk**: echte Lücken holt die Lückenerkennung ohnehin selbst, und ein `//RESEND` für Ereignisse von vor dem Einchecken würde die Empfangsquote (14.3) verfälschen.
- **Terminal-Teilnehmer:** Die TinyBox löst den Verweis auf und schreibt `[re OE3TEC: "Servus, Wetter passt"] Ich bin QRV` – vorher stand dort der rohe Verweis. Enthält der zitierte Beitrag ein Bild, steht im Auszug kurz `[Image]` (sonst bliebe vom Auszug nichts übrig). Im Verlauf (`/H`), wo das Ereignisfenster nicht mehr gilt, steht `[re #4F]`.
- Kommentieren bleibt auf Beiträge beschränkt, die im laufenden Chat eintreffen (Entscheidung 12.10.2026) – History-Zeilen haben keine Folgenummer.

## CR32 – Logfile zum Debuggen mit Claude (✅ 13.10.2026)

**Umgesetzt 13.10.2026, alle Punkte 32.1 bis 32.11** – auch die beiden zunächst
als „nice to have“ zurückgestellten, Laufzeiten (32.8) und Übergabepaket (32.10).
Reines TinyBox-Thema, der Client bleibt unberührt: keine neue Client-Version,
keine News-Datei. Neu `tinybox/logsetup.py`; geändert `__main__.py`, `config.py`,
`session.py`, `app.py`, `texts.py`, `adapters/agw.py`, `adapters/telnet.py`,
`adapters/sysop.py`, `clientsync.py`, `fwd/session.py`, `fwd/send.py` und
`tinybox.conf.example`. Tests in `tests/test_logging.py` (44 Tests).

**Problem (vorher):** Beim Debuggen mit Claude war das Log nur eingeschränkt brauchbar.
Jeder Start legte eine neue Datei `Tinybox_log_<Datum>_<Zeit>.log` an – nach einigen
Neustarts lagen dort ein Dutzend Dateien und es musste erst geklärt werden, welche
gemeint ist. Die Zeilen trugen keine Session-Nummer, zwei gleichzeitige Verbindungen
derselben Station (Funk und Telnet) waren nicht auseinanderzuhalten. Es stand nicht
drin, welche Version und welche Adapter überhaupt laufen, und `level = DEBUG` ließ
sich nur global schalten, was die Datei mit Monitor-Verkehr zuschüttete.

**Ziel:** Eine Datei, aus der sich der Ablauf ohne Rückfragen rekonstruieren lässt –
auch von Claude, der den Rechner nicht sieht.

### 32.1 Eine Datei pro Tag (entschieden 13.10.2026)

**Nicht je Neustart** (so ist es heute) und keine feste Einzeldatei mit Rotation,
sondern **eine Datei pro Kalendertag**: `tinybox-2026-10-13.log` im `log_dir`.

- Grund gegen „je Neustart“: nach `git pull` + `RESTART` liegt die Ursache
  (Startblock, geänderte Konfiguration) in einer anderen Datei als die Wirkung,
  und im Dauerbetrieb entstehen an einem Abend mehrere Dateien.
- Grund für den Tag: Probleme werden zeitlich beschrieben („gestern Abend beim
  Funktest“). `tinybox-2026-10-12.log` ist damit direkt adressierbar, ohne Raten
  zwischen `.1`, `.2`, `.3`.
- **Neustarts bleiben sichtbar**, als Block innerhalb des Tages:

  ```
  2026-10-13 19:42:01.004 I core  #0 - ----- TinyBox 2026.10.12 (a1b2c3d) start -----
  ...
  2026-10-13 21:15:33.210 I core  #0 - ----- stop: RESTART, 1h33m, 7 sessions, 0 errors -----
  2026-10-13 21:15:41.882 I core  #0 - ----- TinyBox 2026.10.12 (f4e5d6c) start -----
  ```

  Damit ist sofort zu sehen, ob zwischen zwei Beobachtungen ein Neustart lag.

**Umsetzung:** nicht mit `TimedRotatingFileHandler` – der benennt die laufende
Datei beim Rollover um, und Windows kann eine offene Datei nicht umbenennen; im
Dauerbetrieb über Mitternacht gibt das Fehler, die man dann gerade im Log nicht
findet. Stattdessen ein kleiner eigener Handler:

- Dateiname aus dem Datum, immer im **Append**-Modus geöffnet. Kein Umbenennen,
  keine Sperrprobleme; mehrere Starts an einem Tag hängen hinten an.
- Vor dem Schreiben ein Datumsvergleich; hat der Tag gewechselt, wird geschlossen
  und die neue Datei geöffnet. Kostet einen Integer-Vergleich pro Zeile.
- `keep_days = 14` in `[logging]`: beim Start und beim Tageswechsel werden ältere
  Dateien gelöscht. Logs liegen ohnehin nie im Repo.
- Notbremse gegen Größe: über 20 MB an einem Tag (DEBUG auf `agw` bei viel
  Verkehr) geht es auf `tinybox-2026-10-13.2.log` weiter.
- Der Pfad steht im Startblock und im `LOG`-Befehl, damit er nicht gesucht
  werden muss.

### 32.1a Format

- **Feste Spalten**, eine Zeile = ein Ereignis:

  ```
  2026-10-13 19:42:08.233 I session  #7 OE3TEC  < LIST
  ```

  Zeit mit Millisekunden | Level als ein Buchstabe (`D I W E`) | Komponente
  (feste Breite) | Kontext (Session-Nummer + Rufzeichen) | Meldung.
  Millisekunden, weil über Funk fast jeder Fehler ein Zeitproblem ist (T1, Retries).
- **Dreizeilige Legende als Kopf der Datei**, damit die Leseregeln mitkommen,
  wenn die Datei in einen Chat gelegt wird.

### 32.2 Session-Nummer

Jede Verbindung bekommt eine laufende Nummer (`#7`), die in **jeder** Zeile dieser
Verbindung steht – auch in denen von `store`, `chat` und `sync`. `grep "#7"` liefert
dann die Verbindung von `connected` bis `disconnected`, auch wenn drei Stationen
gleichzeitig arbeiten. Zeilen ohne Verbindung tragen `#0 -`.

Technisch über `contextvars`: der Kontext wird beim Behandeln einer Zeile gesetzt,
und eine dabei gestartete Task erbt ihn – spätere Zeilen derselben Arbeit behalten
also die Nummer. Weil ein Neustart an dieselbe Tagesdatei anhängt, liest die
TinyBox beim Start die höchste Nummer aus der Datei und zählt darüber weiter:
`#7` bleibt damit **innerhalb der ganzen Tagesdatei** eine Verbindung, nicht nur
innerhalb eines Laufs.

### 32.3 Richtungszeichen in zwei Ebenen

- `<` Eingabe der Station, `>` Ausgabe der TinyBox (wie heute im Monitor).
- `<<` / `>>` für AGW-Frames mit Frametyp und Bytezahl.

So ist auf einen Blick zu sehen, ob eine Zeile auf Text- oder auf Frameebene fehlt –
genau die Unterscheidung, die bei Abbrüchen zählt.

### 32.4 Startblock und Schlusszeile

Erste Zeilen jedes Laufs, immer, auch auf `INFO`: TinyBox-Version und Git-Commit,
Python- und OS-Version, Pfad der `tinybox.conf`, Datenverzeichnis, Mailbox- und
Sysop-Rufzeichen, angebotene Client-Version, AGW-Host/Port und die Adapterliste
(`telnet=on web=on brocast=on inbox=on forward=off mqtt=off`). **Keine Token und
keine Login-URL**, nur `token=set` / `token=unset`.

Schlusszeile: Grund des Endes (normal, Ctrl+C, RESTART, Ausnahme), Laufzeit und
Zähler (Sessions, Frames rein/raus, Bulletins weitergeleitet, Fehler). Damit ist
ein Lauf als sauber oder unsauber erkennbar, ohne die Datei zu lesen.

### 32.5 Ausnahmen mit Kontext

Unerwartete Ausnahmen in allen Adapter-Tasks laufen über einen gemeinsamen Helfer
und kommen mit Traceback, Session-Kontext **und der auslösenden Eingabezeile** ins
Log. Die Eingabezeile ist der Teil, der einen Fehler reproduzierbar macht.

### 32.6 DEBUG je Komponente statt global

In `[logging]` zusätzlich `debug = agw,fwd`: nur diese Komponenten gehen auf
DEBUG, der Rest bleibt auf `level`. Ein unbekannter Name ist ein Konfigurationsfehler
und nennt die Liste. Komponenten: `agw`, `brocast`, `bus`, `chat`, `cmd`, `core`,
`fwd`, `inbox`, `linkq`, `news`, `notify`, `session`, `store`, `svc`, `sync`,
`sysop`, `telnet`, `web` – oder `all`.

Dazu `keep_days` (siehe 32.1). Beides gilt für Datei **und** Konsole, damit man
Eingeschaltetes auch live mitlesen kann.

### 32.7 Sysop-Befehl `LOG`

- `LOG` – zeigt Level, aktive Debug-Komponenten, Dateipfad und Dateigröße.
- `LOG DEBUG agw` / `LOG OFF agw` – schaltet im Betrieb, ohne Neustart.
- `LOG MARK <Text>` – schreibt `===== MARK: <Text> =====` in die Datei.
  Marke setzen, Fehler auslösen, danach „ab der Marke“ sagen: spart beim Debuggen
  die meiste Zeit.

### 32.8 Laufzeiten

Dauer in Millisekunden am Zeilenende in Klammern, dort wo sie etwas aussagt:
Session gesamt, Befehlsausführung, Sync-Lauf, Forward-Session, Schreibzugriff über
50 ms, AGW-Connect.

### 32.9 Datensparsam

Der **Text einer Mail** (Betreff und Rumpf, also die Zeilen im Sendemodus) steht
nur als Länge plus die ersten 40 Zeichen im Log: `< 12c 'Test subject'`. Vollständig
erst mit `LOG DEBUG session`. Die Datei wird in Chats gelegt – fremde persönliche
Post soll nicht mitfahren, und die Datei bleibt klein.

Befehle und Antworten bleiben unverkürzt, sonst wäre das Protokoll nicht mehr zu
lesen; Chat-Zeilen ebenso, die hören die Mitlauscher auf der Frequenz ohnehin.
Wer gar keinen Verkehr im Log will, setzt wie bisher `monitor = no`.

### 32.10 Übergabepaket

`LOG BUNDLE` (bzw. `python -m tinybox --debugbundle`) schreibt
`tinybox_debug_<Datum>.txt`: Startblock, die letzten n Zeilen des Logs, Version,
`tinybox.conf` ohne Token, Verzeichnisübersicht von `data`. Eine Datei, die
unverändert in den Chat gelegt werden kann.

### 32.11 Lesehilfe

Ein echter Auszug (Funktest 13.10.2026, zwei Telnet-Sitzungen):

```
2026-10-13 20:08:28.844 I core     #0 -         ----- TinyBox 0.1.0 (f3bee5c) start -----
2026-10-13 20:08:28.844 I core     #0 -         adapters: telnet=on web=on brocast=on inbox=on forward=off mqtt=off console=on
2026-10-13 20:08:28.844 I core     #0 -         brocast token unset, level INFO, debug agw, keep_days 14
2026-10-13 20:08:28.938 W agw      #0 -         Direwolf AGW 127.0.0.1:8000 not reachable (...), retrying every 5s
2026-10-13 20:08:29.937 I telnet   #1 OE3TEC    telnet connect from ('127.0.0.1', 48146)
2026-10-13 20:08:29.944 I session  #1 OE3TEC    < L
2026-10-13 20:08:29.945 I session  #1 OE3TEC    >  MSG# TS   SIZE TO        @BBS    FROM      DATE   UTC   SUBJECT
2026-10-13 20:08:29.946 I session  #1 OE3TEC    < S OE1ABC
2026-10-13 20:08:29.947 I session  #1 OE3TEC    < 12c 'Test subject'
2026-10-13 20:08:29.949 I session  #1 OE3TEC    session end via telnet after (11ms)
2026-10-13 20:08:30.537 I telnet   #2 OE1ABC    telnet connect from ('127.0.0.1', 42782)
2026-10-13 20:08:31.000 I core     #0 -         ===== MARK: Funktest CR32 =====
2026-10-13 20:08:31.648 I core     #0 -         ----- stop: SHUTDOWN, 2s, 2 sessions, 0/0 frames in/out, 0 fwd, 2 warnings, 0 errors -----
```

Leseregeln:

- `-----` trennt die Läufe; `start` und `stop` stehen direkt untereinander, man
  sieht also sofort, ob zwischen zwei Beobachtungen ein Neustart lag.
- ` E ` sind die Fehler, ` W ` die Warnungen – beides zuerst durchsehen. Die
  Schlusszeile sagt, ob es überhaupt welche gab.
- `#7` greppen gibt eine Verbindung vollständig, quer über alle Komponenten und
  über Neustarts hinweg eindeutig.
- `MARK:` zeigt, worauf gezeigt wurde.
- Ein `>` ohne folgendes `<` innerhalb von Sekunden: die Station ist weg.
- Zahl in Klammern: dort ist die Zeit geblieben.
- `12c '...'` ist gekürzter Mail-Text (32.9), kein abgeschnittener Befehl.

Dieselben drei Zeilen stehen als Kommentarkopf in jeder Logdatei, damit sie
mitkommen, wenn die Datei in einen Chat gelegt wird.

## CR33 – Teilnehmernummern und Verbindungsdetails im Client (✅ 13.10.2026)

**Anlass:** Die Sysop-Web-GUI zeigt seit 13.10. je User die Zahlen hinter den Balken (Richtungen, Verluste, Schwellenleiter, Zähler). Dasselbe soll der TBClient+ zeigen – ohne nennenswert mehr Funkverkehr.

**Payload-Abschätzung (13.10.2026, 5 Stationen, 1200 Bd):** volle Auskunft mit Rufzeichen und Klartext ≈ 230 Byte; mit Teilnehmernummern, kompaktem Klartext (Bytes in 100er-Schritten, SRT in 0,1 s) ≈ 165 Byte ≈ 1,5 s inkl. TXDelay; Binär brächte nur ≈ 0,3 s mehr, wäre aber im Monitor unlesbar und müsste am Binärfilter (CR12) vorbei. Entschieden: Nummern + kompakter Klartext, nur bei Änderung, höchstens alle 2 Minuten (< 1,5 % Kanal).

**Lösung** (Protokoll: PLANUNG.md 12.4 und 14.6):
- **Teilnehmernummern:** Jede Station bekommt beim Betreten eines Boards die kleinste freie Nummer 1…n; sie bleibt, solange die Station im Board ist, und wird danach wieder frei. Neue Cap `NUM` beim `//CLIENT`-Handshake. Für NUM-Clients: `//WHO 1 OE3GAS=/- 3 OE3TEC-1`, Ereignisse `+2 OE3TEC-1 /-`, `-2`, `=2 /k`, `%2 4 3 ?`. `//OK` nennt zusätzlich `q=50/30/20/5,10,20,35,50` (Fenster, Minuten, Mindest-Frames, Balkenschwellen).
- **Alte Clients ohne `NUM`:** bekommen weiterhin die Rufzeichenform – der UI-Frame trägt die Nummernform, alte UI-Clients erhalten die alte Zeile zusätzlich als I-Frame (gleiche Folgenummer, der Client dedupliziert). `//RESEND` liefert ihnen ebenfalls die alte Form.
- **Statusframe `%Q`:** `%Q <n> <Balken> <out Frames> <out Wdh> <in Frames> <REJ tx> <Wdh rx> <REJ rx> <T1> <Netto/100> <Wdh/100> <RX gesendet> <RX verpasst> <SRT·10>;…` – alle Teilnehmer mit Daten, Fensterwerte wie in der Sysop-GUI. **Ohne Folgenummer**, wird nie nachgefordert (der nächste bringt frischere Werte), zählt nicht für die Empfangsquote. Nur an NUM-Clients: einmal als UI-Frame, per I-Frame an Clients ohne UI.
- **Client:** Teilnehmer in der Liste antippen öffnet die Detailansicht: große Balken, drei Richtungskacheln (outgoing, incoming, rx quote) mit Frames, Verlusten und Formel, Schwellenleiter mit Rechnung inkl. T1-Abzug, Zähler (REJ rx, T1, Netto/Wdh, SRT), Alter der Daten. Rechnung im Client nach denselben Regeln wie `linkq.py`, Schwellen aus `q=`.
- Client-Version 2026.10.13.2. Tests: `test_clientproto.py` (`test_member_numbers`), `test_linkq.py` (`test_qstat_line_for_num_clients`, `ClientQualityTests`), `test_tbclient.py`.

## CR34 – Bildübertragung schneller (✅ 13.10.2026)

**Problem:** Ein Bild (8 kB) brauchte ≈ 3 Minuten. Der Client gab die Bytes in 256-Byte-Stücken mit 2 s Pause an Direwolf und wartete je Stück auf die Bestätigung; dazu 128-Byte-Frames fest im Client (`links.py`) und in der TinyBox (`paclen`). Das AX.25-Fenster war nie gefüllt, jede Sendung ein eigener Durchlauf (TXDelay, ACK, Pause): ≈ 45 B/s. Analyse und Rechnung: PLANUNG.md 12.10a.

**Lösung:**
- Frames 256 Byte (Client fest, TinyBox `paclen = 256`, `max_outstanding = 6`).
- Upload am Stück an Direwolf; die Chat-Zeile mit dem Verweis geht gleich hinter den Bytes raus (ein Wechsel weniger). Fortschrittsbalken aus AGW `Y`; Stillstand erst nach 120 s ohne Bewegung ein Fehler.
- `direwolf.conf` beide PCs: `PACLEN 256`, `MAXFRAME 4`, `EMAXFRAME 6` (sonst ginge mit v2.2 das ganze Bild als eine 60-s-Sendung raus).
- Dialog: Größenwahl **klein / normal / groß** (2 / 4 kB / Board-Limit, 192 / 256 / 320 px), Wahl bleibt im Browser; `[images] target_bytes` (4096) und `bytes_per_sec` (100) im Client, `piece_bytes`/`pause_sec` entfallen.
- Erwartung: ≈ 115 B/s, 4-kB-Bild in ≈ 35 s, 8 kB in ≈ 70 s. Nach den ersten Funkmessungen `bytes_per_sec` nachziehen.
- Client-Version 2026.10.13.4. Tests: `test_tbclient.py` (`ImageTests`, `ImageHoldTests`).

## CR35 – Bekanntes Bild nochmal senden (✅ 13.10.2026)

**Problem:** Ein Bild, das schon einmal übertragen wurde, ließ sich nicht erneut in den Chat stellen – der Upload „verschwand“ kommentarlos. Log 13.10., 22:50: `//IMGPUT 22cec8 8008` → sofort `//IMGOK 22cec8`, danach nichts mehr. Die TinyBox erkennt am Hash, dass sie das Bild hat, und verlangt die Bytes nicht nochmal (`//IMGOK` statt `//IMGGO`) – gewollt, spart Airtime. Der Client wertete das aber als „fertig“ und schickte die Chat-Zeile mit dem Verweis nie; die geht sonst erst hinter den Bytes raus (`_send_all`).

**Lösung:** Kommt `//IMGOK` ohne vorheriges `//IMGGO`, sendet der Client nur die Chat-Zeile (`~#<hash>…` + Bildtext). Das Bild erscheint wieder im Chat, die anderen Stationen holen es wie sonst von der TinyBox bzw. haben es schon. Upload-Status trägt `known=True`. TinyBox unverändert.

- Client-Version 2026.10.13.5. Test: `test_tbclient.py` (`ImageHoldTests.test_known_picture_sends_only_the_chat_line`).

## CR36 – Bildgröße im Chat und Größenwahl im Dialog (✅ 14.10.2026)

**Problem:** Ein „small“-Bild (gröbere Auflösung) wurde im Chat genauso groß angezeigt wie ein „large“-Bild – die Bubble streckte jedes Bild auf 240 px. Die Wahl im Dialog bestimmte nur die Bytes, auf dem Schirm war kein Unterschied. Außerdem standen die Zahlen (Pixel, Bytes, Dauer) nur als Hinweistext unter den drei Größenknöpfen.

**Lösung:**
- Größenstufen jetzt **108 / 192 / 320 px** lange Seite (vorher 192 / 256 / 320) bei unverändert 2 kB / 4 kB / Board-Limit.
- **Anzeige in eigener Pixelgröße:** die Bild-Box folgt dem Bild (`fit-content`, höchstens 320 px bzw. 70 % der Fensterbreite). Der unscharfe Platzhalter vor dem Laden bekommt seine Breite aus den Bytes (die Pixel gehen nicht über Funk): bis ≈ 3 kB → 108 px, bis ≈ 6 kB → 192 px, sonst 320 px.
- **Dialog:** „Select size“ mit drei Knöpfen untereinander, jeder trägt seine Zahlen, z. B. `small (108×81), ~2.0 KB, ~30 s` – Pixel aus dem Seitenverhältnis des gewählten Bildes, Dauer aus `bytes_per_sec`. Rechts daneben nur die Bildunterschrift; die früheren Erklärtexte (Ergebniszeile, Hinweis über „Send“) sind weg, die Zahlen stehen ja in den Knöpfen. Die Zeile rechts bleibt für „Shrinking…“ und Fehlermeldungen. Unter 700 px Breite rutscht die Unterschrift unter die Knöpfe.
- Client-Version 2026.10.14.2 (Kosmetik nachgezogen). Nur Web-GUI (`index.html`, `app.js`, `app.css`), kein Protokoll berührt.

## CR37 – Ansichten im brocast-Listener (✅ 14.10.2026)

**Problem:** Drei Ansichten für eine Seite waren zwei zu viel. „Mit Trennlinien“ brachte gegenüber dem
Fließtext nur eine gestrichelte Linie je Unterseite. Im Fließtext standen die Teile-Knöpfe (`1/8`, `2/8`, …),
obwohl dort ohnehin alle Teile untereinander stehen – sie sprangen nur zum Anfang eines Teils. Und die
Teletext-Ansicht hieß zwar so, sah aber aus wie der Fließtext mit weniger Inhalt.

**Lösung:**

1. **„Mit Trennlinien“ entfällt.** Es bleiben **Fließtext** und **Teletext**; ein im Browser gemerktes
   `parts` fällt auf Fließtext zurück. Die Umschaltung steht jetzt bei *jeder* Seite (vorher erst ab zwei
   Teilen), damit auch eine einteilige Seite als Teletext gelesen werden kann.
2. **Fließtext ohne Teile-Knöpfe.** Dort steht nur noch rechts die Umschaltung „Ansicht“. Die Knöpfe
   (mit ◀ ▶) gibt es im Teletext, wo sie wirklich blättern.
3. **Teletext-Optik.** Die Seite wird als schwarzer Bildschirm gezeichnet: eigene Pixelschrift, 40 Zeichen
   je Zeile, Zeilenabstand 1,65 (bewusst luftiger als das enge Original-Raster – das war am Bildschirm zu
   gedrängt). Kopfzeile wie beim Teletext: Rubrik links im roten Feld, Station und Seitennummer rechts,
   darunter der Titel in Gelb. Farben nach Bedeutung: Überschriften gelb, Hinweise/Tabellenköpfe cyan,
   Warnungen gelb, Alarme rot, fehlende Teile magenta.
   - Die Schrift (`brocast/brocast/web/teletext.woff`, 5,8 kB, 228 Zeichen) entsteht aus einem
     7 × 13-Pixel-Raster: `brocast/tools/build_teletext_font.py` rastert DejaVu Sans Mono **Bold** bei 10 px
     in reinem Schwarz-Weiß und macht aus jedem Pixel ein Quadrat im Umriss. Die fette Schnittlage liefert
     2 Pixel breite Striche – das ist der grobe Teletext-Eindruck. Bei `font-size: 32px` ist ein Schriftpixel
     genau zwei Bildschirmpixel (am Handy 24 px), daher die harten Kanten.
   - Ausgeliefert wird sie vom Listener selbst (`/teletext.woff`, CSP `default-src 'self'` – kein
     Internet, keine Google Fonts).
   - **Der Teletext-Bildschirm ist immer Text:** Wetterkacheln und das Wetterraster (CR-Vorgänger,
     PLANUNG 6g) erscheinen dort als Werteliste bzw. als einfache Tabelle, und der Knopf
     „Grafisch/Text“ wird in dieser Ansicht ausgeblendet. Er gilt für den Fließtext.

Vorschau ohne laufenden brocastd: `brocast/mockup/teletext-vorschau.html`.
Betrifft nur den Listener (`app.js`, `app.css`, `webserver.py`, `listener_api.py`) – kein Protokoll, keine
Änderung an dem, was über Funk geht.

## CR38 – Teletext-Kopf, Zeilenabstand und Bildkonverter (✅ 14.10.2026)

**1. Zeilenabstand auf Zeichenhöhe.** 1,65 war gut zwei Zeichenhöhen Luft zwischen den Zeilen – zu viel.
Jetzt 1,125 (18 von 16 Schriftpixeln): zwischen zwei Zeilen bleibt genau eine Zeichenhöhe. Die Zahl ist so
gewählt, dass der Zeilenabstand bei `font-size: 32px` volle 36 Bildschirmpixel sind; bei krummen Werten
säße jede zweite Grundlinie auf einem halben Pixel und die Schrift würde verwischen.

**2. brocast-Schriftzug über jeder Teletext-Seite.** Vorbild ist die ORF-Teletext-Titelseite (Vorlage von
OE3GAS): ein Feld aus lauter hellen Quadraten mit schwarzen Fugen, der Schriftzug steht als ausgesparte,
schwarze Fläche darin, darunter die rote Linie.

- Erzeugt von `brocast/tools/build_logo.py` nach `brocast/brocast/web/brocast-logo.svg` (5,7 kB):
  Raster 6 Einheiten je Zelle (davon 5 das helle Quadrat), Buchstaben aus Liberation Sans Bold
  (Arial-Nachbau wie auf der Vorlage), schwarz-weiß gerastert; die Schriftgröße wird automatisch so
  gewählt, dass der Schriftzug in die Feldbreite passt (91 × 20 Zellen).
- SVG mit `shape-rendering="crispEdges"`, Breite 100 % des Bildschirms – bei 40 Zeichen × 14 px sind
  das genau 560 px, also 1 SVG-Einheit = 1 Bildschirmpunkt.
- Ausgeliefert vom Listener selbst (`/brocast-logo.svg`, CSP `img-src 'self'`).

**3. Bildkonverter (neu).** `py -3 -m brocast bild <datei>` macht aus einem Bild eine Teletext-Bildseite –
ASCII-Art-Prinzip, nur sechsmal feiner.

- **Nur im station-Betrieb:** der Befehl liest `brocastd.conf` und bricht bei `mode = listener` ab.
- **Darstellung:** ein Zeichen trägt 2 × 3 Felder (Sextanten `U+1FB00…U+1FB3B` plus Leer-, Halb- und
  Vollblock, `brocast/mosaic.py`). Ein Bild ist damit ganz normaler Text in `pre`-Blöcken – **keine neue
  Blockart, kein neues Dictionary** (bleibt v2). Der Listener erkennt ein Bild daran, dass der Block nur
  aus Mosaikzeichen besteht, und zeichnet es mit Zeilenhöhe 0,75 em lückenlos; die Zeichen dafür sind in
  der Pixelschrift gezeichnet statt gerastert, damit die Felder exakt aneinanderstoßen.
- **Bytes:** je Zeichen vier Bytes UTF-8, davon sind aber drei bei allen gleich – mit dem
  Preset-Wörterbuch (PLANUNG 6e) bleiben rund 0,9 Byte je Zeichen. Gemessen: 40 × 16 Zeichen
  (80 × 48 Punkte) = 2 096 Byte roh → **514 Byte gepackt, 3–4 Frames**. Eine eigene 1-Byte-Kodierung
  käme auf 370 Byte – die 40 % mehr sind es wert, dafür bleibt die Seite reiner Text.
- **Aufruf:** ohne weitere Angabe nur Vorschau im Fenster samt Byte- und Frame-Zahl; `--senden` gibt die
  Seite an das laufende brocastd (Ingest-API, Lieferant `bild`, Schlüssel = Dateiname → neue Revision
  statt neuer Seite), `--tinybox ORDNER` legt sie als **Bulletin** in den TinyBox-Eingang (Kopfzeile
  `Brocast:` wie bei den GeoSphere-Skripten, Text in der Mailbox ist dasselbe Mosaik).
  Dazu `--spalten` (Breite in Zeichen, max. 40), `--invert`, `--hart` (harte Schwelle für Zeichnungen
  statt Fehlerstreuung), `--titel`, `--text`, `--rubrik`, `--gueltig`.
- **Pillow** wird nur für diesen Befehl gebraucht; fehlt es, sagt der Befehl das und bricht ab.

Tests: `brocast/tests/test_mosaic.py` (Zeichentabelle gegen die Unicode-Namen, Raster, Seitenverhältnis,
Blockgrößen, Frames, und ob die Pixelschrift jedes Mosaikzeichen kennt).
Vorschau: `brocast/mockup/teletext-vorschau.html` (Textseite und Bildseite).

## CR39 – Rubriken in der Seitenleiste der Web-GUI (✅ 14.10.2026)

**Problem:** Die Rubriken standen nur in der Karte „Rubrics" auf dem Dashboard. Wer in den Messages
arbeitete, musste erst aufs Dashboard zurück, um auf eine Rubrik zu filtern.

**Lösung:** In der Seitenleiste unter *Messages* der aufklappbare Punkt **Rubrics** (Pfeil ▾/▸, daneben die
Zahl der Rubriken).

- Darunter je Rubrik eine Zeile mit Name und `Bulletins (ungelesen)`; ein Klick öffnet die Messages,
  gefiltert auf diese Rubrik (wie bisher die Dashboard-Karte, inklusive Chip „Rubric XY ✕" zum Aufheben).
  Die gewählte Rubrik ist in der Seitenleiste markiert.
- Reihenfolge wie in `[rubrics]` der `tinybox.conf`, danach `TBNEWS` und die Rubriken, die nur durch
  Bulletins existieren. Eine abgelehnte Rubrik (`NAME = -`) steht durchgestrichen und grau da,
  der Tooltip nennt den Grund („refused" / „not in [rubrics] of tinybox.conf").
- Auf- und zugeklappt bleibt im Browser gemerkt (`localStorage tinybox.rubrics`), Standard aufgeklappt.
- Die Liste kommt aus `GET /api/rubrics` – dieselbe Quelle wie die Dashboard-Karte, die jetzt denselben
  Zwischenspeicher nutzt (ein Abruf je Aktualisierung statt zwei). Keine Änderung am Server.

Nur Sysop-Oberfläche, daher keine neue Client-Version und keine TBNEWS.

## CR40 – Sync beim Anmelden: nur Köpfe, Text auf Abruf (✅ 15.10.2026)

### Umsetzung (15.10.2026)

Client-Version **2026.10.15**. TinyBox und Client müssen beide aktualisiert werden (neue Cap `SHORT`);
ein alter Client an einer neuen TinyBox und umgekehrt funktionieren weiter (dann ohne `short=`).

- **TinyBox – Frist je Rubrik:** `[rubrics] NAME = Beschreibung | Tage` (auch `7d`), `0` = nie löschen,
  ohne Angabe gilt `[mailbox] bulletin_expire_days`. `purge_expired()` löscht je Rubrik; die Web-GUI zeigt
  „kept 7 d" in der Rubrik-Karte und im Tooltip der Seitenleiste (`/api/rubrics` liefert `expire_days`).
- **TinyBox – `//SYNC … short=<n>`** (Cap `SHORT`): nur Texte persönlicher Mails bis `n` Byte gehen mit.
- **TinyBox – Terminal:** Ausgaben über 10 Zeilen beginnen mit `*** 37 lines follow - send A to abort` und
  laufen dann komplett durch; `A` verwirft, was noch in der Warteschlange liegt (was Direwolf schon hat,
  höchstens `max_outstanding` Frames, geht noch hinaus). Über Telnet wirkt `A` nicht (wird sofort geschrieben).
  Die Seitenteilung von CR29 (`--More--`) ist weg.
- **Client – Abgleich nach jeder Anmeldung:** 1,5 s nach `//OK` startet der Scope `login` (Postausgang,
  Mail-Köpfe, dann Köpfe der abonnierten Rubriken). Abschaltbar mit `[sync] on_login = no`.
  Auch der Knopf „Sync“ holt nur noch Köpfe.
- **Client – kurz:** `[sync] short_bytes` (Vorgabe 256, 0 = nie); steht ein Eintrag in der conf, gilt dieser.
  Ohne Cap `SHORT` (alte TinyBox) holt der Client die kurzen Texte mit einem `//GET`.
- **Client – Text beim Anklicken:** `POST /api/mail/fetch {"id": n}`. Der Reader zeigt „Loading the text
  (1.2 KB) – text #12 (1.2 kB, approx. 15 s)… [Abort]“ und dann den Text. Ohne Verbindung:
  „Not connected – the text cannot be fetched now.“, nichts wird vorgemerkt. Ein Klick während eines
  Abgleichs geht zwischen zwei Wechseln hinaus. In der Liste steht bei fehlenden Texten „not loaded · 1.2 KB“.
- **Client – Abort:** Knopf „✕ Abort“ in den Köpfen *Mail*/*Bulletins* (ersetzt „Cancel“), im Reader beim
  Laden eines Textes. `POST /api/mail/abort` (`/api/mail/cancel` geht weiter). Nach 30 s ohne Antwort
  harter Abbruch.
- **Client – Meldungen** (oben in der Ordnerliste, wegklickbar, und in der Konsole), z. B.
  `Mail: 27 mail header(s) (approx. 55 s) to fetch. Press Abort to stop at any time.`, dann
  `Bulletins: 40 bulletin header(s) (WX 30, DX 10) (approx. 1 min 10 s) to fetch. …` – nach einem
  vollständigen Abgleich verschwindet die Meldung wieder. Beim Abort:
  `Sync aborted. Still pending: 23 mail header(s), … It goes on from here at the next login or with Sync.`
- Tests: `test_rubrics.py` (`RubricValidity`), `test_mailsync.py` (`ShortTextTests`, `LoginSyncAbortTests`,
  `EstimateTests`, angepasst), `test_tinybox.py` (`PagingTests`), `test_agw.py`.

### Erfassung

**Wunsch (OE3GAS):** Meldet sich ein Client bei der TinyBox an, dann soll er

1. die **Köpfe aller Mails** bekommen – die eigene persönliche Post und die Bulletins der Rubriken,
   die er abonniert hat;
2. erst wenn er auf einen Kopf **klickt**, wird diese Mail bzw. dieses Bulletin (der Text) abgerufen.

**Heute:** Der Abgleich startet nur per Knopf, getrennt für *mail* und *bulletins*
(`POST /api/mail/sync`). Er holt die Köpfe (`//SYNC` / `//BSYNC`, CR26) und danach **alle fehlenden
Texte** (`_texts()` in `tbclient/sync.py`); kurze Texte hängt die TinyBox schon an die Delta-Antwort
(`want=`, PLANUNG 12.9 Stufe 2). Bei vielen Bulletins laufen so Texte über Funk, die nie jemand liest.
„Cancel“ (`/api/mail/cancel`) bricht heute hart ab (`task.cancel()` mitten im Wechsel).

### Entscheidungen (OE3GAS, 15.10.2026)

| # | Frage | Entscheidung |
|---|---|---|
| E1 | Kurze persönliche Mails gleich mitnehmen? | **Ja.** Bulletins nie – nur Köpfe. |
| E2 | Wann abgleichen? | **Bei jeder Anmeldung** automatisch (Mail + abonnierte Rubriken). Knopf „Sync“ bleibt für zwischendurch. |
| E3 | Erstes Anmelden (leere Mailbox) | 1) **alle Köpfe der persönlichen Mails**, 2) **alle Köpfe der abonnierten Rubriken** – **kein Limit**, keine „Weiter“-Abfrage. Der User entscheidet selbst mit „Abort“ (E4), wann Schluss ist. Die Menge ist ohnehin durch die Ablauffrist der Bulletins begrenzt. |
| E4 | Abbruch | **Abort-Knopf** für einen **geordneten** Abbruch (siehe unten). |
| E5 | Restanzeige | Beim **Start** des Transfers (nach dem Anmelden) und beim **Abort** eine Meldung: was ist noch ausständig + **geschätzte Zeit**. |
| E6 | Klick auf einen Kopf ohne Verbindung (kein Connect) | Meldung **„not connected“**, Anforderung **verwerfen** – nicht für das nächste Mal vormerken. |
| E7 | Was ist „kurz“? | **`short_bytes` = 256 Byte** als Vorgabe; steht ein Eintrag in `[sync]` der `tbclient.conf`, gilt dieser. Richtwert: „kurz“ ≈ **2 s** Sendezeit. |
| E8 | Hinweis auf Abort | **Zu Beginn** des Downloads wird der User auf die Abort-Möglichkeit hingewiesen, danach laufen **alle** Köpfe komplett durch. |
| E9 | Terminal (CR29) | Abort auch im Terminalbetrieb; damit **entfällt** die Seitenteilung zu 10 Zeilen mit „continue/abort“ (siehe unten). |

### „Kurz“ = 256 Byte (E7)

- Neue Einstellung `[sync] short_bytes` in der `tbclient.conf` (und `tbclient.conf.example`),
  **Vorgabe 256**, 0 = nie Texte mitnehmen. Steht der Eintrag in der conf, gilt dieser.
- 256 Byte = **1 Frame** (PACLEN 256), ca. 3–4 Zeilen Text. Bei 1200 Bd (~100–120 Byte/s netto)
  rund **2 s** Sendezeit – das ist Gerhards Maßstab für „kurz“.
- Passt mit den Köpfen in denselben Wechsel (`chunk_bytes` 1024, `want=`).
- Umsetzung: neuer Parameter `short=<n>` im `//SYNC`, die TinyBox hängt nur Texte persönlicher Mails
  ≤ `short` an; bei `//BSYNC` immer `want=0`. Alte TinyBox ohne `short=` → Client schickt `want=0`
  (nur Köpfe, Texte auf Klick).
- Längere persönliche Mails und alle Bulletins: nur Kopf, Text beim Anklicken.

### Ablauf beim Anmelden

1. Verbindung steht → Client startet von sich aus den Abgleich: zuerst persönliche Post (`//SYNC`),
   dann abonnierte Rubriken (`//BSYNC`), nur Köpfe (+ kurze persönliche Texte, siehe oben).
2. **Hinweis auf Abort** (E8) gleich beim Start, z. B. „Downloading headers – press Abort to stop at any time“.
   Danach laufen **alle** Köpfe ohne Limit und ohne Rückfrage durch (persönliche Post, dann jede abonnierte Rubrik).
3. **Startmeldung** (E5), sobald die erste Antwort da ist – erst dann ist der Umfang bekannt
  (`//SYNCEND <more>` liefert die Zahl der noch ausstehenden Köpfe), z. B.:
   > Sync started: 37 mail headers + 4 short texts, bulletins (3 rubrics) pending – approx. 1 min 40 s
4. Fortschritt in der Statuszeile wie heute (Schritt, n von m).
5. Liste zeigt die Köpfe sofort; Einträge ohne Text erkennbar (Symbol „nicht geladen“ + Größe in Byte).

### Geordneter Abort (E4)

- Knopf **„Abort“** sichtbar, solange ein Abgleich oder Textabruf läuft (ersetzt das bisherige harte Cancel).
- Geordnet heißt: der **laufende Wechsel wird noch fertig empfangen und gespeichert**, dann keine neue
  Anfrage mehr. Kein Abbruch mitten in einem Frame/Text, `seq` bleibt konsistent → der nächste Abgleich
  macht genau dort weiter.
- Wird der Abort gedrückt, während auf die Antwort gewartet wird, und kommt sie nicht binnen einer
  Frist (z. B. 2 × T1-Schätzung bzw. 30 s), dann doch harter Abbruch mit Hinweis.
- Die Verbindung zur TinyBox bleibt bestehen (Chat geht weiter); nur eine vom Sync selbst aufgebaute
  Verbindung (`own_connect`) wird getrennt.
- **Abort-Meldung** (E5), z. B.:
  > Sync aborted. Still pending: 21 mail headers, bulletins of 3 rubrics – approx. 1 min 05 s. Will continue at next login or with „Sync“.

### Zeitschätzung (Vorschlag)

- Restbytes ≈ ausstehende Köpfe × 90 Byte (`HEADER_BYTES`) + Größe der ausstehenden kurzen Texte;
  Bulletins: Zahl der Köpfe je Rubrik aus der Rubrikenliste (`max` gegen lokal höchste Nummer),
  sonst „unbekannt“.
- Zeit = Restbytes ÷ **gemessener** Durchsatz der laufenden Verbindung (Bytes/s der bisherigen Wechsel)
  + Anzahl Wechsel × `pause_sec`. Vor dem ersten Wechsel Annahme 1200 Bd ≈ 100 Byte/s netto.
- Anzeige gerundet („approx. 2 min“), keine Scheingenauigkeit.

### Text auf Klick

- Klick auf einen Kopf → Client holt genau diesen Text (`//GET <id>`, lange Texte über Funk mit
  `//PART`), zeigt „loading … (x Byte, approx. y s)“ und dann den Text; auch hier Abort möglich.
  Einmal geholte Texte bleiben lokal, ein zweiter Klick geht nicht über Funk.
- Neue Web-API, z. B. `POST /api/mail/fetch {"id": n}`, über denselben Syncer (nie zwei Abrufe
  gleichzeitig auf dem Kanal). Läuft gerade der Anmelde-Abgleich, wird der Klick danach bzw. zwischen
  zwei Wechseln bedient.
- **Keine Verbindung** → „not connected“, Anforderung verworfen (E6). Kein eigener Connect nur für den Klick.
- Gelesen-Meldung (`r=` im nächsten `//SYNC`) erst, wenn der Text wirklich angezeigt wurde.

### Ablauffrist der Bulletins

- Bulletins werden nach einer Frist gelöscht; das begrenzt, wie viele Köpfe ein neuer Client überhaupt
  bekommen kann – deshalb ist kein Limit nötig.
- **Heute** gibt es dafür nur **eine** Frist für alle Rubriken: `bulletin_expire_days` (Vorgabe 30) in
  `[mailbox]` der `tinybox.conf`; `purge_expired()` löscht, der Client sieht es über die Tombstones (`//D`).

### Terminal: Abort statt Seitenteilung (E9, ersetzt CR29)

- Heute (CR29): Ausgaben über 10 Zeilen kommen seitenweise (`PAGE_LINES = 10` in `session.py`) mit
  `--More (10/37)-- Enter = continue, A = abort:`.
- Neu: **zu Beginn** einer langen Ausgabe (> 10 Zeilen) ein Hinweis, z. B.
  `37 lines follow - send A to abort`, dann läuft die Ausgabe **komplett** durch, ohne Rückfrage.
- Abort: Eingabe `A` / `Q` / `/AB` während der Ausgabe → die TinyBox schickt nichts mehr nach, Abschluss
  `*** aborted, 21 lines skipped`.
- Technische Grenze: Was schon an Direwolf/AGW übergeben ist, geht noch hinaus. Damit der Abort greift,
  gibt die TinyBox die Ausgabe **portionsweise** an Direwolf (z. B. ~2 Frames vorgehalten, Rest erst wenn
  diese bestätigt sind – AGW `y`/Outstanding-Frames) und prüft dazwischen auf Eingaben.
- Ergibt einen TBNEWS-Hinweis (Bedienung im Terminal ändert sich).

### Entschieden zuletzt

- Ablauffrist: **jede Rubrik bekommt vom Sysop eine eigene Dauer** (Gerhard, 15.10.2026).

## CR41 – KISS-Mode: Kanal- und kisshub-Werte in der Web-GUI (✅ 15.10.2026)

**Problem:** Im KISS-Mode kennt die TinyBox nur ihre eigenen AX.25-Verbindungen. Ob der Kanal voll
ist, ob der TNC hinter kisshub überhaupt arbeitet oder ob Frames im Hub warten, ist nicht sichtbar.
Das führt zu Fehldeutungen beim Qualitäts-Monitoring (T1-Abläufe durch Kollisionen, hängenden TNC
oder volle Hub-Warteschlange sehen aus wie eine schlechte Funkstrecke). Außerdem zeigt die
Kopfzeile grün „connected", solange kisshub läuft – auch wenn der TNC tot ist.

KISS kann grundsätzlich nicht liefern: Trägererkennung (DCD), Signalstärke, verworfene Frames mit
Prüfsummenfehler, tatsächlicher Sendezeitpunkt. Gemessen wird nur, was als gültiger Frame ankommt
oder hinausgeht.

**Weg 1 – Kanal (TinyBox rechnet selbst, aus dem KISS-Datenstrom):** kisshub reicht jeden
empfangenen Frame und die Aussendungen der anderen Clients (brocastd) an die TinyBox weiter.

- Kanalauslastung in % (letzte Minute, letzte 10 Minuten), geschätzt aus Framelänge, Funk-Baudrate
  und TXDELAY; Anteil eigene Aussendungen / andere.
- Frames pro Minute der letzten 60 Minuten.
- Gehörte Stationen (MHEARD): Rufzeichen, Frames, Sendezeit, zuletzt gehört.

**Weg 2 – kisshub (Status-Abfrage `GET http://127.0.0.1:8102/status`, JSON, nur lokal):**

- TNC: Profil, Zustand (down / init / kiss) seit wann, Anzahl Initialisierungen und Portverluste,
  letzter Fehler, die letzten Init-Zeilen mit Antwort.
- Sendewarteschlange: Länge je Priorität, Wartezeit im Hub (Mittel/Maximum der letzten 10 min,
  getrennt für Steuer-Frames und I-Frames), verworfene Frames.
- Clients: Adresse, verbunden seit, Frames in/out, Sendezeit, Absender-Rufzeichen (daran erkennt
  man TinyBox und brocastd).
- Die TinyBox fragt im Takt von `quality_poll_sec` (30 s) ab. `[kiss] status_port` (Standard 8102,
  0 = aus), in kisshub `[server] status_port`.

**Anzeige (nur Sysop-Web-GUI):**

- Kopfzeile im KISS-Mode: statt „Direwolf connected via KISS" der TNC und sein Zustand, z. B.
  „PK-232 ready via KISS"; rot bei TNC nicht bereit oder kisshub nicht erreichbar.
- Dashboard: Karte **Channel** mit Auslastung, Frames/min als Mini-Verlauf, gehörte Stationen,
  TNC-Zustand und Wartezeit im Hub.
- Detailansicht eines Users: Kanalauslastung der letzten 10 min neben den Balken.
- Sysop-Konsole `STATUS`: TNC-Zustand in der Radio-Zeile.

Die Kanalauslastung fließt **nicht** in die Balken ein, sie steht daneben.

Nur TinyBox, kisshub und Sysop-Oberfläche, daher keine neue Client-Version und keine TBNEWS.

**Umgesetzt (15.10.2026):**

- `tinybox/chanmon.py` – Kanalmonitor: jeder Frame aus dem KISS-Strom und jeder eigene;
  Auslastung 1/10 min (TinyBox / andere), Frames und Belegung je Minute (60 min), gehörte Stationen
  mit Pfad. Nur im Speicher.
- kisshub: `GET http://127.0.0.1:8102/status` (`[server] status_port`, 0 = aus) mit TNC-Zustand,
  Init-/Weck-Dialog (letzte 20 Zeilen mit Antwort, ok/nicht ok), Initialisierungen, Portverlusten,
  letztem Fehler, Warteschlange je Priorität, Wartezeit im Hub (Mittel/Maximum, 10 min), verworfenen
  Frames, Clients mit Absender-Rufzeichen und Sendezeit. Neu: Frames, die länger als 30 s warten
  (TNC nicht bereit), werden verworfen statt verspätet gesendet.
- TinyBox: `[kiss] status_port` (Standard 8102), Abfrage alle `quality_poll_sec`;
  `GET /api/channel`; `/api/status` und `/api/sessions/<call>/linkq` um `radio` bzw.
  `channel_load` ergänzt.
- Web-GUI: Kopfzeile „PK-232 ready via KISS" (rot: „kisshub not connected", „PK-232 down",
  „initialising"; Tooltip mit dem Fehler), Dashboard-Karte **Channel** (Kacheln Busy 1 min /
  10 min / Wartezeit im Hub, Verlauf je Minute TinyBox/andere mit Tooltip, kisshub-Werte,
  aufklappbarer TNC-Dialog, Heard-Liste), Kanalauslastung in der Detailansicht unter den Balken.
- `STATUS` in der Sysop-Konsole: „connected (KISS …), TNC PK-232 kiss".
- 13 neue Tests (`tests/test_chanmon.py`).

## CR42 – Freier Connect (✅ 15.10.2026)

### Erfassung (OE3GAS, 15.10.2026)

Bisher war das Ziel fest `[tinybox] call` (OE3GAS-1). Der Client soll jede Station
connecten können; die Eingabe des Rufzeichens erfolgt in der Titelleiste („Connect to:“).
Icons: von OE3GAS beigestellt (Connect, Connecting, Connected, Disconnect, Disconnected,
Connect failed).

### Entscheidungen (OE3GAS, 15.10.2026, nach Entwurf)

1. Titelleiste immer **einzeilig**.
2. Links das eigene Rufzeichen.
3. Ganz rechts Disconnect (solange eine Verbindung besteht oder aufgebaut wird),
   Kuvert bzw. Sprechblase (Mail/Chat) und das Menü.
4. Nicht verbunden: Eingabefeld, nicht zu breit (9 Zeichen).
5. Der Connect-Knopf gleich rechts neben dem Eingabefeld.
6. connecting mit Zähler; die Statusanzeige immer rechts neben dem Rufzeichenpaar.
7. connected mit I-Frames bzw. UI.
8. disconnecting nur als Status, bis die Verbindung weg ist; dann wieder das Eingabefeld.
9. Das Feld merkt sich die letzten Eingaben.

### Umsetzung

- **Ziel:** `ClientCore.target` statt `cfg.tinybox_call`; `POST /api/connect
  {"target": "OE3XBS-8"}` (ohne `target`: das zuletzt verwendete). Prüfung wie in der
  Config (Rufzeichen, SSID 0–15), nicht das eigene. Telnet-Link: immer die eigene TinyBox.
- **Verlauf:** die letzten 10 Ziele, neueste zuerst, in `settings.json` des Clients
  (`recent`, `target`) – damit am Handy dieselbe Liste wie am PC. Im Feld als Auswahlliste;
  leeres Feld + Enter = das zuletzt verwendete Ziel (steht als Platzhalter im Feld).
- **Heim-TinyBox:** `[tinybox] call` bleibt die eigene TinyBox. Die Mailbox gehört zu ihr:
  Abgleich beim Anmelden, Sync-Knopf und Text auf Klick nur, wenn man mit ihr verbunden ist
  (oder offline – dann connectet der Sync wie bisher selbst, immer zu ihr). Der Hinweis auf
  neue Post (UI an TBMAIL) zählt nur von ihr. `auto_connect` geht zu ihr.
- **Einstellungen je TinyBox:** letztes Board, „gesehen bis“ (History) und MOTD gelten je
  Ziel (`settings.json` → `targets`); die Heim-TinyBox behält sie wie bisher oben.
- **Zustände:** neu `disconnecting` (Direwolf meldet sich mit `d`, wenn die Verbindung weg
  ist; ohne Antwort nach 90 s trotzdem offline). Wie die letzte Verbindung endete, steht in
  `ended`: `user` (selbst getrennt), `failed` (kam nicht zustande: „no answer from …“),
  `remote` (von der Gegenstelle oder Direwolf-Verlust: „disconnected by … · hh:mm“).
- **connecting-Zähler:** Sekunden seit dem Connect. Die SABM-Versuche selbst meldet
  Direwolf über AGW nicht, daher keine „Versuch n/10“-Anzeige.
- **Titelleiste:** Logo, Avatar, eigenes Call, Zustands-Icon, dann entweder
  „Connect to:“ + Feld + Connect-Knopf oder das Ziel-Call, Punkt und Statustext; rechts
  Disconnect, Mail/Chat, Menü. Am Handy (≤ 520 px) ohne Logo und ohne „Connect to:“-Text,
  ≤ 400 px auch ohne Avatar. Icons: `tbclient/web/conn/*.png` (aus der Vorlage
  ausgeschnitten, das Grau für die dunkle Leiste hell gemacht).
- Tests: `FreeConnectTests` in `tests/test_tbclient.py` (Fehl-Connect, fremde BBS,
  disconnecting, Verlauf über Neustart, Einstellungen je Ziel, Disconnect ohne Antwort).

## CR43 – Terminalmodus (✅ 15.10.2026)

### Erfassung (OE3GAS, 15.10.2026)

Frage: Wie sieht das aus, wenn man mit dem Client eine andere BBS connectet, die kein
TinyBox-System ist? Können wir eine Art Terminalmodus bieten?

### Befund vorher

Der Client wartete auf „Welcome to TinyBox“ und schickte nach 6 s **trotzdem**
`//CLIENT TB1 …`. Bei einer BPQ- oder FBB-Box landete diese Zeile als Befehl in deren
Prompt, die Oberfläche zeigte leere Boards.

### Umsetzung

- **Erkennung:** Nach dem Connect gilt die Gegenstelle als TinyBox, wenn „Welcome to
  TinyBox“ kommt. Bleibt das 6 s aus, bekommt nur eine **bekannte** TinyBox den Handshake
  trotzdem (die Heim-TinyBox, der Telnet-Testport und jede, die schon einmal mit `//OK`
  geantwortet hat – `settings.json` → `tinyboxes`). Jede andere Station wird nicht mit
  `//CLIENT` behelligt: der Client geht in den Modus `terminal`.
- **Terminal:** Solange nicht feststeht, dass es eine TinyBox ist, wird jede empfangene
  Zeile unverändert ins Terminal gelegt; im Modus `terminal` wird nichts mehr als
  Steuerzeile (`//`) oder Chat-Ereignis (`#`) gedeutet. Eigene Zeilen gehen mit
  `POST /api/term {"text": "…"}` roh hinaus (CR, auch eine leere Zeile). Puffer: 500 Zeilen,
  die Oberfläche bekommt die letzten 300.
- **Ansicht:** Wird die Station als Terminal erkannt, schaltet die Oberfläche von selbst
  auf die Terminal-Ansicht (Monospace, eigene Zeilen blau, Zustandszeilen grau, unten
  Eingabezeile mit Pfeil hoch/runter für die letzten 50 Eingaben). Statustext
  „connected · terminal“; das Mail-Kuvert führt zur (lokalen) Mailbox, von dort `>_`
  zurück ins Terminal.
- **Von Hand:** Menü → „Terminal“ (am PC auch in der linken Spalte) öffnet die Ansicht auch
  bei einer TinyBox; getippte Zeilen gehen dann direkt an sie.
- **Zeichensatz:** UTF-8, sonst Latin-1 (wie bisher in `LineSplitter`).
- **Grenzen:** kein Binärtransfer (YAPP, 7plus), keine Bilder, keine Mailbox der fremden BBS.

## CR44 – Verbindungslogbuch (✅ 15.10.2026)

### Erfassung und Entscheidungen (OE3GAS, 15.10.2026)

Logbuch der Verbindungen in Client und TinyBox – keine Inhalte, nur Gegenstation,
Connect-Zeit, Disconnect-Zeit, Gesamtdauer und, wenn möglich, die Bytes hin und zurück.

1. Aufbewahrung **unbegrenzt**, Export als **CSV** und **ADIF**.
2. In der TinyBox sieht **jeder User seine eigenen Connects**.
3. Fehlversuche (SABM ohne Login) kommen in der TinyBox **nicht** hinein.
4. Frequenz (für ADIF) im Client: **beim Start des Clients einmal abfragen**, gilt für die
   ganze Sitzung; die zuletzt erfasste wird angeboten und kann übernommen oder
   überschrieben werden.

### TinyBox

- Tabelle `connlog` in der Datenbank: `call`, `via` (radio/telnet), `t_on`, `t_off`, `secs`,
  `rx`/`tx` (Nutzdaten-Bytes, gezählt im AGW-, KISS- und Telnet-Adapter),
  `air_tx`/`air_rx` (Bytes über die Luft inkl. Wiederholungen aus der letzten
  `Q`-Abfrage des Direwolf-Forks, sonst leer), `ended` (`bye` = von der TinyBox beendet,
  `disc` = von der Station, `lost` = Verbindung verloren). Geschrieben in `Session.end()`,
  genau einmal; die lokale Sysop-Konsole zählt nicht. Ein Fehler beim Schreiben bricht die
  Trennung nie ab.
- Befehl **`QSO`**: die letzten 10 Connects des eigenen Rufzeichens (alle SSIDs), `QSO 30`
  mehr (max. 100). Sysop: `QSO ALL [n]`, `QSO <call> [n]`. In der Hilfe (`H`).
- Sysop-Weboberfläche: Seite **Connection log** (Filter nach Rufzeichen, Knöpfe CSV und
  ADIF; `GET /api/connlog`, `/api/connlog.csv`, `/api/connlog.adi?call=…`).
- ADIF: `[station] freq` (MHz) und `[station] locator` in `tinybox.conf`; ohne `freq` fehlen
  `FREQ`/`BAND` in der Datei.

### Client

- `data/tbclient/connlog.db`: jede Verbindung, auch nicht zustande gekommene (`failed`
  = keine Antwort, `cancelled` = selbst abgebrochen; Dauer 0, ohne Bytes). Bytes =
  Nutzdaten am Link. `ended`: `user`, `remote`, `failed`, `cancelled`. Mit der Frequenz
  der Sitzung.
- **Frequenz:** Beim ersten Öffnen der Oberfläche nach dem Start fragt ein Dialog nach der
  Frequenz (letzte vorbelegt, „Skip“ = ohne). Änderbar unter Settings → Connection log.
- Settings → **Connection log**: die letzten 200 Einträge, Links CSV (alles) und ADIF (nur
  zustande gekommene Verbindungen, älteste zuerst). `[station] locator` in `tbclient.conf`.

### ADIF

ADIF 3.1.4 (`.adi`): `CALL`, `QSO_DATE`/`TIME_ON`, `QSO_DATE_OFF`/`TIME_OFF`, `MODE` = `PKT`,
`STATION_CALLSIGN`, `OPERATOR`, `FREQ`, `BAND`, `MY_GRIDSQUARE`, `COMMENT`. Rufzeichen ohne
SSID (Logbuchprogramme erwarten ein Rufzeichen); das volle Rufzeichen, Weg, Dauer und Bytes
stehen im `COMMENT`. Gemeinsamer Code: `tinybox/connlog.py`. Tests: `tests/test_connlog.py`,
`FreeConnectTests` in `tests/test_tbclient.py`.

## CR45 – Multi-Connect im Client (✅ 15.10.2026)

### Erfassung (OE3GAS, 15.10.2026)

Den Client zu einem Multi-Connect-Programm ausbauen: max. 5 Verbindungen gleichzeitig,
umschaltbar, jede Verbindung in einem eigenen Fenster (nicht gleichzeitig angezeigt, immer
nur abwechselnd).

### Vorschlag (Claude, 15.10.2026)

1. Kanalleiste unter der Titelleiste, Kanal 1–5, Umschalten per Klick oder Alt+1 … Alt+5;
   die Titelleiste (CR42) zeigt immer den aktiven Kanal.
2. Kanal 0 = Monitor (alles Gehörte), zählt nicht zu den 5.
3. Jeder Kanal mit seiner Ansicht: TinyBox → Chat/Mailbox, sonst Terminal.
4. Hintergrund-Aktivität am Kanal-Chip sichtbar.
5. Dieselbe Station nur einmal; Mailbox-Abgleich über den Kanal der Heim-TinyBox.
6. Kanal bleibt nach Disconnect mit Verlauf stehen, bis man ihn schließt.
7. Sendewarteschlange aller Kanäle im Monitor (gemeinsamer Funkkanal).

### Entscheidungen (OE3GAS, 15.10.2026)

- Zu 4: **Chip blinkt**, wenn im Hintergrund neuer Input kam; **rot blinkend**, wenn im
  Hintergrund ein Disconnect erfolgte.
- Nur **eine** TinyBox im Chat-Modus gleichzeitig; eine weitere TinyBox öffnet als Terminal.
- Telnet-Link: erreicht nur den Testport der eigenen TinyBox (nur auf `127.0.0.1`, also nur
  am TinyBox-PC – praktisch der Zugang des Sysops). Er bleibt **Einkanal-Betrieb**;
  Multi-Connect gibt es nur über Funk (`link = agw`).

### Umsetzung

- **Links:** `AgwPort` hält die eine TCP-Verbindung zu Direwolf (Registrierung, Monitor `k`)
  und verteilt die AGW-Frames nach Gegenstation an die `AgwLink`s – einer je AX.25-
  Verbindung. Ein neuer Connect beginnt mit frischem Zeilenpuffer und Zählern.
- **Kanäle** (`tbclient/channels.py`): Kanal 1–5, je ein Link mit eigenem Zustand
  (connecting … disconnecting), Ende, Terminalzeilen (500), Logbuch-Eintrag und einem
  Aktivitätszähler für das Blinken. Kanal 1 gibt es immer; weitere entstehen beim Connect
  und verschwinden mit dem Kreuz (nur getrennt). Die gleiche Station nur in einem Kanal.
- **Chat-Kanal:** Meldet sich eine TinyBox („Welcome to TinyBox“, oder nach 6 s eine
  bekannte), wird ihr Kanal der Chat-Kanal – sofern nicht schon ein anderer Kanal mit einer
  TinyBox im Client-Modus läuft; dann bleibt er Terminal. Boards, Mailbox, Bilder und Sync
  arbeiten immer mit dem Chat-Kanal. Der Mail-Abgleich ohne Verbindung öffnet einen eigenen
  Kanal zur Heim-TinyBox, der danach wieder verschwindet.
- **Monitor (Kanal 0):** jeder gehörte Frame als Zeile im Stil der klassischen Monitore
  (`fm OE3XYZ to APRS via OE1XAR <UI>: …`, `<I 3,2>`, `<SABM+>`, `<RR 4>`); in der
  Kopfzeile, wie viele Frames je Kanal noch bei Direwolf warten (AGW `Y`, alle 3 s).
- **Oberfläche:** Kanalleiste unter der Titelleiste (Chips mit Nummer, Zustandspunkt,
  Rufzeichen, „chat“ beim Chat-Kanal), „+ new“, Kreuz zum Schließen, Alt+0 … Alt+5. Die
  Titelleiste (CR42) zeigt immer den aktiven Kanal. Chat-Kanal → Chat/Mailbox, jeder
  andere Kanal → Terminal. Der Browser holt mit `/api/state?ch=n` nur die Zeilen des
  gezeigten Kanals; beim Umschalten wird die wartende Abfrage abgebrochen.
- **Blinken:** blau blinkend bei neuem Input im Hintergrund (Terminalzeile oder Chat),
  rot blinkend, wenn dort eine Verbindung von der Gegenseite getrennt wurde oder nicht
  zustande kam; selbst getrennte blinken nicht. Aufrufen des Kanals beendet das Blinken.
- API: `POST /api/connect {"target", "ch"}`, `/api/disconnect {"ch"}`,
  `/api/channel/close {"ch"}`, `/api/term {"text", "ch"}`.
- Tests: `FreeConnectTests` (TinyBox-Chat und BBS-Terminal parallel, zweite Station gleich
  nicht doppelt, nur eine TinyBox im Client-Modus, Kanäle schließen, Monitorzeilen).

## CR46 – Client über kisshub (✅ 15.10.2026)

### Erfassung (OE3GAS, 15.10.2026)

Der Client soll auch mit dem kisshub arbeiten, wenn ein KISS-TNC am PC hängt – damit ist er
allein, ohne TinyBox, ein vollwertiges Packet-Radio-Programm. Ohne Eintrag bleibt
`link = agw` (Direwolf).

### Umsetzung

- `tbclient.conf`: `[tinybox] link = kiss`, dazu `[kiss]` (host, port 8101, status_port
  8102, channel, air_baud, txdelay_ms) und `[ax25]` (version, paclen, maxframe,
  maxframe_ext, srej, n2, T1/T2/T3) – dieselben Werte wie `[ax25]` der TinyBox.
- `tbclient/kisslink.py`: `KissPort` (KISS-TCP zum kisshub über `tinybox.ax25.kissio`,
  Router Frame → Verbindung, Timer aller Verbindungen, Monitor) und `KissLink` (eine
  `Ax25Link` aus `tinybox/ax25` je Kanal, gleiche Schnittstelle wie `AgwLink`). Gesendete
  Frames halten die Timer der anderen Verbindungen an (ein Sender für alle), gehörte
  ebenso (Halbduplex). Stationen, die SABME mit DM beantworten, werden gemerkt (nächstes
  Mal SABM).
- **Gründe beim Trennen:** normal/Zeitüberschreitung → „disconnected“ (beim Connecten
  „no answer from …“), DM → „refused (DM)“, Retries aus → „link lost (no answer)“.
- **kisshub-Status:** alle 30 s `GET /status` (welcher TNC, im KISS-Modus?). Monitor-Kopf
  z. B. „PK-232 ready via KISS · 22 frames · waiting to send 1: 0, 2: 0“; ist der kisshub
  (oder bei AGW Direwolf) nicht erreichbar, zeigt das die Titelleiste rot.
- **Eingehende Connects** (KISS und AGW): ruft eine Station uns an, nimmt sie der erste
  freie Kanal als Terminal; der Chip blinkt. Kein Kanal frei oder die Station schon
  verbunden → DM (KISS) bzw. sofortiges Trennen (AGW).
- **Monitor:** zeigt mit KISS auch die eigenen Frames; Paare, die nach SABME mit
  Modulo 128 arbeiten, werden mit zwei Steuerbytes richtig gelesen (`<I 1,5>`).
- Mit KISS gilt die Verbindung als Funk wie AGW: Bilder (IMG), UI-Frames, Sync-Pausen.
- Tests: `tests/test_tbclient_kiss.py` (Chat mit der TinyBox über deren KISS-Adapter,
  Client zu Client mit eingehendem Connect, Fehl-Connect), AGW-Gegenstück in
  `FreeConnectTests.test_incoming_connect_over_agw`.

### Betrieb

kisshub lauscht nur auf `127.0.0.1`: Client und kisshub laufen auf dem PC mit dem TNC.
Start: `kisshub.bat`, dann `tbclient.bat`. TinyBox und Client können sich denselben
kisshub teilen (unterschiedliche Rufzeichen); kisshub gibt gesendete Frames auch an die
anderen Clients weiter.

## CR47 – Post sofort aussenden (✅ 15.10.2026)

### Erfassung (OE3GAS, 15.10.2026)

Wenn eine Mail vom User geschrieben wurde und in die Outbox geht, soll sie gleich
ausgesendet werden.

### Umsetzung

- Neuer Sync-Umfang **`send`**: nur die Outbox (`//SEND` je Mail), kein Abholen, setzt
  „last sync“ nicht. `ClientCore.send_outbox()` startet ihn gleich nach dem Speichern
  (`POST /api/mail/save`).
- **Verbunden mit der eigenen TinyBox:** geht über diese Verbindung, sie bleibt stehen.
- **Offline:** der Sync baut die Verbindung zur eigenen TinyBox in einem freien Kanal auf,
  sendet und trennt wieder (Kanal verschwindet).
- **Ein Abgleich läuft gerade:** die Mail geht gleich danach hinaus (`send_again`).
- **Chat-Kanal mit einer anderen TinyBox / Verbindung im Auf- oder Abbau / Bild-Upload
  / kein Kanal frei:** die Mail wartet in der Outbox; der Grund steht als Hinweis in der
  Mailbox. Sie geht mit dem nächsten Sync (auch dem nach dem Anmelden) hinaus.
- Hinweis im Composer: „Goes out right away to your TinyBox“.
- Tests: `SendAtOnceTests` in `tests/test_mailsync.py`.

## CR48 – Bake der TinyBox (✅ 15.10.2026)

### Erfassung (OE3GAS, 15.10.2026)

Eine Bake für die TinyBox-BBS: in der Konfiguration unter `[beacon]` steht, welcher Text
in welchem Intervall gesendet wird. Liegen neue Mails für User vor, kommt das in die
Bakenaussendung hinein.

### Umsetzung

- `tinybox.conf` `[beacon]`: `enabled` (Standard no), `interval_min` (5–1440), `dest`
  (Ziel des UI-Frames, Standard BEACON), `path` (bis 2 Digis, z. B. WIDE1-1), `text`
  (`{call}` = mailbox_call, `{qth}`), `mail_list` (yes), `first_after_sec` (60).
- `tinybox/beacon.py`: ein UI-Frame vom Mailbox-Rufzeichen, z. B.
  `TinyBox OE3GAS-1 - connect for mail and chat - Mail for: OE1ABC OE3TEC`. In die Liste
  kommen die Rufzeichen (ohne SSID, alphabetisch) mit **ungelesener persönlicher Post**
  hier – nur lokale Post, nicht wartende Forward-Post oder gehaltene. Gelesen → fällt aus
  der Liste. Mehr als in einen Frame passt (256 Byte): Rest als „+n“. Leerer Text und
  keine neue Post → keine Aussendung.
- AGW: mit Digi-Pfad als `V`-Frame, sonst wie bisher `M`; KISS: UI-Frame mit Pfad.
- Sysop-Konsole: **`BEACON`** sendet sofort und zeigt den Text (auch bei
  `enabled = no`, zum Testen). Die Werte stehen in der Sysop-Weboberfläche unter Settings.
- Nur TinyBox, daher keine neue Client-Version und keine TBNEWS.
- Tests: `tests/test_beacon.py`.

## CR49 – Suche in Mails und Bulletins (✅ 15.10.2026)

### Erfassung (OE3GAS, 15.10.2026)

Suchfunktion im Client und in der TinyBox, um in den Mails und Bulletins zu suchen:
String im Suchfeld eingeben → der Client zeigt die Mails bzw. Bulletins, die den String
enthalten.

### Umsetzung

- **Client:** Suchfeld über der Nachrichtenliste der Mailbox; ab 2 Zeichen sucht er beim
  Tippen (250 ms Pause) in allen Mails und Bulletins hier – Betreff, Text, Absender,
  Empfänger (bei Bulletins die Rubrik), @-Adresse; Groß-/Kleinschreibung egal. Treffer
  als eigene Liste „Search "…"“, neueste zuerst, mit Kennzeichen persönlich / Bulletin
  und Rubrik, bei Treffern im Text mit Ausschnitt. Leeres Feld → zurück zum Ordner davor.
  Gesucht wird nur, was hier liegt: Texte, die noch nicht geholt sind (CR40), nur über den
  Kopf; nicht abonnierte Rubriken gar nicht. `GET /api/mail?folder=s:<text>`,
  `MailStore.search()`.
- **TinyBox:** Befehl **`F text`** (auch `FIND text`): Liste wie `L`, nur Nachrichten, die
  der User sehen darf (eigene persönliche Post, alle Bulletins; Sysop alles). In der
  Hilfe und im Prompt. `MessageService.search()`.
- **Sysop-Weboberfläche:** Das Suchfeld bei Messages findet jetzt auch im Text
  (`GET /api/messages?q=…`), bisher nur Rufzeichen und Betreff.
- Tests: `tests/test_search.py`.

## CR50 – Monitor überarbeitet (✅ 15.10.2026)

### Erfassung (OE3GAS, 15.10.2026)

1. Den Monitor unter „Settings“ entfernen – brauchen wir nicht mehr.
2. Wozu ist das „Terminal“ in der Seitenleiste, brauchen wir das noch?
3. Im Monitor das „fm“ entfernen, die Rufzeichen farblich unterscheiden – jedes durchgehend
   in derselben Farbe.
4. Suchfeld im Monitor: nur Zeilen mit dem Suchstring, auch bei neu hereinkommenden Frames.
5. Knopf „Clear“.
6. Welche speziellen Frames sendet die TinyBox? Filter, der nur diese zeigt.

### Umsetzung

1. Abschnitt „Monitor“ (die alte Protokollzeilen-Konsole) aus den Settings entfernt; der
   Eintrag „Monitor“ in der Seitenleiste schaltet jetzt auf Kanal 0. Die Konsole wird nicht
   mehr mit jedem Snapshot übertragen (spart Bandbreite im LAN).
2. „Terminal“ in der Seitenleiste bleibt, heißt jetzt **„TinyBox terminal“**: Es ist der
   einzige Weg, der TinyBox im Chat-Kanal klassische Befehle zu schicken (`L`, `R`, `F`,
   `QSO`, `J` …) – ein zweiter Kanal zur selben Station geht nicht (eine AX.25-Verbindung
   je Rufzeichenpaar). Für alle anderen Stationen ist das Terminal ohnehin die
   Kanalansicht.
3. Zeilen `20:59:00 OE1ABC → OE3GAS <I 0,0>: Hallo`; jedes Rufzeichen (mit SSID) bekommt
   aus einem Hash eine feste Farbe – dieselbe in jeder Sitzung.
4. Feld **Filter**: zeigt nur Zeilen mit dem Text (Zeit, Rufzeichen, Typ, Art, Inhalt;
   Groß-/Kleinschreibung egal); neue Frames werden beim Eintreffen gefiltert.
5. **Clear** leert den Monitor im Client (`POST /api/monitor/clear`).
6. Auswahl der **TinyBox-Sonderframes** (Kennzeichen am Ende der Kopfzeile):
   - `chat` – UI an `TBCHAT-n`: Chat-Ereignisse (`#seq` …) für Clients im UI-Modus
   - `quality` – `%Q`-Zeilen: die Zahlen hinter den Qualitätsbalken (UI an `TBCHAT-n`)
   - `mail` – UI an `TBMAIL`: Post-Hinweis „OE3ABC 2 new“
   - `beacon` – jede andere UI-Aussendung einer TinyBox (die Bake, CR48)
   - `proto` – I-Frames mit Client-Protokoll (`//CLIENT`, `//OK`, `//IN`, `//SYNC` …)
   Wählbar einzeln oder „all special frames“.
- **Nebenbei behoben:** I- und S-Frames mit Modulo 128 (AX.25 v2.2) wurden im Monitor
  falsch gelesen (Zeichen „�“ vor dem Text, falsche Zähler), wenn das eigene SABME nicht
  zu hören war (Direwolf zeigt die eigenen Frames nicht). Jetzt erkennt der Monitor
  Modulo 128 auch an der Lage der PID bzw. der Länge des S-Frames. Und „Welcome to
  TinyBox“ stand im TinyBox-Terminal doppelt.
- Tests: `RadioTests`/`FreeConnectTests.test_monitor_lines` in `tests/test_tbclient.py`,
  `tests/test_tbclient_kiss.py`.


## CR51 – TinyBox-Web-GUI: Liste bleibt beim Lesen sichtbar (✅ 15.10.2026)

### Erfassung (OE3GAS, 15.10.2026)

Betrifft die Sysop-Web-GUI der TinyBox (http://127.0.0.1:8080/), nicht den Client.

1. Beim Öffnen einer Nachricht verschwindet die Liste, die Nachricht füllt die Seite, rechts
   steht immer das Formular „New message“. Die Übersicht soll sichtbar bleiben, der Text
   darunter angezeigt werden.
2. Das Formular „New message“ nur zeigen, wenn der Knopf „New message“ gedrückt wird – das
   ist ein eigener Vorgang. Beim Lesen fällt es weg; der Knopf „New message“ steht im Kopf
   der Liste.

### Umsetzung

1. `#/message/<Nr>`: oben die Nachrichtenliste (alle Spalten, Filter, Suche, Rubrik bleiben
   erhalten, ca. 38 % der Höhe), darunter die Nachricht mit Reply / Edit header / Kill. Die
   offene Zeile ist markiert. Ein Klick auf eine andere Zeile tauscht nur die Nachricht
   unten aus – die Liste behält ihre Scroll-Position.
2. Das Formular rechts beim Lesen ist entfernt. „New message“ (im Listenkopf) öffnet wie
   bisher `#/compose`. **Reply** führt jetzt ebenfalls dorthin, mit vorausgefülltem
   Empfänger und Betreff; „Cancel“ geht zurück zur Nachricht.
- Dateien: `tinybox/web/app.js` (`viewMessage`, `viewCompose`, `route`),
  `tinybox/web/app.css` (`main.split`). Nur die TinyBox, kein neuer Client.

## CR52 – TinyBox-Web-GUI: Monitor wie im Client (✅ 15.10.2026)

### Erfassung (OE3GAS, 15.10.2026)

1. Die Monitor-Ansicht der TinyBox für den Sysop so gestalten wie im Client (CR50): Rufzeichen
   farblich unterschieden, Suchfeld für Strings.
2. Frage: Sehen wir als Sysop die ausgesendeten Frames der TinyBox? Gemonitort werden sie
   bisher nicht.

### Umsetzung

1. **Monitor** (Seite und Karte im Dashboard):
   - Jedes Rufzeichen hat eine feste Farbe (Hash, wie im Client; dunkler für den hellen
     Hintergrund).
   - Feld **Filter**: nur Zeilen mit dem Text (Zeit, Rufzeichen, Typ, Art, Inhalt;
     Groß-/Kleinschreibung egal), auch für neu eintreffende Zeilen.
   - Auswahl: alles · Kanal-Frames · eigene Frames (TX) · Sitzungstext · Log ·
     TinyBox-Sonderframes (alle, `chat`, `quality`, `mail`, `beacon`, `proto` – wie CR50).
     Ersetzt das bisherige Kästchen „MON“.
   - **Clear** leert den Monitor auch in der TinyBox (`POST /api/monitor/clear`), ein Reload
     bringt die alten Zeilen nicht zurück. Der Rückblick fasst jetzt 600 Zeilen (vorher 300).
2. **Frames im Monitor (KISS-Mode):** Im KISS-Mode macht die TinyBox AX.25 selbst und
   kennt daher jeden Frame – die gehörten und **die eigenen**. Neues Modul
   `tinybox/framemon.py`: jeder Frame wird eine Zeile
   `21:40:02 TX OE3GAS-1 → OE3TEC <I 0,0>: Welcome …` (`RX` gehört, `TX` gesendet; I-, S-,
   U-Frames mit Zählern und P/F, Modulo 128 aus der Verbindung oder geschätzt).
   Die Frames gehen nur an die Web-GUI (Logger `tinybox.frames` ohne Weitergabe), nicht in
   Logdatei oder Konsole.
   - Im **AGW-Mode** (Direwolf) gibt es weiterhin keine Frames, nur Sitzungstext und Log:
     Dort macht Direwolf AX.25 und meldet der TinyBox keine eigenen Frames.
   - Sitzungstext (`TXT`) zeigt jetzt auch das Rufzeichen der Gegenstation
     (`OE3GAS-1 → OE3TEC: …`); bisher stand dort nur `> Text`.
- Dateien: `tinybox/framemon.py` (neu), `tinybox/adapters/kiss.py`, `tinybox/adapters/web.py`,
  `tinybox/web/app.js`, `tinybox/web/app.css`. Test: `tests/test_framemon.py`.
  Nur die TinyBox, kein neuer Client.

## CR53 – TinyBox-Web-GUI: Monitor auf schwarzem Hintergrund (✅ 16.10.2026)

**Wunsch (OE3GAS):** Der Live-Monitor der TinyBox-Web-GUI soll wie der Monitor im Client einen
schwarzen Hintergrund haben.

**Lösung:** Gleiche Farben wie der Client-Monitor (CR50): Grund `#0c1218`, Text hellgrün-grau, Zeit und
Frametyp gedämpft grau, eigene Frames (TX) und Eingaben hellblau, Warnungen hellrot. Die Rufzeichen
bekommen hellere Farben (wie im Client), die TinyBox-Sonderframes (chat, quality, mail, beacon, proto)
farbige Marken. Nur `tinybox/web/app.css` und `tinybox/web/app.js` – nur die TinyBox, kein neuer Client.

## CR54 – Client: Farbbereiche links, neuer Kopf, Knöpfe Chat und Mailbox (✅ 16.10.2026)

### Erfassung (OE3GAS, 16.10.2026)

1. Farbliche Trennung der Bereiche „Chat Boards“, „Mail“, „Bulletins“ und „Station“ – nach
   Mockup (Variante E): Bereiche nicht füllen, sondern in ihrer Farbe umranden, Kopf als
   farbiges Band, gewählter Eintrag voll in der Bereichsfarbe.
2. „Rubrics…“ (Bulletins) und „Settings“ (Station) als Einträge entfernen; dafür ein Zahnrad
   rechts im Kopf von „Bulletins“ und „Station“.
3. Kopfzeile: neben dem Logo zweizeilig „TinyBox Client“, etwas Abstand, dann der Call-Avatar.
4. Der Knopf zurück aus der Mailbox hieß „Terminal“, führte aber zum Monitor – Tooltip
   korrigieren; neben dem Mail-Knopf auch einen Chat-Knopf.

### Umsetzung

1. Farben: Chat Boards violett `#6d4bd1`, Mail petrol `#0b7f86`, Bulletins ocker `#b06a00`,
   Station schiefergrau `#52606e` (unterscheiden sich auch in der Helligkeit; Grün/Rot/Gelb
   bleiben dem Verbindungsstatus und den Qualitätsbalken). Im Dunkelmodus sind Rahmen und
   Symbole aufgehellt. Gilt auch für die Ordnerliste der Mailbox am Handy.
2. Zahnrad bei Bulletins öffnet die Rubrikenliste, bei Station die Settings. Ohne abonnierte
   Rubrik steht im Bulletin-Bereich „No rubric subscribed“.
3. „TinyBox / Client“ neben dem Logo, feiner Trennstrich, dann Avatar und Call. Unter 760 px
   Breite fällt der Schriftzug weg (Platz für „Connect to“).
4. Zwei Knöpfe oben rechts: **Chat** und **Mailbox**; der Knopf der offenen Ansicht ist weiß
   gefüllt. Chat schaltet auf den Chat-Kanal. Mailbox nochmals gedrückt führt zurück, der
   Tooltip sagt wohin: „Back to Chat“, „Back to Monitor“ (Kanal 0) oder „Back to Terminal“.
   Monitor und TinyBox terminal sind in der Seitenleiste markiert, wenn sie offen sind.
- Client-Version 2026.10.16.

## CR55 – Monitor: APRS im Klartext, lehrreich (✅ 16.10.2026)

### Erfassung (OE3GAS, 16.10.2026)

1. APRS-Pakete im Monitor von TinyBox und Client für Menschen lesbar darstellen, wenn ein
   Toggle „APRS“ aktiv ist – nach Variante A: Rohzeile bleibt, darunter die Übersetzung.
2. Die Einzelteile des Pakets grafisch auf die Klartextteile abbilden: Wer sich APRS im Client
   ansieht, interessiert sich für Struktur und „Grammatik“ von APRS.
3. Links zu aprs.fi und OpenStreetMap.
4. Erklären, dass „AP…“-Ziele auf eine Liste definierter Geräte verweisen, andere Ziele (Mic-E)
   eigentlich Nutzdaten sind.
- Entwurf: Design-Canvas „APRS-Monitor lehrreich“ (claude.ai).

### Umsetzung

1. **Decoder `tinybox/aprs.py`** (eine Stelle für TinyBox und Client): zerlegt einen UI-Frame
   in Teile (Rolle = Farbe, Schlüssel, Bezeichnung, Bedeutung, Rechenweg) und Klartext-Chips.
   Die Teile ergeben zusammen wieder das Infofeld. Verstanden werden: Positionen
   unkomprimiert, komprimiert (base-91) und Mic-E (inkl. Längen-Offset, Message-Bits,
   Mehrdeutigkeit, Höhe, Gerät aus Präfix/Suffix, abgeschnittene Pakete); Wetter (mit
   Umrechnung °F→°C, mph→km/h; fehlerhafte Felder wie `h0` rot); Kurs/Geschwindigkeit, PHG,
   RNG, `/A=` Höhe; Zeitstempel (mit Hinweis, wenn die Uhr des Senders falsch geht); Status;
   Nachrichten (Empfänger, Nummer, ack/rej, Bulletins); Telemetrie **skaliert** mit den vorher
   gehörten PARM/UNIT/EQNS/BITS (Speicher je Station); Third-Party (`}`, inneres Paket
   rekursiv); Objekte und Items; positionsloses Wetter.
   - **Zielfeld**: `device ID` (Eintrag der Geräteliste aprs-deviceid), `payload` (Mic-E: die
     Breite + Message-Bits, in der Lupe als sechs Kästchen zerlegt) oder `free word`.
   - **Pfad**: je Eintrag eine Erklärung (wer hat weitergegeben, was ist noch offen), Summe
     und Warnung bei langen Pfaden (WIDE3 und mehr).
   - Entfernung und Richtung vom eigenen `locator` (tinybox.conf / tbclient.conf).
   - Daten: `tinybox/aprs_data.json` – Geräteliste aus aprs-deviceid (CC BY-SA 2.0, Quelle in
     der Lupe genannt) und Symbolnamen aus dem Symbolsatz des Clients.
2. **Monitore**: `tbclient/radio.monitor_entry` und `tinybox/framemon.entry` hängen das Ergebnis
   als `aprs` an den Eintrag (nur UI-Frames mit PID F0, nicht die TinyBox-Sonderframes).
   Der Client liest jetzt auch das H-Bit der Digipeater: der Pfad zeigt `*` wie in der TinyBox.
3. **Anzeige** (`tinybox/web/aprsview.js` + `.css`, eine Kopie für beide GUIs – der Client
   liefert sie aus `tinybox/web` aus):
   - Knopf **APRS** in der Monitor-Leiste (Zustand je Browser gemerkt). An: das Infofeld in
     Farben je Rolle, das Ziel mit Marke `device ID`/`payload`, Marke `aprs`, darunter die
     Klartextzeile mit Links **aprs.fi ↗** und **map ↗**.
   - **Hover**: ein Teil der Rohzeile leuchtet zusammen mit seinem Klartextteil auf (und
     umgekehrt), auch in der Lupe.
   - **Lupe** (rechts neben dem Monitor; Client: Kanal 0, TinyBox: Seite „Monitor“): Klick auf
     eine APRS-Zeile zeigt 1 · Adressteil (From, „To“ mit Erklärung, Pfad), bei Mic-E die
     sechs Zeichen des Zielfelds, 2 · Infofeld Teil für Teil mit Bedeutung und Rechenweg,
     Knöpfe zu aprs.fi und OpenStreetMap. Unter 900 px Breite nur die Klartextzeile.
   - Auswahl „APRS frames“ im Filter; das Suchfeld findet auch den Klartext.
- Tests: `tests/test_aprs.py` (echte Pakete vom 16.10.2026 auf 144.800 MHz, Monitore beider Seiten).
- Client-Version 2026.10.16.2.

## CR56 – APRS-Lense: Feinschliff und Fragen aus dem Betrieb (✅ 16.10.2026)

### Erfassung (OE3GAS, 16.10.2026)

1. Die APRS-Lense-Leiste erst einblenden, wenn der Knopf gedrückt ist. Knopf umbenennen auf
   „APRS Lense“.
2. Zwischen den einzelnen APRS-Aussendungen eine Trennlinie.
3. Frage zu einer Telemetrie-Definition von OE3CRA-2 über OE3XWJ-10: Welche Station habe ich
   hier tatsächlich gehört?
4. Frage zu OE3MZC-2: Was bedeutet „hF gateway“?
5. Diese Fragen soll auch die APRS-Lense beantworten.

### Umsetzung

1. Knopf **APRS Lense** (TinyBox und Client); aus, bis er gedrückt wird. Erst dann erscheinen
   Klartextzeilen und die Leiste. Der Zustand wird je Browser gemerkt (neuer Schlüssel, startet
   also bei allen einmal „aus“).
2. Jede APRS-Aussendung hat oben und unten eine feine Linie.
3. Neue Zeile **Heard** im Adressteil der Lense, dazu der Chip „heard from …“ in der
   Klartextzeile: gehört hat man den **letzten Digipeater, der das Paket weitergegeben hat** (er
   steht mit `*` als letzter Rufzeichen-Eintrag vor den verbrauchten Aliasen), ohne `*` im Pfad
   den Absender selbst. Hat der letzte Digipeater sein Rufzeichen nicht eingetragen, sagt die
   Lense, dass es nicht erkennbar ist. Hover zeigt den passenden Pfad-Eintrag.
4. „hF gateway“ war ein Fehler beim Kleinschreiben – jetzt „HF gateway“. Die Lense erklärt
   Symbole, wo der Name allein nicht reicht: `/&` (ursprünglich HF↔VHF-Gateway, heute meist
   iGates; sauberer wären Overlays I&, R&, T&, 2&), Digipeater-Overlays (1# Fill-in, S# regional,
   I# mit iGate …), Gateway-Overlays, `/_`, `/r`, `/-`.
- Nebenbei: PARM/UNIT/EQNS zeigen ihre Werte jetzt Kanal für Kanal (A1 Volt · A2 Pkt …), lange
  Werte brechen in der Lense um.
- Tests in `tests/test_aprs.py`. Client-Version 2026.10.16.3.

## CR57 – APRS-Lense: Zeilen neu geordnet, Pfad als Kette (✅ 16.10.2026)

### Erfassung (OE3GAS, 16.10.2026)

1. Monitorzeile umbauen: nach `<UI>` neue Zeile, dort ohne „aprs:“ gleich die Payload; neue Zeile,
   dann die Interpretation. „heard from“ entfällt in der Zeile (steht in der Detailansicht).
2. Den Pfad in der Lense grafisch darstellen: Chips mit kleinen Richtungspfeilen, z. B.
   OM0ODX → OE6XTR → OE3XWJ-10, sonst kein Text beim Pfad.

### Umsetzung

1. APRS-Zeilen (Knopf an): Kopf bis `<UI>`, darunter die farbige Payload, darunter der Klartext.
   Marke `aprs` und Chip „heard from …“ sind weg. Ohne Knopf bleibt die Zeile wie bisher.
   TinyBox-Web-GUI und Client gleich.
2. Lense, Zeile **Path**: nur noch die Kette Absender → Digipeater, die weitergegeben haben (mit
   Rufzeichen im Pfad). Die gehörte Station ist hervorgehoben; Hover verbindet sie mit der Zeile
   **Heard**. Ohne Digipeater steht nur der Absender da; hat ein Digi kein Rufzeichen
   eingetragen, endet die Kette mit „?“. Die Texte zu Aliasen und Resthops entfallen.
- Decoder liefert dafür `chain`. Tests in `tests/test_aprs.py`. Client-Version 2026.10.16.4.

## CR58 – Bug: Monitor startet nach Mailbox nicht (✅ 16.10.2026)

**Fehler (OE3GAS):** Nach einem anderen Knopf (z. B. Inbox) reagierte „Monitor“ in der Seitenleiste
nicht; erst nach „TinyBox terminal“ ging es.

**Ursache:** Der Monitor ist Kanal 0. War Kanal 0 schon der aktive Kanal (man kam aus dem Monitor in
die Mailbox), brach der Kanalwechsel sofort ab und die Mailbox blieb stehen. „TinyBox terminal“
wechselte vorher auf den Chat-Kanal, danach ging der Wechsel auf 0 wieder.

**Lösung:** Ein Klick auf den schon aktiven Kanal (Monitor, Kanal-Chip, Alt+Zahl) schaltet jetzt
dessen Ansicht ein. Client-Version 2026.10.16.5.

## CR59 – APRS-Lense: Symbol als Bild, Gerätename gelb (✅ 16.10.2026)

**Wunsch (OE3GAS):** In der Detailansicht beim Symbol-Code auch das Symbol zeigen („> = car“ + Bild) –
die Symbole hat der Client ja schon. Den Gerätenamen (z. B. „WB2OSZ DireWolf“) in der Erklärung zum
„To“-Feld auch gelb.

**Lösung:** Der Decoder gibt beim Symbol-Code das Symbol (Tabelle + Code) mit; die Lense zeigt davor
das Bild aus dem Symbolsatz des Clients (`/aprs/symbols-*.png`). Die TinyBox-Web-GUI hat keine
Symbolbilder und zeigt weiter nur den Text. Der Gerätename in der Erklärung hat die Gerätefarbe (gelb),
Hover verbindet ihn mit dem „To“-Feld. Client-Version 2026.10.16.6.

## CR60 – APRS-Lense am Handy (✅ 16.10.2026)

**Wunsch (OE3GAS):** Am Handy ist die Detailleiste der APRS-Lense nicht zu sehen. Gewählt: Variante A
(Bottom Sheet).

**Lösung** (TinyBox-Web-GUI und Client gleich, `tinybox/web/aprsview.js` + `.css`):
- Unter 900 px Breite ist die Lense ein **Bottom Sheet**: Tippen auf eine APRS-Zeile lässt es von
  unten heraufgleiten (75 % der Höhe); die angetippte Zeile rückt nach oben und bleibt sichtbar, der
  Monitor läuft weiter. Schließen mit ✕, Wisch nach unten (am Griff oder ganz oben im Sheet), Tippen
  außerhalb oder Esc. Tippen auf eine andere APRS-Zeile wechselt den Inhalt.
- **Antippen statt Darüberfahren:** Ein Tipp auf einen Teil der Payload oder des Klartexts hält das
  Paar hervorgehoben (auch in der Lense, die dorthin scrollt); ein Tipp in der Lense markiert den Teil
  oben in der Zeile. Am PC wirkt ein Klick genauso, das Darüberfahren bleibt.
- TinyBox-Dashboard (ohne eigene Lense-Leiste): am Handy erscheint dasselbe Sheet.
- Client-Version 2026.10.16.7.

## CR61 – APRS-Lense: Klartext als Karte; APRS-Statistik mit „Sünden“ (✅ 17.10.2026)

### Erfassung (OE3GAS, 17.10.2026)

1. Zwischen APRS-Paket und Interpretation zu wenig Trennung – gewählt: Variante B (Klartext als Karte).
2. Kleines Statistik-Tool: Frames je gehörter Station, je Sender, je AP-Device und was sonst
   interessant ist – ausdrücklich auch die „Sünden“ ausweisen.

### Umsetzung

1. Die Interpretation steht in einer eigenen, leicht helleren Karte mit runden Ecken unter der
   Payload; die gewählte Zeile hebt auch ihre Karte hervor (TinyBox und Client).
2. **APRS statistics** (Client, Station > APRS statistics). Modul `tinybox/aprsstats.py`, Daten in
   `data/tbclient/aprsstats.db` (bis 7 Tage, Neustart verliert nichts). Zeitfenster letzte Stunde,
   24 h oder seit Start; Reset mit zweitem Klick; alle 15 s aktualisiert.
   - Kacheln: Frames (je Minute), Stationen, Kanalauslastung (geschätzte Sendezeit bei 1200 Bd),
     Internet → Funk. Verlauf als Balken.
   - **Sins**: zu häufige Positionsbaken im Stand (< 5 min) bzw. in Fahrt (< 30 s); unveränderte
     Wiederholungen (< 10 min, Zeitstempel ignoriert; Telemetrie-Definitionen: einmal pro Stunde
     reicht); lange Pfade (WIDE3 und mehr); falsche Uhr; fehlerhafte Pakete; iGates mit viel
     Internet-Verkehr auf Funk (≥ 5 % des Kanals oder ≥ 30/h).
   - Tabellen (sortierbar): Heard, Senders (Third-Party zählt für die innere Station; Abstand,
     Entfernung, Typen, Gerät), Devices, Packet types, Digipeaters mit Wegen und Hop-Verteilung,
     iGates, Range (weiteste direkt/über Digis, Entfernungsklassen; braucht `locator`), Countries.
   - Klick auf ein Rufzeichen öffnet den Monitor, gefiltert auf diese Station.
   - Die TinyBox-Web-GUI bekommt die Statistik vorerst nicht (sieht Frames nur im KISS-Mode).
3. Decoder: Mic-E-Gerät wird auch ohne Präfix und mit CR am Ende erkannt (FT1D, FTM-400, TH-D72);
   Wetterfelder mit zu vielen Ziffern (`h074`, `b125031`) sind jetzt als fehlerhaft markiert.
- Tests: `tests/test_aprsstats.py`, `tests/test_aprs.py`. Client-Version 2026.10.17.

## CR62 – APRS-Lense: Aussendung als Karte, Knopf in drei Stufen (✅ 17.10.2026)

### Erfassung (OE3GAS, 17.10.2026)

1. Die gewählte Aussendung viel deutlicher markieren: die Aussendung als Ganzes, darin die Teile
   „Frame“ und „Interpretation“. Entwurf im Canvas „APRS-Monitor lehrreich“ – gewählt Variante 2
   (Karte mit farbigem Kopfband).
2. Die APRS-Lense ausblendbar: 1. Klick auf „APRS Lense“ = Interpretationssicht (Knopf blau),
   2. Klick = dazu die Lense rechts (Knopf grün wie „Mail“ links), 3. Klick = alles aus, zurück zum
   Monitor (Knopf weiß).
3. In der Interpretationssicht ohne Lense schaltet ein Klick rechts im Kopfband der gewählten
   Aussendung die Lense ein; Text „view Frame in APRS lense“.

### Umsetzung

1. Jede APRS-Aussendung ist eine Karte: oben **Frame** (Kopfzeile + Payload, dunkel), darunter
   **Interpretation** (heller), beide mit kleinem Etikett, gestrichelt getrennt. Die gewählte Karte hat
   einen blauen Rahmen (2 px) und ein blaues Kopfband mit Zeit und Rufzeichen.
2. Knopf in drei Stufen (weiß → blau → grün `#0b7f86` → weiß), Tooltip sagt die nächste Stufe; die
   Stufe wird je Browser gemerkt. Die Lense (rechts bzw. am Handy das Bottom Sheet) gibt es nur in der
   grünen Stufe.
3. Kopfband rechts: Knopf **view Frame in APRS lense** (schaltet auf grün und zeigt die Aussendung in
   der Lense); in der grünen Stufe steht dort „shown in the APRS lense“.
- Gleich in TinyBox-Web-GUI und Client (`tinybox/web/aprsview.js` + `.css`). Client-Version 2026.10.17.2.

## CR63 – APRS-Statistik: Reihenfolge, Geräte-Filter; Kopfband mit Symbol und Entfernung (✅ 17.10.2026)

**Wunsch (OE3GAS):** In der Statistik „Sins“ ganz nach unten, oben „Heard“, „iGates“, „Packet types“;
bei den Pakettypen zuerst die Prozent, dahinter in Klammer die Anzahl; Geräte filterbar wie die
Rufzeichen. Im blauen Kopfband der gewählten Aussendung neben dem Rufzeichen das APRS-Symbol und
„Distance“: ohne Locator „unknown“, sonst km und Richtung.

**Lösung:**
- Statistik: Heard · iGates · Packet types, dann Senders, Devices, Digipeaters, Range, Countries,
  zuletzt Sins (über die ganze Breite). Pakettypen als „12.3 % (45)“.
- Geräte (Tabelle Devices und Spalte Device bei Senders) sind anklickbar: der Monitor zeigt die
  Aussendungen dieses Geräts (bei Third-Party-Paketen auch das Gerät der inneren Station).
- Kopfband: Symbol (Bild aus dem Symbolsatz des Clients) und „Distance: 37 km, 179° S“ (Richtung mit
  16 Himmelsrichtungen); ohne `locator` „unknown (no locator)“, bei Paketen ohne Position
  „no position in this packet“. Decoder liefert dafür `dist`, `home`, `symbol`.
- Client-Version 2026.10.17.3.

## CR64 – APRS-Statistik: Zeitfenster als Knöpfe, Datei laufend aufräumen (✅ 17.10.2026)

**Wunsch (OE3GAS):** Die Statistik zeigte nur die letzte Stunde – Anzeige für letzte Stunde, 24 h und
alles. Die Datei `aprsstats.db` auch im laufenden Betrieb aufräumen, nicht nur beim Start.

**Lösung:**
- Die Auswahl war ein Klappmenü und leicht zu übersehen; jetzt drei Knöpfe **Last hour · 24 h · All**
  in der Kopfleiste, der gewählte blau. „All“ = alles Gespeicherte (max. 7 Tage bzw. seit dem
  letzten Reset). Die Wahl wird je Browser gemerkt.
- `tinybox/aprsstats.py`: einmal pro Stunde werden Datensätze älter als 7 Tage (und über 200 000)
  aus der Datei gelöscht; der freie Platz wird von SQLite wiederverwendet.
- Test `test_file_is_tidied_while_running`. Client-Version 2026.10.17.4.

## CR65 – Statistik je Rufzeichen (Stationsseite) (✅ 17.10.2026)

### Erfassung (OE3GAS, 17.10.2026)

Statistik je Call: Art der Frames, Zeitverlauf Frames/h und was sonst interessant ist. Erreichbar aus
der Monitoransicht (Klick auf ein Rufzeichen) und aus der Übersichts-Statistik. Umfang: Vorschlag
Punkte 1–10 (letzte Texte und Messwert-Verläufe später).

### Umsetzung

- **Zugänge:** Klick auf ein Rufzeichen im Monitor (Absender, Digipeater im Pfad; alle Stufen des
  APRS-Lense-Knopfs; Rufzeichen unterstreichen sich beim Darüberfahren); im blauen Kopfband
  **Station statistics** (bei Third-Party zusätzlich die innere Station); Rufzeichen der Pfad-Kette in
  der Lense; jedes Rufzeichen in der Übersichts-Statistik (statt direkt in den Monitor). Auf der
  Stationsseite sind Rufzeichen wieder anklickbar; **‹ Back** geht Schritt für Schritt zurück, zuletzt
  an dieselbe Stelle im Monitor bzw. in die Übersicht. **Show in monitor** filtert den Monitor.
- **Inhalt** (Zeitfenster Last hour / 24 h / All): Kopf mit Symbol, Rolle (mobil/fix, Digipeater,
  iGate, Wetter, Objekte, Telemetrie), Gerät, Land, Entfernung + Richtung, zuerst/zuletzt gehört,
  Links aprs.fi / Karte / Track; Kacheln (Frames, Kanalanteil und Sendezeit, für andere weitergegeben,
  Internet → Funk, von deinem Funkgerät empfangen); Frames pro Zeiteinheit; Art der Frames;
  Bakenverhalten (typischer/kürzester/längster Abstand, fester Takt?, Verteilung); Wie sie zu dir kommt
  (direkt/über Digis, Wege, Hops, verlangter Pfad, wer sie dir gebracht hat); Aktivität Wochentag ×
  Stunde (alles Gespeicherte); Bewegung (Strecke, Höchstgeschwindigkeit, Höhe); als Digipeater bzw.
  iGate: für welche Stationen; Sünden dieser Station.
- Datensätze speichern dafür zusätzlich Symbol, Geschwindigkeit und Höhe (`tinybox/aprs.py` liefert
  `speed`, `alt`). API `GET /api/aprs/station?call=..&win=..`.
- Tests `test_station_page`. Client-Version 2026.10.17.5.


## CR66 – UI-Frame aus dem Monitor senden (✅ 17.10.2026)

### Erfassung (OE3GAS, 17.10.2026)

Der Client soll einen UI-Frame senden können, am besten in der Monitoransicht vor dem Filterfeld –
für den Test von VARA FM als KISS-TNC über kisshub („Wrong KISS frame“ bei SABM/SABME).

### Umsetzung

- Knopf **Send UI** in der Monitorleiste vor dem Filterfeld klappt eine Zeile auf: **To** (Standard
  `CQ`), **Via** (optional, Digipeater mit Komma oder Leerzeichen, höchstens 8), **Text** (bis
  1024 Byte, Bytezähler), **Send** bzw. Enter. Die Antwort steht daneben („sent 23:45:12 (17 B)“
  oder der Grund, z. B. „kisshub not reachable“, „not a callsign“). Der Text bleibt markiert stehen:
  Enter sendet denselben Frame noch einmal. To/Via merkt sich der Browser.
- Geht über KISS (eigener AX.25-Frame, PID F0, Command-Bit) und über AGW (Direwolf `M` bzw. `V`
  mit Pfad). Über den Telnet-Testport nicht.
- Der eigene Frame erscheint im Monitor wie gehört.
- API `POST /api/ui {"dest", "via", "text"}`, `ClientCore.send_ui()`, Prüfung in `ui_request()`.
- Tests `tests/test_tbclient_ui.py`. Client-Version 2026.10.17.8.

## CR67 – VARA-Monitoring im kisshub: Werte aus 8300, 8100 und passive AX.25-Auswertung (kisshub-Teil umgesetzt 18.10.2026, Anzeige in TinyBox/Client offen)

### Erfassung (OE3GAS, 18.10.2026)

Mit VARA FM als KISS-TNC (Profil `vara-fm`, Tunnel, Konzept 8c) möglichst viele Werte über Kanal,
Gegensignal und Verbindungszustand gewinnen. kisshub wertet aus und stellt die Werte TinyBox und
Client zur Verfügung. Grundlage: statische Analyse VARA HF 4.9.0 / VARA FM 4.3.9 (Projekt „VARA
verstehen“), VARA-Changelog, Pat-Vara, Mercury (VARA-kompatible TNC-Schnittstelle).

**Reihenfolge:** zuerst der Funktest des Tunnels (vollwertiges AX.25 über VARA FM möglich?). CR67
wird erst danach umgesetzt; ohne funktionierenden Tunnel bleibt nur Teil B für UI-Verkehr.

**Regeln:** nur lesend beobachten. Am Befehlsport zunächst **kein Kommando** senden. Keine
Auswertung oder Nachbildung von Lizenz- und Krypto-Meldungen (`REGISTERED`, `LINK (UN)REGISTERED`,
`ENCRYPTION …`) – nur als Text protokollieren. Alle VARA-Ports nur über Loopback.

### Quelle A – VARA-Befehlsport 8300 (neuer Teil `VaraMonitor` im kisshub)

kisshub verbindet sich zusätzlich mit 8300, liest zeilenweise (CR-getrennt, ASCII), sendet nichts.
Unbekannte Zeilen werden roh mit Zeitstempel geloggt. Wiederverbindung wie beim TNC.

| Meldung | Format (Mercury, in VARA noch zu bestätigen) | Auswertung |
|---|---|---|
| `SN` | `SN 8.2` (dB, 1 Nachkomma) | laut HF-Changelog v4.7.2 auch je **empfangenem KISS-Frame**: dem Frame zuordnen, der innerhalb eines kurzen Fensters (Startwert 1 s, einstellbar) an 8100 ankommt → **SN je Gegenstation**. Ohne passenden Frame: als „SN ohne Frame“ zählen |
| `PTT ON` / `PTT OFF` | so | **Sendedauer je Burst**; mit der Größe des zuletzt an 8100 übergebenen Frames → gemessene Rate und Aufwand je Burst (ersetzt die Schätzung `air_baud`/`txdelay`, Grundlage für T1). **Wartezeit bis TX**: Übergabe an 8100 → `PTT ON`. PTT länger als ein Grenzwert (z. B. 60 s) → **Alarm „PTT hängt“** |
| `BUSY ON` / `BUSY OFF` | so | Kanal belegt: Anteil je Minute/Stunde, Zahl der Belegungen, längste Belegung |
| `BITRATE` | `BITRATE (2) 600 BPS` (Speed Level, bps) | falls im KISS-Betrieb gesendet: Speed Level je Burst; Parser tolerant |
| `BUFFER` | `BUFFER 0` | nur ARQ; mitloggen |
| `IAMALIVE` | so | Lebenszeichen; bleibt es länger als 2 Intervalle aus → Warnung |
| `MISSING SOUNDCARD` | so | **Alarm** (laut EA5HVK hilft nur ein PC-Neustart) |
| `VERSION …` | so | im Status anzeigen |
| `PENDING`, `CONNECTED …`, `DISCONNECTED`, `CANCELPENDING` | so | sollten im KISS-Betrieb nicht kommen: kommt doch eins, Warnung (jemand nutzt ARQ auf dem Gerät) |
| alles andere | – | roh loggen, Zähler „unbekannt“ |

SN wird **unverändert** gespeichert und angezeigt. Bezug bei VARA HF laut Analyse 2500 Hz; für VARA FM
(Narrow 3 kHz / Wide 6 kHz NF) unbekannt – vergleichen nur innerhalb derselben Betriebsart.

### Quelle B – KISS-Port 8100 und Tunnel (misst kisshub selbst)

| Wert | Verarbeitung |
|---|---|
| Frames gesendet/empfangen | je Minute, getrennt Typ 0 (UI) und Typ 2 (Tunnel); Zeitreihe 60 min |
| Framegrößen | Verteilung (Klassen bis 64, 128, 256, 512, 1024, darüber) gesendet/empfangen; mit der PTT-Dauer die **Schwellen für Speed Level 1/2/4** ermitteln |
| `foreign`, `echoes`, unlesbare Frames | gibt es seit dem Tunnel; zusätzlich je Minute |
| Gehörte Stationen | Rufzeichen, Frames, letzter/mittlerer/min./max. SN (aus A), zuletzt gehört, über Tunnel ja/nein |
| TNC/Hub | bestehend (CR41): Zustand, Portverluste, Wiederanläufe, Wartezeit in der Hub-Queue |

### Quelle C – passive AX.25-Auswertung im kisshub (je Stationspaar)

Der Hub sieht alle Frames einer Verbindung in beide Richtungen (eigene Clients und Gegenstation).
Je Paar (Rufzeichen A ↔ B, mit SSID) wird geführt:

| Wert | Wie |
|---|---|
| Verbindungsstatus | SABM(E) gesehen → „im Aufbau“, UA → „verbunden“ (mit Version 2.0/2.2), DISC/DM → „getrennt“; Dauer der Verbindung |
| I-Frames und Nutzbytes | je Richtung |
| **Wiederholungen** | I-Frame mit gleichem N(S) und gleichem Inhalt erneut gesendet → Wiederholungsquote je Richtung |
| REJ / SREJ / RNR | je Richtung zählen |
| **Antwortzeit** | eigener I-/Poll-Frame bis zur ersten Quittung (RR/REJ/I mit passendem N(R)) → gemessene Laufzeit über VARA (Mittel, Min., Max.) |
| Abbrüche | DM auf SABM, Verbindung ohne DISC verschwunden (Zeitüberschreitung) |
| Durchsatz | Nutzbytes je Minute während der Verbindung |

Damit lässt sich „AX.25 über PK-232“ und „AX.25 über VARA FM“ mit denselben Kennzahlen
vergleichen, unabhängig davon, ob TinyBox oder Client die Verbindung führen.

### Quelle D – VARA-Logdatei (optional, zweiter Schritt)

kisshub liest `VARAFM.log` mit (Pfad in `kisshub.conf`, nur lesen, ab Dateiende). Ausgewertet:
„Soundcard … missing in action“ (Alarm), „Wrong/Invalid KISS frame“, „Exceeded KISS buffer“,
„KISS size too long“ (zählen – kommen nach bisheriger Erfahrung nicht über TCP), „VARA is not
connected to any App via TCP Port 8300“. Inhalt im KISS-Betrieb erst nach dem Mitschnitt festlegen.

### Weitergabe an TinyBox und Client

- **`GET http://127.0.0.1:8102/status`** (bestehend, nur Loopback) bekommt die Blöcke
  `vara` (Verbindung zu 8300, alive, Version, busy + Anteil, letzte/mittlere Sendedauer, Wartezeit
  bis TX, gemessene Rate und Burst-Aufwand, Alarme), `stations` (Quelle B mit SN) und
  `links` (Quelle C je Paar).
- **Neu `GET http://127.0.0.1:8102/events`**: Datenstrom, eine JSON-Zeile je Ereignis
  (`sn` mit Rufzeichen, `ptt`, `busy`, `alarm`, `link`), damit Monitor und Qualitätsanzeige live
  sind statt alle 30 s abzufragen.
- **TinyBox**: Web-GUI zeigt Kanal (busy-Anteil), SN je Station und Verbindungswerte; die
  Qualitätsbalken der Verbindungen nutzen SN und Wiederholungsquote. Alarme in der Sysop-Konsole.
- **Client**: im Monitor das SN neben jedem empfangenen Frame (falls zugeordnet), in der
  Stationsseite der SN-Verlauf; Kopfzeile mit VARA-Zustand (alive, busy, Alarm).
- Speicherung: Zeitreihen im Speicher (60 min Minutenwerte, 24 h Stundenwerte); Stationswerte wie
  die APRS-Statistik bis 7 Tage in einer Datei.

### Erster Schritt (nach dem Tunnel-Test): Mitschnitt

`tools/vara_capture.py` (kommentiert): 30 min Betrieb, verbindet sich mit 8300 und sendet nichts,
schreibt jede Zeile mit Zeitstempel (ms) in eine Datei; parallel kisshub-`/status` und das
kisshub-Log mit `LOG TRACE`. Danach Formate festlegen, Parser schreiben, Teil A–C umsetzen.

### Offene Fragen (im Mitschnitt klären)

1. Liefert VARA **FM** 4.3.9 im KISS-Betrieb `SN` je empfangenem Frame (wie HF ab 4.7.2)? Auch für
   Typ-2-Rahmen? Kommt `SN` vor oder nach dem Frame an 8100?
2. Stört eine Verbindung am Port 8300 den KISS-Betrieb? (Bekannter Fehler 2023: PTT blieb mit
   KISS plus Befehlsport hängen – beim ersten Test jemand am Funkgerät.) Schaltet sie KISS ab
   (HF-Changelog 4.6.4: „KISS interface continue disabled with Winlink apps“)? Wie viele Clients
   nimmt 8300?
3. Kommen `PTT`, `BUSY`, `BITRATE` auch für KISS-Verkehr?
4. Exakte Formate von `SN`, `BITRATE` in VARA selbst.
5. Was schreibt `VARAFM.log` im KISS-Betrieb?

### Umsetzung im kisshub (18.10.2026, kisshub 2026.10.18.2)

Tunnel-Funktest vorher erfolgreich: vollwertiges AX.25 (v2.2) zwischen TinyBox und Client über
VARA FM, 1200 Bd. Auffällig: lange Pausen zwischen den Sendungen der beiden Stationen.

- **`kisshub/linkstats.py` (Teil B + C, für jeden TNC – PK-232 genauso wie VARA):** je
  Stationspaar Aufbau (Versuche, Dauer, v2.0/2.2, abgelehnt), je Richtung I-Frames, neue Bytes,
  Wiederholungen (gleiche N(S) mit gleichem Inhalt vor der Quittung) mit Quote, RR/RNR/REJ/SREJ,
  Polls (S-Kommando mit P=1 ≈ abgelaufener T1), **Quittungszeit** (I-Frame bis zur Quittung, nur
  einmal gesendete – Karn), **Antwortabstand** (Frame von X nach dem letzten Frame von Y – die
  „langen Pausen“), Goodput, Effizienz (neue Nutzbytes / alle Bytes), geschätzte Sendezeit;
  gehörte Stationen, Framegrößen-Klassen, Minutenzähler, unlesbare Frames. Zeitpunkte: tx = an den
  TNC übergeben, rx = vom TNC geliefert – für PK-232 und VARA gleich gemessen, also vergleichbar.
- **`kisshub/varamon.py` (Teil A):** `[vara] monitor = yes` – zweite Verbindung zum Befehlsport,
  **sendet nichts**. Wertet `PTT ON/OFF` (Burst-Dauer, Wartezeit von der Übergabe bis PTT, daraus
  Ausgleichsgerade Aufwand je Burst + Rate), `BUSY ON/OFF` (Anteil 10/60 min), `SN` (dem Frame
  zugeordnet, der im Fenster `sn_window_ms` ankommt → SN je Station und je Link-Richtung),
  `BITRATE`, `IAMALIVE`, `VERSION`, `MISSING SOUNDCARD` aus; Alarme: PTT länger als 60 s, 180 s
  nichts von VARA, Soundkarte weg; ARQ-Meldungen werden gewarnt, Lizenzzeilen nur geloggt,
  unbekannte Zeilen roh geloggt.
- **Links-Datei** `[log] links_file = kisshub-links.jsonl`: je beendeter Verbindung eine
  JSON-Zeile mit TNC-Profil, Tunnel, air_baud, txdelay, VARA-Messwerten und allen Kennzahlen –
  gleiche Sitzung über PK-232 und über VARA fahren und vergleichen. Beim Ende einer Verbindung
  zusätzlich eine Zusammenfassung im kisshub-Log.
- **Status** `GET /status`: neue Blöcke `quality` (laufende + letzte 5 Verbindungen, Stationen,
  Größen, letzte 10 min) und `vara`.
- **Konsole:** `L`/`LINKS`, `V`/`VARA`, `STATIONS`.
- Tests `tests/test_kisshub_quality.py`.

Offen: Anzeige in TinyBox-Web-GUI und Client, `/events`-Datenstrom, VARA-Logdatei (Teil D).


## CR68 – Bug: Mail bleibt nach dem Senden über eine langsame Strecke im Postausgang (✅ 18.10.2026)

### Erfassung (OE3GAS, 18.10.2026)

VARA-Lauf 5: Antwort „Re: 2. Test Bulletin mit 3000 Zeichen“ (persönlich an OE3XYZ) wurde vom Client
ausgesendet, blieb aber im Outbox stehen („1 change(s) waiting“).

### Ursache

Die kisshub-Auswertung zeigt: Alle 27 I-Frames (4013 Byte) kamen bei der TinyBox an und wurden
quittiert, die TinyBox hat geantwortet. Die Übertragung dauerte über VARA FM (~13 B/s) aber mehrere
Minuten. Der Sync wartet nach `//SEND` höchstens `IDLE_SEC` = 120 s auf eine Antwort – die TinyBox
kann `//SENT` aber erst nach der letzten Zeile schicken. Der Sync gab nach 120 s mit „no answer from
the TinyBox“ auf, das `//SENT` kam danach und wurde nicht mehr zugeordnet; die Mail blieb im
Postausgang (beim nächsten Sync wäre sie erneut gesendet worden – die TinyBox erkennt sie über
`mid=` und antwortet mit den alten Nummern, doppelt wird sie also nicht abgelegt).

### Umsetzung

`tbclient/sync.py` `_next()`: Läuft die Wartezeit ab, fragt der Sync die eigene Verbindung, ob noch
Frames unterwegs sind (`outstanding()`: noch nicht gesendet oder nicht quittiert – KISS aus dem
eigenen AX.25-Automaten, AGW per Direwolf `Y`). Solange das so ist, wartet er weiter (höchstens
`SEND_WAIT_MAX_SEC` = 30 min); „keine Antwort“ gilt erst, wenn nichts Eigenes mehr unterwegs ist.
Tests `tests/test_sync_slowlink.py`. Client-Version 2026.10.18.

## CR69 – Erst fragen, dann senden: bereits vorhandene Mail nicht nochmals übertragen (✅ 18.10.2026)

### Erfassung (OE3GAS, 18.10.2026)

Zu CR68: Wird eine Mail nach verlorener `//SENT`-Antwort nochmals gesendet, erkennt die TinyBox sie
zwar an `mid=` – aber erst, nachdem der ganze Text nochmals übertragen wurde. Über VARA sind das
Minuten. Die TinyBox soll vorher sagen „die hab ich schon“.

### Umsetzung

- **Neuer Befehl** (Cap `HAVE`) `//HAVE <mid> <to>[,<to>...][@<at>]` → `//HAVE <mid> <id> ...`
  (schon gespeichert, eine Nummer je Empfänger) oder `//HAVE <mid> -` (senden). Es werden nur
  eigene Mails gefunden; Empfänger werden wie bei `//SEND` normiert (`tinybox/clientsync.py`).
- **Client** (`tbclient/sync.py`): Vor dem ersten Senden merkt er sich `out_try.<mid>`. Kommt
  `//SENT`, wird die Marke gelöscht. Ist die Marke beim nächsten Sync noch da (Antwort ging verloren,
  Sync abgebrochen, Client beendet), fragt er zuerst `//HAVE`: Ist die Mail schon da, wandert sie
  sofort in „Sent“, **ohne** dass der Text nochmals gesendet wird. Beim ersten Versuch wird nicht
  gefragt – das kostet keinen zusätzlichen Durchgang.
- Ältere TinyBox ohne Cap `HAVE`: wie bisher (senden, Duplikat über `mid=`).
- Tests in `tests/test_mailsync.py`. Client-Version 2026.10.18.2.

## CR70 – Konfiguration ohne Doppelungen: ein Besitzer je Wert ✅

### Erfassung (OE3GAS, 18.10.2026)

Mehrere conf-Dateien enthalten Einträge, die andere Komponenten betreffen (z. B. `air_baud` in
kisshub.conf und tinybox.conf). Die confs sollen schlanker und redundanzfrei werden. Der
Zielordner von Direwolf bzw. die `direwolf.conf` wird unter `[agw]` erfasst. Ein Handbuch
`MANUAL.md` mit den exemplarischen confs anlegen.

### Konzept

`PLANUNG.md` 17.2, Zielaufbau aller confs und Tabelle alt → neu in `MANUAL.md` Abschnitt 2.
Umsetzung in vier Schritten; alte Schlüssel bleiben lesbar.

### Umsetzung (18.10.2026) ✅

- `prcore/direwolfconf.py`: liest `direwolf.conf` (Ordner oder Datei; AGWPORT, KISSPORT, MODEM,
  TXDELAY, PERSIST, SLOTTIME je CHANNEL/ADEVICE, PACLEN, MAXFRAME, EMAXFRAME, FRACK, RETRY).
- kisshub 2026.10.18.7: Profile tragen air_baud/txdelay/max_lead/Port und eine AX.25-Empfehlung
  (VARA FM gemessen: 350 / 2700 / 12000, 256 B, Fenster 4, T1 18–90 s, T2 0,3 s); neues Profil
  `direwolf`; `[kiss]`/`[ax25]` nur Überschreibung; Status = Port + 1; `/status` mit Block
  `radio` inkl. Herkunft; Startzeilen nennen die Quelle jedes Werts.
- TinyBox: `[agw] direwolf_conf / host / port / channel / quality_*` (alt `[direwolf]`),
  paclen/Fenster aus direwolf.conf, `[kiss] port`; KISS-Werte aus dem kisshub-Status für neue
  Verbindungen, Werte aus tinybox.conf gewinnen; Startlog mit Quellen und `config hint`.
- Client 2026.10.18.3: `[radio] interface` (alt `[tinybox] link`), `[agw]`, `[kiss] port`,
  Werte vom kisshub; Bildschätzung aus der Funkrate, solange nichts gemessen ist.
- brocastd: `[radio]/[agw]/[kiss]`, baud/TXDELAY aus direwolf.conf bzw. kisshub.
- dxfeed: Inbox aus `tinybox.conf`; fwdsim: Mailbox-Call, haddress, Telnet-Port, DB aus
  `tinybox.conf`, AGW-Werte aus direwolf.conf.
- kisshub 2026.10.18.8: **eine kisshub.conf für alle TNCs** – Startschalter `-p <profil>`,
  Abschnitte `[<abschnitt>.<profil>]` nur für ein Profil, `{profile}` in Log-Dateinamen,
  `[vara] monitor` bei anderen Profilen nur Hinweis; Hilfe mit `-h` / `-?`.
- Alte Schlüssel gelten als Überschreibung, mit Hinweis beim Start. Tests:
  `tests/test_direwolfconf.py`, `RadioValuesTests`, `KissConfigTests`, Client-/brocastd-/
  dxfeed-/fwdsim-Konfigtests.

## CR71 – Connect über Digipeater (✅ 18.10.2026)

### Erfassung (OE3GAS, 17./18.10.2026)

Der Client soll Stationen über einen oder mehrere Digipeater connecten können (Test über den
TM-D710 OE3XTC-5). Frage: eigenes Via-Feld oder alles in das bestehende Eingabefeld?

### Entscheidung

Ein Feld mit der klassischen TNC-Syntax (`C OE3XYZ-1 V OE3XTC-5,OE3ABC`): gewohnt seit TNC2/BPQ,
der Pfad gehört zum Ziel (Kopieren, Liste der letzten Ziele), kein zweites Feld zum Leeren.
Die Klarheit eines eigenen Felds liefert eine Vorschau unter dem Eingabefeld.

### Umsetzung

- `tbclient/target.py`: `parse()` / `label()` – Rufzeichen, dann `V` oder `VIA`, Digis mit
  Komma und/oder Leerzeichen, Groß/klein egal, höchstens 8 Digis (AX.25). Abgewiesen: fehlendes
  `V`, Digi = Ziel oder eigenes Rufzeichen, Digi doppelt, ungültiges Rufzeichen.
- Kanal (`channels.py`): `via` neben `target`; Statuszeile „connecting OE3XYZ-1 via …“;
  Snapshot mit `via` und `label`. Ankommende Verbindungen haben keinen eigenen Pfad.
- AGW (Direwolf): mit Pfad Frame `'v'` (Anzahl + je 10 Byte Rufzeichen), sonst `'C'` wie bisher.
- KISS: `KissPort.open_link(remote, via)` – der eigene Layer 2 setzt den Pfad ins Adressfeld;
  `[ax25] v20_digis` greift dort wie bei der TinyBox.
- Web-GUI: Feld wächst mit dem Pfad (bis ~46 Zeichen), darunter beim Tippen „to OE3XYZ-1 · via
  OE3XTC-5 → OE3ABC“ bzw. die Fehlermeldung (rot), ab 3 Digis Hinweis „many hops, slow“.
  Titelleiste verbunden: Rufzeichen, daneben klein „via …“. Tooltip: Via ist nur Digipeating,
  ein Node wird selbst connectet und dort mit C weiterverbunden.
- Liste der letzten Ziele speichert den ganzen Pfad (`OE3XYZ-1 via OE3XTC-5`); leeres Feld
  connectet das letzte Ziel samt Pfad. Telnet-Testport: Pfad wird ignoriert.
- Verbindungslog: Spalte Station bleibt das Rufzeichen (ADIF), ohne Pfad.
- Tests: `TargetParseTests`, `ConnectViaAgwTests` (AGW `'v'`), `ConnectViaTests` (Client →
  Digipeater → TinyBox über KISS, beide Richtungen durch den Digi). Client 2026.10.18.7.
- **Funktest und Abnahme** (OE3GAS, 18.10.2026): getestet und abgenommen ✅

## CR72 – Wetterprognose auf Anfrage: User fordert die Prognose für seinen Locator an (offen, erfasst 24.10.2026)

### Erfassung (OE3GAS, 24.10.2026)

Ziel – genau das: **Ein User fordert den Forecast für seinen Locator an.** Er bekommt die
Prognose für seinen Standort zurück, nicht nur für die fest eingestellten Locators der
Aufgabenplanung (Weg 1, PLANUNG Abschnitt 20).

### Vorschlag (zur Entscheidung)

- **Befehl in der TinyBox**, z. B. `WX JN88BN` (Name noch offen; `WX` ist auch die Rubrik).
  Ohne Locator: der Locator aus dem User-Profil (CR73 – gibt es seit 24.10.2026; für die
  Prognose muss er 6-stellig sein). Prüfung wie in `geosphere_prognose.py` (6/8-stellig, im Modellgebiet).
- **Antwort an den Fragenden**, nicht als Bulletin: im Terminal sofort der Text aus
  `geosphere_prognose.bericht()` (≤ 60 Zeichen breit); im Client als persönliche Nachricht
  bzw. eigene Ansicht mit der Prognosegrafik (gleiche Tabelle wie die brocast-Seite).
- **Abruf in der TinyBox** über dieselben Funktionen (Locator → Punkt, API, Schritte) –
  dafür die Logik aus dem Skript in ein Modul ziehen, das TinyBox importiert. Abruf
  asynchron/mit Timeout, damit eine langsame API die Verbindung nicht blockiert.
- **Cache je Locator und Modelllauf:** das Modell rechnet nur alle 3 h neu – gleiche
  Anfragen innerhalb dieser Zeit ohne neuen API-Abruf. Grenze je User/Stunde gegen Missbrauch.
- **Über Funk:** nur die Antwort an den Fragenden; keine brocast-Seite je Anfrage (sonst
  füllt jede Einzelanfrage das Karussell). Offen: Locators, die oft angefragt werden,
  automatisch in Weg 1 aufnehmen?
- Offen: Nur für angemeldete User oder für jeden Connect? Ausgabe-Schritte (3 h / 48 h wie
  Weg 1, im Terminal evtl. 24 h)?

## CR73 – Benutzerprofil: Name, Locator, Home-BBS in TinyBox und Client (✅ umgesetzt 24.10.2026, Funktest offen)

### Erfassung (OE3GAS, 19./24.10.2026)

Bei der Recherche zu den Prompts anderer PR-BBS (FBB, BPQ, BayCom/OpenBCM, JNOS) fiel auf:
Die üblichen Systeme fragen neue Benutzer nach **Name, QTH/Locator und Home-BBS**. Das soll
die TinyBox auch können – und die Daten sind im Client genauso sinnvoll. Fragen: Wo werden
sie gespeichert, und wie wird ein User, der mit dem Client kommt, zur Eingabe eingeladen?

### Entscheidung (OE3GAS, 24.10.2026)

- **Verbindlich in der TinyBox**, eine Kopie im Client. Eingegeben wird im Client (Formular)
  oder im Terminal (Fragen nach dem Login, Befehle). Die TinyBox braucht die Daten selbst
  (Home-BBS fürs Forwarding, Anzeige im Chat, Locator für CR72), auch Terminal-User haben ein
  Profil, und ein neuer PC/Client findet das Profil wieder.
- **Home-BBS gleich mitnehmen.**
- **Sichtbar für alle**: im Chat, im Terminal (`I call`), in anderen Clients.
- **Die neuere Änderung gilt**, egal ob aus Client oder Terminal.

### Umsetzung

- **Ein Profil je Rufzeichen ohne SSID** (OE3GAS-7 = OE3GAS). Felder: Name (bis 12 Buchstaben,
  Leerzeichen, `-`, `.`, `'`; Umlaute erlaubt), Locator (4 oder 6 Stellen – der User wählt die
  Genauigkeit, alle sehen genau das), Home-BBS (Rufzeichen oder hierarchische Adresse, SSID
  fällt weg). Gemeinsame Prüfung, Prüfsumme und Zeilenformat: `prcore/profile.py`.
- **TinyBox**: Tabelle `profiles` (Schema 9) mit Zeit der letzten Änderung und Zeitpunkt der
  letzten Abfrage; Logik in `tinybox/profiles.py`.
  - **Fragen nach dem Login** (nur Terminal, nicht Sysop-Konsole): nach dem Willkommenstext
    `Please introduce yourself …`, dann nur die fehlenden Felder: `Your first name:`,
    `Your locator (e.g. JN88EP):`, `Your home BBS (e.g. OE3XSR):`. Enter überspringt eine
    Frage, `/AB` alle; eine falsche Eingabe wird erklärt und nochmals gefragt. Ein
    unvollständiges Profil wird höchstens alle 30 Tage wieder abgefragt. Abschaltbar mit
    `[mailbox] ask_profile = no`.
  - Kommt währenddessen `//CLIENT` (der Client meldet sich ca. 1 s nach dem Willkommen),
    enden die Fragen still – der Client hat sein eigenes Formular. Bei Verbindungsabbruch
    bleibt, was schon beantwortet war.
  - **Befehle**: `N name`, `NL locator`, `NH home-bbs` (`-` löscht, ohne Argument das eigene
    Profil), `I [call]` zeigt das Profil einer Station. Hilfe ergänzt; der Prompt bleibt
    gleich (kein Byte mehr je Prompt).
  - **Chat im Terminal**: `/W` und die Liste beim Betreten zeigen `OE3ABC (Hans, JN88)`.
  - **Sysop-Web-GUI**: Stationsliste (JLOG) mit Name, Locator, Home-BBS.
- **Client-Protokoll TB1**, neue Fähigkeit `PROF`:
  - `//OK … prof=<crc>` (4 Hex-Stellen) bzw. `prof=-`: der Client vergleicht mit seinem
    Profil – **gleich = nichts über Funk** (ca. 10 Byte je Login).
  - `//PROF t=<unix> loc=… home=… name=…` speichert (Antwort `//PROF OK <crc>`,
    `//PROF ERR <feld>`; ist das Profil in der TinyBox neuer, kommt es als `//PROF = …` zurück).
  - `//PROF ?` → `//PROF = <crc> t=… loc=… home=… name=…` bzw. `//PROF -`.
  - `//WHOIS call,call…` (max. 10) → je Station `//WI <call> loc=… home=… name=…` bzw.
    `//WI <call> -`, dann `//WIEND`.
- **Client** (`tbclient/profiles.py`, Version 2026.10.24):
  - Profil in den Client-Settings (nicht in `tbclient.conf`); Vorschlag für den Locator ist
    `[station] locator`. Nach `//OK`: gleiche Prüfsumme → nichts; TinyBox ohne Profil und im
    Client eingegeben → senden; sonst `//PROF ?` und die neuere Fassung (Zeit `t`) gewinnt.
  - **Einladung**: Balken über dem Chat „Introduce yourself …“ mit *Fill in* / *Later*,
    solange Name oder Locator fehlen und der Client mit einer TinyBox mit `PROF` verbunden ist;
    *Later* = in einer Woche wieder. Formular „My profile“ (auch unter Settings > My profile).
    Lehnt die TinyBox ab, öffnet sich das Formular mit dem Hinweis.
  - **Andere Stationen**: für die Teilnehmer im Board (`//WHO`, Join) einmal `//WHOIS`
    (gesammelt, eine Zeile für alle), eine Woche im Client gemerkt. Teilnehmerliste:
    „Gerhard · JN88EP · 45 km NE“ (Entfernung vom eigenen Locator).
- Tests: `tests/test_profile.py` (Prüfung, Format, TinyBox-Fragen, Befehle, `/W`, TB1,
  Client-Abgleich in beide Richtungen, Einladung, `//WHOIS`).
- **Offen / nächste Schritte**: Funktest PC1 ↔ PC2; Home-BBS für die Zustellung persönlicher
  Post an andere Mailboxen nutzen (White Pages, mit dem Forwarding); CR72 kann den Locator
  aus dem Profil nehmen (braucht 6 Stellen).

## CR74 – Heard: Rauschen mit gültiger Prüfsumme als „Rufzeichen“ (✅ 27.10.2026)

- **Beobachtung**: In „Heard on the channel“ standen Einträge wie `^?kDa?-8`, `??&/K?-8`
  oder `?%j?K-8`, in den kisshub-Verbindungsdaten eine Verbindung mit `OE3cAS-1`.
- **Ursache**: kisshub mit dem TNC des TM-D710 (9600 Bd, Datenband). Bei offener
  Rauschsperre wertet der TNC laufend Rauschen aus; ab und zu stimmt die 16-Bit-Prüfsumme
  zufällig. Weder kisshub noch Client prüften die Adressen – der Client nahm jede
  Quelladresse in die Heard-Liste.
- **Umsetzung**:
  - `prcore/ax25/frame.py`: `addresses_valid()` – Adressfeld vollständig, Rufzeichen nur
    A–Z und 0–9 (1–6 Zeichen), SSID 0–15.
  - kisshub 2026.10.27: Frames vom TNC mit ungültigem Adressfeld werden verworfen und gezählt
    (`invalid` in der Statuszeile und unter `queue` der Statusabfrage, INFO-Logzeile mit den
    ersten 32 Bytes hex). TinyBox-Kanalkarte zeigt „Dropped / invalid“.
  - Client 2026.10.27: `radio.decode()` liefert für solche Frames `None` (auch über
    Direwolf/AGW).
- Tests: `tests/test_kisshub.py` (`test_garbage_address_dropped`), `tests/test_ax25_v22.py`
  (`AddressesValidTests`).
- **Hinweis**: Ein Bitfehler, der zufällig ein gültiges Rufzeichen ergibt, kommt durch –
  dagegen hilft nur die Rauschsperre des Datenbands etwas zuzudrehen.

## CR75 – Eingehender Connect: gleich ins Terminal (✅ 07.11.2026)

### Erfassung (OE3GAS, 07.11.2026)

Wenn eine Station mit dem Client connected, soll gleich in den Terminal-Mode umgeschaltet
werden – außer es handelt sich um eine TinyBox.

### Umsetzung (Client 2026.11.07)

- Bisher: Der eingehende Connect bekam einen freien Kanal als Terminal (CR46), die GUI blieb
  aber auf dem gerade gezeigten Kanal – nur der Chip blinkte.
- Jetzt: Geht der eingehende Kanal online und ist die Gegenstation **keine bekannte TinyBox**,
  setzt `ClientCore.focus_channel()` `focus = {n, seq}` im Snapshot. Die Web-GUI springt bei
  jedem neuen `seq` auf diesen Kanal und zeigt sein Terminal (auch aus Mailbox/Chat heraus).
  Beim Laden der Seite wird ein alter `seq` nur gemerkt, nicht angesprungen.
- „Bekannte TinyBox“ = `known_tinybox()`: die eigene TinyBox aus `tbclient.conf` oder eine,
  die schon einmal als TinyBox erkannt wurde (Settings `tinyboxes`). Dann bleibt die Ansicht,
  der Chip blinkt wie bisher.
- Gilt für AGW, KISS und AXUDP.
- Test: `tests/test_tbclient.py` (`test_incoming_connect_over_agw`, um CR75 erweitert).
- **08.11.2026:** Die Ausnahme „bekannte TinyBox“ ist entfernt – eine TinyBox ruft nie selbst
  einen Client an (Entscheidung OE3GAS, CR76). Jeder eingehende Connect springt in seine Ansicht.

## CR76 – Kennung `//TB?` nach dem Connect: TinyBox, TBClient oder fremde Station (✅ 07.11.2026)

### Erfassung (OE3GAS, 07.11.2026)

Der Client soll gleich nach dem Connect eine Kennung schicken, auf die eine TinyBox reagiert,
eine andere BBS oder ein anderer Connect-Partner aber nicht. Eine TinyBox ruft nie von sich aus
einen Client an – ein SID-Austausch wie beim Forwarding ist daher nicht nötig. Zwei Clients
sollen sich ebenfalls erkennen (CR78).

### Umsetzung (Client 2026.11.07.2, TinyBox)

- Client: nach jedem **ausgehenden** Connect (Funk und AXUDP, nicht Telnet) eine Zeile
  `//TB? CLIENT v=<Version> caps=PROF,HEARD` (im Terminal als gesendete Zeile sichtbar).
- TinyBox (`clientproto.tb_probe()`): Antwort `//TB BOX v=<RELEASE> call=<Mailbox>`, sonst
  nichts – die Sitzung bleibt, wie sie ist. Kommt `//TB?` während der Profilfragen (CR73), wird
  die Frage danach noch einmal gestellt, statt sie zu beenden.
- Client auf `//TB BOX`: `//CLIENT`-Handshake, sofern kein anderer Kanal eine TinyBox im
  Client-Modus hat (**CR45 bleibt**); sonst bleibt der Kanal Terminal mit Hinweis. Auch eine
  späte Antwort (nach den 6 s Erkennungszeit, langsamer Weg) wird noch genommen.
- Client auf `//TB CLIENT …`: der Kanal ist Terminal mit Peer-Funktionen (CR78).
- Fremde Stationen: sehen die eine Zeile, antworten evtl. „unknown command“; der Kanal wird wie
  bisher nach 6 s Terminal. Ältere TinyBoxen ohne `//TB?` erkennt der Client weiter an
  „Welcome to TinyBox“.
- Tests: `tests/test_clientproto.py` (`test_tb_probe_*`), `tests/test_tbclient.py`
  (`test_foreign_bbs_terminal_and_states`, `test_incoming_connect_over_agw`).

## CR77 – Mehrere TinyBoxen gleichzeitig im Client-Modus (abgelehnt, 07.11.2026)

Vorschlag: Chat-Zustand je Kanal, damit mehrere TinyBoxen mit vollen Funktionen verbunden sein
können. **Entscheidung OE3GAS:** nein – die Grenze aus CR45 bleibt: eine TinyBox mit vollen
Funktionen, jede weitere als Terminal.

## CR78 – TBClient zu TBClient: Profile, Heard-Liste, Version (✅ Stufe 1, 07.11.2026)

### Erfassung (OE3GAS, 07.11.2026)

Wenn sich zwei Clients connecten, sollen sie sich erkennen und gemeinsame Funktionen
freischalten.

### Umsetzung Stufe 1 (Client 2026.11.07.2, `tbclient/peer.py`)

- Erkennung über CR76: Der Anrufer schickt `//TB? CLIENT v=… caps=…`, der Angerufene antwortet
  `//TB CLIENT v=… caps=PROF,HEARD`. Beide Kanäle bleiben Terminal; Steuerzeilen (`//…`) des
  Gegenübers erscheinen nicht als Text, sondern als `***`-Hinweise.
- **Profil:** Jede Seite schickt einmal `//PROF loc=.. home=.. name=..` (nur ein selbst
  eingetragenes Profil). Anzeige in der Terminal-Leiste: Name, Locator, Entfernung und Richtung
  aus den Locatoren, Home-BBS; das Profil kommt auch in den Profil-Speicher (wie `//WI`).
- **Heard-Liste:** Knopf „Heard there“ → `//HEARD?`, Antwort
  `//HEARD <call>=<min> …` (bis 10 Stationen, `//HEARD -` = niemand); im Terminal als Zeile.
- **Version:** Die Leiste zeigt „TBClient <Version>“, die Kopfzeile „connected · TBClient …“;
  ist der andere Client neuer, steht ein Hinweis im Terminal.
- API: `POST /api/peer/heard {"ch": n}`; Snapshot: `channels[].peer`.

### Fehler behoben (Client 2026.11.07.3)

- **Beobachtung** (OE3XHU ↔ OE3GAS-10): Kanal mit dem Tag „chat“, Chat-Ansicht mit „Join a
  board first“, keine Eingabe, obwohl die Kopfzeile „connected · TBClient …“ zeigte.
- **Ursache:** Der Kanal war vorher der Chat-Kanal einer TinyBox-Verbindung und blieb es nach
  deren Ende. Früher löste das die 6-s-Erkennung (`to_terminal()` → `detach()`); seit CR76/78
  bricht die Erkennung beim `//TB CLIENT` ab, und auch ein eingehender Connect hat nie gelöst.
- **Umsetzung:** `Channel._terminal()` – Terminal-Modus, Ansicht Terminal, und war der Kanal
  der Chat-Kanal, wird er gelöst. Gilt für Peer (beide Seiten), eingehenden Connect und die
  zweite TinyBox. Test: `test_incoming_connect_over_agw`.

### TinyBox in jedem Kanal (Client 2026.11.07.4)

- **Beobachtung (OE3GAS):** Ein Connect zur TinyBox klappte nur auf Kanal 1.
- **Ursache:** „Connect“ in der Chat-Ansicht („Not connected to OE3GAS-1“) und in den
  Einstellungen schickte keinen Zielruf – der Client nahm die letzte Station *dieses Kanals*
  bzw. die zuletzt verbundene (z. B. den TBClient OE3GAS-10). Nur Kanal 1 hatte noch die
  TinyBox als letzte Station.
- **Umsetzung:** `connectTinybox()` in `app.js`: Ziel ist immer die angezeigte TinyBox; im
  gezeigten Kanal, wenn er frei ist, sonst im ersten freien.
- Dazu: `//TB BOX` kommt jetzt auf einer eigenen Zeile (TinyBox); steht es bei einer älteren
  TinyBox direkt hinter dem Prompt, trennt der Client es ab (`test_tb_box_behind_the_prompt`).

### Stufe 2: eigene Ansicht „TBClient“ (Client 2026.11.07.5)

- **Wunsch (OE3GAS):** Nach dem Connect zu einem TBClient nicht das Terminal, sondern eine
  eigene Ansicht, an der man sieht, dass man mit einem TBClient verbunden ist.
- **Umsetzung (`app.js`, Ansicht `peer`):** Sobald der Kanal einen Peer hat, schaltet die GUI
  von selbst um (beide Seiten, beim Angerufenen mit CR75). Oben eine Karte: Rufzeichen (mit
  Digi-Pfad), Name, Locator, Entfernung/Richtung, Home-BBS, TBClient-Version, seit wann
  verbunden, zuletzt „Hears: …“. Darunter die Zeilen als Sprechblasen – die eigenen rechts, die
  des anderen links, mit Uhrzeit; `***`-Hinweise klein dazwischen, Protokollzeilen (`//TB?` …)
  ausgeblendet. Eingabe „Message to <call>“. Knopf „Terminal“ ↔ „TBClient view“ schaltet auf
  die rohe Terminal-Ansicht und zurück; „Heard there“ wie bisher.
- Die Uhrzeit der Blasen ist die, zu der die Zeile in der GUI erschienen ist (nach Neuladen der
  Seite die Zeit des Neuladens).

### Stufe 3: Ansicht schmäler, Linkqualität (Client 2026.11.07.6)

- **Wunsch (OE3GAS, 07.11.2026):** Chat-Feld schmäler und zentriert, keine Hinweise wie
  „online“/„disconnected“, Linkqualität anzeigen. Keine Trennlinie (die Uhrzeit steht in den
  Blasen).
- Karte, Blasen und Eingabe in einer Spalte von höchstens 760 px, mittig; am Handy volle Breite.
  `***`-Zeilen erscheinen nur noch in der rohen Terminal-Ansicht.
- **Linkqualität:** keine Zeilen über Funk. Jede Seite liest die Zähler ihrer eigenen Verbindung
  alle 30 s (`PEER_Q_SEC`): über AGW mit `Q` beim TinyBox-Fork von Direwolf
  (oe3gas/direwolf-tinybox, `TINYBOX.md`), über KISS/AXUDP aus dem eigenen AX.25
  (`Ax25Link.counters()`, dieselben Namen). Die Auswertung (Fenster 50 Frames / 30 min, Balken
  nach Verlust) ist jetzt `prcore/linkq.py` – TinyBox und Client rechnen gleich
  (`tinybox/linkq.py` importiert nur noch). Aus den eigenen Zählern kommen beide Richtungen:
  → `i_retry / (i_new + i_retry)`, ← `(rej_tx + retry_rx) / i_rx`.
- Karte: „→ Balken OE3GAS-10 ← Balken“, Tippen zeigt Frames, Wiederholungen, REJ, T1, SRT und den
  Netto-Durchsatz (`bytes_new / tx_busy_ms`). Unter 20 Frames je Richtung graue Balken. Direwolf
  ohne Fork: „no link data (Direwolf without the TinyBox fork)“; AXUDP: kein Funkweg.

### Stufe 4: Chat-Verlauf (Client 2026.11.07.6, `tbclient/peerchat.py`)

- **Wunsch (OE3GAS):** Verlauf behalten; beide müssen dasselbe sehen – Hash austauschen, Löschen
  per Knopf, der Partner löscht mit; passt es nicht zusammen, löschen beide.
- **Speicher:** `data/tbclient/peerchat.db` (SQLite, nicht im Repo), je Gegenstation (Rufzeichen
  mit SSID) die letzten **100** Zeilen je Richtung.
- **Zwei Ströme mit Hash-Kette:** gesendet und empfangen getrennt (AX.25 hält die Reihenfolge je
  Richtung; gekreuzte Zeilen machen so keinen Unterschied). `h(n) = sha1(h(n-1) + LF + Text)[:8]`.
  Dazu eine **Generation** (Zufall, neu bei jedem Löschen).
- **Beim Connect** (beide kennen `HIST`): `//HIST g=<gen> m=<n>:<h> y=<n>:<h>`. Jede Seite prüft
  ihren gesendeten Strom gegen das, was die andere empfangen hat:
  - gleich → nichts;
  - der anderen fehlt nur das Ende (höchstens 10 Zeilen, z. B. beim Disconnect verloren) → die
    Zeilen gehen noch einmal hinaus (`//HM <n> <unix> <text>`), kein Schaden;
  - sonst → `//HIST CLR g=<neu>`, beide löschen, Hinweis „chat history removed (not the same on
    both sides)“.
  - Andere Generation (einer hat gelöscht, als keine Verbindung bestand, oder erster Kontakt) →
    beide löschen und nehmen die größere Generation; ein Hinweis nur, wenn wirklich etwas weg war.
- **Knopf „Delete history“:** löscht hier, neue Generation, Hinweis „chat history removed“. Ist der
  andere verbunden: `//HIST DEL g=<gen>` – er löscht sofort, Hinweis „chat history removed by …“.
  Sonst merkt er es beim nächsten Connect an der Generation.
- Die TBClient-Ansicht zeigt den gespeicherten Verlauf (auch nach dem Disconnect, Eingabe dann
  gesperrt); `POST /api/peer/clear {"ch": n}`, Snapshot `peerchat`.
- Tests: `tests/test_peerchat.py`.

### Status-Chips (Client 2026.11.07.9)

- **Wunsch (OE3GAS, 07.11.2026):** „not connected“ als orangefarbener Chip (Kopfzeile und Karte
  der TBClient-Ansicht), neben „TBClient“ ein grüner Chip „connected to <call>“, in der
  Bulletin-/Mail-Liste „not loaded · Größe“ als orangefarbener Chip.
- Umsetzung: `.st-chip.ok` / `.st-chip.warn` (`--ok`/`--warn`), `.tag.notloaded`.
- 08.11.2026: Größe neben „not loaded“ in Bytes („not loaded · 512 bytes“).

### Bewertung bei wenigen Frames (07.11.2026, TinyBox und Client)

- **Anmerkung (OE3GAS):** Erst ab 20 Frames zu bewerten ist zu streng – 5 Frames ohne REJ sind
  schon ein sehr guter Link.
- **Umsetzung (`prcore/linkq.py`, gilt für beide):** unter `quality_min_frames` (20) zählen die
  Ereignisse statt der Prozente: 0 Wiederholungen/REJ → 5 Balken, jede kostet einen, ab 5 → rot;
  T1 wie bisher −1. „Vorläufig“ (`tentative`), solange keine Richtung 20 Frames hat: blasser in
  TinyBox-Web, Client-Chat, TBClient-Karte, `STAT` zeigt `~~~~~`. Ohne Frames grau. Siehe
  PLANUNG 14.

### Stufe 5: Emoticons/Emoji (Client 2026.11.08.2)

- Dieselbe Regel wie im TinyBox-Chat (PLANUNG 12.6, CR28): Emojis gehen nie als Unicode über
  Funk, sondern als klassisches Emoticon (`:-)`) bzw. `~XY`, `~~` = Tilde. Getippte Emoticons
  werden sofort zum Emoji, Knopf ☺ öffnet die Auswahl (ASCII-Smileys zuerst); darüber die
  Anzeige „n bytes on air: …“ bzw. welche Emojis nicht sendbar sind.
- Im Verlauf steht, was über Funk ging (beide Seiten gleich, Hash-Kette bleibt stimmig); die Blasen
  zeigen es als Emoji. Die rohe Terminal-Ansicht zeigt die Funkform.
- Ältere Clients (vor 2026.11.08.2) zeigen in ihrer Ansicht die Funkform `:-)`.

### Stufe 6: Bilder (Client 2026.11.08.3, `tbclient/peerimg.py`)

- Wie CR12, nur ohne TinyBox: Der Sender behält das Bild (verkleinert im Browser, derselbe
  Dialog mit klein/normal/groß, höchstens 8 KB). Über Funk geht nur der Verweis
  `~#<hash><größe><blurhash> Bildunterschrift` als Chat-Zeile – er steht im Verlauf beider Seiten.
- Der andere sieht den unscharfen Platzhalter mit Größe und Ladezeit und holt das Bild **per
  Antippen direkt beim Sender**: `//IMG <hash>` → `//I <hash> <offset> <gesamt>` + die Bytes am
  Stück (das AX.25-Fenster regelt das Tempo) bzw. `//NOIMG <hash>`.
- Ein Client gibt ein Bild nur der Station, der er es geschickt hat (Verweis in seinem
  gesendeten Verlauf mit ihr).
- Ein abgebrochener Download beginnt beim nächsten Antippen von vorn (Offset ist im Protokoll
  vorgesehen). Beide brauchen die Fähigkeit `IMG`; nicht über Telnet. Ablage wie die
  TinyBox-Bilder in `data/tbclient/images/`.
- Test: `tests/test_peerchat.py` (`test_picture_between_clients`).

### Stufe 7: Dateien und Uhrzeit (Client 2026.11.08.4, `tbclient/peerfile.py`)

- **Dateien** (Knopf 📎, höchstens 64 KB): wie die Bilder – der Sender behält die Datei
  (`data/tbclient/files/<hash>`), über Funk geht nur die Chat-Zeile
  `~%<hash> <bytes> <bytes on air> <name>` (im Verlauf beider Seiten). Der andere sieht Name,
  Größe und Zeit auf Funk und holt sie per Antippen: `//FGET <hash>` →
  `//F <hash> <z|r> <n>` + n Bytes bzw. `//NOFILE <hash>`. `z` = LZHUF (B0), `r` = roh, wenn LZHUF
  nichts bringt (ZIP, JPEG). Der Hash geht über die Datei selbst, der Empfänger prüft nach dem
  Entpacken. Nur an die Station, der sie angeboten wurde. Danach „Save“ (Download
  `/file/<hash>/<name>`, Name entschärft). Packen im Thread (64 KB ≈ 0,3 s).
- **Uhrzeit:** `//TB?` und `//TB CLIENT` tragen `t=<Unix-Zeit>`. Die Karte zeigt „🕒 clocks agree“
  (bis 10 s, die Zeile war ja kurz unterwegs) oder „their clock is 3 min ahead/behind“, ab einer
  Minute als orangefarbener Chip.
- Test: `tests/test_peerchat.py` (`test_file_between_clients`).

### Stufe 8: Ping, Speedtest, Schach, QSL, Karte, Zustellhaken (Client 2026.11.08.5)

Auf Vorschlag Claude, freigegeben von OE3GAS (08.11.2026). Fähigkeit `FUN`
(`tbclient/peerfun.py`, `tbclient/web/chess.js`):

- **Ping:** `//PING <token>` → `//PONG <token>`, Laufzeit hin und zurück (letzte 5) in der Karte.
- **Speedtest:** ein Knopf, beide Richtungen: `//ST 2048 go` + 2048 Bytes → `//STR 2048 <ms>`, dann
  `//ST 2048 back` + 2048 Bytes zurück. Der Empfänger misst von der Zeile bis zum letzten Byte;
  Ergebnis „→ … B/s ← … B/s“ (4 KB auf Funk je Test).
- **Schach:** `//CHESS NEW w|b`, `//CHESS M <uci>`, `//CHESS RESIGN`. Regeln (Zugerzeugung,
  Schach, Rochade, en passant, Umwandlung in Dame, Matt/Patt) im Browser, `chess.js` – geprüft mit
  Perft bis Tiefe 3 (8902). Der Client prüft nur, wer am Zug ist; die Partie liegt in den
  Einstellungen je Station und geht nach Neustart/nächstem Connect weiter. Brett mit der eigenen
  Farbe unten, Zug per Antippen; Hinweise im Verlauf („started a chess game“, „resigned“).
- **QSL:** Knopf „QSL“ schickt eine Chat-Zeile `~Q f=<MHz> t=<UTC> loc=<Locator> q=<Balken>`; beide
  Seiten zeigen eine QSL-Karte, „ADIF“ lädt den QSO-Eintrag (CALL, QSO_DATE, TIME_ON, FREQ,
  MODE=PKT, GRIDSQUARE/MY_GRIDSQUARE, QSL_RCVD/QSL_SENT).
- **Mini-Karte** in der Karte: beide Stationen aus den Locatoren, Linie, Locator-Gitter (2°×1°),
  Norden oben, Entfernung und Richtung; Klick öffnet die Route bei OpenStreetMap. Ohne Kacheln,
  nichts aus dem Netz.
- **Zustellhaken:** Eigene Zeilen zeigen „·“ unterwegs und „✓“, sobald Direwolf/KISS nichts mehr
  ausstehend meldet (Abfrage alle 3 s, nur Zeilen dieser Verbindung). Spalte `ok` in
  `peerchat.db` (wird beim Start ergänzt).
- Test: `tests/test_peerchat.py` (`test_ping_speed_chess_tick`).

### Später (eigene Stufen)

- Reaktionen auf Blasen in der TBClient-Ansicht.
- Sprachnachrichten mit Codec2 (WebAssembly im Browser, ~1,5 KB je 10 s) – eigenes Projekt.

## Kanal-Maximum in `tbclient.conf` (✅ 07.11.2026, zu CR45)

`[tinybox] max_channels` (Standard 5, erlaubt 1 … 10) ersetzt die feste Grenze 5 aus CR45.
Eingehende Connects und der Kanal des Mail-Abgleichs zählen mit. Alt+1 … Alt+9 schalten um,
Kanal 10 nur per Klick (Alt+0 bleibt der Monitor).

## CR79 – APRS-Statistik: Netzgraph und Geräte-Torte (✅ Stufe 1, 07.11.2026)

### Erfassung (OE3GAS, 07.11.2026)

- Eine anschauliche Grafik zur APRS-Statistik mit Bubbles, Knoten und Verbindungsvektoren:
  wer erreicht mich über wen.
- Filter nach Art der Pakete: alle, Position, Telemetrie usw.
- Auswertung der verwendeten Geräte als Tortendiagramm.
- Entwurf: Visualisierung im Chat (claude.ai), Varianten Kraft / Hop-Radar / Karte.

### Umsetzung Stufe 1 (Client 2026.11.07.8)

- **Daten:** `AprsStats.graph(window, me=…)` in `prcore/aprsstats.py`, API
  `GET /api/aprs/graph?win=<s>`. Knoten: Stationen, Digipeater, iGates und die eigene Station
  (`kind` = `station` / `digi` / `igate` / `me`), mit letzter bekannter Position (auch außerhalb des
  Zeitfensters, damit Digis mit eigener Bake einen Ort haben), Gerät und `moving` (Positionen
  > 1 km auseinander). Wege: Absender [→ iGate] → Digi … → ich, zusammengezählt je Weg,
  Pakettyp, Gerät und Internet-Herkunft – so filtert die GUI selbst. Höchstens die 80
  aktivsten Absender (`GRAPH_MAX_STATIONS`). Test: `test_graph`.
- **Anzeige** (`tbclient/web/aprsgraph.js`, reines SVG ohne Bibliothek – der Client läuft auch
  ohne Internet): Karte „Network“ in der APRS-Statistik nach „Frames over time“.
  - Bubbles: eigene Box grau, Digi orange, iGate grün, Station blau; mobile Stationen mit
    gestricheltem Ring, geschätzte Position (Digi ohne Bake: Mitte der Nachbarn) gepunktet.
    Größe = Frames durch den Knoten, Linienstärke = Frames je Link, Pfeil zur eigenen Station,
    Internet → Funk grün gestrichelt.
  - **Hop-Radar** (Standard): Ring = Hops (direkt gehört, 1 Hop, 2 Hops …), Winkel = Richtung vom
    eigenen Locator, Nachbarn je nach Größe auseinandergeschoben.
  - **Karte:** echte Richtung, Entfernung auf Wurzel-Skala (nahe Stationen bleiben getrennt),
    Ringe in km; nur mit Locator in `tbclient.conf`.
  - **Kraft:** nur die Struktur, Cluster um die Digis. Wechsel der Ansichten gleitend; die
    gewählte Ansicht bleibt im Browser gemerkt.
  - **Filter:** Paketart (Alle + die im Fenster vorkommenden Typen), „min. frames per link“.
    Die Knoten bleiben beim Filtern an ihrem Platz.
  - Überfahren: die Wege dieser Station hervorgehoben, Zeile darunter mit Frames, Entfernung,
    Hops, Gerät. Klick: Stationsseite (CR65).
  - **Geräte-Torte:** Anteile nach Frames oder Stationen, folgt dem Paketart-Filter; sieben
    Farben, der Rest als „Other“. Klick auf ein Stück oder eine Zeile filtert den Graphen auf die
    Stationen mit diesem Gerät (Chip „Device: … ×“ hebt es auf).

### Stufe 2 (offen, Ideen OE3GAS/Claude)

- **Zeitachse:** Regler über das Zeitfenster, Kanten blenden auf und ab – man sieht, wann ein
  Digi ausfällt oder ein Mobiler durchs Netz wandert.
- **Kanten nach Hop-Typ:** kräftig für einen Hop über WIDE1, blass für WIDE2-2-Fluten.
- **Kanal-Health:** roter Rand an Digis, über die viele „unchanged repeats“ laufen (Sins).


## CR80 – TBClient-Ansicht in drei Spalten, Aktionen rechts (✅ 08.11.2026)

### Erfassung (OE3GAS, 08.11.2026)

- Bei einem Connect mit einem anderen TBClient bekommt die Ansicht drei Spalten:
  - links die Karten (Chat Boards, Mail, Bulletins, Station) wie bisher,
  - in der Mitte das Dialogfenster (Profil, Linkqualität, Mini-Karte, Sprechblasen, Eingabe),
  - rechts eine neue Spalte, so breit wie die linke.
- In die rechte Spalte, untereinander: **Ping**, **Speed test**, **Chess**, **QSL**, dazu
  **Heard there** und **Delete history**. In der Kopfzeile des Dialogs bleibt nur „Terminal“.
- **Speed test:** vorher eine Bestätigung einholen. Der Benutzer soll wissen, dass nun beide
  Stationen je ca. 20 s den Kanal belegen.
- Wurde schon ein Speed test gemacht: der Wert neben dem Knopf (→ … B/s ← … B/s) und
  „tested xx min ago“.
- Ebenso der Wert des letzten Ping daneben, sonst „–“.
- Entwurf: Design-Canvas „TBClient 3 Spalten“ (claude.ai) – Hauptansicht, Bestätigung,
  Zustände der rechten Spalte (nichts / läuft / schon gemacht).

### Vorschlag zur Umsetzung (Claude)

- Rechte Spalte als zwei Karten im Stil der linken: „WITH <call>“ (Ping, Speed test, Chess, QSL)
  und „CHANNEL“ (Heard there, Delete history – rot umrandet).
- Unter jedem Knopf eine Ergebniszeile: Ping „1.8 s · 4 min ago“ bzw. „–“; Speed test Wert und
  „tested 3 min ago“ bzw. „–“, beim Laufen ein Fortschrittsbalken; Chess „your move“ (pulsierend,
  Client 2026.11.08.8) bzw. „waiting for <call>“; QSL „sent hh:mm“.
- Ergebnisse von Ping und Speed test je Gegenstation in den Settings merken, damit „tested
  xx min ago“ auch nach einem neuen Connect stimmt.
- Bestätigung: Dialog „Start speed test with <call>?“ mit Datenmenge und letztem Ergebnis,
  Knöpfe Cancel / Start test. Die Dauer rechnet der Client aus dem letzten Ergebnis, sonst
  aus 1200 Bd (≈ 20 s je Richtung bei 2048 Bytes).
- Schmale Fenster / Handy: die rechte Spalte rutscht unter das Profil (eine Zeile mit den
  Knöpfen, die Werte darunter), wie heute.
- Größe des Speed tests: **1024 Bytes** je Richtung (OE3GAS 08.11.2026, Client 2026.11.08.9;
  vorher 2048). Die Bestätigung nennt dann ca. 10 s je Richtung bei 1200 Bd.

### Umsetzung (Client 2026.11.08.10)

- `#peer-side` rechts (190 px wie die linke Spalte), nur im TBClient-View ab 1000 px; dort
  verschwinden die Knopfzeile unter dem Profil und „Heard there“/„Delete history“ aus der
  Kopfzeile. Schmaler bleibt alles wie bisher.
- Karte „With <call>“: Ping, Speed test …, ♟ Chess, QSL, darunter der letzte Wert oder „–“;
  „your move“ pulsierend bzw. „waiting for <call>“. Karte „Channel“: Heard there, Delete
  history (rot, auch ohne Verbindung).
- Letzte Ergebnisse je Gegenstation in den Settings (`fun_last`, höchstens 50 Stationen):
  „1.8 s · 4 min ago“, „→ 142 B/s ← 138 B/s“ + „tested 3 min ago“.
- Speed test fragt vorher (Dialog): Dauer aus dem letzten Ergebnis, sonst ≈ 120 B/s; gilt
  auch für den Knopf in der schmalen Ansicht. Test: `test_ping_speed_chess_tick`.

## CR81 – Schiffe versenken zwischen zwei TBClients (offen, 08.11.2026)

### Erfassung (OE3GAS, 08.11.2026)

- „Schiffe versenken“ als Spiel Client zu Client, wie Schach (CR78 Stufe 8).
- Frage an Claude: andere geeignete Spiele.
- Entscheidung Prüfung am Ende (OE3GAS, 08.11.2026): **behalten**, als stille Hintergrund-
  Kontrolle. Schummeln ist kaum zu erwarten (dafür müsste jemand den Code ändern), sie findet aber
  auch Fehler, etwa einen auseinandergelaufenen Spielstand nach Neustart oder verlorener Zeile.
  Im Spiel merkt man nichts davon; nur wenn etwas nicht stimmt, steht „board does not match“ im
  Ergebnis.

### Vorschlag zur Umsetzung (Claude)

- **Regeln:** 10 × 10 Felder (A–J, 1–10), Flotte 5 – 4 – 3 – 3 – 2, Schiffe gerade, dürfen
  sich nicht berühren. Wer trifft, schießt noch einmal (Variante, beim Start wählbar?).
- **Protokoll** (Zeilen mit `//`, nichts im Chat-Verlauf außer Start und Ergebnis, Fähigkeit
  `FUN` wie bei Schach):
  - `//BS NEW <hash>` – lädt ein, `<hash>` = sha1 über die eigene Aufstellung + Zufallswert
  - `//BS OK <hash>` – nimmt an, mit dem Hash der eigenen Aufstellung
  - `//BS F E5` – Schuss
  - `//BS R E5 miss|hit|sunk 3` – Antwort
  - `//BS END <aufstellung> <salt>` – am Ende legen beide offen (rund 100 Bytes). Der Client
    des anderen prüft still den Hash und jede Antwort im Spiel; nur bei einer Abweichung steht
    „board does not match“ im Ergebnis.
  - `//BS RESIGN`
- Ein Zug sind rund 15 Bytes, ein ganzes Spiel unter 3 kB über Funk.
- **Ansicht:** zwei Raster nebeneinander (eigene Flotte, Schüsse auf den anderen), Aufstellen
  per Klick oder „random“; „your move“ pulsierend in der rechten Spalte (CR80).
- Spiel je Gegenstation in den Settings, geht nach Neustart oder neuem Connect weiter.

### Weitere Spiele (Ideen, noch nicht entschieden)

- Ein gemeinsamer Rahmen `//G <spiel> …` für alle weiteren Spiele: Einladung, Zug, Aufgabe,
  Speichern, „your move“ – ein neues Spiel bringt nur seine Regeln (in der Web-GUI) mit.
- **Vier gewinnt** – ein Zeichen je Zug, schnell, kennt jeder.
- **Mühle** – klassisch, wenige Züge, kurze Nachrichten.
- **Reversi (Othello)** – 8 × 8, ein Feld je Zug.
- **Dame** – wie Schach, einfachere Regeln.
- **Mastermind** – Geheimcode mit Hash wie bei Schiffe versenken.
- **Würfelspiele (Kniffel)** – faire Würfel ohne Schiedsrichter: beide schicken zuerst den Hash
  einer Zufallszahl, dann die Zahl; der Wurf kommt aus beiden zusammen.
- Funkerisch: **Locator-Raten** – die Gegenstation nennt ein gehörtes Rufzeichen, man tippt
  dessen Locator, Punkte nach Entfernung.
