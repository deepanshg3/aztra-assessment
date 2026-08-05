"""Orchestration for the retail sales data cleaning pipeline.

The pipeline reads every raw dataset from ``data/raw/``, applies the
canonical cleaning rules, removes exact duplicate rows, validates
referential integrity against the cleaned dimension tables and writes the
cleaned datasets to ``data/cleaned/`` using their original filenames.

The pipeline is deterministic and idempotent: re-running it on the same
input always produces identical output.
"""

from __future__ import annotations

import csv
from collections import Counter
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from pathlib import Path

from src.core.logger import get_logger
from src.data_cleaning import cleaners
from src.data_cleaning.config import (
    ALL_DATASETS,
    CHECK_COLUMNS,
    CLEANED_DIR,
    COLUMN_RENAMES,
    DIMENSION_DATASETS,
    FACT_DATASETS,
    RAW_DIR,
)

logger = get_logger(__name__)


@dataclass
class ReferenceSets:
    """Valid reference values drawn from the cleaned dimension tables."""

    sku_codes: set[str] = field(default_factory=set)
    territories: set[str] = field(default_factory=set)
    distributor_ids: set[str] = field(default_factory=set)


@dataclass
class Reconciliation:
    """Per-dataset counters used to log the cleaning summary."""

    dataset: str
    rows_read: int = 0
    rows_written: int = 0
    duplicates_removed: int = 0
    values_standardized: int = 0
    distributor_ids_repaired: int = 0
    missing_values: int = 0
    warnings: dict[tuple[str, str], int] = field(default_factory=dict)

    def log(self) -> None:
        """Log the reconciliation summary for this dataset."""
        logger.info(
            "%s: rows_read=%d rows_written=%d duplicates_removed=%d "
            "values_standardized=%d distributor_ids_repaired=%d "
            "missing_values=%d validation_warnings=%d",
            self.dataset,
            self.rows_read,
            self.rows_written,
            self.duplicates_removed,
            self.values_standardized,
            self.distributor_ids_repaired,
            self.missing_values,
            len(self.warnings),
        )
        for (column, value), count in sorted(self.warnings.items()):
            logger.warning(
                "%s: %s=%r has %d unresolved value(s), preserved as-is",
                self.dataset,
                column,
                value,
                count,
            )


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    """Read a CSV file and return its field names and rows."""
    with open(path, newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        fieldnames = list(reader.fieldnames or ())
        rows = [dict(row) for row in reader]
    return fieldnames, rows


def write_csv(path: Path, fieldnames: Sequence[str], rows: Iterable[dict[str, str]]) -> None:
    """Write rows to a CSV file in a deterministic fashion."""
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(fieldnames))
        writer.writeheader()
        writer.writerows(rows)


def clean_row(
    row: dict[str, str],
    references: ReferenceSets,
) -> tuple[dict[str, str], int, int]:
    """Standardise one raw row and count the changes applied.

    Returns the cleaned row together with the number of values
    standardised and the number of distributor ids repaired.
    """
    cleaned: dict[str, str] = {}
    standardized = 0
    repaired = 0

    for column, raw in row.items():
        target = COLUMN_RENAMES.get(column, column)
        value = cleaners.strip_string(raw)

        if target == "sku_code":
            value = cleaners.normalise_sku_code(value)
        elif target == "territory":
            value = cleaners.normalise_territory(value)
        elif target == "region":
            value = cleaners.normalise_region(value)
        elif target == "tier":
            value = cleaners.normalise_tier(value)
        elif target == "week_start":
            value = cleaners.normalise_date(value)
        elif target == "primary_sales_value":
            value = cleaners.normalise_sales_value(value)
        elif target == "distributor_id":
            repaired_value = cleaners.repair_distributor_id(value, references.distributor_ids)
            if repaired_value != value:
                repaired += 1
            value = repaired_value

        if value != raw:
            standardized += 1
        cleaned[target] = value

    return cleaned, standardized, repaired


def drop_duplicates(rows: list[dict[str, str]]) -> tuple[list[dict[str, str]], int]:
    """Remove exact duplicate rows, preserving first-seen order."""
    unique: list[dict[str, str]] = []
    seen: set[tuple[tuple[str, str], ...]] = set()
    for row in rows:
        key = tuple(sorted(row.items()))
        if key not in seen:
            seen.add(key)
            unique.append(row)
    return unique, len(rows) - len(unique)


