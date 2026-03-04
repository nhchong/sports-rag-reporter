# The Low B Dispatch 🏒

**An autonomous, enterprise-grade AI sports journalism pipeline.**

The Low B Dispatch is a production-ready **Structured RAG (Retrieval-Augmented Generation)** pipeline designed to bring professional-level sports media coverage to local recreational hockey leagues. 

It transforms fragmented, bare-bones boxscore data into high-fidelity, community-focused news reports, operating with strict factual guardrails and Human-in-the-Loop (HITL) enrichment.

---

## 🥅 The Product Vision: Closing the "Narrative Gap"

Millions of adults play recreational sports. They pay league fees, battle through late-night games, and build years-long rivalries. Yet, the digital experience for these players is notoriously poor—usually limited to a static, unstyled table of scores on a clunky website. 

**There is a massive gap between the passion on the ice and the data on the screen.**

As a player in the Monday/Wednesday Low B division of Toronto's DMHL, I built *The Low B Dispatch* to give recreational athletes the "pro treatment." The product doesn't just recite scores; it generates the connective narrative tissue of a sports season. It provides:
* **Weekly Dispatches:** Recaps that highlight momentum shifts, depth scoring, and penalty troubles.
* **Playoff Stakes:** Mathematical breakdowns of series-clinching scenarios and tiebreakers (like the "Lucky Loser" race).
* **Community Authenticity:** A distinct editorial persona that blends the analytical depth of *The Athletic* with the locker-room camaraderie of *Spittin' Chiclets*.

## ⚙️ The Engineering Challenge: AI Integrity

While standard LLMs are excellent at creative writing, they are fundamentally bad at arithmetic and deterministic data retrieval. If you feed an AI a raw web scrape of an 8-day playoff series, it will frequently "hallucinate" goal totals or invent assists for the sake of a better story.

**The Solution:** A decoupled architecture where Python handles the math, humans handle the context, and the AI is heavily constrained to narrative synthesis, backed by strict continuous integration (CI) auditing.



---

## 🏗️ Technical Architecture

This system operates sequentially via a unified bash orchestrator (`publish.sh`), processing structured datasets to ensure 100% data integrity before publication to GitHub Pages.

### 1. Ingestion & Data Governance
* **Resilient Extraction (`scraper.py`):** Utilizes a headless Selenium WebDriver to navigate asynchronous Angular-rendered content. It features state-aware scraping to drastically reduce network load by only processing delta updates.
* **API Synergies (`ingestor.py`):** Interfaces with external APIs to retrieve high-fidelity game rosters, parsing HTML fragments to ensure data is verified against league source files.

### 2. Human-in-the-Loop (HITL) Enrichment
* **Context Curation (`enricher.py`):** Pure data lacks "soul." This interactive CLI tool pauses the pipeline to query the league commissioner for qualitative insights (e.g., short benches, locker-room vibes). It utilizes atomic backups and Pandas masking to safely merge human context with scraped data.

### 3. Deterministic Analytics Layer (The "Source of Truth")
* **Statistical Aggregation (`analyzer.py`):** To prevent hallucinations, this custom Pandas layer pre-calculates all standings, goal differentials, and individual point totals. By passing a mathematically verified "Stat Sheet" to the AI, we eliminate arithmetic errors at the source.
* **Visualization Engine (`viz_generator.py`):** Translates team performance metrics into professional-grade scatter plots, defining division parity and performance trends.

### 4. Generative Synthesis
* **Context-Aware Reporting (`reporter.py`):** Compiles a high-density JSON data brief for the Gemini API. It uses dynamic prompt routing to pivot the narrative strategy based on seasonality (e.g., shifting from "Regular Season Standings" to "Playoff Race to Three" logic).

### 5. Trust, Safety, & Factual Validation
* **Factual Circuit Breaker (`validator.py`):** An "LLM-as-a-Judge" QA system. It extracts factual claims (scores, goals, assists) from the generated Markdown and uses strict Python Regex to cross-reference them against the original CSV databases. The pipeline halts if the AI invents a play or misstates a score.
* **Bias & Tone Auditing (`bias_checker.py`):** A proactive Trust & Safety layer. It scans the narrative for subjective, demeaning framing (e.g., calling a team "pathetic" instead of citing their negative goal differential). It flags systemic bias and requires an Editor-in-Chief override to deploy.

---

## 📂 Project Structure
```text
sports-rag-reporter/
├── docs/                     # Deployment Source (GitHub Pages)
│   ├── _posts/               # Automated Narrative Dispatches
│   └── index.md              # Public Dashboard and Visualizations
├── src/                      # Engineering Core
│   ├── scraper.py            # Selenium ingestion engine
│   ├── ingestor.py           # API-level roster ingestion
│   ├── enricher.py           # Interactive HITL context injection
│   ├── analyzer.py           # Deterministic logic & aggregation
│   ├── viz_generator.py      # Data visualization output
│   ├── reporter.py           # LLM narrative synthesis
│   ├── validator.py          # Factual integrity regex auditor
│   ├── bias_checker.py       # Trust & safety tone auditor
│   ├── backfill_reports.py   # Historical archive generator
│   └── publish.sh            # CI/CD deployment orchestration
├── data/                     # Source of Truth (CSV persistence)
└── README.md                 # Architecture Documentation