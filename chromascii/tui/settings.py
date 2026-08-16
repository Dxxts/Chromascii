import os
import sys
from typing import Optional

from rich.console import Console
from rich.text import Text
from rich.rule import Rule

from ..utils import detect_color_mode, enable_mouse_mode, disable_mouse_mode, read_input_events
from ..renderer.engine import CHARSETS, CHARSET_LABELS, COLOR_MODES, CHARSET_NAMES, DETAIL_MODES
from . import theme

console = Console()

_CLABELS = {'truecolor': '24-bit ANSI', '256': '256-color xterm', 'mono': 'no color'}
_DLABELS = {
    'sextant': 'sextant blocks, 2×3 subpixels',
    'octant': 'octant blocks, 2×4 subpixels, supersampled (sharpest)',
    'braille': 'braille dots, 8 subpixels, supersampled (stippled look)',
    'quadblock': 'quadrant blocks, 2×2 subpixels',
    'halfblock': 'half blocks, 2x vertical res',
    'ascii': 'classic charset look',
}
_IMG = {'.jpg', '.jpeg', '.png', '.bmp', '.webp'}
_ROWS = ['width', 'fps', 'charset', 'color', 'detail', 'dither', 'loop']
_SLW = 26


def _mode(path):
    e = os.path.splitext(path)[1].lower()
    if e in _IMG:    return 'image'
    if e == '.gif':  return 'gif'
    return 'video'


def _md(line, markup):
    line.append_text(Text.from_markup(markup))


def _fill(val, lo, hi, color='cyan'):
    ratio = (val - lo) / max(hi - lo, 1)
    n = max(0, min(_SLW, int(ratio * _SLW)))
    t = Text()
    t.append('█' * n, f'bold {color}')
    t.append('░' * (_SLW - n), 'bright_black')
    return t


