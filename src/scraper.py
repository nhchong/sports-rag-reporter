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
MANIFEST_FILE = os.path.join(DATA_DIR, "games_manifest.csv")

def setup_driver():
    """Configures a stealthy Chrome driver with modern headless compatibility."""
    options = Options()
    options.add_argument("--headless=new")  # Modern headless mode avoids detection
    options.add_argument("--window-size=1920,1080")  # Full viewport prevents mobile layout
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-blink-features=AutomationControlled")  # Hides automation flags
    options.add_argument("user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
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
    """
    Hub-and-spoke pattern: Scrapes the schedule page to build a manifest of all games.
    Returns list of game URLs to scrape individually (the 'spokes').
    """
    print(f"📡 Connecting to Schedule Hub...")
    driver.get(SCORES_URL)
    try:
        WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.TAG_NAME, "table")))
        time.sleep(3)  # Allow dynamic content to render
    except Exception as e:
        print(f"❌ Hub Error: Table failed to load. {e}")
        return []

    # Use role='article' to target only actual game rows (filters out header/empty rows)
    rows = driver.find_elements(By.XPATH, "//table//tbody/tr[@role='article']")
    game_list, manifest_data, seen_ids = [], [], set()

    for row in rows:
        try:
            cols = row.find_elements(By.TAG_NAME, "td")
            if len(cols) < 10: continue  # Skip incomplete rows

            # Extract game ID from the URL in the link
            link = cols[1].find_element(By.TAG_NAME, "a")
            url = link.get_attribute("href")
            game_id = url.split("/game/")[1].split("?")[0].split("/")[0]

            if game_id in seen_ids: continue  # Deduplicate within this scrape session
            seen_ids.add(game_id)

            # 'span.d' targets desktop-only spans (avoids mobile duplicate text)
            team_spans = cols[1].find_elements(By.CSS_SELECTOR, "span.d")
            home_team = team_spans[0].text.strip()
            away_team = team_spans[1].text.strip()

            manifest_data.append({
                'GameID': game_id,
                'Home': home_team,
                'Away': away_team,
                'Division': cols[2].text.strip(),
                'Score': cols[3].text.strip(),
                'Date': cols[4].text.strip(),
                'Time': cols[5].text.strip(),
                'Actions': cols[6].text.strip(),
                'Facility': cols[7].text.strip().replace("opens in new window", "").strip(),
                'Rink': cols[8].text.strip(),
                'GT': cols[9].text.strip()
            })
            game_list.append({'game_id': game_id, 'url': BOXSCORE_TEMPLATE.format(game_id=game_id)})
        except: continue

    save_manifest(manifest_data)
    return game_list

def save_manifest(new_data):
    """Appends new games to manifest, skipping duplicates."""
    if not new_data: return
    os.makedirs(DATA_DIR, exist_ok=True)
    # Filter out games we've already seen in previous runs
    if os.path.exists(MANIFEST_FILE):
        existing = pd.read_csv(MANIFEST_FILE)
        existing_ids = set(existing['GameID'].astype(str))
        new_data = [d for d in new_data if str(d['GameID']) not in existing_ids]

    if new_data:
        df = pd.DataFrame(new_data)
        # Append mode: only write header if file doesn't exist yet
        df.to_csv(MANIFEST_FILE, mode='a' if os.path.exists(MANIFEST_FILE) else 'w', 
                  header=not os.path.exists(MANIFEST_FILE), index=False)

