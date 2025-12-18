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
# Division 41979 maps to 'Monday/Wednesday Low B' in the DMHL system
SCORES_URL = "https://www.dmhl.ca/stats#/533/scores?division_id=41979"
BOXSCORE_TEMPLATE = "https://www.dmhl.ca/stats#/533/game/{game_id}/boxscore"

DATA_DIR = "data"
DETAILS_FILE = os.path.join(DATA_DIR, "game_details.csv")
MANIFEST_FILE = os.path.join(DATA_DIR, "games_manifest.csv")

def setup_driver():
    """
    Initializes a Chrome instance with 'Stealth' settings.
    Headless mode allows the script to run in the background without a UI window.
    AutomationControlled is disabled to mimic a real human user.
    """
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    return webdriver.Chrome(options=options)

def scrape_hub(driver):
    """
    Acts as the 'Discovery' phase. 
    1. Grabs the high-level metadata (Arena, Date, Time) for every game.
    2. Collects the unique GameIDs to be used for deep-diving into boxscores.
    """
    driver.get(SCORES_URL)
    # Wait up to 15 seconds for the table to render (prevents 'ElementNotFound' errors)
    WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.TAG_NAME, "table")))
    time.sleep(3) # Extra buffer for dynamic JavaScript content

    rows = driver.find_elements(By.XPATH, "//table//tbody/tr")
    game_list, manifest, seen = [], [], set()

    for row in rows:
        try:
            # Locate links that contain the /game/ path
            links = row.find_elements(By.XPATH, ".//a[contains(@href, '/game/')]")
            if not links: continue
            
            # Parsing the URL to extract the unique ID (e.g., 1151048)
            gid = links[0].get_attribute("href").split("/game/")[1].split("/")[0].split("?")[0]
            if gid in seen: continue
            seen.add(gid)

            cols = row.find_elements(By.TAG_NAME, "td")
            # Store 'Contextual Data' - essential for the AI Reporter to know WHERE and WHEN
            manifest.append({
                'GameID': gid, 
                'Date': cols[0].text.strip(), 
                'Time': cols[1].text.strip(), 
                'Arena': cols[2].text.strip(), 
                'Home': cols[3].text.strip(), 
                'Away': cols[4].text.strip()
            })
            game_list.append({'game_id': gid, 'url': BOXSCORE_TEMPLATE.format(game_id=gid)})
        except: continue # Skip row if it's a header or malformed
    
    # Persistent storage for game metadata
    pd.DataFrame(manifest).to_csv(MANIFEST_FILE, index=False)
    return game_list

def scrape_spoke(driver, game):
    """
    The 'Deep Dive' phase. Uses 'Semantic Identification' to find tables.
    Instead of hardcoding row positions, we look for keywords like 'Scorer' or 'Infraction'.
    This makes the scraper robust against small website layout changes.
    """
    driver.get(game['url'])
    # Polite scraping: random delays mimic human browsing and prevent IP blocks
    time.sleep(random.uniform(1.5, 3))
    events, date = [], time.strftime("%Y-%m-%d")

    try:
        tables = driver.find_elements(By.TAG_NAME, "table")
        # filter(is_displayed) ignores the 'Ghost Tables' DigitalShift uses for sticky headers
        for table in [t for t in tables if t.is_displayed()]:
            try: hdr = table.find_element(By.TAG_NAME, "thead").text.lower()
            except: continue
            
            rows = table.find_elements(By.TAG_NAME, "tr")[1:] # Drop header row
            
            # Identifying the table type by checking headers
            if "scorer" in hdr: # Process Goals
                for r in rows:
                    c = r.find_elements(By.TAG_NAME, "td")
                    if len(c) >= 6: 
                        events.append({'GameID': game['game_id'], 'EventType': 'Goal', 'Period': c[0].text, 'Time': c[1].text, 'Strength': c[2].text, 'Team': c[3].text, 'Description': c[4].text, 'ScoreState': c[5].text, 'ScrapedAt': date})
            
            elif "infraction" in hdr: # Process Penalties
                for r in rows:
                    c = r.find_elements(By.TAG_NAME, "td")
                    if len(c) >= 6: 
                        events.append({'GameID': game['game_id'], 'EventType': 'Penalty', 'Period': c[0].text, 'Time': c[1].text, 'Strength': c[5].text, 'Team': c[3].text, 'Description': f"{c[2].text} - {c[4].text}", 'ScrapedAt': date})
            
            elif "1st" in hdr and "final" in hdr: # Process Period Scoring Summary
                for r in rows:
                    c = r.find_elements(By.TAG_NAME, "td")
                    if len(c) >= 5:
                        for idx, p in enumerate(['1st', '2nd', '3rd', 'Final']):
                            events.append({'GameID': game['game_id'], 'EventType': 'PeriodScore', 'Period': p, 'Team': c[0].text, 'Description': c[idx+1].text, 'ScrapedAt': date})
    except: pass
    return events

def main():
    """
    Execution Orchestrator. 
    Implements incremental scraping: only boxscores not yet in the details file are processed.
    """
    os.makedirs(DATA_DIR, exist_ok=True)
    driver = setup_driver()
    try:
        games = scrape_hub(driver)
        # Incremental logic: load existing IDs so we don't re-scrape the same data
        exist = set(pd.read_csv(DETAILS_FILE)['GameID'].astype(str)) if os.path.exists(DETAILS_FILE) else set()
        to_do = [g for g in games if g['game_id'] not in exist]
        
        for g in to_do:
            evs = scrape_spoke(driver, g)
            if evs:
                df = pd.DataFrame(evs)
                # Append mode: writing to CSV without overwriting previous games
                df.to_csv(DETAILS_FILE, mode='a', header=not os.path.exists(DETAILS_FILE), index=False)
    finally: driver.quit()

if __name__ == "__main__": main()