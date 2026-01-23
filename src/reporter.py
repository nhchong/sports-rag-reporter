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
    Constructs a high-fidelity data package for the LLM.
    Labels data sources clearly to enable cross-referencing.
    """
    try:
        # 1. Seasonal Context (The Athletic style grounding)
        standings = pd.read_csv(TEAM_STATS_FILE).to_dict(orient='records')
        player_stats = pd.read_csv(PLAYER_STATS_FILE).to_dict(orient='records')
        
        # 2. Weekly Evidence (The Tape)
        details_df = pd.read_csv(DETAILS_FILE)
        manifest_df = pd.read_csv(MANIFEST_FILE)
        
        details_df['ScrapedAt'] = pd.to_datetime(details_df['ScrapedAt'])
        today = datetime.now()
        monday_of_this_week = today - pd.Timedelta(days=today.weekday())
        
        # Filter for current Monday/Wednesday action
        this_week_details = details_df[details_df['ScrapedAt'] >= monday_of_this_week.replace(hour=0, minute=0)].copy()
        
        # Mapping Officials specifically for the current games
        officials = this_week_details[this_week_details['EventType'] == 'Official']
        ref_map = officials.groupby('GameID')['Description'].apply(list).to_dict()

        this_week_details['ScrapedAt'] = this_week_details['ScrapedAt'].dt.strftime('%Y-%m-%d')
        recent_game_ids = this_week_details['GameID'].unique().astype(str)
        recent_manifest = manifest_df[manifest_df['GameID'].astype(str).isin(recent_game_ids)]

        brief = {
            "data_sources": {
                "league_standings": standings, # Context: Who is a powerhouse vs a cellar dweller
                "individual_leaders": player_stats, # Context: Who are the elite threats and PIM kings
                "weekly_play_by_play": this_week_details.to_dict(orient='records'), # The evidence: Goals, PIMs, Timing
                "schedule_and_arenas": recent_manifest.to_dict(orient='records'), # The geography: Location and game times
                "official_assignments": ref_map # The human element: Who was wearing the stripes
            },
            "report_metadata": {
                "current_date": today.strftime('%B %d, %Y'),
                "target_audience": "20-35 year old Toronto-based hockey players"
            }
        }
        return json.dumps(brief, indent=2)
    except Exception as e:
        print(f"❌ Error building brief: {e}")
        return None

def generate_report():
    json_brief = build_reporting_brief() 
    if not json_brief: return

    print("🎙️ Producing 'The Low B Dispatch'...")
    
    # SYSTEM INSTRUCTION: The Athletic (Data) x Spittin' Chiclets (Voice)
    system_instruction = f"""
    You are the Senior Columnist for 'The Low B Dispatch.' 
    
    VOICE INSPIRATION:
    - THE ATHLETIC: You are data-driven. You don't just say someone played well; you use 'individual_leaders' and 'weekly_play_by_play' to prove it. You identify seasonal trends (e.g., scoring droughts, special teams surges).
    - SPITTIN' CHICLETS: You are a locker-room insider. You talk to your audience (20-35 year old men) like peers. You aren't afraid to chirp a 'donkey' performance or call out a team that clearly spent too much time at the bar before a 10:30 PM puck drop. Use raw, authentic language—no corporate AI fluff.

    NARRATIVE STRATEGY:
    1. THE BIG STORY: Look at 'league_standings'. Is the top team slipping? Is there a dark horse rising? Tie this week's games into this season-long arc.
    2. DATA-DRIVEN CHIRPS: Use the 'weekly_play_by_play'. If a league leader ('individual_leaders') went scoreless while taking 6 minutes in penalties, that is your lead story. 
    3. THE HUMAN ELEMENT (THE STRIPES): Cross-reference 'official_assignments' with penalty counts. If a certain ref duo called 12 penalties in a 30-minute game, call out the 'tight whistle' and how it killed the game's flow.
    4. GEOGRAPHY & VIBE: Extract the arenas and game times from 'schedule_and_arenas'. Acknowledge the vibe of a late-night start at UCC vs. a prime-time slot at Mattamy. Mention the Toronto weather ONLY if it adds to the 'grind' of the night.

    THE THREE STARS (Performance-Based):
    Strictly earned through data.
    - **1st Star**: The undeniable MVP. Use stats to justify this.
    - **2nd Star**: A standout performance (e.g., a goalie clinic or a defenseman hitting a scoring milestone).
    - **3rd Star**: The 'Productive Agitator'—someone who played a heavy game, maybe took a seat in the box, but moved the needle for their team.

    CONSTRAINTS:
    - NO BULLSHIT: Avoid phrases like 'thrilling matchup' or 'testament to their skill.' 
    - No references to specific division numbers unless found in the data.
    - Length: Pithy. Professional. Funny.
    - Format: Markdown (H1, H2, Bold).
    """

    prompt = f"DATA BRIEF:\n{json_brief}\n\nTask: Generate this week's Dispatch."

    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash", 
            contents=[system_instruction, prompt]
        )
        report_text = response.text
        
        print(f"\n✅ Dispatch Ready.\n")
        print(report_text)
        
        os.makedirs("data", exist_ok=True)
        with open("data/weekly_report.md", "w") as f:
            f.write(report_text)

    except Exception as e:
        print(f"❌ Gemini API Error: {e}")

if __name__ == "__main__":
    generate_report()