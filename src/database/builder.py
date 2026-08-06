"""Idempotent SQLite database builder for the retail sales project.

Usage::

    builder = DatabaseBuilder()
    builder.build()
"""

from __future__ import annotations

import csv
import sqlite3
from collections import Counter
from collections.abc import Iterator, Sequence
from pathlib import Path
from typing import Any

from src.core.logger import get_logger
from src.database.schema import (
    CREATE_TABLE_DDL,
    CREATE_INDEXES,
    CSV_TO_TABLE,
    FK_RELATIONSHIPS,
    IMPORT_ORDER,
    PK_COLUMNS,
    TABLE_NAMES,
)

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_DEFAULT_DB_DIR = Path("data/database")
_DEFAULT_DB_PATH = _DEFAULT_DB_DIR / "suryaa.db"
_DEFAULT_CLEANED_DIR = Path("data/cleaned")


# ---------------------------------------------------------------------------
# Exception
# ---------------------------------------------------------------------------


class DatabaseBuildError(Exception):
    """Raised when the database build or validation fails."""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _csv_row_count(path: Path) -> int:
    """Return the number of data rows (excluding header) in *path*."""
    with open(path, newline="", encoding="utf-8") as f:
        return sum(1 for _ in f) - 1


def _read_csv_rows(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    """Return (fieldnames, rows) for the CSV at *path*."""
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = list(reader.fieldnames or ())
        rows = [dict(row) for row in reader]
    return fieldnames, rows


def _read_column_values(path: Path, column: str) -> set[str]:
    """Return the set of values present in *column* of the CSV at *path*."""
    values: set[str] = set()
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            val = row.get(column)
            if val:
                values.add(val)
    return values


# ---------------------------------------------------------------------------
# Validation report
# ---------------------------------------------------------------------------


class FKValidationReport:
    """Tracks FK violations discovered during pre-import validation."""

    def __init__(self) -> None:
        self._violations: list[dict[str, Any]] = []

    def add(
        self,
        dataset: str,
        table: str,
        column: str,
        value: str,
        count: int,
    ) -> None:
        self._violations.append(
            {
                "dataset": dataset,
                "table": table,
                "column": column,
                "value": value,
                "count": count,
            }
        )

    @property
    def total_violations(self) -> int:
        return len(self._violations)

    @property
    def has_violations(self) -> bool:
        return self.total_violations > 0

    def log_warnings(self) -> None:
        for v in self._violations:
            logger.warning(
                "FK violation: %s (%s.%s) value=%r appears in %d row(s) "
                "but has no matching PK in the target dimension table",
                v["dataset"],
                v["table"],
                v["column"],
                v["value"],
                v["count"],
            )


# ---------------------------------------------------------------------------
# Builder
# ---------------------------------------------------------------------------


class DatabaseBuilder:
    """Builds the SQLite database from cleaned CSV files.

    The builder is deterministic and idempotent: rerunning ``build()``
    repeatedly produces the same result.
    """

    def __init__(
        self,
        db_path: str | Path = _DEFAULT_DB_PATH,
        cleaned_dir: str | Path = _DEFAULT_CLEANED_DIR,
    ) -> None:
        self._db_path = Path(db_path)
        self._cleaned_dir = Path(cleaned_dir)
        self._fk_report: FKValidationReport | None = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def build(self) -> Path:
        """Execute the full database build pipeline.

        Returns the path to the created database file.
        """
        logger.info("Database build started; target: %s", self._db_path)

        self._ensure_dirs()
        conn = self._connect()

        try:
            self._validate_datasets()
            self._validate_fk_integrity()
            self._fk_report.log_warnings()

            self._drop_tables(conn)
            self._create_tables(conn)
            self._import_all(conn)
            self._create_indexes(conn)
            self._enable_fk_enforcement(conn)
            self._log_summary(conn)
        except Exception:
            logger.exception("Database build failed")
            raise
        finally:
            conn.close()

        logger.info("Database build finished: %s", self._db_path)
        return self._db_path

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _ensure_dirs(self) -> None:
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        logger.info("Database directory ensured: %s", self._db_path.parent)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self._db_path))
        conn.execute("PRAGMA journal_mode = WAL")
        logger.info("Connected to database: %s", self._db_path)
        return conn

    def _validate_datasets(self) -> None:
        missing: list[str] = []
        for csv_name in CSV_TO_TABLE:
            csv_path = self._cleaned_dir / csv_name
            if not csv_path.is_file():
                missing.append(csv_name)
        if missing:
            raise DatabaseBuildError(
                f"Cleaned dataset(s) not found: {', '.join(missing)}"
            )
        logger.info("All %d cleaned datasets present", len(CSV_TO_TABLE))

    def _validate_fk_integrity(self) -> None:
        report = FKValidationReport()

        pk_cache: dict[str, set[str]] = {}
        for csv_name, table in CSV_TO_TABLE.items():
            if table not in PK_COLUMNS:
                continue
            pk_column = PK_COLUMNS[table]
            pk_cache[table] = _read_column_values(
                self._cleaned_dir / csv_name, pk_column
            )

        for source_table, fk_col, target_table, pk_col in FK_RELATIONSHIPS:
            source_csv = self._csv_name_for_table(source_table)
            if source_csv is None:
                continue
            source_path = self._cleaned_dir / source_csv
            if not source_path.is_file():
                continue

            target_pks = pk_cache.get(target_table, set())
            counter: Counter[str] = Counter()
            with open(source_path, newline="", encoding="utf-8") as f:
                for row in csv.DictReader(f):
                    val = row.get(fk_col)
                    if val and val not in target_pks:
                        counter[val] += 1

            for value, count in counter.items():
                report.add(source_csv, source_table, fk_col, value, count)

        self._fk_report = report

        if report.has_violations:
            logger.warning(
                "FK validation complete: %d violation(s) found across %d relationship(s)",
                report.total_violations,
                len(FK_RELATIONSHIPS),
            )
        else:
            logger.info("FK validation passed: no violations detected")

    def _csv_name_for_table(self, table: str) -> str | None:
        for csv_name, tbl in CSV_TO_TABLE.items():
            if tbl == table:
                return csv_name
        return None

    def _drop_tables(self, conn: sqlite3.Connection) -> None:
        conn.execute("PRAGMA foreign_keys = OFF")
        for table in reversed(TABLE_NAMES):
            conn.execute(f"DROP TABLE IF EXISTS {table}")
            logger.info("Table dropped (if existed): %s", table)
        conn.commit()

    def _create_tables(self, conn: sqlite3.Connection) -> None:
        for table in TABLE_NAMES:
            ddl = CREATE_TABLE_DDL[table]
            conn.execute(ddl)
            logger.info("Table created (if not exists): %s", table)
        conn.commit()

    def _create_indexes(self, conn: sqlite3.Connection) -> None:
        count = 0
        for table, stmts in CREATE_INDEXES.items():
            for stmt in stmts:
                conn.execute(stmt)
                count += 1
        conn.commit()
        logger.info("Indexes created: %d", count)

    def _enable_fk_enforcement(self, conn: sqlite3.Connection) -> None:
        conn.execute("PRAGMA foreign_keys = ON")
        logger.info("Foreign key enforcement enabled")

    def _import_all(self, conn: sqlite3.Connection) -> None:
        conn.execute("PRAGMA foreign_keys = OFF")
        for csv_name in IMPORT_ORDER:
            self._import_one(conn, csv_name)
        conn.commit()
        logger.info("All datasets imported successfully")

    def _import_one(self, conn: sqlite3.Connection, csv_name: str) -> None:
        csv_path = self._cleaned_dir / csv_name
        table = CSV_TO_TABLE[csv_name]
        expected_rows = _csv_row_count(csv_path)

        if expected_rows == 0:
            raise DatabaseBuildError(
                f"Dataset {csv_name} is empty (no data rows)"
            )

        fieldnames, rows = _read_csv_rows(csv_path)
        placeholders = ", ".join("?" for _ in fieldnames)
        columns = ", ".join(fieldnames)
        sql = f"INSERT INTO {table} ({columns}) VALUES ({placeholders})"

        conn.executemany(sql, (tuple(r[c] for c in fieldnames) for r in rows))
        conn.commit()

        self._validate_row_count(conn, table, csv_name, expected_rows)
        logger.info(
            "Imported %s -> %s (%d rows)",
            csv_name,
            table,
            expected_rows,
        )

    def _validate_row_count(
        self,
        conn: sqlite3.Connection,
        table: str,
        csv_name: str,
        expected: int,
    ) -> None:
        (actual,) = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
        if actual != expected:
            raise DatabaseBuildError(
                f"Row count mismatch for {csv_name} (table {table}): "
                f"expected {expected}, got {actual}"
            )

    def _log_summary(self, conn: sqlite3.Connection) -> None:
        for table in TABLE_NAMES:
            (count,) = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
            logger.info("  %s: %d rows", table, count)

        if self._fk_report and self._fk_report.has_violations:
            logger.warning(
                "Database built with %d FK violation(s) — see warnings above",
                self._fk_report.total_violations,
            )