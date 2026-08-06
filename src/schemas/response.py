"""Pydantic schema for the final API response returned by the orchestrator."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

ValidIntent = Literal["WHAT", "WHY", "WHAT_TO_DO", "OUT_OF_DOMAIN"]
ValidStatus = Literal["OK", "PENDING_APPROVAL", "ABSTAINED"]


class AssessmentResponse(BaseModel):
    """Validated response returned by the orchestrator for every user question.

    Attributes:
        answer: The final answer text.
        intent: The classified intent of the question.
        citations: List of document filenames used as evidence.
        confidence: Confidence score between 0.0 and 1.0.
        status: Processing status — ``OK`` for completed queries,
            ``PENDING_APPROVAL`` for recommendations awaiting human approval,
            ``ABSTAINED`` for out-of-domain questions.
    """

    answer: str = Field(..., description="Final answer text")
    intent: ValidIntent = Field(
        ...,
        description="One of WHAT, WHY, WHAT_TO_DO, OUT_OF_DOMAIN",
    )
    citations: list[str] = Field(
        default_factory=list,
        description="Document filenames used as evidence",
    )
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Confidence score between 0.0 and 1.0",
    )
    status: ValidStatus = Field(
        ...,
        description="One of OK, PENDING_APPROVAL, ABSTAINED",
    )