"""
fetch_and_plot_chunk1.py
========================
Pulls and plots the first 5-year chunk (2010-01-01 to 2014-12-31) of Google Trends
for the most robust symptom term ('fever') across National and key Indian states.
"""

import time
import random
from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from pytrends.request import TrendReq

# -------------------------------------------------------------------------
# Configuration
# -------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent
OUTPUT_FIGURES_DIR = BASE_DIR.parent.parent / "outputs" / "figures"
OUTPUT_FIGURES_DIR.mkdir(parents=True, exist_ok=True)

START_DATE = "2010-01-01"
END_DATE = "2014-12-31"
TIMEFRAME = f"{START_DATE} {END_DATE}"

PRIMARY_TERM = "fever"
COMPARISON_TERM = "flu"

REGIONS = {
    "National (India)": "IN",
    "Delhi": "IN-DL",
    "Maharashtra": "IN-MH",
    "Kerala": "IN-KL",
    "West Bengal": "IN-WB",
    "Uttar Pradesh": "IN-UP"
}

# -------------------------------------------------------------------------
# Pytrends Helper with Backoff
# -------------------------------------------------------------------------
def get_pytrends_client():
    return TrendReq(hl="en-US", tz=330)

def safe_build_payload(pytrends, kw_list, geo, timeframe, max_retries=3):
    for attempt in range(max_retries):
        try:
            pytrends.build_payload(kw_list, geo=geo, timeframe=timeframe)
            df = pytrends.interest_over_time()
            if df is not None and not df.empty:
                return df.drop(columns=["isPartial"], errors="ignore")
        except Exception as e:
            wait = (2 ** attempt) + random.uniform(1, 2)
            print(f"  [Retry {attempt+1}/{max_retries}] for {geo} ({e}) - waiting {wait:.1f}s")
            time.sleep(wait)
    return None

