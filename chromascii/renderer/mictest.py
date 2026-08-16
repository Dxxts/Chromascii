"""Mic Test — a just-for-fun live audio visualizer. No real purpose beyond
watching your voice bounce around the terminal: a log-spaced frequency
spectrum in one mode, a colored VU-style volume meter in the other."""

import sys
import time

import numpy as np

from ..utils import get_terminal_size, hide_cursor, show_cursor, kbhit, getch, is_quit_key

try:
    import sounddevice as sd
    MIC_AVAILABLE = True
except ImportError:
    MIC_AVAILABLE = False


_BLOCKSIZE = 1024
_DB_FLOOR = -60.0
_DB_CEIL = 0.0
_PARTIALS = ' ▁▂▃▄▅▆▇█'

_GREEN = (74, 222, 128)
_YELLOW = (250, 204, 21)
_ORANGE = (251, 146, 60)
_RED = (239, 68, 68)

_METER_WIDTH_CAP = 70
_PEAK_HOLD_SECONDS = 0.9


def _color(rgb):
    r, g, b = rgb
    return f'\033[38;2;{r};{g};{b}m'


_RESET = '\033[0m'


def _level_color(norm):
    if norm < 0.55:
        return _GREEN
    if norm < 0.75:
        return _YELLOW
    if norm < 0.9:
        return _ORANGE
    return _RED


def _db_norm(value_db):
    return max(0.0, min(1.0, (value_db - _DB_FLOOR) / (_DB_CEIL - _DB_FLOOR)))


def _rms_db(block):
    rms = float(np.sqrt(np.mean(np.square(block)) + 1e-12))
    return 20.0 * np.log10(rms + 1e-9)


def _spectrum_bars(block, n_bars, samplerate):
    n = len(block)
    window = np.hanning(n)
    spectrum = np.abs(np.fft.rfft(block * window))
    freqs = np.fft.rfftfreq(n, d=1.0 / samplerate)

    lo, hi = 40.0, min(8000.0, samplerate / 2.0 - 1.0)
    edges = np.geomspace(lo, max(hi, lo + 1.0), n_bars + 1)
    bars = np.zeros(n_bars)
    for i in range(n_bars):
        mask = (freqs >= edges[i]) & (freqs < edges[i + 1])
        if mask.any():
            bars[i] = spectrum[mask].max()

    db = 20.0 * np.log10(bars + 1e-6)
    return np.clip((db - _DB_FLOOR) / (_DB_CEIL - _DB_FLOOR), 0.0, 1.0)


def _draw_spectrum(norms, tw, th):
    rows = max(4, th - 3)
    grid = [[' '] * tw for _ in range(rows)]
    colors = [[None] * tw for _ in range(rows)]

    for x in range(min(tw, len(norms))):
        height = norms[x] * rows
        full = int(height)
        frac = height - full
        col = _level_color(norms[x])
        for y in range(full):
            row = rows - 1 - y
            grid[row][x] = '█'
            colors[row][x] = col
        if full < rows and frac > 0.05:
            row = rows - 1 - full
            idx = min(len(_PARTIALS) - 1, int(frac * (len(_PARTIALS) - 1)) + 1)
            grid[row][x] = _PARTIALS[idx]
            colors[row][x] = col

    buf = ['\033[H']
    for y in range(rows):
        parts = []
        last_col = None
        for x in range(tw):
            ch = grid[y][x]
            col = colors[y][x]
            if ch == ' ':
                if last_col is not None:
                    parts.append(_RESET)
                    last_col = None
                parts.append(' ')
            else:
                if col != last_col:
                    parts.append(_color(col))
                    last_col = col
                parts.append(ch)
        if last_col is not None:
            parts.append(_RESET)
        buf.append(''.join(parts) + '\n')
    return ''.join(buf)


