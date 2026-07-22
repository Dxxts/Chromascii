import sys
import math
import time
import random
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.align import Align
from rich.rule import Rule

from ..utils import (
    getch, kbhit, get_terminal_size, hide_cursor, show_cursor,
    enable_mouse_mode, disable_mouse_mode, poll_input_event,
)
from ..renderer.engine import _runs as _rle_runs
from . import theme

console = Console()

_TITLE = 'chromascii'
_TAGLINE = 'turn anything into art'
_SHINY_CHANCE = 1 / 20

_V2_UPDATES = [
    '60fps everywhere — video, gif and webcam',
    'Six rendering engines: ascii, halfblock, quadblock, sextant, braille, octant',
    'Synchronized audio for video playback, spacebar pause/resume',
    'Paste a link — YouTube, TikTok, Tenor, Imgur and more',
    'Webcam up to 60fps, 1440p virtual camera',
    'Export rendered output as a video file (--export)',
]

_IDLE_PET_SECONDS = 40
_IDLE_SCREENSAVER_SECONDS = 60
_ASSETS_DIR = Path(__file__).resolve().parent.parent / 'assets'
_SECRET_COMBO = 'cat'


def _normalize_frames(frames):
    h = max(len(f) for f in frames)
    w = max(len(line) for f in frames for line in f)
    out = []
    for f in frames:
        padded = [line.ljust(w) for line in f]
        padded += [' ' * w] * (h - len(padded))
        out.append(padded)
    return out


_RAW_PETS = {
    'cat': [
        [" /\\_/\\ ", "( o.o )", " d   b "],
        [" /\\_/\\ ", "( ^.^ )", "  b d  "],
        [" /\\_/\\ ", "( -.- )", " b   d "],
        [" /\\_/\\ ", "( ^o^ )", "  d b  "],
    ],
    'dog': [
        [" / \\__ ", "(=' ^')", " (\")_(\")"],
        [" / \\__ ", "(=' .')", " (\") (\")"],
        [" / \\__ ", "(=' o')", " (\")_(\")"],
        [" / \\__ ", "(=' -')", " (\") (\")"],
    ],
    'bunny': [
        [" (\\_/)", "(='.'=)", "o(\")(\")o"],
        [" (\\_/)", "(=^.^=)", "o(\")(\")o"],
        [" (\\_/)", "(='-'=)", " (\")(\") "],
        [" (\\_/)", "(=o.o=)", "o(\")(\")o"],
    ],
    'penguin': [
        [" .--. ", "(o  o)", "/|  |\\", " |  | "],
        [" .--. ", "(^  ^)", "\\|  |/", " |  | "],
        [" .--. ", "(-  -)", "/|  |\\", " |  | "],
        [" .--. ", "(o  o)", "\\|  |/", " |  | "],
    ],
}

_PETS = {name: _normalize_frames(frames) for name, frames in _RAW_PETS.items()}
_PET_NAMES = list(_PETS.keys())
_PET_DEFAULT_DURATION = 8.0
_PET_DURATIONS = {'cat': 14.6}

_SCREENSAVER_CHARS = '01+*.:·'
_FIELD_CHARS = ' .:-=+*#%@'


def _splash():
    shiny = random.random() < _SHINY_CHANCE
    for n in range(1, len(_TITLE) + 1):
        console.clear()
        console.print()
        console.print()
        console.print()
        if shiny:
            console.print(Align.center(theme.gradient_text(_TITLE[:n], c1='#fde047', c2='#ffffff')))
        else:
            console.print(Align.center(theme.gradient_text(_TITLE[:n], tint=True)))
        if n == len(_TITLE):
            if shiny:
                console.print(Align.center(Text('✨ shiny ✨', style='bold #fde047')))
            else:
                console.print(Align.center(Text(_TAGLINE, style='dim italic')))
        time.sleep(0.045)
    time.sleep(0.3)


def _print_updates(t):
    console.print(f'  [bold {t.accent2}]✦[/] [bold white]new in v2[/]')
    for line in _V2_UPDATES:
        console.print(f'    [{t.muted}]·[/] [dim]{line}[/]')


def _draw(highlight=None, flash_message=None):
    console.clear()
    t = theme.current()
    console.print()
    console.print(Align.center(theme.gradient_text(_TITLE, tint=True)))
    console.print(Align.center(Text(_TAGLINE, style='dim italic')))
    console.print()

    if flash_message:
        console.print(Align.center(f'[{t.accent2}]{flash_message}[/]'))
        console.print()

    console.print(Rule(style=t.muted))
    console.print()

    _print_updates(t)
    console.print()

    entries = [
        ('1', 'open file', 'pick an image, video or gif'),
        ('2', 'paste path', 'enter a file path or link (YouTube, TikTok, Tenor, Imgur, …)'),
        ('3', 'use webcam', 'live ASCII from camera'),
    ]

    for key, label, hint in entries:
        sel = highlight == key
        line = Text()
        line.append('  ')
        line.append('› ' if sel else '  ', f'bold {t.accent2}')
        line.append(f'{key} ', f'bold {t.accent2}' if sel else t.muted)
        line.append(f'{label:<12}', 'bold white' if sel else 'white')
        line.append(hint, 'white' if sel else 'dim')
        console.print(line)

    console.print()
    console.print(f'  [{t.muted}]q[/]  [dim]quit[/]    '
                   f'[{t.muted}]t[/]  [dim]theme ({t.name})[/]    '
                   f'[{t.muted}]?[/]  [dim]help[/]')
    console.print()


