"""Reading request bodies and fields safely."""

import json

from django.core.exceptions import BadRequest


def get_payload(request):
    """The request body as a dict. Anything else (a JSON list, a string,
    broken JSON) becomes {} so handlers never call .get() on a non-dict."""
    if request.content_type and request.content_type.startswith('multipart/form-data'):
        return request.POST
    if not request.body:
        return request.POST
    try:
        data = json.loads(request.body.decode('utf-8') or '{}')
    except (json.JSONDecodeError, UnicodeDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def text_field(data, key, current='', max_length=None):
    """A stripped string for ``key``; ``current`` when the key is absent, so
    partial saves never blank out fields. Lists/objects are a 400."""
    if key not in data:
        return current if current is not None else ''
    value = data.get(key)
    if value is None:
        value = ''
    elif isinstance(value, bool) or not isinstance(value, (str, int, float)):
        raise BadRequest(f'{key.replace("_", " ").capitalize()} must be text.')
    value = str(value).strip()
    return value[:max_length] if max_length else value


def choice_field(data, key, current, choices):
    """``current`` when absent; otherwise the value must be one of ``choices``."""
    if key not in data:
        return current
    value = data.get(key)
    allowed = choices if isinstance(choices, (set, frozenset)) else dict(choices)
    if value not in allowed:
        raise BadRequest(f'Unknown {key.replace("_", " ")}.')
    return value


def id_field(value, label='id'):
    """An optional integer id: None for empty, 400 for anything non-numeric."""
    if value in (None, ''):
        return None
    if isinstance(value, bool):
        raise BadRequest(f'{label} must be a number.')
    try:
        return int(value)
    except (TypeError, ValueError):
        raise BadRequest(f'{label} must be a number.')


def parse_boolean(value, default=False):
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    return str(value).strip().lower() in {'1', 'true', 'yes', 'on'}


def parse_int(value, default=None):
    try:
        if value in {None, ''}:
            return default
        return int(value)
    except (TypeError, ValueError):
        return default