def _draw_volume(db, peak_db, tw, th):
    rows = max(4, th - 3)
    norm = _db_norm(db)
    peak_norm = _db_norm(peak_db)
    width = min(_METER_WIDTH_CAP, tw - 4)
    filled = int(norm * width)
    peak_col = min(width - 1, int(peak_norm * width))

    lines = []
    lines.append('')
    label = f'{db:6.1f} dB'
    lines.append(f'  {label}')
    lines.append('')

    bar = []
    for i in range(width):
        seg_norm = (i + 1) / width
        col = _level_color(seg_norm)
        if i < filled:
            bar.append(f'{_color(col)}█{_RESET}')
        elif i == peak_col:
            bar.append(f'{_color(col)}▏{_RESET}')
        else:
            bar.append('\033[2m·\033[0m')
    lines.append('  ' + ''.join(bar))
    lines.append('')

    if norm >= 0.97:
        lines.append(f'  {_color(_RED)}⚠ CLIPPING{_RESET}')
    elif norm >= 0.9:
        lines.append(f'  {_color(_RED)}loud{_RESET}')
    elif norm >= 0.75:
        lines.append(f'  {_color(_ORANGE)}getting loud{_RESET}')
    elif norm >= 0.55:
        lines.append(f'  {_color(_YELLOW)}moderate{_RESET}')
    elif norm > 0.05:
        lines.append(f'  {_color(_GREEN)}quiet{_RESET}')
    else:
        lines.append('  \033[2msilence\033[0m')

    pad = rows - len(lines)
    if pad > 0:
        lines += [''] * pad
    return '\033[H' + '\n'.join(lines[:rows]) + '\n'


def _hud(mode, device_name, tw):
    mode_label = 'frequency spectrum' if mode == 'spectrum' else 'volume meter'
    return (f'  \033[1;36mchromascii\033[0m mic test  '
            f'\033[2m{device_name}\033[0m  '
            f'\033[1m{mode_label}\033[0m  '
            f'\033[2m[m] switch mode   [q] stop\033[0m')


def run_mic_test():
    if not MIC_AVAILABLE:
        raise RuntimeError('sounddevice required: pip install chromascii[audio]')

    latest = [None]

    def _callback(indata, frames, time_info, status):
        latest[0] = indata[:, 0].copy()

    try:
        device_name = sd.query_devices(kind='input')['name']
    except Exception:
        device_name = 'default microphone'

    stream = sd.InputStream(channels=1, blocksize=_BLOCKSIZE, dtype='float32', callback=_callback)

    mode = 'spectrum'
    peak_db = _DB_FLOOR
    last_peak_t = 0.0

    hide_cursor()
    sys.stdout.write('\033[2J')

    try:
        stream.start()
        samplerate = stream.samplerate

        while True:
            if kbhit():
                k = getch()
                if is_quit_key(k):
                    break
                if k in ('m', 'M'):
                    mode = 'volume' if mode == 'spectrum' else 'spectrum'
                    sys.stdout.write('\033[2J')

            tw, th = get_terminal_size()
            block = latest[0]

            if block is None:
                sys.stdout.write('\033[Hlistening…')
                sys.stdout.flush()
                time.sleep(0.05)
                continue

            if mode == 'spectrum':
                n_bars = max(8, min(tw, 120))
                norms = _spectrum_bars(block, n_bars, samplerate)
                frame = _draw_spectrum(norms, tw, th)
            else:
                now = time.perf_counter()
                db = _rms_db(block)
                if db >= peak_db or (now - last_peak_t) > _PEAK_HOLD_SECONDS:
                    peak_db = db
                    last_peak_t = now
                frame = _draw_volume(db, peak_db, tw, th)

            sys.stdout.write(frame)
            sys.stdout.write(f'\033[{th};1H\033[2K{_hud(mode, device_name, tw)}')
            sys.stdout.flush()
            time.sleep(0.03)
    finally:
        try:
            stream.stop()
            stream.close()
        except Exception:
            pass
        sys.stdout.write('\033[0m\n')
        show_cursor()
