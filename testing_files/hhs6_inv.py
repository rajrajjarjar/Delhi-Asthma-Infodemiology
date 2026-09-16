"""
region6_lag_validation.py
=========================

PURPOSE
-------
US validation test for the BTP methodology, before applying it to Indian data.

Structure of the test (deliberately mirrors the India setup):
    OUTCOME   = HHS Region 6 weekly "% WEIGHTED ILI" from CDC ILINet  (coarse, clean, official)
    PREDICTOR = Google Trends search interest, pulled PER STATE        (granular)
    METHOD    = Spearman rank correlation at multiple week lags, run SEPARATELY per state

The whole point is to see WHICH states lead their own region's flu curve.
So each of the 5 states in HHS Region 6 gets its own lag curve. We deliberately
do NOT average the states into one regional index -- that would collapse exactly
the per-state differences we are trying to detect.

Google Trends has no "HHS Region" geography, so the 5 member states are pulled
individually with US-XX geo codes and compared against the shared regional curve.

LAG SIGN CONVENTION  (read this before interpreting any output)
--------------------------------------------------------------
We correlate  trends[t - lag]  against  ili[t].
    POSITIVE lag  =>  Google Trends LEADS the ILI curve by that many weeks  (useful)
    NEGATIVE lag  =>  Google Trends TRAILS the ILI curve                    (not useful)
A peak at lag = +2 means search activity rose 2 weeks before clinic visits rose.

OUTPUT FILES
------------
    R6_PerState_LagCurves.xlsx      full rho/p-value at every lag, for every state
    R6_BestLagPerState.xlsx         one row per state: its strongest lag (the headline table)
    R6_AlignedTimeSeries.xlsx       the merged week-by-week data actually fed to Spearman
    R6_KeywordVolumeCheck.xlsx      diagnostic: spots keywords squashed to near-zero by Google's scaling
"""

import time

import numpy as np
import pandas as pd
from pytrends.request import TrendReq
from scipy.stats import spearmanr

# ============================================================================
# CONFIGURATION
# ============================================================================

CSV_FILE = 'E:/Projects/BTP/testing_files/fluuu/ILLnet2.2.csv'

REGION = 'Region 6'

# The 5 states that make up HHS Region 6. Google Trends geo codes.
# Each is analysed separately -- this list drives the per-state loop.
STATES = {
    'US-TX': 'Texas',
    'US-LA': 'Louisiana',
    'US-AR': 'Arkansas',
    'US-NM': 'New Mexico',
    'US-OK': 'Oklahoma',
}

# stop at 2019: COVID destroys both signals from 2020
START_YR, END_YR = 2015, 2019
START_DATE, END_DATE = '2015-01-04', '2019-12-28'

# Symptom-first keyword set. Deliberately excludes vaccine/news-driven terms
# ("flu shot", "bird flu", "flu deaths") which spike on media and campaign
# schedules rather than on actual illness -- the classic Google Flu Trends failure.
TARGET_KWS = [
    'flu symptoms', 'fever', 'sore throat', 'body aches',
    'chills', 'cough', 'how long does flu last', 'flu or cold',
]

# Anchor term used to put separately-pulled queries onto a comparable scale.
# MUST be seasonally FLAT. 'weather' is a bad anchor -- it has its own strong
# winter/summer cycle, which would inject fake seasonality into the predictor.
ANCHOR_KW = 'youtube'

MAX_LAG = 8              # +/- 8 weeks, wide enough to confirm a peak is a real peak
REQUEST_PAUSE_SEC = 2    # politeness delay between Google Trends calls


# ============================================================================
# 1. CDC SIDE -- build the Region 6 outcome curve, keyed by real calendar date
# ============================================================================

def mmwr_week_start_date(year: int, week: int) -> pd.Timestamp:
    """
    Convert an MMWR (epi) year+week into the actual Sunday that week starts on.

    Why this matters: the previous version merged CDC rows to Google Trends rows
    by POSITION (row 0 to row 0, row 1 to row 1). That silently breaks whenever
    the two sources have different row counts -- e.g. 2014 has 53 MMWR weeks, so
    extending the window by one year shifts every subsequent row by a week with
    no error raised. Merging on a real date makes misalignment impossible.

    MMWR rule: week 1 is the week (Sunday-start) containing January 4th.
    """
    jan4 = pd.Timestamp(year=year, month=1, day=4)
    # pandas: Monday=0 ... Sunday=6. Step back to the Sunday on/before Jan 4.
    days_since_sunday = (jan4.dayofweek + 1) % 7
    week1_start = jan4 - pd.Timedelta(days=days_since_sunday)
    return week1_start + pd.Timedelta(weeks=week - 1)


