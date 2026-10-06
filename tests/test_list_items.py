import ast
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from automator.list_items import list_item_candidates, read_list_items
from automator.program import validate, ProgramError, export_python
from automator.scrolling import screen_snapshot, traverse_screen
from automator.server import Application


def mailbox(names=('Google', 'ChatGPT'), parent_text=False):
    rows = []
    for index, name in enumerate(names):
        top = 100 + index * 150
        own = f'text="{name}, Betreff, Vorschau"' if parent_text else ''
        rows.append(f'''<node class="Card" resource-id="mail" bounds="[0,{top}][400,{top+140}]" {own}>
          <node class="Text" resource-id="sender" text="{name}" bounds="[10,{top+5}][380,{top+30}]"/>
          <node class="Text" resource-id="subject" text="Betreff" bounds="[10,{top+35}][380,{top+60}]"/>
          <node class="Text" resource-id="preview" text="Vorschau" bounds="[10,{top+65}][380,{top+100}]"/>
        </node>''')
    # The unrelated, larger scroll pane must not be captured or swiped.
    return '<hierarchy><node class="Sidebar" resource-id="other" scrollable="true" bounds="[410,0][1000,800]"><node text="Unrelated" bounds="[410,0][1000,100]"/></node><node class="List" resource-id="inbox" scrollable="true" bounds="[0,80][400,750]"><node class="Header" text="5 neue" bounds="[0,80][400,100]"/>' + ''.join(rows) + '</node></hierarchy>'


def row_pattern(xml):
    return next(c['pattern'] for c in list_item_candidates(xml, 1000, 800)
                if c['pattern']['item'][-1]['resource_id'] == 'mail')


class MailPages:
    demo = False
    name = 'Test'
    serial = 'test'

    def __init__(self):
        self.index = 1
        self.boxes = []

    def dump_hierarchy(self):
        return mailbox([('Google', 'ChatGPT'), ('ChatGPT', 'Newsletter')][self.index])

    def window_size(self):
        return 1000, 800

    def scroll_snapshot(self):
        return screen_snapshot(self.dump_hierarchy(), *self.window_size())

    def scroll_step(self, direction, snapshot):
        self.boxes.append(snapshot['bounds'])
        self.index = max(0, min(1, self.index + (1 if direction == 'up' else -1)))

    def swipe_points(self, points, duration):
        (x1, y1), (x2, y2) = points[0], points[-1]
        self.swipe(x1, y1, x2, y2, duration)

    def swipe(self, x1, y1, x2, y2, duration):
        self.index = max(0, min(1, self.index + (1 if y1 > y2 else -1)))


