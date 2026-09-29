"""Evidence folder of one backup: screenshots, SHA-256 hashes, CSV and HTML report."""
import csv
import getpass
import hashlib
import html
import io
import json
import platform
from pathlib import Path
from urllib.parse import quote

from .cases import now_iso, safe_name

STATUS_LABELS = {"läuft": "läuft", "abgeschlossen": "abgeschlossen", "abgebrochen": "abgebrochen", "fehler": "Fehler"}
ORDER_LABELS = {"end_to_start": "Vom Ende zum Anfang (z. B. Chatverlauf, neueste Seite zuerst)",
                "start_to_end": "Vom Anfang zum Ende (z. B. E-Mail)"}


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


class EvidenceWriter:
    def __init__(self, root, name, case, device_info, app, options, pattern):
        started = now_iso()
        stamp = started[:19].replace("-", "").replace(":", "").replace("T", "-")
        root = Path(root)
        root.mkdir(parents=True, exist_ok=True)
        folder, suffix = root / f"{stamp}_{safe_name(name)}", 2
        while folder.exists():
            folder, suffix = root / f"{stamp}_{safe_name(name)}_{suffix}", suffix + 1
        folder.mkdir()
        self.folder = folder
        self.pages_since_save = 0
        self.record = {
            "format": "droid-studio-sicherung", "version": 1, "name": name, "status": "läuft", "message": "",
            "started": started, "finished": None,
            "case": {key: case.get(key, "") for key in ("number", "examiner", "note")},
            "device": device_info, "app": app,
            "pc": {"computer": platform.node(), "user": getpass.getuser(), "tool": "Droid Studio"},
            "options": {**options, "order_label": ORDER_LABELS.get(options.get("order"), options.get("order"))},
            "pattern": pattern, "entries": [], "warnings": [],
        }
        self.save()

    def save(self):
        temporary = self.folder / "sicherung.json.tmp"
        temporary.write_text(json.dumps(self.record, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(self.folder / "sicherung.json")
        self.pages_since_save = 0

    def begin_entry(self, text):
        index = len(self.record["entries"]) + 1
        first_line = next((line for line in text.splitlines() if line.strip()), text)
        entry = {"index": index, "text": text, "status": "läuft", "note": "", "started": now_iso(), "finished": None,
                 "folder": f"E{index:04d}_{safe_name(first_line, 40)}", "pages": []}
        self.record["entries"].append(entry)
        self.save()
        return entry

    def add_page(self, entry, data, mime):
        folder = self.folder / entry["folder"]
        folder.mkdir(exist_ok=True)
        name = f"E{entry['index']:04d}_S{len(entry['pages']) + 1:04d}.{'svg' if mime == 'image/svg+xml' else 'png'}"
        (folder / name).write_bytes(data)
        entry["pages"].append({"file": f"{entry['folder']}/{name}", "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data), "time": now_iso()})
        self.pages_since_save += 1
        if self.pages_since_save >= 10:
            self.save()

    def finish_entry(self, entry, status, note=""):
        entry.update(status=status, note=note, finished=now_iso())
        self.save()

    def warn(self, text):
        self.record["warnings"].append({"time": now_iso(), "text": text})
        self.save()

    def finish(self, status, message=""):
        """Write the final documents and the hash list; return the hash of the hash list."""
        for entry in self.record["entries"]:
            if entry["status"] == "läuft":
                entry.update(status="unvollständig", note=entry["note"] or "Sicherung wurde während dieses Eintrags beendet.", finished=now_iso())
        self.record.update(status=status, message=message, finished=now_iso())
        self.save()
        (self.folder / "eintraege.csv").write_text(entries_csv(self.record), encoding="utf-8-sig", newline="")
        (self.folder / "bericht.html").write_text(report_html(self.record), encoding="utf-8")
        files = sorted(path for path in self.folder.rglob("*") if path.is_file() and path.name not in {"hashes.sha256", "sicherung.json.tmp"})
        lines = [f"{sha256_file(path)} *{path.relative_to(self.folder).as_posix()}" for path in files]
        # No newline translation: sha256sum -c must not see a stray carriage return.
        (self.folder / "hashes.sha256").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="")
        return sha256_file(self.folder / "hashes.sha256")


def entries_csv(record):
    out = io.StringIO()
    writer = csv.writer(out, delimiter=";", lineterminator="\r\n")
    writer.writerow(["Nr", "Eintrag", "Status", "Hinweis", "Beginn", "Ende", "Seiten", "Dateien", "SHA-256"])
    for entry in record["entries"]:
        writer.writerow([entry["index"], entry["text"], entry["status"], entry["note"], entry["started"], entry["finished"] or "",
                         len(entry["pages"]), " | ".join(page["file"] for page in entry["pages"]), " | ".join(page["sha256"] for page in entry["pages"])])
    return out.getvalue()


def report_html(record):
    e = lambda value: html.escape(str(value if value is not None else ""))
    url = lambda path: html.escape(quote(path))
    case, device, options = record["case"], record["device"], record["options"]
    entries = record["entries"]
    saved = sum(1 for entry in entries if entry["status"] == "gesichert")
    pages = sum(len(entry["pages"]) for entry in entries)
    def row(label, value):
        return f"<tr><th>{e(label)}</th><td>{e(value)}</td></tr>"
    meta = "".join([
        row("Aktenzeichen", case.get("number") or "—"), row("Bearbeiter/in", case.get("examiner") or "—"), row("Notiz", case.get("note") or "—"),
        row("Bezeichnung der Sicherung", record["name"]), row("Status", STATUS_LABELS.get(record["status"], record["status"]) + (f" – {record['message']}" if record.get("message") else "")),
        row("Beginn (PC-Zeit)", record["started"]), row("Ende (PC-Zeit)", record["finished"] or "—"),
        row("Gerät", device.get("label", "")), row("Hersteller / Modell", f"{device.get('manufacturer', '')} {device.get('model', '')}".strip() or "—"),
        row("Android-Version", f"{device.get('android', '')} (SDK {device.get('sdk', '')})" if device.get("android") else "—"),
        row("Seriennummer (ADB)", device.get("serial", "")), row("Gerätezeit bei Beginn", device.get("device_time") or "nicht ermittelt"),
        row("App (Paket)", record.get("app") or "—"), row("Reihenfolge je Eintrag", options.get("order_label", "")),
        row("Höchstens Seiten je Eintrag", options.get("max_pages", "")),
        row("Computer / Benutzer", f"{record['pc'].get('computer', '')} / {record['pc'].get('user', '')}"),
        row("Ergebnis", f"{saved} von {len(entries)} Einträgen vollständig gesichert · {pages} Screenshots"),
    ])
    warnings = "".join(f"<li><span>{e(item['time'])}</span> {e(item['text'])}</li>" for item in record["warnings"]) or "<li>Keine.</li>"
    rows = []
    for entry in entries:
        first = entry["pages"][0]["file"] if entry["pages"] else None
        thumb = f'<a href="{url(first)}"><img src="{url(first)}" alt="Erste Seite von Eintrag {entry["index"]}" loading="lazy"></a>' if first else "—"
        links = " ".join(f'<a href="{url(page["file"])}" title="SHA-256 {e(page["sha256"])}">S{number}</a>' for number, page in enumerate(entry["pages"], 1)) or "—"
        status = f'<span class="status {"ok" if entry["status"] == "gesichert" else "problem"}">{e(entry["status"])}</span>'
        rows.append(f'<tr><td>{entry["index"]}</td><td>{thumb}</td><td class="text">{e(entry["text"])}</td><td>{status}<div class="note">{e(entry["note"])}</div></td>'
                    f'<td>{e(entry["started"])}<br>{e(entry["finished"] or "")}</td><td class="pages">{len(entry["pages"])}<div>{links}</div></td></tr>')
    hashes = "".join(f'<tr><td><a href="{url(page["file"])}">{e(page["file"])}</a></td><td class="hash">{e(page["sha256"])}</td><td>{e(page["time"])}</td></tr>' for entry in entries for page in entry["pages"])
    return f"""<!doctype html>
<html lang="de"><head><meta charset="utf-8"><title>Sicherungsbericht · {e(record['name'])}</title>
<style>
body{{font:13px/1.5 "Segoe UI",Arial,sans-serif;color:#1f2433;margin:32px;max-width:1200px}}h1{{font-size:22px;margin:0 0 4px}}h2{{font-size:16px;margin:28px 0 8px}}
.sub{{color:#5d6475;margin-bottom:20px}}table{{border-collapse:collapse;width:100%}}th,td{{border:1px solid #d9dce4;padding:6px 8px;text-align:left;vertical-align:top}}
.meta th{{width:230px;background:#f5f6f9;font-weight:600}}.entries th{{background:#f5f6f9}}.text{{white-space:pre-wrap;overflow-wrap:anywhere;max-width:420px}}
img{{width:110px;border:1px solid #d9dce4}}.status{{font-weight:600}}.ok{{color:#23704f}}.problem{{color:#a23b3b}}.note{{color:#5d6475;font-size:12px}}
.pages div{{font-size:11px;margin-top:4px;word-spacing:4px}}.hash{{font-family:Consolas,monospace;font-size:11px;overflow-wrap:anywhere}}ul{{padding-left:18px}}li span{{color:#5d6475}}
@media print{{body{{margin:0}}a{{color:inherit;text-decoration:none}}tr{{break-inside:avoid}}}}
</style></head><body>
<h1>Sicherungsbericht: {e(record['name'])}</h1>
<div class="sub">Erstellt mit Droid Studio. Die Prüfsummen aller Dateien stehen in <code>hashes.sha256</code> (SHA-256), die maschinenlesbaren Daten in <code>sicherung.json</code> und <code>eintraege.csv</code>.</div>
<table class="meta">{meta}</table>
<h2>Hinweise und Warnungen</h2><ul>{warnings}</ul>
<h2>Einträge ({len(entries)})</h2>
<table class="entries"><tr><th>Nr</th><th>Erste Seite</th><th>Eintrag (Text in der Liste)</th><th>Status</th><th>Beginn / Ende</th><th>Seiten</th></tr>{''.join(rows) or '<tr><td colspan="6">Keine Einträge gesichert.</td></tr>'}</table>
<h2>Screenshots und SHA-256</h2>
<table class="entries"><tr><th>Datei</th><th>SHA-256</th><th>Zeitpunkt</th></tr>{hashes or '<tr><td colspan="3">Keine Screenshots.</td></tr>'}</table>
</body></html>
"""
