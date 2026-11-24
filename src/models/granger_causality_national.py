"""
granger_causality_national.py
=============================
Phase 3A: Granger Causality Testing — NATIONAL BASELINE

Tests whether National Google Trends search volume Granger-causes WHO FluNet
laboratory-confirmed influenza cases (INF_ALL), i.e., whether past GT values
contain predictive information about future flu cases beyond what the flu
series' own history provides.

WHAT GRANGER CAUSALITY PROVES
-----------------------------
Granger causality is a formal statistical hypothesis test that answers:
  "Does knowing past values of X (Google Trends) improve predictions of
   Y (flu cases) beyond what Y's own past values can predict?"

This is strictly stronger than correlation: Spearman tells us the two series
move together; Granger proves DIRECTIONAL TEMPORAL PRECEDENCE.

PREREQUISITES
-------------
Both series must be stationary (constant mean/variance over time). We verify
this with the Augmented Dickey-Fuller (ADF) test and difference if needed.

ANALYSIS WINDOWS
----------------
  1. Pre-COVID (2011-01-01 to 2019-12-31) — primary analysis
  2. Post-COVID (2022-07-01 onward)        — secondary confirmation

OUTPUT FILES  (all in Data/results/national/)
---------------------------------------------
  granger_national_results.csv       F-statistics and p-values at each lag
  granger_national_stationarity.csv  ADF test results for both series
  granger_national_summary.csv       Headline verdict table

RUN INSTRUCTIONS
----------------
  cd E:\\Projects\\BTP
  .\\.venv\\Scripts\\python.exe src/models/granger_causality_national.py
"""

from pathlib import Path
import warnings
import io
import contextlib
import numpy as np
import pandas as pd
from statsmodels.tsa.stattools import grangercausalitytests, adfuller

warnings.filterwarnings("ignore", category=FutureWarning)

# ============================================================================
# CONFIGURATION
# ============================================================================

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

FLUNET_CSV = PROJECT_ROOT / "Data" / "Clean" / "INDIA" / "Influenza" / "india_flu.csv"
GT_NATIONAL_CSV = PROJECT_ROOT / "Data" / "processed" / "gtrends" / "IN_stitched.csv"

OUTPUT_DIR = PROJECT_ROOT / "Data" / "results" / "national"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

MAX_GRANGER_LAG = 8   # Test lags 1 through 8 weeks
SIGNIFICANCE = 0.05

PRECOVID_START = "2011-01-01"
PRECOVID_END = "2019-12-31"
POSTCOVID_START = "2022-07-01"


# ============================================================================
# DATA LOADING
# ============================================================================

def load_and_merge():
    """Load FluNet and National GT, merge on week_start, return merged df."""
    flu = pd.read_csv(FLUNET_CSV, parse_dates=["ISO_WEEKSTARTDATE"])
    # Aggregate sentinel + non-sentinel streams by week to prevent duplicate dates
    flu = flu.groupby("ISO_WEEKSTARTDATE")[["INF_ALL"]].sum(min_count=1).dropna()
    flu.index.name = "week_start"

    gt = pd.read_csv(GT_NATIONAL_CSV, index_col=0, parse_dates=True)
    gt.index.name = "week_start"
    zcol = [c for c in gt.columns if c.startswith("zscore_")][0]
    rawcol = [c for c in gt.columns if c.startswith("raw_")][0]
    gt = gt[[rawcol, zcol]].copy()
    gt.columns = ["gt_raw", "gt_zscore"]

    merged = gt.join(flu, how="inner").dropna()
    merged = merged[~merged.index.duplicated(keep="first")].sort_index()
    print(f"[MERGE] {len(merged)} aligned unique weeks "
          f"({merged.index.min().date()} to {merged.index.max().date()})")
    return merged


# ============================================================================
# STATIONARITY TESTING (ADF)
# ============================================================================

def adf_test(series, name):
    """
    Run ADF test and return a dict of results.
    Null hypothesis: series has a unit root (non-stationary).
    If p < 0.05, reject null => series IS stationary.
    """
    result = adfuller(series.dropna(), autolag="AIC")
    return {
        "series": name,
        "adf_statistic": round(result[0], 4),
        "p_value": round(result[1], 6),
        "lags_used": result[2],
        "n_obs": result[3],
        "critical_1pct": round(result[4]["1%"], 4),
        "critical_5pct": round(result[4]["5%"], 4),
        "critical_10pct": round(result[4]["10%"], 4),
        "stationary_at_5pct": result[1] < 0.05,
    }


def ensure_stationarity(df, col, name):
    """
    Test stationarity; if non-stationary, first-difference the series.
    Returns (stationary_series, adf_results_list, was_differenced).
    """
    adf_results = []

    # Test level series
    adf_level = adf_test(df[col], f"{name} (level)")
    adf_results.append(adf_level)
    print(f"  ADF [{name} level]: stat={adf_level['adf_statistic']}, "
          f"p={adf_level['p_value']}, "
          f"stationary={'YES' if adf_level['stationary_at_5pct'] else 'NO'}")

    if adf_level["stationary_at_5pct"]:
        return df[col], adf_results, False

    # First difference
    diffed = df[col].diff().dropna()
    adf_diff = adf_test(diffed, f"{name} (1st diff)")
    adf_results.append(adf_diff)
    print(f"  ADF [{name} 1st diff]: stat={adf_diff['adf_statistic']}, "
          f"p={adf_diff['p_value']}, "
          f"stationary={'YES' if adf_diff['stationary_at_5pct'] else 'NO'}")

    return diffed, adf_results, True


