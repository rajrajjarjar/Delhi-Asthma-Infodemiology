# Environmental Infodemiology: Asthma RSV vs. AQI Pipeline

## Project Overview
This repository contains the Proof of Concept (POC) data-fetching pipeline for a B.Tech bioinformatics project. The goal of this project is to model the temporal lag-correlation between environmental pollution spikes in New Delhi and localized public health symptom searches.

## Data Sources
1. **Google Trends Analytics:** Extracting normalized Relative Search Volume (RSV) for respiratory distress queries (e.g., "asthma") within the `IN-DL` sub-region.
2. **Open-Meteo Air Quality API:** Extracting baseline environmental metrics ($PM_{2.5}$ and standard US AQI) using regional spatial coordinates.

## Tech Stack
* **Python** (Data Extraction & Alignment)
* **pytrends** (Google API Interface)
* **pandas** (Data Cleaning & Structuring)
* **requests** (REST API Networking)
* **Future Implementation:** MongoDB (NoSQL Storage) and React/Node.js (Visualization Dashboard).

## Current POC Status
* Successfully bypassing rate limits using custom delay loops.
* Temporal data windows successfully aligned using dynamic `datetime` injection.