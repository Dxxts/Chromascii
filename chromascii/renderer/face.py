import os
import sys
import time
import json
import random
from pathlib import Path


FACE_STYLES = ('mosaic', 'ascii', 'blackout')
_ASCII_STYLE_CHARS = '@#$%&8B0OQMWNXK*+=-:. '

_DETECT_WIDTH = 360
_HOLD_SECONDS = 1.5
_SMOOTH_ALPHA = 0.40
_SAFETY_MARGIN = 0.12
_MARGIN_MIN = 0.15
_MARGIN_MAX = 0.75

_DEFAULT_MARGINS = {
    'top': 0.35, 'bottom': 0.25, 'left': 0.30, 'right': 0.30,
    'calibrated': False,
}

_STEPS = [
    ('center',  'head straight',    'Look straight at the camera, head straight and still', 2.0),
    ('down',    'head down',        'Tilt your head down, chin toward your chest', 2.5),
    ('up',      'head up',          'Lift your head up', 2.5),
    ('left',    'head left',        'Slowly turn your head to the left', 2.5),
    ('right',   'head right',       'Slowly turn your head to the right', 2.5),
    ('tilt_l',  'tilt left',        'Tilt your head toward your left shoulder', 2.0),
    ('tilt_r',  'tilt right',       'Tilt your head toward your right shoulder', 2.0),
]


_CASCADE_FILES = {
    'default': 'haarcascade_frontalface_default.xml',
    'alt2': 'haarcascade_frontalface_alt2.xml',
    'profile': 'haarcascade_profileface.xml',
}

_cascade_cache = {}
_UNAVAILABLE_HINT = (
    "this opencv-python build doesn't include CascadeClassifier "
    "(happens with some very recent opencv-python wheels, e.g. the 5.x series) — "
    "try: pip install \"opencv-python==4.13.0.92\""
)


def _cascade(kind='default'):
    if kind not in _cascade_cache:
        import cv2
        if not hasattr(cv2, 'CascadeClassifier'):
            raise RuntimeError(_UNAVAILABLE_HINT)
        path = os.path.join(cv2.data.haarcascades, _CASCADE_FILES[kind])
        clf = cv2.CascadeClassifier(path)
        if clf.empty():
            raise RuntimeError(f'could not load haar cascade file: {path}')
        _cascade_cache[kind] = clf
    return _cascade_cache[kind]


def ensure_available():
    """Forces the default cascade to load, raising a clear RuntimeError if it
    can't — call this once up front so callers can degrade gracefully instead
    of crashing on the first detection attempt inside a hot loop."""
    _cascade('default')


def _state_dir():
    if sys.platform == 'win32':
        base = os.environ.get('LOCALAPPDATA') or os.path.expanduser('~')
        d = Path(base) / 'chromascii'
    else:
        base = os.environ.get('XDG_DATA_HOME', os.path.expanduser('~/.local/share'))
        d = Path(base) / 'chromascii'
    d.mkdir(parents=True, exist_ok=True)
    return d


def _calib_path():
    return _state_dir() / 'face_calibration.json'


def load_calibration():
    try:
        with open(_calib_path(), 'r', encoding='utf-8') as f:
            data = json.load(f)
        merged = dict(_DEFAULT_MARGINS)
        merged.update(data)
        return merged
    except Exception:
        return dict(_DEFAULT_MARGINS)


def save_calibration(margins):
    try:
        with open(_calib_path(), 'w', encoding='utf-8') as f:
            json.dump(margins, f)
    except Exception:
        pass


def _run_cascade(kind, gray, scale_factor, min_neighbors):
    faces = _cascade(kind).detectMultiScale(
        gray, scaleFactor=scale_factor, minNeighbors=min_neighbors, minSize=(36, 36)
    )
    if len(faces) == 0:
        return None
    return max(faces, key=lambda f: f[2] * f[3])


