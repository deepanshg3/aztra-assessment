"""SQL executor that runs validated queries against the project database.

Connects to the SQLite database, validates the SQL, executes it, and
returns results as a list of dictionaries preserving column names.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any, Final

from src.core.logger import get_logger
from src.sql.validator import validate

logger = get_logger(__name__)

_DB_PATH: Final[Path] = (
    Path(__file__).resolve().parent.parent.parent
    / "data"
    / "database"
    / "suryaa.db"
)


def _connect() -> sqlite3.Connection:
    """Open a connection to the project SQLite database.

    Returns:
        An :class:`sqlite3.Connection` with ``Row`` factory set.

    Raises:
        RuntimeError: If the database file does not exist or cannot be opened.
    """
    if not _DB_PATH.is_file():
        raise RuntimeError(f"Database file not found: {_DB_PATH}")

    try:
        connection = sqlite3.connect(str(_DB_PATH))
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        return connection
    except sqlite3.Error as exc:
        raise RuntimeError(
            f"Failed to connect to database at {_DB_PATH}: {exc}"
        ) from exc


def execute(sql: str) -> list[dict[str, object]]:
    """Validate and execute a SQL query, returning all results.

    Args:
        sql: The SQL query string to execute.

    Returns:
        A list of dictionaries, each representing one row with column names
        as keys.

    Raises:
        ValueError: If the SQL fails validation.
        RuntimeError: If the database cannot be opened or the query fails.
    """
    safe_sql = validate(sql)

    logger.info("SQL execution started", extra={"sql_len": len(safe_sql)})

    conn = _connect()
    try:
        cursor = conn.execute(safe_sql)
        rows = [dict(row) for row in cursor.fetchall()]
        logger.info(
            "SQL execution completed",
            extra={"rows_returned": len(rows)},
        )
        return rows
    except sqlite3.Error as exc:
        logger.exception("SQL execution failed")
        raise RuntimeError(f"SQL execution failed: {exc}") from exc
    finally:
        conn.close()