"""Final response generator that converts retrieved evidence into a validated
``AssessmentResponse`` using the LLM.

This module is ONLY responsible for building the prompt, calling the reusable
LLM client, parsing the response, and validating it against the Pydantic
schema. It does NOT classify intent, generate SQL, execute SQL, or retrieve
documents.
"""

from __future__ import annotations

import json
from typing import Any

from src.core.input_validation import validate_question
from src.core.logger import get_logger
from src.llm.client import invoke as llm_invoke
from src.response_generator.prompts import RESPONSE_GENERATION_PROMPT
from src.schemas.response import AssessmentResponse

logger = get_logger(__name__)


def _format_rows(rows: list[dict[str, object]] | None) -> str:
    """Format SQL result rows into a readable text representation.

    Args:
        rows: List of row dicts from the SQL executor, or None.

    Returns:
        A string representation suitable for the LLM prompt.
    """
    if not rows:
        return "(no data returned)"
    lines: list[str] = []
    for i, row in enumerate(rows, start=1):
        lines.append(f"  Row {i}: {json.dumps(row)}")
    return "\n".join(lines)


def _format_documents(documents: list[dict[str, object]] | None) -> str:
    """Format retrieved documents into a readable text representation.

    Args:
        documents: List of doc dicts from the retriever, or None.

    Returns:
        A string representation suitable for the LLM prompt.
    """
    if not documents:
        return "(no documents retrieved)"
    lines: list[str] = []
    for i, doc in enumerate(documents, start=1):
        filename = doc.get("filename", "unknown")
        content = doc.get("content", "")
        lines.append(f"  Document {i} ({filename}):\n    {content}")
    return "\n".join(lines)


def _build_prompt(
    question: str,
    intent: str,
    sql_rows: list[dict[str, object]] | None,
    documents: list[dict[str, object]] | None,
) -> str:
    """Construct the full prompt by inserting all evidence.

    Args:
        question: The original user question.
        intent: The classified intent string.
        sql_rows: Rows returned by the SQL executor.
        documents: Documents returned by the retriever.

    Returns:
        A formatted prompt string ready for the LLM.
    """
    return RESPONSE_GENERATION_PROMPT.format(
        question=question,
        intent=intent,
        sql_rows=_format_rows(sql_rows),
        documents=_format_documents(documents),
    )


def _parse_json_response(raw: str) -> dict[str, Any]:
    """Parse the LLM response as JSON, handling markdown fences.

    Args:
        raw: The raw LLM response string.

    Returns:
        A parsed dictionary with keys ``answer``, ``citations``, ``confidence``.

    Raises:
        ValueError: If the response cannot be parsed as JSON.
    """
    text = raw.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        text = "\n".join(lines[1:])
        if text.endswith("```"):
            text = text[:-3].strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(
            "Response generator returned malformed JSON."
        ) from exc


def _validate_parsed_response(data: dict[str, Any]) -> None:
    """Validate that all required fields are present in the parsed response.

    Args:
        data: The parsed JSON dictionary.

    Raises:
        ValueError: If required fields are missing.
    """
    if "answer" not in data or not isinstance(data.get("answer"), str) or not data["answer"].strip():
        raise ValueError("Response generator output is missing a valid 'answer' field.")
    if "citations" not in data or not isinstance(data.get("citations"), list):
        raise ValueError("Response generator output is missing a valid 'citations' field.")
    if "confidence" not in data:
        raise ValueError("Response generator output is missing the 'confidence' field.")


def generate(
    question: str,
    intent: str,
    sql_rows: list[dict[str, object]] | None = None,
    documents: list[dict[str, object]] | None = None,
    status: str = "OK",
) -> AssessmentResponse:
    """Generate a final validated answer using the LLM and supplied evidence.

    Args:
        question: The original user question.
        intent: The detected intent (``WHAT``, ``WHY``, or ``WHAT_TO_DO``).
        sql_rows: Rows returned by the SQL executor (may be empty).
        documents: Documents returned by the retriever (may be empty).
        status: The response status to set (``OK`` or ``PENDING_APPROVAL``).

    Returns:
        A validated ``AssessmentResponse`` instance.

    Raises:
        RuntimeError: If the LLM call fails after all retries.
        ValueError: If the LLM response cannot be parsed or validated.
    """
    question = validate_question(question)

    logger.info(
        "Generating final response",
        extra={"intent": intent, "status": status},
    )

    prompt = _build_prompt(question, intent, sql_rows, documents)
    raw_response = llm_invoke(prompt)

    logger.debug("Raw response generator output received", extra={"resp_len": len(raw_response)})

    try:
        parsed = _parse_json_response(raw_response)
    except ValueError as exc:
        logger.error(
            "Failed to parse response generator output",
            extra={"error": str(exc)},
        )
        raise

    _validate_parsed_response(parsed)

    answer: str = parsed.get("answer", "")
    citations: list[str] = [
        str(c) for c in parsed.get("citations", [])
    ]
    confidence: float = float(parsed.get("confidence", 0.0))

    result = AssessmentResponse(
        answer=answer,
        intent=intent,
        citations=citations,
        confidence=confidence,
        status=status,
    )

    logger.info(
        "Final response generated",
        extra={
            "intent": result.intent,
            "status": result.status,
            "confidence": result.confidence,
            "citations_count": len(result.citations),
        },
    )

    return result