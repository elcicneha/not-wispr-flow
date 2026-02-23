#!/usr/bin/env python3
"""
Not Wispr Flow - Voice Dictation Tool for macOS

A background script that provides voice dictation with two recording modes:
1. Press-and-Hold: Hold Right Control to record, release to transcribe
2. Toggle Mode: Press Right Control + Space to start, Right Control to stop

Uses mlx-whisper for offline speech-to-text transcription (GPU-accelerated on Apple Silicon).
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
import json
from collections import deque
import objc
from ApplicationServices import (
    AXUIElementCreateSystemWide,
    AXUIElementCopyAttributeValue,
    kAXFocusedUIElementAttribute,
    kAXValueAttribute,
    kAXSelectedTextRangeAttribute,
    kAXErrorSuccess,
)
from AppKit import (
    NSApplication, NSStatusBar, NSMenu, NSMenuItem,
    NSVariableStatusItemLength, NSObject, NSOnState, NSOffState,
    NSImage
)

# ============================================================================
# User Configuration - imported from config.py
# ============================================================================
from config import HOTKEY_KEYS, TOGGLE_KEY, WHISPER_MODEL, DEBUG

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
    logger = logging.getLogger('notwisprflow')

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
        log_dir = Path.home() / 'Library' / 'Logs' / 'NotWisprFlow'
        log_dir.mkdir(parents=True, exist_ok=True)
        os.chmod(log_dir, 0o700)

        # Create rotating file handler (10MB per file, keep 5 files)
        log_file = log_dir / 'notwisprflow.log'
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
# Internal Configuration Constants (Developer Settings)
# ============================================================================
# These are technical constants that control internal behavior.
# User-facing settings are in config.py

SAMPLE_RATE = 16000     # Whisper's native sample rate (Hz)
CHANNELS = 1            # Mono audio
DTYPE = 'int16'         # Audio data type for sounddevice
MIN_RECORDING_DURATION = 0.2  # Minimum recording length in seconds
DEBOUNCE_MS = 100       # Debounce time for rapid key presses (milliseconds)
FLUSH_BUFFER_THRESHOLD_MB = 5  # Flush buffer to disk when it exceeds this (crash recovery)
CONTEXT_CHARS = 200           # Max characters before/after cursor for Whisper context


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
    if FLUSH_BUFFER_THRESHOLD_MB < 1:
        errors.append(f"FLUSH_BUFFER_THRESHOLD_MB must be >= 1, got {FLUSH_BUFFER_THRESHOLD_MB}")
    if SAMPLE_RATE <= 0:
        errors.append(f"SAMPLE_RATE must be > 0, got {SAMPLE_RATE}")
    if not WHISPER_MODEL:
        errors.append("WHISPER_MODEL must be a non-empty HuggingFace model repo name")
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

        # Audio buffer — lock-free deque for audio callback thread
        self.audio_buffer = deque()

        # Transcription function: callable(audio_float: np.ndarray) -> str
        # Initialized by initialize_whisper(), backend-agnostic
        self.whisper_model = None

        # VAD model and utilities for silence detection (initialized at startup)
        self.vad_model = None
        self.vad_utils = None

        # Keyboard controller for typing output
        self.keyboard_controller = None

        # Audio stream instance
        self.audio_stream = None

        # Thread safety lock
        self.lock = threading.Lock()

        # Key state tracking
        self.hotkey_pressed = False
        self.space_pressed = False

        # Text insertion mode
        self.last_transcription = None   # stores last transcribed text for "Retype Last"
        self.use_type_mode = False       # False = clipboard paste (default), True = character-by-character

        # Transcription state tracking
        self.is_transcribing = False     # True when transcription thread is running
        self.transcription_start_time = None  # When transcription started (for hang detection)

        # Debouncing
        self.last_press_time = 0

        # Buffer overflow to disk
        self.overflow_files = []        # Paths to flushed .npy temp files for current recording
        self.overflow_file_counter = 0  # Unique filename counter per recording
        self.recording_start_time = None  # For stats tracking


# Global state instance
state = AppState()


# ============================================================================
# Menu Bar Icon Management
# ============================================================================
# All menu bar icon logic consolidated in one place. The app only needs to
# call update_menu_bar_icon(state_name) to change the icon state.

class MenuBarIconManager:
    """Manages menu bar icon state and animations."""

    # Animation speeds in milliseconds - adjust these to change animation speed
    RECORDING_FRAME_INTERVAL = 100   # Recording animation speed (fast, bouncy)
    PROCESSING_FRAME_INTERVAL = 300  # Processing animation speed (slower, calmer)

    def __init__(self):
        self.status_button = None
        self.animation_timer = None
        self.current_frame = 0
        self.current_state = None

        # Load static icons
        self._icons = {
            'idle': self._load_icon('menubar_idle')
        }

        # Load recording animation frames (3 frames, ping-pong sequence)
        self._recording_frames = [
            self._load_icon(f'menubar_recording_{i}')
            for i in range(1, 4)
        ]
        # Ping-pong sequence: 1→2→3→2→1→2→3→2... (indices: 0,1,2,1,0,1,2,1...)
        self._recording_sequence = [0, 1, 2, 1]

        # Load processing animation frames (3 frames, simple loop)
        self._processing_frames = [
            self._load_icon(f'menubar_processing_{i}')
            for i in range(1, 4)
        ]
        # Simple loop: 1→2→3→1→2→3... (indices: 0,1,2,0,1,2...)
        self._processing_sequence = [0, 1, 2]

    def _load_icon(self, icon_name):
        """Load a menu bar icon with @2x retina support."""
        # Get icon directory
        if getattr(sys, 'frozen', False):
            base_path = os.path.join(os.path.dirname(sys.executable), '..', 'Resources')
        else:
            base_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'icons')

        icon_1x_path = os.path.join(base_path, f'{icon_name}.png')
        icon_2x_path = os.path.join(base_path, f'{icon_name}@2x.png')

        # Create NSImage with both resolutions
        icon = NSImage.alloc().initWithSize_((22, 22))

        if os.path.exists(icon_1x_path):
            rep = NSImage.alloc().initWithContentsOfFile_(icon_1x_path)
            if rep and rep.representations():
                icon.addRepresentation_(rep.representations()[0])

        if os.path.exists(icon_2x_path):
            rep = NSImage.alloc().initWithContentsOfFile_(icon_2x_path)
            if rep and rep.representations():
                icon.addRepresentation_(rep.representations()[0])

        icon.setTemplate_(True)  # Enable automatic dark mode inversion
        return icon

    def set_button(self, button):
        """Set the NSStatusBarButton to update."""
        self.status_button = button

    def update_state(self, state_name):
        """
        Update menu bar icon for the given state.

        Args:
            state_name: One of 'idle', 'recording', or 'transcribing'
        """
        if state_name == self.current_state:
            return  # Already in this state

        self.current_state = state_name

        if state_name == 'recording':
            self._start_recording_animation()
        elif state_name == 'transcribing':
            self._start_processing_animation()
        else:
            self._stop_animation()
            self._set_icon(self._icons.get(state_name, self._icons['idle']))

    def _set_icon(self, icon):
        """Set the menu bar icon (thread-safe)."""
        if self.status_button is not None and icon is not None:
            try:
                self.status_button.performSelectorOnMainThread_withObject_waitUntilDone_(
                    'setImage:', icon, False
                )
            except Exception:
                pass

    def _start_recording_animation(self):
        """Start the recording animation (ping-pong: 1→2→3→2→1)."""
        self._stop_animation()
        self.current_frame = 0

        def animate():
            if self.current_state == 'recording' and self.status_button is not None:
                frame_idx = self._recording_sequence[self.current_frame]
                self._set_icon(self._recording_frames[frame_idx])
                self.current_frame = (self.current_frame + 1) % len(self._recording_sequence)

                self.animation_timer = threading.Timer(self.RECORDING_FRAME_INTERVAL / 1000, animate)
                self.animation_timer.daemon = True
                self.animation_timer.start()

        animate()

    def _start_processing_animation(self):
        """Start the processing animation (loop: 1→2→3→1→2→3)."""
        self._stop_animation()
        self.current_frame = 0

        def animate():
            if self.current_state == 'transcribing' and self.status_button is not None:
                frame_idx = self._processing_sequence[self.current_frame]
                self._set_icon(self._processing_frames[frame_idx])
                self.current_frame = (self.current_frame + 1) % len(self._processing_sequence)

                self.animation_timer = threading.Timer(self.PROCESSING_FRAME_INTERVAL / 1000, animate)
                self.animation_timer.daemon = True
                self.animation_timer.start()

        animate()

    def _stop_animation(self):
        """Stop any running animation."""
        if self.animation_timer is not None:
            self.animation_timer.cancel()
            self.animation_timer = None


# Global icon manager instance
_icon_manager = MenuBarIconManager()


def update_menu_bar_icon(state_name):
    """
    Update the menu bar icon state. This is the only function the app needs to call.

    Args:
        state_name: One of 'idle', 'recording', or 'transcribing'
    """
    _icon_manager.update_state(state_name)


# ============================================================================
# Whisper Model Initialization
# ============================================================================

def initialize_whisper():
    """
    Initialize the Whisper backend and return a transcription function.

    This is the ONLY function that knows about the specific Whisper backend.
    To switch backends (e.g. faster-whisper, whisper.cpp), only modify this function.
    The returned callable must accept a float32 numpy array and return a string.

    All MLX/Metal GPU operations are pinned to a single dedicated thread to avoid
    Metal command buffer threading assertions.

    Returns:
        callable: transcribe(audio_float: np.ndarray) -> str
    """
    import queue

    work_q = queue.Queue()
    result_q = queue.Queue()

    def mlx_worker():
        """Dedicated thread — all MLX/Metal operations happen here."""
        try:
            import mlx_whisper

            # Pre-warm: download + load model on this thread
            silent_audio = np.zeros(SAMPLE_RATE, dtype=np.float32)
            mlx_whisper.transcribe(silent_audio, path_or_hf_repo=WHISPER_MODEL, language="en")
            result_q.put(True)

            # Process transcription requests forever
            while True:
                audio_float = work_q.get()
                try:
                    result = mlx_whisper.transcribe(
                        audio_float,
                        path_or_hf_repo=WHISPER_MODEL,
                        language="en",
                    )
                    result_q.put(result)  # Return full dict for inspection
                except Exception as e:
                    result_q.put(e)
        except Exception as e:
            result_q.put(e)

    try:
        logger.info(f"Loading Whisper model: {WHISPER_MODEL}")

        worker = threading.Thread(target=mlx_worker, daemon=True)
        worker.start()

        # Wait for pre-warm to complete
        warmup_result = result_q.get()
        if isinstance(warmup_result, Exception):
            raise warmup_result

        logger.info(f"Whisper model loaded: {WHISPER_MODEL}")

        def transcribe(audio_float):
            work_q.put(audio_float)
            result = result_q.get()
            if isinstance(result, Exception):
                raise result
            return result

        return transcribe

    except Exception as e:
        logger.error(f"FATAL ERROR: Failed to load Whisper model")
        logger.error(f"Details: {e}")
        logger.error("Please check your internet connection (first download) and try again.")
        # Exit 0 so LaunchAgent KeepAlive doesn't create an infinite restart loop
        sys.exit(0)


# ============================================================================
# VAD (Voice Activity Detection) Initialization
# ============================================================================

def initialize_vad():
    """
    Initialize Silero VAD model for silence detection.

    Returns:
        tuple: (model, utils) or (None, None) on failure
    """
    try:
        logger.info("Loading Silero VAD model...")
        import torch

        # Load Silero VAD model and utilities
        model, utils = torch.hub.load(
            repo_or_dir='snakers4/silero-vad',
            model='silero_vad',
            force_reload=False,
            onnx=False,  # Use PyTorch model for better compatibility
            trust_repo=True  # Suppress security warning
        )

        logger.info("Silero VAD model loaded")
        return model, utils
    except Exception as e:
        logger.error(f"Failed to load Silero VAD model: {e}")
        logger.warning("Continuing without VAD - hallucinations may occur on silence")
        return None, None


def contains_speech(audio_float, sample_rate=SAMPLE_RATE, vad_model=None, vad_utils=None):
    """
    Check if audio contains speech using Silero VAD.

    Args:
        audio_float: Audio as float32 numpy array [-1.0, 1.0]
        sample_rate: Sample rate (default: 16000)
        vad_model: Silero VAD model (if None, skips VAD check)
        vad_utils: Silero VAD utilities tuple (if None, skips VAD check)

    Returns:
        True if speech detected or VAD unavailable, False if silence detected
    """
    if vad_model is None or vad_utils is None:
        return True  # If VAD not available, proceed with transcription

    try:
        import torch

        # Convert to torch tensor
        audio_tensor = torch.from_numpy(audio_float)

        # Extract get_speech_timestamps function from utils
        get_speech_timestamps = vad_utils[0]

        speech_timestamps = get_speech_timestamps(
            audio_tensor,
            vad_model,
            sampling_rate=sample_rate,
            threshold=0.5,  # Confidence threshold (0.3-0.6 recommended)
            min_speech_duration_ms=250,  # Minimum speech duration
            min_silence_duration_ms=100,  # Minimum silence duration to split
            return_seconds=False  # Return in samples, not seconds
        )

        # If we found any speech segments, return True
        has_speech = len(speech_timestamps) > 0

        if not has_speech:
            logger.info("VAD: No speech detected in audio")
        else:
            logger.debug(f"VAD: Detected {len(speech_timestamps)} speech segment(s)")

        return has_speech

    except Exception as e:
        logger.warning(f"VAD check failed: {e}, proceeding with transcription")
        return True  # On error, proceed with transcription


# ============================================================================
# Audio Recording Functions
# ============================================================================

def audio_callback(indata, frames, time_info, status):
    """
    Callback function for sounddevice audio stream.
    Called automatically for each audio chunk.

    Lock-free: deque.append() is atomic under CPython's GIL,
    so no lock is needed and no audio frames are ever dropped.

    Args:
        indata: Input audio data (numpy array)
        frames: Number of frames
        time_info: Time information
        status: Stream status flags
    """
    if status:
        logger.warning(f"Audio callback status: {status}")

    if state.is_recording:
        state.audio_buffer.append(indata.copy())


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

    state.audio_buffer.clear()
    state.overflow_files = []
    state.overflow_file_counter = 0
    state.recording_start_time = time.time()
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
        update_menu_bar_icon('recording')
        logger.debug(f"Recording started - Mode: {state.mode}")
    except Exception:
        # Guarantee clean state on failure
        _cleanup_stream()
        state.is_recording = False
        update_menu_bar_icon('idle')
        raise


def _cleanup_stream():
    """Safely close the audio stream with timeout. Idempotent — safe to call anytime.

    Uses a background thread with 2s timeout to prevent stream.stop()/close()
    from hanging and deadlocking the main lock (which blocks all key events).
    """
    if state.audio_stream is not None:
        stream = state.audio_stream
        state.audio_stream = None  # Clear reference immediately so state is clean

        def _close():
            try:
                stream.stop()
                stream.close()
            except Exception:
                pass

        t = threading.Thread(target=_close, daemon=True)
        t.start()
        t.join(timeout=2.0)
        if t.is_alive():
            if logger:
                logger.warning("Audio stream cleanup timed out (2s) — continuing anyway")


def cleanup_stale_overflow_files():
    """Delete leftover overflow .npy files from previous crashes. Called once at startup."""
    try:
        stale = list(OVERFLOW_DIR.glob(f"{OVERFLOW_PREFIX}*.npy"))
        for f in stale:
            try:
                f.unlink()
            except OSError:
                pass
        if stale:
            logger.info(f"Cleaned up {len(stale)} stale overflow file(s)")
    except Exception as e:
        logger.warning(f"Failed to clean stale overflow files: {e}")


def log_recording_stats(duration_sec, buffer_mb, mode, overflow_count, transcription_chars, processing_sec):
    """Append one JSON line of recording analytics to STATS_FILE."""
    try:
        entry = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "duration_sec": round(duration_sec, 2),
            "buffer_mb": round(buffer_mb, 2),
            "mode": mode,
            "overflow_files": overflow_count,
            "transcription_chars": transcription_chars,
            "processing_sec": round(processing_sec, 2),
        }
        with open(STATS_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception as e:
        logger.warning(f"Failed to log recording stats: {e}")


def flush_buffer_to_disk():
    """
    Flush the in-memory audio buffer to a .npy file on disk.

    Thread-safe two-phase design:
      Phase 1 (under lock): Snapshot buffer, clear it, increment counter.
      Phase 2 (no lock): Concatenate and write to disk.
      Phase 3 (under lock): Register the file path if still recording.
    On disk write failure, prepends data back into the buffer.
    """
    # Phase 1: drain deque and snapshot under lock
    with state.lock:
        if not state.audio_buffer:
            return
        snapshot = list(state.audio_buffer)
        state.audio_buffer.clear()
        state.overflow_file_counter += 1
        counter = state.overflow_file_counter

    # Phase 2: write to disk without holding the lock
    overflow_path = OVERFLOW_DIR / f"{OVERFLOW_PREFIX}{os.getpid()}_{counter}.npy"
    try:
        audio_data = np.concatenate(snapshot, axis=0)
        np.save(overflow_path, audio_data)
        logger.debug(f"Flushed buffer to disk: {overflow_path} ({audio_data.nbytes / (1024*1024):.1f}MB)")
    except Exception as e:
        logger.error(f"Failed to flush buffer to disk: {e}")
        # Prepend data back into buffer so nothing is lost
        with state.lock:
            state.audio_buffer.extendleft(reversed(snapshot))
        return

    # Phase 3: register the file if still recording
    with state.lock:
        if state.is_recording:
            state.overflow_files.append(overflow_path)
        else:
            # Recording ended during flush — clean up orphaned file
            try:
                overflow_path.unlink()
            except OSError:
                pass


def stop_recording():
    """
    Stop audio recording and trigger transcription.
    Must be called with state.lock held.

    Idempotent: safe to call even if not currently recording.
    Snapshots the buffer before cleanup so transcription thread owns its data.
    """
    # Snapshot buffer + overflow state, then clear — transcription thread gets its own copies
    buffer_snapshot = list(state.audio_buffer)
    state.audio_buffer.clear()
    overflow_snapshot = list(state.overflow_files)
    mode_snapshot = state.mode
    recording_stop_time = time.time()
    start_time_snapshot = state.recording_start_time
    state.overflow_files = []
    state.overflow_file_counter = 0
    state.recording_start_time = None
    state.is_recording = False
    _cleanup_stream()

    if not buffer_snapshot and not overflow_snapshot:
        logger.debug("Recording stopped - empty buffer, skipping transcription")
        update_menu_bar_icon('idle')
        return

    # Calculate buffer statistics (in-memory portion only)
    total_bytes = sum(chunk.nbytes for chunk in buffer_snapshot)
    buffer_size_mb = total_bytes / (1024 * 1024)

    # Estimate duration (chunks may vary in size, so calculate from total samples)
    total_samples = sum(len(chunk) for chunk in buffer_snapshot)
    duration_sec = total_samples / SAMPLE_RATE

    logger.debug(f"Recording stopped - Buffer: {buffer_size_mb:.1f}MB ({len(buffer_snapshot)} chunks, {duration_sec:.1f}s), overflow files: {len(overflow_snapshot)}")

    # Set transcription flag and update UI before spawning thread
    state.is_transcribing = True
    state.transcription_start_time = time.time()
    update_menu_bar_icon('transcribing')  # Show ⏳ icon

    # Transcription in separate thread — wrapper ensures cleanup
    threading.Thread(
        target=_transcription_wrapper,
        args=(buffer_snapshot,),
        kwargs={
            "overflow_files": overflow_snapshot,
            "recording_mode": mode_snapshot,
            "recording_start_time": start_time_snapshot,
            "recording_stop_time": recording_stop_time,
        },
        daemon=True,
    ).start()


def _transcription_wrapper(audio_buffer, **kwargs):
    """
    Wrapper for transcription thread that tracks state and ensures cleanup.
    Updates is_transcribing flag and menu state before/after transcription.
    Ensures flag is reset even if transcription fails.
    """
    try:
        transcribe_and_type(audio_buffer, **kwargs)
    finally:
        state.is_transcribing = False
        state.transcription_start_time = None
        update_menu_bar_icon('idle')  # Reset to 🎤 icon


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
    # Save to last_transcription with lock protection
    with state.lock:
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


# CFRange struct for extracting cursor position via ctypes
class _CFRange(ctypes.Structure):
    _fields_ = [("location", ctypes.c_long), ("length", ctypes.c_long)]

_ax_lib = ctypes.cdll.LoadLibrary(
    '/System/Library/Frameworks/ApplicationServices.framework/ApplicationServices'
)
_ax_lib.AXValueGetValue.restype = ctypes.c_bool
_ax_lib.AXValueGetValue.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p]
_kAXValueTypeCFRange = 4


def get_cursor_context(max_chars=CONTEXT_CHARS):
    """
    Read text around the cursor in the active application using macOS Accessibility APIs.

    Returns:
        tuple: (before_text, after_text) where each is a string or None on failure.
    """
    try:
        from ApplicationServices import AXUIElementCreateApplication
        from AppKit import NSWorkspace

        # Get the frontmost application's PID
        frontmost = NSWorkspace.sharedWorkspace().frontmostApplication()
        if frontmost is None:
            logger.debug("AX: No frontmost application found")
            return None, None
        pid = frontmost.processIdentifier()
        app_name = frontmost.localizedName()

        # Get the focused UI element from the app
        app_element = AXUIElementCreateApplication(pid)
        err, focused = AXUIElementCopyAttributeValue(
            app_element, kAXFocusedUIElementAttribute, None
        )
        if err != kAXErrorSuccess or focused is None:
            logger.debug(f"AX: No focused element in {app_name} (err={err})")
            return None, None

        # Get text value
        err, value = AXUIElementCopyAttributeValue(
            focused, kAXValueAttribute, None
        )
        if err != kAXErrorSuccess or value is None:
            logger.debug(f"AX: No text value in focused element (err={err})")
            return None, None

        text = str(value)
        if not text:
            return "", ""

        # Get cursor position using ctypes to extract CFRange from AXValueRef
        err, range_val = AXUIElementCopyAttributeValue(
            focused, kAXSelectedTextRangeAttribute, None
        )
        if err != kAXErrorSuccess or range_val is None:
            logger.debug(f"AX: No cursor position available (err={err})")
            return None, None

        cf_range = _CFRange()
        ax_ptr = objc.pyobjc_id(range_val)
        if not _ax_lib.AXValueGetValue(ax_ptr, _kAXValueTypeCFRange, ctypes.byref(cf_range)):
            logger.debug("AX: Failed to extract CFRange from AXValueRef")
            return None, None

        cursor_pos = cf_range.location

        before = text[max(0, cursor_pos - max_chars):cursor_pos]
        after = text[cursor_pos:cursor_pos + max_chars]

        logger.debug(f"AX: Cursor context from {app_name}: {len(before)} chars before, {len(after)} chars after (pos {cursor_pos})")
        return before, after

    except Exception as e:
        logger.debug(f"AX: Cursor context detection failed: {e}")
        return None, None


# ============================================================================
# Text Post-Processing
# ============================================================================

def post_process(text, context_before, context_after):
    """
    Apply post-processing transformations to transcribed text.

    Args:
        text: Raw transcribed text
        context_before: Text preceding the cursor (may be None or empty string)
        context_after: Text following the cursor (may be None or empty string)

    Returns:
        str: Post-processed text ready for insertion
    """
    # Only add a leading space if:
    # - There's actual non-whitespace text before the cursor (not empty/None/whitespace-only)
    # - We're not at the start of a new line (after a newline character)
    # - The text before doesn't end with whitespace
    # - Our transcribed text doesn't start with whitespace
    should_add_leading_space = False
    if (context_before and text and
        context_before.strip() and  # Has actual non-whitespace content
        context_before[-1] != '\n' and  # Not at start of new line
        not context_before[-1].isspace() and  # Not after any whitespace
        not text[0].isspace()):  # Text doesn't start with space
        should_add_leading_space = True
        text = " " + text

    # Only add trailing space if context after doesn't start with a space
    should_add_trailing_space = True
    if context_after and context_after[0].isspace():
        should_add_trailing_space = False

    if should_add_trailing_space and not text.endswith(" "):
        text = text + " "

    return text


def transcribe_and_type(audio_buffer, overflow_files=None, recording_mode=None, recording_start_time=None, recording_stop_time=None):
    """
    Transcribe recorded audio using Whisper and type the result.

    Args:
        audio_buffer: List of numpy arrays containing recorded audio chunks (in-memory tail)
        overflow_files: List of Path objects to .npy overflow files (earlier audio, in order)
        recording_mode: "hold" or "toggle" — for stats logging
        recording_start_time: time.time() when recording started — for stats logging
        recording_stop_time: time.time() when recording stopped — for stats logging
    """
    if overflow_files is None:
        overflow_files = []

    try:
        # Load overflow files first (earlier audio), then append in-memory buffer
        all_chunks = []
        for fpath in overflow_files:
            try:
                chunk = np.load(fpath)
                all_chunks.append(chunk)
            except Exception as e:
                logger.error(f"Failed to load overflow file {fpath}: {e}")
                # Continue — partial transcription is better than nothing

        all_chunks.extend(audio_buffer)

        if not all_chunks:
            logger.warning("No audio recorded")
            return

        # Combine all audio chunks into single array
        audio_data = np.concatenate(all_chunks, axis=0)

        # Convert from int16 to float32 and normalize to [-1.0, 1.0]
        audio_float = audio_data.astype(np.float32) / 32768.0
        audio_float = audio_float.flatten()

        # Check minimum duration
        duration = len(audio_float) / SAMPLE_RATE
        if duration < MIN_RECORDING_DURATION:
            logger.info(f"Audio too short ({duration:.2f}s), skipping transcription (minimum: {MIN_RECORDING_DURATION}s)")
            return

        logger.debug(f"Transcribing {duration:.2f}s of audio...")

        # VAD check: Skip transcription if no speech detected
        if not contains_speech(audio_float, SAMPLE_RATE, state.vad_model, state.vad_utils):
            logger.info("Skipping transcription - no speech detected by VAD")
            return

        # Capture cursor context (kept for future use)
        context_before, context_after = get_cursor_context()

        # Transcribe with Whisper
        processing_start = time.time()
        result = state.whisper_model(audio_float)

        # Extract text and check for hallucinations
        if isinstance(result, dict):
            text = result.get("text", "").strip()
            segments = result.get("segments", [])

            # Backup hallucination detection (chars/sec check)
            # VAD is the primary filter, but this catches edge cases where VAD
            # lets through quiet audio that Whisper hallucinates on
            if segments:
                first_segment = segments[0]
                segment_duration = first_segment.get("end", 0) - first_segment.get("start", 0)
                chars_per_sec = len(text) / segment_duration if segment_duration > 0 else 0

                # Real speech: 10-50 chars/sec, Sparse hallucinations: < 3 chars/sec
                if chars_per_sec < 3.0 and segment_duration > 1.0:
                    logger.info(f"Backup hallucination filter triggered ({chars_per_sec:.1f} chars/sec)")
                    return
        else:
            text = str(result).strip()

        if not text:
            logger.info("No speech detected")
            return

        # Post-process transcribed text
        text = post_process(text, context_before, context_after)

        # Only log transcription content in debug mode (may contain sensitive data)
        logger.debug(f"Transcription: {text}")
        logger.info(f"Transcribed {len(text)} characters")

        # Insert the text at cursor position
        insert_text(text)
        processing_sec = time.time() - processing_start

        # Log recording analytics
        rec_duration = (recording_stop_time - recording_start_time) if (recording_start_time and recording_stop_time) else duration
        buffer_mb = audio_data.nbytes / (1024 * 1024)
        logger.info(f"Processing took {processing_sec:.2f}s")
        log_recording_stats(rec_duration, buffer_mb, recording_mode, len(overflow_files), len(text), processing_sec)

    except Exception as e:
        logger.error(f"Transcription error: {e}")
        if DEBUG:
            import traceback
            traceback.print_exc()
    finally:
        # Clean up overflow files
        for fpath in overflow_files:
            try:
                if fpath.exists():
                    fpath.unlink()
            except OSError:
                pass


# ============================================================================
# Keyboard Event Handlers
# ============================================================================

def on_press(key):
    """
    Handle keyboard key press events.

    State machine transitions on press:
      mode=None   + hotkey              → hold mode, start recording
      mode=None   + hotkey (space held) → toggle mode, start recording
      mode=None   + space (hotkey held) → toggle mode, start recording
      mode=hold   + space               → convert to toggle mode (keep recording)
      mode=hold   + hotkey              → missed release recovery, stop recording
      mode=toggle + hotkey              → stop recording, mode=None

    Stuck state recovery (before normal transitions):
      mode set + not recording + has data → salvage partial recording, reset
      mode set + not recording + no data  → reset to idle, then start new recording
      transcription hung (>60s)           → clear flag so user can record again
    """
    current_time = time.time() * 1000  # Convert to milliseconds

    try:
        with state.lock:
            if is_hotkey(key):
                # Debounce: ignore if too soon after last press
                if current_time - state.last_press_time < DEBOUNCE_MS:
                    return

                state.last_press_time = current_time
                state.hotkey_pressed = True

                # --- Stuck state recovery ---
                # Detect mode/recording desync (mode set but not recording)
                if state.mode is not None and not state.is_recording:
                    has_data = bool(state.audio_buffer or state.overflow_files)
                    if has_data:
                        # Stream crashed mid-recording but buffer has audio.
                        # Salvage: transcribe what we captured, then reset.
                        logger.warning(f"Stuck recovery: mode={state.mode}, not recording, buffer has data. Salvaging partial recording...")
                        try:
                            stop_recording()
                        finally:
                            state.mode = None
                        return  # User presses again to start fresh
                    else:
                        # Recording never actually started (or buffer empty).
                        # Safe to reset — fall through to start a new recording.
                        logger.warning(f"Stuck recovery: mode={state.mode}, not recording, no data. Resetting to idle.")
                        _cleanup_stream()
                        state.mode = None
                        update_menu_bar_icon('idle')
                        # Fall through to state.mode is None → start new recording

                # Detect hung transcription (>60s) blocking the UI
                if state.mode is None and not state.is_recording and state.is_transcribing:
                    if state.transcription_start_time and (time.time() - state.transcription_start_time > 60):
                        logger.warning(f"Stuck recovery: transcription hung for >{time.time() - state.transcription_start_time:.0f}s. Clearing flag.")
                        state.is_transcribing = False
                        state.transcription_start_time = None
                        update_menu_bar_icon('idle')
                    # Note: even with is_transcribing=True, user CAN start a new
                    # recording (transcription runs in its own thread). Fall through.

                # --- Normal state machine ---
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
                    try:
                        stop_recording()
                    finally:
                        state.mode = None
                    logger.info("Toggle mode: Recording stopped")

                elif state.mode == "hold" and state.is_recording:
                    # Hotkey pressed while in hold mode — release event was missed.
                    # Stop recording and reset so the user can start fresh.
                    logger.warning("Hold mode: Hotkey pressed again (missed release?), stopping recording")
                    try:
                        stop_recording()
                    finally:
                        state.mode = None

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
    except Exception as e:
        if logger:
            logger.error(f"Error in on_press handler: {e}")


def on_release(key):
    """
    Handle keyboard key release events.

    State machine transitions on release:
      mode=hold + hotkey released → stop recording, mode=None
      (toggle mode ignores hotkey release — stop happens on next hotkey press)

    Stuck state recovery:
      mode=hold + not recording → reset mode to None (stream crashed)
    """
    try:
        with state.lock:
            if is_hotkey(key):
                state.hotkey_pressed = False

                if state.mode == "hold" and state.is_recording:
                    try:
                        stop_recording()
                    finally:
                        state.mode = None
                    logger.info("Hold mode: Recording stopped")

                elif state.mode == "hold" and not state.is_recording:
                    # Stuck: hold mode but not recording (stream died).
                    # Salvage any data, then reset.
                    has_data = bool(state.audio_buffer or state.overflow_files)
                    if has_data:
                        logger.warning("Stuck recovery (release): mode=hold, not recording, salvaging data.")
                        try:
                            stop_recording()
                        finally:
                            state.mode = None
                    else:
                        logger.warning("Stuck recovery (release): mode=hold, not recording, no data. Resetting.")
                        _cleanup_stream()
                        state.mode = None
                        update_menu_bar_icon('idle')

            elif key == TOGGLE_KEY:
                state.space_pressed = False
    except Exception as e:
        if logger:
            logger.error(f"Error in on_release handler: {e}")


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
    logger.error("Please enable 'Not Wispr Flow' in System Settings > Accessibility and restart")
    logger.error("=" * 60)
    sys.exit(0)  # Clean exit so KeepAlive does NOT restart


# ============================================================================
# Instance Lock
# ============================================================================

PID_FILE = Path.home() / 'Library' / 'Logs' / 'NotWisprFlow' / 'notwisprflow.pid'
OVERFLOW_DIR = Path.home() / 'Library' / 'Logs' / 'NotWisprFlow'  # Reuses log dir (already 0o700)
OVERFLOW_PREFIX = "notwisprflow_overflow_"
STATS_FILE = Path(__file__).resolve().parent / 'recording_stats.jsonl'


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
        # Thread-safe read of last_transcription
        with state.lock:
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

    # Register button with icon manager and set initial icon
    _icon_manager.set_button(button)
    update_menu_bar_icon('idle')

    delegate = MenuDelegate.alloc().init()
    delegate.shutdown_event = shutdown_event

    menu = NSMenu.alloc().init()
    menu.setMinimumWidth_(180)  # Set minimum width for the menu dropdown

    # Retype Last — grayed out when no transcription available
    retype_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
        "Retype last transcript", "retypeLast:", ""
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
        "Quit Not Wispr Flow", "quit:", "q"  # Cmd+Q
    )
    quit_item.setTarget_(delegate)
    menu.addItem_(quit_item)

    status_item.setMenu_(menu)

    # Keep references alive
    return status_item, delegate


def health_monitor(listener, shutdown_event):
    """Background thread: monitors listener health, detects dead audio streams, and flushes buffer to disk."""
    while not shutdown_event.is_set():
        if not listener.is_alive():
            NSApplication.sharedApplication().terminate_(None)
            return

        # Check audio stream health during recording.
        # If the stream died, salvage any captured audio and reset to idle.
        # This catches stream crashes within ~5s so the user isn't left
        # talking into nothing for minutes.
        with state.lock:
            if state.is_recording and state.audio_stream is not None:
                try:
                    stream_alive = state.audio_stream.active
                except Exception:
                    stream_alive = False

                if not stream_alive:
                    has_data = bool(state.audio_buffer or state.overflow_files)
                    logger.warning(f"Health monitor: Audio stream died during recording (has data: {has_data}). Auto-recovering.")
                    try:
                        stop_recording()  # Will transcribe partial data if any
                    finally:
                        state.mode = None

        # Flush buffer to disk if it exceeds threshold (crash recovery)
        if state.is_recording:
            buffer_bytes = sum(c.nbytes for c in list(state.audio_buffer))
            if buffer_bytes / (1024 * 1024) >= FLUSH_BUFFER_THRESHOLD_MB:
                flush_buffer_to_disk()

        shutdown_event.wait(timeout=5)

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

    # Clean up overflow files from previous crashes
    cleanup_stale_overflow_files()

    # Prevent duplicate instances
    pid_lock = acquire_pid_lock()
    if pid_lock is None:
        logger.warning("Another Not Wispr Flow instance is already running. Exiting.")
        sys.exit(0)
    atexit.register(lambda: pid_lock.close())

    logger.info("=" * 60)
    logger.info("Not Wispr Flow - Voice Dictation Tool")
    logger.info("=" * 60)
    logger.info("")

    # Check microphone permissions
    if not test_microphone_access():
        sys.exit(0)  # Exit 0 so LaunchAgent KeepAlive doesn't restart loop

    # Check accessibility permissions (exits if not granted)
    check_accessibility_permission()

    # Initialize Whisper model
    state.whisper_model = initialize_whisper()

    # Initialize Silero VAD for silence detection
    state.vad_model, state.vad_utils = initialize_vad()

    # Initialize keyboard controller
    state.keyboard_controller = Controller()

    # Print usage instructions
    logger.info("=" * 60)
    logger.info("Not Wispr Flow is now running!")
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
        logger.info("Shutting down Not Wispr Flow...")
        listener.stop()
        with state.lock:
            if state.is_recording:
                stop_recording()
            else:
                _cleanup_stream()
            state.mode = None
            # Clean up any remaining overflow files
            for fpath in state.overflow_files:
                try:
                    if fpath.exists():
                        fpath.unlink()
                except OSError:
                    pass
            state.overflow_files = []
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
