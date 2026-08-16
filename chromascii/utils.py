import os
import sys
import shutil
import contextlib


def get_terminal_size():
    s = shutil.get_terminal_size((80, 24))
    return s.columns, s.lines


def detect_color_mode():
    c = os.environ.get('COLORTERM', '').lower()
    if c in ('truecolor', '24bit'):
        return 'truecolor'
    if os.environ.get('WT_SESSION') or os.environ.get('ConEmuANSI') == 'ON':
        return 'truecolor'
    t = os.environ.get('TERM', '')
    if '256color' in t or os.environ.get('TERM_PROGRAM') in ('iTerm.app', 'Hyper', 'vscode'):
        return '256'
    return 'truecolor'


def init_terminal():
    if sys.platform == 'win32':
        import ctypes
        ctypes.windll.kernel32.SetConsoleOutputCP(65001)
        h = ctypes.windll.kernel32.GetStdHandle(-11)
        m = ctypes.c_ulong()
        if ctypes.windll.kernel32.GetConsoleMode(h, ctypes.byref(m)):
            ctypes.windll.kernel32.SetConsoleMode(h, m.value | 0x0004)
        if hasattr(sys.stdout, 'reconfigure'):
            try:
                sys.stdout.reconfigure(encoding='utf-8', errors='replace')
            except Exception:
                pass
        if hasattr(sys.stderr, 'reconfigure'):
            try:
                sys.stderr.reconfigure(encoding='utf-8', errors='replace')
            except Exception:
                pass


@contextlib.contextmanager
def alt_screen():
    """Switches to the terminal's alternate screen buffer for the duration of
    the block, then restores the original screen exactly as it was — same
    trick vim/htop/less use so a redrawing TUI never leaves frame residue in
    the user's scrollback. Always restores on the way out, exceptions and
    Ctrl+C included, so the shell is never left stuck in the alt buffer."""
    sys.stdout.write('\033[?1049h')
    sys.stdout.flush()
    try:
        yield
    finally:
        sys.stdout.write('\033[?1049l')
        sys.stdout.flush()


def hide_cursor():
    sys.stdout.write('\033[?25l')
    sys.stdout.flush()


def show_cursor():
    sys.stdout.write('\033[?25h')
    sys.stdout.flush()


def getch():
    if sys.platform == 'win32':
        import msvcrt
        ch = msvcrt.getch()
        if ch in (b'\x00', b'\xe0'):
            ch2 = msvcrt.getch()
            return {
                b'H': 'up', b'P': 'down', b'K': 'left', b'M': 'right',
                b'G': 'home', b'O': 'end', b'I': 'pageup', b'Q': 'pagedown',
            }.get(ch2, 'special')
        if ch == b'\r':   return '\n'
        if ch in (b'\x08', b'\x7f'): return 'backspace'
        if ch == b'\x1b': return '\x1b'
        if ch == b'\t':   return '\t'
        if ch == b'\x03': return '\x03'
        try:
            return ch.decode('utf-8')
        except Exception:
            return ''
    else:
        import tty, termios, select
        fd = sys.stdin.fileno()
        old = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            ch = sys.stdin.read(1)
            if ch == '\x1b':
                r, _, _ = select.select([sys.stdin], [], [], 0.05)
                if r:
                    ch2 = sys.stdin.read(1)
                    if ch2 == '[':
                        ch3 = sys.stdin.read(1)
                        return {'A': 'up', 'B': 'down', 'C': 'right', 'D': 'left'}.get(ch3, 'special')
                return '\x1b'
            if ch in ('\r', '\n'): return '\n'
            if ch == '\x7f':       return 'backspace'
            if ch == '\x03':       return '\x03'
            return ch
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old)


def kbhit():
    if sys.platform == 'win32':
        import msvcrt
        return msvcrt.kbhit()
    else:
        import select
        r, _, _ = select.select([sys.stdin], [], [], 0)
        return bool(r)


def enable_mouse_mode():
    if sys.platform == 'win32':
        import ctypes
        ENABLE_MOUSE_INPUT = 0x0010
        ENABLE_EXTENDED_FLAGS = 0x0080
        ENABLE_QUICK_EDIT_MODE = 0x0040
        h = ctypes.windll.kernel32.GetStdHandle(-10)
        mode = ctypes.c_ulong()
        if not ctypes.windll.kernel32.GetConsoleMode(h, ctypes.byref(mode)):
            return None
        old = mode.value
        new = (old | ENABLE_MOUSE_INPUT | ENABLE_EXTENDED_FLAGS) & ~ENABLE_QUICK_EDIT_MODE
        ctypes.windll.kernel32.SetConsoleMode(h, new)
        return old
    sys.stdout.write('\033[?1000h')
    sys.stdout.flush()
    return True


