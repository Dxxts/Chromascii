import os
import sys
import shutil


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