def _typewriter_flash(message):
    for i in range(1, len(message) + 1):
        _draw(None, message[:i])
        time.sleep(0.012)
    time.sleep(0.4)


def _draw_help(t):
    console.clear()
    console.print()
    console.print(f'  [bold {t.accent2}]chromascii[/]  [{t.muted}]›[/]  [white]help[/]')
    console.print(Rule(style=t.muted))
    console.print()

    shortcuts = [
        ('1 / 2 / 3', 'open file / paste path / use webcam'),
        ('↑ / ↓', 'navigate menus'),
        ('← / →', 'adjust sliders'),
        ('tab', 'cycle charset / color / detail'),
        ('space', 'toggle loop / dither / virtual cam'),
        ('enter', 'confirm / play'),
        ('t', 'cycle color theme'),
        ('q / esc', 'back / quit'),
    ]
    for keys, desc in shortcuts:
        console.print(f'   [bold {t.accent2}]{keys:<10}[/]  [dim]{desc}[/]')

    console.print()
    console.print(Rule(style=t.muted))
    console.print('[dim]  q  back[/]')


def _show_help():
    t = theme.current()
    _draw_help(t)
    buf = ''
    while True:
        k = getch()
        if k in ('q', 'Q', '\x1b', '\n', '\x03'):
            return None
        if len(k) == 1:
            buf = (buf + k)[-len(_SECRET_COMBO):]
            if buf == _SECRET_COMBO:
                return 'cat'


def _draw_pet_frame(lines, t):
    tw, th = get_terminal_size()
    h = len(lines)
    w = max(len(l) for l in lines)
    row0 = max(1, th - h - 1)
    col0 = max(1, tw - w - 2)
    r, g, b = theme._hex_to_rgb(t.accent2)
    for i, line in enumerate(lines):
        sys.stdout.write(f'\033[{row0 + i};{col0}H')
        sys.stdout.write(f'\033[38;2;{r};{g};{b}m{line}\033[0m')
    sys.stdout.flush()


def _dismiss_pending():
    if kbhit():
        getch()
        return True
    if sys.platform == 'win32':
        return poll_input_event()
    return False


def _play_dancing_pet(name=None):
    from ..renderer.audio import AudioPlayer, AUDIO_AVAILABLE

    if name is None:
        name = random.choice(_PET_NAMES)
    t = theme.current()
    frames = _PETS[name]
    duration = _PET_DURATIONS.get(name, _PET_DEFAULT_DURATION)

    asset = _ASSETS_DIR / f'dancing_{name}.mp3'
    audio = None
    if AUDIO_AVAILABLE and asset.is_file():
        audio = AudioPlayer(str(asset))
        audio.start()

    mouse_token = enable_mouse_mode()
    t0 = time.perf_counter()
    i = 0
    try:
        while time.perf_counter() - t0 < duration:
            if _dismiss_pending():
                break
            _draw_pet_frame(frames[i % len(frames)], t)
            i += 1
            time.sleep(0.25)
    finally:
        disable_mouse_mode(mouse_token)
        if audio:
            audio.stop()


def _render_field_frame(char_idx, fade, charset, ar, ag, ab, br, bg, bb):
    import numpy as np
    H, W = char_idx.shape
    fade_q = (fade * 31).astype(np.int32)
    key = char_idx.astype(np.int64) * 32 + fade_q

    buf = ['\033[H']
    for y in range(H):
        row_idx, row_fade, row_key = char_idx[y], fade[y], key[y]
        starts, lengths = _rle_runs(row_key)
        parts = []
        for x0, ln in zip(starts, lengths):
            ci = int(row_idx[x0])
            if ci == 0:
                parts.append(' ' * int(ln))
                continue
            f = float(row_fade[x0])
            r = int(ar + (br - ar) * f)
            g = int(ag + (bg - ag) * f)
            b = int(ab + (bb - ab) * f)
            parts.append(f'\033[38;2;{r};{g};{b}m{charset[ci] * int(ln)}')
        buf.append(''.join(parts))
        buf.append('\033[0m\n')
    return ''.join(buf)