# ============================================================================
# GRANGER CAUSALITY ENGINE
# ============================================================================

def run_granger(gt_series, flu_series, max_lag=MAX_GRANGER_LAG):
    """
    Run Granger causality test: does GT Granger-cause Flu?

    statsmodels.grangercausalitytests expects a 2-column DataFrame where:
      column 0 = the EFFECT variable (flu cases)
      column 1 = the CAUSE variable (Google Trends)

    Returns a list of dicts with F-stat and p-value at each lag.
    """
    s_flu = flu_series[~flu_series.index.duplicated(keep="first")]
    s_gt = gt_series[~gt_series.index.duplicated(keep="first")]
    combined = pd.concat([s_flu.rename("flu"), s_gt.rename("gt")], axis=1, join="inner").dropna()

    if len(combined) < max_lag + 30:
        print(f"  [WARN] Only {len(combined)} obs, need at least {max_lag+30}")
        return []

    # grangercausalitytests wants [effect, cause] column order
    data = combined[["flu", "gt"]].values

    try:
        with contextlib.redirect_stdout(io.StringIO()):
            results = grangercausalitytests(data, maxlag=max_lag)
    except Exception as e:
        print(f"  [ERROR] Granger test failed: {e}")
        return []

    rows = []
    for lag in range(1, max_lag + 1):
        test_dict = results[lag][0]
        # Extract the SSR-based F-test (most common)
        f_stat = test_dict["ssr_ftest"][0]
        p_val = test_dict["ssr_ftest"][1]
        df_denom = test_dict["ssr_ftest"][2]
        df_num = test_dict["ssr_ftest"][3]

        # Also extract the chi-squared test for confirmation
        chi2_stat = test_dict["ssr_chi2test"][0]
        chi2_p = test_dict["ssr_chi2test"][1]

        rows.append({
            "lag_weeks": lag,
            "f_statistic": round(float(f_stat), 4),
            "f_p_value": float(p_val),
            "f_significant_p05": p_val < SIGNIFICANCE,
            "chi2_statistic": round(float(chi2_stat), 4),
            "chi2_p_value": float(chi2_p),
            "chi2_significant_p05": chi2_p < SIGNIFICANCE,
            "df_num": int(df_num),
            "df_denom": int(df_denom),
            "n_obs": len(combined),
        })

    return rows


# ============================================================================
# MAIN
# ============================================================================

