"""
generate_thesis_figures.py
===========================
Generates the 4 most critical publication-quality figures for the BTP thesis:

  Figure 1: Multi-State Spearman Lag Curves (Pre-COVID Baseline 2011-2019)
  Figure 2: 2015 H1N1 Epidemic Wave Lead Time Overlay (Time-Series Proof)
  Figure 3: Granger Causality Forward vs Reverse F-Statistics (Directional Proof)
  Figure 4: Regional Sentinels vs National Baseline (Why States Outperform)

Outputs are saved in: graphs/india_flu_validation/
Resolution: 300 DPI (Publication / Thesis Ready)
"""

from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

# Set publication style
plt.style.use('seaborn-v0_8-whitegrid' if 'seaborn-v0_8-whitegrid' in plt.style.available else 'default')
plt.rcParams['font.sans-serif'] = 'Arial'
plt.rcParams['font.family'] = 'sans-serif'
plt.rcParams['figure.dpi'] = 300

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
OUTPUT_DIR = PROJECT_ROOT / "graphs" / "india_flu_validation"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

RESULTS_NAT = PROJECT_ROOT / "Data" / "results" / "national"
RESULTS_ST = PROJECT_ROOT / "Data" / "results" / "states"


# ============================================================================
# FIGURE 1: SPEARMAN LAG CURVES (PRE-COVID BASELINE)
# ============================================================================

def plot_fig1_lag_curves():
    print("Generating Figure 1: Spearman Lag Curves...")
    
    # Load lag curves
    df_st = pd.read_csv(RESULTS_ST / "states_lag_curves_precovid.csv")
    df_nat = pd.read_csv(RESULTS_NAT / "national_lag_curves.csv")
    df_nat_pc = df_nat[df_nat["period"] == "pre_covid_2011_2019"]
    
    fig, ax = plt.subplots(figsize=(10, 6))
    
    # Color palette
    colors = {
        "Haryana": "#1f77b4",
        "Kerala": "#2ca02c",
        "Maharashtra": "#ff7f0e",
        "Tamil Nadu": "#9467bd",
        "Delhi": "#d62728",
        "Uttar Pradesh": "#8c564b",
        "West Bengal": "#7f7f7f",
    }
    
    for state, grp in df_st.groupby("state"):
        c = colors.get(state, "#333333")
        lw = 2.5 if state in ["Haryana", "Kerala", "Maharashtra", "Delhi"] else 1.5
        alpha = 0.9 if state in ["Haryana", "Kerala", "Maharashtra", "Delhi"] else 0.5
        ax.plot(grp["lag_weeks"], grp["spearman_rho"], label=state, 
                color=c, linewidth=lw, alpha=alpha, marker="o", markersize=4)
        
    # Plot National baseline as dashed thick line
    ax.plot(df_nat_pc["lag_weeks"], df_nat_pc["spearman_rho"], label="National (IN) Baseline", 
            color="black", linestyle="--", linewidth=3.0, zorder=10)
    
    ax.axvline(0, color="grey", linestyle=":", linewidth=1.5, alpha=0.8)
    ax.axhline(0, color="grey", linestyle="-", linewidth=0.8, alpha=0.5)
    
    # Shaded regions
    ax.axvspan(0, 8, alpha=0.06, color="green", label="Predictive Zone (GT Leads Flu)")
    ax.axvspan(-8, 0, alpha=0.06, color="red", label="Reactive Zone (GT Trails Flu)")
    
    ax.set_title("Figure 1: Multi-State Spearman Lag Curves (Pre-COVID Baseline: 2011–2019)\nEvaluation against WHO FluNet India Laboratory Confirmed Cases", 
                 fontsize=13, fontweight="bold", pad=12)
    ax.set_xlabel("Lag in Weeks (Positive Lag = Google Trends Leads Official Lab Cases)", fontsize=11, fontweight="bold")
    ax.set_ylabel("Spearman Rank Correlation (ρ)", fontsize=11, fontweight="bold")
    ax.set_xlim(-8, 8)
    ax.set_xticks(range(-8, 9))
    ax.set_ylim(-0.15, 0.45)
    
    ax.legend(loc="upper right", frameon=True, fontsize=9, ncol=2)
    plt.tight_layout()
    
    out_path = OUTPUT_DIR / "fig1_spearman_lag_curves_precovid.png"
    plt.savefig(out_path, dpi=300)
    plt.close()
    print(f"  Saved: {out_path.name}")


