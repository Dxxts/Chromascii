<div align="center">

# chromascii

**Turn anything into art — real-time colored ASCII/Unicode rendering in your terminal.**

<!-- demo gif here -->

![Python](https://img.shields.io/badge/python-3.8%2B-blue?style=flat-square)
![Version](https://img.shields.io/badge/version-0.2.0-informational?style=flat-square)
![License](https://img.shields.io/badge/license-MIT-green?style=flat-square)
![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey?style=flat-square)

</div>

---

chromascii converts images, videos, GIFs, live webcam feeds, and web links (YouTube, TikTok, Tenor, Imgur, and anything [yt-dlp](https://github.com/yt-dlp/yt-dlp) supports) into colored art rendered directly in the terminal. Every pixel is packed into Unicode block characters — from plain ASCII up to sub-cell block glyphs carrying two independently-colored regions per character — via 24-bit ANSI escape codes. Video plays with synchronized audio, in real time, at up to 60fps.

It ships with a full interactive TUI: animated launcher, file browser, settings panel, color themes, idle-timer easter eggs — or skip all of that and pass a file path (or a link) directly.

---

## Table of Contents

- [Features](#features)
- [Rendering engines](#rendering-engines)
- [Engine quality comparison](#engine-quality-comparison)
- [How it works](#how-it-works)
- [Installation](#installation)
- [Quick start](#quick-start)
- [Interactive TUI](#interactive-tui)
- [CLI reference](#cli-reference)
- [Charsets](#charsets)
- [Color modes](#color-modes)
- [Links & downloads](#links--downloads)
- [Audio sync](#audio-sync)
- [Supported formats](#supported-formats)
- [Webcam](#webcam)
- [Virtual camera (Discord / Zoom / OBS)](#virtual-camera)
- [Exporting video](#exporting-video)
- [Terminal requirements](#terminal-requirements)
- [Troubleshooting](#troubleshooting)
- [Project structure](#project-structure)
- [Dependencies](#dependencies)
- [License](#license)

---

## Features

| Category | What it does |
|---|---|
| **Images** | JPEG, PNG, BMP, WebP |
| **Video** | MP4, MOV, AVI, WebM — frame-accurate playback, synchronized audio, spacebar pause/resume |
| **GIF** | Respects native frame delays and loop count from metadata |
| **Webcam** | Live feed, up to 60fps, auto-reconnects if disconnected |
| **Links** | Paste a YouTube / TikTok / Tenor / Imgur / direct-media URL — downloaded, cached, and played like a local file |
| **6 rendering engines** | From plain ASCII to sub-cell Unicode block glyphs — pick speed vs. sharpness (see [below](#rendering-engines)) |
| **Virtual camera** | Feeds the rendered output into Discord / Zoom / OBS as a real webcam, up to 1440p/60fps |
| **Export** | Record the rendered output to an MP4 file while it plays |
| **TUI launcher** | Animated startup screen, file browser, settings panel, 16 color themes, streaks, idle easter eggs |
| **Color** | Truecolor (24-bit), 256-color, or monochrome — auto-detected |
| **Terminal resize** | Re-renders every frame at the current terminal dimensions |

---

## Rendering engines

chromascii can turn each terminal cell into more than a single flat-colored character. Several engines split a cell into two independently-colored regions (foreground/background) shaped by a Unicode glyph, effectively packing multiple "pixels" into one character cell. Pick a mode with `--detail` (CLI) or `Tab` on the **detail** row in the settings panel.

| Mode | Subpixels/cell | Supersampling | Unicode block | Font support | Relative cost |
|---|---|---|---|---|---|
| `ascii` | 1 (luminance→char) | — | Basic Latin | Universal | Fastest |
| `halfblock` | 2 (1×2) | — | Block Elements (`▀`) | Universal | Very fast |
| `quadblock` | 4 (2×2) | — | Block Elements / Quadrants | Universal | Fast |
| `sextant` | 6 (2×3) | — | Symbols for Legacy Computing (Unicode 13, 2020) | Wide (modern fonts) | Moderate |
| `braille` | 8 (2×4) | 3×2 (48 samples/cell) | Braille Patterns (`⠀`–`⣿`) | Universal, very old block | Moderate–high |
| `octant` | 8 (2×4) | 4×4 (128 samples/cell) | Symbols for Legacy Computing Supplement (Unicode 16.0, 2024) | Newest — needs an up-to-date font | Highest |

- `char_aspect` (terminal cell width/height compensation) is fixed at `2.0` for **every** mode — it only governs the physical grid shape, not how many subpixels are packed per cell, so switching modes never distorts the image.
- `braille` and `octant` anti-alias by rendering at a higher internal resolution and averaging down before quantizing (this is the "supersampling" column) — this is what makes them the most detailed but also the most expensive modes.
- `ascii` is the only mode that uses a [charset](#charsets) and supports [ordered (Bayer) dithering](#charsets) — the block-based modes choose their own two colors per cell instead of mapping to a fixed palette, so there's no banding to dither away in the first place.
- Every mode is rendered with a run-length-encoded ANSI writer: consecutive same-colored characters are emitted as a single escape sequence, not one per character — this is what keeps large flat regions (skies, backgrounds, subtitles) fast even in the priciest modes.

---

## Engine quality comparison

`octant` (8 subpixels, heavily supersampled) is the sharpest engine on paper, but whether it actually beats `sextant` (6 subpixels, no supersampling) depends entirely on the content. Both engines pick their two per-cell colors with the same adaptive 2-means clustering — quality gains only show up where there's real spatial detail for the extra subpixels to resolve.

Measured by reconstructing each engine's output on a common fine-grained reference grid and comparing MSE/PSNR against a Lanczos-downsampled ground truth of the same source:

| Content type | Sextant MSE | Octant MSE | Octant vs. sextant |
|---|---|---|---|
| Sharp diagonal edges (stripes, foliage-like detail) | 2373.1 | 1904.0 | **+19.8% lower MSE** (+0.95dB PSNR) |
| Curved edges (concentric shapes) | 1435.1 | 1294.4 | **+9.8% lower MSE** (+0.45dB PSNR) |
| Random noise (worst-case texture) | — | — | +1.6% lower MSE |
| Smooth gradient, no noise | 0.72 | 0.69 | +3.5% lower MSE |
| Smooth gradient + light sensor-like noise | 0.70 | 0.85 | **−22.3%** (sextant wins) |
| Smooth 2D gradient + light noise (sky/water-like) | — | — | **−115%** (sextant wins clearly) |

**Takeaway:** use `octant` for content with real edges and texture — foliage, text, fine patterns, busy scenes — where it's a measurable, consistent win. For largely smooth footage (sky, water, walls, soft gradients) `sextant` is equal or slightly ahead, because there's no extra spatial structure for the additional subpixels to capture, and the finer per-cell clustering becomes marginally more sensitive to noise. Two dithering strategies (error-diffusion between cells, and Bayer-biased cluster assignment) were tried to close that smooth-content gap and both were rejected after measurement — the first was mathematically inert (the diffused residual is always exactly zero in this adaptive-palette architecture), and the second visibly speckled perfectly flat regions that should stay a clean solid block. `braille` was also evaluated and kept as an option, but its dot-matrix look reads as visibly stippled compared to sextant/octant's solid block fills.

---

## How it works

### Rendering pipeline

```
camera / file / URL
     │
     ▼
 resolve source ────────────────────────────────────────────────────────────────
     │        local path passthrough, or URL → direct fetch / yt-dlp, cached on disk
     ▼
 resize frame ──────────────────────────────────────────────────────────────────
     │        PIL LANCZOS resize to the target subpixel grid for the chosen engine
     ▼
 subpixel decomposition ────────────────────────────────────────────────────────
     │        ascii: 1 luminance sample → charset index
     │        block modes: 2/4/6/8 subpixels → 2-means color clustering → glyph + fg/bg color
     ▼
 ANSI colorize + RLE ───────────────────────────────────────────────────────────
     │        truecolor:  \033[38;2;R;G;B;48;2;R;G;Bm{glyph}   (run-length collapsed)
     │        256-color:  \033[38;5;N;48;5;Nm{glyph}            (5-bit LUT)
     │        mono:       {char}                                 (ascii mode only)
     ▼
 stdout write ──────────────────────────────────────────────────────────────────
              \033[H (cursor home) + full frame string + flush
```

### Frame timing & audio sync

Video playback uses a `FrameClock`: when an audio track is playing, the clock reads the audio player's actual sample position; otherwise it falls back to `time.perf_counter()`. Decoded frames are pulled from a background decode thread through a bounded queue, and any frame that's fallen behind the clock is dropped in favor of a more recent one — video speed tracks wall-clock time rather than drifting when rendering is momentarily slow.

Pressing **spacebar** during playback stops both video and audio, and resuming seeks the audio stream back to the exact paused position before restarting the clock — no jump, no restart from zero.

### Webcam capture

Capture runs in a dedicated background thread that continuously reads frames into a `deque(maxlen=2)`. The render loop always takes the latest available frame without waiting for capture, decoupling render rate from the camera's hardware frame rate, paced to the configured target FPS (up to 60).

```
┌─ capture thread ──┐       ┌─ render thread (main) ──┐
│  cap.read() loop  │──────▶│  deque[-1] → render      │
│  deque.append()   │       │  stdout.write()           │
└───────────────────┘       └──────────────────────────┘
```

The camera name is resolved asynchronously via a second background thread (PowerShell `Get-PnpDevice` on Windows) so the UI starts instantly — occasionally replaced with a joke nickname instead of the real device name.

---

## Installation

### Requirements

- Python 3.8 or newer
- A modern terminal with truecolor support (see [Terminal requirements](#terminal-requirements))

### From source

```bash
git clone https://github.com/Dxxts/chromascii.git
cd chromascii
pip install .
```

### From PyPI *(once published)*

```bash
pip install chromascii
```

### Optional extras

```bash
pip install chromascii[audio]        # synchronized video audio (av + sounddevice)
pip install chromascii[virtualcam]   # --virtual-cam support (also needs OBS)
```

Both degrade silently if missing — video plays muted without `audio`, `--virtual-cam` prints a warning and continues rendering to the terminal without `virtualcam`.

### Windows PATH note

On Windows with a user Python install, pip places `chromascii.exe` in a Scripts folder that may not be on your PATH. If the command is not found after install:

```powershell
python -c "import sysconfig; print(sysconfig.get_path('scripts'))"
```

Add the printed path to your user PATH via **System Properties → Environment Variables → Path → Edit → New**, then restart your terminal. Alternatively, always invoke via:

```bash
python -m chromascii
```

---

## Quick start

```bash
# Open the interactive TUI
chromascii

# Render an image directly
chromascii photo.jpg

# Play a video with the sharpest engine
chromascii clip.mp4 --detail octant

# Paste a link — downloaded, cached, and played
chromascii "https://youtube.com/watch?v=..."

# Live webcam in 256-color mode
chromascii --webcam --color 256

# Live webcam + feed to Discord as virtual camera
chromascii --webcam --virtual-cam

# Record the rendered output to a video file
chromascii clip.mp4 --export out.mp4
```

---

## Interactive TUI

Running `chromascii` with no arguments opens the interactive launcher.

### Launcher

An animated startup screen types the title letter by letter, then presents the main menu:

```
╭──────────────────────────────────────────────────╮
│   ░▒▓   c h r o m a s c i i   ▓▒░               │
│           turn anything into art                 │
╰──────────────────────────────────────────────────╯

    [1]  open file         pick an image, video or gif
    [2]  paste path        enter a file path or link
    [3]  use webcam        live ASCII from camera
     ?   help                key reference
     q   quit
```

Streaks (consecutive daily opens), lifetime character-render counts, and rotating status messages appear in this screen over time.

### File browser & settings panel

Selecting **open file** opens an inline browser with file metadata (dimensions, duration, size), followed by a settings panel:

```
╭ chromascii ──────────────────────────────────────╮
│  file    demo.mp4                                │
│  mode    ── video ──                             │
╰──────────────────────────────────────────────────╯

  ▶ width     ████████████░░░░░░░░░░░░░░   80 chars
    fps       ███████░░░░░░░░░░░░░░░░░░░   24 fps
    charset   [@#$%&*+=-. ]  default
    color     truecolor      24-bit ANSI
    detail    octant         octant blocks, 2×4 subpixels, supersampled (sharpest)
    dither    off
    loop      on

  ↑↓ navigate   ← → adjust   tab cycle   space toggle   ⏎ play   q back
```

| Key | Action |
|---|---|
| `↑` / `↓` | Move between settings rows |
| `←` / `→` | Adjust **width** (±5) or **fps** (±1) |
| `Tab` | Cycle **charset**, **color**, or **detail** |
| `Space` | Toggle **loop** / **dither** on/off |
| `Enter` | Start playback |
| `q` / `Esc` | Go back to menu |

Rows that don't apply to the current file type are dimmed (e.g. fps/detail/loop for images).

### Playback

```
  chromascii  ▶  demo.mp4   00:12 / 00:32   24fps   120×40   [q] stop
```

`q`/`Esc` stops and returns to the menu; **spacebar** pauses/resumes video (audio included, exact position preserved).

### Extras

- **Themes** — 16 accent-color pairs (violet, sunset, matrix, synthwave, ocean, forest, rose, amber, ice, grape, fire, mint, candy, nord, mono, cyberpunk). Press `t` to cycle; a theme-of-the-day is auto-picked until you choose one manually.
- **Help screen** — press `?` from the main menu for a key reference.
- **Idle easter eggs** — after ~40s idle on the launcher, a small dancing pet (cat, dog, bunny, or penguin) appears; after ~60s, a full-screen screensaver kicks in (matrix rain, vortex, plasma, or starfield — picked at random), dismissed with any key or mouse click. Typing `cat` on the help screen also summons the cat directly.
- **Session stats** — a rotating pool of status messages, ASCII-art trivia, and media-type counters (videos/gifs/images/webcam sessions watched) tracked persistently between runs.

---

## CLI reference

```
chromascii [file-or-url] [options]
chromascii --webcam [options]
```

| Flag | Type | Default | Description |
|---|---|---|---|
| `file` | path / URL | — | Image, video, GIF, or link to render |
| `--webcam` | flag | off | Stream from the default camera (device 0) |
| `--width N` | int | terminal width | Render width in characters |
| `--fps N` | float | source FPS | Override playback frame rate |
| `--chars STR` | string | `@#$%&*+=-:. ` | Custom charset string (`ascii` detail mode only) |
| `--color MODE` | string | auto-detected | `truecolor`, `256`, or `mono` |
| `--detail MODE` | string | `sextant` | `sextant`, `octant`, `braille`, `quadblock`, `halfblock`, or `ascii` |
| `--dither` | flag | off | Ordered (Bayer) dithering for smoother gradients (`ascii` mode) |
| `--loop` | flag | off | Loop video / GIF playback |
| `--no-audio` | flag | off | Disable audio playback for video |
| `--export PATH` | path | — | Also record the rendered output to a video file |
| `--virtual-cam` | flag | off | Also feed output to a virtual camera (needs `pyvirtualcam` + OBS) |

### Examples

```bash
chromascii photo.jpg                              # image, auto settings
chromascii photo.jpg --color mono                 # grayscale ASCII
chromascii clip.mp4 --detail octant --width 160   # sharpest engine, high width
chromascii clip.mp4 --loop --color 256            # looping, 256-color
chromascii clip.gif --loop                        # animated GIF
chromascii "https://tenor.com/..."                # link, auto-downloaded & cached
chromascii --webcam --detail sextant              # live webcam, sextant engine
chromascii --webcam --virtual-cam                 # webcam → Discord
chromascii clip.mp4 --detail ascii --chars "█▓▒░ " --dither   # classic dithered ASCII
chromascii clip.mp4 --export out.mp4 --no-audio   # silent render-to-file
```

---

## Charsets

Used only by the `ascii` detail mode — maps luminance (0–255) to a printable character. Darker pixels map to characters at the start of the string; brighter pixels to the end.

| Name | String | Notes |
|---|---|---|
| `default` | `@#$%&*+=-:. ` | Good all-round balance of density and detail |
| `blocks` | `█▓▒░ ` | Smooth gradients, mosaic look |
| `minimal` | `@. ` | High contrast, minimal noise |
| `custom` | any string | Pass via `--chars` in CLI or enter in settings |

`--dither` applies a tiled 4×4 Bayer matrix to the luminance before quantization, breaking up banding on smooth gradients at the cost of a slightly grainier look — cheap and fully vectorized, unlike sequential Floyd–Steinberg dithering.

---

## Color modes

| Mode | Flag | ANSI sequence | Notes |
|---|---|---|---|
| **Truecolor** | `--color truecolor` | `\033[38;2;R;G;Bm` | 16 million colors. Best quality. |
| **256-color** | `--color 256` | `\033[38;5;Nm` | Nearest xterm-256 palette entry. Wider compatibility. |
| **Mono** | `--color mono` | *(none)* | Pure ASCII shading, no color. Always uses the `ascii` detail engine. |

Auto-detected at startup from `$COLORTERM`, `$WT_SESSION`/`$ConEmuANSI`, and `$TERM`; override with `--color` if detection is wrong.

---

## Links & downloads

Pass a URL anywhere a file path is expected — CLI argument, TUI "paste path", or drop it directly into `chromascii <url>`.

1. **Direct media links** (a URL that already points at a `.jpg`/`.gif`/`.mp4`/etc., or whose response `Content-Type` says so — common for Imgur/Tenor direct links) are streamed straight to disk.
2. Everything else — YouTube, TikTok, and any site [yt-dlp](https://github.com/yt-dlp/yt-dlp) supports — is resolved via `yt_dlp.YoutubeDL` used as a library, format `best[ext=mp4]/best` (chosen specifically to avoid needing a separate ffmpeg merge step).
3. Downloads are cached on disk, keyed by `sha1(url)`, under `%LOCALAPPDATA%\chromascii\cache` (Windows) or `~/.cache/chromascii` (Linux/macOS) — pasting the same link again is instant.

---

## Audio sync

Video audio is decoded with [PyAV](https://pyav.org/) (no system `ffmpeg` binary required) and streamed to the output device via `sounddevice`. It's on by default; disable per-run with `--no-audio`, or leave the `av`/`sounddevice` packages uninstalled to disable it globally (playback still works, silently).

The video clock is audio-driven whenever audio is playing, so frame timing tracks the audio stream rather than drifting independently. Spacebar pause/resume seeks the audio stream to the exact frame position before resuming — no restart, no desync.

---

## Supported formats

| Type | Extensions | Engine | Notes |
|---|---|---|---|
| Image | `.jpg` `.jpeg` `.png` `.bmp` `.webp` | PIL / Pillow | Renders once, re-renders on terminal resize |
| Video | `.mp4` `.mov` `.avi` `.webm` | OpenCV + PyAV (audio) | Frame-accurate timing via `CAP_PROP_POS_MSEC` |
| Animated GIF | `.gif` | PIL ImageSequence | Respects per-frame delays and native loop count |
| Webcam | device 0 | OpenCV | Threaded capture, auto-reconnect, up to 60fps |
| Web links | any URL | direct fetch or yt-dlp | Cached locally after first resolve |

---

## Webcam

```bash
chromascii --webcam
# or from the TUI: select [3] use webcam
```

The HUD shows connection state (`◉ Live: <device name>` / `◉ Not Connected  retrying…`), resolution, and — occasionally — a joke camera nickname instead of the real device name. Capture and render run on separate threads so a slow camera never blocks the render loop, paced to the configured target FPS (up to 60, hardware permitting). Maximize your terminal window for a sharper result — more characters, more detail.

---

## Virtual camera

chromascii can act as a virtual webcam for Discord, Zoom, Google Meet, OBS, and any app that accepts a webcam input — a 2560×1440 pixelated mosaic, each terminal character rendered as a 16×16 pixel colored block with a subtle dark grid, streamed at up to 60fps.

### Setup

1. **Install OBS Studio** ([obsproject.com](https://obsproject.com)) — its bundled virtual camera driver is what apps actually see. Open OBS once and click **Start Virtual Camera** to activate the driver (once per session, or set it to auto-start).
2. **Install pyvirtualcam**: `pip install pyvirtualcam`
3. **Run**: `chromascii --webcam --virtual-cam` (or toggle **virtual cam → on** in the TUI webcam settings)

The HUD shows `◈ virt` next to the live indicator when active. In Discord: **Settings → Voice & Video → Camera → OBS Virtual Camera**.

| Property | Value |
|---|---|
| Resolution | 2560 × 1440 |
| Frame rate | up to 60 fps (matches `--fps`, capped at 60) |
| Cell grid | 160 × 90 |
| Block size | 16 × 16 px per character |

---

## Exporting video

`--export PATH` records the same 2560×1440 mosaic frames used for the virtual camera into an MP4 file (via OpenCV's `VideoWriter`) alongside normal terminal playback — no separate render pass needed:

```bash
chromascii clip.mp4 --export rendered.mp4
```

A short completion chime plays once the file is finalized.

---

## Terminal requirements

| Terminal | Platform | Truecolor | Notes |
|---|---|---|---|
| **Windows Terminal** | Windows | ✅ | Recommended on Windows |
| **iTerm2** | macOS | ✅ | Set `$COLORTERM=truecolor` |
| **Kitty** | Linux / macOS | ✅ | Native truecolor |
| **Alacritty / WezTerm** | Cross-platform | ✅ | |
| **GNOME Terminal / Hyper / VS Code terminal** | Cross-platform | ✅ | |
| **ConEmu / cmder** | Windows | ✅ | |
| Classic `cmd.exe` | Windows | ❌ | Use Windows Terminal instead |
| PuTTY (default) | Windows | ❌ | Falls back to 256-color |

On Windows, chromascii enables ANSI processing via the Console API (`SetConsoleMode + ENABLE_VIRTUAL_TERMINAL_PROCESSING`) and sets the output code page to UTF-8 at startup. No manual configuration required in Windows Terminal.

### Font requirements per engine

- `ascii`, `halfblock`, `quadblock` — any font with basic Unicode block support (essentially universal).
- `braille` — Braille Patterns block, extremely old and universally supported.
- `sextant` — Symbols for Legacy Computing (Unicode 13, 2020); most fonts updated since ~2021 have it (Cascadia Code, JetBrains Mono, Nerd Fonts).
- `octant` — Symbols for Legacy Computing Supplement (Unicode 16.0, 2024); needs a **very recently updated** font. If glyphs render as boxes/`?`, drop to `sextant` or `braille`.

If block characters appear as boxes, fall back to ASCII: `chromascii clip.mp4 --detail ascii --chars "@#$%&*+=-:. "`.

---

## Troubleshooting

**Command not found after install**
Add the Python Scripts directory to your PATH — see the [Windows PATH note](#windows-path-note), or run `python -m chromascii`.

**Block/octant characters render as boxes or `?`**
Your terminal font doesn't cover that Unicode block yet — see [font requirements](#font-requirements-per-engine) above, or switch `--detail`.

**Colors look wrong / no color**
Your terminal may not support truecolor. Try `--color 256` or `--color mono`.

**No audio during video playback**
Install the optional extras: `pip install chromascii[audio]`. Playback still works silently without them.

**Link fails to download**
Make sure `yt-dlp` is installed and up to date (`pip install -U yt-dlp`) — extractors for individual sites change frequently.

**Webcam shows "Not Connected"**
- Make sure no other application is using the camera
- On Windows: check **Settings → Privacy & Security → Camera**
- Chromascii reconnects automatically once the camera is available again

**Virtual camera not appearing in Discord**
- Confirm OBS is installed and **Start Virtual Camera** has been clicked at least once
- Confirm `pyvirtualcam` is installed: `pip show pyvirtualcam`
- Restart Discord after enabling the virtual camera

**Rendering is slow / low FPS**
- Try a lighter engine: `halfblock` or `quadblock` instead of `octant`/`braille`
- Use a smaller terminal window (fewer characters to render)
- `--color 256` is sometimes faster than truecolor depending on terminal

---

## Project structure

```
chromascii/
├── chromascii/
│   ├── main.py               entry point, CLI parsing, TUI orchestration
│   ├── utils.py               terminal I/O, keyboard/mouse input, color detection
│   ├── source.py               URL detection, direct fetch, yt-dlp, disk cache
│   ├── tui/
│   │   ├── launcher.py         animated welcome screen, menu, pets, screensavers
│   │   ├── picker.py           file browser with metadata
│   │   ├── settings.py         settings panel, playback HUD, webcam settings
│   │   ├── theme.py            color themes, theme-of-the-day, time tinting
│   │   ├── state.py            persistent stats (streaks, chars rendered, counters)
│   │   ├── messages.py         rotating status messages, trivia, farewells
│   │   └── sound.py            chime playback
│   └── renderer/
│       ├── engine.py           all rendering engines (numpy vectorized, RLE ANSI)
│       ├── image.py            static image renderer
│       ├── video.py            video/GIF renderer, frame timing, pause/resume
│       ├── webcam.py           threaded webcam capture and virtual camera
│       ├── audio.py            PyAV + sounddevice playback, position-accurate seek
│       └── export.py           mosaic-to-image conversion, MP4 export
├── requirements.txt
└── setup.py
```

---

## Dependencies

| Package | Purpose |
|---|---|
| `opencv-python` | Video decoding, webcam capture, MP4 export |
| `Pillow` | Image loading, GIF frame extraction, frame resizing |
| `numpy` | Vectorized rendering (all engines) |
| `rich` | TUI rendering — panels, tables, markup, live output |
| `colorama` | ANSI initialization on older Windows terminals |
| `yt-dlp` | Resolving non-direct video links (YouTube, TikTok, etc.) |
| `av` *(optional)* | Audio decoding for synchronized video playback |
| `sounddevice` *(optional)* | Audio output |
| `pyvirtualcam` *(optional)* | Virtual camera output for Discord / Zoom / OBS |

---

## License

MIT — see [LICENSE](LICENSE).
