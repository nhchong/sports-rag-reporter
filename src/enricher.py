import pandas as pd
import os
import shutil
from datetime import datetime

MANIFEST_PATH = "data/games_manifest.csv"

def parse_hockey_date(date_str):
    """
    Cleans and parses dates like 'Wed Feb 25'. 
    Appends the current year to prevent Pandas OutOfBounds errors.
    """
    if pd.isna(date_str) or str(date_str).strip() == "":
        return pd.NaT
    
    clean_date = str(date_str).strip()
    current_year = datetime.now().year
    
    # If the date string doesn't have a 4-digit year, append the current one
    if not any(char.isdigit() for char in clean_date[-4:]):
        clean_date = f"{clean_date} {current_year}"
    
    try:
        # 'day_first=False' handles North American style 'Feb 25'
        return pd.to_datetime(clean_date, errors='coerce')
    except:
        return pd.NaT

def enrich_games():
    """
    Human-in-the-Loop enrichment. 
    Uses status-based filtering to find games needing notes.
    """
    if not os.path.exists(MANIFEST_PATH):
        print("❌ Error: Manifest file not found.")
        return

    # 1. DEFENSIVE ENGINEERING: Atomic Backup
    shutil.copy(MANIFEST_PATH, f"{MANIFEST_PATH}.bak")

    df = pd.read_csv(MANIFEST_PATH)
    
    # 2. Ensure Notes column exists
    if 'Notes' not in df.columns:
        df['Notes'] = ""
    
    # 3. ROBUST PARSING: Fix the 'Overflow' bug
    # We create a temporary series for filtering so we don't mess up 
    # the original string formatting in the CSV
    parsed_dates = df['Date'].apply(parse_hockey_date)
    
    # 4. Filter: What is missing? (Status-based instead of Date-based)
    mask = (df['Notes'].isna() | (df['Notes'] == ""))
    pending = df[mask].copy()

    if pending.empty:
        print("✅ No pending games require enrichment.")
        return

    print(f"🏒 COMMISSIONER PORTAL: {len(pending)} games awaiting insights.")
    print("Commands: Enter text to save, press Enter to skip, type 'exit' to quit.\n")

    for index, row in pending.iterrows():
        # Display the human-readable date from the original CSV
        print(f"Matchup: {row['Home']} vs {row['Away']} ({row['Date']})")
        print(f"Details: {row['Score']} at {row['Facility']}")
        
        note = input("✍️ Insight: ").strip()

        if note.lower() == 'exit':
            break
        
        if note:
            df.at[index, 'Notes'] = note
            print("📝 Staged.")
        else:
            print("⏭️ Skipped.")
        print("-" * 30)

    # 5. TRANSACTIONAL COMMIT: Final Verification
    confirm = input(f"\n💾 Save changes to manifest? (y/n): ").lower()
    if confirm == 'y':
        df.to_csv(MANIFEST_PATH, index=False)
        print("✅ Manifest updated and saved.")
    else:
        print("🚫 Save cancelled. Original data preserved.")

if __name__ == "__main__":
    enrich_games()