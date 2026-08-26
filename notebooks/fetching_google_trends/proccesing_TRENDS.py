import pandas as pd

# 1. Set your exact manual paths
input_file_path = r"E:\Projects\BTP\Data\Raw_data\trends_raw_individual.csv"
output_file_path = r"E:\Projects\BTP\Data\Clean\google-trends-processed.csv"

# 2. Load the raw data (we DO NOT overwrite this file)
df = pd.read_csv(input_file_path)

# 3. BULLETPROOF RENAME: Force the very first column (index 0) to be 'date'
# This stops the script from crashing if the first column is named 'ate' or 'Unnamed: 0'
df.rename(columns={df.columns[0]: 'date'}, inplace=True)

# 4. Isolate your 3 validated behavioral proxies
core_columns = ['date', 'حمى', 'جفاف', 'عيادة']
df_clean = df[core_columns].copy()

# 5. Calculate the composite index (mean of the 3 terms)
df_clean['Digital_Panic_Index'] = df_clean[[
    'حمى', 'جفاف', 'عيادة']].mean(axis=1).round(2)

# 6. Save to your exact manual location in the Clean folder
df_clean.to_csv(output_file_path, index=False)

print(f"✅ Success! Compressed index saved exactly to:\n{output_file_path}")
print("-" * 50)
print(df_clean.head(5))
