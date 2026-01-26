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



## 🛠️ Technical Stack & Engineering

### 🛰️ Resilient Data Collection
* **State-Aware Scraping:** Incremental updates only process new Game IDs, drastically reducing network load and execution time.
* **Multi-Source Ingestion:** Synergizes Selenium web-scraping with direct REST API requests to ensure a complete data picture including rosters and officiating crews.

### 📊 Deterministic Data Engineering
* **Regex-Based Normalization:** Sanitizes inconsistent string data into structured integers, ensuring the AI has a "Single Source of Truth."
* **Unified PIM Logic:** Shares calculation helpers across team and player stats to ensure 1:1 statistical parity.
* **Fallback Scoring:** Automatically reconstructs game results from play-by-play logs if official score rows are missing from the source.

### 🎙️ AI Narrative Intelligence
* **Gemini 2.5 Flash Integration:** Leverages high-speed, long-context windows for deep pattern analysis across entire season histories.
* **Hybrid Editorial Tone:** Synthesizes the analytical depth of *The Athletic* with the raw, locker-room authenticity of *Spittin' Chiclets*.
* **Adversarial Pattern Detection:** Identifies "statistical frauds" by cross-referencing high league rankings against negative goal differentials.

---

## 🚀 Setup & Usage

### Prerequisites
* Python 3.9+
* Chrome / ChromeDriver
* Google Gemini API Key

### Installation
```bash
# Clone the repository
git clone [https://github.com/nhchong/sports-rag-reporter.git](https://github.com/nhchong/sports-rag-reporter.git)
cd sports-rag-reporter

# Initialize virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt