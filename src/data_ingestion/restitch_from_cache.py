"""
restitch_from_cache.py
======================
Reads the already-fetched raw chunk CSVs from Data/processed/gtrends/raw_chunks/
and re-stitches them with the CORRECTED pipeline order:

  1. Average anchor-normalised keywords into a raw composite (all positive).
  2. Stitch chunks using median-ratio rescaling on the overlap year.
  3. Z-score the FINAL stitched 16-year series (not per-chunk).

This avoids the sign-flip problem in the original pipeline where z-scoring
before stitching caused negative medians and broken scaling factors.

No network access needed — runs entirely from cached data.

Usage:
  cd E:\\Projects\\BTP
  .\\.venv\\Scripts\\python.exe src/data_ingestion/restitch_from_cache.py
"""

from pathlib import Path
import numpy as np
import pandas as pd

# ============================================================================
# CONFIGURATION
# ============================================================================

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
RAW_CHUNKS_DIR = PROJECT_ROOT / "Data" / "processed" / "gtrends" / "raw_chunks"
OUTPUT_DIR = PROJECT_ROOT / "Data" / "processed" / "gtrends"

CHUNKS = [
    ("2010-01-01", "2014-12-31"),
    ("2014-01-01", "2018-12-31"),
    ("2018-01-01", "2022-12-31"),
    ("2022-01-01", "2026-06-30"),
]

STATES = {
    "IN": "National",
    "IN-DL": "Delhi",
    "IN-UP": "Uttar Pradesh",
    "IN-HR": "Haryana",
    "IN-MH": "Maharashtra",
    "IN-KL": "Kerala",
    "IN-TN": "Tamil Nadu",
    "IN-WB": "West Bengal",
}


# ============================================================================
# STEP 1: RAW COMPOSITE (mean of anchor-normalised keywords, NO z-score)
# ============================================================================

def raw_composite(df):
    """
    Average all anchor-normalised keyword columns into one composite.
    Only includes columns that have at least some non-zero values.
    Result is always >= 0, suitable for median-ratio stitching.
    """
    nonzero_cols = [c for c in df.columns if (df[c] != 0).any()]
    if not nonzero_cols:
        return None
    return df[nonzero_cols].mean(axis=1)


# ============================================================================
# STEP 2: STITCH CHUNKS (median-ratio rescaling on overlap)
# ============================================================================

def stitch_chunks(composites):
    """
    Stitch a list of Series (one per chunk) using the overlap region to
    compute a rescaling factor via mean ratio.

    Since values are raw anchor-normalised (always >= 0), the mean ratio
    is well-behaved and always positive.

    Edge case: if the previous chunk's overlap is all zero (no signal in
    that region/period), that chunk is unreliable as a reference. In that
    case, we restart the reference from the current chunk.
    """
    if not composites:
        return None, []

    stitched = composites[0].copy()
    diagnostics = []

    for i in range(1, len(composites)):
        curr = composites[i]
        if curr is None:
            diagnostics.append({"chunk": i, "status": "SKIPPED_NO_DATA"})
            continue

        overlap_dates = stitched.index.intersection(curr.index)

        if len(overlap_dates) < 10:
            diagnostics.append({
                "chunk": i,
                "overlap_weeks": len(overlap_dates),
                "status": "INSUFFICIENT_OVERLAP"
            })
            new_dates = curr.index.difference(stitched.index)
            stitched = pd.concat([stitched, curr.loc[new_dates]])
            continue

        prev_overlap = stitched.loc[overlap_dates]
        curr_overlap = curr.loc[overlap_dates]

        prev_mean = prev_overlap.mean()
        curr_mean = curr_overlap.mean()

        # If the previous chunk has zero signal in the overlap, the earlier
        # data was below Google's reporting threshold and is unreliable.
        # Discard it and restart the reference from the current chunk.
        if prev_mean == 0 or np.isnan(prev_mean):
            diagnostics.append({
                "chunk": i,
                "overlap_start": str(overlap_dates.min().date()),
                "overlap_end": str(overlap_dates.max().date()),
                "overlap_weeks": len(overlap_dates),
                "prev_mean": 0.0,
                "curr_mean": round(float(curr_mean), 6),
                "scaling_factor": None,
                "status": "RESTARTED_REF (prev overlap was zero)"
            })
            # Drop all previous data, restart from current chunk
            stitched = curr.copy()
            continue

        if curr_mean == 0 or np.isnan(curr_mean):
            factor = 1.0
        else:
            factor = prev_mean / curr_mean

        diagnostics.append({
            "chunk": i,
            "overlap_start": str(overlap_dates.min().date()),
            "overlap_end": str(overlap_dates.max().date()),
            "overlap_weeks": len(overlap_dates),
            "prev_mean": round(float(prev_mean), 6),
            "curr_mean": round(float(curr_mean), 6),
            "scaling_factor": round(float(factor), 4),
            "status": "OK"
        })

        # Rescale current chunk and append non-overlapping portion
        curr_scaled = curr * factor
        new_dates = curr_scaled.index.difference(stitched.index)
        stitched = pd.concat([stitched, curr_scaled.loc[new_dates]])

    return stitched.sort_index(), diagnostics


