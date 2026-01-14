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

def format_event(game_id, event_type, team="N/A", desc="N/A", strength="N/A", period="N/A", time_val="N/A"):
    """
    MASTER SCHEMA: Enforces a strict, identical column order for every single row.
    This prevents 'Final' from appearing in the Team column.
    """
    return {
        'GameID': game_id,
        'EventType': event_type,
        'Team': team,
        'Description': desc,
        'Strength': strength,
        'ScrapedAt': time.strftime("%Y-%m-%d"),
        'Period': period,
        'Time': time_val
    }

def scrape_hub(driver):
    """Scrapes the schedule hub for GameIDs and Arena context."""
    print(f"📡 Connecting to Schedule Hub...")
    driver.get(SCORES_URL)
    
    print("⏳ Loading full season list...")
    for i in range(12): 
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(1.0)
    
    try:
        WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.CSS_SELECTOR, "main table")))
    except: 
        print("❌ Hub Error: Table didn't load.")
        return []

    # PM Decision: Scoped to 'main' content to ignore the site-wide ticker
    rows = driver.find_elements(By.XPATH, "//main//table//tbody/tr[@role='article']")
    game_list, manifest_data, seen_ids = [], [], set()

    for row in rows:
        try:
            cols = row.find_elements(By.TAG_NAME, "td")
            if len(cols) < 8: continue

            link = cols[1].find_element(By.TAG_NAME, "a")
            url = link.get_dom_attribute("href")
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
    print(f" ↳ 👥 Team Stats:", end=" ", flush=True)
    driver.get(TEAM_STATS_TEMPLATE.format(game_id=game_id))
    
    try:
        WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.CSS_SELECTOR, ".tabs")))
    except: return []

    roster_events = []
    for side_idx in [0, 1]:
        try:
            team_tabs = driver.find_elements(By.CSS_SELECTOR, ".tabs.menubar-navigation > .tab")
            if len(team_tabs) <= side_idx: continue
            
            team_name = team_tabs[side_idx].text.strip()
            driver.execute_script("arguments[0].click();", team_tabs[side_idx])
            time.sleep(2) 

            # Targets visible table container to avoid ghost data
            container = driver.find_element(By.CSS_SELECTOR, "div.ng-scope:not(.ng-hide) div.table-scroll")
            rows = container.find_elements(By.CSS_SELECTOR, "tbody tr")
            
            for row in rows:
                cols = row.find_elements(By.TAG_NAME, "td")
                if len(cols) < 7: continue
                
                name_cell = cols[1]
                player_links = name_cell.find_elements(By.TAG_NAME, "a")
                player_name = player_links[0].text.strip() if player_links else name_cell.text.split("#")[0].strip()

                # DATA GUARD: Skip if name is empty
                if not player_name: continue

                roster_events.append(format_event(
                    game_id=game_id,
                    event_type='RosterAppearance',
                    team=team_name,
                    desc=player_name,
                    strength=cols[6].text.strip()
                ))
        except Exception as e:
            continue
    
    print(f"Captured {len(roster_events)} players.")
    return roster_events

def scrape_boxscore_spoke(driver, game):
    game_id = game['game_id']
    print(f" ↳ 🏒 Boxscore:", end=" ", flush=True)
    driver.get(game['url'])
    time.sleep(3)
    events = []

    # Get status text (textContent bypasses visibility issues)
    status_text = ""
    try:
        status_el = driver.find_element(By.CSS_SELECTOR, ".hero .d .bh-white")
        status_text = status_el.get_attribute("textContent").strip()
    except: pass

    try:
        # 1. SCORES
        score_rows = driver.find_elements(By.XPATH, "//div[not(@aria-hidden='true')]//h3[text()='Scoring']/following::table[1]//tbody/tr")
        for row in score_rows:
            cols = row.find_elements(By.TAG_NAME, "td")
            if len(cols) >= 5:
                team_name = cols[0].text.strip()
                if not team_name: continue # DATA GUARD
                
                score_val = cols[4].text.strip()
                desc = f"{score_val} (Forfeit)" if "Forfeit" in status_text else score_val
                events.append(format_event(
                    game_id=game_id, event_type='PeriodScore', team=team_name, desc=desc, period='Final'
                ))

        # 2. GOALS (XPath hardened to ignore table-fixed layout tables)
        goal_rows = driver.find_elements(By.XPATH, "//div[not(@aria-hidden='true')]//h3[text()='Scoring Summary']/following::div[contains(@class, 'table-scroll')][1]/div[not(contains(@class, 'table-fixed'))]//table/tbody/tr")
        for row in goal_rows:
            cols = row.find_elements(By.TAG_NAME, "td")
            if len(cols) >= 5:
                team_name = cols[3].text.strip()
                if not team_name: continue # DATA GUARD
                
                events.append(format_event(
                    game_id=game_id, event_type='Goal', team=team_name, desc=cols[4].text.strip(),
                    strength=cols[2].text.strip(), period=cols[0].text.strip(), time_val=cols[1].text.strip()
                ))

        # 3. PENALTIES (XPath hardened to ignore table-fixed layout tables)
        pen_rows = driver.find_elements(By.XPATH, "//div[not(@aria-hidden='true')]//h3[text()='Penalty Summary']/following::div[contains(@class, 'table-scroll')][1]/div[not(contains(@class, 'table-fixed'))]//table/tbody/tr")
        for row in pen_rows:
            cols = row.find_elements(By.TAG_NAME, "td")
            if len(cols) >= 4:
                team_name = cols[3].text.strip()
                if not team_name: continue # DATA GUARD
                
                events.append(format_event(
                    game_id=game_id, event_type='Penalty', team=team_name, desc=cols[4].text.strip(),
                    period=cols[0].text.strip(), time_val=cols[1].text.strip()
                ))

        # 4. OFFICIALS
        off_rows = driver.find_elements(By.XPATH, "//div[not(@aria-hidden='true')]//h3[text()='Officials']/following::table[1]//tbody/tr")
        for row in off_rows:
            cols = row.find_elements(By.TAG_NAME, "td")
            if len(cols) >= 2:
                name = cols[1].text.strip()
                if not name: continue # DATA GUARD
                events.append(format_event(
                    game_id=game_id, event_type='OfficialAssignment', desc=name, strength=cols[0].text.strip()
                ))

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