"""Small interchangeable real-device and demo adapters."""
import datetime
import html
import io
import re
import threading
import xml.etree.ElementTree as ET

from .lists import read_visible_texts
from .scrolling import U2ScrollDevice, screen_snapshot


def list_devices():
    try:
        import adbutils
        devices = adbutils.adb.list()
        return [{"serial": d.serial, "state": d.state} for d in devices], None
    except ImportError:
        return [], "Gerätebibliotheken fehlen. Bitte setup.bat ausführen."
    except Exception as exc:
        return [], f"ADB ist nicht erreichbar: {exc}"


def focused_package(dumpsys_window):
    """Package of the focused app from `dumpsys window`, or None."""
    # mFocusedApp is the app even while one of its dialogs or a popup has the window focus.
    for key in ("mFocusedApp", "mCurrentFocus"):
        match = re.search(key + r"=[^\n]*?\s([A-Za-z][\w.]*)/[\w.$]+", dumpsys_window)
        if match:
            return match.group(1)
    return None


class AndroidDevice:
    demo = False

    def __init__(self, serial):
        import uiautomator2 as u2
        self.serial = serial
        self.lock = threading.RLock()
        self.device = u2.connect(serial)
        self.device.settings["wait_timeout"] = 10
        # device.info invokes UiDevice.getDisplaySizeDp on the device, which can
        # fail with ApplicationSharedMemory on newer Android builds. The name
        # only needs a stable ADB property, not the UI automation metadata RPC.
        self.name = self.device.adb_device.getprop("ro.product.model").strip() or serial

    def screenshot(self):
        with self.lock:
            picture = self.device.screenshot()
            out = io.BytesIO()
            picture.save(out, format="PNG")
            return out.getvalue(), "image/png"

    def current_app(self):
        with self.lock:
            # uiautomator2's app_current() reported a background chat app on
            # Android 17 while Settings was in front; the window manager knows
            # which app really has the focus.
            try:
                package = focused_package(self.device.adb_device.shell("dumpsys window"))
            except Exception:
                package = None
            return {"package": package or self.device.app_current()["package"]}

    def device_info(self):
        """Identification for the backup report; every value is optional."""
        with self.lock:
            adb = self.device.adb_device
            def read(call):
                try:
                    return str(call()).strip()
                except Exception:
                    return ""
            prop = lambda name: read(lambda: adb.getprop(name))
            return {"label": self.name, "manufacturer": prop("ro.product.manufacturer"), "model": prop("ro.product.model"),
                    "android": prop("ro.build.version.release"), "sdk": prop("ro.build.version.sdk"), "build": prop("ro.build.display.id"),
                    "serial": self.serial, "device_time": read(lambda: adb.shell("date '+%Y-%m-%d %H:%M:%S %z'")), "demo": False}

    def read_list(self, by, value):
        with self.lock:
            return read_visible_texts(self.device.dump_hierarchy(), *self.device.window_size(), by, value)

    def scroll_snapshot(self):
        with self.lock:
            return U2ScrollDevice(self.device).scroll_snapshot()

    def scroll_step(self, direction, snapshot, fast=False):
        with self.lock:
            U2ScrollDevice(self.device).scroll_step(direction, snapshot, fast)

    def scroll_by(self, snapshot, distance):
        with self.lock:
            U2ScrollDevice(self.device).scroll_by(snapshot, distance)

    def elements(self):
        with self.lock:
            xml = self.device.dump_hierarchy()
            width, height = self.device.window_size()
        root = ET.fromstring(xml)
        result = []
        for node in root.iter("node"):
            attrs = node.attrib
            bounds = re.fullmatch(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]", attrs.get("bounds", ""))
            if not bounds or attrs.get("enabled") == "false":
                continue
            x1, y1, x2, y2 = map(int, bounds.groups())
            if x2 <= x1 or y2 <= y1:
                continue
            selector = None
            for key, source in [("resourceId", "resource-id"), ("description", "content-desc"), ("text", "text")]:
                value = attrs.get(source)
                if value and sum(1 for other in root.iter("node") if other.get(source) == value) == 1:
                    selector = {"by": key, "value": value}
                    break
            if selector:
                result.append({"label": attrs.get("text") or attrs.get("content-desc") or selector["value"], "selector": selector, "bounds": [x1 / width, y1 / height, x2 / width, y2 / height]})
        return result

    def exists(self, node):
        with self.lock:
            return bool(self.device(**{node["by"]: node["value"]}).exists)

    def perform(self, node):
        with self.lock:
            d = self.device
            op = node["op"]
            if op == "launch":
                d.app_start(node["package"])
            elif op == "tap":
                width, height = d.window_size()
                d.click(round(node["x"] * (width - 1)), round(node["y"] * (height - 1)))
            elif op == "click":
                d(**{node["by"]: node["value"]}).click(timeout=0)
            elif op == "type":
                d.send_keys(node["text"], clear=True)
            elif op == "press":
                d.press(node["key"])
            elif op == "swipe":
                d.swipe_ext(node["direction"], scale=0.7)


