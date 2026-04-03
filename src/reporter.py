"""
Automated Sports Reporting Pipeline

This module acts as an autonomous data journalism engine. It ingests raw CSV telemetry 
from a hockey league, establishes a chronological reporting window, determines the seasonal 
context (Regular Season, Playoffs, or Finals), and leverages an LLM to generate a 
Markdown-formatted newsletter complete with Jekyll front-matter.
"""

import os
import sys
import json
import warnings
import pandas as pd
import re
from typing import Tuple, Optional
from datetime import datetime, timedelta
from google import genai
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# --- CONFIGURATION & CONSTANTS ---
TEAM_STATS_FILE = "data/team_stats.csv"
PLAYER_STATS_FILE = "data/player_stats.csv"
DETAILS_FILE = "data/game_details.csv"
MANIFEST_FILE = "data/games_manifest.csv"
PLAYOFF_STATS_FILE = "data/playoff_standings.csv" 
PLAYOFF_MATCHUP_FILE = "data/playoff_matchups.csv" 

DOCS_DIR = "docs"
POSTS_DIR = os.path.join(DOCS_DIR, "_posts")

# Asset mapping for dynamically injecting team logos into the Jekyll front-matter
LOGO_MAP = {
    "The Shockers": "/assets/images/theshockers.png",
    "The Sahara": "/assets/images/thesahara.png",
    "Don Cherry's": "/assets/images/doncherrys.png",
    "Flat-Earthers": "/assets/images/flatearthers.png",
    "Muffin Men": "/assets/images/muffinmen.png",
    "4 Lines": "/assets/images/4lines.png"
}

# Initialize LLM Client
api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
client = genai.Client(api_key=api_key)


