"""
clean_dates.py

Single responsibility: clean the Date column only.
  - Parses Date to proper datetime64
  - Reports any rows where the date could not be parsed
  - Reports duplicate (Date, Governorate) pairs, if any
  - Sorts rows chronologically

Does NOT touch governorate names or case numbers — see clean_names.py
and 01_data_cleaning.py for those.

Run:
    python clean_dates.py

Input:
    data/raw/cholera_epi_raw.csv

Output:
    data/clean/dates_cleaned.csv
"""

import pandas as pd
from pathlib import Path

RAW_PATH = Path("data/raw/cholera_epi_raw.csv")
OUT_PATH = Path("data/clean/dates_cleaned.csv")


def clean_dates(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    # Try to parse every value in Date; anything unparseable becomes NaT
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")

    n_bad = df["Date"].isna().sum()
    if n_bad:
        print(f"[clean_dates] WARNING: {n_bad} rows had an unparseable date — inspect and fix manually")
        print(df[df["Date"].isna()])

    # Check for duplicate (Date, Governorate) pairs — same governorate
    # reported twice on the same date usually signals a data entry issue
    dupes = df[df.duplicated(subset=["Date", "Governorate"], keep=False)]
    if len(dupes):
        print(f"[clean_dates] WARNING: {len(dupes)} rows are duplicate (Date, Governorate) pairs")
        print(dupes.sort_values(["Governorate", "Date"]))

    df = df.sort_values(["Governorate", "Date"]).reset_index(drop=True)

    print(f"[clean_dates] Date range: {df['Date'].min().date()} to {df['Date'].max().date()}")
    print(f"[clean_dates] {df['Date'].nunique()} unique dates across the dataset")

    return df


def main():
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    df = pd.read_csv(RAW_PATH)
    print(f"[main] Loaded {df.shape[0]} rows from {RAW_PATH}")

    df = clean_dates(df)

    df.to_csv(OUT_PATH, index=False)
    print(f"[main] Saved date-cleaned file to: {OUT_PATH}")


if __name__ == "__main__":
    main()
