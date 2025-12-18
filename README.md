# DMHL Analytics & RAG Reporting Engine 🏒

A modular **Retrieval-Augmented Generation (RAG)** pipeline designed to scrape, analyze, and generate professional "NHL-style" reports for the **Downtown Men's Hockey League (DMHL)** in Toronto. 

---

## 🤖 RAG Architecture
This project is a specialized implementation of **Structured RAG**. Unlike standard RAG that searches through PDFs, this engine retrieves structured statistical data to "augment" the LLM's generation:

1.  **Retrieval (The Python Pipeline):** The system retrieves live data from the DMHL via `scraper.py` and processes it into structured context via `analyzer.py`.
2.  **Augmentation (The Context Window):** Raw boxscores and derived standings are injected into the LLM prompt, providing the model with "ground truth" facts it wasn't trained on.
3.  **Generation (The Narrative):** The AI (Gemini/GPT-4) transforms the augmented data into a cohesive, contextually accurate hockey recap, preventing "hallucinations" regarding scores or player names.

## 🛠️ System Components
- **Ingestion (`src/scraper.py`):** A Selenium-based engine that performs incremental deep-dives into boxscores to capture goals, penalties, and period scores.
- **Data Engineering (`src/analyzer.py`):** A Pandas-driven engine that reconstructs standings and calculates advanced metrics (L10, Streaks) using official league tie-breakers.

## 📊 Data Features
- **Semantic Scraping:** Identifies web elements by content/context rather than fragile XPaths.
- **Contextual Awareness:** Captures arena locations (St. Mike's, Mattamy, UCC) to fuel narrative reporting.
- **Structured Logic:** Math and standings are calculated in Python *before* reaching the AI to ensure 100% statistical accuracy.

## 🚀 Getting Started

### Installation
1. Clone the repo:
   ```bash
   git clone [https://github.com/yourusername/sports-rag-reporter.git](https://github.com/yourusername/sports-rag-reporter.git)
   cd sports-rag-reporter