"""
Human-in-the-Loop (HITL) Data Enrichment Module

This module provides an interactive Command Line Interface (CLI) for the League Commissioner 
to inject qualitative context (locker room narratives, momentum shifts, anomalies) into the 
quantitative dataset. This subjective data is later leveraged by the LLM to generate 
more nuanced and human-like reporting.
"""

import pandas as pd
import os
import shutil
from datetime import datetime
from typing import Any

# --- CONFIGURATION & FILE PATHS ---
MANIFEST_PATH = "data/games_manifest.csv"


def parse_hockey_date(date_str: Any) -> pd.Timestamp:
    """
    Normalizes truncated date strings (e.g., 'Wed Feb 25') into standard Pandas timestamp objects.
    Appends the current execution year to prevent temporal resolution errors in downstream processing.
    
    Args:
        date_str (Any): The raw, unformatted date string from the scraped manifest.
        
    Returns:
        pd.Timestamp: The normalized timestamp, or pd.NaT if parsing fails.
    """
    if pd.isna(date_str) or str(date_str).strip() == "":
        return pd.NaT
    
    clean_date = str(date_str).strip()
    current_year = datetime.now().year
    
    # Impute the current year if the scraped string lacks a 4-digit year identifier
    if not any(char.isdigit() for char in clean_date[-4:]):
        clean_date = f"{clean_date} {current_year}"
    
    try:
        # Utilize generic parsing to handle North American text formats (Month DD)
        return pd.to_datetime(clean_date, errors='coerce')
    except Exception:
        return pd.NaT


def enrich_games() -> None:
    """
    Executes the interactive enrichment loop.
    
    Flow:
    1. Creates an atomic backup of the target dataset.
    2. Validates schema integrity.
    3. Identifies records lacking qualitative metadata.
    4. Prompts the user sequentially for input.
    5. Executes a transactional commit upon user confirmation.
    """
    if not os.path.exists(MANIFEST_PATH):
        print("❌ Error: Manifest file not found. Ensure scraping pipeline has run.")
        return

    # --- PHASE 1: STATE PRESERVATION ---
    # Create an atomic backup to prevent data corruption during human data entry
    shutil.copy(MANIFEST_PATH, f"{MANIFEST_PATH}.bak")

    # Load dataset
    df = pd.read_csv(MANIFEST_PATH)
    
    # --- PHASE 2: SCHEMA VALIDATION & NORMALIZATION ---
    # Ensure the target column exists to prevent KeyError exceptions
    if 'Notes' not in df.columns:
        df['Notes'] = ""
    
    # Parse dates into a temporary series to allow for chronological sorting 
    # without mutating the underlying string format of the source CSV.
    df['_ParsedDate'] = df['Date'].apply(parse_hockey_date)
    
    # --- PHASE 3: QUEUE GENERATION ---
    # Filter for records where the qualitative data is null or an empty string
    mask = (df['Notes'].isna() | (df['Notes'] == ""))
    
    # Isolate pending records and sort them chronologically (oldest to newest)
    pending = df[mask].sort_values(by='_ParsedDate', ascending=True).copy()

    if pending.empty:
        print("✅ System Status: No pending games require enrichment.")
        # Cleanup temporary column before exiting
        df = df.drop(columns=['_ParsedDate'])
        return

    # --- PHASE 4: INTERACTIVE CLI LOOP ---
    print(f"🏒 COMMISSIONER PORTAL: {len(pending)} games awaiting insights.")
    print("Commands: Enter text to save, press Enter to skip, type 'exit' to quit.\n")

    for index, row in pending.iterrows():
        # Display contextual metadata to guide the user's input
        print(f"Matchup: {row['Home']} vs {row['Away']} ({row['Date']})")
        print(f"Details: {row['Score']} at {row['Facility']}")
        
        # Capture standard input
        note = input("✍️ Insight: ").strip()

        # Handle termination command
        if note.lower() == 'exit':
            break
        
        # Process input
        if note:
            df.at[index, 'Notes'] = note
            print("📝 Staged.")
        else:
            print("⏭️ Skipped.")
            
        print("-" * 30)

    # --- PHASE 5: TRANSACTIONAL COMMIT ---
    # Cleanup the temporary sorting column to maintain strict schema compliance
    df = df.drop(columns=['_ParsedDate'])

    # Require explicit confirmation before overwriting the source of truth
    confirm = input(f"\n💾 Save staged changes to manifest? (y/n): ").lower()
    
    if confirm == 'y':
        df.to_csv(MANIFEST_PATH, index=False)
        print("✅ Commit Successful: Manifest updated and saved.")
    else:
        print("🚫 Transaction Aborted: Save cancelled. Original data preserved.")


if __name__ == "__main__":
    enrich_games()