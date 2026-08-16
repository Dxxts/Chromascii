import sys
from pathlib import Path

from rich.console import Console
from rich.text import Text
from rich.rule import Rule

from ..utils import format_size, enable_mouse_mode, disable_mouse_mode, read_input_events
from . import theme

console = Console()

EXTS = {'.jpg', '.jpeg', '.png', '.gif', '.mp4', '.mov', '.avi', '.webm', '.bmp', '.webp'}
_IMG = {'.jpg', '.jpeg', '.png', '.bmp', '.webp'}
_VID = {'.mp4', '.mov', '.avi', '.webm'}

# 1-indexed terminal row of the first list item — must track the header
# print() calls in _draw() below, since mouse clicks are mapped by row.
_ITEMS_START_ROW = 5


def _index_for_row(y0, n_items):
    idx = (y0 + 1) - _ITEMS_START_ROW
    return idx if 0 <= idx < n_items else None


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
    console.print('[dim]  ↑↓ navigate   ⏎ select   ⌫ go up   click to open   q cancel[/]')


def show_picker():
    cwd = Path.cwd()
    items = _build(cwd)
    sel = 0
    mouse_token = enable_mouse_mode() if sys.platform == 'win32' else None

    try:
        return _run(cwd, items, sel)
    finally:
        disable_mouse_mode(mouse_token)


def _run(cwd, items, sel):
    dirty = True
    while True:
        if dirty:
            _draw(cwd, items, sel)
            dirty = False
        events = read_input_events(block=True)

        activate = False
        for ev in events:
            if ev['type'] == 'mouse':
                # Windows reports a move event on every cell the cursor
                # crosses — redraw only when it actually lands on a
                # different row, or hovering the list turns into a flicker.
                idx = _index_for_row(ev['y'], len(items))
                if idx is None:
                    continue
                if idx != sel:
                    sel = idx
                    dirty = True
                if ev['click']:
                    activate = True
                continue

            k = ev['key']
            if k in ('q', 'Q', '\x1b', '\x03'):
                return ''
            elif k == 'up':
                sel = (sel - 1) % max(len(items), 1)
                dirty = True
            elif k == 'down':
                sel = (sel + 1) % max(len(items), 1)
                dirty = True
            elif k == 'backspace':
                parent = cwd.parent
                if parent != cwd:
                    cwd = parent
                    items = _build(cwd)
                    sel = 0
                    dirty = True
            elif k == '\n':
                activate = True
            elif k.isdigit():
                n = int(k) - 1
                if 0 <= n < len(items):
                    sel = n
                    dirty = True

        if activate and items:
            choice = items[sel]
            if choice == '..':
                parent = cwd.parent
                if parent != cwd:
                    cwd = parent
                    items = _build(cwd)
                    sel = 0
                    dirty = True
            elif isinstance(choice, Path) and choice.is_dir():
                cwd = choice
                items = _build(cwd)
                sel = 0
                dirty = True
            elif isinstance(choice, Path) and choice.is_file():
                return str(choice)
