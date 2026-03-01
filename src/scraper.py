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
    """Initializes a headless Chrome instance for CI/CD compatibility."""
    options = Options()
    options.add_argument("--headless=new") 
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--no-sandbox")
    return webdriver.Chrome(options=options)

def format_event_record(game_id, event_type, team="N/A", desc="N/A", strength="N/A", period="N/A", time_val="N/A"):
    """
    Standardizes the record format for all scraped events.
    Ensures team names are consistently cased for relational joins.
    """
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
    """
    Fetches the high-level league schedule and merges it with local Commissioner insights.
    Logic ensures that manual human enrichment is preserved across automated scrape cycles.
    """
    print(f"📡 Building Comprehensive Manifest...")
    driver.get(HUB_URL)
    try:
        WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.XPATH, "//main//table//tbody/tr[@role='article']")))
    except:
        return []

    # Angular settle time: Ensures dynamic content is fully rendered
    for _ in range(12):
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(0.5)
    
    rows = driver.find_elements(By.XPATH, "//main//table//tbody/tr[@role='article']")
    manifest_data, seen_ids = [], set()
    
    for row in rows:
        try:
            cols = row.find_elements(By.TAG_NAME, "td")
            if len(cols) < 10: continue # index 9 is GT column
            
            team_spans = cols[1].find_elements(By.CSS_SELECTOR, "span.d")
            if len(team_spans) < 2: continue
            
            url = cols[1].find_element(By.TAG_NAME, "a").get_dom_attribute("href")
            game_id = url.split("/game/")[1].split("?")[0].split("/")[0]
            if game_id in seen_ids: continue
            seen_ids.add(game_id)
            
            # Map raw league 'GT' tags to standardized logical anchors
            gt_raw = cols[9].text.strip()
            game_type = "Playoffs" if gt_raw == "PO" else "Regular Season"

            manifest_data.append({
                'GameID': game_id, 
                'Home': team_spans[0].text.strip(), 
                'Away': team_spans[1].text.strip(),
                'Division': cols[2].text.strip(), 
                'GameType': game_type,            
                'Score': cols[3].text.strip(), 
                'Date': cols[4].text.strip(),
                'Time': cols[5].text.strip(), 
                'Status': cols[6].text.strip(), 
                'Facility': cols[7].text.split("opens")[0].strip()
            })
        except: continue
            
    # --- DATA INTEGRITY: Commissioner Note Preservation ---
    # We treat the existing manifest as the secondary source of truth for 'Notes'
    new_df = pd.DataFrame(manifest_data)
    
    if os.path.exists(MANIFEST_FILE):
        old_df = pd.read_csv(MANIFEST_FILE)
        
        # Standardize GameID types to prevent 'False Misses' during the map
        old_df['GameID'] = old_df['GameID'].astype(str)
        new_df['GameID'] = new_df['GameID'].astype(str)
        
        if 'Notes' in old_df.columns:
            # Map existing notes back to the new manifest using GameID as the Unique Key.
            # This 'Left Join' ensures manual insights survive the schedule update.
            notes_map = old_df.set_index('GameID')['Notes'].to_dict()
            new_df['Notes'] = new_df['GameID'].map(notes_map).fillna("")
            print("📝 Preserved existing Commissioner notes.")
        else:
            new_df['Notes'] = ""
    else:
        new_df['Notes'] = ""

    new_df.to_csv(MANIFEST_FILE, index=False)
    print(f"✅ Manifest complete: {len(new_df)} games indexed.")
    return manifest_data

