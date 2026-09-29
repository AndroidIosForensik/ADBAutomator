"""„Liste sichern“: open every entry of an on-device list and page through its content.

Entries are tapped where they are on screen instead of being searched by text,
so identically labelled entries stay separate and combined card texts work.
Scrolling is controlled (no fling) and every new screen is aligned with the
previous one, so no entry is skipped or opened twice.
"""
import re
import statistics
import time
import xml.etree.ElementTree as ET

from .list_items import item_bounds, list_entries
from .scrolling import screen_snapshot


class BackupError(ValueError):
    pass


def overlap(previous, current, expected_shift, tolerance=None):
    """How many leading entries of `current` were already handled on the previous screen.

    Several overlaps can match when neighbouring entries look identical; the one
    whose implied scroll distance is closest to the expected shift wins. With a
    tolerance, a match implying a clearly different shift is no match at all.
    Returns None if the screens do not overlap.
    """
    options = []
    for size in range(min(len(previous), len(current)), 0, -1):
        if [entry["text"] for entry in previous[-size:]] == [entry["text"] for entry in current[:size]]:
            options.append((size, previous[-size]["bounds"][1] - current[0]["bounds"][1]))
    if tolerance is not None:
        options = [option for option in options if abs(option[1] - expected_shift) <= tolerance]
    if not options:
        return None
    return min(options, key=lambda option: abs(option[1] - expected_shift))[0]


def measured_shift(before, after):
    """How far the list really moved, from texts that occur once on both screens."""
    def unique_tops(snap):
        seen, tops = {}, {}
        box = snap["bounds"]
        for node in ET.fromstring(snap["xml"]).iter("node"):
            key = (node.get("text", ""), node.get("content-desc", ""), node.get("resource-id", ""), node.get("class", ""))
            bounds = re.fullmatch(r"\[(-?\d+),(-?\d+)\]\[(-?\d+),(-?\d+)\]", node.get("bounds", ""))
            if not (key[0] or key[1]) or not bounds:
                continue
            top, bottom = int(bounds.group(2)), int(bounds.group(4))
            seen[key] = seen.get(key, 0) + 1
            # Clipped nodes at the edges do not show their real position.
            if top > box[1] + 2 and bottom < box[3] - 2:
                tops[key] = top
        return {key: top for key, top in tops.items() if seen[key] == 1}
    first, second = unique_tops(before), unique_tops(after)
    shifts = [first[key] - second[key] for key in first.keys() & second.keys()]
    return statistics.median(shifts) if shifts else None


def continues(partial, full):
    """Whether a cut-off entry's text is the beginning of a complete entry's text."""
    partial_lines, full_lines = partial.splitlines(), full.splitlines()
    return bool(partial_lines) and full_lines[:len(partial_lines)] == partial_lines


def content_moved(before, after):
    """Whether the content really scrolled between two snapshots.

    Found on a real phone: WhatsApp shows a date bubble and a jump button while
    swiping, and animated GIFs keep changing, so the screen changes although a
    chat that is already at its end does not move. Unique texts reveal the real shift.
    """
    if before["fingerprint"] == after["fingerprint"]:
        return False
    shift = measured_shift(before, after)
    return shift is None or abs(shift) >= 8


def visible_text(snap):
    """All text on the screen in hierarchy order, without the status bar."""
    lines = []
    for node in ET.fromstring(snap["full_xml"]).iter("node"):
        if not item_bounds(node, snap["width"], snap["height"]):
            continue
        values = (node.get("text", "").strip(), node.get("content-desc", "").strip())
        for index, value in enumerate(values):
            # Only suppress a node describing its own identical text. Separate
            # messages can legitimately repeat a word or the same timestamp.
            if value and not (index == 1 and value == values[0]):
                lines.append(value)
    return "\n".join(lines)


def screen_signature(xml):
    """Everything visible except the status bar (clock, notifications)."""
    return tuple((node.get("text", ""), node.get("content-desc", ""), node.get("resource-id", ""), node.get("class", ""), node.get("bounds", ""))
                 for node in ET.fromstring(xml).iter("node") if node.get("package") != "com.android.systemui")


