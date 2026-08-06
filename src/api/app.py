"""FastAPI application for the Retail Sales Analytics assistant.

Provides a single ``POST /ask`` endpoint that accepts a question and returns
a validated ``AssessmentResponse``, plus a ``GET /health`` endpoint.
"""

from __future__ import annotations

from pathlib import Path
from typing import Final

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, ValidationError

from src.core.logger import get_logger
from src.orchestrator.orchestrator import AssessmentOrchestrator
from src.schemas.response import AssessmentResponse

logger = get_logger(__name__)

_PROJECT_ROOT: Final[Path] = Path(__file__).resolve().parent.parent.parent
_DB_PATH: Final[Path] = _PROJECT_ROOT / "data" / "database" / "suryaa.db"
_VECTOR_DB_PATH: Final[Path] = _PROJECT_ROOT / "data" / "vector_db"

app: FastAPI = FastAPI(
    title="Retail Sales Analytics Assistant",
    description="Answer questions about retail sales data using SQL and document retrieval.",
    version="1.0.0",
)


def _validate_startup() -> None:
    """Validate that all required resources exist at startup.

    Raises:
        RuntimeError: If any required resource is missing.
    """
    if not _DB_PATH.is_file():
        raise RuntimeError(
            f"Database not found at {_DB_PATH}. "
            "Run the database builder first."
        )
    if not _VECTOR_DB_PATH.is_dir():
        raise RuntimeError(
            f"Vector database not found at {_VECTOR_DB_PATH}. "
            "Run the indexing pipeline first."
        )


_validate_startup()
_orchestrator: AssessmentOrchestrator = AssessmentOrchestrator()


class AskRequest(BaseModel):
    """Request body for the ``POST /ask`` endpoint."""

    question: str = Field(..., min_length=1, description="The user's question")


@app.exception_handler(ValueError)
def _value_error_handler(request: Request, exc: ValueError) -> JSONResponse:
    """Handle ValueError as HTTP 400."""
    logger.warning("Bad request", extra={"error": str(exc)})
    return JSONResponse(
        status_code=400,
        content={"detail": str(exc)},
    )


@app.exception_handler(ValidationError)
def _validation_error_handler(request: Request, exc: ValidationError) -> JSONResponse:
    """Handle Pydantic ValidationError as HTTP 422."""
    logger.warning("Validation error", extra={"error": str(exc)})
    return JSONResponse(
        status_code=422,
        content={"detail": exc.errors()},
    )


@app.exception_handler(Exception)
def _generic_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle unexpected exceptions as HTTP 500."""
    logger.exception("Unexpected error")
    return JSONResponse(
        status_code=500,
        content={"detail": "An internal error occurred. Please try again later."},
    )


@app.get("/health")
def health() -> dict[str, str]:
    """Health-check endpoint.

    Returns:
        A simple status dictionary ``{"status": "healthy"}``.
    """
    return {"status": "healthy"}


@app.post("/ask", response_model=AssessmentResponse)
def ask(request: AskRequest) -> AssessmentResponse:
    """Process a user question end-to-end and return the final answer.

    Args:
        request: The request body containing the question.

    Returns:
        A validated ``AssessmentResponse`` instance.
    """
    return _orchestrator.process(request.question)