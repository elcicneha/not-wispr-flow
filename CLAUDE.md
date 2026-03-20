# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Not Wispr Flow is a macOS voice dictation tool providing system-wide speech-to-text with hybrid online/offline support. It uses Groq API for fast cloud transcription when available, with local MLX Whisper as a fallback. Silero VAD handles silence detection. It runs as a background menu bar app with two recording modes:

- **Press-and-Hold**: Hold Control to record, release to transcribe
- **Toggle Mode**: Press Control + Space to start recording, Control to stop

## Development Commands

```bash
# Setup
python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt

# Run in terminal (development)
source venv/bin/activate
python3 main.py

# Build .app bundle
rm -rf build dist && python3 setup.py py2app

# Full install to /Applications (builds + signs + installs)
./scripts/install_service.sh

# One-step installer (end users or first-time setup)
./install.sh

# Uninstall
./uninstall.sh
```

No automated tests. Manual testing requires running the app and dictating into a text editor.

## Architecture

### Module Structure
- **`main.py`** — App shell: `AppState`, transcription pipeline, health monitor, entry point
- **`notwisprflow/config.py`** — User-facing settings (model, hotkeys, transcription mode, API keys, LLM prompts)
- **`notwisprflow/constants.py`** — Internal constants (e.g. `SAMPLE_RATE`). NOT for user-facing settings
- **`notwisprflow/keyboard_handler.py`** — Keyboard state machine: `create_handlers()` returns `(on_press, on_release)` closures
- **`notwisprflow/audio.py`** — Recording lifecycle, buffer overflow to disk, recording stats
- **`notwisprflow/menubar.py`** — All menu bar UI: icon manager, menu delegate, prompt panel, status updater
- **`notwisprflow/text_output.py`** — Text insertion (clipboard paste or CGEvent typing), cursor context via Accessibility APIs
- **`notwisprflow/permissions.py`** — macOS mic/accessibility permission checks
- **`notwisprflow/preferences.py`** — Prefs persistence (`~/.config/notwisprflow/preferences.json`) and `resolve_api_key()`
- **`notwisprflow/transcription.py`** — `TranscriptionManager`: MLX Whisper, Groq API, Silero VAD, connectivity monitor, model lifecycle
- **`notwisprflow/llm_processor.py`** — `LLMProcessor`: multi-provider dispatch (Gemini/Groq/OpenAI/Anthropic)
- **`notwisprflow/post_processing.py`** — LLM enhancement + smart spacing pipeline
- **`notwisprflow/startup.py`** — LaunchAgent plist management for start-at-login
- **`notwisprflow/media_control.py`** — Media pause/resume via macOS private `MediaRemote.framework`

### Dependency Graph (acyclic)
```
main.py → keyboard_handler, audio, menubar, text_output, permissions, preferences, startup
keyboard_handler → audio, text_output, config
audio → config, constants, media_control
menubar → config, preferences, text_output, startup
text_output, permissions, media_control, startup → standalone (no app imports)
transcription → constants, preferences
llm_processor → config, preferences
post_processing → llm_processor
```

### Key Patterns
- **Explicit state passing**: `AppState` passed as parameter to all modules — no hidden globals. Single thread lock
- **Callback DI**: `stop_recording(state, update_icon_fn, on_audio_ready_fn)` — audio doesn't know about transcription, avoids circular imports
- **Closures for pynput**: `create_handlers()` returns closures because pynput only accepts `(key)` signature
- **Audio pipeline**: `soundcard` → deque (lock-free, GIL-atomic) → VAD → transcribe → clipboard paste
- **Smart model management**: In auto mode, connectivity monitor unloads local model after 60s stable internet (~2.3GB freed), pre-loads when connectivity drops
- **NSObject subclasses** get `_state` attribute set after `alloc().init()` (PyObjC pattern)

### Recording State Machine
```
None + hotkey press              → Hold mode, start recording
None + hotkey press (space held) → Toggle mode, start recording
None + space press (hotkey held) → Toggle mode, start recording
Hold + space press               → Convert to Toggle mode (recording continues)
Hold + hotkey release            → Stop recording, transcribe
Toggle + hotkey press            → Stop recording, transcribe
```