def scrape_detailed_boxscore(driver, game_id):
    """
    Deep-dives into a specific game's boxscore.
    Uses established CSS/XPath patterns to extract rosters, goals, and penalties.
    """
    print(f" | 🏒 Boxscore:", end=" ", flush=True)
    target_url = BOXSCORE_TEMPLATE.format(game_id=game_id)
    
    for attempt in range(3):
        driver.get(target_url)
        events = []
        try:
            WebDriverWait(driver, 10).until(EC.url_contains(str(game_id)))
            WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.XPATH, "//h3[text()='Scoring']")))
            time.sleep(2.5)
            
            # 1. FINAL SCORES
            scoring_table = driver.find_element(By.XPATH, "//h3[text()='Scoring']/following::table[1]")
            rows = scoring_table.find_elements(By.TAG_NAME, "tr")[1:]
            for row in rows:
                cols = row.find_elements(By.TAG_NAME, "td")
                if len(cols) >= 2 and cols[0].text.strip():
                    events.append(format_event_record(game_id, 'PeriodScore', team=cols[0].text, desc=cols[-1].text, period='Final'))

            if not events:
                print(f"(Empty retry {attempt+1})", end="", flush=True)
                continue

            # 2. ROSTER APPEARANCES
            for side in ['left', 'right']:
                try:
                    side_div = driver.find_element(By.CSS_SELECTOR, f"div[ng-if*='{side}']")
                    team_name = side_div.find_element(By.TAG_NAME, "h3").text.replace('Player', '').replace('Goalie', '').strip()
                    for p in side_div.find_elements(By.CSS_SELECTOR, "a.person-inline"):
                        name = p.text.strip()
                        if name and name not in ["Totals", "Player", "Goaltender"]:
                            events.append(format_event_record(game_id, 'RosterAppearance', team=team_name, desc=name))
                except: continue

            # 3. GOAL SUMMARY
            try:
                for r in driver.find_elements(By.XPATH, "//h3[text()='Scoring Summary']/following::div[contains(@class, 'table-scroll')][1]//tbody/tr"):
                    c = r.find_elements(By.TAG_NAME, "td")
                    if len(c) >= 5:
                        team, desc = c[3].text.strip(), c[4].text.strip()
                        if team and desc and "No goals" not in desc:
                            events.append(format_event_record(game_id, 'Goal', team=team, desc=desc, strength=c[2].text, period=c[0].text, time_val=c[1].text))
            except: pass

            # 4. PENALTY SUMMARY
            try:
                for r in driver.find_elements(By.XPATH, "//h3[text()='Penalty Summary']/following::div[contains(@class, 'table-scroll')][1]//tbody/tr"):
                    c = r.find_elements(By.TAG_NAME, "td")
                    if len(c) >= 6:
                        team, p_type = c[3].text.strip(), c[2].text.strip()
                        if team and p_type and "No penalties" not in p_type:
                            desc = f"{p_type}: {c[4].text} ({c[5].text} mins)"
                            events.append(format_event_record(game_id, 'Penalty', team=team, desc=desc, period=c[0].text, time_val=c[1].text))
            except: pass

            # 5. ASSIGNED OFFICIALS
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
    """Execution entry point: coordinates the manifest build and boxscore deep-scrape."""
    if not os.path.exists(DATA_DIR): os.makedirs(DATA_DIR)
    driver = initialize_headless_browser()
    try:
        manifest = scrape_division_manifest(driver)
        for game in manifest:
            gid = str(game['GameID'])
            
            # Skip games already in the database to optimize run-time
            if os.path.exists(DETAILS_FILE):
                if gid in pd.read_csv(DETAILS_FILE)['GameID'].astype(str).values: continue

            print(f"[{gid}] {game.get('Home')} vs {game.get('Away')}", end="")
            
            # Edge Case: Handle Forfeits without deep-scraping empty boxscores
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

            # Core Boxscore Extraction
            try:
                combined_events = scrape_detailed_boxscore(driver, gid)
                if combined_events:
                    pd.DataFrame(combined_events).to_csv(DETAILS_FILE, mode='a', header=not os.path.exists(DETAILS_FILE), index=False)
            except (InvalidSessionIdException, WebDriverException):
                # Resilience: Restart browser session if connection hangs
                driver.quit(); driver = initialize_headless_browser(); continue
    finally:
        driver.quit()

if __name__ == "__main__":
    run_scraping_pipeline()