"""Readable, standalone HTML reports with the original sources one click away."""
from datetime import datetime
import html
import re
from urllib.parse import quote

from .report_text import entry_title, reading_text


def escape(value):
    return html.escape(str(value if value is not None else ''))


def url(path):
    return html.escape(quote(path, safe='/'))


def date(value):
    try:
        parsed = datetime.fromisoformat(value)
        return parsed.strftime('%d.%m.%Y, %H:%M:%S %z')
    except (ValueError, TypeError):
        return value or '—'


def text_html(text):
    # Preserve wording, paragraphs and repetitions. Times are visually secondary,
    # but are not assigned to a sender/message when the capture cannot prove it.
    rendered = []
    for line in text.split('\n'):
        style = 'time' if re.fullmatch(r'\d{1,2}:\d{2}', line.strip()) else 'line'
        rendered.append(f'<div class="{style}">{escape(line) or "<br>"}</div>')
    return ''.join(rendered)


def report_html(record, *, original_report=None):
    entries = record['entries']
    case, device, options = record['case'], record['device'], record['options']
    app = record.get('app', '')
    saved = sum(entry['status'] == 'gesichert' for entry in entries)
    pages = sum(len(entry['pages']) for entry in entries)
    result = f'{saved} von {len(entries)} Einträgen vollständig gesichert · {pages} Screenshots'
    sections, contents = [], []
    for entry in entries:
        title = entry_title(entry, app)
        anchor = f"eintrag-{entry['index']}"
        contents.append(f'<a href="#{anchor}"><span>{entry["index"]}.</span> {escape(title)}</a>')
        problem = f'<p class="problem">{escape(entry["status"])}{": " + escape(entry["note"]) if entry.get("note") else ""}</p>' if entry['status'] != 'gesichert' or entry.get('note') else ''
        source_info = f'<details class="entry-source"><summary>Angaben zum Eintrag</summary><pre>{escape(entry["text"])}</pre><p>Aufgenommen: {escape(date(entry["started"]))} bis {escape(date(entry.get("finished")))}</p></details>'
        page_parts = []
        ordered = list(enumerate(entry['pages'], 1))
        if options.get('order') == 'end_to_start':
            ordered.reverse()
        for number, page in ordered:
            raw = page.get('text')
            content = reading_text(raw, app) if raw is not None else None
            if content is None:
                body = '<p class="muted">Für diese Aufnahme wurde kein Text gespeichert. Der Inhalt steht im Screenshot.</p>'
            elif not content.strip():
                body = '<p class="muted">Kein auslesbarer Inhaltstext in dieser Aufnahme.</p>'
            else:
                body = f'<div class="transcript">{text_html(content)}</div>'
            source = ''
            if raw is not None:
                download = f'<a href="{url(page["text_file"])}">Originaltext als TXT</a>' if page.get('text_file') else ''
                source = f'<details class="raw"><summary>Originaltext anzeigen</summary><pre>{escape(raw)}</pre>{download}</details>'
            page_parts.append(f'''<section class="capture" aria-label="Aufnahme {number}">
<div class="capture-text"><h3>Aufnahme {number}</h3>{body}{source}</div>
<figure><a href="{url(page['file'])}"><img src="{url(page['file'])}" alt="Screenshot zu Eintrag {entry['index']}, Aufnahme {number}" loading="lazy"></a><figcaption><a href="{url(page['file'])}">Screenshot in Originalgröße</a></figcaption></figure>
</section>''')
        sections.append(f'<article id="{anchor}"><header><span class="entry-number">Eintrag {entry["index"]}</span><h2>{escape(title)}</h2>{problem}{source_info}</header>{"".join(page_parts) or "<p>Keine Aufnahmen vorhanden.</p>"}</article>')

    def row(label, value):
        return f'<tr><th>{escape(label)}</th><td>{escape(value)}</td></tr>' if value else ''
    meta = ''.join(row(label, value) for label, value in [
        ('Aktenzeichen', case.get('number')), ('Bearbeiter/in', case.get('examiner')), ('Notiz', case.get('note')),
        ('Beginn (PC-Zeit)', date(record['started'])), ('Ende (PC-Zeit)', date(record.get('finished'))),
        ('Gerät', device.get('label')), ('Hersteller / Modell', f"{device.get('manufacturer', '')} {device.get('model', '')}".strip()),
        ('Android-Version', device.get('android')), ('SDK', device.get('sdk')), ('Seriennummer (ADB)', device.get('serial')),
        ('Gerätezeit bei Beginn', device.get('device_time')), ('App', app), ('Aufnahmerichtung', options.get('order_label')),
        ('Seitenlimit pro Eintrag', options.get('max_pages')), ('Computer', record.get('pc', {}).get('computer')),
        ('Benutzer', record.get('pc', {}).get('user'))])
    file_rows = []
    for entry in entries:
        for page in entry['pages']:
            for file_key, hash_key in [('file', 'sha256'), ('text_file', 'text_sha256')]:
                if page.get(file_key):
                    file_rows.append(f'<tr><td><a href="{url(page[file_key])}">{escape(page[file_key])}</a></td><td class="hash">{escape(page.get(hash_key))}</td><td>{escape(date(page.get("time")))}</td></tr>')
    warnings = ''.join(f'<li>{escape(item["text"])}</li>' for item in record.get('warnings', []))
    warnings = f'<aside class="warning"><h2>Hinweise zur Sicherung</h2><ul>{warnings}</ul></aside>' if warnings else ''
    status = '' if record['status'] == 'abgeschlossen' and not record.get('message') else f'<p class="problem">Status: {escape(record["status"])}. {escape(record.get("message", ""))}</p>'
    original = f'<p>Diese Lesefassung wurde nachträglich erstellt. <a href="{url(original_report)}">Ursprünglichen Bericht öffnen</a>. Die ursprüngliche Hashliste bezieht sich auf die Originaldateien.</p>' if original_report else ''
    case_line = f'<p>Aktenzeichen: {escape(case["number"])}</p>' if case.get('number') else ''
    return f'''<!doctype html>
<html lang="de"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Sicherungsbericht · {escape(record['name'])}</title><style>
*{{box-sizing:border-box}}html{{scroll-behavior:smooth}}body{{margin:0;background:#fff;color:#222b35;font:15px/1.6 "Segoe UI",Arial,sans-serif}}
main{{max-width:1100px;margin:auto;padding:36px 30px}}h1{{font-size:28px;line-height:1.25;margin:0 0 8px}}h2{{font-size:24px;line-height:1.3;margin:2px 0 10px}}h3{{font-size:12px;font-weight:600;color:#66717d;margin:0 0 18px}}
p{{margin:8px 0}}a{{color:#275f84;text-underline-offset:3px}}a:focus-visible,summary:focus-visible{{outline:2px solid #275f84;outline-offset:4px}}.muted,.summary,.entry-number{{color:#66717d}}.summary{{font-size:13px}}.entry-number{{font-size:12px}}.intro{{margin:18px 0;font-size:13px;color:#596572;max-width:85ch}}
nav{{display:flex;flex-wrap:wrap;gap:6px 24px;border-block:1px solid #dce1e6;padding:14px 0;margin:24px 0}}nav a{{text-decoration:none}}nav span{{color:#73808a}}article{{margin:32px 0 48px;scroll-margin-top:20px}}article>header{{border-bottom:2px solid #354451;padding-bottom:14px}}
.capture{{display:grid;grid-template-columns:minmax(0,1fr) 240px;gap:36px;padding:24px 0;border-bottom:1px solid #dce1e6;align-items:start}}.capture-text{{min-width:0}}.transcript{{font-size:16px;line-height:1.75;overflow-wrap:anywhere}}.line{{white-space:pre-wrap}}.time{{font-size:12px;color:#6a737e;margin:3px 0 16px}}
figure{{margin:0}}img{{width:100%;height:auto;display:block;border:1px solid #dce1e6}}figcaption{{font-size:11px;margin-top:8px;text-align:center}}details{{font-size:12px;color:#5c6773;margin-top:14px}}summary{{cursor:pointer;width:fit-content}}pre{{white-space:pre-wrap;overflow-wrap:anywhere;font:13px/1.6 "Segoe UI",Arial,sans-serif;padding:14px;background:#f5f6f7;color:#343c46}}.problem,.warning{{color:#982d2d}}.warning{{border-left:3px solid;padding:8px 18px;margin:24px 0}}.warning h2{{font-size:16px}}
footer{{border-top:1px solid #dce1e6;padding-top:12px}}table{{border-collapse:collapse;width:100%;font-size:12px;margin:14px 0}}th,td{{text-align:left;vertical-align:top;padding:8px;border-bottom:1px solid #e3e6e9;overflow-wrap:anywhere}}th{{font-weight:600}}.meta th{{width:210px}}.hash{{font:11px/1.5 Consolas,monospace;word-break:break-all}}.table-scroll{{overflow-x:auto}}
@media(max-width:650px){{main{{padding:22px 18px}}.capture{{grid-template-columns:1fr;gap:20px}}figure{{max-width:260px}}h1{{font-size:24px}}}}
@media print{{main{{max-width:none;padding:0}}nav,.raw,.entry-source,footer,.intro{{display:none}}article{{break-before:page}}article:first-of-type{{break-before:auto}}.capture{{grid-template-columns:minmax(0,1fr) 180px;gap:22px}}figure{{break-inside:avoid}}.transcript{{font-size:11pt}}a{{color:inherit;text-decoration:none}}}}
</style></head><body><main>
<header><h1>{escape(record['name'])}</h1><p class="summary">Sicherungsbericht · {escape(date(record['started']))}</p>{case_line}<p>{result}</p>{status}</header>
<details class="intro"><summary>Zur Textdarstellung</summary><p>Lesefassung der gespeicherten Bildschirmtexte. Erkannte Bedienleisten sind ausgeblendet; Bild- und GIF-Bedienelemente erscheinen als Medienhinweis. Der Originaltext ist je Aufnahme aufklappbar. Überlappungen zwischen Aufnahmen bleiben erhalten. Absender und fehlende Texte werden nicht ergänzt.</p></details>
{warnings}<nav aria-label="Einträge">{''.join(contents)}</nav>
{''.join(sections) or '<p>Keine Einträge gesichert.</p>'}
<footer><details><summary>Technische Angaben und Prüfsummen</summary>{original}<table class="meta">{meta}</table>
<p><a href="hashes.sha256">SHA-256-Hashliste</a> · <a href="sicherung.json">Sicherungsdaten (JSON)</a> · <a href="eintraege.csv">Einträge (CSV)</a></p>
<div class="table-scroll"><table><thead><tr><th>Datei</th><th>SHA-256</th><th>Aufgenommen</th></tr></thead><tbody>{''.join(file_rows)}</tbody></table></div>
</details></footer></main></body></html>'''
