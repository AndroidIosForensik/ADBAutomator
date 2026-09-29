"""Shared list extraction, also embedded in standalone Python exports."""
import re
import xml.etree.ElementTree as ET

MAX_LIST_ITEMS = 500


def read_visible_texts(xml, width, height, by, value):
    """Read matching visible text nodes in hierarchy order, preserving duplicates."""
    result = []
    for node in ET.fromstring(xml).iter("node"):
        text = node.get("text", "").strip()
        if not text or node.get("visible-to-user") == "false":
            continue
        if by == "textContains" and value not in text:
            continue
        if by == "resourceId" and node.get("resource-id") != value:
            continue
        if by == "className" and node.get("class") != value:
            continue
        match = re.fullmatch(r"\[(-?\d+),(-?\d+)\]\[(-?\d+),(-?\d+)\]", node.get("bounds", ""))
        if not match:
            continue
        x1, y1, x2, y2 = map(int, match.groups())
        if min(x2, width) <= max(x1, 0) or min(y2, height) <= max(y1, 0):
            continue
        if len(text) > 2000:
            raise ValueError("Ein Listeneintrag enthält mehr als 2000 Zeichen.")
        result.append(text)
        if len(result) > MAX_LIST_ITEMS:
            raise ValueError(f"Mehr als {MAX_LIST_ITEMS} Listeneinträge gefunden. Bitte den Filter eingrenzen.")
    return result