def main():
    print("=" * 60)
    print("Phase 3A: Granger Causality — NATIONAL BASELINE")
    print("=" * 60)

    merged = load_and_merge()
    all_adf_results = []
    all_granger_results = []
    summary_rows = []

    # ==================================================================
    # Pre-COVID Analysis
    # ==================================================================
    precovid = merged.loc[PRECOVID_START:PRECOVID_END].copy()
    print(f"\n--- Pre-COVID Period ({len(precovid)} weeks) ---")

    # Stationarity checks
    gt_stat, adf_gt, gt_diffed = ensure_stationarity(
        precovid, "gt_zscore", "GT_National_PreCOVID")
    flu_stat, adf_flu, flu_diffed = ensure_stationarity(
        precovid, "INF_ALL", "FluNet_PreCOVID")
    all_adf_results.extend(adf_gt + adf_flu)

    # If either was differenced, align them
    if gt_diffed or flu_diffed:
        common_idx = gt_stat.index.intersection(flu_stat.index)
        gt_stat = gt_stat.loc[common_idx]
        flu_stat = flu_stat.loc[common_idx]
        diff_note = " (1st-differenced)"
    else:
        diff_note = " (level)"

    # Test: GT Granger-causes Flu
    print(f"\n  Testing: GT -> Flu{diff_note}")
    gc_gt_flu = run_granger(gt_stat, flu_stat)
    for r in gc_gt_flu:
        r["period"] = "pre_covid_2011_2019"
        r["direction"] = "GT -> FluNet"
        r["differenced"] = gt_diffed or flu_diffed
    all_granger_results.extend(gc_gt_flu)

    # Test: Flu Granger-causes GT (reverse — should be weaker or null)
    print(f"  Testing: Flu -> GT{diff_note} (reverse control)")
    gc_flu_gt = run_granger(flu_stat, gt_stat)
    for r in gc_flu_gt:
        r["period"] = "pre_covid_2011_2019"
        r["direction"] = "FluNet -> GT"
        r["differenced"] = gt_diffed or flu_diffed
    all_granger_results.extend(gc_flu_gt)

    # Summarize pre-COVID
    if gc_gt_flu:
        best_fwd = min(gc_gt_flu, key=lambda x: x["f_p_value"])
        sig_lags_fwd = sum(1 for r in gc_gt_flu if r["f_significant_p05"])
        summary_rows.append({
            "period": "pre_covid_2011_2019",
            "direction": "GT -> FluNet",
            "best_lag": best_fwd["lag_weeks"],
            "best_f_stat": best_fwd["f_statistic"],
            "best_p_value": best_fwd["f_p_value"],
            "significant_lags_out_of_8": sig_lags_fwd,
            "verdict": "GRANGER-CAUSES" if sig_lags_fwd >= 1 else "NO CAUSALITY",
            "differenced": gt_diffed or flu_diffed,
        })
        print(f"\n  GT -> Flu: Best lag={best_fwd['lag_weeks']} "
              f"F={best_fwd['f_statistic']:.2f} "
              f"p={best_fwd['f_p_value']:.2e} "
              f"({sig_lags_fwd}/8 lags significant)")

    if gc_flu_gt:
        best_rev = min(gc_flu_gt, key=lambda x: x["f_p_value"])
        sig_lags_rev = sum(1 for r in gc_flu_gt if r["f_significant_p05"])
        summary_rows.append({
            "period": "pre_covid_2011_2019",
            "direction": "FluNet -> GT",
            "best_lag": best_rev["lag_weeks"],
            "best_f_stat": best_rev["f_statistic"],
            "best_p_value": best_rev["f_p_value"],
            "significant_lags_out_of_8": sig_lags_rev,
            "verdict": "GRANGER-CAUSES" if sig_lags_rev >= 1 else "NO CAUSALITY",
            "differenced": gt_diffed or flu_diffed,
        })
        print(f"  Flu -> GT: Best lag={best_rev['lag_weeks']} "
              f"F={best_rev['f_statistic']:.2f} "
              f"p={best_rev['f_p_value']:.2e} "
              f"({sig_lags_rev}/8 lags significant)")

    # ==================================================================
    # Post-COVID Analysis
    # ==================================================================
    postcovid = merged.loc[POSTCOVID_START:].copy()
    if len(postcovid) >= 50:
        print(f"\n--- Post-COVID Period ({len(postcovid)} weeks) ---")

        gt_stat_p, adf_gt_p, gt_diff_p = ensure_stationarity(
            postcovid, "gt_zscore", "GT_National_PostCOVID")
        flu_stat_p, adf_flu_p, flu_diff_p = ensure_stationarity(
            postcovid, "INF_ALL", "FluNet_PostCOVID")
        all_adf_results.extend(adf_gt_p + adf_flu_p)

        if gt_diff_p or flu_diff_p:
            common_idx = gt_stat_p.index.intersection(flu_stat_p.index)
            gt_stat_p = gt_stat_p.loc[common_idx]
            flu_stat_p = flu_stat_p.loc[common_idx]

        print(f"\n  Testing: GT -> Flu (post-COVID)")
        gc_post = run_granger(gt_stat_p, flu_stat_p)
        for r in gc_post:
            r["period"] = "post_covid_2022_onward"
            r["direction"] = "GT -> FluNet"
            r["differenced"] = gt_diff_p or flu_diff_p
        all_granger_results.extend(gc_post)

        if gc_post:
            best_post = min(gc_post, key=lambda x: x["f_p_value"])
            sig_post = sum(1 for r in gc_post if r["f_significant_p05"])
            summary_rows.append({
                "period": "post_covid_2022_onward",
                "direction": "GT -> FluNet",
                "best_lag": best_post["lag_weeks"],
                "best_f_stat": best_post["f_statistic"],
                "best_p_value": best_post["f_p_value"],
                "significant_lags_out_of_8": sig_post,
                "verdict": "GRANGER-CAUSES" if sig_post >= 1 else "NO CAUSALITY",
                "differenced": gt_diff_p or flu_diff_p,
            })
            print(f"  GT -> Flu: Best lag={best_post['lag_weeks']} "
                  f"F={best_post['f_statistic']:.2f} "
                  f"p={best_post['f_p_value']:.2e} "
                  f"({sig_post}/8 lags significant)")

    # ==================================================================
    # Save all outputs
    # ==================================================================
    if all_granger_results:
        gc_df = pd.DataFrame(all_granger_results)
        gc_df.to_csv(OUTPUT_DIR / "granger_national_results.csv", index=False)

    if all_adf_results:
        adf_df = pd.DataFrame(all_adf_results)
        adf_df.to_csv(OUTPUT_DIR / "granger_national_stationarity.csv",
                       index=False)

    if summary_rows:
        sum_df = pd.DataFrame(summary_rows)
        sum_df.to_csv(OUTPUT_DIR / "granger_national_summary.csv", index=False)

    print(f"\n{'='*60}")
    print("NATIONAL GRANGER CAUSALITY COMPLETE")
    print(f"{'='*60}")
    print(f"  Results       → {OUTPUT_DIR / 'granger_national_results.csv'}")
    print(f"  Stationarity  → {OUTPUT_DIR / 'granger_national_stationarity.csv'}")
    print(f"  Summary       → {OUTPUT_DIR / 'granger_national_summary.csv'}")
    print()


if __name__ == "__main__":
    main()
