import pandas as pd
import re
import os

# --- FILE PATH CONFIGURATION ---
DETAILS_FILE = "data/game_details.csv"
TEAM_STATS_FILE = "data/team_stats.csv"
PLAYER_STATS_FILE = "data/player_stats.csv"
MANIFEST_FILE = "data/games_manifest.csv"
PLAYOFF_STATS_FILE = "data/playoff_standings.csv" 
PLAYOFF_MATCHUP_FILE = "data/playoff_matchups.csv"

# --- UTILITY HELPERS ---

def extract_pims_from_description(description):
    """Maps penalty string keywords to deterministic minute values."""
    desc = str(description).lower()
    if "double minor" in desc: return 4
    if "major" in desc: return 5
    if "misconduct" in desc: return 10
    if "minor" in desc: return 2
    return 0

def parse_integer_value(val):
    """Extracts the first integer from a string, safe for messy scraped data."""
    try:
        match = re.search(r'\d+', str(val))
        return int(match.group()) if match else 0
    except:
        return 0

def initialize_game_data():
    """Loads and cleans the master details file."""
    if not os.path.exists(DETAILS_FILE):
        return None
    df = pd.read_csv(DETAILS_FILE)
    df['GameID'] = df['GameID'].astype(str)
    # Ensure team names match manifest casing
    df['Team'] = df['Team'].fillna("Unknown").str.strip().str.title().replace("'S", "'s", regex=True)
    return df

# --- CORE ENGINES ---

def compute_standings_engine(df, manifest_subset):
    """Calculates full standings (W/L/T/Pts/GF/GA) for a specific subset of games."""
    teams = pd.concat([manifest_subset['Home'], manifest_subset['Away']]).unique()
    standings = {t: {'GP': 0, 'W': 0, 'L': 0, 'T': 0, 'Pts': 0, 'GF': 0, 'GA': 0, 'PIM': 0} for t in teams if "Bye" not in t}

    finals = df[(df['EventType'] == 'PeriodScore') & (df['Period'] == 'Final')].copy()
    
    for _, game in manifest_subset.iterrows():
        gid = str(game['GameID'])
        game_results = finals[finals['GameID'] == gid]
        if len(game_results) < 2: continue
        
        # We use the team names from the match events to determine winner/loser
        t1, t2 = game_results.iloc[0]['Team'], game_results.iloc[1]['Team']
        s1, s2 = parse_integer_value(game_results.iloc[0]['Description']), parse_integer_value(game_results.iloc[1]['Description'])
        
        if t1 in standings and t2 in standings:
            standings[t1]['GP'] += 1; standings[t2]['GP'] += 1
            standings[t1]['GF'] += s1; standings[t1]['GA'] += s2
            standings[t2]['GF'] += s2; standings[t2]['GA'] += s1

            if s1 > s2:
                standings[t1]['W'] += 1; standings[t1]['Pts'] += 2; standings[t2]['L'] += 1
            elif s2 > s1:
                standings[t2]['W'] += 1; standings[t2]['Pts'] += 2; standings[t1]['L'] += 1
            else:
                standings[t1]['T'] += 1; standings[t1]['Pts'] += 1; standings[t2]['T'] += 1; standings[t2]['Pts'] += 1

    # Apply PIMs only for games in this manifest subset
    penalty_events = df[df['EventType'] == 'Penalty']
    subset_ids = set(manifest_subset['GameID'].astype(str))
    for _, row in penalty_events.iterrows():
        if row['Team'] in standings and row['GameID'] in subset_ids:
            standings[row['Team']]['PIM'] += extract_pims_from_description(row['Description'])

    std_df = pd.DataFrame.from_dict(standings, orient='index').reset_index().rename(columns={'index': 'Team'})
    std_df['Diff'] = std_df['GF'] - std_df['GA']
    std_df = std_df.sort_values(by=['Pts', 'W', 'Diff'], ascending=False).reset_index(drop=True)
    std_df.insert(0, 'Rk', range(1, len(std_df) + 1))
    return std_df

def compute_playoff_matchups(df, po_manifest):
    """
    Groups playoff games by matchup to calculate 'Series Points' (Race to Three).
    Uses a temporary sorting logic to bridge Home/Away swaps without altering the source manifest.
    """
    print("🏒 Calculating Playoff Series Points...")
    matchups = []
    
    # We work on a COPY to preserve the integrity of the original manifest labels
    temp_po = po_manifest.copy()
    temp_po['Pairing'] = temp_po.apply(lambda x: "-vs-".join(sorted([x['Home'], x['Away']])), axis=1)
    
    finals = df[(df['EventType'] == 'PeriodScore') & (df['Period'] == 'Final')].copy()

    for pairing in temp_po['Pairing'].unique():
        series_games = temp_po[temp_po['Pairing'] == pairing]
        teams = pairing.split("-vs-")
        t1, t2 = teams[0], teams[1]
        
        t1_pts, t2_pts = 0, 0
        
        for _, game in series_games.iterrows():
            gid = str(game['GameID'])
            res = finals[finals['GameID'] == gid]
            if len(res) < 2: continue
            
            # Identify score by team name to ensure accuracy regardless of Home/Away status
            s1_val = res[res['Team'] == t1]['Description'].values
            s2_val = res[res['Team'] == t2]['Description'].values
            
            s1 = parse_integer_value(s1_val[0]) if len(s1_val) > 0 else 0
            s2 = parse_integer_value(s2_val[0]) if len(s2_val) > 0 else 0
            
            if s1 > s2: t1_pts += 2
            elif s2 > s1: t2_pts += 2
            else: t1_pts += 1; t2_pts += 1
            
        matchups.append({'Matchup': pairing, 'TeamA': t1, 'PtsA': t1_pts, 'TeamB': t2, 'PtsB': t2_pts})
    
    return pd.DataFrame(matchups)

