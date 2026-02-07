import os
import time
import pandas as pd
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import WebDriverException, InvalidSessionIdException
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# --- CONFIGURATION ---
HUB_URL = "https://www.dmhl.ca/stats#/533/scores?division_id=41979"
BOXSCORE_TEMPLATE = "https://www.dmhl.ca/stats#/533/game/{game_id}/boxscore"

# File Persistence
DATA_DIR = "data"
DETAILS_FILE = os.path.join(DATA_DIR, "game_details.csv")
MANIFEST_FILE = os.path.join(DATA_DIR, "games_manifest.csv")

def initialize_headless_browser():
    options = Options()
    options.add_argument("--headless=new") # Explicitly headless for CI/CD
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--no-sandbox")
    return webdriver.Chrome(options=options)

def format_event_record(game_id, event_type, team="N/A", desc="N/A", strength="N/A", period="N/A", time_val="N/A"):
    # Normalize team names to prevent "The Sahara" vs "the sahara"
    clean_team = str(team).strip().title().replace("'S", "'s") if team and team != "N/A" else "N/A"
    return {
        'GameID': game_id, 
        'EventType': event_type, 
        'Team': clean_team, 
        'Description': str(desc).strip(),
        'Strength': strength if strength else "", 
        'ScrapedAt': time.strftime("%Y-%m-%d"),
        'Period': period if period else "N/A", 
        'Time': time_val if time_val else "N/A"
    }

def scrape_division_manifest(driver):
    print(f"📡 Building Comprehensive Manifest...")
    driver.get(HUB_URL)
    try:
        WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.XPATH, "//main//table//tbody/tr[@role='article']")))
    except:
        return []

    for _ in range(12):
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(0.5)
    
    rows = driver.find_elements(By.XPATH, "//main//table//tbody/tr[@role='article']")
    manifest_data, seen_ids = [], set()
    
    for row in rows:
        try:
            cols = row.find_elements(By.TAG_NAME, "td")
            if len(cols) < 8: continue
            team_spans = cols[1].find_elements(By.CSS_SELECTOR, "span.d")
            if len(team_spans) < 2: continue
            url = cols[1].find_element(By.TAG_NAME, "a").get_dom_attribute("href")
            game_id = url.split("/game/")[1].split("?")[0].split("/")[0]
            if game_id in seen_ids: continue
            seen_ids.add(game_id)
            manifest_data.append({
                'GameID': game_id, 'Home': team_spans[0].text.strip(), 'Away': team_spans[1].text.strip(),
                'Division': cols[2].text.strip(), 'Score': cols[3].text.strip(), 'Date': cols[4].text.strip(),
                'Time': cols[5].text.strip(), 'Status': cols[6].text.strip(), 'Facility': cols[7].text.split("opens")[0].strip()
            })
        except: continue
            
    pd.DataFrame(manifest_data).to_csv(MANIFEST_FILE, index=False)
    print(f"✅ Manifest complete: {len(manifest_data)} games indexed.")
    return manifest_data

