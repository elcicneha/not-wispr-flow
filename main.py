#!/usr/bin/env python3
"""
Not Wispr Flow - Voice Dictation Tool for macOS

A background script that provides voice dictation with two recording modes:
1. Press-and-Hold: Hold Right Control to record, release to transcribe
2. Toggle Mode: Press Right Control + Space to start, Right Control to stop

Uses mlx-whisper for offline speech-to-text transcription (GPU-accelerated on Apple Silicon).
"""

import sys
import os

# Fix SSL certificates for py2app bundle — must run before any network imports.
# certifi.where() can return invalid paths in py2app bundles (resolves to system
# Python path instead of bundle path). httpx passes certifi.where() as cafile to
# ssl.create_default_context(), which then fails with FileNotFoundError.
import ssl
import certifi
_cert_path = certifi.where()
if not os.path.exists(_cert_path):
    _alt = os.path.join(os.path.dirname(certifi.__file__), 'cacert.pem')
    if os.path.exists(_alt):
        _cert_path = _alt
# Set SSL_CERT_FILE so httpx uses it directly (bypasses certifi.where() entirely)
if os.path.exists(_cert_path):
    os.environ['SSL_CERT_FILE'] = _cert_path
# Safety net: patch ssl.create_default_context to validate cafile paths
_orig_create_default_context = ssl.create_default_context
def _create_default_context(purpose=ssl.Purpose.SERVER_AUTH, *, cafile=None, capath=None, cadata=None):
    if cafile and not os.path.exists(cafile):
        cafile = _cert_path
    return _orig_create_default_context(purpose, cafile=cafile or _cert_path, capath=capath, cadata=cadata)
ssl.create_default_context = _create_default_context

import time
import threading
import numpy as np
import soundcard as sc
from pynput import keyboard
from pynput.keyboard import Key, Controller
import logging
import logging.handlers
from pathlib import Path
import ctypes
import fcntl
import signal
import atexit
import subprocess
import json
from collections import deque
import objc
from Quartz import (
    CGEventCreateKeyboardEvent, CGEventKeyboardSetUnicodeString,
    CGEventPost, CGEventSetFlags, kCGHIDEventTap,
)
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
    NSImage, NSPasteboard, NSData,
    NSEventModifierFlagControl, NSEventModifierFlagCommand,
    NSScrollView, NSTextView, NSPanel, NSButton, NSTextField,
    NSBezelStyleRounded, NSFont, NSColor,
    NSWindowStyleMaskTitled, NSWindowStyleMaskClosable,
    NSBackingStoreBuffered,
    NSLineBreakByWordWrapping,
)
from Foundation import NSMakeRect

# ============================================================================
# User Configuration - imported from config.py
# ============================================================================
from config import (HOTKEY_KEYS, TOGGLE_KEY, WHISPER_MODEL, DEBUG, LANGUAGE,
                    TRANSCRIPTION_MODE, GROQ_MODEL, GROQ_API_KEY,
                    LLM_MODEL, LLM_MODELS, LLM_TEMPERATURE,
                    LLM_PROMPT, USE_TYPE_MODE,
                    PAUSE_MEDIA_ON_RECORD, GEMINI_API_KEY)
from transcription import TranscriptionManager
from llm_processor import LLMProcessor, load_preference, save_preference
from media_control import pause_media, resume_media
from post_processing import post_process

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
    if TRANSCRIPTION_MODE not in ("offline", "online", "auto"):
        errors.append(f"TRANSCRIPTION_MODE must be 'offline', 'online', or 'auto', got '{TRANSCRIPTION_MODE}'")
    # Note: GROQ_API_KEY validation removed - TranscriptionManager handles it internally
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

        # Transcription manager (handles Groq API + local MLX Whisper + VAD)
        self.transcription_manager = None

        # LLM processor (optional post-processing via Gemini/Groq)
        self.llm_processor = None

        # Keyboard controller for typing output
        self.keyboard_controller = None

        # Recording thread (SoundCard recording loop)
        self._recording_thread = None

        # Thread safety lock
        self.lock = threading.Lock()

        # Key state tracking
        self.hotkey_pressed = False
        self.space_pressed = False
        self.cmd_pressed = False

        # Text insertion mode
        self.last_transcription = None   # stores last transcribed text for "Retype Last"
        self.use_type_mode = USE_TYPE_MODE  # False = clipboard paste (default), True = character-by-character

        # LLM model and prompt selection (runtime state, can be changed via menu bar)
        self.llm_model = load_preference("llm_model", LLM_MODEL)
        self.llm_prompt = load_preference("llm_prompt", LLM_PROMPT)


        # Model loading state (True while speech model is being loaded/downloaded)
        self.is_loading_model = False

        # Transcription state tracking
        self.is_transcribing = False     # True when transcription thread is running
        self.transcription_start_time = None  # When transcription started (for hang detection)

        # Debouncing
        self.last_press_time = 0

        # Buffer overflow to disk
        self.overflow_files = []        # Paths to flushed .npy temp files for current recording
        self.overflow_file_counter = 0  # Unique filename counter per recording
        self.recording_start_time = None  # For stats tracking

        # Media pause/resume during recording
        self.media_was_paused = False  # True if we paused media (so we know to resume)


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
    RECORDING_FRAME_INTERVAL = 200   # Recording animation speed (fast, bouncy)
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


