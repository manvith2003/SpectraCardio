# Data warehouse (`warehouse/`)

A dimensional **star-schema data warehouse** for the SpectraCardio cohort, with
DDL, an ETL loader, a semantic view layer, and warehouse-grade analytical SQL.

```
build_bi_exports.py ──► fact/dim CSVs (powerbi/) ──► build_warehouse.py ──► SQL warehouse
```

## Build & run

```bash
python src/build_bi_exports.py        # (once) generate the fact/dim CSVs
python warehouse/build_warehouse.py    # create schema, load, run analytics
```

This creates `warehouse/spectracardio.db` (SQLite) and writes each analytical
report to `outputs/wh_<report>.csv`. Query it directly:

```bash
sqlite3 warehouse/spectracardio.db "SELECT * FROM vw_lead_band_group;"
```

## Model (star schema)

```
        dim_lead            dim_band
            │                   │
            ▼                   ▼
   ┌────────────────────────────────────┐
   │  fact_band_power  (patient×lead×band)│──► dim_patient
   └────────────────────────────────────┘
   fact_lead_spectral (patient×lead)   ──► dim_patient
   fact_threshold_curve (per threshold)
```

| Object | Type | Grain / role |
|--------|------|--------------|
| `dim_patient` | dimension | one row per patient (Type-1 SCD) |
| `dim_lead`, `dim_band` | dimensions | conformed lookup dims |
| `fact_band_power` | fact | patient × lead × band power (3,204 rows) |
| `fact_lead_spectral` | fact | patient × lead spectral summary (1,068) |
| `fact_threshold_curve` | fact | model recall/false-alarm by threshold |
| `vw_lead_band_group` | view | avg power per lead/band/group (semantic layer) |
| `vw_patient_v1` | view | one tidy row per patient with V1 discriminators |

Foreign keys are enforced (`PRAGMA foreign_keys`), and the loader runs
`foreign_key_check` after load.

## Advanced SQL (`analytics.sql`)

| Report | Technique | Insight |
|--------|-----------|---------|
| `cumulative_gains` | `NTILE` + running `SUM() OVER` | top 2 deciles capture ~52% of all true cases |
| `marginal_tradeoff` | `LAG()` over the threshold sweep | extra false alarms paid per extra case caught |
| `v1_band_pivot` | conditional-aggregation PIVOT | V1 HF power 0.099 (Brugada) vs 0.183 (Healthy) |
| `risk_percentiles` | `PERCENT_RANK` + `CUME_DIST` partitioned by group | per-group risk placement |
| `group_rollup` | grouping-set-style `UNION ALL` rollup | overall + per-group summary in one result |

## Portability

The engine is SQLite (zero-install). The SQL is standard window-function SQL, so
it ports to **DuckDB**, **Postgres**, **BigQuery**, or **Snowflake** with minimal
change — point a different connection at the same `schema.sql` / `analytics.sql`.

> Research/educational demo on a public dataset — not a clinical system.
