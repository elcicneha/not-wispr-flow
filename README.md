# Whispr Clone - Voice Dictation Tool for macOS

A lightweight, offline voice dictation tool for macOS that uses Whisper AI for speech-to-text transcription. Type anywhere using your voice with simple keyboard hotkeys.

## Features

- **Two Recording Modes:**
  - **Press-and-Hold**: Hold Right Control to record, release to transcribe
  - **Toggle/Hands-Free**: Press Right Control + Space to start, Right Control to stop

- **Offline Processing**: Uses faster-whisper for local transcription (no cloud services)
- **Universal**: Works in any macOS application (TextEdit, VSCode, browsers, etc.)
- **Fast**: Optimized with int8 quantization for CPU performance
- **Configurable**: Easy-to-modify settings at the top of the script

## Requirements

- **macOS**: 10.15 (Catalina) or newer
- **Python**: 3.9 or later
- **System Dependencies**: PortAudio (via Homebrew)
- **Architecture**: Supports both Intel (x86_64) and Apple Silicon (ARM64)

## Installation

### 1. Install System Dependencies

```bash
# Install PortAudio via Homebrew
brew install portaudio
```

### 2. Clone the Repository

```bash
git clone <repository-url>
cd wispr-flow-copy
```

### 3. Create Virtual Environment

```bash
python3 -m venv venv
source venv/bin/activate
```

### 4. Install Python Dependencies

```bash
pip install -r requirements.txt
```

**Note**: On first run, the Whisper model (~150MB) will auto-download to `~/.cache/huggingface/`

## macOS Permissions Setup (CRITICAL)

This application requires **two** permissions to function properly:

### 1. Microphone Access

Required for: Audio recording

**Setup:**
1. Open **System Preferences** (or **System Settings** on macOS Ventura+)
2. Navigate to **Security & Privacy** → **Privacy**
3. Select **Microphone** from the left sidebar
4. Check the box for **Terminal** (or your IDE if running from VSCode, PyCharm, etc.)

**If using an IDE:**
- VSCode: Enable for "Code Helper"
- PyCharm: Enable for "pycharm"
- Terminal: Enable for "Terminal"

### 2. Accessibility Access

Required for: Typing transcribed text at cursor position

**Setup:**
1. Open **System Preferences** (or **System Settings**)
2. Navigate to **Security & Privacy** → **Privacy**
3. Select **Accessibility** from the left sidebar
4. Click the lock icon to make changes (enter password)
5. Check the box for **Terminal** (or your IDE)

**Verification:**
- If microphone access is denied, the script will fail immediately with an error
- If accessibility is denied, recording will work but no text will be typed

## Usage

### Running the Application

```bash
# Activate virtual environment
source venv/bin/activate

# Run the script
python3 whispr_clone.py
```

### Recording Modes

#### Press-and-Hold Mode (Quick Dictation)
1. Place cursor where you want text to appear
2. **Press and hold** Right Control key
3. Speak your text
4. **Release** Right Control key
5. Text appears at cursor (1-3 seconds)

**Example:**
```
Hold Right Control → "Hello world, this is a test" → Release
Result: Hello world, this is a test
```

#### Toggle Mode (Hands-Free)
1. Place cursor where you want text to appear
2. **Press Right Control + Space together**
3. You'll see: "Toggle mode activated - recording started"
4. Speak your text (hands-free!)
5. **Press Right Control once** to stop
6. Text appears at cursor

**Example:**
```
Right Control + Space → "This is a longer dictation..." → Right Control
Result: This is a longer dictation...
```

### Stopping the Application

Press `Ctrl+C` in the terminal to quit

## Configuration

Edit the constants at the top of [whispr_clone.py](whispr_clone.py):

```python
WHISPER_MODEL = "base"  # Options: tiny, base, small, medium, large
SAMPLE_RATE = 16000     # Whisper's native rate (don't change)
DEBUG = True            # Set to False for minimal console output
MIN_RECORDING_DURATION = 0.5  # Minimum recording length (seconds)
DEBOUNCE_MS = 100       # Debounce time for key presses (milliseconds)
```

### Model Sizes

| Model  | Size   | RAM    | Speed      | Accuracy |
|--------|--------|--------|------------|----------|
| tiny   | ~75MB  | ~1GB   | Fastest    | Good     |
| base   | ~150MB | ~1GB   | Fast       | Better   |
| small  | ~500MB | ~2GB   | Medium     | Great    |
| medium | ~1.5GB | ~5GB   | Slower     | Excellent|
| large  | ~3GB   | ~10GB  | Slowest    | Best     |

**Recommendation**: Start with `base` for a good balance of speed and accuracy.

### Debug Mode

- **DEBUG = True**: Shows detailed logs (recording status, buffer size, timing)
- **DEBUG = False**: Minimal output (only startup messages and transcriptions)

## Troubleshooting

### "Microphone access denied"

**Solution:**
1. Grant microphone permission in System Preferences → Privacy → Microphone
2. Restart the application
3. On first run, macOS will prompt for permission - click "OK"

