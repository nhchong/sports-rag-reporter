import pandas as pd
import re
import os

# --- CONFIGURATION ---
DETAILS_FILE = "data/game_details.csv"
TEAM_STATS_FILE = "data/team_stats.csv"
PLAYER_STATS_FILE = "data/player_stats.csv"

def calculate_pims_from_text(description):
    """
    PM Decision: Rule-based translation logic.
    Converts human-readable infraction strings into numerical hockey minutes.
    """
    desc = str(description).lower()
    if "double minor" in desc: return 4
    if "major" in desc: return 5
    if "misconduct" in desc: return 10
    if "minor" in desc: return 2
    return 0

def safe_int(val):
    """Safely extracts an integer from a string, returns 0 if it fails."""
    try:
        match = re.search(r'\d+', str(val))
        return int(match.group()) if match else 0
    except:
        return 0

def load_data():
    """Loads raw data and enforces the 8-column Master Schema."""
    try:
        if not os.path.exists(DETAILS_FILE):
             print(f"❌ Error: {DETAILS_FILE} not found. Run scraper first.")
             return None
        
        print(f"📖 Loading data from {DETAILS_FILE}...")
        df = pd.read_csv(DETAILS_FILE)
        
        # SCHEMA ENFORCEMENT: Ensure all expected columns exist to prevent index errors
        master_cols = ['GameID', 'EventType', 'Team', 'Description', 'Strength', 'ScrapedAt', 'Period', 'Time']
        for col in master_cols:
            if col not in df.columns:
                df[col] = "N/A"
            
        df['Description'] = df['Description'].fillna("").astype(str)
        df['Team'] = df['Team'].fillna("Unknown")
        df['Strength'] = df['Strength'].fillna("0")
        df['GameID'] = df['GameID'].astype(str)
        
        return df
    except Exception as e:
        print(f"❌ Error loading data: {e}")
        return None

def generate_standings_base(df):
    """Reconstructs league standings using granular event logs."""
    print("🏆 Processing Team Standings...")
    # Filter for the official final scores
    finals = df[(df['EventType'] == 'PeriodScore') & (df['Period'] == 'Final')].copy()
    
    standings = {}
    for game_id, game_data in finals.groupby('GameID'):
        teams = game_data['Team'].unique()
        if len(teams) < 2: continue
            
        t1, t2 = teams[0], teams[1]
        
        # Get scores for both teams
        try:
            s1 = safe_int(game_data[game_data['Team'] == t1].iloc[0]['Description'])
            s2 = safe_int(game_data[game_data['Team'] == t2].iloc[0]['Description'])
        except: continue

        for t in [t1, t2]:
            if t not in standings:
                standings[t] = {'Games Played': 0, 'Wins': 0, 'Losses': 0, 'Ties': 0, 'Points': 0, 
                                'Goals For': 0, 'Goals Against': 0, 'Penalty Minutes': 0}

        standings[t1]['Games Played'] += 1
        standings[t2]['Games Played'] += 1
        standings[t1]['Goals For'] += s1
        standings[t1]['Goals Against'] += s2
        standings[t2]['Goals For'] += s2
        standings[t2]['Goals Against'] += s1

        if s1 > s2:
            standings[t1]['Wins'] += 1
            standings[t1]['Points'] += 2
            standings[t2]['Losses'] += 1
        elif s2 > s1:
            standings[t2]['Wins'] += 1
            standings[t2]['Points'] += 2
            standings[t1]['Losses'] += 1
        else:
            standings[t1]['Ties'] += 1
            standings[t1]['Points'] += 1
            standings[t2]['Ties'] += 1
            standings[t2]['Points'] += 1

    # PM FIX: Calculate PIMs from specific 'Penalty' events for 100% accuracy
    penalty_events = df[df['EventType'] == 'Penalty']
    for _, row in penalty_events.iterrows():
        team = row['Team']
        if team in standings:
            standings[team]['Penalty Minutes'] += calculate_pims_from_text(row['Description'])

    if not standings: return pd.DataFrame()

    std = pd.DataFrame.from_dict(standings, orient='index').reset_index().rename(columns={'index': 'Team'})
    std['Goal Differential'] = std['Goals For'] - std['Goals Against']
    std['Win Percentage'] = (std['Points'] / (std['Games Played'] * 2)).fillna(0).round(3)
    
    # Standard Hockey Standings sorting: Points > Wins > GD
    std = std.sort_values(by=['Points', 'Wins', 'Goal Differential'], ascending=False).reset_index(drop=True)
    std.index += 1
    std.insert(0, 'Rank', std.index)
    return std

def calculate_team_metrics(df, standings_df):
    """Calculates Special Teams efficiency (PP% and PK%)."""
    if standings_df.empty: return pd.DataFrame()
    print("📊 Calculating Special Teams efficiency...")
    metrics = []
    
    for _, row in standings_df.iterrows():
        team = row['Team']
        gp = row['Games Played']
        team_games = df[df['Team'] == team]['GameID'].unique()
        
        gfa = round(row['Goals For'] / gp, 2) if gp > 0 else 0.0
        
        # Power Play: Your goals scored while on PP / Opponent penalties
        ppg = len(df[(df['Team'] == team) & (df['EventType'] == 'Goal') & (df['Strength'] == 'PP')])
        pp_opps = len(df[(df['GameID'].isin(team_games)) & (df['Team'] != team) & (df['EventType'] == 'Penalty')])
        pp_pct = round((ppg / pp_opps) * 100, 1) if pp_opps > 0 else 0.0

        # Penalty Kill: 1 - (Goals conceded while SH / Your penalties)
        ppga = len(df[(df['GameID'].isin(team_games)) & (df['Team'] != team) & (df['EventType'] == 'Goal') & (df['Strength'] == 'PP')])
        pk_opps = len(df[(df['Team'] == team) & (df['EventType'] == 'Penalty')])
        pk_pct = round(((pk_opps - ppga) / pk_opps) * 100, 1) if pk_opps > 0 else 0.0

        metrics.append({'Team': team, 'GFA': gfa, 'PP%': f"{pp_pct}%", 'PK%': f"{pk_pct}%"})
        
    return pd.DataFrame(metrics)

