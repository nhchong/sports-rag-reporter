"""
Report Integrity Validator

This script acts as an automated QA pipeline. It uses an LLM to parse unstructured 
Markdown newsletters, extract factual claims (scores, player events), and programmatically 
verify those claims against the raw source-of-truth CSV datasets.
"""

import os
import json
import pandas as pd
import re
from datetime import datetime, timedelta
from google import genai
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# --- CONFIGURATION & CONSTANTS ---
POSTS_DIR = "docs/_posts"
FILES = {
    "details": "data/game_details.csv",
    "manifest": "data/games_manifest.csv",
}

# Initialize LLM Client
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))


def clean_text(text: str) -> str:
    """
    Normalizes strings for reliable comparison.
    Removes specific punctuation and converts to lowercase.
    
    Args:
        text (str): The raw string to clean.
        
    Returns:
        str: The normalized string.
    """
    if not text or not isinstance(text, str): 
        return ""
    text = text.replace("#", "").replace("’", "").replace("'", "").strip()
    return text.lower()


def clean_team_name(text: str) -> str:
    """
    Strips parenthetical metadata (like playoff seedings) from team names 
    so they accurately match the raw manifest formatting.
    
    Args:
        text (str): The raw team name.
        
    Returns:
        str: The cleaned team name.
    """
    if not text: 
        return ""
    # Remove any content within parentheses
    text = re.sub(r'\(.*?\)', '', text)
    return " ".join(clean_text(text).split())


