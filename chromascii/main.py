import sys
import os
import argparse

from .utils import init_terminal, detect_color_mode
from .renderer.engine import CHARSETS
from . import source


_IMG = {'.jpg', '.jpeg', '.png', '.bmp', '.webp'}
_GIF = {'.gif'}
_VID = {'.mp4', '.mov', '.avi', '.webm'}
_ALL = _IMG | _GIF | _VID


def _dispatch(path, settings):
    from .tui import state
    ext = os.path.splitext(path)[1].lower()
    if ext in _IMG:
        state.bump_media('image')
        from .renderer.image import render_image
        render_image(path, settings)
    else:
        state.bump_media('gif' if ext in _GIF else 'video')
        from .renderer.video import render_video
        render_video(path, settings)


def _resolve(con, path_or_url):
    if not source.is_url(path_or_url):
        return path_or_url
    from .tui import messages, sound
    phrase = messages.random_download_phrase()
    with con.status(f'[cyan]{phrase}[/]') as status:
        result = source.resolve_source(
            path_or_url, on_progress=lambda m: status.update(f'[cyan]{phrase} ({m})[/]')
        )
    sound.play_chime('plink')
    return result


def _record_session():
    from .renderer.engine import take_char_count
    from .tui import state, messages

    n = take_char_count()
    if n <= 0:
        return None
    total = state.add_chars(n)
    return messages.next_message(total)


def _tui_loop():
    from .tui.launcher import show_launcher, prompt_path
    from .tui.picker import show_picker
    from .tui.settings import show_settings
    from .tui import state
    from rich.console import Console

    con = Console()
    first = True

    streak = state.record_open()
    flash = f'{streak} day streak — welcome back' if streak >= 2 else None

    while True:
        action = show_launcher(first_time=first, flash_message=flash)
        first = False
        flash = None

        if action == 'quit':
            break

        if action == 'webcam':
            from .tui.settings import show_webcam_settings
            wcam_settings = show_webcam_settings()
            if wcam_settings is None:
                continue
            try:
                state.bump_media('webcam')
                from .renderer.webcam import render_webcam
                render_webcam(wcam_settings)
            except Exception as e:
                con.print(f'\n  [red]error:[/] {e}')
                con.input('  press enter to continue')
            finally:
                flash = _record_session()
            continue

        filepath = show_picker() if action == 'file' else prompt_path()

        if not filepath:
            continue

        if source.is_url(filepath):
            try:
                filepath = _resolve(con, filepath)
            except Exception as e:
                con.clear()
                con.print(f'\n  [red]download error:[/] {e}')
                con.input('  press enter to continue')
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
        finally:
            flash = _record_session()


def _parser():
    p = argparse.ArgumentParser(
        prog='chromascii',
        description='Convert images, videos, and GIFs into real-time colored ASCII art.',
    )
    p.add_argument('file', nargs='?', help='Image, video, GIF, or URL (YouTube, TikTok, Tenor, Imgur, …) to render')
    p.add_argument('--webcam', action='store_true', help='Live ASCII from webcam')
    p.add_argument('--width', type=int, default=None, metavar='N')
    p.add_argument('--fps', type=float, default=None, metavar='N')
    p.add_argument('--chars', type=str, default=None, metavar='STR')
    p.add_argument('--color', choices=['truecolor', '256', 'mono'], default=None)
    p.add_argument('--loop', action='store_true')
    p.add_argument('--virtual-cam', action='store_true',
                   dest='virtual_cam',
                   help='Feed ASCII art into a virtual camera (needs pyvirtualcam + OBS)')
    p.add_argument('--detail', choices=['sextant', 'octant', 'braille', 'quadblock', 'halfblock', 'ascii'], default=None,
                   help='Rendering detail mode for video/webcam (default: sextant; octant is sharpest but slowest)')
    p.add_argument('--dither', action='store_true', help='Ordered dithering for smoother gradients (ascii mode)')
    p.add_argument('--no-audio', action='store_true', dest='no_audio', help='Disable audio playback for video')
    p.add_argument('--export', type=str, default=None, metavar='PATH',
                   help='Also record the rendered output to a video file')
    return p


def main():
    init_terminal()
    args = _parser().parse_args()

    if args.file or args.webcam:
        from rich.console import Console
        con = Console()

        file_arg = args.file
        if file_arg:
            try:
                file_arg = _resolve(con, file_arg)
            except Exception as e:
                print(f'chromascii: download failed: {e}', file=sys.stderr)
                sys.exit(1)

        settings = {
            'width': args.width,
            'fps': args.fps,
            'charset_str': args.chars or CHARSETS['default'],
            'color': args.color or detect_color_mode(),
            'loop': args.loop,
            'virtual_cam': args.virtual_cam,
            'detail': args.detail or 'sextant',
            'dither': args.dither,
            'audio': not args.no_audio,
            'export': args.export,
        }
        try:
            if args.webcam:
                from .tui import state
                state.bump_media('webcam')
                from .renderer.webcam import render_webcam
                render_webcam(settings)
            else:
                if not os.path.isfile(file_arg):
                    print(f'chromascii: file not found: {file_arg}', file=sys.stderr)
                    sys.exit(1)
                _dispatch(file_arg, settings)
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
