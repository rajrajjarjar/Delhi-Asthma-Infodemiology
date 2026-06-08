import pandas as pd
df = pd.read_stata("dia_sample.dta")
print("file loading")
print(df.columns.tolist())
