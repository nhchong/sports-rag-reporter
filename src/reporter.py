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

def build_reporting_brief(days_back=7):
    """
    PM Decision: Contextual Intelligence.
    Aggregates the weekly 'tape' with discretionary official metadata.
    """
    try:
        standings = pd.read_csv(TEAM_STATS_FILE).to_dict(orient='records')
        leaders = pd.read_csv(PLAYER_STATS_FILE).head(15).to_dict(orient='records')
        
        details_df = pd.read_csv(DETAILS_FILE)
        details_df['ScrapedAt'] = pd.to_datetime(details_df['ScrapedAt'])
        
        latest_data_date = details_df['ScrapedAt'].max()
        cutoff_date = latest_data_date - pd.Timedelta(days=days_back)
        
        recent_details = details_df[details_df['ScrapedAt'] >= cutoff_date].copy()
        
        # Capture officials for discretionary use
        officials = recent_details[recent_details['EventType'] == 'OfficialAssignment']
        ref_map = officials.groupby('GameID')['Description'].apply(list).to_dict()

        recent_details['ScrapedAt'] = recent_details['ScrapedAt'].dt.strftime('%Y-%m-%d')
        
        manifest_df = pd.read_csv(MANIFEST_FILE)
        recent_game_ids = recent_details['GameID'].unique().astype(str)
        recent_manifest = manifest_df[manifest_df['GameID'].astype(str).isin(recent_game_ids)]

        brief = {
            "league_meta": {
                "name": "Downtown Men's Hockey League (DMHL)",
                "division": "Monday/Wednesday Low B (Division 533)",
                "context": "Non-contact, ages 22-35, Toronto-based competitive rec league.",
                "arenas": ["Upper Canada College (UCC)", "Mattamy Athletic Centre", "St. Michael's Arena"],
                "report_date": "January 15, 2026"
            },
            "season_snapshot": {
                "standings": standings,
                "overall_leaderboard": leaders
            },
            "this_week_tape": {
                "manifest": recent_manifest.to_dict(orient='records'),
                "play_by_play": recent_details.to_dict(orient='records'),
                "referee_assignments": ref_map
            }
        }
        return json.dumps(brief, indent=2)
    except Exception as e:
        print(f"❌ Error building brief: {e}")
        return None

def generate_report():
    json_brief = build_reporting_brief(days_back=7) 
    if not json_brief: return

    print("🎙️ Producing 'The Low B Dispatch'...")
    
    # PM Decision: Narrative Persona Synthesis
    system_instruction = """
    You are the voice of 'The Low B Dispatch.' You provide the definitive, self-aware coverage of DMHL Division 41979 (Monday/Wednesday Low B). 

    CORE MANDATE:
    - 90% FOCUS: Devote the vast majority of the report to the games played THIS CALENDAR WEEK (Monday and Wednesday). Use the play-by-play logs to reconstruct the narrative of those specific nights.
    - BEER LEAGUE REALITY: Constantly acknowledge the absurdity of using high-level data analysis and professional-grade reporting for a league where guys are gassed after a 45-second shift. 

    TONE & AUDIENCE:
    - NO BULLSHIT: Your audience is 20-35-year-old Toronto hockey players. They can sniff out corporate AI-speak or "hockey-bro" caricatures instantly. Be direct, a bit cynical, and authentic.
    - PEER ANALYSIS: Treat players like peers, not professionals. No forced slang. If a team spent the whole night in the box, they didn't "jeopardize the tactical system"—they just killed their team’s Tuesday morning productivity at the office.

    NARRATIVE CONTEXT:
    1. THE TORONTO FACTOR: Reference the specific arenas (UCC, Mattamy, St. Mikes). Incorporate the mid-January Toronto weather (the slush in the parking lot, the temperature drop outside, the feeling of walking into a warm rink from a -10°C wind).
    2. DATA EXTRACTION CHALLENGE: Dig into the 'this_week_tape' to find meaningful (but ridiculous) patterns:
        - THE LATE-NIGHT FADE: Did teams in the 10:30 PM starts collapse in the 3rd period compared to the 8:00 PM games?
        - ARENA TRENDS: Does the data suggest one rink is a 'shooting gallery' while another is a 'penalty trap'?
        - THE CARDIO CHECK: Who scored goals in the final 2 minutes of the 3rd?
    3. OFFICIALS: Mention the refs only if the data shows they actually impacted the flow (e.g., a massive spike in penalties compared to the league average).

    FORMAT:
    - THE OPENER: Set the scene (The weather, the parking struggle, and a self-deprecating nod to why we are analyzing Low B stats like it's the Stanley Cup).
    - THE RUNDOWN: 5-6 numbered points strictly on this Monday and Wednesday’s games. 
    - THE STANDINGS LADDER: How this specific week’s results shifted the hunt for the top seed.
    - THE THREE STARS:
        - 1st Star: The week's actual MVP.
        - 2nd Star: A clutch goal or someone who just showed up on time for a late-night puck drop.
        - 3rd Star: The 'Villain' or 'Donkey'—someone whose stats show they were a liability (e.g., high PIMs in a close loss).
    """

    prompt = f"DATA BRIEF:\n{json_brief}\n\nTask: Generate this week's edition of The Low B Dispatch."

    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash", 
            contents=[system_instruction, prompt]
        )
        report_text = response.text
        
        print("\n" + "═"*60)
        print(f"🏒  THE LOW B DISPATCH | {datetime.now().strftime('%B %d, %Y')}  🏒")
        print("═"*60 + "\n")
        print(report_text)
        
        with open("data/weekly_report.md", "w") as f:
            f.write(report_text)
        print(f"\n✅ Report saved to data/weekly_report.md")

    except Exception as e:
        print(f"❌ Gemini API Error: {e}")

if __name__ == "__main__":
    generate_report()