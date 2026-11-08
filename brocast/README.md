# brocast

Kompaktes Seitenprotokoll über AX.25 Packet Radio: CBOR mit Integer-Keys,
die Bedeutung der Nummern steht im lokalen Dictionary.

Spezifikation (lebendes Dokument):
https://claude.ai/code/artifact/bf4b91a7-7807-42d7-b72e-5739d9c257bd

## Dateien

| Datei | Inhalt |
| --- | --- |
| `brocast-core.yaml` | Kern-Dictionary Version 4 (Umschlag, Bausteine, Enums, Wetter, Quellen-Liste `src`; ab v4 DX-Zusammenfassung `dxsum`, Listen `band`, `mode`, `dxcc` mit ADIF-Nummern, Blockart `data`); v1 als Referenz in `tests\data`. Die DXCC-Liste erzeugt `tools/build_dxcc.py` |
| `brocast.cddl` | Schema zur Validierung |
| `brocast/` | Codec (`codec.py`) und brocastd (`daemon.py`, `station.py`, `carousel.py`, `ingest.py`, `agw.py`, `kiss.py`, `ax25.py`, `store.py`, `fragment.py`, `splitter.py`, `zdict.py`) |
| `brocastd.conf`, `brocastd.bat` | Konfiguration und Start |
| `zdict/` | Preset-Wörterbuch für die Kompression (binär, Teil der Software) |
| `tools/` | `payload_report.py` (Vorher/Nachher-Rechnung), `build_zdict.py` (Wörterbuch bauen) |
| `tests/` | Tests (`runtests.bat`) |
| `dictionary-empfehlung.md` | Momentaufnahme der Spezifikation |

## Einrichten

Python 3.10 oder neuer, dazu zwei Pakete:

```
cd /d E:\Tinybox\brocast
py -3 -m pip install -r requirements.txt
```

## Ausprobieren

```
py -3 -m brocast demo              Beispiel-Wetterseite (57 Bytes) anzeigen
py -3 -m brocast decode <hex>      eine empfangene Seite dekodieren
py -3 -m brocast dict              Dictionary-Version und Hash
```

## brocastd starten (Meilenstein M1)

In `direwolf.conf` muss der AGW-Port aktiv sein (Direwolf-Standard, TinyBox
nutzt ihn ebenfalls):

```
AGWPORT 8000
```

Wer brocastd über KISS anbindet (`interface = kiss`, siehe unten), braucht
stattdessen `KISSPORT 8001`.

Dann `brocastd.bat` doppelklicken oder:

```
py -3 -m brocast.daemon -c brocastd.conf
```

Einstellungen in `brocastd.conf` (Modus `station` oder `listener`, Rufzeichen
`OE3GAS-5`, Airtime-Budget …). Daten liegen unter `data\brocastd.db`.

Seite von Hand einspielen (Ingest-API, z. B. mit curl):

```
curl -X PUT -H "Content-Type: application/json" ^
  http://127.0.0.1:8090/api/v1/pages/test/wetter ^
  -d "{\"typ\":\"wx\",\"ti\":\"Wetter Hollabrunn\",\"dat\":{\"temp\":12.5,\"hum\":65}}"
```

Status: `http://127.0.0.1:8090/api/v1/status` im Browser.

## Was über Funk geht: Frame-Format 2 (ab 14.10.2026)

Eine Seite steht nicht mehr Stück für Stück in den Frames, sondern einmal als
Umschlag und dahinter der gepackte Inhalt:

| | Format 1 (bis 13.10.2026) | **Format 2 (Standard)** |
| --- | --- | --- |
| Umschlag (Titel, Rubrik, Quelle, Zeit) | in **jeder** Unterseite | nur im ersten Fragment |
| Inhalt | Klartext-CBOR, nur ganze Blöcke je Frame | alle Blöcke als ein Blob, mit deflate gepackt |
| Füllung der Frames | 70–80 % | randvoll bis auf das letzte |
| Lesbarkeit im Terminal | theoretisch | nein (ausdrücklich nicht das Ziel) |