# Menu delegate reference — set by main() after setup_menu_bar()
_menu_delegate = None


class _StatusUpdater(NSObject):
    """NSObject subclass for dispatching status menu item updates to the main thread."""

    def setLoading_(self, _):
        if _menu_delegate:
            _menu_delegate.status_item.setTitle_("Loading speech model\u2026")
            if _menu_delegate.hideable_items:
                for item in _menu_delegate.hideable_items:
                    item.setHidden_(True)

    def setReady_(self, _):
        if _menu_delegate:
            _menu_delegate.status_item.setTitle_("Ready")
            if _menu_delegate.hideable_items:
                for item in _menu_delegate.hideable_items:
                    item.setHidden_(False)

_status_updater = _StatusUpdater.alloc().init()


def _on_status_change(event, value):
    """Status callback for TranscriptionManager. Thread-safe."""
    if event == "loading_model":
        if value:
            state.is_loading_model = True
            update_menu_bar_icon('transcribing')
            _status_updater.performSelectorOnMainThread_withObject_waitUntilDone_(
                'setLoading:', None, False
            )
        else:
            state.is_loading_model = False
            if not state.is_recording and not state.is_transcribing:
                update_menu_bar_icon('idle')
            _status_updater.performSelectorOnMainThread_withObject_waitUntilDone_(
                'setReady:', None, False
            )


# ============================================================================
# Audio Recording Functions
# ============================================================================