def compile_weekly_data_package(target_date_str: Optional[str] = None) -> Tuple[Optional[str], bool, bool]:
    """
    Ingests and structures the raw CSV data into a comprehensive JSON context payload for the LLM.
    
    This function utilizes dynamic temporal resolution. If a target date is provided, it retrieves 
    data specifically for the 7 days leading up to that date. If no date is provided, it defaults 
    to the most recently recorded game in the dataset.
    
    Args:
        target_date_str (str, optional): Target reporting date in 'YYYY-MM-DD' format.
        
    Returns:
        Tuple containing:
            - JSON string of the structured data payload (or None if failure).
            - Boolean indicating if the current window is Playoff mode.
            - Boolean indicating if the current window is Championship Finals mode.
    """
    try:
        # --- PHASE 1: INGEST STATIC CONTEXT ---
        standings = pd.read_csv(TEAM_STATS_FILE).to_dict(orient='records')
        player_stats = pd.read_csv(PLAYER_STATS_FILE).to_dict(orient='records')
        
        playoff_standings = []
        if os.path.exists(PLAYOFF_STATS_FILE):
            playoff_standings = pd.read_csv(PLAYOFF_STATS_FILE).to_dict(orient='records')
            
        playoff_series = []
        if os.path.exists(PLAYOFF_MATCHUP_FILE):
            playoff_series = pd.read_csv(PLAYOFF_MATCHUP_FILE).to_dict(orient='records')
        
        details_df = pd.read_csv(DETAILS_FILE)
        manifest_df = pd.read_csv(MANIFEST_FILE)
        
        # Ensure schema safety for narrative metadata
        if 'Notes' not in manifest_df.columns:
            manifest_df['Notes'] = ""
            
        # --- PHASE 2: DATA NORMALIZATION ---
        # The raw manifest lacks year declarations. Impute the correct year based on 
        # standard winter sports seasonality (Fall = Year 1, Winter/Spring = Year 2).
        def append_year(date_str: str) -> str:
            if pd.isna(date_str): 
                return date_str
            if any(m in str(date_str) for m in ['Jan', 'Feb', 'Mar', 'Apr']):
                return f"{date_str} 2026"
            return f"{date_str} 2025"
            
        manifest_df['Date'] = manifest_df['Date'].apply(append_year)
        
        # Suppress Pandas parsing warnings for mixed formats to maintain clean terminal output
        warnings.filterwarnings('ignore', category=UserWarning, module='pandas')
        manifest_df['ParsedDate'] = pd.to_datetime(manifest_df['Date'], format='mixed', errors='coerce')
            
        # --- PHASE 3: TEMPORAL RESOLUTION ---
        if target_date_str:
            # Set bounding box to the absolute end of the target day
            target_date = pd.to_datetime(target_date_str).replace(hour=23, minute=59, second=59)
        else:
            # Auto-resolve to the most recent game played in the entire dataset
            latest_game_date = manifest_df['ParsedDate'].max()
            if pd.notna(latest_game_date):
                target_date = latest_game_date.replace(hour=23, minute=59, second=59)
            else:
                target_date = datetime.now().replace(hour=23, minute=59, second=59)
            
        # Establish the 7-day historical lookback window
        seven_days_ago = target_date - timedelta(days=7)
        
        # Filter dataset to prevent future data leakage into historical reports
        past_manifest = manifest_df[manifest_df['ParsedDate'] <= target_date]
        
        # Isolate the specific games played within our active 7-day reporting window
        this_week_manifest = past_manifest[past_manifest['ParsedDate'] > seven_days_ago]
        recent_game_ids = this_week_manifest['GameID'].astype(str).unique()
        
        # Filter granular play-by-play details to match the active window
        details_df['GameID'] = details_df['GameID'].astype(str)
        this_week_details = details_df[details_df['GameID'].isin(recent_game_ids)].copy()
        
        # Map referee and official assignments for the active games
        officials = this_week_details[this_week_details['EventType'] == 'Official']
        ref_map = officials.groupby('GameID')['Description'].apply(list).to_dict()

        # Simplify manifest for LLM consumption
        recent_manifest = this_week_manifest[
            ['GameID', 'Home', 'Away', 'Date', 'Score', 'Facility', 'Notes', 'GameType']
        ]

        # --- PHASE 4: SEASONAL HEURISTICS ---
        # Determine operational mode (Regular Season vs. Playoffs vs. Finals)
        game_types = recent_manifest['GameType'].fillna("")
        is_playoffs = game_types.str.contains('Playoff|Semi-Final|Final', case=False, regex=True).any()
        
        # If Playoff conditions are met and only two distinct teams remain active, trigger Finals mode
        teams_playing = set(recent_manifest['Home'].unique()).union(set(recent_manifest['Away'].unique()))
        is_finals = bool(is_playoffs and len(teams_playing) == 2)

        # Extract historical records of matchups that occurred prior to the target date
        historical_scores = past_manifest[['Date', 'Home', 'Away', 'Score', 'GameType']].to_dict(orient='records')

        # --- PHASE 5: PAYLOAD CONSTRUCTION ---
        brief = {
            "is_playoff_mode": bool(is_playoffs),
            "is_finals_mode": is_finals,
            "data_sources": {
                "playoff_series_points": playoff_series,
                "playoff_rankings_table": playoff_standings,
                "regular_season_standings": standings,
                "historical_matchup_scores": historical_scores,
                "individual_leaders": player_stats,
                "weekly_play_by_play": this_week_details.to_dict(orient='records'),
                "schedule_and_arenas": recent_manifest.to_dict(orient='records'),
                "official_assignments": ref_map
            },
            "report_metadata": {
                "current_date": target_date.strftime('%B %d, %Y'),
                "target_audience": "Toronto-based adult hockey players (25-35)"
            }
        }
        
        return json.dumps(brief, indent=2), is_playoffs, is_finals
        
    except Exception as e:
        print(f"❌ Error compiling weekly data package: {e}")
        return None, False, False


