# Google Trends Pre-Flight Test (India)

## Purpose
Validates the viability of Google Trends search volume data across Indian candidate states and national queries **before** executing long-range time-series ingestion (2010–2026).

## Key Files
- `gtrends_preflight_test.py`: Standalone script checking threshold viability, granularity decay, and language penetration.
- `gtrends_preflight_report_threshold.csv`: Evaluates zero-inflation percentage and mean volume across candidate states and terms.
- `gtrends_preflight_report_granularity.csv`: Documents the empirical drop from weekly resolution (262 rows over 5 years) to monthly resolution (193 rows over 16 years).

## Core Findings & Rules Established
1. **Granularity Constraint:** Single queries spanning $>5$ years silently collapse into monthly resolution. The primary pipeline must pull data in $\le 5$-year chunks (with overlap) and rescale.
2. **Search Volume:** Core symptom terms (`fever`, `cough`) provide dense, zero-free weekly signal nationwide. The term `flu` has high search penetration in coastal/southern states (Kerala, Tamil Nadu) but is sparse in northern states.
3. **Language Inclusivity:** In northern/Hindi-belt states (UP, Bihar), Hindi symptom terms (`बुखार`, `खांसी`) show search volume equivalent to or higher than English terms, confirming the need for multi-language inclusion to avoid volume suppression.
