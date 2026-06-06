import sys
import os
import time
import numpy as np

from ..utils import get_terminal_size, hide_cursor, show_cursor, kbhit, getch, is_quit_key, format_time
from .engine import render_frame, resize_for_terminal, calc_render_size, CHARSETS


def _hud(fname, cur, tot, fps, rw, rh, tw):
    from io import StringIO
    from rich.console import Console
    buf = StringIO()
    Console(file=buf, width=tw, highlight=False, markup=True).print(
        f"  [bold cyan]chromascii[/]  [dim]▶[/]  [white]{fname}[/]  "
        f"[dim]{format_time(cur)} / {format_time(tot)}[/]  "
        f"[yellow]{fps:.0f}fps[/]  [dim]{rw}×{rh}[/]  [bright_black]\\[q] stop[/]",
        end=''
    )
    return buf.getvalue()


def render_gif(path, settings):
    from PIL import Image, ImageSequence

    charset = settings.get('charset_str', CHARSETS['default'])
    color   = settings.get('color', 'truecolor')
    uw      = settings.get('width')
    do_loop = settings.get('loop', True)
    fname   = os.path.basename(path)

    gif = Image.open(path)
    frames, delays = [], []
    for f in ImageSequence.Iterator(gif):
        frames.append(np.asarray(f.convert('RGB')))
        delays.append(f.info.get('duration', 100) / 1000.0)

    gif_loop = gif.info.get('loop', 0)
    total    = sum(delays)

    hide_cursor()
    sys.stdout.write('\033[2J')
    try:
        it = 0
        while True:
            for i, (fa, delay) in enumerate(zip(frames, delays)):
                if kbhit() and is_quit_key(getch()):
                    return
                t0 = time.perf_counter()
                tw, th = get_terminal_size()
                rw, rh = calc_render_size(fa.shape[1], fa.shape[0], tw, th, uw)
                sys.stdout.write(render_frame(resize_for_terminal(fa, rw, rh), charset, color))
                sys.stdout.write(f'\033[{th};1H\033[2K')
                sys.stdout.write(_hud(fname, sum(delays[:i]), total, 1 / max(delay, 0.001), rw, rh, tw))
                sys.stdout.flush()
                elapsed = time.perf_counter() - t0
                if elapsed < delay:
                    time.sleep(delay - elapsed)
            it += 1
            if not do_loop:
                break
            if gif_loop != 0 and it >= gif_loop:
                break
        getch()
    finally:
        sys.stdout.write('\033[0m\n')
        show_cursor()


def render_video(path, settings):
    try:
        import cv2
    except ImportError:
        raise RuntimeError('opencv-python required: pip install opencv-python')

    if path.lower().endswith('.gif'):
        render_gif(path, settings)
        return

    charset = settings.get('charset_str', CHARSETS['default'])
    color   = settings.get('color', 'truecolor')
    uw      = settings.get('width')
    do_loop = settings.get('loop', False)
    fname   = os.path.basename(path)

    cap = cv2.VideoCapture(path)
    if not cap.isOpened():
        raise RuntimeError(f'Cannot open: {path}')

    native_fps   = cap.get(cv2.CAP_PROP_FPS) or 24.0
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    total_sec    = total_frames / native_fps
    fps          = float(settings.get('fps') or native_fps)
    fdur         = 1.0 / fps

    hide_cursor()
    sys.stdout.write('\033[2J')
    try:
        while True:
            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            while True:
                if kbhit() and is_quit_key(getch()):
                    return
                t0 = time.perf_counter()
                ret, bgr = cap.read()
                if not ret:
                    break

                rgb = bgr[:, :, ::-1]
                cur = cap.get(cv2.CAP_PROP_POS_MSEC) / 1000.0

                tw, th = get_terminal_size()
                rw, rh = calc_render_size(rgb.shape[1], rgb.shape[0], tw, th, uw)

                sys.stdout.write(render_frame(resize_for_terminal(rgb, rw, rh), charset, color))
                sys.stdout.write(f'\033[{th};1H\033[2K')
                sys.stdout.write(_hud(fname, cur, total_sec, fps, rw, rh, tw))
                sys.stdout.flush()

                elapsed = time.perf_counter() - t0
                if elapsed < fdur:
                    time.sleep(fdur - elapsed)

            if not do_loop:
                break
    finally:
        sys.stdout.write('\033[0m\n')
        show_cursor()
        cap.release()
