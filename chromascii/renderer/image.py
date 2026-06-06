import sys
import numpy as np
from PIL import Image

from ..utils import get_terminal_size, hide_cursor, show_cursor, getch, is_quit_key
from .engine import render_frame, resize_for_terminal, calc_render_size, CHARSETS


def render_image(path, settings):
    img = Image.open(path).convert('RGB')
    arr = np.asarray(img)
    iw, ih = img.size

    charset = settings.get('charset_str', CHARSETS['default'])
    color   = settings.get('color', 'truecolor')
    uw      = settings.get('width')

    hide_cursor()
    sys.stdout.write('\033[2J')
    try:
        while True:
            tw, th = get_terminal_size()
            rw, rh = calc_render_size(iw, ih, tw, th, uw)
            sys.stdout.write(render_frame(resize_for_terminal(arr, rw, rh), charset, color))
            sys.stdout.flush()
            k = getch()
            if is_quit_key(k) or k == '\n':
                break
    finally:
        sys.stdout.write('\033[0m\n')
        show_cursor()
