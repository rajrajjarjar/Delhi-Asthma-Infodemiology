# Climate-Driven Disease Forecasting Dashboard — Methodology

**Final-year B.Tech Thesis**

---

## 1. Objective

Forecast disease surges in India by finding a **statistically validated lag** between early-warning predictor signals and confirmed case data, using time-series correlation methods — deliberately avoiding complex ML models in favor of interpretable statistical rigor.

## 2. Background / Evolution of Scope

| Stage | Approach | Outcome |
|---|---|---|
| v1 | Yemen governorate-level cholera data (2017–18), Open-Meteo weather, Arabic/English Google Trends | Rejected by professor |
| v2 | Pivoted to pan-India, disease undecided | — |
| v3 (explored) | EpiClim/IDSP dataset — state/district outbreak data | Found EpiClim has **no influenza/respiratory category**; best-covered disease is Acute Diarrhoeal Disease, but data is outbreak-triggered (sparse, ~40% max weekly coverage even in best-covered states) — unsuitable as primary time series |
| **v4 (current, final)** | **WHO FluNet — national weekly influenza data** as outcome, **state-level Google Trends** as predictor | In progress — pre-flight validation underway |

## 3. Data Sources

### 3.1 Outcome variable — WHO FluNet (India)
- Weekly national influenza surveillance data (`INF_A`, `INF_B`, `INF_ALL`, and subtypes)
- **Validated range: 2010–2026** — consistently 48–53 reported weeks per year, non-null case data in the large majority of weeks. Pre-2010 data (1996–2009) is sparse and will be excluded from the analysis window.
- Granularity: national only — no state/district breakdown exists in the public FluNet export.

### 3.2 Predictor variable — Google Trends (via `pytrends`)
- Primary predictor per original project design (weather data is secondary/supporting, not primary).
- Queried at **state level** (`geo='IN-XX'` ISO 3166-2 codes) rather than only nationally, to work around the fact that the outcome variable has no state granularity of its own.
- Language: **English-first**, based on India's large English-speaking internet base. A **pilot check in Hindi** will be run for 2–3 Hindi-belt candidate states (e.g. Bihar, UP) to test for language-driven bias in search volume before finalizing English-only as sufficient.

### 3.3 Candidate states (shortlist, not exhaustive)
Chosen using India's known regional flu climatology, not queried blindly across all states:
- North India (winter-driven pattern): Delhi, Uttar Pradesh, Punjab
- South/coastal India (monsoon-driven pattern): Kerala, Tamil Nadu, West Bengal
- Additional states may be added if the pre-flight test shows strong, usable signal.

## 4. Methodology Steps

### Step 1 — Pre-flight validation (standalone test file, not part of main pipeline)
Before any real analysis is built, the following is verified for every candidate term/state:
1. **Threshold check** — does the term return real signal (not all-zero / "insufficient data") at national and state level?
2. **Granularity check** — Google Trends silently drops from weekly to **monthly** resolution for any single query spanning more than ~5 years. Since the analysis window is 16 years (2010–2026), all real pulls must be **chunked into ≤5-year windows** and stitched back together with rescaling — this is verified explicitly, not assumed.
3. **Rate-limit resilience** — `pytrends` is an unofficial wrapper; retry/backoff logic is tested to avoid silent failures under repeated queries.
4. **Sanity pilot** — a short recent window is visually checked against a known real flu season before committing to the full 16-year pull.

### Step 2 — Data construction
- Outcome: national weekly FluNet case counts, 2010–2026.
- Predictors: state-level Google Trends series for shortlisted states, pulled in 5-year chunks and stitched with rescaling to preserve weekly resolution across the full window.

### Step 3 — Spearman Rank Correlation (lag discovery)
- For each candidate state's Trends series, test correlation against the national case curve across a range of lag offsets (in weeks) to find the lag at which correlation is strongest.
- States with no meaningful correlation at any lag are dropped — the model is not forced to include unresponsive states.

### Step 4 — Granger Causality (precedence validation)
- Run on the states retained after Step 3, to validate that the predictor series statistically precedes the outcome series at the identified lag (not just correlated, but sequentially predictive).

### Step 5 — Interpretation
- Output is framed as **"leading-indicator regions"**, not a single pinpointed outbreak origin. Multiple states may show concurrent lead signals due to India's regionally staggered flu seasons.
- Granger causality demonstrates statistical precedence/predictive value — **not proof of geographic causation.** This distinction will be stated explicitly in the thesis to preempt the correlation-vs-causation question.

## 5. Known Limitations (stated upfront, not discovered later)

- **No state-level case data exists publicly** for influenza in India — the outcome variable is necessarily national, which can smooth over genuinely regional dynamics. State-level Trends data is used to partially recover regional signal on the predictor side only.
- **English-language search bias**: English search penetration skews toward urban, educated, English-speaking populations and specific states (Kerala, Tamil Nadu, Karnataka, urban Delhi/Maharashtra) more than rural Hindi-belt states. A Hindi-term pilot check is run on 2–3 Hindi-belt states specifically to catch this before it silently biases which states appear to "lead."
- **National aggregation smooths regional climate-driven timing differences** — mitigated, not eliminated, by the multi-state predictor design in Step 3–4.
- **Correlation/precedence ≠ causation** — explicitly acknowledged in interpretation (Step 5).

## 6. Deliberate Scope Exclusions

- SARS-CoV-2 / COVID-19 — excluded per project scope from the start.
- Complex ML forecasting models — deliberately avoided in favor of interpretable statistical methods (Spearman + Granger).
- Full multilingual (100+ Indian languages) term coverage — deemed unmanageable; English-first with targeted Hindi pilot check chosen as the practical middle ground.
