#!/usr/bin/env python3
"""
Transcription backend for Not Wispr Flow.

Provides a unified TranscriptionManager that handles:
- Local MLX Whisper transcription (offline)
- Groq API transcription (online)
- Smart model lifecycle management (auto mode)
- Voice Activity Detection (VAD) via Silero ONNX

The rest of the app only interacts with TranscriptionManager.transcribe()
and TranscriptionManager.contains_speech().
"""

import os
import subprocess
import sys
import threading
import numpy as np

from .constants import SAMPLE_RATE
from .preferences import resolve_api_key


# ============================================================================
# VAD (Voice Activity Detection) — Numpy-only ONNX implementation
# ============================================================================

class SileroVADOnnx:
    """Numpy-only ONNX wrapper for Silero VAD (no torch dependency)."""

    def __init__(self, model_path):
        import onnxruntime as ort

        opts = ort.SessionOptions()
        opts.inter_op_num_threads = 1
        opts.intra_op_num_threads = 1
        opts.log_severity_level = 3

        self.session = ort.InferenceSession(
            model_path,
            providers=['CPUExecutionProvider'],
            sess_options=opts
        )
        self.reset_states()

    def reset_states(self, batch_size=1):
        self._state = np.zeros((2, batch_size, 128), dtype=np.float32)
        self._context = np.zeros((0,), dtype=np.float32)
        self._last_sr = 0
        self._last_batch_size = 0

    def __call__(self, x, sr=16000):
        if x.ndim == 1:
            x = x[np.newaxis, :]
        if x.ndim > 2:
            raise ValueError(f"Too many dimensions: {x.ndim}")

        batch_size = x.shape[0]
        num_samples = 512
        context_size = 64

        if x.shape[-1] != num_samples:
            raise ValueError(f"Expected {num_samples} samples, got {x.shape[-1]}")

        if not self._last_batch_size or self._last_sr != sr or self._last_batch_size != batch_size:
            self.reset_states(batch_size)

        if len(self._context) == 0:
            self._context = np.zeros((batch_size, context_size), dtype=np.float32)

        x_with_context = np.concatenate([self._context, x], axis=1)

        ort_inputs = {
            'input': x_with_context.astype(np.float32),
            'state': self._state.astype(np.float32),
            'sr': np.array(sr, dtype=np.int64)
        }
        ort_outs = self.session.run(None, ort_inputs)
        out, state = ort_outs

        self._state = state
        self._context = x_with_context[:, -context_size:]
        self._last_sr = sr
        self._last_batch_size = batch_size

        return out


def _get_speech_timestamps_numpy(audio, model, threshold=0.5, sampling_rate=16000,
                                 min_speech_duration_ms=250, min_silence_duration_ms=100,
                                 **kwargs):
    """Numpy-only version of get_speech_timestamps (no torch dependency)."""
    if audio.ndim > 1:
        audio = audio.flatten()

    model.reset_states()

    window_size_samples = 512
    min_speech_samples = sampling_rate * min_speech_duration_ms // 1000

    speech_probs = []
    for current_start in range(0, len(audio), window_size_samples):
        chunk = audio[current_start:current_start + window_size_samples]
        if len(chunk) < window_size_samples:
            chunk = np.pad(chunk, (0, window_size_samples - len(chunk)), mode='constant')
        speech_prob = model(chunk, sampling_rate)[0, 0]
        speech_probs.append(speech_prob)

    triggered = False
    speeches = []
    current_speech = {}

    for i, prob in enumerate(speech_probs):
        if prob >= threshold and not triggered:
            triggered = True
            current_speech = {'start': i * window_size_samples}
        elif prob < threshold and triggered:
            triggered = False
            current_speech['end'] = i * window_size_samples
            duration = current_speech['end'] - current_speech['start']
            if duration >= min_speech_samples:
                speeches.append(current_speech)
            current_speech = {}

    if triggered:
        current_speech['end'] = len(audio)
        duration = current_speech['end'] - current_speech['start']
        if duration >= min_speech_samples:
            speeches.append(current_speech)

    return speeches


