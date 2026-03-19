#!/usr/bin/env python3
"""
Not Wispr Flow - User Configuration

Edit these settings to customize your dictation experience.
After changing settings, rebuild and reinstall:
    ./install.sh
"""

from pynput.keyboard import Key

# ============================================================================
# API KEYS
# ============================================================================
# Keys can also be stored as files or env vars instead of hardcoding here:
#   ~/.config/notwisprflow/api_key            (Groq)
#   ~/.config/notwisprflow/gemini_api_key     (Gemini)
#   ~/.config/notwisprflow/openai_api_key     (OpenAI)
#   ~/.config/notwisprflow/anthropic_api_key  (Anthropic)
#   GROQ_API_KEY / GEMINI_API_KEY / OPENAI_API_KEY / ANTHROPIC_API_KEY env vars

# Groq: https://console.groq.com (free tier: 20 req/min, 2000/day)
GROQ_API_KEY = ""

# Gemini: https://aistudio.google.com/app/apikey
GEMINI_API_KEY = ""

# OpenAI: https://platform.openai.com/api-keys
OPENAI_API_KEY = ""

# Anthropic: https://console.anthropic.com/settings/keys
ANTHROPIC_API_KEY = ""



# ============================================================================
# TRANSCRIPTION
# ============================================================================
# "auto"    - Groq API first, local MLX Whisper fallback (default)
# "online"  - Groq API only (requires GROQ_API_KEY)
# "offline" - Local MLX Whisper only (no internet, ~2.3GB RAM)
TRANSCRIPTION_MODE = "auto"

# Language for Whisper transcription
# "en" = English only (recommended), None = auto-detect all languages
# For multilingual (e.g. English + Spanish), use None
LANGUAGE = "en"

# Local Whisper model (only used in offline/auto modes)
# "mlx-community/whisper-large-v3-turbo" - Best quality, ~1.6GB download, ~2.3GB RAM
# "mlx-community/whisper-small"          - Faster, ~500MB, ~2GB RAM
# "mlx-community/whisper-base"           - Fastest, ~150MB, ~1GB RAM
WHISPER_MODEL = "mlx-community/whisper-large-v3-turbo"

# Groq API Whisper model (only used in online/auto modes)
GROQ_MODEL = "whisper-large-v3"

# ============================================================================
# HOTKEYS
# ============================================================================
# Hold mode:   Hold hotkey to record, release to stop
# Toggle mode: Hotkey + toggle key to start, hotkey alone to stop
#
# This is a set — include variants for compatibility across keyboards/macOS versions.
# Examples: {Key.ctrl_r}, {Key.cmd_r, Key.cmd}, {Key.alt_r, Key.alt}, {Key.f13}
HOTKEY_KEYS = {Key.ctrl, Key.ctrl_r}
TOGGLE_KEY = Key.space

# ============================================================================
# BEHAVIOR
# ============================================================================
# Text insertion: False = clipboard paste (default, fast), True = type each char
# Toggleable at runtime via menu bar "Paste Mode"
USE_TYPE_MODE = False

# Pause media (Spotify, YouTube, etc.) while recording, resume after transcription
PAUSE_MEDIA_ON_RECORD = True

# Start app automatically when you log in (creates a macOS LaunchAgent)
# Toggleable at runtime via menu bar "Start at Login"
START_AT_LOGIN = True

# Verbose logging to ~/Library/Logs/NotWisprFlow/notwisprflow.log
DEBUG = False


# ============================================================================
# LLM POST-PROCESSING
# ============================================================================
# Cleans up transcription text (capitalization, punctuation, filler words).
# Adds ~0.5-2s latency. Only runs with online transcription, never offline.
# Set LLM_MODEL to "disabled" to turn off. Changeable at runtime via menu bar.
#
# Available models — to add a custom model, add an entry here:
LLM_MODELS = {
    "disabled": {"provider": None, "display": "Disabled", "group": None},
    # Gemini
    "gemini-2.5-flash": {"provider": "gemini", "display": "Gemini Flash (Fast)", "group": "Gemini"},
    "gemini-2.5-pro": {"provider": "gemini", "display": "Gemini Pro (Best)", "group": "Gemini"},
    # Groq (uses same API key as Whisper transcription)
    "llama-3.3-70b-versatile": {"provider": "groq", "display": "Groq Llama 3.3 70B (Best)", "group": "Groq"},
    "llama-3.1-8b-instant": {"provider": "groq", "display": "Groq Llama 3.1 8B (Fastest)", "group": "Groq"},
    # OpenAI
    "gpt-4o-mini": {"provider": "openai", "display": "GPT-4o Mini (Fast)", "group": "OpenAI"},
    "gpt-4o": {"provider": "openai", "display": "GPT-4o (Best)", "group": "OpenAI"},
    # Anthropic
    "claude-haiku-4-5-20251001": {"provider": "anthropic", "display": "Claude Haiku 4.5 (Fast)", "group": "Anthropic"},
    "claude-sonnet-4-5-20250929": {"provider": "anthropic", "display": "Claude Sonnet 4.5 (Best)", "group": "Anthropic"},
}

# Default model — must be a key from LLM_MODELS above (or "disabled")
LLM_MODEL = "llama-3.3-70b-versatile"
LLM_TEMPERATURE = 0.3  # 0.0 = consistent, 1.0 = creative

# Prompt presets — to add/remove a prompt style, edit this dict.
# Templates use {transcription}, {context_before}, {context_after} placeholders.
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
- If the words "Whisper Flow" or "Whisperflow" (doesn't matter, upper case or lower case) appear in the transcription, convert the words to "Wispr Flow". Similarly "not Whisper Flow" -> "Not Wispr Flow". This is the name of my product, so treat it as a proper noun.

Formatting:
- Sequential lists: If the speaker uses "first...second...third" OR "one...two...three" AND lists 2+ distinct items, format that part of speech as a list:
  1. First item
  2. Second item
  3. Third item and so on...

- Long transcriptions: If transcription exceeds ~100 words AND contains natural topic shifts, insert paragraph breaks (double newline) between topics. Do not break mid-thought.
- Otherwise: Keep as continuous prose with proper punctuation.

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
- If the words "Whisper Flow" or "Whisperflow" (doesn't matter, upper case or lower case) appear in the transcription, convert the words to "Wispr Flow". Similarly "not Whisper Flow" -> "Not Wispr Flow". This is the name of my product, so treat it as a proper noun.

Formatting:
- Sequential lists: If the speaker uses "first...second...third" OR "one...two...three" AND lists 2+ distinct items, format that part of speech as a list:
  1. First item
  2. Second item
  3. Third item and so on...

- Long transcriptions: If transcription exceeds ~100 words AND contains natural topic shifts, insert paragraph breaks (double newline) between topics. Do not break mid-thought.
- Otherwise: Keep as continuous prose with proper punctuation.


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

LLM_PROMPT = "detailed" 
