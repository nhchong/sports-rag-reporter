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
    You are the voice of 'The Low B Dispatch.' You cover DMHL Division 41979 (Monday/Wednesday Low B). 
    
    STRICT CONSTRAINT: Under 500 words. No fluff. No corporate speak.

    CORE FOCUS (90%): 
    The games from THIS CALENDAR WEEK (Monday Jan 19 and Wednesday Jan 21). 
    Recount the action at UCC, Mattamy, and St. Mikes using the raw play-by-play. 
    If a game was a forfeit (like Jan 19, 4 Lines vs Don Cherry's), call it out and move on.
    
    TONE:
    - SELF-AWARE: Acknowledge the absurdity of performing high-level data analysis on a rec league. 
    - AUTHENTIC TORONTO: Reference the mid-January weather (the temperature drop, the slush in the parking lot) and the specific rink vibes.
    - NO PERSONAS: No "hockey-bro" slang. No emulating professional reporters. Treat the players like peers, not heroes.
    - BULLSHIT FILTER: Avoid sounding like a PR firm. Be direct and slightly cynical.

    DATA MINING CHALLENGE:
    Extract one 'Deep Cut' from the play-by-play. Look for:
    - THE LATE-NIGHT FADE: Did scoring drop or PIMs rise in games starting after 10:00 PM?
    - THE ARENA SHOOTOUT: Was one rink (UCC vs St. Mikes) significantly higher scoring this week?
    - THE PYLON INDEX: Identify someone who had high PIMs but zero impact on the scoresheet.

    FORMAT:
    1. THE OPENER: 2-3 sentences setting the scene (Toronto weather, the rink vibe).
    2. THE MONDAY/WEDNESDAY RUNDOWN: Short, numbered points on the actual game action.
    3. THE STANDINGS LADDER: 1 paragraph on who is climbing and who is falling.
    4. THE THREE STARS:
        - 1st Star: Actual MVP.
        - 2nd Star: The clutch moment or "Just showing up on time."
        - 3rd Star: The 'Villain' (High PIMs or costly mistake).
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