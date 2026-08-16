"""A warm little terminal greeting — meant to be called once from a shell
startup hook (see shellhook.py) rather than from inside the chromascii TUI.

Runs for a few seconds (typewriter greeting + art + tip) and never blocks a
shell forever or crashes it: every failure mode here (bad terminal, Ctrl+C
mid-animation, non-tty stdout) is swallowed so a broken greeting can never
break someone's shell startup.

Deliberately never reads stdin. This runs before the user has a shell
prompt, so anything typed while the animation is still playing (someone
typing "chromascii" right away, out of habit) is still in the input buffer
for the shell to pick up afterward — reading it here to support a
skip-on-keypress would silently eat some of those keystrokes instead,
corrupting the very next command they type.
"""

import os
import random
import sys
import time


_RESET = '\033[0m'
_HIDE = '\033[?25l'
_SHOW = '\033[?25h'


# ---------------------------------------------------------------------------
# Content pools
# ---------------------------------------------------------------------------

_TIPS = [
    'chromascii --webcam to go live from your camera',
    'chromascii --webcam --face-censor to blur your face automatically',
    'chromascii clip.gif --loop to loop a gif forever',
    'chromascii "<url>" accepts YouTube, TikTok, Tenor, and Imgur links',
    'chromascii --detail octant for the sharpest possible render',
    'chromascii --webcam --virtual-cam to appear on Discord, Zoom, or OBS',
    'chromascii -h for the full flag reference',
    'chromascii --mic-test to watch your voice as a spectrum',
    'chromascii --calibrate-face to lock in your face-censor tracking',
    'chromascii --color 256 if truecolor looks wrong in your terminal',
    'chromascii --export out.mp4 to save the rendered output',
    'chromascii --chars "█▓▒░ " for a classic dithered look',
    'press space during playback to pause and resume',
    '--dither smooths out gradient banding in ascii mode',
    'chromascii --face-style ascii for a glitchy censor look',
    'chromascii --width 160 for a wider render',
    'six rendering engines: ascii, halfblock, quadblock, sextant, braille, octant',
    'chromascii --loop keeps a video playing on repeat',
    'set CHROMASCII_NO_GREET=1 to silence this greeting',
    'chromascii --uninstall-hook removes this greeting for good',
    'audio stays in sync automatically during video playback',
    'chromascii --no-audio for a silent render',
    'paste a direct image or video link, not just YouTube',
    'chromascii --fps 24 to override the playback frame rate',
    'resize your terminal any time — the render adapts on the fly',
    'face censor works in the virtual cam too, not just the terminal',
    'chromascii --detail braille packs the most detail per character',
    'chromascii -v to check your installed version',
]

_GREETINGS_POSIX = [
    'hey there!', 'welcome back!', 'good to see you again!', 'howdy!',
    'look who it is!', 'ready to make some art?', "hope you're having a good one.",
    "back for more ASCII, huh?", "let's get colorful.", 'systems purring. hi!',
    'oh, hello!', 'well hello there.',
]

_GREETINGS_POWERSHELL = [
    'session initialized.', 'terminal ready.', 'welcome.', 'standing by.',
    'all systems nominal.', 'connection established.', 'environment loaded.',
    'ready when you are.', 'initializing… done.', 'awaiting input.',
    'shell online.', 'good to see you.',
]

# each entry: (name, (line1, line2, line3))
_ANIMALS = {
    'cat':     (' /\\_/\\ ', '( o.o )', ' > ^ < '),
    'kitten':  (' /\\_/\\ ', '( -.- )', '  zzz  '),
    'dog':     (' / \\__ ', "(=' ^')", ' (")_(")'),
    'puppy':   (' / \\__ ', "(=' o')", ' (") (")'),
    'bunny':   (' (\\_/) ', "(='.'=)", 'o(")(")o'),
    'penguin': (' .--.  ', '(o  o) ', '/|  |\\ '),
    'fox':     (' /\\   /\\', '{  ..  }', ' \\  ~  /'),
    'owl':     (' ,___, ', '(o,o)  ', '/)__)  '),
    'bear':    ('  /^^^\\ ', ' (o   o)', '  \\ - / '),
    'koala':   (' (o.o)  ', '/)   (\\ ', '  "   "  '),
    'mouse':   (' ()  () ', ' (o.o)  ', 'c(")(")  '),
    'frog':    (' @..@   ', '(----)  ', '(>__<)   '),
    'chick':   ('  ,~.   ', ' (o.o)  ', ' (,,)(,,) '),
    'hamster': (' (\\_/) ', '( -.-)  ', ' (")(")  '),
}

_WHATEVER = {
    'coffee': ('   ___  ', '  (___) ', '   |_|  '),
    'star':   ('    *    ', '   ***   ', '  *****  '),
    'rocket': ('   /\\   ', '  /  \\  ', ' |----| '),
}

_ART_NAMES = list(_ANIMALS) + list(_WHATEVER)


_PALETTE_POSIX = [
    (249, 115, 22), (168, 85, 247), (34, 211, 238), (250, 204, 21),
    (244, 63, 94), (163, 230, 53), (56, 189, 248), (232, 121, 249),
]
_PALETTE_POWERSHELL = [
    (148, 163, 184), (100, 116, 139), (71, 85, 105), (96, 125, 139),
]

_MATRIX_CHARS = '01+*.:'
_FIELD_CHARS = ' .:-=+*#%@'
_FIELD_W, _FIELD_H = 26, 5


