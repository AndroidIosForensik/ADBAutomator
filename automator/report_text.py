"""A conservative reading view; the saved screen text always remains the source."""
import re
import unicodedata


def comparable(value):
    return ''.join(c for c in value if unicodedata.category(c) != 'Cf').replace('\xa0', ' ').strip()


def entry_title(entry, app):
    lines = entry['text'].splitlines()
    if app in ('com.whatsapp', 'com.whatsapp.w4b') and len(lines) > 1 and lines[0] == 'Bild von ' + lines[1]:
        return lines[1]
    return next((line for line in lines if line.strip()), f"Eintrag {entry['index']}")


def reading_text(text, app):
    """Filter only recognized WhatsApp UI sequences, never isolated common words.

    Old captures lack node roles, so this is explicitly a reading view, not a
    reconstructed transcript. Do not infer senders or merge overlapping pages.
    """
    if app not in ('com.whatsapp', 'com.whatsapp.w4b'):
        return text
    lines = text.splitlines()
    keys = [comparable(line) for line in lines]
    start = 1 if keys and keys[0].startswith('Übersetzen: ') else 0
    if start >= len(keys) or keys[start] != 'Zurück':
        return text
    try:
        header_end = keys.index('Weitere Optionen', start + 1, min(len(keys), start + 9))
    except ValueError:
        return text
    lines = lines[header_end + 1:]
    keys = keys[header_end + 1:]
    first_time = next((i for i, key in enumerate(keys) if re.fullmatch(r'\d{1,2}:\d{2}', key)), len(keys))
    group_card = next((i for i, key in enumerate(keys[:first_time]) if key == 'Gruppenbild bearbeiten'), None)
    group_controls = {'Gruppenbild bearbeiten', 'Beschreibung hinzufügen …', 'MITGLIEDER HINZUFÜGEN',
                      'MITGLIEDSLABEL HINZUFÜGEN', 'PER LINK ODER QR-CODE EINLADEN'}
    encryption_banner = ('Nachrichten und Anrufe sind Ende-zu-Ende-verschlüsselt. Nur Personen in diesem Chat '
                         'können sie lesen, anhören oder teilen. Mehr erfahren')
    omitted = {i for i, key in enumerate(keys[:first_time])
               if key == encryption_banner or (group_card is not None and i >= group_card and key in group_controls)}
    # Only strip the composer when the entire known trailing control group fits.
    if len(keys) >= 5 and keys[-5:-1] == ['Emojis, GIFs und Sticker', 'Nachricht', 'Anhängen', 'Kamera'] and keys[-1].startswith('Sprachnachricht, Button.'):
        lines, keys = lines[:-5], keys[:-5]
    elif keys and keys[-1] == 'Nur WhatsApp kann Nachrichten senden.':
        lines, keys = lines[:-1], keys[:-1]
    if keys and keys[-1] == 'Zur letzten Nachricht gehen':
        lines, keys = lines[:-1], keys[:-1]

    result = []
    i = 0
    while i < len(lines):
        key = keys[i]
        if i in omitted:
            i += 1
            continue
        # Two accessibility descriptions for the very same GIF. Keep a media
        # marker, with the complete descriptions still in the expandable source.
        if key.startswith('GIF ansehen ') and i + 1 < len(keys) and keys[i + 1] == 'GIF abspielen ' + key[len('GIF ansehen '):]:
            result.append('[GIF]')
            i += 2
            if i < len(keys) and keys[i] == 'Abbrechen':
                i += 1
            continue
        # Image controls occur together, sometimes separated by the image time.
        if key in ('Bild vergrößern', 'Bild weiterleiten'):
            other = 'Bild weiterleiten' if key == 'Bild vergrößern' else 'Bild vergrößern'
            match = next((j for j in range(i + 1, min(i + 3, len(keys)))
                          if keys[j] == other and all(re.fullmatch(r'\d{1,2}:\d{2}', k) for k in keys[i + 1:j])), None)
            if match is not None:
                result.append('[Bild]')
                result.extend(lines[i + 1:match])
                i = match + 1
                continue
        result.append(lines[i])
        i += 1
    return '\n'.join(result)
