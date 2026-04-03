"""
Data Aggregation & Analytics Engine

This module serves as the primary ETL (Extract, Transform, Load) pipeline for the sports 
reporting system. It ingests raw, scraped play-by-play telemetry and normalizes it into 
structured, queryable datasets (Standings, Playoff Series, Player Leaderboards) that 
serve as the contextual baseline for the LLM reporting agent.
"""

import pandas as pd
import re
import os
from typing import Optional, Dict, Any

# --- CONFIGURATION & FILE PATHS ---
DETAILS_FILE = "data/game_details.csv"
TEAM_STATS_FILE = "data/team_stats.csv"
PLAYER_STATS_FILE = "data/player_stats.csv"
MANIFEST_FILE = "data/games_manifest.csv"
PLAYOFF_STATS_FILE = "data/playoff_standings.csv" 
PLAYOFF_MATCHUP_FILE = "data/playoff_matchups.csv"


# --- DATA NORMALIZATION & UTILITY HELPERS ---

def extract_pims_from_description(description: str) -> int:
    """
    Maps unstructured penalty string keywords to deterministic minute values.
    
    Args:
        description (str): Raw penalty description from the play-by-play data.
        
    Returns:
        int: Total penalty minutes (PIM) awarded.
    """
    desc = str(description).lower()
    if "double minor" in desc: return 4
    if "major" in desc: return 5
    if "misconduct" in desc: return 10
    if "minor" in desc: return 2
    return 0


def parse_integer_value(val: Any) -> int:
    """
    Defensively extracts the first integer from a string to handle dirty or 
    malformed scraped data (e.g., extracting '5' from '5 goals').
    
    Args:
        val (Any): The raw value to parse.
        
    Returns:
        int: The parsed integer, defaulting to 0 if parsing fails.
    """
    try:
        match = re.search(r'\d+', str(val))
        return int(match.group()) if match else 0
    except Exception:
        return 0


def initialize_game_data() -> Optional[pd.DataFrame]:
    """
    Loads and normalizes the master telemetry dataset.
    Standardizes casing and team names to ensure reliable programmatic joins.
    
    Returns:
        pd.DataFrame | None: The cleaned details dataframe, or None if the file is missing.
    """
    if not os.path.exists(DETAILS_FILE):
        return None
        
    df = pd.read_csv(DETAILS_FILE)
    df['GameID'] = df['GameID'].astype(str)
    
    # Normalize team names to Title Case and fix apostrophe edge cases for joins
    df['Team'] = df['Team'].fillna("Unknown").str.strip().str.title().replace("'S", "'s", regex=True)
    return df


# --- CORE ANALYTICS ENGINES ---

def compute_standings_engine(df: pd.DataFrame, manifest_subset: pd.DataFrame) -> pd.DataFrame:
    """
    Calculates cumulative league standings (W/L/T/Pts/GF/GA/PIM).
    
    Args:
        df (pd.DataFrame): The master play-by-play details dataframe.
        manifest_subset (pd.DataFrame): The filtered schedule (e.g., Regular Season only).
        
    Returns:
        pd.DataFrame: A fully ranked standings table sorted by Points, Wins, and Goal Diff.
    """
    teams = pd.concat([manifest_subset['Home'], manifest_subset['Away']]).unique()
    
    # Initialize standings dictionary (ignoring structural 'Bye' weeks)
    standings = {t: {'GP': 0, 'W': 0, 'L': 0, 'T': 0, 'Pts': 0, 'GF': 0, 'GA': 0, 'PIM': 0} 
                 for t in teams if "Bye" not in t}

    # Isolate the final score events to determine match outcomes
    finals = df[(df['EventType'] == 'PeriodScore') & (df['Period'] == 'Final')].copy()
    
    for _, game in manifest_subset.iterrows():
        gid = str(game['GameID'])
        game_results = finals[finals['GameID'] == gid]
        if len(game_results) < 2: 
            continue
        
        # Extract team names and final scores directly from the period events
        t1, t2 = game_results.iloc[0]['Team'], game_results.iloc[1]['Team']
        s1 = parse_integer_value(game_results.iloc[0]['Description'])
        s2 = parse_integer_value(game_results.iloc[1]['Description'])
        
        if t1 in standings and t2 in standings:
            # Update Games Played and Goal Totals
            standings[t1]['GP'] += 1
            standings[t2]['GP'] += 1
            standings[t1]['GF'] += s1
            standings[t1]['GA'] += s2
            standings[t2]['GF'] += s2
            standings[t2]['GA'] += s1

            # Apply standard 2-point system for results
            if s1 > s2:
                standings[t1]['W'] += 1; standings[t1]['Pts'] += 2; standings[t2]['L'] += 1
            elif s2 > s1:
                standings[t2]['W'] += 1; standings[t2]['Pts'] += 2; standings[t1]['L'] += 1
            else:
                standings[t1]['T'] += 1; standings[t1]['Pts'] += 1; standings[t2]['T'] += 1; standings[t2]['Pts'] += 1

    # Aggregate Penalty Minutes (PIMs) specifically for the games within this subset
    penalty_events = df[df['EventType'] == 'Penalty']
    subset_ids = set(manifest_subset['GameID'].astype(str))
    
    for _, row in penalty_events.iterrows():
        if row['Team'] in standings and row['GameID'] in subset_ids:
            standings[row['Team']]['PIM'] += extract_pims_from_description(row['Description'])

    # Convert dict to DataFrame and calculate tie-breakers (Goal Differential)
    std_df = pd.DataFrame.from_dict(standings, orient='index').reset_index().rename(columns={'index': 'Team'})
    std_df['Diff'] = std_df['GF'] - std_df['GA']
    std_df = std_df.sort_values(by=['Pts', 'W', 'Diff'], ascending=False).reset_index(drop=True)
    std_df.insert(0, 'Rk', range(1, len(std_df) + 1))
    
    return std_df


