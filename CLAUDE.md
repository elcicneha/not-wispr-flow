# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Whispr Clone is a macOS voice dictation tool providing offline, system-wide speech-to-text using faster-whisper. It runs as a background app with a menu bar icon and supports two recording modes:

- **Press-and-Hold**: Hold Right Control to record, release to transcribe
- **Toggle Mode**: Press Right Control + Space to start recording, Right Control to stop

## Development Commands

```bash
# Setup
python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt
brew install portaudio  # required system dependency

# Run in terminal (development)
source venv/bin/activate
python3 whispr_clone.py

# Build .app bundle
rm -rf build dist && python3 setup.py py2app
# Output: dist/Whispr.app

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
All application logic is in `whispr_clone.py` (~810 lines). This is intentional.

### Key Components
1. **`AppState`** — Global state: recording mode, audio buffer, key states, thread lock
2. **Audio Pipeline** — `sounddevice.InputStream` → numpy buffer → `faster-whisper` → `pynput.keyboard.Controller.type()`
3. **Keyboard Handling** — `pynput.Listener` with `on_press`/`on_release` callbacks implementing a state machine
4. **Menu Bar** — `NSStatusBar` icon with Quit menu item via PyObjC (`QuitDelegate` + `setup_menu_bar()`)
5. **Main Loop** — `NSApplication.sharedApplication().run()` on main thread (required for macOS event loop)
6. **Health Monitor** — Background thread detecting stuck keys (>60s) and dead listener

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
- Packages explicitly bundled: numpy, sounddevice, pynput, faster_whisper, ctranslate2, onnxruntime, av, huggingface_hub, tokenizers
- `install_service.sh` code-signs with identity "Whispr Dev" to preserve macOS permissions across rebuilds

## Configuration

All config is in `whispr_clone.py` constants (lines ~98-125):

```python
WHISPER_MODEL = "small"              # tiny/base/small/medium/large
HOTKEY_KEYS = {Key.ctrl, Key.ctrl_r} # Set of keys that trigger recording
TOGGLE_KEY = Key.space               # Combine with hotkey for toggle mode
DEBUG = True                         # Verbose logging
MIN_RECORDING_DURATION = 0.5         # Reject short recordings (seconds)
MAX_RECORDING_DURATION = 300         # Safety limit (seconds)
DEBOUNCE_MS = 100                    # Key press debounce (milliseconds)
```

`HOTKEY_KEYS` is a **set** — pynput may report `Key.ctrl`, `Key.ctrl_r`, or `Key.ctrl_l` depending on macOS version/keyboard. The `is_hotkey(key)` function checks membership.

## Important Gotchas

- **macOS permissions** must be granted to the **app bundle** ("Whispr"), not Terminal/Python: Microphone + Accessibility + Input Monitoring (Privacy & Security)
- **Clean build required** after code changes: `rm -rf build dist` before `python3 setup.py py2app`
- **Exit code 0** on fatal errors is intentional — prevents LaunchAgent `KeepAlive` restart loops
- **PID file lock** (`~/Library/Logs/Whispr/whispr.pid`) prevents duplicate instances
- **Audio callback** uses non-blocking lock (`acquire(blocking=False)`) to avoid audio glitches
- **`stop_recording()`** snapshots the buffer before clearing — transcription thread owns its own copy, no shared state
- **Log files**: `~/Library/Logs/Whispr/whispr.log` (rotating, 10MB x 5), restricted permissions (0o700)
- Model sizes: `base` (150MB, ~1GB RAM) for dev, `small` (500MB, ~2GB RAM) for production

## Modifying the Code

### Adding a new recording mode
1. Add mode tracking to `AppState.__init__()`
2. Add activation logic in `on_press()` state machine
3. Add deactivation logic in `on_release()`
4. Update state transitions in both functions

### Changing Whisper parameters
Edit `transcribe_and_type()` — the `state.whisper_model.transcribe()` call accepts `language`, `beam_size`, `vad_filter`, etc.

### Adding text post-processing
Insert transformations in `transcribe_and_type()` after the line `text = "".join(segment.text for segment in segments).strip()`.