def disable_mouse_mode(token):
    if sys.platform == 'win32':
        if token is None:
            return
        import ctypes
        h = ctypes.windll.kernel32.GetStdHandle(-10)
        ctypes.windll.kernel32.SetConsoleMode(h, token)
        return
    sys.stdout.write('\033[?1000l')
    sys.stdout.flush()


def _win32_input_structs():
    """Builds (once per call) the ctypes structures needed to decode raw
    Windows console input records — shared by poll_input_event() and
    read_input_events() so the layout is only defined in one place."""
    import ctypes
    from ctypes import wintypes

    class _COORD(ctypes.Structure):
        _fields_ = [('X', ctypes.c_short), ('Y', ctypes.c_short)]

    class _KEY_EVENT_RECORD(ctypes.Structure):
        _fields_ = [
            ('bKeyDown', wintypes.BOOL),
            ('wRepeatCount', wintypes.WORD),
            ('wVirtualKeyCode', wintypes.WORD),
            ('wVirtualScanCode', wintypes.WORD),
            ('uChar', wintypes.WCHAR),
            ('dwControlKeyState', wintypes.DWORD),
        ]

    class _MOUSE_EVENT_RECORD(ctypes.Structure):
        _fields_ = [
            ('dwMousePosition', _COORD),
            ('dwButtonState', wintypes.DWORD),
            ('dwControlKeyState', wintypes.DWORD),
            ('dwEventFlags', wintypes.DWORD),
        ]

    class _WINDOW_BUFFER_SIZE_RECORD(ctypes.Structure):
        _fields_ = [('dwSize', _COORD)]

    class _MENU_EVENT_RECORD(ctypes.Structure):
        _fields_ = [('dwCommandId', wintypes.UINT)]

    class _FOCUS_EVENT_RECORD(ctypes.Structure):
        _fields_ = [('bSetFocus', wintypes.BOOL)]

    class _EVENT_UNION(ctypes.Union):
        _fields_ = [
            ('KeyEvent', _KEY_EVENT_RECORD),
            ('MouseEvent', _MOUSE_EVENT_RECORD),
            ('WindowBufferSizeEvent', _WINDOW_BUFFER_SIZE_RECORD),
            ('MenuEvent', _MENU_EVENT_RECORD),
            ('FocusEvent', _FOCUS_EVENT_RECORD),
        ]

    class _INPUT_RECORD(ctypes.Structure):
        _fields_ = [('EventType', wintypes.WORD), ('Event', _EVENT_UNION)]

    return ctypes, wintypes, _INPUT_RECORD


def poll_input_event():
    if sys.platform != 'win32':
        return False

    ctypes, wintypes, _INPUT_RECORD = _win32_input_structs()
    KEY_EVENT = 0x0001
    MOUSE_EVENT = 0x0002

    kernel32 = ctypes.windll.kernel32
    h = kernel32.GetStdHandle(-10)

    count = wintypes.DWORD()
    if not kernel32.GetNumberOfConsoleInputEvents(h, ctypes.byref(count)) or count.value == 0:
        return False

    records = (_INPUT_RECORD * count.value)()
    read = wintypes.DWORD()
    if not kernel32.ReadConsoleInputW(h, records, count.value, ctypes.byref(read)):
        return False

    hit = False
    for i in range(read.value):
        rec = records[i]
        if rec.EventType == KEY_EVENT and rec.Event.KeyEvent.bKeyDown:
            hit = True
        elif rec.EventType == MOUSE_EVENT and rec.Event.MouseEvent.dwButtonState != 0 \
                and rec.Event.MouseEvent.dwEventFlags == 0:
            hit = True
    return hit


_VK_TOKENS = {
    0x26: 'up', 0x28: 'down', 0x25: 'left', 0x27: 'right',
    0x24: 'home', 0x23: 'end', 0x21: 'pageup', 0x22: 'pagedown',
}


