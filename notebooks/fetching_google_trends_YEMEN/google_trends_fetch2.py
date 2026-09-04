from pytrends.request import TrendReq
from pathlib import Path
import pandas as pd
import random
import time
"this code is to fetch google trends of YE zone that is yemen"

"""
pull_google_trends.py

Pulls Google Trends relative search volume (RSV) for a list of terms,
over the same date range as your cholera epidemiology data, restricted
to Yemen (geo="YE").

WHY BATCHING + AN ANCHOR TERM (important, read this):
Google Trends only allows 5 terms per API request, AND each request's
0-100 scale is relative ONLY to the other terms in that same request —
scores from batch 1 are NOT directly comparable to scores from batch 2.

Fix: every batch includes one shared "anchor" term (the same term,
every time). After pulling all batches, we rescale each batch using
the anchor's values so every term ends up on one consistent 0-100
scale, comparable across the whole term list. This is standard
practice for pulling >5 terms from Trends and is worth mentioning
explicitly in your methodology section.

Run:
    python pull_google_trends.py

Input:
    data/reference/google_trends_search_terms.csv   (english_term, arabic_term columns)

Output:
    data/raw/trends_raw.csv   (one column per term, rescaled, weekly)

NOTE: Google Trends aggressively rate-limits automated pulls. This
script sleeps between requests and retries on failure, but if you get
repeated 429 errors, wait a few minutes and rerun — it's Google
throttling you, not a bug in this script.
"""


TERMS_PATH = Path(
    "E:/Projects/BTP/notebooks/fetching_google_trends/google_trends_search_terms.csv")
OUT_PATH = Path("E:/Projects/BTP/Data/Raw_data/google_trends_raw.csv")

# Match this to your cholera epidemiology data's date range
TIMEFRAME = "2017-05-22 2018-02-18"
GEO = "YE"  # Yemen. pytrends/Trends does not support governorate-level geo for Yemen —
# this pulls one national-level series per term (a known limitation,
# already flagged in your project's structural plan).

# Anchor term included in every batch, used to rescale batches onto one
# consistent 0-100 scale. Pick a term you expect to have *some* nonzero
# volume — "diarrhea" (إسهال) is a safer anchor than "cholera" itself,
# which may return all zeros for a country as sparse as Yemen.
ANCHOR_TERM = "إسهال"

SLEEP_BETWEEN_REQUESTS = 15  # seconds — conservative, to avoid 429 rate-limit errors
MAX_RETRIES = 3


def load_terms(path: Path) -> list[str]:
    df = pd.read_csv(path)
    # Combine english_term and arabic_term columns into one flat list,
    # dropping blanks (some rows only have one language filled in)
    terms = pd.concat([df["english_term"], df["arabic_term"]]
                      ).dropna().unique().tolist()
    # anchor gets added back per-batch
    terms = [t for t in terms if t != ANCHOR_TERM]
    print(f"[load_terms] Loaded {len(terms)} unique terms (excluding anchor)")
    return terms


def batch_terms(terms: list[str], batch_size: int = 4) -> list[list[str]]:
    """Split into batches of 4, so each batch + the anchor term = 5 (Trends' max)."""
    return [terms[i: i + batch_size] for i in range(0, len(terms), batch_size)]


def pull_batch(pytrends: TrendReq, batch: list[str]) -> pd.DataFrame | None:
    kw_list = [ANCHOR_TERM] + batch
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            pytrends.build_payload(kw_list, timeframe=TIMEFRAME, geo=GEO)
            df = pytrends.interest_over_time()
            if df.empty:
                print(f"    WARNING: empty result for batch {batch}")
                return None
            if "isPartial" in df.columns:
                df = df.drop(columns=["isPartial"])
            return df
        except Exception as e:
            wait = SLEEP_BETWEEN_REQUESTS * attempt
            print(
                f"    Attempt {attempt}/{MAX_RETRIES} failed ({e}) — waiting {wait}s and retrying")
            time.sleep(wait)
    print(f"    FAILED after {MAX_RETRIES} attempts — skipping batch {batch}")
    return None


def rescale_batch(batch_df: pd.DataFrame, reference_anchor: pd.Series) -> pd.DataFrame:
    """Rescale this batch's values so its anchor column matches the
    reference anchor's scale (from the very first batch)."""
    ratio = (reference_anchor /
             batch_df[ANCHOR_TERM]).replace([float("inf")], 0).fillna(0)
    rescaled = batch_df.drop(columns=[ANCHOR_TERM]).multiply(ratio, axis=0)
    return rescaled


def main():
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    terms = load_terms(TERMS_PATH)
    batches = batch_terms(terms)
    print(f"[main] Split into {len(batches)} batches of up to 4 terms each\n")

    # tz=180 -> roughly Yemen's UTC+3 offset in minutes
    pytrends = TrendReq(hl="en-US", tz=180)

    reference_anchor = None
    all_series = []

    for i, batch in enumerate(batches, start=1):
        print(f"[main] Pulling batch {i}/{len(batches)}: {batch}")
        batch_df = pull_batch(pytrends, batch)

        if batch_df is None:
            continue

        if reference_anchor is None:
            # First successful batch sets the scale everyone else gets rescaled to
            reference_anchor = batch_df[ANCHOR_TERM]
            all_series.append(batch_df.drop(columns=[ANCHOR_TERM]))
        else:
            rescaled = rescale_batch(batch_df, reference_anchor)
            all_series.append(rescaled)

        # Be polite to Google's rate limiter, with a little jitter
        time.sleep(SLEEP_BETWEEN_REQUESTS + random.uniform(0, 3))

    if not all_series:
        print(
            "[main] No data was successfully pulled — check your terms/timeframe/geo and try again")
        return

    merged = pd.concat(all_series, axis=1)
    merged.index.name = "Date"
    merged = merged.reset_index()

    merged.to_csv(OUT_PATH, index=False)
    print(
        f"\n[main] Saved {merged.shape[0]} weekly rows x {merged.shape[1]-1} terms to {OUT_PATH}")
    print("\n[main] Terms with all-zero volume (candidates to drop):")
    numeric_cols = merged.columns.drop("Date")
    all_zero = numeric_cols[(merged[numeric_cols] == 0).all()]
    print(list(all_zero) if len(all_zero)
          else "  None — all terms returned some signal")


if __name__ == "__main__":
    main()
