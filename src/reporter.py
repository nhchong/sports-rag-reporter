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
        
        # 3. Temporal Filtering: Filter strictly for TODAY'S action
        details_df['ScrapedAt'] = pd.to_datetime(details_df['ScrapedAt'])
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        
        # Filter for records that match today's date exactly
        this_week_details = details_df[details_df['ScrapedAt'] >= today].copy()
        
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
    You are the Senior Columnist for 'The Low B Dispatch,' a data-driven hockey newsletter covering the DMHL Monday/Wednesday Low B division in Toronto. Your writing style mirrors 'The Athletic' (analytical depth) and 'Spittin Chiclets' (mature community peer).
    </identity>

    <style_guide>
    - ANALYTICAL: Substantiate every claim with provided JSON data. 
    - ZERO FLUFF: Use sharp, sophisticated humor. No 'hockey bro' lingo. No emojis.
    - NO SUBJECTIVE EFFORT JUDGMENTS: Never call a team 'lazy' or 'pathetic.' Use stats to prove dominance instead.
    - NO LEAKED LOGIC: You are strictly forbidden from including internal data tags like [JSON: ...], [Source: ...], or GameIDs in the final prose.
    - VALIDATION SECURITY: To pass a strict regex validator, you MUST use the exact Full Names of players as they appear in the data. Credit assists only if explicitly listed in parentheses in the play-by-play.
    - AUTHENTIC: Speak to the community as a peer but avois any unprofessional locker-room tone.
    - COMPELLING NARRATIVE: Similar to the media outlet, The Athletic
    - LIGHT-HEARTED BUT PROFESSIONAL: Similar the Spittin Chiclets podcast. 
    - PLAYER-FOCUSED: Much like the media outlet, the Player's Tribune. 
    - FAIR BUT COLORFUL: Keep the narrative engaging and dramatic. You may use colorful language to describe actions (e.g., 'a blistering shot', 'a relentless attack', 'a high-scoring affair'). However, you MUST NOT make subjective judgments about a team's effort or worthiness. Never demean a team by calling them 'flat', 'pathetic', or claiming one team 'drastically outplayed' another if it's not purely based on shot data. Let the stats prove dominance.
    </style_guide>
    """

    # --- PROMPT ARCHITECTURE: Seasonal Pivot Logic ---
    if is_playoffs:
        mode_instructions = """
        <narrative_strategy>
        1. THE ROUND 1 AUTOPSY: Round 1 is over. Describe the high-leverage goals and the exact moments the series were won.
        2. THE SEMI-FINAL BRACKET: Explicitly announce that the Semi-Finals are set. Infer matchups from the standings and the playoff series points and the lucky loser math.
        3. THE SCOUTING REPORT: For each Semi-Final matchup, provide a data-backed 'Tale of the Tape' using regular season history. Analyze if past meetings were defensive grinds or high-PIM affairs.
        5. THE LUCKY LOSER MIRACLE: Explain the math behind the lucky loser's survival. Contrast their 'Goal Diff' against the other losers to justify their reprieve.
        6. PROSE INTEGRATION: Data must be woven seamlessly into the story. Do not list sources or internal logic markers. Do not overwelm the reader with too much data.
        7. Do not refer to games by their gameIDs
        8. COMMISSIONER INSIGHTS: Use 'Notes' to enrich the atmosphere (e.g., penalty context, short benches). If the commissioner provides a subjective, demeaning quote (like a team "looked flat" or the game was "chippy"), you must filter it out or translate it into a neutral observation. Do not use quotes to validate a biased narrative.
        9. DATA ANCHORING: Every claim must be substantiated by the provided JSON data. Do not invent highlights.
        10. Make sure to weave in a summary of every game that happened this week. Every team has to be mentioned. Ensure a balanced representation, objectively acknowledging the statistical merits of both winning and losing teams.
        11. Use the 'official_assignments' to highlight specific referees and linesmen only if they called a lot of penalities or no penalities at all.
        12. If you are going to mentione te first game of the series, don't include the score. 
        </narrative_strategy>

        <playoff_logic>
        ROUND 1: 1vs6, 2vs5, 3vs4 (Complete).
        ROUND 2 (SEMI-FINALS): Winners + 1 Lucky Loser. 
        ROUND 3: The Final (1 game).
        FORMAT: 2-game series, 'Race to Three' (Win=2, Tie=1). If tied after Game 2, 5-min 4-on-4 OT and shootouts apply.
        TIEBREAKERS (IN ORDER):
        1. Points (Win=2, Tie=1)
        2. Goal Differential
        3. Total Goals Scored
        4. Fewest Penalty Minutes
        </playoff_logic>

        <format_requirements>
        Line 1: [Sharp Journalistic Headline]
        Line 2: [Analytical Subline regarding the Lucky Loser/Bracket]
        Body: Markdown headings. Ensure a seamless flow between the Round 1 summary and the Semi-Final previews.
        Three Stars: 
        Must be strictly based on the most recent game data from {today.strftime('%Y-%m-%d')} only. To prevent winner-bias, players on losing or tied teams must be considered if their individual statistical performances warrant it.
        - 1st Star: Most points, favoring goals. Emphasis on important goals. 
        - 2nd Star: Second most points, emphasis on goals. 
        - 3rd Star: The 'Productive Agitator' who contributes on the scoresheet and as a team contirbuter or the top goalie with a shootout or the player who had a clutch goal.
        Length: Max 300 words.
        </format_requirements>
        """
    else:
        mode_instructions = """
        <narrative_strategy>
        1. STANDINGS SHIFTS: Analyze Regular Season movement.
        2. COMMISSIONER INSIGHTS: Neutral reporting of locker room vibes from 'Notes'.
        </narrative_strategy>
        """

    prompt = f"DATA BRIEF:\n{json_brief}\n\nTask: Generate the Round 1 wrap-up and Semi-Final preview report."
    
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
        generated_subline = lines[1].strip() if len(lines) > 1 else "Semi-Finals are set."

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