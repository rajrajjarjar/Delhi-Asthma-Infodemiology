import pandas as pd
df = pd.read_stata("dia_sample.dta")
print("file loading")
print(df.columns.tolist())
reader = pd.io.stata.StataReader("dia_sample.dta")
labels = reader.variable_labels()
for col in df.columns:
    if 'clin' in col:
        print(f"Column '{col}' -> {labels.get(col, 'No Label')}")
        import pandas as pd


print(f"\n🚨 TRUE RAW DATASET SIZE: {len(df)} patients!")
print("--------------------------------------------------")

print("\n1. Let's look at the raw date format causing the warning (First 10 rows):")
# We print the raw 'clin2' column before any pandas datetime conversion
print(df['clin2'].head(10).tolist())

print("\n2. Let's look at the true Cholera (v_chol) counts including nulls:")
# value_counts(dropna=False) forces pandas to count the hidden Null/NaN values
print(df['v_chol'].value_counts(dropna=False))
