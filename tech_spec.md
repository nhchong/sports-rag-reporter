# Technical Specification: The Low B Dispatch Pipeline

## 1. System Overview
**Project Name:** `sports-rag-reporter`
**Architecture Paradigm:** Structured RAG (Retrieval-Augmented Generation), Deterministic ETL, & Agentic LLM Orchestration.
**Objective:** An autonomous, end-to-end data journalism pipeline that ingests raw recreational hockey telemetry (DMHL), calculates deterministic statistics, integrates Human-in-the-Loop (HITL) qualitative context, and utilizes generative AI to produce high-fidelity, validated sports media.

## 2. Technology Stack
* **Language:** Python 3.10+
* **Ingestion & Extraction:** Selenium (Headless WebDriver), BeautifulSoup.
* **Data Engineering (ETL):** Pandas (Temporal filtering, aggregation, standing logic, data normalization).
* **AI/LLM Engine:** Google GenAI SDK (Gemini 2.5 Flash).
* **Visual Analytics:** Matplotlib, Seaborn.
* **Quality Assurance (QA):** Strict Regex pattern matching and LLM-as-a-Judge NLP auditing.
* **Deployment:** Static Site Generation via Jekyll (GitHub Pages).

## 3. Core Architectural Principles
The system operates on a strict decoupling of **Deterministic Logic** (Math/Facts) and **Generative Synthesis** (Narrative/Storytelling) to eliminate LLM hallucinations. 

### 3.1. The Temporal Resolution Engine ("Time Travel")
The pipeline does not rely on static "current day" execution. It utilizes a dynamic Pandas bounding box that allows the system to accurately reconstruct the exact database state of any historical date. 
* **Auto-Seeker:** Automatically detects the most recent game played to define the active 7-day reporting window.
* **Future-Stripping:** When generating historical reports, the pipeline programmatically deletes all games occurring after the target date to prevent future data leakage into the LLM context window.

### 3.2. Dynamic Agentic Routing
The generative layer (`reporter.py`) is context-aware. Before pinging the LLM, it evaluates the schedule to dynamically route the system into one of three distinct prompt architectures:
1. **Regular Season:** Optimizes for standings shifts and momentum.
2. **Playoffs:** Triggers "Race to Three" series math, elimination stakes, and tie-breaker logic.
3. **Championship Finale:** Detects when only two teams remain, triggering an end-of-season retrospective and crowning statistical MVPs.

## 4. Pipeline Data Flow
1. **Extraction (`scraper.py` / `ingestor.py`):** Selenium navigates dynamic JS DOMs, extracting Game Manifests and detailed Play-by-Play boxscores. Data is appended to local CSVs as the immutable source of truth.
2. **HITL Enrichment (`enricher.py`):** A CLI interface pauses execution, prompting the League Commissioner to inject qualitative notes (e.g., locker room vibes, short benches) into the database. Utilizes atomic `.bak` backups for data safety.
3. **Deterministic Analytics (`analyzer.py`):** Pandas calculates W/L/T standings, goal differentials, playoff series points, and individual player stats. The output is a verified JSON "Stat Sheet" payload.
4. **Generative Synthesis (`reporter.py`):** Compiles the JSON payload and routes the prompt to Gemini. The LLM acts solely as a "Senior Columnist," restricted to narrative synthesis based *only* on the provided payload.
5. **Multi-Stage Validation:**
   * **Factual Circuit Breaker (`validator.py`):** An LLM-as-a-Judge extracts claims (scores, goals, assists) from the drafted Markdown. Python Regex cross-references these claims against a 28-day chronological bounding box of the source CSV. Fails on hallucinations.
   * **Trust & Safety NLP Audit (`bias_checker.py`):** A secondary LLM scans the narrative for subjective, demeaning framing or unjustified causality. Flags systemic bias and requires a manual CLI override to deploy.
6. **Visual Synthesis (`viz_generator.py`):** Renders performance scatter plots (e.g., Goal Differential vs. Total Points), dynamically excluding inactive teams, and exports directly to the deployment assets folder.
7. **Deployment (`main.py` / `publish.sh`):** Orchestrates the pipeline and writes final Markdown/YAML front-matter to `docs/_posts/` for immediate Jekyll rendering.

## 5. File & Directory Structure
```text
sports-rag-reporter/
├── docs/                     # Deployment Environment (GitHub Pages / Jekyll)
│   ├── _posts/               # Verified Markdown narrative dispatches
│   ├── assets/images/        # Static assets & dynamically generated visualiztions
│   ├── _config.yml           # Static site configuration
│   └── index.md              # Public Dashboard Frontpage
├── src/                      # Engineering Core
│   ├── main.py               # Application entry point / orchestrator
│   ├── scraper.py            # Selenium DOM extraction engine
│   ├── ingestor.py           # API-level roster/data ingestion
│   ├── enricher.py           # HITL CLI interactive prompt
│   ├── analyzer.py           # Deterministic Pandas ETL calculation engine
│   ├── viz_generator.py      # Matplotlib data visualization output
│   ├── reporter.py           # Context-aware LLM prompting and synthesis
│   ├── scout.py              # Pre-game opponent analytics generation
│   ├── validator.py          # LLM-as-a-Judge factual extraction & regex auditor
│   ├── bias_checker.py       # Editorial tone & safety NLP auditor
│   ├── backfill_reports.py   # Historical generation tool
│   └── publish.sh            # CI/CD deployment automation script
├── data/                     # Source of Truth (CSV Persistence layer)
├── requirements.txt          # Python environment dependencies
└── tech_spec.md              # System architecture and rules (This Document)