def _initialize_vad(logger):
    """Initialize Silero VAD model using ONNX runtime."""
    try:
        if getattr(sys, 'frozen', False):
            bundle_dir = os.path.dirname(sys.executable)
            model_path = os.path.join(bundle_dir, '..', 'Resources', 'resources', 'silero_vad.onnx')
        else:
            model_path = os.path.join(os.path.dirname(__file__), '..', 'resources', 'silero_vad.onnx')

        model_path = os.path.abspath(model_path)

        if not os.path.exists(model_path):
            logger.error(f"FATAL: VAD model not found at {model_path}")
            logger.error("App bundle may be corrupted. Please reinstall.")
            return None, None

        logger.debug(f"Loading Silero VAD from {model_path}")
        model = SileroVADOnnx(model_path)
        utils = (_get_speech_timestamps_numpy,)
        logger.info("Silero VAD loaded")
        return model, utils

    except Exception as e:
        logger.error(f"Failed to load Silero VAD model: {e}", exc_info=True)
        logger.warning("Continuing without VAD - hallucinations may occur on silence")
        return None, None


# ============================================================================
# Local MLX Whisper backend
# ============================================================================

def _initialize_whisper(model_name, language, stop_event, logger):
    """
    Initialize MLX Whisper backend on a dedicated thread.

    All MLX/Metal GPU operations are pinned to a single thread to avoid
    Metal command buffer threading assertions.

    Args:
        model_name: HuggingFace model repo name
        language: Language code or None for auto-detect
        stop_event: threading.Event to signal the worker to exit
        logger: Logger instance

    Returns:
        callable: transcribe(audio_float: np.ndarray) -> dict
    """
    import queue

    work_q = queue.Queue()
    result_q = queue.Queue()

    def mlx_worker():
        try:
            import mlx_whisper

            # Pre-warm: download + load model on this thread
            silent_audio = np.zeros(SAMPLE_RATE, dtype=np.float32)
            mlx_whisper.transcribe(silent_audio, path_or_hf_repo=model_name, language=language)
            result_q.put(True)

            # Process transcription requests until stopped
            while not stop_event.is_set():
                try:
                    audio_float = work_q.get(timeout=1.0)
                except queue.Empty:
                    continue
                try:
                    result = mlx_whisper.transcribe(
                        audio_float,
                        path_or_hf_repo=model_name,
                        language=language,
                    )
                    result_q.put(result)
                except Exception as e:
                    result_q.put(e)
        except Exception as e:
            result_q.put(e)

    logger.info(f"Loading Whisper model: {model_name}")

    worker = threading.Thread(target=mlx_worker, daemon=True)
    worker.start()

    # Wait for pre-warm to complete
    warmup_result = result_q.get()
    if isinstance(warmup_result, Exception):
        raise warmup_result

    logger.info(f"Whisper model loaded: {model_name}")

    def transcribe(audio_float):
        work_q.put(audio_float)
        result = result_q.get()
        if isinstance(result, Exception):
            raise result
        return result

    return transcribe


# ============================================================================
# TranscriptionManager — unified interface
# ============================================================================

