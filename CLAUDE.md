# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Not Wispr Flow is a macOS voice dictation tool providing system-wide speech-to-text with hybrid online/offline support. It uses Groq API for fast cloud transcription when available, with local MLX Whisper as a fallback. Silero VAD handles silence detection. It runs as a background app with a menu bar icon and supports two recording modes:

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

# FAST development workflow (after first install)
./scripts/dev_install.sh
# Updates .py files in existing app bundle (~1 second vs ~30+ seconds)
# Use this for quick iteration when changing main.py or config.py

# Full install to /Applications (builds + signs + installs)
./scripts/install_service.sh
# Use this for: first install, dependency changes, or major changes

# Uninstall (removes app, logs, build artifacts)
./scripts/uninstall_service.sh

# Check service status
./scripts/check_status.sh
```

There are no automated tests. Manual testing requires running the app and dictating into a text editor.

## Architecture

### Multi-File Structure
- **`config.py`** — User-facing settings (model, hotkeys, transcription mode, Groq API key)
- **`transcription.py`** — All transcription logic: `TranscriptionManager` class, MLX Whisper backend, Groq API client, Silero VAD, connectivity monitoring, model lifecycle management
- **`main.py`** — App shell: AppState, keyboard handling, audio capture, menu bar, health monitor, entry point

### Key Components
1. **`TranscriptionManager`** — Unified transcription interface in `transcription.py`. Handles mode selection (offline/online/auto), Groq API calls, local MLX Whisper, VAD, and background model load/unload
2. **`AppState`** — Global state in `main.py`: recording mode, audio buffer, key states, thread lock, text insertion mode
3. **Audio Pipeline** — `sounddevice.InputStream` → numpy buffer (lock-free deque) → `TranscriptionManager.contains_speech()` → `TranscriptionManager.transcribe()` → clipboard paste (default)
4. **Smart Model Management** — In auto mode, a background connectivity monitor unloads the local model after 60s stable internet (frees ~2.3GB RAM) and pre-loads it immediately when connectivity drops
5. **Keyboard Handling** — `pynput.Listener` with `on_press`/`on_release` callbacks implementing a state machine with stuck-state recovery
6. **Menu Bar** — `NSStatusBar` icon with animated states (idle/recording/processing) via `MenuBarIconManager`, plus `MenuDelegate` for Retype Last, Paste Mode toggle, and Quit
7. **Cursor Context** — `get_cursor_context()` reads text around cursor via macOS Accessibility APIs for smart spacing
8. **Buffer Overflow** — Long recordings flush to `.npy` files on disk when buffer exceeds threshold; reassembled at transcription time
9. **Health Monitor** — Background thread detecting dead audio streams, stuck keys, and triggering buffer flushes

### Recording State Machine
```
None + hotkey press              → Hold mode, start recording
None + hotkey press (space held) → Toggle mode, start recording
None + space press (hotkey held) → Toggle mode, start recording
Hold + space press               → Convert to Toggle mode (recording continues)
Hold + hotkey release            → Stop recording, transcribe
Toggle + hotkey press            → Stop recording, transcribe
```

Stuck-state recovery: if mode is set but not recording (stream crashed), the next hotkey press salvages any captured audio and resets to idle.

### Threading Model
- **Main thread**: macOS NSApplication run loop (menu bar, signal handling)
- **Audio callback thread**: `sounddevice` stream callback appends to deque (lock-free, GIL-atomic)
- **MLX worker thread**: Dedicated thread for all MLX/Metal GPU operations (avoids Metal threading assertions); managed by `TranscriptionManager`
- **Transcription thread**: Spawned per recording, owns a snapshot of the audio buffer
- **Connectivity monitor thread**: (auto mode only) Checks internet every 30s, manages model load/unload with hysteresis
- **Health monitor thread**: Daemon, checks listener/stream health and flushes buffer every 5s
- **Keyboard listener thread**: `pynput.Listener`, runs via PyObjC event tap

### Build System
`setup.py` configures py2app. Key settings:
- `LSUIElement: True` — no Dock icon (background agent)
- Packages bundled: numpy, sounddevice, pynput, mlx_whisper, mlx, av, huggingface_hub, tokenizers, onnxruntime, groq
- Explicitly excluded: torch, torchaudio, silero_vad (VAD uses custom numpy-only ONNX wrapper instead)
- `install_service.sh` code-signs with identity "Not Wispr Flow Dev" to preserve macOS permissions across rebuilds
- `install_service.sh` fixes MLX library rpaths and moves `mlx.metallib` to Frameworks directory

## Configuration

**User-facing settings** are in `config.py` (edit this file to customize):

```python
WHISPER_MODEL = "mlx-community/whisper-large-v3-turbo"  # Model selection
LANGUAGE = None           # None = auto-detect all languages, "en" = English only
HOTKEY_KEYS = {Key.ctrl, Key.ctrl_r}  # Set of keys that trigger recording
TOGGLE_KEY = Key.space                # Combine with hotkey for toggle mode
TRANSCRIPTION_MODE = "auto"           # "auto", "offline", or "online"
GROQ_API_KEY = ""                     # Required for "online", optional for "auto"
GROQ_MODEL = "whisper-large-v3-turbo" # Groq Whisper model
USE_TYPE_MODE = False                 # False = paste mode (default), True = type mode
DEBUG = False                         # Verbose logging
```

**Developer/internal constants** remain in `main.py` (technical settings):

```python
SAMPLE_RATE = 16000              # Whisper's native sample rate
MIN_RECORDING_DURATION = 0.2     # Reject short recordings (seconds)
DEBOUNCE_MS = 100                # Key press debounce (milliseconds)
FLUSH_BUFFER_THRESHOLD_MB = 5    # Buffer overflow threshold
CONTEXT_CHARS = 200              # Context window for cursor context
```

`HOTKEY_KEYS` is a **set** — pynput may report `Key.ctrl`, `Key.ctrl_r`, or `Key.ctrl_l` depending on macOS version/keyboard. The `is_hotkey(key)` function checks membership.

## Important Gotchas

- **macOS permissions** must be granted to the **app bundle** ("Not Wispr Flow"), not Terminal/Python: Microphone + Accessibility + Input Monitoring (Privacy & Security)
- **Clean build required** after code changes: `rm -rf build dist` before `python3 setup.py py2app`
- **VAD uses ONNX runtime** — `SileroVADOnnx` class wraps the bundled `resources/silero_vad.onnx` model with numpy-only inference (no torch dependency)
- **MLX operations are pinned to a single thread** — `TranscriptionManager` spawns a dedicated MLX worker thread with a queue; all Metal/MLX calls happen there to avoid threading assertions
- **Groq API** sends audio as WAV bytes over HTTPS; timeout is 10s; free tier allows 20 requests/min, 2000/day
- **Text insertion uses clipboard paste by default** — controlled by `USE_TYPE_MODE` in config.py (False = paste, True = type). `insert_text()` saves/restores clipboard via `NSPasteboard`, restores immediately to avoid clipboard manager capture. Toggle at runtime via menu bar "Paste Mode" item
- **Exit code 0** on fatal errors is intentional — prevents LaunchAgent `KeepAlive` restart loops
- **PID file lock** (`~/Library/Logs/NotWisprFlow/notwisprflow.pid`) prevents duplicate instances
- **Audio callback must never block** — uses lock-free `deque.append()` (GIL-atomic); any blocking I/O in the callback hangs `stream.stop()`
- **`stop_recording()`** snapshots the buffer before clearing — transcription thread owns its own copy, no shared state
- **`_cleanup_stream()`** runs `stream.stop()`/`close()` in a background thread with 2s timeout to prevent deadlocking the main lock
- **Log files**: `~/Library/Logs/NotWisprFlow/notwisprflow.log` (rotating, 10MB x 5), restricted permissions (0o700)
- **Recording stats**: `recording_stats.jsonl` in the project directory — JSONL with duration, buffer size, mode, processing time per recording
- Model sizes: Whisper `large-v3-turbo` (~1.6GB, ~2.3GB RAM), Silero VAD ONNX (~6MB, minimal RAM)

## Modifying the Code

### Adding a new recording mode
1. Add mode tracking to `AppState.__init__()`
2. Add activation logic in `on_press()` state machine
3. Add deactivation logic in `on_release()`
4. Update state transitions in both functions
5. Add stuck-state recovery for the new mode in both handlers

### Changing Whisper parameters
Edit `_initialize_whisper()` in `transcription.py` — the `mlx_whisper.transcribe()` call inside `mlx_worker()` accepts additional keyword arguments. The returned result is a dict with a `"text"` key.

### Tuning VAD sensitivity
In `TranscriptionManager.contains_speech()` in `transcription.py`, adjust the parameters passed to `_get_speech_timestamps_numpy()`:
- `threshold` (0.3-0.6): Lower = more sensitive (catches quieter speech), higher = less false positives
- `min_speech_duration_ms`: Minimum speech segment duration to consider valid
- `min_silence_duration_ms`: Minimum silence duration to split segments

### Adding text post-processing
Insert transformations in `post_process()` which receives `(text, context_before, context_after)`. Currently handles smart spacing based on cursor context.

### Changing text insertion behavior
Set the default mode via `USE_TYPE_MODE` in config.py (False = clipboard paste, True = character-by-character typing). Users can toggle at runtime via the "Paste Mode" menu bar item. Modify `insert_text()` to change the implementation details.
