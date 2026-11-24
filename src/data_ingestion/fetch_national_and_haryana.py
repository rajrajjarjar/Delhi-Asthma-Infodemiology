"""
fetch_national_and_haryana.py
==============================
Dedicated fetch script for:
  1. National baseline (geo='IN') - English symptom keywords
  2. Haryana (geo='IN-HR')       - English + Hindi symptom keywords

Pulls 4 overlapping chunks (2010–2026) and caches raw files directly to:
  Data/processed/gtrends/raw_chunks/{GEO}_chunk{0-3}.csv

Usage:
  cd E:\\Projects\\BTP
  .\\.venv\\Scripts\\python.exe src/data_ingestion/fetch_national_and_haryana.py
"""

import time
import random
from pathlib import Path
import pandas as pd
from pytrends.request import TrendReq

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
RAW_CHUNKS_DIR = PROJECT_ROOT / "Data" / "processed" / "gtrends" / "raw_chunks"
RAW_CHUNKS_DIR.mkdir(parents=True, exist_ok=True)

CHUNKS = [
    ("2010-01-01", "2014-12-31"),
    ("2014-01-01", "2018-12-31"),
    ("2018-01-01", "2022-12-31"),
    ("2022-01-01", "2026-06-30"),
]

TARGETS = {
    "IN": "National",
    "IN-HR": "Haryana",
}

ENGLISH_KEYWORDS = ["flu", "fever", "cough", "viral fever"]
HINDI_KEYWORDS = ["बुखार", "खांसी"]
HINDI_GEOS = {"IN-HR"}
ANCHOR_KW = "youtube"
MAX_KW_PER_REQUEST = 4

PAUSE_BETWEEN_REQUESTS = 5
PAUSE_BETWEEN_CHUNKS = 8
PAUSE_ON_429 = 60
MAX_RETRIES = 5


def get_pytrends_client():
    try:
        return TrendReq(hl="en-US", tz=330, retries=3, backoff_factor=1)
    except TypeError:
        return TrendReq(hl="en-US", tz=330)


def safe_fetch(pytrends, kw_list, geo, timeframe, max_retries=MAX_RETRIES):
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
                wait = PAUSE_ON_429 + random.uniform(2, 10)
                print(
                    f"    [429 RATE LIMIT] Waiting {wait:.0f}s before retry {attempt+1}/{max_retries}...")
            else:
                wait = (2 ** attempt) + random.uniform(1, 3)
                print(
                    f"    [ERROR] {e} — retrying in {wait:.1f}s ({attempt+1}/{max_retries})")
            time.sleep(wait)
            if "429" in err_str:
                try:
                    pytrends = get_pytrends_client()
                except Exception:
                    pass
    return None


def fetch_chunk(pytrends, geo, state_name, chunk_start, chunk_end):
    timeframe = f"{chunk_start} {chunk_end}"
    keywords = list(ENGLISH_KEYWORDS)
    if geo in HINDI_GEOS:
        keywords.extend(HINDI_KEYWORDS)

    batches = [keywords[i:i + MAX_KW_PER_REQUEST]
               for i in range(0, len(keywords), MAX_KW_PER_REQUEST)]
    all_normalised = {}

    for batch in batches:
        payload = [ANCHOR_KW] + batch
        print(f"    Fetching {state_name} ({geo}): {batch} ...")
        df = safe_fetch(pytrends, payload, geo=geo, timeframe=timeframe)

        if df is None:
            print(
                f"    [WARN] No data returned for {state_name} {batch} in {timeframe}")
            continue

        anchor_series = df[ANCHOR_KW].astype(float)
        for kw in batch:
            if kw in df.columns:
                all_normalised[kw] = df[kw].astype(
                    float) / (anchor_series + 1.0)

        time.sleep(PAUSE_BETWEEN_REQUESTS)

    if not all_normalised:
        return None
    return pd.DataFrame(all_normalised)


def main():
    print("=" * 60)
    print("Fetching Google Trends: National (IN) & Haryana (IN-HR)")
    print("=" * 60)

    pytrends = get_pytrends_client()

    for geo, name in TARGETS.items():
        print(f"\nTarget: {name} ({geo})")
        for idx, (c_start, c_end) in enumerate(CHUNKS):
            out_file = RAW_CHUNKS_DIR / f"{geo}_chunk{idx}.csv"
            if out_file.exists():
                print(
                    f"  Chunk {idx+1}/{len(CHUNKS)} already cached: {out_file.name}")
                continue

            print(
                f"  Fetching Chunk {idx+1}/{len(CHUNKS)}: {c_start} → {c_end}")
            df = fetch_chunk(pytrends, geo, name, c_start, c_end)
            if df is not None:
                df.to_csv(out_file)
                print(f"    Saved: {out_file.name} ({len(df)} weeks)")
            else:
                print(f"    [ERROR] Failed chunk {idx+1} for {name}")

            time.sleep(PAUSE_BETWEEN_CHUNKS)

    print("\n✓ Fetch finished. Next, run restitch_from_cache.py to update composites.")


if __name__ == "__main__":
    main()
