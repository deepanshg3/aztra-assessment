"""FastAPI application for the Retail Sales Analytics assistant.

Provides a single ``POST /ask`` endpoint that accepts a question and returns
a validated ``AssessmentResponse``, plus a ``GET /health`` endpoint.
"""

from __future__ import annotations

from fastapi import FastAPI
from pydantic import BaseModel, Field

from src.orchestrator.orchestrator import AssessmentOrchestrator
from src.schemas.response import AssessmentResponse

app: FastAPI = FastAPI(
    title="Retail Sales Analytics Assistant",
    description="Answer questions about retail sales data using SQL and document retrieval.",
    version="1.0.0",
)

_orchestrator: AssessmentOrchestrator = AssessmentOrchestrator()


class AskRequest(BaseModel):
    """Request body for the ``POST /ask`` endpoint."""

    question: str = Field(..., min_length=1, description="The user's question")


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