#!/usr/bin/env python3
"""
Not Wispr Flow - Voice Dictation Tool for macOS

A background app that provides voice dictation with two recording modes:
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
from pynput import keyboard
from pynput.keyboard import Controller
import logging
import logging.handlers
from pathlib import Path
import fcntl
import signal
import atexit
from collections import deque

from AppKit import NSApplication
from Foundation import NSDate, NSDefaultRunLoopMode

from notwisprflow.config import (
    HOTKEY_KEYS, TOGGLE_KEY, WHISPER_MODEL, DEBUG, LANGUAGE,
    TRANSCRIPTION_MODE, GROQ_MODEL, GROQ_API_KEY,
    LLM_MODEL, LLM_MODELS, LLM_TEMPERATURE,
    LLM_PROMPT, USE_TYPE_MODE, START_AT_LOGIN,
)
from notwisprflow.constants import SAMPLE_RATE
from notwisprflow.transcription import TranscriptionManager
from notwisprflow.llm_processor import LLMProcessor
from notwisprflow.media_control import resume_media
from notwisprflow.post_processing import post_process
from notwisprflow.preferences import load_preference
from notwisprflow.startup import is_login_item_installed, install_login_item
from notwisprflow import menubar, audio, keyboard_handler
from notwisprflow.permissions import test_microphone_access, check_accessibility_permission
from notwisprflow.text_output import insert_text, get_cursor_context


# ============================================================================
# Logging Configuration
# ============================================================================

def setup_logging():
    """Configure logging with dual handlers: console + rotating file."""
    logger = logging.getLogger('notwisprflow')
    log_level = logging.DEBUG if DEBUG else logging.INFO
    logger.setLevel(log_level)
    logger.handlers.clear()

    formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    if sys.stdout.isatty():
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(log_level)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    try:
        log_dir = Path.home() / 'Library' / 'Logs' / 'NotWisprFlow'
        log_dir.mkdir(parents=True, exist_ok=True)
        os.chmod(log_dir, 0o700)

        log_file = log_dir / 'notwisprflow.log'
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=10 * 1024 * 1024,
            backupCount=5,
            encoding='utf-8'
        )
        file_handler.setLevel(log_level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except Exception as e:
        if sys.stdout.isatty():
            print(f"Warning: Could not setup file logging: {e}")
            print("Continuing with console logging only...")

    return logger

# Initialize logger (will be set in main())
logger = None


# ============================================================================
# Internal Configuration Constants
# ============================================================================

MIN_RECORDING_DURATION = 0.2  # Minimum recording length in seconds
FLUSH_BUFFER_THRESHOLD_MB = 5  # Flush buffer to disk when it exceeds this (MB)


def validate_config():
    """Validate configuration constants at startup. Exits on invalid config."""
    errors = []
    if not HOTKEY_KEYS or not isinstance(HOTKEY_KEYS, set):
        errors.append("HOTKEY_KEYS must be a non-empty set of Key values")
    if TOGGLE_KEY in HOTKEY_KEYS:
        errors.append("TOGGLE_KEY cannot be the same as a HOTKEY_KEYS entry")
    if not WHISPER_MODEL:
        errors.append("WHISPER_MODEL must be a non-empty HuggingFace model repo name")
    if TRANSCRIPTION_MODE not in ("offline", "online", "auto"):
        errors.append(f"TRANSCRIPTION_MODE must be 'offline', 'online', or 'auto', got '{TRANSCRIPTION_MODE}'")
    if errors:
        for e in errors:
            print(f"Configuration error: {e}", file=sys.stderr)
        sys.exit(0)


# ============================================================================
# Application State
# ============================================================================

class AppState:
    """Global application state management."""

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
# Transcription Pipeline
# ============================================================================

def transcribe_and_type(audio_buffer, overflow_files=None, recording_mode=None,
                        recording_start_time=None, recording_stop_time=None):
    """Transcribe recorded audio using Whisper and type the result.

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

        all_chunks.extend(audio_buffer)

        if not all_chunks:
            logger.warning("No audio recorded")
            return

        audio_data = np.concatenate(all_chunks, axis=0)
        audio_float = audio_data.flatten().astype(np.float32)

        duration = len(audio_float) / SAMPLE_RATE
        if duration < MIN_RECORDING_DURATION:
            logger.debug(f"Audio too short ({duration:.2f}s), skipping")
            return

        logger.debug(f"Transcribing {duration:.2f}s of audio...")

        # VAD check: Skip transcription if no speech detected
        if not state.transcription_manager.contains_speech(audio_float):
            logger.info("Skipping transcription - no speech detected by VAD")
            return

        context_before, context_after = get_cursor_context()

        # Transcribe (Groq API or local MLX Whisper depending on mode)
        processing_start = time.time()
        result = state.transcription_manager.transcribe(audio_float)

        if isinstance(result, dict):
            text = result.get("text", "").strip()
            backend = result.get("backend", "unknown")
        else:
            text = str(result).strip()
            backend = "unknown"

        if not text:
            logger.info("Transcription returned empty text")
            return

        logger.info(f"Transcription: {text}")

        # Post-process transcribed text (includes LLM enhancement if enabled + online)
        text = post_process(text, context_before, context_after, backend=backend,
                            llm_model=state.llm_model, llm_processor=state.llm_processor)

        insert_text(text, state)
        processing_sec = time.time() - processing_start

        total_sec = time.time() - recording_stop_time if recording_stop_time else processing_sec
        logger.info(f"Backend: {backend} | {len(text)} chars | {total_sec:.2f}s total ({processing_sec:.2f}s transcription)")

        rec_duration = (recording_stop_time - recording_start_time) if (recording_start_time and recording_stop_time) else duration
        buffer_mb = audio_data.nbytes / (1024 * 1024)
        audio.log_recording_stats(rec_duration, buffer_mb, recording_mode, len(overflow_files), len(text), processing_sec, backend)

    except Exception as e:
        logger.error(f"Transcription error: {e}")
        if DEBUG:
            import traceback
            traceback.print_exc()
    finally:
        for fpath in overflow_files:
            try:
                if fpath.exists():
                    fpath.unlink()
            except OSError:
                pass


