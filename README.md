# Droid Studio (ADBAutomator)

[Deutsch](README.de.md) · **English** · [![Tests](https://github.com/AndroidIosForensik/ADBAutomator/actions/workflows/tests.yml/badge.svg)](https://github.com/AndroidIosForensik/ADBAutomator/actions/workflows/tests.yml)

Local Python application for the forensic capture of Android screen content and for Android automations built from Scratch-like Blockly blocks. „Liste sichern“ (*back up list*) opens every entry of a list (for example all chats), pages through it completely and documents every page with a screenshot, its visible text, a report and SHA-256 hashes. The user interface runs in the browser; device actions are performed by `uiautomator2` on your computer.

The user interface is in German. In this README, German UI labels are quoted as „Label“ followed by an English translation.

## Download

Ready-to-run Windows version (Windows 10/11, 64-bit, no installation needed): **[Releases](https://github.com/AndroidIosForensik/ADBAutomator/releases/latest)**. Download `Droid-Studio.exe` and double-click it – on first start it unpacks itself into a folder „Droid Studio“ next to it. Alternatively unpack the ZIP file and start `Droid Studio.exe` inside it.

## Running on Windows

If the environment is already set up: **double-click `start.bat`**. The interface opens at <http://127.0.0.1:8765>.

For a new installation:

1. Install Python 3.11 or newer, Node.js with npm, and Git.
2. Get the repository: `git clone https://github.com/AndroidIosForensik/ADBAutomator.git`
3. Run `setup.bat` in the folder. It installs the Python libraries into `.venv` and Blockly locally into `node_modules`.
4. Open `start.bat`. Keep the console window open; Ctrl+C stops the app and any uiautodev inspector it started.

Alternatively:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
npm.cmd ci --ignore-scripts
.\.venv\Scripts\python.exe app.py
```

### Without installation: exe and portable ZIP

```powershell
.\.venv\Scripts\python.exe tools\build_portable.py
.\.venv\Scripts\python.exe tools\test_portable.py
```

This creates two variants in `dist/`, both with bundled Python, Blockly and ADB:

- `Droid-Studio.exe` – a single file. On first start it unpacks itself into a folder `Droid Studio` next to it and starts the app; later starts launch directly. After an update only program files are replaced; `Sicherungen` (backups) and `data` are kept.
- `Droid-Studio-Windows-x64.zip` – for unpacking, e.g. onto a USB stick; double-click `Droid Studio.exe` inside it.

Each file comes with a `.sha256` checksum. The exe is not code-signed; Windows SmartScreen may warn on first start („Weitere Informationen“ / *More info* → „Trotzdem ausführen“ / *Run anyway*). The starter is compiled during the build from `tools/launcher/DroidStudio.cs` with the C# compiler that ships with the .NET Framework.

Use `app.py --port 8766` for a different port. `--no-browser` prevents the browser from opening automatically. The server listens on `127.0.0.1` only.

## Backing up a list (forensic documentation)

„Liste sichern“ opens every entry of a list on the device, pages through its content completely and saves every page as a screenshot – for example all chats of a messenger with their complete history.

1. **Choose a case:** The active case („Fall“) is shown at the top next to the workflow name. Create or switch to a case with case number, examiner and note there. Lists and backups are stored separately per case.
2. **Open the list:** Open the desired list on the device, for example the chat overview.
3. Press **„Liste sichern“** in the device panel, „Gerätebild laden“ (*load device picture*) and move the mouse over a complete entry. The frame and the current entry appear immediately; a click fixes the selection. Detection prefers repeated entry containers in the Android XML hierarchy. Selecting does not tap anything on the device.
4. **Settings:** Give the backup a name and choose how each entry is paged through: „Vom Ende zum Anfang“ (*from end to start*) for chat histories (newest message first) or „Vom Anfang zum Ende“ (*from start to end*) for e-mails and profiles. „Höchstens Seiten je Eintrag“ (*maximum pages per entry*) limits very long content; a truncated entry is marked „unvollständig“ (*incomplete*).
5. **Start the backup.** Progress is shown at the top. „Pause“ stops between two entries, „Nächster Eintrag“ (*next entry*) backs up exactly one more, „Fortsetzen“ (*resume*) continues. „Stopp“ ends the backup; everything saved so far is kept together with a report.

Entries are tapped at their position on screen, not searched by text. This makes entries consisting of several texts (name, message, time) work, and entries with identical names stay separate. Scrolling is done without momentum: the finger rests briefly before lifting so that Android does not fling past entries. Every new screen section is aligned with the previous one; if the list cannot be continued without a gap, the report contains a warning.

**Important:** Put the device into airplane mode first. Otherwise the list may change during the backup, and messengers send read receipts when a chat is opened.

Each backup gets its own folder under `Sicherungen/<case>/<timestamp>_<name>/`:

- `E0001_<entry>/E0001_S0001.png` … the screenshots per entry and page, plus `E0001_S0001.txt` with the page's visible text
- `bericht.html` (report) with case, device (manufacturer, model, Android version, serial number, device time), timestamps, status and the text of each page next to its screenshot
- `eintraege.csv` (semicolon-separated, for Excel) and `sicherung.json` (machine-readable)
- `hashes.sha256` with the SHA-256 values of all files, verifiable with `sha256sum -c hashes.sha256`. The checksum of this hash list is shown in the log and in the „Ablage“ (*archive*).

The **„Ablage“** shows all backups and lists of the active case with progress, status per entry, thumbnails, page text and links to every page. From there you can open the report, CSV and folder, rename lists, export them as CSV or use them as a loop, and delete backups and lists. „Nur Listentexte aufnehmen …“ (*capture list texts only*) records only the texts of a list without opening entries.

In the assistant, „Als Baustein einfügen“ (*insert as block*) creates a „Liste sichern“ block that runs as part of a workflow with „Starten“ (*start*). This block is not exported to Python because the report and hashes are only produced in Droid Studio.

Without a phone everything can be tried with the demo device: choose „Demo-Chats auf dem Demo-Gerät öffnen“ (*open demo chats on the demo device*) in the assistant. The demo list deliberately contains two identical chats and unread messages.

## Backup reports

The report places the screen texts next to the corresponding screenshots. Original texts and technical details can be expanded. For recognised WhatsApp views, toolbars and certain media buttons that belong together are hidden in the reading view. Message texts are never rewritten; overlapping captures stay separate. Senders and missing texts are not guessed.

A separate reading copy can be created for an existing backup:

```powershell
.\.venv\Scripts\python.exe tools/report_reading_copy.py "Sicherungen/CaseFolder/BackupFolder"
```

It first verifies the original hash list and then writes `bericht-lesefassung.html`. The original report, backup data and hash list are not changed. The additional reading copy is not part of the original hash list and appears in the „Ablage“ next to the original report.

## Your first workflow without programming

1. **Try the demo:** The default workflow opens Settings, waits, taps „Anzeige“ (*Display*) and saves a screenshot. „Starten“ runs it. The demo does not control a real phone.
2. **Add blocks:** Click a block on the left to append it at the end, or drag it onto the workspace and dock it to another block. Only blocks connected to „Wenn gestartet“ (*when started*) belong to the workflow; loose blocks must be connected or removed before starting.
3. **Change values:** Click directly on fields and drop-downs in the blocks. More blocks can be placed inside loops and in both branches of a condition.
4. **Pick an element:** Press „Element auswählen“ (*select element*) and click the desired element on the device picture. The preview pauses while selecting. Unique element IDs, descriptions or texts are used; without a suitable match a relative screen position is inserted.
5. **Take over an app:** Open the desired app on the phone and press „Geöffnete App übernehmen“ (*use opened app*). This inserts its launch command without typing a package name. The app block also offers some well-known apps; they must be installed on the phone.
6. **Start:** The active block is highlighted. The log shows steps, errors and links to screenshots. „Stopp“ interrupts waits immediately; a device request already in progress has to return first.
7. **Save:** The current draft is stored in the browser's local storage. In the „Projekt“ menu, „Als Datei speichern“ (*save as file*) additionally downloads a JSON project file, which „Datei öffnen“ (*open file*) loads again. „Neuer Ablauf“ (*new workflow*) or „Beispiel laden“ (*load example*) replaces the draft after confirmation. Save important projects as files first.
8. **Export Python:** „Python-Code“ shows the workflow as readable Python code that can be downloaded as `.py`. Exporting from the demo requires a real Android device later.

`examples/schleife-und-bedingung.json` is an additional project showing nested loops and an if/else condition.

## Checking a workflow step by step

„Schrittweise“ (*step by step*) stops before the first block. The highlighted block is the next command; „Nächster Schritt“ (*next step*) runs it and stops again before the following block. Loops and conditions are entered one by one as well: a step on a loop does not yet run its whole body. Above the workspace you see the next command and, inside a list loop, the current list value. Waits and scroll searches run completely as one command each.

„Fortsetzen“ (*resume*) runs the rest automatically. „Pause“ stops a running workflow before the next block once the current command has finished. „Stopp“ also ends a paused run. While a run is paused, editing, direct device actions and switching devices stay locked. After a change the workflow must be restarted.

For „Anzeige“ the demo shows the entries Brightness, Dark theme and Screen timeout. Tapping opens a simulated detail view; „Zurück“ (*back*) returns to the actual previous page. For a saved list of these three entries the „Anzeige“ page must be open before starting, for example with `open app Settings → tap element Anzeige → for each entry …`. The list itself does not navigate to its origin page.

## Variables and value blocks

The **„Variablen“** (*variables*) category contains „Variable setzen“ (*set variable*), „Variable ändern“ (*change variable*), „Variablenwert“ (*variable value*), „Textwert“ (*text value*), „Zahlenwert“ (*number value*) and „Aktueller Listeneintrag“ (*current list entry*). „Variable setzen“ stores a text or a number under a freely chosen name. „Variable ändern“ adds a number; negative values subtract. Set the variable first, e.g. `Zähler = 0`. Names must match; upper and lower case are distinguished.

Plug the „Variablenwert“ block into a matching value input. Text input, element search, if-element-exists, scroll search and list filter accept text or number values. Wait time, timeout and repeat count require numbers. The additional inputs are labelled, for example, „Suchwert stattdessen“ (*search value instead*) or „Sekunden stattdessen“ (*seconds instead*): a plugged-in value replaces the corresponding fixed field. Without a plugged-in value the field still applies, so existing projects keep working. Value blocks can be dragged onto the workspace and docked; a click in the palette inserts a value into a free matching input of the selected block if possible.

Inside a list loop, „Aktueller Listeneintrag“ can also be assigned to a variable; its value then remains available for the rest of the run. All variables start empty on every new run. „Variablen im aktuellen Lauf“ (*variables in the current run*) shows the values in step mode and after completion. Accessing a variable before it is set, text in a number field, or a value outside the allowed limits stops the workflow at the affected block. Numbers in text fields are used as text; text such as „3“ is not converted into a number automatically.

„Variablen → Variablenbeispiel laden“ (*load variables example*) provides a workflow that copies a text and increments a counter three times without operating the device. The file is `examples/variablen.json`. Variables and connected value blocks are saved with the project and supported by the Python export. Up to 2000 characters and numbers between −10¹² and 10¹² are allowed. Waits and loops keep their existing limits. For the up-front check of the maximum number of steps, a variable repeat is conservatively counted with up to 100 iterations.

## Lists and loops over entries

The **„Listen“** (*lists*) category contains blocks for creating, capturing and processing lists:

- **„Liste erstellen“** (*create list*): give a name and values, e.g. `Werte` with `Anzeige; Akku; Apps`. The pencil in the block opens an editor with one line per value. Semicolons and line breaks separate entries; empty entries are dropped, duplicate values are kept. Semicolons within a single value are therefore not supported.
- **„Listentexte lesen“** (*read list texts*): collects texts from the current device view into a named list. Filterable by „Text enthält“ (*text contains*), common element ID or element type, e.g. `android.widget.TextView`. An empty „Text enthält“ filter reads all visible text nodes. There is no automatic scrolling and no OCR.
- **„Für jeden Eintrag“** (*for each entry*): runs the enclosed commands once per list value. The list name must match the create/read block that runs before it, or the name of a saved list.
- **„Eintrag eingeben“** (*type entry*): types the current list value into the focused text field.
- **„Eintrag antippen“** (*tap entry*): looks for an element whose text, ID or description equals the current list value and taps it.

Example: `open app Settings → create list Werte → for each entry in Werte → tap entry → back`. The last two commands go into the loop. „Listen → Listenbeispiel laden“ (*load list example*) lets you try this in demo mode. Additional project files: `examples/liste-durchlaufen.json` and `examples/bildschirmliste-auslesen.json`.

A list holds at most 500 values with up to 2000 characters each. Captured lists keep the order of the Android UI hierarchy. A loop works on a copy of the list taken when it starts; navigation and later list changes do not affect that run. An empty list skips the loop body. In nested loops, „current entry“ refers to the innermost loop; afterwards the outer value is available again. Lists are stored locally per case under `data/cases/<case>/lists.json` and remain available across runs and restarts. Lists from older versions (`data/lists.json`) are taken over by the first case „Allgemein“ (*general*) on first start. A list with the same name replaces the previous one. The Python export includes saved list values and also supports capture and scroll search. The maximum number of steps is calculated conservatively; screen lists are assumed to have up to 500 entries.

## Capturing and searching whole screen lists

„Bildschirmliste aufnehmen“ (*capture screen list*) is available above the phone view. Open the desired list on the phone and give it a name. „Listenelement auswählen“ (*select list element*) loads a device picture into the capture dialog. Move the mouse over a complete entry there: a frame immediately shows the detected area; on the right you see the current entry and the matching entries as a preview. A click fixes the selection. Selecting does not operate the phone. „Welcher Bereich ist ein vollständiger Eintrag?“ (*which area is a complete entry?*) lets you switch between a text line and a larger enclosing element – choose, for example, the whole mail card instead of just the subject. Capturing can only start after a selection.

The pattern uses element type, element ID and the position in the UI hierarchy, not the text or the screen coordinates of the example. Equally structured elements are searched within the selected list area. If a card already has its own summarising text or description, it is taken once; otherwise its child texts are combined into one multi-line entry. These texts do not additionally appear as separate list entries. Check the preview, especially when one list contains different card layouts. After changes to an app's interface a new selection may be necessary.

Capturing first scrolls to the very top, then down section by section until the view does not change for two consecutive swipes. Only complete entries are taken; fragments of entries cut off at the edge are ignored. „Stopp“ cancels the capture. Only a fully completed capture replaces an existing list; on cancellation or error it is kept. A missing or ambiguous selected list area causes an error instead of silently capturing a different list.

In the „Bildschirmliste aufnehmen“ block you can also choose a list element via the selection icon or the context menu. The pattern is kept when saving/loading the project and included in the Python export. The capture mode „Einzelne Texte mit Filter“ (*single texts with filter*) still offers the previous capture of individual text nodes. Combined entries are list values; to tap them later, the value must match an actual text or description on the device.

The „Ablage“ shows the saved values with their count. „Als Schleife verwenden“ (*use as loop*) inserts a matching „Für jeden Eintrag“ block. The same list name can also be entered directly in a loop block. The „Bildschirmliste aufnehmen“ block performs the capture as part of a workflow.

When capturing single texts, the largest scrollable area reported by Android is used, otherwise the screen without system bars. It reads accessible text nodes (no OCR); titles and subtitles may become separate values. Identical values are stored once in both capture modes so that overlapping sections do not produce duplicates; differently located entries with identical labels can therefore not be distinguished. The limits are 500 distinct entries and 100 swipes each towards the start and the end; beyond that an error is shown instead of saving an incomplete list.

„Text durch Scrollen suchen“ (*find text by scrolling*) searches for a fixed text, „Eintrag durch Scrollen suchen“ (*find entry by scrolling*) for the current list value inside a loop. Both first scroll up and then down on every call. Exact match and „enthalten ist“ (*contained*) are available (case-sensitive). On a match the screen stays there; add „Element antippen“ (*tap element*) or „Eintrag antippen“ afterwards to tap it. Without a match at the end the workflow stops with a message.

Example: `for each entry in Bildschirmliste → find entry by scrolling → tap entry → back`. The last three commands belong in the loop body. „Back“ must lead back to the original list.

## Connecting a real Android device

- Enable **USB debugging** in the Android developer options.
- Connect with a USB data cable and confirm the debugging request on the phone.
- In the device panel click the device name, choose „Erneut suchen“ (*search again*) if necessary and connect the device.
- `unauthorized` means the confirmation on the phone is missing; for `offline` check cable/connection.
- On first connection uiautomator2 may install its automation service on the device.

On Windows, ADB is provided by the installed `adbutils` dependency. Some devices need additional USB drivers. The app does not change any driver settings.

The device name is read directly via ADB. The uiautomator2 query `device.info`, which is not needed to connect, is avoided because it can fail with `ApplicationSharedMemory not initialized` on newer Android builds. The app in the foreground is read from the Android window manager because uiautomator2 can report a background app on Android 17. Screen view and element detection still use uiautomator2.

The live view uses screenshots about once per second; it is not a video stream. Outside selection mode you can operate the device by clicking directly. Home, Back and Recent apps are available below the device picture. Rotation and resolution are taken from the images.

## Blocks

| Block | Function |
| --- | --- |
| App öffnen (*open app*) | Start the selected Android app |
| Element antippen (*tap element*) | Find by text, unique ID or description and tap; waits up to 10 seconds |
| Position antippen (*tap position*) | Tap a relative screen position in percent |
| Text eingeben (*type text*) | Write text into the focused input field, replacing existing content |
| Wischen (*swipe*) | Swipe up, down, left or right |
| Warten (*wait*) | Wait for a fixed time |
| Auf Element warten (*wait for element*) | Wait for an element up to an adjustable timeout |
| Wiederholen (*repeat*) | Repeat the enclosed steps 1–100 times |
| Wenn Element da ist (*if element exists*) | Run the then or else branch depending on visibility |
| Gerätetaste drücken (*press device key*) | Home, Back, Recent apps, Enter or volume |
| Screenshot auf PC speichern (*save screenshot on PC*) | Save the device picture locally under `outputs/`, with the full path and an image link in the log |
| Liste sichern (*back up list*) | Open every entry of the selected list, page through it and document it (see above) |

The demo mode simulates navigation in Settings, taps, text input, Home and Back, and a scrollable demo chat list. Other system keys do not change the demo. Demo screenshots are SVG files; real device pictures are PNG files. Android apps with protected screens or without accessible UI elements can limit the view or element detection.

## uiautodev

„In uiautodev untersuchen“ (*inspect in uiautodev*) starts the official inspector as a separate local Python process at <http://127.0.0.1:20242>. It works with real connected devices, not with the studio demo. If the browser blocks the new window, a clickable link is provided.

The inspector is started with `--offline`. On first use uiautodev loads its interface from its provider and caches it; this may require internet access. Droid Studio's own editor always loads its files locally. Start-up problems are written to `uiautodev.log`. A port already used by something else is neither taken over nor terminated.

## Development and tests

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
node --check web/app.js
node tests/test_block_values.cjs
```

The tests cover nested workflows, conditions, cancellation, missing elements, Python export including text input with quotes, normalised device coordinates, unique selectors, local HTTP endpoints, and the list backup (complete and gap-free traversal, identical entries, evidence folder, hashes, reports). A full hardware test requires an authorised Android device.

Blocks are translated into a restricted JSON command language and validated on the server. No freely entered Python code is executed. Workflows are limited to 500 command blocks, 12 nesting levels and at most 10,000 executed steps. Switching devices and additional runs are locked during a run. The local interface checks Host and Origin; changes additionally require a session token. Page and server compare a version number so that an outdated running server is detected instead of failing silently.

## Structure

- `app.py`: entry point
- `automator/server.py`: local HTTP server, device management, inspector start
- `automator/devices.py`: Android and demo adapters
- `automator/program.py`: validation and Python export
- `automator/runner.py`: workflow control, stop, log
- `automator/backup.py`: „Liste sichern“ – open entries, page through them, align screen sections
- `automator/evidence.py`: backup folder with screenshots, page texts, SHA-256 hash list and CSV
- `automator/report.py`, `automator/report_text.py`: HTML report and reading view
- `automator/cases.py`, `automator/storage.py`: cases, lists per case, archive
- `web/`: German user interface and Blockly integration
- `tools/`: portable build, Windows starter, reading copy
- `tests/`: automated tests without hardware

References: [uiautomator2](https://github.com/openatx/uiautomator2), [uiautodev](https://github.com/codeskyblue/uiautodev), [Blockly serialization](https://docs.blockly.com/guides/configure/serialization/).
