"""Build a relocatable Windows x64 ZIP from the working, installed environment."""
import hashlib
from importlib.metadata import distributions
import json
import platform
from pathlib import Path
import shutil
import struct
import sys
import tempfile
from zipfile import ZipFile, ZIP_DEFLATED


ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / 'dist'


def copy(source, target):
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)


def main():
    if sys.platform != 'win32' or struct.calcsize('P') != 8 or platform.machine().lower() not in ('amd64', 'x86_64'):
        raise SystemExit('Build with the tested Windows x64 Python environment.')
    DIST.mkdir(exist_ok=True)
    base = Path(sys.base_prefix)
    tag = f'python{sys.version_info.major}{sys.version_info.minor}'
    archive = DIST / 'Droid-Studio-Windows-x64.zip'
    with tempfile.TemporaryDirectory(prefix='portable-build-') as temp:
        root = Path(temp) / 'Droid Studio'
        runtime = root / 'runtime'
        runtime.mkdir(parents=True)
        # A ._pth file isolates this runtime from installed Python and PYTHONPATH.
        # No "import site": it would add the Windows user's own site-packages
        # (%APPDATA%\Python\...), whose packages could then affect the app.
        for name in ('python.exe', 'python3.dll', tag + '.dll', 'vcruntime140.dll', 'vcruntime140_1.dll', 'LICENSE.txt'):
            copy(base / name, runtime / name)
        for source in (base / 'DLLs').iterdir():
            if source.suffix not in ('.pyd', '.dll'):
                continue
            if source.stem.startswith(('_test', '_ctypes_test', '_tkinter', 'tcl', 'libtommath')):
                continue
            copy(source, runtime / 'DLLs' / source.name)
        excluded = {'site-packages', '__pycache__', 'test', 'tests', 'idlelib', 'tkinter', 'turtledemo', 'ensurepip', 'venv'}
        with ZipFile(runtime / (tag + '.zip'), 'w', ZIP_DEFLATED, compresslevel=9) as stdlib:
            for source in sorted((base / 'Lib').rglob('*')):
                relative = source.relative_to(base / 'Lib')
                if source.is_file() and not excluded.intersection(relative.parts) and source.suffix not in ('.pyc', '.pyo'):
                    stdlib.write(source, relative.as_posix())
        (runtime / (tag + '._pth')).write_text(
            f'{tag}.zip\n.\nDLLs\nsite-packages\n..\n', encoding='utf-8')

        # Keep package resources (ADB, APKs, DLLs, schemas) and license metadata.
        # The source environment contains only the application's dependencies + pip.
        versions = {}
        for distribution in distributions():
            name = distribution.metadata['Name']
            if name.lower() == 'pip':
                continue
            versions[name] = distribution.version
            location = Path(distribution.locate_file('')).resolve()
            for entry in distribution.files or ():
                source = Path(distribution.locate_file(entry)).resolve()
                if not source.is_relative_to(location) or not source.is_file():
                    continue
                relative = source.relative_to(location)
                if {'__pycache__', 'tests', 'test'}.intersection(relative.parts):
                    continue
                if source.suffix in ('.pyc', '.pyo', '.pyi', '.h', '.c', '.pxd', '.pyx', '.pxi'):
                    continue
                if source.name in ('direct_url.json', 'INSTALLER', 'REQUESTED'):
                    continue
                copy(source, runtime / 'site-packages' / relative)

        copy(ROOT / 'app.py', root / 'app.py')
        copy(ROOT / 'tools/report_reading_copy.py', root / 'tools/report_reading_copy.py')
        for directory, pattern in [('automator', '*.py'), ('web', '*'), ('examples', '*.json')]:
            for source in (ROOT / directory).glob(pattern):
                if source.is_file():
                    copy(source, root / directory / source.name)
        blockly = Path('node_modules/blockly')
        for name in ['blockly_compressed.js', 'msg/de.js']:
            copy(ROOT / blockly / name, root / blockly / name)
        for source in (ROOT / blockly / 'media').iterdir():
            if source.suffix in ('.svg', '.png', '.gif', '.cur'):
                copy(source, root / blockly / 'media' / source.name)
        copy(ROOT / 'tools/portable-licenses/Blockly-LICENSE.txt', root / blockly / 'LICENSE.txt')
        (root / 'LIZENZEN.txt').write_text(
            'Mitgelieferte Komponenten\n\nPython: runtime/LICENSE.txt\n'
            'Blockly 12.3.1: node_modules/blockly/LICENSE.txt\n'
            'Die Python-Bibliotheken enthalten ihre Lizenzen in runtime/site-packages/*dist-info.\n\n'
            + f'Python {platform.python_version()} (Windows x64)\n'
            + '\n'.join(f'{name} {version}' for name, version in sorted(versions.items())) + '\n', encoding='utf-8')
        (root / 'Starten.bat').write_bytes(
            b'@echo off\r\nsetlocal\r\ncd /d "%~dp0"\r\n'
            b'"%~dp0runtime\\python.exe" -B "%~dp0app.py" %*\r\n'
            b'if errorlevel 1 pause\r\n')
        (root / 'LIESMICH.txt').write_text(r'''Droid Studio - portable fuer Windows 10/11 (64 Bit, x64)

ZIP vollstaendig in einen beschreibbaren Ordner entpacken.
Starten.bat doppelklicken. Die App oeffnet sich im Browser.
Python, Node.js und ADB sind enthalten. Eine Installation ist nicht erforderlich.
Das Konsolenfenster offen lassen. Strg+C beendet die App.

Adresse: http://127.0.0.1:8765
Anderer Port: Starten.bat --port 8766

Android-Geraet: USB-Debugging aktivieren, per USB anschliessen und die
Verbindung auf dem Telefon bestaetigen. Je nach Hersteller kann Windows
einen USB-Treiber benoetigen. Ohne Telefon ist die Demo nutzbar.

uiautodev: unter Weitere Geraetefunktionen oeffnen. Seine Weboberflaeche
wird beim ersten Aufruf aus dem Internet geladen. Die Studio-Oberflaeche
und alle Bibliotheken sind bereits im ZIP enthalten.

Liste sichern: Liste auf dem Telefon oeffnen, "Liste sichern" druecken,
im Geraetebild einen Eintrag anklicken und die Sicherung starten. Jeder
Eintrag wird geoeffnet, vollstaendig durchgeblaettert und mit Screenshot,
Seitentext, Bericht und SHA-256-Hashwerten gesichert. Vorher das Telefon
in den Flugmodus schalten (sonst senden Messenger Lesebestaetigungen).

Faelle: oben neben dem Ablaufnamen einen Fall mit Aktenzeichen anlegen.
Sicherungen liegen in Sicherungen\<Fall>\, Listen in data. Die Ablage
zeigt beides je Fall. Diese Ordner werden bei Bedarf angelegt.

Lesefassung fuer eine bestehende Sicherung (Originale bleiben unveraendert):
  runtime\python.exe tools\report_reading_copy.py "Sicherungen\<Fall>\<Sicherung>"

Eigene Ablaeufe unter Projekt > Als Datei speichern exportieren und auf
dem anderen PC unter Projekt > Datei oeffnen laden. Automatische Entwuerfe
liegen im jeweiligen Browser und reisen nicht mit dem ZIP mit.
Das Paket enthaelt keine persoenlichen Listen, Sicherungen oder Logs.

Die Ordner runtime, automator, web und node_modules gehoeren zur App.
Nicht einzeln verschieben; zum Umziehen den gesamten Ordner kopieren.
''', encoding='utf-8')
        with ZipFile(archive, 'w', ZIP_DEFLATED, compresslevel=9) as zipped:
            for source in sorted(root.rglob('*')):
                if source.is_file():
                    zipped.write(source, source.relative_to(root.parent).as_posix())
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    archive.with_suffix('.zip.sha256').write_text(f'{digest}  {archive.name}\n', encoding='ascii')
    print(json.dumps({'archive': str(archive), 'size_mb': round(archive.stat().st_size / 1024**2, 1), 'sha256': digest}))


if __name__ == '__main__':
    main()
