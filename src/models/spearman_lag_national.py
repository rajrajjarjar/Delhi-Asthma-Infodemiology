"""
spearman_lag_national.py
========================
Phase 2A: Spearman Rank Lag Correlation — NATIONAL BASELINE

Compares: Google Trends National composite (geo='IN') vs WHO FluNet INF_ALL.

This is the macro-synchrony baseline. We expect a moderate correlation near
Lag 0 (search behaviour tracks national flu cases concurrently). This file
exists as a standalone, independent deliverable: even if the state-level
sentinel hypothesis does not pan out, this national analysis demonstrates
that Google Trends search volume in India is a statistically significant
proxy for laboratory-confirmed influenza activity.

ANALYSIS WINDOWS
----------------
  1. Full Pre-COVID Baseline (2011-01-01 to 2019-12-31)
  2. Per-year outbreak waves (each calendar year from 2011 to 2019)
  3. Post-COVID Recovery (2022-07-01 onward, if data allows)

COVID EXCLUSION
---------------
During 2020-2022, mass COVID symptom searching inflated 'fever'/'cough'
while routine influenza PCR testing collapsed. These years are analysed
separately to avoid contaminating the main result.

LAG SIGN CONVENTION
-------------------
We correlate  GT[t - lag]  vs  FluNet[t].
  POSITIVE lag  =>  Google Trends LEADS FluNet (predictive, useful)
  NEGATIVE lag  =>  Google Trends TRAILS FluNet (reactive)

OUTPUT FILES  (all in Data/results/national/)
---------------------------------------------
  national_lag_curves.csv           rho/p at every lag
  national_best_lag_summary.csv     headline one-row result
  national_yearly_breakdown.csv     per-year best lag + rho
  national_aligned_timeseries.csv   merged week-by-week data

RUN INSTRUCTIONS
----------------
  cd E:\\Projects\\BTP
  .\\.venv\\Scripts\\python.exe src/models/spearman_lag_national.py
"""

from pathlib import Path
import numpy as np
import pandas as pd
from scipy.stats import spearmanr

# ============================================================================
# CONFIGURATION
# ============================================================================

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

FLUNET_CSV = PROJECT_ROOT / "Data" / "Clean" / "INDIA" / "Influenza" / "india_flu.csv"
GT_NATIONAL_CSV = PROJECT_ROOT / "Data" / "processed" / "gtrends" / "IN_stitched.csv"

OUTPUT_DIR = PROJECT_ROOT / "Data" / "results" / "national"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

MAX_LAG = 8          # test lags from -8 to +8 weeks
MIN_OBS = 30         # minimum overlapping weeks to compute a valid correlation

# Pre-COVID analysis window
PRECOVID_START = "2011-01-01"
PRECOVID_END = "2019-12-31"

# Post-COVID recovery window
POSTCOVID_START = "2022-07-01"


# ============================================================================
# DATA LOADING
# ============================================================================

def load_flunet():
    """Load WHO FluNet India and return a clean weekly Series of INF_ALL."""
    flu = pd.read_csv(FLUNET_CSV, parse_dates=["ISO_WEEKSTARTDATE"])
    # Aggregate sentinel + non-sentinel streams by week to avoid duplicate dates
    flu = flu.groupby("ISO_WEEKSTARTDATE")[["INF_ALL", "INF_A", "INF_B"]].sum(min_count=1).dropna(subset=["INF_ALL"])
    flu = flu[~flu.index.duplicated(keep="first")].sort_index()
    flu.index.name = "week_start"
    print(f"[FluNet] Loaded {len(flu)} unique weeks "
          f"({flu.index.min().date()} to {flu.index.max().date()})")
    return flu


