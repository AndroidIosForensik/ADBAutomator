"""Atomic, local storage for named lists."""
import json
import threading
from pathlib import Path


class ListStore:
    def __init__(self, path):
        self.path = Path(path)
        self.lock = threading.RLock()
        self.values = {}
        self.meta = {}
        self.revision = 0
        if self.path.exists():
            data = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                raise ValueError("Ungültiger Listenspeicher.")
            # Version 1 stored {name: [values]}; version 2 adds metadata per list.
            entries = data.get("lists") if data.get("version") == 2 else {name: {"values": values} for name, values in data.items()}
            if not isinstance(entries, dict):
                raise ValueError("Ungültiger Listenspeicher.")
            for name, entry in entries.items():
                values = entry.get("values") if isinstance(entry, dict) else None
                self.check(name, values)
                self.values[name] = list(values)
                self.meta[name] = dict(entry.get("meta") or {})

    @staticmethod
    def check(name, values):
        if not isinstance(name, str) or not name.strip() or len(name) > 80:
            raise ValueError("Bitte einen Listennamen mit höchstens 80 Zeichen eingeben.")
        if not isinstance(values, list) or len(values) > 500 or any(not isinstance(v, str) or not v.strip() or len(v) > 2000 for v in values):
            raise ValueError("Eine Liste darf bis zu 500 Texte mit jeweils 2000 Zeichen enthalten.")

    def snapshot(self):
        with self.lock:
            return {name: list(values) for name, values in self.values.items()}

    def details(self):
        with self.lock:
            return [{"name": name, "count": len(values), "meta": dict(self.meta.get(name, {}))} for name, values in self.values.items()]

    def _write(self, values, meta):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        data = {"version": 2, "lists": {name: {"values": entries, "meta": meta.get(name, {})} for name, entries in values.items()}}
        temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(self.path)
        self.values, self.meta = values, meta
        self.revision += 1

    def save(self, name, values, meta=None):
        self.check(name, values)
        with self.lock:
            self._write({**self.values, name: list(values)}, {**self.meta, name: dict(meta or {})})

    def rename(self, name, new_name):
        new_name = new_name.strip() if isinstance(new_name, str) else new_name
        with self.lock:
            if name not in self.values:
                raise ValueError("Diese Liste gibt es nicht mehr.")
            self.check(new_name, self.values[name])
            if new_name != name and new_name in self.values:
                raise ValueError(f"Eine Liste „{new_name}“ gibt es bereits.")
            # Keep the original order so the overview does not jump around.
            values = {new_name if key == name else key: entries for key, entries in self.values.items()}
            meta = {new_name if key == name else key: entry for key, entry in self.meta.items()}
            self._write(values, meta)

    def delete(self, name):
        with self.lock:
            if name not in self.values:
                raise ValueError("Diese Liste gibt es nicht mehr.")
            self._write({key: entries for key, entries in self.values.items() if key != name},
                        {key: entry for key, entry in self.meta.items() if key != name})
