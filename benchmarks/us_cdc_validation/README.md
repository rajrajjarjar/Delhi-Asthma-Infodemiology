# US CDC ILINet Benchmark & Proof of Concept

## Purpose
Demonstrates and validates the BTP early-warning methodology using CDC ILINet surveillance data (HHS Region 6: Texas, Louisiana, Arkansas, New Mexico, Oklahoma) for the period 2015–2019.

## Folder Organization
- `data/`: CDC surveillance datasets (`ILLnet2.2.csv` for weighted ILI percentages, and NREVSS lab confirmation data).
- `scripts/`:
  - `region6_lag_validation.py`: Main validation script computing multi-week Spearman rank correlation ($[-8, +8]$ weeks) per state against the regional ILI curve.
  - `hhs_seasonal_peaks.py`: Seasonal peak timing and intensity analysis across all 10 HHS regions.
  - `plot_region6_lag_curves.py`: Generates per-state and overlaid lag curves.
  - `hhs_region6_composite_test.py`: Supporting composite analysis script.
- `results/`:
  - `per_state_lags/`: Correlation tables (`R6_BestLagPerState.xlsx`, `R6_PerState_LagCurves.xlsx`), time-series datasets, and lag curve plots.
  - `seasonal_peaks/`: Peak summary spreadsheets and overlay charts.
  - `merged_region6/`: Merged region-level datasets and regression outputs.

## Validated Results
- **Texas:** Statistically proven to **lead** the regional curve by **1 week** ($\rho = 0.5024, p = 5.75 \times 10^{-18}$).
- **New Mexico, Oklahoma, Louisiana:** Synchronous ($\text{lag} = 0, \rho \approx 0.53 - 0.58$).
- **Arkansas:** Trails by 1 week ($\text{lag} = -1$).
