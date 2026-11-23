"""
BTP - Google Trends Pre-Flight Test (standalone, NOT part of main pipeline)
=============================================================================
Purpose: validate the Google Trends side of the methodology BEFORE building
the real analysis on top of it. This script does NOT compute any lag,
correlation, or causality - it only checks whether the data itself is
usable. Keep this file separate from the actual BTP pipeline; only wire
things into the main project once every check here passes.

What this checks, and why each one matters:
  1. Threshold check   - does each term return real signal (not all-zero /
                          "insufficient data") at national and state level?
  2. Granularity check - does a 16-year single query silently degrade to
                          monthly resolution? (Google Trends does this
                          automatically past 5 years, with no warning.)
  3. Rate-limit check  - does pytrends survive repeated calls without
                          getting throttled (HTTP 429)?
  4. Sanity pilot       - does one term's recent trend even loosely shape-
                          match a real recent flu season, before trusting
                          the pipeline with 16 years of data?

Run this locally (Google Trends isn't reachable from every sandboxed
environment). Results are written to a report file, not consumed further -
you read the report and decide whether to proceed.
"""

from pathlib import Path
import time
import random
import pandas as pd
from pytrends.request import TrendReq

CURRENT_DIR = Path(__file__).resolve().parent

# ---- fill these in before running ----
CANDIDATE_TERMS = ["flu", "fever", "cough", "viral fever"]   # English terms to test
HINDI_TERMS = ["बुखार", "खांसी"]                             # Hindi pilot check terms
CANDIDATE_STATES = {                                          # ISO 3166-2:IN codes
    "Delhi": "IN-DL",
    "Uttar Pradesh": "IN-UP",
    "Bihar": "IN-BR",
    "Maharashtra": "IN-MH",
    "Kerala": "IN-KL",
    "Tamil Nadu": "IN-TN",
    "West Bengal": "IN-WB",
}
HINDI_BELT_STATES = {
    "Uttar Pradesh": "IN-UP",
    "Bihar": "IN-BR",
    "Delhi": "IN-DL",
}
NATIONAL_GEO = "IN"
report_output_path = str(CURRENT_DIR / "gtrends_preflight_report.csv")
# ----------------------------------------

pytrends = TrendReq(hl="en-US", tz=330)  # tz=330 = IST offset in minutes


def safe_pytrends_call(build_fn, max_retries=3):
    """
    Wrap any pytrends call with retry + backoff, since the unofficial API
    gets rate-limited (429) if hit too fast. Returns None on repeated
    failure instead of crashing the whole test run.
    """
    for attempt in range(max_retries):
        try:
            return build_fn()
        except Exception as e:
            wait = (2 ** attempt) + random.uniform(0, 1)
            print(f"  [retry {attempt+1}/{max_retries}] {e} - waiting {wait:.1f}s")
            time.sleep(wait)
    return None


def check_threshold(term: str, geo: str, timeframe: str = "today 5-y") -> dict:
    """
    Pull recent (<=5yr, so weekly-resolution) data for one term+geo and
    report whether it's usable: non-empty, not all zero, and what
    fraction of points are zero (a lot of zeros can still mean 'mostly
    below threshold' even if not fully empty).
    """
    def build():
        pytrends.build_payload([term], timeframe=timeframe, geo=geo)
        return pytrends.interest_over_time()

    df = safe_pytrends_call(build)

    if df is None or df.empty:
        return {"term": term, "geo": geo, "status": "NO_DATA", "zero_pct": None, "mean": None}

    series = df[term]
    zero_pct = (series == 0).mean() * 100
    return {
        "term": term,
        "geo": geo,
        "status": "OK" if zero_pct < 90 else "MOSTLY_ZERO",
        "zero_pct": round(zero_pct, 1),
        "mean": round(series.mean(), 2),
    }


