# DMHL Analytics & Structured RAG Reporting Engine 🏒

A modular **Structured RAG (Retrieval-Augmented Generation)** pipeline that transforms raw recreational hockey data into high-fidelity, professional-grade news reports. This system bridges the gap between fragmented league data and engaging community storytelling.

---

## 🎯 The Problem: The Narrative Gap
Recreational sports data is notoriously fragmented, often locked behind inconsistent web interfaces or stale boxscores. While the drama of a 10:30 PM comeback or a season-long rivalry is just as real as in the NHL, these stories are rarely told. Recreational sports lack the **narrative infrastructure**—the journalists, the beat reporters, and the analysts—that turn raw stats into shared community history.

This project bridges that gap. By using **deterministic data processing** combined with **Generative AI**, we ensure 100% statistical accuracy while providing the engaging, human-centric storytelling that recreational athletes deserve.



## 🤖 System Architecture
This engine utilizes a **Structured Data Contract** to power its LLM generation. Unlike standard RAG that searches through messy text, this system processes structured datasets first, ensuring the AI cannot "hallucinate" scores, standings, or penalty counts.

1.  **Extraction (`scraper.py`):** A state-aware Selenium/Requests pipeline that handles dynamic DOM content and interfaces with private APIs to pull rosters and game events.
2.  **Logic Layer (`analyzer.py`):** A deterministic Pandas layer that handles the "Hard Math"—calculating standings, PIM normalization, and special teams efficiency.
3.  **Synthesis (`reporter.py` & `scout.py`):** A tiered JSON ingestion strategy that feeds **Gemini 2.5 Flash** both macro season trends and micro game-day details to produce distinct narrative outputs.

## ✨ Key Features

### 🛰️ Resilient Data Collection
* **State-Aware Scraping:** Incremental updates that only process new Game IDs, drastically reducing network load.
* **Multi-Source Ingestion:** Synergizes Selenium web-scraping with direct REST API requests for a complete data picture (rosters, officiating crews).
* **Column-Shift Detection:** Intelligent manifest parsing that handles inconsistent CSV layouts (e.g., scores stored in 'Status' columns) automatically.

### 📊 Deterministic Data Engineering
* **Regex-Based Normalization:** Sanitizes inconsistent string data (e.g., `#8 Player: Infraction`) into structured integers.
* **Unified PIM Logic:** Shares calculation helpers across team and player stats to ensure 1:1 statistical parity.
* **Fallback Scoring:** Reconstructs game results from play-by-play logs if official score rows are missing.

### 🎙️ AI Narrative Intelligence
* **Gemini 2.5 Flash Integration:** Leverages high-speed, long-context windows for deep pattern analysis across entire seasons.
* **Hybrid Editorial Tone:** Synthesizes the analytical depth of *The Athletic* with the raw authenticity of *Spittin' Chiclets*.
* **Adversarial Pattern Detection:** Identifies "statistical frauds" by cross-referencing high rankings against negative goal differentials.

## 📂 Project Structure
```text
sports-rag-reporter/
├── src/
│   ├── scraper.py     # Selenium/API ingestion pipeline
│   ├── analyzer.py    # Deterministic data processing & normalization
│   ├── reporter.py    # Weekly newsletter generation (The Dispatch)
│   └── scout.py       # Gameday matchup intelligence
├── data/              # Local CSV storage (Git ignored)
├── .env               # Secrets & Authentication (Git ignored)
├── requirements.txt   # Environment dependencies
└── README.md          # Project documentation