def audit_report_integrity() -> bool:
    """
    Executes the end-to-end data validation pipeline.
    
    Flow:
    1. Determines the most recent publication.
    2. establishes a chronological bounding box for data retrieval.
    3. Prompts the LLM to extract structured facts from the raw text.
    4. Validates extracted facts against the CSV datasets.
    
    Returns:
        bool: True if all claims are verified, False if discrepancies are found or execution fails.
    """
    try:
        # --- STEP 1: DATA INGESTION & TEMPORAL FILTERING ---
        raw_data = {k: pd.read_csv(v) for k, v in FILES.items()}
        
        # Identify the most recent report target for auditing
        all_posts = sorted([f for f in os.listdir(POSTS_DIR) if f.endswith(".md")])
        if not all_posts:
            print("❌ FAIL: No markdown posts found in directory.")
            return False

        latest_file = all_posts[-1]
        latest_report_path = os.path.join(POSTS_DIR, latest_file)
        
        with open(latest_report_path, 'r') as f:
            report_content = f.read()
        print(f"📝 AUDITING: {latest_file}")

        # Parse the report date from the filename to establish the audit timeline
        try:
            report_date = pd.to_datetime(latest_file[:10])
        except ValueError:
            # Fallback to current runtime if filename parsing fails
            report_date = datetime.now()

        # Define a 28-day bounding box (14 days prior/post) to capture relevant 
        # game data while excluding unrelated seasonal data.
        start_date = report_date - timedelta(days=14)
        end_date = report_date + timedelta(days=14)

        raw_data['details']['ScrapedAt'] = pd.to_datetime(raw_data['details']['ScrapedAt'])
        
        # Construct the localized dataset
        data = {
            'manifest': raw_data['manifest'].copy(),
            'details': raw_data['details'][
                (raw_data['details']['ScrapedAt'] >= start_date) & 
                (raw_data['details']['ScrapedAt'] <= end_date)
            ].copy()
        }
        
        # Pre-compute cleaned descriptions for faster iterative searching later
        data['details']['Desc_Clean'] = data['details']['Description'].apply(clean_text)

    except Exception as e:
        print(f"❌ FAIL: Pipeline Setup Error: {e}")
        return False

    # --- STEP 2: STRUCTURED LLM EXTRACTION ---
    # We instruct the model to act purely as an extraction parser,
    # mapping unstructured narrative into a strict JSON schema.
    extract_prompt = f"""
    You are a precise data extraction tool. Read the following sports report and extract the facts into the exact JSON structure below. 
    Even if the report is written as a flowing narrative or a championship retrospective, you MUST hunt for the hidden final scores, goals, and assists.

    REPORT CONTENT:
    {report_content}

    JSON STRUCTURE:
    {{
      "matchups": [{{"home": "Team Name", "away": "Team Name", "score": "X-Y"}}],
      "events": [{{"player": "Full Name", "type": "goal"}}, {{"player": "Full Name", "type": "assist"}}],
      "officials": ["Name"]
    }}
    """
    
    try:
        # Execute LLM call
        response = client.models.generate_content(model="gemini-2.5-flash", contents=[extract_prompt])
        
        # Sanitize and parse JSON response
        json_str = response.text.replace("```json", "").replace("```", "").strip()
        audit_data = json.loads(json_str)
        
        # Log the extracted payload for debugging and system visibility
        print("\n🧠 AI EXTRACTION PAYLOAD:")
        print(json.dumps(audit_data, indent=2))
        
        # Defensive check against empty extractions (prevents silent false-positives)
        if not audit_data.get('matchups') and not audit_data.get('events'):
            print("\n⚠️ WARNING: The AI extracted zero matchups and zero events. Check if the report is empty or lacks formatted data.")
            return False

    except Exception as e:
        print(f"❌ FAIL: LLM Extraction Error: {e}")
        return False

    errors = []

    # --- STEP 3: PROGRAMMATIC VERIFICATION ---
    
    # Phase A: Audit Team Matchups and Final Scores
    print(f"\n🥅 AUDITING MATCHUPS & SCORES...")
    for m in audit_data.get('matchups', []):
        t1 = clean_team_name(m.get('home', ''))
        t2 = clean_team_name(m.get('away', ''))
        raw_score = m.get('score')
        
        print(f"   🔍 Checking Matchup: {m.get('home', 'Unknown')} vs {m.get('away', 'Unknown')} | Score: {raw_score}")
        
        # Guard against malformed score data
        if not raw_score: 
            errors.append(f"SCORE ERROR: Missing score for {m.get('home')} vs {m.get('away')}")
            continue
            
        reported_score = str(raw_score).replace(" ", "")
        
        # Bypass non-numerical scores (e.g., forfeits or text summaries)
        if not re.match(r'^\d+-\d+$', reported_score): 
            print(f"      ⏭️  Skipping non-numerical score format: {reported_score}")
            continue 

        # Query the manifest for the matching fixture (bidirectional check)
        match = data['manifest'][
            ((data['manifest']['Home'].apply(clean_team_name).str.contains(t1)) & (data['manifest']['Away'].apply(clean_team_name).str.contains(t2))) |
            ((data['manifest']['Home'].apply(clean_team_name).str.contains(t2)) & (data['manifest']['Away'].apply(clean_team_name).str.contains(t1)))
        ]
        
        # Compile all valid score permutations (e.g., "3-2" and "2-3")
        all_valid_scores = []
        for csv_s in match['Score'].str.replace(" ", "").values:
            all_valid_scores.append(csv_s)
            if "-" in csv_s:
                p = csv_s.split("-")
                all_valid_scores.append(f"{p[1]}-{p[0]}")
        
        # Evaluate discrepancy
        if reported_score not in all_valid_scores:
            errors.append(f"SCORE ERROR: {m['home']} vs {m['away']} reported {reported_score}")
            print(f"      ❌ FAILED: Score {reported_score} not found in manifest.")
        else:
            print(f"      ✅ Verified")

    # Phase B: Audit Individual Player Events (Goals, Assists, Penalties)
    print(f"\n🏒 AUDITING PLAYER EVENTS...")
    for event in audit_data.get('events', []):
        p_name = clean_text(event.get('player', ''))
        e_type = str(event.get('type', '')).lower()
        
        print(f"   🔍 Checking Event: {event.get('player', 'Unknown')} ({e_type})")
        
        # Filter details dataset for any row containing the player's name
        player_rows = data['details'][data['details']['Desc_Clean'].str.contains(p_name)]
        
        found = False
        for _, row in player_rows.iterrows():
            raw_desc = row['Description'].lower()
            
            # Parsing Logic: Assess event syntax based on source CSV conventions
            if "goal" in e_type and row['EventType'].lower() == "goal":
                # Goal scorers are positioned before the parenthesis
                if p_name in clean_text(raw_desc.split('(')[0]): 
                    found = True
            elif "assist" in e_type and row['EventType'].lower() == "goal":
                # Assistants are contained within the parenthesis
                if "(" in raw_desc and p_name in clean_text(raw_desc.split('(')[1]): 
                    found = True
            elif "penalty" in e_type and row['EventType'].lower() == "penalty":
                found = True
                
            if found: 
                break

        # Evaluate discrepancy
        if found:
            print(f"      ✅ Verified")
        else:
            errors.append(f"EVENT ERROR: {event.get('player')} ({e_type}) not found.")
            print(f"      ❌ FAILED: Could not locate event in source telemetry.")

    # --- FINAL REPORTING ---
    print("\n" + "=" * 60)
    if not errors:
        print("🎉 AUDIT PASSED: All claims successfully verified against source datasets.")
        return True
    else:
        print(f"🛑 AUDIT FAILED: {len(errors)} discrepancies found.")
        for err in errors:
            print(f"  - {err}")
        return False


if __name__ == "__main__":
    # Execute script
    audit_report_integrity()