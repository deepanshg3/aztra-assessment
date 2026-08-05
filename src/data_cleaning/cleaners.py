"""Field-level standardisation helpers for the cleaning pipeline.

Every function takes a single string value and returns the canonical
standardised string, leaving the value untouched when it cannot be
normalised safely.
"""

from __future__ import annotations

import datetime
import re
from collections.abc import Iterable

from src.data_cleaning.config import (
    DATE_FORMATS,
    MISSING_SENTINELS,
    REGION_NORMALISATION,
    TERRITORY_ALIASES,
    TIER_NORMALISATION,
)

_NUMERIC_PREFIX_RE = re.compile(r"^rs\.?\s*", re.IGNORECASE)


def strip_string(value: str) -> str:
    """Return ``value`` with leading and trailing whitespace removed."""
    return value.strip()


def normalise_sku_code(value: str) -> str:
    """Return an upper-cased, whitespace-trimmed SKU code."""
    return value.strip().upper()


def normalise_territory(value: str) -> str:
    """Map known territory aliases to their canonical name."""
    return TERRITORY_ALIASES.get(value.strip(), value.strip())


def normalise_region(value: str) -> str:
    """Map abbreviated region values to their full name."""
    return REGION_NORMALISATION.get(value.strip(), value.strip())


def normalise_tier(value: str) -> str:
    """Map tier variants to their canonical lowercase form."""
    tier = value.strip()
    return TIER_NORMALISATION.get(tier, tier.lower())


def normalise_date(value: str) -> str:
    """Return ``value`` as an ISO ``YYYY-MM-DD`` date string.

    Supports the formats listed in ``DATE_FORMATS``. Values that match no
    supported format are returned unchanged.
    """
    candidate = value.strip()
    for date_format in DATE_FORMATS:
        try:
            parsed = datetime.datetime.strptime(candidate, date_format)
        except ValueError:
            continue
        return parsed.strftime("%Y-%m-%d")
    return candidate


def normalise_sales_value(value: str) -> str:
    """Convert a mixed-format monetary value to a plain numeric string.

    Removes currency prefixes (e.g. ``Rs``) and thousands separators.
    Values that cannot be parsed are returned unchanged.
    """
    candidate = _NUMERIC_PREFIX_RE.sub("", value.strip())
    candidate = candidate.replace(",", "")
    try:
        return str(float(candidate))
    except ValueError:
        return value.strip()


def repair_distributor_id(value: str, valid_ids: Iterable[str]) -> str:
    """Drop a leading zero from a distributor id when that repairs it.

    The repaired value is only used when it exists in ``valid_ids``,
    ensuring corrupted ids are never blindly modified.
    """
    candidate = value.strip()
    if not candidate.startswith("0"):
        return candidate
    repaired = candidate[1:]
    if repaired in set(valid_ids):
        return repaired
    return candidate


def is_missing(value: str) -> bool:
    """Return ``True`` when ``value`` represents a missing cell."""
    return value.strip().upper() in MISSING_SENTINELS
