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
import ctypes
import fcntl
import os
import signal
import atexit
import subprocess
import objc
from AppKit import (
    NSApplication, NSStatusBar, NSMenu, NSMenuItem,
    NSVariableStatusItemLength, NSObject, NSOnState, NSOffState
)

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
        # Create log directory with restricted permissions (transcriptions may contain sensitive data)
        log_dir = Path.home() / 'Library' / 'Logs' / 'Whispr'
        log_dir.mkdir(parents=True, exist_ok=True)
        os.chmod(log_dir, 0o700)

        # Create rotating file handler (10MB per file, keep 5 files)
        log_file = log_dir / 'whispr.log'
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=10 * 1024 * 1024,  # 10 MB
            backupCount=5,
            encoding='utf-8'
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
MAX_RECORDING_DURATION = 300  # Maximum recording length in seconds (safety limit)

# ============================================================================
# HOTKEY CONFIGURATION - Change these to customize your recording keys!
# ============================================================================
# HOTKEY_KEYS is a set — pynput may report Key.ctrl, Key.ctrl_r, or Key.ctrl_l
# depending on macOS version, keyboard layout, and backend. Including all
# variants that should count as "the hotkey" eliminates mismatches.
#
# Examples:
#   {Key.ctrl, Key.ctrl_r}           - Right Control (default, broadest match)
#   {Key.ctrl_r}                     - Right Control only (strict)
#   {Key.ctrl, Key.ctrl_l}           - Left Control
#   {Key.cmd_r}                      - Right Command (⌘)
#   {Key.alt_r, Key.alt}             - Right Option/Alt
#   {Key.f13}                        - F13

HOTKEY_KEYS = {Key.ctrl, Key.ctrl_r}  # All key codes that trigger recording
TOGGLE_KEY = Key.space                # Key to combine with hotkey for toggle mode

KEY_STATE_TIMEOUT = 60  # Seconds before a "stuck" key press is auto-reset


def is_hotkey(key):
    """Check if a key event matches any of the configured hotkey variants."""
    return key in HOTKEY_KEYS


def validate_config():
    """Validate configuration constants at startup. Exits on invalid config."""
    errors = []
    if not HOTKEY_KEYS or not isinstance(HOTKEY_KEYS, set):
        errors.append("HOTKEY_KEYS must be a non-empty set of Key values")
    if TOGGLE_KEY in HOTKEY_KEYS:
        errors.append("TOGGLE_KEY cannot be the same as a HOTKEY_KEYS entry")
    if DEBOUNCE_MS < 0:
        errors.append(f"DEBOUNCE_MS must be >= 0, got {DEBOUNCE_MS}")
    if MIN_RECORDING_DURATION <= 0:
        errors.append(f"MIN_RECORDING_DURATION must be > 0, got {MIN_RECORDING_DURATION}")
    if MAX_RECORDING_DURATION <= MIN_RECORDING_DURATION:
        errors.append(f"MAX_RECORDING_DURATION ({MAX_RECORDING_DURATION}) must be > MIN_RECORDING_DURATION ({MIN_RECORDING_DURATION})")
    if SAMPLE_RATE <= 0:
        errors.append(f"SAMPLE_RATE must be > 0, got {SAMPLE_RATE}")
    if WHISPER_MODEL not in ("tiny", "base", "small", "medium", "large"):
        errors.append(f"WHISPER_MODEL must be one of tiny/base/small/medium/large, got '{WHISPER_MODEL}'")
    if errors:
        for e in errors:
            print(f"Configuration error: {e}", file=sys.stderr)
        sys.exit(0)


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
        self.hotkey_pressed = False
        self.space_pressed = False

        # Timestamp when hotkey was pressed (for stuck-key detection)
        self.hotkey_press_time = 0

        # Text insertion mode
        self.last_transcription = None   # stores last transcribed text for "Retype Last"
        self.use_type_mode = False       # False = clipboard paste (default), True = character-by-character

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
        # Exit 0 so LaunchAgent KeepAlive doesn't create an infinite restart loop
        sys.exit(0)


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
        logger.warning(f"Audio callback status: {status}")

    # Use non-blocking lock to avoid audio glitches
    if state.lock.acquire(blocking=False):
        try:
            if state.is_recording:
                # Safety limit: stop appending if max duration exceeded
                max_chunks = int(MAX_RECORDING_DURATION * SAMPLE_RATE / frames) if frames > 0 else float('inf')
                if len(state.audio_buffer) < max_chunks:
                    state.audio_buffer.append(indata.copy())
                else:
                    logger.warning("Max recording duration reached, stopping buffer append")
        finally:
            state.lock.release()


