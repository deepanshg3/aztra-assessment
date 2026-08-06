"""Deterministic SQL safety validator.

Rejects queries that contain dangerous or mutating SQL statements and
ensures only a single SELECT query is executed.
"""

from __future__ import annotations

import re
from typing import Final

from src.core.logger import get_logger

logger = get_logger(__name__)

_FORBIDDEN_KEYWORDS: Final[set[str]] = {
    "INSERT",
    "UPDATE",
    "DELETE",
    "DROP",
    "ALTER",
    "CREATE",
    "ATTACH",
    "DETACH",
    "PRAGMA",
    "VACUUM",
    "REINDEX",
    "TRUNCATE",
    "REPLACE",
}

_KEYWORD_PATTERN: str = r"\b(" + "|".join(_FORBIDDEN_KEYWORDS) + r")\b"

_RE_MULTI_STATEMENT: re.Pattern = re.compile(r";\s*(?:\n|$)", re.MULTILINE)


def _has_forbidden_keywords(sql: str) -> bool:
    """Check whether the SQL contains any forbidden keyword.

    Uses word-boundary matching to avoid false positives (e.g. ``UPDATES``
    matching ``UPDATE``).

    Args:
        sql: The SQL string to inspect.

    Returns:
        True if a forbidden keyword is found.
    """
    return bool(re.search(_KEYWORD_PATTERN, sql, re.IGNORECASE))


def _has_multiple_statements(sql: str) -> bool:
    """Check whether the SQL contains more than one statement.

    A single SELECT statement may contain semicolons inside string literals,
    but for production safety we reject any semicolon not at the end.

    Args:
        sql: The SQL string to inspect.

    Returns:
        True if multiple statements are detected.
    """
    stripped = sql.strip().rstrip(";")
    return ";" in stripped


def _is_select_statement(sql: str) -> bool:
    """Return True if the SQL begins with SELECT or WITH."""
    statement = sql.strip().upper()
    return statement.startswith("SELECT") or statement.startswith("WITH")


def validate(sql: str) -> str:
    """Validate a SQL string for safety and single-statement compliance.

    Args:
        sql: The raw SQL string to validate.

    Returns:
        The validated SQL string (unchanged).

    Raises:
        ValueError: If the SQL contains forbidden keywords.
        ValueError: If the SQL is not a single SELECT statement.
    """
    logger.info("SQL validation started")

    if not sql or not sql.strip():
        raise ValueError("SQL string is empty.")

    if not _is_select_statement(sql):
        raise ValueError(
            "Only SELECT statements are allowed. "
            f"Query must begin with SELECT. Got: {sql[:80]!r}"
        )

    if _has_forbidden_keywords(sql):
        raise ValueError(
            f"Only read-only SELECT queries are allowed."
        )

    if _has_multiple_statements(sql):
        raise ValueError(
            "Multiple SQL statements are not allowed. "
            "Provide a single SELECT statement only."
        )

    logger.info("SQL validation passed")
    return sql.strip()
