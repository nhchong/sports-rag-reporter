import pandas as pd
import re
import os

# --- FILE PATH CONFIGURATION ---
DETAILS_FILE = "data/game_details.csv"
TEAM_STATS_FILE = "data/team_stats.csv"
PLAYER_STATS_FILE = "data/player_stats.csv"

def extract_pims_from_description(description):
    """
    Parses penalty minutes from a text description using keyword mapping.
    
    Returns:
        int: The number of penalty minutes assigned.
    """
    desc = str(description).lower()
    if "double minor" in desc: return 4
    if "major" in desc: return 5
    if "misconduct" in desc: return 10
    if "minor" in desc: return 2
    return 0

def parse_integer_value(val):
    """
    Safely extracts an integer from a string using regex.
    Used for parsing scores and numeric data from messy text fields.
    """
    try:
        match = re.search(r'\d+', str(val))
        return int(match.group()) if match else 0
    except (ValueError, AttributeError):
        return 0

def initialize_game_data():
    """
    Loads raw game details from CSV and performs initial data cleaning.
    Ensures required columns exist and handles missing values.
    """
    try:
        if not os.path.exists(DETAILS_FILE):
             print(f"❌ Error: {DETAILS_FILE} not found. Ensure the scraper has run.")
             return None
        
        print(f"📖 Loading data from {DETAILS_FILE}...")
        df = pd.read_csv(DETAILS_FILE)
        
        # Verify master column structure
        master_cols = ['GameID', 'EventType', 'Team', 'Description', 'Strength', 'ScrapedAt', 'Period', 'Time']
        for col in master_cols:
            if col not in df.columns:
                df[col] = "N/A"
            
        # Data standardization
        df['Description'] = df['Description'].fillna("").astype(str)
        df['Team'] = df['Team'].fillna("Unknown")
        df['Strength'] = df['Strength'].fillna("0")
        df['GameID'] = df['GameID'].astype(str)
        
        return df
    except Exception as e:
        print(f"❌ Critical error loading data: {e}")
        return None

def compute_league_standings(df):
    """
    Calculates team standings, including W-L-T records, points, and goal differentials.
    
    Logic:
    - Primary: Uses 'PeriodScore' with 'Final' period labels.
    - Fallback: Reconstructs scores by aggregating 'Goal' events if score rows are missing.
    """
    print("🏆 Processing Team Standings...")
    
    # 1. ATTEMPT: Use official PeriodScore rows
    finals = df[(df['EventType'] == 'PeriodScore') & (df['Period'] == 'Final')].copy()
    
    # 2. FALLBACK: Aggregate Goal events if PeriodScore is absent
    if finals.empty:
        print("⚠️ Official scores missing. Calculating standings from Goal logs...")
        goals_df = df[df['EventType'] == 'Goal'].groupby(['GameID', 'Team']).size().reset_index(name='Score')
        finals = goals_df.rename(columns={'Score': 'Description'})

    standings = {}
    for game_id, game_data in finals.groupby('GameID'):
        teams = game_data['Team'].unique()
        if len(teams) < 2: continue
            
        t1, t2 = teams[0], teams[1]
        
        try:
            s1 = parse_integer_value(game_data[game_data['Team'] == t1].iloc[0]['Description'])
            s2 = parse_integer_value(game_data[game_data['Team'] == t2].iloc[0]['Description'])
        except (IndexError, KeyError): 
            continue

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

        # Record determination logic
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

    # Team-level PIM aggregation
    penalty_events = df[df['EventType'] == 'Penalty']
    for _, row in penalty_events.iterrows():
        team = row['Team']
        if team in standings:
            standings[team]['Penalty Minutes'] += extract_pims_from_description(row['Description'])

    if not standings: 
        print("❌ Data Warning: No standings generated. Check CSV for 'Goal' or 'PeriodScore' events.")
        return pd.DataFrame()

    # Post-processing and sorting
    std = pd.DataFrame.from_dict(standings, orient='index').reset_index().rename(columns={'index': 'Team'})
    std['Goal Differential'] = std['Goals For'] - std['Goals Against']
    std['Win Percentage'] = (std['Points'] / (std['Games Played'] * 2)).fillna(0).round(3)
    
    std = std.sort_values(by=['Points', 'Wins', 'Goal Differential'], ascending=False).reset_index(drop=True)
    std.index += 1
    std.insert(0, 'Rank', std.index)
    return std

def compute_team_efficiency_metrics(df, standings_df):
    """
    Calculates advanced team-level metrics like Power Play and Penalty Kill efficiency.
    """
    if standings_df.empty: return pd.DataFrame()
    print("📊 Calculating Special Teams efficiency...")
    metrics = []
    
    for _, row in standings_df.iterrows():
        team = row['Team']
        gp = row['Games Played']
        team_games = df[df['Team'] == team]['GameID'].unique()
        
        gfa = round(row['Goals For'] / gp, 2) if gp > 0 else 0.0
        
        # Power Play Percentage calculation
        ppg = len(df[(df['Team'] == team) & (df['EventType'] == 'Goal') & (df['Strength'] == 'PP')])
        pp_opps = len(df[(df['GameID'].isin(team_games)) & (df['Team'] != team) & (df['EventType'] == 'Penalty')])
        pp_pct = round((ppg / pp_opps) * 100, 1) if pp_opps > 0 else 0.0

        # Penalty Kill Percentage calculation
        ppga = len(df[(df['GameID'].isin(team_games)) & (df['Team'] != team) & (df['EventType'] == 'Goal') & (df['Strength'] == 'PP')])
        pk_opps = len(df[(df['Team'] == team) & (df['EventType'] == 'Penalty')])
        pk_pct = round(((pk_opps - ppga) / pk_opps) * 100, 1) if pk_opps > 0 else 0.0

        metrics.append({'Team': team, 'GFA': gfa, 'PP%': f"{pp_pct}%", 'PK%': f"{pk_pct}%"})
        
    return pd.DataFrame(metrics)

