"""Validate a small command language; never execute user-supplied Python."""
import json
import math
import inspect

from .lists import MAX_LIST_ITEMS, read_visible_texts
from .scrolling import screen_snapshot, U2ScrollDevice, traverse_screen
from .list_items import validate_item_pattern, item_bounds, item_text, pattern_nodes, selected_region, read_list_items, list_entries
from .values import scalar_value, variable_value, as_text, as_number


class ProgramError(ValueError):
    pass


SELECTORS = {"text", "resourceId", "description"}
KEYS = {"home", "back", "recent", "enter", "volume_up", "volume_down"}
DIRECTIONS = {"up", "down", "left", "right"}


def validate(program, saved_lists=None):
    count = 0

    def string(value, label, allow_empty=False):
        if not isinstance(value, str) or len(value) > 2000 or (not allow_empty and not value.strip()):
            raise ProgramError(f"{label}: Bitte einen gültigen Text eingeben (max. 2000 Zeichen).")
        return value

    def number(value, low, high, label, integer=False):
        if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value):
            raise ProgramError(f"{label}: Bitte eine Zahl eingeben.")
        if not low <= value <= high or (integer and int(value) != value):
            raise ProgramError(f"{label}: Erlaubt sind Werte von {low} bis {high}.")
        return int(value) if integer else value

    def reference(value, in_loop):
        if value == {'source': 'item'}:
            if not in_loop:
                raise ProgramError('„Aktueller Eintrag“ gehört in eine „Für jeden Eintrag“-Schleife.')
            return dict(value)
        if set(value) == {'source', 'name'} and value['source'] == 'variable':
            return {'source': 'variable', 'name': variable_name(value['name'])}
        raise ProgramError('Unbekannter Variablen- oder Listenwert.')

    def variable_name(value):
        name = string(value, 'Variablenname').strip()
        if len(name) > 80:
            raise ProgramError('Ein Variablenname darf höchstens 80 Zeichen enthalten.')
        return name

    def number_value(value, low, high, label, in_loop, integer=False):
        return reference(value, in_loop) if isinstance(value, dict) else number(value, low, high, label, integer)

    def text_value(value, label, in_loop, allow_empty=False):
        if isinstance(value, dict):
            return reference(value, in_loop)
        return string(value, label, allow_empty)

    def list_name(value):
        value = string(value, "Listenname").strip()
        if len(value) > 80:
            raise ProgramError("Ein Listenname darf höchstens 80 Zeichen enthalten.")
        return value

    def sequence(items, depth=0, in_loop=False):
        nonlocal count
        if not isinstance(items, list) or depth > 12:
            raise ProgramError("Der Ablauf ist ungültig oder zu tief verschachtelt.")
        result = []
        for item in items:
            count += 1
            if count > 500 or not isinstance(item, dict):
                raise ProgramError("Ein Ablauf darf höchstens 500 Blöcke enthalten.")
            op = item.get("op")
            node = {"op": op, "id": string(item.get("id", "block"), "Block-ID")}
            if op in {"click", "wait_for", "if_exists"}:
                if item.get("by") not in SELECTORS:
                    raise ProgramError("Bitte Text, Element-ID oder Beschreibung als Suchmethode wählen.")
                node.update(by=item["by"], value=text_value(item.get("value"), "Gesuchtes Element", in_loop))
            if op == "launch":
                node["package"] = string(item.get("package"), "App-Paket")
            elif op == "tap":
                for key in ("x", "y"):
                    node[key] = number(item.get(key), 0, 1, "Bildschirmposition")
            elif op in {"click", "wait_for"}:
                node["timeout"] = number_value(item.get("timeout", 10), 0, 120, "Zeitlimit", in_loop)
            elif op == "type":
                node["text"] = text_value(item.get("text"), "Eingabetext", in_loop, True)
            elif op == "wait":
                node["seconds"] = number_value(item.get("seconds"), 0, 3600, "Wartezeit", in_loop)
            elif op == "press":
                if item.get("key") not in KEYS:
                    raise ProgramError("Unbekannte Gerätetaste.")
                node["key"] = item["key"]
            elif op == "swipe":
                if item.get("direction") not in DIRECTIONS:
                    raise ProgramError("Unbekannte Wischrichtung.")
                node["direction"] = item["direction"]
            elif op == "repeat":
                node["times"] = number_value(item.get("times"), 1, 100, "Wiederholungen", in_loop, True)
                node["body"] = sequence(item.get("body"), depth + 1, in_loop)
            elif op == 'var_set':
                node['name'] = variable_name(item.get('name'))
                value = item.get('value')
                try:
                    node['value'] = reference(value, in_loop) if isinstance(value, dict) else scalar_value(value)
                except ValueError as exc:
                    raise ProgramError(str(exc)) from exc
            elif op == 'var_change':
                node['name'] = variable_name(item.get('name'))
                node['amount'] = number_value(item.get('amount'), -1e12, 1e12, 'Änderung', in_loop)
            elif op == "list_create":
                node["name"] = list_name(item.get("name"))
                values = item.get("items")
                if not isinstance(values, list) or len(values) > MAX_LIST_ITEMS:
                    raise ProgramError(f"Eine Liste darf höchstens {MAX_LIST_ITEMS} Einträge enthalten.")
                node["items"] = [string(value, "Listeneintrag") for value in values]
            elif op in {"read_list", "scan_list"}:
                node["name"] = list_name(item.get("name"))
                if item.get("by") not in {"textContains", "resourceId", "className"}:
                    raise ProgramError("Unbekannter Filter für die Bildschirm-Liste.")
                node["by"] = item["by"]
                node["value"] = text_value(item.get("value"), "Listenfilter", in_loop, item["by"] == "textContains")
                if op == 'scan_list' and item.get('pattern') is not None:
                    try:
                        node['pattern'] = validate_item_pattern(item['pattern'])
                    except ValueError as exc:
                        raise ProgramError(str(exc)) from exc
            elif op == "scroll_find":
                node["value"] = text_value(item.get("value"), "Suchtext", in_loop)
                node["match"] = item.get("match", "exact")
                if node["match"] not in {"exact", "contains"}:
                    raise ProgramError("Unbekannte Textsuche.")
            elif op == "for_each":
                node["name"] = list_name(item.get("name"))
                node["body"] = sequence(item.get("body"), depth + 1, True)
            elif op == "backup_list":
                node["name"] = list_name(item.get("name"))
                if item.get("pattern") is None:
                    raise ProgramError("„Liste sichern“: Bitte zuerst im Baustein ein Listenelement auswählen (Auswahl-Symbol).")
                try:
                    node["pattern"] = validate_item_pattern(item["pattern"])
                except ValueError as exc:
                    raise ProgramError(str(exc)) from exc
                node["order"] = item.get("order", "end_to_start")
                if node["order"] not in {"end_to_start", "start_to_end"}:
                    raise ProgramError("Unbekannte Reihenfolge für „Liste sichern“.")
                node["max_pages"] = number(item.get("max_pages", 200), 1, 2000, "Seiten je Eintrag", True)
            elif op == "if_exists":
                node["body"] = sequence(item.get("body"), depth + 1, in_loop)
                node["otherwise"] = sequence(item.get("otherwise", []), depth + 1, in_loop)
            elif op != "screenshot":
                raise ProgramError(f"Unbekannter Befehl: {op}")
            result.append(node)
        return result

    result = sequence(program)
    if not result:
        raise ProgramError("Verbinde mindestens einen Befehl mit dem Startblock.")

    # Global upper bounds remain valid even when a loop replaces a named list.
    bounds = {name: len(values) for name, values in (saved_lists or {}).items()}
    def collect(items):
        for node in items:
            if node["op"] in {"list_create", "read_list", "scan_list"}:
                size = len(node["items"]) if node["op"] == "list_create" else MAX_LIST_ITEMS
                bounds[node["name"]] = max(bounds.get(node["name"], 0), size)
            collect(node.get("body", []))
            collect(node.get("otherwise", []))
    collect(result)

    def cost(items):
        total = 0
        for node in items:
            total += 1
            if node["op"] == "repeat":
                total += (100 if isinstance(node['times'], dict) else node['times']) * cost(node["body"])
            if node["op"] == "for_each":
                if node["name"] not in bounds:
                    raise ProgramError(f'Liste „{node["name"]}“ fehlt. Füge zuerst einen Listen-Baustein hinzu.')
                total += bounds[node["name"]] * cost(node["body"])
            if node["op"] == "if_exists":
                total += max(cost(node["body"]), cost(node["otherwise"]))
        return total

    if cost(result) > 10000:
        raise ProgramError("Dieser Ablauf würde mehr als 10.000 Schritte ausführen. Verkleinere die Schleifen.")
    return result


