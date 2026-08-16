"""Installs/removes a one-line hook in the user's shell startup files so a
new interactive terminal prints a random chromascii greeting (see greet.py).

Only touches profiles for shells actually found on PATH, and only ever adds
or removes the single marked block below — never anything else in the file.
"""

import os
import shutil
import subprocess
import sys


_MARK_BEGIN = '# >>> chromascii greet >>>'
_MARK_END = '# <<< chromascii greet <<<'

_BLOCKS = {
    'powershell': (
        f'{_MARK_BEGIN}\n'
        'if (Get-Command chromascii -ErrorAction SilentlyContinue) { chromascii --greet --shell powershell }\n'
        f'{_MARK_END}\n'
    ),
    'bash': (
        f'{_MARK_BEGIN}\n'
        'if command -v chromascii >/dev/null 2>&1; then chromascii --greet --shell bash; fi\n'
        f'{_MARK_END}\n'
    ),
}
_BLOCKS['pwsh'] = _BLOCKS['powershell'].replace('--shell powershell', '--shell pwsh')
_BLOCKS['zsh'] = _BLOCKS['bash'].replace('--shell bash', '--shell zsh')


def _which(cmd):
    return shutil.which(cmd) is not None


def _query_powershell_profile(exe):
    if not _which(exe):
        return None
    try:
        r = subprocess.run(
            [exe, '-NoProfile', '-Command', '$PROFILE'],
            capture_output=True, text=True, timeout=8,
            creationflags=0x08000000 if sys.platform == 'win32' else 0,
        )
        p = r.stdout.strip()
        return p or None
    except Exception:
        return None


def targets():
    """Returns [(shell_name, profile_path), ...] for every shell found on PATH."""
    out = []
    seen_paths = set()
    for exe in ('powershell', 'pwsh'):
        p = _query_powershell_profile(exe)
        if p and p not in seen_paths:
            out.append((exe, p))
            seen_paths.add(p)
    home = os.path.expanduser('~')
    if _which('bash'):
        out.append(('bash', os.path.join(home, '.bashrc')))
    if _which('zsh'):
        out.append(('zsh', os.path.join(home, '.zshrc')))
    return out


def _read(path):
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        return ''


def _write(path, text):
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(text)


def _install_one(shell, path):
    text = _read(path)
    if _MARK_BEGIN in text:
        return 'already-installed'
    block = _BLOCKS[shell]
    new_text = text
    if new_text and not new_text.endswith('\n'):
        new_text += '\n'
    if new_text:
        new_text += '\n'
    new_text += block
    _write(path, new_text)
    return 'installed'


def _uninstall_one(shell, path):
    if not os.path.isfile(path):
        return 'not-found'
    text = _read(path)
    if _MARK_BEGIN not in text:
        return 'no-hook'
    out_lines = []
    skipping = False
    for line in text.splitlines(keepends=True):
        stripped = line.strip()
        if stripped == _MARK_BEGIN:
            skipping = True
            continue
        if stripped == _MARK_END:
            skipping = False
            continue
        if not skipping:
            out_lines.append(line)
    new_text = ''.join(out_lines)
    while new_text.endswith('\n\n\n'):
        new_text = new_text[:-1]
    _write(path, new_text)
    return 'removed'


def status():
    """Returns [(shell, path, installed_bool), ...] for every detected shell,
    without modifying anything."""
    return [(shell, path, _MARK_BEGIN in _read(path)) for shell, path in targets()]


def install():
    """Adds the greet hook to every detected shell profile. Returns
    [(shell, path, status), ...] — status is 'installed' or 'already-installed',
    or 'error' with the exception message swapped in for path's counterpart."""
    results = []
    for shell, path in targets():
        try:
            status = _install_one(shell, path)
        except Exception as e:
            status = f'error: {e}'
        results.append((shell, path, status))
    return results


def uninstall():
    results = []
    for shell, path in targets():
        try:
            status = _uninstall_one(shell, path)
        except Exception as e:
            status = f'error: {e}'
        results.append((shell, path, status))
    return results