def _recording_loop():
    """Background thread: records audio via SoundCard (CoreAudio) and appends to buffer.

    Uses SoundCard's context manager for clean resource management.
    When state.is_recording becomes False, the loop exits, the context
    manager closes CoreAudio cleanly — no hanging, no timeouts needed.

    Audio data is float32 in [-1, 1] range (SoundCard's native format).
    """
    try:
        mic = sc.default_microphone()
        with mic.recorder(samplerate=SAMPLE_RATE, channels=[0]) as rec:
            while state.is_recording:
                # Record in 100ms blocks so we check is_recording flag frequently
                data = rec.record(numframes=SAMPLE_RATE // 10)
                # deque.append() is GIL-atomic — no lock needed
                if state.is_recording:
                    state.audio_buffer.append(data)
    except Exception as e:
        if logger:
            logger.error(f"Recording thread error: {e}")
        # Reset state so the user isn't stuck
        state.is_recording = False
        update_menu_bar_icon('idle')


def start_recording():
    """
    Start audio recording via SoundCard in a background thread.
    Must be called with state.lock held.

    On failure: guarantees state is clean (is_recording=False).
    Raises on failure so the caller can reset mode.
    """
    # Wait for any previous recording thread to finish
    if state._recording_thread is not None and state._recording_thread.is_alive():
        logger.warning("Waiting for previous recording thread to finish...")
        state._recording_thread.join(timeout=2.0)
        if state._recording_thread.is_alive():
            logger.warning("Previous recording thread still alive after 2s — proceeding anyway")

    state.audio_buffer.clear()
    state.overflow_files = []
    state.overflow_file_counter = 0
    state.recording_start_time = time.time()

    try:
        state.is_recording = True
        state._recording_thread = threading.Thread(target=_recording_loop, daemon=True)
        state._recording_thread.start()
        update_menu_bar_icon('recording')
        logger.debug(f"Recording started - Mode: {state.mode}")

        # Pause media in background (don't block recording start)
        if PAUSE_MEDIA_ON_RECORD and not state.media_was_paused:
            def _pause_media_async():
                if pause_media(logger):
                    with state.lock:
                        state.media_was_paused = True
            threading.Thread(target=_pause_media_async, daemon=True).start()
    except Exception:
        # Guarantee clean state on failure
        state.is_recording = False
        update_menu_bar_icon('idle')
        raise


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


def log_recording_stats(duration_sec, buffer_mb, mode, overflow_count, transcription_chars, processing_sec, backend="unknown"):
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
            "backend": backend,
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
    state.is_recording = False  # Recording thread will exit its loop and clean up

    if not buffer_snapshot and not overflow_snapshot:
        logger.debug("Recording stopped - empty buffer, skipping transcription")
        # Resume media if we paused it
        if state.media_was_paused:
            state.media_was_paused = False
            threading.Thread(target=resume_media, args=(logger,), daemon=True).start()
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
        # Resume media if we paused it and not already recording again
        with state.lock:
            should_resume = state.media_was_paused and not state.is_recording
            if should_resume:
                state.media_was_paused = False
        if should_resume:
            resume_media(logger)
        update_menu_bar_icon('idle')  # Reset to 🎤 icon


# ============================================================================
# Transcription and Text Output
# ============================================================================

def _type_chunked(text, chunk_size=16, delay=0.008):
    """
    Type text by sending chunks of characters via CGEvent keyboard events.

    Uses CGEventKeyboardSetUnicodeString to send multiple characters per
    keyboard event — the same mechanism macOS input methods (CJK) use to
    commit entire words. Much faster than character-by-character typing
    while avoiding auto-period and character drop issues.

    500 chars → ~32 events × 8ms = ~256ms (vs 4s char-by-char).

    Args:
        text: The text to type
        chunk_size: Characters per keyboard event (default 16, max ~20)
        delay: Seconds between events (default 8ms)
    """
    for i in range(0, len(text), chunk_size):
        chunk = text[i:i + chunk_size]
        # Create key down/up events (virtual keycode 0 is arbitrary —
        # CGEventKeyboardSetUnicodeString overrides the actual character output)
        event_down = CGEventCreateKeyboardEvent(None, 0, True)
        event_up = CGEventCreateKeyboardEvent(None, 0, False)
        # Clear modifier flags so held keys (e.g. Cmd+Ctrl from retype shortcut)
        # don't cause characters to be interpreted as shortcuts
        CGEventSetFlags(event_down, 0)
        CGEventSetFlags(event_up, 0)
        CGEventKeyboardSetUnicodeString(event_down, len(chunk), chunk)
        CGEventKeyboardSetUnicodeString(event_up, len(chunk), chunk)
        CGEventPost(kCGHIDEventTap, event_down)
        CGEventPost(kCGHIDEventTap, event_up)
        time.sleep(delay)


def insert_text(text):
    """
    Insert transcribed text at cursor position.
    Uses clipboard paste by default (instant, unicode-safe) with concealed
    clipboard write to avoid polluting clipboard history.
    Falls back to character-by-character typing when use_type_mode is enabled.
    """
    with state.lock:
        state.last_transcription = text

    if state.use_type_mode:
        _type_chunked(text)
        return

    pb = NSPasteboard.generalPasteboard()
    old_clipboard = pb.stringForType_('public.utf8-plain-text')

    # Eagerly place transcription text on clipboard
    pb.clearContents()
    if not pb.setString_forType_(text, 'public.utf8-plain-text'):
        logger.error(f"Failed to set clipboard content ({len(text)} chars)")
        return

    # Mark as concealed so clipboard managers (Alfred, Paste, Maccy) ignore it
    pb.setData_forType_(NSData.data(), 'org.nspasteboard.ConcealedType')

    # Small delay for clipboard to settle, then simulate Cmd+V
    time.sleep(0.02)
    state.keyboard_controller.press(Key.cmd)
    state.keyboard_controller.press('v')
    state.keyboard_controller.release('v')
    state.keyboard_controller.release(Key.cmd)

    # Wait for paste to complete before restoring clipboard
    time.sleep(0.2)

    # Restore previous clipboard contents
    pb.clearContents()
    if old_clipboard is not None:
        pb.setString_forType_(old_clipboard, 'public.utf8-plain-text')


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

        # SoundCard outputs float32 in [-1.0, 1.0] range — just flatten
        audio_float = audio_data.flatten().astype(np.float32)

        # Check minimum duration
        duration = len(audio_float) / SAMPLE_RATE
        if duration < MIN_RECORDING_DURATION:
            logger.debug(f"Audio too short ({duration:.2f}s), skipping")
            return

        logger.debug(f"Transcribing {duration:.2f}s of audio...")

        # VAD check: Skip transcription if no speech detected
        if not state.transcription_manager.contains_speech(audio_float):
            logger.info("Skipping transcription - no speech detected by VAD")
            return

        # Capture cursor context (kept for future use)
        context_before, context_after = get_cursor_context()

        # Transcribe (Groq API or local MLX Whisper depending on mode)
        processing_start = time.time()
        result = state.transcription_manager.transcribe(audio_float)

        # Extract text and backend
        if isinstance(result, dict):
            text = result.get("text", "").strip()
            backend = result.get("backend", "unknown")
        else:
            text = str(result).strip()
            backend = "unknown"

        if not text:
            logger.info("Transcription returned empty text")
            return

        # Log original transcription (before post-processing)
        logger.info(f"Transcription: {text}")

        # Post-process transcribed text (includes LLM enhancement if enabled + online)
        text = post_process(text, context_before, context_after, backend=backend,
                            llm_model=state.llm_model, llm_processor=state.llm_processor)

        # Insert the text at cursor position
        insert_text(text)
        processing_sec = time.time() - processing_start

        # Log backend + timing summary (easy to grep/compare API vs local)
        total_sec = time.time() - recording_stop_time if recording_stop_time else processing_sec
        logger.info(f"Backend: {backend} | {len(text)} chars | {total_sec:.2f}s total ({processing_sec:.2f}s transcription)")

        # Log recording analytics
        rec_duration = (recording_stop_time - recording_start_time) if (recording_start_time and recording_stop_time) else duration
        buffer_mb = audio_data.nbytes / (1024 * 1024)
        log_recording_stats(rec_duration, buffer_mb, recording_mode, len(overflow_files), len(text), processing_sec, backend)

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

    # Ignore recording hotkeys while model is loading
    if state.is_loading_model:
        return

    try:
        with state.lock:
            if is_hotkey(key):
                # Debounce: ignore if too soon after last press
                if current_time - state.last_press_time < DEBOUNCE_MS:
                    return

                state.last_press_time = current_time
                state.hotkey_pressed = True

                # Cmd held = command combo (e.g. Ctrl+Cmd+C for retype), skip recording
                if state.cmd_pressed:
                    return

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
                        state.is_recording = False
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

            elif key in (Key.cmd, Key.cmd_r, Key.cmd_l):
                state.cmd_pressed = True

            elif state.hotkey_pressed and state.cmd_pressed and getattr(key, 'vk', None) == 8:
                # Ctrl+Cmd+C → Retype last transcription
                # Cancel accidental recording if hotkey was pressed before Cmd
                if state.is_recording:
                    state.is_recording = False
                    state.audio_buffer.clear()
                    state.overflow_files = []
                    state.mode = None
                    update_menu_bar_icon('idle')
                    logger.debug("Cancelled recording for Retype shortcut")
                text = state.last_transcription
                if text:
                    threading.Thread(target=_type_chunked, args=(text,), daemon=True).start()
                    logger.debug("Retype: typing last transcription via global shortcut")

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
                    # Stuck: hold mode but not recording (recording thread died).
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
                        state.is_recording = False
                        state.mode = None
                        update_menu_bar_icon('idle')

            elif key == TOGGLE_KEY:
                state.space_pressed = False

            elif key in (Key.cmd, Key.cmd_r, Key.cmd_l):
                state.cmd_pressed = False
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
        logger.debug("Testing microphone access...")

        # Try to record a brief test via SoundCard (CoreAudio)
        mic = sc.default_microphone()
        with mic.recorder(samplerate=SAMPLE_RATE, channels=[0]) as rec:
            rec.record(numframes=SAMPLE_RATE // 10)  # 100ms test

        logger.debug("Microphone access OK")
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
        logger.debug("Accessibility permission: OK")
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
STATS_FILE = Path.home() / 'Library' / 'Logs' / 'NotWisprFlow' / 'recording_stats.jsonl'


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

def _make_text_view(width, height, editable=True, font_size=13):
    """Create an NSScrollView + NSTextView pair for text editing."""
    scroll = NSScrollView.alloc().initWithFrame_(NSMakeRect(0, 0, width, height))
    scroll.setHasVerticalScroller_(True)
    scroll.setBorderType_(2)  # NSBezelBorder
    inner_w = width - 4
    tv = NSTextView.alloc().initWithFrame_(NSMakeRect(0, 0, inner_w, height))
    tv.setMinSize_(NSMakeRect(0, 0, inner_w, height).size)
    tv.setMaxSize_(NSMakeRect(0, 0, inner_w, 10000).size)
    tv.setVerticallyResizable_(True)
    tv.setHorizontallyResizable_(False)
    tv.textContainer().setWidthTracksTextView_(True)
    tv.setFont_(NSFont.systemFontOfSize_(font_size))
    tv.setAllowsUndo_(True)
    tv.setEditable_(editable)
    tv.setSelectable_(True)
    if not editable:
        tv.setBackgroundColor_(NSColor.controlBackgroundColor())
        tv.setTextColor_(NSColor.secondaryLabelColor())
    scroll.setDocumentView_(tv)
    return scroll, tv


class _PromptPanelController(NSObject):
    """Controller for the Personal Prompt editing panel with collapsible system prompt sections."""
    _panel = None
    _subtitle = None
    _personal_scroll = None
    _personal_tv = None
    _sections = None
    _cancel_btn = None
    _save_btn = None
    _should_save = False

    def doSave_(self, sender):
        """Save button: set flag and stop modal."""
        self._should_save = True
        NSApplication.sharedApplication().stopModal()

    def doCancel_(self, sender):
        """Cancel button: stop modal without saving."""
        self._should_save = False
        NSApplication.sharedApplication().stopModal()

    def toggleSection_(self, sender):
        """Toggle expand/collapse of a system prompt section."""
        idx = sender.tag()
        sec = self._sections[idx]
        sec["expanded"] = not sec["expanded"]
        arrow = "\u25BC" if sec["expanded"] else "\u25B6"
        sender.setTitle_(f"{arrow} {sec['label']}")
        self._relayout()

    def editSection_(self, sender):
        """Toggle between Edit and Save for a system prompt section."""
        idx = sender.tag()
        sec = self._sections[idx]

        if not sec["editing"]:
            # Start editing
            sec["editing"] = True
            sec["tv"].setEditable_(True)
            sec["tv"].setBackgroundColor_(NSColor.textBackgroundColor())
            sec["tv"].setTextColor_(NSColor.labelColor())
            self._panel.makeFirstResponder_(sec["tv"])
            sender.setTitle_("Save")
            sec["reset_btn"].setHidden_(False)
        else:
            # Save: persist override immediately
            new_text = sec["tv"].string()
            has_context = sec["variant"] == "with_context"
            if state.llm_processor:
                preset = state.llm_processor.get_preset_system_prompt(has_context)
                if new_text.strip() == preset.strip():
                    state.llm_processor.reset_custom_system_prompt(sec["variant"])
                else:
                    state.llm_processor.set_custom_system_prompt(sec["variant"], new_text)
            # Return to read-only
            sec["tv"].setEditable_(False)
            sec["tv"].setBackgroundColor_(NSColor.controlBackgroundColor())
            sec["tv"].setTextColor_(NSColor.secondaryLabelColor())
            sec["editing"] = False
            sender.setTitle_("Edit")
            # Update info label
            has_custom = state.llm_processor.has_custom_system_prompt(sec["variant"]) if state.llm_processor else False
            if has_custom:
                sec["info"].setStringValue_("Custom override")
            else:
                preset_name = state.llm_processor._prompt_config.get("display", "") if state.llm_processor else ""
                sec["info"].setStringValue_(f"From preset: {preset_name}")
            sec["reset_btn"].setHidden_(not has_custom)

    def resetSection_(self, sender):
        """Reset a system prompt section to the preset default and persist immediately."""
        idx = sender.tag()
        sec = self._sections[idx]
        has_context = sec["variant"] == "with_context"
        preset_text = ""
        preset_name = ""
        if state.llm_processor:
            state.llm_processor.reset_custom_system_prompt(sec["variant"])
            preset_text = state.llm_processor.get_preset_system_prompt(has_context)
            preset_name = state.llm_processor._prompt_config.get("display", "")
        sec["tv"].setString_(preset_text)
        sec["tv"].setEditable_(False)
        sec["tv"].setBackgroundColor_(NSColor.controlBackgroundColor())
        sec["tv"].setTextColor_(NSColor.secondaryLabelColor())
        sec["editing"] = False
        sec["edit_btn"].setTitle_("Edit")
        sec["reset_btn"].setHidden_(True)
        sec["info"].setStringValue_(f"From preset: {preset_name}")

    def _relayout(self, animate=True):
        """Reposition all views and resize panel based on current section expand states."""
        W = 420
        PAD = 20
        IW = W - 2 * PAD

        # Compute layout top-down (top = distance from top of content area)
        top = 8   # top padding
        sub_top = top
        top += 36  # subtitle (32) + gap (4)
        pp_top = top
        top += 128  # personal prompt (120) + gap (8)

        sec_layout = []
        for sec in self._sections:
            layout = {"disc_top": top}
            top += 28  # disclosure (24) + gap (4)
            if sec["expanded"]:
                layout["info_top"] = top
                top += 22  # info (18) + gap (4)
                layout["scroll_top"] = top
                top += 144  # scroll (140) + gap (4)
                layout["btn_top"] = top
                top += 30  # buttons (24) + gap (6)
            sec_layout.append(layout)

        top += 8  # gap before cancel/save
        btn_top = top
        top += 42  # buttons (30) + bottom padding (12)
        total_h = top

        # Convert top-offset to macOS Y (Y=0 at bottom)
        def mac_y(t, h):
            return total_h - t - h

        self._subtitle.setFrame_(NSMakeRect(PAD, mac_y(sub_top, 32), IW, 32))
        self._personal_scroll.setFrame_(NSMakeRect(PAD, mac_y(pp_top, 120), IW, 120))

        for sec, lay in zip(self._sections, sec_layout):
            sec["disclosure"].setFrame_(NSMakeRect(PAD, mac_y(lay["disc_top"], 24), IW, 24))
            if sec["expanded"]:
                sec["info"].setFrame_(NSMakeRect(PAD, mac_y(lay["info_top"], 18), IW, 18))
                sec["scroll"].setFrame_(NSMakeRect(PAD, mac_y(lay["scroll_top"], 140), IW, 140))
                sec["edit_btn"].setFrame_(NSMakeRect(PAD, mac_y(lay["btn_top"], 24), 60, 24))
                sec["reset_btn"].setFrame_(NSMakeRect(PAD + 70, mac_y(lay["btn_top"], 24), 120, 24))

            for key in ["info", "scroll", "edit_btn"]:
                sec[key].setHidden_(not sec["expanded"])
            if sec["expanded"]:
                has_custom = state.llm_processor.has_custom_system_prompt(sec["variant"]) if state.llm_processor else False
                sec["reset_btn"].setHidden_(not (has_custom or sec["editing"]))
            else:
                sec["reset_btn"].setHidden_(True)

        self._cancel_btn.setFrame_(NSMakeRect(W - 190, mac_y(btn_top, 30), 80, 30))
        self._save_btn.setFrame_(NSMakeRect(W - 100, mac_y(btn_top, 30), 80, 30))

        # Resize panel keeping top edge stable
        old_frame = self._panel.frame()
        content_rect = NSMakeRect(0, 0, W, total_h)
        new_frame = self._panel.frameRectForContentRect_(content_rect)
        top_y = old_frame.origin.y + old_frame.size.height
        final = NSMakeRect(old_frame.origin.x, top_y - new_frame.size.height,
                           new_frame.size.width, new_frame.size.height)
        if animate:
            self._panel.setFrame_display_animate_(final, True, True)
        else:
            self._panel.setFrame_display_(final, True)


class MenuDelegate(NSObject):
    """Handles all menu bar actions: Retype Last, Paste Mode toggle, LLM Model/Prompt pickers, Personal Prompt, Quit."""
    shutdown_event = None
    paste_mode_item = None
    llm_model_items = None   # dict: model_name -> NSMenuItem
    personal_prompt_item = None
    status_item = None       # always-visible status line ("Ready" / "Loading…" / "Downloading… X%")
    hideable_items = None    # items hidden during model loading

    def retypeLast_(self, sender):
        """Type last transcription character-by-character in a background thread."""
        with state.lock:
            text = state.last_transcription
        if text:
            threading.Thread(
                target=_type_chunked,
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
        logger.debug(f"Text insertion mode: {mode_name}")

    def selectLLMModel_(self, sender):
        """Switch LLM model (radio-button style selection)."""
        model_name = sender.representedObject()
        if model_name is None:
            return

        # Update state and processor
        state.llm_model = model_name
        if state.llm_processor:
            state.llm_processor.switch_model(model_name)

        # Save preference for persistence across restarts
        save_preference("llm_model", model_name)

        # Update checkmarks (radio-button: only one checked)
        if self.llm_model_items:
            for name, item in self.llm_model_items.items():
                item.setState_(NSOnState if name == model_name else NSOffState)

        display = LLM_MODELS.get(model_name, {}).get("display", model_name)
        logger.info(f"LLM model switched to: {display} ({model_name})")

    def editPersonalPrompt_(self, sender):
        """Open panel to edit personal prompt and system prompt overrides."""
        W = 420
        PAD = 20
        IW = W - 2 * PAD

        panel = NSPanel.alloc().initWithContentRect_styleMask_backing_defer_(
            NSMakeRect(0, 0, W, 100),  # dummy height, _relayout sets correct size
            NSWindowStyleMaskTitled | NSWindowStyleMaskClosable,
            NSBackingStoreBuffered,
            False,
        )
        panel.setTitle_("Personal Prompt")
        content = panel.contentView()

        ctrl = _PromptPanelController.alloc().init()
        ctrl._panel = panel

        # Subtitle
        subtitle = NSTextField.alloc().initWithFrame_(NSMakeRect(0, 0, IW, 32))
        subtitle.setStringValue_("Additional instructions for the LLM.\nLeave empty to disable.")
        subtitle.setBezeled_(False)
        subtitle.setDrawsBackground_(False)
        subtitle.setEditable_(False)
        subtitle.setSelectable_(False)
        subtitle.setFont_(NSFont.systemFontOfSize_(12))
        subtitle.setTextColor_(NSColor.secondaryLabelColor())
        subtitle.setLineBreakMode_(NSLineBreakByWordWrapping)
        content.addSubview_(subtitle)
        ctrl._subtitle = subtitle

        # Personal prompt text view (always editable)
        pp_scroll, pp_tv = _make_text_view(IW, 120)
        pp_tv.setString_((state.llm_processor._personal_prompt or "") if state.llm_processor else "")
        content.addSubview_(pp_scroll)
        ctrl._personal_scroll = pp_scroll
        ctrl._personal_tv = pp_tv

        # System prompt sections (collapsible)
        ctrl._sections = []
        section_defs = [
            ("with_context", "System Prompt (with context)"),
            ("no_context", "System Prompt (no context)"),
        ]
        for i, (variant, label) in enumerate(section_defs):
            has_context = variant == "with_context"

            # Disclosure button
            disc = NSButton.alloc().initWithFrame_(NSMakeRect(0, 0, IW, 24))
            disc.setTitle_(f"\u25B6 {label}")
            disc.setBordered_(False)
            disc.setFont_(NSFont.boldSystemFontOfSize_(12))
            disc.setAlignment_(0)  # NSTextAlignmentLeft
            disc.setTarget_(ctrl)
            disc.setAction_("toggleSection:")
            disc.setTag_(i)
            content.addSubview_(disc)

            # Info label
            info = NSTextField.alloc().initWithFrame_(NSMakeRect(0, 0, IW, 18))
            info.setBezeled_(False)
            info.setDrawsBackground_(False)
            info.setEditable_(False)
            info.setSelectable_(False)
            info.setFont_(NSFont.systemFontOfSize_(11))
            info.setTextColor_(NSColor.tertiaryLabelColor())
            content.addSubview_(info)

            # System prompt text view (read-only initially)
            sys_scroll, sys_tv = _make_text_view(IW, 140, editable=False, font_size=12)
            content.addSubview_(sys_scroll)

            # Edit button
            edit_btn = NSButton.alloc().initWithFrame_(NSMakeRect(0, 0, 60, 24))
            edit_btn.setTitle_("Edit")
            edit_btn.setBezelStyle_(NSBezelStyleRounded)
            edit_btn.setFont_(NSFont.systemFontOfSize_(11))
            edit_btn.setTarget_(ctrl)
            edit_btn.setAction_("editSection:")
            edit_btn.setTag_(i)
            content.addSubview_(edit_btn)

            # Reset button
            reset_btn = NSButton.alloc().initWithFrame_(NSMakeRect(0, 0, 120, 24))
            reset_btn.setTitle_("Reset to Preset")
            reset_btn.setBezelStyle_(NSBezelStyleRounded)
            reset_btn.setFont_(NSFont.systemFontOfSize_(11))
            reset_btn.setTarget_(ctrl)
            reset_btn.setAction_("resetSection:")
            reset_btn.setTag_(i)
            content.addSubview_(reset_btn)

            # Set initial text and info
            has_custom = state.llm_processor.has_custom_system_prompt(variant) if state.llm_processor else False
            if has_custom:
                sys_text = state.llm_processor.get_active_system_prompt(has_context)
                info_text = "Custom override"
            else:
                sys_text = state.llm_processor.get_preset_system_prompt(has_context) if state.llm_processor else ""
                preset_name = state.llm_processor._prompt_config.get("display", "") if state.llm_processor else ""
                info_text = f"From preset: {preset_name}"

            sys_tv.setString_(sys_text)
            info.setStringValue_(info_text)

            ctrl._sections.append({
                "variant": variant, "label": label,
                "disclosure": disc, "info": info,
                "scroll": sys_scroll, "tv": sys_tv,
                "edit_btn": edit_btn, "reset_btn": reset_btn,
                "expanded": False, "editing": False,
            })

        # Cancel button (Escape)
        cancel_btn = NSButton.alloc().initWithFrame_(NSMakeRect(0, 0, 80, 30))
        cancel_btn.setTitle_("Cancel")
        cancel_btn.setBezelStyle_(NSBezelStyleRounded)
        cancel_btn.setKeyEquivalent_("\x1b")
        content.addSubview_(cancel_btn)
        ctrl._cancel_btn = cancel_btn

        # Save button (Cmd+S)
        save_btn = NSButton.alloc().initWithFrame_(NSMakeRect(0, 0, 80, 30))
        save_btn.setTitle_("Save")
        save_btn.setBezelStyle_(NSBezelStyleRounded)
        save_btn.setKeyEquivalent_("s")
        save_btn.setKeyEquivalentModifierMask_(NSEventModifierFlagCommand)
        content.addSubview_(save_btn)
        ctrl._save_btn = save_btn

        # Wire save/cancel to controller methods
        save_btn.setTarget_(ctrl)
        save_btn.setAction_("doSave:")
        cancel_btn.setTarget_(ctrl)
        cancel_btn.setAction_("doCancel:")

        # Layout, center, and show
        ctrl._relayout(animate=False)
        panel.center()
        panel.makeFirstResponder_(pp_tv)

        app = NSApplication.sharedApplication()
        app.runModalForWindow_(panel)
        panel.orderOut_(None)

        if ctrl._should_save:
            # Save personal prompt
            new_personal = pp_tv.string()
            if state.llm_processor:
                state.llm_processor.set_personal_prompt(new_personal)

            # Also save any system prompt sections still in editing mode
            for sec in ctrl._sections:
                if sec["editing"] and state.llm_processor:
                    new_text = sec["tv"].string()
                    has_ctx = sec["variant"] == "with_context"
                    preset = state.llm_processor.get_preset_system_prompt(has_ctx)
                    if new_text.strip() == preset.strip():
                        state.llm_processor.reset_custom_system_prompt(sec["variant"])
                    else:
                        state.llm_processor.set_custom_system_prompt(sec["variant"], new_text)

            # Update menu item title
            has_active = bool(new_personal.strip())
            if not has_active and state.llm_processor:
                has_active = (
                    state.llm_processor.has_custom_system_prompt("with_context") or
                    state.llm_processor.has_custom_system_prompt("no_context")
                )
            if self.personal_prompt_item:
                self.personal_prompt_item.setTitle_(
                    "Personal Prompt (Active)" if has_active else "Personal Prompt..."
                )

    def openLogs_(self, sender):
        """Open the logs directory in Finder."""
        log_dir = Path.home() / 'Library' / 'Logs' / 'NotWisprFlow'
        log_file = log_dir / 'notwisprflow.log'

        # Open log file if it exists, otherwise open the directory
        if log_file.exists():
            subprocess.run(['open', str(log_file)], check=False)
        elif log_dir.exists():
            subprocess.run(['open', str(log_dir)], check=False)
        else:
            logger.warning("Log file not found")

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
    """Create a menu bar status icon with Retype Last, Paste Mode toggle, LLM Model picker, and Quit."""
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

    # Status — always visible, shows current state
    status_menu_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
        "Loading speech model\u2026", None, ""
    )
    status_menu_item.setEnabled_(False)
    menu.addItem_(status_menu_item)
    delegate.status_item = status_menu_item

    menu.addItem_(NSMenuItem.separatorItem())

    # Items hidden during model loading (collected below)
    hideable_items = []

    # Retype Last — grayed out when no transcription available
    retype_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
        "Retype last transcript", "retypeLast:", "c"
    )
    retype_item.setKeyEquivalentModifierMask_(NSEventModifierFlagControl | NSEventModifierFlagCommand)
    retype_item.setTarget_(delegate)
    menu.addItem_(retype_item)
    hideable_items.append(retype_item)

    sep1 = NSMenuItem.separatorItem()
    menu.addItem_(sep1)
    hideable_items.append(sep1)

    # Paste Mode toggle — checked by default (paste mode ON)
    paste_mode_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
        "Paste Mode", "togglePasteMode:", ""
    )
    paste_mode_item.setTarget_(delegate)
    paste_mode_item.setState_(NSOffState if state.use_type_mode else NSOnState)
    delegate.paste_mode_item = paste_mode_item
    menu.addItem_(paste_mode_item)
    hideable_items.append(paste_mode_item)

    # LLM Model submenu — built from LLM_MODELS in config.py
    llm_menu_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
        "LLM Model", None, ""
    )
    llm_submenu = NSMenu.alloc().init()
    llm_model_items = {}
    current_model = state.llm_model

    # Build submenu grouped by "group" field, with separators between groups
    last_group = "FIRST"  # sentinel to track group transitions
    for model_name, model_info in LLM_MODELS.items():
        group = model_info.get("group")
        # Add separator between different groups
        if group != last_group and last_group != "FIRST":
            llm_submenu.addItem_(NSMenuItem.separatorItem())
        last_group = group

        item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
            model_info["display"], "selectLLMModel:", ""
        )
        item.setTarget_(delegate)
        item.setRepresentedObject_(model_name)
        item.setState_(NSOnState if model_name == current_model else NSOffState)
        llm_submenu.addItem_(item)
        llm_model_items[model_name] = item

    llm_menu_item.setSubmenu_(llm_submenu)
    delegate.llm_model_items = llm_model_items
    menu.addItem_(llm_menu_item)
    hideable_items.append(llm_menu_item)

    # Personal Prompt — editable additional instructions for LLM
    has_personal = bool(state.llm_processor and state.llm_processor._personal_prompt)
    personal_title = "Prompts..."
    personal_prompt_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
        personal_title, "editPersonalPrompt:", ""
    )
    personal_prompt_item.setTarget_(delegate)
    delegate.personal_prompt_item = personal_prompt_item
    menu.addItem_(personal_prompt_item)
    hideable_items.append(personal_prompt_item)

    sep2 = NSMenuItem.separatorItem()
    menu.addItem_(sep2)
    hideable_items.append(sep2)

    # Open Logs
    logs_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
        "Open Logs", "openLogs:", ""
    )
    logs_item.setTarget_(delegate)
    menu.addItem_(logs_item)

    menu.addItem_(NSMenuItem.separatorItem())

    # Quit
    quit_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
        "Quit Not Wispr Flow", "quit:", "q"  # Cmd+Q
    )
    quit_item.setTarget_(delegate)
    menu.addItem_(quit_item)

    delegate.hideable_items = hideable_items

    status_item.setMenu_(menu)

    # Keep references alive
    return status_item, delegate


