"""Select repeated UI containers instead of collecting their individual text nodes."""
import re
import statistics
import xml.etree.ElementTree as ET


def validate_item_pattern(pattern):
    if not isinstance(pattern, dict) or not {'region', 'item'} <= set(pattern) or set(pattern) - {'region', 'item', 'source'}:
        raise ValueError('Ungültiges Listenelement-Muster.')
    result = {}
    for key in ('region', 'item'):
        path = pattern[key]
        if not isinstance(path, list) or len(path) > 32 or (key == 'item' and not path):
            raise ValueError('Ungültiger Pfad für das Listenelement.')
        result[key] = []
        for part in path:
            if not isinstance(part, dict) or set(part) != {'class', 'resource_id'} or any(not isinstance(value, str) or len(value) > 2000 for value in part.values()):
                raise ValueError('Ungültiges Listenelement-Muster.')
            result[key].append(dict(part))
    if 'source' in pattern:
        if pattern['source'] not in {'text', 'content-desc', 'children'}:
            raise ValueError('Ungültige Textquelle für das Listenelement.')
        result['source'] = pattern['source']
    return result


def item_bounds(node, width, height):
    if node.get('visible-to-user') == 'false' or node.get('package') == 'com.android.systemui':
        return None
    match = re.fullmatch(r'\[(-?\d+),(-?\d+)\]\[(-?\d+),(-?\d+)\]', node.get('bounds', ''))
    if not match:
        return None
    x1, y1, x2, y2 = map(int, match.groups())
    box = (max(0, x1), max(0, y1), min(width, x2), min(height, y2))
    return box if box[2] > box[0] and box[3] > box[1] else None


def item_text(node, width, height):
    if not item_bounds(node, width, height):
        return ''
    # A parent often already describes the entire mail/card. Do not also emit
    # its descendants (sender, subject, preview, date) as separate list values.
    own = node.get('text', '').strip() or node.get('content-desc', '').strip()
    if own:
        return own
    parts = []
    for child in node:
        text = item_text(child, width, height)
        if text and text not in parts:
            parts.append(text)
    return '\n'.join(parts)


def pattern_nodes(root, path, width, height):
    nodes = [root]
    for segment in path:
        nodes = [child for parent in nodes for child in parent
                 if child.tag == 'node' and item_bounds(child, width, height)
                 and child.get('class', '') == segment['class']
                 and child.get('resource-id', '') == segment['resource_id']]
    return nodes


def selected_region(xml, width, height, pattern):
    root = ET.fromstring(xml)
    regions = pattern_nodes(root, pattern['region'], width, height)
    if len(regions) != 1:
        raise ValueError('Der ausgewählte Listenbereich ist nicht mehr eindeutig sichtbar. Bitte das Listenelement erneut auswählen.')
    return regions[0]


def read_list_items(xml, width, height, pattern):
    region = selected_region(xml, width, height, pattern)
    result = []
    for node in pattern_nodes(region, pattern['item'], width, height):
        source = pattern.get('source', 'children')
        if source != 'children' and not node.get(source, '').strip():
            continue
        text = item_text(node, width, height)
        if not text:
            continue
        if len(text) > 2000:
            raise ValueError('Ein Listeneintrag enthält mehr als 2000 Zeichen. Bitte einen kleineren Bereich auswählen.')
        result.append(text)
        if len(result) > 500:
            raise ValueError('Mehr als 500 Listeneinträge gefunden. Bitte die Auswahl eingrenzen.')
    return result


def list_entries(snapshot, pattern, reference_height=None, uncut=()):
    """Entries of the selected list in screen order, each marked complete or cut off.

    Android reports bounds clipped to the visible area, so an entry cut off at
    the edge of the list is shorter than a typical entry of the same list; its
    text is only a fragment (for example just the second line of a card).
    `uncut` names edges that cannot cut anything off: "top" at the start of
    the list, "bottom" at its end.
    """
    xml, width, height = snapshot["full_xml"], snapshot["width"], snapshot["height"]
    region = selected_region(xml, width, height, pattern)
    box = item_bounds(region, width, height) or (0, 0, width, height)
    source = pattern.get("source", "children")
    entries = []
    for node in pattern_nodes(region, pattern["item"], width, height):
        if source != "children" and not node.get(source, "").strip():
            continue
        text, bounds = item_text(node, width, height), item_bounds(node, width, height)
        if text and bounds:
            entries.append({"text": text, "bounds": bounds})
    entries.sort(key=lambda entry: (entry["bounds"][1], entry["bounds"][0]))
    inner = [e["bounds"][3] - e["bounds"][1] for e in entries if e["bounds"][1] > box[1] + 2 and e["bounds"][3] < box[3] - 2]
    typical = statistics.median(inner) if inner else reference_height
    for entry in entries:
        top, bottom = entry["bounds"][1], entry["bounds"][3]
        at_edge = (top <= box[1] + 2 and "top" not in uncut) or (bottom >= box[3] - 2 and "bottom" not in uncut)
        entry["complete"] = not at_edge or not typical or bottom - top >= typical * .9
    return box, entries


def list_item_candidates(xml, width, height):
    root = ET.fromstring(xml)
    candidates = []
    preview_cache = {}

    def visit(parent, path, region_path):
        for node in parent:
            if node.tag != 'node' or not item_bounds(node, width, height):
                continue
            descriptor = {'class': node.get('class', ''), 'resource_id': node.get('resource-id', '')}
            node_path = path + [descriptor]
            if len(node_path) > 32:
                continue
            if node.get('scrollable') == 'true':
                visit(node, node_path, node_path)
                continue
            text = item_text(node, width, height)
            if text and node_path[len(region_path):]:
                source = 'text' if node.get('text', '').strip() else 'content-desc' if node.get('content-desc', '').strip() else 'children'
                pattern = {'region': region_path, 'item': node_path[len(region_path):], 'source': source}
                key = repr(pattern)
                if key not in preview_cache:
                    try:
                        preview_cache[key] = read_list_items(xml, width, height, pattern)
                    except ValueError:
                        preview_cache[key] = []
                values = preview_cache[key]
                if values:
                    x1, y1, x2, y2 = item_bounds(node, width, height)
                    candidates.append({'bounds': [x1 / width, y1 / height, x2 / width, y2 / height],
                                       'pattern': pattern, 'label': text[:200], 'count': len(values),
                                       'preview': values[:5], 'depth': len(pattern['item'])})
            visit(node, node_path, region_path)
    visit(root, [], [])
    return candidates
