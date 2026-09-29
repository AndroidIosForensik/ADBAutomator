import ast
import json
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from unittest.mock import Mock, PropertyMock, patch
import sys
from types import SimpleNamespace

from automator.devices import AndroidDevice, DemoDevice
from automator.program import ProgramError, export_python, validate
from automator.runner import Runner
from automator.server import Application, Server


class ProgramTests(unittest.TestCase):
    def test_rejects_empty_unknown_and_invalid_numbers(self):
        for program in [[], [{"op": "shell"}], [{"op": "wait", "seconds": -1}], [{"op": "wait", "seconds": float('nan')}], [{"op": "repeat", "times": 1.2, "body": []}], [{"op": "tap", "x": True, "y": 0}], [{"op": "tap", "x": 1.01, "y": 0}], [{"op": "click", "by": "arbitrary", "value": "abc"}]]:
            with self.subTest(program=program), self.assertRaises(ProgramError):
                validate(program)

    def test_validation_returns_clean_copy(self):
        raw = [{"op": "wait", "seconds": 0, "untrusted": "data"}]
        result = validate(raw)
        self.assertNotIn("untrusted", result[0])
        self.assertIn("untrusted", raw[0])

    def test_prevents_excessive_repeat_expansion(self):
        program = [{"op": "wait", "seconds": 0}]
        for _ in range(3):
            program = [{"op": "repeat", "times": 100, "body": program}]
        with self.assertRaises(ProgramError):
            validate(program)

    def test_export_quotes_code_injection_as_literal(self):
        text = '\"); __import__("os").system("bad") #\nä'
        code = export_python([{"op": "type", "text": text}])
        parsed = ast.parse(code)
        self.assertEqual(parsed.body[-1].value.args[0].value, text)

    def test_export_all_commands_and_nested_branches(self):
        commands = [
            {"op": "launch", "package": "com.android.settings"},
            {"op": "tap", "x": 1, "y": 0},
            {"op": "click", "by": "text", "value": "Anzeige"},
            {"op": "wait_for", "by": "resourceId", "value": "example:id", "timeout": 1},
            {"op": "type", "text": "Äpfel"},
            {"op": "swipe", "direction": "up"},
            {"op": "wait", "seconds": 0},
            {"op": "press", "key": "back"},
            {"op": "screenshot"},
            {"op": "repeat", "times": 2, "body": []},
            {"op": "if_exists", "by": "text", "value": "Anzeige", "body": [{"op": "press", "key": "home"}], "otherwise": [{"op": "wait", "seconds": 0}]},
        ]
        code = export_python(commands, 'serial"quoted')
        ast.parse(code)
        self.assertIn('if not d(resourceId="example:id").wait(timeout=1)', code)
        self.assertIn('for _ in range(2):\n    pass', code)


class RunnerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.runner = Runner(self.temp.name)
        self.device = DemoDevice()
        # No artificial demo delay during engine unit tests.
        self.device.demo = False

    def run_program(self, program):
        self.runner.start(program, self.device)
        self.runner.thread.join(3)
        self.assertFalse(self.runner.thread.is_alive())
        return self.runner.snapshot()

    def test_demo_end_to_end_with_artifact(self):
        result = self.run_program([{"op": "launch", "package": "com.android.settings"}, {"op": "click", "by": "text", "value": "Anzeige"}, {"op": "screenshot"}])
        self.assertEqual(result["status"], "completed")
        self.assertEqual(self.device.page, "Anzeige")
        self.assertEqual(len(list(Path(self.temp.name).glob('*.svg'))), 1)
        self.assertTrue(any(log.get('artifact') for log in result['logs']))

    def test_repeats_and_false_branch(self):
        result = self.run_program([{"op": "repeat", "times": 3, "body": [{"op": "press", "key": "home"}]}, {"op": "if_exists", "by": "text", "value": "fehlt", "body": [{"op": "type", "text": "falsch"}], "otherwise": [{"op": "type", "text": "richtig"}]}])
        self.assertEqual(result["status"], "completed")
        self.assertEqual(self.device.typed, "richtig")
        self.assertEqual(result["steps"], 6)

    def test_true_branch(self):
        result = self.run_program([{"op": "if_exists", "by": "text", "value": "Anzeige", "body": [{"op": "type", "text": "ja"}], "otherwise": []}])
        self.assertEqual(result['status'], 'completed')
        self.assertEqual(self.device.typed, 'ja')

    def test_missing_element_stops_at_error(self):
        result = self.run_program([{"op": "wait_for", "id": "missing", "by": "text", "value": "fehlt", "timeout": 0}, {"op": "type", "text": "niemals"}])
        self.assertEqual(result['status'], 'error')
        self.assertEqual(result['active_id'], 'missing')
        self.assertEqual(self.device.typed, '')

    def test_stop_interrupts_long_wait_and_rejects_second_start(self):
        self.runner.start([{"op": "wait", "seconds": 100}], self.device)
        with self.assertRaises(ValueError):
            self.runner.start([{"op": "press", "key": "home"}], self.device)
        self.runner.stop()
        self.runner.thread.join(1)
        self.assertEqual(self.runner.snapshot()['status'], 'stopped')

    def test_stop_interrupts_element_polling(self):
        self.runner.start([{"op": "wait_for", "by": "text", "value": "missing", "timeout": 100}], self.device)
        time.sleep(0.02)
        self.runner.stop()
        self.runner.thread.join(1)
        self.assertEqual(self.runner.snapshot()['status'], 'stopped')


