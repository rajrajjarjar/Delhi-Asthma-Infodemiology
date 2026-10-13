"""
plot_hhs_seasonal_peaks.py
============================

Compares seasonal flu timing across all 10 HHS Regions using CDC ILINet's
'% WEIGHTED ILI'. Raw case counts aren't needed for this: %ILI moves
proportionally with case burden, so peak TIMING (which month each region
peaks in) is preserved even though the absolute Y-axis isn't a raw case
count. (If you later want to compare MAGNITUDE across regions rather than
just timing, that's when raw case counts would start to matter.)

Produces:
    hhs_seasonal_overlay.png   - all 10 regions' avg %ILI by calendar month,
                                  overlaid on one chart (the main comparison)
    hhs_peak_month_summary.png - bar chart: each region's peak month + intensity
    hhs_peak_months.xlsx       - the underlying numbers (peak month, peak ILI,
                                  and the full month-by-month curve per region)
"""

import calendar

import matplotlib.pyplot as plt
import pandas as pd

# ----------------------------------------------------------------------
# CONFIG
# ----------------------------------------------------------------------
# the HHS Region ILINet export
CSV_FILE = 'E:/Projects/BTP/testing_files/fluuu/ILLnet2.2.csv'
OUTPUT_DIR = 'E:/Projects/BTP/testing_files/hhs_season peak'

# Fixed color per region so multiple charts stay visually consistent
REGION_COLORS = {
    'Region 1': '#1f77b4', 'Region 2': '#ff7f0e', 'Region 3': '#2ca02c',
    'Region 4': '#d62728', 'Region 5': '#9467bd', 'Region 6': '#8c564b',
    'Region 7': '#e377c2', 'Region 8': '#7f7f7f', 'Region 9': '#bcbd22',
    'Region 10': '#17becf',
}


def mmwr_week_start_date(year: int, week: int) -> pd.Timestamp:
    """Same MMWR-week-to-calendar-date logic used in the lag validation script,
    kept consistent so peak-month results line up with earlier analysis."""
    jan4 = pd.Timestamp(year=year, month=1, day=4)
    days_since_sunday = (jan4.dayofweek + 1) % 7
    week1_start = jan4 - pd.Timedelta(days=days_since_sunday)
    return week1_start + pd.Timedelta(weeks=week - 1)


def load_data(path: str) -> pd.DataFrame:
    # row 0 is a title banner, not the header
    df = pd.read_csv(path, skiprows=1)
    df['ili'] = pd.to_numeric(df['% WEIGHTED ILI'], errors='coerce')

    df['week_start'] = [
        mmwr_week_start_date(int(y), int(w))
        for y, w in zip(df['YEAR'], df['WEEK'])
    ]
    df['month'] = df['week_start'].dt.month

    return df


def compute_monthly_curves(df: pd.DataFrame) -> pd.DataFrame:
    """Average %ILI per calendar month, per region, across all years in the
    file. This is the seasonal 'shape' for each region -- averaging across
    years smooths out any single unusual season."""
    monthly = (
        df.groupby(['REGION', 'month'])['ili']
        .mean()
        .reset_index()
        .rename(columns={'ili': 'avg_ili'})
    )
    return monthly


def summarise_peaks(monthly: pd.DataFrame) -> pd.DataFrame:
    """Reduce each region's monthly curve to its single peak month."""
    rows = []
    for region, grp in monthly.groupby('REGION'):
        peak_row = grp.loc[grp['avg_ili'].idxmax()]
        rows.append({
            'region': region,
            'peak_month_num': int(peak_row['month']),
            'peak_month_name': calendar.month_name[int(peak_row['month'])],
            'peak_avg_ili': round(peak_row['avg_ili'], 3),
        })
    return (pd.DataFrame(rows)
            .sort_values('region', key=lambda s: s.str.extract(r'(\d+)')[0].astype(int))
            .reset_index(drop=True))


def plot_overlay(monthly: pd.DataFrame):
    """Main comparison chart: all 10 regions' seasonal curves on one plot."""
    fig, ax = plt.subplots(figsize=(10, 6))

    for region, color in REGION_COLORS.items():
        sub = monthly[monthly['REGION'] == region].sort_values('month')
        if sub.empty:
            continue
        ax.plot(sub['month'], sub['avg_ili'],
                marker='o', markersize=4, linewidth=2,
                color=color, label=region)

    ax.set_xticks(range(1, 13))
    ax.set_xticklabels([calendar.month_abbr[m] for m in range(1, 13)])
    ax.set_xlabel('Month')
    ax.set_ylabel('Average % Weighted ILI (across all years)')
    ax.set_title('Seasonal ILI Timing by HHS Region')
    ax.legend(title='Region', loc='upper right', ncol=2, fontsize=8)
    ax.grid(True, alpha=0.3)
    fig.tight_layout()

    out_path = f'{OUTPUT_DIR}/hhs_seasonal_overlay.png'
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    print(f'Saved {out_path}')


def plot_peak_summary(peaks: pd.DataFrame):
    """Bar chart: each region's peak month (color) and peak intensity (height),
    for a quick side-by-side comparison of 'who peaks when, and how hard'."""
    fig, ax = plt.subplots(figsize=(10, 5.5))

    colors = [REGION_COLORS.get(r, '#333333') for r in peaks['region']]
    bars = ax.bar(peaks['region'], peaks['peak_avg_ili'], color=colors)

    # Label each bar with its peak month, since the bar height alone
    # doesn't show timing -- that's the whole point of this chart.
    for bar, month_name in zip(bars, peaks['peak_month_name']):
        ax.annotate(
            month_name,
            xy=(bar.get_x() + bar.get_width() / 2, bar.get_height()),
            xytext=(0, 4), textcoords='offset points',
            ha='center', fontsize=8, fontweight='bold',
        )

    ax.set_xlabel('HHS Region')
    ax.set_ylabel('Peak average % Weighted ILI')
    ax.set_title('Peak Month and Intensity by HHS Region')
    ax.grid(True, axis='y', alpha=0.3)
    plt.setp(ax.get_xticklabels(), rotation=30, ha='right')
    fig.tight_layout()

    out_path = f'{OUTPUT_DIR}/hhs_peak_month_summary.png'
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    print(f'Saved {out_path}')


if __name__ == '__main__':
    df = load_data(CSV_FILE)
    monthly = compute_monthly_curves(df)
    peaks = summarise_peaks(monthly)

    print(peaks.to_string(index=False))

    plot_overlay(monthly)
    plot_peak_summary(peaks)

    # Save the underlying numbers too, in case you want them for the writeup
    # or to cross-check against whatever second dataset you end up finding.
    with pd.ExcelWriter(f'{OUTPUT_DIR}/hhs_peak_months.xlsx') as writer:
        peaks.to_excel(writer, sheet_name='peak_summary', index=False)
        monthly.to_excel(writer, sheet_name='monthly_curves', index=False)

    print(f'\nSaved {OUTPUT_DIR}/hhs_peak_months.xlsx')
