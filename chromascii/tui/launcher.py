import time
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.align import Align

from ..utils import getch

console = Console()

_PALETTE = [
    'bold magenta', 'bold bright_magenta', 'bold blue',
    'bold bright_blue', 'bold cyan', 'bold bright_cyan',
    'bold green', 'bold bright_green', 'bold yellow', 'bold bright_yellow',
]

_LETTERS = list('chromascii')


def _build_title(n=None):
    t = Text(justify='center')
    t.append('  ░▒▓  ', 'dim')
    for i, ch in enumerate(_LETTERS):
        if n is None or i < n:
            t.append(f' {ch} ', _PALETTE[i % len(_PALETTE)])
        else:
            t.append('   ', '')
    t.append('  ▓▒░  ', 'dim')
    return t


def _splash():
    for n in range(len(_LETTERS) + 1):
        console.clear()
        console.print()
        console.print()
        console.print(Align.center(_build_title(n)))
        if n == len(_LETTERS):
            console.print(Align.center(Text('turn anything into art', style='dim italic')))
        time.sleep(0.055)
    time.sleep(0.25)


def _draw(highlight=None):
    console.clear()

    inner = Text(justify='center')
    inner.append_text(_build_title())
    inner.append('\n')
    inner.append('turn anything into art', 'dim italic')

    console.print()
    console.print(Align.center(
        Panel(inner, border_style='bright_black', padding=(1, 6), expand=False)
    ))
    console.print()

    entries = [
        ('1', 'open file',  'pick an image, video or gif'),
        ('2', 'paste path', 'enter a file path manually'),
        ('3', 'use webcam', 'live ASCII from camera'),
    ]

    for key, label, hint in entries:
        sel = highlight == key
        line = Text()
        line.append('   ')
        if sel:
            line.append(f' {key} ', 'bold black on bright_cyan')
        else:
            line.append(f' {key} ', 'bold black on white')
        line.append(f'  {label:<14}', 'bold bright_cyan' if sel else 'cyan')
        line.append(hint, 'white' if sel else 'dim')
        console.print(line)

    console.print()
    console.print('   [dim] q  [/][bright_black]quit[/]')
    console.print()


def show_launcher(first_time=True):
    if first_time:
        _splash()

    last = None
    while True:
        _draw(last)
        k = getch()
        if k == '1':
            last = '1'
            _draw('1')
            time.sleep(0.08)
            return 'file'
        if k == '2':
            last = '2'
            _draw('2')
            time.sleep(0.08)
            return 'path'
        if k == '3':
            last = '3'
            _draw('3')
            time.sleep(0.08)
            return 'webcam'
        if k in ('q', 'Q', '\x1b', '\x03'):
            return 'quit'


def prompt_path():
    console.clear()
    console.print()
    console.print(Align.center(
        Panel(
            '[bold cyan]enter path[/]\n\n[dim]full path to an image, video, or gif[/]',
            border_style='cyan', padding=(1, 4), expand=False
        )
    ))
    console.print()
    try:
        p = console.input('  [bold bright_white]›[/] ').strip().strip('"').strip("'")
        return p
    except (EOFError, KeyboardInterrupt):
        return ''
