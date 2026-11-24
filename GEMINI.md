# Project Context: Climate & Trends-Driven Disease Forecasting (BTP)

## Project Overview
This repository contains the Bachelor of Technology (B.Tech) final-year thesis project on developing an **early-warning disease prediction tool using Google Trends** to detect disease surges in India.

The methodology favors **interpretable statistical methods** (Spearman rank correlation over multi-week lead/lag windows and Granger causality) over complex "black-box" machine learning models.

---

## Directory Structure

```
E:\Projects\BTP\
├── benchmarks\
│   └── us_cdc_validation\            # Proof-of-concept validation on US CDC HHS Region 6 (2015-2019)
│       ├── data\                     # CDC ILINet and NREVSS datasets
│       ├── scripts\                  # Validation, lag correlation, peak detection, and plotting scripts
│       └── results\                  # Excel tables, lag curve plots, and seasonal summaries
├── Data\
│   ├── Clean\
│   │   ├── INDIA\
│   │   │   ├── Influenza\            # Clean WHO FluNet national surveillance data (2010-2026)
│   │   │   └── Diar\                 # Clean IDSP/EpiClim diarrhea outbreak data (backup dataset)
│   │   └── yemen\                    # v1 legacy cholera data (archived)
│   └── Raw_data\                     # Unprocessed original exports
├── docs\
│   ├── BTP_Methodology.md            # Detailed thesis methodology and research plan
│   └── btp_pipeline_flowchart.svg    # Pipeline architecture diagram
├── experiments\
│   └── gtrends_preflight\            # India preflight tests (thresholds, granularity trap, Hindi pilot)
│       ├── gtrends_preflight_test.py
│       ├── gtrends_preflight_report_threshold.csv
│       └── gtrends_preflight_report_granularity.csv
├── notebooks\
│   ├── pre_processing_India\
│   │   ├── influenza\                # Exploratory notebooks for FluNet India
│   │   └── diarrhea\                 # Exploratory notebooks for IDSP Acute Diarrhoeal Disease
│   └── pre_processing_YEMEN\         # Legacy exploratory notebooks
├── src\                              # Active production pipeline for India
│   ├── data_ingestion\               # 5-year chunked Google Trends fetch and stitching pipeline
│   ├── models\                       # Spearman rank lag correlation & Granger causality engines
│   └── visualization\                # Lead indicator plotting and dashboard utilities
└── README.MD
```

---

## Key Data Sources
1. **Outcome:** WHO FluNet India ([Data/Clean/INDIA/Influenza/india_flu.csv](file:///e:/Projects/BTP/Data/Clean/INDIA/Influenza/india_flu.csv))
   - Weekly laboratory-confirmed influenza surveillance (`INF_A`, `INF_B`, `INF_ALL`), 2010–2026.
   - 1,152 weeks, 89.4% non-zero reporting.
2. **Predictors:** Google Trends relative search volume (via `pytrends`).
   - Queried per state (`IN-DL`, `IN-UP`, `IN-HR`, `IN-MH`, `IN-KL`, `IN-TN`, `IN-WB`) plus National baseline (`IN`).
   - Scaled using `youtube` anchor keyword to avoid seasonal distortions.
   - Pulled in $\le 5$-year chunks to preserve weekly resolution.
   - Includes English and Hindi symptom keywords (Hindi in `IN-DL`, `IN-UP`, `IN-HR`).
