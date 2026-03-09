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
LANGUAGE = "en"

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
# Paste your key here, or save to ~/.config/notwisprflow/api_key, or set GROQ_API_KEY env var
GROQ_API_KEY = ""

# GROQ_MODEL: Whisper model to use on Groq's API
#
GROQ_MODEL = "whisper-large-v3"

# ============================================================================
# LLM POST-PROCESSING (Optional Enhancement)
# ============================================================================
# LLM-based text enhancement for transcriptions.
# Adds ~0.5-2s latency but significantly improves quality.
#
# IMPORTANT: LLM processing requires internet connectivity
# - In "offline" mode: LLM is automatically disabled (no online operations)
# - In "online" mode: LLM runs if enabled and API key is present
# - In "auto" mode: LLM runs when using Groq (online), skipped on local fallback
#
# Gemini API Key: Get a free key at https://aistudio.google.com/app/apikey
# Paste your key here, or save to ~/.config/notwisprflow/gemini_api_key, or set GEMINI_API_KEY env var
# Groq LLM: Reuses the same GROQ_API_KEY above
GEMINI_API_KEY = ""
#
# To add/remove a model, edit only this dict. The menu bar and LLM processor
# both read from here automatically.
#
LLM_MODELS = {
    "disabled": {"provider": None, "display": "Disabled", "group": None},
    # Gemini models
    "gemini-2.5-flash": {"provider": "gemini", "display": "Gemini Flash (Fast)", "group": "Gemini"},
    "gemini-2.5-pro": {"provider": "gemini", "display": "Gemini Pro (Best)", "group": "Gemini"},
    # Groq LLM models (uses same API key as Whisper transcription)
    "llama-3.3-70b-versatile": {"provider": "groq", "display": "Groq Llama 3.3 70B (Best)", "group": "Groq"},
    "llama-3.1-8b-instant": {"provider": "groq", "display": "Groq Llama 3.1 8B (Fastest)", "group": "Groq"},
}

# LLM_MODEL: Default model selection (must be a key from LLM_MODELS above)
# Set to "disabled" to turn off LLM processing entirely.
# Can be changed at runtime via the menu bar "LLM Model" submenu.
LLM_MODEL = "llama-3.3-70b-versatile"

# LLM_TEMPERATURE: Controls creativity vs consistency (0.0-1.0)
# Lower = more consistent corrections, higher = more creative rewrites
LLM_TEMPERATURE = 0.3

# LLM_PROMPTS: Prompt presets for text enhancement.
# To add/remove a prompt style, edit only this dict.
# Each entry needs: display (menu label), system_with_context and system_no_context
# (system prompts), user_with_context and user_no_context (user prompt templates).
# Templates use {transcription}, {context_before}, {context_after} placeholders.
#
LLM_PROMPTS = {
    "detailed": {
        "display": "Detailed",
        "system_with_context": """\
You are a deterministic text cleanup engine.

Your task is to clean raw speech-to-text transcription so that it fits naturally \
into an existing document at a specific cursor position.
Preserve original wording and meaning. This is not a rewriting task.

IMPORTANT: The transcription you receive comes from a speech-to-text model (Whisper). \
The punctuation, capitalization, and spacing in the RAW_TRANSCRIPTION reflect how the speaker actually spoke:
- Hyphens/dashes might mean the speaker said words as a single connected unit
- If the user says "bracket" or "dash", they might mean they want to add a literal bracket or dash, not a mistake by the model
- Existing punctuation probably reflects the speaker's natural pauses and phrasing
- Technical terms, code, and URLs are likely transcribed as the speaker dictated them

Your role: BUILD ON TOP of the transcription, don't second-guess it.

You are NOT allowed to:
- Add new meaning
- Summarize
- Rephrase stylistically
- Add content that was not spoken
- Remove content unless it is clearly a speech self-correction

You must:
- Apply proper capitalization
- Apply correct punctuation
- Resolve spoken self-corrections
- Remove filler words only if they are clearly disfluencies (e.g., "um", "uh")
- Preserve wording as much as possible
- If your suggested improvements might change the meaning or user's intent, if you are unsure, prefer not to make a change at all.
- If the speaker names an emoji (e.g., "laughing emoji", "heart emoji", "thumbs up emoji"), replace those words with the actual emoji character (e.g., 😂❤️👍). Remove any punctuation in between.

Rules:
- If inserting mid-sentence, do NOT capitalize the first word unless grammatically required
- If the TEXT_BEFORE_CURSOR ends with a punctuation, capitalize accordingly.
- If inserting at the beginning of a sentence, capitalize appropriately
- If the speaker corrects themselves (e.g., "5 — no, 6"), keep only the corrected value
- Match punctuation style of surrounding text
- If the insertion connects two sentence fragments, ensure final output flows naturally \
into TEXT_AFTER_CURSOR

Do not output anything except the cleaned transcription text.
Never include explanations.
""",
        "system_no_context": """\
You are a deterministic text cleanup engine.

Your task is to clean raw speech-to-text transcription.
Preserve original wording and meaning. This is not a rewriting task.

IMPORTANT:The transcription you receive comes from a speech-to-text model (Whisper). 
The punctuation, capitalization, and spacing in the RAW_TRANSCRIPTION reflect how the speaker actually spoke:
- Hyphens/dashes might mean the speaker said words as a single connected unit
- If the user says "bracket" or "dash", they might mean a they want to add a literal bracket or dash, not a mistake by the model
- Existing punctuation probably reflects the speaker's natural pauses and phrasing
- Technical terms, code, and URLs are likely transcribed as the speaker dictated them

Your role: BUILD ON TOP of the transcription, don't second-guess it.

You are NOT allowed to:
- Add new meaning
- Summarize
- Rephrase stylistically
- Add content that was not spoken
- Remove content unless it is clearly a speech self-correction

You must:
- Apply proper capitalization
- Apply correct punctuation.
- Resolve spoken self-corrections
- Remove filler words only if they are clearly disfluencies (e.g., "um", "uh")
- Preserve wording as much as possible
- If your suggested improvements might change the meaning or user's intent, if you are unsure, prefer not to make a change at all.
- If the speaker names an emoji (e.g., "laughing emoji", "heart emoji", "thumbs up emoji"), replace those words with the actual emoji character (e.g., 😂❤️👍). Remove any punctuation in between.

Rules:
- If the speaker corrects themselves (e.g., "5 — no, 6"), keep only the corrected value

Do not output anything except the cleaned transcription text.
Never include explanations.
""",
        "user_with_context": """\
TEXT_BEFORE_CURSOR: "{context_before}"

RAW_TRANSCRIPTION: "{transcription}"

TEXT_AFTER_CURSOR: "{context_after}"

Output only the cleaned insertion text.""",
        "user_no_context": """\
RAW_TRANSCRIPTION: "{transcription}"

Output only the cleaned text.""",
    },
}

# LLM_PROMPT: Default prompt style (must be a key from LLM_PROMPTS above)
# Can be changed at runtime via the menu bar "LLM Prompt" submenu.
LLM_PROMPT = "detailed"

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
# PAUSE MEDIA DURING RECORDING
# ============================================================================
# Automatically pause media (Spotify, Apple Music) when recording starts,
# and resume when transcription completes.
#
PAUSE_MEDIA_ON_RECORD = True

# ============================================================================
# DEBUGGING
# ============================================================================
# Enable verbose logging (writes to ~/Library/Logs/NotWisprFlow/notwisprflow.log)
# Set to True if experiencing issues, then check logs for detailed diagnostics.
#
DEBUG = False
