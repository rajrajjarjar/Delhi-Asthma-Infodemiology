
import pandas as pd
import matplotlib.pyplot as plt

# 1. Load your two pristine datasets
df_clinical = pd.read_csv(r"E:\Projects\BTP\Data\Clean\merged_clean-first.csv")
df_trends = pd.read_csv(
    r"E:\Projects\BTP\Data\Clean\google-trends-processed.csv")

# 2. Convert date columns to actual pandas Datetime objects
df_clinical['Date'] = pd.to_datetime(df_clinical['Date'])
df_trends['date'] = pd.to_datetime(df_trends['date'])

# 3. Isolate one specific governorate (Sana'a) for the eye candy
df_sanaa = df_clinical[df_clinical['Governorate'] == "Sana'a"].copy()

# 4. Merge the two datasets together based on the exact dates
df_merged = pd.merge(df_sanaa, df_trends, left_on='Date',
                     right_on='date', how='inner')
df_merged = df_merged.sort_values('Date')

# 5. Build the aesthetic dual-axis graph
fig, ax1 = plt.subplots(figsize=(14, 7))

# Plot 1: Clinical Cases (Red)
color_clinical = '#d62728'
ax1.set_xlabel('Timeline (2017 - 2018)', fontsize=12, fontweight='bold')
ax1.set_ylabel('New Cholera Cases (Sana\'a)',
               color=color_clinical, fontsize=12, fontweight='bold')
ax1.plot(df_merged['Date'], df_merged['New_Cases'], color=color_clinical,
         linewidth=2.5, marker='o', label='Clinical Cases')
ax1.tick_params(axis='y', labelcolor=color_clinical)
ax1.grid(True, alpha=0.3)

# Plot 2: Digital Panic Index (Blue)
ax2 = ax1.twinx()
color_trends = '#1f77b4'
ax2.set_ylabel('Digital Panic Index (Google Trends RSV)',
               color=color_trends, fontsize=12, fontweight='bold')
ax2.plot(df_merged['Date'], df_merged['Digital_Panic_Index'], color=color_trends,
         linewidth=2.5, linestyle='--', marker='s', label='Digital Panic')
ax2.tick_params(axis='y', labelcolor=color_trends)

# Final Polish
plt.title('Spatiotemporal Overlay: Sana\'a Outbreak vs. Digital Panic Index',
          fontsize=16, fontweight='bold', pad=15)
fig.tight_layout()

# Display the masterpiece
plt.show()
