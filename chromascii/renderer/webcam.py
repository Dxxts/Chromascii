import sys
import time
import threading
import collections

from ..utils import get_terminal_size, hide_cursor, show_cursor, kbhit, getch, is_quit_key
from .engine import render_frame, resize_for_terminal, calc_render_size, CHARSETS


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
    vcam_tag  = '  [bold magenta]◈ virt[/]' if vcam_on else ''
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


def _make_vcam_frame(rgb, cols, rows, out_w, out_h):
    import numpy as np
    from PIL import Image

    bw = max(1, out_w // cols)
    bh = max(1, out_h // rows)

    small = np.array(Image.fromarray(rgb).resize((cols, rows), Image.NEAREST))
    up    = small.repeat(bh, axis=0).repeat(bw, axis=1)
    out   = up[:out_h, :out_w].copy()

    out[::bh] = (out[::bh].astype('float32') * 0.30).astype('uint8')
    out[:, ::bw] = (out[:, ::bw].astype('float32') * 0.30).astype('uint8')

    return out.astype('uint8')


def render_webcam(settings):
    try:
        import cv2
    except ImportError:
        raise RuntimeError('opencv-python required: pip install opencv-python')

    charset  = settings.get('charset_str', CHARSETS['default'])
    color    = settings.get('color', 'truecolor')
    uw       = settings.get('width')
    use_vcam = settings.get('virtual_cam', False)
    cam_idx  = 0

    cam_name = [f'Camera {cam_idx}']
    name_t   = threading.Thread(target=_fetch_cam_name, args=(cam_idx, cam_name), daemon=True)
    name_t.start()

    vcam       = None
    vcam_w     = 1280
    vcam_h     = 720
    vcam_cols  = 80
    vcam_rows  = 45

    if use_vcam:
        try:
            import pyvirtualcam  # type: ignore
            vcam = pyvirtualcam.Camera(
                width=vcam_w, height=vcam_h, fps=20,
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

    buf       = collections.deque(maxlen=2)
    connected = threading.Event()
    stop_ev   = threading.Event()

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
    sys.stdout.write('\033[2J')

    try:
        t.start()

        while True:
            if kbhit() and is_quit_key(getch()):
                break

            tw, th    = get_terminal_size()
            is_live   = connected.is_set()
            status    = 'on' if is_live else 'off'
            vcam_live = use_vcam and vcam is not None

            if not buf:
                sys.stdout.write('\033[H')
                sys.stdout.write(_hud_str('off', cam_name[0], 0, 0, tw, th, vcam_live))
                sys.stdout.flush()
                time.sleep(0.12)
                continue

            bgr = buf[-1]
            rgb = bgr[:, :, ::-1]
            rw, rh = calc_render_size(rgb.shape[1], rgb.shape[0], tw, th, uw)

            sys.stdout.write(render_frame(resize_for_terminal(rgb, rw, rh), charset, color))
            sys.stdout.write(f'\033[{th};1H\033[2K')
            sys.stdout.write(_hud_str(status, cam_name[0], rw, rh, tw, th, vcam_live))
            sys.stdout.flush()

            if vcam_live and is_live:
                vf = _make_vcam_frame(rgb, vcam_cols, vcam_rows, vcam_w, vcam_h)
                vcam.send(vf)
                vcam.sleep_until_next_frame()

    finally:
        stop_ev.set()
        sys.stdout.write('\033[0m\n')
        show_cursor()
        if vcam:
            try:
                vcam.__exit__(None, None, None)
            except Exception:
                pass