def scrape_spoke(driver, game):
    """
    Spoke: Scrapes individual game boxscore pages.
    Uses XPath with aria-hidden guards to avoid mobile/hidden duplicate tables.
    """
    url, game_id = game['url'], game['game_id']
    print(f" ↳ Scraping Game {game_id}...", end=" ")
    driver.get(url)
    time.sleep(random.uniform(2, 4))  # Random delay to appear more human-like
    events, current_date = [], time.strftime("%Y-%m-%d")

    try:
        # 1. PERIOD SCORE: Final scores for standings calculation
        # [not(@aria-hidden='true')] ensures we get the visible desktop table, not hidden mobile version
        scores = driver.find_elements(By.XPATH, "//h3[text()='Scoring']/following::table[not(@aria-hidden='true')][1]//tr")
        for row in scores:
            cols = row.find_elements(By.TAG_NAME, "td")
            if len(cols) >= 5 and cols[0].text.strip():
                events.append({'GameID': game_id, 'EventType': 'PeriodScore', 'Period': 'Final', 'Team': cols[0].text.strip(), 'Description': cols[-1].text.strip(), 'ScrapedAt': current_date})

        # 2. THE 3 STARS
        stars = driver.find_elements(By.CLASS_NAME, "game-star")
        for star in stars:
            try:
                rank = star.find_element(By.CLASS_NAME, "bh-black").text.strip().replace('\n', ' ')
                name = star.find_element(By.CLASS_NAME, "name").text.strip()
                team = star.find_element(By.CLASS_NAME, "sh-black").text.strip()
                events.append({'GameID': game_id, 'EventType': 'Star', 'Period': rank, 'Team': team, 'Description': name, 'ScrapedAt': current_date})
            except: continue

        # 3. SCORING SUMMARY: Individual goal events with scorer/assists
        # The table-scroll div contains the actual data table (mobile has aria-hidden duplicate)
        goal_xpath = "//h3[text()='Scoring Summary']/following::div[contains(@class, 'table-scroll') and not(@aria-hidden='true')][1]//tbody/tr"
        goals = driver.find_elements(By.XPATH, goal_xpath)
        for row in goals:
            cols = row.find_elements(By.TAG_NAME, "td")
            # Guard: Skip empty/ghost rows that Selenium sometimes finds
            if len(cols) >= 6 and cols[1].text.strip() and cols[3].text.strip():
                events.append({'GameID': game_id, 'EventType': 'Goal', 'Period': cols[0].text.strip(), 'Time': cols[1].text.strip(), 'Strength': cols[2].text.strip(), 'Team': cols[3].text.strip(), 'Description': cols[4].text.strip(), 'ScoreState': cols[5].text.strip(), 'ScrapedAt': current_date})

        # 4. PENALTY SUMMARY: Penalty infractions
        pen_xpath = "//h3[text()='Penalty Summary']/following::div[contains(@class, 'table-scroll') and not(@aria-hidden='true')][1]//tbody/tr"
        pens = driver.find_elements(By.XPATH, pen_xpath)
        for row in pens:
            cols = row.find_elements(By.TAG_NAME, "td")
            if len(cols) >= 6 and cols[1].text.strip() and cols[3].text.strip():
                events.append({'GameID': game_id, 'EventType': 'Penalty', 'Period': cols[0].text.strip(), 'Time': cols[1].text.strip(), 'Team': cols[3].text.strip(), 'Description': cols[4].text.strip(), 'Strength': cols[5].text.strip(), 'ScrapedAt': current_date})

        # 5. OFFICIALS
        offics = driver.find_elements(By.XPATH, "//h3[text()='Officials']/following::table[not(@aria-hidden='true')][1]//tbody/tr")
        for row in offics:
            cols = row.find_elements(By.TAG_NAME, "td")
            if len(cols) >= 2 and cols[0].text.strip():
                events.append({'GameID': game_id, 'EventType': 'Official', 'Description': f"{cols[0].text.strip()}: {cols[1].text.strip()}", 'ScrapedAt': current_date})

    except Exception as e:
        print(f"⚠️ Error: {e}")
    
    print(f"Collected {len(events)} events.")
    return events

def save_new_events(new_data):
    """
    Enforces consistent schema across all event types.
    Some events (like Officials) don't have all columns, so we pad with None.
    """
    if not new_data: return
    df = pd.DataFrame(new_data)
    master_columns = ['GameID', 'EventType', 'Period', 'Time', 'Strength', 'Team', 'Description', 'ScoreState', 'ScrapedAt']
    # Ensure all columns exist (pad missing ones with None)
    for col in master_columns:
        if col not in df.columns: df[col] = None 
    df = df[master_columns]  # Reorder to consistent schema
    file_exists = os.path.exists(DETAILS_FILE)
    df.to_csv(DETAILS_FILE, mode='a', header=not file_exists, index=False)

def main():
    """
    Main orchestration: Hub-and-spoke pattern.
    1. Load existing game IDs to enable incremental scraping
    2. Scrape hub (schedule) to get list of all games
    3. Filter to only new games
    4. Scrape each game's boxscore (spoke)
    """
    os.makedirs(DATA_DIR, exist_ok=True)
    existing_ids = get_existing_game_ids()
    print(f"📚 History loaded. Found {len(existing_ids)} previously scraped games.")
    driver = setup_driver()
    try:
        all_games = scrape_hub(driver)  # Get manifest of all games
        games_to_scrape = [g for g in all_games if g['game_id'] not in existing_ids]  # Incremental: only new games
        if games_to_scrape:
            for i, game in enumerate(games_to_scrape):
                print(f"[{i+1}/{len(games_to_scrape)}]", end=" ")
                events = scrape_spoke(driver, game)  # Scrape individual boxscore
                if events: save_new_events(events)
        else:
            print("zzz No new games found.")
    finally:
        driver.quit()

if __name__ == "__main__":
    main()