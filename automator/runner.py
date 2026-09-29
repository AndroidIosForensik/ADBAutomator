import copy
import threading
import time
from collections import deque
from pathlib import Path

from .backup import ListBackup
from .cases import now_iso
from .evidence import EvidenceWriter
from .program import validate
from .scrolling import traverse_screen
from .values import resolve_command, scalar_value, as_number, variable_value


class Stopped(Exception):
    pass


LABELS = {"launch": "App öffnen", "tap": "Position antippen", "click": "Element antippen", "type": "Text eingeben", "wait": "Warten", "wait_for": "Auf Element warten", "press": "Taste drücken", "swipe": "Wischen", "repeat": "Wiederholen", "if_exists": "Element prüfen", "screenshot": "Screenshot auf PC speichern"}
LABELS.update(list_create="Liste erstellen", read_list="Listentexte lesen", for_each="Für jeden Eintrag")
LABELS.update(scan_list="Bildschirmliste aufnehmen", scroll_find="Text durch Scrollen suchen")
LABELS.update(var_set='Variable setzen', var_change='Variable ändern', backup_list='Liste sichern')
LIST_SOURCES = {"list_create": "Baustein „Liste erstellen“", "read_list": "Bildschirm (sichtbare Texte)", "scan_list": "Bildschirm (durchgescrollt)"}


