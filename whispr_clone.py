#!/usr/bin/env python3
"""
Whispr Clone - Voice Dictation Tool for macOS

A background script that provides voice dictation with two recording modes:
1. Press-and-Hold: Hold Right Control to record, release to transcribe
2. Toggle Mode: Press Right Control + Space to start, Right Control to stop

Uses faster-whisper for offline speech-to-text transcription.
"""

import sys
import time
import threading
import numpy as np
import sounddevice as sd
from pynput import keyboard
from pynput.keyboard import Key, Controller
import logging
import logging.handlers
from pathlib import Path

# ============================================================================
# Logging Configuration
# ============================================================================

def setup_logging():
    """
    Configure logging with dual handlers: console + rotating file.

    Returns:
        logging.Logger: Configured logger instance
    """
    # Create logger
    logger = logging.getLogger('whispr')

    # Determine log level from DEBUG constant
    log_level = logging.DEBUG if DEBUG else logging.INFO
    logger.setLevel(log_level)

    # Clear any existing handlers
    logger.handlers.clear()

    # Log format with timestamp
    formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # Console handler (if running in terminal)
    if sys.stdout.isatty():
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(log_level)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    # File handler (always enabled)
    try:
        # Create log directory
        log_dir = Path.home() / 'Library' / 'Logs' / 'Whispr'
        log_dir.mkdir(parents=True, exist_ok=True)

        # Create rotating file handler (10MB per file, keep 5 files)
        log_file = log_dir / 'whispr.log'
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=10 * 1024 * 1024,  # 10 MB
            backupCount=5
        )
        file_handler.setLevel(log_level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    except Exception as e:
        # If file logging fails, warn but continue
        if sys.stdout.isatty():
            print(f"Warning: Could not setup file logging: {e}")
            print("Continuing with console logging only...")

    return logger

# Initialize logger (will be set in main())
logger = None

# ============================================================================
# Configuration Constants
# ============================================================================

WHISPER_MODEL = "small"  # Options: tiny, base, small, medium, large
SAMPLE_RATE = 16000     # Whisper's native sample rate (Hz)
CHANNELS = 1            # Mono audio
DTYPE = 'int16'         # Audio data type for sounddevice
DEBUG = True            # Set to False for minimal console output
MIN_RECORDING_DURATION = 0.5  # Minimum recording length in seconds
DEBOUNCE_MS = 100       # Debounce time for rapid key presses (milliseconds)

# ============================================================================
# HOTKEY CONFIGURATION - Change these to customize your recording keys!
# ============================================================================
# Available options for HOTKEY:
#   Key.ctrl_r     - Right Control key (default, may not exist on some keyboards)
#   Key.ctrl_l     - Left Control key
#   Key.cmd_r      - Right Command (⌘) key
#   Key.cmd_l      - Left Command (⌘) key
#   Key.alt_r      - Right Option/Alt key
#   Key.alt_l      - Left Option/Alt key
#   Key.f13        - F13 key (good if you have it)
#   Key.f14        - F14 key
#   Key.caps_lock  - Caps Lock key

HOTKEY = Key.ctrl      # Main recording trigger key
TOGGLE_KEY = Key.space   # Key to combine with HOTKEY for toggle mode

# ============================================================================
# Application State
# ============================================================================

class AppState:
    """Global application state management"""

    def __init__(self):
        # Recording mode: None, "hold", or "toggle"
        self.mode = None

        # Current recording status
        self.is_recording = False

        # Audio buffer to store recorded chunks
        self.audio_buffer = []

        # Whisper model instance (loaded at startup)
        self.whisper_model = None

        # Keyboard controller for typing output
        self.keyboard_controller = None

        # Audio stream instance
        self.audio_stream = None

        # Thread safety lock
        self.lock = threading.Lock()

        # Key state tracking
        self.right_ctrl_pressed = False
        self.space_pressed = False

        # Debouncing
        self.last_press_time = 0


# Global state instance
state = AppState()


# ============================================================================
# Whisper Model Initialization
# ============================================================================

def initialize_whisper():
    """
    Initialize and load the Whisper model.

    Returns:
        WhisperModel: Loaded Whisper model instance
    """
    try:
        from faster_whisper import WhisperModel

        logger.info(f"Loading Whisper model: {WHISPER_MODEL}")

        model = WhisperModel(
            WHISPER_MODEL,
            device="cpu",
            compute_type="int8"  # Optimized for CPU performance
        )

        logger.info(f"Whisper model loaded: {WHISPER_MODEL}")
        return model

    except Exception as e:
        logger.error(f"FATAL ERROR: Failed to load Whisper model")
        logger.error(f"Details: {e}")
        logger.error("Please check your internet connection (first download) and try again.")
        sys.exit(1)


# ============================================================================
# Audio Recording Functions
# ============================================================================

def audio_callback(indata, frames, time_info, status):
    """
    Callback function for sounddevice audio stream.
    Called automatically for each audio chunk.

    Args:
        indata: Input audio data (numpy array)
        frames: Number of frames
        time_info: Time information
        status: Stream status flags
    """
    if status:
        logger.debug(f"Audio callback status: {status}")

    # Only append data when actively recording
    if state.is_recording:
        state.audio_buffer.append(indata.copy())


def start_recording():
    """
    Start audio recording by creating and starting an audio stream.
    """
    # Clear the audio buffer
    state.audio_buffer = []

    # Create audio input stream
    state.audio_stream = sd.InputStream(
        samplerate=SAMPLE_RATE,
        channels=CHANNELS,
        dtype=DTYPE,
        callback=audio_callback
    )

    # Start the stream
    state.audio_stream.start()
    state.is_recording = True

    logger.debug(f"Recording started - Mode: {state.mode}")


def stop_recording():
    """
    Stop audio recording and trigger transcription.
    """
    if state.audio_stream is not None:
        state.audio_stream.stop()
        state.audio_stream.close()
        state.audio_stream = None

    state.is_recording = False

    logger.debug(f"Recording stopped - Buffer size: {len(state.audio_buffer)} chunks")

    # Process transcription in separate thread to avoid blocking
    threading.Thread(target=transcribe_and_type, daemon=True).start()


# ============================================================================
# Transcription and Text Output
# ============================================================================

def transcribe_and_type():
    """
    Transcribe recorded audio using Whisper and type the result.
    """
    try:
        # Check if buffer has data
        if not state.audio_buffer or len(state.audio_buffer) == 0:
            logger.warning("No audio recorded")
            return

        # Combine all audio chunks into single array
        audio_data = np.concatenate(state.audio_buffer, axis=0)

        # Convert from int16 to float32 and normalize to [-1.0, 1.0]
        audio_float = audio_data.astype(np.float32) / 32768.0
        audio_float = audio_float.flatten()

        # Check minimum duration
        duration = len(audio_float) / SAMPLE_RATE
        if duration < MIN_RECORDING_DURATION:
            logger.info(f"Audio too short ({duration:.2f}s), skipping transcription (minimum: {MIN_RECORDING_DURATION}s)")
            return

        logger.debug(f"Transcribing {duration:.2f}s of audio...")

        # Transcribe with Whisper
        segments, info = state.whisper_model.transcribe(
            audio_float,
            language="en",      # English only for faster processing
            beam_size=5,
            vad_filter=True     # Voice Activity Detection filter
        )

        # Extract text from segments
        text = "".join(segment.text for segment in segments).strip()

        if not text:
            logger.info("No speech detected")
            return

        # Always log transcription (even in non-debug mode)
        logger.info(f"Transcription: {text}")

        # Type the text at cursor position
        state.keyboard_controller.type(text)

    except Exception as e:
        logger.error(f"Transcription error: {e}")
        if DEBUG:
            import traceback
            traceback.print_exc()


# ============================================================================
# Keyboard Event Handlers
# ============================================================================

def on_press(key):
    """
    Handle keyboard key press events.

    Args:
        key: The key that was pressed
    """
    current_time = time.time() * 1000  # Convert to milliseconds

    with state.lock:
        # Hotkey pressed (configured key for recording)
        if key == HOTKEY:
            # Debounce: ignore if too soon after last press
            if current_time - state.last_press_time < DEBOUNCE_MS:
                return

            state.last_press_time = current_time
            state.right_ctrl_pressed = True

            # Start hold mode if no mode active and space not pressed
            if state.mode is None and not state.space_pressed:
                state.mode = "hold"
                start_recording()
                logger.info("Hold mode: Recording started")

            # Stop toggle mode if currently in toggle mode
            elif state.mode == "toggle" and state.is_recording:
                stop_recording()
                state.mode = None
                logger.info("Recording stopped")

        # Toggle key pressed (for activating hands-free mode)
        elif key == TOGGLE_KEY:
            state.space_pressed = True

            # Activate toggle mode if Right Control is also pressed
            if state.right_ctrl_pressed:
                if state.mode is None:
                    # Start fresh toggle mode
                    state.mode = "toggle"
                    start_recording()
                    logger.info("Toggle mode activated - recording started")
                elif state.mode == "hold":
                    # Convert hold mode to toggle mode
                    state.mode = "toggle"
                    logger.debug("Converted hold mode to toggle mode")


def on_release(key):
    """
    Handle keyboard key release events.

    Args:
        key: The key that was released
    """
    with state.lock:
        # Hotkey released
        if key == HOTKEY:
            state.right_ctrl_pressed = False

            # Stop hold mode if currently in hold mode
            if state.mode == "hold" and state.is_recording:
                stop_recording()
                state.mode = None
                logger.info("Recording stopped")

        # Toggle key released
        elif key == TOGGLE_KEY:
            state.space_pressed = False


# ============================================================================
# Permission Checks
# ============================================================================

def test_microphone_access():
    """
    Test if microphone access is granted.

    Returns:
        bool: True if microphone is accessible, False otherwise
    """
    try:
        logger.info("Testing microphone access...")

        # Try to open a test stream
        test_stream = sd.InputStream(
            samplerate=SAMPLE_RATE,
            channels=CHANNELS,
            dtype=DTYPE
        )
        test_stream.start()
        time.sleep(0.1)
        test_stream.stop()
        test_stream.close()

        logger.info("Microphone access OK")
        return True

    except Exception as e:
        logger.error("=" * 60)
        logger.error("ERROR: Microphone access denied or unavailable")
        logger.error("=" * 60)
        logger.error(f"Details: {e}")
        logger.error("")
        logger.error("macOS Permissions Required:")
        logger.error("1. Open System Preferences (or System Settings)")
        logger.error("2. Go to Security & Privacy → Privacy")
        logger.error("3. Select 'Microphone' from the left sidebar")
        logger.error("4. Enable access for 'Terminal' (or your IDE/Python)")
        logger.error("\nPlease grant permission and restart the application.")
        logger.error("=" * 60)
        return False


def check_accessibility_permission():
    """
    Check if accessibility permissions are granted for keyboard control.
    Note: This is a basic check - full verification requires actual typing attempt.

    Returns:
        bool: True (we'll verify during actual operation)
    """
    logger.info("\nNote: This app requires Accessibility permissions to type text.")
    logger.info("If text doesn't appear when you dictate:")
    logger.info("1. Open System Preferences → Security & Privacy → Privacy")
    logger.info("2. Select 'Accessibility' from the left sidebar")
    logger.info("3. Enable access for 'Terminal' (or your IDE/Python)")
    logger.info("")
    return True


# ============================================================================
# Main Application
# ============================================================================

def main():
    """
    Main application entry point.
    """
    global logger

    # Setup logging first
    logger = setup_logging()

    logger.info("=" * 60)
    logger.info("Whispr Clone - Voice Dictation Tool")
    logger.info("=" * 60)
    logger.info("")

    # Check microphone permissions
    if not test_microphone_access():
        sys.exit(1)

    # Check accessibility permissions (informational)
    check_accessibility_permission()

    # Initialize Whisper model
    state.whisper_model = initialize_whisper()

    # Initialize keyboard controller
    state.keyboard_controller = Controller()

    # Print usage instructions
    logger.info("=" * 60)
    logger.info("Whispr Clone is now running!")
    logger.info("=" * 60)
    logger.info("")
    logger.info("Usage:")
    logger.info("  Press-and-Hold Mode:")
    logger.info("    - Hold Right Control → speak → release to transcribe")
    logger.info("")
    logger.info("  Toggle/Hands-Free Mode:")
    logger.info("    - Press Right Control + Space together → speak")
    logger.info("    - Press Right Control again to stop and transcribe")
    logger.info("")
    logger.info(f"Settings: Model={WHISPER_MODEL}, Debug={'ON' if DEBUG else 'OFF'}")
    logger.info("\nPress Ctrl+C to quit")
    logger.info("=" * 60)
    logger.info("")

    # Start keyboard listener
    listener = keyboard.Listener(
        on_press=on_press,
        on_release=on_release
    )
    listener.start()

    # Keep application running
    try:
        listener.join()
    except KeyboardInterrupt:
        logger.info("\n\nShutting down Whispr Clone...")
        listener.stop()
        if state.audio_stream is not None:
            state.audio_stream.stop()
            state.audio_stream.close()
        logger.info("Goodbye!")
        sys.exit(0)


# ============================================================================
# Entry Point
# ============================================================================

if __name__ == "__main__":
    main()