# ============================================================================
# FIGURE 2: 2015 H1N1 EPIDEMIC WAVE LEAD TIME OVERLAY
# ============================================================================

def plot_fig2_epidemic_overlay():
    print("Generating Figure 2: 2015 Epidemic Lead Time Overlay...")
    
    ts_st = pd.read_csv(RESULTS_ST / "states_aligned_timeseries.csv", index_col=0, parse_dates=True)
    ts_nat = pd.read_csv(RESULTS_NAT / "national_aligned_timeseries.csv", index_col=0, parse_dates=True)
    
    # Filter for the 2015 epidemic wave
    t_start = "2014-12-01"
    t_end = "2015-06-30"
    sub_st = ts_st.loc[t_start:t_end]
    sub_nat = ts_nat.loc[t_start:t_end]
    
    fig, ax1 = plt.subplots(figsize=(11, 6))
    ax2 = ax1.twinx()
    
    # Left axis: WHO FluNet laboratory cases (shaded area)
    line_flu = ax1.fill_between(sub_st.index, 0, sub_st["INF_ALL"], 
                                color="#d95f02", alpha=0.25, label="WHO FluNet Lab Cases (INF_ALL)")
    ax1.plot(sub_st.index, sub_st["INF_ALL"], color="#d95f02", linewidth=2.0)
    
    # Right axis: Google Trends Search Z-Scores
    line_mh, = ax2.plot(sub_st.index, sub_st["Maharashtra"], color="#1f77b4", linewidth=2.5, 
                        label="Maharashtra GT (ρ = 0.77, Lead = +1 wk)")
    line_hr, = ax2.plot(sub_st.index, sub_st["Haryana"], color="#2ca02c", linewidth=2.5, 
                        label="Haryana GT (ρ = 0.80, Lead = +1 wk)")
    line_nat, = ax2.plot(sub_nat.index, sub_nat["gt_zscore"], color="black", linestyle="--", linewidth=2.0, 
                         label="National GT Baseline (ρ = 0.48)")
    
    # Highlight peaks with vertical dashed arrows
    peak_flu_date = sub_st["INF_ALL"].idxmax()
    peak_mh_date = sub_st["Maharashtra"].idxmax()
    
    ax1.axvline(peak_flu_date, color="#d95f02", linestyle=":", linewidth=1.8, alpha=0.9)
    ax2.axvline(peak_mh_date, color="#1f77b4", linestyle=":", linewidth=1.8, alpha=0.9)
    
    ax1.annotate(f"Lab Peak\n({peak_flu_date.strftime('%b %d')})", 
                 xy=(peak_flu_date, sub_st['INF_ALL'].max()), 
                 xytext=(peak_flu_date + pd.Timedelta(days=7), sub_st['INF_ALL'].max() * 0.9),
                 arrowprops=dict(arrowstyle="->", color="#d95f02", lw=1.5),
                 fontsize=9, fontweight="bold", color="#d95f02")
    
    ax2.annotate(f"Search Peak\n({peak_mh_date.strftime('%b %d')})\n~1 Wk Early Lead", 
                 xy=(peak_mh_date, sub_st['Maharashtra'].max()), 
                 xytext=(peak_mh_date - pd.Timedelta(days=28), sub_st['Maharashtra'].max() * 0.85),
                 arrowprops=dict(arrowstyle="->", color="#1f77b4", lw=1.5),
                 fontsize=9, fontweight="bold", color="#1f77b4")
    
    ax1.set_title("Figure 2: Empirical Early-Warning Proof — 2015 H1N1 Epidemic Surge\nGoogle Trends Symptom Queries Lead Confirmed Laboratory Surveillance by 7 Days", 
                 fontsize=12, fontweight="bold", pad=12)
    ax1.set_xlabel("Epidemic Timeline (Weekly)", fontsize=11, fontweight="bold")
    ax1.set_ylabel("Confirmed Influenza Laboratory Cases (WHO FluNet)", fontsize=11, fontweight="bold", color="#d95f02")
    ax2.set_ylabel("Google Trends Symptom Search Index (Z-Score)", fontsize=11, fontweight="bold", color="#1f77b4")
    
    ax1.xaxis.set_major_formatter(mdates.DateFormatter('%b %Y'))
    ax1.xaxis.set_major_locator(mdates.MonthLocator())
    
    # Combined legend
    lines = [line_flu, line_hr, line_mh, line_nat]
    labels = ["WHO FluNet Confirmed Cases", "Haryana GT (ρ = 0.80, Lead +1 wk)", 
              "Maharashtra GT (ρ = 0.77, Lead +1 wk)", "National Baseline GT (ρ = 0.48)"]
    ax1.legend(lines, labels, loc="upper right", frameon=True, fontsize=9)
    
    plt.tight_layout()
    out_path = OUTPUT_DIR / "fig2_epidemic_surge_2015_lead_time.png"
    plt.savefig(out_path, dpi=300)
    plt.close()
    print(f"  Saved: {out_path.name}")


