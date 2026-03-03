"""Post-processing pipeline for transcribed text.

Handles LLM enhancement and smart spacing before text insertion.
"""

import logging

logger = logging.getLogger("NotWisprFlow")


def post_process(text, context_before, context_after, backend="unknown", llm_model="disabled", llm_processor=None):
    """
    Apply post-processing transformations to transcribed text.

    Processing pipeline:
    1. LLM enhancement (if enabled AND online) - grammar, punctuation, corrections
    2. Smart spacing - add leading/trailing spaces based on context

    Args:
        text: Raw transcribed text
        context_before: Text preceding the cursor (may be None or empty string)
        context_after: Text following the cursor (may be None or empty string)
        backend: Transcription backend used ("groq" or "local")
        llm_model: Current LLM model name (or "disabled")
        llm_processor: LLMProcessor instance (or None)

    Returns:
        str: Post-processed text ready for insertion
    """
    # Step 1: LLM enhancement (optional, online only)
    # LLM runs if: enabled (runtime toggle) AND backend is online (groq)
    # This respects the offline/online mode separation
    llm_time = 0.0
    original_text = text  # Save for logging

    llm_active = llm_model != "disabled" and llm_processor and llm_processor.enabled
    if llm_active and backend == "groq":
        text, llm_time = llm_processor.process(text, context_before, context_after)
        if llm_time > 0:
            logger.info(f"LLM processing ({llm_model}): {llm_time:.2f}s")
            logger.info(f"  Before: {original_text}")
            logger.info(f"  After:  {text}")
    elif llm_active and backend == "local":
        logger.debug("LLM processing skipped (local/offline transcription)")
    elif llm_model == "disabled" and backend == "groq":
        logger.debug("LLM processing disabled by user")

    # Step 2: Smart spacing
    # Only add a leading space if:
    # - There's actual non-whitespace text before the cursor (not empty/None/whitespace-only)
    # - We're not at the start of a new line (after a newline character)
    # - The text before doesn't end with whitespace
    # - Our transcribed text doesn't start with whitespace
    should_add_leading_space = False
    if (context_before and text and
        context_before.strip() and  # Has actual non-whitespace content
        context_before[-1] != '\n' and  # Not at start of new line
        not context_before[-1].isspace() and  # Not after any whitespace
        not text[0].isspace()):  # Text doesn't start with space
        should_add_leading_space = True
        text = " " + text

    # Only add trailing space if context after doesn't start with a space
    should_add_trailing_space = True
    if context_after and context_after[0].isspace():
        should_add_trailing_space = False

    if should_add_trailing_space and not text.endswith(" "):
        text = text + " "

    return text
