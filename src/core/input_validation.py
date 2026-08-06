"""Reusable input validation helpers for the project."""

from __future__ import annotations

_MAX_QUESTION_LENGTH: int = 5000


def validate_question(question: str) -> str:
    """Validate and sanitize a user question before processing.

    Args:
        question: The raw user question.

    Returns:
        The sanitized question with leading/trailing whitespace removed.

    Raises:
        ValueError: If the question is empty or exceeds the maximum length.
    """
    sanitized = question.strip()

    if not sanitized:
        raise ValueError("Question cannot be empty.")

    if len(sanitized) > _MAX_QUESTION_LENGTH:
        raise ValueError(
            f"Question exceeds maximum length of {_MAX_QUESTION_LENGTH} characters. "
            f"Got {len(sanitized)} characters."
        )

    return sanitized