def start_recording():
    """
    Start audio recording by creating and starting an audio stream.
    Must be called with state.lock held.

    Idempotent: safely cleans up any existing stream before starting.
    On failure: guarantees state is clean (is_recording=False, stream=None).
    Raises on failure so the caller can reset mode.
    """
    # Clean up any existing stream first (idempotent)
    _cleanup_stream()

    state.audio_buffer = []
    state.is_recording = False

    try:
        state.audio_stream = sd.InputStream(
            samplerate=SAMPLE_RATE,
            channels=CHANNELS,
            dtype=DTYPE,
            callback=audio_callback
        )
        state.audio_stream.start()
        state.is_recording = True
        logger.debug(f"Recording started - Mode: {state.mode}")
    except Exception:
        # Guarantee clean state on failure
        _cleanup_stream()
        state.is_recording = False
        raise


def _cleanup_stream():
    """Safely close the audio stream. Idempotent — safe to call anytime."""
    if state.audio_stream is not None:
        try:
            state.audio_stream.stop()
            state.audio_stream.close()
        except Exception:
            pass
        state.audio_stream = None


def stop_recording():
    """
    Stop audio recording and trigger transcription.
    Must be called with state.lock held.

    Idempotent: safe to call even if not currently recording.
    Snapshots the buffer before cleanup so transcription thread owns its data.
    """
    # Snapshot buffer, then clear — transcription thread gets its own copy
    buffer_snapshot = list(state.audio_buffer)
    state.audio_buffer = []
    state.is_recording = False
    _cleanup_stream()

    if not buffer_snapshot:
        logger.debug("Recording stopped - empty buffer, skipping transcription")
        return

    logger.debug(f"Recording stopped - Buffer size: {len(buffer_snapshot)} chunks")

    # Transcription in separate thread — owns buffer_snapshot, no shared state
    threading.Thread(target=transcribe_and_type, args=(buffer_snapshot,), daemon=True).start()


# ============================================================================
# Transcription and Text Output
# ============================================================================

def insert_text(text):
    """
    Insert transcribed text at cursor position.
    Uses clipboard paste by default (instant, unicode-safe).
    Falls back to character-by-character typing when use_type_mode is enabled.
    Always saves the text as last_transcription for "Retype Last" menu action.
    """
    state.last_transcription = text

    if state.use_type_mode:
        state.keyboard_controller.type(text)
    else:
        # Save current clipboard contents
        try:
            old_clipboard = subprocess.run(
                ['pbpaste'], capture_output=True, text=True
            ).stdout
        except Exception:
            old_clipboard = None

        # Copy transcription to clipboard and paste
        subprocess.run(['pbcopy'], input=text.encode('utf-8'), check=True)
        time.sleep(0.05)
        state.keyboard_controller.press(Key.cmd)
        state.keyboard_controller.press('v')
        state.keyboard_controller.release('v')
        state.keyboard_controller.release(Key.cmd)

        # Restore previous clipboard after a brief delay
        if old_clipboard is not None:
            time.sleep(0.2)
            subprocess.run(
                ['pbcopy'], input=old_clipboard.encode('utf-8'), check=True
            )


