"""Intent classifier that categorises a user question into a predefined intent.

This module contains no business logic beyond classification. It loads the
classification prompt, calls the reusable LLM client, validates the output
against the Pydantic schema, and returns the validated result.
"""

from __future__ import annotations

import json
from typing import Any

from src.core.logger import get_logger
from src.llm.client import invoke as llm_invoke
from src.llm.prompts import INTENT_CLASSIFICATION_PROMPT
from src.schemas.intent import IntentClassification

logger = get_logger(__name__)


def _build_prompt(question: str) -> str:
    """Insert the user question into the classification prompt template."""
    return INTENT_CLASSIFICATION_PROMPT.format(question=question)


def _parse_json_response(raw: str) -> dict[str, Any]:
    """Parse the LLM response as JSON, handling markdown fences."""
    text = raw.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        fence = lines[0]
        text = "\n".join(lines[1:])
        if text.endswith("```"):
            text = text[:-3].strip()
        elif fence.count("```") == 2 and len(lines) == 1:
            text = fence.replace("```json", "").replace("```", "").strip()
    return json.loads(text)


def _validate_response(data: dict[str, Any]) -> IntentClassification:
    """Validate the parsed JSON against the IntentClassification schema."""
    try:
        return IntentClassification(**data)
    except Exception as exc:
        logger.error(
            "Intent validation failed",
            extra={"parsed_data": data, "error": str(exc)},
        )
        raise


def classify(question: str) -> IntentClassification:
    """Classify a user question into a predefined intent.

    Args:
        question: The raw user question string.

    Returns:
        A validated :class:`IntentClassification` instance.

    Raises:
        RuntimeError: If the LLM call fails after retries.
        ValueError: If the response cannot be parsed or validated.
    """
    logger.info("Classifying intent", extra={"question": question})

    prompt = _build_prompt(question)
    raw_response = llm_invoke(prompt)

    logger.debug("Raw LLM response received", extra={"raw": raw_response})

    try:
        parsed = _parse_json_response(raw_response)
    except (json.JSONDecodeError, Exception) as exc:
        logger.error(
            "Failed to parse LLM response as JSON",
            extra={"raw": raw_response, "error": str(exc)},
        )
        raise ValueError(
            f"LLM returned malformed JSON. Response: {raw_response!r}"
        ) from exc

    classification = _validate_response(parsed)

    logger.info(
        "Intent classified",
        extra={"intent": classification.intent},
    )

    return classification