def compute_playoff_matchups(df: pd.DataFrame, po_manifest: pd.DataFrame) -> pd.DataFrame:
    """
    Aggregates individual playoff games into a 'Series Points' view.
    
    Matches are grouped by pairings to correctly calculate "Race to X" series totals, 
    abstracting away Home/Away status which fluctuates game-by-game.
    
    Args:
        df (pd.DataFrame): Master details dataframe.
        po_manifest (pd.DataFrame): The playoff-specific manifest subset.
        
    Returns:
        pd.DataFrame: A table mapping each series, the teams involved, and their cumulative points.
    """
    print("🏒 Calculating Playoff Series Points...")
    matchups = []
    
    # Create an agnostic pairing key (e.g., 'Team A-vs-Team B') to group multi-game series
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
            if len(res) < 2: 
                continue
            
            # Index scores by team name to prevent home/away assignment errors
            s1_val = res[res['Team'] == t1]['Description'].values
            s2_val = res[res['Team'] == t2]['Description'].values
            
            s1 = parse_integer_value(s1_val[0]) if len(s1_val) > 0 else 0
            s2 = parse_integer_value(s2_val[0]) if len(s2_val) > 0 else 0
            
            if s1 > s2: t1_pts += 2
            elif s2 > s1: t2_pts += 2
            else: t1_pts += 1; t2_pts += 1
            
        matchups.append({'Matchup': pairing, 'TeamA': t1, 'PtsA': t1_pts, 'TeamB': t2, 'PtsB': t2_pts})
    
    return pd.DataFrame(matchups)