def get_cdc_target() -> pd.DataFrame:
    """
    Load ILINet and return the Region 6 weekly ILI curve.

    Uses '% WEIGHTED ILI' because this is HHS-Region-level data, where CDC
    publishes the population-weighted figure. (At state level that column is
    blank and you must use '%UNWEIGHTED ILI' instead.)
    """
    print(f"[CDC] Loading {REGION} from ILINet ...")
    # row 0 is a title banner, not the header
    df = pd.read_csv(CSV_FILE, skiprows=1)

    df = df[
        (df['REGION'] == REGION)
        & (df['YEAR'] >= START_YR)
        & (df['YEAR'] <= END_YR)
    ].copy()

    # CDC uses 'X' for missing values -- coerce so they become NaN, not strings.
    df['ili_percent'] = pd.to_numeric(df['% WEIGHTED ILI'], errors='coerce')

    # Attach the real week-start date so we can merge on it later.
    df['week_start'] = [
        mmwr_week_start_date(int(y), int(w))
        for y, w in zip(df['YEAR'], df['WEEK'])
    ]

    df = df.sort_values('week_start').reset_index(drop=True)

    print(f"[CDC] {len(df)} weeks loaded "
          f"({df['week_start'].min().date()} to {df['week_start'].max().date()})")

    return df[['week_start', 'YEAR', 'WEEK', 'ili_percent']]


# ============================================================================
# 2. GOOGLE TRENDS SIDE -- one composite search index per state
# ============================================================================

def build_pytrends_client() -> TrendReq:
    """
    Construct the pytrends client.

    Newer pytrends releases removed the retries/backoff_factor kwargs, so we try
    the richer signature first and quietly fall back rather than crashing.
    """
    try:
        return TrendReq(hl='en-US', tz=360, retries=3, backoff_factor=1)
    except TypeError:
        return TrendReq(hl='en-US', tz=360)


def fetch_state_composite(pytrends: TrendReq, geo: str, label: str):
    """
    Pull all 8 keywords for ONE state and reduce them to a single composite index.

    Returns (composite_series, raw_volume_diagnostics).

    Two-stage normalisation, and both stages exist for a specific reason:

      STAGE 1 -- divide by the anchor term.
        Google rescales every query to 0-100 independently, so a pull for Texas
        and a pull for Oklahoma are NOT on a shared scale. Including the same
        anchor term in every request and dividing by it puts all states onto a
        common footing.

      STAGE 2 -- z-score each keyword before averaging them.
        'fever' and 'cough' have far higher search volume than
        'how long does flu last'. A plain mean of the raw normalised columns is
        therefore dominated by the two loudest terms, and the rest just add
        rounding noise. Z-scoring first gives every keyword equal weight in the
        composite, which is what we actually want.
    """
    timeframe = f'{START_DATE} {END_DATE}'

    # Google allows max 5 terms per request, and 1 slot is reserved for the
    # anchor, so the 8 keywords are pulled in chunks of 4.
    kw_chunks = [TARGET_KWS[i:i + 4] for i in range(0, len(TARGET_KWS), 4)]

    normalised_cols = {}
    raw_means = {}

    for chunk in kw_chunks:
        payload = [ANCHOR_KW] + chunk
        pytrends.build_payload(kw_list=payload, geo=geo, timeframe=timeframe)
        df_gt = pytrends.interest_over_time()

        if df_gt.empty:
            print(f"  [WARN] {label}: empty response for {chunk}")
            continue

        df_gt = df_gt.drop(columns=['isPartial'], errors='ignore')

        anchor = df_gt[ANCHOR_KW].astype(float)

        for kw in chunk:
            series = df_gt[kw].astype(float)

            # Diagnostic: if a keyword's raw mean is ~0, Google has quantised it
            # into near-nothing and it is contributing noise rather than signal.
            raw_means[kw] = series.mean()

            # Stage 1: anchor normalisation. +1 guards against divide-by-zero.
            normalised_cols[kw] = series / (anchor + 1.0)

        time.sleep(REQUEST_PAUSE_SEC)

    if not normalised_cols:
        return None, raw_means

    df_norm = pd.DataFrame(normalised_cols)

    # Stage 2: z-score each keyword, then average into one composite per week.
    df_z = (df_norm - df_norm.mean()) / df_norm.std(ddof=0)
    composite = df_z.mean(axis=1)
    composite.name = label

    return composite, raw_means


def fetch_all_states():
    """
    Loop every state in the region and collect its composite index.

    Crucially, each state's series is kept SEPARATE. The earlier version averaged
    them into a single 'regional_index', which made it impossible to tell whether
    Texas leads the curve more than Oklahoma does -- i.e. it erased the finding
    the whole experiment is meant to produce.
    """
    pytrends = build_pytrends_client()

    state_series = {}
    volume_report = []

    for geo, name in STATES.items():
        print(f"[TRENDS] Fetching {name} ({geo}) ...")
        composite, raw_means = fetch_state_composite(pytrends, geo, name)

        for kw, mean_val in raw_means.items():
            volume_report.append({
                'state': name,
                'keyword': kw,
                'raw_mean_0_100': round(mean_val, 3),
                # Flag terms Google has squashed so low they carry little information.
                'possibly_too_sparse': mean_val < 1.0,
            })

        if composite is not None:
            state_series[name] = composite

    df_states = pd.DataFrame(state_series)
    df_states.index.name = 'week_start'
    df_states = df_states.reset_index()

    # Google Trends returns week-START dates (Sundays), matching our MMWR
    # week_start, so this column merges cleanly against the CDC frame.
    df_states['week_start'] = pd.to_datetime(df_states['week_start'])

    return df_states, pd.DataFrame(volume_report)


