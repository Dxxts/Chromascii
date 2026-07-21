<div align="center">

# chromascii

**Turn anything into art — real-time colored ASCII rendering in your terminal.**

<!-- demo gif here -->

![Python](https://img.shields.io/badge/python-3.8%2B-blue?style=flat-square)
![License](https://img.shields.io/badge/license-MIT-green?style=flat-square)
![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey?style=flat-square)

</div>

---

chromascii converts images, videos, GIFs, and live webcam feeds into colored ASCII art rendered directly in the terminal. Every pixel becomes a character; every character carries the original color via 24-bit ANSI escape codes. The result is rendered in real time, frame by frame, at playback speed.

It ships with a full interactive TUI launcher with animated menus, a file browser, and a settings panel — or you can skip all of that and pass a file path directly.

---

## Table of Contents

- [Features](#features)
- [How it works](#how-it-works)
- [Installation](#installation)
- [Quick start](#quick-start)
- [Interactive TUI](#interactive-tui)
- [CLI reference](#cli-reference)
- [Charsets](#charsets)
- [Color modes](#color-modes)
- [Supported formats](#supported-formats)
- [Webcam](#webcam)
- [Virtual camera (Discord / Zoom / OBS)](#virtual-camera)
- [Terminal requirements](#terminal-requirements)
- [Troubleshooting](#troubleshooting)
- [License](#license)

---

## Features

| Category | What it does |
|---|---|
| **Images** | JPEG, PNG, BMP, WebP — renders once, redraw on resize |
| **Video** | MP4, MOV, AVI, WebM — frame-accurate playback with FPS control |
| **GIF** | Respects native frame delays and loop count from metadata |
| **Webcam** | Live feed from the default camera, auto-reconnects if disconnected |
| **Virtual camera** | Feeds pixelated ASCII art into Discord / Zoom / OBS as a real webcam |
| **TUI launcher** | Animated startup screen, file browser, interactive settings panel |
| **Color** | Truecolor (24-bit), 256-color, or monochrome — auto-detected |
| **Charsets** | Four built-in presets plus custom strings |
| **Terminal resize** | Re-renders every frame at the current terminal dimensions |

---

## How it works

### Rendering pipeline

```
camera / file
     │
     ▼
 resize frame ──────────────────────────────────────────────────────────────────
     │        PIL LANCZOS resize to (terminal_cols, terminal_rows - 2)
     ▼
 luminance map ─────────────────────────────────────────────────────────────────
     │        L = (R×299 + G×587 + B×114) / 1000   (BT.601, numpy vectorized)
     ▼
 charset lookup ────────────────────────────────────────────────────────────────
     │        index = L × (len(charset) - 1) / 255
     │        char  = charset[index]               (numpy array indexing)
     ▼
 ANSI colorize ─────────────────────────────────────────────────────────────────
     │        truecolor:  \033[38;2;R;G;Bm{char}
     │        256-color:  \033[38;5;{xterm256}m{char}   (5-bit LUT)
     │        mono:       {char}
     ▼
 stdout write ──────────────────────────────────────────────────────────────────
              \033[H (cursor home) + full frame string + flush
```

### Frame timing

For video and GIF, each frame is timed against a `time.perf_counter()` baseline. If the render finishes early, the thread sleeps the remainder. If it runs late, the next frame starts immediately (no drift accumulation).

For video, the current playback position is read from `cv2.CAP_PROP_POS_MSEC` — the actual decoder timestamp — rather than estimated from a frame counter. This keeps the HUD timer accurate regardless of codec or variable frame rate.

### Webcam capture

Capture runs in a dedicated background thread that continuously reads frames into a `deque(maxlen=2)`. The render loop always takes the latest available frame without waiting for capture, which decouples the render rate from the camera's hardware frame rate and eliminates stutter.

```
┌─ capture thread ──┐       ┌─ render thread (main) ──┐
│  cap.read() loop  │──────▶│  deque[-1] → render      │
│  deque.append()   │       │  stdout.write()           │
└───────────────────┘       └──────────────────────────┘
```

The camera name is resolved asynchronously via a second background thread (PowerShell `Get-PnpDevice` on Windows, `v4l2-ctl` on Linux) so the UI starts instantly.

### Virtual camera output

When `--virtual-cam` is enabled, each webcam frame is also rendered as a 1280×720 image and sent to a virtual camera driver:

1. Source frame → resize to 80×45 (the "character grid")
2. Each cell → upscale to 16×16 px block with the cell's average color
3. Grid lines darkened at block boundaries → pixel-art / mosaic look
4. Output sent to `pyvirtualcam` at 20 fps

This output appears as a real webcam in any app (Discord, Zoom, OBS, Meet).

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

### Windows PATH note

On Windows with a user Python install, pip places `chromascii.exe` in a Scripts folder that may not be on your PATH. If the command is not found after install:

```powershell
# Find the Scripts folder
python -c "import sysconfig; print(sysconfig.get_path('scripts'))"

# Or for a user-level install
python -c "import site; print(site.getusersitepackages().replace('site-packages','Scripts'))"
```

Add the printed path to your user PATH via **System Properties → Environment Variables → Path → Edit → New**, then restart your terminal.

Alternatively, always invoke via:

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

# Play a video at 24 fps
chromascii clip.mp4 --fps 24

# Live webcam in 256-color mode
chromascii --webcam --color 256

# Live webcam + feed to Discord as virtual camera
chromascii --webcam --virtual-cam
```

---

## Interactive TUI

Running `chromascii` with no arguments opens the interactive launcher.

### Launcher

An animated startup screen types the title letter by letter with a rainbow gradient, then presents the main menu:

```
╭──────────────────────────────────────────────────╮
│                                                  │
│   ░▒▓   c h r o m a s c i i   ▓▒░               │
│           turn anything into art                 │
│                                                  │
╰──────────────────────────────────────────────────╯

    [1]  open file         pick an image, video or gif
    [2]  paste path        enter a file path manually
    [3]  use webcam        live ASCII from camera
     q   quit
```

Press `1`, `2`, `3`, or `q`.

### File browser

Selecting **open file** opens an inline file browser:

```
╭ open file  ~/Desktop/media ─────────────────────╮

    📁  ..
    📁  clips/
  ▶ 🖼   sunset.jpg     4.2 MB  3840×2160
    🎞   demo.mp4      18.4 MB  1920×1080  0:32
    🎞   loop.gif       2.1 MB   640×480   1.2s

  ↑↓ navigate   ⏎ select   ⌫ go up   q cancel
```

| Key | Action |
|---|---|
| `↑` / `↓` | Move selection |
| `Enter` | Open folder / select file |
| `Backspace` | Go up one directory |
| `1`–`9` | Jump to that numbered entry |
| `q` / `Esc` | Cancel |

File metadata is shown inline: image dimensions, video resolution and duration, GIF size and playback length.

### Settings panel

After selecting a file (or choosing webcam), a settings panel appears before playback starts:

```
╭ chromascii ──────────────────────────────────────╮
│  file    demo.mp4                                │
│  mode    ── video ──                             │
╰──────────────────────────────────────────────────╯

  ▶ width     ████████████░░░░░░░░░░░░░░   80 chars
    fps       ███████░░░░░░░░░░░░░░░░░░░   24 fps
    charset   [@#$%&*+=-. ]  default
    color     truecolor      24-bit ANSI
    loop      on

  ↑↓ navigate   ← → adjust   tab cycle   space toggle   ⏎ play   q back
```

| Key | Action |
|---|---|
| `↑` / `↓` | Move between settings rows |
| `←` / `→` | Adjust **width** (±5) or **fps** (±1) |
| `Tab` | Cycle **charset** or **color** mode |
| `Space` | Toggle **loop** on/off |
| `Enter` | Start playback |
| `q` / `Esc` | Go back to menu |

Rows that don't apply to the current file type are dimmed (e.g., fps and loop for images).

### Playback HUD

During playback, a status bar is pinned to the bottom of the terminal:

```
  chromascii  ▶  demo.mp4   00:12 / 00:32   24fps   120×40   [q] stop
```

Press `q` or `Esc` at any time to stop and return to the menu.

---

## CLI reference

```
chromascii [file] [options]
chromascii --webcam [options]
```

| Flag | Type | Default | Description |
|---|---|---|---|
| `file` | path | — | Image, video, or GIF to render |
| `--webcam` | flag | off | Stream from the default camera (device 0) |
| `--width N` | int | terminal width | Render width in characters |
| `--fps N` | float | source FPS | Override playback frame rate |
| `--chars STR` | string | `@#$%&*+=-:. ` | Custom charset string |
| `--color MODE` | string | auto-detected | Color mode: `truecolor`, `256`, or `mono` |
| `--loop` | flag | off | Loop video / GIF playback |
| `--virtual-cam` | flag | off | Also feed output to virtual camera (needs `pyvirtualcam` + OBS) |

### Examples

```bash
chromascii photo.jpg                              # image, auto settings
chromascii photo.jpg --color mono                 # grayscale ASCII
chromascii clip.mp4 --fps 30 --width 160          # video, high quality
chromascii clip.mp4 --loop --color 256            # looping, 256-color
chromascii clip.gif --loop                        # animated GIF
chromascii --webcam                               # live webcam
chromascii --webcam --virtual-cam                 # webcam → Discord
chromascii clip.mp4 --chars "█▓▒░ "              # blocks charset
chromascii clip.mp4 --chars "@. "                # minimal charset
```

---

## Charsets

A charset maps luminance (0–255) to a printable character. Darker pixels → characters at the start of the string; brighter pixels → characters at the end.

| Name | String | Notes |
|---|---|---|
| `default` | `@#$%&*+=-:. ` | Good all-round balance of density and detail |
| `blocks` | `█▓▒░ ` | Smooth gradients, mosaic look |
| `minimal` | `@. ` | High contrast, minimal noise |
| `custom` | any string | Pass via `--chars` in CLI or enter in settings |

Custom example:

```bash
chromascii photo.jpg --chars "▓▒░·  "
chromascii photo.jpg --chars "01"
chromascii photo.jpg --chars "CHROMASCII "
```

---

## Color modes

| Mode | Flag | ANSI sequence | Notes |
|---|---|---|---|
| **Truecolor** | `--color truecolor` | `\033[38;2;R;G;Bm` | 16 million colors. Best quality. Requires a modern terminal. |
| **256-color** | `--color 256` | `\033[38;5;Nm` | Maps RGB to the nearest xterm-256 palette entry. Wider compatibility. |
| **Mono** | `--color mono` | *(none)* | Pure ASCII shading, no color. Works in any terminal. |

The color mode is auto-detected at startup:

1. Check `$COLORTERM` — if `truecolor` or `24bit` → use truecolor
2. Check `$WT_SESSION` (Windows Terminal) or `$ConEmuANSI` → truecolor
3. Check `$TERM` for `256color` → 256
4. Default → attempt truecolor

Override with `--color` if the detection is wrong.

---

## Supported formats

| Type | Extensions | Engine | Notes |
|---|---|---|---|
| Image | `.jpg` `.jpeg` `.png` `.bmp` `.webp` | PIL / Pillow | Renders once, re-renders on terminal resize |
| Video | `.mp4` `.mov` `.avi` `.webm` | OpenCV | Frame-accurate timing via `CAP_PROP_POS_MSEC` |
| Animated GIF | `.gif` | PIL ImageSequence | Respects per-frame delays and native loop count |
| Webcam | device 0 | OpenCV | Threaded capture, auto-reconnect |

---

## Webcam

```bash
chromascii --webcam
# or from the TUI: select [3] use webcam
```

### Connection states

The HUD shows the camera state at all times:

| HUD indicator | Meaning |
|---|---|
| `◉ Not Connected  retrying…` | Camera not detected or busy — keeps retrying every 0.5 s |
| `◉ Live: Integrated Camera` | Camera is connected and streaming — shows the device's friendly name |

The camera name is resolved in the background (PowerShell `Get-PnpDevice` on Windows, `v4l2-ctl` on Linux) and appears in the HUD once available.

### Resolution

The webcam render fills the entire terminal window. Larger terminal = more characters = sharper output. Press `q` to stop.

> **Tip:** Maximize your terminal for best quality. A 220×60 terminal gives roughly 6× more characters than a 99×30 window.

---

## Virtual camera

chromascii can act as a virtual webcam for Discord, Zoom, Google Meet, OBS, and any other app that accepts a webcam input. The output is a 1280×720 pixelated mosaic — each terminal character becomes a solid 16×16 pixel colored block with a subtle dark grid.

### Setup

**Step 1 — Install OBS Studio**

OBS ships with a built-in virtual camera driver since v26.1.
Download at [obsproject.com](https://obsproject.com). You do not need to use OBS itself — just installing it registers the virtual camera driver.

After installing, open OBS once and click **Start Virtual Camera** to activate the driver. You only need to do this once per Windows session (or set it to start automatically).

**Step 2 — Install pyvirtualcam**

```bash
pip install pyvirtualcam
```

**Step 3 — Run chromascii**

```bash
chromascii --webcam --virtual-cam
```

Or from the TUI: webcam → settings → toggle **virtual cam → on** → Enter.

When active, the HUD shows `◈ virt` next to the live indicator.

### In Discord

1. Open Discord → **Settings → Voice & Video → Camera**
2. Select **OBS Virtual Camera** from the dropdown
3. Start a video call — your feed will be the live ASCII art

### Output specification

| Property | Value |
|---|---|
| Resolution | 1280 × 720 |
| Frame rate | 20 fps |
| Format | RGB (sent to `pyvirtualcam`) |
| Cell size | 16 × 16 px per character |
| Grid | Character grid (80 cols × 45 rows) |

---

## Terminal requirements

| Terminal | Platform | Truecolor | Notes |
|---|---|---|---|
| **Windows Terminal** | Windows | ✅ | Recommended on Windows |
| **iTerm2** | macOS | ✅ | Set `$COLORTERM=truecolor` |
| **Kitty** | Linux / macOS | ✅ | Native truecolor |
| **Alacritty** | Cross-platform | ✅ | |
| **WezTerm** | Cross-platform | ✅ | |
| **GNOME Terminal** | Linux | ✅ | |
| **Hyper** | Cross-platform | ✅ | |
| **VS Code terminal** | Cross-platform | ✅ | |
| **ConEmu / cmder** | Windows | ✅ | |
| Classic `cmd.exe` | Windows | ❌ | Use Windows Terminal instead |
| PuTTY (default) | Windows | ❌ | Falls back to 256-color |

On Windows, chromascii enables ANSI processing via the Console API (`SetConsoleMode + ENABLE_VIRTUAL_TERMINAL_PROCESSING`) and sets the output code page to UTF-8 (65001) at startup. No manual configuration required if using Windows Terminal.

### Font requirements

Block charset (`█▓▒░`) and the cursor indicator (`▶`) require a font with full Unicode block coverage. Recommended:

- **Cascadia Code / Mono** (default in Windows Terminal)
- **JetBrains Mono**
- **Fira Code**
- Any [Nerd Font](https://www.nerdfonts.com)

If block characters appear as boxes, fall back to the default ASCII charset:

```bash
chromascii clip.mp4 --chars "@#$%&*+=-:. "
```

---

## Troubleshooting

**Command not found after install**
Add the Python Scripts directory to your PATH. See the [Windows PATH note](#windows-path-note) above, or run `python -m chromascii` instead.

**Block characters render as boxes or `?`**
Your terminal font doesn't include Unicode block elements. Install Cascadia Code or any Nerd Font, or use `--chars "@#$%&*+=-:. "`.

**Colors look wrong / no color**
Your terminal may not support truecolor. Try `--color 256` or `--color mono`.

**Video plays but the timer doesn't advance**
Update opencv-python: `pip install -U opencv-python`. Older versions can report incorrect `CAP_PROP_POS_MSEC` on some codecs.

**Webcam shows "Not Connected"**
- Make sure no other application is currently using the camera
- On Windows: check **Settings → Privacy & Security → Camera** and ensure app access is allowed
- Try unplugging and replugging the camera; chromascii will reconnect automatically

**Virtual camera not appearing in Discord**
- Confirm OBS is installed and you have clicked **Start Virtual Camera** at least once
- Confirm `pyvirtualcam` is installed: `pip show pyvirtualcam`
- Restart Discord after enabling the virtual camera

**Rendering is slow / low FPS**
- Use a smaller terminal window (fewer characters to render)
- Try `--color 256` — it's faster than truecolor on some setups
- Use `--chars "@. "` (shorter charset = simpler indexing, negligible gain)
- The bottleneck is almost always Python string building; this is expected

---

## Project structure

```
chromascii/
├── chromascii/
│   ├── main.py              entry point, CLI parsing, TUI orchestration
│   ├── utils.py             terminal I/O, keyboard input, color detection
│   ├── tui/
│   │   ├── launcher.py      animated welcome screen and main menu
│   │   ├── picker.py        file browser with metadata
│   │   └── settings.py      settings panel, playback HUD, webcam settings
│   └── renderer/
│       ├── engine.py        core ASCII + ANSI rendering (numpy vectorized)
│       ├── image.py         static image renderer
│       ├── video.py         video and GIF renderer with frame timing
│       └── webcam.py        threaded webcam capture and virtual camera
├── SETUP.md                 detailed setup and troubleshooting guide
├── requirements.txt
└── setup.py
```

---

## Dependencies

| Package | Purpose |
|---|---|
| `opencv-python` | Video decoding, webcam capture |
| `Pillow` | Image loading, GIF frame extraction, frame resizing |
| `numpy` | Vectorized luminance computation and charset mapping |
| `rich` | TUI rendering — panels, tables, markup, live output |
| `colorama` | ANSI initialization on older Windows terminals |
| `pyvirtualcam` *(optional)* | Virtual camera output for Discord / Zoom / OBS |

---

## License

MIT — see [LICENSE](LICENSE).