def export_python(program, serial=None, saved_lists=None):
    program = validate(program, saved_lists)
    def contains(items, operations):
        return any(n["op"] in operations or contains(n.get("body", []), operations) or contains(n.get("otherwise", []), operations) for n in items)
    if contains(program, {"backup_list"}):
        raise ProgramError("„Liste sichern“ läuft nur in Droid Studio, weil dort Bericht und Hashwerte entstehen. Für den Python-Export diesen Baustein deaktivieren.")
    def used_names(items):
        names = set()
        for node in items:
            if node["op"] == "for_each":
                names.add(node["name"])
            names.update(used_names(node.get("body", [])))
            names.update(used_names(node.get("otherwise", [])))
        return names
    referenced = used_names(program)
    saved_lists = {name: values for name, values in (saved_lists or {}).items() if name in referenced}
    quote = lambda value: json.dumps(value, ensure_ascii=False)
    lines = ["# Erstellt mit Droid Studio · benötigt: pip install uiautomator2", "import time", "from pathlib import Path", "import uiautomator2 as u2", "", f"d = u2.connect({quote(serial) if serial else ''})", "Path('screenshots').mkdir(exist_ok=True)", ""]
    def has_reference(value):
        if isinstance(value, dict):
            return value.get('source') in {'variable', 'item'} or any(has_reference(v) for v in value.values())
        return isinstance(value, list) and any(has_reference(v) for v in value)
    if has_reference(program) or contains(program, {'var_set', 'var_change'}):
        lines.extend(['import math', 'variables = {}', ''])
        for helper in (scalar_value, variable_value, as_text, as_number):
            lines.extend([inspect.getsource(helper).rstrip(), ''])
    if contains(program, {"list_create", "read_list", "scan_list", "for_each"}):
        lines.extend(["lists = " + quote(saved_lists or {}), ""])
    if contains(program, {"read_list", "scan_list", "scroll_find"}):
        lines.extend(["import re", "import statistics", "import xml.etree.ElementTree as ET", f"MAX_LIST_ITEMS = {MAX_LIST_ITEMS}", "", inspect.getsource(read_visible_texts).rstrip(), ""])
    if contains(program, {"scan_list", "scroll_find"}):
        for helper in (item_bounds, item_text, pattern_nodes, selected_region, read_list_items, list_entries, screen_snapshot, U2ScrollDevice, traverse_screen):
            lines.extend([inspect.getsource(helper).rstrip(), ""])
        lines.extend(["scroll_device = U2ScrollDevice(d)", ""])
    loop_count = 0

    def emit(items, indent=0, current_item=None):
        nonlocal loop_count
        pad = "    " * indent
        def expression(value):
            if isinstance(value, dict):
                return current_item if value['source'] == 'item' else f"variable_value(variables, {quote(value['name'])})"
            return quote(value)
        def text_expression(value, allow_empty=False):
            return f"as_text({expression(value)}, 'Textwert', {allow_empty})" if isinstance(value, dict) else quote(value)
        def number_expression(value, low, high, label, integer=False):
            return f"as_number({expression(value)}, {low}, {high}, {quote(label)}, {integer})" if isinstance(value, dict) else quote(value)
        if not items:
            lines.append(pad + "pass")
        for node in items:
            op = node["op"]
            selector = f"d({node['by']}={text_expression(node['value'])})" if "by" in node else ""
            if op == "launch":
                statement = f"d.app_start({quote(node['package'])})"
            elif op == "tap":
                # Pixel conversion avoids uiautomator2 treating 1.0 as pixel 1.
                statement = f"w, h = d.window_size()\n{pad}d.click(round({node['x']} * (w - 1)), round({node['y']} * (h - 1)))"
            elif op == "click":
                statement = f"{selector}.click(timeout={number_expression(node['timeout'], 0, 120, 'Zeitlimit')})"
            elif op == "wait_for":
                statement = f"if not {selector}.wait(timeout={number_expression(node['timeout'], 0, 120, 'Zeitlimit')}):\n{pad}    raise TimeoutError('Element nicht gefunden: ' + {text_expression(node['value'])})"
            elif op == "type":
                statement = f"d.send_keys({text_expression(node['text'], True)}, clear=True)"
            elif op == "wait":
                statement = f"time.sleep({number_expression(node['seconds'], 0, 3600, 'Wartezeit')})"
            elif op == 'var_set':
                statement = f"variables[{quote(node['name'])}] = scalar_value({expression(node['value'])})"
            elif op == 'var_change':
                statement = f"variables[{quote(node['name'])}] = scalar_value(as_number(variable_value(variables, {quote(node['name'])}), -1e12, 1e12, 'Variable ändern') + {number_expression(node['amount'], -1e12, 1e12, 'Änderung')})"
            elif op == "press":
                statement = f"d.press({quote(node['key'])})"
            elif op == "swipe":
                statement = f"d.swipe_ext({quote(node['direction'])}, scale=0.7)"
            elif op == "screenshot":
                statement = "d.screenshot(str(Path('screenshots') / f'{time.time_ns()}.png'))"
            elif op == "repeat":
                lines.append(pad + f"for _ in range({number_expression(node['times'], 1, 100, 'Wiederholungen', True)}):")
                emit(node["body"], indent + 1, current_item)
                continue
            elif op == "list_create":
                statement = f"lists[{quote(node['name'])}] = {quote(node['items'])}"
            elif op == "read_list":
                statement = f"lists[{quote(node['name'])}] = read_visible_texts(d.dump_hierarchy(), *d.window_size(), {quote(node['by'])}, {text_expression(node['value'], node['by'] == 'textContains')})"
            elif op == "scan_list":
                pattern_arg = f", pattern={quote(node['pattern'])}" if node.get('pattern') else ''
                statement = f"lists[{quote(node['name'])}] = traverse_screen(scroll_device, by={quote(node['by'])}, value={text_expression(node['value'], node['by'] == 'textContains')}, progress=print{pattern_arg})"
            elif op == "scroll_find":
                statement = f"if not traverse_screen(scroll_device, target={text_expression(node['value'])}, match={quote(node['match'])}, progress=print):\n{pad}    raise ValueError('Text bis zum Ende nicht gefunden: ' + {text_expression(node['value'])})"
            elif op == "for_each":
                loop_count += 1
                variable = f"item_{loop_count}"
                lines.append(pad + f"if {quote(node['name'])} not in lists:")
                lines.append(pad + "    raise ValueError(" + quote(f'Liste „{node["name"]}“ wurde noch nicht erstellt oder gelesen.') + ")")
                lines.append(pad + f"for {variable} in list(lists[{quote(node['name'])}]):")
                emit(node["body"], indent + 1, variable)
                continue
            elif op == "if_exists":
                lines.append(pad + f"if {selector}.exists:")
                emit(node["body"], indent + 1, current_item)
                if node["otherwise"]:
                    lines.append(pad + "else:")
                    emit(node["otherwise"], indent + 1, current_item)
                continue
            lines.append(pad + statement)
    emit(program)
    return "\n".join(lines) + "\n"