# ============================================================================
# 3. LAG ANALYSIS -- one Spearman curve per state
# ============================================================================

def run_per_state_lag(merged: pd.DataFrame, state_names, max_lag=MAX_LAG):
    """
    For each state, correlate its search composite against the SHARED Region 6
    ILI curve across a range of week lags.

    Sign convention (repeated here because it is the easiest thing to get wrong):
        shift(+lag) moves values forward in time, so row t holds trends[t - lag].
        Correlating that against ili[t] therefore tests
        "did search activity `lag` weeks ago track flu activity now?"
        => POSITIVE lag = Trends LEADS ILI.
    """
    rows = []

    for state in state_names:
        for lag in range(-max_lag, max_lag + 1):
            shifted = merged[state].shift(lag)

            valid = shifted.notna() & merged['ili_percent'].notna()
            n_obs = int(valid.sum())

            # Guard: very small overlaps produce meaningless correlations.
            if n_obs < 30:
                continue

            rho, p_val = spearmanr(
                shifted[valid], merged['ili_percent'][valid])

            rows.append({
                'state': state,
                'lag_weeks': lag,
                'spearman_rho': round(float(rho), 4),
                'p_value': float(p_val),
                'n_weeks': n_obs,
                'significant_p05': p_val < 0.05,
            })

    return pd.DataFrame(rows)


def summarise_best_lag(lag_curves: pd.DataFrame) -> pd.DataFrame:
    """
    Reduce each state's full lag curve to its single strongest lag.

    This is the headline table: it is what tells you which states behave as
    leading indicators, which is the exact question the India phase will ask.
    """
    summaries = []

    for state, grp in lag_curves.groupby('state'):
        best = grp.loc[grp['spearman_rho'].idxmax()]

        summaries.append({
            'state': state,
            'best_lag_weeks': int(best['lag_weeks']),
            'spearman_rho': best['spearman_rho'],
            'p_value': best['p_value'],
            'leads_or_trails': (
                'LEADS' if best['lag_weeks'] > 0
                else 'TRAILS' if best['lag_weeks'] < 0
                else 'SYNCHRONOUS'
            ),
            'significant_p05': bool(best['significant_p05']),
        })

    return (pd.DataFrame(summaries)
            .sort_values('spearman_rho', ascending=False)
            .reset_index(drop=True))


# ============================================================================
# EXECUTE
# ============================================================================

if __name__ == "__main__":

    # --- Outcome variable: the shared Region 6 curve ---
    cdc_df = get_cdc_target()

    # --- Predictor variables: one composite per state ---
    trends_df, volume_df = fetch_all_states()

    # --- Align on real dates, never on row position ---
    merged = pd.merge(cdc_df, trends_df, on='week_start', how='inner')
    merged = merged.sort_values('week_start').reset_index(drop=True)

    print(f"\n[MERGE] {len(merged)} weeks aligned on week_start "
          f"(CDC had {len(cdc_df)}, Trends had {len(trends_df)})")

    if len(merged) < 100:
        print(
            "[WARN] Few overlapping weeks -- check that both sources cover the same window.")

    state_names = [name for name in STATES.values() if name in merged.columns]

    # --- Lag analysis, per state ---
    lag_curves = run_per_state_lag(merged, state_names)
    best_lags = summarise_best_lag(lag_curves)

    print("\n=== HHS REGION 6 :: BEST LAG PER STATE ===")
    print("(positive lag = Google Trends leads the ILI curve)\n")
    print(best_lags.to_string(index=False))

    # --- Save everything with self-describing filenames ---
    lag_curves.to_excel("R6_PerState_LagCurves.xlsx", index=False)
    best_lags.to_excel("R6_BestLagPerState.xlsx", index=False)
    merged.to_excel("R6_AlignedTimeSeries.xlsx", index=False)
    volume_df.to_excel("R6_KeywordVolumeCheck.xlsx", index=False)

    print("\nSaved:")
    print("  R6_BestLagPerState.xlsx      <- headline result, read this first")
    print("  R6_PerState_LagCurves.xlsx   <- full rho vs lag, for plotting")
    print("  R6_AlignedTimeSeries.xlsx    <- week-by-week aligned data")
    print("  R6_KeywordVolumeCheck.xlsx   <- check 'possibly_too_sparse' column")