def load_national_gt():
    """Load the stitched National (IN) Google Trends composite."""
    gt = pd.read_csv(GT_NATIONAL_CSV, index_col=0, parse_dates=True)
    gt.index.name = "week_start"
    # Use the z-scored column
    zcol = [c for c in gt.columns if c.startswith("zscore_")][0]
    rawcol = [c for c in gt.columns if c.startswith("raw_")][0]
    out = gt[[rawcol, zcol]].copy()
    out.columns = ["gt_raw", "gt_zscore"]
    print(f"[GT-National] Loaded {len(out)} weeks "
          f"({out.index.min().date()} to {out.index.max().date()})")
    return out


# ============================================================================
# SPEARMAN LAG CORRELATION ENGINE
# ============================================================================

def compute_lag_curve(gt_series, flu_series, max_lag=MAX_LAG, min_obs=MIN_OBS):
    """
    Compute Spearman rho at each lag from -max_lag to +max_lag.

    Uses .shift(lag) so that:
      positive lag  =>  GT LEADS Flu  (we're testing GT from `lag` weeks ago)
      negative lag  =>  GT TRAILS Flu
    """
    rows = []
    for lag in range(-max_lag, max_lag + 1):
        shifted_gt = gt_series.shift(lag)
        valid = shifted_gt.notna() & flu_series.notna()
        n_obs = int(valid.sum())

        if n_obs < min_obs:
            continue

        rho, p_val = spearmanr(shifted_gt[valid], flu_series[valid])
        rows.append({
            "lag_weeks": lag,
            "spearman_rho": round(float(rho), 4),
            "p_value": float(p_val),
            "n_weeks": n_obs,
            "significant_p05": p_val < 0.05,
            "significant_p01": p_val < 0.01,
        })

    return pd.DataFrame(rows)


def find_best_lag(lag_curve_df):
    """Extract the single best (highest rho) lag from a lag curve."""
    if lag_curve_df.empty:
        return None
    best = lag_curve_df.loc[lag_curve_df["spearman_rho"].idxmax()]
    return {
        "best_lag_weeks": int(best["lag_weeks"]),
        "spearman_rho": best["spearman_rho"],
        "p_value": best["p_value"],
        "n_weeks": int(best["n_weeks"]),
        "leads_or_trails": (
            "LEADS" if best["lag_weeks"] > 0
            else "TRAILS" if best["lag_weeks"] < 0
            else "SYNCHRONOUS"
        ),
        "significant_p05": bool(best["significant_p05"]),
    }


# ============================================================================
# MAIN
# ============================================================================

