# The Low B Dispatch 🏒🤖

![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)
![Gemini API](https://img.shields.io/badge/AI-Google_Gemini_2.5_Flash-orange.svg)
![Pandas](https://img.shields.io/badge/Data-Pandas-150458.svg)
![Jekyll](https://img.shields.io/badge/Deployment-Jekyll_&_GitHub_Pages-red.svg)

**An autonomous, enterprise-grade AI sports journalism pipeline.**

*The Low B Dispatch* is a production-ready **Structured RAG (Retrieval-Augmented Generation)** system designed to bring professional-level, data-driven sports media coverage to local recreational hockey leagues. 

Operating with strict factual guardrails, dynamic prompt routing, and "LLM-as-a-Judge" evaluation layers, the system transforms fragmented, bare-bones boxscore data into high-fidelity, community-focused news reports.

---

## 🥅 The Vision: Closing the "Narrative Gap"

Millions of adults play recreational sports. They pay league fees, battle through late-night games, and build years-long rivalries. Yet, the digital experience for these players is notoriously poor—usually limited to a static, unstyled table of scores on a clunky website. 

**There is a massive gap between the passion on the ice and the data on the screen.**

As a player in the Monday/Wednesday Low B division of Toronto's DMHL, I built *The Low B Dispatch* to give recreational athletes the "pro treatment." The product doesn't just recite scores; it generates the connective narrative tissue of a sports season. It provides weekly recaps, playoff math breakdowns, and community authenticity—blending the analytical depth of *The Athletic* with the locker-room camaraderie of *Spittin' Chiclets*.

---

## 🧠 Applied AI Architecture

While standard LLMs excel at creative writing, they are fundamentally flawed at arithmetic and deterministic data retrieval. Feeding an LLM a raw web scrape of a hockey season results in severe "hallucinations"—invented goals, incorrect standings, and false narratives.

This project solves this by implementing modern AI engineering paradigms: **Separation of Concerns, Agentic Routing, and AI Evals.**

### 1. Structured RAG & Deterministic Grounding
Instead of asking the LLM to do math, the system utilizes a **deterministic analytics layer** (`analyzer.py` via Pandas) to pre-calculate all standings, goal differentials, and individual point totals. The LLM is then injected with a highly structured JSON context payload, strictly constraining it to narrative synthesis rather than data calculation. 

### 2. Dynamic Agent Routing
The generation engine (`reporter.py`) acts as a context-aware agent. It analyzes the temporal data state and dynamically routes to specific prompt architectures based on seasonality:
* **Regular Season Mode:** Focuses on standings shifts and momentum.
* **Playoff Mode:** Automatically pivots to "Race to Three" math, elimination stakes, and tie-breakers.
* **Championship Finale:** Detects the end of the season, synthesizes a year-in-review, and crowns the statistical MVPs.

### 3. Human-in-the-Loop (HITL) Enrichment
Pure data lacks "soul." The `enricher.py` module introduces an interactive CLI checkpoint that pauses the pipeline, querying the league commissioner for qualitative insights (e.g., short benches, locker-room vibes). This effectively merges human subjective context with scraped quantitative data before LLM generation.

### 4. AI Evals ("LLM-as-a-Judge")
To guarantee absolute trust and safety, the pipeline employs two distinct AI auditing layers before publication:
* **Factual Circuit Breaker (`validator.py`):** Uses an LLM to extract factual claims (scores, goals, assists) from the generated Markdown, then uses strict Python Regex to cross-reference them against the original CSV databases. The pipeline halts instantly if a hallucination is detected.
* **Tone & Bias Auditing (`bias_checker.py`):** A secondary LLM acts as the "Editor-in-Chief." It scans the narrative for subjective, demeaning framing (e.g., evaluating if a team is unfairly criticized without statistical backing). It flags systemic bias and requires a manual CLI override to deploy.

---

## ⚙️ Pipeline Execution Flow

The system operates sequentially, orchestrated via `main.py` and `publish.sh`:

1. **Ingestion (`scraper.py` / `ingestor.py`):** Headless Selenium extraction of asynchronous league data.
2. **Aggregation (`analyzer.py`):** Pandas ETL pipeline computing the statistical source-of-truth.
3. **Enrichment (`enricher.py`):** HITL CLI for injecting qualitative narrative context.
4. **Generation (`reporter.py`):** Temporal "time-travel" context windowing and Gemini 2.5 Flash synthesis.
5. **Visualization (`viz_generator.py`):** Automated Matplotlib generation of league parity scatter plots.
6. **Validation (`validator.py` & `bias_checker.py`):** Multi-stage AI and programmatic integrity audits.
7. **Deployment:** Automated Jekyll rendering and push to GitHub Pages.

---

## 📂 Project Structure

```text
sports-rag-reporter/
├── docs/                     # Deployment Source (GitHub Pages / Jekyll)
│   ├── _posts/               # Generated LLM Narrative Dispatches
│   ├── assets/               # Static assets & dynamically generated visualiztions
│   ├── _config.yml           # Jekyll configuration
│   └── index.md              # Public Dashboard Frontpage
├── src/                      # Engineering Core
│   ├── main.py               # Application entry point / orchestrator
│   ├── scraper.py            # Selenium ingestion engine
│   ├── ingestor.py           # API-level roster ingestion
│   ├── enricher.py           # HITL qualitative context injection
│   ├── analyzer.py           # Deterministic Pandas logic & ETL aggregation
│   ├── viz_generator.py      # Automated Matplotlib visual analytics
│   ├── reporter.py           # Gemini LLM narrative synthesis & temporal routing
│   ├── scout.py              # Opponent scouting analytics 
│   ├── validator.py          # LLM-as-a-Judge factual extraction & regex auditor
│   ├── bias_checker.py       # Editorial tone & bias NLP auditor
│   ├── backfill_reports.py   # Historical report archive generator
│   └── publish.sh            # CI/CD deployment automation
├── data/                     # Source of Truth (CSV persistence)
├── .env                      # API Keys and Environment Variables
├── Gemfile                   # Ruby dependencies for local Jekyll testing
├── requirements.txt          # Python dependencies
└── README.md                 # Architecture Documentation