Gemessen an den Testseiten in `test\`: 45 % weniger Bytes und 42 % weniger
Kanalzeit, bei langen Bulletins deutlich mehr. Selbst nachrechnen:

```
py -3 tools\payload_report.py                   Seiten der eigenen Datenbank
py -3 tools\payload_report.py test\*.json       Seiten aus Dateien
py -3 tools\payload_report.py --conf brocastd.conf
```

Beides steht im Header-Byte jedes Frames (hohes Nibble = Format), ein Listener
mit alter Software lässt die neuen Frames also liegen, statt halbe Seiten
anzuzeigen – und meldet im Empfangslog „neueres Format, brocastd
aktualisieren“. Umstellen in `brocastd.conf`:

```
[station]
wire_format = 2        ; 1 = alt, nur für Vergleichsmessungen
compress    = yes
```

**Preset-Wörterbuch.** Gepackt wird mit einem Wörterbuch, das beide Seiten
schon haben (`zdict\brocast-zdict-1.bin`, 32 kB: Funk- und Mailbox-Wortschatz,
Stationsnamen, Blockgerüste). Deshalb schrumpfen auch kurze Seiten um 30–50 %.
Das Wörterbuch gehört zur Software, nicht zum brocast-Dictionary: Seine
**Generation** (1) steht im Frame, und beim Start prüft brocastd den SHA-256
der Datei. Passt sie nicht, wird unkomprimiert gesendet (Warnung im Log) bzw.
eine Seite verworfen – dann hilft `git pull`. Wer das Wörterbuch ändert, muss
`tools\build_zdict.py --gen 2` benutzen und **beide** PCs aktualisieren.

**Verlorene Fragmente.** Eine Seite ist erst vollständig, wenn alle Fragmente
da sind; brocastd sammelt sie im Arbeitsspeicher (15 min, höchstens 64 halbe
Seiten) und setzt sie beim nächsten Karussell-Lauf zusammen. Weil es viel
weniger Fragmente als früher Unterseiten sind, kommt eine Seite trotzdem
häufiger ganz an: bei 97 % Frame-Erfolg sind 3 Fragmente in 91 % der Fälle
komplett, 8 Unterseiten nur in 78 %. Was noch fehlt, zeigt die Statusseite
(`wire.waiting`).

## Wie oft eine Seite wiederholt wird

Eine neue Revision geht sofort hinaus, dann nach `repeat_minutes`, danach alle
`max_interval_min`. Eine alte Revision braucht das nicht mehr so oft –
`aging` staffelt nach dem Alter:

```
[station]
aging = 24:120, 72:360, 168:1440   ; Vorgabe: ab 24 h alle 2 h, ab 3 Tagen alle 6 h,
                                   ; ab 7 Tagen einmal am Tag
