"""
granger_causality_states.py
===========================
Phase 3B: Granger Causality Testing — STATE-LEVEL SENTINELS

For each of the 7 candidate states, tests whether that state's Google Trends
composite Granger-causes WHO FluNet national flu cases.

This is the directional causality companion to Phase 2B (Spearman lag). While
Spearman showed correlation at various lags, Granger formally tests whether
the state's search data contains predictive information above and beyond the
flu series' own autoregressive structure.

BIDIRECTIONAL TESTING
---------------------
For each state, we test both directions:
  1. GT_state -> FluNet  (does search activity predict flu cases?)
  2. FluNet -> GT_state  (reverse control — do flu cases predict searches?)

If (1) is significant but (2) is not, the state's search data is a true
leading indicator, not just a contemporaneous correlate.

OUTPUT FILES  (all in Data/results/states/)
-------------------------------------------
  granger_states_results.csv         F-statistics at each lag, all states
  granger_states_stationarity.csv    ADF test results for all series
  granger_states_summary.csv         Headline verdict per state

RUN INSTRUCTIONS
----------------
  cd E:\\Projects\\BTP
  .\\.venv\\Scripts\\python.exe src/models/granger_causality_states.py
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
GT_COMPOSITES_CSV = PROJECT_ROOT / "Data" / "processed" / "gtrends" / "all_states_composites.csv"

OUTPUT_DIR = PROJECT_ROOT / "Data" / "results" / "states"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

STATE_COLUMNS = [
    "Delhi", "Haryana", "Uttar Pradesh",
    "Maharashtra", "Kerala", "Tamil Nadu", "West Bengal",
]

MAX_GRANGER_LAG = 8
SIGNIFICANCE = 0.05

PRECOVID_START = "2011-01-01"
PRECOVID_END = "2019-12-31"
POSTCOVID_START = "2022-07-01"


# ============================================================================
# DATA LOADING
# ============================================================================

def load_and_merge():
    """Load FluNet and state GT composites, merge on week_start."""
    flu = pd.read_csv(FLUNET_CSV, parse_dates=["ISO_WEEKSTARTDATE"])
    # Aggregate sentinel + non-sentinel streams by week to prevent duplicate dates
    flu = flu.groupby("ISO_WEEKSTARTDATE")[["INF_ALL"]].sum(min_count=1).dropna()
    flu.index.name = "week_start"

    gt = pd.read_csv(GT_COMPOSITES_CSV, index_col=0, parse_dates=True)
    gt.index.name = "week_start"

    merged = gt.join(flu, how="inner").dropna(subset=["INF_ALL"])
    # Ensure strictly unique chronological index
    merged = merged[~merged.index.duplicated(keep="first")].sort_index()
    state_cols = [c for c in STATE_COLUMNS if c in merged.columns]
    print(f"[MERGE] {len(merged)} aligned unique weeks, {len(state_cols)} states")
    return merged, state_cols


# ============================================================================
# STATIONARITY TESTING (ADF)
# ============================================================================

def adf_test(series, name):
    """Run ADF test on a series."""
    result = adfuller(series.dropna(), autolag="AIC")
    return {
        "series": name,
        "adf_statistic": round(result[0], 4),
        "p_value": round(result[1], 6),
        "lags_used": result[2],
        "n_obs": result[3],
        "critical_5pct": round(result[4]["5%"], 4),
        "stationary_at_5pct": result[1] < 0.05,
    }


def make_stationary(series, name):
    """
    Test stationarity, difference if needed.
    Returns (stationary_series, list_of_adf_dicts, was_differenced).
    """
    adf_results = []
    adf_lev = adf_test(series, f"{name} (level)")
    adf_results.append(adf_lev)

    if adf_lev["stationary_at_5pct"]:
        return series, adf_results, False

    diffed = series.diff().dropna()
    adf_d = adf_test(diffed, f"{name} (1st diff)")
    adf_results.append(adf_d)
    return diffed, adf_results, True


# ============================================================================
# GRANGER CAUSALITY ENGINE
# ============================================================================

def run_granger(cause_series, effect_series, max_lag=MAX_GRANGER_LAG):
    """
    Test: does cause_series Granger-cause effect_series?
    statsmodels expects columns [effect, cause].
    Returns a list of dicts with F-stat and p-value at each lag.
    """
    s_eff = effect_series[~effect_series.index.duplicated(keep="first")]
    s_cau = cause_series[~cause_series.index.duplicated(keep="first")]
    combined = pd.concat([s_eff.rename("effect"), s_cau.rename("cause")], axis=1, join="inner").dropna()

    if len(combined) < max_lag + 30:
        return []

    data = combined[["effect", "cause"]].values

    try:
        with contextlib.redirect_stdout(io.StringIO()):
            results = grangercausalitytests(data, maxlag=max_lag)
    except Exception as e:
        print(f"    [ERROR] {e}")
        return []

    rows = []
    for lag in range(1, max_lag + 1):
        test_dict = results[lag][0]
        f_stat = test_dict["ssr_ftest"][0]
        p_val = test_dict["ssr_ftest"][1]
        chi2_stat = test_dict["ssr_chi2test"][0]
        chi2_p = test_dict["ssr_chi2test"][1]

        rows.append({
            "lag_weeks": lag,
            "f_statistic": round(float(f_stat), 4),
            "f_p_value": float(p_val),
            "f_significant_p05": p_val < SIGNIFICANCE,
            "chi2_statistic": round(float(chi2_stat), 4),
            "chi2_p_value": float(chi2_p),
            "n_obs": len(combined),
        })
    return rows


# ============================================================================
# MAIN
# ============================================================================

def main():
    print("=" * 60)
    print("Phase 3B: Granger Causality — STATE-LEVEL SENTINELS")
    print("=" * 60)

    merged, state_cols = load_and_merge()
    all_adf_results = []
    all_granger_results = []
    summary_rows = []

    # ==================================================================
    # Pre-COVID Analysis (2011–2019)
    # ==================================================================
    precovid = merged.loc[PRECOVID_START:PRECOVID_END].copy()
    print(f"\n{'='*60}")
    print(f"PRE-COVID (2011–2019, {len(precovid)} weeks)")
    print(f"{'='*60}")

    # Stationarity for FluNet (shared across all states)
    flu_stat, adf_flu, flu_diffed = make_stationary(
        precovid["INF_ALL"], "FluNet_PreCOVID")
    all_adf_results.extend(adf_flu)
    flu_label = "1st-diff" if flu_diffed else "level"
    print(f"  FluNet: {flu_label}, ADF p={adf_flu[-1]['p_value']}")

    for state in state_cols:
        print(f"\n  --- {state} ---")

        # Stationarity for this state's GT
        gt_stat, adf_gt, gt_diffed = make_stationary(
            precovid[state], f"GT_{state}_PreCOVID")
        all_adf_results.extend(adf_gt)

        # Align after any differencing
        common_idx = gt_stat.index.intersection(flu_stat.index)
        gt_aligned = gt_stat.loc[common_idx]
        flu_aligned = flu_stat.loc[common_idx]

        diff_applied = gt_diffed or flu_diffed

        # Forward: GT -> Flu
        gc_fwd = run_granger(gt_aligned, flu_aligned)
        for r in gc_fwd:
            r.update({
                "state": state,
                "period": "pre_covid_2011_2019",
                "direction": "GT -> FluNet",
                "differenced": diff_applied,
            })
        all_granger_results.extend(gc_fwd)

        # Reverse: Flu -> GT (control)
        gc_rev = run_granger(flu_aligned, gt_aligned)
        for r in gc_rev:
            r.update({
                "state": state,
                "period": "pre_covid_2011_2019",
                "direction": "FluNet -> GT",
                "differenced": diff_applied,
            })
        all_granger_results.extend(gc_rev)

        # Summarize this state
        if gc_fwd:
            best_fwd = min(gc_fwd, key=lambda x: x["f_p_value"])
            sig_fwd = sum(1 for r in gc_fwd if r["f_significant_p05"])
            fwd_verdict = "GRANGER-CAUSES" if sig_fwd >= 1 else "NO CAUSALITY"
        else:
            best_fwd = {"lag_weeks": None, "f_statistic": None, "f_p_value": 1}
            sig_fwd = 0
            fwd_verdict = "INSUFFICIENT DATA"

        if gc_rev:
            best_rev = min(gc_rev, key=lambda x: x["f_p_value"])
            sig_rev = sum(1 for r in gc_rev if r["f_significant_p05"])
            rev_verdict = "REVERSE-CAUSES" if sig_rev >= 1 else "NO REVERSE"
        else:
            best_rev = {"lag_weeks": None, "f_statistic": None, "f_p_value": 1}
            sig_rev = 0
            rev_verdict = "INSUFFICIENT DATA"

        summary_rows.append({
            "state": state,
            "period": "pre_covid_2011_2019",
            "fwd_best_lag": best_fwd["lag_weeks"],
            "fwd_best_f": best_fwd["f_statistic"],
            "fwd_best_p": best_fwd["f_p_value"],
            "fwd_sig_lags": sig_fwd,
            "fwd_verdict": fwd_verdict,
            "rev_best_lag": best_rev["lag_weeks"],
            "rev_best_f": best_rev["f_statistic"],
            "rev_best_p": best_rev["f_p_value"],
            "rev_sig_lags": sig_rev,
            "rev_verdict": rev_verdict,
            "differenced": diff_applied,
        })

        fwd_sym = "✓" if sig_fwd >= 1 else "✗"
        rev_sym = "✓" if sig_rev >= 1 else "✗"
        print(f"    GT->Flu: F={best_fwd['f_statistic']}, "
              f"p={best_fwd['f_p_value']:.2e}, "
              f"{sig_fwd}/8 sig [{fwd_sym}] | "
              f"Flu->GT: {sig_rev}/8 sig [{rev_sym}]")

    # ==================================================================
    # Post-COVID Analysis (2022-07 onward)
    # ==================================================================
    postcovid = merged.loc[POSTCOVID_START:].copy()
    if len(postcovid) >= 50:
        print(f"\n{'='*60}")
        print(f"POST-COVID (2022-07+, {len(postcovid)} weeks)")
        print(f"{'='*60}")

        flu_stat_p, adf_flu_p, flu_diff_p = make_stationary(
            postcovid["INF_ALL"], "FluNet_PostCOVID")
        all_adf_results.extend(adf_flu_p)

        for state in state_cols:
            print(f"\n  --- {state} ---")
            gt_stat_p, adf_gt_p, gt_diff_p = make_stationary(
                postcovid[state], f"GT_{state}_PostCOVID")
            all_adf_results.extend(adf_gt_p)

            common_idx = gt_stat_p.index.intersection(flu_stat_p.index)
            gt_a = gt_stat_p.loc[common_idx]
            flu_a = flu_stat_p.loc[common_idx]
            diff_applied = gt_diff_p or flu_diff_p

            gc_fwd = run_granger(gt_a, flu_a)
            for r in gc_fwd:
                r.update({
                    "state": state,
                    "period": "post_covid_2022_onward",
                    "direction": "GT -> FluNet",
                    "differenced": diff_applied,
                })
            all_granger_results.extend(gc_fwd)

            if gc_fwd:
                best_p = min(gc_fwd, key=lambda x: x["f_p_value"])
                sig_p = sum(1 for r in gc_fwd if r["f_significant_p05"])

                summary_rows.append({
                    "state": state,
                    "period": "post_covid_2022_onward",
                    "fwd_best_lag": best_p["lag_weeks"],
                    "fwd_best_f": best_p["f_statistic"],
                    "fwd_best_p": best_p["f_p_value"],
                    "fwd_sig_lags": sig_p,
                    "fwd_verdict": "GRANGER-CAUSES" if sig_p >= 1 else "NO CAUSALITY",
                    "rev_best_lag": None,
                    "rev_best_f": None,
                    "rev_best_p": None,
                    "rev_sig_lags": None,
                    "rev_verdict": "NOT TESTED",
                    "differenced": diff_applied,
                })

                sym = "✓" if sig_p >= 1 else "✗"
                print(f"    GT->Flu: F={best_p['f_statistic']}, "
                      f"p={best_p['f_p_value']:.2e}, "
                      f"{sig_p}/8 sig [{sym}]")

    # ==================================================================
    # Save all outputs
    # ==================================================================
    if all_granger_results:
        gc_df = pd.DataFrame(all_granger_results)
        gc_df.to_csv(OUTPUT_DIR / "granger_states_results.csv", index=False)

    if all_adf_results:
        adf_df = pd.DataFrame(all_adf_results)
        adf_df.to_csv(OUTPUT_DIR / "granger_states_stationarity.csv",
                       index=False)

    if summary_rows:
        sum_df = pd.DataFrame(summary_rows)
        sum_df.to_csv(OUTPUT_DIR / "granger_states_summary.csv", index=False)

    print(f"\n{'='*60}")
    print("STATE-LEVEL GRANGER CAUSALITY COMPLETE")
    print(f"{'='*60}")
    print(f"  Results       → {OUTPUT_DIR / 'granger_states_results.csv'}")
    print(f"  Stationarity  → {OUTPUT_DIR / 'granger_states_stationarity.csv'}")
    print(f"  Summary       → {OUTPUT_DIR / 'granger_states_summary.csv'}")
    print()


if __name__ == "__main__":
    main()