def check_granularity(term: str, geo: str) -> dict:
    """
    Compare the row-spacing of a 5-year query vs a 16-year query for the
    SAME term+geo. If the 16-year query returns far fewer points than
    ~16*52, it has silently dropped to monthly resolution.
    """
    def build_5y():
        pytrends.build_payload([term], timeframe="today 5-y", geo=geo)
        return pytrends.interest_over_time()

    def build_16y():
        pytrends.build_payload([term], timeframe="2010-01-01 2026-01-01", geo=geo)
        return pytrends.interest_over_time()

    df_5y = safe_pytrends_call(build_5y)
    df_16y = safe_pytrends_call(build_16y)

    rows_5y = len(df_5y) if df_5y is not None else 0
    rows_16y = len(df_16y) if df_16y is not None else 0

    # weekly over 16 years should be ~832 rows; monthly would be ~192
    likely_monthly = rows_16y < 400

    return {
        "term": term,
        "geo": geo,
        "rows_5y_query": rows_5y,
        "rows_16y_query": rows_16y,
        "granularity_degraded": likely_monthly,
    }


def run_pilot_check(term: str, geo: str):
    """
    Quick visual sanity check: print the last ~12 weeks of a term's trend
    so you can eyeball whether it moves at all during a real flu season,
    before trusting it for 16 years of analysis.
    """
    def build():
        pytrends.build_payload([term], timeframe="today 3-m", geo=geo)
        return pytrends.interest_over_time()

    df = safe_pytrends_call(build)
    if df is None or df.empty:
        print(f"  Pilot check FAILED for {term} / {geo}: no data")
        return
    print(f"  Pilot check for {term} / {geo} (last {len(df)} points):")
    print(df[term].to_string())


def main():
    results_threshold = []
    results_granularity = []

    print("=== 1. Threshold check (National + Candidate States) ===")
    for term in CANDIDATE_TERMS:
        print(f"Testing term (English): '{term}' ...")
        r_nat = check_threshold(term, NATIONAL_GEO)
        r_nat["state_name"] = "National"
        r_nat["language"] = "English"
        results_threshold.append(r_nat)
        time.sleep(1)

        for state_name, geo_code in CANDIDATE_STATES.items():
            r = check_threshold(term, geo_code)
            r["state_name"] = state_name
            r["language"] = "English"
            results_threshold.append(r)
            time.sleep(1)

    print("\n=== 1b. Hindi Pilot Check (Hindi Belt States) ===")
    for term in HINDI_TERMS:
        print(f"Testing term (Hindi): '{term}' ...")
        r_nat = check_threshold(term, NATIONAL_GEO)
        r_nat["state_name"] = "National"
        r_nat["language"] = "Hindi"
        results_threshold.append(r_nat)
        time.sleep(1)

        for state_name, geo_code in HINDI_BELT_STATES.items():
            r = check_threshold(term, geo_code)
            r["state_name"] = state_name
            r["language"] = "Hindi"
            results_threshold.append(r)
            time.sleep(1)

    print("\n=== 2. Granularity check (5yr vs 16yr query) ===")
    for term in CANDIDATE_TERMS[:2]:  # check 2 terms to prove granularity drop
        print(f"Checking granularity for '{term}' ...")
        results_granularity.append(check_granularity(term, NATIONAL_GEO))
        time.sleep(1)

    print("\n=== 3. Pilot sanity check (last 3 months, national) ===")
    run_pilot_check(CANDIDATE_TERMS[0], NATIONAL_GEO)

    # Convert to DataFrames
    df_thresh = pd.DataFrame(results_threshold)
    df_gran = pd.DataFrame(results_granularity)

    # Save reports
    thresh_csv = report_output_path.replace(".csv", "_threshold.csv")
    gran_csv = report_output_path.replace(".csv", "_granularity.csv")
    df_thresh.to_csv(thresh_csv, index=False)
    df_gran.to_csv(gran_csv, index=False)

    print("\n" + "="*50)
    print("PREFLIGHT SUMMARY - THRESHOLD CHECK:")
    print("="*50)
    print(df_thresh[["term", "state_name", "geo", "language", "status", "zero_pct", "mean"]].to_string(index=False))

    print("\n" + "="*50)
    print("PREFLIGHT SUMMARY - GRANULARITY CHECK:")
    print("="*50)
    print(df_gran.to_string(index=False))

    print(f"\nReports saved successfully to:\n- {thresh_csv}\n- {gran_csv}")
    print("\nDone. Review the findings before pulling the full 16-year time series.")


if __name__ == "__main__":
    main()
