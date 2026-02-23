# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Not Wispr Flow is a macOS voice dictation tool providing offline, system-wide speech-to-text using mlx-whisper with Silero VAD for silence detection. It runs as a background app with a menu bar icon and supports two recording modes:

- **Press-and-Hold**: Hold Right Control to record, release to transcribe
- **Toggle Mode**: Press Right Control + Space to start recording, Right Control to stop

## Development Commands

```bash
# Setup
python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt
brew install portaudio  # required system dependency

# Run in terminal (development)
source venv/bin/activate
python3 main.py

# Build .app bundle
rm -rf build dist && python3 setup.py py2app
# Output: dist/Not Wispr Flow.app

# Install to /Applications (builds + signs + installs)
./scripts/install_service.sh

# Uninstall (removes app, logs, build artifacts)
./scripts/uninstall_service.sh

# Check service status
./scripts/check_status.sh
```

There are no automated tests. Manual testing requires running the app and dictating into a text editor.

## Architecture

### Single-File Design
All application logic is in `main.py` (~810 lines). This is intentional.

### Key Components
1. **`AppState`** — Global state: recording mode, audio buffer, VAD model, key states, thread lock
2. **Audio Pipeline** — `sounddevice.InputStream` → numpy buffer → Silero VAD (silence check) → mlx-whisper → `pynput.keyboard.Controller.type()`
3. **Hallucination Prevention** — Silero VAD pre-filters silence, backup chars/sec check catches edge cases
4. **Keyboard Handling** — `pynput.Listener` with `on_press`/`on_release` callbacks implementing a state machine
5. **Menu Bar** — `NSStatusBar` icon with Quit menu item via PyObjC (`MenuDelegate` + `setup_menu_bar()`)
6. **Main Loop** — `NSApplication.sharedApplication().run()` on main thread (required for macOS event loop)
7. **Health Monitor** — Background thread detecting stuck keys (>60s) and dead listener

### Recording State Machine
```
None + hotkey press              → Hold mode, start recording
None + hotkey press (space held) → Toggle mode, start recording
None + space press (hotkey held) → Toggle mode, start recording
Hold + space press               → Convert to Toggle mode (recording continues)
Hold + hotkey release            → Stop recording, transcribe
Toggle + hotkey press            → Stop recording, transcribe
```

### Threading Model
- **Main thread**: macOS NSApplication run loop (menu bar, signal handling)
- **Audio callback thread**: `sounddevice` stream callback appends to buffer (non-blocking lock)
- **Transcription thread**: Spawned per recording, owns a snapshot of the audio buffer
- **Health monitor thread**: Daemon, checks listener and stuck key states every 5s
- **Keyboard listener thread**: `pynput.Listener`, runs via PyObjC event tap

### Build System
`setup.py` configures py2app. Key settings:
- `LSUIElement: True` — no Dock icon (background agent)
- Packages explicitly bundled: numpy, sounddevice, pynput, mlx_whisper, mlx, av, huggingface_hub, tokenizers, torch, silero-vad
- `install_service.sh` code-signs with identity "Not Wispr Flow Dev" to preserve macOS permissions across rebuilds

## Configuration

**User-facing settings** are in `config.py` (edit this file to customize):

```python
WHISPER_MODEL = "mlx-community/whisper-large-v3-turbo"  # Model selection
HOTKEY_KEYS = {Key.ctrl, Key.ctrl_r}  # Set of keys that trigger recording
TOGGLE_KEY = Key.space                # Combine with hotkey for toggle mode
DEBUG = False                         # Verbose logging
```

**Developer/internal constants** remain in `main.py` (technical settings):

```python
SAMPLE_RATE = 16000              # Whisper's native sample rate
MIN_RECORDING_DURATION = 0.2     # Reject short recordings (seconds)
DEBOUNCE_MS = 100                # Key press debounce (milliseconds)
FLUSH_BUFFER_THRESHOLD_MB = 5    # Buffer overflow threshold
CONTEXT_CHARS = 200              # Context window for transcription
```

`HOTKEY_KEYS` is a **set** — pynput may report `Key.ctrl`, `Key.ctrl_r`, or `Key.ctrl_l` depending on macOS version/keyboard. The `is_hotkey(key)` function checks membership.

## Important Gotchas

- **macOS permissions** must be granted to the **app bundle** ("Not Wispr Flow"), not Terminal/Python: Microphone + Accessibility + Input Monitoring (Privacy & Security)
- **Clean build required** after code changes: `rm -rf build dist` before `python3 setup.py py2app`
- **Silero VAD model** downloads automatically on first run (~6MB) via torch.hub, cached in `~/.cache/torch/hub/`
- **VAD is the primary hallucination filter** — pre-filters silence before mlx-whisper, backup chars/sec check catches edge cases
- **Exit code 0** on fatal errors is intentional — prevents LaunchAgent `KeepAlive` restart loops
- **PID file lock** (`~/Library/Logs/NotWisprFlow/notwisprflow.pid`) prevents duplicate instances
- **Audio callback** uses non-blocking lock (`acquire(blocking=False)`) to avoid audio glitches
- **`stop_recording()`** snapshots the buffer before clearing — transcription thread owns its own copy, no shared state
- **Log files**: `~/Library/Logs/NotWisprFlow/notwisprflow.log` (rotating, 10MB x 5), restricted permissions (0o700)
- Model sizes: Whisper `large-v3-turbo` (~1.6GB, ~2.3GB RAM), Silero VAD (~6MB, minimal RAM)

## Modifying the Code

### Adding a new recording mode
1. Add mode tracking to `AppState.__init__()`
2. Add activation logic in `on_press()` state machine
3. Add deactivation logic in `on_release()`
4. Update state transitions in both functions

### Changing Whisper parameters
Edit `transcribe_and_type()` — the `state.whisper_model()` call accepts the audio float array and returns text.

### Tuning VAD sensitivity
In `contains_speech()` function, adjust these parameters:
- `threshold` (0.3-0.6): Lower = more sensitive (catches quieter speech), higher = less false positives
- `min_speech_duration_ms`: Minimum speech segment duration to consider valid
- `min_silence_duration_ms`: Minimum silence duration to split segments

### Adding text post-processing
Insert transformations in `transcribe_and_type()` after the line `text = state.whisper_model(audio_float)`.
