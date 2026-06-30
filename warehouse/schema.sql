-- schema.sql — SpectraCardio analytical data warehouse (star schema)
-- ---------------------------------------------------------------------------
-- Dimensional model: a central grain of "one ECG band-power measurement per
-- patient / lead / frequency band" (fact_band_power), surrounded by conformed
-- dimensions. A second fact captures lead-level spectral summaries, and a small
-- helper fact stores the model's threshold sweep.
--
-- Grain
--   fact_band_power     : patient x lead x band            (356 x 3 x 3 = 3,204)
--   fact_lead_spectral  : patient x lead                   (356 x 3 = 1,068)
--   fact_threshold_curve: one row per screening threshold  (17)
--
-- Dimensions are conformed (shared keys) so facts join cleanly. dim_patient is
-- a Type-1 SCD here (we overwrite; no history is tracked for this static cohort).
-- ---------------------------------------------------------------------------

PRAGMA foreign_keys = ON;

DROP VIEW  IF EXISTS vw_lead_band_group;
DROP VIEW  IF EXISTS vw_patient_v1;
DROP TABLE IF EXISTS fact_band_power;
DROP TABLE IF EXISTS fact_lead_spectral;
DROP TABLE IF EXISTS fact_threshold_curve;
DROP TABLE IF EXISTS dim_patient;
DROP TABLE IF EXISTS dim_lead;
DROP TABLE IF EXISTS dim_band;

-- ---- DIMENSIONS -----------------------------------------------------------
CREATE TABLE dim_patient (
    patient_id    INTEGER PRIMARY KEY,
    group_label   TEXT    NOT NULL,          -- 'Brugada' | 'Healthy'
    brugada       INTEGER NOT NULL CHECK (brugada IN (0,1)),
    sudden_death  INTEGER NOT NULL CHECK (sudden_death IN (0,1)),
    scd_label     TEXT,
    basal_pattern INTEGER,
    basal_label   TEXT,
    risk_score    REAL,                       -- out-of-fold model score
    flagged       INTEGER
);

CREATE TABLE dim_lead (
    lead       TEXT PRIMARY KEY,              -- 'V1' | 'V2' | 'V3'
    region     TEXT,
    lead_order INTEGER
);

CREATE TABLE dim_band (
    band         TEXT PRIMARY KEY,            -- 'lf_0p5_5' | 'mf_5_15' | 'hf_15_40'
    band_label   TEXT,
    freq_low_hz  REAL,
    freq_high_hz REAL,
    description  TEXT
);

-- ---- FACTS ----------------------------------------------------------------
CREATE TABLE fact_band_power (
    patient_id INTEGER NOT NULL REFERENCES dim_patient(patient_id),
    lead       TEXT    NOT NULL REFERENCES dim_lead(lead),
    band       TEXT    NOT NULL REFERENCES dim_band(band),
    abs_power  REAL,
    rel_power  REAL,
    PRIMARY KEY (patient_id, lead, band)
);

CREATE TABLE fact_lead_spectral (
    patient_id   INTEGER NOT NULL REFERENCES dim_patient(patient_id),
    lead         TEXT    NOT NULL REFERENCES dim_lead(lead),
    dom_freq     REAL,
    centroid     REAL,
    spec_entropy REAL,
    edge95       REAL,
    rms          REAL,
    ptp          REAL,
    n_peaks      INTEGER,
    PRIMARY KEY (patient_id, lead)
);

CREATE TABLE fact_threshold_curve (
    threshold   REAL PRIMARY KEY,
    recall      REAL,
    caught      INTEGER,
    missed      INTEGER,
    false_alarm INTEGER,
    precision   REAL
);

-- ---- ANALYTICAL VIEWS (semantic layer) ------------------------------------
-- Average relative power per lead/band/group — the spectral-signature view.
CREATE VIEW vw_lead_band_group AS
SELECT l.lead, b.band, b.band_label, p.group_label,
       ROUND(AVG(f.rel_power), 4) AS avg_rel_power,
       COUNT(*)                   AS n_patients
FROM fact_band_power f
JOIN dim_lead    l ON l.lead = f.lead
JOIN dim_band    b ON b.band = f.band
JOIN dim_patient p ON p.patient_id = f.patient_id
GROUP BY l.lead, b.band, p.group_label;

-- One tidy row per patient with the key V1 discriminators (analyst convenience).
CREATE VIEW vw_patient_v1 AS
SELECT d.patient_id, d.group_label, d.brugada, d.risk_score, d.flagged,
       MAX(CASE WHEN f.band = 'hf_15_40' THEN f.rel_power END) AS v1_hf_relpower,
       s.spec_entropy AS v1_spec_entropy
FROM dim_patient d
JOIN fact_band_power   f ON f.patient_id = d.patient_id AND f.lead = 'V1'
JOIN fact_lead_spectral s ON s.patient_id = d.patient_id AND s.lead = 'V1'
GROUP BY d.patient_id;
