#!/usr/bin/env python3
"""
LLM Post-Processing for Not Wispr Flow.

Provides intelligent text enhancement using multiple providers:
- Google Gemini API
- Groq API (chat completions with Llama models)

All model definitions live in config.py (LLM_MODELS dict).
"""

import json
import os
import time
from typing import Optional, Tuple

from config import LLM_MODELS, LLM_PROMPTS, GEMINI_API_KEY, GROQ_API_KEY

# ============================================================================
# PREFERENCES PERSISTENCE
# ============================================================================
_PREFS_DIR = os.path.expanduser("~/.config/notwisprflow")
_PREFS_FILE = os.path.join(_PREFS_DIR, "preferences.json")


def load_preference(key: str, default=None):
    """Load a single preference from ~/.config/notwisprflow/preferences.json."""
    try:
        if os.path.exists(_PREFS_FILE):
            with open(_PREFS_FILE, "r") as f:
                prefs = json.load(f)
            return prefs.get(key, default)
    except Exception:
        pass
    return default


def save_preference(key: str, value):
    """Save a single preference to ~/.config/notwisprflow/preferences.json."""
    try:
        os.makedirs(_PREFS_DIR, exist_ok=True)
        prefs = {}
        if os.path.exists(_PREFS_FILE):
            with open(_PREFS_FILE, "r") as f:
                prefs = json.load(f)
        prefs[key] = value
        with open(_PREFS_FILE, "w") as f:
            json.dump(prefs, f, indent=2)
    except Exception:
        pass


# ============================================================================
# PROVIDER USAGE CONFIG
# ============================================================================
PROVIDER_USAGE_CONFIG = {
    "gemini": {
        "usage_attr": "usage_metadata",
        "input_field": "prompt_token_count",
        "output_field": "candidates_token_count",
        "daily_request_limit": 250,
    },
    "groq": {
        "usage_attr": "usage",
        "input_field": "prompt_tokens",
        "output_field": "completion_tokens",
        "daily_request_limit": 500,
    },
}


