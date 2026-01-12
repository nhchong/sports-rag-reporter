import os
import time
import random
import pandas as pd
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# --- CONFIGURATION ---
SCORES_URL = "https://www.dmhl.ca/stats#/533/scores?division_id=41979"
BOXSCORE_TEMPLATE = "https://www.dmhl.ca/stats#/533/game/{game_id}/boxscore"
TEAM_STATS_TEMPLATE = "https://www.dmhl.ca/stats#/533/game/{game_id}/team-stats"

DATA_DIR = "data"
DETAILS_FILE = os.path.join(DATA_DIR, "game_details.csv")
MANIFEST_FILE = os.path.join(DATA_DIR, "games_manifest.csv")

def setup_driver():
    """Configures a stealthy background browser with a desktop viewport."""
    options = Options()
    options.add_argument("--headless=new") 
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    return webdriver.Chrome(options=options)

def scrape_hub(driver):
    """Scrapes the schedule hub for GameIDs and Arena context."""
    print(f"📡 Connecting to Schedule Hub...")
    driver.get(SCORES_URL)
    
    print("⏳ Loading full season list...")
    for i in range(12): 
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(1.0)
    
    try:
        WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.TAG_NAME, "table")))
    except: 
        print("❌ Hub Error: Table didn't load.")
        return []

    rows = driver.find_elements(By.XPATH, "//table//tbody/tr[@role='article']")
    game_list, manifest_data, seen_ids = [], [], set()

    for row in rows:
        try:
            cols = row.find_elements(By.TAG_NAME, "td")
            if len(cols) < 8: continue

            link = cols[1].find_element(By.TAG_NAME, "a")
            url = link.get_attribute("href")
            game_id = url.split("/game/")[1].split("?")[0].split("/")[0]

            if game_id in seen_ids: continue
            seen_ids.add(game_id)

            team_spans = cols[1].find_elements(By.CSS_SELECTOR, "span.d")
            raw_arena = cols[7].text.strip()
            clean_arena = raw_arena.replace("opens in new window", "").strip()

            manifest_data.append({
                'GameID': game_id, 'Home': team_spans[0].text.strip(), 'Away': team_spans[1].text.strip(),
                'Date': cols[4].text.strip(), 'Time': cols[5].text.strip(), 'Arena': clean_arena, 'Score': cols[3].text.strip()
            })
            game_list.append({'game_id': game_id, 'url': BOXSCORE_TEMPLATE.format(game_id=game_id)})
        except: continue

    os.makedirs(DATA_DIR, exist_ok=True)
    pd.DataFrame(manifest_data).to_csv(MANIFEST_FILE, index=False)
    print(f"✅ Hub complete. Found {len(game_list)} total games.")
    return game_list

def scrape_roster_spoke(driver, game_id):
    """Forces Angular data-binding by waiting for visible rows."""
    print(f" ↳ 👥 Team Stats:", end=" ", flush=True)
    driver.get(TEAM_STATS_TEMPLATE.format(game_id=game_id))
    
    try:
        WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.CSS_SELECTOR, ".menubar-navigation")))
    except: return []

    roster_events = []
    for side_idx in [0, 1]:
        try:
            team_tabs = driver.find_elements(By.CSS_SELECTOR, ".tabs.menubar-navigation > .tab")
            if len(team_tabs) <= side_idx: continue
            
            team_name = team_tabs[side_idx].text.strip()
            driver.execute_script("arguments[0].click();", team_tabs[side_idx])
            time.sleep(2.0)

            visible_container = driver.find_element(By.CSS_SELECTOR, "div.ng-scope:not(.ng-hide)")
            if "No player stats recorded" in visible_container.text:
                continue

            WebDriverWait(driver, 10).until(
                lambda d: len(visible_container.find_elements(By.CSS_SELECTOR, "tr[ng-repeat*='e in'] .person-inline")) > 0
            )

            rows = visible_container.find_elements(By.CSS_SELECTOR, "tbody tr[ng-repeat*='e in']")
            for row in rows:
                cols = row.find_elements(By.TAG_NAME, "td")
                if len(cols) < 7: continue 
                
                name_el = row.find_elements(By.CLASS_NAME, "person-inline")
                if name_el and name_el[0].text.strip():
                    roster_events.append({
                        'GameID': game_id, 'EventType': 'RosterAppearance', 'Team': team_name,
                        'Description': name_el[0].text.strip(), 'Strength': cols[6].text.strip(), 
                        'ScrapedAt': time.strftime("%Y-%m-%d")
                    })
        except: continue
    
    print(f"Captured {len(roster_events)} players.")
    return roster_events

