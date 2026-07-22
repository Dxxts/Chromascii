import hashlib
import mimetypes
import os
import sys
import urllib.request
from pathlib import Path
from urllib.parse import urlparse


_DIRECT_EXTS = {'.jpg', '.jpeg', '.png', '.bmp', '.webp', '.gif', '.mp4', '.mov', '.avi', '.webm'}


def is_url(s):
    try:
        return urlparse(s).scheme in ('http', 'https')
    except Exception:
        return False


def _cache_dir():
    if sys.platform == 'win32':
        base = os.environ.get('LOCALAPPDATA') or os.path.expanduser('~')
        d = Path(base) / 'chromascii' / 'cache'
    else:
        base = os.environ.get('XDG_CACHE_HOME', os.path.expanduser('~/.cache'))
        d = Path(base) / 'chromascii'
    d.mkdir(parents=True, exist_ok=True)
    return d


def _cache_key(url):
    return hashlib.sha1(url.encode('utf-8')).hexdigest()


def _cached_file(key):
    matches = sorted(_cache_dir().glob(f'{key}.*'))
    return matches[0] if matches else None


def _direct_fetch(url, key, on_progress=None):
    parsed = urlparse(url)
    ext = os.path.splitext(parsed.path)[1].lower()

    if ext not in _DIRECT_EXTS:
        try:
            req = urllib.request.Request(url, method='HEAD', headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=10) as resp:
                ctype = resp.headers.get('Content-Type', '').split(';')[0].strip()
                guessed = mimetypes.guess_extension(ctype) if ctype else None
                if guessed:
                    ext = '.jpg' if guessed == '.jpe' else guessed
        except Exception:
            pass

    if ext not in _DIRECT_EXTS:
        return None

    dest = _cache_dir() / f'{key}{ext}'
    if on_progress:
        on_progress('downloading…')
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req, timeout=30) as resp, open(dest, 'wb') as f:
        while True:
            chunk = resp.read(65536)
            if not chunk:
                break
            f.write(chunk)
    return str(dest)


def _ytdlp_fetch(url, key, on_progress=None):
    try:
        import yt_dlp
    except ImportError:
        raise RuntimeError('yt-dlp required: pip install yt-dlp')

    opts = {
        'outtmpl': str(_cache_dir() / f'{key}.%(ext)s'),
        'format': 'best[ext=mp4]/best',
        'quiet': True,
        'no_warnings': True,
        'noplaylist': True,
        'noprogress': True,
    }
    if on_progress:
        def _hook(d):
            if d.get('status') == 'downloading':
                on_progress(f"downloading… {d.get('_percent_str', '').strip()}")
            elif d.get('status') == 'finished':
                on_progress('processing…')
        opts['progress_hooks'] = [_hook]

    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=True)
        path = ydl.prepare_filename(info)
        if not os.path.isfile(path):
            found = _cached_file(key)
            if found is None:
                raise RuntimeError(f'yt-dlp download finished but output file not found for {url}')
            path = str(found)

    return path


def resolve_source(path_or_url, on_progress=None):
    if not is_url(path_or_url):
        return path_or_url

    key = _cache_key(path_or_url)
    cached = _cached_file(key)
    if cached:
        return str(cached)

    direct = _direct_fetch(path_or_url, key, on_progress)
    if direct:
        return direct

    return _ytdlp_fetch(path_or_url, key, on_progress)