def health_monitor(listener, shutdown_event):
    """Background thread: monitors listener health, detects dead audio streams, and flushes buffer to disk."""
    while not shutdown_event.is_set():
        if not listener.is_alive():
            NSApplication.sharedApplication().terminate_(None)
            return

        # Check recording thread health during recording.
        # If the thread died, salvage any captured audio and reset to idle.
        # This catches recording crashes within ~5s so the user isn't left
        # talking into nothing for minutes.
        with state.lock:
            if state.is_recording and state._recording_thread is not None:
                if not state._recording_thread.is_alive():
                    has_data = bool(state.audio_buffer or state.overflow_files)
                    logger.warning(f"Health monitor: Recording thread died (has data: {has_data}). Auto-recovering.")
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

    logger.info("--- Not Wispr Flow starting ---")

    # Check microphone permissions
    if not test_microphone_access():
        sys.exit(0)  # Exit 0 so LaunchAgent KeepAlive doesn't restart loop

    # Check accessibility permissions (exits if not granted)
    check_accessibility_permission()

    # Initialize transcription manager (handles Groq API + local MLX Whisper + VAD)
    # Note: does NOT load the model yet — that happens in background after menu bar is up
    state.transcription_manager = TranscriptionManager(
        mode=TRANSCRIPTION_MODE,
        groq_api_key=GROQ_API_KEY,
        groq_model=GROQ_MODEL,
        whisper_model=WHISPER_MODEL,
        language=LANGUAGE,
        logger=logger,
        status_callback=_on_status_change,
    )

    # Initialize LLM processor (model may be overridden by saved preference)
    state.llm_processor = LLMProcessor(
        model=state.llm_model,
        temperature=LLM_TEMPERATURE,
        prompt=state.llm_prompt,
        logger=logger,
    )

    # Initialize keyboard controller
    state.keyboard_controller = Controller()

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
        if state.transcription_manager:
            state.transcription_manager.shutdown()
        listener.stop()
        with state.lock:
            if state.is_recording:
                stop_recording()
            state.is_recording = False  # Ensure recording thread exits
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

    # Set up menu bar icon (must be on main thread — appears immediately)
    global _menu_delegate
    _menu_refs = setup_menu_bar(shutdown_event)
    _menu_delegate = _menu_refs[1]  # MenuDelegate instance

    # Initialize transcription in background (model loading shows processing animation)
    def _init_transcription():
        try:
            state.transcription_manager.initialize()
        except Exception as e:
            logger.error(f"Failed to initialize transcription: {e}", exc_info=True)
            TranscriptionManager._show_error_dialog(
                "Could not start Not Wispr Flow.\n\n"
                "Check the logs for details."
            )
            NSApplication.sharedApplication().performSelectorOnMainThread_withObject_waitUntilDone_(
                'terminate:', None, False
            )
            return

        # Log startup summary
        llm_display = LLM_MODELS.get(state.llm_model, {}).get("display", state.llm_model)
        logger.info(f"Ready | Mode={TRANSCRIPTION_MODE}, LLM={llm_display}, Debug={'ON' if DEBUG else 'OFF'}")

    threading.Thread(target=_init_transcription, daemon=True).start()

    # Run macOS event loop (blocks until quit)
    NSApplication.sharedApplication().run()


# ============================================================================
# Entry Point
# ============================================================================

if __name__ == "__main__":
    main()
