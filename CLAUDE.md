# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Whispr Clone is a macOS voice dictation tool that provides offline, system-wide speech-to-text using OpenAI's Whisper model via faster-whisper. It runs as a background service and supports two recording modes:

- **Press-and-Hold**: Hold Right Control to record, release to transcribe
- **Toggle Mode**: Press Right Control + Space to start recording, Right Control to stop

The application is built as a standalone macOS .app bundle using py2app and can run as a LaunchAgent for auto-start on login.

## Architecture

### Single-File Design
The entire application logic lives in `whispr_clone.py` (~500 lines). This is intentional - the app is meant to be simple and self-contained.

### Key Components
1. **State Management**: `AppState` class tracks recording mode, audio buffer, and key states
2. **Audio Pipeline**: sounddevice → numpy buffer → faster-whisper → text output
3. **Keyboard Handling**: pynput listens for hotkey combinations and types transcribed text
4. **Threading Model**: Audio callback runs in stream thread, transcription in separate daemon thread
5. **Logging**: Dual handlers (console + rotating file) for both terminal and background service modes

### Recording State Machine
```
None → [Right Control press] → Hold Mode → [Right Control release] → Transcribe → None
None → [Right Control + Space] → Toggle Mode → [Right Control press] → Transcribe → None
```

## Development Commands

### Environment Setup
```bash
# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# First run downloads Whisper model (~150MB for 'base')
python3 whispr_clone.py
```

### Running the Application

#### Development/Testing (Terminal Mode)
```bash
source venv/bin/activate
python3 whispr_clone.py
```

#### Build and Install as App Bundle
```bash
# Build .app bundle with py2app (takes 2-5 minutes)
python3 setup.py py2app

# App bundle will be at: dist/Whispr.app
```

#### Install as Background Service
```bash
# One-command install (builds + installs + starts service)
./scripts/install_service.sh

# Check service status
./scripts/check_status.sh

# Uninstall service
./scripts/uninstall_service.sh
```

### Log Locations
- Application logs: `~/Library/Logs/Whispr/whispr.log`
- System stdout: `~/Library/Logs/Whispr/stdout.log`
- System stderr: `~/Library/Logs/Whispr/stderr.log`

### Testing
There are no automated tests. Manual testing involves:
1. Run `python3 whispr_clone.py` in terminal
2. Open TextEdit or any text editor
3. Test press-and-hold: Hold Right Control, say "hello world", release
4. Test toggle mode: Press Right Control + Space, say "testing toggle mode", press Right Control
5. Verify text appears within 1-3 seconds

Test with `test_components.py` and `test_keys.py` for basic functionality checks.

## Important Technical Details

### py2app Build Process
- **setup.py** configures the entire build
- **Packages explicitly included**: numpy, sounddevice, faster_whisper, ctranslate2, onnxruntime, pynput
- **Critical setting**: `LSUIElement: True` makes it run without Dock icon (background agent)
- **Permissions**: NSMicrophoneUsageDescription and NSAppleEventsUsageDescription required in plist
- Build artifacts: `build/` (temporary), `dist/Whispr.app` (final bundle)

### App Bundle Structure
```
dist/Whispr.app/
├── Contents/
│   ├── Info.plist           # Bundle metadata (generated from setup.py)
│   ├── MacOS/Whispr         # Executable wrapper
│   └── Resources/           # Python runtime + all dependencies
```

### LaunchAgent Installation
The `install_service.sh` script:
1. Builds the .app bundle via `python3 setup.py py2app`
2. Copies to `/Applications/Whispr.app`
3. Generates `~/Library/LaunchAgents/com.whispr.dictation.plist`
4. Loads with `launchctl load`

The plist configures:
- `RunAtLoad: true` - auto-start on login
- `KeepAlive: {SuccessfulExit: false}` - restart if crashes
- Redirects stdout/stderr to log files

### macOS Permissions
The app requires two permissions that must be granted to **"Whispr"** (the app bundle), not Python/Terminal:

1. **Microphone** (Privacy & Security → Microphone) - for audio recording
2. **Accessibility** (Privacy & Security → Accessibility) - for typing transcribed text

After first install, macOS will prompt for these. If previously granted to Python/Terminal, they must be re-granted to the Whispr app.

## Configuration

All configuration is in `whispr_clone.py` constants (lines 86-112):

### Key Settings
```python
WHISPER_MODEL = "small"      # Model size: tiny, base, small, medium, large
DEBUG = True                 # Verbose logging (set False for production)
HOTKEY = Key.ctrl            # Recording trigger (change if no Right Control)
TOGGLE_KEY = Key.space       # Toggle mode activator
MIN_RECORDING_DURATION = 0.5 # Reject recordings shorter than this
```

