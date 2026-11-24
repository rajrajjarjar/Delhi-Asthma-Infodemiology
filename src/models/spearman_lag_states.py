"""
spearman_lag_states.py
======================
Phase 2B: Spearman Rank Lag Correlation — STATE-LEVEL SENTINEL ANALYSIS

Compares: Google Trends per-state composites (7 states) vs WHO FluNet INF_ALL.

This is the core sentinel hypothesis test. The question:
  "Do some Indian states' symptom search volumes rise BEFORE national
   laboratory-confirmed flu cases, providing early-warning lead time?"

Each state gets its own independent lag curve against the shared national
FluNet outcome variable. States are NEVER averaged together — doing so
would destroy the per-state lead/lag differences that are the whole point.

ANALYSIS WINDOWS
----------------
  1. Full Pre-COVID Baseline (2011-01-01 to 2019-12-31)
  2. Per-year outbreak waves (each calendar year from 2011 to 2019)
  3. Post-COVID Recovery (2022-07-01 onward, if data allows)

COVID EXCLUSION
---------------
During 2020-2022, mass COVID symptom searching inflated 'fever'/'cough'
while routine influenza PCR testing collapsed. These years are analysed
separately.

LAG SIGN CONVENTION
-------------------
We correlate  GT_state[t - lag]  vs  FluNet[t].
  POSITIVE lag  =>  State Trends LEADS FluNet (predictive sentinel!)
  NEGATIVE lag  =>  State Trends TRAILS FluNet (reactive)

OUTPUT FILES  (all in Data/results/states/)
-------------------------------------------
  states_lag_curves_precovid.csv       rho/p at every lag, all states
  states_best_lag_summary.csv          headline table: best lag per state
  states_yearly_breakdown.csv          per-state, per-year best lag + rho
  states_aligned_timeseries.csv        merged week-by-week data
  states_lag_curves_postcovid.csv      post-COVID lag curves

RUN INSTRUCTIONS
----------------
  cd E:\\Projects\\BTP
  .\\.venv\\Scripts\\python.exe src/models/spearman_lag_states.py
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
GT_COMPOSITES_CSV = PROJECT_ROOT / "Data" / "processed" / "gtrends" / "all_states_composites.csv"

OUTPUT_DIR = PROJECT_ROOT / "Data" / "results" / "states"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# States to analyse (excludes National — that has its own script)
STATE_COLUMNS = [
    "Delhi", "Haryana", "Uttar Pradesh",
    "Maharashtra", "Kerala", "Tamil Nadu", "West Bengal",
]

MAX_LAG = 8
MIN_OBS = 30

PRECOVID_START = "2011-01-01"
PRECOVID_END = "2019-12-31"
POSTCOVID_START = "2022-07-01"


# ============================================================================
# DATA LOADING
# ============================================================================

def load_flunet():
    """Load WHO FluNet India national surveillance."""
    flu = pd.read_csv(FLUNET_CSV, parse_dates=["ISO_WEEKSTARTDATE"])
    # Aggregate sentinel + non-sentinel streams by week to avoid duplicate dates
    flu = flu.groupby("ISO_WEEKSTARTDATE")[["INF_ALL", "INF_A", "INF_B"]].sum(min_count=1).dropna(subset=["INF_ALL"])
    flu = flu[~flu.index.duplicated(keep="first")].sort_index()
    flu.index.name = "week_start"
    print(f"[FluNet] Loaded {len(flu)} unique weeks "
          f"({flu.index.min().date()} to {flu.index.max().date()})")
    return flu


def load_state_composites():
    """Load the z-scored state composites from all_states_composites.csv."""
    gt = pd.read_csv(GT_COMPOSITES_CSV, index_col=0, parse_dates=True)
    gt.index.name = "week_start"

    # Verify expected state columns are present
    available = [c for c in STATE_COLUMNS if c in gt.columns]
    missing = [c for c in STATE_COLUMNS if c not in gt.columns]
    if missing:
        print(f"[WARN] Missing state columns: {missing}")

    print(f"[GT-States] Loaded {len(gt)} weeks × {len(available)} states "
          f"({gt.index.min().date()} to {gt.index.max().date()})")
    return gt[available]


# ============================================================================
# SPEARMAN LAG CORRELATION ENGINE
# ============================================================================

def compute_lag_curve(gt_series, flu_series, max_lag=MAX_LAG, min_obs=MIN_OBS):
    """
    Compute Spearman rho at each lag from -max_lag to +max_lag.

    Uses .shift(lag):
      positive lag  =>  GT LEADS Flu
      negative lag  =>  GT TRAILS Flu
    """
    rows = []
    for lag in range(-max_lag, max_lag + 1):
        shifted = gt_series.shift(lag)
        valid = shifted.notna() & flu_series.notna()
        n_obs = int(valid.sum())

        if n_obs < min_obs:
            continue

        rho, p_val = spearmanr(shifted[valid], flu_series[valid])
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
    print("Phase 2B: Spearman Lag Correlation — STATE-LEVEL SENTINELS")
    print("=" * 60)

    # Load data
    flu = load_flunet()
    gt_states = load_state_composites()

    # Merge on week_start (inner join)
    merged = gt_states.join(flu, how="inner")
    merged = merged.dropna(subset=["INF_ALL"])
    state_cols = [c for c in STATE_COLUMNS if c in merged.columns]

    print(f"\n[MERGE] {len(merged)} aligned weeks "
          f"({merged.index.min().date()} to {merged.index.max().date()})")

    # Save aligned time series
    ts_path = OUTPUT_DIR / "states_aligned_timeseries.csv"
    merged.to_csv(ts_path)

    # ==================================================================
    # Analysis 1: Pre-COVID Baseline (2011–2019)
    # ==================================================================
    precovid = merged.loc[PRECOVID_START:PRECOVID_END]
    print(f"\n{'='*60}")
    print(f"PRE-COVID BASELINE ({len(precovid)} weeks)")
    print(f"{'='*60}")

    precovid_lag_curves = []
    precovid_best_lags = []

    for state in state_cols:
        lag_curve = compute_lag_curve(precovid[state], precovid["INF_ALL"])
        lag_curve["state"] = state
        lag_curve["period"] = "pre_covid_2011_2019"
        precovid_lag_curves.append(lag_curve)

        best = find_best_lag(lag_curve)
        if best:
            best["state"] = state
            best["period"] = "pre_covid_2011_2019"
            precovid_best_lags.append(best)

            status = "✓" if best["significant_p05"] else "✗"
            print(f"  {state:18s} | Lag {best['best_lag_weeks']:+d} | "
                  f"rho={best['spearman_rho']:+.4f} | "
                  f"p={best['p_value']:.2e} [{status}] | "
                  f"{best['leads_or_trails']}")

    # Save pre-COVID lag curves
    if precovid_lag_curves:
        pc_lags = pd.concat(precovid_lag_curves, ignore_index=True)
        pc_lags.to_csv(OUTPUT_DIR / "states_lag_curves_precovid.csv",
                       index=False)

    # ==================================================================
    # Analysis 2: Post-COVID Recovery (2022-07 onward)
    # ==================================================================
    postcovid = merged.loc[POSTCOVID_START:]
    postcovid_best_lags = []

    if len(postcovid) >= MIN_OBS:
        print(f"\n{'='*60}")
        print(f"POST-COVID RECOVERY ({len(postcovid)} weeks)")
        print(f"{'='*60}")

        postcovid_lag_curves = []

        for state in state_cols:
            lag_curve = compute_lag_curve(
                postcovid[state], postcovid["INF_ALL"])
            lag_curve["state"] = state
            lag_curve["period"] = "post_covid_2022_onward"
            postcovid_lag_curves.append(lag_curve)

            best = find_best_lag(lag_curve)
            if best:
                best["state"] = state
                best["period"] = "post_covid_2022_onward"
                postcovid_best_lags.append(best)

                status = "✓" if best["significant_p05"] else "✗"
                print(f"  {state:18s} | Lag {best['best_lag_weeks']:+d} | "
                      f"rho={best['spearman_rho']:+.4f} | "
                      f"p={best['p_value']:.2e} [{status}] | "
                      f"{best['leads_or_trails']}")

        if postcovid_lag_curves:
            pt_lags = pd.concat(postcovid_lag_curves, ignore_index=True)
            pt_lags.to_csv(
                OUTPUT_DIR / "states_lag_curves_postcovid.csv", index=False)

    # ==================================================================
    # Analysis 3: Per-Year × Per-State Breakdown (2011–2019)
    # ==================================================================
    print(f"\n{'='*60}")
    print("PER-YEAR × PER-STATE BREAKDOWN (2011–2019)")
    print(f"{'='*60}")

    yearly_rows = []
    for year in range(2011, 2020):
        yr_data = merged.loc[f"{year}-01-01":f"{year}-12-31"]
        if len(yr_data) < MIN_OBS:
            continue

        flu_total = int(yr_data["INF_ALL"].sum())
        flu_peak = str(yr_data["INF_ALL"].idxmax().date())

        yr_state_results = []
        for state in state_cols:
            yr_lag = compute_lag_curve(yr_data[state], yr_data["INF_ALL"])
            yr_best = find_best_lag(yr_lag)
            if yr_best:
                yr_best["state"] = state
                yr_best["year"] = year
                yr_best["flu_total"] = flu_total
                yr_best["flu_peak_week"] = flu_peak
                yearly_rows.append(yr_best)
                yr_state_results.append(
                    f"{state}: {yr_best['best_lag_weeks']:+d} "
                    f"(rho={yr_best['spearman_rho']:+.3f})")

        print(f"  {year} (flu_total={flu_total}): "
              + " | ".join(yr_state_results[:4]))
        if len(yr_state_results) > 4:
            print(f"       " + " | ".join(yr_state_results[4:]))

    # ==================================================================
    # Save combined outputs
    # ==================================================================

    # Best lag summary (all periods)
    all_best = precovid_best_lags + postcovid_best_lags
    if all_best:
        best_df = pd.DataFrame(all_best)
        # Sort: pre-COVID first, then by rho descending
        best_df = best_df.sort_values(
            ["period", "spearman_rho"], ascending=[True, False])
        summary_path = OUTPUT_DIR / "states_best_lag_summary.csv"
        best_df.to_csv(summary_path, index=False)
    else:
        summary_path = "NOT GENERATED"

    # Yearly breakdown
    if yearly_rows:
        yearly_df = pd.DataFrame(yearly_rows)
        yearly_path = OUTPUT_DIR / "states_yearly_breakdown.csv"
        yearly_df.to_csv(yearly_path, index=False)
    else:
        yearly_path = "NOT GENERATED"

    print(f"\n{'='*60}")
    print("STATE-LEVEL ANALYSIS COMPLETE")
    print(f"{'='*60}")
    print(f"  Pre-COVID lags   → {OUTPUT_DIR / 'states_lag_curves_precovid.csv'}")
    print(f"  Post-COVID lags  → {OUTPUT_DIR / 'states_lag_curves_postcovid.csv'}")
    print(f"  Best lag summary → {summary_path}")
    print(f"  Yearly detail    → {yearly_path}")
    print(f"  Aligned data     → {ts_path}")
    print()


if __name__ == "__main__":
    main()
