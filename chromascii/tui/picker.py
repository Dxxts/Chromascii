from pathlib import Path

from rich.console import Console
from rich.text import Text
from rich.rule import Rule

from ..utils import getch, format_size
from . import theme

console = Console()

EXTS = {'.jpg', '.jpeg', '.png', '.gif', '.mp4', '.mov', '.avi', '.webm', '.bmp', '.webp'}
_IMG = {'.jpg', '.jpeg', '.png', '.bmp', '.webp'}
_VID = {'.mp4', '.mov', '.avi', '.webm'}


def _color(p, t):
    e = p.suffix.lower()
    if p.is_dir():   return f'bold {t.accent2}'
    if e in _IMG:    return t.success
    if e == '.gif':  return t.accent
    if e in _VID:    return t.warn
    return 'white'


def _icon(p):
    e = p.suffix.lower()
    if p.is_dir():   return '📁'
    if e in _IMG:    return '🖼 '
    return '🎞 '


def _meta(p):
    try:
        size = format_size(p.stat().st_size)
        e = p.suffix.lower()
        if e in _IMG:
            try:
                from PIL import Image
                w, h = Image.open(p).size
                return f'{size}  {w}×{h}'
            except Exception:
                return size
        if e in _VID:
            try:
                import cv2
                cap = cv2.VideoCapture(str(p))
                fps = cap.get(cv2.CAP_PROP_FPS) or 1
                frames = cap.get(cv2.CAP_PROP_FRAME_COUNT)
                w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                cap.release()
                secs = int(frames / fps)
                return f'{size}  {w}×{h}  {secs//60}:{secs%60:02d}'
            except Exception:
                return size
        if e == '.gif':
            try:
                from PIL import Image
                img = Image.open(p)
                w, h = img.size
                n = getattr(img, 'n_frames', 1)
                dur = img.info.get('duration', 100) * n / 1000
                return f'{size}  {w}×{h}  {dur:.1f}s'
            except Exception:
                return size
    except Exception:
        return ''
    return ''


def _build(cwd):
    items = ['..']
    try:
        for e in sorted(cwd.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())):
            if e.is_dir():
                items.append(e)
            elif e.is_file() and e.suffix.lower() in EXTS:
                items.append(e)
    except PermissionError:
        pass
    return items


def _draw(cwd, items, sel):
    console.clear()
    t = theme.current()

    console.print()
    console.print(f'  [bold {t.accent2}]chromascii[/]  [{t.muted}]›[/]  [white]open file[/]  [dim]{cwd}[/]')
    console.print(Rule(style=t.muted))
    console.print()

    for i, item in enumerate(items):
        is_sel = i == sel
        cursor = f'[bold {t.accent2}]› [/]' if is_sel else '  '

        if item == '..':
            line = Text.from_markup(
                f'  {cursor}[bold {t.accent2}]📁  ..[/]'
            )
            console.print(line)
            continue

        col = _color(item, t)
        icon = _icon(item)
        name = (item.name + '/') if item.is_dir() else item.name
        meta = '' if item.is_dir() else _meta(item)

        line = Text()
        line.append('  ')
        line.append_text(Text.from_markup(cursor))
        line.append(icon + '  ', f'bold {col}' if is_sel else col)
        line.append(f'{name:<32}', 'bold white' if is_sel else col)
        line.append(f'  {meta}', 'white' if is_sel else 'dim')
        console.print(line)

    console.print()
    console.print(Rule(style=t.muted))
    console.print('[dim]  ↑↓ navigate   ⏎ select   ⌫ go up   q cancel[/]')


def show_picker():
    cwd = Path.cwd()
    items = _build(cwd)
    sel = 0

    while True:
        _draw(cwd, items, sel)
        k = getch()

        if k in ('q', 'Q', '\x1b', '\x03'):
            return ''
        elif k == 'up':
            sel = (sel - 1) % max(len(items), 1)
        elif k == 'down':
            sel = (sel + 1) % max(len(items), 1)
        elif k == 'backspace':
            parent = cwd.parent
            if parent != cwd:
                cwd = parent
                items = _build(cwd)
                sel = 0
        elif k == '\n':
            if not items:
                continue
            choice = items[sel]
            if choice == '..':
                parent = cwd.parent
                if parent != cwd:
                    cwd = parent
                    items = _build(cwd)
                    sel = 0
            elif isinstance(choice, Path) and choice.is_dir():
                cwd = choice
                items = _build(cwd)
                sel = 0
            elif isinstance(choice, Path) and choice.is_file():
                return str(choice)
        elif k.isdigit():
            n = int(k) - 1
            if 0 <= n < len(items):
                sel = n
