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
PLAYOFF_STATS_FILE = "data/playoff_standings.csv" 
PLAYOFF_MATCHUP_FILE = "data/playoff_matchups.csv" 
DOCS_DIR = "docs"
POSTS_DIR = os.path.join(DOCS_DIR, "_posts")

# --- LOGO MAPPING ---
LOGO_MAP = {
    "The Shockers": "/assets/images/theshockers.png",
    "The Sahara": "/assets/images/thesahara.png",
    "Don Cherry's": "/assets/images/doncherrys.png",
    "Flat-Earthers": "/assets/images/flatearthers.png",
    "Muffin Men": "/assets/images/muffinmen.png",
    "4 Lines": "/assets/images/4lines.png"
}

# Initialize the Gemini client
api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
client = genai.Client(api_key=api_key)

def compile_weekly_data_package():
    """
    Constructs a comprehensive data package for the LLM.
    Detects 'Seasonality' by checking GameType to pivot the AI's narrative focus.
    """
    try:
        # 1. Load Quantitative Context
        standings = pd.read_csv(TEAM_STATS_FILE).to_dict(orient='records')
        player_stats = pd.read_csv(PLAYER_STATS_FILE).to_dict(orient='records')
        
        playoff_standings = []
        if os.path.exists(PLAYOFF_STATS_FILE):
            playoff_standings = pd.read_csv(PLAYOFF_STATS_FILE).to_dict(orient='records')
            
        playoff_series = []
        if os.path.exists(PLAYOFF_MATCHUP_FILE):
            playoff_series = pd.read_csv(PLAYOFF_MATCHUP_FILE).to_dict(orient='records')
        
        # 2. Load Manifest & Details
        details_df = pd.read_csv(DETAILS_FILE)
        manifest_df = pd.read_csv(MANIFEST_FILE)
        
        # Ensure 'Notes' column exists (Maker-Owner Safety Check)
        if 'Notes' not in manifest_df.columns:
            manifest_df['Notes'] = ""
        
        # 3. Temporal Filtering: Filter for the current week's action
        details_df['ScrapedAt'] = pd.to_datetime(details_df['ScrapedAt'])
        today = datetime.now()
        monday_of_this_week = today - pd.Timedelta(days=today.weekday())
        
        this_week_details = details_df[
            details_df['ScrapedAt'] >= monday_of_this_week.replace(hour=0, minute=0)
        ].copy()
        
        # 4. Map Official Assignments
        officials = this_week_details[this_week_details['EventType'] == 'Official']
        ref_map = officials.groupby('GameID')['Description'].apply(list).to_dict()

        # 5. Extract Recent Manifest & Determine Season Mode
        this_week_details['ScrapedAt'] = this_week_details['ScrapedAt'].dt.strftime('%Y-%m-%d')
        recent_game_ids = this_week_details['GameID'].unique().astype(str)
        
        recent_manifest = manifest_df[manifest_df['GameID'].astype(str).isin(recent_game_ids)][
            ['GameID', 'Home', 'Away', 'Date', 'Score', 'Facility', 'Notes', 'GameType']
        ]

        # LOGIC: If any game this week is a Playoff game, we pivot the entire report to Playoff Mode
        is_playoffs = "Playoffs" in recent_manifest['GameType'].values

        brief = {
            "is_playoff_mode": is_playoffs,
            "data_sources": {
                "playoff_series_points": playoff_series,
                "playoff_rankings_table": playoff_standings,
                "regular_season_standings": standings,
                "individual_leaders": player_stats,
                "weekly_play_by_play": this_week_details.to_dict(orient='records'),
                "schedule_and_arenas": recent_manifest.to_dict(orient='records'),
                "official_assignments": ref_map
            },
            "report_metadata": {
                "current_date": today.strftime('%B %d, %Y'),
                "target_audience": "Toronto-based adult hockey players (25-35)"
            }
        }
        return json.dumps(brief, indent=2), is_playoffs
    except Exception as e:
        print(f"❌ Error compiling weekly data package: {e}")
        return None, False

