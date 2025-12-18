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
STANDINGS_URL = "https://www.dmhl.ca/stats#/533/standings?division_id=41979&render=division"
BOXSCORE_TEMPLATE = "https://www.dmhl.ca/stats#/533/game/{game_id}/boxscore"

DATA_DIR = "data"
DETAILS_FILE = os.path.join(DATA_DIR, "game_details.csv")
STANDINGS_FILE = os.path.join(DATA_DIR, "standings.csv")
MANIFEST_FILE = os.path.join(DATA_DIR, "games_manifest.csv")

def setup_driver():
    """Configures a stealthy Chrome driver with modern headless compatibility."""
    options = Options()
    # Using 'new' headless mode is more stable on macOS and avoids certain bot-detection
    options.add_argument("--headless=new") 
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    
    # Selenium Manager automatically handles the driver path
    return webdriver.Chrome(options=options)

def get_existing_game_ids():
    """Reads the CSV to find which games we already have to enable incremental scraping."""
    if not os.path.exists(DETAILS_FILE):
        return set()
    try:
        df = pd.read_csv(DETAILS_FILE)
        return set(df['GameID'].astype(str).unique())
    except Exception:
        return set()

def scrape_hub(driver):
    """Scrapes the schedule to build a 'Manifest' of game metadata using 10-column logic."""
    print(f"📡 Connecting to Schedule Hub...")
    driver.get(SCORES_URL)
    
    try:
        WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.TAG_NAME, "table")))
        time.sleep(3)
    except Exception as e:
        print(f"❌ Hub Error: Table failed to load. {e}")
        return []

    # Use role='article' to target only the actual game rows in the table
    rows = driver.find_elements(By.XPATH, "//table//tbody/tr[@role='article']")
    game_list, manifest_data, seen_ids = [], [], set()

    print(f" ↳ Scanning {len(rows)} rows for game data...")
    for row in rows:
        try:
            cols = row.find_elements(By.TAG_NAME, "td")
            # Ensure the row has the full 10 columns we expect
            if len(cols) < 10: continue

            # 1. Extract GameID from the link in column index 1 (Home vs Away)
            link = cols[1].find_element(By.TAG_NAME, "a")
            url = link.get_attribute("href")
            game_id = url.split("/game/")[1].split("?")[0].split("/")[0]

            if game_id in seen_ids: continue
            seen_ids.add(game_id)

            # 2. Extract Team Names - Using 'span.d' to get clean desktop text (avoiding mobile duplicates)
            team_spans = cols[1].find_elements(By.CSS_SELECTOR, "span.d")
            home_team = team_spans[0].text.strip()
            away_team = team_spans[1].text.strip()

            # 3. Build Manifest - Mapping to your 10-column structure
            manifest_data.append({
                'GameID': game_id,
                'Home': home_team,           # Index 1 (Split)
                'Away': away_team,           # Index 1 (Split)
                'Division': cols[2].text.strip(),
                'Score': cols[3].text.strip(),
                'Date': cols[4].text.strip(),
                'Time': cols[5].text.strip(),
                'Actions': cols[6].text.strip(),
                'Facility': cols[7].text.strip(),
                'Rink': cols[8].text.strip(),
                'GT': cols[9].text.strip()
            })

            game_list.append({
                'game_id': game_id,
                'url': BOXSCORE_TEMPLATE.format(game_id=game_id)
            })
        except: continue

    save_manifest(manifest_data)
    print(f"✅ Found {len(game_list)} valid games.")
    return game_list

def save_manifest(new_data):
    """Saves the high-level game info while avoiding duplicates."""
    if not new_data: return

    if os.path.exists(MANIFEST_FILE):
        existing = pd.read_csv(MANIFEST_FILE)
        existing_ids = set(existing['GameID'].astype(str))
        new_data = [d for d in new_data if str(d['GameID']) not in existing_ids]

    if new_data:
        df = pd.DataFrame(new_data)
        df.to_csv(MANIFEST_FILE, mode='a' if os.path.exists(MANIFEST_FILE) else 'w', 
                  header=not os.path.exists(MANIFEST_FILE), index=False)
        print(f"📝 Added {len(new_data)} games to Manifest.")

