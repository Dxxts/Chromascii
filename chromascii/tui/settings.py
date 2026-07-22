import os
from typing import Optional

from rich.console import Console
from rich.text import Text
from rich.rule import Rule

from ..utils import getch, detect_color_mode
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
        console.print('[dim]  ↑↓ navigate   ← → adjust   tab cycle   space toggle   ⏎ play   q back[/]')

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

    def run(self) -> Optional[dict]:
        while True:
            self._draw()
            k = getch()
            if k in ('q', 'Q', '\x1b', '\x03'): return None
            if k == '\n': return self._export()
            if k == 'up':    self.sel = (self.sel - 1) % len(_ROWS)
            elif k == 'down': self.sel = (self.sel + 1) % len(_ROWS)
            elif k in ('left', 'right'): self._adjust(k)
            elif k == '\t':  self._cycle()
            elif k == ' ':
                if _ROWS[self.sel] == 'loop': self.loop = not self.loop
                elif _ROWS[self.sel] == 'dither': self.dither = not self.dither

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
    _ROWS = ['fps', 'color', 'virtual_cam']

    def __init__(self):
        self.fps = 30
        self.colidx = 0 if detect_color_mode() == 'truecolor' else 1
        self.vcam = False
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

        labels = ['fps', 'color', 'virtual cam']
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

            console.print(line)

        console.print()
        console.print(Rule(style=MUTED))
        console.print('[dim]  ↑↓ navigate   ← → adjust   tab cycle   space toggle   ⏎ start   q back[/]')

    def run(self) -> Optional[dict]:
        n = len(self._ROWS)
        while True:
            self._draw()
            k = getch()
            if k in ('q', 'Q', '\x1b', '\x03'): return None
            if k == '\n':
                return {
                    'width': None,
                    'fps': self.fps,
                    'charset_str': CHARSETS['default'],
                    'color': COLOR_MODES[self.colidx],
                    'virtual_cam': self.vcam,
                }
            if k == 'up':    self.sel = (self.sel - 1) % n
            elif k == 'down': self.sel = (self.sel + 1) % n
            elif k in ('left', 'right'):
                if self._ROWS[self.sel] == 'fps':
                    delta = 1 if k == 'right' else -1
                    self.fps = max(1, min(60, self.fps + delta))
            elif k == '\t':
                if self._ROWS[self.sel] == 'color':
                    self.colidx = (self.colidx + 1) % len(COLOR_MODES)
            elif k == ' ':
                if self._ROWS[self.sel] == 'virtual_cam':
                    self.vcam = not self.vcam


def show_webcam_settings() -> Optional[dict]:
    return _WebcamSettings().run()
