import os
import time
import pandas as pd
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# --- CONFIGURATION (Unchanged) ---
SCORES_URL = "https://www.dmhl.ca/stats#/533/scores?division_id=41979"
BOXSCORE_TEMPLATE = "https://www.dmhl.ca/stats#/533/game/{game_id}/boxscore"
TEAM_STATS_TEMPLATE = "https://www.dmhl.ca/stats#/533/game/{game_id}/team-stats"

DATA_DIR = "data"
DETAILS_FILE = os.path.join(DATA_DIR, "game_details.csv")
MANIFEST_FILE = os.path.join(DATA_DIR, "games_manifest.csv")

def setup_driver():
    options = Options()
    options.add_argument("--headless=new") 
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    return webdriver.Chrome(options=options)

def format_event(game_id, event_type, team="N/A", desc="N/A", strength="N/A", period="N/A", time_val="N/A"):
    return {
        'GameID': game_id, 'EventType': event_type, 'Team': team, 'Description': desc,
        'Strength': strength, 'ScrapedAt': time.strftime("%Y-%m-%d"), 'Period': period, 'Time': time_val
    }

def get_processed_ids():
    if not os.path.exists(DETAILS_FILE): return set()
    try:
        df = pd.read_csv(DETAILS_FILE)
        return set(df['GameID'].astype(str).unique())
    except: return set()

def scrape_hub(driver):
    print(f"📡 Connecting to Schedule Hub...")
    driver.get(SCORES_URL)
    for i in range(12): 
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(0.5)
    
    rows = driver.find_elements(By.XPATH, "//main//table//tbody/tr[@role='article']")
    game_list, manifest_data, seen_ids = [], [], set()

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
                'GameID': game_id, 'Home': team_spans[0].text.strip(), 'Away': team_spans[1].text.strip(),
                'Date': cols[4].text.strip(), 'Arena': cols[7].text.split("opens")[0].strip()
            })
            game_list.append({'game_id': game_id, 'url': BOXSCORE_TEMPLATE.format(game_id=game_id)})
        except: continue
    pd.DataFrame(manifest_data).to_csv(MANIFEST_FILE, index=False)
    print(f"✅ Hub complete. Found {len(game_list)} games.")
    return game_list

def scrape_roster_spoke(driver, game_id):
    """HARDENED: Uses Angular 'ng-hide' awareness to prevent roster mirroring."""
    print(f" ↳ 👥 Team Stats:", end=" ", flush=True)
    driver.get(TEAM_STATS_TEMPLATE.format(game_id=game_id))
    
    try:
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CSS_SELECTOR, ".tabs")))
    except: return []

    roster_events = []
    for side_idx in [0, 1]:
        try:
            # Click Team Tab
            tabs = driver.find_elements(By.CSS_SELECTOR, ".tabs.menubar-navigation > .tab")
            team_name = tabs[side_idx].text.strip()
            driver.execute_script("arguments[0].click();", tabs[side_idx])
            
            time.sleep(2.5) # Wait for Angular state transition
            
            # Target the container that is physically visible (not hidden by Angular)
            container = driver.find_element(By.CSS_SELECTOR, "div.ng-scope:not(.ng-hide) .table-scroll")
            rows = container.find_elements(By.CSS_SELECTOR, "tbody tr")
            
            for row in rows:
                cols = row.find_elements(By.TAG_NAME, "td")
                if len(cols) < 7: continue
                p_name = cols[1].text.split("#")[0].strip()
                if p_name and p_name != "Totals":
                    roster_events.append(format_event(game_id, 'RosterAppearance', team_name, p_name, strength=cols[6].text.strip()))
        except: continue
    
    print(f"Captured {len(roster_events)} players.")
    return roster_events

def scrape_boxscore_spoke(driver, game):
    """ORIGINAL LOGIC: Preserved from your working version."""
    game_id = game['game_id']
    print(f" ↳ 🏒 Boxscore:", end=" ", flush=True)
    driver.get(game['url'])
    time.sleep(2)
    events = []
    try:
        # Scoring Summary (Hardened XPaths)
        score_rows = driver.find_elements(By.XPATH, "//h3[text()='Scoring']/following::table[1]//tbody/tr")
        for row in score_rows:
            cols = row.find_elements(By.TAG_NAME, "td")
            if len(cols) >= 5:
                events.append(format_event(game_id, 'PeriodScore', cols[0].text.strip(), cols[4].text.strip(), period='Final'))

        goal_rows = driver.find_elements(By.XPATH, "//h3[text()='Scoring Summary']/following::div[contains(@class, 'table-scroll')][1]//table/tbody/tr")
        for row in goal_rows:
            cols = row.find_elements(By.TAG_NAME, "td")
            if len(cols) >= 5:
                events.append(format_event(game_id, 'Goal', cols[3].text.strip(), cols[4].text.strip(), cols[2].text.strip(), cols[0].text.strip(), cols[1].text.strip()))

        pen_rows = driver.find_elements(By.XPATH, "//h3[text()='Penalty Summary']/following::div[contains(@class, 'table-scroll')][1]//table/tbody/tr")
        for row in pen_rows:
            cols = row.find_elements(By.TAG_NAME, "td")
            if len(cols) >= 4:
                events.append(format_event(game_id, 'Penalty', cols[3].text.strip(), cols[4].text.strip(), period=cols[0].text.strip(), time_val=cols[1].text.strip()))
        
        off_rows = driver.find_elements(By.XPATH, "//h3[text()='Officials']/following::table[1]//tbody/tr")
        for row in off_rows:
            cols = row.find_elements(By.TAG_NAME, "td")
            if len(cols) >= 2:
                events.append(format_event(game_id, 'OfficialAssignment', desc=cols[1].text.strip(), strength=cols[0].text.strip()))
    except: pass
    print(f"Captured {len(events)} events.")
    return events

def main():
    if not os.path.exists(DATA_DIR): os.makedirs(DATA_DIR)
    processed_ids = get_processed_ids()
    driver = setup_driver()
    try:
        all_games = scrape_hub(driver)
        new_games = [g for g in all_games if str(g['game_id']) not in processed_ids]
        if not new_games:
            print("✨ Everything is up to date.")
            return

        for i, game in enumerate(new_games):
            print(f"[{i+1}/{len(new_games)}] Game {game['game_id']}")
            roster = scrape_roster_spoke(driver, game['game_id'])
            boxscore = scrape_boxscore_spoke(driver, game)
            combined = roster + boxscore
            if combined:
                pd.DataFrame(combined).to_csv(DETAILS_FILE, mode='a', header=not os.path.exists(DETAILS_FILE), index=False)
    finally:
        driver.quit()

if __name__ == "__main__":
    main()