# Yemen Cholera Governorate-Level Dataset
## Data Cleaning, Preprocessing & Audit Report

### 1. Dataset Overview

The dataset contains **governorate-level epidemiological data for the Yemen cholera outbreak**.

After preprocessing and cleaning, the dataset contains:

- **2,827 observations (rows)**
- **6 variables (columns)**
- **21 unique governorates**
- Date range: **22 May 2017 – 18 February 2018**
- **0 missing values**
- **0 duplicate Date + Governorate combinations**

The cleaned dataset is stored as:

`Data/Clean/merged_clean-first.csv`

---

# 2. Variables in the Dataset

The final dataset contains the following six columns:

| Column | Meaning | Data type after loading |
|---|---|---|
| `Date` | Reporting date | String containing valid dates |
| `Governorate` | Yemen governorate | String |
| `Cases` | Cumulative reported cholera cases | Integer |
| `Deaths` | Cumulative reported deaths | Integer |
| `New_Cases` | Incremental cases between observations | Float |
| `New_Cases_flag` | Indicates whether the observation required negative-correction handling | String |

### Important distinction

`Cases` is a **cumulative** measure.

`New_Cases` is an **incremental** measure calculated from changes in cumulative cases.

For example, if a governorate reports:

```text
Cases:
100 → 130 → 175

New_Cases:
100 → 30 → 45
```

The first observation is treated specially because there is no previous observation.

---

# 3. Governorate Standardization

The original data contained inconsistent spellings/names for some governorates.

The preprocessing standardized them so that the final dataset contains **21 unique governorates**:

- Abyan
- Aden
- Al Bayda
- Al Dhale'e
- Al Hudaydah
- Al Jawf
- Al Maharah
- Al Mahwit
- Amanat Al Asimah
- Amran
- Dhamar
- Hadramawt
- Hajjah
- Ibb
- Lahj
- Marib
- Raymah
- Sa'ada
- Sana'a
- Shabwah
- Taizz

The specifically identified standardizations were:

| Original name | Standardized name |
|---|---|
| `Al Mahrah` | `Al Maharah` |
| `Al-Hudaydah` | `Al Hudaydah` |
| `Al_Jawf` | `Al Jawf` |
| `Ma'areb` | `Marib` |
| `Moklla` | `Hadramawt` |
| `Say'on` | `Hadramawt` |

The final unique-governorate list contains the standardized names and does not contain the original inconsistent forms.

---

# 4. Mukalla and Sayun → Hadramawt

The preprocessing merged the district-level observations identified as Mukalla and Sayun into the `Hadramawt` governorate.

After cleaning:

- `Hadramawt` contains **114 observations**.
- There are **no duplicate Date + Governorate combinations**.

This is important because merging two sources into one governorate could potentially create multiple observations for the same date.

The duplicate audit found:

```text
Duplicate rows: 0
Duplicate Date + Governorate combinations: 0
```

Therefore, the final dataset maintains one observation per governorate/date combination.

---

# 5. Date Processing

The preprocessing converted the `Date` field to datetime.

After saving to CSV and loading the CSV again with `pd.read_csv()`, pandas reads the dates as strings by default. However, the audit confirmed that **all 2,827 date values can be successfully converted to valid dates**.

Audit result:

```text
Invalid dates: 0
```

Date range:

```text
Earliest: 2017-05-22
Latest:   2018-02-18
```

Therefore, there is no evidence of malformed or invalid dates.

For future analysis, the CSV can be loaded with:

```python
df = pd.read_csv(
    "Data/Clean/merged_clean-first.csv",
    parse_dates=["Date"]
)
```

so that `Date` is explicitly loaded as a pandas datetime column.

---

# 6. Missing-Value Audit

The dataset contains **no missing values**.

| Column | Missing values |
|---|---:|
| Date | 0 |
| Governorate | 0 |
| Cases | 0 |
| Deaths | 0 |
| New_Cases | 0 |
| New_Cases_flag | 0 |
| **Total** | **0** |

Therefore, all:

**2,827 × 6 = 16,962 cells**

contain a value.

This is useful because missing dates, governorates, case counts, or death counts could interfere with epidemiological calculations.

However, zero missing values does not by itself guarantee that all values are correct, which is why the additional audits were performed.

---

# 7. Data Types

The cleaned dataset was checked for appropriate data types.

Current types after loading the CSV:

```text
Date              str
Governorate       str
Cases             int64
Deaths            int64
New_Cases         float64
New_Cases_flag    str
```

`Cases` and `Deaths` are correctly represented as integers.

