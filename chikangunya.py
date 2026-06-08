import pandas as pd
df = pd.read_stata("sample.dta")
print("file loading")
print(df.columns.tolist())