def detect_face_box(bgr, thorough=False):
    """Returns the largest detected face as (x, y, w, h) in bgr's own pixel space, or None.

    The default (fast) pass only tries the frontal cascade on an equalized frame —
    cheap enough to run every frame while already tracking. thorough=True also tries
    the un-equalized frame, a more lenient alt cascade, and left/right profile
    cascades — slower, but used while still searching for the first lock (or after
    tracking has been lost for a while), where recall matters more than speed.
    """
    import cv2
    h, w = bgr.shape[:2]
    scale = _DETECT_WIDTH / w if w > _DETECT_WIDTH else 1.0
    small = cv2.resize(bgr, (max(1, int(w * scale)), max(1, int(h * scale)))) if scale != 1.0 else bgr
    gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
    gray_eq = cv2.equalizeHist(gray)

    best = _run_cascade('default', gray_eq, 1.15, 5)

    if best is None and thorough:
        best = _run_cascade('default', gray, 1.1, 4)
    if best is None and thorough:
        best = _run_cascade('alt2', gray_eq, 1.1, 3)
    if best is None and thorough:
        best = _run_cascade('profile', gray_eq, 1.1, 3)
    if best is None and thorough:
        flipped = cv2.flip(gray_eq, 1)
        prof = _run_cascade('profile', flipped, 1.1, 3)
        if prof is not None:
            fx, fy, fw, fh = prof
            best = (flipped.shape[1] - fx - fw, fy, fw, fh)

    if best is None:
        return None
    fx, fy, fw, fh = best
    if scale != 1.0:
        inv = 1.0 / scale
        fx, fy, fw, fh = fx * inv, fy * inv, fw * inv, fh * inv
    return (int(fx), int(fy), int(fw), int(fh))


def _pad_box(box, margins, frame_w, frame_h):
    x, y, w, h = box
    x0 = x - w * margins['left']
    y0 = y - h * margins['top']
    x1 = x + w + w * margins['right']
    y1 = y + h + h * margins['bottom']
    x0 = max(0, int(round(x0)))
    y0 = max(0, int(round(y0)))
    x1 = min(frame_w, int(round(x1)))
    y1 = min(frame_h, int(round(y1)))
    return (x0, y0, x1, y1)


class FaceCensor:
    """Tracks a face across frames with smoothing and a hold-last grace period,
    so a momentary detection miss never uncovers the face."""

    def __init__(self, margins=None):
        self.margins = margins or load_calibration()
        self._smoothed = None
        self._last_seen = 0.0
        self.locked = False

    def update(self, bgr):
        h, w = bgr.shape[:2]
        now = time.perf_counter()
        raw = detect_face_box(bgr, thorough=not self.locked)

        if raw is not None:
            target = _pad_box(raw, self.margins, w, h)
            if self._smoothed is None:
                self._smoothed = target
            else:
                a = _SMOOTH_ALPHA
                self._smoothed = tuple(
                    int(round(a * t + (1 - a) * s)) for t, s in zip(target, self._smoothed)
                )
            self._last_seen = now
            self.locked = True
            return self._smoothed

        if self._smoothed is not None and (now - self._last_seen) < _HOLD_SECONDS:
            return self._smoothed

        # tracking lost beyond the grace period — drop back to a full multi-cascade
        # search on the next frame instead of only retrying the cheap frontal pass
        self.locked = False
        return None


def _clip(box, w, h):
    x0, y0, x1, y1 = box
    x0 = max(0, min(x0, w - 1))
    y0 = max(0, min(y0, h - 1))
    x1 = max(x0 + 1, min(x1, w))
    y1 = max(y0 + 1, min(y1, h))
    return x0, y0, x1, y1


def pixelate_heavy(rgb, box, grid=5):
    """Collapses the region to a tiny flat-color grid — used for the terminal path,
    where the surrounding image is already ASCII-downsampled and the face must carry
    strictly less detail than that, not just look blurred."""
    import cv2
    h, w = rgb.shape[:2]
    x0, y0, x1, y1 = _clip(box, w, h)
    region = rgb[y0:y1, x0:x1]
    if region.size == 0:
        return rgb
    small = cv2.resize(region, (grid, grid), interpolation=cv2.INTER_AREA)
    mosaic = cv2.resize(small, (x1 - x0, y1 - y0), interpolation=cv2.INTER_NEAREST)
    out = rgb.copy()
    out[y0:y1, x0:x1] = mosaic
    return out


