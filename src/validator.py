import os
import json
import pandas as pd
import re
from datetime import datetime, timedelta
from google import genai
from dotenv import load_dotenv

load_dotenv()

# --- CONFIGURATION ---
POSTS_DIR = "docs/_posts"
FILES = {
    "details": "data/game_details.csv",
    "manifest": "data/games_manifest.csv",
}

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

def clean_text(text):
    """General normalization: handles apostrophes and removes player number symbols (#)."""
    if not text or not isinstance(text, str): return ""
    text = text.replace("#", "").replace("’", "").replace("'", "").strip()
    return text.lower()

def clean_team_name(text):
    """Specific for teams: Strips seeds like '(1st Seed)' so they match the manifest."""
    if not text: return ""
    text = re.sub(r'\(.*?\)', '', text)
    return " ".join(clean_text(text).split())

def audit_report_integrity():
    try:
        # --- 🛡️ STEP 1: LOAD & FILTER (8-DAY WINDOW) ---
        raw_data = {k: pd.read_csv(v) for k, v in FILES.items()}
        
        start_date = datetime.now() - timedelta(days=8)
        raw_data['details']['ScrapedAt'] = pd.to_datetime(raw_data['details']['ScrapedAt'])
        
        data = {
            'manifest': raw_data['manifest'].copy(),
            'details': raw_data['details'][raw_data['details']['ScrapedAt'] >= start_date.replace(hour=0, minute=0)].copy()
        }
        
        # IMPORTANT: We keep the parentheses here so the assist logic can see them
        data['details']['Desc_Clean'] = data['details']['Description'].apply(clean_text)
        
        all_posts = sorted([f for f in os.listdir(POSTS_DIR) if f.endswith(".md")])
        latest_report_path = os.path.join(POSTS_DIR, all_posts[-1])
        with open(latest_report_path, 'r') as f:
            report_content = f.read()
        print(f"📝 AUDITING: {all_posts[-1]}")

    except Exception as e:
        print(f"❌ FAIL: Setup: {e}")
        return False

    # --- 🤖 STEP 2: STRUCTURED EXTRACTION ---
    extract_prompt = f"""
    Extract specific facts from this hockey report into JSON.
    REPORT CONTENT:
    {report_content}

    JSON STRUCTURE:
    {{
      "matchups": [{{ "home": "str", "away": "str", "score": "X-Y" }}],
      "events": [{{ "player": "Full Name", "type": "goal/assist/penalty" }}],
      "officials": ["Name"]
    }}
    """
    
    try:
        response = client.models.generate_content(model="gemini-2.5-flash", contents=[extract_prompt])
        json_str = response.text.replace("```json", "").replace("```", "").strip()
        audit_data = json.loads(json_str)
    except Exception as e:
        print(f"❌ FAIL: AI Extraction: {e}")
        return False

    errors = []

    # --- 🏒 STEP 3: VERIFICATION ---
    
    # 1. Audit Scores
    print(f"\n🥅 AUDITING MATCHUPS & SCORES...")
    for m in audit_data.get('matchups', []):
        t1, t2 = clean_team_name(m.get('home', '')), clean_team_name(m.get('away', ''))
        
        # DEFENSIVE CHECK: Handle cases where AI returns null for score
        raw_score = m.get('score')
        if not raw_score: 
            continue
            
        reported_score = str(raw_score).replace(" ", "")
        
        if not re.match(r'^\d+-\d+$', reported_score): continue # Ignore non-numerical summaries

        match = data['manifest'][
            ((data['manifest']['Home'].apply(clean_team_name).str.contains(t1)) & (data['manifest']['Away'].apply(clean_team_name).str.contains(t2))) |
            ((data['manifest']['Home'].apply(clean_team_name).str.contains(t2)) & (data['manifest']['Away'].apply(clean_team_name).str.contains(t1)))
        ]
        
        all_valid_scores = []
        for csv_s in match['Score'].str.replace(" ", "").values:
            all_valid_scores.append(csv_s)
            if "-" in csv_s:
                p = csv_s.split("-")
                all_valid_scores.append(f"{p[1]}-{p[0]}")
        
        if reported_score not in all_valid_scores:
            errors.append(f"SCORE ERROR: {m['home']} vs {m['away']} reported {reported_score}")
        else:
            print(f"   ✅ Verified: {m['home']} vs {m['away']} ({reported_score})")

    # 2. Audit Player Events
    print(f"\n🏒 AUDITING PLAYER EVENTS...")
    for event in audit_data.get('events', []):
        p_name, e_type = clean_text(event['player']), event['type'].lower()
        # Find rows where player exists in the Description
        player_rows = data['details'][data['details']['Desc_Clean'].str.contains(p_name)]
        
        found = False
        for _, row in player_rows.iterrows():
            raw_desc = row['Description'].lower()
            if "goal" in e_type and row['EventType'].lower() == "goal":
                # Goal Scorer is ALWAYS before the parenthesis
                if p_name in clean_text(raw_desc.split('(')[0]): found = True
            elif "assist" in e_type and row['EventType'].lower() == "goal":
                # Assistants are ALWAYS inside the parenthesis
                if "(" in raw_desc and p_name in clean_text(raw_desc.split('(')[1]): found = True
            elif "penalty" in e_type and row['EventType'].lower() == "penalty":
                found = True
            if found: break

        if found:
            print(f"   ✅ VERIFIED: {event['player']} ({e_type})")
        else:
            errors.append(f"EVENT ERROR: {event['player']} ({e_type}) not found.")
            print(f"   ❌ FAIL: {event['player']} ({e_type})")

    print("\n" + "=" * 60)
    if not errors:
        print("🎉 AUDIT PASSED: All claims verified against directional data window.")
        return True
    else:
        print(f"🛑 AUDIT FAILED: {len(errors)} discrepancies found.")
        return False

if __name__ == "__main__":
    audit_report_integrity()