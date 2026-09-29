import csv
import hashlib
import io
import json
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from unittest.mock import patch

from automator.backup import ListBackup, list_entries, overlap
from automator.cases import CaseStore
from automator.devices import DEMO_CHATS, DEMO_CHATS_PACKAGE, DemoDevice, focused_package
from automator.list_items import list_item_candidates
from automator.program import ProgramError, export_python, validate
from automator.runner import Runner
from automator.scrolling import screen_snapshot, traverse_screen
from automator.server import Application, Server
from automator.storage import ListStore

FAST = {"settle": 0, "fling_settle": 0, "poll": 0}


def open_chats(device):
    device.perform({"op": "launch", "package": DEMO_CHATS_PACKAGE})
    snap = device.scroll_snapshot()
    return next(c["pattern"] for c in list_item_candidates(snap["full_xml"], 390, 800) if c["pattern"]["item"][-1]["resource_id"] == "demo:id/chat_row")


def expected_pages(messages):
    # The demo chat shows 600 px; every controlled drag moves 360 px minus 8 px touch slop.
    overflow = max(0, messages * 64 - 600)
    return 1 + -(-overflow // 352)


class Recorder:
    """Stands in for the evidence folder in engine tests."""

    def __init__(self):
        self.entries, self.warnings = [], []

    def begin_entry(self, text):
        entry = {"index": len(self.entries) + 1, "text": text, "pages": [], "status": "läuft", "note": ""}
        self.entries.append(entry)
        return entry

    def add_page(self, entry, data, mime):
        entry["pages"].append(data)

    def finish_entry(self, entry, status, note=""):
        entry.update(status=status, note=note)

    def warn(self, text):
        self.warnings.append(text)


class EngineTests(unittest.TestCase):
    def setUp(self):
        self.device = DemoDevice()
        self.pattern = open_chats(self.device)

    def backup(self, **options):
        writer = Recorder()
        counts = ListBackup(self.device, self.pattern, writer, checkpoint=lambda seconds=0: None, open_timeout=0, **FAST, **options).run()
        return writer, counts

    def test_every_entry_once_in_order_including_identical_rows(self):
        self.device.scroll_by(self.device.scroll_snapshot(), 300)  # start in the middle of the list
        writer, counts = self.backup()
        self.assertEqual([entry["text"].split("\n")[0] for entry in writer.entries], [chat[0] for chat in DEMO_CHATS])
        self.assertEqual([len(entry["pages"]) for entry in writer.entries], [expected_pages(chat[4]) for chat in DEMO_CHATS])
        self.assertEqual({entry["status"] for entry in writer.entries}, {"gesichert"})
        self.assertEqual(counts, {"entries": 16, "saved": 16, "problems": 0, "pages": sum(expected_pages(chat[4]) for chat in DEMO_CHATS)})
        self.assertEqual(writer.warnings, [])
        self.assertEqual(self.device.page, "Demo-Chats")

    def test_screens_overlap_without_scrolling_back(self):
        # Found on a real phone: the next screen must keep a handled entry in view,
        # otherwise every step needs a correction and large cards can leave gaps.
        distances = []
        original = self.device.scroll_by
        self.device.scroll_by = lambda snapshot, distance: (distances.append(distance), original(snapshot, distance))[1]
        writer, counts = self.backup()
        self.assertEqual(counts["saved"], 16)
        self.assertTrue(distances and all(distance > 0 for distance in distances), distances)

    def test_tall_entries_are_all_handled_in_order(self):
        for row in (200, 300, 400):
            with self.subTest(row=row), patch("automator.devices.ROW", row):
                self.device = DemoDevice()
                self.pattern = open_chats(self.device)
                writer, counts = self.backup()
                self.assertEqual([entry["text"].split("\n")[0] for entry in writer.entries], [chat[0] for chat in DEMO_CHATS])
                self.assertEqual(writer.warnings, [])

    def test_text_capture_keeps_no_fragments_of_cut_off_entries(self):
        # Found on a real phone: a card cut off at the edge contributed only its
        # second line ("Mobile Daten, WLAN, Hotspot") as an extra list value.
        self.device.scroll_by(self.device.scroll_snapshot(), 300)
        values = traverse_screen(self.device, pattern=self.pattern, checkpoint=lambda seconds=0: None)
        complete_rows = {"\n".join(part for part in (name, message, time, str(unread) if unread else "") if part)
                         for name, message, time, unread, _ in DEMO_CHATS}
        self.assertEqual(len(values), 15)  # the two identical "Unbekannt" rows are one value
        self.assertEqual(set(values) - complete_rows, set())

    def test_chat_pages_run_from_newest_to_oldest_message(self):
        writer, _ = self.backup()
        team = writer.entries[1]
        self.assertIn(b"16. Nachricht", team["pages"][0])
        self.assertIn(b"1. Nachricht", team["pages"][-1])
        writer, _ = self.backup(order="start_to_end")
        self.assertIn(b"1. Nachricht", writer.entries[1]["pages"][0])
        self.assertEqual(len(writer.entries), 16)

    def test_page_limit_marks_entry_incomplete(self):
        writer, counts = self.backup(max_pages=2)
        team = writer.entries[1]
        self.assertEqual((team["status"], len(team["pages"])), ("unvollständig", 2))
        self.assertEqual(counts["problems"], 1)

    def test_entry_that_does_not_open_is_documented_and_not_left(self):
        original = self.device._open_chat
        self.device._open_chat = lambda index: None if DEMO_CHATS[index][0] == "Jonas" else original(index)
        writer, counts = self.backup()
        jonas = writer.entries[7]
        self.assertEqual((jonas["text"].split("\n")[0], jonas["status"], jonas["pages"]), ("Jonas", "öffnete nicht", []))
        self.assertEqual((counts["entries"], counts["saved"]), (16, 15))

    def test_cut_off_rows_are_not_complete(self):
        self.device.scroll_by(self.device.scroll_snapshot(), 108)  # 100 px after touch slop
        snap = self.device.scroll_snapshot()
        _, entries = list_entries(screen_snapshot(snap["full_xml"], 390, 800, self.pattern), self.pattern)
        self.assertFalse(entries[0]["complete"])
        self.assertFalse(entries[-1]["complete"])
        self.assertTrue(all(entry["complete"] for entry in entries[1:-1]))
        self.assertEqual([entry["text"].split("\n")[0] for entry in entries[:2]], ["Team Nord", "Lena"])

    def test_overlap_uses_distance_for_identical_neighbours(self):
        rows = lambda texts, top: [{"text": text, "bounds": (0, top + i * 50, 10, top + i * 50 + 50)} for i, text in enumerate(texts)]
        previous = rows(["a", "x", "x", "x"], 100)
        # Scrolled by two rows: "x", "x" are old, the third "x" and "b" are new.
        current = rows(["x", "x", "x", "b"], 100)
        self.assertEqual(overlap(previous, current, 100), 2)
        self.assertEqual(overlap(previous, current, 50), 3)
        self.assertIsNone(overlap(previous, rows(["c", "d"], 100), 100))


class RunnerBackupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.cases = CaseStore(self.temp.name, Path(self.temp.name) / "Sicherungen")
        self.runner = Runner(self.temp.name, self.cases.lists, self.cases)
        self.runner.backup_timing = FAST
        self.device = DemoDevice()
        self.pattern = open_chats(self.device)
        self.node = {"op": "backup_list", "id": "b", "name": "Chats: Demo/Test", "pattern": self.pattern, "order": "end_to_start", "max_pages": 50}

    def folder(self):
        return next(self.cases.case_folder(self.cases.active_case()).iterdir())

    def test_evidence_folder_report_csv_and_valid_hashes(self):
        self.runner.start([self.node], self.device)
        self.runner.thread.join(30)
        self.assertEqual(self.runner.snapshot()["status"], "completed")
        folder = self.folder()
        self.assertNotIn("/", folder.name)
        record = json.loads((folder / "sicherung.json").read_text(encoding="utf-8"))
        self.assertEqual((record["status"], len(record["entries"]), record["device"]["model"]), ("abgeschlossen", 16, "Demo-Gerät"))
        self.assertNotIn(b"\r", (folder / "hashes.sha256").read_bytes())
        lines = (folder / "hashes.sha256").read_text(encoding="utf-8").splitlines()
        for line in lines:
            digest, name = line.split(" *", 1)
            self.assertEqual(hashlib.sha256((folder / name).read_bytes()).hexdigest(), digest, name)
        self.assertIn("bericht.html", {line.split(" *", 1)[1] for line in lines})
        raw = (folder / "eintraege.csv").read_bytes()
        self.assertNotIn(b"\r\r", raw)
        rows = list(csv.reader(io.StringIO(raw.decode("utf-8-sig"), newline=""), delimiter=";"))
        self.assertEqual(len(rows), 17)
        report = (folder / "bericht.html").read_text(encoding="utf-8")
        self.assertIn("16 von 16 Einträgen vollständig gesichert", report)
        self.assertNotIn("<script", report)
        logs = self.runner.snapshot()["logs"]
        self.assertTrue(any(log.get("artifact", "").endswith("/bericht.html") for log in logs))
        summary = self.cases.backups()[0]
        self.assertEqual((summary["entries"], summary["saved"], summary["problems"]), (16, 16, 0))

    def test_stop_keeps_what_was_saved_and_marks_report(self):
        self.runner.backup_timing = {"settle": .02, "fling_settle": .02, "poll": .02}
        self.runner.start([self.node], self.device)
        deadline = time.monotonic() + 10
        while (self.runner.snapshot()["backup"] or {}).get("saved", 0) < 2 and time.monotonic() < deadline:
            time.sleep(.01)
        self.runner.stop()
        self.runner.thread.join(10)
        self.assertEqual(self.runner.snapshot()["status"], "stopped")
        record = json.loads((self.folder() / "sicherung.json").read_text(encoding="utf-8"))
        self.assertEqual(record["status"], "abgebrochen")
        self.assertGreaterEqual(sum(entry["status"] == "gesichert" for entry in record["entries"]), 2)
        self.assertLess(len(record["entries"]), 16)
        self.assertNotIn("läuft", {entry["status"] for entry in record["entries"]})
        self.assertTrue((self.folder() / "hashes.sha256").is_file())

    def test_pause_waits_between_entries(self):
        self.runner.backup_timing = {"settle": .02, "fling_settle": .02, "poll": .02}
        self.runner.start([self.node], self.device)
        deadline = time.monotonic() + 10
        while not (self.runner.snapshot()["backup"] or {}).get("entry") and time.monotonic() < deadline:
            time.sleep(.005)
        self.runner.pause()
        deadline = time.monotonic() + 10
        while self.runner.snapshot()["status"] != "paused" and time.monotonic() < deadline:
            time.sleep(.01)
        entries = self.runner.snapshot()["backup"]["entry"]
        time.sleep(.2)
        self.assertEqual(self.runner.snapshot()["backup"]["entry"], entries)
        self.runner.resume()
        self.runner.thread.join(30)
        self.assertEqual(self.runner.snapshot()["status"], "completed")

    def test_validation_and_export(self):
        with self.assertRaisesRegex(ProgramError, "Listenelement"):
            validate([{"op": "backup_list", "name": "X"}])
        with self.assertRaises(ProgramError):
            validate([{**self.node, "order": "sideways"}])
        with self.assertRaises(ProgramError):
            validate([{**self.node, "max_pages": 0}])
        self.assertEqual(validate([self.node])[0]["max_pages"], 50)
        with self.assertRaisesRegex(ProgramError, "nur in Droid Studio"):
            export_python([self.node])


class FocusedAppTests(unittest.TestCase):
    def test_focused_app_comes_from_window_manager(self):
        # Real Android 17 output while uiautomator2 wrongly reported a background chat app.
        output = ("  mCurrentFocus=Window{d9b83e u0 com.android.settings/com.android.settings.Settings}\n"
                  "  mFocusedApp=ActivityRecord{235076573 u0 com.android.settings/.Settings t143}\n")
        self.assertEqual(focused_package(output), "com.android.settings")
        popup = "  mCurrentFocus=Window{1 u0 PopupWindow:4f2}\n  mFocusedApp=ActivityRecord{2 u0 com.whatsapp/.Main t9}\n"
        self.assertEqual(focused_package(popup), "com.whatsapp")
        self.assertIsNone(focused_package("  mCurrentFocus=Window{1 u0 NotificationShade}\n  mFocusedApp=null\n"))


class CaseAndListStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_legacy_lists_move_into_first_case_and_cases_separate_lists(self):
        (self.root / "lists.json").write_text(json.dumps({"Alt": ["a", "b"]}), encoding="utf-8")
        cases = CaseStore(self.root, self.root / "Sicherungen")
        self.assertEqual(cases.lists.snapshot(), {"Alt": ["a", "b"]})
        first = cases.active
        cases.create({"number": "AZ 12/34", "examiner": "Prüfer", "note": ""})
        self.assertEqual(cases.lists.snapshot(), {})
        cases.lists.save("Neu", ["x"])
        cases.select(first)
        self.assertEqual(cases.lists.snapshot(), {"Alt": ["a", "b"]})
        reopened = CaseStore(self.root, self.root / "Sicherungen")
        self.assertEqual(reopened.active, first)
        self.assertEqual(len(reopened.overview()["cases"]), 2)
        with self.assertRaises(ValueError):
            cases.create({"number": " "})

    def test_backup_ids_cannot_leave_the_case_folder(self):
        cases = CaseStore(self.root, self.root / "Sicherungen")
        for bad in ["..", "../x", "a/b", "", None, "C:x"]:
            with self.assertRaises(ValueError):
                cases.backup_folder(bad)

    def test_list_store_reads_old_format_renames_and_deletes(self):
        path = self.root / "lists.json"
        path.write_text(json.dumps({"A": ["1"], "B": ["2"]}), encoding="utf-8")
        store = ListStore(path)
        store.save("C", ["3"], {"source": "Test"})
        store.rename("A", "Z")
        with self.assertRaises(ValueError):
            store.rename("Z", "B")
        store.delete("B")
        reopened = ListStore(path)
        self.assertEqual(reopened.snapshot(), {"Z": ["1"], "C": ["3"]})
        self.assertEqual(reopened.details()[1], {"name": "C", "count": 1, "meta": {"source": "Test"}})


class LibraryServerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.app = Application(cls.temp.name)
        cls.app.runner.backup_timing = FAST
        cls.server = Server(("127.0.0.1", 0), cls.app)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.app.close()
        cls.thread.join(2)
        cls.temp.cleanup()

    def request(self, route, body=None):
        headers = {"X-Studio-Token": self.app.token} if body is not None else {}
        request = urllib.request.Request(self.base + route, data=json.dumps(body).encode() if body is not None else None, headers=headers)
        with urllib.request.urlopen(request, timeout=10) as response:
            return response.read(), response.headers

    def test_session_reports_version_the_page_expects(self):
        from automator.server import APP_VERSION
        session = json.loads(self.request("/api/session")[0])
        page = Path("web/app.js").read_text(encoding="utf-8")
        self.assertEqual(session["version"], APP_VERSION)
        self.assertIn(f"const APP_VERSION = {APP_VERSION};", page)

    def test_case_backup_library_and_evidence(self):
        state = json.loads(self.request("/api/cases/create", {"number": "AZ 7", "examiner": "E. Muster", "note": ""})[0])
        self.assertEqual(state["case"]["title"], "AZ 7")
        pattern = open_chats(self.app.device)
        self.request("/api/backup", {"name": "Chats", "pattern": pattern, "serial": "demo", "order": "end_to_start", "max_pages": 20})
        self.app.runner.thread.join(30)
        library = json.loads(self.request("/api/library")[0])
        backup = library["backups"][0]
        self.assertEqual((backup["name"], backup["entries"], backup["status"]), ("Chats", 16, "abgeschlossen"))
        details = json.loads(self.request("/api/backup?id=" + urllib.request.quote(backup["id"]))[0])
        self.assertEqual(len(details["hash_list_sha256"]), 64)
        self.assertNotIn(" ", details["base"])
        report, headers = self.request(details["base"] + "bericht.html")
        self.assertIn(b"AZ 7", report)
        self.assertIn("default-src 'none'", headers["Content-Security-Policy"])
        self.request(details["base"] + urllib.request.quote(details["entries"][0]["pages"][0]["file"]))
        with self.assertRaises(urllib.error.HTTPError) as error:
            self.request("/evidence/../cases.json")
        self.assertEqual(error.exception.code, 404)
        error.exception.close()
        self.request("/api/backups/delete", {"id": backup["id"]})
        self.assertEqual(json.loads(self.request("/api/library")[0])["backups"], [])


if __name__ == "__main__":
    unittest.main()
