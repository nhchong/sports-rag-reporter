import os
import json
import re
import pandas as pd
from datetime import datetime
from google import genai
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# --- FILE PATH CONFIGURATION ---
DETAILS_FILE = "data/game_details.csv"
TEAM_STATS_FILE = "data/team_stats.csv"
PLAYER_STATS_FILE = "data/player_stats.csv"
MANIFEST_FILE = "data/games_manifest.csv"

# Initialize the Gemini 2.5 Flash client
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

def normalize_team_name(text):
    """
    Standardizes team names to ensure reliable data matching across disparate sources.
    
    Performs the following:
    - Converts to lowercase.
    - Removes the leading 'The' (case-insensitive).
    - Replaces hyphens with spaces.
    - Strips redundant whitespace.
    """
    if not isinstance(text, str): 
        return ""
    text = text.lower().replace("-", " ")
    text = re.sub(r'\bthe\b', '', text)
    return " ".join(text.split()).strip()

def fetch_matchup_context(my_team_raw, opponent_raw):
    """
    Aggregates historical and seasonal data for a specific team matchup.
    
    Mines CSV data sources to compile:
    1. Head-to-Head (H2H) results with column-shift detection.
    2. Opponent player metrics (Points and Penalty Minutes).
    3. League standings and goal differentials.
    4. Recent play-by-play logs for pattern analysis.
    """
    try:
        details_df = pd.read_csv(DETAILS_FILE)
        team_stats = pd.read_csv(TEAM_STATS_FILE)
        player_stats = pd.read_csv(PLAYER_STATS_FILE)
        manifest_df = pd.read_csv(MANIFEST_FILE)

        my_norm = normalize_team_name(my_team_raw)
        opp_norm = normalize_team_name(opponent_raw)

        # 1. HEAD-TO-HEAD HISTORY
        # Filters manifest for games involving both teams, regardless of Home/Away status.
        h2h_manifest = manifest_df[
            (manifest_df['Home'].apply(normalize_team_name).str.contains(my_norm, na=False) & 
             manifest_df['Away'].apply(normalize_team_name).str.contains(opp_norm, na=False)) |
            (manifest_df['Home'].apply(normalize_team_name).str.contains(opp_norm, na=False) & 
             manifest_df['Away'].apply(normalize_team_name).str.contains(my_norm, na=False))
        ].copy()
        
        h2h_wins, h2h_losses, h2h_ties = 0, 0, 0
        h2h_history_list = []
        
        for _, game in h2h_manifest.iterrows():
            # Data Integrity Check: If 'Score' contains division info, scores are in 'Status'.
            score_raw = str(game['Status']) if '-' in str(game['Status']) else str(game['Score'])
            scores = score_raw.split('-')
            
            if len(scores) == 2:
                s1, s2 = int(scores[0].strip()), int(scores[1].strip())
                is_home = my_norm in normalize_team_name(game['Home'])
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

        # 2. INDIVIDUAL PLAYER METRICS
        opp_players = player_stats[player_stats['Team'].str.contains(opponent_raw, case=False, na=False)].copy()
        if 'Pts' not in opp_players.columns: 
            opp_players['Pts'] = opp_players['G'] + opp_players['A']
        
        pim_intel = {
            "team_total": int(opp_players['PIM'].sum()),
            "offenders": opp_players.sort_values(by='PIM', ascending=False).head(3)[['Player', 'PIM', 'Pts']].to_dict('records')
        }

        # 3. SEASONAL STANDINGS
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
        print(f"❌ Error during data aggregation: {e}")
        return None

def generate_matchup_briefing():
    """
    Orchestrates the data retrieval and LLM generation for a matchup summary.
    """
    my_team, opponent = "Shockers", "Flat-Earthers"
    data = fetch_matchup_context(my_team, opponent)
    if not data: 
        return

    # Configuration for the AI's persona and objective
    system_instruction = f"""
    You are a Senior Sports Analyst specializing in hockey data. 
    Task: Produce a data-driven briefing for the {my_team} ahead of their matchup with the {opponent}.
    
    VOICE: High-quality professional reporting (e.g., The Athletic) mixed with authentic, direct perspectives. 
    Target Demographic: Men aged 20-35. Avoid corporate clichés and AI-generated fluff.
    
    STRICT DATA RELIANCE:
    - H2H History: We are 0-3 against them. Explicitly cite Dec 22 (2-3), Nov 3 (3-6), and Oct 6 (0-1).
    - Statistical Patterns: Analyze Goal Differentials. Highlight if a high-seeded team has a negative differential (potential overperformance).
    
    FORMAT: 
    1. STANDINGS (Rank & Points)
    2. SEASON RECORDS (W-L-T)
    3. HEAD-TO-HEAD BATTLE (Historical dates and scores)
    4. OPPONENT INTEL (Top Scorers & Penalty Leaders. Use jersey numbers on first mention.)
    5. NOTABLE STORY (One high-value tactical insight found in the data)

    STRICT CONSTRAINT: Keep the output under 300 words. Pithy and direct.
    """

    prompt = f"MATCHUP DATA PACKAGE:\n{json.dumps(data)}\n\nTask: Generate the pre-game briefing." 

    try:
        # Request generation from Gemini 2.5 Flash
        response = client.models.generate_content(
            model="gemini-2.5-flash", 
            contents=[system_instruction, prompt]
        )
        print("\n🏒 PRE-GAME BRIEFING:\n")
        print("═"*45 + "\n" + response.text + "\n" + "═"*45)
    except Exception as e:
        print(f"❌ Gemini API Error: {e}")

if __name__ == "__main__":
    generate_matchup_briefing()