# Droid Studio (ADBAutomator)

Lokale Python-Anwendung für die forensische Sicherung von Android-Bildschirminhalten und für Android-Abläufe aus Scratch-ähnlichen Blockly-Bausteinen. „Liste sichern“ öffnet jeden Eintrag einer Liste (etwa alle Chats), blättert ihn vollständig durch und dokumentiert jede Seite mit Screenshot, Bericht und SHA-256-Hashwerten. Die Oberfläche läuft im Browser, die Geräteaktionen führt `uiautomator2` auf deinem Computer aus.

## Starten unter Windows

Ist die Umgebung bereits eingerichtet: **`start.bat` doppelklicken**. Die Oberfläche öffnet sich unter <http://127.0.0.1:8765>.

Bei einer neuen Installation:

1. Python 3.11 oder neuer, Node.js mit npm und Git installieren.
2. Das Repository holen: `git clone https://github.com/AndroidIosForensik/ADBAutomator.git`
3. Im Ordner `setup.bat` ausführen. Das installiert die Python-Bibliotheken in `.venv` sowie Blockly lokal in `node_modules`.
4. `start.bat` öffnen. Das Konsolenfenster offen lassen; Strg+C beendet die App und einen von ihr gestarteten uiautodev-Inspektor.

Alternativ:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
npm.cmd ci --ignore-scripts
.\.venv\Scripts\python.exe app.py
```

### Ohne Installation: Exe und portable ZIP

```powershell
.\.venv\Scripts\python.exe tools\build_portable.py
.\.venv\Scripts\python.exe tools\test_portable.py
```

Das erzeugt in `dist/` zwei Varianten, beide mit eingebautem Python, Blockly und ADB:

- `Droid-Studio.exe` – eine einzelne Datei. Beim ersten Start entpackt sie sich in einen Ordner `Droid Studio` daneben und startet die App; spätere Starts gehen direkt los. Nach einem Update werden nur Programmdateien ersetzt, `Sicherungen` und `data` bleiben erhalten.
- `Droid-Studio-Windows-x64.zip` – zum Entpacken, etwa auf einen USB-Stick; darin `Droid Studio.exe` doppelklicken.

Zu jeder Datei liegt eine `.sha256`-Prüfsumme bei. Die Exe ist nicht signiert; Windows SmartScreen kann beim ersten Start warnen („Weitere Informationen“ → „Trotzdem ausführen“). Der Starter wird beim Build mit dem C#-Compiler des .NET Framework aus `tools/launcher/DroidStudio.cs` übersetzt.

Ein anderer Port ist mit `app.py --port 8766` möglich. `--no-browser` verhindert das automatische Öffnen des Browsers. Der Server lauscht ausschließlich auf `127.0.0.1`.

## Liste sichern (forensische Dokumentation)

„Liste sichern“ öffnet jeden Eintrag einer Liste auf dem Gerät, blättert seinen Inhalt vollständig durch und speichert jede Seite als Screenshot, zum Beispiel alle Chats eines Messengers mit ihrem kompletten Verlauf.

1. **Fall wählen:** Oben neben dem Ablaufnamen steht der aktive Fall. Dort einen Fall mit Aktenzeichen, Bearbeiter/in und Notiz anlegen oder wechseln. Listen und Sicherungen werden je Fall getrennt abgelegt.
2. **Liste öffnen:** Auf dem Gerät die gewünschte Liste öffnen, etwa die Chatübersicht.
3. **„Liste sichern“** in der Geräteansicht drücken, „Gerätebild laden“ und im Bild auf einen vollständigen Eintrag klicken. Rahmen und Vorschau zeigen, was als ein Eintrag gilt. Die Auswahl tippt nichts auf dem Gerät an.
4. **Einstellungen:** Bezeichnung vergeben und wählen, wie jeder Eintrag durchgeblättert wird: „Vom Ende zum Anfang“ für Chatverläufe (neueste Nachricht zuerst) oder „Vom Anfang zum Ende“ für E-Mails und Profile. „Höchstens Seiten je Eintrag“ begrenzt sehr lange Inhalte; ein gekürzter Eintrag wird als „unvollständig“ markiert.
5. **Sicherung starten.** Oben steht der Fortschritt. „Pause“ hält zwischen zwei Einträgen an, „Nächster Eintrag“ sichert genau einen weiteren, „Fortsetzen“ läuft weiter. „Stopp“ beendet die Sicherung; bereits Gesichertes bleibt mit Bericht erhalten.

Die Einträge werden an ihrer Position auf dem Bildschirm angetippt, nicht per Text gesucht. Dadurch funktionieren auch Einträge aus mehreren Texten (Name, Nachricht, Uhrzeit), und gleichnamige Einträge bleiben getrennt. Gescrollt wird ohne Schwung: Der Finger hält vor dem Loslassen kurz still, damit Android nicht über Einträge hinwegscrollt. Jeder neue Bildschirmabschnitt wird mit dem vorherigen abgeglichen; lässt sich die Liste nicht lückenlos fortsetzen, steht eine Warnung im Bericht.

**Wichtig:** Das Gerät vorher in den Flugmodus versetzen. Sonst kann sich die Liste während der Sicherung ändern, und Messenger senden beim Öffnen eines Chats Lesebestätigungen.

Jede Sicherung erhält einen eigenen Ordner unter `Sicherungen/<Fall>/<Zeitpunkt>_<Bezeichnung>/`:

- `E0001_<Eintrag>/E0001_S0001.png` … die Screenshots je Eintrag und Seite
- `bericht.html` mit Fall, Gerät (Hersteller, Modell, Android-Version, Seriennummer, Gerätezeit), Zeitpunkten, Status und Vorschaubild je Eintrag
- `eintraege.csv` (Semikolon-getrennt, für Excel) und `sicherung.json` (maschinenlesbar)
- `hashes.sha256` mit den SHA-256-Werten aller Dateien, prüfbar mit `sha256sum -c hashes.sha256`. Die Prüfsumme dieser Hashliste steht im Protokoll und in der Ablage.

Die **Ablage** zeigt alle Sicherungen und Listen des aktiven Falls mit Fortschritt, Status je Eintrag, Vorschaubildern und Links zu jeder Seite. Von dort lassen sich Bericht, CSV und Ordner öffnen, Listen umbenennen, als CSV exportieren oder als Schleife verwenden sowie Sicherungen und Listen löschen. „Nur Listentexte aufnehmen …“ nimmt wie bisher nur die Texte einer Liste auf, ohne Einträge zu öffnen.

Im Assistenten erzeugt „Als Baustein einfügen“ einen Baustein „Liste sichern“, der mit „Starten“ als Teil eines Ablaufs läuft. Dieser Baustein wird nicht als Python exportiert, weil Bericht und Hashwerte nur in Droid Studio entstehen.

Ohne Handy lässt sich alles mit dem Demo-Gerät ausprobieren: Im Assistenten „Demo-Chats auf dem Demo-Gerät öffnen“ wählen. Die Demo-Liste enthält absichtlich zwei identische Chats und ungelesene Nachrichten.

## Ohne Programmieren zum ersten Ablauf

1. **Demo ausprobieren:** Der voreingestellte Ablauf öffnet die Einstellungen, wartet, tippt auf „Anzeige“ und speichert einen Screenshot. „Starten“ führt ihn aus. Die Demo steuert kein echtes Telefon.
2. **Bausteine hinzufügen:** Links einen Baustein anklicken, um ihn am Ende anzufügen. Oder auf die Arbeitsfläche ziehen und an einen anderen Baustein andocken. Nur die mit „Wenn gestartet“ verbundenen Bausteine gehören zum Ablauf; lose Blöcke müssen vor dem Start verbunden oder entfernt werden.
3. **Werte ändern:** Direkt auf Felder und Auswahllisten in den Blöcken klicken. Weitere Blöcke lassen sich in Wiederholungen und in die beiden Zweige einer Bedingung einsetzen.
4. **Element aufnehmen:** „Element auswählen“ drücken, dann das gewünschte Element auf dem Gerätebild anklicken. Die Vorschau pausiert für die Auswahl. Verwendet werden eindeutige Element-IDs, Beschreibungen oder Texte; ohne geeigneten Treffer wird eine relative Bildschirmposition eingefügt.
5. **App übernehmen:** Eine gewünschte App auf dem Telefon öffnen und „Geöffnete App übernehmen“ drücken. Dadurch wird ihr Startbefehl eingefügt, ohne einen Paketnamen eingeben zu müssen. Im App-Baustein gibt es zusätzlich einige bekannte Apps zur Auswahl; sie müssen auf dem Telefon installiert sein.
6. **Starten:** Der aktive Block wird hervorgehoben. Das Protokoll zeigt Schritte, Fehler und Links zu Screenshots. „Stopp“ unterbricht Wartezeiten sofort; eine bereits laufende Geräteanfrage muss zunächst zurückkehren.
7. **Speichern:** Der aktuelle Entwurf wird im lokalen Browserspeicher gesichert. Im Menü „Projekt“ lädt „Als Datei speichern“ zusätzlich eine JSON-Projektdatei herunter; mit „Datei öffnen“ lässt sie sich wieder laden. „Neuer Ablauf“ oder „Beispiel laden“ ersetzt den Entwurf nach Rückfrage. Vorher wichtige Projekte als Datei speichern.
8. **Python exportieren:** Unter „Python-Code“ wird der Ablauf als lesbarer Python-Code angezeigt und kann als `.py` heruntergeladen werden. Für einen Export aus der Demo ist später ein echtes Android-Gerät erforderlich.

Unter `examples/schleife-und-bedingung.json` liegt ein zusätzliches Projekt zum Öffnen, das verschachtelte Wiederholungen und eine Wenn-/Sonst-Bedingung zeigt.

## Einen Ablauf schrittweise prüfen

**Schrittweise** hält vor dem ersten Baustein an. Der hervorgehobene Block ist der nächste Befehl; **Nächster Schritt** führt ihn aus und hält wieder vor dem folgenden Block an. Auch Schleifen und Bedingungen werden einzeln betreten: Ein Schritt auf einer Schleife führt noch nicht ihren gesamten Inhalt aus. Über der Arbeitsfläche stehen der nächste Befehl und innerhalb einer Listenschleife der aktuelle Listenwert. Wartezeiten und Scroll-Suchen werden als jeweils ein Befehl vollständig ausgeführt.

**Fortsetzen** führt den Rest automatisch aus. **Pause** hält einen laufenden Ablauf vor dem nächsten Baustein an, sobald der aktuelle Befehl abgeschlossen ist. **Stopp** beendet auch einen angehaltenen Ablauf. Während eines angehaltenen Laufs bleiben Bearbeitung, direkte Geräteaktionen und Gerätewechsel gesperrt. Nach einer Änderung muss der Ablauf neu gestartet werden.

Die Demo zeigt für „Anzeige“ die Einträge Helligkeit, Dunkles Design und Bildschirm-Timeout. Antippen öffnet eine eigene simulierte Detailansicht; **Zurück** kehrt zur tatsächlichen vorherigen Seite zurück. Für eine gespeicherte Liste dieser drei Einträge muss vor dem Start die Seite **Anzeige** geöffnet sein, zum Beispiel mit `App Einstellungen öffnen → Element Anzeige antippen → Für jeden Eintrag …`. Die Liste selbst navigiert nicht zu ihrer Ursprungsseite.

## Variablen und einsetzbare Werte

Unter **Variablen** findest du **Variable setzen**, **Variable ändern**, **Variablenwert**, **Textwert**, **Zahlenwert** und **Aktueller Listeneintrag**. „Variable setzen“ speichert einen Text oder eine Zahl unter einem frei gewählten Namen. „Variable ändern“ addiert einen Zahlenwert; negative Werte ziehen etwas ab. Setze die Variable vorher, zum Beispiel `Zähler = 0`. Namen müssen übereinstimmen; Groß- und Kleinschreibung werden unterschieden.

Stecke den Baustein **Variablenwert** in einen passenden Werteingang. Texteingabe, Elementsuche, Wenn-Element-da-ist, Scroll-Suche und Listenfilter nehmen Text- oder Zahlenwerte an. Wartezeit, Zeitlimit und Wiederholungsanzahl benötigen Zahlen. Die zusätzlichen Eingänge heißen beispielsweise **Suchwert stattdessen** oder **Sekunden stattdessen**: Ein eingesetzter Wert ersetzt das entsprechende feste Feld. Ohne eingesetzten Wert gilt weiterhin das Feld. Vorhandene Projekte funktionieren dadurch unverändert. Wertbausteine lassen sich auf die Arbeitsfläche ziehen und andocken; ein Klick in der Palette setzt einen Wert in einen freien passenden Eingang des ausgewählten Bausteins, wenn möglich.

In einer Listenschleife kann **Aktueller Listeneintrag** auch einer Variablen zugewiesen werden. Ihr Wert bleibt danach für den restlichen Lauf verfügbar. Alle Variablen starten bei jedem neuen Lauf leer. **Variablen im aktuellen Lauf** zeigt die Werte auch im Schrittmodus und nach dem Abschluss an. Ein Zugriff vor dem Setzen, ein Text in einem Zahlenfeld oder ein Wert außerhalb der zulässigen Grenzen hält den Ablauf am betroffenen Baustein an. Zahlen werden in Textfeldern als Text verwendet; Text wie „3“ wird nicht automatisch in eine Zahl umgewandelt.

Unter **Variablen → Variablenbeispiel laden** gibt es einen Ablauf, der einen Text kopiert und einen Zähler dreimal erhöht, ohne das Gerät zu bedienen. Die Datei liegt unter `examples/variablen.json`. Variablen und verbundene Wertbausteine werden mit dem Projekt gespeichert und im Python-Export unterstützt. Erlaubt sind bis zu 2000 Zeichen bzw. Zahlen zwischen −10¹² und 10¹². Wartezeiten und Schleifen behalten ihre bisherigen Grenzen. Für die Vorabprüfung der maximalen Schrittzahl wird eine variable Wiederholung konservativ mit bis zu 100 Durchläufen angesetzt.

## Listen und Schleifen über Einträge

Die Kategorie **Listen** enthält Bausteine zum Erstellen, Aufnehmen und Verarbeiten von Listen:

- **Liste erstellen:** Name und Werte angeben, zum Beispiel `Werte` mit `Anzeige; Akku; Apps`. Der Stift im Block öffnet einen Editor mit einer Zeile pro Wert. Semikolons und Zeilenumbrüche trennen Einträge; leere Einträge entfallen, doppelte Werte bleiben erhalten. Semikolons innerhalb eines einzelnen Werts werden daher nicht unterstützt.
- **Listentexte lesen:** Sammelt Texte aus der aktuellen Geräteansicht in einer benannten Liste. Filterbar nach „Text enthält“, gemeinsamer Element-ID oder Elementtyp, z. B. `android.widget.TextView`. Ein leerer „Text enthält“-Filter liest alle sichtbaren Textknoten. Es wird nicht automatisch gescrollt und es findet keine OCR statt.
- **Für jeden Eintrag:** Führt die eingeschlossenen Befehle einmal pro Listenwert aus. Der Listenname muss mit dem Erstellen-/Lesen-Baustein übereinstimmen, der vorher ausgeführt wird, oder dem Namen einer gespeicherten Liste.
- **Eintrag eingeben:** Gibt den aktuellen Listenwert in das fokussierte Textfeld ein.
- **Eintrag antippen:** Sucht ein Element, dessen Text, ID oder Beschreibung dem aktuellen Listenwert entspricht, und tippt es an.

Beispiel: `App Einstellungen öffnen → Liste Werte erstellen → Für jeden Eintrag in Werte → Eintrag antippen → Zurück`. Die letzten beiden Befehle werden in die Schleife gesteckt. Unter **Listen → Listenbeispiel laden** lässt sich dieser Ablauf im Demo-Modus ausprobieren. Zusätzliche Projektdateien: `examples/liste-durchlaufen.json` und `examples/bildschirmliste-auslesen.json`.

Eine Liste enthält maximal 500 Werte mit jeweils höchstens 2000 Zeichen. Gelesene Listen behalten die Reihenfolge der Android-UI-Hierarchie. Die Schleife arbeitet mit einer Kopie der Liste zu ihrem Beginn; Navigation und spätere Listenänderungen verändern diesen Durchlauf nicht. Eine leere Liste überspringt den Schleifeninhalt. Bei verschachtelten Schleifen bezeichnet „aktueller Eintrag“ den Wert der innersten Schleife; danach ist der äußere Wert wieder verfügbar. Listen werden je Fall lokal unter `data/cases/<Fall>/lists.json` gespeichert und stehen über mehrere Läufe und Neustarts hinweg zur Verfügung. Listen aus älteren Versionen (`data/lists.json`) übernimmt beim ersten Start der erste Fall „Allgemein“. Ein gleicher Listenname ersetzt die bisherige Liste. Der Python-Export übernimmt gespeicherte Listenwerte und unterstützt auch Aufnahme und Scroll-Suche. Die maximale Schrittzahl wird konservativ berechnet; bei Bildschirm-Listen werden dabei bis zu 500 Einträge angenommen.

## Ganze Bildschirmlisten aufnehmen und durchsuchen

Über der Handyansicht gibt es **↓ Bildschirmliste aufnehmen**. Öffne auf dem Handy die gewünschte Liste und vergib einen Namen. Mit **Listenelement auswählen** lädst du ein Gerätebild in den Aufnahmedialog. Klicke dort auf einen vollständigen Eintrag. Die Auswahl bedient das Handy nicht. Ein Rahmen zeigt den gewählten Bereich; rechts siehst du die passenden Einträge als Vorschau. Über **Welcher Bereich ist ein vollständiger Eintrag?** kannst du zwischen einer Textzeile und einem größeren, umschließenden Element wechseln. Wähle beispielsweise die ganze Mail-Karte statt nur den Betreff. Erst nach der Auswahl lässt sich die Aufnahme starten.

Das Muster verwendet Elementtyp, Element-ID und die Position in der UI-Hierarchie, nicht den Text oder die Bildschirmkoordinaten des Beispiels. Es wird im ausgewählten Listenbereich nach gleich aufgebauten Elementen gesucht. Hat eine Karte bereits einen eigenen zusammenfassenden Text oder eine Beschreibung, wird dieser einmal übernommen; andernfalls werden ihre untergeordneten Texte zu einem mehrzeiligen Eintrag zusammengefasst. Diese Texte erscheinen nicht zusätzlich als einzelne Listeneinträge. Prüfe die Vorschau, insbesondere bei unterschiedlichen Kartenlayouts innerhalb derselben Liste. Nach Änderungen der App-Oberfläche kann eine erneute Auswahl erforderlich sein.

Die Aufnahme scrollt zuerst ganz zum Anfang, dann abschnittsweise nach unten, bis sich die Ansicht bei zwei aufeinanderfolgenden Wischbewegungen nicht mehr verändert. **Stopp** bricht die Aufnahme ab. Erst eine vollständig beendete Aufnahme ersetzt eine vorhandene Liste; bei Abbruch oder Fehler bleibt diese erhalten. Ein fehlender oder nicht eindeutiger ausgewählter Listenbereich führt zu einem Fehler, statt automatisch eine andere Liste aufzunehmen.

Auch im Baustein **Bildschirmliste aufnehmen** kannst du über das Auswahl-Symbol oder das Rechtsklick-Menü ein Listenelement festlegen. Das Muster bleibt beim Speichern/Laden des Projekts erhalten und wird in den Python-Export übernommen. Die Aufnahmeart **Einzelne Texte mit Filter** bietet weiterhin die bisherige Erfassung einzelner Textknoten. Zusammengefasste Einträge sind Listenwerte; zum späteren Antippen muss der Wert zu einem tatsächlichen Text bzw. einer Beschreibung auf dem Gerät passen.

**Listen ansehen** zeigt die gespeicherten Werte mit Anzahl. Mit **Als Schleife verwenden** wird ein passender „Für jeden Eintrag“-Baustein eingefügt. Derselbe Listenname kann auch direkt in einem Schleifenbaustein eingetragen werden. Der Baustein **Bildschirmliste aufnehmen** führt die Aufnahme als Teil eines Ablaufs aus.

Bei der Aufnahme einzelner Texte wird der größte von Android gemeldete scrollbare Bereich verwendet, sonst der Bildschirm ohne Systemleisten. Sie liest zugängliche Textknoten (keine OCR); Titel und Untertitel können dabei getrennte Werte sein. Gleiche Werte werden bei beiden Aufnahmearten einmal gespeichert, damit überlappende Abschnitte keine Duplikate liefern. Identisch beschriftete unterschiedliche Einträge sind dadurch nicht unterscheidbar. Die Grenzen sind 500 unterschiedliche Einträge und jeweils 100 Wischbewegungen zum Anfang bzw. Ende; danach gibt es eine Fehlermeldung statt einer unvollständig gespeicherten Liste.

**Text durch Scrollen suchen** sucht einen festen Text, **Eintrag durch Scrollen suchen** den aktuellen Listenwert innerhalb einer Schleife. Beide scrollen bei jedem Aufruf zuerst nach oben und anschließend nach unten. Wählbar sind exakte Übereinstimmung und „enthalten ist“ (Groß-/Kleinschreibung wird berücksichtigt). Bei einem Treffer bleibt der Bildschirm dort stehen; zum Antippen anschließend „Element antippen“ bzw. „Eintrag antippen“ hinzufügen. Ohne Treffer am Ende wird der Ablauf mit einer Meldung angehalten.

Beispiel: `Für jeden Eintrag in Bildschirmliste → Eintrag durch Scrollen suchen → Eintrag antippen → Zurück`. Die drei letzten Befehle gehören in den Schleifenrumpf. Das Zurück muss wieder zur ursprünglichen Liste führen.

## Echtes Android-Gerät verbinden

- In den Android-Entwickleroptionen **USB-Debugging** einschalten.
- Per USB-Datenkabel verbinden und die Debugging-Anfrage auf dem Telefon bestätigen.
- In der Geräteansicht auf den Gerätenamen klicken, gegebenenfalls „Erneut suchen“ wählen und das Gerät verbinden.
- Bei `unauthorized` fehlt die Bestätigung auf dem Telefon; bei `offline` Kabel/Verbindung prüfen.
- Beim ersten Verbinden kann uiautomator2 seinen Automatisierungsdienst auf dem Gerät bereitstellen.

ADB wird unter Windows durch die installierte `adbutils`-Abhängigkeit mitgeliefert. Je nach Gerät werden zusätzliche USB-Treiber benötigt. Die App verändert keine Treibereinstellungen.

Der Gerätename wird direkt über ADB gelesen. Die für den Verbindungsaufbau unnötige uiautomator2-Abfrage `device.info` wird vermieden, da sie auf neueren Android-Builds mit `ApplicationSharedMemory not initialized` scheitern kann. Bildschirmansicht und Elementerkennung verwenden weiterhin uiautomator2.

Die Live-Ansicht verwendet Screenshots ungefähr einmal pro Sekunde; sie ist kein Videostream. Außerhalb des Auswahlmodus kannst du das Gerät durch Klicken direkt bedienen. Home, Zurück und Letzte Apps sind unter dem Gerätebild erreichbar. Drehung und Auflösung werden anhand der Bilder berücksichtigt.

## Bausteine

| Baustein | Funktion |
| --- | --- |
| App öffnen | Gewählte Android-App starten |
| Element antippen | Nach Text, eindeutiger ID oder Beschreibung suchen und tippen; maximal 10 Sekunden warten |
| Position antippen | Relative Bildschirmposition in Prozent antippen |
| Text eingeben | Text in das fokussierte Eingabefeld schreiben; vorhandenen Inhalt ersetzen |
| Wischen | Nach oben, unten, links oder rechts wischen |
| Warten | Eine festgelegte Zeit warten |
| Auf Element warten | Bis zu einem einstellbaren Zeitlimit auf ein Element warten |
| Wiederholen | Eingeschlossene Schritte 1–100 Mal wiederholen |
| Wenn Element da ist | Je nach Sichtbarkeit den Dann- oder Sonst-Zweig ausführen |
| Gerätetaste drücken | Home, Zurück, Letzte Apps, Enter oder Lautstärke |
| Screenshot auf PC speichern | Gerätebild lokal auf dem PC unter `outputs/` speichern, mit vollständigem Speicherort und Bildlink im Protokoll |

Der Demo-Modus simuliert die Navigation in Einstellungen, Antippen, Texteingabe, Home und Zurück. Wischbewegungen und weitere Systemtasten verändern die Demo nicht. Screenshots der Demo sind SVG-Dateien; echte Gerätebilder sind PNG-Dateien. Android-Apps mit geschützten Bildschirmansichten oder ohne zugängliche UI-Elemente können die Ansicht bzw. Elementerkennung einschränken.

## uiautodev

„In uiautodev untersuchen“ startet den offiziellen Inspektor als separaten lokalen Python-Prozess unter <http://127.0.0.1:20242>. Er arbeitet mit echten angeschlossenen Geräten, nicht mit der Studio-Demo. Falls der Browser das neue Fenster blockiert, steht ein anklickbarer Link bereit.

Der Inspektor wird mit `--offline` gestartet. Beim ersten Aufruf lädt uiautodev seine Oberfläche von seinem Anbieter und cached sie; dafür kann Internetzugang nötig sein. Droid Studios eigener Editor lädt seine Dateien immer lokal. Startprobleme stehen in `uiautodev.log`. Ein schon anderweitig belegter Port wird nicht übernommen oder beendet.

## Entwicklung und Prüfungen

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
node --check web/app.js
node tests/test_block_values.cjs
```

