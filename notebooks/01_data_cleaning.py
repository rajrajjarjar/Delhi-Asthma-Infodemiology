"""
01_data_cleaning.py

Phase 1: Data Cleaning
-----------------------
Cleans the raw Yemen cholera governorate-level CSV:
  1. Standardizes inconsistent governorate name spellings
  2. Merges Mukalla/Sayun district-level rows into one Hadramawt governorate
  3. Fixes dtypes (Date -> datetime, Cases/Deaths -> numeric, strips commas)
  4. Converts CUMULATIVE case counts into INCREMENTAL new-cases-per-period
     (this is the column your Spearman/Granger analysis should actually use)
  5. Flags and corrects negative diffs caused by data-correction artifacts
     in the raw cumulative reporting

Run:
    python 01_data_cleaning.py

Input:
    data/raw/cholera_epi_raw.csv

Output:
    data/clean/cholera_clean.csv
"""

import pandas as pd
import numpy as np
from pathlib import Path

# ----------------------------------------------------------------------
# CONFIG - adjust paths if your folder structure differs
# ----------------------------------------------------------------------
RAW_PATH = Path("data/raw/cholera_epi_raw.csv")
CLEAN_PATH = Path("data/clean/cholera_clean.csv")

# Mapping of raw (messy) governorate names -> standardized canonical name.
# Anything not in this dict is assumed already-correct and passes through unchanged.
GOVERNORATE_NAME_MAP = {
    "AL Mahrah": "Al Maharah",
    "Al Maharah": "Al Maharah",
    "Al Hudaydah": "Al Hudaydah",
    "Al-Hudaydah": "Al Hudaydah",
    "Al Jawf": "Al Jawf",
    "Al_Jawf": "Al Jawf",
    "Marib": "Marib",
    "Ma'areb": "Marib",
    # Mukalla and Sayun are districts within Hadramawt governorate that
    # were reported separately in the raw data. We merge them into one
    # governorate-level row by summing Cases/Deaths per date.
    "Moklla": "Hadramawt",
    "Say'on": "Hadramawt",
}


def load_raw(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    print(f"[load_raw] Loaded {df.shape[0]} rows, {df.shape[1]} columns from {path}")
    return df


def standardize_governorate_names(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["Governorate_clean"] = (
        df["Governorate"].map(GOVERNORATE_NAME_MAP).fillna(df["Governorate"])
    )
    n_before = df["Governorate"].nunique()
    n_after = df["Governorate_clean"].nunique()
    print(f"[standardize_governorate_names] {n_before} raw names -> {n_after} standardized governorates")
    return df


def fix_dtypes(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["Date"] = pd.to_datetime(df["Date"])
    for col in ["Cases", "Deaths"]:
        df[col] = (
            df[col].astype(str).str.replace(",", "", regex=False).str.strip()
        )
        df[col] = pd.to_numeric(df[col], errors="coerce")
    n_nulls = df[["Cases", "Deaths"]].isnull().sum().sum()
    if n_nulls:
        print(f"[fix_dtypes] WARNING: {n_nulls} values could not be parsed as numeric — inspect these rows")
    return df


def merge_duplicate_governorates(df: pd.DataFrame) -> pd.DataFrame:
    """Collapse rows sharing the same (Date, standardized Governorate) —
    e.g. Mukalla + Sayun on the same date both become Hadramawt, summed."""
    agg = df.groupby(["Date", "Governorate_clean"], as_index=False).agg(
        Cases=("Cases", "sum"),
        Deaths=("Deaths", "sum"),
    )
    agg = agg.rename(columns={"Governorate_clean": "Governorate"})
    agg = agg.sort_values(["Governorate", "Date"]).reset_index(drop=True)
    print(f"[merge_duplicate_governorates] Shape after merge: {agg.shape}")
    return agg


def cumulative_to_incremental(df: pd.DataFrame) -> pd.DataFrame:
    """Convert cumulative Cases into New_Cases (incremental), per governorate.
    The first reported period per governorate has no prior value, so its
    cumulative value is used as-is for that first period's New_Cases."""
    df = df.copy()
    df["New_Cases"] = df.groupby("Governorate")["Cases"].diff()

    first_idx = df.groupby("Governorate").head(1).index
    df.loc[first_idx, "New_Cases"] = df.loc[first_idx, "Cases"]

    return df


def flag_and_fix_negative_diffs(df: pd.DataFrame) -> pd.DataFrame:
    """Cumulative reporting sometimes gets revised downward (data corrections),
    which produces impossible negative New_Cases values after .diff().
    We flag these rows for transparency and clip them to 0."""
    df = df.copy()
    neg_mask = df["New_Cases"] < 0
    n_neg = neg_mask.sum()

    df["New_Cases_flag"] = "ok"
    df.loc[neg_mask, "New_Cases_flag"] = "corrected_negative"
    df.loc[neg_mask, "New_Cases"] = 0

    print(f"[flag_and_fix_negative_diffs] {n_neg} negative-diff rows flagged and clipped to 0")
    if n_neg:
        print(df.loc[neg_mask, ["Date", "Governorate", "Cases", "New_Cases_flag"]])
    return df


def run_quality_report(df: pd.DataFrame) -> None:
    print("\n===== DATA QUALITY REPORT =====")
    print("Shape:", df.shape)
    print("Date range:", df["Date"].min().date(), "to", df["Date"].max().date())
    print("Governorates:", df["Governorate"].nunique())
    print("\nRows per governorate (uneven counts = inconsistent reporting frequency):")
    print(df["Governorate"].value_counts().sort_index())
    print("================================\n")


def main():
    CLEAN_PATH.parent.mkdir(parents=True, exist_ok=True)

    df = load_raw(RAW_PATH)
    df = standardize_governorate_names(df)
    df = fix_dtypes(df)
    df = merge_duplicate_governorates(df)
    df = cumulative_to_incremental(df)
    df = flag_and_fix_negative_diffs(df)

    run_quality_report(df)

    df.to_csv(CLEAN_PATH, index=False)
    print(f"Saved cleaned file to: {CLEAN_PATH}")


if __name__ == "__main__":
    main()
