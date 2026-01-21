import os
import time
import requests
import pandas as pd
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import WebDriverException, InvalidSessionIdException

# --- CONFIGURATION ---
TICKET = "L3NutYEhmS9PA0ScGKjzEwhg7-lYrTqD2qEBhfnESydZPPb_Ogns-l2hKOB2tcXWS3Gc_IygKfTDih6Qiy7tUXOd"
SCORES_URL = "https://www.dmhl.ca/stats#/533/scores?division_id=41979"
BOXSCORE_TEMPLATE = "https://www.dmhl.ca/stats#/533/game/{game_id}/boxscore"
ROSTER_API_URL = "https://web.api.digitalshift.ca/partials/stats/game/team-stats"

DATA_DIR = "data"
DETAILS_FILE = os.path.join(DATA_DIR, "game_details.csv")
MANIFEST_FILE = os.path.join(DATA_DIR, "games_manifest.csv")

API_HEADERS = {
    'Accept': 'application/json, text/plain, */*',
    'Authorization': f'ticket="{TICKET}"',
    'Origin': 'https://www.dmhl.ca',
    'Referer': 'https://www.dmhl.ca/',
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
}

def setup_driver():
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--no-sandbox")
    return webdriver.Chrome(options=options)

def format_event(game_id, event_type, team="N/A", desc="N/A", strength="N/A", period="N/A", time_val="N/A"):
    # Standardize team names to Title Case for standings consistency
    clean_team = str(team).strip().title().replace("'S", "'s") if team and team != "N/A" else "N/A"
    return {
        'GameID': game_id, 'EventType': event_type, 'Team': clean_team, 'Description': desc,
        'Strength': strength if strength else "", 'ScrapedAt': time.strftime("%Y-%m-%d"),
        'Period': period if period else "N/A", 'Time': time_val if time_val else "N/A"
    }

def scrape_hub_manifest(driver):
    print(f"📡 Building Comprehensive Manifest for Division 41979...")
    driver.get(SCORES_URL)
    time.sleep(5)
    for _ in range(12):
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(0.5)
    
    rows = driver.find_elements(By.XPATH, "//main//table//tbody/tr[@role='article']")
    manifest_data, seen_ids = [], set()
    for row in rows:
        try:
            cols = row.find_elements(By.TAG_NAME, "td")
            if len(cols) < 8: continue
            url = cols[1].find_element(By.TAG_NAME, "a").get_dom_attribute("href")
            game_id = url.split("/game/")[1].split("?")[0].split("/")[0]
            if game_id in seen_ids: continue
            seen_ids.add(game_id)
            
            team_spans = cols[1].find_elements(By.CSS_SELECTOR, "span.d")
            manifest_data.append({
                'GameID': game_id,
                'Home': team_spans[0].text.strip(),
                'Away': team_spans[1].text.strip(),
                'Score': cols[2].text.strip(),
                'Status': cols[3].text.strip(),
                'Date': cols[4].text.strip(),
                'Time': cols[5].text.strip(),
                'Facility': cols[6].text.strip(),
                'Arena': cols[7].text.split("opens")[0].strip()
            })
        except: continue
    pd.DataFrame(manifest_data).to_csv(MANIFEST_FILE, index=False)
    print(f"✅ Manifest complete: {len(manifest_data)} games.")
    return manifest_data

def ingest_rosters_api(game_id):
    print(f" ↳ 👥 API Roster:", end=" ", flush=True)
    try:
        res = requests.get(ROSTER_API_URL, headers=API_HEADERS, params={'game_id': game_id})
        if res.status_code != 200: return []
        soup = BeautifulSoup(res.json().get('content', ''), 'html.parser')
        roster_events = []
        for side in ['left', 'right']:
            side_div = soup.find('div', {'ng-if': f"ctrl.side == '{side}'"})
            if not side_div: continue
            header = side_div.find('h3', class_='h4')
            team_name = header.get_text().replace('Player', '').replace('Goalie', '').strip() if header else "Unknown"
            seen = set()
            for link in side_div.find_all('a', class_='person-inline'):
                name = link.get_text().strip()
                if name and name not in seen and name not in ["Totals", "Player", "Goaltender"]:
                    seen.add(name)
                    roster_events.append(format_event(game_id, 'RosterAppearance', team=team_name, desc=name))
        print(f"{len(roster_events)} members.", end="")
        return roster_events
    except: return []