```

Das Alter zählt ab dem Zeitpunkt, an dem der Inhalt entstanden ist: liefert
der Lieferant das Ingest-Feld `born` (Unix-Sekunden, geht nicht über Funk),
gilt dieses – TinyBox schickt das Erstelldatum des Bulletins mit. Sonst zählt
der Zeitpunkt der Revision. Die regelmäßigen Bestätigungen (stündlicher Sync)
setzen das Alter nicht zurück; sie halten nur `t` frisch, wovon der Ablauf
(`exp`) abhängt. `born` verändert den Inhalt nicht: wird es nachgeliefert,
entsteht keine neue Revision, nur das Alter wird korrigiert.

Mit `168:0` statt `168:1440` ruht eine Seite nach 7 Tagen ganz. `0` heißt: die Seite ruht. Sie bleibt im Bestand und geht wieder auf Funk,
sobald der Lieferant sie ändert (neue Revision). Das ist der größte Hebel,
wenn viele alte Bulletins im Karussell liegen – zum Beispiel ein Dutzend
Client-News, die sich nicht mehr ändern.

## Verbindung zu Direwolf: AGW oder KISS

brocastd spricht mit Direwolf **entweder über AGW oder über KISS**, nie über
beide gleichzeitig. Gewählt wird in `brocastd.conf`:

```
[direwolf]
interface = agw        ; agw (empfohlen) oder kiss
agw_port  = 8000
kiss_port = 8001
channel   = 0
```

Eine alte `brocastd.conf` mit Abschnitt `[kiss]` (ohne `[direwolf]`) läuft
unverändert weiter, und zwar über KISS.

### Sendepausen (`burst_frames`, `burst_gap_s`)

Direwolf sendet alles, was in seiner Sendewarteschlange liegt, in **einer**
Aussendung (ein PTT-Zyklus). Eine Seite mit vielen Teilen, z. B. das Dictionary
mit ca. 15 Frames, würde die Frequenz sonst eine halbe Minute am Stück belegen.
brocastd teilt deshalb selbst auf:

```
[station]
burst_frames = 4       ; höchstens 4 Frames pro Aussendung (0 = keine Aufteilung)
burst_gap_s  = 3       ; danach 3 s Pause, Kanal frei für andere Stationen
```

Bei 1200 Bd sind 4 volle Frames rund 8 s Sendezeit. In der Pause können andere
Stationen senden; Direwolf prüft vor der nächsten Aussendung wieder den Kanal
(DCD, `DWAIT`, `SLOTTIME`, `PERSIST`). Mehr Frames pro Block und kürzere Pausen
sind schneller, aber weniger kanalfreundlich.

### Der Unterschied: wer weiß, wann gesendet wurde?

**AGW (empfohlen).** brocastd fragt Direwolf (AGW-Abfrage `y`), wie viele
Frames noch in der Warteschlange liegen, und schickt den nächsten Block erst,
wenn sie leer ist – plus Sendezeit des letzten Frames, ein kleiner Zuschlag für
TXTAIL und `burst_gap_s`. Die Pause gilt damit auch, wenn der Kanal belegt war
und Direwolf warten musste. Der Takt kommt von Direwolf.

**KISS.** Über KISS meldet Direwolf nicht, wann eine Aussendung zu Ende ist.
brocastd **berechnet** das Ende aus Baudrate, `txdelay_ms` und Framelänge und
nimmt dabei an, dass Direwolf sofort senden konnte. Folgen:

- Bei freiem Kanal funktioniert die Aufteilung wie bei AGW.
- **Bei belegtem Kanal** hält Direwolf den ersten Block zurück. brocastd
  rechnet trotzdem weiter und reicht nach Ablauf der Pause den nächsten Block
  nach. Beide liegen dann gemeinsam in Direwolfs Warteschlange und gehen **in
  einer langen Aussendung** hinaus – die Aufteilung ist genau dann wirkungslos,
  wenn auf der Frequenz viel los ist.
- Stimmen `baud` oder `txdelay_ms` in `brocastd.conf` nicht mit `direwolf.conf`
  überein, sind die berechneten Pausen zu kurz oder zu lang.

KISS ist sinnvoll, wenn kein AGW-Port verfügbar ist (z. B. ein Hardware-TNC
oder ein anderes Programm statt Direwolf). Beim Start schreibt brocastd im
Modus `station` mit KISS einen Hinweis ins Log.

### Sonderfälle bei AGW

- Beantwortet Direwolf die Abfrage nicht (sehr alte Version), schreibt brocastd
  einmal eine Warnung ins Log und rechnet die Pausen wie bei KISS.
- Hält Direwolf Frames länger als 60 s zurück (Kanal dauerhaft belegt, DCD
  hängt), steht eine Warnung im Log; brocastd schickt bis dahin nichts nach.
- TinyBox und brocastd teilen sich den AGW-Port; Direwolf erlaubt mehrere
  AGW-Programme gleichzeitig. Die Abfrage `y` zählt die Frames des ganzen
  Kanals, also voraussichtlich auch die von TinyBox – brocastd wartet dann auch
  auf TinyBox-Aussendungen (beim ersten Funktest im Debug-Log prüfen).

## Listener (Meilenstein M2)

brocastd hält empfangene Seiten wie Teletext: gelesen/ungelesen, „aktualisiert“
bei neuer Revision, Favoriten, Löschen bis zur nächsten Revision, Ablauf,
Höchstzahlen, Abo mit Opt-out, Warnungen immer sichtbar. Eine Station zeigt
auch ihre eigenen Seiten.

**Oberfläche (M3):** bei laufendem brocastd im Browser `http://127.0.0.1:7733/` öffnen.
Rubriken/Stationen links, Seitenliste in der Mitte, Seite rechts; Suche,
Seitennummer-Eingabe, Einstellungen (Abo, Grenzen) und Status oben bzw. links unten.

