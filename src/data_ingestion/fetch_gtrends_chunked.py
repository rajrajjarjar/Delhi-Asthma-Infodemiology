"""
fetch_gtrends_chunked.py
========================
Phase 1 of the BTP India pipeline: fetch 16 years of weekly Google Trends data
(2010–2026) by pulling in overlapping ≤5-year chunks, rescaling across the
overlaps, and stitching into a single seamless weekly time series per state.

WHY CHUNKING IS MANDATORY
--------------------------
Google Trends silently degrades weekly resolution to monthly when a single
query spans more than ~5 years. This was empirically verified in the
preflight test (experiments/gtrends_preflight/). The workaround:

  1. Pull in ≤5-year windows with 1-year overlaps.
  2. Within each window, normalise every keyword against a seasonally-flat
     anchor term ('youtube') so that separately-pulled states and chunks
     land on a comparable scale.
  3. Across adjacent chunks, use the 1-year overlap to compute a rescaling
     ratio that corrects for the arbitrary 0–100 renormalisation Google
     applies to each independent query.
  4. Z-score each keyword before averaging into a composite, so loud terms
     like 'fever' don't drown out narrower terms like 'viral fever'.

CHUNK PLAN (4 chunks, 3 overlaps)
----------------------------------
  Chunk 1: 2010-01-01 to 2014-12-31  (reference scale)
  Chunk 2: 2014-01-01 to 2018-12-31  (overlap: 2014)
  Chunk 3: 2018-01-01 to 2022-12-31  (overlap: 2018)
  Chunk 4: 2022-01-01 to 2026-06-30  (overlap: 2022; end trimmed to present)

DATE ALIGNMENT
--------------
Google Trends returns Sunday-start weeks. FluNet uses Monday-start ISO weeks.
To merge later, we shift GT dates forward by 1 day to align to Monday, then
round down to the nearest Monday to guarantee clean joins.

OUTPUT FILES
------------
  Data/processed/gtrends/
    {state_geo}_raw_chunks.csv       - per-chunk raw data (debugging)
    {state_geo}_stitched.csv         - final stitched weekly series
    all_states_composites.csv        - all states' composites in one file
    stitching_diagnostics.csv        - overlap ratios and scaling factors

RUN INSTRUCTIONS
----------------
  cd E:\\Projects\\BTP
  .\\.venv\\Scripts\\python.exe src/data_ingestion/fetch_gtrends_chunked.py

  Expect ~15–20 minutes (7 states × 4 chunks × 2 keyword batches × 5s delay).
  If Google rate-limits (429), the script pauses for 60s and retries. If you
  get persistent 429s, wait 5 minutes and re-run; it resumes from the last
  saved chunk automatically.
"""

import time
import random
import json
from pathlib import Path
from datetime import datetime

import numpy as np
import pandas as pd
from pytrends.request import TrendReq

# ============================================================================
# CONFIGURATION
# ============================================================================

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

# Output directories
RAW_CHUNKS_DIR = PROJECT_ROOT / "Data" / "processed" / "gtrends" / "raw_chunks"
OUTPUT_DIR = PROJECT_ROOT / "Data" / "processed" / "gtrends"
RAW_CHUNKS_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Chunk definitions: (start_date, end_date)
CHUNKS = [
    ("2010-01-01", "2014-12-31"),
    ("2014-01-01", "2018-12-31"),
    ("2018-01-01", "2022-12-31"),
    ("2022-01-01", "2026-06-30"),
]

# States to query
STATES = {
    "IN-DL": "Delhi",
    "IN-UP": "Uttar Pradesh",
    "IN-BR": "Bihar",
    "IN-MH": "Maharashtra",
    "IN-KL": "Kerala",
    "IN-TN": "Tamil Nadu",
    "IN-WB": "West Bengal",
}

# English symptom keywords (pulled for ALL states)
ENGLISH_KEYWORDS = ["flu", "fever", "cough", "viral fever"]

# Hindi symptom keywords (pulled ONLY for Hindi-belt states)
HINDI_KEYWORDS = ["बुखार", "खांसी"]
HINDI_BELT_GEOS = {"IN-DL", "IN-UP", "IN-BR"}

# Anchor keyword: must be seasonally flat. 'youtube' is ideal because it has
# near-constant search volume year-round. 'weather' is a BAD anchor -- it has
# its own winter/summer cycle that would inject fake seasonality.
ANCHOR_KW = "youtube"