# ---------------------------------------------------------------------------
# Style profiles — this is what makes bash feel different from PowerShell
# ---------------------------------------------------------------------------

class _Style:
    def __init__(self, name, greetings, palette, char_delay, hold_seconds,
                 animal_weight, matrix_tones, plasma_tones):
        self.name = name
        self.greetings = greetings
        self.palette = palette
        self.char_delay = char_delay
        self.hold_seconds = hold_seconds
        self.animal_weight = animal_weight
        self.matrix_tones = matrix_tones
        self.plasma_tones = plasma_tones


_STYLE_POSIX = _Style(
    'posix', _GREETINGS_POSIX, _PALETTE_POSIX,
    char_delay=0.011, hold_seconds=1.0, animal_weight=0.75,
    matrix_tones=((20, 150, 70), (140, 255, 160)),
    plasma_tones=((236, 72, 153), (59, 130, 246)),
)
_STYLE_POWERSHELL = _Style(
    'powershell', _GREETINGS_POWERSHELL, _PALETTE_POWERSHELL,
    char_delay=0.020, hold_seconds=1.3, animal_weight=0.35,
    matrix_tones=((40, 55, 72), (110, 130, 150)),
    plasma_tones=((51, 65, 85), (100, 116, 139)),
)


def _style_for(shell):
    if shell in ('powershell', 'pwsh'):
        return _STYLE_POWERSHELL
    return _STYLE_POSIX


# ---------------------------------------------------------------------------
# Rendering helpers
# ---------------------------------------------------------------------------

def _color(rgb):
    r, g, b = rgb
    return f'\033[38;2;{r};{g};{b}m'


def _typewriter(text, delay, color):
    prefix = _color(color)
    for i in range(1, len(text) + 1):
        sys.stdout.write('\r  ' + prefix + text[:i] + _RESET)
        sys.stdout.flush()
        time.sleep(delay)
    sys.stdout.write('\n')
    sys.stdout.flush()


def _pick_art_lines(style):
    if random.random() < style.animal_weight:
        return random.choice(list(_ANIMALS.values()) + list(_WHATEVER.values()))
    return None


def _matrix_lines(style):
    lo, hi = style.matrix_tones
    lines = []
    for _ in range(_FIELD_H):
        row = []
        for _ in range(_FIELD_W):
            if random.random() < 0.35:
                rgb = hi if random.random() < 0.15 else lo
                row.append(f'{_color(rgb)}{random.choice(_MATRIX_CHARS)}')
            else:
                row.append(' ')
        lines.append(f'{"".join(row)}{_RESET}')
    return lines


def _plasma_lines(style):
    import math
    (r1, g1, b1), (r2, g2, b2) = style.plasma_tones
    phase = random.uniform(0, 6.28)
    lines = []
    for y in range(_FIELD_H):
        row = []
        for x in range(_FIELD_W):
            v = (math.sin(x * 0.35 + phase) + math.sin(y * 0.6 + phase * 1.3)
                 + math.sin((x + y) * 0.25 + phase * 0.7))
            v = (v + 3) / 6.0
            idx = min(len(_FIELD_CHARS) - 1, max(0, int(v * len(_FIELD_CHARS))))
            ch = _FIELD_CHARS[idx]
            if ch == ' ':
                row.append(' ')
                continue
            r = int(r1 + (r2 - r1) * v)
            g = int(g1 + (g2 - g1) * v)
            b = int(b1 + (b2 - b1) * v)
            row.append(f'{_color((r, g, b))}{ch}')
        lines.append(f'{"".join(row)}{_RESET}')
    return lines


def _art_block(style):
    animal = _pick_art_lines(style)
    if animal is not None:
        color = random.choice(style.palette)
        return [f'{_color(color)}{line}{_RESET}' for line in animal]
    return random.choice([_matrix_lines, _plasma_lines])(style)


# ---------------------------------------------------------------------------
# Entry points
# ---------------------------------------------------------------------------

def _should_run():
    if os.environ.get('CHROMASCII_NO_GREET'):
        return False
    if not sys.stdout.isatty():
        return False
    return True


def _run(shell):
    style = _style_for(shell)
    greeting = random.choice(style.greetings)
    tip = random.choice(_TIPS)
    accent = random.choice(style.palette)

    sys.stdout.write('\n')
    _typewriter(greeting, style.char_delay, accent)

    for line in _art_block(style):
        sys.stdout.write(f'  {line}\n')
    sys.stdout.write('\n')
    sys.stdout.flush()

    _typewriter(f'tip: {tip}', style.char_delay, (120, 120, 130))

    sys.stdout.write('\n')
    sys.stdout.flush()
    time.sleep(style.hold_seconds)


def greet(shell=None):
    """Prints a short (~2-3s) animated greeting, then returns. Silently does
    nothing when stdout isn't a real terminal or CHROMASCII_NO_GREET is set —
    a shell startup hook must never corrupt scripted output. Never reads
    stdin (see module docstring), and nothing here is allowed to hang or
    crash the calling shell, including on Ctrl+C mid-animation."""
    if not _should_run():
        return
    sys.stdout.write(_HIDE)
    sys.stdout.flush()
    try:
        _run(shell)
    except BaseException:
        pass
    finally:
        sys.stdout.write(_SHOW)
        sys.stdout.flush()
