"""Application settings loaded from environment variables."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Final

from dotenv import load_dotenv
from pydantic import Field, ValidationError
from pydantic import BaseModel as _BaseModel

_PROJECT_ROOT: Final[Path] = Path(__file__).resolve().parent.parent.parent
_DOT_ENV_PATH: Final[Path] = _PROJECT_ROOT / ".env"

load_dotenv(dotenv_path=_DOT_ENV_PATH, override=False)


class _Settings(_BaseModel):
    gemini_api_key: str = Field(..., min_length=1, repr=False)
    gemini_model: str = Field(default="gemini-2.0-flash-lite", min_length=1)
    embedding_model: str = Field(default="gemini-embedding-001", min_length=1)


def _load_settings() -> _Settings:
    raw = {
        "gemini_api_key": os.getenv("GEMINI_API_KEY", ""),
        "gemini_model": os.getenv("GEMINI_MODEL", "gemini-2.0-flash-lite"),
        "embedding_model": os.getenv("EMBEDDING_MODEL", "gemini-embedding-001"),
    }
    try:
        return _Settings(**raw)
    except ValidationError as exc:
        missing = [e["loc"][0] for e in exc.errors() if e["type"] == "missing"]
        msg = (
            f"Missing required environment variable(s): {', '.join(missing)}. "
            f"Ensure they are set in {_DOT_ENV_PATH} or in the shell environment."
        )
        raise RuntimeError(msg) from exc


settings: Final[_Settings] = _load_settings()