DEMO_CHATS_PACKAGE = "de.droidstudio.demo.chats"
# Name, last message, time, unread messages, messages in the conversation.
# The two identical "Unbekannt" rows and the two different "Lena" rows are deliberate.
DEMO_CHATS = [("Mama", "Ruf mich bitte heute Abend an", "18:42", 2, 12), ("Team Nord", "Treffen verschoben auf Donnerstag", "17:15", 0, 16),
              ("Lena", "Danke dir!", "16:03", 1, 5), ("Unbekannt", "Verpasster Anruf", "Gestern", 0, 1), ("Unbekannt", "Verpasster Anruf", "Gestern", 0, 1),
              ("Paketdienst", "Ihre Sendung wird heute zugestellt", "Gestern", 0, 4), ("Fußballverein", "Training fällt aus", "Gestern", 3, 11),
              ("Jonas", "Hast du die Unterlagen?", "Mo.", 0, 7), ("Arztpraxis", "Terminerinnerung: Di. 9:30 Uhr", "Mo.", 0, 3),
              ("Nachbarn", "Wer hat das Paket angenommen?", "So.", 0, 8), ("Oma", "Frohe Ostern!", "12.04.", 0, 6), ("Werkstatt", "Ihr Auto ist fertig", "10.04.", 0, 3),
              ("Lena", "Bis später", "08.04.", 0, 4), ("Vermieter", "Nebenkostenabrechnung im Anhang", "02.04.", 0, 5),
              ("Schule", "Elternabend am 20.", "28.03.", 0, 9), ("Sportgruppe", "Neue Termine im Kalender", "21.03.", 0, 13)]
LIST_BOX, CHAT_BOX, ROW, MESSAGE = (0, 190, 390, 750), (0, 120, 390, 720), 76, 64


def clip(box, area):
    x1, y1, x2, y2 = max(box[0], area[0]), max(box[1], area[1]), min(box[2], area[2]), min(box[3], area[3])
    return (x1, y1, x2, y2) if x2 > x1 and y2 > y1 else None


def bounds_text(box):
    return f"[{box[0]},{box[1]}][{box[2]},{box[3]}]"