def pixelate_medium(rgb, box, cell=18):
    """Mosaic-blurs the region while keeping it recognizable as an intentional privacy
    blur rather than a flat block — used for the virtual-cam path, where the rest of
    the frame stays near full quality."""
    import cv2
    h, w = rgb.shape[:2]
    x0, y0, x1, y1 = _clip(box, w, h)
    region = rgb[y0:y1, x0:x1]
    if region.size == 0:
        return rgb
    rw, rh = x1 - x0, y1 - y0
    cols = max(4, rw // cell)
    rows = max(4, rh // cell)
    small = cv2.resize(region, (cols, rows), interpolation=cv2.INTER_AREA)
    mosaic = cv2.resize(small, (rw, rh), interpolation=cv2.INTER_NEAREST)
    out = rgb.copy()
    out[y0:y1, x0:x1] = mosaic
    return out


def fallback_box(frame_w, frame_h):
    """Used before any face has ever been locked this session (or once tracking
    has been lost past the hold period). We have no idea where in the frame the
    face actually is — a face is not necessarily centered or near the top, as
    laptop webcam framing varies a lot — so the only safe default is to censor
    the entire frame rather than guess a region and risk missing it."""
    return (0, 0, frame_w, frame_h)


def _apply_ascii_style(rgb, box):
    """Fills the region with a continuously-randomized grid of ASCII glyphs on a
    solid dark backdrop — a distinct, self-consciously 'digital' censor look,
    fully opaque so nothing underneath can leak through."""
    import cv2
    h, w = rgb.shape[:2]
    x0, y0, x1, y1 = _clip(box, w, h)
    region = rgb[y0:y1, x0:x1]
    if region.size == 0:
        return rgb
    out = rgb.copy()
    region = out[y0:y1, x0:x1]
    region[:] = (12, 12, 12)
    bw, bh = x1 - x0, y1 - y0
    cell = max(10, min(bw, bh) // 12)
    font = cv2.FONT_HERSHEY_SIMPLEX
    for gy in range(0, bh, cell):
        for gx in range(0, bw, cell):
            ch = random.choice(_ASCII_STYLE_CHARS)
            if ch == ' ':
                continue
            color = (random.randint(80, 255), random.randint(180, 255), random.randint(80, 255))
            cv2.putText(region, ch, (gx, gy + cell - 2), font, cell / 24.0, color, 1, cv2.LINE_AA)
    return out


def _apply_blackout_style(rgb, box):
    h, w = rgb.shape[:2]
    x0, y0, x1, y1 = _clip(box, w, h)
    out = rgb.copy()
    out[y0:y1, x0:x1] = (12, 12, 12)
    return out


def _apply_style(rgb, box, style, heavy):
    if style == 'ascii':
        return _apply_ascii_style(rgb, box)
    if style == 'blackout':
        return _apply_blackout_style(rgb, box)
    return pixelate_heavy(rgb, box) if heavy else pixelate_medium(rgb, box)


def censor_for_terminal(rgb, box, style='mosaic'):
    if box is None:
        h, w = rgb.shape[:2]
        box = fallback_box(w, h)
    return _apply_style(rgb, box, style, heavy=True)


def censored_vcam_frame(rgb, box, out_w, out_h, style='mosaic'):
    """Resizes to near-normal quality and censors only the face region — the rest
    of the frame looks like a regular webcam feed."""
    import cv2
    h, w = rgb.shape[:2]
    resized = cv2.resize(rgb, (out_w, out_h), interpolation=cv2.INTER_LINEAR)
    sx, sy = out_w / w, out_h / h
    if box is None:
        box = fallback_box(w, h)
    x0, y0, x1, y1 = box
    scaled = (int(x0 * sx), int(y0 * sy), int(x1 * sx), int(y1 * sy))
    return _apply_style(resized, scaled, style, heavy=False)


# ---------------------------------------------------------------------------
# Calibration / training wizard
# ---------------------------------------------------------------------------

def run_calibration(cam_idx=0):
    """Interactive wizard: walks the user through moving their head in every
    direction while the detector tracks it, then derives per-direction padding
    margins wide enough that normal head movement never breaks the censor box.

    Shows a live ASCII preview of the camera with the raw detected face outlined
    in green, so the user sees exactly what the detector sees rather than a
    blind text-only progress bar."""
    import cv2
    from io import StringIO
    from rich.console import Console
    from ..utils import get_terminal_size, hide_cursor, show_cursor, kbhit, getch, is_quit_key, confetti_burst, detect_color_mode
    from .engine import render_frame_halfblock, calc_render_size, resize_for_terminal

    con = Console()

    try:
        ensure_available()
    except Exception as e:
        con.print(f'\n  [yellow]Face censor unavailable:[/] {e}\n')
        con.input('  press enter to continue')
        return None

    cap = cv2.VideoCapture(cam_idx)
    if not cap.isOpened():
        cap.release()
        return None

    color_mode = detect_color_mode()
    hide_cursor()
    con.clear()

    ref_box = None
    extents = {'left': 0.0, 'right': 0.0, 'top': 0.0, 'bottom': 0.0}
    aborted = False
    last_bgr = None

    _PANEL_LINES = 9

    def _draw(bgr, box, title, instruction, remaining, found):
        tw, th = get_terminal_size()
        video_h = max(4, th - _PANEL_LINES)

        if bgr is not None:
            rgb = bgr[:, :, ::-1].copy()
            if box is not None:
                x, y, bw_, bh_ = box
                cv2.rectangle(rgb, (int(x), int(y)), (int(x + bw_), int(y + bh_)), (0, 255, 0), 3)
            rw, rh = calc_render_size(rgb.shape[1], rgb.shape[0], tw, video_h + 2)
            resized = resize_for_terminal(rgb, rw, rh * 2)
            sys.stdout.write(render_frame_halfblock(resized, color_mode))
        else:
            sys.stdout.write('\033[H')

        buf = StringIO()
        c = Console(file=buf, width=tw, highlight=False, markup=True)
        c.print()
        c.print(f'  [bold cyan]chromascii[/]  [dim]›[/]  [white]face censor calibration[/]'
                f'  [dim](green box = what the detector sees)[/]')
        c.print('  [dim]' + '─' * min(60, tw - 2) + '[/]')
        c.print(f'  [bold yellow]{title}[/]  {instruction}')
        status = '[bold green]● face detected[/]' if found else '[bold red]○ no face detected — reposition[/]'
        c.print(f'  {status}    [dim]{remaining:.1f}s[/]    [dim]s = skip step   q = cancel[/]')
        sys.stdout.write('\n' + buf.getvalue())
        sys.stdout.write('\033[0J')
        sys.stdout.flush()

    try:
        for key, title, instruction, duration in _STEPS:
            boxes = []
            t_start = time.perf_counter()
            skip = False

            while True:
                elapsed = time.perf_counter() - t_start
                remaining = duration - elapsed
                if remaining <= 0:
                    break

                ret, bgr = cap.read()
                found = False
                box = None
                if ret:
                    last_bgr = bgr
                    box = detect_face_box(bgr, thorough=True)
                    if box is not None:
                        found = True
                        boxes.append(box)

                _draw(last_bgr, box, title, instruction, remaining, found)

                if kbhit():
                    k = getch()
                    if is_quit_key(k):
                        aborted = True
                        break
                    if k in ('s', 'S'):
                        skip = True
                        break

                time.sleep(0.03)

            if aborted:
                break
            if skip or not boxes:
                continue

            xs = [b[0] for b in boxes]
            ys = [b[1] for b in boxes]
            x2s = [b[0] + b[2] for b in boxes]
            y2s = [b[1] + b[3] for b in boxes]
            avg_box = (
                sum(xs) / len(xs), sum(ys) / len(ys),
                sum(x2s) / len(x2s) - sum(xs) / len(xs),
                sum(y2s) / len(y2s) - sum(ys) / len(ys),
            )

            if key == 'center':
                ref_box = avg_box
                continue

            if ref_box is None:
                continue

            rx, ry, rw, rh = ref_box
            min_x, min_y = min(xs), min(ys)
            max_x2, max_y2 = max(x2s), max(y2s)

            extents['left'] = max(extents['left'], (rx - min_x) / rw)
            extents['top'] = max(extents['top'], (ry - min_y) / rh)
            extents['right'] = max(extents['right'], (max_x2 - (rx + rw)) / rw)
            extents['bottom'] = max(extents['bottom'], (max_y2 - (ry + rh)) / rh)

        if aborted or ref_box is None:
            return None

        margins = {
            'left': min(_MARGIN_MAX, max(_MARGIN_MIN, extents['left'] + _SAFETY_MARGIN)),
            'right': min(_MARGIN_MAX, max(_MARGIN_MIN, extents['right'] + _SAFETY_MARGIN)),
            'top': min(_MARGIN_MAX, max(_MARGIN_MIN, extents['top'] + _SAFETY_MARGIN)),
            'bottom': min(_MARGIN_MAX, max(_MARGIN_MIN, extents['bottom'] + _SAFETY_MARGIN)),
            'calibrated': True,
        }
        save_calibration(margins)

        con.clear()
        con.print()
        con.print('  [bold green]calibration complete[/]')
        con.print()
        con.print(f"  margins applied  [dim]left[/] {margins['left']:.0%}  "
                   f"[dim]right[/] {margins['right']:.0%}  "
                   f"[dim]top[/] {margins['top']:.0%}  "
                   f"[dim]bottom[/] {margins['bottom']:.0%}")
        con.print()
        con.print('  [dim]press a key to continue[/]')
        confetti_burst()
        getch()
        return margins
    finally:
        cap.release()
        show_cursor()
