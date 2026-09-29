import tempfile
import time
import unittest

from automator.devices import DemoDevice
from automator.server import Application


class StepTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.app = Application(self.temp.name)
        self.device = self.app.device
        self.device.demo = False
        self.runner = self.app.runner
        self.addCleanup(self.cleanup)

    def cleanup(self):
        self.runner.stop()
        if self.runner.thread:
            self.runner.thread.join(2)
        self.temp.cleanup()

    def wait_for(self, status, steps=None):
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            state = self.runner.snapshot()
            if state['status'] == status and (steps is None or state['steps'] == steps):
                return state
            time.sleep(.005)
        self.fail(f'Expected {status}, {steps}; got {state}')

    def click(self, text):
        self.device.perform({'op': 'click', 'by': 'text', 'value': text})

    def test_display_list_loop_returns_to_actual_parent(self):
        self.click('Anzeige')
        values = self.device.read_list('textContains', '')
        self.app.lists.save('Bildschirmliste', values)
        self.app.post('/api/run', {'step_mode': True, 'program': [
            {'id': 'loop', 'op': 'for_each', 'name': 'Bildschirmliste', 'body': [
                {'id': 'click', 'op': 'click', 'by': 'text', 'value': {'source': 'item'}, 'timeout': 0},
                {'id': 'back', 'op': 'press', 'key': 'back'}]}]})
        state = self.wait_for('paused', 0)
        self.assertEqual(state['active_id'], 'loop')
        self.assertEqual(self.device.page, 'Anzeige')
        self.app.post('/api/step', {})
        state = self.wait_for('paused', 1)
        self.assertEqual(state['current_item'], 'Helligkeit')
        self.assertEqual(state['active_id'], 'click')
        for index, value in enumerate(values):
            self.app.post('/api/step', {})
            state = self.wait_for('paused', 2 + index * 2)
            self.assertEqual(state['active_id'], 'back')
            self.assertEqual(self.device.page, value)
            self.assertEqual(self.device.elements(), [])
            self.assertNotIn('Automatisch anpassen', self.device.screenshot()[0].decode())
            self.app.post('/api/step', {})
            state = self.wait_for('completed' if index == len(values) - 1 else 'paused', 3 + index * 2)
            self.assertEqual(self.device.page, 'Anzeige')
            self.assertEqual(self.device.read_list('textContains', ''), values)
        self.assertEqual(self.app.lists.snapshot()['Bildschirmliste'], values)

    def test_paused_run_blocks_changes_and_stop_wakes_worker(self):
        self.app.post('/api/run', {'step_mode': True, 'program': [{'op': 'type', 'text': 'never'}]})
        self.wait_for('paused', 0)
        for route, body in [('/api/connect', {'serial': 'demo'}), ('/api/action', {'action': {'op': 'press', 'key': 'home'}}), ('/api/run', {'program': [{'op': 'wait', 'seconds': 0}]})]:
            with self.subTest(route=route), self.assertRaises(ValueError):
                self.app.post(route, body)
        self.app.post('/api/stop', {})
        self.wait_for('stopped', 0)
        self.assertEqual(self.device.typed, '')

    def test_resume_finishes_nested_loops_with_correct_values(self):
        self.app.lists.save('Outer', ['A', 'B'])
        self.app.lists.save('Inner', ['X'])
        program = [{'op': 'for_each', 'name': 'Outer', 'body': [
            {'op': 'for_each', 'name': 'Inner', 'body': [{'op': 'type', 'text': {'source': 'item'}}]},
            {'id': 'outer-text', 'op': 'type', 'text': {'source': 'item'}}]}]
        self.runner.start(program, self.device, True)
        self.wait_for('paused', 0)
        for steps in range(1, 4):
            self.runner.advance()
            state = self.wait_for('paused', steps)
        self.assertEqual(state['active_id'], 'outer-text')
        self.assertEqual(state['current_item'], 'A')
        self.app.post('/api/resume', {})
        self.wait_for('completed', 7)
        self.assertEqual(self.device.typed, 'B')

    def test_pause_waits_for_current_command_and_does_not_skip_next(self):
        self.runner.start([{'op': 'wait', 'seconds': .15}, {'op': 'type', 'text': 'after'}], self.device)
        self.wait_for('running', 1)
        self.app.post('/api/pause', {})
        self.wait_for('paused', 1)
        self.assertEqual(self.device.typed, '')
        self.app.post('/api/step', {})
        self.wait_for('completed', 2)
        self.assertEqual(self.device.typed, 'after')

    def test_invalid_controls_do_not_start_a_run(self):
        for route in ['/api/step', '/api/pause', '/api/resume']:
            with self.subTest(route=route), self.assertRaises(ValueError):
                self.app.post(route, {})
        with self.assertRaises(ValueError):
            self.runner.start([{'op': 'wait', 'seconds': 0}], self.device, 'false')
        self.assertEqual(self.runner.status, 'idle')

    def test_demo_tap_and_back_use_navigation_history(self):
        for text in ['Anzeige', 'Helligkeit']:
            element = next(e for e in self.device.elements() if e['label'] == text)
            x1, y1, x2, y2 = element['bounds']
            self.device.perform({'op': 'tap', 'x': (x1 + x2) / 2, 'y': (y1 + y2) / 2})
        self.device.perform({'op': 'press', 'key': 'back'})
        self.assertEqual(self.device.page, 'Anzeige')
        self.device.perform({'op': 'press', 'key': 'back'})
        self.assertEqual(self.device.page, 'Einstellungen')


if __name__ == '__main__':
    unittest.main()