class Runner:
    def __init__(self, output_dir, list_store=None, cases=None):
        self.output_dir = Path(output_dir)
        self.list_store = list_store
        self.cases = cases
        self.backup = None
        # Waiting times of „Liste sichern“; None picks defaults for real or demo devices.
        self.backup_timing = None
        self.lock = threading.RLock()
        self.condition = threading.Condition(self.lock)
        self.step_mode = False
        self.current_item = None
        self.active_label = None
        self.variables = {}
        self.cancel = threading.Event()
        self.thread = None
        self.status = "idle"
        self.active_id = None
        self.steps = 0
        self.logs = deque(maxlen=300)
        self.started = None
        self.finished = None

    def snapshot(self):
        with self.lock:
            return {"status": self.status, "active_id": self.active_id, "active_label": self.active_label, "current_item": self.current_item, "variables": dict(self.variables), "step_mode": self.step_mode, "steps": self.steps, "logs": copy.deepcopy(list(self.logs)), "elapsed": round((self.finished or time.monotonic()) - self.started, 1) if self.started else 0, "backup": dict(self.backup) if self.backup else None}

    def log(self, text, level="info", **extra):
        with self.lock:
            self.logs.append({"time": time.strftime("%H:%M:%S"), "text": text, "level": level, **extra})

    def start(self, program, device, step_mode=False):
        if not isinstance(step_mode, bool):
            raise ValueError("Ungültiger Schrittmodus.")
        program = validate(program, self.list_store.snapshot() if self.list_store else None)
        with self.lock:
            if self.thread and self.thread.is_alive():
                raise ValueError("Es läuft bereits ein Ablauf.")
            self.cancel.clear()
            self.logs.clear()
            self.steps = 0
            self.active_id = None
            self.active_label = None
            self.current_item = None
            self.step_mode = step_mode
            self.variables = {}
            self.backup = None
            self.status = "running"
            self.started = time.monotonic()
            self.finished = None
            self.thread = threading.Thread(target=self._run, args=(program, device), daemon=True)
            self.thread.start()

    def stop(self):
        with self.lock:
            if self.status in {"running", "paused"}:
                self.status = "stopping"
                self.cancel.set()
                self.condition.notify_all()

    def advance(self):
        with self.condition:
            if self.status != "paused":
                raise ValueError("Einzelschritte sind nur bei angehaltenem Ablauf möglich.")
            self.status = "running"
            self.condition.notify_all()

    def resume(self):
        with self.condition:
            if self.status != "paused":
                raise ValueError("Der Ablauf ist nicht angehalten.")
            self.step_mode = False
            self.status = "running"
            self.condition.notify_all()

    def pause(self):
        with self.condition:
            if self.status != "running":
                raise ValueError("Es läuft kein Ablauf.")
            self.step_mode = True

    def before_step(self, node, current_item):
        with self.condition:
            self.checkpoint()
            self.active_id = node["id"]
            self.active_label = LABELS[node["op"]]
            self.current_item = current_item
            if self.step_mode:
                self.status = "paused"
                while self.status == "paused":
                    self.condition.wait()
            self.checkpoint()
            self.steps += 1
            if self.steps > 10000:
                raise ValueError("Der Ablauf hat die Grenze von 10.000 Schritten erreicht.")

    def pause_point(self):
        """Let „Pause“ take effect between the entries of a long backup."""
        with self.condition:
            self.checkpoint()
            if self.step_mode:
                self.status = "paused"
                while self.status == "paused":
                    self.condition.wait()
            self.checkpoint()

    def checkpoint(self, seconds=0):
        if self.cancel.wait(seconds):
            raise Stopped()

    def _run(self, program, device):
        try:
            self.log("Demo gestartet · Aktionen werden simuliert." if device.demo else f"Gestartet auf {device.name}.")
            self._sequence(program, device, self.list_store.snapshot() if self.list_store else {})
            self.checkpoint()
            with self.lock:
                self.status = "completed"
            self.log("Ablauf erfolgreich abgeschlossen.", "success")
        except Stopped:
            with self.lock:
                self.status = "stopped"
            self.log("Ablauf gestoppt.", "warning")
        except Exception as exc:
            with self.lock:
                self.status = "error"
            self.log(str(exc) or type(exc).__name__, "error")
        finally:
            with self.lock:
                self.finished = time.monotonic()
                if self.status != "error":
                    self.active_id = None
                    self.active_label = None
                    self.current_item = None

    def _sequence(self, items, device, lists, current_item=None):
        for node in items:
            self.checkpoint()
            self.before_step(node, current_item)
            node = resolve_command(node, self.variables, current_item)
            detail = node.get("value", node.get("text"))
            self.log(LABELS[node["op"]] + (f' · {detail}' if isinstance(detail, str) and detail else ""), block_id=node["id"])
            op = node["op"]
            if op in {'var_set', 'var_change'}:
                with self.lock:
                    value = node['value'] if op == 'var_set' else as_number(variable_value(self.variables, node['name']), -1e12, 1e12, 'Variable ändern') + node['amount']
                    self.variables[node['name']] = scalar_value(value)
                self.log(f'Variable „{node["name"]}“ = {value}', block_id=node['id'])
            elif op == "wait":
                self.checkpoint(node["seconds"])
            elif op == "repeat":
                for _ in range(node["times"]):
                    self.checkpoint()
                    self._sequence(node["body"], device, lists, current_item)
            elif op in {"list_create", "read_list", "scan_list"}:
                if op == "scan_list":
                    values = traverse_screen(device, by=node["by"], value=node["value"], checkpoint=self.checkpoint, progress=self.log, pattern=node.get('pattern'))
                else:
                    values = list(node["items"]) if op == "list_create" else device.read_list(node["by"], node["value"])
                self.checkpoint()
                if self.list_store:
                    self.list_store.save(node["name"], values, {"source": LIST_SOURCES[op], "device": device.name, "updated": now_iso()})
                lists[node["name"]] = values
                self.log(f'Liste „{node["name"]}“: {len(values)} Einträge.', "success")
            elif op == "backup_list":
                self._backup(node, device)
            elif op == "scroll_find":
                if not traverse_screen(device, target=node["value"], match=node["match"], checkpoint=self.checkpoint, progress=self.log):
                    raise ValueError(f'Text „{node["value"]}“ bis zum Ende nicht gefunden. Der Bildschirm bewegt sich nicht mehr.')
            elif op == "for_each":
                if node["name"] not in lists:
                    raise ValueError(f'Liste „{node["name"]}“ wurde noch nicht erstellt oder gelesen.')
                values = list(lists[node["name"]])
                if not values:
                    self.log(f'Liste „{node["name"]}“ ist leer. Schleife übersprungen.', "warning")
                for index, value in enumerate(values, 1):
                    self.checkpoint()
                    self.log(f'Eintrag {index}/{len(values)}: {value[:160]}', block_id=node["id"])
                    self._sequence(node["body"], device, lists, value)
            elif op == "if_exists":
                self._sequence(node["body"] if device.exists(node) else node["otherwise"], device, lists, current_item)
            elif op in {"wait_for", "click"}:
                deadline = time.monotonic() + node["timeout"]
                while not device.exists(node):
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise TimeoutError(f'Element „{node["value"]}“ nach {node["timeout"]} Sekunden nicht gefunden.')
                    self.checkpoint(min(0.2, remaining))
                self.checkpoint()
                if op == "click":
                    device.perform(node)
            elif op == "screenshot":
                data, mime = device.screenshot()
                self.output_dir.mkdir(parents=True, exist_ok=True)
                name = f"screenshot-{time.time_ns()}.{'svg' if mime == 'image/svg+xml' else 'png'}"
                (self.output_dir / name).write_bytes(data)
                self.log(f"Screenshot auf PC gespeichert: {(self.output_dir / name).resolve()}", "success", artifact=f"/outputs/{name}")
            else:
                device.perform(node)
            self.checkpoint(0.35 if device.demo else 0.05)

    def _backup(self, node, device):
        if self.cases:
            case = self.cases.active_case()
            root = self.cases.case_folder(case)
        else:
            case, root = {}, self.output_dir / "Sicherungen"
        writer = EvidenceWriter(root, node["name"], case, device.device_info(), device.current_app().get("package", ""),
                                {"order": node["order"], "max_pages": node["max_pages"]}, node["pattern"])
        report = self.cases.evidence_url(case, writer.folder.name) + "bericht.html" if self.cases else None
        with self.lock:
            self.backup = {"name": node["name"], "id": writer.folder.name, "folder": str(writer.folder.resolve()),
                           "entry": 0, "text": "", "page": 0, "saved": 0, "problems": 0, "pages": 0}
        self.log(f'Sicherung „{node["name"]}“ gestartet · Ordner: {writer.folder.resolve()}', block_id=node["id"])

        def status(**values):
            with self.lock:
                self.backup.update(values)

        engine = ListBackup(device, node["pattern"], writer, order=node["order"], max_pages=node["max_pages"], checkpoint=self.checkpoint,
                            log=lambda text, level="info": self.log(text, level), status=status, pause_point=self.pause_point,
                            **(self.backup_timing or ({"settle": .15, "fling_settle": .15, "poll": .15} if device.demo else {})))
        try:
            counts = engine.run()
        except Stopped:
            digest = writer.finish("abgebrochen", "Vom Benutzer gestoppt.")
            self.log(f"Sicherung abgebrochen. Bereits gesicherte Einträge und der Bericht bleiben erhalten. SHA-256 der Hashliste: {digest}", "warning", artifact=report)
            raise
        except Exception as exc:
            digest = writer.finish("fehler", str(exc) or type(exc).__name__)
            self.log(f"Bericht zur unvollständigen Sicherung erstellt. SHA-256 der Hashliste: {digest}", "warning", artifact=report)
            raise
        digest = writer.finish("abgeschlossen")
        level = "success" if not counts["problems"] else "warning"
        self.log(f'Sicherung abgeschlossen: {counts["saved"]} von {counts["entries"]} Einträgen vollständig, {counts["pages"]} Screenshots.', level, artifact=report)
        self.log(f"SHA-256 der Hashliste (hashes.sha256): {digest}", "success")
