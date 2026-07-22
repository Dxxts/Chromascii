import datetime

from rich.text import Text

from . import state

SUCCESS = '#4ade80'
WARN = '#fbbf24'
ERROR = '#f87171'
MUTED = 'bright_black'
TEXT = 'white'

THEMES = {
    'violet': ('#8b5cf6', '#22d3ee'),
    'sunset': ('#fb923c', '#f472b6'),
    'matrix': ('#16a34a', '#4ade80'),
    'synthwave': ('#ec4899', '#22d3ee'),
    'ocean': ('#0ea5e9', '#14b8a6'),
    'forest': ('#22c55e', '#a3e635'),
    'rose': ('#f43f5e', '#fb7185'),
    'amber': ('#f59e0b', '#fbbf24'),
    'ice': ('#38bdf8', '#e2e8f0'),
    'grape': ('#7c3aed', '#c084fc'),
    'fire': ('#ef4444', '#f97316'),
    'mint': ('#10b981', '#5eead4'),
    'candy': ('#f472b6', '#fde047'),
    'nord': ('#5e81ac', '#88c0d0'),
    'mono': ('#d4d4d8', '#a1a1aa'),
    'cyberpunk': ('#facc15', '#ec4899'),
}

THEME_NAMES = list(THEMES.keys())

_cached_name = None


class Theme:
    def __init__(self, name, accent, accent2):
        self.name = name
        self.accent = accent
        self.accent2 = accent2
        self.success = SUCCESS
        self.warn = WARN
        self.error = ERROR
        self.muted = MUTED
        self.text = TEXT


def _theme_of_day():
    seed = datetime.date.today().toordinal()
    return THEME_NAMES[seed % len(THEME_NAMES)]


def current():
    global _cached_name
    if _cached_name is None:
        if state.theme_touched():
            name = state.get_theme_name()
            _cached_name = name if name in THEMES else 'violet'
        else:
            _cached_name = _theme_of_day()
    accent, accent2 = THEMES[_cached_name]
    return Theme(_cached_name, accent, accent2)


def cycle():
    global _cached_name
    cur = current()
    idx = (THEME_NAMES.index(cur.name) + 1) % len(THEME_NAMES)
    _cached_name = THEME_NAMES[idx]
    state.set_theme_name(_cached_name)
    return current()


def _hex_to_rgb(h):
    h = h.lstrip('#')
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def time_tint(hex_color, hour=None):
    if hour is None:
        hour = datetime.datetime.now().hour
    r, g, b = _hex_to_rgb(hex_color)
    if 0 <= hour < 6:
        factor = 0.55
        b = min(255, int(b * 1.15))
    elif 18 <= hour < 22:
        factor = 0.9
        r = min(255, int(r * 1.1))
    elif 22 <= hour < 24:
        factor = 0.7
    else:
        factor = 1.0
    r, g, b = (max(0, min(255, int(c * factor))) for c in (r, g, b))
    return f'#{r:02x}{g:02x}{b:02x}'


def gradient_text(s, c1=None, c2=None, bold=True, tint=False):
    if c1 is None or c2 is None:
        t = current()
        c1, c2 = c1 or t.accent, c2 or t.accent2
    if tint:
        c1, c2 = time_tint(c1), time_tint(c2)
    r1, g1, b1 = _hex_to_rgb(c1)
    r2, g2, b2 = _hex_to_rgb(c2)
    n = max(len(s) - 1, 1)
    out = Text()
    prefix = 'bold ' if bold else ''
    for i, ch in enumerate(s):
        f = i / n
        r = round(r1 + (r2 - r1) * f)
        g = round(g1 + (g2 - g1) * f)
        b = round(b1 + (b2 - b1) * f)
        out.append(ch, f'{prefix}#{r:02x}{g:02x}{b:02x}')
    return out
