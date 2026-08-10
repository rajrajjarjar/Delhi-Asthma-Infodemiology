"""
plot_raw_vs_clean.py

Progress-report visual: compares RAW cumulative case counts against the
CLEANED incremental (New_Cases) counts, for 3 selected governorates.

Purpose: show your professor exactly what the cleaning step did —
raw data is a cumulative running total (always climbing), while the
cleaned New_Cases column shows actual week-to-week outbreak activity
(rises and falls) — which is what the lag analysis actually needs.

Run:
    python plot_raw_vs_clean.py

Input:
    data/clean/cholera_clean.csv   (needs Cases, New_Cases, Date, Governorate)

Output:
    outputs/figures/raw_vs_clean_cases.png
"""

import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path

DATA_PATH = Path("./Data/Clean/merged_clean-first.csv")
OUT_PATH = Path("./Graphs/figures_yemen/raw_vs_clean_cases.png")

GOVERNORATES = ["Al Hudaydah", "Hajjah", "Aden"]


def main():
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(DATA_PATH, parse_dates=["Date"])
    subset = df[df["Governorate"].isin(GOVERNORATES)]

    fig, axes = plt.subplots(2, 1, figsize=(10, 8), sharex=True)

    # --- Top: RAW cumulative cases ---
    ax = axes[0]
    for gov in GOVERNORATES:
        gov_data = subset[subset["Governorate"] == gov].sort_values("Date")
        ax.plot(gov_data["Date"], gov_data["Cases"],
                marker="o", markersize=2, label=gov)
    ax.set_title("Raw Data — Cumulative Reported Cases")
    ax.set_ylabel("Cumulative Cases")
    ax.legend()
    ax.grid(alpha=0.3)

    # --- Bottom: CLEAN incremental new cases ---
    ax = axes[1]
    for gov in GOVERNORATES:
        gov_data = subset[subset["Governorate"] == gov].sort_values("Date")
        ax.plot(gov_data["Date"], gov_data["New_Cases"],
                marker="o", markersize=2, label=gov)
    ax.set_title("Cleaned Data — New Cases per Reporting Period")
    ax.set_ylabel("New Cases")
    ax.set_xlabel("Date")
    ax.legend()
    ax.grid(alpha=0.3)

    fig.suptitle(
        f"Raw vs. Cleaned Cholera Data: {', '.join(GOVERNORATES)}", fontsize=13)
    fig.tight_layout()
    fig.savefig(OUT_PATH, dpi=150)
    print(f"Saved figure to: {OUT_PATH}")


if __name__ == "__main__":
    main()
