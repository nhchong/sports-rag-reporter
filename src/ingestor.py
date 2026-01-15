import os
import requests
import pandas as pd
from bs4 import BeautifulSoup
import time
from datetime import datetime

# --- CONFIGURATION ---
TICKET = 'L3NutYEhmS9PA0ScGKjzEwhg7-lYrTqD2qEBhfnESydZPPb_Ogns-l2hKOB2tcXWS3Gc_IygKfTDih6Qiy7tUXOd'
HEADERS = {
    'Authorization': f'ticket="{TICKET}"',
    'Origin': 'https://www.dmhl.ca',
    'Referer': 'https://www.dmhl.ca/',
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
}

DATA_DIR = "data"
DETAILS_FILE = os.path.join(DATA_DIR, "game_details.csv")
MANIFEST_FILE = os.path.join(DATA_DIR, "games_manifest.csv")

def fetch_game_partial(game_id):
    """Hits API once per game. Returns the 'content' HTML string."""
    url = f"https://web.api.digitalshift.ca/partials/stats/game/team-stats"
    params = {"game_id": game_id} # No side parameter needed, we get both at once
    try:
        response = requests.get(url, headers=HEADERS, params=params, timeout=10)
        if response.status_code == 200:
            return response.json().get("content", "")
        return None
    except Exception as e:
        print(f"❌ Connection Error: {e}")
        return None

def parse_combined_rosters(html_snippet, game_id):
    """Correctly identifies team names and players by parsing section-by-section."""
    soup = BeautifulSoup(html_snippet, 'html.parser')
    events = []
    
    # Each team has an <h3> followed by a div containing the table
    # We find all team headers
    team_sections = soup.find_all("h3")
    
    for section in team_sections:
        # Extract clean team name (e.g., '4 LINES Player' -> '4 LINES')
        team_name = section.get_text(strip=True).replace("Player", "").strip()
        
        # The table is inside the next div sibling
        table = section.find_next("table")
        if not table: continue
        
        rows = table.select("tbody tr")
        for row in rows:
            cols = row.find_all("td")
            if len(cols) < 7: continue
            
            p_name = cols[1].get_text(strip=True).split("#")[0].strip()
            if not p_name or p_name == "Totals": continue
            
            events.append({
                'GameID': game_id,
                'EventType': 'RosterAppearance',
                'Team': team_name,
                'Description': p_name,
                'Strength': cols[6].get_text(strip=True), # This captures PIMs
                'ScrapedAt': datetime.now().strftime("%Y-%m-%d"),
                'Period': 'N/A', 'Time': 'N/A'
            })
    return events

def run_full_ingestion():
    if not os.path.exists(MANIFEST_FILE):
        print("❌ Error: games_manifest.csv not found.")
        return

    manifest = pd.read_csv(MANIFEST_FILE)
    game_ids = manifest['GameID'].unique()
    
    print(f"🚀 API Ingestion: {len(game_ids)} games.")
    
    # Purge old corrupted data
    if os.path.exists(DETAILS_FILE): os.remove(DETAILS_FILE)

    all_data = []
    for i, game_id in enumerate(game_ids):
        print(f"[{i+1}/{len(game_ids)}] Processing {game_id}...", end=" ", flush=True)
        
        html = fetch_game_partial(game_id)
        if html:
            roster_data = parse_combined_rosters(html, game_id)
            all_data += roster_data
            print(f"✅ ({len(roster_data)} spots)")
        else:
            print("⚠️ Skipped")
        
        time.sleep(0.1)

    if all_data:
        pd.DataFrame(all_data).to_csv(DETAILS_FILE, index=False)
        print(f"\n✨ Database Rebuilt: {len(all_data)} clean entries.")

if __name__ == "__main__":
    run_full_ingestion()