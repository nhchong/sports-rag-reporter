import os
import sys
import time
import pandas as pd
from datetime import datetime
from google import genai  # Ensure you ran: pip install google-genai
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# --- CONFIGURATION ---
TEAM_STATS_FILE = "data/team_stats.csv"
PLAYER_STATS_FILE = "data/player_stats.csv"
DETAILS_FILE = "data/game_details.csv"
MANIFEST_FILE = "data/games_manifest.csv"

# 1. Setup Client with the NEW SDK syntax
# Note: Ensure your .env has GOOGLE_API_KEY or GEMINI_API_KEY
api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")

if not api_key:
    print("❌ Error: No API Key found. Please set GOOGLE_API_KEY in your .env file.")
    sys.exit(1)

client = genai.Client(api_key=api_key)

def get_data_payload():
    """Aggregates all CSV data and reverses logs for recency."""
    try:
        # Check if files exist before reading
        for f in [TEAM_STATS_FILE, PLAYER_STATS_FILE, DETAILS_FILE, MANIFEST_FILE]:
            if not os.path.exists(f):
                raise FileNotFoundError(f"Missing data file: {f}")

        standings = pd.read_csv(TEAM_STATS_FILE).to_string()
        leaders = pd.read_csv(PLAYER_STATS_FILE).head(15).to_string()
        
        # 1. Load Schedule Manifest (Context for dates/locations)
        manifest_df = pd.read_csv(MANIFEST_FILE)
        # Reverse manifest to show newest games at the top
        manifest = manifest_df.iloc[::-1].head(10).to_string()
        
        # 2. Load Detailed Logs and REVERSE THEM
        # This puts the absolute newest events at the very top of the list
        details_df = pd.read_csv(DETAILS_FILE).tail(100) # Increased tail for better context
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
    Write a weekly recap for the DMHL (recreational hockey league).
    
    CRITICAL INSTRUCTION: 
    The data below is sorted with the NEWEST information at the top. 
    Focus your 'Headlines' section on the games and dates listed at the TOP of the Manifest and Logs.
    
    DATA SOURCE:
    {data_text}

    TASK:
    1. THE HEADLINES: '32 Thoughts' style bullets. Use the Arena name and Date from the manifest 
       to ground the stories (e.g., 'Monday night at Mattamy...').
    2. THE TAPE STUDY: Analyze team discipline vs production based on the PIMs and goals.
    3. WEEKLY AWARDS: 'Clutch Performer', 'Sin Bin Resident', 'Under-the-Radar Star'.

    TONE: Professional, gritty, and exciting.
    """

    try:
        # Use a supported model name (e.g., 'gemini-2.0-flash')
        response = client.models.generate_content(
            model="gemini-2.5-flash", 
            contents=prompt
        )
        report_text = response.text
        
        print("\n" + "="*60)
        print(f"🏒 DMHL WEEKLY INSIDER REPORT - {datetime.now().strftime('%Y-%m-%d')} 🏒")
        print("="*60 + "\n")
        print(report_text)
        
        # Ensure data directory exists
        os.makedirs("data", exist_ok=True)
        with open("data/weekly_report.txt", "w") as f:
            f.write(report_text)
        print(f"\n✅ Report saved to data/weekly_report.txt")

    except Exception as e:
        print(f"❌ Gemini API Error: {e}")

if __name__ == "__main__":
    generate_report()