import pandas as pd
from google import genai
import os
import sys
import time
from datetime import datetime

# --- CONFIGURATION ---
TEAM_STATS_FILE = "data/team_stats.csv"
PLAYER_STATS_FILE = "data/player_stats.csv"
DETAILS_FILE = "data/game_details.csv"
MANIFEST_FILE = "data/games_manifest.csv"

# 1. Setup Client
api_key = os.getenv("GOOGLE_API_KEY")
client = genai.Client(api_key=api_key)

def get_data_payload():
    """Aggregates all CSV data and reverses logs for recency."""
    try:
        standings = pd.read_csv(TEAM_STATS_FILE).to_string()
        leaders = pd.read_csv(PLAYER_STATS_FILE).head(15).to_string()
        
        # 1. Load Schedule Manifest (Context for dates/locations)
        manifest_df = pd.read_csv(MANIFEST_FILE)
        # Reverse manifest to show newest games at the top
        manifest = manifest_df.iloc[::-1].head(10).to_string()
        
        # 2. Load Detailed Logs and REVERSE THEM
        # This puts the absolute newest events at the very top of the list
        details_df = pd.read_csv(DETAILS_FILE).tail(60) 
        recent_events = details_df.iloc[::-1].to_string() 
        
        current_date = datetime.now().strftime("%B %d, %Y")
        
        return (
            f"TODAY'S DATE: {current_date}\n\n"
            f"SCHEDULE MANIFEST (NEWEST GAMES FIRST):\n{manifest}\n\n"
            f"STANDINGS:\n{standings}\n\n"
            f"SCORING LEADERS:\n{leaders}\n\n"
            f"DETAILED GAME LOGS (NEWEST EVENTS FIRST):\n{recent_events}"
        )
    except Exception as e:
        print(f"❌ Error reading data: {e}")
        return None

def generate_report():
    data_text = get_data_payload()
    if not data_text: return

    print("🤖 Generating DMHL Weekly Report (Prioritizing Newest Games)...")
    
    prompt = f"""
    You are a prestige hockey columnist for The Athletic. 
    Write a weekly recap for the DMHL.
    
    CRITICAL INSTRUCTION: 
    The data below is sorted with the NEWEST information at the top. 
    Focus your 'Headlines' section on the games and dates listed at the TOP of the Manifest and Logs.
    
    DATA SOURCE:
    {data_text}

    TASK:
    1. THE HEADLINES: '32 Thoughts' style bullets. Use the Arena name and Date from the manifest 
       to ground the stories (e.g., 'Monday night at Mattamy...').
    2. THE TAPE STUDY: Analyze team discipline vs production.
    3. WEEKLY AWARDS: 'Clutch Performer', 'Sin Bin Resident', 'Under-the-Radar Star'.

    TONE: Professional, gritty, and exciting.
    """

    try:
        response = client.models.generate_content(model="gemini-2.5-flash", contents=prompt)
        report_text = response.text
        
        print("\n" + "="*60)
        print(f"🏒 DMHL WEEKLY INSIDER REPORT - {datetime.now().strftime('%Y-%m-%d')} 🏒")
        print("="*60 + "\n")
        print(report_text)
        
        with open("data/weekly_report.txt", "w") as f:
            f.write(report_text)
        print(f"\n✅ Report saved to data/weekly_report.txt")

    except Exception as e:
        print(f"❌ Gemini API Error: {e}")

if __name__ == "__main__":
    generate_report()