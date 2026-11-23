# Climate & Trends-Driven Disease Forecasting (BTP)

**Final-Year B.Tech Bioinformatics Thesis Project**

An interpretable, early-warning disease outbreak forecasting pipeline that models the lead time between localized Google Trends search signals and laboratory-confirmed disease surges in India.

---

## Key Highlights & Findings
* **Methodology Validation:** Tested and verified on US CDC HHS Region 6 data (2015–2019), identifying Texas as a 1-week lead indicator ($\rho = 0.5024, p < 10^{-17}$).
* **Granularity Trap Solved:** Proven that 16-year continuous queries silently collapse into monthly data. The pipeline employs chunked $\le 5$-year queries with overlap rescaling to retain true weekly resolution.
* **Hindi-Belt Inclusivity:** Confirmed that Hindi symptom terms (`बुखार`, `खांसी`) have search volume equivalent to English in states like UP and Bihar, preventing linguistic suppression of signals.
* **India Surveillance:** Using WHO FluNet weekly confirmed case counts (2010–2026) as the primary outcome curve against multi-state search interest series.

---

## Project Structure Overview
- `src/`: Active India pipeline (chunked ingestion, lag correlation, Granger causality).
- `experiments/gtrends_preflight/`: Diagnostic tests verifying term thresholds, 5-yr vs 16-yr granularity, and Hindi language search volume.
- `benchmarks/us_cdc_validation/`: Methodology proof-of-concept on US CDC ILINet data (scripts, data, and visual lag curves).
- `Data/Clean/INDIA/`: Cleaned surveillance datasets for WHO FluNet (`Influenza/`) and IDSP (`Diar/`).
- `docs/`: Thesis methodology ([docs/BTP_Methodology.md](docs/BTP_Methodology.md)) and architecture flowcharts.

---

## Environment & Execution
Use the dedicated virtual environment:
```powershell
.\.venv\Scripts\Activate.ps1
```

To run the Google Trends Preflight Test:
```powershell
.\.venv\Scripts\python.exe experiments/gtrends_preflight/gtrends_preflight_test.py
```

To run the US CDC validation lag analysis:
```powershell
.\.venv\Scripts\python.exe benchmarks/us_cdc_validation/scripts/region6_lag_validation.py
```
