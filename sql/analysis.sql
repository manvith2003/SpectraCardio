-- analysis.sql
-- ----------------------------------------------------------------------------
-- Advanced cohort-analysis queries for the SpectraCardio Brugada screen.
-- These run on the `ecg_features` table (one row per patient, 42 spectral +
-- morphology features, plus brugada / sudden_death / basal_pattern labels)
-- built by src/build_db.py and re-loaded by src/deep_analysis.py.
--
-- The queries use CTEs, window functions (NTILE, RANK, PERCENT_RANK), and
-- conditional aggregation -- the SQL a data analyst writes to understand a
-- cohort and quantify how well a single feature separates two groups.
-- ----------------------------------------------------------------------------


-- Q1. RISK-DECILE LIFT TABLE
-- Split the cohort into 10 equal buckets by V1 high-frequency relative power
-- (low HF power = more Brugada-like). Then measure the actual Brugada rate in
-- each decile. A working signal should show Brugada cases concentrated in the
-- low-power deciles -- this is a classic "lift / gains" analysis.
WITH ranked AS (
    SELECT patient_id, brugada, V1_bpr_hf_15_40,
           NTILE(10) OVER (ORDER BY V1_bpr_hf_15_40 ASC) AS hf_decile
    FROM ecg_features
)
SELECT
    hf_decile,
    COUNT(*)                                   AS n_patients,
    ROUND(MIN(V1_bpr_hf_15_40), 4)             AS min_hf_relpower,
    ROUND(MAX(V1_bpr_hf_15_40), 4)             AS max_hf_relpower,
    SUM(brugada)                               AS brugada_cases,
    ROUND(100.0 * SUM(brugada) / COUNT(*), 1)  AS brugada_rate_pct
FROM ranked
GROUP BY hf_decile
ORDER BY hf_decile;


-- Q2. PER-LEAD SEPARATION
-- For each precordial lead, contrast the mean HF relative power of Brugada vs
-- healthy and express the gap as a percentage reduction. Shows V1 carries the
-- strongest separation -- which is exactly where the Brugada pattern lives.
WITH g AS (
    SELECT
        AVG(CASE WHEN brugada=1 THEN V1_bpr_hf_15_40 END) AS v1_brug,
        AVG(CASE WHEN brugada=0 THEN V1_bpr_hf_15_40 END) AS v1_healthy,
        AVG(CASE WHEN brugada=1 THEN V2_bpr_hf_15_40 END) AS v2_brug,
        AVG(CASE WHEN brugada=0 THEN V2_bpr_hf_15_40 END) AS v2_healthy,
        AVG(CASE WHEN brugada=1 THEN V3_bpr_hf_15_40 END) AS v3_brug,
        AVG(CASE WHEN brugada=0 THEN V3_bpr_hf_15_40 END) AS v3_healthy
    FROM ecg_features
)
SELECT 'V1' AS lead, ROUND(v1_brug,4) AS brugada_avg, ROUND(v1_healthy,4) AS healthy_avg,
       ROUND(100.0*(v1_healthy-v1_brug)/v1_healthy,1) AS pct_lower_in_brugada FROM g
UNION ALL
SELECT 'V2', ROUND(v2_brug,4), ROUND(v2_healthy,4),
       ROUND(100.0*(v2_healthy-v2_brug)/v2_healthy,1) FROM g
UNION ALL
SELECT 'V3', ROUND(v3_brug,4), ROUND(v3_healthy,4),
       ROUND(100.0*(v3_healthy-v3_brug)/v3_healthy,1) FROM g;


-- Q3. SUSPICION RANKING + "HEALTHY BUT HIGH-RISK" FLAGS
-- Rank every patient by suspicion (ascending HF power) with a window function,
-- and surface the healthy-labelled patients who nonetheless sit in the most
-- suspicious 10% -- the false-positive candidates a screen would surface, worth
-- a second look in a real workflow.
WITH scored AS (
    SELECT patient_id, brugada,
           V1_bpr_hf_15_40, V1_spec_entropy,
           PERCENT_RANK() OVER (ORDER BY V1_bpr_hf_15_40 ASC) AS suspicion_pctile
    FROM ecg_features
)
SELECT patient_id,
       ROUND(V1_bpr_hf_15_40,4) AS V1_hf_relpower,
       ROUND(V1_spec_entropy,3) AS V1_spec_entropy,
       ROUND(suspicion_pctile,3) AS suspicion_pctile
FROM scored
WHERE brugada = 0 AND suspicion_pctile <= 0.10
ORDER BY suspicion_pctile ASC;


-- Q4. SPECTRAL-ENTROPY QUARTILES vs BRUGADA RATE
-- Independent check on a second feature: does lower V1 spectral entropy also
-- track Brugada? Quartile the cohort by entropy and report the rate per bucket.
WITH q AS (
    SELECT brugada, V1_spec_entropy,
           NTILE(4) OVER (ORDER BY V1_spec_entropy ASC) AS entropy_quartile
    FROM ecg_features
)
SELECT entropy_quartile,
       COUNT(*)                                  AS n_patients,
       ROUND(AVG(V1_spec_entropy),3)             AS avg_entropy,
       SUM(brugada)                              AS brugada_cases,
       ROUND(100.0*SUM(brugada)/COUNT(*),1)      AS brugada_rate_pct
FROM q
GROUP BY entropy_quartile
ORDER BY entropy_quartile;


-- Q5. SUDDEN-CARDIAC-DEATH SUBGROUP PROFILE
-- Within confirmed Brugada patients, compare the spectral profile of those with
-- vs without a sudden-cardiac-death history -- an exploratory clinical slice.
SELECT
    CASE sudden_death WHEN 1 THEN 'SCD history' ELSE 'No SCD' END AS scd_group,
    COUNT(*)                          AS n,
    ROUND(AVG(V1_bpr_hf_15_40),4)     AS avg_V1_hf_relpower,
    ROUND(AVG(V1_spec_entropy),3)     AS avg_V1_spec_entropy,
    ROUND(AVG(V1_centroid),2)         AS avg_V1_centroid
FROM ecg_features
WHERE brugada = 1
GROUP BY sudden_death
ORDER BY sudden_death DESC;
