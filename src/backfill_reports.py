import os
import json
import time
import pandas as pd
from datetime import datetime, timedelta
from google import genai
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# --- CONFIGURATION ---
DETAILS_FILE = "data/game_details.csv"
TEAM_STATS_FILE = "data/team_stats.csv"
PLAYER_STATS_FILE = "data/player_stats.csv"
MANIFEST_FILE = "data/games_manifest.csv"
DOCS_DIR = "docs"
POSTS_DIR = os.path.join(DOCS_DIR, "_posts")

# Automating exactly the last 10 Thursdays ending Jan 29, 2026
def generate_last_ten_thursdays():
    end_date = datetime(2026, 1, 29)
    thursdays = []
    for i in range(10):
        target = end_date - timedelta(weeks=i)
        thursdays.append(target.strftime('%Y-%m-%d'))
    return thursdays # Already newest first

BACKFILL_DATES = generate_last_ten_thursdays()

# Initialize Gemini Client
api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
client = genai.Client(api_key=api_key)

def get_historical_brief(target_date):
    """
    Constructs the week-specific data packet for the AI.
    """
    try:
        manifest_df = pd.read_csv(MANIFEST_FILE)
        details_df = pd.read_csv(DETAILS_FILE)
        standings = pd.read_csv(TEAM_STATS_FILE)
        player_stats = pd.read_csv(PLAYER_STATS_FILE)

        # Handle DMHL year-less dates for Fall/Winter
        manifest_df['DateClean'] = manifest_df['Date'].apply(
            lambda x: f"{str(x)}, 2025" if any(mo in str(x) for mo in ["Nov", "Dec"]) else f"{str(x)}, 2026"
        )
        manifest_df['ParsedDate'] = pd.to_datetime(manifest_df['DateClean'], format='mixed')
        
        monday_of_week = target_date - timedelta(days=target_date.weekday())
        weekly_manifest = manifest_df[
            (manifest_df['ParsedDate'] >= monday_of_week) & 
            (manifest_df['ParsedDate'] <= target_date)
        ].copy()

        if weekly_manifest.empty:
            return None

        recent_game_ids = weekly_manifest['GameID'].unique().astype(str)
        this_week_details = details_df[details_df['GameID'].astype(str).isin(recent_game_ids)].copy()

        if this_week_details.empty:
            return None

        officials = this_week_details[this_week_details['EventType'] == 'Official']
        ref_map = officials.groupby('GameID')['Description'].apply(list).to_dict()

        # Serialization safety
        weekly_manifest['ParsedDate'] = weekly_manifest['ParsedDate'].dt.strftime('%Y-%m-%d')
        
        brief = {
            "data_sources": {
                "league_standings": standings.to_dict(orient='records'),
                "individual_leaders": player_stats.to_dict(orient='records'),
                "weekly_play_by_play": this_week_details.to_dict(orient='records'),
                "schedule_and_arenas": weekly_manifest.to_dict(orient='records'),
                "official_assignments": ref_map
            },
            "report_metadata": {
                "current_date": target_date.strftime('%B %d, %Y'),
                "target_audience": "Mature, 25-35 year old Toronto hockey players"
            }
        }
        
        return json.dumps(brief, indent=2, default=str)
    except Exception as e:
        print(f"❌ Error building brief for {target_date}: {e}")
        return None

def run_backfill():
    print(f"🚀 Starting 10-Week Backfill: {BACKFILL_DATES[-1]} to {BACKFILL_DATES[0]}...")
    os.makedirs(DOCS_DIR, exist_ok=True)
    os.makedirs(POSTS_DIR, exist_ok=True)

    system_instruction = """
    You are the Senior Columnist for 'The Low B Dispatch,' a data-driven hockey newsletter. You cover the DMHL, which stands for the Downtown Mens Hockey League. The league is based in Toronto. Most of the players are between the ages of 25 and 35. Games are played on Monday and Wednesday. The division that you are covering is Monday/Wednesday Low B. 
    
    VOICE & STYLE:
    - ANALYTICAL: Use data to substantiate claims. 
    - AUTHENTIC: Speak to the community as a peer but avois any unprofessional locker-room tone.
    - ZERO FLUFF: Avoid generic PR language.
    - COMPELLING NARRATIVE: Similar to the media outlet, The Atheltic
    - LIGHT-HEARTED BUT PROFESSIONAL: Similar the Spittin Chiclets podcast. 
    - MATURE WIT: No 'hockey bro' lingo. Use sharp, sophisticated humor. 

    NARRATIVE STRATEGY:
    1. THE BIG STORY: Identify standings shifts.
    2. DATA-DRIVEN INSIGHTS: Highlight specific player discrepancies.
    3. THE OFFICIALS: Comment on officiating volume and whether or not it impacted the game. 
    4. VIBE & VENUE: Contextualize results based on arena/time. 
    5. 80/20 Rule: 80% COVERAGE is Focused on the 'weekly_play_by_play' events and 20% CONTEXT: Ground results in standings and leaders.
    6. Make sure to weave in a summary of every game that happened this week. Every team has to be mentioned. 

    STRUCTURE & LENGTH:
    - WORD LIMIT: Approximately 250 words.
    - FORMAT: Header, H1, H2

    THE THREE STARS:
    Must be strictly based on weekly data.
    - 1st Star: MVP.
    - 2nd Star: Standout (Goalie/Defense).
    - 3rd Star: The 'Productive Agitator' who contributes on the scoresheet and as a team contirbuter. 
    """

    # Index.md is now handled by Jekyll's home layout - no manual table needed

    for date_str in BACKFILL_DATES:
        target_date = datetime.strptime(date_str, '%Y-%m-%d')
        json_brief = get_historical_brief(target_date)

        if not json_brief:
            continue

        print(f"🎙️ Generating Dispatch for {date_str}...")

        try:
            response = client.models.generate_content(
                model="gemini-2.5-flash", 
                contents=[system_instruction, f"DATA BRIEF:\n{json_brief}"]
            )
            
            # Jekyll post naming convention: YYYY-MM-DD-dispatch.md
            filename = f"{date_str}-dispatch.md"
            filepath = os.path.join(POSTS_DIR, filename)
            
            # Format date for front matter title
            formatted_date = target_date.strftime('%B %d, %Y')
            
            # Jekyll Front Matter
            front_matter = f"""---
layout: single
title: 'Weekly Dispatch: {formatted_date}'
excerpt: 'Data-driven analysis of the DMHL.'
author_profile: true
sidebar:
  nav: "docs"
---

"""
            
            with open(filepath, "w") as f:
                f.write(front_matter)
                f.write(response.text)

            print(f"✅ Created: {filename}")
            
            # --- API BREATHE TIMER ---
            # Wait 15 seconds between reports to stay under the 20-request-per-day burst limit
            time.sleep(15)

        except Exception as e:
            print(f"❌ Error during AI generation for {date_str}: {e}")
            time.sleep(20)

    print("\n🏁 10-week archive complete. Push to GitHub to go live!")

if __name__ == "__main__":
    run_backfill()