def generate_weekly_digest_report():
    """
    Pivots prompt instructions based on season mode and generates the Markdown report.
    """
    json_brief, is_playoffs = compile_weekly_data_package() 
    if not json_brief: return

    print(f"🎙️ Generating Mode: {'PLAYOFFS' if is_playoffs else 'REGULAR SEASON'}")
    
    # --- PROMPT ARCHITECTURE: Shared Identity & Style ---
    base_instructions = """
    <identity>
    You are the Senior Columnist for 'The Low B Dispatch,' a data-driven hockey newsletter. You cover the DMHL, which stands for the Downtown Mens Hockey League. The league is based in Toronto. Most of the players are between the ages of 25 and 35. Games are played on Monday and Wednesday. The division that you are covering is Monday/Wednesday Low B. 
    </identity>

    <style_guide>
    - ANALYTICAL: Use data to substantiate claims. 
    - AUTHENTIC: Speak to the community as a peer but avois any unprofessional locker-room tone.
    - ZERO FLUFF: Avoid generic PR language.
    - COMPELLING NARRATIVE: Similar to the media outlet, The Athletic
    - LIGHT-HEARTED BUT PROFESSIONAL: Similar the Spittin Chiclets podcast. 
    - PLAYER-FOCUSED: Much like the media outlet, the Player's Tribune. 
    - MATURE WIT: No 'hockey bro' lingo. Use sharp, sophisticated humor. No emojis.
    </style_guide>

    """

    # --- PROMPT ARCHITECTURE: Seasonal Pivot Logic ---
    if is_playoffs:
        mode_instructions = """
        <narrative_strategy>
        1. THE BRACKET & LUCKY LOSER: Analyze the 'playoff_series_points'. Explicitly discuss the 'Lucky Loser' race—who among the losers has the best Goal Diff or Points to sneak into Round 2?
        2. THE "RACE TO THREE": Explicitly mention point standings in the series (e.g., "The 416ers sit at 2 points; a tie in Game 2 punches their ticket").
        3. DATA ANCHORING: Every claim must be substantiated by the provided JSON data. Do not invent highlights. Use 'weekly_play_by_play' to highlight clutch goals or costly penalties.
        4. PLAYER FOCUS: Use 'player_stats' and 'weekly_play_by_play' to highlight clutch playoff performances. Use 'individual_leaders' to spotlight who is elevating their game in the post-season.
        5. COMMISSIONER INSIGHTS: High Priority. Use 'Notes' to enrich the report with the game commentary provided by the commisioner who was at the game. 
        6. THE OFFICIALS: Highlight 'official_assignments' only if they were a dominant factor in the weekly PIMs.
        7. VIBE & VENUE: Contextualize results using 'schedule_and_arenas' and specific weather data for that day to set the scene. 
        8. 80/20 Rule: 80% COVERAGE is Focused on the 'weekly_play_by_play' events and 20% CONTEXT: Ground results in standings and leaders.
        9. Make sure to weave in a summary of every game that happened this week. Every team has to be mentioned. 
        10. Use the 'game_details' to highlight specific game events. Weave in the game details into the narrative.
        11. Do not refer to games by their gameIDs

        </narrative_strategy>

        <playoff_logic>
        ROUND 1: Matchups are 1vs6, 2vs5, and 3vs4. These are two-game series using the 'Race to Three' points format.
        ROUND 2: Winners advance. One 'Lucky Loser' (the team with the best results among the three Round 1 losers) advances to play the #1 seed. The other two winners face off. (1 game).
        ROUND 3: The Final (1 game).

        'RACE TO THREE' LOGIC:
        - Win = 2 pts | Tie = 1 pt.
        - GAME 1: Ends in regulation. Ties stand at 1-1.
        - GAME 2 (CLINCHING): 
            - If series is tied at 2 pts each after regulation (e.g., 1-1 split or two ties), a 5-min 4-on-4 sudden death OT occurs.
            - If still tied after OT, a 3-person simultaneous shootout determines the series winner.
        - DISCIPLINE: Penalties from Game 2 regulation do NOT carry over to Overtime.

        TIEBREAKERS (IN ORDER):
        1. Points (Win=2, Tie=1)
        2. Goal Differential
        3. Total Goals Scored
        4. Fewest Penalty Minutes
        </playoff_logic>

        <format_requirements>
        Line 1: [Sharp Playoff Headline]
        Line 2: [Analytical Subline]
        Body: Markdown headings. Separate sections for 'Series Math' or 'Lucky Loser' projections. Keep these sections as short as possible. 
        Three Stars: 
        Must be strictly based on weekly data.
        - 1st Star: Most points, favoring goals. Emphasis on important goals. 
        - 2nd Star: Second most points, emphasis on goals. 
        - 3rd Star: The 'Productive Agitator' who contributes on the scoresheet and as a team contirbuter or the top goalie with a shootout or the player who had a clutch goal. 
        Length: No more than 300 words
        </format_requirements>

        <task_sequence>
        Step 1: Parse 'playoff_series_scores' to determine the "Race to Three" status for each seed pairing.
        Step 2: Identify 'Three Stars' based on high-leverage weekly performances.
        Step 3: Write the dispatch focusing on the playoff stakes and narrative shifts.
        </task_sequence>
        """
    else:
        mode_instructions = """
        <narrative_strategy>
        1. STANDINGS SHIFTS: Analyze how this week's results changed the Regular Season table.
        2. RACE FOR TOP SEED: Who is pulling away? Who is struggling in the 'Low B' basement?
        3. EFFICIENCY: Use 'regular_season_standings' to highlight powerplay and penalty kill trends.
        4. COMMISSIONER INSIGHTS: High Priority. Use 'Notes' for locker room vibes and arena atmosphere.
        </narrative_strategy>
        """

    prompt = f"DATA BRIEF:\n{json_brief}\n\nTask: Generate the weekly dispatch report."
    
    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash", 
            contents=[base_instructions, mode_instructions, prompt]
        )
        report_text = response.text
        
        # Post-Processing: Logos and Headers
        teaser_logo = "/assets/images/rink-header.jpg"
        for team, logo_path in LOGO_MAP.items():
            if team in report_text:
                teaser_logo = logo_path
                break

        lines = report_text.strip().split('\n')
        generated_headline = lines[0].replace('#', '').strip()
        generated_subline = lines[1].strip() if len(lines) > 1 else "Weekly league analysis."

        # Persistence: Archive to GitHub Pages
        os.makedirs(POSTS_DIR, exist_ok=True)
        today = datetime.now()
        filename = f"{today.strftime('%Y-%m-%d')}-dispatch.md"
        filepath = os.path.join(POSTS_DIR, filename)
        
        front_matter = f"""---
layout: single
title: "{generated_headline}"
excerpt: "{generated_subline}"
header:
  teaser: "{teaser_logo}"
author_profile: true
---

"""
        with open(filepath, "w") as f:
            f.write(front_matter)
            f.write(report_text)

        print(f"\n✅ Published: {filepath}")
        print("-" * 30)
        print(report_text)

    except Exception as e:
        print(f"❌ Gemini API Error: {e}")

if __name__ == "__main__":
    generate_weekly_digest_report()