def generate_weekly_digest_report(target_date_str: Optional[str] = None):
    """
    Executes the LLM generation pipeline.
    
    Dynamically swaps prompt architectures based on the seasonal context retrieved 
    from the data package, calls the Gemini model, and writes the resulting output 
    to a Markdown file configured for Jekyll deployment.
    
    Args:
        target_date_str (str, optional): Target reporting date in 'YYYY-MM-DD' format.
    """
    package = compile_weekly_data_package(target_date_str) 
    if not package[0]: 
        return
    
    json_brief, is_playoffs, is_finals = package

    # Console logging for pipeline visibility
    if is_finals:
        print("🎙️ Generating Mode: CHAMPIONSHIP FINALE")
    elif is_playoffs:
        print("🎙️ Generating Mode: PLAYOFFS")
    else:
        print("🎙️ Generating Mode: REGULAR SEASON")
    
    # --- PROMPT ARCHITECTURE: Core Identity ---
    base_instructions = """
    <identity>
    You are the Senior Columnist for 'The Low B Dispatch,' a data-driven hockey newsletter covering the DMHL Monday/Wednesday Low B division in Toronto. Your writing style sits at the intersection of 'The Athletic' (analytical, deep-dive journalism) and 'The Players' Tribune' (authentic, player-focused storytelling), delivered with the sharp wit of a respected community peer.
    </identity>

    <style_guide>
    - THE VOICE: Write like a cynical, sharp, veteran beat reporter for 'The Athletic'. Punchy, dense, and analytical. 
    - THE BANNED CLICHÉS: Do NOT use amateur sports clichés. Banned phrases include: "barn burner", "epic proportions", "jaws of defeat", "see-saw affair", "down to the wire", "heart-stopping". 
    - NATURAL INTEGRATION: Do not sound robotic.
    - NAME FORMATTING: Use a player's Full Name on the very first mention. Use Last Name for subsequent mentions.
    </style_guide>

    <system_guardrails>
    - HOCKEY LOGIC (CRITICAL): Know the difference between an Empty Net (EN) and Extra Attacker (EA) goal.
    - NO EFFORT JUDGMENTS: Never demean a team or player by calling them "lazy" or "pathetic". 
    - NO LEAKED PIPELINE LOGIC: Never print internal tags or raw GameIDs.
    </system_guardrails>
    """

    # --- PROMPT ARCHITECTURE: Dynamic Sub-Routines ---
    if is_finals:
        mode_instructions = """
        <narrative_strategy>
        1. THE CHAMPIONSHIP HOOK: This is the absolute final report of the season. Open with the crowning of the DMHL Low B Champion. Describe how they won the final matchup based strictly on the recap data.
        2. SEASON RETROSPECTIVE: Step back and provide a compelling, overarching summary of the season. Did a juggernaut go wire-to-wire? Did a 'Lucky Loser' make a Cinderella run? Use the regular season and playoff standings data to paint the picture.
        3. HARDWARE HANDOUT (TOP POINT GETTERS): Scan the 'individual_leaders' data to identify the absolute top 3 scoring leaders of the season. Dedicate a section to honoring their statistical dominance.
        4. PROSE FLOW: Make it feel like a grand finale. It should be celebratory, definitive, and sharp.
        5. COMMISSIONER INSIGHTS: Use 'Notes' for atmosphere.
        </narrative_strategy>

        <data_guardrails>
        1. THE SOURCE OF TRUTH: Crown the champion based on the 'weekly_play_by_play' and 'schedule_and_arenas' data. Do not hallucinate a winner.
        2. DATA AGGREGATION: Pull the top scorers strictly from 'individual_leaders'.
        </data_guardrails>

        <format_requirements>
        - Headline: [Epic Championship Headline specifically naming the winning team and their accomplishment. Make it bold and journalistic.]
        - Subline: [One punchy sentence summarizing the final victory and putting a bow on the season.]
        - The Lede: [Crown the champion. Recap the final game(s) that sealed the deal in a flowing, dramatic paragraph.]
        - Season in Review: [1-2 paragraphs summarizing the overarching storylines of the entire season. Reference regular season dominance vs playoff reality.]
        - The Hardware (League Leaders): [List the top 3 overall point getters from the data. Format: **[Name] ([Team]) - [Total Points] Pts**. Add a brief sentence honoring their dominance.]
        - The Final Dispatch Three Stars: [Exactly THREE stars for the championship game heroes.]
          * Format: **[1st/2nd/3rd] Star: [Player Name] ([Team])** - [G]G, [A]A, [Pts]Pts. - [Reasoning]. 
          * 1st Star: "The Championship MVP" (The ultimate clutch performer of the final game)
          * 2nd Star: "The Stat Sheet Stuffer" 
          * 3rd Star: "The Unsung Hero" (Defense, special teams, or crucial momentum shifts)
        - Length: Target 450-550 words.
        </format_requirements>
        """
        task_instruction = "Task: Generate the Championship End-of-Season recap, crowning the champion, summarizing the storylines, and honoring the top scorers."

    elif is_playoffs:
        mode_instructions = """
        <narrative_strategy>
        1. DYNAMIC PLAYOFF TRACKING: Analyze the 'schedule_and_arenas' to determine the round.
        2. THE LEDE (THE HOOK): Make the opening paragraph an explosive hook about the biggest drama of THIS specific week.
        3. COMBINED RECAP & SCOUTING: For the active matchups, blend the recap with the momentum shifts and the stakes.
        </narrative_strategy>
        <format_requirements>
        - Headline: [Specific storyline headline]
        - Subline: [One sentence analytical summary]
        - The Lede: [Punchy storyline hook]
        - The Matchups: [Markdown headings for each series with recaps]
        - The Dispatch Three Stars: [Exactly THREE stars for the week's heroes.]
          * Format: **[1st/2nd/3rd] Star: [Player Name] ([Team])** - [G]G, [A]A, [Pts]Pts. - [Reasoning]. 
        </format_requirements>
        """
        task_instruction = "Task: Generate the weekly Playoff wrap-up."

    else:
        mode_instructions = """
        <narrative_strategy>
        1. DYNAMIC CURRENT STATE: Look at standings shifts and narratives.
        2. THE LEDE: Lead with the most important storyline.
        3. REGULAR SEASON TRACKING: Analyze the biggest games of the week.
        </narrative_strategy>
        <format_requirements>
        - Headline: [Sharp Journalistic Headline]
        - Subline: [Contextual summary]
        - The Lede: [Standings shift or storyline]
        - The Recaps: [Combine recaps into a narrative]
        - The Dispatch Three Stars: [Exactly THREE stars for the week's heroes.]
          * Format: **[1st/2nd/3rd] Star: [Player Name] ([Team])** - [G]G, [A]A, [Pts]Pts. - [Reasoning]. 
        </format_requirements>
        """
        task_instruction = "Task: Generate the Regular Season wrap-up."

    prompt = f"DATA BRIEF:\n{json_brief}\n\n{task_instruction}"
    
    try:
        # Execute LLM call
        response = client.models.generate_content(
            model="gemini-2.5-flash", 
            contents=[base_instructions, mode_instructions, prompt]
        )
        report_text = response.text
        
        # --- POST-PROCESSING & FORMATTING ---
        # Evaluate output for team mentions to dynamically assign header artwork
        teaser_logo = "/assets/images/rink-header.jpg"
        for team, logo_path in LOGO_MAP.items():
            if team in report_text:
                teaser_logo = logo_path
                break

        # Parse generated text to isolate the headline and subline for Jekyll metadata
        lines = report_text.strip().split('\n')
        generated_headline = lines[0].replace('#', '').strip()
        generated_subline = lines[1].strip() if len(lines) > 1 else "The Season Wraps Up."

        # Ensure output directory structure exists
        os.makedirs(POSTS_DIR, exist_ok=True)
        
        # Determine appropriate filename via target date or dynamic resolution
        if target_date_str:
            file_date = datetime.strptime(target_date_str, "%Y-%m-%d") 
        else:
            file_date_str = json.loads(json_brief)['report_metadata']['current_date']
            file_date = datetime.strptime(file_date_str, '%B %d, %Y')
            
        filename = f"{file_date.strftime('%Y-%m-%d')}-dispatch.md"
        filepath = os.path.join(POSTS_DIR, filename)
        
        # Construct Jekyll configuration block
        front_matter = f"""---
layout: single
title: "{generated_headline}"
excerpt: "{generated_subline}"
header:
  teaser: "{teaser_logo}"
author_profile: true
---

"""
        # Write asset to disk
        with open(filepath, "w") as f:
            f.write(front_matter)
            f.write(report_text)

        print(f"\n✅ Published: {filepath}")
        print("-" * 30)
        print(report_text)

    except Exception as e:
        print(f"❌ LLM Generation or File Writing Error: {e}")


if __name__ == "__main__":
    # Allow for temporal testing by accepting a date string via the CLI 
    # (e.g., `python3 src/reporter.py 2026-03-25`)
    passed_date = sys.argv[1] if len(sys.argv) > 1 else None
    generate_weekly_digest_report(passed_date)