def scrape_boxscore_selenium(driver, game_id):
    """Refined Selenium extraction with 'is_displayed' filters to block phantom rows."""
    print(f" | 🏒 Boxscore:", end=" ", flush=True)
    driver.get(BOXSCORE_TEMPLATE.format(game_id=game_id))
    time.sleep(3)
    events = []

    try:
        # 1. SCORING TABLE (Summary)
        try:
            scoring_table = driver.find_element(By.XPATH, "//h3[text()='Scoring']/following::table[1]")
            rows = scoring_table.find_elements(By.TAG_NAME, "tr")[1:]
            for row in rows:
                if not row.is_displayed(): continue
                cols = row.find_elements(By.TAG_NAME, "td")
                if len(cols) >= 2 and cols[0].text.strip():
                    events.append(format_event(game_id, 'PeriodScore', team=cols[0].text, desc=cols[-1].text, period='Final'))
        except: pass

        # 2. SCORING SUMMARY (Goals)
        try:
            # Use XPATH to find only the FIRST table-scroll div to avoid duplicates
            goal_rows = driver.find_elements(By.XPATH, "//h3[text()='Scoring Summary']/following::div[contains(@class, 'table-scroll')][1]//tbody/tr")
            for r in goal_rows:
                if not r.is_displayed() or "No goals recorded" in r.text: continue
                c = r.find_elements(By.TAG_NAME, "td")
                # Ensure the 'Team' column (index 3) is not empty
                if len(c) >= 5 and c[3].text.strip():
                    events.append(format_event(game_id, 'Goal', team=c[3].text, desc=c[4].text, strength=c[2].text, period=c[0].text, time_val=c[1].text))
        except: pass

        # 3. PENALTY SUMMARY
        try:
            pen_rows = driver.find_elements(By.XPATH, "//h3[text()='Penalty Summary']/following::div[contains(@class, 'table-scroll')][1]//tbody/tr")
            for r in pen_rows:
                if not r.is_displayed() or "No penalties recorded" in r.text: continue
                c = r.find_elements(By.TAG_NAME, "td")
                # Ensure the 'Team' column (index 3) is not empty
                if len(c) >= 5 and c[3].text.strip():
                    desc = f"{c[2].text}: {c[4].text} ({c[5].text} mins)"
                    events.append(format_event(game_id, 'Penalty', team=c[3].text, desc=desc, period=c[0].text, time_val=c[1].text))
        except: pass

        # 4. OFFICIALS
        try:
            official_table = driver.find_element(By.XPATH, "//h3[text()='Officials']/following::table[1]")
            off_rows = official_table.find_elements(By.TAG_NAME, "tr")[1:]
            for row in off_rows:
                if not row.is_displayed(): continue
                cols = row.find_elements(By.TAG_NAME, "td")
                if len(cols) >= 2 and cols[1].text.strip():
                    events.append(format_event(game_id, 'Official', desc=f"{cols[0].text}: {cols[1].text}"))
        except: pass

    except Exception as e:
        if "session" in str(e).lower(): raise e
        
    print(f"{len(events)} events.")
    return events

def main():
    if not os.path.exists(DATA_DIR): os.makedirs(DATA_DIR)
    driver = setup_driver()
    try:
        if not os.path.exists(MANIFEST_FILE):
            manifest = scrape_hub_manifest(driver)
        else:
            manifest = pd.read_csv(MANIFEST_FILE).to_dict('records')

        for game in manifest:
            processed = set()
            if os.path.exists(DETAILS_FILE):
                try: processed = set(pd.read_csv(DETAILS_FILE)['GameID'].astype(str).unique())
                except: pass

            gid = str(game['GameID'])
            if gid in processed: continue

            print(f"[{gid}] {game.get('Home', 'N/A')} vs {game.get('Away', 'N/A')}", end="")
            try:
                combined = ingest_rosters_api(gid) + scrape_boxscore_selenium(driver, gid)
                if not combined:
                    combined = [format_event(gid, 'EmptyGame', desc='Forfeit or Cancelled')]
                pd.DataFrame(combined).to_csv(DETAILS_FILE, mode='a', header=not os.path.exists(DETAILS_FILE), index=False)
            except (InvalidSessionIdException, WebDriverException):
                print("\n🔄 Restarting Chrome session...")
                try: driver.quit()
                except: pass
                driver = setup_driver()
                continue
    finally:
        driver.quit()

if __name__ == "__main__":
    main()