import os
import time
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
    options = Options()
    options.add_argument("--headless=new") 
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    return webdriver.Chrome(options=options)

def format_event(game_id, event_type, team="N/A", desc="N/A", strength="N/A", period="N/A", time_val="N/A"):
    # Standardize team names to Title Case for standings consistency
    clean_team = str(team).strip().title().replace("'S", "'s") if team else "N/A"
    return {
        'GameID': game_id, 'EventType': event_type, 'Team': clean_team, 'Description': desc,
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
            
            url_el = cols[1].find_elements(By.TAG_NAME, "a")
            if not url_el: continue
            
            url = url_el[0].get_dom_attribute("href")
            game_id = url.split("/game/")[1].split("?")[0].split("/")[0]
            if game_id in seen_ids: continue
            
            team_spans = cols[1].find_elements(By.CSS_SELECTOR, "span.d")
            if not team_spans[0].text.strip(): continue 

            seen_ids.add(game_id)
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
    """HARDENED: Uses State-Change Detection to prevent roster mirroring."""
    print(f" ↳ 👥 Team Stats:", end=" ", flush=True)
    driver.get(TEAM_STATS_TEMPLATE.format(game_id=game_id))
    
    try:
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CSS_SELECTOR, ".tabs")))
    except: return []

    roster_events = []
    last_team_first_player = None 

    for side_idx in [0, 1]:
        try:
            tabs = driver.find_elements(By.CSS_SELECTOR, ".tabs.menubar-navigation > .tab")
            team_name = tabs[side_idx].text.strip()
            driver.execute_script("arguments[0].click();", tabs[side_idx])
            
            # WAIT FOR CONTENT SWAP: Ensures Angular has updated the text from the previous tab
            if last_team_first_player:
                try:
                    WebDriverWait(driver, 5).until(
                        lambda d: d.find_element(By.CSS_SELECTOR, "div.ng-scope:not(.ng-hide) tbody tr td:nth-child(2)").text.strip() != last_team_first_player
                    )
                except:
                    time.sleep(1)

            container = driver.find_element(By.CSS_SELECTOR, "div.ng-scope:not(.ng-hide) .table-scroll")
            rows = container.find_elements(By.CSS_SELECTOR, "tbody tr")
            
            if rows:
                current_first_player = rows[0].find_elements(By.TAG_NAME, "td")[1].text.split("#")[0].strip()
                last_team_first_player = current_first_player

                for row in rows:
                    cols = row.find_elements(By.TAG_NAME, "td")
                    if len(cols) < 7: continue
                    p_name = cols[1].text.split("#")[0].strip()
                    
                    if p_name and p_name not in ["Totals", "Player", "Goaltender"]:
                        roster_events.append(format_event(
                            game_id, 'RosterAppearance', team_name, p_name, strength=cols[6].text.strip()
                        ))
        except: continue
    
    print(f"Captured {len(roster_events)} players.")
    return roster_events

def scrape_boxscore_spoke(driver, game):
    game_id = game['game_id']
    print(f" ↳ 🏒 Boxscore:", end=" ", flush=True)
    driver.get(game['url'])
    time.sleep(2)
    events = []
    try:
        # 1. Final Scores
        score_rows = driver.find_elements(By.XPATH, "//h3[text()='Scoring']/following::table[1]//tbody/tr")
        for row in score_rows:
            cols = row.find_elements(By.TAG_NAME, "td")
            if len(cols) >= 5 and cols[0].text.strip():
                events.append(format_event(game_id, 'PeriodScore', cols[0].text.strip(), cols[4].text.strip(), period='Final'))

        # 2. Goals
        goal_rows = driver.find_elements(By.XPATH, "//h3[text()='Scoring Summary']/following::div[contains(@class, 'table-scroll')][1]//table/tbody/tr")
        for row in goal_rows:
            cols = row.find_elements(By.TAG_NAME, "td")
            if len(cols) >= 5 and cols[4].text.strip():
                events.append(format_event(game_id, 'Goal', cols[3].text.strip(), cols[4].text.strip(), cols[2].text.strip(), cols[0].text.strip(), cols[1].text.strip()))

        # 3. Penalties
        pen_rows = driver.find_elements(By.XPATH, "//h3[text()='Penalty Summary']/following::div[contains(@class, 'table-scroll')][1]//table/tbody/tr")
        for row in pen_rows:
            cols = row.find_elements(By.TAG_NAME, "td")
            if len(cols) >= 4 and cols[3].text.strip():
                events.append(format_event(game_id, 'Penalty', cols[3].text.strip(), cols[4].text.strip(), period=cols[0].text.strip(), time_val=cols[1].text.strip()))
        
        # 4. Officials
        off_rows = driver.find_elements(By.XPATH, "//h3[text()='Officials']/following::table[1]//tbody/tr")
        for row in off_rows:
            cols = row.find_elements(By.TAG_NAME, "td")
            if len(cols) >= 2 and cols[1].text.strip():
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