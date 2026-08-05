"""Static configuration for the data cleaning pipeline."""

from __future__ import annotations

from pathlib import Path

RAW_DIR: Path = Path("data/raw")
CLEANED_DIR: Path = Path("data/cleaned")

DIMENSION_DATASETS: tuple[str, ...] = (
    "dim_sku.csv",
    "dim_geo.csv",
    "dim_rep.csv",
    "dim_distributor.csv",
)

FACT_DATASETS: tuple[str, ...] = (
    "fact_primary_sales.csv",
    "fact_targets.csv",
    "stockouts.csv",
    "promotions.csv",
)

ALL_DATASETS: tuple[str, ...] = DIMENSION_DATASETS + FACT_DATASETS

COLUMN_RENAMES: dict[str, str] = {
    "material_no": "sku_code",
    "item_code": "sku_code",
    "sku": "sku_code",
    "area": "territory",
}

TERRITORY_ALIASES: dict[str, str] = {
    "Bombay": "Mumbai",
    "BLR": "Bengaluru",
    "BGL": "Bengaluru",
    "BLG": "Bengaluru",
    "BEN": "Bengaluru",
}

REGION_NORMALISATION: dict[str, str] = {
    "S": "South",
    "E": "East",
}

TIER_NORMALISATION: dict[str, str] = {
    "VAL": "value",
    "Value": "value",
    "PREM": "premium",
    "Premium": "premium",
    "Mainstream": "mainstream",
}

DATE_FORMATS: tuple[str, ...] = (
    "%Y-%m-%d",
    "%d-%m-%Y",
    "%m/%d/%y",
    "%d %b %Y",
)

MISSING_SENTINELS: frozenset[str] = frozenset({"", "NA", "N/A", "#N/A"})

CHECK_COLUMNS: dict[str, tuple[str, ...]] = {
    "fact_primary_sales.csv": ("sku_code", "territory", "distributor_id"),
    "fact_targets.csv": ("sku_code", "territory"),
    "stockouts.csv": ("sku_code", "territory"),
    "promotions.csv": ("sku_code", "territory"),
    "dim_rep.csv": ("territory",),
    "dim_distributor.csv": ("territory",),
    "dim_geo.csv": (),
    "dim_sku.csv": (),
}