Die Tests prüfen verschachtelte Abläufe, Bedingungen, Abbruch, fehlende Elemente, Python-Export einschließlich Texteingaben mit Anführungszeichen, normalisierte Gerätekoordinaten, eindeutige Selektoren und lokale HTTP-Endpunkte. Für einen vollständigen Hardwaretest muss ein Android-Gerät autorisiert verbunden sein.

Die Blöcke werden in eine begrenzte JSON-Befehlssprache übersetzt und auf dem Server validiert. Es wird kein frei eingegebener Python-Code ausgeführt. Abläufe sind auf 500 Befehlsblöcke, 12 Verschachtelungsebenen und maximal 10.000 ausgeführte Schritte begrenzt. Gerätewechsel und zusätzliche Läufe sind während eines Laufs gesperrt. Die lokale Schnittstelle prüft Host und Origin; Änderungen benötigen zusätzlich ein Sitzungstoken.

## Aufbau

- `app.py`: Startpunkt
- `automator/server.py`: lokaler HTTP-Server, Geräteverwaltung, Inspektorstart
- `automator/devices.py`: Android- und Demo-Adapter
- `automator/program.py`: Validierung und Python-Export
- `automator/runner.py`: Ablaufsteuerung, Stopp, Protokoll
- `automator/backup.py`: „Liste sichern“ – Einträge öffnen, durchblättern, Bildschirmabschnitte abgleichen
- `automator/evidence.py`: Sicherungsordner mit Screenshots, SHA-256-Hashliste, CSV und HTML-Bericht
- `automator/cases.py`, `automator/storage.py`: Fälle, Listen je Fall, Ablage
- `web/`: deutsche Oberfläche und Blockly-Integration
- `tests/`: automatisierte Tests ohne Hardware

