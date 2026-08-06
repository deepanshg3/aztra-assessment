"""Pydantic schema for validated LLM intent classification output."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

ValidIntent = Literal["WHAT", "WHY", "WHAT_TO_DO", "OUT_OF_DOMAIN"]


class IntentClassification(BaseModel):
    """Strictly validated intent classification result.

    Attributes:
        intent: The classified intent, restricted to one of the four
            assessment-defined values.
    """

    intent: ValidIntent = Field(
        ...,
        description="One of WHAT, WHY, WHAT_TO_DO, OUT_OF_DOMAIN",
    )