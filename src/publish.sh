#!/bin/bash

echo "🏒 Running Pipeline..."

# 1. Get Data
python3 src/scraper.py

# 2. Crunch Numbers
python3 src/analyzer.py

# 3. Generate Visuals
#echo "🎨 Generating Graphics..."
#python3 src/viz_generator.py

# 4. Write the Story
echo "✍️ Writing the Dispatch..."
python3 src/reporter.py

# ---------------------------------------------------------
# STAGE 1: FACTUAL INTEGRITY (Data Hallucination Check)
# ---------------------------------------------------------
echo "🧮 Running Factual Validator..."
VALIDATOR_OUTPUT=$(python3 src/validator.py)
echo "$VALIDATOR_OUTPUT"

if [[ "$VALIDATOR_OUTPUT" == *"🛑 AUDIT FAILED"* ]]; then
    echo ""
    echo "🚨 FACTUAL ERROR DETECTED: The AI hallucinated or misreported data."
    echo "🛑 DEPLOYMENT ABORTED: Fix docs/_posts/ and run again."
    exit 1
fi

# ---------------------------------------------------------
# STAGE 2: NARRATIVE INTEGRITY (Bias & Subjectivity Check)
# ---------------------------------------------------------
echo "🛡️ Running Trust & Safety Audit..."
BIAS_OUTPUT=$(python3 src/bias_checker.py)
echo "$BIAS_OUTPUT"

# Human-in-the-Loop Override Logic
if [[ "$BIAS_OUTPUT" == *"PUBLICATION HALTED"* ]]; then
    echo ""
    echo "⚠️ BIAS DETECTED: The AI flagged potential framing issues above."
    
    # Pause the script and ask for human input
    read -p "👨‍⚖️ EDITOR-IN-CHIEF OVERRIDE: Do you want to publish this report anyway? (y/n): " choice
    
    case "$choice" in 
      y|Y ) 
        echo "✅ Override accepted. Proceeding with deployment..."
        ;;
      * ) 
        echo "🛑 DEPLOYMENT ABORTED: Report held back for edits. Fix docs/_posts/ and run again."
        exit 1
        ;;
    esac
else
    echo "✅ Bias Audit passed cleanly. Proceeding with deployment..."
fi

# ---------------------------------------------------------
# DEPLOYMENT
# ---------------------------------------------------------
echo "📤 Uploading to GitHub Pages..."
git add docs/
git commit -m "Automated Dispatch Update: $(date)"
git push origin main

echo "🏁 Dispatch is live at https://nhchong.github.io/sports-rag-reporter/"