---
layout: home
author_profile: true
header:
  overlay_color: "#000"
  overlay_filter: "0.5"
  overlay_image: /assets/images/hockey-canada.jpg # Removed /docs
  cta_label: false 
  cta_url: false  
excerpt: "The definitive data record of the DMHL. Professional-grade reporting and analytical deep-dives for the Monday/Wednesday Low B division."

# feature_row config for technical highlights
feature_row:
  - image_path: /assets/images/python-logo.png
    alt: "Data Ingestion"
    title: "Resilient Ingestion"
    excerpt: "A Selenium-based engine built to handle async Angular rendering with Explicit URL guards and recursive retry loops."
    url: "https://github.com/nhchong/sports-rag-reporter/blob/main/src/scraper.py"
    btn_label: "View Scraper"
    btn_class: "btn--primary"
  - image_path: /assets/images/gemini-logo.png
    alt: "AI Generation"
    title: "Generative Analytics"
    excerpt: "Utilizes Google Gemini 1.5 Pro to transform structured CSV metrics into high-fidelity, data-backed sports narratives."
    url: "https://github.com/nhchong/sports-rag-reporter/blob/main/src/reporter.py"
    btn_label: "View Prompt Logic"
    btn_class: "btn--primary"

# Complete Team Lineup
team_row:
  - image_path: /assets/images/theshockers.png
    alt: "The Shockers"
    title: "The Shockers"
  - image_path: /assets/images/thesahara.png
    alt: "The Sahara"
    title: "The Sahara"
  - image_path: /assets/images/doncherrys.png
    alt: "Don Cherry's"
    title: "Don Cherry's"
  - image_path: /assets/images/flatearthers.png
    alt: "Flat-Earthers"
    title: "Flat-Earthers"
  - image_path: /assets/images/muffinmen.png
    alt: "Muffin Men"
    title: "Muffin Men"
  - image_path: /assets/images/4lines.png
    alt: "4 Lines"
    title: "4 Lines"
---

# Project Overview
Welcome to **The Low B Dispatch**. This project is an automated end-to-end data pipeline designed to provide professional-grade coverage for the **Downtown Men’s Hockey League (DMHL)** in Toronto. 

Historically, amateur sports suffer from a narrative gap—stats exist on fragmented pages, but the "story" of the week is rarely told. This project bridges that gap by treating raw league data as a source of truth for an AI-driven newsroom, specifically covering the **Monday/Wednesday Low B** division.

Every report below is generated autonomously. The pipeline ingests the latest boxscores, analyzes team efficiency metrics, and prompts a specialized LLM agent to write a weekly recap with 100% evidence-backed accuracy.

### The Tech Stack
![Python](https://img.shields.io/badge/python-3670A0?style=for-the-badge&logo=python&logoColor=ffdd54)
![Selenium](https://img.shields.io/badge/-selenium-%2343B02A?style=for-the-badge&logo=selenium&logoColor=white)
![Pandas](https://img.shields.io/badge/pandas-%23150458.svg?style=for-the-badge&logo=pandas&logoColor=white)
![Google Gemini](https://img.shields.io/badge/Google%20Gemini-8E75B2?style=for-the-badge&logo=googlegemini&logoColor=white)

<!--{% include feature_row %} -->

---

### League Parity Dashboard
*Goal Differential vs. Total Points. Top-right teams are dominant; bottom-left teams are battling for traction.*

<figure style="text-align: center; margin-top: 1.5em; margin-bottom: 2.5em;">
  <img src="{{ '/assets/images/league_parity.png' | relative_url }}" alt="DMHL League Parity Scatter Plot" style="border: 1px solid #eaeaea; border-radius: 4px; box-shadow: 0 4px 12px rgba(0,0,0,0.1); max-width: 100%;">
</figure>


---