# -------------------------------------------------------------------------
# Main Data Extraction
# -------------------------------------------------------------------------
def main():
    print(f"=== Fetching 5-Year Chunk (2010–2015): Term = '{PRIMARY_TERM}' ===")
    pytrends = get_pytrends_client()
    
    collected_series = {}
    
    # 1. Pull National: 'fever' and 'flu'
    print(f"Fetching National ('{PRIMARY_TERM}' & '{COMPARISON_TERM}')...")
    df_nat = safe_build_payload(pytrends, [PRIMARY_TERM, COMPARISON_TERM], geo="IN", timeframe=TIMEFRAME)
    if df_nat is not None:
        collected_series[f"{PRIMARY_TERM}_National"] = df_nat[PRIMARY_TERM]
        collected_series[f"{COMPARISON_TERM}_National"] = df_nat[COMPARISON_TERM]
    else:
        print("[WARN] National query returned no data (likely rate-limited). Try again after 60s cooldown.")
    
    time.sleep(5)  # Polite delay between requests to avoid HTTP 429

    # 2. Pull Candidate States for 'fever'
    for state_name, geo_code in REGIONS.items():
        if geo_code == "IN":
            continue
        print(f"Fetching {state_name} ({geo_code}) for '{PRIMARY_TERM}'...")
        df_state = safe_build_payload(pytrends, [PRIMARY_TERM], geo=geo_code, timeframe=TIMEFRAME)
        if df_state is not None:
            collected_series[f"{PRIMARY_TERM}_{state_name}"] = df_state[PRIMARY_TERM]
        time.sleep(5)  # Polite delay between states

    if not collected_series:
        print("\n[ERROR] No data could be fetched. Google is currently rate-limiting your IP (HTTP 429).")
        print("Please wait 2-3 minutes and run this script again.")
        return

    # Combine into single DataFrame
    df_all = pd.DataFrame(collected_series)
    df_all.index.name = "date"
    
    # Save CSV
    csv_path = BASE_DIR / "gtrends_chunk1_2010_2015_data.csv"
    df_all.to_csv(csv_path)
    print(f"\nSaved raw time series data to: {csv_path}")
    print(f"Shape: {df_all.shape} (Rows: {len(df_all)} weekly points, Columns: {len(df_all.columns)})")
    print(f"Date range: {df_all.index.min().date()} to {df_all.index.max().date()}")

    # ---------------------------------------------------------------------
    # Plot 1: 5-Year Continuous National Fever Timeline
    # ---------------------------------------------------------------------
    nat_col = f"{PRIMARY_TERM}_National"
    if nat_col in df_all.columns:
        plt.style.use("seaborn-v0_8-whitegrid" if "seaborn-v0_8-whitegrid" in plt.style.available else "default")
        
        fig, ax = plt.subplots(figsize=(14, 6))
        ax.plot(df_all.index, df_all[nat_col], color="#1f77b4", linewidth=2, label="National Search Interest ('fever')")
        
        # Shading annual monsoon / post-monsoon surge windows (approx July - October of each year)
        for year in range(2010, 2015):
            surge_start = pd.Timestamp(f"{year}-07-01")
            surge_end = pd.Timestamp(f"{year}-10-31")
            ax.axvspan(surge_start, surge_end, color="#ff7f0e", alpha=0.15, label="Monsoon / Post-Monsoon Season" if year == 2010 else "")

        ax.xaxis.set_major_locator(mdates.YearLocator())
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
        ax.xaxis.set_minor_locator(mdates.MonthLocator(bymonth=[4, 7, 10]))
        
        ax.set_title("5-Year Weekly Google Trends for 'fever' in India (2010–2014)", fontsize=16, fontweight="bold", pad=14)
        ax.set_ylabel("Google Trends Relative Search Volume (0–100)", fontsize=12)
        ax.set_xlabel("Year", fontsize=12)
        ax.set_ylim(0, 105)
        ax.grid(True, linestyle="--", alpha=0.5)
        ax.legend(loc="upper left", frameon=True, fontsize=11)
        
        fig.tight_layout()
        plot1_path = BASE_DIR / "gtrends_fever_5yr_timeline.png"
        fig.savefig(plot1_path, dpi=200)
        fig.savefig(OUTPUT_FIGURES_DIR / "gtrends_2010_2015_fever_5yr.png", dpi=200)
        plt.close(fig)
        print(f"Saved Plot 1 to: {plot1_path}")
    else:
        print(f"[SKIP] Plot 1 skipped: '{nat_col}' column not present.")

    # ---------------------------------------------------------------------
    # Plot 2: Regional Breakdown (Available States)
    # ---------------------------------------------------------------------
    available_states = [c for c in df_all.columns if c.startswith(f"{PRIMARY_TERM}_")]
    if len(available_states) > 1:
        n_plots = len(available_states)
        n_cols = 2
        n_rows = (n_plots + 1) // 2
        fig, axes = plt.subplots(n_rows, n_cols, figsize=(15, 4 * n_rows), sharex=True, sharey=True)
        axes = axes.flatten() if hasattr(axes, "flatten") else [axes]

        colors = ["#1f77b4", "#d62728", "#2ca02c", "#9467bd", "#ff7f0e", "#8c564b"]

        for idx, col in enumerate(available_states):
            ax = axes[idx]
            label = col.replace(f"{PRIMARY_TERM}_", "")
            ax.plot(df_all.index, df_all[col], color=colors[idx % len(colors)], linewidth=1.8, label=label)
            
            rolling_avg = df_all[col].rolling(window=4, center=True).mean()
            ax.plot(df_all.index, rolling_avg, color="black", linestyle="--", alpha=0.7, linewidth=1.2, label="4-week MA")
            
            ax.set_title(label, fontsize=13, fontweight="bold")
            ax.set_ylim(0, 105)
            ax.grid(True, linestyle=":", alpha=0.6)
            ax.legend(loc="upper left", fontsize=9)
            ax.xaxis.set_major_locator(mdates.YearLocator())
            ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))

        # Hide any unused subplots
        for idx in range(len(available_states), len(axes)):
            axes[idx].set_visible(False)

        fig.suptitle("Regional Search Behavior for 'fever' across Indian Regions (2010–2014)", fontsize=16, fontweight="bold", y=0.995)
        fig.tight_layout()
        plot2_path = BASE_DIR / "gtrends_fever_regional_comparison.png"
        fig.savefig(plot2_path, dpi=200)
        plt.close(fig)
        print(f"Saved Plot 2 to: {plot2_path}")

    # ---------------------------------------------------------------------
    # Plot 3: 'fever' vs 'flu' (Why 'fever' is the superior signal)
    # ---------------------------------------------------------------------
    fig, ax = plt.subplots(figsize=(14, 5.5))
    if f"{PRIMARY_TERM}_National" in df_all.columns and f"{COMPARISON_TERM}_National" in df_all.columns:
        ax.plot(df_all.index, df_all[f"{PRIMARY_TERM}_National"], color="#1f77b4", linewidth=2, label="National Search: 'fever' (Dense, Seasonal)")
        ax.plot(df_all.index, df_all[f"{COMPARISON_TERM}_National"], color="#d62728", linewidth=1.8, linestyle="-.", label="National Search: 'flu' (Sporadic, Media-driven)")

    ax.xaxis.set_major_locator(mdates.YearLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    ax.set_title("Comparison: 'fever' vs. 'flu' Search Volume in India (2010–2014)", fontsize=15, fontweight="bold", pad=12)
    ax.set_ylabel("Google Trends Index (0–100)", fontsize=12)
    ax.set_xlabel("Year", fontsize=12)
    ax.grid(True, linestyle="--", alpha=0.5)
    ax.legend(loc="upper right", frameon=True, fontsize=11)
    
    fig.tight_layout()
    plot3_path = BASE_DIR / "gtrends_fever_vs_flu.png"
    fig.savefig(plot3_path, dpi=200)
    plt.close(fig)
    print(f"Saved Plot 3 to: {plot3_path}")

    print("\nAll tasks completed successfully!")

if __name__ == "__main__":
    main()
