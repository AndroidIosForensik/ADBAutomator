import copy
import unittest

from automator.backup import visible_text
from automator.report import report_html
from automator.report_text import entry_title, reading_text


HEADER = 'Zurück\nKontakt\nVideoanruf\nSprachanruf\nWeitere Optionen\n'
FOOTER = '\nEmojis, GIFs und Sticker\nNachricht\nAnhängen\nKamera\nSprachnachricht, Button. Doppeltippe und halte zum Aufnehmen.'


class ReportTests(unittest.TestCase):
    def test_toolbar_removal_does_not_remove_message_words_or_repetitions(self):
        body = 'Kamera\nZurück\nNachricht\nHallo\nHallo\n12:15\n12:15\n  eingerückter Text\n❤️'
        self.assertEqual(reading_text(HEADER + body + FOOTER, 'com.whatsapp'), body)

    def test_unknown_apps_and_unrecognized_layouts_remain_unchanged(self):
        raw = HEADER + 'Text' + FOOTER
        self.assertEqual(reading_text(raw, 'mail.app'), raw)
        self.assertEqual(reading_text('Weitere Optionen\nKamera', 'com.whatsapp'), 'Weitere Optionen\nKamera')

    def test_group_card_buttons_hidden_but_messages_kept(self):
        raw = HEADER + 'Gruppenbild bearbeiten\nKontakt\nDu hast diese Gruppe erstellt\nBeschreibung hinzufügen\xa0…\nMITGLIEDER HINZUFÜGEN\nHallo\n12:15\nMITGLIEDER HINZUFÜGEN' + FOOTER
        self.assertEqual(reading_text(raw, 'com.whatsapp'), 'Kontakt\nDu hast diese Gruppe erstellt\nHallo\n12:15\nMITGLIEDER HINZUFÜGEN')

    def test_media_controls_become_markers_without_losing_times(self):
        raw = HEADER + 'Bild vergrößern\n12:15\nBild weiterleiten\nGIF ansehen Beschreibung\nGIF abspielen Beschreibung\nAbbrechen\n12:16' + FOOTER
        self.assertEqual(reading_text(raw, 'com.whatsapp'), '[Bild]\n12:15\n[GIF]\n12:16')
        self.assertEqual(reading_text(HEADER + 'Bild weiterleiten\nEine Nachricht' + FOOTER, 'com.whatsapp'), 'Bild weiterleiten\nEine Nachricht')

    def record(self):
        return {'name': 'Test <Sicherung>', 'started': '2026-09-29T21:00:00+02:00', 'finished': None,
                'status': 'abgebrochen', 'message': 'Angehalten', 'case': {}, 'device': {}, 'pc': {},
                'app': 'com.whatsapp', 'options': {'order': 'end_to_start'},
                'warnings': [{'text': 'Lücke <prüfen>'}],
                'entries': [{'index': 1, 'text': 'Bild von Kontakt\nKontakt\nVorschau…', 'status': 'unvollständig',
                             'note': 'Limit erreicht', 'started': '2026-09-29T21:00:00+02:00', 'finished': None,
                             'pages': [{'file': 'E1/1.png', 'sha256': 'a', 'time': '', 'text': HEADER + 'neuer <script>alert(1)</script> & ❤️' + FOOTER},
                                       {'file': 'E1/2.png', 'sha256': 'b', 'time': '', 'text': HEADER + 'älterer Text' + FOOTER}]}]}

    def test_report_keeps_sources_and_warnings_and_does_not_change_record(self):
        record = self.record()
        before = copy.deepcopy(record)
        rendered = report_html(record, original_report='bericht.html')
        self.assertEqual(record, before)
        self.assertEqual(entry_title(record['entries'][0], record['app']), 'Kontakt')
        self.assertIn('neuer &lt;script&gt;alert(1)&lt;/script&gt; &amp; ❤️', rendered)
        self.assertNotIn('<script>', rendered)
        self.assertIn('Sprachnachricht, Button.', rendered)  # expandable, unmodified source
        self.assertIn('Lücke &lt;prüfen&gt;', rendered)
        self.assertIn('Limit erreicht', rendered)
        self.assertIn('Ursprünglichen Bericht öffnen', rendered)
        self.assertNotIn('<summary>Technische Angaben und Prüfsummen</summary><table><tr><th>Aktenzeichen', rendered)
        self.assertLess(rendered.index('alt="Screenshot zu Eintrag 1, Aufnahme 2"'), rendered.index('alt="Screenshot zu Eintrag 1, Aufnahme 1"'))

    def test_missing_text_has_screenshot_fallback(self):
        record = self.record()
        del record['entries'][0]['pages'][0]['text']
        self.assertIn('Für diese Aufnahme wurde kein Text gespeichert.', report_html(record))

    def test_capture_keeps_identical_text_in_distinct_nodes(self):
        nodes = ''.join(f'<node text="{text}" content-desc="{text}" bounds="[0,{i * 20}][100,{i * 20 + 20}]"/>'
                        for i, text in enumerate(['Hallo', 'Hallo', '12:15', '12:15']))
        snap = {'full_xml': '<hierarchy>' + nodes + '</hierarchy>', 'width': 100, 'height': 200}
        self.assertEqual(visible_text(snap), 'Hallo\nHallo\n12:15\n12:15')


if __name__ == '__main__':
    unittest.main()
