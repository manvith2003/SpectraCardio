-- analytics.sql — warehouse-grade analytical queries
-- ---------------------------------------------------------------------------
-- Each report is delimited by a "-- name: <id>" marker so build_warehouse.py
-- can run them and export results. They lean on window functions, conditional-
-- aggregation pivots, and grouping-set-style rollups against the star schema.
-- ---------------------------------------------------------------------------

-- name: cumulative_gains
-- Gains/lift table: bucket patients into deciles by V1 high-frequency relative
-- power (low = more Brugada-like) and track the cumulative share of all true
-- cases captured as you descend the risk-ranked list.
WITH ranked AS (
    SELECT f.patient_id, p.brugada,
           NTILE(10) OVER (ORDER BY f.rel_power ASC) AS decile
    FROM fact_band_power f
    JOIN dim_patient p ON p.patient_id = f.patient_id
    WHERE f.lead = 'V1' AND f.band = 'hf_15_40'
),
agg AS (
    SELECT decile, COUNT(*) AS n_patients, SUM(brugada) AS brugada_cases,
           ROUND(100.0 * SUM(brugada) / COUNT(*), 1) AS brugada_rate_pct
    FROM ranked GROUP BY decile
),
tot AS (SELECT SUM(brugada_cases) AS total_pos FROM agg)
SELECT a.decile, a.n_patients, a.brugada_cases, a.brugada_rate_pct,
       SUM(a.brugada_cases) OVER (ORDER BY a.decile) AS cum_caught,
       ROUND(100.0 * SUM(a.brugada_cases) OVER (ORDER BY a.decile) / t.total_pos, 1)
           AS cum_pct_of_all_cases
FROM agg a CROSS JOIN tot t
ORDER BY a.decile;

-- name: marginal_tradeoff
-- Threshold sweep with LAG: how many *extra* false alarms each step costs for
-- the *extra* cases it catches — the marginal economics of lowering the bar.
SELECT threshold, recall, caught, false_alarm,
       caught      - LAG(caught)      OVER (ORDER BY threshold) AS d_caught,
       false_alarm - LAG(false_alarm) OVER (ORDER BY threshold) AS d_false_alarm
FROM fact_threshold_curve
ORDER BY threshold;

-- name: v1_band_pivot
-- Conditional-aggregation PIVOT: mean V1 relative power per band, Brugada vs
-- Healthy, as columns.
SELECT d.group_label,
       ROUND(AVG(CASE WHEN f.band = 'lf_0p5_5' THEN f.rel_power END), 4) AS lf_0p5_5,
       ROUND(AVG(CASE WHEN f.band = 'mf_5_15'  THEN f.rel_power END), 4) AS mf_5_15,
       ROUND(AVG(CASE WHEN f.band = 'hf_15_40' THEN f.rel_power END), 4) AS hf_15_40
FROM fact_band_power f
JOIN dim_patient d ON d.patient_id = f.patient_id
WHERE f.lead = 'V1'
GROUP BY d.group_label;

-- name: risk_percentiles
-- Within-group percentile placement of each patient's risk score
-- (PERCENT_RANK + CUME_DIST) — the highest-risk patients per group.
WITH r AS (
    SELECT patient_id, group_label, ROUND(risk_score, 3) AS risk_score,
           ROUND(PERCENT_RANK() OVER (PARTITION BY group_label ORDER BY risk_score), 3) AS pct_rank,
           ROUND(CUME_DIST()    OVER (PARTITION BY group_label ORDER BY risk_score), 3) AS cume_dist
    FROM dim_patient
)
SELECT * FROM r ORDER BY risk_score DESC LIMIT 12;

-- name: group_rollup
-- Grouping-set-style rollup: overall totals plus per-group breakdown in one
-- result (emulated with UNION ALL, the portable form of ROLLUP).
SELECT 'ALL' AS segment, COUNT(*) AS n_patients,
       ROUND(100.0 * SUM(brugada) / COUNT(*), 1) AS brugada_rate_pct,
       ROUND(AVG(risk_score), 3) AS avg_risk_score
FROM dim_patient
UNION ALL
SELECT group_label, COUNT(*),
       ROUND(100.0 * SUM(brugada) / COUNT(*), 1),
       ROUND(AVG(risk_score), 3)
FROM dim_patient
GROUP BY group_label
ORDER BY segment;