def count_missing(rows: Iterable[dict[str, str]]) -> int:
    """Count cells that hold missing values across the given rows."""
    total = 0
    for row in rows:
        for value in row.values():
            if cleaners.is_missing(value):
                total += 1
    return total


def validate_rows(
    rows: Iterable[dict[str, str]],
    check_columns: Sequence[str],
    references: ReferenceSets,
) -> dict[tuple[str, str], int]:
    """Validate referential integrity, preserving invalid rows.

    Returns a mapping of ``(column, value)`` to the number of rows that
    reference an unknown value. Invalid rows are never discarded.
    """
    warnings: Counter[tuple[str, str]] = Counter()
    for row in rows:
        for column in check_columns:
            value = row.get(column)
            if value is None:
                continue
            valid = {
                "sku_code": references.sku_codes,
                "territory": references.territories,
                "distributor_id": references.distributor_ids,
            }[column]
            if value not in valid:
                warnings[(column, value)] += 1
    return dict(warnings)


def update_references(references: ReferenceSets, dataset: str, rows: Sequence[dict[str, str]]) -> None:
    """Populate the reference sets from a cleaned dimension table."""
    if dataset == "dim_sku.csv":
        references.sku_codes = {row["sku_code"] for row in rows}
    elif dataset == "dim_geo.csv":
        references.territories = {row["territory"] for row in rows}
    elif dataset == "dim_distributor.csv":
        references.distributor_ids = {row["distributor_id"] for row in rows}


def clean_dataset(
    dataset: str,
    raw_dir: Path,
    cleaned_dir: Path,
    references: ReferenceSets,
) -> Reconciliation:
    """Clean, deduplicate, validate and write a single dataset."""
    raw_path = raw_dir / dataset
    if not raw_path.is_file():
        raise FileNotFoundError(f"Raw dataset not found: {raw_path}")

    fieldnames, rows = read_csv(raw_path)
    target_fieldnames = [COLUMN_RENAMES.get(column, column) for column in fieldnames]

    cleaned_rows: list[dict[str, str]] = []
    reconciliation = Reconciliation(dataset=dataset, rows_read=len(rows))
    for row in rows:
        cleaned, standardized, repaired = clean_row(row, references)
        cleaned_rows.append(cleaned)
        reconciliation.values_standardized += standardized
        reconciliation.distributor_ids_repaired += repaired

    unique_rows, duplicates_removed = drop_duplicates(cleaned_rows)
    reconciliation.duplicates_removed = duplicates_removed
    reconciliation.rows_written = len(unique_rows)
    reconciliation.missing_values = count_missing(unique_rows)

    update_references(references, dataset, unique_rows)
    reconciliation.warnings = validate_rows(
        unique_rows, CHECK_COLUMNS[dataset], references
    )

    write_csv(cleaned_dir / dataset, target_fieldnames, unique_rows)
    reconciliation.log()
    return reconciliation


def run_pipeline(
    raw_dir: str | Path = RAW_DIR,
    cleaned_dir: str | Path = CLEANED_DIR,
) -> None:
    """Execute the full cleaning pipeline over every raw dataset."""
    raw_path = Path(raw_dir)
    cleaned_path = Path(cleaned_dir)

    if not raw_path.is_dir():
        raise FileNotFoundError(f"Raw data directory not found: {raw_path}")

    cleaned_path.mkdir(parents=True, exist_ok=True)
    references = ReferenceSets()

    logger.info("Starting cleaning pipeline for %d datasets", len(ALL_DATASETS))

    for dataset in DIMENSION_DATASETS:
        clean_dataset(dataset, raw_path, cleaned_path, references)
    for dataset in FACT_DATASETS:
        clean_dataset(dataset, raw_path, cleaned_path, references)

    logger.info("Cleaning pipeline finished. Cleaned output written to %s", cleaned_path)


def main() -> None:
    """Run the pipeline from the command line."""
    run_pipeline()


if __name__ == "__main__":
    main()