def compute_player_statistics(df: pd.DataFrame) -> pd.DataFrame:
    """
    Parses play-by-play events to generate an individual player leaderboard.
    
    Extracts goals, assists, penalty minutes, and specific game contexts (Power Play, 
    Shorthanded, Game-Winning Goals) using regex parsing on raw event descriptions.
    
    Args:
        df (pd.DataFrame): Master details dataframe.
        
    Returns:
        pd.DataFrame: Comprehensive player statistics sorted by total points.
    """
    print("👤 Calculating Player Stats...")
    player_metrics = {}
    player_games = {} 

    # --- GWG (Game-Winning Goal) State Machine ---
    # A goal is the GWG if it is the goal that puts the winning team 
    # exactly one point ahead of the losing team's FINAL score.
    finals = df[(df['EventType'] == 'PeriodScore') & (df['Period'] == 'Final')].copy()
    game_winners = {} 
    
    for gid in finals['GameID'].unique():
        game_res = finals[finals['GameID'] == gid]
        if len(game_res) == 2:
            s1 = parse_integer_value(game_res.iloc[0]['Description'])
            s2 = parse_integer_value(game_res.iloc[1]['Description'])
            t1, t2 = game_res.iloc[0]['Team'], game_res.iloc[1]['Team']
            
            if s1 > s2:
                game_winners[gid] = {'winner': t1, 'gwg_number': s2 + 1}
            elif s2 > s1:
                game_winners[gid] = {'winner': t2, 'gwg_number': s1 + 1}

    def init_player(p_name: str, team: str):
        """Helper to initialize a player record in the metrics dictionary."""
        if p_name not in player_metrics:
            player_metrics[p_name] = {
                'Team': team, 'G': 0, 'A': 0, 'Pts': 0, 
                'PIM': 0, 'PPG': 0, 'SHG': 0, 'GWG': 0
            }
            player_games[p_name] = set()

    # Track Games Played via Roster Appearances
    for _, row in df[df['EventType'] == 'RosterAppearance'].iterrows():
        p_name, team, gid = row['Description'].strip(), row['Team'], row['GameID']
        init_player(p_name, team)
        player_games[p_name].add(gid)

    # Track running scores per game to correctly identify the GWG event
    running_scores = {}

    # Parse Scoring Events (Goals & Assists)
    for _, row in df[df['EventType'] == 'Goal'].iterrows():
        desc = row['Description']
        gid = row['GameID']
        team = row['Team']
        strength = str(row['Strength']).strip()
        
        # Increment running score state
        if gid not in running_scores: running_scores[gid] = {}
        if team not in running_scores[gid]: running_scores[gid][team] = 0
        running_scores[gid][team] += 1
        current_goal_num = running_scores[gid][team]

        # Extract Goal Scorer (Regex looks for Player Name before parentheses)
        scorer_match = re.search(r'#\d+\s+([^(:]+)', desc)
        if scorer_match:
            p_name = scorer_match.group(1).strip()
            init_player(p_name, team)
            
            player_metrics[p_name]['G'] += 1
            player_metrics[p_name]['Pts'] += 1
            
            # Special Teams Context
            if strength == 'PP': player_metrics[p_name]['PPG'] += 1
            if strength == 'SH': player_metrics[p_name]['SHG'] += 1
            
            # GWG Logic Evaluation
            if gid in game_winners and game_winners[gid]['winner'] == team and current_goal_num == game_winners[gid]['gwg_number']:
                player_metrics[p_name]['GWG'] += 1
            
            player_games[p_name].add(gid)

        # Extract Assistants (Regex pulls comma-separated names from within parentheses)
        assist_chunk = re.search(r'\((.*?)\)', desc)
        if assist_chunk:
            for raw in assist_chunk.group(1).split(','):
                a_match = re.search(r'#\d+\s+([^,]+)', raw)
                if a_match:
                    a_name = a_match.group(1).strip()
                    init_player(a_name, team)
                    
                    player_metrics[a_name]['A'] += 1
                    player_metrics[a_name]['Pts'] += 1
                    player_games[a_name].add(gid)

    # Parse Penalty Events
    for _, row in df[df['EventType'] == 'Penalty'].iterrows():
        desc, gid, team = row['Description'], row['GameID'], row['Team']
        name_match = re.search(r'#\d+\s+([^:]+)', desc)
        if name_match:
            p_name = name_match.group(1).strip()
            if p_name in player_metrics:
                player_metrics[p_name]['PIM'] += extract_pims_from_description(desc)
                player_games[p_name].add(gid)

    # Compile final structured payload
    stats = []
    for name, m in player_metrics.items():
        gp = len(player_games.get(name, set()))
        stats.append({
            'Player': name, 'Team': m['Team'], 'GP': gp, 
            'G': m['G'], 'A': m['A'], 'Pts': m['Pts'], 'PIM': m['PIM'],
            'PPG': m['PPG'], 'SHG': m['SHG'], 'GWG': m['GWG']
        })
    
    return pd.DataFrame(stats).sort_values(by='Pts', ascending=False)


def run_analysis_pipeline():
    """
    Main execution orchestrator.
    Cleans the schedule manifest, triggers calculations for regular season, 
    playoffs, and players, then archives the structured data to CSV.
    """
    print("🚀 Starting Data Analysis...")
    df = initialize_game_data()
    if df is None: 
        print("❌ Missing source telemetry. Analysis aborted.")
        return

    manifest_df = pd.read_csv(MANIFEST_FILE)
    
    # Ensure Notes column is present and strictly strings for downstream LLM safety
    if 'Notes' not in manifest_df.columns: 
        manifest_df['Notes'] = ""
    manifest_df['Notes'] = manifest_df['Notes'].fillna("")

    # Clean team names in manifest for consistent programmatic joining
    for col in ['Home', 'Away']:
        manifest_df[col] = manifest_df[col].str.strip().str.title().replace("'S", "'s", regex=True)

    # --- EXECUTION: Regular Season Standings ---
    rs_manifest = manifest_df[manifest_df['GameType'] == 'Regular Season']
    if not rs_manifest.empty:
        rs_standings = compute_standings_engine(df, rs_manifest)
        rs_standings.to_csv(TEAM_STATS_FILE, index=False)
        print(f"✅ Season stats archived.")

    # --- EXECUTION: Playoff Tracking ---
    po_manifest = manifest_df[manifest_df['GameType'] == 'Playoffs'].copy()
    if not po_manifest.empty:
        po_standings = compute_standings_engine(df, po_manifest)
        po_standings.to_csv(PLAYOFF_STATS_FILE, index=False)
        
        po_matchups = compute_playoff_matchups(df, po_manifest)
        po_matchups.to_csv(PLAYOFF_MATCHUP_FILE, index=False)
        print(f"✅ Playoff Ranked Table & Matchups archived.")

    # --- EXECUTION: Player Leaderboards ---
    player_stats = compute_player_statistics(df)
    player_stats.to_csv(PLAYER_STATS_FILE, index=False)
    print(f"✅ Player stats archived.")
    
    print(f"🏁 Analysis pipeline complete.")


if __name__ == "__main__":
    run_analysis_pipeline()