def compute_player_statistics(df):
    """Analyzes individual performance across Goals, Assists, and individual PIMs."""
    print("👤 Calculating Player Stats...")
    player_metrics = {}
    player_games = {} 

    for _, row in df[df['EventType'] == 'RosterAppearance'].iterrows():
        p_name, team, gid = row['Description'].strip(), row['Team'], row['GameID']
        if p_name not in player_metrics:
            player_metrics[p_name] = {'Team': team, 'G': 0, 'A': 0, 'Pts': 0, 'PIM': 0}
            player_games[p_name] = set()
        player_games[p_name].add(gid)

    for _, row in df[df['EventType'] == 'Goal'].iterrows():
        desc, gid, team = row['Description'], row['GameID'], row['Team']
        scorer_match = re.search(r'#\d+\s+([^(:]+)', desc)
        if scorer_match:
            p_name = scorer_match.group(1).strip()
            if p_name not in player_metrics:
                player_metrics[p_name] = {'Team': team, 'G': 0, 'A': 0, 'Pts': 0, 'PIM': 0}
                player_games[p_name] = set()
            player_metrics[p_name]['G'] += 1
            player_metrics[p_name]['Pts'] += 1
            player_games[p_name].add(gid)

        assist_chunk = re.search(r'\((.*?)\)', desc)
        if assist_chunk:
            for raw in assist_chunk.group(1).split(','):
                a_match = re.search(r'#\d+\s+([^,]+)', raw)
                if a_match:
                    a_name = a_match.group(1).strip()
                    if a_name not in player_metrics:
                        player_metrics[a_name] = {'Team': team, 'G': 0, 'A': 0, 'Pts': 0, 'PIM': 0}
                        player_games[a_name] = set()
                    player_metrics[a_name]['A'] += 1
                    player_metrics[a_name]['Pts'] += 1
                    player_games[a_name].add(gid)

    for _, row in df[df['EventType'] == 'Penalty'].iterrows():
        desc, gid, team = row['Description'], row['GameID'], row['Team']
        name_match = re.search(r'#\d+\s+([^:]+)', desc)
        if name_match:
            p_name = name_match.group(1).strip()
            if p_name in player_metrics:
                player_metrics[p_name]['PIM'] += extract_pims_from_description(desc)
                player_games[p_name].add(gid)

    stats = []
    for name, m in player_metrics.items():
        gp = len(player_games.get(name, set()))
        stats.append({'Player': name, 'Team': m['Team'], 'GP': gp, 'G': m['G'], 'A': m['A'], 'Pts': m['Pts'], 'PIM': m['PIM']})
    
    return pd.DataFrame(stats).sort_values(by='Pts', ascending=False)

def run_analysis_pipeline():
    """Main execution flow: Cleans manifest, computes stats/matchups, and archives data."""
    print("🚀 Starting Data Analysis...")
    df = initialize_game_data()
    if df is None: return

    manifest_df = pd.read_csv(MANIFEST_FILE)
    
    # Ensure Notes column is present and sanitized
    if 'Notes' not in manifest_df.columns: manifest_df['Notes'] = ""
    manifest_df['Notes'] = manifest_df['Notes'].fillna("")

    # Clean team names for consistent joins
    for col in ['Home', 'Away']:
        manifest_df[col] = manifest_df[col].str.strip().str.title().replace("'S", "'s", regex=True)

    # 1. Season Stats
    rs_manifest = manifest_df[manifest_df['GameType'] == 'Regular Season']
    if not rs_manifest.empty:
        rs_standings = compute_standings_engine(df, rs_manifest)
        rs_standings.to_csv(TEAM_STATS_FILE, index=False)
        print(f"✅ Season stats archived.")

    # 2. Playoff Logic
    po_manifest = manifest_df[manifest_df['GameType'] == 'Playoffs'].copy()
    if not po_manifest.empty:
        po_standings = compute_standings_engine(df, po_manifest)
        po_standings.to_csv(PLAYOFF_STATS_FILE, index=False)
        
        po_matchups = compute_playoff_matchups(df, po_manifest)
        po_matchups.to_csv(PLAYOFF_MATCHUP_FILE, index=False)
        print(f"✅ Playoff Ranked Table & Matchups archived.")

    # 3. Player Leaderboard
    player_stats = compute_player_statistics(df)
    player_stats.to_csv(PLAYER_STATS_FILE, index=False)
    print(f"✅ Player stats archived.")
    
    print(f"🏁 Analysis pipeline complete.")

if __name__ == "__main__":
    run_analysis_pipeline()