import os
import sys
import json
import warnings
import pandas as pd
from datetime import datetime, timedelta
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

def compile_weekly_data_package(target_date_str=None):
    """
    Constructs a comprehensive data package for the LLM.
    Uses True Time Travel by filtering against the actual Game Dates in the manifest.
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
        
        if 'Notes' not in manifest_df.columns:
            manifest_df['Notes'] = ""
            
        # --- TRUE TIME TRAVEL LOGIC ---
        if target_date_str:
            # Push the target to the absolute end of the day (11:59 PM)
            target_date = pd.to_datetime(target_date_str).replace(hour=23, minute=59, second=59)
        else:
            target_date = datetime.now().replace(hour=23, minute=59, second=59)
            
        # Define "This Week" as the 7 days leading up to our target date
        seven_days_ago = target_date - timedelta(days=7)
        
        # --- THE MISSING YEAR FIX ---
        def append_year(date_str):
            if pd.isna(date_str): return date_str
            # If the month is Jan, Feb, Mar, or Apr, it's 2026. Otherwise, it's 2025.
            if any(m in str(date_str) for m in ['Jan', 'Feb', 'Mar', 'Apr']):
                return f"{date_str} 2026"
            return f"{date_str} 2025"
            
        manifest_df['Date'] = manifest_df['Date'].apply(append_year)
        # ---------------------------------
        
        # Parse dates in manifest (Silence the warning and force mixed format)
        warnings.filterwarnings('ignore', category=UserWarning, module='pandas')
        manifest_df['ParsedDate'] = pd.to_datetime(manifest_df['Date'], format='mixed', errors='coerce')
        
        # CRITICAL: Strip out the future! (Hide any games after our target date)
        past_manifest = manifest_df[manifest_df['ParsedDate'] <= target_date]
        
        # Find games that happened *specifically* in the 7 days leading up to our target date
        this_week_manifest = past_manifest[past_manifest['ParsedDate'] > seven_days_ago]
        recent_game_ids = this_week_manifest['GameID'].astype(str).unique()
        
        # Filter the play-by-play details to ONLY include those specific GameIDs
        details_df['GameID'] = details_df['GameID'].astype(str)
        this_week_details = details_df[details_df['GameID'].isin(recent_game_ids)].copy()
        
        # 4. Map Official Assignments
        officials = this_week_details[this_week_details['EventType'] == 'Official']
        ref_map = officials.groupby('GameID')['Description'].apply(list).to_dict()

        # 5. Extract Recent Manifest & Determine Season Mode
        recent_manifest = this_week_manifest[
            ['GameID', 'Home', 'Away', 'Date', 'Score', 'Facility', 'Notes', 'GameType']
        ]

        # --- DEBUG BLOCK ---
        print(f"\n🔍 DEBUG: Looking for games between {seven_days_ago.date()} and {target_date.date()}")
        print(f"🔍 DEBUG: Found {len(recent_manifest)} games.")
        if len(recent_manifest) > 0:
            print(recent_manifest[['Date', 'Home', 'Away', 'GameType']])
        print("-" * 50)
        # -------------------

        # LOGIC: Bulletproof Playoff Check
        game_types = recent_manifest['GameType'].fillna("")
        is_playoffs = game_types.str.contains('Playoff|Semi-Final|Final', case=False, regex=True).any()

        # 6. Extract Historical Matchups (Only up to the target date, hiding future matchups!)
        historical_scores = past_manifest[['Date', 'Home', 'Away', 'Score', 'GameType']].to_dict(orient='records')

        brief = {
            "is_playoff_mode": bool(is_playoffs),
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
                "target_audience": "Toronto-based adult hockey players (25-35)",
                "time_travel_warning": "CRITICAL: You are writing this on the current_date. Ignore any aggregated stats that imply games played after this date."
            }
        }
        return json.dumps(brief, indent=2), is_playoffs
    except Exception as e:
        print(f"❌ Error compiling weekly data package: {e}")
        return None, False

def generate_weekly_digest_report(target_date_str=None):
    """
    Pivots prompt instructions based on season mode and generates the Markdown report.
    """
    json_brief, is_playoffs = compile_weekly_data_package(target_date_str) 
    if not json_brief: return

    print(f"🎙️ Generating Mode: {'PLAYOFFS' if is_playoffs else 'REGULAR SEASON'}")
    
    # --- PROMPT ARCHITECTURE: Shared Identity & Style ---
    base_instructions = """
    <identity>
    You are the Senior Columnist for 'The Low B Dispatch,' a data-driven hockey newsletter covering the DMHL Monday/Wednesday Low B division in Toronto. Your writing style sits at the intersection of 'The Athletic' (analytical, deep-dive journalism) and 'The Players' Tribune' (authentic, player-focused storytelling), delivered with the sharp wit of a respected community peer.
    </identity>

    <style_guide>
    - THE VOICE: Write like a cynical, sharp, veteran beat reporter for 'The Athletic'. Punchy, dense, and analytical. 
    - THE BANNED CLICHÉS: Do NOT use amateur sports clichés. Banned phrases include: "barn burner", "epic proportions", "jaws of defeat", "see-saw affair", "down to the wire", "heart-stopping". 
    - NATURAL INTEGRATION: Do not sound robotic. Instead of saying "bench depth was noted as robust," say "both teams rolled full benches."
    - NARRATIVE FREEDOM: You have the creative license to tell a compelling story. Read between the lines of the boxscore.
    - NAME FORMATTING: Use a player's Full Name on the very first mention (e.g., Brandon Sanders). For all subsequent mentions, use their Last Name only (e.g., Sanders).
    - ASSIST CURATION: Do NOT read like a dry boxscore. Stop listing every single assist. Only mention playmakers if they had 3+ assists or a clutch setup.
    </style_guide>

    <system_guardrails>
    - HOCKEY LOGIC (CRITICAL): Know the difference between an Empty Net (EN) and Extra Attacker (EA) goal. A team pulling their goalie to TIE the game scores an "Extra Attacker" goal. A team shooting into the opponent's net to EXTEND a lead scores an "Empty Net" goal. Never say a team tied the game with an empty net goal.
    - THREE STARS FORMAT (STRICT): You MUST include the stat line in the formatting exactly like this: **[Star] Star: [Name] ([Team])** - [G]G, [A]A, [Pts]Pts. - [Reasoning]. Do not drop the stats!
    - VALIDATION SECURITY: The very first time you mention a player involved in a scoring/penalty event, you MUST use their exact Full Name as it appears in the JSON.
    - NO EFFORT JUDGMENTS: Never demean a team or player by calling them "lazy" or "pathetic". 
    - NO LEAKED PIPELINE LOGIC: Never print internal tags or raw GameIDs.
    </system_guardrails>
    """

    # --- PROMPT ARCHITECTURE: Seasonal Pivot Logic ---
    if is_playoffs:
        mode_instructions = """
        <narrative_strategy>
        1. DYNAMIC PLAYOFF TRACKING: Analyze the 'schedule_and_arenas' and 'playoff_series_points'. Determine the exact round (If 4 teams are playing, it is the Semi-Finals. If 2 teams, it is the Finals). Also determine the exact stakes: if no team has 2 points yet, these are Game 1 tone-setters. If teams have points, these are elimination/clinching games.
        2. THE LEDE (THE HOOK): Make the opening paragraph an explosive hook about the biggest drama of THIS specific week (e.g., the Lucky Loser pushing the #1 seed to the brink, or massive blown leads). Frame it around the context of the Semi-Finals.
        3. COMBINED RECAP & SCOUTING: For the active matchups, write a single, flowing section blending the recap of the game just played, the momentum shifts, and how their regular-season 'Tale of the Tape' sets the stakes for Game 2.
        4. PROSE FLOW: Use connective tissue and varied sentence structures. Write like a cynical, sharp, human sports columnist for 'The Athletic'. No robotic recaps.
        5. COMMISSIONER INSIGHTS: Use 'Notes' for atmosphere.
        </narrative_strategy>

        <data_guardrails>
        1. TEMPORAL BOUNDARY (CRITICAL): You are writing this report on the 'current_date' provided in the JSON. You MUST ONLY recap the games that occurred in the 'weekly_play_by_play' data. Do not write full recaps for past rounds; only mention past rounds briefly as context (e.g., "Fresh off their Round 1 victory over..."). 
        2. THE SOURCE OF TRUTH: Use 'weekly_play_by_play' to understand the *flow* of the game. Use 'individual_leaders' for stats.
        3. NO HALLUCINATIONS: Do not invent regular season history or stakes.
        </data_guardrails>

        <playoff_logic>
        FORMAT: 2-game series, 'Race to Three' points (Win=2, Tie=1). 
        Determine who is leading, who is facing elimination, or if a series is tied based on the data. 
        TIEBREAKERS (If tied after Game 2): 1. Points, 2. Goal Differential, 3. Total Goals, 4. Fewest Penalty Minutes.
        LUCKY LOSER: A team that advanced despite losing their previous series.
        </playoff_logic>

        <format_requirements>
        - Headline: [Must contain the names of the teams involved in the biggest storyline. Example: "Lucky Losers Stun #1 Don Cherry's in Semi-Final Opener". NO generic "Playoffs Begin" titles.]
        - Subline: [A sharp, one-sentence analytical summary placed right below the headline. No more than 15 words. Use this to add context to the upset or highlight the secondary storyline.]
        - The Lede: [One punchy paragraph hooking the reader with the organic storyline you identified.]
        - The Matchups: [Use Markdown headings for each series. Write 1-2 flowing paragraphs per series blending recap, 'Tale of the Tape', and Game 2 stakes.]
        - The Dispatch Three Stars: [Exactly THREE stars TOTAL for the entire week.]
          * Format: **[1st/2nd/3rd] Star: [Player Name] ([Team])** - [G]G, [A]A, [Pts]Pts. - [Reasoning]. 
          * 1st Star: "The Clutch Performer" 
          * 2nd Star: "The Stat Sheet Stuffer" 
          * 3rd Star: "The Intangible Hero"
        - Length: Target 400-500 words. Keep it brutally tight but well-written.
        </format_requirements>
        """
        task_instruction = "Task: Generate the weekly Playoff wrap-up and preview report for the current week's action."

    else:
        mode_instructions = """
        <narrative_strategy>
        1. DYNAMIC CURRENT STATE: Look at the dates and standings to determine the current narrative. Is it early in the season? A mid-season slump? A late-season push for playoff seeding?
        2. THE LEDE: Lead with the most important storyline—a major upset, a massive blowout, or a team stealing first place.
        3. REGULAR SEASON TRACKING: Analyze standings shifts and highlight standout weekly performances.
        4. THE "WHY", NOT THE "HOW": Don't just list goals. Explain how games were won (e.g., special teams dominance, clutch 3rd periods, penalty trouble).
        5. COMMISSIONER INSIGHTS: Neutral reporting of locker room vibes from 'Notes'.
        </narrative_strategy>
        
        <format_requirements>
        - Headline: [Sharp Journalistic Headline]
        - The Lede: [Summary of the biggest standings shift or storyline]
        - The Recaps: [Combine the recaps into a flowing narrative.]
        - The Dispatch Three Stars: [Exactly THREE stars TOTAL for the entire week.]
          * Format: **[1st/2nd/3rd] Star: [Player Name] ([Team])** - [G]G, [A]A, [Pts]Pts. - [Reasoning]. 
          * 1st Star: "The Clutch Performer"
          * 2nd Star: "The Stat Sheet Stuffer"
          * 3rd Star: "The Special Teams/Intangible Hero"
        - Length: Target 350-450 words.
        </format_requirements>
        """
        task_instruction = "Task: Generate the Regular Season weekly wrap-up and updated standings analysis."

    prompt = f"DATA BRIEF:\n{json_brief}\n\n{task_instruction}"
    
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
        
        # Use target_date for filename so you can time travel without overwriting today's post
        file_date = datetime.strptime(target_date_str, "%Y-%m-%d") if target_date_str else datetime.now()
        filename = f"{file_date.strftime('%Y-%m-%d')}-dispatch.md"
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
    # Catch a date passed via terminal (e.g. python3 src/reporter.py 2026-03-12)
    passed_date = sys.argv[1] if len(sys.argv) > 1 else None
    generate_weekly_digest_report(passed_date)