class ItemTests(unittest.TestCase):
    def test_children_form_one_mail_and_header_is_excluded(self):
        xml = mailbox()
        pattern = row_pattern(xml)
        self.assertEqual(read_list_items(xml, 1000, 800, pattern), ['Google\nBetreff\nVorschau', 'ChatGPT\nBetreff\nVorschau'])
        candidate = next(c for c in list_item_candidates(xml, 1000, 800) if c['pattern'] == pattern)
        self.assertEqual(candidate['count'], 2)
        self.assertEqual(candidate['bounds'], [0, .125, .4, .3])

    def test_parent_summary_is_not_repeated_as_children(self):
        xml = mailbox(parent_text=True)
        self.assertEqual(read_list_items(xml, 1000, 800, row_pattern(xml)), ['Google, Betreff, Vorschau', 'ChatGPT, Betreff, Vorschau'])
        xml = xml.replace('text="Google, Betreff, Vorschau"', 'content-desc="Google, Betreff, Vorschau"')
        self.assertEqual(read_list_items(xml, 1000, 800, row_pattern(xml))[0], 'Google, Betreff, Vorschau')

    def test_repetition_is_based_on_xml_siblings_not_total_matches(self):
        candidates = list_item_candidates(mailbox(), 1000, 800)
        rows = [c for c in candidates if c['pattern']['item'][-1]['resource_id'] == 'mail']
        senders = [c for c in candidates if c['pattern']['item'][-1]['resource_id'] == 'sender']
        self.assertTrue(all(c['in_list'] and c['repeated'] for c in rows))
        self.assertTrue(all(c['count'] == 2 and not c['repeated'] for c in senders))

    def test_single_clickable_row_and_nested_wrappers_remain_selectable(self):
        root = ET.fromstring(mailbox(names=('Google',)))
        region = next(node for node in root.iter('node') if node.get('resource-id') == 'inbox')
        row = next(node for node in region if node.get('resource-id') == 'mail')
        row.set('clickable', 'true')
        region.remove(row)
        wrapper = ET.SubElement(region, 'node', {'class': 'Wrapper', 'bounds': '[0,100][400,700]'})
        wrapper.append(row)
        xml = ET.tostring(root, encoding='unicode')
        candidate = next(c for c in list_item_candidates(xml, 1000, 800)
                         if c['pattern']['item'][-1]['resource_id'] == 'mail')
        self.assertTrue(candidate['clickable'])
        self.assertFalse(candidate['repeated'])
        self.assertEqual(candidate['depth'], 2)
        self.assertEqual(read_list_items(xml, 1000, 800, candidate['pattern']), ['Google\nBetreff\nVorschau'])

    def test_candidate_bounds_respect_xml_ancestor_viewport(self):
        xml = '''<hierarchy><node class="List" scrollable="true" bounds="[0,100][400,600]">
          <node class="Card" text="Oben" bounds="[0,0][400,150]"/>
          <node class="Card" text="Unten" bounds="[0,550][400,750]"/>
          <node class="Card" text="Außerhalb" bounds="[0,650][400,750]"/>
        </node></hierarchy>'''
        candidates = list_item_candidates(xml, 1000, 800)
        self.assertEqual([c['label'] for c in candidates], ['Oben', 'Unten'])
        self.assertEqual([c['bounds'] for c in candidates], [[0, .125, .4, .1875], [0, .6875, .4, .75]])
        self.assertEqual(candidates[0]['preview'], ['Oben', 'Unten'])
        self.assertEqual(candidates[0]['count'], 2)

    def test_category_card_with_same_class_is_not_a_mail_summary(self):
        xml = mailbox(parent_text=True)
        pattern = row_pattern(xml)
        category = '<node class="Card" resource-id="mail" bounds="[0,400][400,500]"><node class="Text" text="Benachrichtigungen" bounds="[0,400][400,440]"/><node class="Text" text="5 neue" bounds="[0,440][400,480]"/></node>'
        root = ET.fromstring(xml)
        next(node for node in root.iter('node') if node.get('resource-id') == 'inbox').append(ET.fromstring(category))
        xml = ET.tostring(root, encoding='unicode')
        self.assertEqual(len(read_list_items(xml, 1000, 800, {**pattern, 'source': 'children'})), 3)
        self.assertEqual(read_list_items(xml, 1000, 800, pattern), ['Google, Betreff, Vorschau', 'ChatGPT, Betreff, Vorschau'])

    def test_hidden_parent_hides_descendants(self):
        xml = mailbox()
        pattern = row_pattern(xml)
        xml = xml.replace('class="Card"', 'visible-to-user="false" class="Card"', 1)
        self.assertEqual(read_list_items(xml, 1000, 800, pattern), ['ChatGPT\nBetreff\nVorschau'])

    def test_rewind_grouping_overlap_and_selected_scroll_region(self):
        device = MailPages()
        pattern = row_pattern(device.dump_hierarchy())
        values = traverse_screen(device, pattern=pattern, checkpoint=lambda _: None)
        self.assertEqual(values, [f'{name}\nBetreff\nVorschau' for name in ['Google', 'ChatGPT', 'Newsletter']])
        self.assertEqual(set(device.boxes), {(0, 80, 400, 750)})

    def test_missing_or_ambiguous_region_fails_without_fallback(self):
        xml = mailbox()
        pattern = row_pattern(xml)
        with self.assertRaises(ValueError):
            read_list_items(xml.replace('resource-id="inbox"', 'resource-id="changed"'), 1000, 800, pattern)
        xml = xml.replace('</hierarchy>', '<node class="List" resource-id="inbox" bounds="[0,0][100,100]"/></hierarchy>')
        with self.assertRaises(ValueError):
            read_list_items(xml, 1000, 800, pattern)

    def test_validation_and_standalone_export_keep_pattern(self):
        device = MailPages()
        pattern = row_pattern(device.dump_hierarchy())
        program = [{'op': 'scan_list', 'name': 'Mails', 'by': 'textContains', 'value': '', 'pattern': pattern}]
        self.assertEqual(validate(program)[0]['pattern'], pattern)
        code = export_python(program)
        ast.parse(code)
        namespace = {}
        with patch.dict(sys.modules, {'uiautomator2': SimpleNamespace(connect=lambda: device)}), patch('time.sleep'), patch.object(Path, 'mkdir'), patch('builtins.print'):
            exec(compile(code, 'export.py', 'exec'), namespace)
        self.assertEqual(len(namespace['lists']['Mails']), 3)
        for invalid in [{}, {'region': [], 'item': []}, {'region': [], 'item': [{'class': 5, 'resource_id': ''}]}]:
            with self.subTest(pattern=invalid), self.assertRaises(ProgramError):
                validate([{**program[0], 'pattern': invalid}])

    def test_capture_saves_grouped_rows_and_failed_retry_preserves_list(self):
        with tempfile.TemporaryDirectory() as directory:
            app = Application(directory)
            app.device = MailPages()
            pattern = row_pattern(app.device.dump_hierarchy())
            original = app.runner.checkpoint
            app.runner.checkpoint = lambda seconds=0: original(0)
            body = {'name': 'Mails', 'pattern': pattern, 'serial': 'test'}
            app.post('/api/capture', body)
            app.runner.thread.join(3)
            self.assertEqual(app.runner.status, 'completed')
            values = app.lists.snapshot()['Mails']
            self.assertEqual(len(values), 3)
            with self.assertRaises(ValueError):
                app.post('/api/capture', {**body, 'serial': 'another-device'})
            app.device.dump_hierarchy = lambda: '<hierarchy/>'
            app.post('/api/capture', body)
            app.runner.thread.join(3)
            self.assertEqual(app.runner.status, 'error')
            self.assertEqual(Application(directory).lists.snapshot()['Mails'], values)


if __name__ == '__main__':
    unittest.main()
