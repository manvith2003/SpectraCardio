# Power BI build guide — SpectraCardio

This folder contains a ready-to-import **star schema** and a `DAX_measures.txt`
file. Building the dashboard is plug-and-play. Power BI Desktop is **Windows-only
and free** (Microsoft Store). On a Mac, use the Tableau version instead (see
`../tableau/`), or build this on a Windows machine / VM.

## What's in this folder

| File | Role in the model | Grain |
|------|-------------------|-------|
| `dim_patient.csv` | Dimension — one row per patient (label, risk, flag) | 356 rows |
| `dim_lead.csv` | Dimension — the three precordial leads | 3 rows |
| `dim_band.csv` | Dimension — the three frequency bands | 3 rows |
| `fact_band_power.csv` | Fact — band power per patient/lead/band | 3,204 rows |
| `fact_lead_spectral.csv` | Fact — lead-level spectral summaries | 1,068 rows |
| `fact_threshold_curve.csv` | Helper — recall/false-alarm by threshold | 17 rows |
| `fact_forecast_timeline.csv` | Helper — early-warning forecast timeline | 40 rows |
| `DAX_measures.txt` | Copy-paste measures | — |

## Step 1 — Import

Get Data → Text/CSV → import all six CSVs. In each import preview, check the data
types (patient_id = Whole Number or Text but **consistent across tables**;
powers/scores = Decimal Number). Load.

## Step 2 — Build relationships (Model view)

Drag to create these one-to-many links (the "1" side is the dimension):

```
dim_patient[patient_id] 1 --→ * fact_band_power[patient_id]
dim_patient[patient_id] 1 --→ * fact_lead_spectral[patient_id]
dim_lead[lead]          1 --→ * fact_band_power[lead]
dim_lead[lead]          1 --→ * fact_lead_spectral[lead]
dim_band[band]          1 --→ * fact_band_power[band]
```

Leave `fact_threshold_curve` standalone. Set all relationships to single-direction
cross-filter (the default) — the star schema keeps filters clean and DAX simple.

## Step 3 — Add the measures

Open `DAX_measures.txt` and paste each block as a New measure (right-click a table
→ New measure). Start with `Total Patients`, `Brugada Patients`, `Recall %`,
`Avg Rel Power`.

## Step 4 — Build the four-page report

**Page 1 — Cohort overview**
- Cards: `Total Patients`, `Brugada Patients`, `Brugada Prevalence %`
- Donut: `Total Patients` by `dim_patient[group_label]`
- One-line text box stating the imbalance and why recall (not accuracy) is the metric.

**Page 2 — Spectral signature** (the money chart)
- Clustered column or matrix: Axis = `dim_band[band_label]`, Legend =
  `dim_patient[group_label]`, Values = `Avg Rel Power`, filtered to `lead = "V1"`.
  This shows the ~2× lower HF power in Brugada — the core finding.
- Slicer: `dim_lead[lead]` to flip between V1/V2/V3.
- Card: `HF Power Gap (Healthy - Brugada)`.

**Page 3 — Triage**
- Table: `dim_patient[patient_id]`, `group_label`, `risk_score`, sorted desc by
  risk. Conditional-format `risk_score` as a color scale.
- Histogram (use a binned `risk_score`): score distribution by group.
- Cards: `Recall %`, `Precision %`, `Flag Rate %`, `Missed Cases`.

**Page 4 — Threshold what-if**
- Slicer: `fact_threshold_curve[threshold]`.
- Line chart: `threshold` on axis, `recall` and (scaled) `false_alarm` as lines —
  the recall/false-alarm trade-off.
- Cards: `Cases Caught @ Threshold`, `False Alarms @ Threshold`.

**Page 5 — Early-warning forecast**
- Line chart: Axis = `fact_forecast_timeline[t_sec]`; Values = `risk`, `forecast`,
  `threshold`. The forecast line pulls ahead of the risk line and reaches the
  threshold first — the visual "predict the spike early" story.
- Cards: `Pre-Alerts Fired`, `Early-Warning Lead Time (s)`, `Peak Forecast Risk`.
- Optional: scatter/markers where `pre_alert = 1` vs where `flagged = 1` to show
  the warning firing before the crossing.

## Step 5 — Publish

Publish to Power BI Service (free) and copy the report link, or export to PDF for
a static portfolio artifact. Either link goes straight on your resume.

> Tip for interviews: the star schema itself is a talking point — explain why you
> separated facts from dimensions and put band power in long format rather than 9
> wide columns. That modeling choice is what BI roles screen for.