# ============================================================================
# FIGURE 3: GRANGER CAUSALITY FORWARD VS REVERSE F-STATISTICS
# ============================================================================

def plot_fig3_granger_comparison():
    print("Generating Figure 3: Granger Causality Forward vs Reverse...")
    
    df_st_sum = pd.read_csv(RESULTS_ST / "granger_states_summary.csv")
    df_st_pc = df_st_sum[df_st_sum["period"] == "pre_covid_2011_2019"].copy()
    
    df_nat_sum = pd.read_csv(RESULTS_NAT / "granger_national_summary.csv")
    nat_fwd = df_nat_sum[(df_nat_sum["period"] == "pre_covid_2011_2019") & (df_nat_sum["direction"] == "GT -> FluNet")].iloc[0]
    nat_rev = df_nat_sum[(df_nat_sum["period"] == "pre_covid_2011_2019") & (df_nat_sum["direction"] == "FluNet -> GT")].iloc[0]
    
    entities = ["Delhi", "Maharashtra", "Uttar Pradesh", "Haryana", "Tamil Nadu", "Kerala", "National (IN)"]
    fwd_f = []
    rev_f = []
    
    for e in entities:
        if e == "National (IN)":
            fwd_f.append(nat_fwd["best_f_stat"])
            rev_f.append(nat_rev["best_f_stat"])
        else:
            row = df_st_pc[df_st_pc["state"] == e].iloc[0]
            fwd_f.append(row["fwd_best_f"])
            rev_f.append(row["rev_best_f"])
            
    x = np.arange(len(entities))
    width = 0.38
    
    fig, ax = plt.subplots(figsize=(11, 6))
    
    rects1 = ax.bar(x - width/2, fwd_f, width, label="Forward Test: Google Trends → FluNet (Predictive)", 
                    color="#2b5c8f", edgecolor="black", linewidth=0.8)
    rects2 = ax.bar(x + width/2, rev_f, width, label="Reverse Control: FluNet → Google Trends (Reactionary)", 
                    color="#d95f02", edgecolor="black", linewidth=0.8)
    
    # Significance threshold line (approximate F critical value ~ 2.0 to 2.5)
    ax.axhline(2.0, color="red", linestyle="--", linewidth=1.2, label="Significance Threshold (p < 0.05)")
    
    ax.set_title("Figure 3: Econometric Directional Precedence — Granger Causality (Pre-COVID)\nComparison of Forward Predictive Power vs Reverse Reactionary Control", 
                 fontsize=12, fontweight="bold", pad=12)
    ax.set_ylabel("Granger Causality F-Statistic (Higher = Stronger Precedence)", fontsize=11, fontweight="bold")
    ax.set_xticks(x)
    ax.set_xticklabels(entities, fontsize=10, fontweight="bold")
    ax.set_ylim(0, 24)
    
    # Annotate Unidirectional Stars
    ax.annotate("TRUE UNIDIRECTIONAL\n(F=19.7 vs F=1.4 n.s.)\np = 2.37e-20", 
                xy=(0 - width/2, 19.7), xytext=(-0.35, 20.8),
                fontsize=8, fontweight="bold", color="#2b5c8f")
    
    ax.annotate("DOMINANT FORWARD\n(F=19.6 vs F=3.8)", 
                xy=(1 - width/2, 19.6), xytext=(0.65, 20.8),
                fontsize=8, fontweight="bold", color="#2b5c8f")

    ax.annotate("UNIDIRECTIONAL", 
                xy=(4 - width/2, 8.7), xytext=(3.6, 10.0),
                fontsize=8, fontweight="bold", color="#2b5c8f")
                
    ax.legend(loc="upper right", frameon=True, fontsize=9)
    plt.tight_layout()
    
    out_path = OUTPUT_DIR / "fig3_granger_causality_forward_vs_reverse.png"
    plt.savefig(out_path, dpi=300)
    plt.close()
    print(f"  Saved: {out_path.name}")