class AndroidAdapterTests(unittest.TestCase):
    def test_connect_does_not_require_broken_android_metadata_rpc(self):
        device = Mock()
        info = PropertyMock(side_effect=RuntimeError('ApplicationSharedMemory not initialized'))
        type(device).info = info
        device.settings = {}
        device.adb_device.getprop.return_value = 'Pixel 9a'
        connect = Mock(return_value=device)
        with patch.dict(sys.modules, {'uiautomator2': SimpleNamespace(connect=connect)}):
            adapter = AndroidDevice('test-serial')
        self.assertEqual(adapter.name, 'Pixel 9a')
        info.assert_not_called()
        connect.assert_called_once_with('test-serial')
        device.adb_device.getprop.assert_called_once_with('ro.product.model')

    def adapter(self):
        adapter = AndroidDevice.__new__(AndroidDevice)
        adapter.device = Mock()
        adapter.lock = threading.RLock()
        return adapter

    def test_edge_coordinates_are_pixels(self):
        adapter = self.adapter()
        adapter.device.window_size.return_value = (1080, 2400)
        adapter.perform({"op": "tap", "x": 1, "y": 0.5})
        adapter.device.click.assert_called_once_with(1079, 1200)

    def test_hierarchy_uses_unique_selector_and_ignores_disabled(self):
        adapter = self.adapter()
        adapter.device.window_size.return_value = (100, 200)
        adapter.device.dump_hierarchy.return_value = '<hierarchy><node resource-id="duplicate" text="Eins" bounds="[0,0][50,50]"/><node resource-id="duplicate" text="Zwei" bounds="[0,50][50,100]"/><node text="Inaktiv" enabled="false" bounds="[0,100][50,150]"/></hierarchy>'
        nodes = adapter.elements()
        self.assertEqual(len(nodes), 2)
        self.assertEqual(nodes[0]['selector'], {"by": "text", "value": "Eins"})
        self.assertEqual(nodes[1]['bounds'], [0, .25, .5, .5])


class ServerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.app = Application(cls.temp.name)
        cls.server = Server(('127.0.0.1', 0), cls.app)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = f'http://127.0.0.1:{cls.server.server_port}'

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.app.close()
        cls.thread.join(2)
        cls.temp.cleanup()

    def request(self, route, body=None, headers=None):
        req = urllib.request.Request(self.base + route, data=json.dumps(body).encode() if body is not None else None, headers=headers or {})
        return urllib.request.urlopen(req, timeout=3)

    def test_local_session_and_assets(self):
        with self.request('/api/session') as response:
            self.assertTrue(json.load(response)['device']['demo'])
        with self.request('/') as response:
            self.assertIn(b'Droid', response.read())

    def test_second_server_cannot_bind_same_port(self):
        with self.assertRaises(OSError):
            Server(('127.0.0.1', self.server.server_port), self.app)

    def test_current_app_can_be_captured_without_package_input(self):
        with self.request('/api/current-app') as response:
            self.assertEqual(json.load(response)['package'], 'com.android.settings')

    def test_missing_token_and_cross_origin_are_rejected(self):
        for headers in [{}, {'X-Studio-Token': self.app.token, 'Origin': 'https://unrelated.example'}]:
            with self.subTest(origin=headers.get('Origin')):
                with self.assertRaises(urllib.error.HTTPError) as error:
                    self.request('/api/connect', {"serial": "demo"}, headers)
                self.assertEqual(error.exception.code, 403)
                error.exception.close()

    def test_rebinding_host_is_rejected(self):
        with self.assertRaises(urllib.error.HTTPError) as error:
            self.request('/api/session', headers={'Host': 'unrelated.example'})
        self.assertEqual(error.exception.code, 403)
        error.exception.close()

    def test_parent_paths_are_not_served(self):
        for path in ['/../app.py', '/vendor/%2e%2e/app.py', '/outputs/../app.py']:
            with self.subTest(path=path), self.assertRaises(urllib.error.HTTPError) as error:
                self.request(path)
            self.assertEqual(error.exception.code, 404)
            error.exception.close()

    def test_export_and_malformed_program(self):
        with self.request('/api/export', {"program": [{"op": "wait", "seconds": 1}]}, {'X-Studio-Token': self.app.token}) as response:
            ast.parse(json.load(response)['code'])
        with self.assertRaises(urllib.error.HTTPError) as error:
            self.request('/api/run', {"program": [{"op": "exec"}]}, {'X-Studio-Token': self.app.token})
        self.assertEqual(error.exception.code, 400)
        error.exception.close()


if __name__ == '__main__':
    unittest.main()
