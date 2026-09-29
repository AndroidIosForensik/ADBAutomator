"""Evidence folder of one backup: screenshots, SHA-256 hashes, CSV and HTML report."""
import csv
import getpass
import hashlib
import io
import json
import platform
from pathlib import Path

from .cases import now_iso, safe_name
from .report import report_html

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

    def add_page(self, entry, data, mime, text=None):
        folder = self.folder / entry["folder"]
        folder.mkdir(exist_ok=True)
        stem = f"E{entry['index']:04d}_S{len(entry['pages']) + 1:04d}"
        name = f"{stem}.{'svg' if mime == 'image/svg+xml' else 'png'}"
        (folder / name).write_bytes(data)
        page = {"file": f"{entry['folder']}/{name}", "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data), "time": now_iso()}
        if text is not None:
            # The screen's text as Android reports it, next to the screenshot.
            encoded = text.encode("utf-8")
            (folder / f"{stem}.txt").write_bytes(encoded)
            page.update(text=text, text_file=f"{entry['folder']}/{stem}.txt", text_sha256=hashlib.sha256(encoded).hexdigest())
        entry["pages"].append(page)
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