def _screensaver_matrix():
    t = theme.current()
    ar, ag, ab = theme._hex_to_rgb(t.accent)
    br, bg, bb = theme._hex_to_rgb(t.accent2)

    tw, th = get_terminal_size()
    heads = [random.randint(-th, 0) for _ in range(tw)]
    speeds = [random.choice([1, 1, 2]) for _ in range(tw)]
    trail = 10

    while True:
        if _dismiss_pending():
            return

        ntw, nth = get_terminal_size()
        if (ntw, nth) != (tw, th):
            tw, th = ntw, nth
            heads = [random.randint(-th, 0) for _ in range(tw)]
            speeds = [random.choice([1, 1, 2]) for _ in range(tw)]
            console.clear()

        rows = [[' '] * tw for _ in range(th)]
        for c in range(tw):
            head = heads[c]
            for d in range(trail):
                row = head - d
                if 0 <= row < th:
                    ch = random.choice(_SCREENSAVER_CHARS)
                    rows[row][c] = (ch, 'head' if d == 0 else ('fade' if d < 3 else 'tail'))
            heads[c] += speeds[c]
            if head - trail > th:
                heads[c] = random.randint(-th, 0)

        buf = ['\033[H']
        for row in rows:
            parts = []
            for cell in row:
                if cell == ' ':
                    parts.append(' ')
                else:
                    ch, kind = cell
                    if kind == 'head':
                        parts.append(f'\033[1;38;2;{br};{bg};{bb}m{ch}')
                    elif kind == 'fade':
                        parts.append(f'\033[38;2;{ar};{ag};{ab}m{ch}')
                    else:
                        parts.append(f'\033[2;38;2;{ar};{ag};{ab}m{ch}')
            buf.append(''.join(parts))
            buf.append('\033[0m\n')
        sys.stdout.write(''.join(buf))
        sys.stdout.flush()
        time.sleep(0.08)


def _screensaver_vortex():
    import numpy as np
    t = theme.current()
    ar, ag, ab = theme._hex_to_rgb(t.accent)
    br, bg, bb = theme._hex_to_rgb(t.accent2)
    tw, th = get_terminal_size()
    t0 = time.perf_counter()
    n = len(_FIELD_CHARS)

    while True:
        if _dismiss_pending():
            return
        ntw, nth = get_terminal_size()
        if (ntw, nth) != (tw, th):
            tw, th = ntw, nth
            console.clear()

        elapsed = time.perf_counter() - t0
        ys, xs = np.mgrid[0:th, 0:tw].astype(np.float64)
        cx, cy = tw / 2.0, th / 2.0
        dx = xs - cx
        dy = (ys - cy) * 2.0
        radius = np.sqrt(dx * dx + dy * dy)
        angle = np.arctan2(dy, dx)
        wave = np.sin(angle * 3 + radius * 0.22 - elapsed * 2.2)
        v = (wave + 1) / 2.0
        idx = (v * (n - 1)).astype(np.int32).clip(0, n - 1)
        maxr = radius.max() or 1.0
        fade = np.clip(1.0 - radius / maxr, 0.0, 1.0)

        sys.stdout.write(_render_field_frame(idx, fade, _FIELD_CHARS, ar, ag, ab, br, bg, bb))
        sys.stdout.flush()
        time.sleep(0.06)


def _screensaver_plasma():
    import numpy as np
    t = theme.current()
    ar, ag, ab = theme._hex_to_rgb(t.accent)
    br, bg, bb = theme._hex_to_rgb(t.accent2)
    tw, th = get_terminal_size()
    t0 = time.perf_counter()
    n = len(_FIELD_CHARS)

    while True:
        if _dismiss_pending():
            return
        ntw, nth = get_terminal_size()
        if (ntw, nth) != (tw, th):
            tw, th = ntw, nth
            console.clear()

        elapsed = time.perf_counter() - t0
        xs = np.arange(tw, dtype=np.float64)
        ys = np.arange(th, dtype=np.float64) * 2.0
        X, Y = np.meshgrid(xs, ys)
        v = (np.sin(X * 0.15 + elapsed * 1.3)
             + np.sin(Y * 0.15 + elapsed * 1.1)
             + np.sin((X + Y) * 0.1 + elapsed * 1.7)
             + np.sin(np.sqrt(X * X + Y * Y) * 0.12 - elapsed * 2.0))
        v = (v + 4) / 8.0
        idx = (v * (n - 1)).astype(np.int32).clip(0, n - 1)

        sys.stdout.write(_render_field_frame(idx, v, _FIELD_CHARS, ar, ag, ab, br, bg, bb))
        sys.stdout.flush()
        time.sleep(0.07)


