import os
import sys
import json
import pandas as pd
from datetime import datetime
from google import genai
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# --- CONFIGURATION ---
TEAM_STATS_FILE = "data/team_stats.csv"
PLAYER_STATS_FILE = "data/player_stats.csv"
DETAILS_FILE = "data/game_details.csv"
MANIFEST_FILE = "data/games_manifest.csv"

# API Setup
api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
if not api_key:
    print("❌ Error: No API Key found in .env file.")
    sys.exit(1)

client = genai.Client(api_key=api_key)

def build_reporting_brief(days_back=10):
    """
    PM Decision: Tiered Data Ingestion.
    Filters raw logs into a structured 'Story Brief' for the LLM.
    """
    try:
        # 1. Macro Trends (The Season Narrative)
        standings = pd.read_csv(TEAM_STATS_FILE).to_dict(orient='records')
        leaders = pd.read_csv(PLAYER_STATS_FILE).head(15).to_dict(orient='records')
        
        # 2. Filter for Recency (The 'Current' Tape)
        details_df = pd.read_csv(DETAILS_FILE)
        details_df['ScrapedAt'] = pd.to_datetime(details_df['ScrapedAt'])
        
        # Ground the report in the most recent data point
        latest_data_date = details_df['ScrapedAt'].max()
        cutoff_date = latest_data_date - pd.Timedelta(days=days_back)
        
        recent_details = details_df[details_df['ScrapedAt'] >= cutoff_date].copy()
        recent_details['ScrapedAt'] = recent_details['ScrapedAt'].dt.strftime('%Y-%m-%d')
        
        # 3. Contextual Grounding (Schedule Manifest)
        manifest_df = pd.read_csv(MANIFEST_FILE)
        recent_game_ids = recent_details['GameID'].unique().astype(str)
        recent_manifest = manifest_df[manifest_df['GameID'].astype(str).isin(recent_game_ids)]

        # 4. Construct the JSON Brief
        brief = {
            "metadata": {
                "today_date": "January 14, 2026",
                "reporting_window": f"{cutoff_date.date()} to {latest_data_date.date()}",
                "league": "DMHL Division 533",
                "location": "Toronto, ON"
            },
            "season_snapshot": {
                "standings": standings,
                "scoring_leaders": leaders
            },
            "the_tape": {
                "recent_games_manifest": recent_manifest.to_dict(orient='records'),
                "play_by_play_logs": recent_details.to_dict(orient='records')
            }
        }
        return json.dumps(brief, indent=2)

    except Exception as e:
        print(f"❌ Error building JSON brief: {e}")
        return None

def generate_report():
    # Build the structured context
    json_brief = build_reporting_brief(days_back=10) 
    if not json_brief: return

    print("🎙️ Producing the 'DMHL Insider' (V3 Captivating Edition)...")
    
    # PM Decision: Narrative Logic Instruction Set
    system_instruction = """
    You are the lead columnist for the 'DMHL Insider'. Your brand is the 'Smart Insider'—someone who 
    knows the stats like a scout but talks like a teammate at the bar. 

    NARRATIVE STYLE:
    - 32 THOUGHTS: Use a numbered list. Lead several points with "I'm curious about..." or "I wonder if..." 
    - THE ATHLETIC: Analyze the data. If a team is leading the league but has a poor PK%, question their longevity.
    - SPITTING CHICLETS: Be direct and locker-room honest. If a team got blown out, say they "didn't get off the bus." 
    - NO FORCED SLANG: Do not force 'snipes' or 'sauce' unless it fits perfectly. Avoid cringey cliches.

    EDITORIAL FRAMEWORK:
    1. THE "WHY": Speculate on why trends are happening based on PIMs or GFA.
    2. THE STANDINGS LADDER: Mention how games affected the teams' 'Life in the Standings' (e.g., "Leapfrogging into 2nd").
    3. THE TORONTO VIBE: It's mid-January in Toronto. Ground the report in the winter atmosphere at St. Mikes or Mattamy.
    4. STRICT RECENCY: Only report on games in 'the_tape'. Use January context as 'NOW'.
    """

    prompt = f"""
    CONTEXT DATA (JSON):
    {json_brief}

    TASK:
    - Write a captivating weekly report.
    - Format: 
       * A sharp intro setting the January scene in Toronto.
       * 5-6 numbered 'Thoughts' on the recent games and season standings.
       * 'The PIM Tracker' (Who needs to stay out of the bin?)
       * 'The Star of the Week' (Cross-reference recent goals with the season leaders).
    """

    try:
        # Using 2.0 Flash for high-speed narrative generation
        response = client.models.generate_content(
            model="gemini-2.5-flash", 
            contents=[system_instruction, prompt]
        )
        report_text = response.text
        
        print("\n" + "═"*60)
        print(f"🏒  DMHL INSIDER REPORT | {datetime.now().strftime('%B %d, %Y')}  🏒")
        print("═"*60 + "\n")
        print(report_text)
        
        os.makedirs("data", exist_ok=True)
        with open("data/weekly_report.md", "w") as f:
            f.write(report_text)
        print(f"\n✅ Report saved to data/weekly_report.md")

    except Exception as e:
        print(f"❌ Gemini API Error: {e}")

if __name__ == "__main__":
    generate_report()