### "No text appears after dictation"

**Cause**: Accessibility permission not granted

**Solution:**
1. Grant accessibility permission in System Preferences → Privacy → Accessibility
2. No need to restart - try dictating again

### "Audio too short, skipping transcription"

**Cause**: Recording was shorter than 0.5 seconds

**Solution:**
- Hold the key longer while speaking
- Adjust `MIN_RECORDING_DURATION` in config

### "No speech detected"

**Cause**: Either silent recording or background noise only

**Solution:**
- Speak closer to microphone
- Ensure microphone is working (`System Preferences → Sound → Input`)
- Check input levels while recording

### "Model download fails"

**Cause**: Network issues during first-time model download

**Solution:**
```bash
# Manually download model
python3 -c "from faster_whisper import WhisperModel; WhisperModel('base')"

# Or check internet connection and retry
```

### Recording works but transcription is slow

**Solutions:**
- Use a smaller model (`tiny` instead of `base`)
- Close other applications to free RAM
- On older Macs, stick with `tiny` or `base` models

### Wrong keyboard detected (no Right Control)

**Solution:**
- Some keyboards lack Right Control
- Edit `whispr_clone.py` and change hotkey:
  ```python
  # Change from Key.ctrl_r to:
  if key == Key.f13:  # Use F13 key instead
  ```

## Testing

### Basic Test

```bash
# Run the application
python3 whispr_clone.py

# Expected output:
# Testing microphone access...
# Microphone access OK
# Loading Whisper model: base
# Whisper model loaded: base
# Whispr Clone is now running!
```

### Test Press-and-Hold Mode

1. Open TextEdit
2. Hold Right Control
3. Say: "Testing press and hold mode"
4. Release Right Control
5. **Expected**: Text appears in TextEdit within 2-3 seconds

### Test Toggle Mode

1. Open any text application
2. Press Right Control + Space together
3. **Expected console**: "Toggle mode activated - recording started"
4. Say: "This is hands free mode"
5. Press Right Control (single press)
6. **Expected console**: "Recording stopped"
7. **Expected**: Text appears in application

### Test in Multiple Applications

Test dictation works in:
- TextEdit (bundled macOS app)
- Notes (bundled macOS app)
- VSCode (editor)
- Terminal (command line)
- Chrome/Safari (address bar, forms)

## Performance

**Typical Performance (base model on M1 Mac):**
- Model load time: <1 second (after first download)
- Transcription latency: 1-2 seconds for 5-second clips
- Memory usage: ~500MB with base model loaded
- CPU usage: Spike during transcription, idle otherwise

**Apple Silicon (M1/M2/M3):**
- Faster transcription due to unified memory
- Lower power consumption

**Intel Macs:**
- Use `base` or `tiny` models for best performance
- Expect 2-3x longer transcription times

## Project Structure

```
wispr-flow-copy/
├── whispr_clone.py      # Main application (single file)
├── requirements.txt     # Python dependencies
├── README.md           # This file
├── .gitignore          # Git ignore rules
└── venv/               # Virtual environment (not tracked)
```

## How It Works

1. **Keyboard Listener**: `pynput` monitors keyboard events (press/release)
2. **Audio Recording**: `sounddevice` captures microphone input in real-time
3. **State Management**: Tracks current mode (hold/toggle) and recording status
4. **Transcription**: `faster-whisper` converts audio → text using Whisper AI
5. **Text Output**: `pynput.keyboard.Controller` types text at cursor position

## Advanced Usage

### Running in Background

```bash
# Run with caffeinate to prevent sleep
caffeinate -i python3 whispr_clone.py

# Or run in background (less recommended)
nohup python3 whispr_clone.py &
```

### Auto-start on Login

Create a LaunchAgent:

```bash
# Create plist file
nano ~/Library/LaunchAgents/com.whispr.clone.plist
```

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.whispr.clone</string>
    <key>ProgramArguments</key>
    <array>
        <string>/path/to/venv/bin/python3</string>
        <string>/path/to/whispr_clone.py</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
</dict>
</plist>
```

```bash
# Load agent
launchctl load ~/Library/LaunchAgents/com.whispr.clone.plist
```

## Contributing

Contributions welcome! Areas for improvement:
- GPU acceleration support
- Custom word replacement (e.g., "comma" → ",")
- Visual feedback (menu bar icon)
- Multiple language support
- Streaming transcription

## License

[Add your license here]

## Acknowledgments

- [faster-whisper](https://github.com/guillaumekln/faster-whisper) - Efficient Whisper implementation
- [OpenAI Whisper](https://github.com/openai/whisper) - Original Whisper model
- [pynput](https://github.com/moses-palmer/pynput) - Keyboard monitoring and control
- [sounddevice](https://python-sounddevice.readthedocs.io/) - Audio I/O

## Support

For issues, questions, or suggestions:
- Open an issue on GitHub
- Check the Troubleshooting section above
- Review macOS permissions carefully (most common issue)

---

**Note**: This tool is designed for macOS only. For Windows/Linux support, keyboard handling and permissions would need to be adapted.
