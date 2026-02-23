# Not Wispr Flow

A free, offline voice-to-text tool for **macOS**. Hold a key, speak, release — your words get typed wherever your cursor is. Works in any app.

Everything runs locally on your machine. No cloud, no subscription, no data leaving your computer. It uses OpenAI's Whisper model through Apple's MLX framework, so transcription happens on your Mac's GPU.

> **This is a macOS-only app.** It relies on macOS-specific system APIs (Accessibility, AppKit, etc.) and Apple's MLX framework for GPU acceleration. It will not run on Windows or Linux.

---

## About this project

This was inspired by [Wispr Flow](https://wisprflow.ai/). I genuinely admire what they've built. This project doesn't come close to the level of quality and features they offer. But this gets the job done for free and runs entirely on your own machine. The tradeoff is it uses some of your RAM (~2-3GB) since the AI model sits in memory while the app is running.

---

## Quick start

You need a Mac with Apple Silicon (M1/M2/M3/M4).

### Setting up your Mac (skip what you already have)

**Install Homebrew** (a package manager for macOS — think of it as an app store for developer tools):

Open the Terminal app (search "Terminal" in Spotlight) and paste:
```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```
Follow the on-screen instructions. When it's done, close and reopen Terminal.

**Install Python and Git:**
```bash
brew install python git portaudio
```
This installs Python (the programming language this app is written in), Git (to download the code), and PortAudio (needed for microphone access).

### Installing the app

**Optional:** If you want the code in a specific folder (e.g. Documents, Desktop), open that folder in Finder, right-click on it, and select **"New Terminal at Folder"**. Otherwise, just open Terminal — the code will be downloaded to your home directory by default.

Then paste these commands:

```bash
git clone <your-repo-url>
cd not-wispr-flow
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Running it

```bash
source venv/bin/activate
python3 main.py
```

The first run downloads the Whisper model (~1.6GB). After that, startup takes a few seconds.

**Every time you want to use it**, open Terminal and run those two lines (`source venv/bin/activate` then `python3 main.py`). Or set it up as a background service (see the technical section below).

### Grant macOS permissions

macOS will prompt you — say yes to all of them. If it doesn't prompt, go to **System Settings > Privacy & Security** and manually enable these for Terminal (or whatever app you ran the command from):

- **Microphone** — so it can hear you
- **Accessibility** — so it can type text into other apps
- **Input Monitoring** — so it can detect the hotkey

If any of these are missing, things will silently not work. This is the #1 issue people run into.

---

## How to use it

Once it's running, click into any app where you want text to appear.

**Press-and-hold** (for quick dictation):
1. Hold **Right Control**
2. Speak
3. Release **Right Control**
4. Text appears at your cursor

**Toggle mode** (for longer, hands-free dictation):
1. Press **Right Control + Space** together to start recording
2. Speak as long as you want
3. Press **Right Control** again to stop
4. Text appears at your cursor

To quit, press `Ctrl+C` in the terminal.

---

## Troubleshooting

**Nothing happens when I press the hotkey** — Almost always a permissions issue. Double-check all three permissions (Microphone, Accessibility, Input Monitoring) in System Settings > Privacy & Security.

**I speak but no text appears** — Accessibility permission is probably missing.

**"Audio too short, skipping"** — You released the key too quickly. Hold it longer.

**Transcription is slow** — Try a smaller model (see the customization section below).

**Logs** — Check `~/Library/Logs/NotWisprFlow/notwisprflow.log` if something seems off.

---

## A note about Wispr Flow

Seriously, go check out [Wispr Flow](https://wisprflow.ai). It's a great product. If you want something that just works out of the box with a clean UI and you don't mind paying for it, use that instead. This project exists for people who want a free, local alternative and don't mind a little terminal work.

---

# Technical details

Everything below is for folks who want to customize, understand, or contribute to the project.

## Changing the Whisper model

Open [main.py](main.py) and find this line near the top (line 112):

```python
WHISPER_MODEL = "mlx-community/whisper-large-v3-turbo"
```

Replace it with any mlx-whisper compatible model from [HuggingFace's mlx-community](https://huggingface.co/mlx-community). Some options:

| Model | Download size | RAM usage | Tradeoff |
|-------|--------------|-----------|----------|
| `mlx-community/whisper-tiny` | ~75MB | ~1GB | Fastest, least accurate |
| `mlx-community/whisper-base` | ~150MB | ~1GB | Quick and decent |
| `mlx-community/whisper-small` | ~500MB | ~1.5GB | Good middle ground |
| `mlx-community/whisper-large-v3-turbo` | ~1.6GB | ~2.5GB | **Default** — best speed/accuracy tradeoff |
| `mlx-community/whisper-large-v3` | ~3GB | ~4GB | Most accurate, slower |

Restart the app after changing the model. It'll download the new one on first run.

## Changing the hotkey

If your keyboard doesn't have Right Control or you want a different trigger, find this line (line 137):

```python
HOTKEY_KEYS = {Key.ctrl, Key.ctrl_r}
```

Some alternatives:
```python
HOTKEY_KEYS = {Key.cmd_r}              # Right Command
HOTKEY_KEYS = {Key.alt_r, Key.alt}     # Right Option
HOTKEY_KEYS = {Key.f13}                # F13 key
```

## How it works

1. A keyboard listener (pynput) watches for the hotkey press/release
2. While the key is held, audio is captured from your microphone (sounddevice)
3. On release, the audio buffer is passed to mlx-whisper for transcription on the GPU
4. The transcribed text is typed at the cursor position using macOS Accessibility APIs

The whole app is a single Python file ([main.py](main.py)). The menu bar icon runs through macOS's AppKit via PyObjC.

## Running as a background service

If you don't want to keep a terminal window open:

```bash
# Install as a macOS LaunchAgent (auto-starts on login)
./scripts/install_service.sh

# Check if it's running
./scripts/check_status.sh

# Uninstall
./scripts/uninstall_service.sh
```

## Project structure

```
main.py                  — The entire app (single file)
requirements.txt         — Python dependencies
setup.py                 — py2app config for building a .app bundle
scripts/
  install_service.sh     — Build, sign, and install to /Applications
  uninstall_service.sh   — Remove the app and LaunchAgent
  check_status.sh        — Show whether the service is running
```

## Acknowledgments

- [Wispr Flow](https://wisprflow.ai) — the inspiration
- [OpenAI Whisper](https://github.com/openai/whisper) — the model that makes this possible
- [mlx-whisper](https://github.com/ml-explore/mlx-examples/tree/main/whisper) — GPU-accelerated Whisper for Apple Silicon
- [pynput](https://github.com/moses-palmer/pynput) — keyboard monitoring
- [sounddevice](https://python-sounddevice.readthedocs.io/) — audio capture
