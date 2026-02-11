# Low B Dispatch: Technical Product Specification 🏒

The Low B Dispatch is a production-grade **Structured RAG (Retrieval-Augmented Generation)** pipeline designed to transform fragmented recreational sports data into high-fidelity, professional-grade news reports. This system utilizes a deterministic logic layer combined with a generative synthesis engine to provide analytical depth for Toronto’s DMHL.

---==

## The Problem: The Narrative Gap
In recreational sports, data is often siloed in inconsistent web interfaces, creating a "Narrative Gap" between the events on the ice and the community's history.

* Participant-Led Solution: As a player in the Monday/Wednesday Low B division of the DMHL, I built this engine to provide the narrative infrastructure that recreational athletes deserve.

* Beyond Raw Stats: While standard platforms offer boxscores, they lack the analytical storytelling found in professional media.

* Deterministic Integrity: To prevent the hallucinations common in standard LLM applications, this system processes data through a custom Pandas engine before any narrative synthesis occurs.



## Technical Architecture
This engine utilizes a **Structured Data Contract** to power its LLM generation. Unlike standard RAG that searches through messy text, this system processes structured datasets first, ensuring the AI cannot "hallucinate" scores, standings, or penalty counts.

1.  **Data Acquisition and Governance** 
* **Resilient Extraction (`scraper.py`):** Utilizes a headless Selenium WebDriver to navigate asynchronous Angular-rendered content. It manages the extraction of a comprehensive game manifest and detailed play-by-play boxscores.
* **API Ingestion (`ingestor.py`):** Interfaces directly with the DigitalShift partials API to retrieve high-fidelity game rosters. It uses BeautifulSoup to parse HTML content fragments, ensuring roster data is verified against league source files.

2. **Deterministic Analytics Layer**
* **Business Logic (`analyzer.py`):** A custom Pandas engine that performs all statistical calculations, including standings, goal differentials, and win percentages. It identifies Game Winning Goals (GWG) and computes special teams efficiency metrics such as PP% and PK%.
* **Visualization Engine (`viz_generator.py`):** Translates team performance metrics into professional-grade scatter plots. It maps Goal Differential against Total Points to define division parity and performance trends.

3. **Synthesis and Strategic Insights**
* **Weekly Production (`reporter.py`):** Compiles a high-density JSON data package for Gemini 2.5 Flash. The engine generates weekly dispatches with unique headlines and sublines, utilizing dynamic team logo mapping for homepage thumbnails.
* **Historical Context (`backfill_reports.py`):** Facilitates targeted generation of past reports to build a data-consistent seasonal archive.
* **Matchup Intelligence (`scout.py`):** Aggregates historical head-to-head results and individual player metrics to generate data-driven pre-game briefings.

## Key Features

### Resilient Data Collection
* **State-Aware Scraping:** Incremental updates that only process new Game IDs, drastically reducing network load.
* **Multi-Source Ingestion:** Synergizes Selenium web-scraping with direct REST API requests for a complete data picture (rosters, officiating crews).
* **Column-Shift Detection:** Intelligent manifest parsing that handles inconsistent CSV layouts (e.g., scores stored in 'Status' columns) automatically.

### Deterministic Data Engineering
* **Regex-Based Normalization:** Sanitizes inconsistent string data (e.g., `#8 Player: Infraction`) into structured integers.
* **Unified PIM Logic:** Shares calculation helpers across team and player stats to ensure 1:1 statistical parity.
* **Fallback Scoring:** Reconstructs game results from play-by-play logs if official score rows are missing.

### AI Narrative Intelligence
* **Gemini 2.5 Flash Integration:** Leverages high-speed, long-context windows for deep pattern analysis across entire seasons.
* **Hybrid Editorial Tone:** Synthesizes the analytical depth of *The Athletic* with the raw authenticity of *Spittin' Chiclets*.
* **Adversarial Pattern Detection:** Identifies "statistical frauds" by cross-referencing high rankings against negative goal differentials.

## Project Structure
```text
sports-rag-reporter/
├── docs/                     # Deployment Source (GitHub Pages)
│   ├── _posts/               # Automated Narrative Dispatches
│   ├── _data/                # UI Configuration (navigation.yml)
│   ├── assets/               # Parity Charts and Brand Assets
│   └── index.md              # Public Dashboard and Visualizations
├── src/                      # Engineering Core
│   ├── scraper.py            # Selenium ingestion engine
│   ├── ingestor.py           # API-level roster ingestion
│   ├── analyzer.py           # Logic and standing calculations
│   ├── viz_generator.py       # Data visualization output
│   ├── reporter.py           # Production narrative synthesis
│   ├── backfill_reports.py   # Historical archive generator
│   ├── scout.py              # Pre-game matchup intelligence
│   └── publish.sh            # Deployment orchestration
├── data/                     # Source of Truth (CSV persistence)
└── README.md                 # Product Documentation