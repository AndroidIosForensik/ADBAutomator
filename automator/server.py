import argparse
import base64
import importlib.util
import json
import mimetypes
import os
import secrets
import socket
import subprocess
import sys
import threading
import time
import urllib.request
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit

from .cases import CaseStore
from .devices import AndroidDevice, DemoDevice, list_devices
from .evidence import sha256_file
from .program import export_python, validate
from .runner import Runner
from .list_items import list_item_candidates

ROOT = Path(__file__).resolve().parent.parent
# Raised whenever page and server API change together; both sides compare it.
APP_VERSION = 3


def inspector_ready(url):
    """Identify uiautodev before reusing a listener we did not start."""
    try:
        with urllib.request.urlopen(url + "/api/info", timeout=1) as response:
            info = json.loads(response.read(65536))
            return (response.status == 200 and isinstance(info, dict)
                    and info.get("description") == "client for https://web.uiauto.dev"
                    and isinstance(info.get("version"), str)
                    and isinstance(info.get("drivers"), list))
    except (OSError, ValueError):
        return False


class Application:
    def __init__(self, output_dir=None):
        self.device = DemoDevice()
        data_dir = Path(output_dir) if output_dir else ROOT / "data"
        evidence_dir = Path(output_dir) / "Sicherungen" if output_dir else ROOT / "Sicherungen"
        self.cases = CaseStore(data_dir, evidence_dir)
        self.runner = Runner(output_dir or ROOT / "outputs", self.cases.lists, self.cases)
        self.control = threading.RLock()
        self.token = secrets.token_urlsafe(32)
        self.inspector = None
        self.inspector_log = None

    @property
    def lists(self):
        # Lists belong to the active case and change with it.
        return self.cases.lists

    def state(self):
        device = self.device
        case = self.cases.active_case()
        return {"device": {"serial": device.serial, "name": device.name, "demo": device.demo}, "run": self.runner.snapshot(), "case": self.cases.public(case),
                "lists_revision": f"{case['id']}:{self.lists.revision}", "list_names": list(self.lists.snapshot())}

    def library(self):
        case = self.cases.active_case()
        values = self.lists.snapshot()
        lists = [{**item, "values": values.get(item["name"], [])} for item in self.lists.details()]
        return {"case": self.cases.public(case), "lists": lists, "backups": self.cases.backups(),
                "evidence_path": str(self.cases.case_folder(case).resolve())}

    def backup_details(self, backup_id):
        record = self.cases.backup(backup_id)
        hashes = self.cases.backup_folder(backup_id) / "hashes.sha256"
        record["hash_list_sha256"] = sha256_file(hashes) if hashes.is_file() else None
        return record

    def open_folder(self, backup_id):
        folder = self.cases.backup_folder(backup_id) if backup_id else self.cases.case_folder(self.cases.active_case())
        folder.mkdir(parents=True, exist_ok=True)
        if hasattr(os, "startfile"):
            os.startfile(folder)
        else:
            subprocess.Popen(["xdg-open", str(folder)])
        return {"path": str(folder.resolve())}

    def require_idle(self):
        if self.runner.thread and self.runner.thread.is_alive():
            raise ValueError("Bitte den laufenden Ablauf zuerst stoppen.")

    def post(self, route, body):
        if route == "/api/stop":
            self.runner.stop()
            return self.state()
        if route in {"/api/step", "/api/resume", "/api/pause"}:
            {"/api/step": self.runner.advance, "/api/resume": self.runner.resume, "/api/pause": self.runner.pause}[route]()
            return self.state()
        if route == "/api/export":
            return {"code": export_python(body.get("program"), None if self.device.demo else self.device.serial, self.lists.snapshot())}
        if route == "/api/open-folder":
            return self.open_folder(body.get("id"))
        with self.control:
            self.require_idle()
            if route in {"/api/cases/create", "/api/cases/select", "/api/cases/update"}:
                if route == "/api/cases/create":
                    self.cases.create(body)
                elif route == "/api/cases/select":
                    self.cases.select(body.get("id"))
                else:
                    self.cases.update(body)
                self.runner.list_store = self.cases.lists
                return {**self.state(), "cases": self.cases.overview()}
            if route == "/api/lists/rename":
                self.lists.rename(body.get("name"), body.get("new_name"))
            elif route == "/api/lists/delete":
                self.lists.delete(body.get("name"))
            elif route == "/api/backups/delete":
                if self.runner.backup and self.runner.backup.get("id") == body.get("id") and self.runner.status in {"running", "paused", "stopping"}:
                    raise ValueError("Diese Sicherung läuft noch.")
                self.cases.delete_backup(body.get("id"))
            elif route == "/api/backup":
                if body.get("serial", self.device.serial) != self.device.serial:
                    raise ValueError("Das Gerät wurde gewechselt. Bitte das Listenelement neu auswählen.")
                self.runner.start([{"op": "backup_list", "id": "assistant", "name": body.get("name"), "pattern": body.get("pattern"),
                                    "order": body.get("order", "end_to_start"), "max_pages": body.get("max_pages", 200)}], self.device)
            elif route == "/api/connect":
                serial = body.get("serial")
                if not isinstance(serial, str) or not serial or len(serial) > 200:
                    raise ValueError("Bitte ein Gerät auswählen.")
                self.device = DemoDevice() if serial == "demo" else AndroidDevice(serial)
            elif route == "/api/run":
                self.runner.start(body.get("program"), self.device, body.get("step_mode", False))
            elif route == "/api/capture":
                if body.get('serial', self.device.serial) != self.device.serial:
                    raise ValueError('Das Gerät wurde gewechselt. Bitte das Listenelement neu auswählen.')
                self.runner.start([{"op": "scan_list", "name": body.get("name"), "by": body.get("by", "textContains"), "value": body.get("value", ""), "pattern": body.get('pattern')}], self.device)
            elif route == "/api/action":
                nodes = validate([body.get("action")])
                if nodes[0]["op"] not in {"tap", "press", "launch"}:
                    raise ValueError("Diese Direktaktion ist nicht erlaubt.")
                self.device.perform(nodes[0])
            elif route == "/api/inspector":
                return self.start_inspector()
            else:
                raise ValueError("Unbekannter Endpunkt.")
        return self.state()

    def start_inspector(self):
        # Never stop or replace an unrelated service already listening here.
        url = "http://127.0.0.1:20242"
        if inspector_ready(url):
            return {"url": url}
        if not importlib.util.find_spec("uiautodev"):
            raise ValueError("uiautodev fehlt. Bitte setup.bat ausführen.")
        if self.inspector is None or self.inspector.poll() is not None:
            with socket.socket() as sock:
                sock.settimeout(1)
                if sock.connect_ex(("127.0.0.1", 20242)) == 0:
                    raise ValueError("Port 20242 ist belegt, aber uiautodev antwortet dort nicht. Bitte den Dienst auf diesem Port prüfen.")
            if self.inspector_log:
                self.inspector_log.close()
            self.inspector_log = open(ROOT / "uiautodev.log", "a", encoding="utf-8")
            # web.uiauto.dev redirects to this host; proxying that redirect would
            # move the browser off localhost and disconnect the local inspector.
            self.inspector = subprocess.Popen([sys.executable, "-m", "uiautodev", "server", "--host", "127.0.0.1", "--port", "20242", "--no-browser", "--offline", "--server-url", "https://uiauto2.devsleep.com"], cwd=ROOT, stdout=self.inspector_log, stderr=subprocess.STDOUT, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            if self.inspector.poll() is not None:
                raise ValueError("uiautodev konnte nicht starten. Details stehen in uiautodev.log.")
            if inspector_ready(url):
                return {"url": url}
            time.sleep(0.2)
        raise ValueError("uiautodev startet noch. Bitte gleich erneut versuchen.")

    def close(self):
        self.runner.stop()
        if self.inspector and self.inspector.poll() is None:
            self.inspector.terminate()
            try:
                self.inspector.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.inspector.kill()
                self.inspector.wait(timeout=5)
        if self.inspector_log:
            self.inspector_log.close()


class Server(ThreadingHTTPServer):
    daemon_threads = True
    # Windows SO_REUSEADDR can let a second studio bind an active port.
    allow_reuse_address = False

    def server_bind(self):
        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()

    def __init__(self, address, app):
        self.app = app
        super().__init__(address, Handler)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_args):
        pass

    def trusted(self):
        port = self.server.server_port
        hosts = {f"127.0.0.1:{port}", f"localhost:{port}"}
        return self.headers.get("Host") in hosts and self.headers.get("Origin") in {None, *(f"http://{host}" for host in hosts)}

    def send_data(self, data, mime="application/json; charset=utf-8", status=200, headers=None):
        if not isinstance(data, bytes):
            data = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(status)
        for key, value in (headers or {}).items():
            self.send_header(key, value)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.end_headers()
        try:
            self.wfile.write(data)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            pass

    def do_GET(self):
        if not self.trusted():
            return self.send_data({"error": "Nur lokale Zugriffe sind erlaubt."}, status=403)
        route = unquote(urlsplit(self.path).path)
        app = self.server.app
        try:
            if route == "/api/session":
                return self.send_data({"app": "droid-studio", "version": APP_VERSION, "token": app.token, **app.state()})
            if route == "/api/state":
                return self.send_data(app.state())
            if route == "/api/lists":
                return self.send_data({"lists": app.lists.snapshot()})
            if route == "/api/cases":
                return self.send_data(app.cases.overview())
            if route == "/api/library":
                return self.send_data(app.library())
            if route == "/api/backup":
                backup_id = parse_qs(urlsplit(self.path).query).get("id", [""])[0]
                try:
                    return self.send_data(app.backup_details(backup_id))
                except ValueError as exc:
                    return self.send_data({"error": str(exc)}, status=404)
            if route == "/api/devices":
                devices, error = list_devices()
                return self.send_data({"devices": devices, "error": error})
            if route == "/api/screen":
                data, mime = app.device.screenshot()
                return self.send_data(data, mime)
            if route == "/api/elements":
                return self.send_data({"elements": app.device.elements()})
            if route == '/api/list-preview':
                with app.control:
                    app.require_idle()
                    with app.device.lock:
                        snapshot = app.device.scroll_snapshot()
                        data, mime = app.device.screenshot()
                    candidates = list_item_candidates(snapshot['full_xml'], snapshot['width'], snapshot['height'])
                    return self.send_data({'serial': app.device.serial, 'image': f'data:{mime};base64,' + base64.b64encode(data).decode(), 'candidates': candidates})
            if route == "/api/current-app":
                return self.send_data(app.device.current_app())
            if route.startswith("/vendor/"):
                base, name = ROOT / "node_modules" / "blockly", route[len("/vendor/"):]
            elif route.startswith("/outputs/"):
                base, name = app.runner.output_dir, route[len("/outputs/"):]
            elif route.startswith("/examples/"):
                base, name = ROOT / "examples", route[len("/examples/"):]
            elif route.startswith("/evidence/"):
                base, name = app.cases.evidence_dir, route[len("/evidence/"):]
            else:
                base, name = ROOT / "web", route.lstrip("/") or "index.html"
            target = (base / name).resolve()
            if not target.is_relative_to(base.resolve()) or not target.is_file():
                return self.send_data({"error": "Datei nicht gefunden."}, status=404)
            mime = "application/javascript" if target.suffix == ".js" else mimetypes.guess_type(str(target))[0] or "application/octet-stream"
            if target.suffix == ".html":
                mime = "text/html; charset=utf-8"
            # Reports show text read from the device; never let it run scripts.
            headers = {"Content-Security-Policy": "default-src 'none'; img-src 'self'; style-src 'unsafe-inline'"} if route.startswith("/evidence/") else None
            self.send_data(target.read_bytes(), mime, headers=headers)
        except Exception as exc:
            self.send_data({"error": str(exc)}, status=503)

    def do_POST(self):
        if not self.trusted() or not secrets.compare_digest(self.headers.get("X-Studio-Token", ""), self.server.app.token):
            # Consume a bounded request body before closing the connection. On
            # Windows unread inbound data can otherwise reset the 403 response.
            try:
                size = int(self.headers.get("Content-Length", "0"))
                if 0 < size <= 2_000_000:
                    self.rfile.read(size)
            except (ValueError, OSError):
                pass
            return self.send_data({"error": "Sitzung abgelaufen. Bitte die Seite neu laden."}, status=403)
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if not 0 < size <= 2_000_000:
                raise ValueError("Der Ablauf ist leer oder zu groß.")
            body = json.loads(self.rfile.read(size))
            if not isinstance(body, dict):
                raise ValueError("Ungültige Anfrage.")
            result = self.server.app.post(urlsplit(self.path).path, body)
            self.send_data(result)
        except (ValueError, TypeError, RecursionError) as exc:
            self.send_data({"error": str(exc)}, status=400)
        except Exception as exc:
            self.send_data({"error": f"Geräteaktion fehlgeschlagen: {exc}"}, status=503)


