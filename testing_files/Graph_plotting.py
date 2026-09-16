"""
plot_region6_lag_curves.py
===========================

Reads R6_PerState_LagCurves.xlsx (full Spearman rho vs. lag, for all 5
HHS Region 6 states) and produces:

    - 5 individual PNGs, one lag curve per state
    - 1 combined PNG with all 5 states overlaid, for direct comparison

Each plot marks lag=0 (synchronous) with a dashed reference line and
annotates the peak rho (best lag) for that state, so the "which state
leads/trails/is synchronous" read is visible at a glance -- not just in
the underlying numbers.
"""

import matplotlib.pyplot as plt
import pandas as pd

# ----------------------------------------------------------------------
# CONFIG -- adjust the input path to wherever you saved the xlsx
# ----------------------------------------------------------------------
INPUT_FILE = 'R6_PerState_LagCurves.xlsx'
OUTPUT_DIR = '.'   # change to a folder path if you want PNGs elsewhere

# Fixed colour per state so individual and combined plots stay consistent
STATE_COLORS = {
    'Texas': '#d62728',
    'Louisiana': '#1f77b4',
    'Arkansas': '#2ca02c',
    'New Mexico': '#9467bd',
    'Oklahoma': '#ff7f0e',
}


def load_data(path: str) -> pd.DataFrame:
    df = pd.read_excel(path)
    df = df.sort_values(['state', 'lag_weeks']).reset_index(drop=True)
    return df


def plot_individual(df: pd.DataFrame, state: str, color: str):
    """One figure per state: rho vs lag, peak lag annotated."""
    sub = df[df['state'] == state]

    # The single strongest lag for this state -- what we're annotating.
    best_row = sub.loc[sub['spearman_rho'].idxmax()]
    best_lag = int(best_row['lag_weeks'])
    best_rho = best_row['spearman_rho']

    fig, ax = plt.subplots(figsize=(7, 4.5))

    ax.plot(sub['lag_weeks'], sub['spearman_rho'],
            marker='o', color=color, linewidth=2)

    # lag = 0 reference line: left of it = Trends trails ILI,
    # right of it = Trends leads ILI (see sign convention below).
    ax.axvline(0, color='gray', linestyle='--', linewidth=1, alpha=0.7)

    # Mark and label the peak.
    ax.scatter([best_lag], [best_rho], color='black', zorder=5, s=60)
    ax.annotate(
        f'peak: lag={best_lag:+d}, rho={best_rho:.3f}',
        xy=(best_lag, best_rho),
        xytext=(10, 12), textcoords='offset points',
        fontsize=9, fontweight='bold',
    )

    ax.set_title(f'{state} — Google Trends vs. Region 6 ILI (Spearman)')
    ax.set_xlabel(
        'Lag (weeks)  [negative = Trends trails, positive = Trends leads]')
    ax.set_ylabel('Spearman rho')
    ax.grid(True, alpha=0.3)
    fig.tight_layout()

    out_path = f'{OUTPUT_DIR}/lag_curve_{state.replace(" ", "_")}.png'
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    print(f'Saved {out_path}')


def plot_combined(df: pd.DataFrame):
    """All 5 states overlaid on one figure, for direct shape/peak comparison."""
    fig, ax = plt.subplots(figsize=(9, 5.5))

    for state, color in STATE_COLORS.items():
        sub = df[df['state'] == state]
        if sub.empty:
            continue
        ax.plot(sub['lag_weeks'], sub['spearman_rho'],
                marker='o', markersize=4, linewidth=2,
                color=color, label=state)

    ax.axvline(0, color='gray', linestyle='--', linewidth=1, alpha=0.7)

    ax.set_title('HHS Region 6 — Spearman Lag Curves, All States Compared')
    ax.set_xlabel(
        'Lag (weeks)  [negative = Trends trails, positive = Trends leads]')
    ax.set_ylabel('Spearman rho')
    ax.legend(title='State', loc='best')
    ax.grid(True, alpha=0.3)
    fig.tight_layout()

    out_path = f'{OUTPUT_DIR}/lag_curve_combined_all_states.png'
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    print(f'Saved {out_path}')


if __name__ == '__main__':
    df = load_data(INPUT_FILE)

    for state in df['state'].unique():
        color = STATE_COLORS.get(state, '#333333')
        plot_individual(df, state, color)

    plot_combined(df)
