import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from automator.program import export_python, validate, ProgramError
from automator.runner import Runner, Stopped
from automator.scrolling import screen_snapshot, traverse_screen, U2ScrollDevice
from automator.storage import ListStore
from automator.server import Application


class Pages:
    demo = False
    name = "Testgerät"
    serial = "test"

    def __init__(self, pages=None, index=1):
        self.pages = pages or [["A", "B"], ["B", "C"], ["C", "D"]]
        self.index = min(index, len(self.pages) - 1)
        self.moves = []
        self.actions = []
        self.ticks = 0

    def window_size(self):
        return 400, 800

    def dump_hierarchy(self):
        self.ticks += 1
        root = ET.Element("hierarchy")
        ET.SubElement(root, "node", {"package": "com.android.systemui", "text": str(self.ticks), "bounds": "[0,0][400,40]"})
        region = ET.SubElement(root, "node", {"scrollable": "true", "bounds": "[0,100][400,700]"})
        for i, text in enumerate(self.pages[self.index]):
            ET.SubElement(region, "node", {"text": text, "resource-id": "title", "bounds": f"[20,{100 + i*50}][380,{150 + i*50}]"})
        return ET.tostring(root, encoding="unicode")

    def scroll_snapshot(self):
        return screen_snapshot(self.dump_hierarchy(), *self.window_size())

    def scroll_step(self, direction, snapshot):
        self.moves.append(direction)
        self.index = max(0, min(len(self.pages) - 1, self.index + (1 if direction == "up" else -1)))

    def swipe_points(self, points, duration):
        (x1, y1), (x2, y2) = points[0], points[-1]
        self.swipe(x1, y1, x2, y2, duration)

    def swipe(self, x1, y1, x2, y2, duration):
        self.scroll_step("up" if y1 > y2 else "down", None)

    def perform(self, action):
        self.actions.append(action)


class ScrollTests(unittest.TestCase):
    def test_rewinds_from_middle_collects_in_order_and_ignores_clock(self):
        device = Pages()
        self.assertEqual(traverse_screen(device, checkpoint=lambda _: None), ["A", "B", "C", "D"])
        self.assertEqual(device.moves, ["down"] * 3 + ["up"] * 4)

    def test_search_rewinds_even_if_target_initially_visible_and_stops_on_page(self):
        device = Pages()
        self.assertTrue(traverse_screen(device, target="C", checkpoint=lambda _: None))
        self.assertEqual(device.index, 1)
        self.assertEqual(device.moves, ["down"] * 3 + ["up"])

    def test_missing_target_and_contains(self):
        self.assertFalse(traverse_screen(Pages(), target="missing", checkpoint=lambda _: None))
        self.assertTrue(traverse_screen(Pages([["Alpha Beta"]], 0), target="Beta", match="contains", checkpoint=lambda _: None))
        self.assertFalse(traverse_screen(Pages([["Alpha Beta"]], 0), target="Beta", checkpoint=lambda _: None))

    def test_filter_uses_entire_screen_for_movement(self):
        self.assertEqual(traverse_screen(Pages(), by="textContains", value="D", checkpoint=lambda _: None), ["D"])

    def test_endless_scroll_and_cancellation(self):
        device = Pages()
        device.scroll_step = lambda direction, snapshot: device.pages[device.index].append(str(len(device.pages[device.index])))
        with self.assertRaisesRegex(ValueError, "Anfang"):
            traverse_screen(device, checkpoint=lambda _: None, max_swipes=4)
        def cancel(_):
            raise Stopped()
        with self.assertRaises(Stopped):
            traverse_screen(Pages(), checkpoint=cancel)

    def test_limits_are_not_silently_truncated(self):
        device = Pages([[str(i) for i in range(500)], ["new"]], 0)
        # Use compact synthetic nodes so all 500 values are actually visible.
        def snapshot():
            xml = '<hierarchy>' + ''.join(f'<node text="{text}" bounds="[0,0][10,10]"/>' for text in device.pages[device.index]) + '</hierarchy>'
            return screen_snapshot(xml, 400, 800)
        device.scroll_snapshot = snapshot
        with self.assertRaisesRegex(ValueError, "500"):
            traverse_screen(device, checkpoint=lambda _: None)

    def test_swipes_are_inside_scroll_region(self):
        calls = []
        adapter = U2ScrollDevice(SimpleNamespace(swipe_points=lambda points, duration: calls.append(points)))
        adapter.scroll_step("up", {"bounds": (50, 200, 350, 600)})
        adapter.scroll_step("down", {"bounds": (50, 200, 350, 600)})
        self.assertEqual(calls, [[(200, 520), (200, 280), (200, 280)], [(200, 280), (200, 520), (200, 520)]])

    def test_controlled_scroll_holds_before_release_and_stays_in_region(self):
        calls = []
        adapter = U2ScrollDevice(SimpleNamespace(swipe_points=lambda points, duration: calls.append(points)))
        adapter.scroll_by({"bounds": (0, 100, 400, 500)}, 150)
        adapter.scroll_by({"bounds": (0, 100, 400, 500)}, -1000)
        # The last point repeats the end point: the finger rests, so Android does not fling.
        self.assertEqual(calls, [[(200, 460), (200, 310), (200, 310)], [(200, 140), (200, 460), (200, 460)]])


class StoredScrollTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = ListStore(Path(self.temp.name) / "lists.json")
        self.runner = Runner(self.temp.name, self.store)
        # Do not sleep in traversal tests, but still honor cancellation.
        original = self.runner.checkpoint
        self.runner.checkpoint = lambda seconds=0: original(0)

    def run_program(self, program, device=None):
        device = device or Pages()
        self.runner.start(program, device)
        self.runner.thread.join(3)
        self.assertFalse(self.runner.thread.is_alive())
        return self.runner.snapshot()

    def test_capture_persists_and_foreach_search_uses_saved_values(self):
        result = self.run_program([{"op": "scan_list", "name": "Werte", "by": "textContains", "value": ""}])
        self.assertEqual(result["status"], "completed")
        self.assertEqual(ListStore(self.store.path).snapshot(), {"Werte": ["A", "B", "C", "D"]})
        device = Pages()
        result = self.run_program([{"op": "for_each", "name": "Werte", "body": [{"op": "scroll_find", "value": {"source": "item"}}, {"op": "type", "text": {"source": "item"}}]}], device)
        self.assertEqual(result["status"], "completed")
        self.assertEqual([n["text"] for n in device.actions], ["A", "B", "C", "D"])

    def test_failed_capture_keeps_previous_list(self):
        self.store.save("Werte", ["old"])
        device = Pages()
        def fail(direction, snapshot):
            raise RuntimeError("USB getrennt")
        device.scroll_step = fail
        result = self.run_program([{"op": "scan_list", "name": "Werte", "by": "textContains", "value": ""}], device)
        self.assertEqual(result["status"], "error")
        self.assertEqual(self.store.snapshot()["Werte"], ["old"])

    def test_not_found_stops_following_actions(self):
        device = Pages()
        result = self.run_program([{"op": "scroll_find", "value": "missing"}, {"op": "press", "key": "home"}], device)
        self.assertEqual(result["status"], "error")
        self.assertIn("nicht gefunden", result["logs"][-1]["text"])
        self.assertEqual(device.actions, [])

    def test_cancelled_capture_keeps_previous_list(self):
        self.store.save("Werte", ["old"])
        device = Pages()
        original = device.scroll_step
        def stop_on_second_page(direction, snapshot):
            original(direction, snapshot)
            if direction == "up":
                self.runner.stop()
        device.scroll_step = stop_on_second_page
        result = self.run_program([{"op": "scan_list", "name": "Werte", "by": "textContains", "value": ""}], device)
        self.assertEqual(result["status"], "stopped")
        self.assertEqual(self.store.snapshot()["Werte"], ["old"])

    def test_validation_rejects_search_outside_loop(self):
        for node in [{"op": "scroll_find", "value": {"source": "item"}}, {"op": "scroll_find", "value": ""}, {"op": "scroll_find", "value": "A", "match": "invalid"}]:
            with self.assertRaises(ProgramError):
                validate([node])

    def test_export_executes_capture_and_search_with_same_behavior(self):
        device = Pages()
        code = export_python([{"op": "scan_list", "name": "Captured", "by": "textContains", "value": ""}, {"op": "for_each", "name": "Saved", "body": [{"op": "scroll_find", "value": {"source": "item"}}]}], saved_lists={"Saved": ["D", "A"]})
        namespace = {}
        with patch.dict(sys.modules, {"uiautomator2": SimpleNamespace(connect=lambda: device)}), patch("time.sleep"), patch.object(Path, "mkdir"), patch("builtins.print"):
            exec(compile(code, "export.py", "exec"), namespace)
        self.assertEqual(namespace["lists"]["Captured"], ["A", "B", "C", "D"])
        self.assertEqual(device.index, 0)

    def test_application_capture_endpoint_and_restart_persistence(self):
        app = Application(self.temp.name)
        app.device = Pages()
        original = app.runner.checkpoint
        app.runner.checkpoint = lambda seconds=0: original(0)
        app.post("/api/capture", {"name": "Saved"})
        app.runner.thread.join(3)
        self.assertEqual(app.runner.snapshot()["status"], "completed")
        self.assertEqual(app.state()["list_names"], ["Saved"])
        self.assertEqual(Application(self.temp.name).lists.snapshot()["Saved"], ["A", "B", "C", "D"])


if __name__ == "__main__":
    unittest.main()
