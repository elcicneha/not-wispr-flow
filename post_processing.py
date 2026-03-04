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
    # Only add a leading space if we KNOW there's actual text before the cursor.
    # context_before=None → AX couldn't read context → don't add space (avoid extra spaces)
    # context_before="" → cursor is at field start → don't add space
    # context_before="actual text" → add space only if it doesn't end with whitespace/newline
    should_add_leading_space = False
    if text and not text[0].isspace():
        if (context_before and
              context_before.strip() and  # Has actual non-whitespace content
              context_before[-1] != '\n' and  # Not at start of new line
              not context_before[-1].isspace()):  # Not after any whitespace
            should_add_leading_space = True

    if should_add_leading_space:
        text = " " + text

    # Add trailing space based on context_after
    # If context_after is None or empty → add trailing space
    # If context_after exists → only add space if it doesn't start with whitespace
    should_add_trailing_space = True
    if text and not text.endswith(" "):
        if context_after and context_after[0].isspace():
            should_add_trailing_space = False

        if should_add_trailing_space:
            text = text + " "

    return text
