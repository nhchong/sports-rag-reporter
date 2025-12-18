import pandas as pd
import re
import os

# --- CONFIGURATION ---
DETAILS_FILE = "data/game_details.csv"
MANIFEST_FILE = "data/games_manifest.csv"
STANDINGS_FILE = "data/standings.csv"

def load_data():
    """Loads raw data and handles basic null-value cleanup."""
    try:
        if not os.path.exists(DETAILS_FILE):
             print(f"❌ Error: {DETAILS_FILE} not found. Run scraper first.")
             return None
        
        df = pd.read_csv(DETAILS_FILE)
        df['Description'] = df['Description'].fillna("")
        df['Team'] = df['Team'].fillna("Unknown")
        # Ensure GameID is string for consistent grouping
        df['GameID'] = df['GameID'].astype(str)
        return df
    except Exception as e:
        print(f"❌ Error loading data: {e}")
        return None

def generate_standings(df):
    """
    Reconstructs league standings with full descriptive column names.
    Calculates stats chronologically to support Last 10 and Win/Loss Streaks.
    """
    # 1. Sort games by GameID to ensure chronological history
    finals = df[(df['EventType'] == 'PeriodScore') & (df['Period'] == 'Final')].copy()
    finals = finals.sort_values(by=['GameID'])

    standings = {}
    team_histories = {}

    for game_id, game_data in finals.groupby('GameID', sort=True):
        teams_in_game = game_data['Team'].unique()
        if len(teams_in_game) != 2: 
            continue
            
        t1, t2 = teams_in_game[0], teams_in_game[1]
        
        try:
            # Enhanced error handling for score parsing
            s1 = int(game_data[game_data['Team'] == t1].iloc[0]['Description'])
            s2 = int(game_data[game_data['Team'] == t2].iloc[0]['Description'])
        except (ValueError, IndexError): 
            continue

        for t in [t1, t2]:
            if t not in standings:
                standings[t] = {
                    'Games Played': 0, 'Wins': 0, 'Losses': 0, 'Ties': 0,
                    'Points': 0, 'Regulation Wins': 0, 'Goals For': 0,
                    'Goals Against': 0, 'Penalty Minutes': 0
                }
                team_histories[t] = []

        # Update core stats
        standings[t1]['Games Played'] += 1
        standings[t2]['Games Played'] += 1
        standings[t1]['Goals For'] += s1
        standings[t1]['Goals Against'] += s2
        standings[t2]['Goals For'] += s2
        standings[t2]['Goals Against'] += s1

        # Win/Loss/Tie Logic based on DMHL rules
        if s1 > s2:
            standings[t1]['Wins'] += 1
            standings[t1]['Regulation Wins'] += 1
            standings[t1]['Points'] += 2
            standings[t2]['Losses'] += 1
            team_histories[t1].append('W'); team_histories[t2].append('L')
        elif s2 > s1:
            standings[t2]['Wins'] += 1
            standings[t2]['Regulation Wins'] += 1
            standings[t2]['Points'] += 2
            standings[t1]['Losses'] += 1
            team_histories[t1].append('L'); team_histories[t2].append('W')
        else:
            standings[t1]['Ties'] += 1
            standings[t1]['Points'] += 1
            standings[t2]['Ties'] += 1
            standings[t2]['Points'] += 1
            team_histories[t1].append('T'); team_histories[t2].append('T')

    # 2. Add Penalty Minutes from event logs
    for _, row in df[df['EventType'] == 'Penalty'].iterrows():
        if row['Team'] in standings:
            try:
                # Safely extract minutes from 'M:SS' format
                standings[row['Team']]['Penalty Minutes'] += int(row['Strength'].split(':')[0])
            except (ValueError, AttributeError, IndexError): 
                pass

    # 3. Process Last 10 and Streaks
    l10_data = {}
    streak_data = {}
    for team, history in team_histories.items():
        recent_10 = history[-10:]
        l10_data[team] = f"{recent_10.count('W')}-{recent_10.count('L')}-{recent_10.count('T')}"
        if history:
            rev = list(reversed(history))
            curr = rev[0]
            count = 0
            for res in rev:
                if res == curr: count += 1
                else: break
            streak_data[team] = f"{curr}{count}"
        else:
            streak_data[team] = "-"

    # 4. Create DataFrame and Calculate Derived Columns
    std = pd.DataFrame.from_dict(standings, orient='index').reset_index()
    std = std.rename(columns={'index': 'Team'})
    std['Goal Differential'] = std['Goals For'] - std['Goals Against']
    std['Win Percentage'] = (std['Points'] / (std['Games Played'] * 2)).fillna(0).round(3)
    std['Last 10'] = std['Team'].map(l10_data)
    std['Streak'] = std['Team'].map(streak_data)

    # 5. DMHL Tie-breaker Sort: Points > Wins > Goal Differential
    std = std.sort_values(
        by=['Points', 'Wins', 'Goal Differential', 'Goals For'],
        ascending=False
    ).reset_index(drop=True)

    # 6. Final Polish
    std.index += 1
    std.insert(0, 'Rank', std.index)

    final_order = [
        'Rank', 'Team', 'Games Played', 'Wins', 'Losses', 'Ties', 'Points',
        'Win Percentage', 'Regulation Wins', 'Goals For', 'Goals Against',
        'Goal Differential', 'Penalty Minutes', 'Last 10', 'Streak'
    ]
    return std[final_order]

def get_player_stats(df, target_team):
    """Extracts goals and assists for a specific team."""
    goals = df[(df['EventType'] == 'Goal') & (df['Team'] == target_team)]
    stats = {}

    for _, row in goals.iterrows():
        desc = row['Description']
        # Scorer regex
        scorer_match = re.search(r'#\d+\s+([^(]+)', desc)
        if scorer_match:
            p = scorer_match.group(1).strip()
            if p not in stats: stats[p] = {'G': 0, 'A': 0, 'Pts': 0}
            stats[p]['G'] += 1
            stats[p]['Pts'] += 1
        # Assists regex
        assist_chunk = re.search(r'\((.*?)\)', desc)
        if assist_chunk:
            for raw in assist_chunk.group(1).split(','):
                a_match = re.search(r'#\d+\s+(.*)', raw)
                if a_match:
                    p = a_match.group(1).strip()
                    if "Spare" in p: continue
                    if p not in stats: stats[p] = {'G': 0, 'A': 0, 'Pts': 0}
                    stats[p]['A'] += 1
                    stats[p]['Pts'] += 1

    return pd.DataFrame.from_dict(stats, orient='index').reset_index().rename(columns={'index': 'Player'})

def main():
    print("📊 Generating League Standings...")
    df = load_data()
    if df is None: return

    # 1. Generate the data
    standings = generate_standings(df)
    
    # 2. Ensure data directory exists and save
    os.makedirs("data", exist_ok=True)
    standings.to_csv(STANDINGS_FILE, index=False)
    
    # 3. Output Preview
    print(f"✅ Standings successfully updated and saved to {STANDINGS_FILE}")
    print("\n🏆 DMHL STANDINGS PREVIEW:")
    print("=" * 140)
    pd.set_option('display.max_columns', None)
    pd.set_option('display.width', 1000)
    print(standings.to_string(index=False))
    print("=" * 140)

if __name__ == "__main__":
    main()