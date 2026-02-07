#!/bin/bash
echo "🏒 Running Pipeline..."
python3 src/scraper.py
python3 src/analyzer.py
python3 src/reporter.py

echo "📤 Uploading to GitHub Pages..."
git add docs/
git commit -m "Automated Dispatch Update: $(date)"
git push origin main

echo "🏁 Dispatch is live at https://nhchong.github.io/sports-rag-reporter/"