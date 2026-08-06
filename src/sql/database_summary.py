DATABASE_SUMMARY = """
Retail Sales Analytics Database

========================
TABLES
========================

dim_sku
Stores master information about every product sold.
PK: sku_code
Columns:
- sku_code
- category
- brand
- sku_name
- pack_size
- flavour
- tier
- base_mrp

dim_geo
Stores the geographical hierarchy used across the business.
PK: territory
Columns:
- territory
- region

dim_rep
Stores sales representatives and the territory they manage.
PK: rep_id
FK: territory -> dim_geo.territory
Columns:
- rep_id
- rep_name
- territory

dim_distributor
Stores distributor information and the territory they operate in.
PK: distributor_id
FK: territory -> dim_geo.territory
Columns:
- distributor_id
- distributor_name
- territory

fact_primary_sales
Stores weekly sales transactions for every SKU sold through a distributor in a territory.
PK: (week_start, sku_code, territory, distributor_id)
FK:
- sku_code -> dim_sku
- territory -> dim_geo
- distributor_id -> dim_distributor
Columns:
- week_start
- sku_code
- territory
- distributor_id
- primary_sales_units
- primary_sales_value

fact_targets
Stores monthly sales targets for each SKU in every territory.
PK: (month, sku_code, territory)
FK:
- sku_code -> dim_sku
- territory -> dim_geo
Columns:
- month
- sku_code
- territory
- target_value

promotions
Stores promotional campaigns active for a SKU during a specific week.
PK: (week_start, sku_code, territory)
FK:
- sku_code -> dim_sku
- territory -> dim_geo
Columns:
- week_start
- sku_code
- territory
- promo_type
- promo_discount_pct

stockouts
Stores stock availability events and the duration of stock shortages.
PK: (week_start, sku_code, territory)
FK:
- sku_code -> dim_sku
- territory -> dim_geo
Columns:
- week_start
- sku_code
- territory
- stockout_flag
- stockout_days

========================
RELATIONSHIPS
========================

Product information
All fact tables join dim_sku using sku_code.

Geography
All fact tables, dim_rep and dim_distributor join dim_geo using territory.

Distributor
fact_primary_sales joins dim_distributor using distributor_id.

========================
BUSINESS NOTES
========================

- primary_sales_units is the quantity of products sold.
- primary_sales_value is the monetary value of those sales.
- target_value represents the planned sales target.
- stockout_flag = 1 indicates a stockout occurred during that week.
- stockout_days is the number of days the SKU remained out of stock.
- promo_discount_pct is the discount percentage offered during a promotion.
- week_start represents weekly data.
- month is stored in YYYY-MM format.

========================
SQL RULES
========================

- Generate exactly one SQLite SELECT query.
- Never generate INSERT, UPDATE, DELETE, DROP, ALTER, CREATE or PRAGMA statements.
- Use JOINs whenever information spans multiple tables.
- Use explicit column names instead of SELECT *.
- Aggregate only when required.
- Return only raw SQL.
"""
