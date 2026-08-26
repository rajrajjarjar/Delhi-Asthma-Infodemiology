"""
pull_google_trends_individual.py

Pulls Google Trends RSV for each term ONE AT A TIME (no batching, no
anchor term, no rescaling).

WHY THE CHANGE FROM THE BATCHED VERSION:
The batched approach (5 terms per request, one shared anchor to rescale
across batches) has a hidden flaw: within any single request, Google
Trends scales ALL terms in that request relative to whichever term has
the highest volume. If one term in a batch dominates, the others --
even with real, meaningful search activity -- get compressed down to
single digits or rounded to 0. Our actual pull showed exactly this:
the anchor term came back "0 for every week" in nearly every batch,
which is implausible for a term as common as "diarrhea" -- it wasn't
silent, it was just losing the internal scaling competition depending
on which random terms it got grouped with.

THE FIX: query one term at a time. Each term gets scaled only against
its OWN historical peak, so nothing can squash it artificially.

WHY THIS IS FINE FOR YOUR ANALYSIS SPECIFICALLY:
Spearman rank correlation only needs each term's own series to
correctly preserve its own relative rises and falls over time -- it
does NOT require different terms to be on one shared, comparable
absolute scale. So dropping cross-term comparability costs you
nothing methodologically, and removes the scaling-collapse problem
entirely. (If a later part of your project DOES need cross-term
comparability -- e.g. "which symptom had the single highest absolute
search volume" -- that's a different question and would need a
different approach. Flag it if that comes up.)

Run:
    python pull_google_trends_individual.py

Input:
    data/reference/google_trends_search_terms.csv

Output:
    data/raw/trends_raw_individual.csv   (one column per term, weekly, each on its own scale)
"""

import time
import random
import pandas as pd
from pathlib import Path
from pytrends.request import TrendReq


TERMS_PATH = Path(
    "E:/Projects/BTP/notebooks/fetching_google_trends/google_trends_search_terms.csv")
OUT_PATH = Path("E:/Projects/BTP/notebooks/data/raw/trends_raw_individual.csv")

TIMEFRAME = "2017-05-22 2018-02-18"
GEO = "YE"

SLEEP_BETWEEN_REQUESTS = 15  # seconds -- conservative, to avoid 429 rate-limit errors
MAX_RETRIES = 3


def load_terms(path: Path) -> list[str]:
    df = pd.read_csv(path)
    terms = pd.concat([df["english_term"], df["arabic_term"]]
                      ).dropna().unique().tolist()
    print(f"[load_terms] Loaded {len(terms)} unique terms")
    return terms


def pull_single_term(pytrends: TrendReq, term: str) -> pd.Series | None:
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            pytrends.build_payload([term], timeframe=TIMEFRAME, geo=GEO)
            df = pytrends.interest_over_time()
            if df.empty:
                print(f"    '{term}' -> empty result (no reportable volume)")
                return None
            series = df[term]
            n_nonzero = (series != 0).sum()
            print(
                f"    '{term}' -> {n_nonzero}/{len(series)} nonzero weeks, max={series.max()}")
            return series
        except Exception as e:
            wait = SLEEP_BETWEEN_REQUESTS * attempt
            print(
                f"    Attempt {attempt}/{MAX_RETRIES} failed ({e}) -- waiting {wait}s and retrying")
            time.sleep(wait)
    print(f"    FAILED after {MAX_RETRIES} attempts -- skipping '{term}'")
    return None


def main():
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    terms = load_terms(TERMS_PATH)
    pytrends = TrendReq(hl="en-US", tz=180)

    results = {}
    for i, term in enumerate(terms, start=1):
        print(f"[main] ({i}/{len(terms)}) Pulling '{term}'")
        series = pull_single_term(pytrends, term)
        if series is not None:
            results[term] = series
        time.sleep(SLEEP_BETWEEN_REQUESTS + random.uniform(0, 3))

    if not results:
        print(
            "[main] No data was successfully pulled at all -- see note below on next steps")
        return

    merged = pd.DataFrame(results)
    merged.index.name = "Date"
    merged = merged.reset_index()
    merged.to_csv(OUT_PATH, index=False)

    print(
        f"\n[main] Saved {merged.shape[0]} weekly rows x {merged.shape[1]-1} terms to {OUT_PATH}")

    numeric_cols = merged.columns.drop("Date")
    all_zero = numeric_cols[(merged[numeric_cols] == 0).all()]
    has_signal = [c for c in numeric_cols if c not in all_zero]

    print(f"\n[main] Terms WITH signal ({len(has_signal)}): {has_signal}")
    print(f"[main] Terms still all-zero ({len(all_zero)}): {list(all_zero)}")


if __name__ == "__main__":
    main()
