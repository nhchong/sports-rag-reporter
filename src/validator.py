import os
import json
import pandas as pd
import re
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

USE_MOCK = False 

POSTS_DIR = "docs/_posts"
FILES = {
    "details": "data/game_details.csv",
    "manifest": "data/games_manifest.csv",
}

def clean_text(text):
    if not text or not isinstance(text, str): return ""
    text = text.replace("’", "'").replace("'", "").strip()
    text = re.sub(r'\s*[\-\u2013\u2014]\s*', '-', text)
    return text.lower()

def audit_report_integrity():
    try:
        # --- 🛡️ STEP 1: LOAD & FILTER FOR TODAY ONLY ---
        raw_data = {k: pd.read_csv(v) for k, v in FILES.items()}
        
        today_str = datetime.now().strftime('%Y-%m-%d')
        print(f"📅 VALIDATOR FOCUS: {today_str}")

        # Filter manifest and details to ONLY include today's scrape
        data = {}
        data['manifest'] = raw_data['manifest'][raw_data['manifest']['Date'].str.contains("Mar 2", na=False)].copy()
        data['details'] = raw_data['details'][raw_data['details']['ScrapedAt'] == today_str].copy()
        
        if data['manifest'].empty:
            print(f"⚠️ No games found in manifest for today. Check your scraper.")
            return False

    except Exception as e:
        print(f"❌ FAIL: Loading/Filtering CSVs: {e}")
        return False

    # Get the latest report
    all_files = [os.path.join(POSTS_DIR, f) for f in os.listdir(POSTS_DIR) if f.endswith(".md")]
    all_files.sort(key=os.path.getmtime, reverse=True)
    if not all_files:
        print("❌ No report files found.")
        return False
    current_post_path = all_files[0]
    
    print("🤖 MODE: LIVE (Calling Gemini API)")
    from google import genai
    from google.genai import types
    
    client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
    with open(current_post_path, "r") as f:
        content = f.read()
    
    # --- 🎯 THE STRICT WHITELIST PROMPT ---
    prompt = (
        "Extract ONLY the following five categories from the report: "
        "1. Facility (metadata) "
        "2. Matchups (home team, away team, and final score) "
        "3. Goals (player and if it was PP or SH) "
        "4. Assists (player) "
        "5. Penalties (player and specific infraction like 'holding') "
        "6. Officials (names mentioned) "
        "Ignore everything else, including Three Stars, Series Math, and Excerpts. "
        f"Report content: {content}"
    )
    
    schema = {
        "type": "OBJECT",
        "properties": {
            "metadata": {"type": "OBJECT", "properties": {"facility": {"type": "STRING"}}},
            "matchups": {"type": "ARRAY", "items": {"type": "OBJECT", "properties": {"home": {"type": "STRING"}, "away": {"type": "STRING"}, "score": {"type": "STRING"}}}},
            "events": {"type": "ARRAY", "items": {"type": "OBJECT", "properties": {
                "player": {"type": "STRING"}, 
                "type": {"type": "STRING"},
                "subtype": {"type": "STRING"}
            }}},
            "officials": {"type": "ARRAY", "items": {"type": "STRING"}}
        }
    }

    response = client.models.generate_content(
        model="gemini-2.5-flash", 
        contents=prompt, 
        config=types.GenerateContentConfig(response_mime_type='application/json', response_schema=schema)
    )
    audit_data = json.loads(response.text)

    print(f"\n--- 🧪 VALIDATOR START: {os.path.basename(current_post_path)} ---")
    errors = []

    # 1. VALIDATE MATCHUPS & SCORES
    m_df = data['manifest']
    m_df['Home_Clean'] = m_df['Home'].apply(clean_text)
    m_df['Away_Clean'] = m_df['Away'].apply(clean_text)
    
    valid_game_ids = []
    print(f"🥅 AUDITING MATCHUPS & SCORES...")
    for m in audit_data.get('matchups', []):
        t1, t2 = clean_text(m['home']), clean_text(m['away'])
        # Match against our "Today Only" manifest
        match_truth = m_df[((m_df['Home_Clean'] == t1) & (m_df['Away_Clean'] == t2)) | ((m_df['Home_Clean'] == t2) & (m_df['Away_Clean'] == t1))].sort_values(by='GameID', ascending=False)
        
        if not match_truth.empty:
            g_row = match_truth.iloc[0]
            valid_game_ids.append(str(g_row['GameID'])) # Ensure string for comparison
            
            actual_score = clean_text(str(g_row['Score']))
            rep_score = clean_text(m['score'])
            flipped = "-".join(rep_score.split("-")[::-1])
            
            if rep_score == actual_score or flipped == actual_score:
                print(f"   ✅ Verified Matchup: {m['home']} vs {m['away']} ({m['score']})")
            else:
                errors.append(f"SCORE ERROR: {m['home']} vs {m['away']} says {m['score']}, data says {g_row['Score']}")
        else:
            errors.append(f"MATCHUP ERROR: {m['home']} vs {m['away']} not in today's games.")

    # 2. AUDIT PLAYER EVENTS
    print(f"\n🏒 AUDITING PLAYER EVENTS...")
    details_df = data['details']
    details_df['GameID'] = details_df['GameID'].astype(str)
    
    # Restrict search ONLY to the GameIDs identified in today's manifest
    restricted_details = details_df[details_df['GameID'].isin(valid_game_ids)].copy()
    restricted_details['Desc_Clean'] = restricted_details['Description'].apply(clean_text)

    for event in audit_data.get('events', []):
        p_name = clean_text(event.get('player', ''))
        e_type = event.get('type', '').lower()
        e_subtype = clean_text(event.get('subtype', ''))
        
        if not any(x in e_type for x in ['goal', 'assist', 'penalty', 'netted']):
            continue

        potential_rows = restricted_details[restricted_details['Desc_Clean'].str.contains(p_name, case=False, na=False)]
        found = False
        for _, row in potential_rows.iterrows():
            row_type = row['EventType'].lower()
            if "assist" in e_type:
                if row_type == "goal" and "(" in row['Description'] and p_name in clean_text(row['Description'].split('(')[1]):
                    found = True
            elif "penalty" in e_type:
                if row_type == "penalty" and (not e_subtype or e_subtype in row['Desc_Clean']):
                    found = True
            elif "goal" in e_type or "netted" in e_type:
                if row_type == "goal" and p_name in clean_text(row['Description'].split('(')[0]):
                    found = True
            if found: break

        if found:
            print(f"   ✅ VERIFIED: {event.get('player')} ({e_type})")
        else:
            print(f"   ❌ FAIL: {event.get('player')} ({e_type}) - Factual violation.")
            errors.append(f"EVENT ERROR: {event.get('player')} ({e_type}) is a hallucination.")

    # 3. AUDIT OFFICIALS
    print(f"\n👮 AUDITING OFFICIALS...")
    for off in audit_data.get('officials', []):
        off_clean = clean_text(off)
        off_found = not restricted_details[restricted_details['Desc_Clean'].str.contains(off_clean, case=False, na=False)].empty
        if off_found:
            print(f"   ✅ VERIFIED: Official {off}")
        else:
            print(f"   ❌ FAIL: Official {off} - Not in today's data.")
            errors.append(f"OFFICIAL ERROR: {off} was not listed for these games.")

    print("\n" + "=" * 60)
    if errors:
        print(f"🛑 AUDIT FAILED: {len(errors)} discrepancies found.")
        for e in errors: print(f" -> {e}")
        return False

    print("✅ AUDIT PASSED: Data Integrity Verified.")
    return True

if __name__ == "__main__":
    if not audit_report_integrity():
        exit(1)