class SettingsPanel:
    # 1-indexed terminal row of the first settings row — must track the
    # header print() calls in _draw() below, since mouse clicks map by row.
    _ROWS_START_ROW = 5

    def __init__(self, path):
        self.path = path
        self.fname = os.path.basename(path)
        self.mode = _mode(path)
        self.width = 80
        self.fps = 24
        self.cidx = 0
        self.colidx = 0 if detect_color_mode() == 'truecolor' else 1
        self.didx = 0
        self.dither = False
        self.loop = True
        self.sel = 0
        self.custstr = ''

    def _draw(self):
        console.clear()
        t = theme.current()
        ACCENT2, MUTED, SUCCESS, WARN = t.accent2, t.muted, t.success, t.warn

        mode_str = {'image': 'image', 'gif': 'gif', 'video': 'video'}[self.mode]
        cname = CHARSET_NAMES[self.cidx]
        cprev = CHARSET_LABELS.get(cname, '')
        colname = COLOR_MODES[self.colidx]

        console.print()
        console.print(f'  [bold {ACCENT2}]chromascii[/]  [{MUTED}]›[/]  [white]{self.fname}[/]  [dim]{mode_str}[/]')
        console.print(Rule(style=MUTED))
        console.print()

        rows = [
            ('width', True),
            ('fps', self.mode == 'video'),
            ('charset', True),
            ('color', True),
            ('detail', self.mode != 'image'),
            ('dither', self.mode != 'image'),
            ('loop', self.mode != 'image'),
        ]

        for i, (label, active) in enumerate(rows):
            sel = i == self.sel
            cursor = f'[bold {ACCENT2}]›[/]' if sel else ' '
            dim = not active

            line = Text()
            line.append_text(Text.from_markup(f'  {cursor} '))
            line.append(f'{label:<9}', f'bold {ACCENT2}' if sel else ('dim' if dim else 'white'))
            line.append(' ')

            if label == 'width':
                if sel:
                    line.append_text(_fill(self.width, 20, 200, ACCENT2))
                else:
                    line.append_text(_fill(self.width, 20, 200, MUTED if dim else ACCENT2))
                line.append(f'  {self.width} chars', 'white' if sel else ('dim' if dim else 'white'))
                if sel: _md(line, '  [dim]← →[/]')

            elif label == 'fps':
                if sel:
                    line.append_text(_fill(self.fps, 1, 60, WARN))
                else:
                    line.append_text(_fill(self.fps, 1, 60, MUTED if dim else WARN))
                line.append(f'  {self.fps} fps', 'white' if sel else ('dim' if dim else 'white'))
                if sel: _md(line, '  [dim]← →[/]')

            elif label == 'charset':
                _md(line, f'[dim]{cprev}[/]   ')
                line.append(cname, f'bold {ACCENT2}' if sel else ('dim' if dim else 'white'))
                if sel: _md(line, '  [dim]tab[/]')

            elif label == 'color':
                line.append(colname, f'bold {ACCENT2}' if sel else 'white')
                _md(line, f'   [dim]{_CLABELS[colname]}[/]')
                if sel: _md(line, '  [dim]tab[/]')

            elif label == 'detail':
                dname = DETAIL_MODES[self.didx]
                line.append(dname, f'bold {ACCENT2}' if sel else ('dim' if dim else 'white'))
                _md(line, f'   [dim]{_DLABELS[dname]}[/]')
                if sel: _md(line, '  [dim]tab[/]')

            elif label == 'dither':
                if self.dither:
                    _md(line, f'[bold {SUCCESS}]on[/]')
                else:
                    _md(line, '[dim]off[/]')
                if sel: _md(line, '  [dim]space[/]')

            elif label == 'loop':
                if self.loop:
                    _md(line, f'[bold {SUCCESS}]on[/]')
                else:
                    _md(line, '[dim]off[/]')
                if sel: _md(line, '  [dim]space[/]')

            console.print(line)

        console.print()
        console.print(Rule(style=MUTED))
        console.print('[dim]  ↑↓ navigate   ← → adjust   tab/click cycle   space/click toggle   ⏎ play   q back[/]')

    def _adjust(self, d):
        delta = 1 if d == 'right' else -1
        row = _ROWS[self.sel]
        if row == 'width':
            self.width = max(20, min(200, self.width + delta * 5))
        elif row == 'fps':
            self.fps = max(1, min(60, self.fps + delta))

    def _cycle(self):
        row = _ROWS[self.sel]
        if row == 'charset':
            self.cidx = (self.cidx + 1) % len(CHARSET_NAMES)
        elif row == 'color':
            self.colidx = (self.colidx + 1) % len(COLOR_MODES)
        elif row == 'detail':
            self.didx = (self.didx + 1) % len(DETAIL_MODES)

    def _toggle(self):
        row = _ROWS[self.sel]
        if row == 'loop':
            self.loop = not self.loop
        elif row == 'dither':
            self.dither = not self.dither

    def _row_for_y(self, y0):
        idx = (y0 + 1) - self._ROWS_START_ROW
        return idx if 0 <= idx < len(_ROWS) else None

    def run(self) -> Optional[dict]:
        mouse_token = enable_mouse_mode() if sys.platform == 'win32' else None
        dirty = True
        try:
            while True:
                if dirty:
                    self._draw()
                    dirty = False
                events = read_input_events(block=True)

                for ev in events:
                    if ev['type'] == 'mouse':
                        # Windows reports a move event on every cell the
                        # cursor crosses — redraw only on an actual row
                        # change, or hovering the list turns into a flicker.
                        idx = self._row_for_y(ev['y'])
                        if idx is None:
                            continue
                        if idx != self.sel:
                            self.sel = idx
                            dirty = True
                        if ev['click']:
                            self._cycle()
                            self._toggle()
                            dirty = True
                        continue

                    k = ev['key']
                    if k in ('q', 'Q', '\x1b', '\x03'): return None
                    if k == '\n': return self._export()
                    dirty = True
                    if k == 'up':    self.sel = (self.sel - 1) % len(_ROWS)
                    elif k == 'down': self.sel = (self.sel + 1) % len(_ROWS)
                    elif k in ('left', 'right'): self._adjust(k)
                    elif k == '\t':  self._cycle()
                    elif k == ' ':   self._toggle()
        finally:
            disable_mouse_mode(mouse_token)

    def _export(self):
        cname = CHARSET_NAMES[self.cidx]
        if cname == 'custom':
            if not self.custstr:
                console.print(f'\n  [{theme.current().accent2}]custom charset:[/] ', end='')
                try:
                    self.custstr = input().strip() or CHARSETS['default']
                except (EOFError, KeyboardInterrupt):
                    self.custstr = CHARSETS['default']
            cs = self.custstr
        else:
            cs = CHARSETS.get(cname, CHARSETS['default'])

        return {
            'width': self.width if self.mode != 'image' else None,
            'fps': self.fps if self.mode == 'video' else None,
            'charset': cname,
            'charset_str': cs,
            'color': COLOR_MODES[self.colidx],
            'detail': DETAIL_MODES[self.didx],
            'dither': self.dither,
            'loop': self.loop,
        }


def show_settings(path) -> Optional[dict]:
    return SettingsPanel(path).run()


