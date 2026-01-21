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

def build_reporting_brief():
    """
    Aggregates full season stats and this week's specific tape for narrative contrast.
    """
    try:
        # 1. LOAD FULL SEASON DATA
        standings = pd.read_csv(TEAM_STATS_FILE).to_dict(orient='records')
        all_leaders = pd.read_csv(PLAYER_STATS_FILE).to_dict(orient='records')
        manifest_df = pd.read_csv(MANIFEST_FILE)
        details_df = pd.read_csv(DETAILS_FILE)
        
        details_df['ScrapedAt'] = pd.to_datetime(details_df['ScrapedAt'])
        
        # 2. ISOLATE THIS WEEK'S ACTION
        today = datetime.now()
        monday_of_this_week = today - pd.Timedelta(days=today.weekday())
        this_week_details = details_df[details_df['ScrapedAt'] >= monday_of_this_week.replace(hour=0, minute=0)].copy()
        
        # 3. MAPPING OFFICIALS
        officials = this_week_details[this_week_details['EventType'] == 'Official']
        ref_map = officials.groupby('GameID')['Description'].apply(list).to_dict()

        this_week_details['ScrapedAt'] = this_week_details['ScrapedAt'].dt.strftime('%Y-%m-%d')
        recent_game_ids = this_week_details['GameID'].unique().astype(str)
        recent_manifest = manifest_df[manifest_df['GameID'].astype(str).isin(recent_game_ids)]

        brief = {
            "league_meta": {
                "name": "Downtown Men's Hockey League (DMHL)",
                "division": "Monday/Wednesday Low B (Division 533)",
                "current_date": today.strftime('%B %d, %Y')
            },
            "season_stats": {
                "full_standings": standings,
                "league_wide_leaders": all_leaders
            },
            "this_week_tape": {
                "manifest": recent_manifest.to_dict(orient='records'),
                "play_by_play": this_week_details.to_dict(orient='records'),
                "referee_assignments": ref_map
            }
        }
        return json.dumps(brief, indent=2)
    except Exception as e:
        print(f"❌ Error: {e}")
        return None

def generate_report():
    json_brief = build_reporting_brief() 
    if not json_brief: return

    print("🎙️ Producing 'The Low B Dispatch'...")
    
    # SYSTEM INSTRUCTION: No cringe, high narrative, season-long trends.
    system_instruction = f"""
    You are the voice of 'The Low B Dispatch.' You cover DMHL Division 41979 (Monday/Wednesday Low B).
    Today is {datetime.now().strftime('%A, %B %d, %Y')}.

    EDITORIAL GUIDELINES:
    - NO CRINGE: Avoid forced "hockey-speak," over-the-top personas, or corporate AI polish. If it sounds like an automated email from a HR department or a "try-hard" influencer, delete it.
    - SEASONAL ARCH: Use the 'season_stats' to tell stories. Don't just report this week's scores; explain how these games fit into the larger story of the season. 
    - THE REALITY: Acknowledge the humor of professional-grade reporting for a 10:30 PM rec league start at UCC.

    NARRATIVE ANALYSIS (SEASON TRENDS):
    Look at the 'season_stats' vs 'this_week_tape' to find:
    1. THE HEATING UP/COOLING DOWN: Identify a team or player whose performance this week drastically differs from their season average.
    2. THE GATEKEEPERS: Which teams are consistent bullies, and which ones are perpetual underdogs?
    3. THE DISCIPLINE TRACKER: Are certain teams getting more frustrated as the season goes on? (Look for PIM trends).
    4. ARENA IDENTITY: Do teams play differently at Mattamy vs St. Mikes?

    CONSTRAINTS:
    - Length: Under 500 words.
    - Focus: 90% on this Monday/Wednesday action, but viewed through the lens of the full season.
    - Formatting: Clean Markdown (H1, H2, Bold, Tables).

    FORMAT:
    - # TITLE: Direct and relevant.
    - ## THE RUNDOWN: Summary of Monday/Wednesday action.
    - ## SEASONAL TRENDS: What the data tells us about where the league is heading.
    - ## THE THREE STARS: 
        - **1st Star**: MVP of the week.
        - **2nd Star**: Impact player/Season-long consistency.
        - **3rd Star**: The Villain (High PIMs/Season-long liability).
    """

    prompt = f"DATA BRIEF:\n{json_brief}\n\nTask: Generate the Markdown report."

    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash", 
            contents=[system_instruction, prompt]
        )
        report_text = response.text
        
        print(f"\n✅ Report generated.\n")
        print(report_text)
        
        os.makedirs("data", exist_ok=True)
        with open("data/weekly_report.md", "w") as f:
            f.write(report_text)

    except Exception as e:
        print(f"❌ Gemini API Error: {e}")

if __name__ == "__main__":
    generate_report()