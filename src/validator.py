import os
import json
import pandas as pd
import re
from dotenv import load_dotenv

load_dotenv()

# --- 💡 THE TOGGLE SWITCH ---
USE_MOCK = True  # Set to False to audit actual .md files using Gemini
# ----------------------------

POSTS_DIR = "docs/_posts"
FILES = {
    "details": "data/game_details.csv",
    "manifest": "data/games_manifest.csv",
    "player_stats": "data/player_stats.csv",
    "playoff_standings": "data/playoff_standings.csv"
}

# FULL MOCK DATA (Restored and Complete)
MOCK_DATA = {
    "metadata": {
        "facility": "St. Mikes Arena",
        "date": "Wednesday"
    },
    "matchups": [
        {"home": "Don Cherry's", "away": "Muffin Men", "score": "5-1"},
        {"home": "The Sahara", "away": "4 Lines", "score": "6-4"},
        {"home": "Flat-Earthers", "away": "The Shockers", "score": "1-1"}
    ],
    "events": [
        {"player": "Michael Murphy", "type": "Goal", "detail": "Michael Murphy opened their account with a powerplay goal in the second period"},
        {"player": "Conor Pang", "type": "Assist", "detail": "assisted by Conor Pang"},
        {"player": "Jack Pirie", "type": "Goal", "detail": "adding to an even-strength tally from Jack Pirie in the first"},
        {"player": "Sean Murphy", "type": "Goal", "detail": "Sean Murphy also chipped in with a powerplay marker"},
        {"player": "Cosimo Morin", "type": "Goal", "detail": "Despite an early even-strength goal from Muffin Men's Cosimo Morin"},
        {"player": "Derrick Wong", "type": "Goal", "detail": "including goals from Derrick Wong"},
        {"player": "Mac Savage", "type": "Goal", "detail": "Mac Savage"},
        {"player": "Kosta Likourezos", "type": "Goal", "detail": "Kosta Likourezos"},
        {"player": "Wil Nenadovic", "type": "Goal", "detail": "Wil Nenadovic"},
        {"player": "Andrew Biggs", "type": "Goal", "detail": "Andrew Biggs"},
        {"player": "Brendan Hancock", "type": "Goal", "detail": "and Brendan Hancock"},
        {"player": "Adam Miller", "type": "Goal", "detail": "4 Lines' Adam Miller put up a valiant two-goal effort"},
        {"player": "Shane Ferguson", "type": "Goal", "detail": "with Shane Ferguson adding a shorthanded tally"},
        {"player": "Marcus Simmonds", "type": "Goal", "detail": "with Marcus Simmonds scoring for the Flat-Earthers"},
        {"player": "Alex Matheson", "type": "Goal", "detail": "and Alex Matheson finding the net for The Shockers"},
        {"player": "Caden Bower", "type": "Penalty", "detail": "notably a double-minor for high-sticking to The Shockers' Caden Bower"}, # FAILS: Text describes penalty
        {"player": "Brandon Sanders", "type": "Penalty", "detail": "and a pair of minors to Flat-Earthers' Brandon Sanders"},
        {"player": "Michael Murphy", "type": "Assist", "detail": "With a goal and an assist, including a critical powerplay marker, Murphy spearheaded"},
        {"player": "Kosta Likourezos", "type": "Assist", "detail": "Likourezos contributed a goal and an assist in The Sahara's high-scoring win"}
    ],
    "officials": [
        "Evan Benwell",
        "Brad Kuchar"
    ],
    "rankings": [
        {"team": "Don Cherry's", "rk": 1}
    ]
}

def normalize_score(score_str):
    """Standardizes score strings: removes spaces and handles all dash types."""
    if not score_str: return ""
    return str(score_str).replace('–', '-').replace('—', '-').replace(" ", "")