Jede Seite lässt sich auf zwei Arten anzeigen (Umschalter „Ansicht“, wird im
Browser gemerkt): **Fließtext** (alles untereinander im normalen Seitenlayout) und
**Teletext** – ein schwarzer Bildschirm mit eigener Pixelschrift, 40 Zeichen je
Zeile und weitem Zeilenabstand, Rubrik im roten Feld, Titel in Gelb; bei mehreren
Unterseiten blättern die Teile-Knöpfe und ◀ ▶ durch die Teile. Der Teletext-
Bildschirm ist immer Text: Wetterkacheln und Wetterraster erscheinen dort als
Werteliste bzw. einfache Tabelle (der Knopf „Grafisch/Text“ gilt für den Fließtext
und wird im Teletext ausgeblendet). Testseiten: `test\senden.bat bulletin`
(ein langer Text in 4 Teilen) und `test\senden.bat magazin` (3 thematische Teile).
Vorschau ohne laufenden brocastd: `mockup\teletext-vorschau.html`.

Über jeder Teletext-Seite steht der brocast-Schriftzug nach dem Vorbild der
Teletext-Titelseite (helle Quadrate mit schwarzen Fugen, Buchstaben ausgespart,
darunter die rote Linie): `brocast/web/brocast-logo.svg`, erzeugt mit
`tools/build_logo.py`.

Die Pixelschrift `brocast/web/teletext.woff` (7 kB) wird mit
`tools/build_teletext_font.py` aus einem 7 × 13-Pixel-Raster erzeugt (DejaVu Sans
Mono Bold bei 10 px, schwarz-weiß gerastert, jedes Pixel ein Quadrat im Umriss);
die Mosaikzeichen für Bildseiten sind darin gezeichnet statt gerastert. Das
Skript muss nur laufen, wenn sich Zeichenvorrat oder Raster ändern.

## Bilder (nur Station)

```
py -3 -m brocast bild foto.jpg --titel "Shack von OE3GAS"      nur Vorschau + Bytes
py -3 -m brocast bild foto.jpg --senden                        an das laufende brocastd
py -3 -m brocast bild foto.jpg --tinybox ..\eingang            als Bulletin in die TinyBox
```

Das Bild wird zu Teletext-Mosaik: ein Zeichen trägt 2 × 3 Felder (Sextanten
`U+1FB00…U+1FB3B`), 40 × 16 Zeichen sind also 80 × 48 Punkte. Die Seite besteht
aus ganz normalen `pre`-Blöcken – keine neue Blockart, kein neues Dictionary –
und kostet gepackt rund 500 Byte (3–4 Frames). Weitere Schalter: `--spalten`
(Breite in Zeichen, höchstens 40), `--invert`, `--hart` (harte Schwelle statt
Fehlerstreuung, gut für Zeichnungen und Logos), `--text` (Bildunterschrift),
`--rubrik`, `--gueltig`. Dafür wird Pillow gebraucht (`pip install pillow`);
im Listener-Betrieb lehnt der Befehl ab.

