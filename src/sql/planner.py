"""SQL query planner that generates SQL from a user question.

This module is responsible ONLY for generating SQL. It does not execute,
validate, or modify the generated query.
"""

from __future__ import annotations

from src.core.logger import get_logger
from src.llm.client import invoke as llm_invoke
from src.sql.database_summary import DATABASE_SUMMARY
from src.sql.prompts import SQL_PLANNING_PROMPT

logger = get_logger(__name__)


def _build_prompt(question: str) -> str:
    """Construct the full prompt by inserting placeholders.

    Args:
        question: The user's natural-language question.

    Returns:
        A formatted prompt string ready for the LLM.
    """
    return SQL_PLANNING_PROMPT.format(
        database_summary=DATABASE_SUMMARY,
        question=question,
    )


def _clean_sql(raw: str) -> str:
    """Strip markdown code fences and normalise the SQL output.

    Args:
        raw: The raw LLM response.

    Returns:
        A clean SQL string.
    """
    text = raw.strip()

    if text.startswith("```"):
        text = text.removeprefix("```sql")
        text = text.removeprefix("```sqlite")
        text = text.removeprefix("```")
        text = text.removesuffix("```")

    text = text.strip()

    if text.endswith(";"):
        text = text[:-1].strip()

    return text


def plan(question: str) -> str:
    """Generate a SQL query for the given user question.

    Args:
        question: The user's natural-language question.

    Returns:
        A raw SQL query string.

    Raises:
        RuntimeError: If the LLM call fails after all retries.
    """
    logger.info("SQL generation started", extra={"question": question})

    prompt = _build_prompt(question)
    raw_sql = llm_invoke(prompt)
    sql = _clean_sql(raw_sql)

    logger.info("SQL generated successfully", extra={"sql": sql})
    return sql
