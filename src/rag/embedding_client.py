"""Reusable embedding client wrapping Google's embedding model via LangChain.

The rest of the project must never import LangChain directly.
All embedding generation goes through the ``embed`` function exposed here.
"""

from __future__ import annotations

import time
from typing import Final

from langchain_google_genai import GoogleGenerativeAIEmbeddings

from src.core.logger import get_logger
from src.core.settings import settings

logger = get_logger(__name__)

_MAX_RETRIES: Final[int] = 3
_BASE_DELAY_S: Final[float] = 1.0
_BACKOFF_FACTOR: Final[float] = 2.0

_embeddings: GoogleGenerativeAIEmbeddings | None = None


def _init_embeddings() -> GoogleGenerativeAIEmbeddings:
    """Initialise and return the LangChain Google embedding model.

    The instance is cached after the first call so that subsequent calls
    reuse the same client.
    """
    global _embeddings
    if _embeddings is not None:
        return _embeddings

    logger.info(
        "Initialising embedding model",
        extra={"model": settings.embedding_model},
    )
    _embeddings = GoogleGenerativeAIEmbeddings(
        model=settings.embedding_model,
        google_api_key=settings.gemini_api_key,
    )
    logger.info("Embedding model initialised successfully")
    return _embeddings


def _is_transient_failure(exception: Exception) -> bool:
    """Return True if the exception is likely a transient network/API failure."""
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


def _invoke_with_retry(model: GoogleGenerativeAIEmbeddings, text: str) -> list[float]:
    """Embed text with exponential-backoff retry for transient failures."""
    last_exception: BaseException | None = None

    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            logger.debug("Embedding request", extra={"attempt": attempt})
            vector = model.embed_query(text)
            logger.debug(
                "Embedding response received",
                extra={"dimensions": len(vector)},
            )
            return vector
        except Exception as exc:
            last_exception = exc
            if not _is_transient_failure(exc):
                logger.error(
                    "Non-transient embedding failure",
                    extra={"error": str(exc)},
                )
                raise

            if attempt < _MAX_RETRIES:
                delay = _BASE_DELAY_S * (_BACKOFF_FACTOR ** (attempt - 1))
                logger.warning(
                    "Transient embedding failure, retrying",
                    extra={
                        "attempt": attempt,
                        "delay_s": delay,
                        "error": str(exc),
                    },
                )
                time.sleep(delay)
            else:
                logger.error(
                    "Embedding call failed after all retries",
                    extra={"attempts": _MAX_RETRIES, "error": str(exc)},
                )

    raise RuntimeError(
        f"Embedding call failed after {_MAX_RETRIES} attempts. "
        f"Last error: {last_exception}"
    ) from last_exception


def embed(text: str) -> list[float]:
    """Generate a vector embedding for the given text.

    Args:
        text: The text to embed.

    Returns:
        A list of floats representing the embedding vector.

    Raises:
        RuntimeError: If the embedding call fails after all retries.
    """
    model = _init_embeddings()
    return _invoke_with_retry(model, text)