def scrape_spoke(driver, game):
    """Extracts boxscore events including Goals, Penalties, and Period Scores."""
    url, game_id = game['url'], game['game_id']
    print(f" ↳ Scraping Game {game_id}...", end=" ")
    
    driver.get(url)
    time.sleep(random.uniform(1.5, 3))
    events, current_date = [], time.strftime("%Y-%m-%d")

    try:
        tables = driver.find_elements(By.TAG_NAME, "table")
        for table in tables:
            # Skip hidden tables and tables with no data rows
            if not table.is_displayed(): continue
            rows = table.find_elements(By.TAG_NAME, "tr")
            if len(rows) < 2: continue

            try:
                header_text = table.find_element(By.TAG_NAME, "thead").text.lower()
            except: continue

            # --- MATCH: GOALS ---
            if "scorer" in header_text:
                for row in rows[1:]:
                    cols = row.find_elements(By.TAG_NAME, "td")
                    if len(cols) >= 6:
                        events.append({
                            'GameID': game_id, 'EventType': 'Goal', 'Period': cols[0].text.strip(),
                            'Time': cols[1].text.strip(), 'Strength': cols[2].text.strip(),
                            'Team': cols[3].text.strip(), 'Description': cols[4].text.strip(),
                            'ScoreState': cols[5].text.strip(), 'ScrapedAt': current_date
                        })

            # --- MATCH: PENALTIES ---
            elif "infraction" in header_text:
                for row in rows[1:]:
                    cols = row.find_elements(By.TAG_NAME, "td")
                    if len(cols) >= 6:
                        events.append({
                            'GameID': game_id, 'EventType': 'Penalty', 'Period': cols[0].text.strip(),
                            'Time': cols[1].text.strip(), 'Strength': cols[5].text.strip(),
                            'Team': cols[3].text.strip(), 'Description': f"{cols[2].text.strip()} - {cols[4].text.strip()}",
                            'ScrapedAt': current_date
                        })

            # --- MATCH: PERIOD SCORES ---
            elif "1st" in header_text and "final" in header_text:
                for row in rows[1:]:
                    cols = row.find_elements(By.TAG_NAME, "td")
                    if len(cols) >= 5:
                        team = cols[0].text.strip()
                        for idx, p_label in enumerate(['1st', '2nd', '3rd', 'Final']):
                            events.append({
                                'GameID': game_id, 'EventType': 'PeriodScore', 'Period': p_label,
                                'Team': team, 'Description': cols[idx+1].text.strip(), 'ScrapedAt': current_date
                            })
    except Exception as e:
        print(f"⚠️ Error: {e}")
    
    print(f"Collected {len(events)} events.")
    return events

def save_new_events(new_data):
    """Enforces schema consistency and appends new events to disk."""
    if not new_data: return
    
    df = pd.DataFrame(new_data)
    master_columns = ['GameID', 'EventType', 'Period', 'Time', 'Strength', 'Team', 'Description', 'ScoreState', 'ScrapedAt']
    
    for col in master_columns:
        if col not in df.columns:
            df[col] = None 
            
    df = df[master_columns]
    file_exists = os.path.exists(DETAILS_FILE)
    df.to_csv(DETAILS_FILE, mode='a', header=not file_exists, index=False)

def main():
    os.makedirs(DATA_DIR, exist_ok=True)
    existing_ids = get_existing_game_ids()
    print(f"📚 History loaded. Found {len(existing_ids)} previously scraped games.")

    driver = setup_driver()
    try:
        all_games = scrape_hub(driver)
        games_to_scrape = [g for g in all_games if g['game_id'] not in existing_ids]

        if games_to_scrape:
            print(f"🚀 Processing {len(games_to_scrape)} NEW games...")
            for i, game in enumerate(games_to_scrape):
                print(f"[{i+1}/{len(games_to_scrape)}]", end=" ")
                events = scrape_spoke(driver, game)
                if events:
                    save_new_events(events)
            print("🎉 Batch complete.")
        else:
            print("zzz No new games found. Your data is up to date.")
    finally:
        driver.quit()

if __name__ == "__main__":
    main()