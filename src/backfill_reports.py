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

# Re-directing to the _posts folder for the new Athletic-style layout
POSTS_DIR = "docs/_posts"

# Automating the last 10 Thursdays ending Feb 2, 2026 (or adjusted for Jan 29)
def generate_last_ten_thursdays():
    end_date = datetime(2026, 1, 29) # The most recent reporting Thursday
    thursdays = []
    for i in range(10):
        target = end_date - timedelta(weeks=i)
        thursdays.append(target.strftime('%Y-%m-%d'))
    return thursdays

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

        # Handle DMHL year-less dates (Nov/Dec = 2025, Jan = 2026)
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

        # Final serialization cleanup
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
    print(f"🚀 Starting Athletic-Style Backfill: {len(BACKFILL_DATES)} Reports...")
    os.makedirs(POSTS_DIR, exist_ok=True)

    system_instruction = """
    You are the Senior Columnist for 'The Low B Dispatch.' 
    
    VOICE & INSPIRATION:
    - THE ATHLETIC: Data-driven and analytical.
    - SPITTIN' CHICLETS: Candid, peer-to-peer locker-room perspective.
    - MATURE WIT: No 'hockey bro' lingo. Use sharp, sophisticated humor and wit. 

    EDITORIAL STRATEGY (80/20 Rule):
    - 80% COVERAGE: Focus on the specific games from 'weekly_play_by_play'. 
    - 20% CONTEXT: Ground results in standings and leaders.

    STRUCTURE:
    - WORD LIMIT: Approximately 600 words.
    - MANDATORY: Conclude with 'The Three Stars of the Week'.
    
    FORMATTING: Use Markdown (## Headings). Use > blockquotes for specific data callouts.
    """

    for date_str in BACKFILL_DATES:
        target_date = datetime.strptime(date_str, '%Y-%m-%d')
        json_brief = get_historical_brief(target_date)

        if not json_brief:
            continue

        print(f"🎙️ Generating Dispatch for {date_str}...")

        try:
            # Using Gemini 2.0-flash as it is more stable for back-to-back requests
            response = client.models.generate_content(
                model="gemini-2.0-flash", 
                contents=[system_instruction, f"DATA BRIEF:\n{json_brief}"]
            )
            
            # JEKYLL FILENAME CONVENTION: YYYY-MM-DD-title.md
            filename = f"{date_str}-dispatch.md"
            filepath = os.path.join(POSTS_DIR, filename)
            
            # JEKYLL FRONT MATTER: Required for 'The Athletic' layout
            front_matter = f"""---
layout: single
title: "Weekly Dispatch: {target_date.strftime('%B %d, %Y')}"
date: {date_str}
excerpt: "A deep dive into the DMHL action for the week of {target_date.strftime('%b %d')}. Data, drama, and the Three Stars."
author_profile: true
---

"""
            
            with open(filepath, "w") as f:
                f.write(front_matter + response.text)

            print(f"✅ Created: {filename}")
            
            # PAUSE: Reset the Token bucket and Request count
            time.sleep(15)

        except Exception as e:
            print(f"❌ Error during AI generation for {date_str}: {e}")
            time.sleep(30)

    print("\n🏁 Archive generation complete. Run git commands to push to GitHub.")

if __name__ == "__main__":
    run_backfill()