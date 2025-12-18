# Technical Specification: Automated Sports Analytics & Reporting Engine

## 1. Project Overview
**Name:** `sports-rag-reporter`
**Goal:** To build an automated pipeline that scrapes match results from dynamic recreational sports websites (DMHL, XTSC), processes the statistical data to calculate standings and trends, and uses Generative AI (LLMs) to produce stylistic, "news-anchor" style commentary and power rankings.

## 2. Tech Stack
* **Language:** Python 3.10+
* **Web Scraping:** Selenium (WebDriver) with Headless Chrome (handling dynamic JS rendering).
* **Data Processing:** Pandas (DataFrames, CSV I/O, statistical calculations).
* **AI/LLM:** OpenAI API (GPT-4o) or Anthropic API (Claude 3.5 Sonnet) for generating narrative text.
* **Environment:** Local Python `venv`, managed via `requirements.txt`.
* **Version Control:** Git / GitHub.

## 3. Architecture & Data Flow
1.  **Ingestion (Scraper):** Selenium bot visits league URL -> Waits for JS table load -> Extracts HTML -> Parses into Raw Game Data (CSV).
2.  **Processing (Analyzer):** Pandas reads Raw CSV -> Calculates derived metrics (Wins, Losses, Goal Diff, Streaks) -> Outputs Standings (DataFrame/JSON).
3.  **Generation (Reporter):** System constructs a prompt with the Standings Data + Context (e.g., "Act as a rowdy sports anchor") -> Sends to LLM -> Receives commentary.
4.  **Presentation:** Prints report to terminal (MVP) or saves to `reports/` folder as a text/markdown file.

## 4. File Structure
```text
sports-rag-reporter/
├── data/
│   ├── raw_scores.csv       # The raw output from the scraper
│   └── standings.csv        # The calculated table (W-L-PTS)
├── src/
│   ├── __init__.py
│   ├── scraper.py           # Selenium logic to grab the table
│   ├── analyzer.py          # Pandas logic to calculate standings/stats
│   └── reporter.py          # LLM API logic to generate the news
├── reports/                 # Folder for saving generated text files
├── main.py                  # Entry point (orchestrates the flow)
├── requirements.txt         # Dependencies (selenium, pandas, openai)
└── tech_spec.md             # This file (Project Context)