`New_Cases` is numeric (`float64`), which is appropriate because it was calculated using differences.

`Governorate` and `New_Cases_flag` are text fields.

The only apparent difference from the intended preprocessing is that `Date` is currently a string after reading the CSV. This is a normal consequence of CSV storage/loading rather than evidence of a failed preprocessing operation, because all dates successfully converted to valid datetime values.

---

# 8. Conversion of Cumulative Cases to New Cases

One of the most important preprocessing steps was converting cumulative `Cases` into incremental `New_Cases`.

The intended calculation is:

```text
New_Cases = Current Cases - Previous Cases
```

within each governorate, after chronological ordering.

The first observation of each governorate is treated separately:

```text
New_Cases = Cases
```

because there is no previous observation.

### Independent audit

The expected `New_Cases` values were recalculated independently from the cleaned `Cases` column.

Results:

```text
Total rows checked: 2827
Unexpected mismatches: 0
```

This means **all 2,827 observations matched the expected calculation** after accounting for the negative-correction rule.

This is strong evidence that the cumulative-to-incremental transformation was implemented correctly.

---

# 9. Handling Negative Cumulative Differences

Cumulative epidemiological reports can sometimes decrease because previously reported numbers are corrected.

For example:

```text
Previous cumulative Cases = 6
Current cumulative Cases  = 4

Difference = 4 - 6 = -2
```

A negative value cannot represent actual new cases.

The preprocessing therefore:

1. Detects the negative difference.
2. Sets `New_Cases` to `0`.
3. Sets `New_Cases_flag` to `corrected_negative`.

### Audit results

```text
Negative New_Cases remaining: 0
```

The flag distribution is:

| Flag | Number of rows |
|---|---:|
| `ok` | 2,825 |
| `corrected_negative` | 2 |
| **Total** | **2,827** |

The two corrected observations are:

| Date | Governorate | Cases | New_Cases | Flag |
|---|---|---:|---:|---|
| 2017-07-10 | Hadramawt | 4 | 0 | corrected_negative |
| 2017-10-10 | Hadramawt | 559 | 0 | corrected_negative |

These are **intentional corrections rather than preprocessing errors**.

---

# 10. First Observation Audit

For every governorate, the first chronological observation was checked.

The preprocessing rule was:

```text
First New_Cases = First Cases
```

Results:

```text
Governorates checked: 21
Correct first observations: 21
Mismatches: 0
```

Therefore, the first-observation handling worked correctly for **100% of governorates**.

Some governorates start later than others. For example:

- Most governorates begin on **2017-05-22**
- Al Maharah begins on **2017-06-10**
- Hadramawt begins on **2017-06-30**
- Sa'ada begins on **2017-05-27**
- Shabwah begins on **2017-05-27**

This explains why some governorates contain fewer observations.

---

# 11. Duplicate Audit

The dataset was checked for duplicate combinations of:

```text
Date + Governorate
```

Results:

```text
Duplicate rows: 0
Duplicate Date + Governorate combinations: 0
```

This means the final dataset does not contain multiple observations for the same governorate on the same date.

This is especially important after merging Mukalla and Sayun into Hadramawt.

---

# 12. Numerical Summary

The numerical variables were summarized using `.describe()`.

| Statistic | Cases | Deaths | New_Cases |
|---|---:|---:|---:|
| Count | 2,827 | 2,827 | 2,827 |
| Mean | 26,869.44 | 89.81 | 376.30 |
| Std. Dev. | 28,299.86 | 96.26 | 574.30 |
| Minimum | 2 | 0 | 0 |
| 25th percentile | 4,105.5 | 12 | 32 |
| Median | 17,585 | 60 | 199 |
| 75th percentile | 41,403 | 141 | 503 |
| Maximum | 155,908 | 422 | 9,216 |

### Interpretation

There are no negative values in any of the three numerical variables:

```text
Minimum Cases     = 2
Minimum Deaths    = 0
Minimum New_Cases = 0
```

The maximum cumulative case count is:

```text
155,908
```

The maximum cumulative death count is:

```text
422
```

The largest incremental increase between observations is:

```text
9,216 cases
```

These large values should not automatically be considered errors. Epidemiological outbreak data can naturally contain highly uneven case counts.

The mean is substantially higher than the median for `Cases` and `New_Cases`, indicating that the distributions are right-skewed. This means some observations have considerably larger values than typical observations.

---

# 13. Reporting Frequency

The number of observations differs slightly between governorates.

