import pandas as pd
import re
import os

# --- CONFIGURATION ---
DETAILS_FILE = "data/game_details.csv"
TEAM_STATS_FILE = "data/team_stats.csv"
PLAYER_STATS_FILE = "data/player_stats.csv"

def calculate_pims_from_text(description):
    desc = str(description).lower()
    if "double minor" in desc: return 4
    if "major" in desc: return 5
    if "misconduct" in desc: return 10
    if "minor" in desc: return 2
    return 0

def safe_int(val):
    try:
        match = re.search(r'\d+', str(val))
        return int(match.group()) if match else 0
    except:
        return 0

def load_data():
    try:
        if not os.path.exists(DETAILS_FILE):
             print(f"❌ Error: {DETAILS_FILE} not found. Run scraper first.")
             return None
        
        print(f"📖 Loading data from {DETAILS_FILE}...")
        df = pd.read_csv(DETAILS_FILE)
        
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
    print("🏆 Processing Team Standings...")
    
    # 1. ATTEMPT: Use official PeriodScore rows
    finals = df[(df['EventType'] == 'PeriodScore') & (df['Period'] == 'Final')].copy()
    
    # 2. FALLBACK: Calculate scores from Goal events if PeriodScore is missing
    if finals.empty:
        print("⚠️ No official scores found. Calculating standings from Goal logs...")
        goals_df = df[df['EventType'] == 'Goal'].groupby(['GameID', 'Team']).size().reset_index(name='Score')
        # Format the fallback to match what the loop expects
        finals = goals_df.rename(columns={'Score': 'Description'})

    standings = {}
    for game_id, game_data in finals.groupby('GameID'):
        teams = game_data['Team'].unique()
        if len(teams) < 2: continue
            
        t1, t2 = teams[0], teams[1]
        
        try:
            # We use float/int conversion here to handle fallback vs original data
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

    penalty_events = df[df['EventType'] == 'Penalty']
    for _, row in penalty_events.iterrows():
        team = row['Team']
        if team in standings:
            standings[team]['Penalty Minutes'] += calculate_pims_from_text(row['Description'])

    if not standings: 
        print("❌ Still no standings generated. Verify CSV has 'Goal' or 'PeriodScore' rows.")
        return pd.DataFrame()

    std = pd.DataFrame.from_dict(standings, orient='index').reset_index().rename(columns={'index': 'Team'})
    std['Goal Differential'] = std['Goals For'] - std['Goals Against']
    std['Win Percentage'] = (std['Points'] / (std['Games Played'] * 2)).fillna(0).round(3)
    
    std = std.sort_values(by=['Points', 'Wins', 'Goal Differential'], ascending=False).reset_index(drop=True)
    std.index += 1
    std.insert(0, 'Rank', std.index)
    return std

def calculate_team_metrics(df, standings_df):
    if standings_df.empty: return pd.DataFrame()
    print("📊 Calculating Special Teams efficiency...")
    metrics = []
    
    for _, row in standings_df.iterrows():
        team = row['Team']
        gp = row['Games Played']
        team_games = df[df['Team'] == team]['GameID'].unique()
        
        gfa = round(row['Goals For'] / gp, 2) if gp > 0 else 0.0
        
        ppg = len(df[(df['Team'] == team) & (df['EventType'] == 'Goal') & (df['Strength'] == 'PP')])
        pp_opps = len(df[(df['GameID'].isin(team_games)) & (df['Team'] != team) & (df['EventType'] == 'Penalty')])
        pp_pct = round((ppg / pp_opps) * 100, 1) if pp_opps > 0 else 0.0

        ppga = len(df[(df['GameID'].isin(team_games)) & (df['Team'] != team) & (df['EventType'] == 'Goal') & (df['Strength'] == 'PP')])
        pk_opps = len(df[(df['Team'] == team) & (df['EventType'] == 'Penalty')])
        pk_pct = round(((pk_opps - ppga) / pk_opps) * 100, 1) if pk_opps > 0 else 0.0

        metrics.append({'Team': team, 'GFA': gfa, 'PP%': f"{pp_pct}%", 'PK%': f"{pk_pct}%"})
        
    return pd.DataFrame(metrics)