# pytrends can send at most 5 keywords per request; 1 slot is the anchor.
# So we batch the remaining keywords in groups of 4.
MAX_KW_PER_REQUEST = 4

# Rate limit protection
PAUSE_BETWEEN_REQUESTS = 5    # seconds between individual API calls
PAUSE_BETWEEN_STATES = 10     # seconds between states
PAUSE_ON_429 = 60             # seconds to wait on rate-limit error
MAX_RETRIES = 5               # retries per individual request


# ============================================================================
# PYTRENDS HELPERS
# ============================================================================

def get_pytrends_client():
    """Create a fresh pytrends client."""
    try:
        return TrendReq(hl="en-US", tz=330, retries=3, backoff_factor=1)
    except TypeError:
        return TrendReq(hl="en-US", tz=330)


def safe_fetch(pytrends, kw_list, geo, timeframe, max_retries=MAX_RETRIES):
    """
    Fetch interest_over_time with exponential backoff.
    Returns a DataFrame or None on persistent failure.
    """
    for attempt in range(max_retries):
        try:
            pytrends.build_payload(kw_list, geo=geo, timeframe=timeframe)
            df = pytrends.interest_over_time()
            if df is not None and not df.empty:
                return df.drop(columns=["isPartial"], errors="ignore")
            return None
        except Exception as e:
            err_str = str(e)
            if "429" in err_str:
                wait = PAUSE_ON_429 + random.uniform(0, 10)
                print(f"    [429 RATE LIMIT] Waiting {wait:.0f}s before retry "
                      f"{attempt+1}/{max_retries}...")
            else:
                wait = (2 ** attempt) + random.uniform(1, 3)
                print(f"    [ERROR] {e} — retrying in {wait:.1f}s "
                      f"({attempt+1}/{max_retries})")
            time.sleep(wait)

            # Get fresh cookies after a 429
            if "429" in err_str:
                try:
                    pytrends = get_pytrends_client()
                except Exception:
                    pass

    return None


# ============================================================================
# CORE LOGIC: FETCH ONE CHUNK FOR ONE STATE
# ============================================================================

def fetch_chunk_for_state(pytrends, geo, state_name, chunk_start, chunk_end):
    """
    Pull all keywords (English + Hindi if applicable) for one state and
    one time chunk. Returns a DataFrame indexed by date with one column
    per keyword (anchor-normalised).

    Keywords are batched in groups of 4 (+ anchor = 5 per request).
    """
    timeframe = f"{chunk_start} {chunk_end}"

    # Decide which keywords to pull for this state
    keywords = list(ENGLISH_KEYWORDS)
    if geo in HINDI_BELT_GEOS:
        keywords.extend(HINDI_KEYWORDS)

    # Batch keywords: each batch = [anchor] + up to 4 keywords
    batches = []
    for i in range(0, len(keywords), MAX_KW_PER_REQUEST):
        batches.append(keywords[i:i + MAX_KW_PER_REQUEST])

    all_normalised = {}

    for batch in batches:
        payload = [ANCHOR_KW] + batch
        print(f"    Fetching {state_name}: {batch} ...")
        df = safe_fetch(pytrends, payload, geo=geo, timeframe=timeframe)

        if df is None:
            print(f"    [WARN] No data returned for {state_name} {batch} "
                  f"in {chunk_start}–{chunk_end}")
            continue

        anchor_series = df[ANCHOR_KW].astype(float)

        for kw in batch:
            if kw not in df.columns:
                continue
            raw = df[kw].astype(float)
            # Anchor normalisation: divide by anchor (+1 to avoid div-by-zero)
            normalised = raw / (anchor_series + 1.0)
            all_normalised[kw] = normalised

        time.sleep(PAUSE_BETWEEN_REQUESTS)

    if not all_normalised:
        return None

    return pd.DataFrame(all_normalised)


# ============================================================================
# Z-SCORE COMPOSITE: COMBINE KEYWORDS INTO ONE SIGNAL PER STATE
# ============================================================================

