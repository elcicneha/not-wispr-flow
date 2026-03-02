#!/usr/bin/env python3
"""
LLM Post-Processing for Not Wispr Flow.

Provides intelligent text enhancement using Gemini API:
- Grammar correction
- Punctuation improvement
- Natural language refinement
- Context-aware formatting
"""

import os
import time
from typing import Optional, Tuple

# ============================================================================
# LLM PROMPT TEMPLATE
# ============================================================================
# This prompt is sent to Gemini to enhance transcribed text.
# Customize this to change how the LLM processes your dictations.
#
LLM_SYSTEM_PROMPT = """You are a text correction assistant for voice dictation. Your task is to:

1. Fix grammar and punctuation errors
2. Correct obvious transcription mistakes (e.g., "their" → "there" if contextually wrong)
3. Preserve the original meaning, tone, and intent
4. Keep informal language if that's the speaker's style
5. Return ONLY the corrected text, no explanations or quotes
"""

# ============================================================================
# PROVIDER USAGE CONFIG
# ============================================================================
# Maps provider names to their response field paths for token usage extraction.
# To add a new provider: add an entry with the attribute names on the response object.
#
PROVIDER_USAGE_CONFIG = {
    "gemini": {
        "usage_attr": "usage_metadata",
        "input_field": "prompt_token_count",
        "output_field": "candidates_token_count",
        "daily_request_limit": 250,
    },
    "openai": {
        "usage_attr": "usage",
        "input_field": "prompt_tokens",
        "output_field": "completion_tokens",
        "daily_request_limit": 500,
    },
    # "anthropic": {
    #     "usage_attr": "usage",
    #     "input_field": "input_tokens",
    #     "output_field": "output_tokens",
    #     "daily_request_limit": 1000,
    # },
}


