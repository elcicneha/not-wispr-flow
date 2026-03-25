"""Keyboard event handler state machine for Not Wispr Flow.

Implements the recording state machine:
  None + hotkey press              -> Hold mode, start recording
  None + hotkey press (space held) -> Toggle mode, start recording
  None + space press (hotkey held) -> Toggle mode, start recording
  Hold + space press               -> Convert to Toggle mode (recording continues)
  Hold + hotkey release            -> Stop recording, transcribe
  Toggle + hotkey press            -> Stop recording, transcribe
"""

import logging
import threading
import time

from pynput.keyboard import Key

from .config import HOTKEY_KEYS, TOGGLE_KEY
from . import audio
from .text_output import insert_text

logger = logging.getLogger("notwisprflow")

# Debounce time for rapid key presses (milliseconds)
DEBOUNCE_MS = 100


def is_hotkey(key):
    """Check if a key event matches any of the configured hotkey variants."""
    return key in HOTKEY_KEYS


def create_handlers(state, update_icon_fn, on_audio_ready_fn):
    """Create keyboard event handlers bound to state and callbacks.

    Args:
        state: AppState instance
        update_icon_fn: callable(state_name) for menu bar icon updates
        on_audio_ready_fn: callable(buffer, overflow, mode, start_time, stop_time)
                          called when recording has audio data ready for transcription

    Returns:
        (on_press, on_release) callables for pynput.Listener
    """

    def on_press(key):
        """Handle keyboard key press events.

        State machine transitions on press:
          mode=None   + hotkey              -> hold mode, start recording
          mode=None   + hotkey (space held) -> toggle mode, start recording
          mode=None   + space (hotkey held) -> toggle mode, start recording
          mode=hold   + space               -> convert to toggle mode (keep recording)
          mode=hold   + hotkey              -> missed release recovery, stop recording
          mode=toggle + hotkey              -> stop recording, mode=None

        Stuck state recovery (before normal transitions):
          mode set + not recording + has data -> salvage partial recording, reset
          mode set + not recording + no data  -> reset to idle, then start new recording
          transcription hung (>60s)           -> clear flag so user can record again
        """
        current_time = time.time() * 1000

        # Ignore recording hotkeys while model is loading
        if state.is_loading_model:
            return

        try:
            with state.lock:
                if is_hotkey(key):
                    # Debounce
                    if current_time - state.last_press_time < DEBOUNCE_MS:
                        return

                    state.last_press_time = current_time
                    state.hotkey_pressed = True

                    # Cmd held = command combo (e.g. Ctrl+Cmd+C for retype), skip recording
                    if state.cmd_pressed:
                        return

                    # --- Stuck state recovery ---
                    if state.mode is not None and not state.is_recording:
                        has_data = bool(state.audio_buffer or state.overflow_files)
                        if has_data:
                            logger.warning(f"Stuck recovery: mode={state.mode}, not recording, buffer has data. Salvaging partial recording...")
                            try:
                                audio.stop_recording(state, update_icon_fn, on_audio_ready_fn)
                            finally:
                                state.mode = None
                            return
                        else:
                            logger.warning(f"Stuck recovery: mode={state.mode}, not recording, no data. Resetting to idle.")
                            state.is_recording = False
                            state.mode = None
                            update_icon_fn('idle')

                    # Detect hung transcription (>60s)
                    if state.mode is None and not state.is_recording and state.is_transcribing:
                        if state.transcription_start_time and (time.time() - state.transcription_start_time > 60):
                            logger.warning(f"Stuck recovery: transcription hung for >{time.time() - state.transcription_start_time:.0f}s. Clearing flag.")
                            state.is_transcribing = False
                            state.transcription_start_time = None
                            update_icon_fn('idle')

                    # --- Normal state machine ---
                    if state.mode is None:
                        state.mode = "toggle" if state.space_pressed else "hold"
                        try:
                            audio.start_recording(state, update_icon_fn)
                        except Exception as e:
                            logger.error(f"Failed to start recording: {e}")
                            state.mode = None
                            return
                        logger.info(f"{state.mode.capitalize()} mode: Recording started")

                    elif state.mode == "toggle" and state.is_recording:
                        try:
                            audio.stop_recording(state, update_icon_fn, on_audio_ready_fn)
                        finally:
                            state.mode = None
                        logger.info("Toggle mode: Recording stopped")

                    elif state.mode == "hold" and state.is_recording:
                        logger.warning("Hold mode: Hotkey pressed again (missed release?), stopping recording")
                        try:
                            audio.stop_recording(state, update_icon_fn, on_audio_ready_fn)
                        finally:
                            state.mode = None

                elif key == TOGGLE_KEY:
                    state.space_pressed = True

                    if state.hotkey_pressed:
                        if state.mode is None:
                            state.mode = "toggle"
                            try:
                                audio.start_recording(state, update_icon_fn)
                            except Exception as e:
                                logger.error(f"Failed to start recording: {e}")
                                state.mode = None
                                return
                            logger.info("Toggle mode: Recording started")
                        elif state.mode == "hold":
                            state.mode = "toggle"
                            logger.debug("Converted hold mode to toggle mode")

                elif key in (Key.cmd, Key.cmd_r, Key.cmd_l):
                    state.cmd_pressed = True

                elif state.hotkey_pressed and state.cmd_pressed and getattr(key, 'vk', None) == 8:
                    # Ctrl+Cmd+C -> Retype last transcription
                    if state.is_recording:
                        audio.cancel_recording(state)
                        update_icon_fn('idle')
                        logger.debug("Cancelled recording for Retype shortcut")
                    text = state.last_transcription
                    if text:
                        threading.Thread(target=insert_text, args=(text, state), daemon=True).start()
                        logger.debug("Retype: inserting last transcription via global shortcut")

        except Exception as e:
            logger.error(f"Error in on_press handler: {e}")

    def on_release(key):
        """Handle keyboard key release events.

        State machine transitions on release:
          mode=hold + hotkey released -> stop recording, mode=None
          (toggle mode ignores hotkey release)

        Stuck state recovery:
          mode=hold + not recording -> reset mode to None (stream crashed)
        """
        try:
            with state.lock:
                if is_hotkey(key):
                    state.hotkey_pressed = False

                    if state.mode == "hold" and state.is_recording:
                        try:
                            audio.stop_recording(state, update_icon_fn, on_audio_ready_fn)
                        finally:
                            state.mode = None
                        logger.info("Hold mode: Recording stopped")

                    elif state.mode == "hold" and not state.is_recording:
                        has_data = bool(state.audio_buffer or state.overflow_files)
                        if has_data:
                            logger.warning("Stuck recovery (release): mode=hold, not recording, salvaging data.")
                            try:
                                audio.stop_recording(state, update_icon_fn, on_audio_ready_fn)
                            finally:
                                state.mode = None
                        else:
                            logger.warning("Stuck recovery (release): mode=hold, not recording, no data. Resetting.")
                            state.is_recording = False
                            state.mode = None
                            update_icon_fn('idle')

                elif key == TOGGLE_KEY:
                    state.space_pressed = False

                elif key in (Key.cmd, Key.cmd_r, Key.cmd_l):
                    state.cmd_pressed = False
        except Exception as e:
            logger.error(f"Error in on_release handler: {e}")

    return on_press, on_release