class TranscriptionManager:
    """
    Unified transcription interface supporting local MLX Whisper and Groq API.

    Modes:
        "offline" - Local MLX Whisper only (100% offline)
        "online"  - Groq API only (requires internet + API key)
        "auto"    - Try Groq first, fall back to local MLX
    """

    def __init__(self, mode, groq_api_key, groq_model, whisper_model, language, logger, status_callback=None):
        self.mode = mode
        self.logger = logger
        self._status_callback = status_callback  # callable(event, value) for UI updates

        # VAD (always local, always loaded — only ~50MB)
        self.vad_model, self.vad_utils = _initialize_vad(logger)

        # Groq config — resolve API key: config.py → env var → dotfile
        self._groq_client = None
        self._groq_api_key = resolve_api_key(groq_api_key, "GROQ_API_KEY", "~/.config/notwisprflow/api_key")
        self._groq_model = groq_model

        # Local MLX model state
        self._local_transcribe_fn = None
        self._model_lock = threading.Lock()
        self._worker_stop = None

        # Connectivity monitor state (auto mode only)
        self._online = True  # Assume online until first check; Groq attempt will confirm
        self._online_streak = 0
        self._shutdown = None
        self._connectivity_thread = None

        # Model config
        self._language = language
        self._whisper_model_name = whisper_model

    def initialize(self):
        """Called at startup. Load backends based on mode."""
        if self.mode == "offline":
            self._load_local_model()
        elif self.mode == "online":
            self._validate_groq_key()
        elif self.mode == "auto":
            if self._groq_api_key:
                self.logger.debug("Auto mode: Groq API key found, will use Groq with local fallback")
                # Don't load model yet - will load on-demand if needed
                self._start_connectivity_monitor()
                # Pre-download model files in background so they're cached when needed
                threading.Thread(target=self._predownload_model, daemon=True).start()
            else:
                self.logger.debug("Auto mode: No Groq API key configured, using local transcription only")
                self._load_local_model()

    def transcribe(self, audio_float):
        """
        Transcribe audio. Returns dict with "text" and "backend" keys.

        backend is "groq" or "local".
        In auto mode: tries Groq first, falls back to local MLX.
        """
        if self.mode == "offline":
            result = self._transcribe_local(audio_float)
            result["backend"] = "local"
            return result
        elif self.mode == "online":
            result = self._transcribe_groq(audio_float)
            result["backend"] = "groq"
            return result
        else:  # auto
            if not self._groq_api_key or not self._online:
                result = self._transcribe_local(audio_float)
                result["backend"] = "local"
                return result
            try:
                result = self._transcribe_groq(audio_float)
                result["backend"] = "groq"
                return result
            except Exception as e:
                self.logger.warning(f"Groq API failed ({e}), falling back to local Whisper")
                self._online = False  # Don't try Groq again until monitor confirms we're back
                result = self._transcribe_local(audio_float)
                result["backend"] = "local"
                return result

    def contains_speech(self, audio_float, sample_rate=SAMPLE_RATE):
        """Check if audio contains speech using Silero VAD with RMS energy fallback.

        Passes if VAD detects speech OR RMS energy exceeds a floor threshold.
        The energy fallback catches melodic/sung speech that VAD misclassifies,
        while still blocking truly silent recordings (which cause Whisper hallucinations).
        """
        # RMS energy check — truly silent audio sits well below 0.01
        rms = float(np.sqrt(np.mean(audio_float ** 2)))
        if rms > 0.01:
            self.logger.info(f"RMS check passed (rms={rms:.4f}), skipping VAD")
            return True
        self.logger.info(f"RMS check failed (rms={rms:.4f}), falling through to VAD")

        if self.vad_model is None or self.vad_utils is None:
            return True  # If VAD not available, proceed with transcription

        try:
            get_speech_timestamps = self.vad_utils[0]
            speech_timestamps = get_speech_timestamps(
                audio_float,
                self.vad_model,
                sampling_rate=sample_rate,
                threshold=0.2,
                min_speech_duration_ms=250,
                min_silence_duration_ms=100,
                return_seconds=False
            )

            has_speech = len(speech_timestamps) > 0
            if not has_speech:
                self.logger.info(f"VAD: No speech detected in audio (rms={rms:.4f})")
            else:
                self.logger.debug(f"VAD: Detected {len(speech_timestamps)} speech segment(s)")
            return has_speech

        except Exception as e:
            self.logger.warning(f"VAD check failed: {e}, proceeding with transcription")
            return True

    def shutdown(self):
        """Clean up threads and resources."""
        if self._shutdown:
            self._shutdown.set()
        if self._worker_stop:
            self._worker_stop.set()

    # --- Private methods ---

    @staticmethod
    def _show_error_dialog(message):
        """Show a macOS error dialog via osascript. 'Open Logs' button opens the log file."""
        log_path = os.path.expanduser("~/Library/Logs/NotWisprFlow/notwisprflow.log")
        escaped = message.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '" & return & "')
        script = (
            f'set result to display dialog "{escaped}" '
            f'with title "Not Wispr Flow" '
            f'buttons {{"OK", "Open Logs"}} default button "OK" with icon note\n'
            f'if button returned of result is "Open Logs" then\n'
            f'    do shell script "open \\"{log_path}\\""\n'
            f'end if'
        )
        try:
            subprocess.run(["osascript", "-e", script], timeout=60)
        except Exception:
            pass

    def _validate_groq_key(self):
        """Validate that a Groq API key is available."""
        if not self._groq_api_key:
            self.logger.error("FATAL: GROQ_API_KEY is required for 'online' mode")
            self.logger.error("Set it in config.py, GROQ_API_KEY env var, or ~/.config/notwisprflow/api_key")
            sys.exit(0)

    def _transcribe_groq(self, audio_float):
        """Send audio to Groq API for transcription."""
        import io
        import wave
        from groq import Groq

        # Convert float32 numpy → WAV bytes
        audio_int16 = (audio_float * 32768).clip(-32768, 32767).astype(np.int16)
        buf = io.BytesIO()
        with wave.open(buf, 'wb') as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(SAMPLE_RATE)
            wf.writeframes(audio_int16.tobytes())
        buf.seek(0)

        if self._groq_client is None:
            self._groq_client = Groq(api_key=self._groq_api_key, timeout=10.0)

        result = self._groq_client.audio.transcriptions.create(
            file=("audio.wav", buf),
            model=self._groq_model,
            language=self._language or "",
        )
        return {"text": result.text}

    def _predownload_model(self):
        """Download model files to HuggingFace cache without loading into memory."""
        try:
            from huggingface_hub import snapshot_download
            snapshot_download(self._whisper_model_name)
            self.logger.info(f"Speech model pre-downloaded: {self._whisper_model_name}")
        except Exception as e:
            self.logger.debug(f"Model pre-download skipped: {e}")

    def _load_local_model(self):
        """Load MLX Whisper model (blocks until ready)."""
        with self._model_lock:
            if self._local_transcribe_fn is not None:
                return  # Already loaded

            if self._status_callback:
                self._status_callback("loading_model", True)

            self._worker_stop = threading.Event()
            try:
                self._local_transcribe_fn = _initialize_whisper(
                    self._whisper_model_name, self._language,
                    self._worker_stop, self.logger
                )
            except Exception as e:
                self.logger.error(f"Failed to load Whisper model: {e}", exc_info=True)
                self._show_error_dialog(
                    "Could not load the speech model.\n\n"
                    "Check the logs for details."
                )
                sys.exit(0)
            finally:
                if self._status_callback:
                    self._status_callback("loading_model", False)

    def _unload_local_model(self):
        """Unload MLX Whisper to free ~2.3GB RAM."""
        with self._model_lock:
            if self._local_transcribe_fn is None:
                return
            self._worker_stop.set()
            self._local_transcribe_fn = None
            self.logger.info("Local Whisper model unloaded (RAM freed)")

    def _transcribe_local(self, audio_float):
        """Transcribe with local MLX Whisper, loading model if needed."""
        if self._local_transcribe_fn is None:
            self.logger.info("Loading local Whisper model on demand...")
            self._load_local_model()
        return self._local_transcribe_fn(audio_float)

    def _check_connectivity(self):
        """Fast connectivity check to Groq API (~100ms)."""
        import socket
        try:
            socket.create_connection(("api.groq.com", 443), timeout=3)
            return True
        except OSError:
            return False

    def _start_connectivity_monitor(self):
        """
        Background thread: check connectivity every 30s, manage model lifecycle.

        Hysteresis-based:
        - Unload local model after 2 consecutive online checks (60s stable)
        - Pre-load local model immediately on first offline check
        """
        if not self._groq_api_key:
            return  # No point monitoring if no API key

        ONLINE_THRESHOLD = 2   # Consecutive online checks before unloading
        CHECK_INTERVAL = 30    # Seconds between checks

        def monitor():
            while not self._shutdown.is_set():
                online = self._check_connectivity()
                self._online = online

                if online:
                    self._online_streak += 1
                    if self._online_streak >= ONLINE_THRESHOLD and self._local_transcribe_fn is not None:
                        self.logger.info("Stable internet detected, unloading local model to save RAM")
                        self._unload_local_model()
                else:
                    self._online_streak = 0
                    if self._local_transcribe_fn is None:
                        self.logger.info("Internet lost, pre-loading local Whisper model")
                        try:
                            self._load_local_model()
                        except Exception as e:
                            self.logger.error(f"Failed to pre-load local model: {e}")

                self._shutdown.wait(CHECK_INTERVAL)

        self._shutdown = threading.Event()
        self._connectivity_thread = threading.Thread(target=monitor, daemon=True)
        self._connectivity_thread.start()
        self.logger.debug("Connectivity monitor started (30s interval, hysteresis=2)")