class LLMProcessor:
    """
    Handles LLM-based post-processing of transcriptions using Gemini API.

    Features:
    - Grammar and punctuation correction
    - Natural language refinement
    - Configurable processing modes
    - Fallback to original text on errors
    """

    def __init__(self, api_key: str, model: str, enabled: bool, logger, provider: str = "gemini"):
        """
        Initialize LLM processor.

        Args:
            api_key: Gemini API key (empty string to resolve from env/dotfile)
            model: Gemini model name (e.g., "gemini-2.0-flash-exp")
            enabled: Whether LLM processing is enabled
            logger: Logger instance
            provider: Provider name matching a key in PROVIDER_USAGE_CONFIG
        """
        self.enabled = enabled
        self.logger = logger
        self._api_key = self._resolve_api_key(api_key, logger)
        self._model = model
        self._client = None

        # Usage tracking
        self._provider = provider
        self._provider_config = PROVIDER_USAGE_CONFIG.get(provider, {})
        self._daily_requests = 0
        self._daily_input_tokens = 0
        self._daily_output_tokens = 0
        self._tracking_date = time.strftime("%Y-%m-%d")

        if not self.enabled:
            self.logger.info("LLM post-processing: Disabled")
        elif self.enabled and not self._api_key:
            self.logger.warning("LLM processing enabled but no Gemini API key found. Disabling LLM processing.")
            self.logger.warning("Set GEMINI_API_KEY environment variable or save to ~/.config/notwisprflow/gemini_api_key")
            self.enabled = False
        else:
            self.logger.info(f"LLM post-processing: Enabled (model: {self._model}, provider: {self._provider})")

    @staticmethod
    def _resolve_api_key(config_key: str, logger) -> str:
        """
        Resolve Gemini API key from env var → dotfile.

        Priority:
        1. GEMINI_API_KEY environment variable
        2. ~/.config/notwisprflow/gemini_api_key file

        Args:
            config_key: API key from config (ignored, kept for API compatibility)
            logger: Logger instance for logging key source

        Returns:
            str: Resolved API key or empty string
        """
        # Check environment variable first
        env_key = os.environ.get("GEMINI_API_KEY", "")
        if env_key:
            logger.info("Gemini API key: found in environment variable")
            return env_key

        # Check dotfile
        key_file = os.path.expanduser("~/.config/notwisprflow/gemini_api_key")
        if os.path.exists(key_file):
            try:
                with open(key_file, "r") as f:
                    key = f.read().strip()
                if key:
                    logger.info(f"Gemini API key: found in {key_file}")
                    return key
            except Exception as e:
                logger.warning(f"Failed to read Gemini API key from {key_file}: {e}")

        return ""

    def _initialize_client(self):
        """Lazy initialization of Gemini client."""
        if self._client is None and self._api_key:
            try:
                from google import genai

                # Debug: log API key info (first/last 4 chars only for security)
                key_preview = f"{self._api_key[:4]}...{self._api_key[-4:]}" if len(self._api_key) > 8 else "***"
                self.logger.debug(f"Configuring Gemini with API key: {key_preview} (length: {len(self._api_key)})")

                self._client = genai.Client(api_key=self._api_key)
                self.logger.info(f"Gemini LLM client initialized: {self._model}")
            except Exception as e:
                import traceback
                self.logger.error(f"Failed to initialize Gemini client: {e}")
                self.logger.error(f"Traceback: {traceback.format_exc()}")
                self.enabled = False

    def process(self, text: str, context_before: Optional[str] = None,
                context_after: Optional[str] = None) -> Tuple[str, float]:
        """
        Process transcribed text through LLM for enhancement.

        Args:
            text: Raw transcribed text
            context_before: Text before cursor (for context-aware processing)
            context_after: Text after cursor (for context-aware processing)

        Returns:
            Tuple of (processed_text, processing_time_seconds)
            Returns original text if processing fails or is disabled
        """
        if not self.enabled:
            return text, 0.0

        start_time = time.time()

        try:
            self._initialize_client()

            if self._client is None:
                return text, 0.0

            # Build prompt with context if available
            prompt = self._build_prompt(text, context_before, context_after)

            # Call Gemini API (new google-genai package)
            from google.genai import types

            response = self._client.models.generate_content(
                model=self._model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.3,  # Lower temperature for more consistent corrections
                )
            )

            processed_text = response.text.strip()
            processing_time = time.time() - start_time

            # Track usage (async-safe: in-memory counters only)
            self._track_usage(self._extract_token_usage(response))

            # Validate output
            if not processed_text:
                self.logger.warning("LLM returned empty response, using original text")
                return text, processing_time

            if len(processed_text) < len(text) * 0.5:
                self.logger.warning(
                    f"LLM output appears truncated ({len(processed_text)} chars vs {len(text)} input chars), using original text"
                )
                return text, processing_time

            if len(processed_text) > len(text) * 3:
                self.logger.warning(
                    f"LLM output unexpectedly long ({len(processed_text)} chars vs {len(text)} input chars), using original text"
                )
                return text, processing_time

            return processed_text, processing_time

        except Exception as e:
            processing_time = time.time() - start_time
            self.logger.warning(f"LLM processing failed ({e}), using original text")
            return text, processing_time

    def _extract_token_usage(self, response) -> dict:
        """Extract token counts from LLM response using provider config."""
        if not self._provider_config:
            return {}
        try:
            usage_obj = getattr(response, self._provider_config["usage_attr"], None)
            if usage_obj is None:
                return {}
            input_tokens = getattr(usage_obj, self._provider_config["input_field"], 0)
            output_tokens = getattr(usage_obj, self._provider_config["output_field"], 0)
            return {"input": input_tokens or 0, "output": output_tokens or 0}
        except Exception:
            return {}

    def _track_usage(self, token_usage: dict):
        """Track daily API usage and warn when approaching free tier limits."""
        # Reset counters on new day
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

        daily_limit = self._provider_config.get("daily_request_limit")
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

    def _build_prompt(self, text: str, context_before: Optional[str],
                     context_after: Optional[str]) -> str:
        """
        Build prompt for Gemini API with optional context.

        Uses the LLM_SYSTEM_PROMPT constant (defined at top of file) and adds
        cursor context if available.
        """
        # Start with the system prompt template
        prompt = LLM_SYSTEM_PROMPT + "\n"

        # Add context if available
        if context_before and context_before.strip():
            prompt += f"\n[Text before cursor]: ...{context_before[-100:]}\n"

        prompt += f"\n[Dictated text to correct]: {text}\n"

        if context_after and context_after.strip():
            prompt += f"\n[Text after cursor]: {context_after[:100]}...\n"

        prompt += "\nReturn only the corrected version of the dictated text:"

        return prompt