class LLMProcessor:
    """
    Handles LLM-based post-processing of transcriptions.

    Supports multiple providers (Gemini, Groq) with runtime model switching.
    Provider is inferred from the model name via LLM_MODELS in config.py.
    """

    def __init__(self, model: str, temperature: float, prompt: str, logger):
        """
        Initialize LLM processor.

        Args:
            model: Model name (key from LLM_MODELS in config.py)
            temperature: LLM temperature (0.0-1.0)
            prompt: Prompt preset name (key from LLM_PROMPTS in config.py)
            logger: Logger instance
        """
        self.logger = logger
        self._temperature = temperature
        self._prompt_name = prompt
        self._prompt_config = LLM_PROMPTS.get(prompt, {})

        # Resolve API keys for both providers at init (so switching is instant)
        self._gemini_api_key = self._resolve_gemini_api_key(logger)
        self._groq_api_key = self._resolve_groq_api_key(logger)

        # Lazy-initialized clients (one per provider)
        self._gemini_client = None
        self._groq_client = None

        # Usage tracking (per-provider)
        self._daily_requests = 0
        self._daily_input_tokens = 0
        self._daily_output_tokens = 0
        self._tracking_date = time.strftime("%Y-%m-%d")

        # Personal prompt (additional instructions appended to system prompt)
        self._personal_prompt = load_preference("personal_prompt", "")

        # Custom system prompt overrides (per-variant, replace preset when set)
        self._custom_system_with_context = load_preference("custom_system_with_context", "")
        self._custom_system_no_context = load_preference("custom_system_no_context", "")

        # Set initial model (also sets self._provider, self.enabled)
        self._model = None
        self._provider = None
        self.enabled = False
        self.switch_model(model, log=True)

    def switch_model(self, model: str, log: bool = True):
        """
        Switch to a different LLM model at runtime.

        Args:
            model: Model name (key from LLM_MODELS in config.py)
            log: Whether to log the switch
        """
        model_info = LLM_MODELS.get(model)
        if model_info is None:
            self.logger.warning(f"Unknown LLM model '{model}', disabling LLM")
            model = "disabled"
            model_info = LLM_MODELS["disabled"]

        self._model = model
        self._provider = model_info["provider"]

        if self._provider is None:
            self.enabled = False
            if log:
                self.logger.debug("LLM post-processing: Disabled")
        elif self._provider == "gemini" and not self._gemini_api_key:
            self.enabled = False
            if log:
                self.logger.warning(
                    "LLM model requires Gemini API key but none found. "
                    "Set GEMINI_API_KEY env var or save to ~/.config/notwisprflow/gemini_api_key"
                )
        elif self._provider == "groq" and not self._groq_api_key:
            self.enabled = False
            if log:
                self.logger.warning(
                    "LLM model requires Groq API key but none found. "
                    "Set GROQ_API_KEY env var or save to ~/.config/notwisprflow/api_key"
                )
        else:
            self.enabled = True
            if log:
                self.logger.debug(
                    f"LLM post-processing: Enabled "
                    f"(model: {self._model}, provider: {self._provider})"
                )

    def switch_prompt(self, prompt_name: str):
        """Switch to a different prompt preset at runtime."""
        prompt_config = LLM_PROMPTS.get(prompt_name)
        if prompt_config is None:
            self.logger.warning(f"Unknown LLM prompt '{prompt_name}', keeping current")
            return
        self._prompt_name = prompt_name
        self._prompt_config = prompt_config
        self.logger.info(f"LLM prompt switched to: {prompt_config['display']} ({prompt_name})")

    def set_personal_prompt(self, text: str):
        """Set personal prompt (additional instructions appended to system prompt)."""
        self._personal_prompt = text.strip()
        save_preference("personal_prompt", self._personal_prompt)
        if self._personal_prompt:
            self.logger.debug(f"Personal prompt set ({len(self._personal_prompt)} chars)")
        else:
            self.logger.debug("Personal prompt cleared")

    def set_custom_system_prompt(self, variant: str, text: str):
        """Set a custom system prompt override for a specific variant."""
        text = text.strip()
        if variant == "with_context":
            self._custom_system_with_context = text
            save_preference("custom_system_with_context", text)
        elif variant == "no_context":
            self._custom_system_no_context = text
            save_preference("custom_system_no_context", text)
        status = f"set ({len(text)} chars)" if text else "cleared"
        self.logger.debug(f"Custom system prompt ({variant}): {status}")

    def has_custom_system_prompt(self, variant: str) -> bool:
        if variant == "with_context":
            return bool(self._custom_system_with_context)
        return bool(self._custom_system_no_context)

    def reset_custom_system_prompt(self, variant: str):
        """Clear custom system prompt override, reverting to preset."""
        self.set_custom_system_prompt(variant, "")

    def get_active_system_prompt(self, has_context: bool) -> str:
        """Get the active system prompt WITHOUT personal prompt appended (for UI display)."""
        if has_context:
            return self._custom_system_with_context or self._prompt_config.get("system_with_context", "")
        return self._custom_system_no_context or self._prompt_config.get("system_no_context", "")

    def get_preset_system_prompt(self, has_context: bool) -> str:
        """Get the preset default system prompt (ignoring any custom override)."""
        if has_context:
            return self._prompt_config.get("system_with_context", "")
        return self._prompt_config.get("system_no_context", "")

    @property
    def model(self) -> str:
        return self._model

    @property
    def prompt_name(self) -> str:
        return self._prompt_name

    @staticmethod
    def _resolve_gemini_api_key(logger) -> str:
        """Resolve Gemini API key from config.py → env var → dotfile."""
        if GEMINI_API_KEY:
            logger.debug("Gemini API key: found in config.py")
            return GEMINI_API_KEY

        env_key = os.environ.get("GEMINI_API_KEY", "")
        if env_key:
            logger.debug("Gemini API key: found in environment variable")
            return env_key

        key_file = os.path.expanduser("~/.config/notwisprflow/gemini_api_key")
        if os.path.exists(key_file):
            try:
                with open(key_file, "r") as f:
                    key = f.read().strip()
                if key:
                    logger.debug(f"Gemini API key: found in {key_file}")
                    return key
            except Exception as e:
                logger.warning(f"Failed to read Gemini API key from {key_file}: {e}")

        return ""

    @staticmethod
    def _resolve_groq_api_key(logger) -> str:
        """Resolve Groq API key from config.py → env var → dotfile (same key as Whisper transcription)."""
        if GROQ_API_KEY:
            logger.debug("Groq LLM API key: found in config.py")
            return GROQ_API_KEY

        env_key = os.environ.get("GROQ_API_KEY", "")
        if env_key:
            logger.debug("Groq LLM API key: found in environment variable")
            return env_key

        key_file = os.path.expanduser("~/.config/notwisprflow/api_key")
        if os.path.exists(key_file):
            try:
                with open(key_file, "r") as f:
                    key = f.read().strip()
                if key:
                    logger.debug(f"Groq LLM API key: found in {key_file}")
                    return key
            except Exception as e:
                logger.warning(f"Failed to read Groq API key from {key_file}: {e}")

        return ""

    # ── Client initialization ──────────────────────────────────────────────

    def _get_gemini_client(self):
        """Lazy initialization of Gemini client."""
        if self._gemini_client is None and self._gemini_api_key:
            try:
                from google import genai
                self._gemini_client = genai.Client(api_key=self._gemini_api_key)
                self.logger.debug(f"Gemini LLM client initialized: {self._model}")
            except Exception as e:
                import traceback
                self.logger.error(f"Failed to initialize Gemini client: {e}")
                self.logger.error(f"Traceback: {traceback.format_exc()}")
                self.enabled = False
        return self._gemini_client

    def _get_groq_client(self):
        """Lazy initialization of Groq client."""
        if self._groq_client is None and self._groq_api_key:
            try:
                from groq import Groq
                self._groq_client = Groq(api_key=self._groq_api_key, timeout=10.0)
                self.logger.debug(f"Groq LLM client initialized: {self._model}")
            except Exception as e:
                import traceback
                self.logger.error(f"Failed to initialize Groq client: {e}")
                self.logger.error(f"Traceback: {traceback.format_exc()}")
                self.enabled = False
        return self._groq_client

    # ── Processing ─────────────────────────────────────────────────────────

    def process(self, text: str, context_before: Optional[str] = None,
                context_after: Optional[str] = None) -> Tuple[str, float]:
        """
        Process transcribed text through LLM for enhancement.

        Returns:
            Tuple of (processed_text, processing_time_seconds).
            Returns original text if processing fails or is disabled.
        """
        if not self.enabled or self._provider is None:
            return text, 0.0

        start_time = time.time()

        try:
            has_context = self._has_context(context_before, context_after)
            if has_context:
                self.logger.info(
                    f"LLM context: before={repr(context_before[-100:] if context_before else None)}, "
                    f"after={repr(context_after[:100] if context_after else None)}"
                )
            else:
                self.logger.info("LLM context: none (standalone text)")

            if self._provider == "gemini":
                processed_text, response = self._process_gemini(text, context_before, context_after)
            elif self._provider == "groq":
                processed_text, response = self._process_groq(text, context_before, context_after)
            else:
                return text, 0.0

            processing_time = time.time() - start_time

            # Track usage
            if response is not None:
                self._track_usage(self._extract_token_usage(response))

            # Validate output
            if not processed_text:
                self.logger.warning("LLM returned empty response, using original text")
                return text, processing_time

            if len(processed_text) < len(text) * 0.5:
                self.logger.warning(
                    f"LLM output appears truncated ({len(processed_text)} chars vs "
                    f"{len(text)} input chars), using original text"
                )
                return text, processing_time

            if len(processed_text) > len(text) * 3:
                self.logger.warning(
                    f"LLM output unexpectedly long ({len(processed_text)} chars vs "
                    f"{len(text)} input chars), using original text"
                )
                return text, processing_time

            return processed_text, processing_time

        except Exception as e:
            processing_time = time.time() - start_time
            self.logger.warning(f"LLM processing failed ({e}), using original text")
            return text, processing_time

    def _process_gemini(self, text: str, context_before: Optional[str],
                        context_after: Optional[str]) -> Tuple[str, object]:
        """Call Gemini API for text enhancement."""
        client = self._get_gemini_client()
        if client is None:
            return text, None

        prompt = self._build_prompt(text, context_before, context_after)

        from google.genai import types
        response = client.models.generate_content(
            model=self._model,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=self._temperature,
            )
        )

        return response.text.strip(), response

    def _process_groq(self, text: str, context_before: Optional[str],
                      context_after: Optional[str]) -> Tuple[str, object]:
        """Call Groq chat completions API for text enhancement."""
        client = self._get_groq_client()
        if client is None:
            return text, None

        has_context = self._has_context(context_before, context_after)
        user_prompt = self._build_user_prompt(text, context_before, context_after, has_context)
        system_prompt = self._get_system_prompt(has_context)

        response = client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=self._temperature,
        )

        return response.choices[0].message.content.strip(), response

    # ── Prompt building ────────────────────────────────────────────────────

    def _has_context(self, context_before: Optional[str], context_after: Optional[str]) -> bool:
        """Check if meaningful cursor context is available."""
        return bool(
            (context_before and context_before.strip()) or
            (context_after and context_after.strip())
        )

    def _build_prompt(self, text: str, context_before: Optional[str],
                      context_after: Optional[str]) -> str:
        """Build combined prompt for Gemini (system + user in one string)."""
        has_context = self._has_context(context_before, context_after)
        system = self._get_system_prompt(has_context)
        user = self._build_user_prompt(text, context_before, context_after, has_context)
        return system + "\n\n" + user

    def _get_system_prompt(self, has_context: bool) -> str:
        """Get the appropriate system prompt based on whether context is available."""
        if has_context:
            prompt = self._custom_system_with_context or self._prompt_config.get("system_with_context", "")
        else:
            prompt = self._custom_system_no_context or self._prompt_config.get("system_no_context", "")
        if self._personal_prompt:
            prompt += "\n\nAdditional instructions:\n" + self._personal_prompt
        return prompt

    def _build_user_prompt(self, text: str, context_before: Optional[str],
                           context_after: Optional[str],
                           has_context: Optional[bool] = None) -> str:
        """Build user message from prompt template."""
        if has_context is None:
            has_context = self._has_context(context_before, context_after)

        if has_context:
            template = self._prompt_config.get("user_with_context", 'Clean: "{transcription}"')
        else:
            template = self._prompt_config.get("user_no_context", 'Clean: "{transcription}"')

        return template.format(
            transcription=text,
            context_before=(context_before[-100:] if context_before else ""),
            context_after=(context_after[:100] if context_after else ""),
        )

    # ── Usage tracking ─────────────────────────────────────────────────────

    def _extract_token_usage(self, response) -> dict:
        """Extract token counts from LLM response using provider config."""
        config = PROVIDER_USAGE_CONFIG.get(self._provider, {})
        if not config:
            return {}
        try:
            usage_obj = getattr(response, config["usage_attr"], None)
            if usage_obj is None:
                return {}
            input_tokens = getattr(usage_obj, config["input_field"], 0)
            output_tokens = getattr(usage_obj, config["output_field"], 0)
            return {"input": input_tokens or 0, "output": output_tokens or 0}
        except Exception:
            return {}

    def _track_usage(self, token_usage: dict):
        """Track daily API usage and warn when approaching free tier limits."""
        today = time.strftime("%Y-%m-%d")
        if today != self._tracking_date:
            self._daily_requests = 0
            self._daily_input_tokens = 0
            self._daily_output_tokens = 0
            self._tracking_date = today

        self._daily_requests += 1
        self._daily_input_tokens += token_usage.get("input", 0)
        self._daily_output_tokens += token_usage.get("output", 0)

        self.logger.debug(
            f"LLM usage: req #{self._daily_requests} today | "
            f"tokens in={token_usage.get('input', '?')} out={token_usage.get('output', '?')} | "
            f"daily total in={self._daily_input_tokens} out={self._daily_output_tokens}"
        )

        config = PROVIDER_USAGE_CONFIG.get(self._provider, {})
        daily_limit = config.get("daily_request_limit")
        if daily_limit:
            usage_pct = self._daily_requests / daily_limit
            if usage_pct >= 0.95:
                self.logger.critical(
                    f"Near free tier limit ({self._daily_requests}/{daily_limit} daily requests). "
                    f"Charges may apply soon."
                )
            elif usage_pct >= 0.80:
                self.logger.warning(
                    f"Approaching free tier limit ({self._daily_requests}/{daily_limit} daily requests)"
                )
