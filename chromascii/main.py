import sys
import os
import argparse

from .utils import init_terminal, detect_color_mode, alt_screen
from .renderer.engine import CHARSETS
from . import source
from . import __version__


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
                con.clear()
                con.print(f'\n  [red]error:[/] {e}')
                con.input('  press enter to continue')
            finally:
                flash = _record_session()
            continue

        if action == 'mictest':
            try:
                from .renderer.mictest import run_mic_test
                run_mic_test()
            except KeyboardInterrupt:
                pass
            except Exception as e:
                con.clear()
                con.print(f'\n  [red]error:[/] {e}')
                con.input('  press enter to continue')
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
            con.clear()
            con.print(f'\n  [red]error:[/] {e}')
            con.input('  press enter to continue')
        finally:
            flash = _record_session()


def _parser():
    p = argparse.ArgumentParser(
        prog='chromascii',
        description='Convert images, videos, and GIFs into real-time colored ASCII art.',
        add_help=False,
    )
    p.add_argument('file', nargs='?', help='Image, video, GIF, or URL (YouTube, TikTok, Tenor, Imgur, …) to render')
    p.add_argument('-h', '--help', action='store_true', help='Show this help message and exit')
    p.add_argument('-v', '--version', action='store_true', help='Show the installed version and exit')
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
    p.add_argument('--face-censor', action='store_true', dest='face_censor',
                   help='Pixelate the detected face — heavily in the terminal, moderately in the virtual cam (webcam only)')
    p.add_argument('--face-style', choices=['mosaic', 'ascii', 'blackout'], default=None, dest='face_style',
                   help='Face censor look: mosaic (default) | ascii (continuous random ASCII noise) | blackout')
    p.add_argument('--calibrate-face', action='store_true', dest='calibrate_face',
                   help='Run the face-censor calibration wizard (move your head through every direction), then exit')
    p.add_argument('--mic-test', action='store_true', dest='mic_test',
                   help='Live mic visualizer, just for fun: frequency spectrum + colored volume meter (press m to switch)')
    p.add_argument('--greet', action='store_true',
                   help='Print one random ASCII greeting + tip and exit (used internally by the shell hook)')
    p.add_argument('--shell', choices=['powershell', 'pwsh', 'bash', 'zsh'], default=None,
                   help='Which shell is calling --greet (used internally by the shell hook to pick a style)')
    p.add_argument('--install-hook', action='store_true', dest='install_hook',
                   help='Install a hook so every new terminal prints a random chromascii greeting on startup')
    p.add_argument('--uninstall-hook', action='store_true', dest='uninstall_hook',
                   help='Remove the shell greeting hook installed by --install-hook')
    return p


# ---------------------------------------------------------------------------
# Help & version
# ---------------------------------------------------------------------------

def _print_version():
    print(f'chromascii {__version__}')


_HOOK_STATUS_STYLE = {
    'installed': 'bold green', 'removed': 'bold green',
    'already-installed': 'dim', 'no-hook': 'dim', 'not-found': 'dim',
}


def _run_hook_action(action):
    from rich.console import Console
    from . import shellhook

    con = Console()
    fn = shellhook.install if action == 'install' else shellhook.uninstall
    results = fn()

    if not results:
        con.print('[yellow]no shell detected (powershell/pwsh/bash/zsh not found on PATH)[/]')
        return

    verb = 'installed' if action == 'install' else 'removed'
    con.print(f'\n  [bold cyan]chromascii[/] — greeting hook ({verb})\n')
    for shell, path, status in results:
        style = _HOOK_STATUS_STYLE.get(status, 'yellow')
        con.print(f'    [{style}]{status:<18}[/]  [dim]{shell:<10}[/]  {path}')
    con.print()
    if action == 'install':
        con.print('  [dim]open a new terminal to see it — chromascii --uninstall-hook to remove it[/]')
        con.print('  [dim]set CHROMASCII_NO_GREET=1 to silence it without uninstalling[/]\n')