**Sendung (Station, 08.11.2026):** In der Kopfzeile zeigt ein Feld, was die Station gerade
sendet – „ON AIR P120 Wetter Krems 3/7“ mit Fortschrittsbalken, sonst die nächste Seite mit
Countdown, „⏸ PAUSE“ bei vollem Airtime-Budget oder „✕ KEIN SENDER“, wenn Direwolf getrennt
ist; daneben das Airtime-Budget. Ein Klick (oder „Sendung“ in der Seitenleiste) öffnet die
Ansicht mit der Seite auf Sendung (Teile als Kästchen, Bytes, Airtime, Restzeit, bei AGW die
Frames in der Direwolf-Queue), dem Budget, den nächsten Seiten und den zuletzt gesendeten.
Zeit = Übergabe an Direwolf wie im Sendeprotokoll; bei KISS ist die Restzeit berechnet. Die
Oberfläche fragt jede Sekunde, solange gesendet wird, sonst alle 5 s.

**Bake (Station):** `[beacon]` in `brocastd.conf` sendet alle `interval_min` Minuten (Standard
30, mindestens 5, 0 = aus; die erste beim Start) einen UI-Frame im Klartext an `dest` (Standard
`BEACON`), z. B. „OE3GAS-5: brocast - Teletext-Seiten ueber Packet Radio …“ – so sieht jeder am
Terminal oder Monitor, was hier sendet. Text frei (`text`, höchstens 250 Bytes, ASCII empfohlen,
Platzhalter `{call}` `{version}` `{pages}`); mehrere Zeilen: die weiteren eingerückt unter
`text =`, sie gehen mit CR getrennt im selben Frame. Die Bake geht nie mitten in eine Seite, zählt zur
Airtime, wird aber vom Budget nicht zurückgehalten; sie steht im Sendeprotokoll und unter
„Zuletzt gesendet“.

**Seite nicht mehr senden:** „✕“ bei „Als Nächstes“ (oder „Nicht mehr senden“ bei einer eigenen
Seite) nimmt sie aus der Sendung: Die Hörer bekommen die Rücknahme und löschen sie, und schickt
die Quelle (TinyBox-Abgleich, dxfeed) denselben Inhalt wieder, bleibt sie draußen. Erst ein
geänderter Inhalt kommt wieder – oder „Wieder senden“. Ein Bulletin ist endgültig weg, wenn es
auch in der TinyBox gelöscht ist. Das einfache „Löschen“ einer fremden Seite blendet sie nur
in der eigenen Liste aus.

Die Rohdaten liefert weiterhin die JSON-API:

| Adresse | Inhalt |
| --- | --- |
| `http://127.0.0.1:7733/api/v1/status` | Status |
| `POST /api/v1/tx/off {"id": n}` · `POST /api/v1/tx/restore {"provider", "key"}` | Station: Seite aus der Sendung nehmen / wieder senden |
| `http://127.0.0.1:7733/api/v1/tx` | Station: was gerade gesendet wird (Seite, Teil n/gesamt), was als Nächstes kommt, zuletzt gesendet, Airtime-Budget – aktualisiert bei jeder Übergabe eines Frames an Direwolf |
| `http://127.0.0.1:7733/api/v1/categories` | Rubriken mit Anzahl/ungelesen (auch leere, die eine Station ankündigt) |
| `http://127.0.0.1:7733/api/v1/rubrics` | alle Rubriken für die Abo-Matrix, mit Beschreibung und `stations` |
| `http://127.0.0.1:7733/api/v1/stations` | gehörte Stationen |
| `http://127.0.0.1:7733/api/v1/pages?cat=dx` | Seiten einer Rubrik (auch `station=`, `unread=1`, `favorite=1`, `q=`) |
| `http://127.0.0.1:7733/api/v1/pages/OE3GAS-5/25?raw=1` | eine Seite, mit Rohansicht |

Schreibende Aufrufe (lesen/ungelesen, Favorit, löschen, Einstellungen, Abo)
brauchen den Header `X-Brocast-Client: 1`; Details in `brocast/listener_api.py`.

