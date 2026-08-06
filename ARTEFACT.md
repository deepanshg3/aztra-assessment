# Reconciliation Report

## Objective

Produce a single, consistent, queryable dataset from eight raw CSV files (four dimensions, two facts, two enriched tables) provided for the Suryaa Consumer Products FMCG sales investigation. The reconciled dataset feeds an AI assistant that answers WHAT, WHY, and WHAT_TO_DO questions over structured sales data.

## Reconciliation Methodology

All eight datasets were processed through a deterministic, idempotent cleaning pipeline. Each raw CSV was read, field-level standardisation was applied per column type, exact duplicate rows were removed, and the cleaned output was written to a separate directory. Dimension tables were cleaned first so that foreign-key references were available when cleaning fact tables. Referential integrity warnings were logged but invalid references were preserved as-is in the data (not dropped).

The pipeline is deterministic and idempotent; repeated execution on identical input produces identical cleaned datasets.

## Data Quality Observations

- Column names were inconsistent across datasets. `material_no`, `item_code`, and `sku` were aliases for `sku_code`. `area` was an alias for `territory`. These were normalised to canonical names via a rename mapping.
- Date formats varied: `%Y-%m-%d`, `%d-%m-%Y`, `%m/%d/%y`, and `%d %b %Y` were all present. All dates were standardised to ISO `YYYY-MM-DD`.
- - Monetary values (`primary_sales_value` and `target_value`) are stored as `REAL` values in the SQLite database. Currency prefixes and thousands separators are removed from `primary_sales_value` during preprocessing before import.
- Region values used single-letter abbreviations (`S` → `South`, `E` → `East`). These were expanded.
- Tier values used mixed casing and abbreviations (`VAL`, `Value`, `PREM`, `Premium`, `Mainstream`). These were normalised to lowercase canonical forms (`value`, `premium`, `mainstream`).

## Assumptions

- Missing-value sentinel values (`""`, `NA`, `N/A`, `#N/A`) were detected for auditing purposes. Rows containing these values were preserved without modification, and no imputation was performed.
- Distributor IDs with a leading zero (e.g., `0DIST01`) were repaired when dropping the zero produced a valid ID present in the `dim_distributor` table. If the repaired ID was not valid, the original value was preserved.
- No statistical imputation or interpolation was applied to any missing numeric field.
- Territory aliases (`Bombay` → `Mumbai`, `BLR`/`BGL`/`BLG`/`BEN` → `Bengaluru`) were resolved to canonical names.

## Handling of Duplicate Records

Exact duplicate rows (all columns identical) were identified within each dataset independently. The first occurrence was retained; all subsequent duplicates were discarded. Duplicate detection was performed on the cleaned data. Cross-dataset duplication was not evaluated.

## Handling of Missing Values

Missing values were detected using a sentinel set (`""`, `"NA"`, `"N/A"`, `"#N/A"`). Rows containing missing values were preserved in the output without modification. No rows were dropped due to missing data. Missing count was logged per dataset for audit purposes.

## Handling of Unit Consistency

- Monetary values (`primary_sales_value` and `target_value`) are consistently stored in INR (Indian Rupees). Currency strings and thousands separators were removed from `primary_sales_value`, which was stored as a numeric string.
- All months are stored as `YYYY-MM` in the `fact_targets` table.
- The `base_mrp` in `dim_sku` is in INR.
- The `promo_discount_pct` in `promotions` is an integer percentage.
- The `stockout_days` in `stockouts` is an integer count of days.
- No unit conversions were required or applied.

## Treatment of Excluded Records

No records were excluded from any dataset. The pipeline is designed to preserve all input rows regardless of quality. Referential integrity violations were logged as warnings but no rows were removed.

## Treatment of PII

The `dim_rep` table contains `rep_name` (sales officer names), which is considered business contact information rather than sensitive PII under the assessment context. No anonymisation, redaction, or masking was applied. The `dim_distributor` table contains `distributor_name` (business entity names), which is not considered PII.

No personal customer data, financial identifiers, or sensitive personal information was present in any dataset.

## Final Reconciliation Summary

| Dataset            | Rows Read | Rows Written | Duplicates Removed | Values Standardised | 
| ------------------ | --------: | -----------: | -----------------: | ------------------: | 
| dim_sku            |       134 |          134 |                  0 |                 Yes |        
| dim_geo            |        12 |           12 |                  0 |                 Yes |      
| dim_rep            |        12 |           12 |                  0 |                 Yes |         
| dim_distributor    |        24 |           24 |                  0 |                 Yes |         
| fact_primary_sales |    61,932 |       61,932 |                  0 |                 Yes |          
| fact_targets       |    14,292 |       14,292 |                  0 |                 Yes |           
| stockouts          |         2 |            2 |                  0 |                 Yes |          
| promotions         |         2 |            2 |                  0 |                 Yes |        


All eight cleaned datasets were loaded into an SQLite database with foreign key constraints, indexes on all join columns, and post-load row count verification. The database supports the AI assistant's SQL query pipeline.