# ============================================================================
# STEP 3: Z-SCORE THE FINAL STITCHED SERIES
# ============================================================================

def zscore_series(s):
    """Standard z-score: (x - mean) / std."""
    mean = s.mean()
    std = s.std(ddof=0)
    if std == 0:
        return s - mean
    return (s - mean) / std


# ============================================================================
# MAIN
# ============================================================================

def main():
    print("=" * 60)
    print("RE-STITCHING FROM CACHED CHUNKS (z-score AFTER stitching)")
    print("=" * 60)

    all_composites = {}
    all_diagnostics = []

    for geo, state_name in STATES.items():
        print(f"\n--- {state_name} ({geo}) ---")

        chunk_composites = []
        for chunk_idx in range(len(CHUNKS)):
            path = RAW_CHUNKS_DIR / f"{geo}_chunk{chunk_idx}.csv"
            if not path.exists():
                print(f"  Chunk {chunk_idx}: NOT FOUND at {path}")
                chunk_composites.append(None)
                continue

            df = pd.read_csv(path, index_col=0, parse_dates=True)
            comp = raw_composite(df)
            if comp is not None:
                print(f"  Chunk {chunk_idx}: {len(comp)} weeks, "
                      f"{len([c for c in df.columns if (df[c]!=0).any()])} active keywords, "
                      f"mean={comp.mean():.4f}")
            chunk_composites.append(comp)

        # Filter out Nones
        valid = [c for c in chunk_composites if c is not None]
        if not valid:
            print(f"  [SKIP] No valid chunks for {state_name}")
            continue

        # Stitch
        stitched_raw, diag = stitch_chunks(valid)
        for d in diag:
            d["state"] = state_name
            d["geo"] = geo
        all_diagnostics.extend(diag)

        # Align Sunday → Monday (GT returns Sunday-start, FluNet uses Monday)
        stitched_raw.index = stitched_raw.index + pd.Timedelta(days=1)

        # Z-score the FULL stitched series
        stitched_z = zscore_series(stitched_raw)

        # Save per-state: both raw and z-scored
        out_df = pd.DataFrame({
            f"raw_{state_name}": stitched_raw,
            f"zscore_{state_name}": stitched_z,
        })
        out_df.index.name = "week_start"

        state_csv = OUTPUT_DIR / f"{geo.replace('-', '_')}_stitched.csv"
        out_df.to_csv(state_csv)

        print(f"  Stitched: {len(stitched_raw)} weeks "
              f"({stitched_raw.index.min().date()} → {stitched_raw.index.max().date()})")
        print(f"  Raw range: [{stitched_raw.min():.4f}, {stitched_raw.max():.4f}]")
        print(f"  Z-score range: [{stitched_z.min():.2f}, {stitched_z.max():.2f}]")
        print(f"  Saved → {state_csv}")

        all_composites[state_name] = stitched_z

    # Combined output
    if all_composites:
        combined = pd.DataFrame(all_composites)
        combined.index.name = "week_start"
        combined_path = OUTPUT_DIR / "all_states_composites.csv"
        combined.to_csv(combined_path)
        print(f"\n{'='*60}")
        print(f"COMBINED: {combined_path}")
        print(f"Shape: {combined.shape}")
        print(f"Range: {combined.index.min().date()} → {combined.index.max().date()}")

    # Diagnostics
    if all_diagnostics:
        diag_df = pd.DataFrame(all_diagnostics)
        diag_path = OUTPUT_DIR / "stitching_diagnostics.csv"
        diag_df.to_csv(diag_path, index=False)
        print(f"\nDiagnostics → {diag_path}")
        print(diag_df.to_string(index=False))

    print("\n✓ Re-stitching complete.")


if __name__ == "__main__":
    main()