def compute_composite(df_normalised):
    """
    Z-score each keyword column, then average into a single composite index.

    Why z-score first: 'fever' has much higher raw volume than 'viral fever'.
    Without z-scoring, the composite would be dominated by the loudest term
    and the quieter terms would just add rounding noise.
    """
    if df_normalised is None or df_normalised.empty:
        return None

    # Drop columns that are all-zero (term returned no signal in this chunk)
    nonzero_cols = [c for c in df_normalised.columns
                    if (df_normalised[c] != 0).any()]
    if not nonzero_cols:
        return None

    df = df_normalised[nonzero_cols].copy()

    # Z-score each keyword
    df_z = (df - df.mean()) / df.std(ddof=0).replace(0, 1)

    # Average across all z-scored keywords → one composite per week
    composite = df_z.mean(axis=1)
    composite.name = "composite"
    return composite


# ============================================================================
# STITCHING: RESCALE AND JOIN CHUNKS
# ============================================================================

def stitch_chunks(chunk_composites, chunk_ranges):
    """
    Stitch multiple overlapping chunk composites into one continuous series.

    Method:
      - Chunk 0 is the reference scale.
      - For each subsequent chunk, compute a scaling factor from the overlap
        region: factor = median(chunk_prev_overlap) / median(chunk_curr_overlap).
      - Multiply the new chunk by this factor.
      - In the overlap zone, keep the previous chunk's values (they are on
        the reference scale already).
      - Append the non-overlapping portion of the new chunk.
    """
    if not chunk_composites:
        return None, []

    stitched = chunk_composites[0].copy()
    diagnostics = []

    for i in range(1, len(chunk_composites)):
        curr = chunk_composites[i]
        if curr is None:
            diagnostics.append({
                "chunk": i, "overlap_start": None, "overlap_end": None,
                "scaling_factor": None, "status": "SKIPPED_NO_DATA"
            })
            continue

        # Find the overlap dates
        overlap_dates = stitched.index.intersection(curr.index)

        if len(overlap_dates) < 10:
            # Not enough overlap to compute a reliable ratio
            diagnostics.append({
                "chunk": i,
                "overlap_weeks": len(overlap_dates),
                "scaling_factor": None,
                "status": "INSUFFICIENT_OVERLAP"
            })
            # Still append the new chunk unscaled (better than losing it)
            new_dates = curr.index.difference(stitched.index)
            stitched = pd.concat([stitched, curr.loc[new_dates]])
            continue

        # Compute scaling factor from overlap medians
        prev_median = stitched.loc[overlap_dates].median()
        curr_median = curr.loc[overlap_dates].median()

        if curr_median == 0 or np.isnan(curr_median):
            scaling_factor = 1.0
        else:
            scaling_factor = prev_median / curr_median

        diagnostics.append({
            "chunk": i,
            "overlap_start": str(overlap_dates.min().date()),
            "overlap_end": str(overlap_dates.max().date()),
            "overlap_weeks": len(overlap_dates),
            "prev_median": round(float(prev_median), 4),
            "curr_median": round(float(curr_median), 4),
            "scaling_factor": round(float(scaling_factor), 4),
            "status": "OK"
        })

        # Rescale the current chunk
        curr_scaled = curr * scaling_factor

        # Append only the non-overlapping portion (keep prev values in overlap)
        new_dates = curr_scaled.index.difference(stitched.index)
        stitched = pd.concat([stitched, curr_scaled.loc[new_dates]])

    stitched = stitched.sort_index()
    return stitched, diagnostics


# ============================================================================
# DATE ALIGNMENT: GT SUNDAY → FLUNET MONDAY
# ============================================================================

def align_to_monday(series):
    """
    Google Trends returns Sunday-start weeks. FluNet uses Monday-start ISO
    weeks. Shift GT dates forward by 1 day so both datasets key on Monday.
    """
    series = series.copy()
    series.index = series.index + pd.Timedelta(days=1)
    return series


# ============================================================================
# RESUME LOGIC: SKIP ALREADY-FETCHED CHUNKS
# ============================================================================

def chunk_cache_path(geo, chunk_idx):
    return RAW_CHUNKS_DIR / f"{geo}_chunk{chunk_idx}.csv"


def load_cached_chunk(geo, chunk_idx):
    path = chunk_cache_path(geo, chunk_idx)
    if path.exists():
        df = pd.read_csv(path, index_col=0, parse_dates=True)
        return df
    return None


def save_chunk_cache(df, geo, chunk_idx):
    path = chunk_cache_path(geo, chunk_idx)
    df.to_csv(path)


