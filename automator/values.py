"""Scalar variables shared by the runner and standalone Python exports."""
import math


def scalar_value(value):
    if isinstance(value, str) and len(value) <= 2000:
        return value
    if not isinstance(value, bool) and isinstance(value, (int, float)) and math.isfinite(value) and abs(value) <= 1e12:
        return value
    raise ValueError('Variablen erlauben Text bis 2000 Zeichen oder endliche Zahlen zwischen -10¹² und 10¹².')


def variable_value(variables, name):
    if name not in variables:
        raise ValueError(f'Variable „{name}“ wurde noch nicht gesetzt.')
    return variables[name]


def as_text(value, label, allow_empty=False):
    text = str(scalar_value(value))
    if not allow_empty and not text.strip():
        raise ValueError(f'{label}: Der Wert darf nicht leer sein.')
    return text


def as_number(value, low, high, label, integer=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f'{label}: Die Variable muss eine Zahl enthalten, keinen Text.')
    if not low <= value <= high or (integer and int(value) != value):
        raise ValueError(f'{label}: Erlaubt sind Werte von {low} bis {high}.')
    return int(value) if integer else value


def resolve_value(value, variables, current_item=None):
    if isinstance(value, dict):
        if value.get('source') == 'item':
            return current_item
        return variable_value(variables, value['name'])
    return value


def resolve_command(node, variables, current_item=None):
    result = dict(node)
    op = node['op']
    for key in ('value', 'text', 'seconds', 'times', 'timeout', 'amount'):
        if key in node:
            result[key] = resolve_value(node[key], variables, current_item)
    if op in {'click', 'wait_for', 'if_exists', 'scroll_find', 'read_list', 'scan_list'}:
        result['value'] = as_text(result['value'], 'Suchtext / Listenfilter', op in {'read_list', 'scan_list'} and node['by'] == 'textContains')
    if op == 'type':
        result['text'] = as_text(result['text'], 'Eingabetext', True)
    for key, low, high, label, integer in [('seconds', 0, 3600, 'Wartezeit', False), ('timeout', 0, 120, 'Zeitlimit', False), ('times', 1, 100, 'Wiederholungen', True), ('amount', -1e12, 1e12, 'Änderung', False)]:
        if key in result:
            result[key] = as_number(result[key], low, high, label, integer)
    if op == 'var_set':
        result['value'] = scalar_value(result['value'])
    return result