### Model Selection Trade-offs
- `tiny` (75MB): Fastest, ~1GB RAM, lower accuracy
- `base` (150MB): Good balance, ~1GB RAM
- `small` (500MB): Better accuracy, ~2GB RAM
- `medium` (1.5GB): High accuracy, ~5GB RAM, slow on CPU
- `large` (3GB): Best accuracy, ~10GB RAM, very slow on CPU

Recommendation: Use `base` for development, `small` for production.

### Hotkey Customization
Some keyboards (especially laptops) lack Right Control. To change:
```python
HOTKEY = Key.f13          # Use F13 instead
HOTKEY = Key.cmd_r        # Use Right Command
HOTKEY = Key.alt_r        # Use Right Option
```

## Common Workflows

### Adding a New Recording Mode
1. Add mode to `AppState.__init__()` mode tracking
2. Modify `on_press()` to detect mode activation
3. Modify `on_release()` to handle mode deactivation
4. Update state transitions in both functions

### Changing Whisper Parameters
Edit `transcribe_and_type()` function (line 279):
```python
segments, info = state.whisper_model.transcribe(
    audio_float,
    language="en",    # Change language here
    beam_size=5,      # Increase for better accuracy (slower)
    vad_filter=True   # Voice Activity Detection
)
```

### Adding Post-Processing
Insert text transformations in `transcribe_and_type()` after line 287:
```python
text = "".join(segment.text for segment in segments).strip()

# Add transformations here:
text = text.replace("comma", ",")
text = text.capitalize()
```

### Building with Icon
Modify `setup.py` OPTIONS dict:
```python
'iconfile': 'path/to/icon.icns',  # Add to OPTIONS dict
```
Icon must be .icns format (macOS icon). Use `iconutil` or online converters to create from PNG/SVG.

## Debugging Issues

### Service Won't Start
```bash
./scripts/check_status.sh           # Check if running
tail -50 ~/Library/Logs/Whispr/stderr.log  # View errors
```

### No Text Appears After Dictation
- Check Accessibility permissions granted to "Whispr"
- Logs will show "Transcription: [text]" but text won't type

### Model Download Fails
```bash
# Manually download model while venv is active
source venv/bin/activate
python3 -c "from faster_whisper import WhisperModel; WhisperModel('base')"
```

### Rebuild After Code Changes
```bash
# Clean build (required after changing whispr_clone.py)
rm -rf build dist
python3 setup.py py2app

# Reinstall service (automatically rebuilds)
./scripts/install_service.sh
```

## Project Dependencies

### Core Runtime Dependencies
- **faster-whisper**: Whisper inference engine (uses ctranslate2 for speed)
- **sounddevice**: Cross-platform audio I/O (wraps PortAudio)
- **pynput**: Keyboard monitoring and control (macOS uses PyObjC frameworks)
- **numpy**: Audio buffer manipulation

### Build-Only Dependencies
- **py2app**: Creates standalone macOS app bundles
- **pyobjc-***: macOS framework bindings (installed by pynput)

### System Dependencies
- **PortAudio**: Must be installed via `brew install portaudio`

## File Structure

```
whispr-flow-copy/
├── whispr_clone.py          # Main application (all logic here)
├── setup.py                 # py2app build configuration
├── requirements.txt         # Python dependencies
├── README.md               # User documentation
├── scripts/
│   ├── install_service.sh   # Build + install as LaunchAgent
│   ├── uninstall_service.sh # Remove LaunchAgent
│   ├── check_status.sh      # Show service status + logs
│   └── verify_bundle.sh     # Validate .app bundle contents
├── build/                   # Temporary build artifacts (git-ignored)
├── dist/                    # Final .app bundle (git-ignored)
│   └── Whispr.app/
└── venv/                    # Virtual environment (git-ignored)
```

## Notes for Future Development

### Adding GUI/Menu Bar Icon
Would require adding PyObjC code to create NSStatusItem. Not currently implemented to keep app lightweight.

### GPU Acceleration
faster-whisper supports CUDA on NVIDIA GPUs, but macOS lacks CUDA support. Metal acceleration would require different backend.

### Streaming Transcription
Current implementation waits for full recording before transcribing. Streaming would require different Whisper wrapper (e.g., whisper-streaming).

### Multi-Language Support
Change `language="en"` to `language=None` for auto-detection, or specific language code. Affects speed (auto-detect is slower).