def find_game_winning_goals(df):
    """Identifies game-winning goal scorers based on chronologically ordered goals."""
    gwg_keys = []
    finals = df[(df['EventType'] == 'PeriodScore') & (df['Period'] == 'Final')]
    
    for game_id, game_data in finals.groupby('GameID'):
        if len(game_data) != 2: continue
        
        t1, t2 = game_data.iloc[0]['Team'], game_data.iloc[1]['Team']
        s1 = safe_int(game_data.iloc[0]['Description'])
        s2 = safe_int(game_data.iloc[1]['Description'])
        
        if s1 == s2: continue 
        
        winner = t1 if s1 > s2 else t2
        goal_num = (min(s1, s2) + 1)
        
        w_goals = df[(df['GameID'] == game_id) & (df['Team'] == winner) & (df['EventType'] == 'Goal')]
        # Sort by Period then Time to find the specific goal that broke the opponent's maximum score
        w_goals = w_goals.sort_values(by=['Period', 'Time'], ascending=[True, False])
        
        if len(w_goals) >= goal_num:
            gwg_keys.append((game_id, w_goals.iloc[goal_num - 1]['Description']))
            
    return gwg_keys

def calculate_player_stats(df):
    """Aggregates individual player leaderboards from Roster and Goal logs."""
    print("👤 Calculating Player Stats...")
    player_data = {}
    gwg_list = find_game_winning_goals(df)

    # 1. Base Stats (GP and Season PIMs from Roster)
    roster_df = df[df['EventType'] == 'RosterAppearance']
    for _, row in roster_df.iterrows():
        name, team = row['Description'].strip(), row['Team']
        if name not in player_data:
            player_data[name] = {'Team': team, 'GP': 0, 'G': 0, 'A': 0, 'Pts': 0, 'PIM': 0, 'PPG': 0, 'SHG': 0, 'GWG': 0}
        player_data[name]['GP'] += 1
        # Use strength column for Roster PIMs (if available)
        player_data[name]['PIM'] += safe_int(row['Strength'])

    # 2. Offensive Stats from Goal logs
    for _, row in df[df['EventType'] == 'Goal'].iterrows():
        desc, gid, strength = row['Description'], row['GameID'], row['Strength']
        
        # Extract Scorer
        scorer_match = re.search(r'#\d+\s+([^(]+)', desc)
        if scorer_match:
            p_name = scorer_match.group(1).strip()
            if p_name in player_data:
                p = player_data[p_name]
                p['G'] += 1; p['Pts'] += 1
                if 'PP' in str(strength): p['PPG'] += 1
                if 'SH' in str(strength): p['SHG'] += 1
                if (gid, desc) in gwg_list: p['GWG'] += 1

        # Extract Assists
        assist_chunk = re.search(r'\((.*?)\)', desc)
        if assist_chunk:
            for raw in assist_chunk.group(1).split(','):
                a_match = re.search(r'#\d+\s+(.*)', raw)
                if a_match:
                    a_name = a_match.group(1).strip()
                    if a_name in player_data:
                        player_data[a_name]['A'] += 1; player_data[a_name]['Pts'] += 1

    stats = []
    for name, d in player_data.items():
        stats.append({
            'Player': name, 'Team': d['Team'], 'GP': d['GP'], 'G': d['G'], 'A': d['A'], 
            'Pts': d['Pts'], 'Pts/G': round(d['Pts']/d['GP'], 2) if d['GP'] > 0 else 0,
            'PIM': d['PIM'], 'PPG': d['PPG'], 'SHG': d['SHG'], 'GWG': d['GWG']
        })
    
    if not stats: return pd.DataFrame()
    return pd.DataFrame(stats).sort_values(by='Pts', ascending=False)

def main():
    print("🚀 Starting Analysis...")
    df = load_data()
    if df is None: return

    # Generate Standings
    standings = generate_standings_base(df)
    
    # Add Efficiency Metrics
    team_metrics = calculate_team_metrics(df, standings)
    
    if not standings.empty:
        if not team_metrics.empty:
            team_stats = standings.merge(team_metrics, on='Team', how='left')
        else:
            team_stats = standings
        team_stats.to_csv(TEAM_STATS_FILE, index=False)
        print(f"✅ Team stats saved to {TEAM_STATS_FILE}")
    
    # Generate Player Leaderboard
    player_stats = calculate_player_stats(df)
    if not player_stats.empty:
        player_stats.to_csv(PLAYER_STATS_FILE, index=False)
        print(f"✅ Player stats saved to {PLAYER_STATS_FILE}")

    print(f"🏁 Analytics complete. System ready for reporting.")

if __name__ == "__main__":
    main()