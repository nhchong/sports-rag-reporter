import os
import sys
import json
import pandas as pd
from datetime import datetime
from google import genai
from dotenv import load_dotenv

load_dotenv()

# --- CONFIGURATION ---
TEAM_STATS_FILE = "data/team_stats.csv"
PLAYER_STATS_FILE = "data/player_stats.csv"
DETAILS_FILE = "data/game_details.csv"
MANIFEST_FILE = "data/games_manifest.csv"

api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
client = genai.Client(api_key=api_key)

def build_reporting_brief(days_back=7):
    """
    PM Decision: Contextual Intelligence.
    Aggregates the weekly 'tape' with discretionary official metadata.
    """
    try:
        standings = pd.read_csv(TEAM_STATS_FILE).to_dict(orient='records')
        leaders = pd.read_csv(PLAYER_STATS_FILE).head(15).to_dict(orient='records')
        
        details_df = pd.read_csv(DETAILS_FILE)
        details_df['ScrapedAt'] = pd.to_datetime(details_df['ScrapedAt'])
        
        latest_data_date = details_df['ScrapedAt'].max()
        cutoff_date = latest_data_date - pd.Timedelta(days=days_back)
        
        recent_details = details_df[details_df['ScrapedAt'] >= cutoff_date].copy()
        
        # Capture officials for discretionary use
        officials = recent_details[recent_details['EventType'] == 'OfficialAssignment']
        ref_map = officials.groupby('GameID')['Description'].apply(list).to_dict()

        recent_details['ScrapedAt'] = recent_details['ScrapedAt'].dt.strftime('%Y-%m-%d')
        
        manifest_df = pd.read_csv(MANIFEST_FILE)
        recent_game_ids = recent_details['GameID'].unique().astype(str)
        recent_manifest = manifest_df[manifest_df['GameID'].astype(str).isin(recent_game_ids)]

        brief = {
            "league_meta": {
                "name": "Downtown Men's Hockey League (DMHL)",
                "division": "Monday/Wednesday Low B (Division 533)",
                "context": "Non-contact, ages 22-35, Toronto-based competitive rec league.",
                "arenas": ["Upper Canada College (UCC)", "Mattamy Athletic Centre", "St. Michael's Arena"],
                "report_date": "January 15, 2026"
            },
            "season_snapshot": {
                "standings": standings,
                "overall_leaderboard": leaders
            },
            "this_week_tape": {
                "manifest": recent_manifest.to_dict(orient='records'),
                "play_by_play": recent_details.to_dict(orient='records'),
                "referee_assignments": ref_map
            }
        }
        return json.dumps(brief, indent=2)
    except Exception as e:
        print(f"❌ Error building brief: {e}")
        return None

def generate_report():
    json_brief = build_reporting_brief(days_back=7) 
    if not json_brief: return

    print("🎙️ Producing 'The Low B Dispatch'...")
    
    # PM Decision: Narrative Persona Synthesis
    system_instruction = """
    You are the lead columnist for 'The Low B Dispatch,' the definitive source for DMHL Division 533. 
    Your audience is Toronto-based hockey players aged 22-35.

    EDITORIAL PERSONA:
    - 32 THOUGHTS: Lead with numbered points. Use the 'insider' structure (e.g., 'I'm hearing...', 'I wonder if...').
    - THE ATHLETIC: Use the data (PP%, standings movement, GFA) to ground your analysis.
    - SPITTIN' CHICLETS: Infuse the casual, locker-room energy of the podcast. Be direct, blunt, and authentic. Treat the players like peers, not professionals. Chirp a 'donkey' performance if the data shows a high PIM count led to a loss, but keep it grounded in rec-league reality.

    NARRATIVE RULES:
    1. THIS WEEK'S GAMES: Focus 90% on 'this_week_tape'. Recount the action at UCC, Mattamy, and St. Mikes.
    2. DISCRETIONARY REFS: Mention the referees (from 'referee_assignments') ONLY if it impacts the story (e.g., a tight-whistle game vs. letting them play).
    3. STANDINGS IMPACT: Weave how this week's results shifted the 'Standings Ladder.'
    4. NO FORCED SLANG: Don't use 'hockey-speak' just to use it. Use it naturally.

    FORMAT:
    - INTRO: Set the scene (mid-January winter in Toronto).
    - THE RUNDOWN: 5-6 numbered points on the week's matchups.
    - LEADERBOARD WATCH: Highlights from the season stat leaders.
    - THE THREE STARS:
        - 1st Star: The week's standout MVP.
        - 2nd Star: A clutch goal or massive goaltending performance.
        - 3rd Star: The 'Unsung Hero' or depth contributor.
    """

    prompt = f"DATA BRIEF:\n{json_brief}\n\nTask: Generate this week's edition of The Low B Dispatch."

    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash", 
            contents=[system_instruction, prompt]
        )
        report_text = response.text
        
        print("\n" + "═"*60)
        print(f"🏒  THE LOW B DISPATCH | {datetime.now().strftime('%B %d, %Y')}  🏒")
        print("═"*60 + "\n")
        print(report_text)
        
        with open("data/weekly_report.md", "w") as f:
            f.write(report_text)
        print(f"\n✅ Report saved to data/weekly_report.md")

    except Exception as e:
        print(f"❌ Gemini API Error: {e}")

if __name__ == "__main__":
    generate_report()