def find_game_winning_goals(df):
    gwg_keys = []
    # Note: GWG logic still relies on PeriodScore or Goals. 
    # Let's use the same logic here.
    finals = df[(df['EventType'] == 'PeriodScore') & (df['Period'] == 'Final')]
    if finals.empty:
        # Re-calc goals for GWG logic
        finals = df[df['EventType'] == 'Goal'].groupby(['GameID', 'Team']).size().reset_index(name='Description')

    for game_id, game_data in finals.groupby('GameID'):
        if len(game_data) != 2: continue
        t1, t2 = game_data.iloc[0]['Team'], game_data.iloc[1]['Team']
        s1 = safe_int(game_data.iloc[0]['Description'])
        s2 = safe_int(game_data.iloc[1]['Description'])
        if s1 == s2: continue 
        winner = t1 if s1 > s2 else t2
        goal_num = (min(s1, s2) + 1)
        w_goals = df[(df['GameID'] == game_id) & (df['Team'] == winner) & (df['EventType'] == 'Goal')]
        w_goals = w_goals.sort_values(by=['Period', 'Time'], ascending=[True, False])
        if len(w_goals) >= goal_num:
            gwg_keys.append((game_id, w_goals.iloc[goal_num - 1]['Description']))
    return gwg_keys

def calculate_player_stats(df):
    print("👤 Calculating Player Stats...")
    player_data = {}
    gwg_list = find_game_winning_goals(df)
    
    # 1. Initialize Roster & Games Played
    roster_df = df[df['EventType'] == 'RosterAppearance']
    for _, row in roster_df.iterrows():
        name, team = row['Description'].strip(), row['Team']
        if name not in player_data:
            player_data[name] = {'Team': team, 'GP': 0, 'G': 0, 'A': 0, 'Pts': 0, 'PIM': 0, 'PPG': 0, 'SHG': 0, 'GWG': 0}
        player_data[name]['GP'] += 1

    # 2. FIXED PIM CALCULATION
    penalty_events = df[df['EventType'] == 'Penalty']
    for _, row in penalty_events.iterrows():
        desc = row['Description']
        
        # NEW REGEX: Skips the '#' and number, grabs the name before the colon.
        # Pattern: "#8 Mitchell Moloney: Unsportsmanlike..." -> grabs "Mitchell Moloney"
        name_match = re.search(r'#\d+\s+(.*?):', desc)
        
        if name_match:
            p_name = name_match.group(1).strip()
            if p_name in player_data:
                # OPTIONAL: Extracting PIMs directly from (02:00 mins) is safer than keyword search
                # If you prefer to keep your calculate_pims_from_text, call it here.
                pims = calculate_pims_from_text(desc)
                player_data[p_name]['PIM'] += pims
            else:
                # Log this if a player gets a penalty but isn't in the RosterAppearance
                # Useful for identifying scraping gaps
                pass

    # 3. SCORING LOGIC
    for _, row in df[df['EventType'] == 'Goal'].iterrows():
        desc, gid, strength = row['Description'], row['GameID'], row['Strength']
        
        # Scorer regex: grabs name after jersey number
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

        # Assists logic
        assist_chunk = re.search(r'\((.*?)\)', desc)
        if assist_chunk:
            for raw in assist_chunk.group(1).split(','):
                a_match = re.search(r'#\d+\s+([^,]+)', raw)
                if a_match:
                    a_name = a_match.group(1).strip()
                    if a_name in player_data:
                        player_data[a_name]['A'] += 1
                        player_data[a_name]['Pts'] += 1

    # 4. Final Conversion
    stats = []
    for name, d in player_data.items():
        stats.append({
            'Player': name, 'Team': d['Team'], 'GP': d['GP'], 'G': d['G'], 'A': d['A'], 
            'Pts': d['Pts'], 'Pts/G': round(d['Pts']/d['GP'], 2) if d['GP'] > 0 else 0,
            'PIM': d['PIM'], 'PPG': d['PPG'], 'SHG': d['SHG'], 'GWG': d['GWG']
        })
    
    return pd.DataFrame(stats).sort_values(by='Pts', ascending=False)

def main():
    print("🚀 Starting Analysis...")
    df = load_data()
    if df is None: return

    standings = generate_standings_base(df)
    team_metrics = calculate_team_metrics(df, standings)
    
    if not standings.empty:
        if not team_metrics.empty:
            team_stats = standings.merge(team_metrics, on='Team', how='left')
        else:
            team_stats = standings
        team_stats.to_csv(TEAM_STATS_FILE, index=False)
        print(f"✅ Team stats saved to {TEAM_STATS_FILE}")
    
    player_stats = calculate_player_stats(df)
    if not player_stats.empty:
        player_stats.to_csv(PLAYER_STATS_FILE, index=False)
        print(f"✅ Player stats saved to {PLAYER_STATS_FILE}")
    print(f"🏁 Analytics complete.")

if __name__ == "__main__":
    main()