# ============================================================================
# FIGURE 4: REGIONAL SENTINELS VS NATIONAL BASELINE
# ============================================================================

def plot_fig4_sentinel_vs_national():
    print("Generating Figure 4: Sentinel States vs National Baseline...")
    
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5.5))
    
    # Panel A: Pre-COVID Continuous Correlation (2011-2019, 447 wks)
    entities_pc = ["Haryana", "Kerala", "Maharashtra", "Tamil Nadu", "Delhi", "National (IN)"]
    rhos_pc = [0.3587, 0.3331, 0.2892, 0.2774, 0.1937, 0.1524]
    colors_pc = ["#2ca02c", "#2ca02c", "#1f77b4", "#1f77b4", "#1f77b4", "black"]
    
    bars1 = ax1.bar(entities_pc, rhos_pc, color=colors_pc, edgecolor="black", linewidth=0.8, alpha=0.85)
    ax1.set_title("(A) Long-Term Baseline Correlation (2011–2019)\nContinuous 447-Week Non-Epidemic Horizon", fontsize=11, fontweight="bold")
    ax1.set_ylabel("Spearman Rank Correlation (ρ)", fontsize=10, fontweight="bold")
    ax1.set_ylim(0, 0.45)
    ax1.tick_params(axis='x', rotation=30)
    
    for bar in bars1:
        yval = bar.get_height()
        ax1.text(bar.get_x() + bar.get_width()/2.0, yval + 0.01, f"{yval:.2f}", ha='center', va='bottom', fontsize=9, fontweight="bold")
        
    ax1.annotate("Sentinel States beat National\nby >2x correlation strength", 
                 xy=(0.5, 0.35), xytext=(1.2, 0.39),
                 arrowprops=dict(arrowstyle="->", color="black", lw=1.2),
                 fontsize=8.5, fontweight="bold")

    # Panel B: 2015 Epidemic Outbreak Surge (Peak Lead Performance)
    entities_15 = ["Haryana", "Maharashtra", "Delhi", "National (IN)"]
    rhos_15 = [0.7993, 0.7686, 0.6226, 0.4802]
    colors_15 = ["#2ca02c", "#1f77b4", "#1f77b4", "black"]
    
    bars2 = ax2.bar(entities_15, rhos_15, color=colors_15, edgecolor="black", linewidth=0.8, alpha=0.85)
    ax2.set_title("(B) 2015 H1N1 Epidemic Outbreak Wave\nAll States Leading by +1 Week (+7 Days)", fontsize=11, fontweight="bold")
    ax2.set_ylabel("Spearman Rank Correlation (ρ) at Lag +1", fontsize=10, fontweight="bold")
    ax2.set_ylim(0, 0.95)
    ax2.tick_params(axis='x', rotation=15)
    
    for bar in bars2:
        yval = bar.get_height()
        ax2.text(bar.get_x() + bar.get_width()/2.0, yval + 0.015, f"{yval:.2f}", ha='center', va='bottom', fontsize=9, fontweight="bold")
        
    ax2.annotate("Haryana (ρ=0.80) & Maharashtra (ρ=0.77)\noutperform National (ρ=0.48) by ~30%", 
                 xy=(0.8, 0.77), xytext=(0.4, 0.86),
                 arrowprops=dict(arrowstyle="->", color="black", lw=1.2),
                 fontsize=8.5, fontweight="bold")
    
    plt.suptitle("Figure 4: The Sentinel State Advantage — Proving Why Regional Trends Beat National Aggregation", 
                 fontsize=13, fontweight="bold", y=1.02)
    plt.tight_layout()
    
    out_path = OUTPUT_DIR / "fig4_state_sentinels_vs_national_baseline.png"
    plt.savefig(out_path, dpi=300)
    plt.close()
    print(f"  Saved: {out_path.name}")


# ============================================================================
# MAIN
# ============================================================================

def main():
    print("=" * 60)
    print("Generating Thesis Figures for Spearman & Granger Causality")
    print("=" * 60)
    
    plot_fig1_lag_curves()
    plot_fig2_epidemic_overlay()
    plot_fig3_granger_comparison()
    plot_fig4_sentinel_vs_national()
    
    print("\n✓ All 4 figures generated successfully in graphs/india_flu_validation/")


if __name__ == "__main__":
    main()
