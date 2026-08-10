import pandas as pd

# load your sample stata data file
df = pd.read_stata('dia_sample.dta')

# DEBUG: print the first 5 rows of the raw data to see what it looks like
print("--- RAW DATA PRE-PROCESSING ---")
print(df[['clin2', 'v_chol']].head())
print("-------------------------------\n")

# parse the date (removed strict formatting so it auto-detects)
df['date_parsed'] = pd.to_datetime(df['clin2'], errors='coerce')

# extract year and week
df['year'] = df['date_parsed'].dt.year
df['week'] = df['date_parsed'].dt.isocalendar().week

# flag the positive O1 cases
df['is_o1'] = df['v_chol'].astype(str).str.contains(
    'O1', na=False, case=False).astype(int)

# collapse and group by year and week
summary = df.groupby(['year', 'week']).agg(
    total_admissions=('v_chol', 'count'),
    positive_o1_cases=('is_o1', 'sum')
).reset_index()

# drop any rows where the date failed to parse (year is NaN)
summary = summary.dropna(subset=['year'])

# sort and print
summary = summary.sort_values(by=['year', 'week'])
print("--- FINAL COLLAPSED DATA ---")
print(summary.to_string(index=False))