def _transcription_wrapper(audio_buffer, **kwargs):
    """Wrapper for transcription thread that tracks state and ensures cleanup."""
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
        menubar.update_icon('idle')


def _on_audio_ready(buffer, overflow, mode, start_time, stop_time):
    """Callback from audio.stop_recording — spawns transcription thread."""
    threading.Thread(
        target=_transcription_wrapper,
        args=(buffer,),
        kwargs={
            "overflow_files": overflow,
            "recording_mode": mode,
            "recording_start_time": start_time,
            "recording_stop_time": stop_time,
        },
        daemon=True,
    ).start()


# ============================================================================
# Health Monitor
# ============================================================================

def health_monitor(listener, shutdown_event):
    """Background thread: monitors listener health, detects dead audio streams, and flushes buffer to disk."""
    while not shutdown_event.is_set():
        if not listener.is_alive():
            shutdown_event.set()
            return

        # Check recording thread health during recording.
        # If the thread died, salvage any captured audio and reset to idle.
        with state.lock:
            if state.is_recording and state._recording_thread is not None:
                if not state._recording_thread.is_alive():
                    has_data = bool(state.audio_buffer or state.overflow_files)
                    logger.warning(f"Health monitor: Recording thread died (has data: {has_data}). Auto-recovering.")
                    try:
                        audio.stop_recording(state, menubar.update_icon, _on_audio_ready)
                    finally:
                        state.mode = None

        # Flush buffer to disk if it exceeds threshold (crash recovery)
        if state.is_recording:
            buffer_bytes = sum(c.nbytes for c in list(state.audio_buffer))
            if buffer_bytes / (1024 * 1024) >= FLUSH_BUFFER_THRESHOLD_MB:
                audio.flush_buffer_to_disk(state)

        shutdown_event.wait(timeout=5)

    shutdown_event.set()


