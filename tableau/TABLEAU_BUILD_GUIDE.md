# Tableau Public build guide — SpectraCardio

**Tableau Public is free and runs on Mac and Windows**, and it publishes to a
shareable public web link — ideal for a portfolio you drop on a resume. This is
the recommended dashboard route if you're on a Mac (Power BI Desktop is
Windows-only).

## Files in this folder

| File | Use it for | Grain |
|------|-----------|-------|
| `tableau_features_long.csv` | The spectral charts (denormalized, one row per patient/lead/band) | 3,204 rows |
| `tableau_patients.csv` | Triage table + risk-score distribution | 356 rows |
| `tableau_threshold_curve.csv` | Recall vs false-alarm trade-off line | 17 rows |
| `tableau_forecast_timeline.csv` | Early-warning forecast timeline | 40 rows |

The long table is pre-joined, so Tableau needs no data modeling — just connect
and drag.

## Step 0 — Setup

Download Tableau Public (free) and create a free Tableau Public account (needed to
publish). Open it → Connect → Text file → pick `tableau_features_long.csv`.

## Step 1 — The spectral-signature chart (your headline viz)

1. New worksheet. Drag `Band Label` to Columns, `Rel Power` to Rows.
2. Change the `Rel Power` measure to **Average** (right-click the pill → Measure → Average).
3. Drag `Group Label` to Color → side-by-side bars (set Marks to Bar; use
   Analytics or the Columns shelf to cluster).
4. Drag `Lead` to Filters → show filter → select **V1**.
5. Title it "Average spectral power: Brugada vs Healthy (lead V1)". You'll see the
   high-frequency (HF) band is markedly lower for Brugada — the core finding.

## Step 2 — Risk-score distribution

1. New worksheet, connect/add `tableau_patients.csv` (Data → New Data Source).
2. Drag `Risk Score` to Columns → right-click → Create bins (size ~0.05).
3. Drag `Risk Score (bin)` to Columns, `Number of Records` (or CNT) to Rows.
4. `Group Label` to Color. Shows healthy clustered near 0, Brugada spread higher.

## Step 3 — Triage table

1. New worksheet. `Patient Id` to Rows; `Risk Score`, `Group Label`, `Flagged` to
   Text/Detail. Sort descending by `Risk Score`.
2. Drag `Risk Score` to Color for a heat effect. This is the "who to review first" list.

## Step 4 — Threshold trade-off

1. New worksheet, add `tableau_threshold_curve.csv`.
2. `Threshold` to Columns; `Recall` and `False Alarm` to Rows (dual axis,
   synchronize or use a secondary axis). Shows recall rising as false alarms rise.

## Step 4b — Early-warning forecast

1. New worksheet, add `tableau_forecast_timeline.csv`.
2. `T Sec` to Columns. Drag `Risk`, `Forecast`, and `Threshold` to Rows (or to a
   single axis via Measure Values) so all three plot together.
3. The `Forecast` line climbs to the threshold *before* `Risk` does — that's the
   early warning. Drag `Pre Alert` to Color or Shape to mark the warned points.
4. Title: "Early-warning forecast — pre-alert fires before the risk crosses."

## Step 5 — Assemble + publish

1. New Dashboard. Drag the four sheets in. Add a title and a one-line caption:
   "FFT-based ECG screening — recall-prioritized triage on 356 patients
   (educational demo, not diagnostic)."
2. File → Save to Tableau Public. Copy the public URL.

Put that URL on your resume and LinkedIn next to the GitHub repo link — a
clickable live dashboard is one of the strongest things a data-analyst applicant
can show.

> Honesty note for your write-up: the high-recall threshold flags ~54% of the
> cohort and produces many false alarms. Say so — framing it as a deliberate
> first-pass-screen trade-off reads as analytical maturity, not a weakness.
