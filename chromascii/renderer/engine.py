import numpy as np
from PIL import Image


CHARSETS = {
    'default': '@#$%&*+=-:. ',
    'blocks':  '█▓▒░ ',
    'minimal': '@. ',
}

CHARSET_LABELS = {
    'default': '@#$%&*+=- .',
    'blocks':  '█▓▒░ ',
    'minimal': '@. ',
    'custom':  '(custom)',
}

COLOR_MODES   = ['truecolor', '256', 'mono']
CHARSET_NAMES = ['default', 'blocks', 'minimal', 'custom']

_LUT = None


def _get_lut():
    global _LUT
    if _LUT is None:
        lut = np.zeros((32, 32, 32), dtype=np.uint8)
        for ri in range(32):
            for gi in range(32):
                for bi in range(32):
                    lut[ri, gi, bi] = 16 + 36 * round(ri / 31 * 5) + 6 * round(gi / 31 * 5) + round(bi / 31 * 5)
        _LUT = lut
    return _LUT


def render_frame(arr, charset, color_mode='truecolor', home=True):
    H, W = arr.shape[:2]
    ca = np.array(list(charset), dtype='U1')
    n  = len(charset)

    R = arr[:, :, 0].astype(np.int32)
    G = arr[:, :, 1].astype(np.int32)
    B = arr[:, :, 2].astype(np.int32)

    L    = (R * 299 + G * 587 + B * 114) // 1000
    idx  = (L * (n - 1) // 255).clip(0, n - 1)
    chars = ca[idx]

    buf = ['\033[H'] if home else []

    if color_mode == 'truecolor':
        for y in range(H):
            cy, ry, gy, by = chars[y], R[y], G[y], B[y]
            buf.append(''.join(f'\033[38;2;{ry[x]};{gy[x]};{by[x]}m{cy[x]}' for x in range(W)))
            buf.append('\033[0m\n')

    elif color_mode == '256':
        lut = _get_lut()
        ci  = lut[(R >> 3).clip(0, 31), (G >> 3).clip(0, 31), (B >> 3).clip(0, 31)]
        for y in range(H):
            cy, ciy = chars[y], ci[y]
            buf.append(''.join(f'\033[38;5;{ciy[x]}m{cy[x]}' for x in range(W)))
            buf.append('\033[0m\n')

    else:
        for y in range(H):
            buf.append(''.join(chars[y]) + '\n')

    return ''.join(buf)


def resize_for_terminal(arr, w, h):
    img = Image.fromarray(arr.astype(np.uint8), 'RGB')
    return np.asarray(img.resize((w, h), Image.LANCZOS))


def calc_render_size(iw, ih, tw, th, user_w=None, char_aspect=2.0):
    rw     = min(user_w or tw, tw)
    aspect = iw / max(ih, 1)
    rh     = max(1, int(rw / (aspect * char_aspect)))
    maxh   = max(th - 2, 1)
    if rh > maxh:
        rh = maxh
        rw = max(1, min(tw, int(rh * aspect * char_aspect)))
    return max(1, rw), max(1, rh)