def transcribe_and_type(audio_buffer):
    """
    Transcribe recorded audio using Whisper and type the result.

    Args:
        audio_buffer: List of numpy arrays containing recorded audio chunks
    """
    try:
        # Check if buffer has data
        if not audio_buffer or len(audio_buffer) == 0:
            logger.warning("No audio recorded")
            return

        # Combine all audio chunks into single array
        audio_data = np.concatenate(audio_buffer, axis=0)

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

        # Only log transcription content in debug mode (may contain sensitive data)
        logger.debug(f"Transcription: {text}")
        logger.info(f"Transcribed {len(text)} characters")

        # Insert the text at cursor position
        insert_text(text)

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

    State machine transitions on press:
      mode=None  + hotkey              → hold mode, start recording
      mode=None  + hotkey (space held) → toggle mode, start recording
      mode=None  + space (hotkey held) → toggle mode, start recording
      mode=hold  + space               → convert to toggle mode (keep recording)
      mode=toggle + hotkey             → stop recording, mode=None
    """
    if DEBUG:
        logger.debug(f"Key press: {key!r} (type={type(key).__name__}, match={is_hotkey(key)})")

    current_time = time.time() * 1000  # Convert to milliseconds

    with state.lock:
        if is_hotkey(key):
            # Debounce: ignore if too soon after last press
            if current_time - state.last_press_time < DEBOUNCE_MS:
                return

            state.last_press_time = current_time
            state.hotkey_pressed = True
            state.hotkey_press_time = time.time()

            if state.mode is None:
                # Start recording — toggle if space already held, else hold
                state.mode = "toggle" if state.space_pressed else "hold"
                try:
                    start_recording()
                except Exception as e:
                    logger.error(f"Failed to start recording: {e}")
                    state.mode = None
                    return
                logger.info(f"{state.mode.capitalize()} mode: Recording started")

            elif state.mode == "toggle" and state.is_recording:
                stop_recording()
                state.mode = None
                logger.info("Toggle mode: Recording stopped")

        elif key == TOGGLE_KEY:
            state.space_pressed = True

            if state.hotkey_pressed:
                if state.mode is None:
                    # Hotkey already held, space just arrived → toggle mode
                    state.mode = "toggle"
                    try:
                        start_recording()
                    except Exception as e:
                        logger.error(f"Failed to start recording: {e}")
                        state.mode = None
                        return
                    logger.info("Toggle mode: Recording started")
                elif state.mode == "hold":
                    # Convert hold → toggle (recording continues uninterrupted)
                    state.mode = "toggle"
                    logger.debug("Converted hold mode to toggle mode")


def on_release(key):
    """
    Handle keyboard key release events.

    State machine transitions on release:
      mode=hold + hotkey released → stop recording, mode=None
      (toggle mode ignores hotkey release — stop happens on next hotkey press)
    """
    if DEBUG:
        logger.debug(f"Key release: {key!r} (type={type(key).__name__})")

    with state.lock:
        if is_hotkey(key):
            state.hotkey_pressed = False

            if state.mode == "hold" and state.is_recording:
                stop_recording()
                state.mode = None
                logger.info("Hold mode: Recording stopped")

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
        logger.error("2. Go to Security & Privacy > Privacy")
        logger.error("3. Select 'Microphone' from the left sidebar")
        logger.error("4. Enable access for 'Terminal' (or your IDE/Python)")
        logger.error("\nPlease grant permission and restart the application.")
        logger.error("=" * 60)
        return False


def is_accessibility_trusted(prompt=False):
    """
    Check if the process has Accessibility permission using macOS API.

    Args:
        prompt: If True, opens System Settings to the Accessibility pane

    Returns:
        bool: True if the process is trusted for accessibility
    """
    try:
        app_services = ctypes.cdll.LoadLibrary(
            '/System/Library/Frameworks/ApplicationServices.framework/ApplicationServices'
        )

        if not prompt:
            return bool(app_services.AXIsProcessTrusted())

        # Use AXIsProcessTrustedWithOptions to show the system prompt
        core_foundation = ctypes.cdll.LoadLibrary(
            '/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation'
        )

        core_foundation.CFStringCreateWithCString.restype = ctypes.c_void_p
        core_foundation.CFStringCreateWithCString.argtypes = [
            ctypes.c_void_p, ctypes.c_char_p, ctypes.c_uint32
        ]
        key = core_foundation.CFStringCreateWithCString(
            None, b"AXTrustedCheckOptionPrompt", 0x08000100  # kCFStringEncodingUTF8
        )

        kCFBooleanTrue = ctypes.c_void_p.in_dll(core_foundation, 'kCFBooleanTrue')

        core_foundation.CFDictionaryCreate.restype = ctypes.c_void_p
        core_foundation.CFDictionaryCreate.argtypes = [
            ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p,
            ctypes.c_long, ctypes.c_void_p, ctypes.c_void_p
        ]
        keys_arr = (ctypes.c_void_p * 1)(key)
        vals_arr = (ctypes.c_void_p * 1)(kCFBooleanTrue)
        kCFTypeDictionaryKeyCallBacks = ctypes.c_void_p.in_dll(
            core_foundation, 'kCFTypeDictionaryKeyCallBacks'
        )
        kCFTypeDictionaryValueCallBacks = ctypes.c_void_p.in_dll(
            core_foundation, 'kCFTypeDictionaryValueCallBacks'
        )
        opts = core_foundation.CFDictionaryCreate(
            None, keys_arr, vals_arr, 1,
            ctypes.byref(kCFTypeDictionaryKeyCallBacks),
            ctypes.byref(kCFTypeDictionaryValueCallBacks)
        )

        app_services.AXIsProcessTrustedWithOptions.restype = ctypes.c_bool
        app_services.AXIsProcessTrustedWithOptions.argtypes = [ctypes.c_void_p]
        result = app_services.AXIsProcessTrustedWithOptions(opts)

        core_foundation.CFRelease(opts)
        core_foundation.CFRelease(key)
        return bool(result)
    except Exception:
        return False


def check_accessibility_permission():
    """
    Check if accessibility permissions are granted for keyboard control.
    If not granted, opens System Settings and waits up to 30 seconds for the user
    to grant permission. Exits cleanly if not granted after waiting.

    Returns:
        bool: True if granted, exits with code 0 if not
    """
    if is_accessibility_trusted():
        logger.info("Accessibility permission: OK")
        return True

    logger.warning("Accessibility permission not granted. Opening System Settings...")
    is_accessibility_trusted(prompt=True)

    for i in range(6):
        time.sleep(5)
        if is_accessibility_trusted():
            logger.info("Accessibility permission: OK (granted after prompt)")
            return True
        logger.info("Waiting for accessibility permission... (%d/6)", i + 1)

    logger.error("=" * 60)
    logger.error("FATAL: Accessibility permission not granted after 30 seconds")
    logger.error("Please enable 'Whispr' in System Settings > Accessibility and restart")
    logger.error("=" * 60)
    sys.exit(0)  # Clean exit so KeepAlive does NOT restart


# ============================================================================
# Instance Lock
# ============================================================================

PID_FILE = Path.home() / 'Library' / 'Logs' / 'Whispr' / 'whispr.pid'


def acquire_pid_lock():
    """
    Prevent duplicate instances using a PID file lock.

    Returns:
        file object if lock acquired, None if another instance is running
    """
    try:
        PID_FILE.parent.mkdir(parents=True, exist_ok=True)
        pid_file = open(PID_FILE, 'w')
        os.chmod(PID_FILE, 0o600)
        fcntl.flock(pid_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        pid_file.write(str(os.getpid()))
        pid_file.flush()
        return pid_file
    except (IOError, OSError):
        return None


# ============================================================================
# Menu Bar Icon
# ============================================================================

class MenuDelegate(NSObject):
    """Handles all menu bar actions: Retype Last, Paste Mode toggle, Quit."""
    shutdown_event = None
    paste_mode_item = None

    def retypeLast_(self, sender):
        """Type last transcription character-by-character in a background thread."""
        text = state.last_transcription
        if text:
            threading.Thread(
                target=state.keyboard_controller.type,
                args=(text,),
                daemon=True
            ).start()

    def togglePasteMode_(self, sender):
        """Toggle between clipboard paste and character-by-character typing."""
        state.use_type_mode = not state.use_type_mode
        if self.paste_mode_item:
            self.paste_mode_item.setState_(
                NSOffState if state.use_type_mode else NSOnState
            )
        mode_name = "Type" if state.use_type_mode else "Paste"
        logger.info(f"Text insertion mode: {mode_name}")

    def quit_(self, sender):
        if self.shutdown_event:
            self.shutdown_event.set()
        NSApplication.sharedApplication().terminate_(None)

    def validateMenuItem_(self, item):
        """Enable/disable menu items dynamically."""
        if item.action() == b"retypeLast:":
            return state.last_transcription is not None
        return True


def setup_menu_bar(shutdown_event):
    """Create a menu bar status icon with Retype Last, Paste Mode toggle, and Quit."""
    app = NSApplication.sharedApplication()

    status_bar = NSStatusBar.systemStatusBar()
    status_item = status_bar.statusItemWithLength_(NSVariableStatusItemLength)
    button = status_item.button()
    button.setTitle_("\U0001f3a4")  # microphone emoji

    delegate = MenuDelegate.alloc().init()
    delegate.shutdown_event = shutdown_event

    menu = NSMenu.alloc().init()

    # Retype Last — grayed out when no transcription available
    retype_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
        "Retype Last", "retypeLast:", ""
    )
    retype_item.setTarget_(delegate)
    menu.addItem_(retype_item)

    menu.addItem_(NSMenuItem.separatorItem())

    # Paste Mode toggle — checked by default (paste mode ON)
    paste_mode_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
        "Paste Mode", "togglePasteMode:", ""
    )
    paste_mode_item.setTarget_(delegate)
    paste_mode_item.setState_(NSOnState)
    delegate.paste_mode_item = paste_mode_item
    menu.addItem_(paste_mode_item)

    menu.addItem_(NSMenuItem.separatorItem())

    # Quit
    quit_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
        "Quit Whispr", "quit:", ""
    )
    quit_item.setTarget_(delegate)
    menu.addItem_(quit_item)

    status_item.setMenu_(menu)

    # Keep references alive
    return status_item, delegate


def health_monitor(listener, shutdown_event):
    """Background thread: monitors listener health and stuck key states."""
    while listener.is_alive() and not shutdown_event.is_set():
        listener.join(timeout=5)
        with state.lock:
            now = time.time()
            if state.hotkey_pressed and (now - state.hotkey_press_time > KEY_STATE_TIMEOUT):
                logger.warning("Hotkey stuck for >%ds, resetting state", KEY_STATE_TIMEOUT)
                if state.is_recording:
                    stop_recording()
                state.hotkey_pressed = False
                state.mode = None
    # If listener died or shutdown requested, terminate the app
    NSApplication.sharedApplication().terminate_(None)


# ============================================================================
# Main Application
# ============================================================================

def main():
    """
    Main application entry point.
    """
    global logger

    # Validate config before anything else
    validate_config()

    # Setup logging first
    logger = setup_logging()

    # Prevent duplicate instances
    pid_lock = acquire_pid_lock()
    if pid_lock is None:
        logger.warning("Another Whispr instance is already running. Exiting.")
        sys.exit(0)
    atexit.register(lambda: pid_lock.close())

    logger.info("=" * 60)
    logger.info("Whispr Clone - Voice Dictation Tool")
    logger.info("=" * 60)
    logger.info("")

    # Check microphone permissions
    if not test_microphone_access():
        sys.exit(0)  # Exit 0 so LaunchAgent KeepAlive doesn't restart loop

    # Check accessibility permissions (exits if not granted)
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
    hotkey_name = ", ".join(str(k).replace("Key.", "") for k in HOTKEY_KEYS)
    logger.info("Usage:")
    logger.info("  Press-and-Hold Mode:")
    logger.info(f"    - Hold [{hotkey_name}], speak, release to transcribe")
    logger.info("")
    logger.info("  Toggle/Hands-Free Mode:")
    logger.info(f"    - Press [{hotkey_name}] + Space together, then speak")
    logger.info(f"    - Press [{hotkey_name}] again to stop and transcribe")
    logger.info("")
    logger.info(f"Settings: Model={WHISPER_MODEL}, Debug={'ON' if DEBUG else 'OFF'}")
    logger.info("=" * 60)
    logger.info("")

    # Shutdown via flag — signal handler only sets the flag, no I/O
    shutdown_event = threading.Event()

    def shutdown(signum, frame):
        shutdown_event.set()
        NSApplication.sharedApplication().terminate_(None)

    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)

    # Register cleanup for app termination
    def cleanup():
        logger.info("Shutting down Whispr Clone...")
        listener.stop()
        with state.lock:
            if state.is_recording:
                stop_recording()
            else:
                _cleanup_stream()
            state.mode = None
        logger.info("Goodbye!")

    atexit.register(cleanup)

    # Start keyboard listener
    listener = keyboard.Listener(
        on_press=on_press,
        on_release=on_release
    )
    listener.start()

    # Start health monitoring in background thread
    health_thread = threading.Thread(
        target=health_monitor,
        args=(listener, shutdown_event),
        daemon=True
    )
    health_thread.start()

    # Set up menu bar icon (must be on main thread)
    _menu_refs = setup_menu_bar(shutdown_event)

    # Run macOS event loop (blocks until quit)
    NSApplication.sharedApplication().run()


# ============================================================================
# Entry Point
# ============================================================================

if __name__ == "__main__":
    main()