class _WebcamSettings:
    _ROWS = ['fps', 'color', 'virtual_cam', 'face_censor', 'face_style']
    # 1-indexed terminal row of the first settings row — must track the
    # header print() calls in _draw() below, since mouse clicks map by row.
    _ROWS_START_ROW = 5

    def __init__(self):
        from ..renderer.face import load_calibration, FACE_STYLES
        self.fps = 30
        self.colidx = 0 if detect_color_mode() == 'truecolor' else 1
        self.vcam = False
        self.face_censor = False
        self.face_styles = FACE_STYLES
        self.face_style_idx = 0
        self.calibrated = load_calibration().get('calibrated', False)
        self.sel = 0

    def _draw(self):
        from ..utils import get_terminal_size
        tw, th = get_terminal_size()
        console.clear()
        t = theme.current()
        ACCENT2, MUTED, SUCCESS, WARN = t.accent2, t.muted, t.success, t.warn
        colname = COLOR_MODES[self.colidx]

        console.print()
        console.print(f'  [bold {ACCENT2}]chromascii[/]  [{MUTED}]›[/]  [white]webcam[/]  '
                       f'[dim]fills terminal — maximize window for best quality[/]')
        console.print(Rule(style=MUTED))
        console.print()

        labels = ['fps', 'color', 'virtual cam', 'face censor', 'face style']
        for i, label in enumerate(labels):
            sel = i == self.sel
            cursor = f'[bold {ACCENT2}]›[/]' if sel else ' '
            line = Text()
            line.append_text(Text.from_markup(f'  {cursor} '))
            line.append(f'{label:<13}', f'bold {ACCENT2}' if sel else 'white')
            line.append(' ')

            if label == 'fps':
                line.append_text(_fill(self.fps, 1, 60, WARN))
                line.append(f'  {self.fps} fps', 'white')
                if sel: _md(line, '  [dim]← →[/]')
            elif label == 'color':
                line.append(colname, f'bold {ACCENT2}' if sel else 'white')
                _md(line, f'   [dim]{_CLABELS[colname]}[/]')
                if sel: _md(line, '  [dim]tab[/]')
            elif label == 'virtual cam':
                _md(line, f'[bold {SUCCESS}]on[/]' if self.vcam else '[dim]off[/]')
                if sel: _md(line, '  [dim]space[/]')
            elif label == 'face censor':
                _md(line, f'[bold {SUCCESS}]on[/]' if self.face_censor else '[dim]off[/]')
                calib_tag = f'[{SUCCESS}]calibrated[/]' if self.calibrated else f'[{WARN}]using default margins[/]'
                _md(line, f'   [dim]{calib_tag}[/]')
                if sel: _md(line, '  [dim]space  ·  c to (re)calibrate[/]')
            elif label == 'face style':
                style_name = self.face_styles[self.face_style_idx]
                line.append(style_name, f'bold {ACCENT2}' if sel else 'white')
                if sel: _md(line, '  [dim]tab[/]')

            console.print(line)

        console.print()
        console.print(Rule(style=MUTED))
        console.print('[dim]  ↑↓ navigate   ← → adjust   tab/click cycle   space/click toggle   c calibrate face   ⏎ start   q back[/]')

    def _row_for_y(self, y0):
        idx = (y0 + 1) - self._ROWS_START_ROW
        return idx if 0 <= idx < len(self._ROWS) else None

    def _cycle(self, row):
        if row == 'color':
            self.colidx = (self.colidx + 1) % len(COLOR_MODES)
        elif row == 'face_style':
            self.face_style_idx = (self.face_style_idx + 1) % len(self.face_styles)

    def _toggle(self, row):
        if row == 'virtual_cam':
            self.vcam = not self.vcam
        elif row == 'face_censor':
            self.face_censor = not self.face_censor

    def _activate(self, row):
        """A mouse click's equivalent of that row's tab-cycle / space-toggle
        keyboard shortcut, so clicking a setting acts on it directly instead
        of only moving the cursor there."""
        self._cycle(row)
        self._toggle(row)

    def run(self) -> Optional[dict]:
        n = len(self._ROWS)
        mouse_token = enable_mouse_mode() if sys.platform == 'win32' else None
        dirty = True
        try:
            while True:
                if dirty:
                    self._draw()
                    dirty = False
                events = read_input_events(block=True)

                for ev in events:
                    if ev['type'] == 'mouse':
                        # Windows reports a move event on every cell the
                        # cursor crosses — redraw only on an actual row
                        # change, or hovering the list turns into a flicker.
                        idx = self._row_for_y(ev['y'])
                        if idx is None:
                            continue
                        if idx != self.sel:
                            self.sel = idx
                            dirty = True
                        if ev['click']:
                            self._activate(self._ROWS[idx])
                            dirty = True
                        continue

                    k = ev['key']
                    if k in ('q', 'Q', '\x1b', '\x03'):
                        return None
                    if k == '\n':
                        return {
                            'width': None,
                            'fps': self.fps,
                            'charset_str': CHARSETS['default'],
                            'color': COLOR_MODES[self.colidx],
                            'virtual_cam': self.vcam,
                            'face_censor': self.face_censor,
                            'face_style': self.face_styles[self.face_style_idx],
                        }
                    dirty = True
                    if k == 'up':    self.sel = (self.sel - 1) % n
                    elif k == 'down': self.sel = (self.sel + 1) % n
                    elif k in ('left', 'right'):
                        if self._ROWS[self.sel] == 'fps':
                            delta = 1 if k == 'right' else -1
                            self.fps = max(1, min(60, self.fps + delta))
                    elif k == '\t':
                        self._cycle(self._ROWS[self.sel])
                    elif k == ' ':
                        self._toggle(self._ROWS[self.sel])
                    elif k in ('c', 'C'):
                        from ..renderer.face import run_calibration
                        margins = run_calibration()
                        if margins is not None:
                            self.calibrated = True
                            self.face_censor = True
        finally:
            disable_mouse_mode(mouse_token)


def show_webcam_settings() -> Optional[dict]:
    return _WebcamSettings().run()
