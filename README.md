# DMHL Analytics & RAG Reporting Engine 🏒

A modular **Structured RAG** pipeline that transforms raw recreational hockey data into high-fidelity, professional-grade news reports.

---

## 🎯 The Problem
Recreational sports data is notoriously fragmented, often locked behind inconsistent web interfaces or poorly structured boxscores. This project builds a bridge between raw league data and professional narrative reporting, ensuring 100% statistical accuracy while maintaining an engaging, human-centric tone.

## 🤖 System Architecture
Unlike standard RAG implementations that rely on unstructured text retrieval, this engine utilizes a **Structured Data Contract** to power its LLM generation:



1.  **Extraction (Resilient Ingestion):** A state-aware Selenium pipeline that performs incremental updates and handles environmental instability (browser timeouts, responsive DOM duplication) automatically.
2.  **Analysis (Deterministic Logic):** A Python/Pandas layer that handles the "Math" (standings, PIM normalization, special teams efficiency) before the data reaches the AI.
3.  **Synthesis (Contextual Narrative):** A tiered JSON ingestion strategy that feeds the LLM both macro season trends and micro game-day details to produce a multi-persona weekly newsletter.



## 🛠️ Core Capabilities

### 🛰️ Resilient Data Collection
* **State-Aware Scraping:** Only retrieves new game data, significantly reducing operational load and redundant network requests.
* **Fault-Tolerant Design:** Auto-recovery logic and session management ensure completion across long-running data collection tasks.

### 📊 Advanced Data Engineering
* **Statistical Normalization:** Translates unstructured league logs and descriptive text into clean, numerical metrics for accurate analysis.
* **Micro-to-Macro Mapping:** Automatically links individual game events and player performances to season-wide team standings and trends.

### 🎙️ Narrative Intelligence
* **Hybrid Editorial Tone:** Synthesizes analytical depth (*The Athletic*) with engaging, community-focused reporting and "insider" structures (*32 Thoughts*).
* **Temporal Awareness:** Prioritizes current events through dynamic data filtering while utilizing historical context to identify streaks and anomalies.

---

## 🚀 Getting Started

### Installation
```bash
# Clone the repository
git clone [https://github.com/nhchong/sports-rag-reporter.git](https://github.com/nhchong/sports-rag-reporter.git)
cd sports-rag-reporter

# Install dependencies
pip install -r requirements.txt