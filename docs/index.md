---
layout: home
author_profile: true
header:
  overlay_color: "#000"
  overlay_filter: "0.5"
  overlay_image: /assets/images/rink-header.jpg 
  caption: "The Low B Dispatch: Where AI meets the Ice."
excerpt: "A data-driven deep dive into the DMHL, powered by custom Selenium scrapers and LLMs."
---

# 🏒 About the Dispatch
The **Low B Dispatch** is more than a newsletter; it is an automated, AI-driven sports journalism pipeline. 

### The Project
This project was built to solve the lack of granular coverage in amateur sports. By bridging the gap between raw web data and natural language generation, I've created a system that provides professional-grade reporting for the **Downtown Men’s Hockey League (DMHL)** in Toronto.

### The Pipeline (Under the Hood)
* **Ingestion:** A Selenium-based engine crawls the official DMHL site, utilizing **Explicit URL Guards** and **Recursive Retry Loops** to ensure data integrity in high-latency environments.
* **Analysis:** An ETL layer processes raw boxscores into structured team efficiency metrics (Power Play/Penalty Kill) and seasonal leaders.
* **Narrative Generation:** The cleaned data is fed into **Google Gemini** using advanced prompt engineering to produce analytical, locker-room-style columns that are 100% evidence-backed.

---

### 📊 The State of the League
*A visualization of Goal Differential vs. Total Points. Teams in the top-right are dominant; those in the bottom-left are underperforming.*

<figure style="text-align: center; margin-top: 1.5em; margin-bottom: 2.5em;">
  <img src="{{ '/assets/images/league_parity.png' | relative_url }}" alt="DMHL League Parity Scatter Plot" style="border: 1px solid #eaeaea; border-radius: 4px; box-shadow: 0 4px 12px rgba(0,0,0,0.1); max-width: 100%;">
  <figcaption style="font-size: 0.85rem; color: #666; margin-top: 12px; font-style: italic;">
    Generated via `viz_generator.py`. Updated weekly following Wednesday night games.
  </figcaption>
</figure>

---

# The Feed
The archives of **The Low B Dispatch**. We focus on the 80%—the weekly play-by-play—and the 20% context that grounds results in the standings. No fluff, just the facts and the Three Stars.