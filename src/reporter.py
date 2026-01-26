import os
import sys
import json
import pandas as pd
from datetime import datetime
from google import genai
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# --- FILE PATH CONFIGURATION ---
TEAM_STATS_FILE = "data/team_stats.csv"
PLAYER_STATS_FILE = "data/player_stats.csv"
DETAILS_FILE = "data/game_details.csv"
MANIFEST_FILE = "data/games_manifest.csv"

# Initialize the Gemini 2.5 Flash client
api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
client = genai.Client(api_key=api_key)

def compile_weekly_data_package():
    """
    Constructs a comprehensive data package for the LLM by synthesizing 
    seasonal context with granular weekly event data.
    
    The package includes:
    - Seasonal standings and individual player metrics.
    - Filtered play-by-play data for the current calendar week.
    - Official assignments mapped to specific Game IDs.
    - Geographic context (arenas and schedules).
    """
    try:
        # 1. Load Seasonal Context
        standings = pd.read_csv(TEAM_STATS_FILE).to_dict(orient='records')
        player_stats = pd.read_csv(PLAYER_STATS_FILE).to_dict(orient='records')
        
        # 2. Load and Filter Weekly Evidence
        details_df = pd.read_csv(DETAILS_FILE)
        manifest_df = pd.read_csv(MANIFEST_FILE)
        
        details_df['ScrapedAt'] = pd.to_datetime(details_df['ScrapedAt'])
        today = datetime.now()
        monday_of_this_week = today - pd.Timedelta(days=today.weekday())
        
        # Isolating events from the current production cycle (Mon/Wed/Fri action)
        this_week_details = details_df[
            details_df['ScrapedAt'] >= monday_of_this_week.replace(hour=0, minute=0)
        ].copy()
        
        # 3. Map Official Assignments
        officials = this_week_details[this_week_details['EventType'] == 'Official']
        ref_map = officials.groupby('GameID')['Description'].apply(list).to_dict()

        # Format timestamps for JSON serialization
        this_week_details['ScrapedAt'] = this_week_details['ScrapedAt'].dt.strftime('%Y-%m-%d')
        recent_game_ids = this_week_details['GameID'].unique().astype(str)
        recent_manifest = manifest_df[manifest_df['GameID'].astype(str).isin(recent_game_ids)]

        # Construct final high-fidelity brief
        brief = {
            "data_sources": {
                "league_standings": standings,
                "individual_leaders": player_stats,
                "weekly_play_by_play": this_week_details.to_dict(orient='records'),
                "schedule_and_arenas": recent_manifest.to_dict(orient='records'),
                "official_assignments": ref_map
            },
            "report_metadata": {
                "current_date": today.strftime('%B %d, %Y'),
                "target_audience": "Toronto-based adult hockey players (20-35)"
            }
        }
        return json.dumps(brief, indent=2)
    except Exception as e:
        print(f"❌ Error compiling weekly data package: {e}")
        return None

def generate_weekly_digest_report():
    """
    Orchestrates the LLM generation to produce 'The Low B Dispatch' weekly column.
    
    Integrates professional data-driven analysis with an authentic, 
    community-focused narrative voice.
    """
    json_brief = compile_weekly_data_package() 
    if not json_brief: 
        return

    print("🎙️ Producing 'The Low B Dispatch' weekly digest...")
    
    # AI System Configuration: Professional Analysis x Locker Room Authenticity
    system_instruction = f"""
    You are the Senior Columnist for 'The Low B Dispatch,' a data-driven hockey newsletter. 
    
    VOICE & STYLE:
    - ANALYTICAL: Use 'individual_leaders' and 'weekly_play_by_play' to substantiate claims. 
    - AUTHENTIC: Speak to the community as a peer. Use direct language and call out poor 
      performances or unusual game circumstances (e.g., late starts, officiating).
    - ZERO FLUFF: Avoid generic PR language.

    NARRATIVE STRATEGY:
    1. THE BIG STORY: Identify shifts in league standings or emerging dark horses.
    2. DATA-DRIVEN INSIGHTS: Highlight specific player discrepancies (e.g., scoring vs. PIMs).
    3. THE OFFICIALS: Comment on officiating trends if supported by penalty volume.
    4. VIBE & VENUE: Contextualize results based on arena and scheduling.

    THE THREE STARS:
    Must be strictly based on weekly data.
    - 1st Star: Undeniable MVP.
    - 2nd Star: Standout performance (Goalie clinic, scoring milestone, etc).
    - 3rd Star: The 'Productive Agitator'—someone who impacted the game physically and statistically.

    CONSTRAINTS:
    - Markdown formatting required.
    - Professional yet direct tone.
    - Length: Pithy and insightful.
    """

    prompt = f"DATA BRIEF:\n{json_brief}\n\nTask: Generate this week's newsletter dispatch."

    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash", 
            contents=[system_instruction, prompt]
        )
        report_text = response.text
        
        print(f"\n✅ Digest generated successfully.\n")
        print(report_text)
        
        # Save output to Markdown for archive/GitHub publishing
        os.makedirs("data", exist_ok=True)
        with open("data/weekly_report.md", "w") as f:
            f.write(report_text)

    except Exception as e:
        print(f"❌ Gemini API Error: {e}")

if __name__ == "__main__":
    generate_weekly_digest_report()