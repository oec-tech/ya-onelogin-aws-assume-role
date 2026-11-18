"""
Remembers the AWS role and MFA device picked last time, so the menus can
start on them. Only ARNs and device ids are stored, nothing secret.
"""

import json
import os


LAST_CHOICES_PATH = os.path.join(os.path.expanduser('~'), '.onelogin', 'last_choices.json')


def _key(subdomain, username, app_id):
    return '%s|%s|%s' % (subdomain, username, app_id)


def _read():
    try:
        with open(LAST_CHOICES_PATH) as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def get_last_choice(subdomain, username, app_id, kind):
    entry = _read().get(_key(subdomain, username, app_id))
    return entry.get(kind) if isinstance(entry, dict) else None


def save_last_choice(subdomain, username, app_id, kind, value):
    data = _read()
    entry = data.setdefault(_key(subdomain, username, app_id), {})
    if not isinstance(entry, dict) or entry.get(kind) == value:
        return
    entry[kind] = value
    try:
        os.makedirs(os.path.dirname(LAST_CHOICES_PATH), exist_ok=True)
        with open(LAST_CHOICES_PATH, 'w') as f:
            json.dump(data, f, indent=2)
    except OSError:
        pass


def index_of(values, value):
    try:
        return values.index(value)
    except ValueError:
        return None
