# Technical Specification: DMHL RAG Reporter

## 1. System Overview
A Retrieval-Augmented Generation (RAG) pipeline designed to automate NHL-style sports journalism for the Downtown Men's Hockey League (DMHL). The system utilizes a Medallion Architecture to transition data from raw web-scraped events to high-density analytical insights.

## 2. Data Architecture (Medallion Pattern)

[Image of a data pipeline diagram showing the transition from Bronze raw data to Silver cleaned data to Gold analytical insights]

### 2.1 Bronze Layer (Raw Ingestion)
- **Source:** DigitalShift (dmhl.ca) via Selenium.
- **Storage:** `data/01_bronze/`
- **Files:** `game_details_raw.csv`, `manifest_raw.csv`.
- **Policy:** Append-only. Data is stored in its native format with a `scraped_at` timestamp.

### 2.2 Silver Layer (Standardization)
- **Process:** Data cleaning, deduplication, and schema enforcement.
- **Storage:** `data/02_silver/`
- **Files:** `cleaned_events.csv`, `league_standings.csv`.
- **Key Logic:** Normalizes team names (e.g., "Pigs" -> "The Pigs") and converts period scores into a structured Points/Wins/Losses standings table.

### 2.3 Gold Layer (Analytical Insights)
- **Process:** Feature engineering and "Bespoke Math" calculations.
- **Storage:** `data/03_gold/`
- **Files:** `team_metrics.json`, `player_archetypes.json`.
- **Logic:** This layer calculates the specific metrics (PP%, PK%, Streaks, PIM-to-Point Ratios) used to populate the AI prompt.

## 3. RAG Pipeline & LLM Integration

### 3.1 Retrieval Strategy
Instead of vector search, the system uses **Structured Metadata Retrieval**. The `reporter.py` script queries the Gold layer for a specific `GameID` to build a context-dense Markdown package.

### 3.2 Prompt Augmentation
The LLM is provided with three distinct context blocks:
1. **Game Manifest:** Venue, Time, and Matchup stakes.
2. **Historical Context:** Season series records and recent momentum (Last 3 games).
3. **Statistical Profile:** Team efficiency (PP/PK) and Player archetypes (Grinder vs. Skill).

### 3.3 Generation
- **Model:** Google Gemini 1.5 Flash.
- **Persona:** Professional Hockey Beat Reporter (The Athletic style).
- **Constraints:** Zero-hallucination policy (must use provided statistics only).

## 4. Technical Stack
- **Language:** Python 3.11+
- **Data Handling:** Pandas (Vectorized math for Silver/Gold layers).
- **Automation:** Selenium (Headless Chrome).
- **LLM API:** Google Generative AI SDK.

## 5. Success Metrics
- **Accuracy:** Standings must match the official DMHL standings 1:1.
- **Latency:** Generation of a full report in under 5 seconds.
- **Reliability:** Scraper must handle "Ghost Tables" and dynamic JS rendering on the DMHL site.