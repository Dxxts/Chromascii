import sys
import os
import time
import queue
import threading
import numpy as np

from ..utils import get_terminal_size, hide_cursor, show_cursor, kbhit, getch, is_quit_key, format_time
from .engine import (
    render_frame, render_frame_halfblock, render_frame_quadblock, render_frame_sextant,
    render_frame_braille, render_frame_octant,
    resize_for_terminal, calc_render_size, CHARSETS,
    resolve_detail_mode, char_aspect_for, note_chars,
    _BRAILLE_SSX, _BRAILLE_SSY, _OCTANT_SSX, _OCTANT_SSY,
)
from .audio import AudioPlayer, AUDIO_AVAILABLE
from .export import Exporter, cellgrid_to_image


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


def _render(rgb, settings, rw, rh, mode):
    charset = settings.get('charset_str', CHARSETS['default'])
    color = settings.get('color', 'truecolor')
    dither = settings.get('dither', False)
    note_chars(rw * rh)
    if mode == 'octant':
        resized = resize_for_terminal(rgb, rw * 2 * _OCTANT_SSX, rh * 4 * _OCTANT_SSY)
        return render_frame_octant(resized, color)
    if mode == 'braille':
        resized = resize_for_terminal(rgb, rw * 2 * _BRAILLE_SSX, rh * 4 * _BRAILLE_SSY)
        return render_frame_braille(resized, color)
    if mode == 'sextant':
        resized = resize_for_terminal(rgb, rw * 2, rh * 3)
        return render_frame_sextant(resized, color)
    if mode == 'quadblock':
        resized = resize_for_terminal(rgb, rw * 2, rh * 2)
        return render_frame_quadblock(resized, color)
    if mode == 'halfblock':
        resized = resize_for_terminal(rgb, rw, rh * 2)
        return render_frame_halfblock(resized, color)
    resized = resize_for_terminal(rgb, rw, rh)
    return render_frame(resized, charset, color, dither=dither)


class FrameClock:
    def __init__(self, audio_player=None, start_offset=0.0):
        self._t0 = time.perf_counter()
        self.audio_player = audio_player
        self.start_offset = start_offset

    def now(self):
        if self.audio_player is not None and self.audio_player.is_playing():
            return self.start_offset + self.audio_player.position()
        return self.start_offset + (time.perf_counter() - self._t0)


def render_gif(path, settings):
    from PIL import Image, ImageSequence

    uw = settings.get('width')
    do_loop = settings.get('loop', True)
    fname = os.path.basename(path)
    mode = resolve_detail_mode(settings)
    char_aspect = char_aspect_for(mode)

    gif = Image.open(path)
    frames, delays = [], []
    for f in ImageSequence.Iterator(gif):
        frames.append(np.asarray(f.convert('RGB')))
        delays.append(f.info.get('duration', 100) / 1000.0)

    gif_loop = gif.info.get('loop', 0)
    total = sum(delays)

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
                rw, rh = calc_render_size(fa.shape[1], fa.shape[0], tw, th, uw, char_aspect=char_aspect)
                sys.stdout.write(_render(fa, settings, rw, rh, mode))
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


def _put_blocking(q, item, stop_ev):
    while not stop_ev.is_set():
        try:
            q.put(item, timeout=0.2)
            return True
        except queue.Full:
            continue
    return False


def _decode_worker(cap, q, stop_ev):
    import cv2
    while not stop_ev.is_set():
        ret, bgr = cap.read()
        if not ret:
            _put_blocking(q, None, stop_ev)
            return
        pos = cap.get(cv2.CAP_PROP_POS_MSEC) / 1000.0
        if not _put_blocking(q, (pos, bgr), stop_ev):
            return


def render_video(path, settings):
    try:
        import cv2
    except ImportError:
        raise RuntimeError('opencv-python required: pip install opencv-python')

    if path.lower().endswith('.gif'):
        render_gif(path, settings)
        return

    uw = settings.get('width')
    do_loop = settings.get('loop', False)
    want_audio = settings.get('audio', True)
    export_path = settings.get('export')
    fname = os.path.basename(path)
    mode = resolve_detail_mode(settings)
    char_aspect = char_aspect_for(mode)

    cap = cv2.VideoCapture(path)
    if not cap.isOpened():
        raise RuntimeError(f'Cannot open: {path}')

    native_fps = cap.get(cv2.CAP_PROP_FPS) or 24.0
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    total_sec = total_frames / native_fps
    fps = float(settings.get('fps') or native_fps)
    fdur = 1.0 / fps

    audio = AudioPlayer(path) if (want_audio and AUDIO_AVAILABLE) else None
    exporter = None
    last_rendered_pos = 0.0

    hide_cursor()
    sys.stdout.write('\033[2J')
    try:
        while True:
            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            q = queue.Queue(maxsize=4)
            stop_ev = threading.Event()
            t = threading.Thread(target=_decode_worker, args=(cap, q, stop_ev), daemon=True)
            t.start()

            if audio is not None:
                audio.start()
            clock = FrameClock(audio if (audio and audio.is_playing()) else None)

            pending = None
            try:
                while True:
                    if kbhit():
                        k = getch()
                        if is_quit_key(k):
                            return
                        if k == ' ':
                            if audio is not None:
                                audio.stop()
                            paused_at = last_rendered_pos
                            while True:
                                if kbhit():
                                    k2 = getch()
                                    if is_quit_key(k2):
                                        return
                                    if k2 == ' ':
                                        break
                                time.sleep(0.05)
                            if audio is not None:
                                audio.start(start_pos=paused_at)
                            clock = FrameClock(audio if (audio and audio.is_playing()) else None, start_offset=paused_at)
                            continue

                    if pending is None:
                        item = q.get()
                        if item is None:
                            break
                        pending = item

                    target = clock.now()
                    while True:
                        pos, _bgr = pending
                        if pos >= target - fdur:
                            break
                        try:
                            nxt = q.get_nowait()
                        except queue.Empty:
                            break
                        if nxt is None:
                            pending = None
                            break
                        pending = nxt
                    if pending is None:
                        break

                    pos, bgr = pending
                    target = clock.now()
                    if pos > target + 0.001:
                        time.sleep(min(pos - target, fdur))
                        continue
                    pending = None
                    last_rendered_pos = pos

                    rgb = bgr[:, :, ::-1]
                    tw, th = get_terminal_size()
                    rw, rh = calc_render_size(rgb.shape[1], rgb.shape[0], tw, th, uw, char_aspect=char_aspect)

                    sys.stdout.write(_render(rgb, settings, rw, rh, mode))
                    sys.stdout.write(f'\033[{th};1H\033[2K')
                    sys.stdout.write(_hud(fname, pos, total_sec, fps, rw, rh, tw))
                    sys.stdout.flush()

                    if export_path:
                        if exporter is None:
                            exporter = Exporter(export_path, fps, (2560, 1440))
                        exporter.write(cellgrid_to_image(rgb, rw, rh, 2560, 1440))

            finally:
                stop_ev.set()
                try:
                    while True:
                        q.get_nowait()
                except queue.Empty:
                    pass
                t.join(timeout=1.0)
                if audio is not None:
                    audio.stop()

            if not do_loop:
                break
    finally:
        sys.stdout.write('\033[0m\n')
        show_cursor()
        cap.release()
        if exporter is not None:
            exporter.close()
            from ..tui.sound import play_chime
            play_chime('plink')
