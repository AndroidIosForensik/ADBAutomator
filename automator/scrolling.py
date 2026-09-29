"""Shared scroll traversal, also embedded in exported Python scripts."""
import re
import statistics
import time
import xml.etree.ElementTree as ET

from .lists import MAX_LIST_ITEMS, read_visible_texts
from .list_items import selected_region, item_bounds, read_list_items, list_entries


def screen_snapshot(xml, width, height, pattern=None):
    root = ET.fromstring(xml)

    def bounds(node):
        match = re.fullmatch(r"\[(-?\d+),(-?\d+)\]\[(-?\d+),(-?\d+)\]", node.get("bounds", ""))
        if not match:
            return None
        a, b, c, d = map(int, match.groups())
        a, b, c, d = max(0, a), max(0, b), min(width, c), min(height, d)
        return (a, b, c, d) if c > a and d > b else None

    candidates = [(n, bounds(n)) for n in root.iter("node") if n.get("scrollable") == "true" and n.get("visible-to-user") != "false"]
    candidates = [(n, box) for n, box in candidates if box]
    scrollable = bool(pattern or candidates)
    if pattern:
        region = selected_region(xml, width, height, pattern)
        box = item_bounds(region, width, height) or (0, int(height * .1), width, int(height * .9))
    elif candidates:
        region, box = max(candidates, key=lambda pair: (pair[1][2] - pair[1][0]) * (pair[1][3] - pair[1][1]))
    else:
        # System bars contain clocks and other changing content unrelated to scrolling.
        for parent in root.iter():
            for child in list(parent):
                if child.get("package") == "com.android.systemui":
                    parent.remove(child)
        region, box = root, (0, int(height * .1), width, int(height * .9))
    visible = []
    for node in region.iter("node"):
        if node.get("visible-to-user") != "false" and bounds(node):
            visible.append((node.get("text", ""), node.get("content-desc", ""), node.get("resource-id", ""), node.get("class", ""), bounds(node)))
    return {"xml": ET.tostring(region, encoding="unicode"), "full_xml": xml, "width": width, "height": height, "bounds": box, "fingerprint": tuple(visible), "scrollable": scrollable}


class U2ScrollDevice:
    def __init__(self, device):
        self.device = device

    def scroll_snapshot(self):
        return screen_snapshot(self.device.dump_hierarchy(), *self.device.window_size())

    def drag(self, x, start, end):
        # Holding still before lifting the finger leaves Android no release
        # velocity, so the list stops exactly where the finger stopped instead
        # of flinging past entries that were never on screen.
        self.device.swipe_points([(x, start), (x, end), (x, end)], duration=.25)

    def scroll_step(self, direction, snapshot, fast=False):
        """"up" moves the finger up (towards later content), "down" back to the start."""
        left, top, right, bottom = snapshot["bounds"]
        x = round((left + right) / 2)
        low, high = round(top + (bottom - top) * .8), round(top + (bottom - top) * .2)
        start, end = (low, high) if direction == "up" else (high, low)
        if fast:
            self.device.swipe(x, start, x, end, duration=.1)
        else:
            self.drag(x, start, end)

    def scroll_by(self, snapshot, distance):
        """Move the content by about `distance` pixels; positive reveals later entries."""
        left, top, right, bottom = snapshot["bounds"]
        height = bottom - top
        distance = max(-.8 * height, min(.8 * height, distance))
        start = top + (.9 if distance > 0 else .1) * height
        self.drag(round((left + right) / 2), round(start), round(start - distance))


def traverse_screen(device, by="textContains", value="", target=None, match="exact", checkpoint=time.sleep, progress=None, max_swipes=100, pattern=None):
    """Rewind, then collect unique texts or find a target; never save partial results."""
    progress = progress or (lambda message: None)
    checkpoint(0)
    def snapshot():
        result = device.scroll_snapshot()
        return screen_snapshot(result['full_xml'], result['width'], result['height'], pattern) if pattern else result
    current = snapshot()
    if pattern and not read_list_items(current['full_xml'], current['width'], current['height'], pattern):
        raise ValueError('Kein passendes Listenelement sichtbar. Bitte die ursprüngliche Liste öffnen oder das Muster neu auswählen.')

    def step(direction):
        nonlocal current
        checkpoint(0)
        previous = current["fingerprint"]
        device.scroll_step(direction, current)
        checkpoint(.4)
        current = snapshot()
        return current["fingerprint"] == previous

    progress("Scrolle zum Anfang …")
    unchanged = 0
    for _ in range(max_swipes):
        unchanged = unchanged + 1 if step("down") else 0
        if unchanged >= 2:
            break
    else:
        raise ValueError(f"Der Anfang wurde nach {max_swipes} Wischbewegungen nicht erreicht. Aufnahme/Suche abgebrochen; vorhandene Listen bleiben erhalten.")

    values, seen, unchanged, typical = [], set(), 0, None
    for page in range(max_swipes + 1):
        if pattern:
            # Only complete entries: a card cut off at the edge shows just a fragment of its text.
            uncut = ({"top"} if page == 0 else set()) | ({"bottom"} if unchanged >= 2 else set())
            complete = [entry for entry in list_entries(current, pattern, typical, uncut)[1] if entry["complete"]]
            if complete:
                typical = statistics.median(entry["bounds"][3] - entry["bounds"][1] for entry in complete)
            texts = [entry["text"] for entry in complete]
        else:
            texts = read_visible_texts(current["xml"], current["width"], current["height"], by if target is None else "textContains", value if target is None else "")
        if target is not None:
            if any(text == target if match == "exact" else target in text for text in texts):
                progress(f'Text „{target}“ gefunden.')
                return True
            progress(f"Suche · Bildschirmabschnitt {page + 1}")
        else:
            for text in texts:
                if text not in seen:
                    if len(values) >= MAX_LIST_ITEMS:
                        raise ValueError("Mehr als 500 unterschiedliche Texte. Bitte den Listenfilter eingrenzen. Vorhandene Liste bleibt erhalten.")
                    seen.add(text)
                    values.append(text)
            progress(f"Aufnahme · {len(values)} " + ('Listeneinträge' if pattern else 'unterschiedliche Texte'))
        if unchanged >= 2:
            return values if target is None else False
        if page == max_swipes:
            raise ValueError(f"Das Ende wurde nach {max_swipes} Wischbewegungen nicht erreicht. Aufnahme/Suche abgebrochen; vorhandene Listen bleiben erhalten.")
        unchanged = unchanged + 1 if step("up") else 0
