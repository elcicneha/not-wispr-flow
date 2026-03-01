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
# TRANSCRIPTION BACKEND
# ============================================================================
# TRANSCRIPTION_MODE: Controls how audio is transcribed
#   "auto"     - Try Groq API first, fall back to local MLX Whisper (default)
#   "offline"  - Always use local MLX Whisper (100% offline, ~2.3GB RAM)
#   "online"   - Always use Groq API (requires internet + API key, low RAM)
#
# Privacy: "online" and "auto" modes send audio to Groq's servers for transcription.
# In "auto" mode without an API key, only local transcription is used.
#
TRANSCRIPTION_MODE = "auto"

# GROQ_API_KEY: Required for "online" mode, optional for "auto" mode
# Get a free key at https://console.groq.com
#
# API Key: Set via GROQ_API_KEY environment variable or save to ~/.config/notwisprflow/api_key
# NOT stored in this config file for security reasons

# GROQ_MODEL: Whisper model to use on Groq's API
#
GROQ_MODEL = "whisper-large-v3-turbo"

# ============================================================================
# LLM POST-PROCESSING (Optional Enhancement)
# ============================================================================
# Enable LLM-based text enhancement for transcriptions
#   True  - Send transcriptions to Gemini for grammar/punctuation correction
#   False - Use raw Whisper output (faster, no API calls)
#
# IMPORTANT: LLM processing requires internet connectivity
# - In "offline" mode: LLM is automatically disabled (no online operations)
# - In "online" mode: LLM runs if enabled and API key is present
# - In "auto" mode: LLM runs when using Groq (online), skipped when using local Whisper (offline fallback)
#
# Note: LLM processing adds ~0.5-2s latency but significantly improves quality
# Privacy: When enabled, transcribed text is sent to Google's Gemini API
#
# API Key: Set via GEMINI_API_KEY environment variable or save to ~/.config/notwisprflow/gemini_api_key
# Get a free key at https://aistudio.google.com/app/apikey
LLM_ENABLED = True

# GEMINI_MODEL: Gemini model to use for text enhancement
#   "gemini-2.5-flash"      - Latest, fastest (recommended for real-time use ~500-800ms)
#   "gemini-2.0-flash"      - Previous generation, still fast (~600-900ms)
#   "gemini-2.5-pro"        - Highest quality (slower, costs more) (~1500-2500ms)
GEMINI_MODEL = "gemini-2.5-flash"

# ============================================================================
# TEXT INSERTION MODE
# ============================================================================
# Controls how transcribed text is inserted at the cursor position
#   False - Use clipboard paste (default, instant, unicode-safe)
#   True  - Use character-by-character typing (slower, avoids clipboard)
#
# Paste mode (False): Faster and more reliable, handles all unicode characters,
#                     but briefly modifies clipboard (restored immediately)
# Type mode (True):   Slower, types each character individually, doesn't touch
#                     clipboard, may have issues with complex unicode
#
# You can toggle between modes at runtime via the menu bar "Paste Mode" item
USE_TYPE_MODE = False

# ============================================================================
# DEBUGGING
# ============================================================================
# Enable verbose logging (writes to ~/Library/Logs/NotWisprFlow/notwisprflow.log)
# Set to True if experiencing issues, then check logs for detailed diagnostics.
#
DEBUG = True