class DemoChats:
    """A scrollable chat list with conversations, for trying „Liste sichern“ without a phone."""

    def __init__(self):
        self.unread = [chat[3] for chat in DEMO_CHATS]
        self.list_offset = 0
        self.chat = None
        self.chat_offset = 0

    def list_max(self):
        return max(0, len(DEMO_CHATS) * ROW - (LIST_BOX[3] - LIST_BOX[1]))

    def chat_max(self):
        return max(0, DEMO_CHATS[self.chat][4] * MESSAGE - (CHAT_BOX[3] - CHAT_BOX[1]))

    def rows(self):
        """Visible chat rows with bounds clipped to the list, as Android reports them."""
        for index, chat in enumerate(DEMO_CHATS):
            top = LIST_BOX[1] + index * ROW - self.list_offset
            box = clip((0, top, 390, top + ROW), LIST_BOX)
            if box:
                yield index, chat, top, box

    def messages(self):
        name, count = DEMO_CHATS[self.chat][0], DEMO_CHATS[self.chat][4]
        for index in range(count):
            top = CHAT_BOX[1] + index * MESSAGE - self.chat_offset
            box = clip((0, top, 390, top + MESSAGE), CHAT_BOX)
            if box:
                mine = index % 2 == 1
                yield ("Du" if mine else name), f"{index + 1}. Nachricht im Verlauf mit {name}", mine, top, box

    def open(self, index):
        # Like a messenger: opening shows the newest messages and marks the chat as read.
        self.chat = index
        self.unread[index] = 0
        self.chat_offset = self.chat_max()

    def scroll(self, distance, in_chat):
        # Real touch input loses a few pixels before the content starts to move.
        distance = max(0, abs(distance) - 8) * (1 if distance > 0 else -1)
        if in_chat:
            self.chat_offset = round(max(0, min(self.chat_max(), self.chat_offset + distance)))
        else:
            self.list_offset = round(max(0, min(self.list_max(), self.list_offset + distance)))

    def xml(self, in_chat):
        root = ET.Element("hierarchy")
        clock = datetime.datetime.now().strftime("%H:%M:%S")
        ET.SubElement(root, "node", {"package": "com.android.systemui", "class": "android.widget.TextView", "text": clock, "bounds": "[0,0][390,40]"})
        frame = ET.SubElement(root, "node", {"package": DEMO_CHATS_PACKAGE, "class": "android.widget.FrameLayout", "bounds": "[0,40][390,800]"})
        if in_chat:
            ET.SubElement(frame, "node", {"class": "android.widget.TextView", "resource-id": "demo:id/title", "text": DEMO_CHATS[self.chat][0], "bounds": "[60,60][370,110]"})
            area = ET.SubElement(frame, "node", {"class": "androidx.recyclerview.widget.RecyclerView", "resource-id": "demo:id/messages", "scrollable": "true", "bounds": bounds_text(CHAT_BOX)})
            for sender, text, _, top, box in self.messages():
                row = ET.SubElement(area, "node", {"class": "android.widget.LinearLayout", "resource-id": "demo:id/message_row", "bounds": bounds_text(box)})
                for part, value, offset in (("sender", sender, 6), ("text", text, 26)):
                    child = clip((20, top + offset, 370, top + offset + 20), CHAT_BOX)
                    if child:
                        ET.SubElement(row, "node", {"class": "android.widget.TextView", "resource-id": f"demo:id/{part}", "text": value, "bounds": bounds_text(child)})
            ET.SubElement(frame, "node", {"class": "android.widget.EditText", "resource-id": "demo:id/input", "text": "Nachricht", "bounds": "[12,734][378,786]"})
        else:
            ET.SubElement(frame, "node", {"class": "android.widget.TextView", "resource-id": "demo:id/title", "text": "Demo-Chats", "bounds": "[20,70][370,120]"})
            area = ET.SubElement(frame, "node", {"class": "androidx.recyclerview.widget.RecyclerView", "resource-id": "demo:id/chats", "scrollable": "true", "bounds": bounds_text(LIST_BOX)})
            for index, (name, message, time, _, _), top, box in self.rows():
                row = ET.SubElement(area, "node", {"class": "android.widget.LinearLayout", "resource-id": "demo:id/chat_row", "clickable": "true", "bounds": bounds_text(box)})
                parts = [("name", name, (80, top + 12, 290, top + 36)), ("message", message, (80, top + 42, 330, top + 64)), ("time", time, (295, top + 12, 375, top + 32))]
                if self.unread[index]:
                    parts.append(("unread", str(self.unread[index]), (345, top + 40, 371, top + 64)))
                for part, value, child in parts:
                    child = clip(child, LIST_BOX)
                    if child:
                        ET.SubElement(row, "node", {"class": "android.widget.TextView", "resource-id": f"demo:id/{part}", "text": value, "bounds": bounds_text(child)})
        return ET.tostring(root, encoding="unicode")

    def tap(self, x, y):
        for index, _, _, box in self.rows():
            if box[0] <= x <= box[2] and box[1] <= y <= box[3]:
                self.open(index)
                return True
        return False

    def svg(self, in_chat):
        e = html.escape
        area = CHAT_BOX if in_chat else LIST_BOX
        parts = ['<svg xmlns="http://www.w3.org/2000/svg" width="390" height="800" viewBox="0 0 390 800">', '<rect width="390" height="800" fill="#f7f8f5"/>',
                 f'<defs><clipPath id="area"><rect x="0" y="{area[1]}" width="390" height="{area[3] - area[1]}"/></clipPath></defs>',
                 '<g font-family="Segoe UI,Arial,sans-serif" fill="#1f2a24">', '<text x="25" y="30" font-size="14" font-weight="600">09:41</text>']
        if in_chat:
            parts += ['<rect y="40" width="390" height="80" fill="#1f7a5a"/>', '<path d="M40 70l-10 10 10 10" fill="none" stroke="#fff" stroke-width="3" stroke-linecap="round"/>',
                      f'<text x="60" y="92" font-size="20" font-weight="600" fill="#fff">{e(DEMO_CHATS[self.chat][0])}</text>', '<g clip-path="url(#area)">']
            for sender, text, mine, top, _ in self.messages():
                x = 110 if mine else 14
                parts += [f'<rect x="{x}" y="{top + 4}" width="266" height="54" rx="10" fill="{"#d7f5dd" if mine else "#ffffff"}" stroke="#dfe5df"/>',
                          f'<text x="{x + 12}" y="{top + 22}" font-size="11" fill="#1f7a5a" font-weight="600">{e(sender)}</text>',
                          f'<text x="{x + 12}" y="{top + 44}" font-size="12">{e(text[:36])}</text>']
            parts += ['</g>', '<rect x="12" y="734" width="366" height="52" rx="26" fill="#fff" stroke="#dfe5df"/>', '<text x="32" y="766" font-size="14" fill="#8a948d">Nachricht</text>']
        else:
            parts += ['<text x="25" y="108" font-size="30" font-weight="600">Demo-Chats</text>',
                      f'<text x="25" y="140" font-size="12" fill="#6f7a73">Beispielliste für „Liste sichern“ · {len(DEMO_CHATS)} Chats</text>', '<g clip-path="url(#area)">']
            for index, (name, message, time, _, _), top, _ in self.rows():
                parts += [f'<circle cx="42" cy="{top + 38}" r="24" fill="#cfe8da"/>', f'<text x="42" y="{top + 45}" font-size="18" text-anchor="middle" fill="#1f7a5a">{e(name[0])}</text>',
                          f'<text x="80" y="{top + 30}" font-size="16" font-weight="600">{e(name)}</text>', f'<text x="80" y="{top + 58}" font-size="13" fill="#6f7a73">{e(message)}</text>',
                          f'<text x="372" y="{top + 30}" font-size="11" fill="#6f7a73" text-anchor="end">{e(time)}</text>', f'<line x1="80" y1="{top + ROW}" x2="390" y2="{top + ROW}" stroke="#e3e8e4"/>']
                if self.unread[index]:
                    parts += [f'<circle cx="358" cy="{top + 52}" r="11" fill="#25a366"/>', f'<text x="358" y="{top + 56}" font-size="11" fill="#fff" text-anchor="middle">{self.unread[index]}</text>']
            parts.append('</g>')
        parts += ['<rect x="147" y="790" width="96" height="4" rx="2" fill="#1f2a24"/></g></svg>']
        return "".join(parts).encode()


