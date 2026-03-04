# Technical Specification: The Low B Dispatch Pipeline

## 1. Project Overview
**Name:** `sports-rag-reporter`
**Architecture:** Structured RAG (Retrieval-Augmented Generation) & Deterministic AI Pipeline.
**Goal:** To build an automated, enterprise-grade pipeline that extracts raw recreational sports data (DMHL), calculates deterministic statistics, enriches data via Human-in-the-Loop (HITL), and utilizes generative AI to produce high-fidelity, validated sports journalism.

## 2. Tech Stack
* **Language:** Python 3.10+
* **Web Scraping / Ingestion:** Selenium (WebDriver, Headless Chrome) and BeautifulSoup.
* **Data Engineering & Analytics:** Pandas (aggregation, standing logic, regex cleaning).
* **AI/LLM Engine:** Google GenAI SDK (Gemini 2.5 Flash).
* **Validation:** Strict Python Regex and LLM-as-a-Judge QA.
* **Deployment & CI/CD:** Bash (`publish.sh`) to GitHub Pages (Jekyll/Markdown).

## 3. Pipeline Architecture & Data Flow
The system operates on a strict decoupling of **Deterministic Logic** (math) and **Generative Synthesis** (storytelling).

1. **Ingestion (`scraper.py` / `ingestor.py`):** * Selenium navigates dynamic JS tables, extracting Game Manifests and detailed Play-by-Play boxscores. Data is appended locally to CSVs as the single source of truth.
2. **Enrichment (`enricher.py`):** * CLI pauses execution to allow the League Commissioner (Human) to inject qualitative notes into the database, utilizing atomic backups for safety.
3. **Deterministic Analytics (`analyzer.py`):** * Pandas calculates all standings, goal differentials, and individual point totals (Goals/Assists). Output is a "Verified Stat Sheet" (JSON/Dict) to prevent LLM hallucination.
4. **Generative Synthesis (`reporter.py`):** * Compiles the structured data and context window. Gemini generates the narrative using dynamic prompt routing (e.g., 'Season Mode' vs 'Playoff Mode') and specific journalistic personas.
5. **Trust & Validation (`validator.py` / `bias_checker.py`):**
   * *Validator:* Extracts factual claims from the draft and matches them exactly against the source CSV. Fails on hallucinations.
   * *Bias Checker:* Audits the tone for demeaning language to protect brand safety.
6. **Publication (`publish.sh`):** * Orchestrates the entire pipeline. On success, writes to `docs/_posts/` for immediate web rendering.

## 4. File Structure
```text
sports-rag-reporter/
├── docs/                     # GitHub Pages deployment source
│   ├── _posts/               # Generated Markdown reports
│   └── _data/                
├── src/                      # Core Engineering
│   ├── scraper.py            # Selenium DOM extraction
│   ├── ingestor.py           # API-level data ingestion
│   ├── enricher.py           # HITL CLI interface
│   ├── analyzer.py           # Pandas calculation engine
│   ├── viz_generator.py      # Matplotlib/Seaborn visualization
│   ├── reporter.py           # Gemini prompting and synthesis
│   ├── validator.py          # Regex-based factual auditing
│   ├── bias_checker.py       # LLM safety and tone audit
│   ├── backfill_reports.py   # Historical generation tool
│   ├── scout.py              # Pre-game matchup generation
│   └── publish.sh            # Main orchestration script
├── data/                     # CSV Persistence layer
└── tech_spec.md              # System architecture and rules