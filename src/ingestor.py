import requests
import pandas as pd
import time
import os  # Added missing import
from bs4 import BeautifulSoup

# --- CONFIGURATION ---
TICKET = "L3NutYEhmS9PA0ScGKjzEwhg7-lYrTqD2qEBhfnESydZPPb_Ogns-l2hKOB2tcXWS3Gc_IygKfTDih6Qiy7tUXOd"
BASE_URL = "https://web.api.digitalshift.ca/partials/stats/game/team-stats"

HEADERS = {
    'Accept': 'application/json, text/plain, */*',
    'Authorization': f'ticket="{TICKET}"',
    'Origin': 'https://www.dmhl.ca',
    'Referer': 'https://www.dmhl.ca/',
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Mobile Safari/537.36'
}

def get_game_rosters(game_id):
    params = {'game_id': game_id}
    try:
        response = requests.get(BASE_URL, headers=HEADERS, params=params)
        if response.status_code != 200:
            print(f"❌ API Error {response.status_code}")
            return []

        json_data = response.json()
        html_content = json_data.get('content', '')
        soup = BeautifulSoup(html_content, 'html.parser')
        
        all_events = []
        print(f"\n🏒 GAME ROSTERS: {game_id}")
        print("="*50)

        # Target the Home (left) and Away (right) blocks
        for side in ['left', 'right']:
            side_div = soup.find('div', {'ng-if': f"ctrl.side == '{side}'"})
            if not side_div: continue

            # Extract Team Name
            header = side_div.find('h3', class_='h4')
            raw_title = header.get_text().strip() if header else "Unknown Team"
            team_name = raw_title.replace('Player', '').replace('Goalie', '').strip()

            # Extract Names using a Set to block the 'table-fixed' duplicates
            player_links = side_div.find_all('a', class_='person-inline')
            unique_names = []
            seen = set()

            for link in player_links:
                name = link.get_text().strip()
                if name and name not in seen:
                    unique_names.append(name)
                    seen.add(name)

            # --- PRINT TO SCREEN ---
            print(f"{side.upper()} TEAM: {team_name}")
            print(f"Count: {len(unique_names)} players")
            if unique_names:
                for i in range(0, len(unique_names), 4):
                    print("  • " + ", ".join(unique_names[i:i+4]))
            print("-" * 50)

            for name in unique_names:
                all_events.append({
                    'GameID': game_id,
                    'EventType': 'RosterAppearance',
                    'Team': team_name,
                    'Description': name,
                    'ScrapedAt': time.strftime("%Y-%m-%d"),
                    'Strength': 'N/A', 'Period': 'N/A', 'Time': 'N/A'
                })
        
        return all_events

    except Exception as e:
        print(f"❌ Error: {e}")
        return []

# --- RUN ---
game_id = "1176619"
roster_data = get_game_rosters(game_id)

if roster_data:
    # Ensure data directory exists
    if not os.path.exists('data'):
        os.makedirs('data')
        
    df = pd.DataFrame(roster_data)
    # Save/Append to CSV
    df.to_csv('data/game_details.csv', mode='a', header=not os.path.exists('data/game_details.csv'), index=False)
    print(f"\n✅ Data successfully appended to data/game_details.csv")