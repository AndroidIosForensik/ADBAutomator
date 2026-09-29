"""Cases keep the lists and evidence of different investigations apart."""
import datetime
import json
import re
import secrets
import shutil
import threading
from pathlib import Path
from urllib.parse import quote

from .storage import ListStore


def now_iso():
    return datetime.datetime.now().astimezone().isoformat(timespec="seconds")


def safe_name(text, limit=40):
    """A Windows-safe, readable folder or file name component."""
    text = re.sub(r'[<>:"/\\|?*\x00-\x1f​-‏ - ﻿]+', " ", str(text))
    text = re.sub(r"\s+", " ", text).strip(" .")
    return text[:limit].rstrip(" .") or "ohne Name"


class CaseStore:
    def __init__(self, data_dir, evidence_dir):
        self.data_dir = Path(data_dir)
        self.evidence_dir = Path(evidence_dir)
        self.path = self.data_dir / "cases.json"
        self.lock = threading.RLock()
        self.cases, self.active = [], None
        if self.path.exists():
            data = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(data, dict) or not isinstance(data.get("cases"), list):
                raise ValueError("Ungültiger Fallspeicher.")
            self.cases = [case for case in data["cases"] if isinstance(case, dict) and isinstance(case.get("id"), str)]
            self.active = data.get("active")
        if not self.cases:
            # The first case takes over lists saved before cases existed.
            case = self._new_case("", "", "")
            legacy = self.data_dir / "lists.json"
            if legacy.is_file():
                target = self.list_path(case)
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(legacy, target)
            self.cases.append(case)
            self.active = case["id"]
            self._write()
        if not any(case["id"] == self.active for case in self.cases):
            self.active = self.cases[0]["id"]
        self.lists = ListStore(self.list_path(self.active_case()))

    def _new_case(self, number, examiner, note):
        case_id = secrets.token_hex(4)
        folder = f"{safe_name(number or 'Allgemein', 50)}_{case_id}"
        return {"id": case_id, "number": number, "examiner": examiner, "note": note, "created": now_iso(), "folder": folder}

    def _write(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(json.dumps({"active": self.active, "cases": self.cases}, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(self.path)

    @staticmethod
    def title(case):
        return case["number"] or "Allgemein (ohne Aktenzeichen)"

    def list_path(self, case):
        return self.data_dir / "cases" / case["id"] / "lists.json"

    def case_folder(self, case):
        return self.evidence_dir / case["folder"]

    @staticmethod
    def evidence_url(case, backup_id=""):
        return f"/evidence/{quote(case['folder'])}/" + (f"{quote(backup_id)}/" if backup_id else "")

    def active_case(self):
        with self.lock:
            return dict(next(case for case in self.cases if case["id"] == self.active))

    def public(self, case):
        return {**case, "title": self.title(case)}

    def overview(self):
        with self.lock:
            return {"active": self.active, "cases": [self.public(case) for case in self.cases]}

    @staticmethod
    def _fields(body):
        values = {}
        for key, label, limit in (("number", "Aktenzeichen", 80), ("examiner", "Bearbeiter/in", 120), ("note", "Notiz", 500)):
            value = body.get(key, "")
            if not isinstance(value, str) or len(value) > limit:
                raise ValueError(f"{label}: höchstens {limit} Zeichen.")
            values[key] = value.strip()
        if not values["number"]:
            raise ValueError("Bitte ein Aktenzeichen oder eine Fallbezeichnung eingeben.")
        return values

    def create(self, body):
        values = self._fields(body)
        with self.lock:
            case = self._new_case(values["number"], values["examiner"], values["note"])
            self.cases.append(case)
            self.active = case["id"]
            self._write()
            self.lists = ListStore(self.list_path(case))
            return self.public(case)

    def update(self, body):
        values = self._fields(body)
        with self.lock:
            case = self._find(body.get("id"))
            # The evidence folder keeps its name; reports store their own case snapshot.
            case.update(values)
            self._write()
            return self.public(case)

    def select(self, case_id):
        with self.lock:
            case = self._find(case_id)
            self.active = case["id"]
            self._write()
            self.lists = ListStore(self.list_path(case))
            return self.public(case)

    def _find(self, case_id):
        case = next((case for case in self.cases if case["id"] == case_id), None)
        if case is None:
            raise ValueError("Diesen Fall gibt es nicht.")
        return case

    # Backups live in the case's evidence folder; every backup folder is self-describing.
    def backups(self):
        folder = self.case_folder(self.active_case())
        result = []
        for record_path in sorted(folder.glob("*/sicherung.json")) if folder.is_dir() else []:
            try:
                record = json.loads(record_path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            entries = record.get("entries", [])
            result.append({"id": record_path.parent.name, "name": record.get("name", record_path.parent.name), "status": record.get("status"),
                           "started": record.get("started"), "finished": record.get("finished"), "app": record.get("app"),
                           "device": record.get("device", {}).get("label"), "entries": len(entries),
                           "saved": sum(1 for entry in entries if entry.get("status") == "gesichert"),
                           "problems": sum(1 for entry in entries if entry.get("status") not in {"gesichert", "läuft"}),
                           "pages": sum(len(entry.get("pages", [])) for entry in entries)})
        result.sort(key=lambda item: item.get("started") or "", reverse=True)
        return result

    def backup_folder(self, backup_id):
        if not isinstance(backup_id, str) or not re.fullmatch(r"[^/\\:]{1,120}", backup_id) or backup_id in {".", ".."}:
            raise ValueError("Unbekannte Sicherung.")
        folder = self.case_folder(self.active_case()) / backup_id
        if not (folder / "sicherung.json").is_file():
            raise ValueError("Diese Sicherung gibt es nicht mehr.")
        return folder

    def backup(self, backup_id):
        folder = self.backup_folder(backup_id)
        record = json.loads((folder / "sicherung.json").read_text(encoding="utf-8"))
        record["id"] = backup_id
        record["base"] = self.evidence_url(self.active_case(), backup_id)
        record["path"] = str(folder.resolve())
        record["reading_report"] = "bericht-lesefassung.html" if (folder / "bericht-lesefassung.html").is_file() else None
        return record

    def delete_backup(self, backup_id):
        shutil.rmtree(self.backup_folder(backup_id))
