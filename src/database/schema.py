"""Table and index DDL for the retail sales SQLite database."""

from __future__ import annotations

from collections.abc import Sequence

# ---------------------------------------------------------------------------
# Table DDL
# ---------------------------------------------------------------------------

CREATE_TABLE_DIM_SKU = """\
CREATE TABLE IF NOT EXISTS dim_sku (
    sku_code    TEXT PRIMARY KEY,
    category    TEXT NOT NULL,
    brand       TEXT NOT NULL,
    sku_name    TEXT NOT NULL,
    pack_size   TEXT NOT NULL,
    flavour     TEXT NOT NULL,
    tier        TEXT NOT NULL,
    base_mrp    REAL NOT NULL
)
"""

CREATE_TABLE_DIM_GEO = """\
CREATE TABLE IF NOT EXISTS dim_geo (
    territory   TEXT PRIMARY KEY,
    region      TEXT NOT NULL
)
"""

CREATE_TABLE_DIM_REP = """\
CREATE TABLE IF NOT EXISTS dim_rep (
    rep_id      TEXT PRIMARY KEY,
    rep_name    TEXT NOT NULL,
    territory   TEXT NOT NULL REFERENCES dim_geo(territory)
)
"""

CREATE_TABLE_DIM_DISTRIBUTOR = """\
CREATE TABLE IF NOT EXISTS dim_distributor (
    distributor_id   TEXT PRIMARY KEY,
    distributor_name TEXT NOT NULL,
    territory        TEXT NOT NULL REFERENCES dim_geo(territory)
)
"""

CREATE_TABLE_FACT_PRIMARY_SALES = """\
CREATE TABLE IF NOT EXISTS fact_primary_sales (
    week_start          TEXT    NOT NULL,
    sku_code            TEXT    NOT NULL REFERENCES dim_sku(sku_code),
    territory           TEXT    NOT NULL REFERENCES dim_geo(territory),
    distributor_id      TEXT    NOT NULL REFERENCES dim_distributor(distributor_id),
    primary_sales_units INTEGER NOT NULL,
    primary_sales_value REAL    NOT NULL,
    PRIMARY KEY (week_start, sku_code, territory, distributor_id)
)
"""

CREATE_TABLE_FACT_TARGETS = """\
CREATE TABLE IF NOT EXISTS fact_targets (
    month        TEXT  NOT NULL,
    sku_code     TEXT  NOT NULL REFERENCES dim_sku(sku_code),
    territory    TEXT  NOT NULL REFERENCES dim_geo(territory),
    target_value REAL  NOT NULL,
    PRIMARY KEY (month, sku_code, territory)
)
"""

CREATE_TABLE_STOCKOUTS = """\
CREATE TABLE IF NOT EXISTS stockouts (
    week_start    TEXT    NOT NULL,
    sku_code      TEXT    NOT NULL REFERENCES dim_sku(sku_code),
    territory     TEXT    NOT NULL REFERENCES dim_geo(territory),
    stockout_flag INTEGER NOT NULL,
    stockout_days INTEGER NOT NULL,
    PRIMARY KEY (week_start, sku_code, territory)
)
"""

CREATE_TABLE_PROMOTIONS = """\
CREATE TABLE IF NOT EXISTS promotions (
    week_start       TEXT NOT NULL,
    sku_code         TEXT NOT NULL REFERENCES dim_sku(sku_code),
    territory        TEXT NOT NULL REFERENCES dim_geo(territory),
    promo_type       TEXT NOT NULL,
    promo_discount_pct INTEGER NOT NULL,
    PRIMARY KEY (week_start, sku_code, territory)
)
"""

# ---------------------------------------------------------------------------
# Index DDL
# ---------------------------------------------------------------------------

