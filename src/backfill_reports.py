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
POSTS_DIR = "docs/_posts"

# --- LOGO MAPPING FOR TEASERS ---
LOGO_MAP = {
    "The Shockers": "/assets/images/theshockers.png",
    "The Sahara": "/assets/images/thesahara.png",
    "Don Cherry's": "/assets/images/doncherrys.png",
    "Flat-Earthers": "/assets/images/flatearthers.png",
    "Muffin Men": "/assets/images/muffinmen.png",
    "4 Lines": "/assets/images/4lines.png"
}

def generate_last_ten_thursdays():
    end_date = datetime(2026, 1, 29) 
    thursdays = []
    for i in range(10):
        target = end_date - timedelta(weeks=i)
        thursdays.append(target.strftime('%Y-%m-%d'))
    return thursdays

BACKFILL_DATES = ["2026-02-05"]

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
    print(f"🚀 Starting Headline-Enabled Backfill: {len(BACKFILL_DATES)} Reports...")
    os.makedirs(POSTS_DIR, exist_ok=True)

    system_instruction = """
    You are the Senior Columnist for 'The Low B Dispatch,' a data-driven hockey newsletter. You cover the DMHL, which stands for the Downtown Mens Hockey League. The league is based in Toronto. Most of the players are between the ages of 25 and 35. Games are played on Monday and Wednesday. The division that you are covering is Monday/Wednesday Low B. 
    
    VOICE & STYLE:
    - ANALYTICAL: Use data to substantiate claims. 
    - AUTHENTIC: Speak to the community as a peer but avois any unprofessional locker-room tone.
    - ZERO FLUFF: Avoid generic PR language.
    - COMPELLING NARRATIVE: Similar to the media outlet, The Athletic
    - LIGHT-HEARTED BUT PROFESSIONAL: Similar the Spittin Chiclets podcast. 
    - PLAYER-FOCUSED: Much like the media outlet, the Player's Tribune. 
    - MATURE WIT: No 'hockey bro' lingo. Use sharp, sophisticated humor. 

    NARRATIVE STRATEGY:
    1. THE BIG STORY: Start with shifts in the Standings. Use the 'team_stats' to explain why a team moved up or down.
    2. DATA-DRIVEN INSIGHTS: Highlight specific player discrepancies.
    3. THE OFFICIALS: Comment on officiating volume and whether or not it impacted the game. 
    4. VIBE & VENUE: Contextualize results based on arena/time. Paint a visual by adding in weather data on that specific day. 
    5. 80/20 Rule: 80% COVERAGE is Focused on the 'weekly_play_by_play' events and 20% CONTEXT: Ground results in standings and leaders.
    6. Make sure to weave in a summary of every game that happened this week. Every team has to be mentioned. 
    7. Use the 'player_stats' to highlight specific player performances. Use the 'weekly_play_by_play' to highlight specific game events.
    8. Use the 'schedule_and_arenas' to highlight specific arena and time of day of the games.
    9. Use the 'official_assignments' to highlight specific referees and linesmen only if they called a lot of penalities or no penalities at all.
    10. Use the 'game_details' to highlight specific game events. Weave in the game details into the narrative.
    11. If there is a big story, make sure to weave it in to the narrative.

    STYLE GUIDELINES:
    STRUCTURE & LENGTH:
    - WORD LIMIT: Approximately 200 words.

    THE THREE STARS:
    Must be strictly based on weekly data.
    - 1st Star: Most points, favoring goals. Emphasis on important goals. 
    - 2nd Star: Second most points, emphasis on goals. 
    - 3rd Star: The 'Productive Agitator' who contributes on the scoresheet and as a team contirbuter or the top goalie. 

    OUTPUT FORMAT:
    - Your response MUST begin with a unique 'Headline' and 'Subline' on the first two lines.
    - Followed by the newsletter body using Markdown (## Headings). Use > blockquotes for specific data callouts. No emojis.
    """

    for date_str in BACKFILL_DATES:
        target_date = datetime.strptime(date_str, '%Y-%m-%d')
        json_brief = get_historical_brief(target_date)

        if not json_brief:
            continue

        print(f"🎙️ Generating Dispatch for {date_str}...")

        try:
            response = client.models.generate_content(
                model="gemini-2.5-flash", 
                contents=[system_instruction, f"DATA BRIEF:\n{json_brief}\n\nTask: Generate a historical newsletter dispatch."]
            )
            report_text = response.text

            # --- DYNAMIC TEASER LOGIC ---
            for team, logo_path in LOGO_MAP.items():
                if team in report_text:
                    teaser_logo = logo_path
                    break

            # --- DYNAMIC HEADLINE/SUBLINE PARSING ---
            lines = report_text.strip().split('\n')
            generated_headline = lines[0].strip() if len(lines) > 0 else f"Weekly Dispatch: {target_date.strftime('%B %d, %Y')}"
            generated_subline = lines[1].strip() if len(lines) > 1 else "Data-driven analysis of the DMHL."
            # The actual body content starts after the headline/subline
            actual_content = "\n".join(lines[2:]).strip()
            
            # JEKYLL FILENAME CONVENTION
            filename = f"{date_str}-dispatch.md"
            filepath = os.path.join(POSTS_DIR, filename)
            
            # JEKYLL FRONT MATTER
            front_matter = f"""---
layout: single
title: "{generated_headline}"
excerpt: "{generated_subline}"
date: {date_str}
header:
  teaser: "{teaser_logo}"
author_profile: true
---

"""
            
            with open(filepath, "w") as f:
                f.write(front_matter + actual_content)

            print(f"✅ Created: {filename} with teaser: {teaser_logo}")
            time.sleep(12) # Slightly faster for backfill but still safe

        except Exception as e:
            print(f"❌ Error during AI generation for {date_str}: {e}")
            time.sleep(30)

    print("\n🏁 Backfill complete.")

if __name__ == "__main__":
    run_backfill()