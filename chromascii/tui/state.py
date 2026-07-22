import json
import os
import sys
import datetime
from pathlib import Path

_DEFAULT = {
    'chars_rendered': 0,
    'theme': 'violet',
    'theme_touched': False,
    'msg_bag': [],
    'streak_days': 0,
    'last_open_date': None,
    'videos_watched': 0,
    'gifs_watched': 0,
    'images_viewed': 0,
    'webcam_sessions': 0,
}


def _state_dir():
    if sys.platform == 'win32':
        base = os.environ.get('LOCALAPPDATA') or os.path.expanduser('~')
        d = Path(base) / 'chromascii'
    else:
        base = os.environ.get('XDG_DATA_HOME', os.path.expanduser('~/.local/share'))
        d = Path(base) / 'chromascii'
    d.mkdir(parents=True, exist_ok=True)
    return d


def _state_file():
    return _state_dir() / 'state.json'


def load():
    try:
        with open(_state_file(), 'r', encoding='utf-8') as f:
            data = json.load(f)
        merged = dict(_DEFAULT)
        merged.update(data)
        return merged
    except Exception:
        return dict(_DEFAULT)


def save(state):
    try:
        with open(_state_file(), 'w', encoding='utf-8') as f:
            json.dump(state, f)
    except Exception:
        pass


def add_chars(n):
    if n <= 0:
        return load().get('chars_rendered', 0)
    s = load()
    s['chars_rendered'] = s.get('chars_rendered', 0) + n
    save(s)
    return s['chars_rendered']


def get_theme_name():
    return load().get('theme', 'violet')


def set_theme_name(name):
    s = load()
    s['theme'] = name
    s['theme_touched'] = True
    save(s)


def theme_touched():
    return load().get('theme_touched', False)


def bump_media(kind):
    key = {'video': 'videos_watched', 'gif': 'gifs_watched',
           'image': 'images_viewed', 'webcam': 'webcam_sessions'}.get(kind)
    if key is None:
        return 0
    s = load()
    s[key] = s.get(key, 0) + 1
    save(s)
    return s[key]


def record_open():
    today = datetime.date.today().isoformat()
    s = load()
    last = s.get('last_open_date')
    streak = s.get('streak_days', 0)

    if last == today:
        pass
    elif last == (datetime.date.today() - datetime.timedelta(days=1)).isoformat():
        streak += 1
    else:
        streak = 1

    s['last_open_date'] = today
    s['streak_days'] = streak
    save(s)
    return streak
