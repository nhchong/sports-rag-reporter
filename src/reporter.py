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

        # 6. Extract Historical Matchups for AI Scouting
        historical_scores = manifest_df[['Date', 'Home', 'Away', 'Score', 'GameType']].to_dict(orient='records')

        brief = {
            "is_playoff_mode": is_playoffs,
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
        1. DYNAMIC CURRENT STATE: Analyze the data to determine the *furthest* round currently being played (e.g., Semi-Finals). FOCUS ENTIRELY ON THIS ROUND. 
        2. THE LEDE (THE HOOK): Do not write a generic intro. Make the opening paragraph an explosive hook about the biggest drama of the CURRENT round (e.g., #1 seed surviving a scare, a massive 3-goal comeback). 
        3. COMBINED RECAP & SCOUTING: For the active matchups in the CURRENT round, write a single, flowing section blending the recap, momentum shifts, and the stakes for Game 2. 
        4. PROSE FLOW: Use connective tissue and varied sentence structures. Write like a cynical, sharp, human sports columnist. No robotic recaps.
        5. COMMISSIONER INSIGHTS: Use 'Notes' for atmosphere.
        </narrative_strategy>

        <data_guardrails>
        1. TEMPORAL BOUNDARY (CRITICAL): If your data contains both Round 1 games and Semi-Final games, DO NOT write full recaps for the Round 1 games. Only mention them briefly as context (e.g., "Fresh off their Round 1 victory over..."). Your primary focus must be the most recent round.
        2. THE SOURCE OF TRUTH: Use 'weekly_play_by_play' to understand the *flow* of the game. Use 'individual_leaders' for stats.
        3. NO HALLUCINATIONS: Do not invent regular season history or stakes.
        </data_guardrails>

        <playoff_logic>
        FORMAT: 2-game series, 'Race to Three' points (Win=2, Tie=1). 
        Determine who is leading, who is facing elimination, or if a series is tied based on the data. 
        TIEBREAKERS (If tied after Game 2): 1. Points, 2. Goal Differential, 3. Total Goals, 4. Fewest Penalty Minutes.
        </playoff_logic>

        <format_requirements>
        - Headline: [Must contain the names of the teams involved in the biggest storyline you discovered. NO generic "Playoffs Begin" titles. Make it specific to the events.]
        - Subline: [A sharp, one-sentence analytical summary placed right below the headline. No more than 15 words. Use this to add context to the upset, name the standout player, or highlight the secondary storyline.].  
        - The Lede: [One punchy paragraph hooking the reader with the organic storyline you identified.]
        - The Matchups: [Use Markdown headings for each series. Write 1-2 flowing paragraphs per series blending recap, 'Tale of the Tape', and future stakes.]
        - The Dispatch Three Stars: [Exactly THREE stars TOTAL for the entire week.]
          * Format: **[1st/2nd/3rd] Star: [Player Name] ([Team])** - [G]G, [A]A, [Pts]Pts. - [Reasoning]. 
          * 1st Star: "The Clutch Performer" 
          * 2nd Star: "The Stat Sheet Stuffer" 
          * 3rd Star: "The Intangible Hero"
        - Length: Target 400-500 words. Keep it brutally tight but well-written.
        </format_requirements>
        """
        task_instruction = "Task: Generate the weekly Playoff wrap-up and preview report. Analyze the data to organically find the best headline narrative."

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