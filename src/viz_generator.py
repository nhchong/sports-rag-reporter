"""
Data Visualization Module

This module generates static, production-quality charts for the Jekyll front-end.
It ingests aggregated team statistics and produces a scatter plot analyzing 
league parity by comparing underlying performance (Goal Differential) against 
actual outcomes (Total Points).
"""

import pandas as pd
import matplotlib.pyplot as plt
import os

# --- CONFIGURATION & CONSTANTS ---
INPUT_FILE = "data/team_stats.csv"

# Route output directly to the Jekyll static assets directory for immediate deployment
OUTPUT_DIR = "docs/assets/images"
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "league_parity.png")

# Define entities to exclude from the visual analysis (e.g., mid-season drops, exhibition teams)
EXCLUDED_TEAMS = ["Arctic Dolphins", "Pdiym"]


def generate_parity_chart() -> None:
    """
    Executes the visualization pipeline.
    
    Flow:
    1. Validates the existence of the source dataset.
    2. Filters out explicitly excluded teams to prevent chart skew.
    3. Renders a quadrant-based scatter plot using Matplotlib.
    4. Archives the high-resolution artifact to the static web directory.
    """
    if not os.path.exists(INPUT_FILE):
        print(f"❌ Error: Source dataset not found at {INPUT_FILE}. Visualization aborted.")
        return

    # Ensure the destination directory architecture exists
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print("📊 Initializing League Parity Visualization...")
    df = pd.read_csv(INPUT_FILE)

    # --- PHASE 1: DATA FILTERING ---
    if EXCLUDED_TEAMS:
        print(f"📉 Applying exclusion filter for entities: {EXCLUDED_TEAMS}")
        # Retain only records where the team name is absent from the exclusion list
        df = df[~df['Team'].isin(EXCLUDED_TEAMS)].copy()
    
    if df.empty:
        print("⚠️ Warning: Dataset is empty post-filtering. Visualization aborted.")
        return

    # --- PHASE 2: COLUMN MAPPING ---
    # Dynamically map column names to ensure compatibility with the upstream analyzer output
    x_col = 'Diff' if 'Diff' in df.columns else 'Goal Differential'
    y_col = 'Pts' if 'Pts' in df.columns else 'Points'

    # --- PHASE 3: RENDERING & STYLING ---
    # Apply a clean, journalistic visual theme
    plt.style.use('seaborn-v0_8-whitegrid') 
    fig, ax = plt.subplots(figsize=(10, 6))

    # Render primary data points
    ax.scatter(
        df[x_col], 
        df[y_col], 
        color='#cc0000', # Primary brand accent color
        s=100,           # Marker radius
        alpha=0.8,       # Opacity layer for overlapping density
        edgecolor='black'
    )

    # Inject data labels for spatial context
    for _, row in df.iterrows():
        ax.annotate(
            row['Team'], 
            (row[x_col], row[y_col]),
            xytext=(5, 5), # Spatial offset to prevent marker occlusion
            textcoords='offset points',
            fontsize=9,
            fontweight='bold'
        )

    # Establish visual hierarchy and typographic structure
    ax.set_title("DMHL Division Parity: Performance vs. Results", fontsize=14, fontweight='bold', pad=20)
    ax.set_xlabel("Goal Differential (Underlying Performance)", fontsize=12, fontweight='bold')
    ax.set_ylabel("Total Points (Standings Outcomes)", fontsize=12, fontweight='bold')
    
    # Render quadrant boundaries to highlight over/under-performers
    # The horizontal line represents the league average points
    ax.axhline(y=df[y_col].mean(), color='grey', linestyle='--', alpha=0.5, linewidth=1)
    # The vertical line represents a neutral (0) goal differential
    ax.axvline(x=0, color='black', linewidth=1.5)

    # Optimize spatial layout
    plt.tight_layout()

    # --- PHASE 4: ARTIFACT EXPORT ---
    plt.savefig(OUTPUT_FILE, dpi=150, bbox_inches='tight')
    plt.close()
    
    print(f"✅ Rendering Complete: Visualization archived to {OUTPUT_FILE}")


if __name__ == "__main__":
    generate_parity_chart()