def _screensaver_starfield():
    t = theme.current()
    ar, ag, ab = theme._hex_to_rgb(t.accent)
    br, bg, bb = theme._hex_to_rgb(t.accent2)
    tw, th = get_terminal_size()
    cx, cy = tw / 2.0, th / 2.0

    def _new_star():
        return {'angle': random.uniform(0, 2 * math.pi), 'dist': random.uniform(0, 3),
                'speed': random.uniform(0.3, 0.9)}

    stars = [_new_star() for _ in range(80)]
    prev = {}

    while True:
        if _dismiss_pending():
            clear_buf = [f'\033[{y};{x}H ' for (x, y) in prev.values()]
            sys.stdout.write(''.join(clear_buf))
            sys.stdout.flush()
            return

        ntw, nth = get_terminal_size()
        if (ntw, nth) != (tw, th):
            tw, th = ntw, nth
            cx, cy = tw / 2.0, th / 2.0
            console.clear()
            prev = {}

        buf = []
        new_prev = {}
        maxr = max(cx, cy)
        for i, s in enumerate(stars):
            old = prev.get(i)
            if old:
                buf.append(f'\033[{old[1]};{old[0]}H ')

            s['dist'] += s['speed']
            x = cx + math.cos(s['angle']) * s['dist']
            y = cy + math.sin(s['angle']) * s['dist'] * 0.5
            xi, yi = int(x), int(y)

            if s['dist'] > maxr * 1.3 or not (0 <= xi < tw and 0 <= yi < th):
                stars[i] = _new_star()
                continue

            f = min(1.0, s['dist'] / maxr)
            r = int(ar + (br - ar) * f)
            g = int(ag + (bg - ag) * f)
            b = int(ab + (bb - ab) * f)
            ch = '.' if s['dist'] < 4 else ('*' if f < 0.7 else '@')
            buf.append(f'\033[{yi + 1};{xi + 1}H\033[38;2;{r};{g};{b}m{ch}\033[0m')
            new_prev[i] = (xi + 1, yi + 1)

        prev = new_prev
        sys.stdout.write(''.join(buf))
        sys.stdout.flush()
        time.sleep(0.04)


_SCREENSAVERS = [_screensaver_matrix, _screensaver_vortex, _screensaver_plasma, _screensaver_starfield]


def _run_screensaver():
    hide_cursor()
    console.clear()
    mouse_token = enable_mouse_mode()
    try:
        random.choice(_SCREENSAVERS)()
    finally:
        disable_mouse_mode(mouse_token)
        show_cursor()


def _show_farewell():
    from . import messages
    t = theme.current()
    console.clear()
    console.print()
    console.print(Align.center(theme.gradient_text(_TITLE, tint=True)))
    console.print()
    console.print(Align.center(f'[{t.accent2}]{messages.random_farewell()}[/]'))
    console.print()
    time.sleep(1.1)


def show_launcher(first_time=True, flash_message=None):
    if first_time:
        _splash()

    if flash_message:
        _typewriter_flash(flash_message)

    last = None
    redraw = True
    last_input_t = time.perf_counter()
    pet_shown = False

    while True:
        if redraw:
            _draw(last, flash_message)
            redraw = False

        if kbhit():
            k = getch()
            last_input_t = time.perf_counter()
            pet_shown = False
            redraw = True

            if k == '1':
                last = '1'; _draw('1', flash_message); time.sleep(0.08)
                return 'file'
            if k == '2':
                last = '2'; _draw('2', flash_message); time.sleep(0.08)
                return 'path'
            if k == '3':
                last = '3'; _draw('3', flash_message); time.sleep(0.08)
                return 'webcam'
            if k in ('t', 'T'):
                theme.cycle()
                continue
            if k == '?':
                secret = _show_help()
                if secret == 'cat':
                    _play_dancing_pet('cat')
                last_input_t = time.perf_counter()
                pet_shown = False
                continue
            if k in ('q', 'Q', '\x1b', '\x03'):
                _show_farewell()
                return 'quit'
            continue

        idle = time.perf_counter() - last_input_t

        if idle >= _IDLE_SCREENSAVER_SECONDS:
            _run_screensaver()
            last_input_t = time.perf_counter()
            pet_shown = False
            redraw = True
            continue

        if idle >= _IDLE_PET_SECONDS and not pet_shown:
            _play_dancing_pet()
            pet_shown = True
            redraw = True
            continue

        time.sleep(0.1)


def prompt_path():
    t = theme.current()
    console.clear()
    console.print()
    console.print(Align.center(
        Panel(
            f'[bold {t.accent2}]enter path[/]\n\n'
            f'[dim]full path to an image, video, or gif — or a link '
            f'(YouTube, TikTok, Tenor, Imgur, …)[/]',
            border_style=t.accent, padding=(1, 4), expand=False
        )
    ))
    console.print()
    try:
        p = console.input(f'  [bold {t.accent2}]›[/] ').strip().strip('"').strip("'")
        return p
    except (EOFError, KeyboardInterrupt):
        return ''