# ============================================================================
# MAIN
# ============================================================================

def main():
    print("=" * 60)
    print("BTP — 16-Year Chunked Google Trends Ingestion Pipeline")
    print("=" * 60)
    print(f"States: {list(STATES.values())}")
    print(f"Chunks: {len(CHUNKS)} ({CHUNKS[0][0]} to {CHUNKS[-1][1]})")
    print(f"Keywords (English): {ENGLISH_KEYWORDS}")
    print(f"Keywords (Hindi, for {list(HINDI_BELT_GEOS)}): {HINDI_KEYWORDS}")
    print(f"Anchor: '{ANCHOR_KW}'")
    print(f"Output: {OUTPUT_DIR}")
    print()

    pytrends = get_pytrends_client()
    all_state_composites = {}
    all_diagnostics = []

    for geo, state_name in STATES.items():
        print(f"\n{'='*50}")
        print(f"STATE: {state_name} ({geo})")
        print(f"{'='*50}")

        chunk_composites = []

        for chunk_idx, (c_start, c_end) in enumerate(CHUNKS):
            print(
                f"\n  Chunk {chunk_idx+1}/{len(CHUNKS)}: {c_start} → {c_end}")

            # Check cache first (resume support)
            cached = load_cached_chunk(geo, chunk_idx)
            if cached is not None:
                print(
                    f"    [CACHE HIT] Loaded from {chunk_cache_path(geo, chunk_idx)}")
                composite = compute_composite(cached)
                chunk_composites.append(composite)
                continue

            # Fetch fresh data
            df_norm = fetch_chunk_for_state(
                pytrends, geo, state_name, c_start, c_end
            )

            if df_norm is not None:
                save_chunk_cache(df_norm, geo, chunk_idx)
                print(
                    f"    Saved {len(df_norm)} weeks × {len(df_norm.columns)} keywords")
                composite = compute_composite(df_norm)
                chunk_composites.append(composite)
            else:
                print(f"    [WARN] No data for this chunk")
                chunk_composites.append(None)

            # Polite pause between chunks
            time.sleep(PAUSE_BETWEEN_STATES)

        # Stitch chunks together
        print(f"\n  Stitching {sum(1 for c in chunk_composites if c is not None)} "
              f"chunks for {state_name}...")
        # Filter out None chunks
        valid_composites = [c for c in chunk_composites if c is not None]

        if not valid_composites:
            print(f"  [ERROR] No valid chunks for {state_name}. Skipping.")
            continue

        stitched, diagnostics = stitch_chunks(valid_composites, CHUNKS)

        # Record diagnostics
        for d in diagnostics:
            d["state"] = state_name
            d["geo"] = geo
        all_diagnostics.extend(diagnostics)

        # Align Sunday → Monday for FluNet compatibility
        stitched = align_to_monday(stitched)

        # Save per-state stitched series
        state_csv = OUTPUT_DIR / f"{geo.replace('-', '_')}_stitched.csv"
        stitched_df = stitched.to_frame(name=f"composite_{state_name}")
        stitched_df.index.name = "week_start"
        stitched_df.to_csv(state_csv)
        print(f"  Saved: {state_csv}")
        print(
            f"  Date range: {stitched.index.min().date()} → {stitched.index.max().date()}")
        print(f"  Total weeks: {len(stitched)}")

        all_state_composites[state_name] = stitched

    # ---- Combined output: all states in one file ----
    if all_state_composites:
        combined = pd.DataFrame(all_state_composites)
        combined.index.name = "week_start"
        combined_path = OUTPUT_DIR / "all_states_composites.csv"
        combined.to_csv(combined_path)
        print(f"\n{'='*60}")
        print(f"COMBINED OUTPUT: {combined_path}")
        print(f"Shape: {combined.shape}")
        print(
            f"Date range: {combined.index.min().date()} → {combined.index.max().date()}")
        print(f"{'='*60}")

    # ---- Save diagnostics ----
    if all_diagnostics:
        diag_df = pd.DataFrame(all_diagnostics)
        diag_path = OUTPUT_DIR / "stitching_diagnostics.csv"
        diag_df.to_csv(diag_path, index=False)
        print(f"\nStitching diagnostics: {diag_path}")
        print(diag_df.to_string(index=False))

    print("\n✓ Pipeline complete.")


if __name__ == "__main__":
    main()