def audit_report_integrity():
    # 1. Load Sources
    data = {k: pd.read_csv(v) for k, v in FILES.items()}
    errors = []
    
    # 2. Select Report File (Sort by Modification Time)
    all_files = [os.path.join(POSTS_DIR, f) for f in os.listdir(POSTS_DIR) if f.endswith(".md")]
    all_files.sort(key=os.path.getmtime, reverse=True)
    
    if not all_files:
        print("❌ No report files found.")
        return False
    
    current_post_path = all_files[0]
    
    # 3. Get Audit Data (Toggle between Mock and Live)
    if USE_MOCK:
        print("🛠️ MODE: MOCK (Internal JSON Fixture)")
        audit_data = MOCK_DATA
    else:
        print("🤖 MODE: LIVE (Calling Gemini API)")
        # (Gemini API logic remains here in your actual file)
        from google import genai
        client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
        with open(current_post_path, "r") as f:
            content = f.read()
        prompt = f"Extract factual claims to JSON: {content}" # Condensed for brevity
        response = client.models.generate_content(model="gemini-2.0-flash", contents=prompt, config={'response_mime_type': 'application/json'})
        audit_data = json.loads(response.text)

    print(f"\n--- 🧪 VALIDATOR START: {os.path.basename(current_post_path)} ---")

    # 4. Step 1: Order-Agnostic Matchup Detection
    valid_game_ids = []
    m_df = data['manifest']
    facility_col = next((c for c in ['Facility', 'Arena', 'Rink'] if c in m_df.columns), 'Facility')
    score_col = next((c for c in ['Score', 'FinalScore', 'Result'] if c in m_df.columns), 'Score')
    reported_facility = audit_data['metadata'].get('facility', '')

    print(f"🥅 TRIANGULATING UNIQUE GAME_IDs...")
    for m in audit_data.get('matchups', []):
        t1, t2 = m['home'], m['away']
        
        # Order-agnostic search: (T1 vs T2) OR (T2 vs T1)
        match_truth = m_df[
            ((m_df['Home'] == t1) & (m_df['Away'] == t2) |
             (m_df['Home'] == t2) & (m_df['Away'] == t1)) &
            (m_df[facility_col].str.contains(reported_facility, case=False, na=False))
        ]
        
        if not match_truth.empty:
            g_row = match_truth.sort_values(by='GameID', ascending=False).iloc[0]
            g_id = int(g_row['GameID'])
            valid_game_ids.append(g_id)
            
            # Normalize and handle score flip if teams are swapped in manifest
            actual_score = normalize_score(g_row[score_col])
            reported_score = normalize_score(m['score'])
            
            if g_row['Home'] != t1:
                parts = reported_score.split('-')
                if len(parts) == 2:
                    reported_score = f"{parts[1]}-{parts[0]}"
            
            score_match = (actual_score == reported_score) or (actual_score == "0-0" and "forfeit" in m['score'].lower())
            print(f"   ✅ Game {g_id}: {t1} vs {t2} | Score Match: {'✅' if score_match else '❌ (Data says '+actual_score+')'}")
            if not score_match:
                errors.append(f"SCORE ERROR: {t1} vs {t2} mismatch.")
        else:
            print(f"   ⚠️ NOT FOUND: {t1} vs {t2} at {reported_facility}")
            errors.append(f"MATCHUP ERROR: {t1} vs {t2} missing.")

    # 5. Step 2: Context-Aware Event Audit (Positional Parsing)
    print(f"\n🏒 AUDITING EVENTS IN GAME_IDs: {valid_game_ids}")
    details_df = data['details']
    active_details = details_df[details_df['GameID'].astype(int).isin(valid_game_ids)]

    for event in audit_data.get('events', []):
        p_name, e_type = event['player'], event['type']
        found = False

        if e_type == "Goal":
            # Must be outside brackets in a Goal row
            matches = active_details[
                (active_details['EventType'] == 'Goal') & 
                (active_details['Description'].str.split('(').str[0].str.contains(p_name, case=False, na=False))
            ]
            found = not matches.empty

        elif e_type == "Assist":
            # Must be inside brackets in a Goal row
            matches = active_details[
                (active_details['EventType'] == 'Goal') & 
                (active_details['Description'].str.contains(r'\(.*\b' + re.escape(p_name) + r'\b.*\)', case=False, na=False, regex=True))
            ]
            found = not matches.empty

        elif e_type == "Penalty":
            # Standard Penalty check
            matches = active_details[
                (active_details['EventType'] == 'Penalty') & 
                (active_details['Description'].str.contains(p_name, case=False, na=False))
            ]
            found = not matches.empty

        if found:
            print(f"   ✅ VERIFIED: {p_name} {e_type}")
        else:
            print(f"   ❌ FAIL: {p_name} {e_type} position/log mismatch.")
            errors.append(f"EVENT ERROR: {p_name} {e_type} hallucination.")

    # 6. Step 3: Official Verification
    print(f"\n👮 AUDITING OFFICIALS...")
    for off in audit_data.get('officials', []):
        off_truth = active_details[active_details['Description'].str.contains(off, case=False, na=False)]
        if off_truth.empty:
            print(f"   ❌ FAIL: Official {off} missing.")
            errors.append(f"OFFICIAL ERROR: {off} assignment.")
        else:
            print(f"   ✅ VERIFIED: {off} on-site.")

    # 7. Step 4: Standings Audit
    print(f"\n📊 VALIDATING STANDINGS...")
    for rk in audit_data.get('rankings', []):
        team, rank = rk['team'], rk['rk']
        if team in data['playoff_standings']['Team'].values:
            actual_rk = data['playoff_standings'][data['playoff_standings']['Team'] == team]['Rk'].values[0]
            match = rank == actual_rk
            print(f"   {team} | Reported: {rank} | Actual: {actual_rk} {'✅' if match else '❌'}")
            if not match:
                errors.append(f"RANKING ERROR: {team} rank mismatch.")

    # 8. Final Verdict
    print("\n" + "=" * 60)
    if errors:
        print(f"🛑 AUDIT FAILED: {len(errors)} discrepancies found.")
        for e in errors:
            print(f" -> {e}")
        print("=" * 60)
        return False

    print("✅ AUDIT PASSED: 100% Relational & Positional Integrity.")
    print("=" * 60)
    return True

if __name__ == "__main__":
    audit_report_integrity()