def identify_game_winning_goals(df):
    """
    Determines which goals were technically the 'Game Winning Goal' (GWG).
    Defined as the goal that put the winning team one goal ahead of the opponent's final total.
    """
    gwg_keys = []
    finals = df[(df['EventType'] == 'PeriodScore') & (df['Period'] == 'Final')]
    
    if finals.empty:
        finals = df[df['EventType'] == 'Goal'].groupby(['GameID', 'Team']).size().reset_index(name='Description')

    for game_id, game_data in finals.groupby('GameID'):
        if len(game_data) != 2: continue
        t1, t2 = game_data.iloc[0]['Team'], game_data.iloc[1]['Team']
        s1 = parse_integer_value(game_data.iloc[0]['Description'])
        s2 = parse_integer_value(game_data.iloc[1]['Description'])
        
        if s1 == s2: continue 
        
        winner = t1 if s1 > s2 else t2
        goal_num = (min(s1, s2) + 1)
        
        w_goals = df[(df['GameID'] == game_id) & (df['Team'] == winner) & (df['EventType'] == 'Goal')]
        w_goals = w_goals.sort_values(by=['Period', 'Time'], ascending=[True, False])
        
        if len(w_goals) >= goal_num:
            gwg_keys.append((game_id, w_goals.iloc[goal_num - 1]['Description']))
    return gwg_keys

def compute_player_statistics(df):
    """
    Aggregates individual player data including Points, PIMs, and Game-Winning Goals.
    Utilizes regex to extract player names and jersey numbers from event logs.
    """
    print("👤 Calculating Player Stats...")
    player_data = {}
    gwg_list = identify_game_winning_goals(df)
    
    # 1. Initialize Roster and GP
    roster_df = df[df['EventType'] == 'RosterAppearance']
    for _, row in roster_df.iterrows():
        name, team = row['Description'].strip(), row['Team']
        if name not in player_data:
            player_data[name] = {'Team': team, 'GP': 0, 'G': 0, 'A': 0, 'Pts': 0, 'PIM': 0, 'PPG': 0, 'SHG': 0, 'GWG': 0}
        player_data[name]['GP'] += 1

    # 2. Individual PIM Calculation
    penalty_events = df[df['EventType'] == 'Penalty']
    for _, row in penalty_events.iterrows():
        desc = row['Description']
        # Extract player name (skipping jersey number) before the colon
        name_match = re.search(r'#\d+\s+(.*?):', desc)
        
        if name_match:
            p_name = name_match.group(1).strip()
            if p_name in player_data:
                player_data[p_name]['PIM'] += extract_pims_from_description(desc)

    # 3. Individual Scoring Aggregation
    for _, row in df[df['EventType'] == 'Goal'].iterrows():
        desc, gid, strength = row['Description'], row['GameID'], row['Strength']
        
        # Scorer identification
        scorer_match = re.search(r'#\d+\s+([^(:]+)', desc)
        if scorer_match:
            p_name = scorer_match.group(1).strip()
            if p_name in player_data:
                p = player_data[p_name]
                p['G'] += 1
                p['Pts'] += 1
                if 'PP' in str(strength): p['PPG'] += 1
                if 'SH' in str(strength): p['SHG'] += 1
                if (gid, desc) in gwg_list: p['GWG'] += 1

        # Assist identification
        assist_chunk = re.search(r'\((.*?)\)', desc)
        if assist_chunk:
            for raw in assist_chunk.group(1).split(','):
                a_match = re.search(r'#\d+\s+([^,]+)', raw)
                if a_match:
                    a_name = a_match.group(1).strip()
                    if a_name in player_data:
                        player_data[a_name]['A'] += 1
                        player_data[a_name]['Pts'] += 1

    # 4. Final aggregation into sorted DataFrame
    stats = []
    for name, d in player_data.items():
        stats.append({
            'Player': name, 'Team': d['Team'], 'GP': d['GP'], 'G': d['G'], 'A': d['A'], 
            'Pts': d['Pts'], 'Pts/G': round(d['Pts']/d['GP'], 2) if d['GP'] > 0 else 0,
            'PIM': d['PIM'], 'PPG': d['PPG'], 'SHG': d['SHG'], 'GWG': d['GWG']
        })
    
    if not stats: return pd.DataFrame()
    return pd.DataFrame(stats).sort_values(by='Pts', ascending=False)

def run_analysis_pipeline():
    """
    Main entry point for the analysis script.
    Coordinates the loading of data and the generation of team and player statistics.
    """
    print("🚀 Starting Data Analysis...")
    df = initialize_game_data()
    if df is None: return

    standings = compute_league_standings(df)
    team_metrics = compute_team_efficiency_metrics(df, standings)
    
    # Save Team Stats
    if not standings.empty:
        if not team_metrics.empty:
            team_stats = standings.merge(team_metrics, on='Team', how='left')
        else:
            team_stats = standings
        team_stats.to_csv(TEAM_STATS_FILE, index=False)
        print(f"✅ Team stats archived: {TEAM_STATS_FILE}")
    
    # Save Player Stats
    player_stats = compute_player_statistics(df)
    if not player_stats.empty:
        player_stats.to_csv(PLAYER_STATS_FILE, index=False)
        print(f"✅ Player stats archived: {PLAYER_STATS_FILE}")
    
    print(f"🏁 Analysis pipeline complete.")

if __name__ == "__main__":
    run_analysis_pipeline()