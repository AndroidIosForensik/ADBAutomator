import ast
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from automator.devices import DemoDevice
from automator.lists import read_visible_texts
from automator.program import ProgramError, export_python, validate
from automator.runner import Runner

ITEM = {"source": "item"}


def make_list(name="Werte", items=None):
    return {"op": "list_create", "name": name, "items": ["Anzeige", "Akku"] if items is None else items}


def each(body, name="Werte"):
    return {"op": "for_each", "name": name, "body": body}


class ListTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.runner = Runner(self.temp.name)
        self.device = DemoDevice()
        self.device.demo = False
        self.device.perform = Mock(wraps=self.device.perform)

    def run_program(self, program):
        self.runner.start(program, self.device)
        self.runner.thread.join(3)
        self.assertFalse(self.runner.thread.is_alive())
        return self.runner.snapshot()

    def typed_values(self):
        return [call.args[0]['text'] for call in self.device.perform.call_args_list if call.args[0]['op'] == 'type']

    def test_preserves_order_duplicates_and_does_not_interpolate_values(self):
        values = ['Äpfel', 'Äpfel', '{item}', '"\nText']
        result = self.run_program([make_list(items=values), each([{"op": "type", "text": ITEM}])])
        self.assertEqual(result['status'], 'completed')
        self.assertEqual(self.typed_values(), values)

    def test_empty_list_skips_body(self):
        result = self.run_program([make_list(items=[]), each([{"op": "press", "key": "home"}])])
        self.assertEqual(result['status'], 'completed')
        self.device.perform.assert_not_called()
        self.assertTrue(any('leer' in log['text'] for log in result['logs']))

    def test_nested_loop_restores_outer_item(self):
        result = self.run_program([make_list('Außen', ['A', 'B']), make_list('Innen', ['X']), each([each([{"op": "type", "text": ITEM}], 'Innen'), {"op": "type", "text": ITEM}], 'Außen')])
        self.assertEqual(result['status'], 'completed')
        self.assertEqual(self.typed_values(), ['X', 'A', 'X', 'B'])

    def test_replacing_list_during_iteration_uses_original_snapshot(self):
        result = self.run_program([make_list(items=['A', 'B']), each([make_list(items=['C']), {"op": "type", "text": ITEM}])])
        self.assertEqual(result['status'], 'completed')
        self.assertEqual(self.typed_values(), ['A', 'B'])

    def test_list_must_be_created_before_use(self):
        result = self.run_program([each([]), make_list()])
        self.assertEqual(result['status'], 'error')
        self.assertIn('noch nicht', result['logs'][-1]['text'])

    def test_list_state_is_reset_between_runs(self):
        self.run_program([make_list()])
        result = self.run_program([each([]), make_list()])
        self.assertEqual(result['status'], 'error')

    def test_read_screen_and_click_every_entry(self):
        result = self.run_program([{"op": "read_list", "name": "Werte", "by": "textContains", "value": ""}, each([{"op": "click", "by": "text", "value": ITEM, "timeout": 0}, {"op": "press", "key": "back"}])])
        self.assertEqual(result['status'], 'completed')
        clicks = [call.args[0]['value'] for call in self.device.perform.call_args_list if call.args[0]['op'] == 'click']
        self.assertEqual(clicks, [row[0] for row in self.device._rows()])

    def test_cancel_inside_foreach(self):
        self.runner.start([make_list(), each([{"op": "wait", "seconds": 100}])], self.device)
        self.runner.stop()
        self.runner.thread.join(1)
        self.assertEqual(self.runner.snapshot()['status'], 'stopped')

    def test_validation_rejects_invalid_lists_and_out_of_scope_items(self):
        programs = [
            [make_list(items=['x'] * 501)], [make_list(items=[3])],
            [make_list(items=['a' * 2001])], [make_list(name=' ')],
            [{"op": "type", "text": ITEM}],
            [{"op": "click", "by": "text", "value": ITEM}],
            [each([])],
            [{"op": "read_list", "name": "Werte", "by": "shell", "value": "x"}],
            [{"op": "read_list", "name": "Werte", "by": "resourceId", "value": ""}],
        ]
        for program in programs:
            with self.subTest(program=program), self.assertRaises(ProgramError):
                validate(program)

    def test_expanded_list_loops_obey_step_limit(self):
        with self.assertRaises(ProgramError):
            validate([make_list(items=['x'] * 101), each([each([{"op": "type", "text": ITEM}])])])


class ExtractionTests(unittest.TestCase):
    XML = '''<hierarchy>
      <node text="Eins" resource-id="row" class="Text" bounds="[0,0][20,20]"/>
      <node text="Eins" resource-id="row" class="Text" bounds="[0,20][20,40]"/>
      <node text="Zwei" resource-id="row" class="Other" bounds="[-10,40][20,60]"/>
      <node text="Offscreen" resource-id="row" bounds="[100,100][120,120]"/>
      <node text="Hidden" visible-to-user="false" bounds="[0,0][20,20]"/>
      <node text="  " bounds="[0,0][20,20]"/>
    </hierarchy>'''

    def test_filters_and_visibility_preserve_duplicates(self):
        self.assertEqual(read_visible_texts(self.XML, 100, 100, 'resourceId', 'row'), ['Eins', 'Eins', 'Zwei'])
        self.assertEqual(read_visible_texts(self.XML, 100, 100, 'className', 'Text'), ['Eins', 'Eins'])
        self.assertEqual(read_visible_texts(self.XML, 100, 100, 'textContains', 'Zw'), ['Zwei'])
        self.assertEqual(read_visible_texts(self.XML, 100, 100, 'textContains', 'missing'), [])

    def test_extraction_rejects_excess_without_silent_truncation(self):
        xml = '<hierarchy>' + '<node text="a" bounds="[0,0][10,10]"/>' * 501 + '</hierarchy>'
        with self.assertRaises(ValueError):
            read_visible_texts(xml, 100, 100, 'textContains', '')


class ExportListTests(unittest.TestCase):
    def execute_export(self, program, device):
        code = export_python(program)
        ast.parse(code)
        with patch.dict(sys.modules, {'uiautomator2': SimpleNamespace(connect=lambda: device)}), patch.object(Path, 'mkdir'):
            exec(compile(code, '<export-test>', 'exec'), {})
        return code

    def test_nested_scopes_and_quotes_in_export(self):
        device = Mock()
        program = [make_list('A', ['"quoted"', '__import__("bad")']), make_list('B', ['inner']), each([each([{"op": "type", "text": ITEM}], 'B'), {"op": "type", "text": ITEM}], 'A')]
        self.execute_export(program, device)
        self.assertEqual([call.args[0] for call in device.send_keys.call_args_list], ['inner', '"quoted"', 'inner', '__import__("bad")'])

    def test_exported_reader_has_same_results_as_runner(self):
        device = Mock()
        device.window_size.return_value = (100, 100)
        device.dump_hierarchy.return_value = ExtractionTests.XML
        code = self.execute_export([{"op": "read_list", "name": "Werte", "by": "resourceId", "value": "row"}, each([{"op": "type", "text": ITEM}])], device)
        self.assertNotIn('from automator', code)
        self.assertEqual([call.args[0] for call in device.send_keys.call_args_list], ['Eins', 'Eins', 'Zwei'])