class ListBackup:
    def __init__(self, device, pattern, writer, *, order="end_to_start", max_pages=200, checkpoint=time.sleep,
                 log=None, status=None, pause_point=None, settle=.5, fling_settle=.9, poll=.3, open_timeout=6, max_list_swipes=3000):
        self.device, self.pattern, self.writer = device, pattern, writer
        self.order, self.max_pages = order, max_pages
        self.checkpoint = checkpoint
        self.log = log or (lambda text, level="info": None)
        self.status = status or (lambda **values: None)
        self.pause_point = pause_point or (lambda: None)
        # settle: after a controlled drag; fling_settle: after a fast swipe that keeps moving.
        self.settle, self.fling_settle, self.poll = settle, fling_settle, poll
        self.open_timeout, self.max_list_swipes = open_timeout, max_list_swipes
        self.typical = None
        self.swipes = 0
        self.counts = {"entries": 0, "saved": 0, "problems": 0, "pages": 0}

    # -- list screen -------------------------------------------------------
    def list_snapshot(self):
        snap = self.device.scroll_snapshot()
        return screen_snapshot(snap["full_xml"], snap["width"], snap["height"], self.pattern)

    def read(self, snap, uncut=()):
        box, entries = list_entries(snap, self.pattern, self.typical, uncut)
        heights = [e["bounds"][3] - e["bounds"][1] for e in entries if e["complete"]]
        if heights:
            self.typical = statistics.median(heights)
        return box, entries

    def scroll_list(self, snap, distance):
        self.swipes += 1
        if self.swipes > self.max_list_swipes:
            raise BackupError(f"Das Listenende wurde nach {self.max_list_swipes} Wischbewegungen nicht erreicht. Sicherung angehalten.")
        self.device.scroll_by(snap, distance)
        self.checkpoint(self.settle)
        return self.list_snapshot()

    def rewind(self, snap):
        unchanged = 0
        while unchanged < 2:
            self.checkpoint(0)
            before = snap
            self.swipes += 1
            if self.swipes > self.max_list_swipes:
                raise BackupError("Der Anfang der Liste wurde nicht erreicht. Sicherung angehalten.")
            self.device.scroll_step("down", snap, fast=True)
            self.checkpoint(self.fling_settle)
            snap = self.list_snapshot()
            unchanged = 0 if content_moved(before, snap) else unchanged + 1
        return snap

    @staticmethod
    def plan_scroll(box, entries):
        """How far to scroll, and which entry should then be at the top.

        Normally the last completely visible entry moves to the top and stays
        visible, so the next screen overlaps the entries already handled. Only
        when entries are so tall that this would barely move does the first
        cut-off entry move to the top instead; it is then expected there.
        A small margin keeps the entry off the edge, where it would look cut off.
        """
        top, height = box[1], box[3] - box[1]
        margin = max(8, height * .04)
        complete = [e for e in entries if e["complete"]]
        if complete and complete[-1]["bounds"][1] - top - margin >= height * .25:
            return min(height * .8, complete[-1]["bounds"][1] - top - margin), None
        last_top = complete[-1]["bounds"][1] if complete else top
        cut_off = [e for e in entries if not e["complete"] and e["bounds"][1] > last_top]
        if cut_off:
            return max(height * .2, min(height * .8, cut_off[0]["bounds"][1] - top - margin)), cut_off[0]
        return height * .6, None

    def align(self, previous, current, before, after, requested):
        """Overlap of two screens, checked against how far the list really moved."""
        shift = measured_shift(before, after)
        if shift is None:
            # Nothing unique to measure (e.g. identical neighbours): judge by the
            # requested distance, which touch slop and the list end can shorten.
            return overlap(previous, current, requested, max(24, .5 * (self.typical or 0)))
        return overlap(previous, current, shift, max(12, .3 * (self.typical or 0)))

    # -- whole run ---------------------------------------------------------
    def run(self):
        snap = self.list_snapshot()
        _, entries = self.read(snap)
        if not entries:
            raise BackupError("Kein Listeneintrag nach dem gewählten Muster sichtbar. Bitte die Liste auf dem Gerät öffnen oder das Listenelement neu auswählen.")
        self.log("Scrolle zum Anfang der Liste …")
        snap = self.rewind(snap)
        # At the very start nothing can be cut off at the top edge.
        _, entries = self.read(snap, uncut={"top"})
        targets = [e for e in entries if e["complete"]]
        first_screen = True
        while True:
            for target in targets:
                snap = self.handle(target, snap)
            box, entries = self.read(snap, uncut={"top"} if first_screen else ())
            first_screen = False
            previous = [e for e in entries if e["complete"]]
            distance, expected = self.plan_scroll(box, entries)
            before_scroll = snap
            moved = False
            for _ in range(2):
                before = snap
                snap = self.scroll_list(snap, distance)
                if content_moved(before, snap):
                    moved = True
                    break
            if not moved:
                # At the end nothing is cut off at the bottom edge either; handle
                # short last entries that looked cut off while more could follow.
                _, entries = self.read(snap, uncut={"top", "bottom"} if not previous else {"bottom"})
                last_top = previous[-1]["bounds"][1] if previous else None
                for target in [e for e in entries if e["complete"] and (last_top is None or e["bounds"][1] > last_top)]:
                    snap = self.handle(target, snap)
                break
            box, entries = self.read(snap)
            complete = [e for e in entries if e["complete"]]
            size = self.align(previous, complete, before_scroll, snap, distance) if previous else 0
            if size is None and expected and complete and continues(expected["text"], complete[0]["text"]):
                size = 0
            if size is None:
                # Went too far: step back half the distance and align again.
                self.log("Überlappung nicht gefunden, scrolle ein Stück zurück.")
                snap = self.scroll_list(snap, -distance / 2)
                box, entries = self.read(snap)
                complete = [e for e in entries if e["complete"]]
                size = self.align(previous, complete, before_scroll, snap, distance / 2)
                if size is None:
                    text = f"Nach Eintrag {self.counts['entries']} ließ sich die Liste nicht lückenlos fortsetzen. Möglicherweise fehlen dort Einträge."
                    self.writer.warn(text)
                    self.log(text, "warning")
                    size = 0
            targets = complete[size:]
        return self.counts

    # -- one entry ---------------------------------------------------------
    def handle(self, target, snap):
        self.pause_point()
        self.checkpoint(0)
        entry = self.writer.begin_entry(target["text"])
        self.counts["entries"] += 1
        label = next((line for line in target["text"].splitlines() if line.strip()), target["text"])[:120]
        self.status(entry=entry["index"], text=label, page=0, **{k: self.counts[k] for k in ("saved", "problems", "pages")})
        _, entries = self.read(snap)
        match = next((e for e in entries if e["text"] == target["text"] and abs(e["bounds"][1] - target["bounds"][1]) <= 12), None)
        if match is None:
            same = [e for e in entries if e["text"] == target["text"]]
            match = same[0] if len(same) == 1 else None
        if match is None:
            return self.problem(entry, "nicht gefunden", "Der Eintrag war beim Antippen nicht mehr an seiner Stelle sichtbar.", snap)
        x1, y1, x2, y2 = match["bounds"]
        before = screen_signature(snap["full_xml"])
        self.device.perform({"op": "tap", "x": (x1 + x2) / 2 / snap["width"], "y": (y1 + y2) / 2 / snap["height"]})
        if not self.wait_for_change(before):
            return self.problem(entry, "öffnete nicht", "Nach dem Antippen änderte sich die Ansicht nicht.", snap)
        complete = self.capture(entry)
        if complete:
            self.counts["saved"] += 1
            self.writer.finish_entry(entry, "gesichert")
            self.log(f"Eintrag {entry['index']}: „{label[:80]}“ · {len(entry['pages'])} Seite(n) gesichert.")
        else:
            self.counts["problems"] += 1
            self.writer.finish_entry(entry, "unvollständig", f"Seitenlimit von {self.max_pages} Seiten erreicht; der Inhalt geht weiter.")
            self.log(f"Eintrag {entry['index']}: Seitenlimit von {self.max_pages} Seiten erreicht.", "warning")
        self.status(saved=self.counts["saved"], problems=self.counts["problems"])
        return self.return_to_list(entry)

    def problem(self, entry, status, note, snap):
        self.counts["problems"] += 1
        self.writer.finish_entry(entry, status, note)
        self.status(problems=self.counts["problems"])
        self.log(f"Eintrag {entry['index']}: {note}", "warning")
        return snap

    def wait_for_change(self, before):
        deadline = time.monotonic() + self.open_timeout
        while True:
            self.checkpoint(self.poll)
            current = screen_signature(self.device.scroll_snapshot()["full_xml"])
            if current != before:
                break
            if time.monotonic() > deadline:
                return False
        # Let the opened view finish loading before the first screenshot.
        for _ in range(6):
            self.checkpoint(self.settle)
            latest = screen_signature(self.device.scroll_snapshot()["full_xml"])
            if latest == current:
                break
            current = latest
        return True

    def save_page(self, entry, snap):
        data, mime = self.device.screenshot()
        self.writer.add_page(entry, data, mime, visible_text(snap))
        self.counts["pages"] += 1
        self.status(page=len(entry["pages"]), pages=self.counts["pages"])

    def capture(self, entry):
        """Screenshot the opened view page by page; False if the page limit cut it short."""
        snap = self.device.scroll_snapshot()
        rewind, forward = ("up", "down") if self.order == "end_to_start" else ("down", "up")
        if snap["scrollable"]:
            unchanged, swipes = 0, 0
            while unchanged < 2 and swipes < self.max_pages + 2:
                before = snap
                self.device.scroll_step(rewind, snap, fast=True)
                swipes += 1
                self.checkpoint(self.fling_settle)
                snap = self.device.scroll_snapshot()
                unchanged = 0 if content_moved(before, snap) else unchanged + 1
        self.save_page(entry, snap)
        if not snap["scrollable"]:
            return True
        unchanged = 0
        while True:
            before = snap
            self.device.scroll_step(forward, snap)
            self.checkpoint(self.settle)
            snap = self.device.scroll_snapshot()
            if not content_moved(before, snap):
                unchanged += 1
                if unchanged >= 2:
                    return True
                continue
            unchanged = 0
            if len(entry["pages"]) >= self.max_pages:
                return False
            self.save_page(entry, snap)

    def return_to_list(self, entry):
        for _ in range(3):
            self.device.perform({"op": "press", "key": "back"})
            for _ in range(8):
                self.checkpoint(self.settle)
                try:
                    snap = self.list_snapshot()
                    if self.read(snap)[1]:
                        return snap
                except ValueError:
                    pass
        raise BackupError(f"Nach Eintrag {entry['index']} kehrte die App nicht zur Liste zurück. Sicherung angehalten; bisher gesicherte Einträge bleiben erhalten.")