def main():
    print("=" * 60)
    print("Phase 2A: Spearman Lag Correlation — NATIONAL BASELINE")
    print("=" * 60)

    # Load data
    flu = load_flunet()
    gt = load_national_gt()

    # Merge on week_start (inner join)
    merged = gt.join(flu, how="inner")
    merged = merged.dropna(subset=["INF_ALL"])
    print(f"\n[MERGE] {len(merged)} aligned weeks "
          f"({merged.index.min().date()} to {merged.index.max().date()})")

    # Save aligned time series
    ts_path = OUTPUT_DIR / "national_aligned_timeseries.csv"
    merged.to_csv(ts_path)
    print(f"  Saved → {ts_path}")

    # ----------------------------------------------------------------
    # Analysis 1: Pre-COVID Baseline (2011–2019)
    # ----------------------------------------------------------------
    precovid = merged.loc[PRECOVID_START:PRECOVID_END]
    print(f"\n--- Pre-COVID Baseline ({len(precovid)} weeks) ---")

    lag_curve = compute_lag_curve(precovid["gt_zscore"], precovid["INF_ALL"])
    best = find_best_lag(lag_curve)

    if best:
        print(f"  Best Lag: {best['best_lag_weeks']:+d} weeks | "
              f"rho = {best['spearman_rho']:+.4f} | "
              f"p = {best['p_value']:.2e} | "
              f"{best['leads_or_trails']}")
    else:
        print("  [WARN] No valid lag could be computed")

    # Tag and save
    lag_curve["period"] = "pre_covid_2011_2019"
    all_lag_curves = [lag_curve]

    # ----------------------------------------------------------------
    # Analysis 2: Post-COVID Recovery (2022-07 onward)
    # ----------------------------------------------------------------
    postcovid = merged.loc[POSTCOVID_START:]
    if len(postcovid) >= MIN_OBS:
        print(f"\n--- Post-COVID Recovery ({len(postcovid)} weeks) ---")
        lag_curve_post = compute_lag_curve(
            postcovid["gt_zscore"], postcovid["INF_ALL"])
        best_post = find_best_lag(lag_curve_post)

        if best_post:
            print(f"  Best Lag: {best_post['best_lag_weeks']:+d} weeks | "
                  f"rho = {best_post['spearman_rho']:+.4f} | "
                  f"p = {best_post['p_value']:.2e} | "
                  f"{best_post['leads_or_trails']}")

        lag_curve_post["period"] = "post_covid_2022_onward"
        all_lag_curves.append(lag_curve_post)

    # ----------------------------------------------------------------
    # Analysis 3: Per-Year Outbreak Breakdown (2011–2019)
    # ----------------------------------------------------------------
    print(f"\n--- Per-Year Breakdown ---")
    yearly_rows = []

    for year in range(2011, 2020):
        yr_data = merged.loc[f"{year}-01-01":f"{year}-12-31"]
        if len(yr_data) < MIN_OBS:
            continue

        yr_lag = compute_lag_curve(yr_data["gt_zscore"], yr_data["INF_ALL"])
        yr_best = find_best_lag(yr_lag)

        if yr_best:
            yr_best["year"] = year
            yr_best["n_weeks_in_year"] = len(yr_data)
            yr_best["flu_total"] = int(yr_data["INF_ALL"].sum())
            yr_best["flu_peak_week"] = str(
                yr_data["INF_ALL"].idxmax().date())
            yearly_rows.append(yr_best)

            status = "✓" if yr_best["significant_p05"] else "✗"
            print(f"  {year}: Lag {yr_best['best_lag_weeks']:+d} | "
                  f"rho={yr_best['spearman_rho']:+.4f} | "
                  f"p={yr_best['p_value']:.2e} [{status}] | "
                  f"flu_total={yr_best['flu_total']}")

        yr_lag["period"] = f"year_{year}"
        all_lag_curves.append(yr_lag)

    # ----------------------------------------------------------------
    # Save all outputs
    # ----------------------------------------------------------------
    # 1. Full lag curves (all periods combined)
    combined_lags = pd.concat(all_lag_curves, ignore_index=True)
    lag_path = OUTPUT_DIR / "national_lag_curves.csv"
    combined_lags.to_csv(lag_path, index=False)

    # 2. Best lag summary
    summary_rows = []
    if best:
        best["period"] = "pre_covid_2011_2019"
        summary_rows.append(best)
    if len(postcovid) >= MIN_OBS and best_post:
        best_post["period"] = "post_covid_2022_onward"
        summary_rows.append(best_post)

    summary_df = pd.DataFrame(summary_rows)
    summary_path = OUTPUT_DIR / "national_best_lag_summary.csv"
    summary_df.to_csv(summary_path, index=False)

    # 3. Yearly breakdown
    if yearly_rows:
        yearly_df = pd.DataFrame(yearly_rows)
        yearly_path = OUTPUT_DIR / "national_yearly_breakdown.csv"
        yearly_df.to_csv(yearly_path, index=False)
    else:
        yearly_path = "NOT GENERATED (insufficient data)"

    print(f"\n{'='*60}")
    print("NATIONAL ANALYSIS COMPLETE")
    print(f"{'='*60}")
    print(f"  Lag curves     → {lag_path}")
    print(f"  Best lag       → {summary_path}")
    print(f"  Yearly detail  → {yearly_path}")
    print(f"  Aligned data   → {ts_path}")
    print()


if __name__ == "__main__":
    main()