def scrape_detailed_boxscore(driver, game_id):
    print(f" | 🏒 Boxscore:", end=" ", flush=True)
    target_url = BOXSCORE_TEMPLATE.format(game_id=game_id)
    
    for attempt in range(3):
        driver.get(target_url)
        events = []
        try:
            WebDriverWait(driver, 10).until(EC.url_contains(str(game_id)))
            WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.XPATH, "//h3[text()='Scoring']")))
            time.sleep(2.5) # Allow Angular content to settle
            
            # 1. SCORES (Validation Anchor)
            scoring_table = driver.find_element(By.XPATH, "//h3[text()='Scoring']/following::table[1]")
            rows = scoring_table.find_elements(By.TAG_NAME, "tr")[1:]
            for row in rows:
                cols = row.find_elements(By.TAG_NAME, "td")
                if len(cols) >= 2 and cols[0].text.strip():
                    events.append(format_event_record(game_id, 'PeriodScore', team=cols[0].text, desc=cols[-1].text, period='Final'))

            if not events:
                print(f"(Empty retry {attempt+1})", end="", flush=True)
                continue

            # 2. ROSTERS (Guard: Must have player name)
            for side in ['left', 'right']:
                try:
                    side_div = driver.find_element(By.CSS_SELECTOR, f"div[ng-if*='{side}']")
                    team_name = side_div.find_element(By.TAG_NAME, "h3").text.replace('Player', '').replace('Goalie', '').strip()
                    for p in side_div.find_elements(By.CSS_SELECTOR, "a.person-inline"):
                        name = p.text.strip()
                        if name and name not in ["Totals", "Player", "Goaltender"]:
                            events.append(format_event_record(game_id, 'RosterAppearance', team=team_name, desc=name))
                except: continue

            # 3. GOALS (Guard: Must have team AND player name)
            try:
                for r in driver.find_elements(By.XPATH, "//h3[text()='Scoring Summary']/following::div[contains(@class, 'table-scroll')][1]//tbody/tr"):
                    c = r.find_elements(By.TAG_NAME, "td")
                    if len(c) >= 5:
                        team, desc = c[3].text.strip(), c[4].text.strip()
                        if team and desc and "No goals" not in desc:
                            events.append(format_event_record(game_id, 'Goal', team=team, desc=desc, strength=c[2].text, period=c[0].text, time_val=c[1].text))
            except: pass

            # 4. PENALTIES (Guard: Must have team AND type)
            try:
                for r in driver.find_elements(By.XPATH, "//h3[text()='Penalty Summary']/following::div[contains(@class, 'table-scroll')][1]//tbody/tr"):
                    c = r.find_elements(By.TAG_NAME, "td")
                    if len(c) >= 6:
                        team, p_type = c[3].text.strip(), c[2].text.strip()
                        if team and p_type and "No penalties" not in p_type:
                            desc = f"{p_type}: {c[4].text} ({c[5].text} mins)"
                            events.append(format_event_record(game_id, 'Penalty', team=team, desc=desc, period=c[0].text, time_val=c[1].text))
            except: pass

            # 5. OFFICIALS
            try:
                for row in driver.find_elements(By.XPATH, "//h3[text()='Officials']/following::table[1]//tr")[1:]:
                    cols = row.find_elements(By.TAG_NAME, "td")
                    if len(cols) >= 2 and cols[1].text.strip():
                        events.append(format_event_record(game_id, 'Official', desc=f"{cols[0].text.strip()}: {cols[1].text.strip()}"))
            except: pass

            print(f"{len(events)} events.")
            return events
        except: continue
            
    print("Failed.")
    return []

def run_scraping_pipeline():
    if not os.path.exists(DATA_DIR): os.makedirs(DATA_DIR)
    driver = initialize_headless_browser()
    try:
        manifest = scrape_division_manifest(driver)
        for game in manifest:
            gid = str(game['GameID'])
            if os.path.exists(DETAILS_FILE):
                if gid in pd.read_csv(DETAILS_FILE)['GameID'].astype(str).values: continue

            print(f"[{gid}] {game.get('Home')} vs {game.get('Away')}", end="")
            
            if str(game.get('Status')).strip().lower() == "forfeit":
                print(" 🏳️ Recording Forfeit...", end="")
                s_parts = str(game.get('Score')).split('-')
                h_score, a_score = (s_parts[0].strip(), s_parts[1].strip()) if len(s_parts) > 1 else ("0", "0")
                f_events = [
                    format_event_record(gid, 'PeriodScore', team=game['Home'], desc=h_score, period='Final'),
                    format_event_record(gid, 'PeriodScore', team=game['Away'], desc=a_score, period='Final'),
                    format_event_record(gid, 'Official', desc='Status: Official Forfeit')
                ]
                pd.DataFrame(f_events).to_csv(DETAILS_FILE, mode='a', header=not os.path.exists(DETAILS_FILE), index=False)
                print(" Done.")
                continue

            try:
                combined_events = scrape_detailed_boxscore(driver, gid)
                if combined_events:
                    pd.DataFrame(combined_events).to_csv(DETAILS_FILE, mode='a', header=not os.path.exists(DETAILS_FILE), index=False)
            except (InvalidSessionIdException, WebDriverException):
                driver.quit(); driver = initialize_headless_browser(); continue
    finally:
        driver.quit()

if __name__ == "__main__":
    run_scraping_pipeline()