CREATE_INDEXES: dict[str, Sequence[str]] = {
    "dim_sku": (
        "CREATE INDEX IF NOT EXISTS idx_dim_sku_category ON dim_sku(category)",
        "CREATE INDEX IF NOT EXISTS idx_dim_sku_brand    ON dim_sku(brand)",
    ),
    "dim_geo": (
        "CREATE INDEX IF NOT EXISTS idx_dim_geo_region ON dim_geo(region)",
    ),
    "dim_rep": (
        "CREATE INDEX IF NOT EXISTS idx_dim_rep_territory ON dim_rep(territory)",
    ),
    "dim_distributor": (
        "CREATE INDEX IF NOT EXISTS idx_dim_distributor_territory ON dim_distributor(territory)",
    ),
    "fact_primary_sales": (
        "CREATE INDEX IF NOT EXISTS idx_fps_sku_code       ON fact_primary_sales(sku_code)",
        "CREATE INDEX IF NOT EXISTS idx_fps_territory      ON fact_primary_sales(territory)",
        "CREATE INDEX IF NOT EXISTS idx_fps_week_start     ON fact_primary_sales(week_start)",
        "CREATE INDEX IF NOT EXISTS idx_fps_distributor_id ON fact_primary_sales(distributor_id)",
    ),
    "fact_targets": (
        "CREATE INDEX IF NOT EXISTS idx_ft_sku_code   ON fact_targets(sku_code)",
        "CREATE INDEX IF NOT EXISTS idx_ft_territory  ON fact_targets(territory)",
        "CREATE INDEX IF NOT EXISTS idx_ft_month      ON fact_targets(month)",
    ),
    "stockouts": (
        "CREATE INDEX IF NOT EXISTS idx_stockouts_sku_code   ON stockouts(sku_code)",
        "CREATE INDEX IF NOT EXISTS idx_stockouts_territory  ON stockouts(territory)",
        "CREATE INDEX IF NOT EXISTS idx_stockouts_week_start ON stockouts(week_start)",
    ),
    "promotions": (
        "CREATE INDEX IF NOT EXISTS idx_promotions_sku_code   ON promotions(sku_code)",
        "CREATE INDEX IF NOT EXISTS idx_promotions_territory  ON promotions(territory)",
        "CREATE INDEX IF NOT EXISTS idx_promotions_week_start ON promotions(week_start)",
    ),
}

# ---------------------------------------------------------------------------
# Table metadata
# ---------------------------------------------------------------------------

TABLE_NAMES: tuple[str, ...] = (
    "dim_sku",
    "dim_geo",
    "dim_rep",
    "dim_distributor",
    "fact_primary_sales",
    "fact_targets",
    "stockouts",
    "promotions",
)

CSV_TO_TABLE: dict[str, str] = {
    "dim_sku.csv": "dim_sku",
    "dim_geo.csv": "dim_geo",
    "dim_rep.csv": "dim_rep",
    "dim_distributor.csv": "dim_distributor",
    "fact_primary_sales.csv": "fact_primary_sales",
    "fact_targets.csv": "fact_targets",
    "stockouts.csv": "stockouts",
    "promotions.csv": "promotions",
}

CREATE_TABLE_DDL: dict[str, str] = {
    "dim_sku": CREATE_TABLE_DIM_SKU,
    "dim_geo": CREATE_TABLE_DIM_GEO,
    "dim_rep": CREATE_TABLE_DIM_REP,
    "dim_distributor": CREATE_TABLE_DIM_DISTRIBUTOR,
    "fact_primary_sales": CREATE_TABLE_FACT_PRIMARY_SALES,
    "fact_targets": CREATE_TABLE_FACT_TARGETS,
    "stockouts": CREATE_TABLE_STOCKOUTS,
    "promotions": CREATE_TABLE_PROMOTIONS,
}

# FK relationships for pre-import validation: (fact_or_enriched_table, fk_column, dimension_table, pk_column)
FK_RELATIONSHIPS: tuple[tuple[str, str, str, str], ...] = (
    ("dim_rep", "territory", "dim_geo", "territory"),
    ("dim_distributor", "territory", "dim_geo", "territory"),
    ("fact_primary_sales", "sku_code", "dim_sku", "sku_code"),
    ("fact_primary_sales", "territory", "dim_geo", "territory"),
    ("fact_primary_sales", "distributor_id", "dim_distributor", "distributor_id"),
    ("fact_targets", "sku_code", "dim_sku", "sku_code"),
    ("fact_targets", "territory", "dim_geo", "territory"),
    ("stockouts", "sku_code", "dim_sku", "sku_code"),
    ("stockouts", "territory", "dim_geo", "territory"),
    ("promotions", "sku_code", "dim_sku", "sku_code"),
    ("promotions", "territory", "dim_geo", "territory"),
)

# Primary-key columns for dimension tables (used in FK validation cache)
PK_COLUMNS: dict[str, str] = {
    "dim_sku": "sku_code",
    "dim_geo": "territory",
    "dim_distributor": "distributor_id",
    "dim_rep": "rep_id",
}

# Load order: dimensions first, then facts
IMPORT_ORDER: tuple[str, ...] = (
    "dim_geo.csv",
    "dim_sku.csv",
    "dim_distributor.csv",
    "dim_rep.csv",
    "fact_primary_sales.csv",
    "fact_targets.csv",
    "stockouts.csv",
    "promotions.csv",
)