def scrape_boxscore_spoke(driver, game):
    """Updated Boxscore: Added Data Guards to prevent empty/ghost rows."""
    game_id = game['game_id']
    print(f" ↳ 🏒 Boxscore:", end=" ", flush=True)
    driver.get(game['url'])
    time.sleep(3)
    events, current_date = [], time.strftime("%Y-%m-%d")

    status_text = ""
    try: status_text = driver.find_element(By.CSS_SELECTOR, ".hero .bh-white").text.strip()
    except: pass

    try:
        # 1. SCORES - Guard: Check for Team Name
        score_rows = driver.find_elements(By.XPATH, "//h3[text()='Scoring']/following::table[1]//tbody/tr")
        for row in score_rows:
            cols = row.find_elements(By.TAG_NAME, "td")
            if len(cols) >= 5:
                team_name = cols[0].text.strip()
                if team_name: # ONLY process if team name is not blank
                    score_val = cols[4].text.strip()
                    desc = f"{score_val} (Forfeit)" if "Forfeit" in status_text else score_val
                    events.append({
                        'GameID': game_id, 'EventType': 'PeriodScore', 'Period': 'Final',
                        'Team': team_name, 'Description': desc, 'ScrapedAt': current_date
                    })

        # 2. GOALS - Guard: Check for Team Name
        goal_rows = driver.find_elements(By.XPATH, "//h3[text()='Scoring Summary']/following::div[contains(@class, 'table-scroll')][1]//tbody/tr")
        for row in goal_rows:
            cols = row.find_elements(By.TAG_NAME, "td")
            if len(cols) >= 5:
                team_col = cols[3].text.strip()
                if team_col: # ONLY process if team column is not blank
                    events.append({
                        'GameID': game_id, 'EventType': 'Goal', 'Period': cols[0].text.strip(),
                        'Time': cols[1].text.strip(), 'Strength': cols[2].text.strip(),
                        'Team': team_col, 'Description': cols[4].text.strip(), 'ScrapedAt': current_date
                    })

        # 3. PENALTIES - Guard: Check for Team Name
        pen_rows = driver.find_elements(By.XPATH, "//h3[text()='Penalty Summary']/following::div[contains(@class, 'table-scroll')][1]//tbody/tr")
        for row in pen_rows:
            cols = row.find_elements(By.TAG_NAME, "td")
            if len(cols) >= 4:
                team_col = cols[3].text.strip()
                if team_col: # ONLY process if team column is not blank
                    events.append({
                        'GameID': game_id, 'EventType': 'Penalty', 'Period': cols[0].text.strip(),
                        'Time': cols[1].text.strip(), 'Team': team_col,
                        'Description': cols[4].text.strip(), 'ScrapedAt': current_date
                    })

        # 4. OFFICIALS - Guard: Check for Name
        try:
            off_rows = driver.find_elements(By.XPATH, "//h3[text()='Officials']/following::table[1]//tbody/tr")
            for row in off_rows:
                cols = row.find_elements(By.TAG_NAME, "td")
                if len(cols) >= 2:
                    name = cols[1].text.strip()
                    if name: # ONLY process if official name is not blank
                        events.append({
                            'GameID': game_id, 
                            'EventType': 'OfficialAssignment', 
                            'Period': 'N/A',
                            'Team': 'N/A', 
                            'Description': name, 
                            'Strength': cols[0].text.strip(), 
                            'ScrapedAt': current_date
                        })
        except: pass 

    except Exception as e:
        pass
    
    print(f"Captured {len(events)} events.")
    return events

def main():
    if not os.path.exists(DATA_DIR): os.makedirs(DATA_DIR)
    if os.path.exists(DETAILS_FILE): os.remove(DETAILS_FILE)
    
    driver = setup_driver()
    try:
        all_games = scrape_hub(driver)
        if all_games:
            print(f"✨ Starting full season scrape ({len(all_games)} games)...")
            for i, game in enumerate(all_games):
                print(f"\n[{i+1}/{len(all_games)}] Processing Game {game['game_id']}")
                roster = scrape_roster_spoke(driver, game['game_id'])
                boxscore = scrape_boxscore_spoke(driver, game)
                
                combined = roster + boxscore
                if combined:
                    pd.DataFrame(combined).to_csv(DETAILS_FILE, mode='a', header=not os.path.exists(DETAILS_FILE), index=False)
            print("\n🏁 Full season scrape complete.")
    finally:
        driver.quit()

if __name__ == "__main__":
    main()