def _decode_key_event(ke):
    """Converts a Windows KEY_EVENT_RECORD into the same token vocabulary
    getch() returns, so callers can share one set of key-handling branches
    regardless of which function produced the keypress."""
    vk = ke.wVirtualKeyCode
    if vk in _VK_TOKENS:
        return _VK_TOKENS[vk]
    if vk == 0x08:
        return 'backspace'
    if vk == 0x0D:
        return '\n'
    if vk == 0x1B:
        return '\x1b'
    if vk == 0x09:
        return '\t'
    ch = ke.uChar
    if ch and ch != '\x00':
        return ch
    return 'special'


def read_input_events(block=True):
    """Blocks for at least one console input event and returns a normalized
    list of events:
      {'type': 'key', 'key': <getch()-compatible token>}
      {'type': 'mouse', 'x': col0, 'y': row0, 'move': bool, 'click': bool}

    This is the single input source a screen should use once it wants mouse
    hover/click support — mixing it with getch()/kbhit() in the same screen
    would race for the same underlying console input queue. On non-Windows,
    where there's no cross-platform mouse event stream to decode, it falls
    back to a single blocking getch() wrapped as a key event; mouse events
    simply never occur there."""
    if sys.platform != 'win32':
        return [{'type': 'key', 'key': getch()}]

    ctypes, wintypes, _INPUT_RECORD = _win32_input_structs()
    KEY_EVENT = 0x0001
    MOUSE_EVENT = 0x0002
    MOUSE_MOVED = 0x0001

    kernel32 = ctypes.windll.kernel32
    h = kernel32.GetStdHandle(-10)

    if block:
        count = wintypes.DWORD()
        if kernel32.GetNumberOfConsoleInputEvents(h, ctypes.byref(count)) and count.value == 0:
            kernel32.WaitForSingleObject(h, 0xFFFFFFFF)

    count = wintypes.DWORD()
    if not kernel32.GetNumberOfConsoleInputEvents(h, ctypes.byref(count)) or count.value == 0:
        return []

    records = (_INPUT_RECORD * count.value)()
    read = wintypes.DWORD()
    if not kernel32.ReadConsoleInputW(h, records, count.value, ctypes.byref(read)):
        return []

    events = []
    for i in range(read.value):
        rec = records[i]
        if rec.EventType == KEY_EVENT:
            ke = rec.Event.KeyEvent
            if not ke.bKeyDown:
                continue
            events.append({'type': 'key', 'key': _decode_key_event(ke)})
        elif rec.EventType == MOUSE_EVENT:
            me = rec.Event.MouseEvent
            events.append({
                'type': 'mouse',
                'x': me.dwMousePosition.X,
                'y': me.dwMousePosition.Y,
                'move': bool(me.dwEventFlags & MOUSE_MOVED),
                'click': me.dwEventFlags == 0 and (me.dwButtonState & 0x0001) != 0,
            })
    return events


def format_time(s):
    s = max(0, int(s))
    return f'{s // 60:02d}:{s % 60:02d}'


def format_size(b):
    for u in ('B', 'KB', 'MB', 'GB'):
        if b < 1024:
            return f'{b:.1f} {u}'
        b /= 1024
    return f'{b:.1f} TB'


def is_quit_key(k):
    return k in ('q', 'Q', '\x1b', '\x03')


_CONFETTI_CHARS = '*+.oO@#%'
_CONFETTI_COLORS = ['#f87171', '#fbbf24', '#4ade80', '#22d3ee', '#8b5cf6', '#f472b6']


def confetti_burst(duration=0.35):
    import random
    import time as _time

    tw, th = get_terminal_size()
    t0 = _time.perf_counter()
    sys.stdout.write('\033[2J')
    while _time.perf_counter() - t0 < duration:
        buf = ['\033[H']
        for _y in range(th):
            parts = []
            for _x in range(tw):
                if random.random() < 0.06:
                    r, g, b = _hex_to_rgb(random.choice(_CONFETTI_COLORS))
                    ch = random.choice(_CONFETTI_CHARS)
                    parts.append(f'\033[38;2;{r};{g};{b}m{ch}')
                else:
                    parts.append(' ')
            buf.append(''.join(parts))
            buf.append('\033[0m\n')
        sys.stdout.write(''.join(buf))
        sys.stdout.flush()
        _time.sleep(0.05)


def _hex_to_rgb(h):
    h = h.lstrip('#')
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))