def main():
    parser = argparse.ArgumentParser(description="Droid Studio – visuelle Android-Automatisierung")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()
    app = Application()
    try:
        server = Server(("127.0.0.1", args.port), app)
    except OSError as exc:
        url = f"http://127.0.0.1:{args.port}"
        try:
            with urllib.request.urlopen(url + "/api/session", timeout=2) as response:
                existing = json.load(response)
            if existing.get("app") == "droid-studio" and existing.get("version") == APP_VERSION:
                print(f"Droid Studio läuft bereits: {url}", flush=True)
                if not args.no_browser:
                    webbrowser.open(url)
                return
            if existing.get("app") == "droid-studio":
                # Opening the browser would show the new page against the old server.
                parser.exit(1, f"Auf {url} läuft noch eine ältere Droid-Studio-Version.\n"
                               "Bitte deren Konsolenfenster schließen (oder dort Strg+C drücken) und start.bat erneut starten.\n")
        except (OSError, ValueError):
            pass
        parser.exit(1, f"Port {args.port} ist nicht verfügbar: {exc}\nBitte einen anderen Port mit --port wählen.\n")
    url = f"http://127.0.0.1:{server.server_port}"
    print(f"Droid Studio: {url}\nBeenden mit Strg+C", flush=True)
    if not args.no_browser:
        threading.Timer(0.5, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        app.close()
