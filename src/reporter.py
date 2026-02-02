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
POSTS_DIR = os.path.join(DOCS_DIR, "_posts")

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

    THE THREE STARS:
    Must be strictly based on weekly data.
    - 1st Star: MVP.
    - 2nd Star: Standout (Goalie/Defense).
    - 3rd Star: The 'Productive Agitator' who contributes on the scoresheet and as a team contirbuter. 
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
        os.makedirs(POSTS_DIR, exist_ok=True)
        today = datetime.now()
        datestamp = today.strftime('%Y-%m-%d')
        filename = f"{datestamp}-dispatch.md"
        filepath = os.path.join(POSTS_DIR, filename)
        
        # Format date for front matter title
        formatted_date = today.strftime('%B %d, %Y')
        
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
        
        # Save the report with front matter
        with open(filepath, "w") as f:
            f.write(front_matter)
            f.write(report_text)

        print(f"\n✅ Digest generated and archived: {filepath}")
        print(report_text)

    except Exception as e:
        print(f"❌ Gemini API Error: {e}")

if __name__ == "__main__":
    generate_weekly_digest_report()