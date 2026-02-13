import pandas as pd
import matplotlib.pyplot as plt
import os

# --- CONFIGURATION ---
INPUT_FILE = "data/team_stats.csv"
# Save directly to the Jekyll assets folder so it's live immediately
OUTPUT_DIR = "docs/assets/images"
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "league_parity.png")

# --- TEAMS TO EXCLUDE FROM VISUALIZATION ---
# Add exact team names here to hide them from the chart
EXCLUDED_TEAMS = ["Arctic Dolphins", "Pdiym"]

def generate_parity_chart():
    """
    Reads team stats and generates a professional scatter plot 
    visualizing Goal Differential vs. Total Points.
    """
    if not os.path.exists(INPUT_FILE):
        print("❌ Stats file not found. Skipping visualization.")
        return

    # Ensure output directory exists
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print("📊 Generating League Parity Chart...")
    df = pd.read_csv(INPUT_FILE)

    # --- FILTERING STEP ---
    if EXCLUDED_TEAMS:
        print(f"📉 Excluding teams from visualization: {EXCLUDED_TEAMS}")
        # Keep only rows where the team name is NOT in the excluded list
        # The tilde (~) operator negates the boolean condition
        df = df[~df['Team'].isin(EXCLUDED_TEAMS)].copy()
    
    if df.empty:
        print("⚠️ Warning: No data left to plot after filtering.")
        return

    # --- THE ATHLETIC STYLE SETUP ---
    plt.style.use('seaborn-v0_8-whitegrid') # A clean, professional base theme
    fig, ax = plt.subplots(figsize=(10, 6))

    # 1. Plot Data Points
    # Using a deep red for the points to match your theme accents
    ax.scatter(
        df['Goal Differential'], 
        df['Points'], 
        color='#cc0000', 
        s=100, # Size of dots
        alpha=0.8, # Slight transparency
        edgecolor='black'
    )

    # 2. Annotate Team Names
    # Loop through data to label each dot
    for i, row in df.iterrows():
        ax.annotate(
            row['Team'], 
            (row['Goal Differential'], row['Points']),
            xytext=(5, 5), # Offset text slightly up and right
            textcoords='offset points',
            fontsize=9,
            fontweight='bold'
        )

    # 3. Professional Styling & Context
    ax.set_title("DMHL Division Parity: Performance vs. Results", fontsize=14, fontweight='bold', pad=20)
    ax.set_xlabel("Goal Differential (The 'Actual' Performance)", fontsize=12, fontweight='bold')
    ax.set_ylabel("Total Points (The Standings)", fontsize=12, fontweight='bold')
    
    # Add strong zero lines to define the quadrants
    # Calculate mean only on the filtered data
    ax.axhline(y=df['Points'].mean(), color='grey', linestyle='--', alpha=0.5, linewidth=1)
    ax.axvline(x=0, color='black', linewidth=1.5)

    # Clean up layout
    plt.tight_layout()

    # 4. Save high-res image to docs folder
    plt.savefig(OUTPUT_FILE, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"✅ Visualization saved to: {OUTPUT_FILE}")

if __name__ == "__main__":
    generate_parity_chart()