Stuck-state recovery: if mode is set but not recording (stream crashed), next hotkey press salvages captured audio and resets.

### Threading Model
- **Main thread**: NSApplication manual event loop (0.5s timeout for Ctrl+C support)
- **Audio callback**: `soundcard` recorder, lock-free `deque.append()` — must never block
- **MLX worker**: Dedicated thread for all Metal/MLX GPU ops (avoids Metal threading assertions)
- **Transcription**: Per-recording thread, owns buffer snapshot (no shared state)
- **Connectivity monitor**: (auto mode) Checks internet every 30s, manages model load/unload
- **Health monitor**: Daemon, checks stream health every 5s
- **Keyboard listener**: `pynput.Listener` via PyObjC event tap

### Build System
`setup.py` configures py2app. `LSUIElement: True` (no Dock icon). Excludes torch/torchaudio/silero_vad (VAD uses numpy-only ONNX wrapper). `install_service.sh` code-signs and fixes MLX rpaths.

## Configuration

User-facing settings in `notwisprflow/config.py`. Internal constants stay in their respective modules.

Key non-obvious settings:
- `HOTKEY_KEYS` is a **set** — pynput may report `Key.ctrl`, `Key.ctrl_r`, or `Key.ctrl_l` depending on macOS/keyboard
- `TRANSCRIPTION_MODE`: `"auto"` (cloud with offline fallback), `"offline"`, or `"online"`
- `LLM_MODEL`: set to `"disabled"` to turn off. LLM only runs with online transcription, never offline
- `USE_TYPE_MODE`: `False` = clipboard paste (default), `True` = character-by-character typing

API key resolution order (via `resolve_api_key()`): config.py → env var → dotfile in `~/.config/notwisprflow/` (`api_key`, `gemini_api_key`, `openai_api_key`, `anthropic_api_key`). Runtime state (LLM model, prompt) persists in `~/.config/notwisprflow/preferences.json`.

## Important Gotchas

- **macOS permissions** go to the **app bundle** ("Not Wispr Flow"), not Terminal: Microphone + Accessibility + Input Monitoring
- **Clean build required** after code changes: `rm -rf build dist` before `python3 setup.py py2app`
- **MLX pinned to single thread** — all Metal/MLX calls go through `TranscriptionManager`'s dedicated worker queue
- **Audio callback must never block** — blocking I/O in the callback hangs `stream.stop()`
- **`stop_recording()` snapshots buffer** before clearing — transcription thread owns its copy
- **Text insertion** saves/restores clipboard via `NSPasteboard`, restores immediately to avoid clipboard manager capture
- **Media playing detection** uses `pmset -g assertions` because MediaRemote query APIs are broken for browser media on macOS Sequoia. Command APIs (PAUSE/PLAY) still work
- **Exit code 0** on fatal errors — intentional, prevents LaunchAgent restart loops
- **PID file lock**: `~/Library/Logs/NotWisprFlow/notwisprflow.pid`
- **Logs**: `~/Library/Logs/NotWisprFlow/notwisprflow.log` (rotating, 10MB x 5)

## Modifying the Code

### Adding a new recording mode
1. Add mode to `AppState.__init__()` in `main.py`
2. Add activation/deactivation in `on_press()`/`on_release()` in `keyboard_handler.py`
3. Add stuck-state recovery for the new mode

### Tuning VAD sensitivity
In `TranscriptionManager.contains_speech()`, adjust `_get_speech_timestamps_numpy()` params: `threshold` (0.3-0.6), `min_speech_duration_ms`, `min_silence_duration_ms`.

### Adding an LLM provider
Add provider in `llm_processor.py` (key resolution, client init, process method). Add models to `LLM_MODELS` in `config.py`. Add prompt presets to `LLM_PROMPTS` in `config.py`.

## Design Decisions Log (MANDATORY)

**After completing any task**, append a new entry to `DESIGN_DECISIONS.md`:

1. **What was done**
2. **What was explicitly NOT done and why**
3. **Alternatives considered**
4. **What was tried and didn't work** (include specifics)
5. **What worked and why**

Format: `## Section Title`, `**Decision: ...**`, bullet points, ending with `---`. Skip ONLY for purely informational tasks with zero code changes.
