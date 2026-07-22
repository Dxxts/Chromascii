import sys
import time
import random
import threading
import collections

from ..utils import get_terminal_size, hide_cursor, show_cursor, kbhit, getch, is_quit_key, confetti_burst
from .engine import (
    render_frame, render_frame_halfblock, render_frame_quadblock, render_frame_sextant,
    render_frame_braille, render_frame_octant,
    resize_for_terminal, calc_render_size, CHARSETS,
    resolve_detail_mode, char_aspect_for, note_chars,
    _BRAILLE_SSX, _BRAILLE_SSY, _OCTANT_SSX, _OCTANT_SSY,
)
from .export import cellgrid_to_image


_NICKNAME_CHANCE = 1 / 6
_NICKNAMES = [
    'looking good today',
    'definitely a real camera',
    'Camera McCameraface',
    'the all-seeing eye',
    'Definitely Not A Robot Cam',
    'main character energy',
    'camera of the year (probably)',
    'your best angle, guaranteed',
    'trust me, this is a camera',
    'high definition, low expectations',
]


def _fetch_cam_name(idx, out):
    if sys.platform == 'win32':
        try:
            import subprocess
            r = subprocess.run(
                ['powershell', '-Command',
                 f'(Get-PnpDevice -Class Camera -Status OK)[{idx}].FriendlyName'],
                capture_output=True, text=True, timeout=5,
                creationflags=0x08000000,
            )
            name = r.stdout.strip()
            if name and 2 < len(name) < 80 and '\n' not in name:
                out[0] = name
                return
        except Exception:
            pass
    out[0] = f'Camera {idx}'


def _hud_str(status, cam_name, rw, rh, tw, th, vcam_on=False):
    from io import StringIO
    from rich.console import Console
    buf = StringIO()
    c = Console(file=buf, width=tw, highlight=False, markup=True)
    vcam_tag = '  [bold magenta]◈ virt[/]' if vcam_on else ''
    size_hint = '' if rw >= 140 else f'  [dim](maximize terminal for ↑ quality)[/]'
    if status == 'off':
        c.print(
            f"  [bold cyan]chromascii[/]  [bold red]◉ Not Connected[/]"
            f"{vcam_tag}  [bright_black]retrying…  \\[q] stop[/]",
            end=''
        )
    else:
        c.print(
            f"  [bold cyan]chromascii[/]  [bold green]◉ Live[/]"
            f"[dim]: {cam_name}[/]{vcam_tag}  "
            f"[dim]{rw}×{rh}[/]{size_hint}  [bright_black]\\[q] stop[/]",
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


def render_webcam(settings):
    try:
        import cv2
    except ImportError:
        raise RuntimeError('opencv-python required: pip install opencv-python')

    uw = settings.get('width')
    mode = resolve_detail_mode(settings)
    char_aspect = char_aspect_for(mode)
    use_vcam = settings.get('virtual_cam', False)
    target_fps = float(settings.get('fps') or 30)
    fdur = 1.0 / max(target_fps, 1.0)
    cam_idx = 0

    if random.random() < _NICKNAME_CHANCE:
        cam_name = [random.choice(_NICKNAMES)]
    else:
        cam_name = [f'Camera {cam_idx}']
        name_t = threading.Thread(target=_fetch_cam_name, args=(cam_idx, cam_name), daemon=True)
        name_t.start()

    vcam = None
    vcam_w = 2560
    vcam_h = 1440
    vcam_cols = 160
    vcam_rows = 90

    if use_vcam:
        try:
            import pyvirtualcam
            vcam = pyvirtualcam.Camera(
                width=vcam_w, height=vcam_h, fps=min(target_fps, 60),
                fmt=pyvirtualcam.PixelFormat.RGB,
            )
            vcam.__enter__()
        except ImportError:
            from rich.console import Console
            Console().print(
                '[yellow]pyvirtualcam not installed — virtual cam disabled.[/]\n'
                '[dim]pip install pyvirtualcam   (also needs OBS Virtual Camera driver)[/]'
            )
            time.sleep(2)
            use_vcam = False
        except Exception as e:
            from rich.console import Console
            Console().print(f'[yellow]Virtual cam error: {e}[/]')
            time.sleep(2)
            use_vcam = False

    buf = collections.deque(maxlen=2)
    connected = threading.Event()
    stop_ev = threading.Event()

    def _capture():
        cap = None
        while not stop_ev.is_set():
            if cap is None or not cap.isOpened():
                connected.clear()
                cap = cv2.VideoCapture(cam_idx)
                if not cap.isOpened():
                    cap.release()
                    cap = None
                    time.sleep(0.5)
                    continue
                cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                cap.set(cv2.CAP_PROP_FPS, target_fps)
                connected.set()

            ret, bgr = cap.read()
            if ret:
                buf.append(bgr)
            else:
                connected.clear()
                cap.release()
                cap = None
                time.sleep(0.2)

        if cap:
            cap.release()

    t = threading.Thread(target=_capture, daemon=True)

    hide_cursor()
    confetti_burst()

    try:
        t.start()

        while True:
            t0 = time.perf_counter()

            if kbhit() and is_quit_key(getch()):
                break

            tw, th = get_terminal_size()
            is_live = connected.is_set()
            status = 'on' if is_live else 'off'
            vcam_live = use_vcam and vcam is not None

            if not buf:
                sys.stdout.write('\033[H')
                sys.stdout.write(_hud_str('off', cam_name[0], 0, 0, tw, th, vcam_live))
                sys.stdout.flush()
                time.sleep(0.12)
                continue

            bgr = buf[-1]
            rgb = bgr[:, :, ::-1]
            rw, rh = calc_render_size(rgb.shape[1], rgb.shape[0], tw, th, uw, char_aspect=char_aspect)

            sys.stdout.write(_render(rgb, settings, rw, rh, mode))
            sys.stdout.write(f'\033[{th};1H\033[2K')
            sys.stdout.write(_hud_str(status, cam_name[0], rw, rh, tw, th, vcam_live))
            sys.stdout.flush()

            if vcam_live and is_live:
                vf = cellgrid_to_image(rgb, vcam_cols, vcam_rows, vcam_w, vcam_h)
                vcam.send(vf)
                vcam.sleep_until_next_frame()

            elapsed = time.perf_counter() - t0
            if elapsed < fdur:
                time.sleep(fdur - elapsed)

    finally:
        stop_ev.set()
        sys.stdout.write('\033[0m\n')
        show_cursor()
        if vcam:
            try:
                vcam.__exit__(None, None, None)
            except Exception:
                pass