# ============================================================================
# Instance Lock
# ============================================================================

PID_FILE = Path.home() / 'Library' / 'Logs' / 'NotWisprFlow' / 'notwisprflow.pid'


def acquire_pid_lock():
    """Prevent duplicate instances using a PID file lock.

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
# Main Application
# ============================================================================

def main():
    global logger

    validate_config()
    logger = setup_logging()

    # Clean up overflow files from previous crashes
    audio.cleanup_stale_overflow_files()

    # Prevent duplicate instances
    pid_lock = acquire_pid_lock()
    if pid_lock is None:
        logger.warning("Another Not Wispr Flow instance is already running. Exiting.")
        sys.exit(0)
    atexit.register(lambda: pid_lock.close())

    logger.info("--- Not Wispr Flow starting ---")

    # Install login item on first run if config says so
    if START_AT_LOGIN and not is_login_item_installed():
        install_login_item()

    # Check permissions
    if not test_microphone_access():
        sys.exit(0)  # Exit 0 so LaunchAgent KeepAlive doesn't restart loop

    check_accessibility_permission()

    # Initialize transcription manager (does NOT load model yet — that happens in background)
    status_callback = menubar.create_status_callback(state)
    state.transcription_manager = TranscriptionManager(
        mode=TRANSCRIPTION_MODE,
        groq_api_key=GROQ_API_KEY,
        groq_model=GROQ_MODEL,
        whisper_model=WHISPER_MODEL,
        language=LANGUAGE,
        logger=logger,
        status_callback=status_callback,
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

    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)

    # Start keyboard listener
    on_press, on_release = keyboard_handler.create_handlers(
        state=state,
        update_icon_fn=menubar.update_icon,
        on_audio_ready_fn=_on_audio_ready,
    )
    listener = keyboard.Listener(on_press=on_press, on_release=on_release)
    listener.start()

    # Register cleanup for app termination
    def cleanup():
        logger.info("Shutting down Not Wispr Flow...")
        if state.transcription_manager:
            state.transcription_manager.shutdown()
        listener.stop()
        with state.lock:
            if state.is_recording:
                audio.stop_recording(state, menubar.update_icon, _on_audio_ready)
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

    # Start health monitoring in background thread
    health_thread = threading.Thread(
        target=health_monitor,
        args=(listener, shutdown_event),
        daemon=True
    )
    health_thread.start()

    # Set up menu bar icon (must be on main thread — appears immediately)
    _menu_refs = menubar.setup_menu_bar(shutdown_event, state)

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

        llm_display = LLM_MODELS.get(state.llm_model, {}).get("display", state.llm_model)
        logger.info(f"Ready | Mode={TRANSCRIPTION_MODE}, LLM={llm_display}, Debug={'ON' if DEBUG else 'OFF'}")

    threading.Thread(target=_init_transcription, daemon=True).start()

    # Run macOS event loop — manually pump events with a timeout so Python
    # gets control back periodically, allowing signal handlers (Ctrl+C) to fire.
    # NSApp.run() is a blocking C call that never yields to Python.
    app = NSApplication.sharedApplication()
    app.finishLaunching()
    try:
        while not shutdown_event.is_set():
            event = app.nextEventMatchingMask_untilDate_inMode_dequeue_(
                0xFFFFFFFFFFFFFFFF,  # NSEventMaskAny
                NSDate.dateWithTimeIntervalSinceNow_(0.5),
                NSDefaultRunLoopMode,
                True,
            )
            if event:
                app.sendEvent_(event)
                app.updateWindows()
    except KeyboardInterrupt:
        pass


# ============================================================================
# Entry Point
# ============================================================================

if __name__ == "__main__":
    main()