| Governorate | Observations |
|---|---:|
| Abyan | 136 |
| Aden | 136 |
| Al Bayda | 136 |
| Al Dhale'e | 136 |
| Al Hudaydah | 136 |
| Al Jawf | 136 |
| Al Maharah | 131 |
| Al Mahwit | 136 |
| Amanat Al Asimah | 136 |
| Amran | 136 |
| Dhamar | 136 |
| Hadramawt | 114 |
| Hajjah | 136 |
| Ibb | 136 |
| Lahj | 136 |
| Marib | 136 |
| Raymah | 136 |
| Sa'ada | 135 |
| Sana'a | 136 |
| Shabwah | 135 |
| Taizz | 136 |

Most governorates therefore have **136 observations**.

Hadramawt has fewer observations primarily because its first available observation occurs later in the overall study period.

---

# 14. Date-Interval Analysis

The difference between consecutive reporting dates was calculated separately within each governorate.

Results:

| Statistic | Days |
|---|---:|
| Number of intervals | 2,806 |
| Mean interval | 2.01 |
| Standard deviation | 2.66 |
| Minimum | 1 |
| 25th percentile | 1 |
| Median | 1 |
| 75th percentile | 1 |
| Maximum | 21 |

The dataset is therefore **predominantly daily**, because the median interval between observations is only **1 day**.

However, reporting is not perfectly continuous.

The largest observed gap between consecutive observations is:

**21 days**

Therefore, the dataset should not be treated as a perfectly regular daily time series without considering these reporting gaps.

---

# 15. Overall Data Quality Assessment

The preprocessing audit produced the following results:

| Audit | Result |
|---|---|
| Dataset structure | PASS |
| Missing values | PASS |
| Numerical data types | PASS |
| Valid dates | PASS |
| Governorate standardization | PASS |
| Mukalla/Sayun merge integrity | PASS |
| Duplicate Date + Governorate combinations | PASS |
| Cumulative → New_Cases conversion | PASS |
| Negative case handling | PASS |
| First observation handling | PASS |
| Numerical plausibility | PASS |
| Reporting-frequency inspection | PASS with irregularities |

### Key quantitative findings

- **2,827 total observations**
- **21 governorates**
- **6 variables**
- **0 missing values**
- **0 duplicate Date + Governorate combinations**
- **0 invalid dates**
- **0 unexpected New_Cases mismatches**
- **0 negative New_Cases remaining**
- **2 corrected-negative observations**
- **21/21 governorates correctly handled at their first observation**
- Median reporting interval: **1 day**
- Maximum reporting gap: **21 days**

---

# 16. Important Limitations

Passing the cleaning audit does **not** mean that the original epidemiological data is perfect.

The audit establishes that the **preprocessing operations appear to have been implemented correctly**, but several characteristics of the source data should still be considered in future analysis.

### 1. Reporting is irregular

Although the median interval is 1 day, gaps can reach 21 days.

Therefore, a missing reporting date should not automatically be interpreted as zero cases.

### 2. Cumulative case corrections exist

There are two observations where cumulative cases decreased.

These were intentionally converted to zero incremental cases.

However, the correction means that the reported cumulative series is not strictly monotonic.

### 3. `New_Cases` represents reported increments

`New_Cases` should be interpreted as the change in the reported cumulative case count, not necessarily the exact number of infections that occurred biologically during that period.

Reporting delays and retrospective corrections can affect the values.

### 4. First observations are not necessarily the beginning of the outbreak

For each governorate, the first available observation was assigned its cumulative case count as `New_Cases`.

Therefore, the first `New_Cases` value represents the **cases accumulated before or up to the first available reporting observation**, rather than necessarily cases occurring on that exact date.

---

# 17. Final Conclusion

The cleaned Yemen cholera governorate-level dataset appears to have undergone a **successful and internally consistent preprocessing process**.

The most important transformations were independently verified:

- Governorate names were standardized.
- Mukalla and Sayun were incorporated into Hadramawt.
- Dates are valid.
- Numerical fields are numeric.
- No missing values exist.
- No duplicate Date + Governorate combinations exist.
- Cumulative cases were correctly converted into incremental cases.
- First observations were correctly handled.
- Negative cumulative corrections were detected and flagged.
- No negative `New_Cases` remain.

The strongest validation is the independent reconstruction of `New_Cases`, which produced **0 mismatches across all 2,827 rows**.

Therefore, the dataset is in a reasonable state to proceed to the next stages of the BTP, while keeping the **irregular reporting frequency and cumulative-reporting corrections** in mind during subsequent epidemiological or machine-learning analysis.