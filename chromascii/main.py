import sys
import os
import argparse

from .utils import init_terminal, detect_color_mode
from .renderer.engine import CHARSETS


_IMG  = {'.jpg', '.jpeg', '.png', '.bmp', '.webp'}
_GIF  = {'.gif'}
_VID  = {'.mp4', '.mov', '.avi', '.webm'}
_ALL  = _IMG | _GIF | _VID


def _dispatch(path, settings):
    ext = os.path.splitext(path)[1].lower()
    if ext in _IMG:
        from .renderer.image import render_image
        render_image(path, settings)
    else:
        from .renderer.video import render_video
        render_video(path, settings)


def _tui_loop():
    from .tui.launcher import show_launcher, prompt_path
    from .tui.picker import show_picker
    from .tui.settings import show_settings
    from rich.console import Console

    con = Console()
    first = True

    while True:
        action = show_launcher(first_time=first)
        first = False

        if action == 'quit':
            break

        if action == 'webcam':
            from .tui.settings import show_webcam_settings
            wcam_settings = show_webcam_settings()
            if wcam_settings is None:
                continue
            try:
                from .renderer.webcam import render_webcam
                render_webcam(wcam_settings)
            except Exception as e:
                con.print(f'\n  [red]error:[/] {e}')
                con.input('  press enter to continue')
            continue

        filepath = show_picker() if action == 'file' else prompt_path()

        if not filepath:
            continue

        if not os.path.isfile(filepath):
            con.clear()
            con.print(f'\n  [red]file not found:[/] {filepath}')
            con.input('  press enter to continue')
            continue

        if os.path.splitext(filepath)[1].lower() not in _ALL:
            con.clear()
            con.print(f'\n  [red]unsupported format[/]  supported: {", ".join(sorted(_ALL))}')
            con.input('  press enter to continue')
            continue

        settings = show_settings(filepath)
        if settings is None:
            continue

        try:
            _dispatch(filepath, settings)
        except KeyboardInterrupt:
            pass
        except Exception as e:
            con.print(f'\n  [red]error:[/] {e}')
            con.input('  press enter to continue')


def _parser():
    p = argparse.ArgumentParser(
        prog='chromascii',
        description='Convert images, videos, and GIFs into real-time colored ASCII art.',
    )
    p.add_argument('file', nargs='?', help='Image, video, or GIF to render')
    p.add_argument('--webcam', action='store_true', help='Live ASCII from webcam')
    p.add_argument('--width',  type=int,   default=None, metavar='N')
    p.add_argument('--fps',    type=float, default=None, metavar='N')
    p.add_argument('--chars',  type=str,   default=None, metavar='STR')
    p.add_argument('--color',  choices=['truecolor', '256', 'mono'], default=None)
    p.add_argument('--loop',        action='store_true')
    p.add_argument('--virtual-cam', action='store_true',
                   dest='virtual_cam',
                   help='Feed ASCII art into a virtual camera (needs pyvirtualcam + OBS)')
    return p


def main():
    init_terminal()
    args = _parser().parse_args()

    if args.file or args.webcam:
        settings = {
            'width':       args.width,
            'fps':         args.fps,
            'charset_str': args.chars or CHARSETS['default'],
            'color':       args.color or detect_color_mode(),
            'loop':        args.loop,
            'virtual_cam': args.virtual_cam,
        }
        try:
            if args.webcam:
                from .renderer.webcam import render_webcam
                render_webcam(settings)
            else:
                if not os.path.isfile(args.file):
                    print(f'chromascii: file not found: {args.file}', file=sys.stderr)
                    sys.exit(1)
                _dispatch(args.file, settings)
        except KeyboardInterrupt:
            pass
        except Exception as e:
            print(f'chromascii: {e}', file=sys.stderr)
            sys.exit(1)
        return

    try:
        _tui_loop()
    except KeyboardInterrupt:
        pass


if __name__ == '__main__':
    main()