**Zugriff aus dem LAN/WLAN** (z. B. vom Handy): in `brocastd.conf`

```
[listener]
web_host  = 0.0.0.0
allow_lan = yes
lan_names = pc2.fritz.box     ; nur nötig, wenn der Browser einen anderen Namen benutzt
```

Dann im Browser `http://<IP-Adresse des PCs>:7733/` oder `http://<Rechnername>:7733/`.
Die Oberfläche hat **keine Anmeldung** – jedes Gerät im Netz kann Seiten löschen
und Einstellungen ändern. Deshalb in der Windows-Firewall TCP 7733 eingehend nur
für das Heimnetz freigeben (PowerShell als Administrator, Netz anpassen):

```
New-NetFirewallRule -DisplayName "brocastd Listener" -Direction Inbound -Protocol TCP -LocalPort 7733 -RemoteAddress 192.168.1.0/24 -Action Allow
```

Aufrufe mit fremden Domainnamen im Host-Header werden weiter abgewiesen
(Schutz gegen DNS-Rebinding). Die Ingest-API (Port 8090) bleibt immer auf
127.0.0.1 – über sie wird gesendet.

## Dauerbetrieb (PC2) und Sendeprotokoll

- `..\start_alles.bat` startet Direwolf, brocastd und TinyBox in eigenen Fenstern
  (Direwolf-Pfad oben in der Datei einmal anpassen). brocastd und TinyBox werden
  nach einem Absturz automatisch neu gestartet.
- Autostart: Verknüpfung zu `start_alles.bat` in den Autostart-Ordner legen
  (Win+R → `shell:startup`).
- `logs\brocastd_log_<Datum>_<Zeit>.log`: Programm-Log, eine Datei pro Start.
- `logs\Sendeprotokoll_<JJJJ-MM>.txt`: jeder gesendete Frame mit Zeit (UTC),
  Rufzeichen, Seite, Revision, Teil, Bytes, Sendezeit, Lieferant und Titel.
  Nachweis für den Betrieb, wird nie automatisch gelöscht.

## Wetterseite (GeoSphere, typ wx)

`geosphere_station.py --tinybox` (im TinyBox-Ordner) legt den Wetterbericht wie
bisher als Bulletin in den TinyBox-Eingang, dazu in der Kopfzeile `Brocast:` die
fertige Wetterseite. Die Mailbox zeigt den Text, der brocast-Adapter von TinyBox
reicht die Seite an brocastd weiter (PLANUNG.md, Abschnitt 6d). Gesendet werden
nur Zahlen (Dictionary `wx`, ab Version 2), dazu der Temperaturverlauf 24 h als
Zeitreihe (ein Wert je 2 h). Das ergibt normalerweise **einen** Frame
(~205 Bytes, ca. 1,9 s bei 1200 Bd) statt mehrerer Textseiten.

```
py -3 geosphere_station.py --tinybox     Mailbox (Text) + brocast (Wetterseite)
py -3 geosphere_station.py --brocast     nur zum Testen ohne TinyBox: direkt an brocastd
py -3 geosphere_station.py --region --tinybox
                                         24 Stationen Wein-/Waldviertel: Einzelberichte
                                         (je eine wx-Seite) + Gesamtueberblick
                                         "Wetter Wein- & Waldviertel" (Tabellenseite,
                                         gepackt 3 Frames)
```

Die Listener-Oberfläche zeigt Seiten vom typ `wx` als Kacheln (Temperatur mit
24-h-Spanne, Windrose, Luftdruck mit Tendenz, Feuchte, Verlauf, Niederschlag).
Felder, die die Ansicht nicht kennt, erscheinen darunter als einfache Werte.
Offline-Vorschau ohne laufenden brocastd: `mockup\wx-vorschau.html`.