Referenzen: [uiautomator2](https://github.com/openatx/uiautomator2), [uiautodev](https://github.com/codeskyblue/uiautodev), [Blockly-Serialisierung](https://docs.blockly.com/guides/configure/serialization/).

## Sicherungsberichte

Der Bericht stellt Bildschirmtexte neben die zugehörigen Screenshots. Originaltexte und technische Angaben bleiben aufklappbar. Bei erkannten WhatsApp-Ansichten werden Bedienleisten und bestimmte zusammengehörige Medien-Schaltflächen für die Lesefassung ausgeblendet. Nachrichtentexte werden nicht umgeschrieben; überlappende Aufnahmen bleiben getrennt. Absender und fehlende Texte werden nicht geraten.

Für eine vorhandene Sicherung kann eine separate Lesefassung erzeugt werden:

```powershell
.\.venv\Scripts\python.exe tools/report_reading_copy.py "Sicherungen/Fallordner/Sicherungsordner"
```

Das prüft zunächst die ursprüngliche Hashliste und schreibt `bericht-lesefassung.html`. Originalbericht, Sicherungsdaten und Hashliste werden nicht verändert. Die zusätzliche Lesefassung ist nicht Teil der ursprünglichen Hashliste und erscheint in der Ablage neben dem Originalbericht.
