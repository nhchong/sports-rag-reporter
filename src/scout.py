import os
import json
import re
import pandas as pd
from datetime import datetime
from google import genai
from dotenv import load_dotenv

load_dotenv()

# --- CONFIGURATION ---
DETAILS_FILE = "data/game_details.csv"
TEAM_STATS_FILE = "data/team_stats.csv"
PLAYER_STATS_FILE = "data/player_stats.csv"
MANIFEST_FILE = "data/games_manifest.csv"

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

def normalize(text):
    """Standardizes names for robust matching (removes 'The', hyphens, extra spaces)."""
    if not isinstance(text, str): return ""
    text = text.lower().replace("-", " ")
    text = re.sub(r'\bthe\b', '', text)
    return " ".join(text.split()).strip()

def get_scouting_data(my_team_raw, opponent_raw):
    """Mines data with column-shift detection and pattern analysis."""
    try:
        details_df = pd.read_csv(DETAILS_FILE)
        team_stats = pd.read_csv(TEAM_STATS_FILE)
        player_stats = pd.read_csv(PLAYER_STATS_FILE)
        manifest_df = pd.read_csv(MANIFEST_FILE)

        my_norm = normalize(my_team_raw)
        opp_norm = normalize(opponent_raw)

        # 1. FIXED H2H: Handle the column shift (Actual Score is in 'Status' column)
        h2h_manifest = manifest_df[
            (manifest_df['Home'].apply(normalize).str.contains(my_norm, na=False) & 
             manifest_df['Away'].apply(normalize).str.contains(opp_norm, na=False)) |
            (manifest_df['Home'].apply(normalize).str.contains(opp_norm, na=False) & 
             manifest_df['Away'].apply(normalize).str.contains(my_norm, na=False))
        ].copy()
        
        h2h_wins, h2h_losses, h2h_ties = 0, 0, 0
        h2h_history_list = []
        
        for _, game in h2h_manifest.iterrows():
            # DETECT SHIFT: If 'Score' is the division, actual score is in 'Status'
            score_raw = str(game['Status']) if '-' in str(game['Status']) else str(game['Score'])
            scores = score_raw.split('-')
            
            if len(scores) == 2:
                s1, s2 = int(scores[0].strip()), int(scores[1].strip())
                is_home = my_norm in normalize(game['Home'])
                my_score = s1 if is_home else s2
                opp_score = s2 if is_home else s1
                
                res = "T" if s1 == s2 else ("W" if my_score > opp_score else "L")
                if res == "W": h2h_wins += 1
                elif res == "L": h2h_losses += 1
                else: h2h_ties += 1
                
                h2h_history_list.append({
                    "date": game.get('Date', 'N/A'),
                    "score": score_raw,
                    "result": res
                })

        # 2. PIM & POINTS DATA
        opp_players = player_stats[player_stats['Team'].str.contains(opponent_raw, case=False, na=False)].copy()
        if 'Pts' not in opp_players.columns: opp_players['Pts'] = opp_players['G'] + opp_players['A']
        
        pim_intel = {
            "team_total": int(opp_players['PIM'].sum()),
            "offenders": opp_players.sort_values(by='PIM', ascending=False).head(3)[['Player', 'PIM', 'Pts']].to_dict('records')
        }

        # 3. STANDINGS & MOMENTUM
        us_stats = team_stats[team_stats['Team'].str.contains(my_team_raw, case=False, na=False)].iloc[0].to_dict()
        them_stats = team_stats[team_stats['Team'].str.contains(opponent_raw, case=False, na=False)].iloc[0].to_dict()

        return {
            "matchup": f"{my_team_raw} vs {opponent_raw}",
            "records": {"us": us_stats, "them": them_stats},
            "h2h": {"summary": f"{h2h_wins}-{h2h_losses}-{h2h_ties}", "history": h2h_history_list},
            "pim_intel": pim_intel,
            "opp_top_scorers": opp_players.sort_values(by='Pts', ascending=False).head(3).to_dict('records'),
            "raw_tape_for_patterns": details_df.tail(200).to_dict('records')
        }
    except Exception as e:
        print(f"❌ Data Extraction Error: {e}")
        return None

def generate_whatsapp_brief():
    my_team, opponent = "Shockers", "Flat-Earthers"
    data = get_scouting_data(my_team, opponent)
    if not data: return

    system_instruction = f"""
    You are the Shockers Lead Scout using Gemini 2.5 Flash.  
    Target Audience: 20-35 year old men (WhatsApp Group).
    
    VOICE: Athletic x Spittin' Chiclets. Data-heavy but grit-focused. No corporate fluff. No cringe.
    
    STRICT DATA RULES:
    1. H2H: We are 0-3 against them. Use 'history' to cite Dec 22 (2-3), Nov 3 (3-6), and Oct 6 (0-1). Frame this as a vendetta.
    2. PATTERN: Review Goal Differentials. If they are #3 with a negative diff and we are #6 with a positive diff, identify them as 'Frauds' who are lucky to be where they are.
    
    FORMAT: 
    - 1. STANDINGS (Seed & Pts)
    - 2. RECORDS (Full season W-L-T)
    - 3. H2H BATTLE (Exact dates and scores)
    - 4. OPPONENT INTEL (Top 3 Pts & PIM Leader. Include player numbers on first mention.)
    - 5. Compelling Pattern (One high-value tactical insight found in the stats)

    CONSTRAINT: Under 300 words. Pithy and aggressive.
    """

    prompt = f"DATA PACKAGE:\n{json.dumps(data)}\n\nTask: Generate the bare-bones WhatsApp scouting brief." 

    try:
        response = client.models.generate_content(model="gemini-2.5-flash", contents=[system_instruction, prompt])
        print("\n📱 COPY THIS INTO WHATSAPP:\n")
        print("═"*45 + "\n" + response.text + "\n" + "═"*45)
    except Exception as e:
        print(f"❌ Gemini API Error: {e}")

if __name__ == "__main__":
    generate_whatsapp_brief()