Der Gesamtüberblick ist eine Tabellenseite (`typ text`, Blöcke `table`), deren
erster Block mit `n` die Spaltenbedeutung mitschickt (`["name", "temp", "wdir",
"wspd", "gust", "r24h"]`, Namen aus dem Wetter-Dictionary). Der Listener macht
daraus das Wetterraster: Extremwerte der Region, Temperaturbalken, Windpfeile,
Regenbalken; Zeilen mit nur einer Zelle (`["Weinviertel"]`) sind Gruppen. Der
Knopf **Grafisch / Text** auf der Seite schaltet auf die schlichte Tabelle bzw.
bei `wx`-Seiten auf Wertekarten um (gemerkt im Browser). Vorschau:
`mockup\wx-region-vorschau.html`.

## Rubriken der Station (Indexseite)

Die TinyBox meldet ihre Rubrikenliste (`[rubrics]` in `tinybox.conf`) beim
vollen Abgleich mit (`PUT /api/v1/pages/tinybox`, Feld `rubrics`). brocastd
sendet daraus eine Seite `typ index` („Rubriken“, Lieferant `brocastd`) im
Karussell; neue Revision nur, wenn sich die Liste ändert. Listener zeigen die
angekündigten Rubriken samt Beschreibung schon, bevor die erste Seite kommt
(Übersicht, Abo-Matrix), und lassen gestrichene Rubriken fallen, sobald keine
Seite mehr dazu vorhanden ist. `GET /api/v1/rubrics` (Ingest-Port) zeigt den
Stand auf der Station. Hintergrund: `PLANUNG.md`, Abschnitt 6f.

## Dictionary über Funk (gepackt)

Eine Station sendet ihr Dictionary zusätzlich gepackt über Funk (zlib über die
CBOR-Form, ~2,8 kB statt ~12 kB): ca. 15 Frames, rund 30 s bei 1200 Bd. Gleich
nach dem Start bzw. einer neuen Version, 15 min später noch einmal, danach alle
`dict_broadcast_hours` Stunden (`brocastd.conf`, Standard 24, 0 = aus).

Ein Listener braucht dafür kein Rufzeichen. Er sammelt die Teile auch über
mehrere Aussendungen, prüft dann Länge, Prüfsumme, Version und dass nur Einträge
dazukommen. Installiert wird

- automatisch, wenn die Station unter Einstellungen → „Dictionary über Funk
  automatisch übernehmen von“ eingetragen ist (z. B. `OE3GAS-5`),
- sonst nach Klick auf „Installieren“ im gelben Hinweis.

Die alte Datei bleibt als `brocast-core.v<alt>.bak.yaml` erhalten.

## Dictionary aktualisieren (über TinyBox)

1. Station: neue `brocast-core.yaml` (höhere `version`, nur Ergänzungen) in den
   brocast-Ordner legen. TinyBox bietet sie sofort mit dem Befehl `DICT` an
   (`[brocast] dict_file` in `tinybox.conf`), brocastd kündigt sie an
   (`dict_source` in `brocastd.conf`, brocastd neu starten).
2. Listener: gelber Hinweis „Dictionary v2 erhältlich …“. Mailbox connecten,
   `DICT` eingeben, Ausgabe mitschneiden.
3. Im Listener „Importieren“ → Mitschnitt-Datei wählen oder einfügen →
   „Prüfen und installieren“. Die alte Datei bleibt als
   `brocast-core.v1.bak.yaml` erhalten, ein Neustart ist nicht nötig.

## In Python

```python
from brocast import Codec

codec = Codec()
data = codec.encode({"id": 7, "t": 1790000000, "typ": "wx",
                     "dat": {"temp": 12.5, "hum": 65}})
page = codec.decode(data, ax25_src="OE3GAS-10")
print("\n".join(codec.describe(page)))
```

## Regeln fürs Dictionary

- Eine vergebene Nummer wird nie umgedeutet.
- Neue Einträge nur mit neuer `version`; Versionen sind additiv.
- Keys 0–23 und −1…−24 (1 Byte) nur für die Kern-Spezifikation.
