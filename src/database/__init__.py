"""Relational database layer for the retail sales analytics project.

Provides table schemas, index definitions, and an idempotent builder
that imports every cleaned CSV from ``data/cleaned/`` into a normalised
SQLite database at ``data/database/suryaa.db``.
"""

from src.database.builder import DatabaseBuilder

__all__ = ["DatabaseBuilder"]