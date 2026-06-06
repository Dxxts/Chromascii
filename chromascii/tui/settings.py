import os
from typing import Optional

from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.rule import Rule

from ..utils import getch, detect_color_mode
from ..renderer.engine import CHARSETS, CHARSET_LABELS, COLOR_MODES, CHARSET_NAMES

console = Console()

_CLABELS = {'truecolor': '24-bit ANSI', '256': '256-color xterm', 'mono': 'no color'}
_IMG = {'.jpg', '.jpeg', '.png', '.bmp', '.webp'}
_ROWS = ['width', 'fps', 'charset', 'color', 'loop']
_SLW = 26


def _mode(path):
    e = os.path.splitext(path)[1].lower()
    if e in _IMG:    return 'image'
    if e == '.gif':  return 'gif'
    return 'video'


def _fill(val, lo, hi, color='cyan'):
    ratio = (val - lo) / max(hi - lo, 1)
    n = max(0, min(_SLW, int(ratio * _SLW)))
    t = Text()
    t.append('█' * n,         f'bold {color}')
    t.append('░' * (_SLW - n), 'bright_black')
    return t


class SettingsPanel:
    def __init__(self, path):
        self.path    = path
        self.fname   = os.path.basename(path)
        self.mode    = _mode(path)
        self.width   = 80
        self.fps     = 24
        self.cidx    = 0
        self.colidx  = 0 if detect_color_mode() == 'truecolor' else 1
        self.loop    = True
        self.sel     = 0
        self.custstr = ''

    def _draw(self):
        console.clear()

        mode_str = {'image': '── image ──', 'gif': '── gif ──', 'video': '── video ──'}[self.mode]
        cname  = CHARSET_NAMES[self.cidx]
        cprev  = CHARSET_LABELS.get(cname, '')
        colname = COLOR_MODES[self.colidx]

        console.print(Panel(
            f'  [dim]file[/]    [white]{self.fname}[/]\n'
            f'  [dim]mode[/]    [dim]{mode_str}[/]',
            title='[bold magenta]chromascii[/]',
            border_style='bright_black',
            padding=(0, 2),
        ))
        console.print()

        rows = [
            ('width',   True),
            ('fps',     self.mode == 'video'),
            ('charset', True),
            ('color',   True),
            ('loop',    self.mode != 'image'),
        ]

        for i, (label, active) in enumerate(rows):
            sel = i == self.sel
            cursor = '[bold bright_cyan]▶[/]' if sel else ' '
            dim = not active

            line = Text()
            line.append_text(Text.from_markup(f'  {cursor} '))
            line.append(f'{label:<9}', 'bold cyan' if sel else ('dim' if dim else 'white'))
            line.append(' ')

            if label == 'width':
                if sel:
                    line.append_text(_fill(self.width, 20, 200, 'cyan'))
                else:
                    line.append_text(_fill(self.width, 20, 200, 'bright_black' if dim else 'cyan'))
                line.append(f'  {self.width} chars', 'white' if sel else ('dim' if dim else 'white'))
                line.append('  [dim]← →[/]' if sel else '', '')

            elif label == 'fps':
                if sel:
                    line.append_text(_fill(self.fps, 1, 60, 'yellow'))
                else:
                    line.append_text(_fill(self.fps, 1, 60, 'bright_black' if dim else 'yellow'))
                line.append(f'  {self.fps} fps', 'white' if sel else ('dim' if dim else 'white'))
                line.append('  [dim]← →[/]' if sel else '', '')

            elif label == 'charset':
                line.append(f'[dim]{cprev}[/]   ', '')
                line.append(cname, 'bright_cyan' if sel else ('dim' if dim else 'white'))
                if sel: line.append('  [dim]tab[/]', '')

            elif label == 'color':
                line.append(colname, 'bright_cyan' if sel else 'white')
                line.append(f'   [dim]{_CLABELS[colname]}[/]', '')
                if sel: line.append('  [dim]tab[/]', '')

            elif label == 'loop':
                if self.loop:
                    line.append('[bold green]on[/]', '')
                else:
                    line.append('[dim]off[/]', '')
                if sel: line.append('  [dim]space[/]', '')

            console.print(line)

        console.print()
        console.print(Rule(style='bright_black'))
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

    def _export(self):
        cname = CHARSET_NAMES[self.cidx]
        if cname == 'custom':
            if not self.custstr:
                console.print('\n  [cyan]custom charset:[/] ', end='')
                try:
                    self.custstr = input().strip() or CHARSETS['default']
                except (EOFError, KeyboardInterrupt):
                    self.custstr = CHARSETS['default']
            cs = self.custstr
        else:
            cs = CHARSETS.get(cname, CHARSETS['default'])

        return {
            'width':       self.width if self.mode != 'image' else None,
            'fps':         self.fps if self.mode == 'video' else None,
            'charset':     cname,
            'charset_str': cs,
            'color':       COLOR_MODES[self.colidx],
            'loop':        self.loop,
        }


def show_settings(path) -> Optional[dict]:
    return SettingsPanel(path).run()


class _WebcamSettings:
    _ROWS = ['color', 'virtual_cam']

    def __init__(self):
        self.colidx = 0 if detect_color_mode() == 'truecolor' else 1
        self.vcam   = False
        self.sel    = 0

    def _draw(self):
        from ..utils import get_terminal_size
        tw, th = get_terminal_size()
        console.clear()
        colname = COLOR_MODES[self.colidx]

        console.print(Panel(
            f'  [dim]mode[/]    [white]── webcam ──[/]\n'
            f'  [dim]size[/]    [dim]fills terminal  —  maximize window for best quality[/]',
            title='[bold magenta]chromascii[/]',
            border_style='bright_black', padding=(0, 2),
        ))
        console.print()

        labels = ['color', 'virtual cam']
        for i, label in enumerate(labels):
            sel    = i == self.sel
            cursor = '[bold bright_cyan]▶[/]' if sel else ' '
            line   = Text()
            line.append_text(Text.from_markup(f'  {cursor} '))
            line.append(f'{label:<13}', 'bold cyan' if sel else 'white')
            line.append(' ')

            if label == 'color':
                line.append(colname, 'bright_cyan' if sel else 'white')
                line.append(f'   [dim]{_CLABELS[colname]}[/]', '')
                if sel: line.append('  [dim]tab[/]', '')
            elif label == 'virtual cam':
                line.append('[bold green]on[/]' if self.vcam else '[dim]off[/]', '')
                if sel: line.append('  [dim]space[/]', '')

            console.print(line)

        console.print()
        console.print(Rule(style='bright_black'))
        console.print('[dim]  ↑↓ navigate   tab cycle   space toggle   ⏎ start   q back[/]')

    def run(self) -> Optional[dict]:
        while True:
            self._draw()
            k = getch()
            if k in ('q', 'Q', '\x1b', '\x03'): return None
            if k == '\n':
                return {
                    'width':       None,
                    'charset_str': CHARSETS['default'],
                    'color':       COLOR_MODES[self.colidx],
                    'virtual_cam': self.vcam,
                }
            if k == 'up':    self.sel = (self.sel - 1) % 2
            elif k == 'down': self.sel = (self.sel + 1) % 2
            elif k == '\t':
                if self._ROWS[self.sel] == 'color':
                    self.colidx = (self.colidx + 1) % len(COLOR_MODES)
            elif k == ' ':
                if self._ROWS[self.sel] == 'virtual_cam':
                    self.vcam = not self.vcam


def show_webcam_settings() -> Optional[dict]:
    return _WebcamSettings().run()
