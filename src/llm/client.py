"""Reusable LLM client wrapping LangChain's Google Gemini integration.

The rest of the project must never import LangChain directly.
All LLM interaction goes through the ``invoke`` function exposed here.
"""

from __future__ import annotations

import time
from typing import Any, Final

from langchain_google_genai import ChatGoogleGenerativeAI

from src.core.logger import get_logger
from src.core.settings import settings

logger = get_logger(__name__)

_MAX_RETRIES: Final[int] = 3
_BASE_DELAY_S: Final[float] = 1.0
_BACKOFF_FACTOR: Final[float] = 2.0

_model: ChatGoogleGenerativeAI | None = None


def _init_model() -> ChatGoogleGenerativeAI:
    """Initialise and return the LangChain Gemini model.

    The model is cached after the first call so that subsequent invocations
    reuse the same client instance.
    """
    global _model
    if _model is not None:
        return _model

    logger.info(
        "Initialising Gemini model", extra={"model": settings.gemini_model}
    )
    _model = ChatGoogleGenerativeAI(
        model=settings.gemini_model,
        google_api_key=settings.gemini_api_key,
    )
    logger.info("Gemini model initialised successfully")
    return _model


def _is_transient_failure(exception: Exception) -> bool:
    """Return ``True`` if *exception* is likely a transient network/API error."""
    import requests
    from google.api_core import exceptions as google_exceptions

    transient_types = (
        google_exceptions.ServiceUnavailable,
        google_exceptions.DeadlineExceeded,
        google_exceptions.InternalServerError,
        google_exceptions.ResourceExhausted,
        google_exceptions.GatewayTimeout,
        requests.exceptions.ConnectionError,
        requests.exceptions.Timeout,
    )
    return isinstance(exception, transient_types)


def _invoke_with_retry(model: ChatGoogleGenerativeAI, prompt: str) -> str:
    """Call the model with exponential-backoff retry for transient failures."""
    last_exception: Exception | None = None

    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            logger.debug("LLM request", extra={"attempt": attempt})
            response = model.invoke(prompt)
            content: Any = response.content
            text = str(content) if content is not None else ""
            logger.debug("LLM response received", extra={"length": len(text)})
            return text
        except Exception as exc:
            last_exception = exc
            if not _is_transient_failure(exc):
                logger.error("Non-transient LLM failure", extra={"error": str(exc)})
                raise

            if attempt < _MAX_RETRIES:
                delay = _BASE_DELAY_S * (_BACKOFF_FACTOR ** (attempt - 1))
                logger.warning(
                    "Transient LLM failure, retrying",
                    extra={"attempt": attempt, "delay_s": delay, "error": str(exc)},
                )
                time.sleep(delay)
            else:
                logger.error(
                    "LLM call failed after all retries",
                    extra={"attempts": _MAX_RETRIES, "error": str(exc)},
                )

    raise RuntimeError(
        f"LLM call failed after {_MAX_RETRIES} attempts. "
        f"Last error: {last_exception}"
    ) from last_exception


def invoke(prompt: str) -> str:
    """Send a prompt to the LLM and return the text response.

    Args:
        prompt: The full prompt string to send to the model.

    Returns:
        The model's response as plain text.

    Raises:
        RuntimeError: If the call fails after all retries.
    """
    model = _init_model()
    return _invoke_with_retry(model, prompt)