class DemoDevice:
    demo = True
    serial = "demo"
    name = "Android · Demo-Gerät"

    def __init__(self):
        self.lock = threading.RLock()
        self.page = "Einstellungen"
        self.typed = ""
        self.history = []
        self.chats = DemoChats()

    def _in_chats(self):
        return self.page in {"Demo-Chats", "Chat"}

    def _rows(self):
        if self.page == "Einstellungen":
            return [("Netzwerk & Internet", "WLAN, Mobilfunk, Datennutzung", "#e0e9ff"), ("Verbundene Geräte", "Bluetooth, Android Auto", "#e2f0ed"), ("Apps", "Standard-Apps, Berechtigungen", "#eee4fa"), ("Benachrichtigungen", "Verlauf, Unterhaltungen", "#fff0d7"), ("Akku", "86 % · Noch etwa 1 Tag", "#e5efdc"), ("Anzeige", "Helligkeit, Design, Schriftgröße", "#f8e4db"), ("Ton & Vibration", "Lautstärke, Nicht stören", "#e4e9fa")]
        if self.page == "Startbildschirm":
            return [("Einstellungen", "Geräteeinstellungen öffnen", "#e0e9ff"), ("Demo-Chats", "Beispielliste für „Liste sichern“", "#e2f0ed")]
        if self.page == "Anzeige":
            return [("Helligkeit", "Automatisch anpassen", "#fff0d7"), ("Dunkles Design", "Aus", "#eee4fa"), ("Bildschirm-Timeout", "Nach 30 Sekunden", "#e2f0ed")]
        return []

    def _navigate(self, page):
        self.history.append(self.page)
        self.page = page
        self.typed = ""
        if page == "Demo-Chats":
            self.chats.list_offset = 0

    def _open_chat(self, index):
        self.history.append(self.page)
        self.page = "Chat"
        self.chats.open(index)

    def current_app(self):
        return {"package": DEMO_CHATS_PACKAGE if self._in_chats() else "com.android.settings"}

    def device_info(self):
        return {"label": self.name, "manufacturer": "Droid Studio", "model": "Demo-Gerät", "android": "14", "sdk": "34", "build": "demo",
                "serial": self.serial, "device_time": datetime.datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %z"), "demo": True}

    def read_list(self, by, value):
        with self.lock:
            if self._in_chats():
                return read_visible_texts(self.chats.xml(self.page == "Chat"), 390, 800, by, value)
            root = ET.Element("hierarchy")
            for i, row in enumerate(self._rows()):
                ET.SubElement(root, "node", {"text": row[0], "class": "android.widget.TextView", "resource-id": "demo:id/title", "bounds": f"[14,{211 + i * 67}][376,{273 + i * 67}]"})
            return read_visible_texts(ET.tostring(root, encoding="unicode"), 390, 800, by, value)

    def scroll_snapshot(self):
        with self.lock:
            if self._in_chats():
                return screen_snapshot(self.chats.xml(self.page == "Chat"), 390, 800)
            root = ET.Element("hierarchy")
            region = ET.SubElement(root, "node", {"scrollable": "true", "bounds": "[0,200][390,760]"})
            for i, row in enumerate(self._rows()):
                ET.SubElement(region, "node", {"text": row[0], "class": "android.widget.TextView", "resource-id": "demo:id/title", "bounds": f"[14,{211 + i * 67}][376,{273 + i * 67}]"})
            return screen_snapshot(ET.tostring(root, encoding="unicode"), 390, 800)

    def scroll_step(self, direction, snapshot, fast=False):
        # The demo settings fit on a single page; only the demo chats scroll.
        with self.lock:
            if self._in_chats():
                height = snapshot["bounds"][3] - snapshot["bounds"][1]
                self.chats.scroll((3 if fast else .6) * height * (1 if direction == "up" else -1), self.page == "Chat")

    def scroll_by(self, snapshot, distance):
        with self.lock:
            if self._in_chats():
                height = snapshot["bounds"][3] - snapshot["bounds"][1]
                self.chats.scroll(max(-.8 * height, min(.8 * height, distance)), self.page == "Chat")

    def elements(self):
        with self.lock:
            if self.page == "Demo-Chats":
                names = [chat[0] for chat in DEMO_CHATS]
                return [{"label": chat[0], "selector": {"by": "text", "value": chat[0]}, "bounds": [box[0] / 390, box[1] / 800, box[2] / 390, box[3] / 800]}
                        for _, chat, _, box in self.chats.rows() if names.count(chat[0]) == 1]
            if self.page == "Chat":
                return []
            return [{"label": row[0], "selector": {"by": "text", "value": row[0]}, "bounds": [0.035, (211 + i * 67) / 800, 0.965, (273 + i * 67) / 800]} for i, row in enumerate(self._rows())]

    def exists(self, node):
        return any(e["selector"] == {"by": node["by"], "value": node["value"]} for e in self.elements())

    def perform(self, node):
        with self.lock:
            op = node["op"]
            if op == "launch":
                self.history.clear()
                self.page = {"com.android.settings": "Einstellungen", DEMO_CHATS_PACKAGE: "Demo-Chats"}.get(node["package"], node["package"])
                self.typed = ""
                self.chats.list_offset = 0
            elif op == "click":
                if not self.exists(node):
                    raise ValueError("Das Element ist im Demo-Bildschirm nicht sichtbar.")
                if self.page == "Demo-Chats":
                    self._open_chat(next(index for index, chat, _, _ in self.chats.rows() if chat[0] == node["value"]))
                else:
                    self._navigate(node["value"])
            elif op == "tap" and self._in_chats():
                if self.page == "Demo-Chats":
                    index = next((index for index, _, _, box in self.chats.rows() if box[0] <= node["x"] * 390 <= box[2] and box[1] <= node["y"] * 800 <= box[3]), None)
                    if index is not None:
                        self._open_chat(index)
            elif op == "tap":
                for element in self.elements():
                    x1, y1, x2, y2 = element["bounds"]
                    if x1 <= node["x"] <= x2 and y1 <= node["y"] <= y2:
                        self._navigate(element["label"])
                        break
            elif op == "press":
                if node["key"] == "home":
                    self.history.clear()
                    self.page = "Startbildschirm"
                elif node["key"] == "back":
                    self.page = self.history.pop() if self.history else "Startbildschirm"
                self.typed = ""
            elif op == "type":
                self.typed = node["text"]

    def screenshot(self):
        with self.lock:
            if self._in_chats():
                return self.chats.svg(self.page == "Chat"), "image/svg+xml"
            parts = ['<svg xmlns="http://www.w3.org/2000/svg" width="390" height="800" viewBox="0 0 390 800">', '<rect width="390" height="800" fill="#f8f9fc"/>', '<g font-family="Segoe UI,Arial,sans-serif" fill="#20273b">', '<text x="25" y="34" font-size="14" font-weight="600">09:41</text>', '<path d="M310 22h3v8h-3zm6-4h3v12h-3zm6-4h3v16h-3z" fill="#20273b"/>', '<rect x="340" y="19" width="24" height="12" rx="3" fill="none" stroke="#20273b" stroke-width="1.5"/><rect x="343" y="22" width="17" height="6" rx="1" fill="#20273b"/>', f'<text x="25" y="111" font-size="30" font-weight="500">{html.escape(self.page[:23])}</text>', '<rect x="20" y="139" width="350" height="48" rx="24" fill="#e9edf5"/>', '<circle cx="43" cy="162" r="7" fill="none" stroke="#798296" stroke-width="2"/><path d="m48 168 5 5" stroke="#798296" stroke-width="2"/>', f'<text x="66" y="168" font-size="14" fill="#798296">{html.escape(self.typed[:32] or "Einstellungen durchsuchen")}</text>']
            for i, (title, subtitle, colour) in enumerate(self._rows()):
                y = 211 + i * 67
                parts += [f'<circle cx="42" cy="{y+29}" r="19" fill="{colour}"/>', f'<rect x="35" y="{y+22}" width="14" height="14" rx="4" fill="none" stroke="#64708a" stroke-width="1.8"/>', f'<text x="77" y="{y+24}" font-size="16" font-weight="500">{html.escape(title)}</text>', f'<text x="77" y="{y+45}" font-size="11.5" fill="#8890a0">{html.escape(subtitle)}</text>']
            if not self._rows():
                detail = {"Helligkeit": "Helligkeit: 65 %", "Dunkles Design": "Dunkles Design: Aus", "Bildschirm-Timeout": "Ruhezustand nach 30 Sekunden"}.get(self.page, "Demo-Unterseite")
                parts += [f'<text x="25" y="242" font-size="18">{html.escape(detail)}</text>', '<text x="25" y="282" font-size="13" fill="#798296">Simulierte Ansicht · Zurück führt zur Liste.</text>']
                if self.page == "Helligkeit":
                    parts += ['<rect x="25" y="315" width="340" height="8" rx="4" fill="#e2deef"/><rect x="25" y="315" width="221" height="8" rx="4" fill="#7960d8"/><circle cx="246" cy="319" r="11" fill="#7960d8"/>']
            parts += ['<rect x="147" y="780" width="96" height="4" rx="2" fill="#20273b"/></g></svg>']
            return "".join(parts).encode(), "image/svg+xml"
