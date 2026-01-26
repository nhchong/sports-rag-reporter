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
DOCS_DIR = "docs"

# Initialize the Gemini 2.5 Flash client
api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
client = genai.Client(api_key=api_key)

def compile_weekly_data_package():
    """
    Constructs a comprehensive data package for the LLM by synthesizing 
    seasonal context with granular weekly event data.
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
        
        # Isolating events from the current production cycle
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
    Saves the output to the /docs folder for automated GitHub Pages hosting.
    """
    json_brief = compile_weekly_data_package() 
    if not json_brief: 
        return

    print("🎙️ Producing 'The Low B Dispatch' weekly digest...")
    
    # AI System Configuration: Professional Analysis x Locker Room Authenticity
    system_instruction = """
    You are the Senior Columnist for 'The Low B Dispatch,' a data-driven hockey newsletter. 
    
    VOICE & STYLE:
    - ANALYTICAL: Use data to substantiate claims. 
    - AUTHENTIC: Speak to the community as a peer (locker-room tone).
    - ZERO FLUFF: Avoid generic PR language.

    NARRATIVE STRATEGY:
    1. THE BIG STORY: Identify standings shifts.
    2. DATA-DRIVEN INSIGHTS: Highlight specific player discrepancies.
    3. THE OFFICIALS: Comment on officiating volume.
    4. VIBE & VENUE: Contextualize results based on arena/time.

    THE THREE STARS:
    Must be strictly based on weekly data.
    - 1st Star: MVP.
    - 2nd Star: Standout (Goalie/Defense).
    - 3rd Star: The 'Productive Agitator'.
    """

    prompt = f"DATA BRIEF:\n{json_brief}\n\nTask: Generate this week's newsletter dispatch."

    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash", 
            contents=[system_instruction, prompt]
        )
        report_text = response.text
        
        # --- PUBLIC ARCHIVING LOGIC (GitHub Pages) ---
        os.makedirs(DOCS_DIR, exist_ok=True)
        today = datetime.now()
        datestamp = today.strftime('%Y_%m_%d')
        filename = f"dispatch_{datestamp}.md"
        filepath = os.path.join(DOCS_DIR, filename)
        
        # 1. Save the specific report
        with open(filepath, "w") as f:
            f.write(report_text)
            
        # 2. Update the public Index page
        index_path = os.path.join(DOCS_DIR, "index.md")
        if not os.path.exists(index_path):
            with open(index_path, "w") as f:
                f.write("# 🗞️ The Low B Dispatch Archive\n\nWelcome to the official record of DMHL drama.\n")
        
        with open(index_path, "a") as f:
            f.write(f"\n* [{today.strftime('%B %d, %Y')} - Weekly Dispatch]({filename})")

        print(f"\n✅ Digest generated and archived: {filepath}")
        print(report_text)

    except Exception as e:
        print(f"❌ Gemini API Error: {e}")

if __name__ == "__main__":
    generate_weekly_digest_report()