def _print_help():
    import shutil
    from rich.console import Console
    from rich.table import Table
    from rich.rule import Rule

    term_w = shutil.get_terminal_size(fallback=(100, 24)).columns
    con = Console(width=max(100, term_w))

    def section(title):
        con.print()
        con.print(f'[bold cyan]{title}[/]')
        con.print(Rule(style='grey37'))

    def table(rows, col1=24):
        t = Table.grid(padding=(0, 2))
        t.add_column(style='green', no_wrap=True, min_width=col1)
        t.add_column(style='white')
        for a, b in rows:
            t.add_row(a, b)
        con.print(t)

    con.print()
    con.print(f'[bold cyan]chromascii[/] [dim]v{__version__}[/]  '
              f'— turn anything into real-time colored ASCII/Unicode art in your terminal')

    section('USAGE')
    table([
        ('chromascii', 'open the interactive TUI (file browser, settings, webcam)'),
        ('chromascii <file-or-url>', 'render an image, video, GIF, or link directly'),
        (r'chromascii --webcam \[options]', 'stream the live webcam as ASCII'),
        ('chromascii --calibrate-face', 'run the face-censor calibration wizard and exit'),
        ('chromascii --mic-test', 'just-for-fun live mic visualizer: spectrum / volume meter'),
        ('chromascii -h | --help', 'show this help and exit'),
        ('chromascii -v | --version', 'show the installed version and exit'),
    ])

    section('INPUT')
    table([
        ('file', 'path to an image (.jpg .jpeg .png .bmp .webp), video (.mp4 .mov .avi .webm), or GIF'),
        ('', 'or a URL — YouTube, TikTok, Tenor, Imgur, or any direct media link / yt-dlp target'),
        ('--webcam', 'stream from the default camera (device 0) instead of a file'),
    ])

    section('RENDERING')
    table([
        ('--width N', 'render width in characters (default: current terminal width)'),
        ('--detail MODE', "sextant (default) | octant | braille | quadblock | halfblock | ascii"),
        ('--chars STR', 'custom luminance→character ramp, dark to light (ascii mode only)'),
        ('--color MODE', 'truecolor | 256 | mono  (default: auto-detected from the terminal)'),
        ('--dither', 'ordered (Bayer) dithering to smooth gradients (ascii mode only)'),
    ])

    section('PLAYBACK  (video / gif)')
    table([
        ('--fps N', 'override the playback frame rate (default: source fps, webcam default 30)'),
        ('--loop', 'loop video / GIF playback'),
        ('--no-audio', 'disable synchronized audio playback'),
        ('space', '(during playback) pause / resume, audio included'),
        ('q / Esc', '(during playback) stop and return'),
    ])

    section('WEBCAM & VIRTUAL CAMERA')
    table([
        ('--virtual-cam', 'also feed the rendered output to a virtual camera (Discord / Zoom / OBS)'),
        ('', 'needs OBS Studio (Start Virtual Camera once) + pip install pyvirtualcam'),
        ('--face-censor', 'pixelate the detected face — heavy flat blocks in the terminal,'),
        ('', 'a moderate privacy mosaic (rest of the frame stays normal) in the virtual cam'),
        ('--face-style MODE', 'mosaic (default) | ascii (continuous random ASCII noise) | blackout'),
        ('--calibrate-face', 'walk through a short guided wizard (look down/up/left/right/tilt)'),
        ('', 'so the censor box is padded wide enough to never slip off during head movement'),
    ])

    section('EXPORT')
    table([
        ('--export PATH', 'also record the rendered mosaic frames to an MP4 file while it plays'),
    ])

    section('MIC TEST')
    table([
        ('--mic-test', 'live microphone visualizer — just for fun, no real purpose'),
        ('', 'starts in frequency-spectrum mode (log-scaled bars, bass to treble)'),
        ('', "press 'm' to switch to a colored volume meter (green → yellow → orange → red)"),
        ('', 'needs sounddevice: pip install chromascii[audio]'),
        ('q / Esc', 'stop and return'),
    ])

    section('SHELL GREETER')
    table([
        ('--install-hook', 'hook every new terminal (PowerShell/pwsh/bash/zsh, whichever are on PATH)'),
        ('', 'to print a random ASCII greeting + tip on startup'),
        ('--uninstall-hook', 'remove that hook again'),
        ('--greet', 'print one greeting right now and exit (what the hook calls internally)'),
        ('', 'set CHROMASCII_NO_GREET=1 to silence it without uninstalling'),
    ])

    section('EXAMPLES')
    table([
        ('chromascii photo.jpg', 'image, auto settings'),
        ('chromascii photo.jpg --color mono', 'grayscale ASCII'),
        ('chromascii clip.mp4 --detail octant --width 160', 'sharpest engine, wide render'),
        ('chromascii clip.mp4 --loop --color 256', 'looping playback, 256-color'),
        ('chromascii clip.gif --loop', 'animated GIF'),
        ('chromascii "https://youtube.com/watch?v=…"', 'link — downloaded, cached, played'),
        ('chromascii "https://tenor.com/…"', 'same, for any yt-dlp-supported / direct link'),
        ('chromascii --webcam', 'live webcam, default settings'),
        ('chromascii --webcam --detail sextant', 'live webcam, sextant engine'),
        ('chromascii --webcam --color 256', 'live webcam, 256-color'),
        ('chromascii --webcam --virtual-cam', 'webcam → Discord / Zoom / OBS'),
        ('chromascii --webcam --face-censor', 'webcam with the face pixelated (terminal only)'),
        ('chromascii --webcam --face-censor --face-style ascii', 'random ASCII-noise censor look'),
        ('chromascii --webcam --virtual-cam --face-censor', 'censored face, fed to Discord/OBS too'),
        ('chromascii --calibrate-face', 'run the calibration wizard on its own'),
        ('chromascii clip.mp4 --detail ascii --chars "█▓▒░ " --dither', 'classic dithered ASCII'),
        ('chromascii clip.mp4 --export out.mp4 --no-audio', 'silent render-to-file'),
        ('chromascii --install-hook', 'greet every new terminal with a random ASCII tip'),
        ('chromascii --uninstall-hook', 'remove that greeting hook'),
        ('chromascii --mic-test', 'talk into the mic and watch the spectrum / volume meter'),
    ], col1=36)

    section('TERMINAL REQUIREMENTS')
    table([
        ('recommended', 'Windows Terminal, iTerm2, Kitty, Alacritty, WezTerm, GNOME Terminal, VS Code'),
        ('truecolor', "set $COLORTERM=truecolor if colors look wrong; falls back to --color 256"),
        ('fonts', 'sextant needs a 2021+ font; octant needs a 2024+ font (Cascadia Code, Nerd Fonts)'),
        ('not supported', 'classic cmd.exe and default PuTTY — use Windows Terminal / --color 256'),
    ])

    section('TROUBLESHOOTING')
    table([
        ('command not found', 'add the Python Scripts dir to PATH, or run: python -m chromascii'),
        ('boxes / "?" glyphs', "terminal font doesn't cover that block — try --detail sextant/ascii"),
        ('wrong / no colors', 'terminal lacks truecolor — try --color 256 or --color mono'),
        ('no audio', r'pip install chromascii\[audio]   (needs av + sounddevice)'),
        ('link fails to download', 'pip install -U yt-dlp — site extractors change often'),
        ('webcam "Not Connected"', 'close other apps using the camera; check OS camera privacy settings'),
        ('virtual cam not in Discord', 'click "Start Virtual Camera" in OBS once, then restart Discord'),
        ('face never gets censored', 'run --calibrate-face in good, even lighting facing the camera'),
        ('censor box flickers off', 're-run --calibrate-face — it pads margins from your own head range'),
        ('low fps / slow rendering', 'use --detail halfblock or quadblock, or shrink the terminal window'),
    ], col1=28)

    con.print()
    con.print('[dim]Docs & project structure: see README.md in the repository root.[/]')
    con.print()


def main():
    init_terminal()
    args = _parser().parse_args()

    if args.help:
        _print_help()
        return
    if args.version:
        _print_version()
        return
    if args.calibrate_face:
        from .renderer.face import run_calibration
        with alt_screen():
            run_calibration()
        return
    if args.mic_test:
        from .renderer.mictest import run_mic_test
        try:
            with alt_screen():
                run_mic_test()
        except KeyboardInterrupt:
            pass
        except Exception as e:
            print(f'chromascii: {e}', file=sys.stderr)
            sys.exit(1)
        return
    if args.greet:
        from .greet import greet
        greet(shell=args.shell)
        return
    if args.install_hook:
        _run_hook_action('install')
        return
    if args.uninstall_hook:
        _run_hook_action('uninstall')
        return

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
            'face_censor': args.face_censor,
            'face_style': args.face_style or 'mosaic',
        }
        try:
            with alt_screen():
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
        with alt_screen():
            _tui_loop()
    except KeyboardInterrupt:
        pass


if __name__ == '__main__':
    main()
