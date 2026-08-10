"""
clean_names.py

Single responsibility: standardize the Governorate column only.
  - Maps inconsistent spellings to one canonical name
    (e.g. "Al-Hudaydah" / "Al Hudaydah" -> "Al Hudaydah")
  - Flags Mukalla/Sayun as sub-district rows belonging to Hadramawt
    (mapped here, but NOT merged/summed — merging duplicate rows is a
    separate concern, handled in 01_data_cleaning.py)
  - Reports before/after unique governorate counts

Does NOT touch dates or case numbers — see clean_dates.py and
01_data_cleaning.py for those.

Run:
    python clean_names.py

Input:
    data/raw/cholera_epi_raw.csv

Output:
    data/clean/names_cleaned.csv
"""

import pandas as pd
from pathlib import Path

RAW_PATH = Path("data/raw/cholera_epi_raw.csv")
OUT_PATH = Path("data/clean/names_cleaned.csv")

# Raw (messy) governorate name -> standardized canonical name.
# Anything not listed here is assumed already-correct and passes through unchanged.
GOVERNORATE_NAME_MAP = {
    "AL Mahrah": "Al Maharah",
    "Al Maharah": "Al Maharah",
    "Al Hudaydah": "Al Hudaydah",
    "Al-Hudaydah": "Al Hudaydah",
    "Al Jawf": "Al Jawf",
    "Al_Jawf": "Al Jawf",
    "Marib": "Marib",
    "Ma'areb": "Marib",
    # Mukalla and Sayun are districts within Hadramawt governorate.
    # Mapped here for naming consistency; if you want them combined into
    # one Hadramawt row per date, do that merge step separately (see
    # 01_data_cleaning.py's merge_duplicate_governorates function).
    "Moklla": "Hadramawt",
    "Say'on": "Hadramawt",
}


def clean_names(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    raw_names = sorted(df["Governorate"].unique())
    print(f"[clean_names] {len(raw_names)} raw governorate names found:")
    for name in raw_names:
        mapped = GOVERNORATE_NAME_MAP.get(name, name)
        flag = "  -> " + mapped if name in GOVERNORATE_NAME_MAP else ""
        print(f"    {name!r}{flag}")

    df["Governorate"] = df["Governorate"].map(GOVERNORATE_NAME_MAP).fillna(df["Governorate"])

    n_after = df["Governorate"].nunique()
    print(f"\n[clean_names] Standardized down to {n_after} unique governorates")

    # Warn if Mukalla/Sayun rows now share (Date, Governorate) with other
    # Hadramawt rows — since this script doesn't merge/sum, those stay as
    # separate rows and will look like duplicates downstream.
    hadramawt_dupes = df[
        (df["Governorate"] == "Hadramawt")
        & df.duplicated(subset=["Date", "Governorate"], keep=False)
    ]
    if len(hadramawt_dupes):
        print(
            f"[clean_names] NOTE: {len(hadramawt_dupes)} Hadramawt rows share a "
            "(Date, Governorate) pair after merging Mukalla/Sayun names — "
            "these still need to be aggregated (summed) in a later step."
        )

    return df


def main():
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    df = pd.read_csv(RAW_PATH)
    print(f"[main] Loaded {df.shape[0]} rows from {RAW_PATH}")

    df = clean_names(df)

    df.to_csv(OUT_PATH, index=False)
    print(f"\n[main] Saved name-cleaned file to: {OUT_PATH}")


if __name__ == "__main__":
    main()
