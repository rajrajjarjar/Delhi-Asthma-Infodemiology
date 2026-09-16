import pandas as pd
import numpy as np
import time
from pytrends.request import TrendReq
from scipy.stats import spearmanr

# --- CONFIGURATION ---
CSV_FILE = 'E:/Projects/BTP/testing_files/fluuu/ILLnet2.2.csv'
REGION = 'Region 6'
STATES = ['US-TX', 'US-LA', 'US-AR', 'US-NM', 'US-OK']
START_YR, END_YR = 2015, 2019
START_DATE, END_DATE = '2015-01-04', '2019-12-28'

# Your 8 target keywords
TARGET_KWS = [
    'flu symptoms', 'fever', 'sore throat', 'body aches',
    'chills', 'cough', 'how long does flu last', 'flu or cold'
]
ANCHOR_KW = 'weather'

# --- 1. PREPROCESS CDC DATA ---


def get_cdc_target():
    print(f"Loading CDC data for {REGION}...")
    df = pd.read_csv(CSV_FILE, skiprows=1)
    df = df[(df['REGION'] == REGION) & (df['YEAR'] >= START_YR)
            & (df['YEAR'] <= END_YR)].copy()

    # Create standard YYYYWW index
    df['epiweek'] = df['YEAR'].astype(
        str) + df['WEEK'].astype(str).str.zfill(2)
    df['epiweek'] = df['epiweek'].astype(int)

    df = df.sort_values('epiweek').reset_index(drop=True)
    return df[['epiweek', '% WEIGHTED ILI']].rename(columns={'% WEIGHTED ILI': 'ili_percent'})

# --- 2. FETCH & NORMALIZE GOOGLE TRENDS ---


def fetch_normalized_trends():
    pytrends = TrendReq(hl='en-US', tz=360, retries=3, backoff_factor=1)
    timeframe = f'{START_DATE} {END_DATE}'

    # Split the 8 keywords into chunks of 4 (so we can prepend the anchor term, totaling 5)
    kw_chunks = [TARGET_KWS[i:i + 4] for i in range(0, len(TARGET_KWS), 4)]

    state_dataframes = []

    for state in STATES:
        print(f"Fetching Google Trends for {state}...")
        state_combined = None

        for chunk in kw_chunks:
            payload = [ANCHOR_KW] + chunk
            pytrends.build_payload(
                kw_list=payload, geo=state, timeframe=timeframe)
            df_gt = pytrends.interest_over_time()

            if df_gt.empty:
                continue

            df_gt = df_gt.drop(columns=['isPartial'], errors='ignore')

            # THE NORMALIZATION: Scale each keyword against the anchor term
            for kw in chunk:
                # Add +1 to anchor to avoid division by zero if weather drops to 0
                df_gt[f'{kw}_norm'] = df_gt[kw] / (df_gt[ANCHOR_KW] + 1)

            # Keep only the normalized columns
            norm_cols = [f'{kw}_norm' for kw in chunk]
            if state_combined is None:
                state_combined = df_gt[norm_cols]
            else:
                state_combined = state_combined.join(df_gt[norm_cols])

            time.sleep(2)  # Prevent API bans

        if state_combined is not None:
            # Create a composite score for the state (average of all 8 normalized terms)
            state_combined['state_composite'] = state_combined.mean(axis=1)
            state_dataframes.append(state_combined['state_composite'])

    # Combine all 5 states and average them to create the Regional Index
    df_region_trends = pd.concat(state_dataframes, axis=1)
    df_region_trends['regional_index'] = df_region_trends.mean(axis=1)

    return df_region_trends[['regional_index']].reset_index()

# --- 3. ALIGN & RUN SPEARMAN ---


def run_lag_analysis(cdc_df, trends_df, max_lag=4):
    print("\nAligning data and calculating Spearman Rank...")
    cdc_df['row_idx'] = range(len(cdc_df))
    trends_df['row_idx'] = range(len(trends_df))

    merged = pd.merge(cdc_df, trends_df, on='row_idx')

    results = []
    for lag in range(-max_lag, max_lag + 1):
        shifted_trend = merged['regional_index'].shift(lag)

        valid_idx = shifted_trend.notna() & merged['ili_percent'].notna()
        rho, p_val = spearmanr(
            shifted_trend[valid_idx], merged['ili_percent'][valid_idx])
        results.append(
            {'Lag (Weeks)': lag, 'Spearman Rho': rho, 'p-value': p_val})

    results_df = pd.DataFrame(results).sort_values(
        by='Lag (Weeks)').reset_index(drop=True)

    # Return BOTH the results and the merged dataframe
    return results_df, merged


# --- EXECUTE ---
if __name__ == "__main__":
    cdc_target = get_cdc_target()
    trends_index = fetch_normalized_trends()

    # Unpack both return values here
    results_df, merged = run_lag_analysis(cdc_target, trends_index)

    print("\n=== HHS REGION 6 LAG VALIDATION ===")
    print(results_df.to_string(index=False))

    # Now both files will save cleanly!
    results_df.to_excel("Real_Region6_Lag_Results.xlsx", index=False)
    merged.to_excel("Real_Region6_Merged_Data.xlsx", index=False)
    print("\nFiles saved successfully!")
