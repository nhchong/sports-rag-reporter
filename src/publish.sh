#!/bin/bash

# ---------------------------------------------------------
# DEMO MODE LOGIC
# ---------------------------------------------------------

# 1. Check for Validator Fail
#if [[ "$1" == "--validator-fail" ]]; then
#    echo "⚠️ [DEMO MODE]: Isolated Factual Audit."
#   echo "📂 Running ONLY the validator on the current draft..."
#   echo ""
#    python3 src/validator.py
#   echo "🏁 Demo complete. (Deployment skipped due to CLI flag)"
#    exit 0
#fi

# 2. Check for Bias Fail
if [[ "$1" == "--bias-fail" ]]; then
    echo "⚠️ [DEMO MODE]: Isolated Bias Audit."
    echo "🛡️ Running ONLY the Trust & Safety checker..."
    echo ""
    python3 src/bias_checker.py
    echo ""
    echo "🏁 Demo complete. (Deployment skipped due to CLI flag)"
    exit 0
fi

# 3. Block any other unknown arguments
if [[ -n "$1" ]]; then
    echo "❌ Unknown argument: $1"
    exit 1
fi

# ---------------------------------------------------------
# FULL PIPELINE (Only runs if NO arguments are provided)
# ---------------------------------------------------------
echo "🏒 Running Full Pipeline..."

# 1. Data Ingestion
python3 src/scraper.py

# 2. Human-in-the-Loop Enrichment
echo "📝 ENTERING EXECUTIVE EDITOR MODE..."
python3 src/enricher.py

# 3. Processing & Generation
python3 src/analyzer.py
echo "✍️ Writing this weeks Dispatch..."
python3 src/reporter.py

# 4. Factual Integrity
#echo "🧮 Running Factual Validator..."
#VALIDATOR_OUTPUT=$(python3 src/validator.py)
#echo "$VALIDATOR_OUTPUT"

#if [[ "$VALIDATOR_OUTPUT" == *"🛑 AUDIT FAILED"* ]]; then
   # echo ""
   # echo "🚨 FACTUAL ERROR DETECTED: The AI hallucinated or misreported data."
   # echo "🛑 DEPLOYMENT ABORTED: Fix docs/_posts/ and run again."
   # exit 1
#fi

# 5. Bias Audit & Human-in-the-Loop
echo "🛡️ Running Trust & Safety Audit..."
BIAS_OUTPUT=$(python3 src/bias_checker.py)
echo "$BIAS_OUTPUT"

if [[ "$BIAS_OUTPUT" == *"PUBLICATION HALTED"* ]]; then
    echo ""
    echo "⚠️ BIAS DETECTED: The AI flagged potential framing issues."
    read -p "👨‍⚖️ EDITOR-IN-CHIEF OVERRIDE: Do you want to publish this report anyway? (y/n): " choice
    
    case "$choice" in 
      y|Y ) echo "✅ Override accepted. Proceeding..." ;;
      * ) echo "🛑 DEPLOYMENT ABORTED."; exit 1 ;;
    esac
fi

# ---------------------------------------------------------
# DEPLOYMENT (Only reached if no CLI flags were used)
# ---------------------------------------------------------
echo "📤 Uploading to GitHub Pages..."
git add .
git commit -m "Automated Dispatch Update: $(date)"
git push origin main

echo "🏁 Dispatch is live at https://nhchong.github.io/sports-rag-reporter/"