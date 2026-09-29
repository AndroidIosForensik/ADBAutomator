import json
import tempfile
import unittest
from unittest.mock import patch, mock_open

from automator.server import Application, inspector_ready


class InspectorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.app = Application(self.temp.name)
        self.addCleanup(self.temp.cleanup)
        self.addCleanup(self.app.close)

    def test_existing_inspector_is_reused_without_taking_ownership(self):
        with patch('automator.server.inspector_ready', return_value=True), \
                patch('automator.server.subprocess.Popen') as spawn:
            self.assertEqual(self.app.start_inspector(), {'url': 'http://127.0.0.1:20242'})
            self.app.close()
        spawn.assert_not_called()
        self.assertIsNone(self.app.inspector)

    def test_unrelated_listener_is_not_opened_or_replaced(self):
        with patch('automator.server.inspector_ready', return_value=False), \
                patch('automator.server.importlib.util.find_spec', return_value=True), \
                patch('automator.server.socket.socket') as socket, \
                patch('automator.server.subprocess.Popen') as spawn:
            socket.return_value.__enter__.return_value.connect_ex.return_value = 0
            with self.assertRaisesRegex(ValueError, 'uiautodev antwortet dort nicht'):
                self.app.start_inspector()
        spawn.assert_not_called()

    def test_free_port_starts_inspector_and_waits_for_identity(self):
        with patch('automator.server.inspector_ready', side_effect=[False, False, True]), \
                patch('automator.server.importlib.util.find_spec', return_value=True), \
                patch('automator.server.socket.socket') as socket, \
                patch('automator.server.subprocess.Popen') as spawn, \
                patch('automator.server.time.sleep'), patch('builtins.open', mock_open()):
            socket.return_value.__enter__.return_value.connect_ex.return_value = 1
            spawn.return_value.poll.return_value = None
            self.assertEqual(self.app.start_inspector(), {'url': 'http://127.0.0.1:20242'})
            spawn.assert_called_once()
            command = spawn.call_args.args[0]
            self.assertEqual(command[command.index("--server-url") + 1], "https://uiauto2.devsleep.com")
            self.app.close()
            spawn.return_value.terminate.assert_called_once()
            self.app.inspector = None

    def test_identity_requires_uiautodev_not_just_http_success(self):
        valid = {'description': 'client for https://web.uiauto.dev',
                 'version': '0.14.1', 'drivers': ['android', 'ios']}
        for body, expected in [(json.dumps(valid).encode(), True),
                               (b'{"status":"ok"}', False),
                               (b'[]', False), (b'<html>Other app</html>', False),
                               (b'\xff', False)]:
            with self.subTest(body=body), patch('automator.server.urllib.request.urlopen') as request:
                response = request.return_value.__enter__.return_value
                response.status = 200
                response.read.return_value = body
                self.assertEqual(inspector_ready('http://127.0.0.1:20242'), expected)

    def test_unreachable_inspector_is_not_ready(self):
        with patch('automator.server.urllib.request.urlopen', side_effect=OSError):
            self.assertFalse(inspector_ready('http://127.0.0.1:20242'))


if __name__ == '__main__':
    unittest.main()
