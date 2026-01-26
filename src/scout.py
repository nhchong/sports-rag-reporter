import os
import json
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

# Initialize Gemini 2.5 Flash Client
api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
client = genai.Client(api_key=api_key)

def get_scouting_data(my_team, opponent):
    """Deep-mines granular data to establish records, momentum, and venue history."""
    try:
        # Load all core CSVs
        details_df = pd.read_csv(DETAILS_FILE)
        team_stats = pd.read_csv(TEAM_STATS_FILE)
        player_stats = pd.read_csv(PLAYER_STATS_FILE)
        manifest_df = pd.read_csv(MANIFEST_FILE)

        # 1. PIM DATA FIX: Explicitly extract Team Total and Top Offenders
        # Filter for opponent team using case-insensitive partial match
        opp_players = player_stats[player_stats['Team'].str.contains(opponent, case=False, na=False)].copy()
        
        # Ensure 'Pts' column exists for sorting
        if 'Pts' not in opp_players.columns:
            opp_players['Pts'] = opp_players['G'] + opp_players['A']
            
        # Extract specific PIM leaders to prevent AI hallucinations
        top_pims = opp_players.sort_values(by='PIM', ascending=False).head(3)
        opp_pim_list = top_pims[['Player', 'PIM', 'Pts']].to_dict('records')
        team_total_pim = int(opp_players['PIM'].sum())

        # 2. STANDINGS & SEASON RECORDS
        us_stats = team_stats[team_stats['Team'].str.contains(my_team, case=False, na=False)].iloc[0].to_dict()
        them_stats = team_stats[team_stats['Team'].str.contains(opponent, case=False, na=False)].iloc[0].to_dict()

        # 3. HEAD-TO-HEAD (H2H) HISTORY: Identify all previous meetings
        h2h_manifest = manifest_df[
            (manifest_df['Home'].str.contains(my_team, case=False) & manifest_df['Away'].str.contains(opponent, case=False)) |
            (manifest_df['Home'].str.contains(opponent, case=False) & manifest_df['Away'].str.contains(my_team, case=False))
        ].copy()
        
        h2h_wins, h2h_losses, h2h_ties = 0, 0, 0
        h2h_detailed_list = []
        
        for _, game in h2h_manifest.iterrows():
            scores = str(game['Score']).split('-')
            if len(scores) == 2:
                s1, s2 = int(scores[0].strip()), int(scores[1].strip())
                date_str = game.get('Date', 'Unknown Date')
                
                # Determine result from Shocker perspective
                is_home = my_team.lower() in game['Home'].lower()
                my_score = s1 if is_home else s2
                opp_score = s2 if is_home else s1
                
                if s1 == s2: h2h_ties += 1
                elif my_score > opp_score: h2h_wins += 1
                else: h2h_losses += 1
                
                h2h_detailed_list.append({"date": date_str, "score": game['Score'], "result": "W" if my_score > opp_score else "L"})

        # 4. PATTERN DATA: Grab recent play-by-play for trend analysis
        recent_pbp = details_df[
            (details_df['Team'].str.contains(f"{my_team}|{opponent}", case=False, na=False))
        ].tail(100).to_dict('records')

        return {
            "matchup": f"{my_team} vs {opponent}",
            "records": {"us": us_stats, "them": them_stats},
            "h2h": {"summary": f"{h2h_wins}-{h2h_losses}-{h2h_ties}", "history": h2h_detailed_list},
            "pim_intel": {"team_total": team_total_pim, "offenders": opp_pim_list},
            "opp_top_scorers": opp_players.sort_values(by='Pts', ascending=False).head(3).to_dict('records'),
            "raw_tape": recent_pbp
        }
    except Exception as e:
        print(f"❌ Data Extraction Error: {e}")
        return None

def generate_whatsapp_brief():
    my_team, opponent = "Shockers", "Flat-Earthers"
    data = get_scouting_data(my_team, opponent)
    if not data: return

    print(f"📡 Scouting the {opponent} for the boys...")
    
    # SYSTEM INSTRUCTION: Professional Data x Locker Room Grit
    system_instruction = f"""
    You are the Shockers Lead Scout using Gemini 2.5 Flash. 
    Target Audience: 20-35 year old men (WhatsApp Group).
    
    STRICT DATA RULES:
    1. H2H ACCURACY: We are 0-3 against them. Explicitly mention the Oct 6 (0-1), Nov 3 (3-6), and Dec 22 (2-3) losses.
    2. PIM INTEGRITY: If 'offenders' has data, use those numbers. Never report 0 PIMs if the data shows otherwise.
    3. THE PATTERN: Analyze 'raw_tape' and 'records'. If they are #3 but have a -7 Goal Differential, call them 'Frauds' and explain why (e.g., they get shelled but squeak out wins).
    
    FORMAT: 
    - 1. STANDINGS (Seed & Pts)
    - 2. RECORDS (Full season W-L-T)
    - 3. H2H BATTLE (Specific dates and scores)
    - 4. OPPONENT INTEL (Top 3 Pts & PIM Leader with exact PIM count)
    - 5. COMPELLING PATTERN (One high-value tactical insight)

    CONSTRAINT: Under 350 words. Pithy. No generic AI fluff.
    """

    prompt = f"DATA PACKAGE:\n{json.dumps(data)}\n\nTask: Generate the bare-bones WhatsApp scouting brief."

    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash", 
            contents=[system_instruction, prompt]
        )
        print("\n📱 COPY THIS INTO WHATSAPP:\n")
        print("═"*45)
        print(response.text)
        print("═"*45)
    except Exception as e:
        print(f"❌ Gemini API Error: {e}")

if __name__ == "__main__":
    generate_whatsapp_brief()