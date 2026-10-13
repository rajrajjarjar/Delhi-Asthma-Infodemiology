import pandas as pd
import matplotlib.pyplot as plt

# =========================
# Load data
# =========================
file_path = r"E:/Projects/BTP/Data/Clean/INDIA/Influenza/india_flu.csv"

df = pd.read_csv(file_path)

# =========================
# Prepare data
# =========================
df["ISO_WEEKSTARTDATE"] = pd.to_datetime(df["ISO_WEEKSTARTDATE"])
df["INF_ALL"] = pd.to_numeric(df["INF_ALL"], errors="coerce")

df = df.dropna(subset=["ISO_WEEKSTARTDATE", "INF_ALL"])

df["Year"] = df["ISO_WEEKSTARTDATE"].dt.year
df["Month"] = df["ISO_WEEKSTARTDATE"].dt.month

# Keep only 2021–2024
years = [2021, 2022, 2023, 2024]
df = df[df["Year"].isin(years)]

# =========================
# Monthly cases
# =========================
monthly = (
    df.groupby(["Year", "Month"])["INF_ALL"]
      .sum()
      .reset_index()
)

# Pivot
data = monthly.pivot(
    index="Month",
    columns="Year",
    values="INF_ALL"
)

# =========================
# Plot
# =========================
fig, ax = plt.subplots(figsize=(12, 6.5))

for year in years:
    ax.plot(
        data.index,
        data[year],
        linewidth=3,
        label=str(year)
    )

# Month labels
months = [
    "Jan", "Feb", "Mar", "Apr",
    "May", "Jun", "Jul", "Aug",
    "Sep", "Oct", "Nov", "Dec"
]

ax.set_xticks(range(1, 13))
ax.set_xticklabels(months, fontsize=11)

# Labels
ax.set_xlabel("Month", fontsize=13, labelpad=10)
ax.set_ylabel("Influenza Cases", fontsize=13, labelpad=10)

# Title
ax.set_title(
    "Monthly Influenza Cases in India (2021–2024)",
    fontsize=18,
    fontweight="bold",
    pad=18
)

# Subtle horizontal grid
ax.grid(
    axis="y",
    linestyle="--",
    linewidth=0.7,
    alpha=0.25
)

# Remove unnecessary borders
ax.spines["top"].set_visible(False)
ax.spines["right"].set_visible(False)

# Legend
ax.legend(
    title="Year",
    ncol=4,
    loc="upper center",
    bbox_to_anchor=(0.5, 1.02),
    frameon=False,
    fontsize=11
)

# Make layout clean
plt.tight_layout()

plt.show()
