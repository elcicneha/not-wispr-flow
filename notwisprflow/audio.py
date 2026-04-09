"""Audio recording lifecycle and buffer management for Not Wispr Flow.

Handles microphone recording, buffer overflow to disk, and recording stats.
"""

import json
import logging
import os
import threading
import time
from pathlib import Path

import numpy as np
import soundcard as sc

from .config import PAUSE_MEDIA_ON_RECORD
from .constants import SAMPLE_RATE
from .media_control import pause_media, resume_media

logger = logging.getLogger("notwisprflow")

# Buffer overflow constants
OVERFLOW_DIR = Path.home() / 'Library' / 'Logs' / 'NotWisprFlow'
OVERFLOW_PREFIX = "notwisprflow_overflow_"
STATS_FILE = Path.home() / 'Library' / 'Logs' / 'NotWisprFlow' / 'recording_stats.jsonl'


def recording_loop(state):
    """Background thread: records audio via SoundCard (CoreAudio) and appends to buffer.

    Uses SoundCard's context manager for clean resource management.
    Audio data is float32 in [-1, 1] range (SoundCard's native format).
    """
    try:
        mic_id = state.selected_mic_id
        if mic_id is not None:
            try:
                mic = sc.get_microphone(mic_id)
                logger.debug(f"Using selected microphone: {mic.name}")
            except Exception:
                logger.warning(f"Selected microphone not found (id={mic_id}), falling back to system default")
                mic = sc.default_microphone()
        else:
            mic = sc.default_microphone()
        with mic.recorder(samplerate=SAMPLE_RATE, channels=[0]) as rec:
            while state.is_recording:
                data = rec.record(numframes=SAMPLE_RATE // 10)
                if state.is_recording:
                    state.audio_buffer.append(data)
    except Exception as e:
        logger.error(f"Recording thread error: {e}")
        state.is_recording = False


def start_recording(state, update_icon_fn):
    """Start audio recording via SoundCard in a background thread.

    Must be called with state.lock held.
    On failure: guarantees state is clean (is_recording=False).
    Raises on failure so the caller can reset mode.

    Args:
        state: AppState instance
        update_icon_fn: callable(state_name) for menu bar icon updates
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
        state._recording_thread = threading.Thread(target=recording_loop, args=(state,), daemon=True)
        state._recording_thread.start()
        update_icon_fn('recording')
        logger.debug(f"Recording started - Mode: {state.mode}")

        # Pause media in background (don't block recording start)
        if PAUSE_MEDIA_ON_RECORD and not state.media_was_paused:
            def _pause_media_async():
                if pause_media(logger):
                    with state.lock:
                        state.media_was_paused = True
            threading.Thread(target=_pause_media_async, daemon=True).start()
    except Exception:
        state.is_recording = False
        update_icon_fn('idle')
        raise


def stop_recording(state, update_icon_fn, on_audio_ready_fn):
    """Stop audio recording and dispatch audio data.

    Must be called with state.lock held. Idempotent.
    Snapshots the buffer before cleanup.

    If audio data is available, calls on_audio_ready_fn(buffer, overflow, mode, start_time, stop_time).
    If empty, resumes media if needed and updates icon to idle.

    Args:
        state: AppState instance
        update_icon_fn: callable(state_name) for menu bar icon updates
        on_audio_ready_fn: callable(buffer, overflow, mode, start_time, stop_time) when audio is ready
    """
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

    if not buffer_snapshot and not overflow_snapshot:
        logger.debug("Recording stopped - empty buffer, skipping transcription")
        if state.media_was_paused:
            state.media_was_paused = False
            threading.Thread(target=resume_media, args=(logger,), daemon=True).start()
        update_icon_fn('idle')
        return

    # Calculate buffer statistics
    total_bytes = sum(chunk.nbytes for chunk in buffer_snapshot)
    buffer_size_mb = total_bytes / (1024 * 1024)
    total_samples = sum(len(chunk) for chunk in buffer_snapshot)
    duration_sec = total_samples / SAMPLE_RATE

    logger.debug(f"Recording stopped - Buffer: {buffer_size_mb:.1f}MB ({len(buffer_snapshot)} chunks, {duration_sec:.1f}s), overflow files: {len(overflow_snapshot)}")

    state.is_transcribing = True
    state.transcription_start_time = time.time()
    update_icon_fn('transcribing')

    on_audio_ready_fn(buffer_snapshot, overflow_snapshot, mode_snapshot, start_time_snapshot, recording_stop_time)


def cancel_recording(state):
    """Cancel current recording without transcribing. Must be called with state.lock held."""
    state.is_recording = False
    state.audio_buffer.clear()
    state.overflow_files = []
    state.overflow_file_counter = 0
    state.recording_start_time = None
    state.mode = None


def flush_buffer_to_disk(state):
    """Flush the in-memory audio buffer to a .npy file on disk.

    Thread-safe two-phase design:
      Phase 1 (under lock): Snapshot buffer, clear it, increment counter.
      Phase 2 (no lock): Concatenate and write to disk.
      Phase 3 (under lock): Register the file path if still recording.
    On disk write failure, prepends data back into the buffer.
    """
    with state.lock:
        if not state.audio_buffer:
            return
        snapshot = list(state.audio_buffer)
        state.audio_buffer.clear()
        state.overflow_file_counter += 1
        counter = state.overflow_file_counter

    overflow_path = OVERFLOW_DIR / f"{OVERFLOW_PREFIX}{os.getpid()}_{counter}.npy"
    try:
        audio_data = np.concatenate(snapshot, axis=0)
        np.save(overflow_path, audio_data)
        logger.debug(f"Flushed buffer to disk: {overflow_path} ({audio_data.nbytes / (1024*1024):.1f}MB)")
    except Exception as e:
        logger.error(f"Failed to flush buffer to disk: {e}")
        with state.lock:
            state.audio_buffer.extendleft(reversed(snapshot))
        return

    with state.lock:
        if state.is_recording:
            state.overflow_files.append(overflow_path)
        else:
            try:
                overflow_path.unlink()
            except OSError:
                pass


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
