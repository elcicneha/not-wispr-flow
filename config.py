#!/usr/bin/env python3
"""
Not Wispr Flow - User Configuration

Edit these settings to customize your dictation experience.
After changing settings, rebuild and reinstall:
    ./scripts/install_service.sh
"""

from pynput.keyboard import Key

# ============================================================================
# WHISPER MODEL SELECTION
# ============================================================================
# Choose your Whisper model (affects speed vs accuracy tradeoff):
#   "mlx-community/whisper-large-v3-turbo"  - Best quality, ~1.6GB, ~2.3GB RAM
#   "mlx-community/whisper-small"           - Faster, ~500MB, ~2GB RAM (may hallucinate)
#   "mlx-community/whisper-base"            - Fastest, ~150MB, ~1GB RAM (less accurate)
#
WHISPER_MODEL = "mlx-community/whisper-large-v3-turbo"

# LANGUAGE: Control which language(s) Whisper should transcribe
#
# Options:
#   "en"     - English only (recommended - prevents hallucinations in other languages)
#   None     - Auto-detect ANY language (for multilingual use: English + Spanish, etc.)
#   "es"     - Spanish only
#   "hi"     - Hindi only (outputs Devanagari script)
#   "pa"     - Punjabi only (outputs Gurmukhi script)
#   etc. (see Whisper docs for 99+ supported languages)
#
# IMPORTANT: Whisper does NOT support specifying multiple specific languages like ["en", "es"].
# Your options are:
#   1. Force ONE language: LANGUAGE = "en"  (ignores all other languages)
#   2. Auto-detect ALL languages: LANGUAGE = None  (detects English, Spanish, Hindi, etc.)
#
# For English + Spanish dictation, use: LANGUAGE = None
# This enables auto-detection and switches between languages automatically.
#
# NOTE: Forcing "en" on Hindi/Punjabi may produce romanized output (Hinglish) but results
# are inconsistent. For reliable Hinglish, use language="hi" + transliteration library.
#
LANGUAGE = None

# ============================================================================
# HOTKEY CONFIGURATION
# ============================================================================
# HOTKEY_KEYS: The key(s) that trigger recording
#
# IMPORTANT: This is a Python set containing pynput Key objects. macOS may report
# the same physical key with different codes (Key.ctrl vs Key.ctrl_r vs Key.ctrl_l).
# Including multiple variants ensures reliable detection across different keyboards
# and macOS versions.
#
# Common options:
#   {Key.ctrl, Key.ctrl_r}           - Right Control (default, broadest compatibility)
#   {Key.ctrl_r}                     - Right Control only (strict matching)
#   {Key.ctrl, Key.ctrl_l}           - Left Control
#   {Key.cmd_r, Key.cmd}             - Right Command (⌘)
#   {Key.alt_r, Key.alt}             - Right Option/Alt
#   {Key.f13}                        - F13 key
#
HOTKEY_KEYS = {Key.ctrl, Key.ctrl_r}

# TOGGLE_KEY: Press this WITH the hotkey to enable toggle mode
#
# Toggle mode: Press Hotkey+Space to START recording, Hotkey alone to STOP
# Hold mode: Hold Hotkey to record, release to stop (default behavior)
#
TOGGLE_KEY = Key.space

# ============================================================================
# DEBUGGING
# ============================================================================
# Enable verbose logging (writes to ~/Library/Logs/NotWisprFlow/notwisprflow.log)
# Set to True if experiencing issues, then check logs for detailed diagnostics.
#
DEBUG = True
